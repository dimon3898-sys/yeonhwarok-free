"""Gate 1 process environment and bounded, secret-redacted diagnostic capture."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

SECRET_NAME = re.compile(r'OWNER_CODE|PASSWORD|PASSWD|TOKEN|SECRET|CREDENTIAL|API_KEY|PRIVATE_KEY|ACCESS_KEY', re.I)
LIMIT = 65536


def redact(text, environ=None):
    value = str(text)
    for name, secret in (os.environ if environ is None else environ).items():
        if SECRET_NAME.search(name) and isinstance(secret, str) and secret:
            value = value.replace(secret, '[REDACTED]')
    value = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', value)
    value = re.sub(r'(?i)(Bearer\s+)[\w.+/=-]+', r'\1[REDACTED]', value)
    value = re.sub(r'(?i)((?:password|token|secret|api[_-]?key|authorization|cookie|owner[_-]?code)[\s\"\x27:=]+)[^\s,;\"\x27]+', r'\1[REDACTED]', value)
    return value[:LIMIT]


def prepare_user_environment(account, runtime, environ=None):
    """Must run as the target UID, after preserving provider device groups."""
    env = dict(os.environ if environ is None else environ)
    home, runtime = Path(account.pw_dir), Path(runtime)
    paths = {'HOME': home, 'XDG_CACHE_HOME': home / '.cache',
             'XDG_CONFIG_HOME': home / '.config', 'XDG_RUNTIME_DIR': runtime / 'xdg'}
    for name, directory in paths.items():
        if directory.is_symlink():
            raise ValueError('GPU_USER_DIRECTORY_SYMLINK')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = directory.stat()
        if metadata.st_uid != account.pw_uid or not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError('GPU_USER_DIRECTORY_INACCESSIBLE')
        if name != 'HOME':
            directory.chmod(0o700)
        if name == 'XDG_RUNTIME_DIR' and stat.S_IMODE(directory.stat().st_mode) != 0o700:
            raise ValueError('GPU_XDG_RUNTIME_PERMISSION_INVALID')
        env[name] = str(directory)
    env['WORLD_ENGINE_CHROMIUM_REAL'] = '/usr/bin/chromium'
    env['WORLD_ENGINE_RENDER_MODE'] = 'gpu-required'
    return env


def worker_environment(environ):
    return {name: value for name, value in environ.items() if not SECRET_NAME.search(name)}


def environment_evidence(environ):
    directories = {}
    for name in ('HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_RUNTIME_DIR'):
        path = Path(environ[name]) if environ.get(name) else None
        try:
            metadata = path.stat() if path else None
            directories[name] = {'path': redact(str(path), environ) if path else 'UNSET',
                                 'uid': metadata.st_uid if metadata else None,
                                 'mode': oct(stat.S_IMODE(metadata.st_mode)) if metadata else None,
                                 'accessible': bool(path and os.access(path, os.R_OK | os.W_OK | os.X_OK))}
        except OSError:
            directories[name] = {'path': redact(str(path), environ), 'accessible': False}
    return {'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(),
            'directories': directories,
            'xdg_environment': {name: redact(value, environ) for name, value in environ.items() if name.startswith('XDG_') and not SECRET_NAME.search(name)},
            'chromium_real_executable': environ.get('WORLD_ENGINE_CHROMIUM_REAL', 'UNSET'),
            'nvidia_driver_capabilities': redact(environ.get('NVIDIA_DRIVER_CAPABILITIES', 'UNSET'), environ)}
