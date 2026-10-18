#!/usr/bin/env python3
"""Keep the frozen supervisor and materialize only approved backup Secrets."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from parent import HERE, proxy, runtime

SECRET_INPUTS = (
    ('WORLD_ENGINE_STUDIO_BACKUP_KEY', 'WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE', 'backup-key'),
    ('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN', 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN_FILE', 'dropbox-token'),
)


def _read_input(path, uid=1000):
    path = Path(path)
    if (not path.is_absolute() or '..' in path.parts or path.is_relative_to('/world-storage')
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise RuntimeError('DURABILITY_PRIVATE_SECRET_PATH_REQUIRED')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in {0, uid}
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or not 1 <= info.st_size <= 65536):
            raise RuntimeError('DURABILITY_PRIVATE_SECRET_INPUT_REQUIRED')
        raw = os.read(descriptor, 65537)
        if len(raw) != info.st_size:
            raise RuntimeError('DURABILITY_SECRET_CHANGED')
        return raw
    finally:
        os.close(descriptor)


def prepare_backup_secrets(environ, state_root, *, uid=1000, gid=1000):
    """Never generate a key that would be lost with this container."""
    frozen = proxy().https.bootstrap.original
    result = dict(environ)
    directory = Path(state_root) / 'durability-secrets'
    for raw_name, file_name, basename in SECRET_INPUTS:
        raw, file = result.get(raw_name), result.get(file_name)
        if file:
            value = _read_input(file, uid)
        elif raw is not None:
            if not isinstance(raw, str) or not 1 <= len(raw.encode()) <= 65536:
                raise RuntimeError('DURABILITY_SECRET_INPUT_INVALID')
            value = raw.encode()
        else:
            # Missing backup credentials block production preflight, not setup.
            result.pop(raw_name, None)
            continue
        frozen._private_directory(directory, uid, gid)
        target = directory / basename
        frozen._private_file(target, value, uid, gid)
        result[file_name] = str(target)
        result.pop(raw_name, None)
    return result


def spawn_studio(command, **kwargs):
    command = list(command)
    expected = ['/usr/bin/python3', '-B', str(proxy().https.root / 'https_server.py')]
    if command[:3] == expected:
        command[0] = sys.executable
        command[2] = str(HERE / 'durable_server.py')
    return subprocess.Popen(command, **kwargs)


def main(argv=None):
    frozen = proxy().https.bootstrap
    try:
        if os.geteuid() != 0:
            raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
        from manifest import verify_sources
        verify_sources()
        config = frozen.prepare_configuration(os.environ)
        environment = prepare_backup_secrets(os.environ, config['root'])
        environment = frozen.child_environment(environment, studio=True, config=config)
        for name in frozen.original.SECRET_ENV | {row[0] for row in SECRET_INPUTS}:
            os.environ.pop(name, None)
        return frozen.supervise(config, environment, sys.argv[1:] if argv is None else argv,
                                spawn=spawn_studio)
    except Exception as error:
        frozen._record('STARTUP_BLOCKED', status='FAIL', errorCode=runtime()._safe(error), renderAllowed=False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
