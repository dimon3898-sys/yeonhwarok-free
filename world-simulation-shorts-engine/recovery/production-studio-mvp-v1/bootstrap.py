#!/usr/bin/env python3
"""Supervise the unchanged health/GPU admission service plus opt-in Studio.

This starts no render jobs, deployments, retries, or billing operations. A user
must provide the owner credential and real HTTPS origin through gCube settings.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import pwd
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit
import urllib.request

HERE = Path(__file__).resolve().parent
STATE_ROOT = Path('/var/lib/world-engine-private/engine/production-studio-mvp-v1')
LEGACY_COMMAND = ['/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py']
SECRET_ENV = {'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}
POLICY_KEYS = {'validUntil', 'maxWallSeconds', 'maxRetries', 'maxCostAmount', 'currency', 'gpuHourlyRate'}


def _private_directory(path, uid=1000, gid=1000):
    path = Path(path)
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError('STUDIO_PRIVATE_PATH_SYMLINK_FORBIDDEN')
    if path.exists():
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError('STUDIO_PRIVATE_DIRECTORY_REQUIRED')
        return path
    path.mkdir(mode=0o700, parents=False)
    if os.geteuid() == 0:
        os.chown(path, uid, gid)
    elif os.geteuid() != uid:
        raise RuntimeError('STUDIO_PRIVATE_IDENTITY_REQUIRED')
    return path


def _private_file(path, raw=None, uid=1000, gid=1000):
    path = Path(path)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != uid
                or stat.S_IMODE(info.st_mode) != 0o600 or not 1 <= info.st_size <= 65536):
            raise RuntimeError('STUDIO_PRIVATE_FILE_REQUIRED')
        if raw is not None and hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
            raise RuntimeError('STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED')
        return path
    if raw is None:
        raise RuntimeError('STUDIO_OWNER_CONFIGURATION_REQUIRED')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        if os.geteuid() == 0:
            os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, 'wb', closefd=False) as target:
            target.write(raw); target.flush(); os.fsync(target.fileno())
    finally:
        os.close(descriptor)
    return path


def prepare_configuration(environ, *, default_root=STATE_ROOT, uid=1000, gid=1000):
    origin = environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', '')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        raise RuntimeError('STUDIO_HTTPS_ORIGIN_REQUIRED')
    root = Path(environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT', str(default_root)))
    if (not root.is_absolute() or '..' in root.parts or root == Path('/world-storage')
            or root.is_relative_to('/world-storage')):
        raise RuntimeError('STUDIO_PRIVATE_LOCAL_STATE_REQUIRED')
    _private_directory(root, uid, gid)
    owner = root / 'owner-code'
    value = environ.get('WORLD_ENGINE_STUDIO_OWNER_CODE')
    if value is not None and (not isinstance(value, str) or not 16 <= len(value) <= 256
            or any(ord(char) < 33 or ord(char) > 126 for char in value)):
        raise RuntimeError('STUDIO_OWNER_CODE_LENGTH_REQUIRED')
    _private_file(owner, value.encode('utf-8') if value is not None else None, uid, gid)
    production = _private_directory(root / 'production', uid, gid)
    policy = environ.get('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON')
    if policy is not None:
        try:
            document = json.loads(policy)
        except (ValueError, TypeError):
            raise RuntimeError('STUDIO_OPERATOR_POLICY_JSON_REQUIRED') from None
        if (not isinstance(document, dict) or not POLICY_KEYS <= document.keys()
                or set(document) - POLICY_KEYS - {'schema'}
                or ('schema' in document and document['schema'] != 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1')):
            raise RuntimeError('STUDIO_OPERATOR_POLICY_FIELDS_REQUIRED')
        # Detailed real rate, expiry and cost bounds are enforced by the existing
        # controller immediately before every authenticated Start. No defaults.
        raw = (json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        _private_file(production / 'operator_policy.json', raw, uid, gid)
    port = environ.get('WORLD_ENGINE_STUDIO_PORT', '8080')
    if not re.fullmatch(r'[1-9][0-9]{3,4}', port) or not 1024 <= int(port) <= 65535 or int(port) == 8000:
        raise RuntimeError('STUDIO_DISTINCT_PORT_REQUIRED')
    try:
        home = Path(pwd.getpwuid(uid).pw_dir)
    except KeyError:
        raise RuntimeError('STUDIO_ENGINE_ACCOUNT_REQUIRED') from None
    if not home.is_absolute() or not home.is_dir() or home.is_symlink():
        raise RuntimeError('STUDIO_ENGINE_HOME_REQUIRED')
    xdg = {key: _private_directory(root / suffix, uid, gid) for key, suffix in
        [('XDG_RUNTIME_DIR', 'xdg-runtime'), ('XDG_CONFIG_HOME', 'xdg-config'), ('XDG_CACHE_HOME', 'xdg-cache')]}
    return {'root': root, 'owner': owner, 'origin': origin, 'port': int(port), 'home': home, 'xdg': xdg}


def child_environment(environ, *, studio=False, config=None):
    result = {key: value for key, value in environ.items()
              if key not in SECRET_ENV and (studio or not key.startswith('WORLD_ENGINE_STUDIO_'))}
    if studio:
        result['WORLD_ENGINE_STUDIO_OWNER_FILE'] = str(config['owner'])
        result['WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'] = config['origin']
        result['HOME'] = str(config['home'])
        result['WORLD_ENGINE_RUNTIME_DIR'] = str(config['root'])
        result['WORLD_ENGINE_RENDER_MODE'] = 'gpu-required'
        result.update({key: str(value) for key, value in config['xdg'].items()})
    return result


def device_groups():
    """Reuse the frozen graphics-device allowlist; never retain arbitrary groups."""
    path = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/deployment/gcube/gpu_access.py')
        if str(HERE).startswith('/opt/') else HERE.parents[1] / 'deployment/gcube/gpu_access.py')
    if any(part.is_symlink() for part in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != '9bb5799b73fc26ce209d807ab13d0bbe2f9604be10f58e53727d6ccea9b8eec7':
        raise RuntimeError('STUDIO_FROZEN_DEVICE_GROUP_HELPER_REQUIRED')
    spec = importlib.util.spec_from_file_location('_studio_original_device_groups', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    groups = module.collect_device_groups()
    if not isinstance(groups, list) or groups != sorted(set(groups)) or any(type(g) is not int or g <= 0 for g in groups):
        raise RuntimeError('STUDIO_DEVICE_GROUP_ALLOWLIST_REQUIRED')
    return groups


def legacy_health_ready():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:8000/healthz', timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def stop_child(child):
    if child is None or child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=8)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=3)


def supervise(config, environ, legacy_args=(), *, spawn=subprocess.Popen, health=legacy_health_ready,
              monotonic=time.monotonic, pause=time.sleep, startup_timeout=180):
    legacy = studio = None
    stopping = False
    previous = {}
    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True
    for name in (signal.SIGTERM, signal.SIGINT):
        previous[name] = signal.signal(name, request_stop)
    try:
        legacy = spawn([*LEGACY_COMMAND, *legacy_args], env=child_environment(environ), start_new_session=True)
        deadline = monotonic() + startup_timeout
        while not stopping:
            code = legacy.poll()
            if code is not None:
                return code if code else 1
            if health():
                break
            if monotonic() >= deadline:
                raise RuntimeError('STUDIO_ORIGINAL_GPU_HEALTH_NOT_READY')
            pause(0.25)
        if stopping:
            return 143
        command = ['/usr/bin/python3', '-B', str(HERE / 'server.py'),
            '--state-root', str(config['root']), '--owner-file', str(config['owner']),
            '--public-origin', config['origin'], '--export-root', '/world-storage',
            '--host', '0.0.0.0', '--port', str(config['port'])]
        studio = spawn(command, env=child_environment(environ, studio=True, config=config),
            start_new_session=True, user=1000, group=1000, extra_groups=device_groups())
        print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_BOOTSTRAP_V1', 'stage': 'SERVICES_STARTED',
            'renderAutomaticallyStarted': False, 'nvidiaVerifiedByStudio': False, 'healthPort': 8000,
            'studioPort': config['port']}), flush=True)
        while not stopping:
            for child in (legacy, studio):
                code = child.poll()
                if code is not None:
                    return code if code else 1
            pause(0.25)
        return 143
    finally:
        stop_child(studio); stop_child(legacy)
        for name, handler in previous.items():
            signal.signal(name, handler)


def main(argv=None):
    try:
        if os.geteuid() != 0:
            raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
        import studio_manifest
        studio_manifest.verify_sources()
        config = prepare_configuration(os.environ)
        environment = child_environment(os.environ, studio=True, config=config)
        for name in SECRET_ENV:
            os.environ.pop(name, None)
        return supervise(config, environment, sys.argv[1:] if argv is None else argv)
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_BOOTSTRAP_FAILED'
        print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_BOOTSTRAP_V1', 'status': 'FAIL',
            'errorCode': code, 'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
