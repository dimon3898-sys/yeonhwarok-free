"""Install an image-pinned private archive from the existing storage mount.

No network, renderer, source transformation, or permission repair is performed.
Call only after the existing owner/configuration checks have succeeded.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

SCHEMA = 'WORLD_ENGINE_PRIVATE_PACKAGE_V1'
MANIFEST = 'PRIVATE_PACKAGE_MANIFEST.json'
_HEX = re.compile(r'[a-f0-9]{64}\Z')
REGISTRY_KEYS = ('WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE',
                 'WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256')


def require(condition, code):
    if not condition:
        raise RuntimeError('PRIVATE_PACKAGE_' + code)


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def relative(value):
    require(isinstance(value, str) and '\\' not in value and '\x00' not in value,
            'PATH_INVALID')
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value and
            all(part not in ('', '.', '..') for part in path.parts) and len(path.parts) >= 2,
            'PATH_INVALID')
    return path


def private_parent(path, uid, gid):
    require(path.is_absolute() and str(path) == os.path.normpath(path), 'ROOT_INVALID')
    for current in reversed((path, *path.parents)):
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode) and not current.is_symlink() and
                info.st_uid in (0, uid) and not stat.S_IMODE(info.st_mode) & 0o022,
                'ROOT_UNSAFE')
    info = path.stat()
    require(info.st_uid == uid and info.st_gid == gid and
            stat.S_IMODE(info.st_mode) == 0o700, 'ROOT_OWNER_MODE')


def unpack(archive, receipt, destination, *, uid=1000, gid=1000):
    """Verify every byte before promoting fresh roots; no existing root is changed."""
    private_parent(destination, uid, gid)
    require(receipt.get('schema') == SCHEMA, 'RECEIPT_SCHEMA')
    require(_HEX.fullmatch(receipt.get('archiveSHA256', '')) and
            _HEX.fullmatch(receipt.get('manifestSHA256', '')), 'RECEIPT_PIN')
    require(type(receipt.get('files')) is int and 0 < receipt['files'] <= 10000,
            'FILE_COUNT')
    require(type(receipt.get('unpackedBytes')) is int and
            0 < receipt['unpackedBytes'] <= 2 * 1024**3, 'SIZE_LIMIT')
    fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stage = None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size == receipt['archiveBytes'],
                'ARCHIVE_SIZE')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            require(digest(stream) == receipt['archiveSHA256'], 'ARCHIVE_HASH')
            stream.seek(0)
            with zipfile.ZipFile(stream) as bundle:
                entries = bundle.infolist()
                names = [entry.filename for entry in entries]
                require(len(names) == len(set(names)) == receipt['files'] + 1,
                        'DUPLICATE_OR_COUNT')
                require(MANIFEST in names and bundle.getinfo(MANIFEST).file_size <= 8 * 1024**2,
                        'MANIFEST_REQUIRED')
                raw = bundle.read(MANIFEST)
                require(hashlib.sha256(raw).hexdigest() == receipt['manifestSHA256'],
                        'MANIFEST_HASH')
                manifest = json.loads(raw)
                require(manifest.get('schema') == SCHEMA and isinstance(manifest.get('files'), list),
                        'MANIFEST_SCHEMA')
                records = {}
                for record in manifest['files']:
                    path = relative(record['path'])
                    require(record['path'] not in records and
                            type(record.get('bytes')) is int and 0 <= record['bytes'] <= 128 * 1024**2 and
                            _HEX.fullmatch(record.get('sha256', '')), 'FILE_RECORD')
                    records[str(path)] = record
                require(set(names) == set(records) | {MANIFEST} and
                        sum(record['bytes'] for record in records.values()) == receipt['unpackedBytes'],
                        'FILE_SET')
                roots = {relative(name).parts[0] for name in records}
                require(sorted(roots) == sorted(receipt['roots']), 'ROOT_SET')
                require(not any((destination / name).exists() or
                                (destination / name).is_symlink() for name in roots), 'DESTINATION_EXISTS')
                for entry in entries:
                    mode = entry.external_attr >> 16
                    require(not entry.is_dir() and not entry.flag_bits & 1 and
                            (not stat.S_IFMT(mode) or stat.S_ISREG(mode)), 'ENTRY_TYPE')
                    if entry.filename != MANIFEST:
                        require(entry.file_size == records[entry.filename]['bytes'], 'ENTRY_SIZE')
                stage = Path(tempfile.mkdtemp(prefix='.private-package-', dir=destination.parent))
                os.chmod(stage, 0o700)
                for name, record in records.items():
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    hasher, count = hashlib.sha256(), 0
                    with bundle.open(name) as source, target.open('xb') as out:
                        for block in iter(lambda: source.read(1024 * 1024), b''):
                            count += len(block)
                            require(count <= record['bytes'], 'FILE_SIZE')
                            hasher.update(block)
                            out.write(block)
                        out.flush()
                        os.fsync(out.fileno())
                    require(count == record['bytes'] and hasher.hexdigest() == record['sha256'],
                            'FILE_HASH')
                    os.chmod(target, 0o600)
                    os.chown(target, uid, gid)
                for directory, subdirs, _ in os.walk(stage):
                    for name in subdirs:
                        os.chmod(Path(directory) / name, 0o700)
                        os.chown(Path(directory) / name, uid, gid)
                registry = relative(receipt['registryRelativePath'])
                require(str(registry) in records and
                        records[str(registry)]['sha256'] == receipt['registrySHA256'], 'REGISTRY_PIN')
                for name in sorted(roots):
                    os.rename(stage / name, destination / name)
                parent_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
    finally:
        os.close(fd)
        if stage is not None:
            shutil.rmtree(stage)
    return dict(zip(REGISTRY_KEYS, (str(destination / receipt['registryRelativePath']),
                                    receipt['registrySHA256'])))


def install(receipt_file, repo_root):
    """The receipt and this module are both pinned by the startup manifest."""
    require(os.geteuid() == 0, 'ROOT_BOOTSTRAP_REQUIRED')
    receipt = json.loads(Path(receipt_file).read_bytes())
    require(receipt.get('installationPath') == '/workspace/shared', 'ROOT_FIXED')
    archive_name = receipt.get('archiveName', '')
    require(re.fullmatch(r'KW20_PRIVATE_[A-Za-z0-9_-]+\.zip', archive_name), 'ARCHIVE_NAME')
    for item in receipt['nativeCodePins']:
        path = Path(repo_root) / relative(item['path'])
        require(path.is_relative_to(repo_root) and not path.is_symlink(), 'CODE_PATH')
        with path.open('rb') as stream:
            require(digest(stream) == item['sha256'], 'CODE_HASH')
    return unpack(Path('/world-storage') / archive_name, receipt, Path('/workspace/shared'))
