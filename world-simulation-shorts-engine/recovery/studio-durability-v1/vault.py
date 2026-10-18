"""Authenticated, bounded-memory durable objects; never export key material.

The separate recovery key authenticates private checkpoints after local state
loss. Shared hashes alone are never accepted as NVIDIA/cache provenance.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from stores import BackupError, Conflict, NotFound, OID, MAX_OBJECT, _directory, read_private_file

CHUNK_BYTES = MAX_OBJECT - 1024
MAX_CHUNKS = 16384
MAX_FILE_BYTES = CHUNK_BYTES * MAX_CHUNKS
MAX_MANIFEST_BYTES = 8 * 1024**2
_SCHEMA = b'WORLD_ENGINE_DURABILITY_OBJECT_V1\0'


def read_key_file(path):
    raw = read_private_file(path, limit=128)
    try:
        text = raw.decode('ascii').strip()
        key = base64.b64decode(text.encode('ascii'), altchars=b'-_', validate=True)
    except (UnicodeError, ValueError, binascii.Error):
        raise BackupError('DURABILITY_KEY_FORMAT_INVALID') from None
    if len(key) != 32 or base64.urlsafe_b64encode(key).decode('ascii') != text:
        raise BackupError('DURABILITY_KEY_32_BYTES_REQUIRED')
    return key


def _json_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise BackupError('DURABILITY_MANIFEST_JSON_INVALID') from None


def _json_load(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise BackupError('DURABILITY_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    try:
        result = json.loads(body, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(BackupError('DURABILITY_NONFINITE_JSON')))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BackupError('DURABILITY_MANIFEST_JSON_INVALID') from None
    if not isinstance(result, dict):
        raise BackupError('DURABILITY_MANIFEST_OBJECT_REQUIRED')
    return result


def _descriptor(value):
    if (not isinstance(value, dict) or set(value) != {'sha256', 'bytes', 'chunks'}
            or not isinstance(value['sha256'], str) or not OID.fullmatch(value['sha256'])
            or type(value['bytes']) is not int or not 0 <= value['bytes'] <= MAX_FILE_BYTES
            or not isinstance(value['chunks'], list) or len(value['chunks']) > MAX_CHUNKS
            or any(not isinstance(oid, str) or not OID.fullmatch(oid) for oid in value['chunks'])
            or len(value['chunks']) != (value['bytes'] + CHUNK_BYTES - 1) // CHUNK_BYTES):
        raise BackupError('DURABILITY_DESCRIPTOR_INVALID')
    return value


class Vault:
    def __init__(self, key32bytes, store):
        if not isinstance(key32bytes, bytes) or len(key32bytes) != 32:
            raise BackupError('DURABILITY_KEY_32_BYTES_REQUIRED')
        if not callable(getattr(store, 'get', None)) or not callable(getattr(store, 'put', None)):
            raise BackupError('DURABILITY_STORE_REQUIRED')
        material = HKDF(algorithm=hashes.SHA256(), length=64,
                        salt=b'WORLD_ENGINE_DURABILITY_HKDF_V1',
                        info=b'encryption-and-private-object-addressing').derive(key32bytes)
        self._cipher = AESGCM(material[:32])
        self._address_key = material[32:]
        self.store = store

    def _object_id(self, kind, plaintext):
        return hmac.new(self._address_key, _SCHEMA + kind + plaintext, hashlib.sha256).hexdigest()

    def _decrypt(self, oid, kind, envelope):
        if (not isinstance(oid, str) or not OID.fullmatch(oid) or kind not in {b'C', b'M'}
                or not isinstance(envelope, bytes) or not 33 <= len(envelope) <= MAX_OBJECT
                or envelope[:5] != b'WED1' + kind):
            raise BackupError('DURABILITY_AUTHENTICATED_OBJECT_REQUIRED')
        nonce = envelope[5:17]
        try:
            plaintext = self._cipher.decrypt(nonce, envelope[17:], _SCHEMA + kind + oid.encode('ascii'))
        except (InvalidTag, ValueError):
            raise BackupError('DURABILITY_OBJECT_AUTHENTICATION_FAILED') from None
        if not hmac.compare_digest(oid, self._object_id(kind, plaintext)):
            raise BackupError('DURABILITY_OBJECT_ADDRESS_MISMATCH')
        return plaintext

    def _get_object(self, oid, kind):
        return self._decrypt(oid, kind, self.store.get(oid))

    def _put_object(self, kind, plaintext):
        if not isinstance(plaintext, bytes) or len(plaintext) > CHUNK_BYTES:
            raise BackupError('DURABILITY_PLAINTEXT_CHUNK_TOO_LARGE')
        oid = self._object_id(kind, plaintext)
        try:
            existing = self._get_object(oid, kind)
        except NotFound:
            nonce = os.urandom(12)
            envelope = b'WED1' + kind + nonce + self._cipher.encrypt(
                nonce, plaintext, _SCHEMA + kind + oid.encode('ascii'))
            try:
                self.store.put(oid, envelope)
            except Conflict:
                # Another writer may have sealed identical plaintext with a
                # different random nonce. Authenticate rather than overwrite.
                pass
            existing = self._get_object(oid, kind)
        if not hmac.compare_digest(existing, plaintext):
            raise BackupError('DURABILITY_EXISTING_OBJECT_PLAINTEXT_MISMATCH')
        return oid

    def put_bytes(self, data):
        if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
            raise BackupError('DURABILITY_BYTES_INVALID')
        chunks = [self._put_object(b'C', data[i:i + CHUNK_BYTES]) for i in range(0, len(data), CHUNK_BYTES)]
        return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'chunks': chunks}

    def put_file(self, path, expected_sha=None):
        path = Path(path)
        directory = fd = None
        try:
            directory = _directory(path.parent)
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_uid != 1000 or stat.S_IMODE(before.st_mode) != 0o600
                    or not 0 <= before.st_size <= MAX_FILE_BYTES):
                raise BackupError('DURABILITY_PRIVATE_SOURCE_REQUIRED')
            if expected_sha is not None and (not isinstance(expected_sha, str) or not OID.fullmatch(expected_sha)):
                raise BackupError('DURABILITY_EXPECTED_HASH_INVALID')
            digest, count, chunks = hashlib.sha256(), 0, []
            while True:
                block = bytearray()
                while len(block) < CHUNK_BYTES:
                    row = os.read(fd, CHUNK_BYTES - len(block))
                    if not row:
                        break
                    block.extend(row)
                if not block:
                    break
                count += len(block)
                if count > before.st_size or len(chunks) >= MAX_CHUNKS:
                    raise BackupError('DURABILITY_SOURCE_CHANGED')
                raw = bytes(block)
                digest.update(raw)
                chunks.append(self._put_object(b'C', raw))
            after = os.fstat(fd)
            current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            facts = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
            actual = digest.hexdigest()
            if (facts(before) != facts(after) or facts(current) != facts(after) or count != before.st_size
                    or (expected_sha is not None and not hmac.compare_digest(actual, expected_sha))):
                raise BackupError('DURABILITY_SOURCE_HASH_OR_IDENTITY_MISMATCH')
            return {'sha256': actual, 'bytes': count, 'chunks': chunks}
        except BackupError:
            raise
        except OSError:
            raise BackupError('DURABILITY_SOURCE_READ_FAILED') from None
        finally:
            for item in (fd, directory):
                if item is not None:
                    os.close(item)

    def _blocks(self, descriptor):
        descriptor = _descriptor(descriptor)
        digest, count = hashlib.sha256(), 0
        for index, oid in enumerate(descriptor['chunks']):
            block = self._get_object(oid, b'C')
            expected = min(CHUNK_BYTES, descriptor['bytes'] - index * CHUNK_BYTES)
            if len(block) != expected:
                raise BackupError('DURABILITY_CHUNK_LENGTH_MISMATCH')
            count += len(block)
            digest.update(block)
            yield block
        if count != descriptor['bytes'] or not hmac.compare_digest(digest.hexdigest(), descriptor['sha256']):
            raise BackupError('DURABILITY_DESCRIPTOR_HASH_MISMATCH')

    def get_bytes(self, descriptor, limit=MAX_MANIFEST_BYTES):
        _descriptor(descriptor)
        if type(limit) is not int or not 0 <= limit <= MAX_MANIFEST_BYTES or descriptor['bytes'] > limit:
            raise BackupError('DURABILITY_IN_MEMORY_LIMIT_EXCEEDED')
        return b''.join(self._blocks(descriptor))

    def verify_descriptor(self, descriptor):
        for _ in self._blocks(descriptor):
            pass
        return True

    def restore_file(self, descriptor, dest):
        _descriptor(descriptor)
        dest = Path(dest)
        directory = fd = None
        try:
            directory = _directory(dest.parent)
            parent = os.fstat(directory)
            if parent.st_uid != 1000 or stat.S_IMODE(parent.st_mode) != 0o700:
                raise BackupError('DURABILITY_PRIVATE_DESTINATION_REQUIRED')
            fd = os.open(dest.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            for block in self._blocks(descriptor):
                view = memoryview(block)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise BackupError('DURABILITY_RESTORE_WRITE_FAILED')
                    view = view[written:]
            os.fsync(fd)
            os.fsync(directory)
            return descriptor
        except BaseException as error:
            if fd is not None and directory is not None:
                # Remove only this operation's newly created incomplete file.
                try:
                    held, current = os.fstat(fd), os.stat(dest.name, dir_fd=directory, follow_symlinks=False)
                    if (held.st_dev, held.st_ino) == (current.st_dev, current.st_ino):
                        os.unlink(dest.name, dir_fd=directory)
                except OSError:
                    pass
            if isinstance(error, BackupError):
                raise
            if isinstance(error, OSError):
                raise BackupError('DURABILITY_RESTORE_FAILED') from None
            raise
        finally:
            for item in (fd, directory):
                if item is not None:
                    os.close(item)

    def save_manifest(self, manifest):
        if not isinstance(manifest, dict):
            raise BackupError('DURABILITY_MANIFEST_OBJECT_REQUIRED')
        raw = _json_bytes(manifest)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise BackupError('DURABILITY_MANIFEST_TOO_LARGE')
        descriptor = self.put_bytes(raw)
        # The root seal authenticates the complete ordered chunk descriptor.
        root = _json_bytes({'schema': 'WORLD_ENGINE_ENCRYPTED_MANIFEST_V1', 'content': descriptor})
        return self._put_object(b'M', root)

    def load_manifest(self, checkpoint_id):
        root = _json_load(self._get_object(checkpoint_id, b'M'))
        if set(root) != {'schema', 'content'} or root['schema'] != 'WORLD_ENGINE_ENCRYPTED_MANIFEST_V1':
            raise BackupError('DURABILITY_ROOT_MANIFEST_INVALID')
        return _json_load(self.get_bytes(root['content']))

    def publish_receipt(self, receipt_manifest):
        """Publish encrypted receipt only after its root has authenticated."""
        receipt_id = self.save_manifest(receipt_manifest)
        if self.load_manifest(receipt_id) != receipt_manifest:
            raise BackupError('DURABILITY_RECEIPT_READBACK_FAILED')
        self.store.publish_receipt(receipt_id)
        return receipt_id

    def list_receipts(self, limit=256):
        """Opaque discovery followed by full AEAD authentication, never guesses."""
        return [{'receiptId': oid, 'manifest': self.load_manifest(oid)}
                for oid in self.store.list_receipts(limit=limit)]
