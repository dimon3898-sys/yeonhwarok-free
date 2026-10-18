#!/usr/bin/env python3
"""Keep the frozen supervisor and materialize only approved backup Secrets."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
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


def prepare_startup_restore(environ, *, run=subprocess.run):
    """Explicit optional CPU restore, before the target STATE_ROOT is created."""
    checkpoint_id = environ.get('WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID')
    plan_sha = environ.get('WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256')
    if checkpoint_id is None and plan_sha is None:
        return dict(environ)
    image_digest = environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST')
    explicit_root = environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT')
    if (not isinstance(checkpoint_id, str) or not re.fullmatch(r'[a-f0-9]{64}', checkpoint_id)
            or not isinstance(plan_sha, str) or not re.fullmatch(r'[a-f0-9]{64}', plan_sha)
            or not isinstance(image_digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image_digest)
            or not isinstance(explicit_root, str) or not explicit_root):
        raise RuntimeError('DURABILITY_EXPLICIT_STARTUP_RESTORE_BINDINGS_REQUIRED')
    target = Path(explicit_root)
    if (not target.is_absolute() or '..' in target.parts or target == Path('/')
            or target.is_relative_to('/world-storage')
            or any(p.is_symlink() for p in (target, *target.parents))):
        raise RuntimeError('DURABILITY_PRIVATE_RESTORE_ROOT_REQUIRED')
    frozen = proxy().https.bootstrap.original
    # Keep approved credentials outside the fresh destination. Do not initialize
    # the destination first or replace any existing root/claim to force restore.
    aux = Path('/var/lib/world-engine-private/engine/studio-durability-bootstrap')
    frozen._private_directory(aux, 1000, 1000)
    environment = prepare_backup_secrets(environ, aux)
    allowed = {row[1] for row in SECRET_INPUTS} | {'WORLD_ENGINE_STUDIO_BACKUP_MODE',
               'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX', 'WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID'}
    allowed |= {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'PYTHONDONTWRITEBYTECODE',
                'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE',
                'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}
    child_environment = {name: value for name, value in environment.items() if name in allowed}
    command = [sys.executable, '-B', str(HERE / 'startup_restore.py'),
               '--checkpoint-id', checkpoint_id, '--plan-sha256', plan_sha,
               '--image-digest', image_digest, '--state-root', str(target)]
    print(json.dumps({'stage': 'STARTUP_RESTORE_IN_PROGRESS', 'maximumSeconds': 600,
                      'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
    result = run(command, env=child_environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                 stderr=subprocess.DEVNULL, user=1000, group=1000, extra_groups=[],
                 close_fds=True, timeout=600, check=False)
    try:
        if len(result.stdout) > 16384:
            raise ValueError()
        receipt = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise RuntimeError('DURABILITY_STARTUP_RESTORE_RESPONSE_INVALID') from None
    if (result.returncode or receipt.get('restoreVerified') is not True
            or receipt.get('checkpointId') != checkpoint_id or receipt.get('planSHA256') != plan_sha
            or receipt.get('imageDigest') != image_digest or receipt.get('productionRenderingStarted') is not False
            or receipt.get('executionAuthorityRestored') is not False
            or receipt.get('newOperatorApprovalRequired') is not True):
        code = receipt.get('code', 'DURABILITY_STARTUP_RESTORE_FAILED')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,95}', code):
            code = 'DURABILITY_STARTUP_RESTORE_FAILED'
        raise RuntimeError(code)
    print(json.dumps({'stage': 'STARTUP_RESTORE_VERIFIED', 'renderAllowed': False,
                      'gpuRenderingVerified': False}), flush=True)
    return environment


def main(argv=None):
    frozen = proxy().https.bootstrap
    try:
        if os.geteuid() != 0:
            raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
        from manifest import verify_sources
        verify_sources()
        environment = prepare_startup_restore(os.environ)
        config = frozen.prepare_configuration(environment)
        environment = prepare_backup_secrets(environment, config['root'])
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
