"""Real AEAD/local filesystem tests and explicitly fake Dropbox HTTP tests."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stores import BackupError, Conflict, DropboxStore, MAX_OBJECT, MountedStore, NotFound
from vault import CHUNK_BYTES, Vault, read_key_file


class Response:
    status = 200

    def __init__(self, url, body):
        self.url, self.body = url, body

    def geturl(self):
        return self.url

    def read(self, count):
        return self.body[:count]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class FakeDropboxHTTP:
    """No external request: mimics bounded official API responses."""
    def __init__(self):
        self.objects, self.folders, self.calls = {}, set(), []
        self.failure = None
        self.list_override = None

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        if self.failure is not None:
            raise self.failure
        url = request.full_url
        if url.endswith('/list_folder') or url.endswith('/list_folder/continue'):
            argument = json.loads(request.data)
            if self.list_override is not None:
                return Response(url, json.dumps(self.list_override).encode())
            if 'cursor' in argument:
                path, offset = argument['cursor'].rsplit('|', 1)
                offset = int(offset)
            else:
                path, offset = argument['path'], 0
            names = sorted(p for p in self.objects if p.startswith(path + '/'))
            page = names[offset:offset + 2]
            entries = [{'.tag': 'file', 'name': p.rsplit('/', 1)[1], 'path_lower': p.lower(),
                        'size': len(self.objects[p])} for p in page]
            return Response(url, json.dumps({'entries': entries, 'has_more': offset + 2 < len(names),
                                             'cursor': path + '|' + str(offset + 2)}).encode())
        if url.endswith('/create_folder_v2'):
            path = json.loads(request.data)['path']
            self.folders.add(path)
            return Response(url, b'{"metadata":{}}')
        argument = json.loads(request.headers['Dropbox-api-arg'])
        path = argument['path']
        if url.endswith('/download'):
            if path not in self.objects:
                raise urllib.error.HTTPError(url, 409, '', {}, io.BytesIO(b'{"error_summary":"path/not_found/fixture"}'))
            return Response(url, self.objects[path])
        assert url.endswith('/upload')
        assert argument['mode'] == 'add' and argument['strict_conflict'] is True and argument['autorename'] is False
        if path in self.objects:
            raise urllib.error.HTTPError(url, 409, '', {}, io.BytesIO(b'{"error_summary":"path/conflict/file/fixture"}'))
        self.objects[path] = request.data
        return Response(url, b'{"name":"opaque"}')


class VaultStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='durability-test-')
        self.root = Path(self.temp.name)
        self.shared = self.root / 'shared'
        self.shared.mkdir(mode=0o700)
        self.private = self.root / 'private'
        self.private.mkdir(mode=0o700)
        self.key = bytes(range(32))
        self.store = MountedStore(self.shared)
        self.vault = Vault(self.key, self.store)

    def tearDown(self):
        self.temp.cleanup()

    def secret(self, name, body):
        path = self.private / name
        path.write_bytes(body)
        path.chmod(0o600)
        return path

    def dropbox(self):
        token = self.secret('dropbox-token', b'fixture-only-durable-token-not-credential')
        store = DropboxStore('/private-fixture/checkpoints', token)
        fake = FakeDropboxHTTP()
        store._opener = fake
        return store, fake

    def test_real_crypto_roundtrip_and_fresh_vault_manifest(self):
        data = b'private-scene-json-fixture' * 43
        descriptor = self.vault.put_bytes(data)
        checkpoint = self.vault.save_manifest({'scene': descriptor, 'schema': 'TEST_ONLY'})
        fresh = Vault(self.key, MountedStore(self.shared))
        self.assertEqual(fresh.load_manifest(checkpoint)['scene'], descriptor)
        self.assertEqual(fresh.get_bytes(descriptor), data)
        self.assertTrue(fresh.verify_descriptor(descriptor))
        self.assertFalse(self.store.external_verified)
        for path in self.shared.iterdir():
            self.assertNotIn(data, path.read_bytes())
            self.assertRegex(path.name, r'^[a-f0-9]{64}$')

    def test_large_file_chunking_and_restore_after_private_source_loss(self):
        data = (bytes(range(251)) * ((CHUNK_BYTES * 2 + 313) // 251 + 1))[:CHUNK_BYTES * 2 + 313]
        source = self.secret('source.mp4', data)
        descriptor = self.vault.put_file(source, hashlib.sha256(data).hexdigest())
        self.assertEqual(len(descriptor['chunks']), 3)
        source.unlink()  # This fixture simulates ephemeral-container data loss.
        target = self.private / 'restored.mp4'
        Vault(self.key, MountedStore(self.shared)).restore_file(descriptor, target)
        self.assertEqual(target.read_bytes(), data)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(p.stat().st_size <= MAX_OBJECT for p in self.shared.iterdir()))

    def test_empty_file_and_invalid_memory_limit(self):
        descriptor = self.vault.put_bytes(b'')
        self.assertEqual(descriptor['chunks'], [])
        self.assertEqual(self.vault.get_bytes(descriptor), b'')
        with self.assertRaises(BackupError):
            self.vault.get_bytes(descriptor, limit=True)

    def test_duplicate_plaintext_reuses_existing_ciphertext(self):
        first = self.vault.put_bytes(b'completed-scene')
        existing = {p.name: p.read_bytes() for p in self.shared.iterdir()}
        second = Vault(self.key, self.store).put_bytes(b'completed-scene')
        self.assertEqual(first, second)
        self.assertEqual(existing, {p.name: p.read_bytes() for p in self.shared.iterdir()})

    def test_wrong_key_and_modified_object_fail_authentication(self):
        descriptor = self.vault.put_bytes(b'keep-original')
        with self.assertRaises(BackupError):
            Vault(bytes(reversed(self.key)), self.store).get_bytes(descriptor)
        path = self.shared / descriptor['chunks'][0]
        payload = path.read_bytes()
        path.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
        with self.assertRaisesRegex(BackupError, 'AUTHENTICATION_FAILED'):
            self.vault.get_bytes(descriptor)
        with self.assertRaises(BackupError):
            self.vault.put_bytes(b'keep-original')

    def test_order_hash_and_descriptor_limits_are_checked(self):
        descriptor = self.vault.put_bytes(b'A' * CHUNK_BYTES + b'B' * CHUNK_BYTES)
        changed = {**descriptor, 'chunks': list(reversed(descriptor['chunks']))}
        with self.assertRaisesRegex(BackupError, 'HASH_MISMATCH'):
            self.vault.verify_descriptor(changed)
        for changed in ({**descriptor, 'bytes': -1}, {**descriptor, 'bytes': True},
                        {**descriptor, 'extra': 1}, {**descriptor, 'chunks': ['../not-opaque']}):
            with self.assertRaises(BackupError):
                self.vault.verify_descriptor(changed)

    def test_restore_does_not_overwrite_and_rejects_symlinks(self):
        descriptor = self.vault.put_bytes(b'new-data')
        existing = self.secret('existing', b'original-data')
        with self.assertRaises(BackupError):
            self.vault.restore_file(descriptor, existing)
        self.assertEqual(existing.read_bytes(), b'original-data')
        link = self.private / 'link'
        link.symlink_to(existing)
        with self.assertRaises(BackupError):
            self.vault.restore_file(descriptor, link)
        with self.assertRaises(BackupError):
            self.vault.put_file(link)
        self.assertEqual(existing.read_bytes(), b'original-data')

    def test_restore_bad_hash_removes_only_own_new_incomplete_file(self):
        descriptor = self.vault.put_bytes(b'new-data')
        target = self.private / 'incomplete'
        with self.assertRaises(BackupError):
            self.vault.restore_file({**descriptor, 'sha256': '0' * 64}, target)
        self.assertFalse(target.exists())

    def test_source_hash_and_private_modes(self):
        source = self.secret('source', b'fixed-source')
        with self.assertRaises(BackupError):
            self.vault.put_file(source, '0' * 64)
        source.chmod(0o644)
        with self.assertRaises(BackupError):
            self.vault.put_file(source)

    def test_key_file_strict_format_mode_and_links(self):
        key = self.secret('key', base64.urlsafe_b64encode(self.key))
        self.assertEqual(read_key_file(key), self.key)
        key.chmod(0o644)
        with self.assertRaises(BackupError):
            read_key_file(key)
        key.chmod(0o600)
        link = self.private / 'key-link'
        link.symlink_to(key)
        with self.assertRaises(BackupError):
            read_key_file(link)
        key.write_bytes(b'not-a-real-32-byte-key')
        with self.assertRaises(BackupError):
            read_key_file(key)

    def test_store_is_additive_and_rejects_unsafe_ids(self):
        oid = 'a' * 64
        self.store.put(oid, b'original')
        self.store.put(oid, b'original')
        with self.assertRaises(Conflict):
            self.store.put(oid, b'changed')
        self.assertEqual(self.store.get(oid), b'original')
        for oid in ('../escape', 'a' * 65, 'A' * 64):
            with self.assertRaises(BackupError):
                self.store.get(oid)
        with self.assertRaises(NotFound):
            self.store.get('b' * 64)

    def test_interrupted_publish_leaves_no_final_object_and_retry_succeeds(self):
        oid = 'c' * 64
        with mock.patch('stores._publish_noreplace', side_effect=BackupError('DURABILITY_FIXTURE_INTERRUPTED')):
            with self.assertRaises(BackupError):
                self.store.put(oid, b'completed-object')
        with self.assertRaises(NotFound):
            self.store.get(oid)
        self.assertEqual(list(self.shared.iterdir()), [])
        self.store.put(oid, b'completed-object')
        self.assertEqual(self.store.get(oid), b'completed-object')

    def test_manifest_root_tamper_never_loads_as_trusted_manifest(self):
        checkpoint = self.vault.save_manifest({'scene': 'private-plan'})
        path = self.shared / checkpoint
        payload = path.read_bytes()
        path.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
        with self.assertRaisesRegex(BackupError, 'AUTHENTICATION_FAILED'):
            self.vault.load_manifest(checkpoint)

    def test_store_rejects_symlink_objects_and_roots(self):
        source = self.secret('other', b'secret')
        (self.shared / ('a' * 64)).symlink_to(source)
        with self.assertRaises(BackupError):
            self.store.get('a' * 64)
        link = self.root / 'shared-link'
        link.symlink_to(self.shared)
        with self.assertRaises(OSError):
            MountedStore(link)

    def test_fake_dropbox_upload_download_real_vault_crypto(self):
        store, fake = self.dropbox()
        vault = Vault(self.key, store)
        descriptor = vault.put_bytes(b'private-data')
        checkpoint = vault.save_manifest({'descriptor': descriptor})
        self.assertEqual(vault.load_manifest(checkpoint)['descriptor'], descriptor)
        self.assertTrue(vault.verify_descriptor(descriptor))
        self.assertTrue(store.external_verified)  # Capability only; fake HTTP is not evidence.
        self.assertTrue(fake.folders)
        self.assertTrue(all(timeout == 30 for _, timeout in fake.calls))
        self.assertTrue(all(url.startswith('https://') for url, _ in fake.calls))

    def test_fake_dropbox_auth_network_and_size_failures_do_not_retry(self):
        store, fake = self.dropbox()
        fake.failure = urllib.error.HTTPError('https://api.dropboxapi.com/', 401, '', {}, io.BytesIO(b'{}'))
        with self.assertRaisesRegex(BackupError, 'AUTH_FAILED'):
            store.get('a' * 64)
        self.assertEqual(len(fake.calls), 1)
        fake.failure = TimeoutError('fixture')
        with self.assertRaisesRegex(BackupError, 'CONNECTION_FAILED'):
            store.get('a' * 64)
        fake.failure = None
        fake.objects[store.prefix + '/' + 'a' * 64] = b'X' * (MAX_OBJECT + 1)
        with self.assertRaisesRegex(BackupError, 'TOO_LARGE'):
            store.get('a' * 64)

    def test_fake_dropbox_redirect_and_conflicting_content_fail_closed(self):
        store, fake = self.dropbox()
        fake.objects[store.prefix + '/' + 'a' * 64] = b'original'
        with self.assertRaises(Conflict):
            store.put('a' * 64, b'different')
        from stores import _NoRedirect
        with self.assertRaisesRegex(BackupError, 'REDIRECT_REJECTED'):
            _NoRedirect().redirect_request(None, None, 302, '', {}, 'https://untrusted.invalid/')

    def test_receipt_catalog_discovers_authenticated_manifests_after_private_loss(self):
        self.assertEqual(self.vault.list_receipts(), [])
        payload = {'schema': 'WORLD_ENGINE_STUDIO_DURABLE_RECEIPT_V1', 'checkpointId': 'a' * 64,
                   'createdUnixNs': 1234, 'testOnly': True}
        receipt = self.vault.publish_receipt(payload)
        fresh = Vault(self.key, MountedStore(self.shared))
        self.assertEqual(fresh.list_receipts(), [{'receiptId': receipt, 'manifest': payload}])
        catalog = self.shared / 'receipts'
        self.assertEqual([p.name for p in catalog.iterdir()], [receipt])
        self.assertNotIn(b'createdUnixNs', (catalog / receipt).read_bytes())
        self.assertEqual((catalog / receipt).read_bytes(), (self.shared / receipt).read_bytes())

    def test_catalog_tampering_or_limits_never_returns_false_empty_success(self):
        self.vault.publish_receipt({'schema': 'TEST_ONLY', 'index': 1})
        self.vault.publish_receipt({'schema': 'TEST_ONLY', 'index': 2})
        with self.assertRaisesRegex(BackupError, 'TOO_LARGE'):
            self.vault.list_receipts(limit=1)
        for limit in (0, True, 4097):
            with self.assertRaises(BackupError):
                self.vault.list_receipts(limit=limit)
        (self.shared / 'receipts' / ('f' * 64)).write_bytes(b'forged')
        with self.assertRaises(BackupError):
            self.vault.list_receipts()

    def test_fake_dropbox_receipts_paginated_and_encrypted(self):
        store, fake = self.dropbox()
        vault = Vault(self.key, store)
        for index in range(3):
            vault.publish_receipt({'schema': 'TEST_ONLY', 'index': index})
        fresh = Vault(self.key, store)
        self.assertEqual(sorted(row['manifest']['index'] for row in fresh.list_receipts()), [0, 1, 2])
        self.assertTrue(any(url.endswith('/list_folder/continue') for url, _ in fake.calls))
        self.assertTrue(all(b'"index"' not in value for value in fake.objects.values()))
        with self.assertRaisesRegex(BackupError, 'TOO_LARGE'):
            fresh.list_receipts(limit=2)

    def test_fake_dropbox_catalog_rejects_bad_paths_and_cursor_loops(self):
        store, fake = self.dropbox()
        fake.list_override = {'entries': [{'.tag': 'file', 'name': 'a' * 64,
            'path_lower': '/unapproved/' + 'a' * 64, 'size': 40}], 'has_more': False}
        with self.assertRaisesRegex(BackupError, 'CATALOG_INVALID'):
            store.list_receipts()
        fake.list_override = {'entries': [], 'has_more': True, 'cursor': 'same-forever'}
        with self.assertRaisesRegex(BackupError, 'CURSOR_INVALID'):
            store.list_receipts()


if __name__ == '__main__':
    unittest.main()
