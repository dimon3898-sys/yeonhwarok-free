"""Audio-aware, versioned Studio exports over the frozen shared-storage adapter.

The existing silent exporter remains unchanged. Shared Dropbox bytes are always
untrusted and rehashed; mounted readback never asserts external synchronization.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re

HERE = Path(__file__).resolve().parent
RECOVERY = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
            if str(HERE).startswith('/opt/') else HERE.parent)
STORAGE_SHA = '4c858e7afe5e912bce63bf03f08c6c98d9430cc91134262710db5bdbd6ca4491'
PUBLIC = frozenset({'WORLD_ENGINE_STUDIO_VIDEO.mp4', 'QUALITY_SUMMARY.json', 'SHA256SUMS', 'SFX.wav'})
LOCATION = re.compile(r'world-engine-export-[a-f0-9]{24}/studio-[a-f0-9]{24}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
MAX_FILE = 4 * 1024**3


def _storage():
    path = Path('/opt/world-engine-storage-fix/storage.py')
    if not path.is_file():
        path = RECOVERY / 'gcube-storage-fix-v1/storage.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != STORAGE_SHA:
        raise RuntimeError('STUDIO_FROZEN_STORAGE_CHANGED')
    spec = importlib.util.spec_from_file_location('_studio_frozen_export_storage', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _facts(storage, directory, name, expected=None, *, copy_to=None):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    destination = None
    try:
        before = storage._file_info(source)
        if not 0 < before.st_size <= MAX_FILE:
            raise RuntimeError('STUDIO_EXPORT_FILE_SIZE_INVALID')
        if copy_to is not None:
            destination = os.open(copy_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest, size = hashlib.sha256(), 0
        while True:
            block = os.read(source, 1024 * 1024)
            if not block:
                break
            if size + len(block) > min(before.st_size, MAX_FILE):
                raise RuntimeError('STUDIO_EXPORT_CHANGED_DURING_READ')
            digest.update(block)
            size += len(block)
            if destination is not None:
                storage._write_all(destination, block)
        after = os.fstat(source)
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)):
            raise RuntimeError('STUDIO_EXPORT_CHANGED_DURING_READ')
        facts = {'name': name, 'bytes': size, 'sha256': digest.hexdigest()}
        if expected is not None and facts != expected:
            raise RuntimeError('STUDIO_EXPORT_HASH_MISMATCH')
        if destination is not None:
            os.fsync(destination)
        return facts
    except BaseException:
        # Only the exclusively created incomplete private copy may be removed;
        # never unlink an existing export or a substituted path identity.
        if destination is not None:
            created = os.fstat(destination)
            try:
                current = os.stat(copy_to, follow_symlinks=False)
                if (created.st_dev, created.st_ino) == (current.st_dev, current.st_ino):
                    os.unlink(copy_to)
            except FileNotFoundError:
                pass
        raise
    finally:
        for descriptor in (source, destination):
            if descriptor is not None:
                os.close(descriptor)


def _export_fd(storage, export_root, location, *, legacy=False):
    expression = (r'world-engine-export-[a-f0-9]{24}/video-[a-f0-9]{24}' if legacy else LOCATION.pattern)
    if not isinstance(location, str) or re.fullmatch(expression, location) is None:
        raise RuntimeError('STUDIO_EXPORT_LOCATION_INVALID')
    root = storage._open_directory(Path(export_root).absolute())
    first = None
    try:
        parent, child = location.split('/')
        first = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        return os.open(child, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=first)
    finally:
        for descriptor in (first, root):
            if descriptor is not None:
                os.close(descriptor)


def copy_verified_silent(result, export_root, destination):
    """Rehash every legacy export before copying its silent MP4 into private work."""
    path = RECOVERY / 'universal-auto-video-v2/delivery.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != 'b41022ec747c6cd0683dccb3cd0fa94619c5e1badff82015ad0ec29d17dcffcf':
        raise RuntimeError('STUDIO_FROZEN_DELIVERY_CHANGED')
    spec = importlib.util.spec_from_file_location('_studio_frozen_silent_delivery', path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    checked = legacy.verify_mounted_export(result, export_root)
    if checked.get('mountedViewReadbackVerified') is not True:
        raise RuntimeError('STUDIO_SILENT_EXPORT_NOT_VERIFIED')
    rows = [row for row in result.get('files', []) if row.get('file') == 'WORLD_ENGINE_AUTO_VIDEO.mp4']
    if len(rows) != 1:
        raise RuntimeError('STUDIO_SILENT_VIDEO_RECEIPT_REQUIRED')
    row = rows[0]
    expected = {'name': row['file'], 'sha256': row['sha256'], 'bytes': row['bytes']}
    storage = _storage()
    directory = _export_fd(storage, export_root, result.get('exportDirectory'), legacy=True)
    try:
        _facts(storage, directory, expected['name'], expected, copy_to=Path(destination))
    finally:
        os.close(directory)
    return expected


def export_media(public_dir, export_root, private_base):
    """Export one fresh version, with an exact media-only allowlist and readback."""
    storage = _storage()
    public_dir = Path(public_dir).absolute()
    names = set(os.listdir(public_dir))
    required = PUBLIC - {'SFX.wav'}
    if names not in (required, PUBLIC) or public_dir.is_symlink():
        raise RuntimeError('STUDIO_EXACT_PUBLIC_ALLOWLIST_REQUIRED')
    source = storage._open_directory(public_dir, safe_parents=True, account_uid=1000)
    session = storage.StorageSession.create(pwd.getpwuid(1000), base=Path(private_base), export_root=Path(export_root))
    private = export = target = None
    try:
        session.preflight()
        expected = {name: _facts(storage, source, name) for name in sorted(names)}
        summary = json.loads((public_dir / 'QUALITY_SUMMARY.json').read_text())
        if (set(summary) != {'schema', 'technicalVerification', 'frames', 'fps', 'width', 'height',
                            'durationSeconds', 'audioStreams', 'sfxEnabled', 'videoDecodedPixelsUnchanged',
                            'fullDecode', 'visualQuality', 'externalDownloadVerified', 'finalPromotion'}
                or summary.get('schema') != 'WORLD_ENGINE_STUDIO_SAFE_QA_V1'
                or summary.get('technicalVerification') != 'PASS'
                or summary.get('visualQuality') != 'USER_VIDEO_REVIEW_REQUIRED'
                or summary.get('externalDownloadVerified') is not False or summary.get('finalPromotion') is not False):
            raise RuntimeError('STUDIO_PUBLIC_QA_SUMMARY_INVALID')
        lines = (public_dir / 'SHA256SUMS').read_text(encoding='ascii').splitlines()
        expected_lines = [expected[name]['sha256'] + '  ' + name for name in sorted(names - {'SHA256SUMS'})]
        if lines != expected_lines:
            raise RuntimeError('STUDIO_PUBLIC_HASH_MANIFEST_INVALID')
        private = session._private_fd()
        export = session._export_fd(private)
        name, target = storage._new_directory(export, 'studio-')
        for filename in sorted(names):
            session._source_digest(source, filename, expected[filename]['sha256'])
            session._copy_public_file(source, target, filename, expected[filename]['sha256'])
        storage._shared_fsync(target)
        result = {'schema': 'WORLD_ENGINE_STUDIO_EXPORT_V1',
                  'exportDirectory': session.export_name + '/' + name,
                  'files': list(expected.values()), 'mountedViewReadbackVerified': True,
                  'remotePersistenceVerified': False, 'externalDownloadVerified': False}
        verify_export(result, export_root)
        return result
    finally:
        for descriptor in (target, export, private, source):
            if descriptor is not None:
                os.close(descriptor)


def verify_export(result, export_root):
    if not isinstance(result, dict) or result.get('schema') != 'WORLD_ENGINE_STUDIO_EXPORT_V1':
        raise RuntimeError('STUDIO_EXPORT_RECEIPT_REQUIRED')
    rows = result.get('files')
    if not isinstance(rows, list) or len(rows) not in {3, 4}:
        raise RuntimeError('STUDIO_EXPORT_RECEIPT_INVALID')
    names = [row.get('name') for row in rows if isinstance(row, dict)]
    if set(names) not in (PUBLIC - {'SFX.wav'}, PUBLIC) or len(names) != len(set(names)):
        raise RuntimeError('STUDIO_EXPORT_RECEIPT_INVALID')
    storage = _storage()
    directory = _export_fd(storage, export_root, result.get('exportDirectory'))
    try:
        if set(os.listdir(directory)) != set(names):
            raise RuntimeError('STUDIO_EXACT_PUBLIC_ALLOWLIST_REQUIRED')
        for row in rows:
            if (set(row) != {'name', 'bytes', 'sha256'} or type(row['bytes']) is not int
                    or not 0 < row['bytes'] <= MAX_FILE or not SHA.fullmatch(str(row['sha256']))):
                raise RuntimeError('STUDIO_EXPORT_RECEIPT_INVALID')
            _facts(storage, directory, row['name'], row)
    finally:
        os.close(directory)
    return {**result, 'mountedViewReadbackVerified': True,
            'remotePersistenceVerified': False, 'externalDownloadVerified': False}
