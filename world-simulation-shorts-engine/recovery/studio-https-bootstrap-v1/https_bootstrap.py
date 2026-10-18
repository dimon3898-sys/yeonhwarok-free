#!/usr/bin/env python3
"""Start the owner-only configuration UI before unchanged GPU admission.

The web service being alive never grants rendering admission. No GPU job is
created, resumed, or retried by this supervisor, including on restart.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess
import sys
import time

from frozen import load_originals

HERE = Path(__file__).resolve().parent
_originals = load_originals()
original = _originals.bootstrap
STATE_ROOT = original.STATE_ROOT
CONFIGURATION_ERROR = 'WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'
_POLICY_CODES = {'STUDIO_OPERATOR_POLICY_REQUIRED', 'STUDIO_OPERATOR_POLICY_JSON_REQUIRED',
    'STUDIO_OPERATOR_POLICY_FIELDS_REQUIRED', 'STUDIO_OPERATOR_POLICY_INVALID',
    'STUDIO_OPERATOR_POLICY_EXPIRED', 'STUDIO_COST_LIMIT_EXCEEDED',
    'STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED', 'STUDIO_PRIVATE_FILE_REQUIRED'}


def _safe_code(error, fallback='STUDIO_BOOTSTRAP_FAILED'):
    value = getattr(error, 'code', None) or str(error)
    return value if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', value) else fallback


def _json_policy(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise RuntimeError('STUDIO_OPERATOR_POLICY_JSON_REQUIRED') from None
    if (not isinstance(value, dict) or not original.POLICY_KEYS <= value.keys()
            or set(value) - original.POLICY_KEYS - {'schema'}
            or ('schema' in value and value['schema'] != 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1')):
        raise RuntimeError('STUDIO_OPERATOR_POLICY_FIELDS_REQUIRED')
    return value


def _validate_policy(value):
    """Reuse the unchanged cost/expiry validator without making a controller."""
    name = '_https_frozen_policy_validator'
    module = sys.modules.get(name)
    if module is None:
        path = _originals.root / 'studio_controller.py'
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    class ReadOnlyPolicy:
        def json(self, name, optional=False):
            if name != 'operator_policy.json':
                raise RuntimeError('STUDIO_OPERATOR_POLICY_INVALID')
            return value
    return module.StudioController._policy(None, ReadOnlyPolicy())


def _prepare_policy(environ, production, uid, gid):
    policy_path = production / 'operator_policy.json'
    raw = environ.get('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON')
    try:
        if raw is None:
            if not policy_path.exists() and not policy_path.is_symlink():
                return 'STUDIO_OPERATOR_POLICY_REQUIRED'
            original._private_file(policy_path, uid=uid, gid=gid)
            value = _json_policy(policy_path.read_text(encoding='utf-8'))
            _validate_policy(value)
            return None
        value = _json_policy(raw)
        _validate_policy(value)
        canonical = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        # Original helper refuses to overwrite any different existing policy.
        original._private_file(policy_path, canonical, uid, gid)
        return None
    except Exception as error:
        code = _safe_code(error, 'STUDIO_OPERATOR_POLICY_INVALID')
        return code if code in _POLICY_CODES else 'STUDIO_OPERATOR_POLICY_INVALID'


def prepare_configuration(environ, *, default_root=STATE_ROOT, uid=1000, gid=1000):
    root = Path(environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT', str(default_root)))
    if (not root.is_absolute() or '..' in root.parts or root == Path('/world-storage')
            or root.is_relative_to('/world-storage')):
        raise RuntimeError('STUDIO_PRIVATE_LOCAL_STATE_REQUIRED')
    original._private_directory(root, uid, gid)
    owner = root / 'owner-code'
    value = environ.get('WORLD_ENGINE_STUDIO_OWNER_CODE')
    if value is not None and (not isinstance(value, str) or not 16 <= len(value) <= 256
            or any(ord(char) < 33 or ord(char) > 126 for char in value)):
        raise RuntimeError('STUDIO_OWNER_CODE_LENGTH_REQUIRED')
    original._private_file(owner, value.encode('utf-8') if value is not None else None, uid, gid)
    production = original._private_directory(root / 'production', uid, gid)
    configuration_error = _prepare_policy(environ, production, uid, gid)
    port = environ.get('WORLD_ENGINE_STUDIO_PORT', '8080')
    if not isinstance(port, str) or not re.fullmatch(r'[1-9][0-9]{3,4}', port) or not 1024 <= int(port) <= 65535 or int(port) == 8000:
        raise RuntimeError('STUDIO_DISTINCT_PORT_REQUIRED')
    try:
        home = Path(pwd.getpwuid(uid).pw_dir)
    except KeyError:
        raise RuntimeError('STUDIO_ENGINE_ACCOUNT_REQUIRED') from None
    if not home.is_absolute() or not home.is_dir() or home.is_symlink():
        raise RuntimeError('STUDIO_ENGINE_HOME_REQUIRED')
    xdg = {key: original._private_directory(root / suffix, uid, gid) for key, suffix in
        [('XDG_RUNTIME_DIR', 'xdg-runtime'), ('XDG_CONFIG_HOME', 'xdg-config'), ('XDG_CACHE_HOME', 'xdg-cache')]}
    # Missing origin is deliberate setup state. No placeholder is invented.
    return {'root': root, 'owner': owner, 'origin': environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', ''),
            'port': int(port), 'home': home, 'xdg': xdg, 'configuration_error': configuration_error}


def child_environment(environ, *, studio=False, config=None):
    clean = dict(environ)
    clean.pop(CONFIGURATION_ERROR, None)
    result = original.child_environment(clean, studio=studio, config=config)
    result.pop(CONFIGURATION_ERROR, None)
    if studio:
        if not config['origin']:
            result.pop('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', None)
        error = config.get('configuration_error')
        if error is not None:
            if error not in _POLICY_CODES:
                raise RuntimeError('STUDIO_CONFIGURATION_ERROR_INVALID')
            result[CONFIGURATION_ERROR] = error
    return result


def _record(stage, **fields):
    print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_HTTPS_BOOTSTRAP_V1', 'stage': stage,
        'renderAutomaticallyStarted': False, 'gpuRenderingVerified': False, **fields}), flush=True)


def supervise(config, environ, legacy_args=(), *, spawn=subprocess.Popen,
              pause=time.sleep, monotonic=time.monotonic, stop=original.stop_child,
              device_groups=original.device_groups):
    legacy = studio = None
    legacy_exited = False
    stopping = False
    previous = {}
    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True
    for name in (signal.SIGTERM, signal.SIGINT):
        previous[name] = signal.signal(name, request_stop)
    try:
        command = ['/usr/bin/python3', '-B', str(HERE / 'https_server.py'),
            '--state-root', str(config['root']), '--owner-file', str(config['owner']),
            '--export-root', '/world-storage', '--host', '0.0.0.0', '--port', str(config['port'])]
        studio = spawn(command, env=child_environment(environ, studio=True, config=config),
            start_new_session=True, user=1000, group=1000, extra_groups=device_groups())
        _record('SETUP_SERVICE_STARTED', studioPort=config['port'], healthPort=8000,
                configurationError=config.get('configuration_error'))
        # This unchanged service owns hardware admission only. Starting it does
        # not start rendering; its failure must not kill the safe setup UI.
        try:
            legacy = spawn([*original.LEGACY_COMMAND, *legacy_args], env=child_environment(environ), start_new_session=True)
        except Exception as error:
            legacy_exited = True
            _record('GPU_ADMISSION_BLOCKED', errorCode=_safe_code(error, 'STUDIO_GPU_SERVICE_START_FAILED'), renderAllowed=False)
        while not stopping:
            code = studio.poll()
            if code is not None:
                _record('SETUP_SERVICE_EXITED', exitCode=code, renderAllowed=False)
                return code if code else 1
            if not legacy_exited:
                code = legacy.poll()
                if code is not None:
                    legacy_exited = True
                    _record('GPU_ADMISSION_EXITED', exitCode=code, renderAllowed=False)
            pause(0.25)
        return 143
    finally:
        stop(studio)
        stop(legacy)
        for name, handler in previous.items():
            signal.signal(name, handler)


def main(argv=None):
    try:
        if os.geteuid() != 0:
            raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
        import manifest
        manifest.verify_sources()
        config = prepare_configuration(os.environ)
        environment = child_environment(os.environ, studio=True, config=config)
        for name in original.SECRET_ENV:
            os.environ.pop(name, None)
        return supervise(config, environment, sys.argv[1:] if argv is None else argv)
    except Exception as error:
        _record('STARTUP_BLOCKED', status='FAIL', errorCode=_safe_code(error), renderAllowed=False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
