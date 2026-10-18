"""Small input adapter around the immutable, approved offline backup runtime.

The source files, crypto, permission checks, OAuth, cache, claims and render
entrypoints remain the inherited implementation. No GPU policy is relaxed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import threading

from key_encoding import canonical_key

HERE = Path(__file__).resolve().parent
OFFLINE = (Path('/opt/world-engine-studio-dropbox-offline')
           if HERE.is_relative_to('/opt') else HERE.parent / 'studio-dropbox-offline-v1')
PYTHON = '/opt/world-engine-studio-durability-venv/bin/python'
PINS = {'offline_runtime.py': 'a31ef39da32d9176927ee639f4fdc1cd61aa5df54427e7cc3608d83d80578815',
        'offline_manifest.py': 'efa96efac5899c60a6bfde08167fc1162542188eb95125ee1cb35cda85c8965c'}
_LOCK = threading.Lock()
_OLD = None


def frozen():
    for name, digest in PINS.items():
        path = OFFLINE / name
        if (any(p.is_symlink() for p in (path, *path.parents))
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise RuntimeError('PRODUCTION_FROZEN_OFFLINE_SOURCE_CHANGED')
    if str(OFFLINE) not in sys.path:
        sys.path.insert(0, str(OFFLINE))
    import offline_manifest
    if Path(offline_manifest.__file__).resolve() != OFFLINE / 'offline_manifest.py':
        raise RuntimeError('PRODUCTION_OFFLINE_MODULE_COLLISION')
    offline_manifest.verify_sources()
    import offline_runtime
    if Path(offline_runtime.__file__).resolve() != OFFLINE / 'offline_runtime.py':
        raise RuntimeError('PRODUCTION_OFFLINE_MODULE_COLLISION')
    return offline_runtime


def canonical_reader(old, offline, original):
    def read(path):
        # Same original UID1000/0600/nlink/no-symlink/change-detection reader.
        # Never rewrite or weaken the original Secret file to normalize it.
        raw = old.stores.read_private_file(path, limit=128)
        try:
            encoded = canonical_key(raw.decode('ascii')).encode('ascii')
        except (UnicodeError, RuntimeError):
            raise old.stores.BackupError('PRODUCTION_BACKUP_KEY_ENCODING_INVALID') from None
        with offline._access_scratch(old) as scratch:
            descriptor, name = tempfile.mkstemp(prefix='canonical-', dir=scratch)
            try:
                os.fchmod(descriptor, 0o600)
                if os.write(descriptor, encoded) != len(encoded):
                    raise old.stores.BackupError('PRODUCTION_PRIVATE_KEY_COPY_FAILED')
                os.fsync(descriptor)
                return original(name)
            finally:
                os.close(descriptor)
                os.unlink(name)  # This newly created private scratch file only.
    read.original_reader = original  # Non-secret reference for focused regression.
    return read


def redirect(command, previous):
    copied = previous(command)
    expected = str(OFFLINE / 'offline_entry.py')
    if (isinstance(copied, (list, tuple)) and len(copied) >= 4
            and copied[1:3] == ['-B', expected]
            and copied[3] in {'server', 'runtime', 'coordinator', 'startup-restore'}):
        return [*copied[:2], str(HERE / 'production_entry.py'), *copied[3:]]
    return copied


def install():
    global _OLD
    with _LOCK:
        if _OLD is not None:
            return _OLD
        offline = frozen()
        old = offline.install()
        original = old.vault.read_key_file
        old.vault.read_key_file = canonical_reader(old, offline, original)
        previous = offline.redirect_command
        offline.redirect_command = lambda command: redirect(command, previous)
        _OLD = old
        return old
