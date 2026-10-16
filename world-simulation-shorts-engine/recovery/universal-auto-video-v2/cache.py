"""Neutral scene cache: immutable attempts; only verified receipts are reusable.

No native frames are held in memory, old claims are never touched, and a cache
hit is not GPU or remote-storage verification. Private POSIX helpers are reused
from the existing storage adapter; shared Dropbox is never a cache root.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import time

HERE = Path(__file__).resolve().parent
_STORAGE = HERE.parent / 'gcube-storage-fix-v1/storage.py'
_spec = importlib.util.spec_from_file_location('_universal_reused_storage', _STORAGE)
storage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage)
HEX = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z')
MAX_JSON = 32 * 1024**2


class CacheError(RuntimeError):
    pass


def canonical_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise CacheError('INVALID_JSON') from None


def canonical_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CacheError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _component(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in {'.', '..'}:
        raise CacheError('UNSAFE_NAME')
    return name


def _owned(info, directory=False):
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode) or info.st_uid != os.geteuid() or info.st_gid != os.getegid()
            or (stat.S_IMODE(info.st_mode) & 0o077)
            or (not directory and info.st_nlink != 1)):
        raise CacheError('PRIVATE_PATH_REQUIRED')
    return info


class PrivateTree:
    """Pinned openat directory tree. No symlink traversal or metadata repair."""
    def __init__(self, root, *, create=False):
        self.path = Path(root)
        if not self.path.is_absolute() or '..' in self.path.parts:
            raise CacheError('ABSOLUTE_PRIVATE_PATH_REQUIRED')
        if str(self.path) == '/world-storage' or '/world-storage/' in str(self.path) + '/':
            raise CacheError('SHARED_STORAGE_IS_NOT_PRIVATE_CACHE')
        if create:
            parent = storage._open_directory(self.path.parent, safe_parents=True, account_uid=os.geteuid())
            try:
                try:
                    os.mkdir(_component(self.path.name), 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
            finally:
                os.close(parent)
        self.fd = storage._open_directory(self.path, safe_parents=True, account_uid=os.geteuid())
        try:
            _owned(os.fstat(self.fd), True)
            if storage._filesystem(self.path) not in storage.LOCAL_FILESYSTEMS:
                raise CacheError('LOCAL_POSIX_CACHE_REQUIRED')
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def child(self, name, *, create=False):
        _component(name)
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=self.fd)
                os.fsync(self.fd)
            except FileExistsError:
                pass
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
        _owned(os.fstat(descriptor), True)
        result = object.__new__(PrivateTree)
        result.path, result.fd = self.path / name, descriptor
        return result

    def json(self, name, *, optional=False):
        _component(name)
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        except FileNotFoundError:
            if optional:
                return None
            raise
        try:
            before = _owned(os.fstat(descriptor))
            if not 1 <= before.st_size <= MAX_JSON:
                raise CacheError('JSON_SIZE_INVALID')
            data = storage._read_fd(descriptor, limit=MAX_JSON)
            after = os.fstat(descriptor)
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)):
                raise CacheError('RECORD_CHANGED_DURING_READ')
            return json.loads(data, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(CacheError('NONFINITE_JSON')))
        finally:
            os.close(descriptor)

    def write_json(self, name, value, *, replace=False):
        _component(name)
        data = canonical_bytes(value)
        if len(data) > MAX_JSON:
            raise CacheError('JSON_SIZE_INVALID')
        temporary = 'pending-' + os.urandom(12).hex() + '.json'
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.fd)
        try:
            storage._write_all(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        # A private directory lock is mandatory around replacing mutable state.
        if replace:
            try:
                _owned(os.stat(name, dir_fd=self.fd, follow_symlinks=False))
            except FileNotFoundError:
                pass
            os.rename(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        else:
            # link+unlink has no replace race. Never overwrite a prior receipt.
            os.link(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
            os.unlink(temporary, dir_fd=self.fd)
        os.fsync(self.fd)
        return hashlib.sha256(data).hexdigest()

    @contextmanager
    def lock(self, name='LOCK', *, wait_seconds=0):
        _component(name)
        descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            _owned(os.fstat(descriptor))
            deadline = time.monotonic() + min(8.0, max(0.0, wait_seconds))
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise CacheError('JOB_OR_CACHE_BUSY') from None
                    time.sleep(0.02)
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            held = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                raise CacheError('LOCK_PATH_CHANGED')
            yield descriptor
        finally:
            os.close(descriptor)

    def hash_file(self, name):
        _component(name)
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        try:
            before = _owned(os.fstat(descriptor))
            if before.st_size == 0:
                raise CacheError('EMPTY_ARTIFACT')
            digest = hashlib.sha256()
            while True:
                block = os.read(descriptor, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
            after = os.fstat(descriptor)
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if ((before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns)
                    != (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns)
                    or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)):
                raise CacheError('ARTIFACT_CHANGED_DURING_HASH')
            return {'file': name, 'sha256': digest.hexdigest(), 'bytes': after.st_size}
        finally:
            os.close(descriptor)


def scene_cache_key(plan, scene, previous=None, following=None):
    """Whole inputs plus neighboring state—not a global plan hash.

    An unrelated later scene need not evict an early segment. Shared timeline
    and source changes do. Neighbor boundary changes invalidate both neighbors.
    """
    context = {key: plan.get(key) for key in ('fps', 'resolution', 'aspectRatio',
        'sourceManifest', 'renderProfile', 'encoder', 'audioSettings', 'timelineEpoch',
        'rendererVersion', 'nativePayloadVersion', 'legacyScenePlan', 'nativePayload',
        'nativePayloads', 'activationSHA256', 'renderBinding', 'cameraProfile',
        'materialProfile', 'eventTimeline', 'territoryState', 'frontierState')}
    return canonical_sha256({'schema': 'WORLD_ENGINE_SCENE_CACHE_KEY_V2',
        'scene': scene, 'context': context,
        'previousBoundaryEnd': None if previous is None else previous.get('boundaryEnd'),
        'followingBoundaryStart': None if following is None else following.get('boundaryStart')})


class SceneCache:
    def __init__(self, root, *, create=False):
        self.tree = PrivateTree(root, create=create)

    def close(self):
        self.tree.close()

    def _key(self, key):
        if not isinstance(key, str) or not HEX.fullmatch(key):
            raise CacheError('INVALID_CACHE_KEY')
        return self.tree.child(key, create=True)

    def begin(self, key):
        """A failed attempt remains as evidence; it is never a success entry."""
        with self._key(key) as entry:
            attempt = 'attempt-' + os.urandom(12).hex()
            with entry.child(attempt, create=True) as directory:
                directory.write_json('ATTEMPT.json', {'schema': 'WORLD_ENGINE_SCENE_ATTEMPT_V1',
                    'key': key, 'attemptId': attempt, 'createdUnixSeconds': time.time(), 'state': 'RUNNING'})
                return directory.path

    def lookup(self, key):
        with self._key(key) as entry:
            index = entry.json('SUCCESS.json', optional=True)
            if index is None:
                return None
            if not isinstance(index, dict) or set(index) != {'key', 'attemptId', 'receiptSHA256'} or index['key'] != key:
                raise CacheError('CACHE_INDEX_INVALID')
            with entry.child(index['attemptId']) as attempt:
                if attempt.hash_file('COMPLETE.json')['sha256'] != index['receiptSHA256']:
                    raise CacheError('CACHE_RECEIPT_CORRUPT')
                receipt = attempt.json('COMPLETE.json')
                if (receipt.get('schema') != 'WORLD_ENGINE_SCENE_CACHE_RECEIPT_V2'
                        or receipt.get('key') != key or receipt.get('status') != 'COMPLETE'
                        or not isinstance(receipt.get('files'), list) or not receipt['files']):
                    raise CacheError('CACHE_RECEIPT_INVALID')
                for expected in receipt['files']:
                    if attempt.hash_file(expected['file']) != expected:
                        raise CacheError('CACHE_ARTIFACT_CORRUPT')
                segment = dict(receipt['segment'])
                segment['path'] = str(attempt.path / _component(segment['file']))
                segment['cacheKey'], segment['cacheHit'] = key, True
                return segment

    def complete(self, key, attempt_path, segment):
        """Caller supplies an independently FFprobe/decode verified segment."""
        if segment.get('technical') != 'PASS' or segment.get('frameCountVerified') is not True:
            raise CacheError('SEGMENT_VERIFICATION_REQUIRED')
        if (type(segment.get('testOnly')) is not bool
                or (segment['testOnly'] is False and (segment.get('hardwareVerified') is not True
                                                      or segment.get('fullDecodeVerified') is not True))):
            raise CacheError('NATIVE_VERIFICATION_OR_EXPLICIT_TEST_PROVENANCE_REQUIRED')
        attempt_path = Path(attempt_path)
        expected_parent = self.tree.path / key
        if attempt_path.parent != expected_parent or not attempt_path.name.startswith('attempt-'):
            raise CacheError('ATTEMPT_PATH_INVALID')
        with self._key(key) as entry, entry.lock():
            with entry.child(attempt_path.name) as attempt:
                name = _component(Path(segment['path']).name)
                if Path(segment['path']) != attempt_path / name:
                    raise CacheError('SEGMENT_PATH_INVALID')
                facts = attempt.hash_file(name)
                if facts['sha256'] != segment.get('sha256'):
                    raise CacheError('SEGMENT_HASH_MISMATCH')
                saved = {k: v for k, v in segment.items() if k not in {'path', 'cacheHit'}}
                saved['file'] = name
                artifact_names = segment.get('artifacts', [name])
                if (not isinstance(artifact_names, list) or name not in artifact_names
                        or not 1 <= len(artifact_names) <= 12 or len(set(artifact_names)) != len(artifact_names)):
                    raise CacheError('SEGMENT_ARTIFACT_LIST_INVALID')
                files = [attempt.hash_file(_component(item)) for item in artifact_names]
                receipt = {'schema': 'WORLD_ENGINE_SCENE_CACHE_RECEIPT_V2', 'key': key,
                    'status': 'COMPLETE', 'files': files, 'segment': saved,
                    'remotePersistenceVerified': False, 'externalDownloadVerified': False}
                digest = attempt.write_json('COMPLETE.json', receipt)
            entry.write_json('SUCCESS.json', {'key': key, 'attemptId': attempt_path.name,
                                            'receiptSHA256': digest}, replace=True)
        return self.lookup(key)
