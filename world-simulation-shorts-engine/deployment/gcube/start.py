"""Image entrypoint: preserved engine, explicit GPU proof, private durable state."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from urllib.request import urlopen

APP = Path(__file__).resolve().parents[2]


class BootError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def integer_option(env, name, default, low, high):
    value = env.get(name, str(default))
    if not isinstance(value, str) or not value.isdecimal() or not low <= int(value) <= high:
        raise BootError('INVALID_' + name)
    return int(value)


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def seed_audio(source, destination):
    """Preserve the approved library and never replace a persisted generated asset."""
    source, destination = Path(source), Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    for original in source.rglob('*'):
        if original.is_symlink():
            raise BootError('UNSAFE_IMAGE_AUDIO')
        if not original.is_file():
            continue
        target = destination / original.relative_to(source)
        if not target.resolve().is_relative_to(destination.resolve()):
            raise BootError('UNSAFE_PERSISTED_AUDIO')
        walk = target
        while walk != destination:
            if walk.is_symlink():
                raise BootError('UNSAFE_PERSISTED_AUDIO')
            walk = walk.parent
        if target.exists():
            if not target.is_file() or _sha(original) != _sha(target):
                raise BootError('PERSISTED_AUDIO_CONFLICT')
            continue
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with original.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)


def link_image_path(source, target):
    """Called only inside the deployment image, never on the user's checkout."""
    source, target = Path(source), Path(target).resolve()
    if source.is_symlink():
        if source.resolve() != target:
            raise BootError('IMAGE_WRITABLE_PATH_CONFLICT')
        return
    if source.exists():
        if not source.is_dir() or any(source.iterdir()):
            raise BootError('IMAGE_WRITABLE_PATH_NOT_EMPTY')
        source.rmdir()
    source.symlink_to(target, target_is_directory=True)


def configure_image_paths(app, storage, namespace):
    if not re.fullmatch(r'(?:cpu|gpu)-[a-f0-9]{64}', namespace):
        raise BootError('INVALID_RENDER_PROFILE')
    cache = Path(storage.cache_root) / namespace
    if cache.is_symlink() or cache.resolve() != Path(storage.cache_root).resolve() / namespace:
        raise BootError('UNSAFE_PERSISTED_CACHE')
    created = False
    try:
        cache.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        pass
    fd = os.open(cache, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if created and os.geteuid() == 0:
            os.fchown(fd, storage.uid, storage.gid)
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            raise BootError('UNSAFE_PERSISTED_CACHE')
        if hasattr(storage, 'uid') and (info.st_uid != storage.uid or info.st_gid != storage.gid):
            raise BootError('PERSISTED_CACHE_OWNERSHIP')
    finally:
        os.close(fd)
    # Mutable outputs are separate from the read-only approved source/data/assets.
    link_image_path(Path(app) / 'cache', cache)
    audio = Path(app) / 'assets/audio'
    saved = Path(app) / 'assets/image_audio_seed'
    if not audio.is_symlink() and audio.is_dir():
        if saved.exists():
            raise BootError('IMAGE_AUDIO_SEED_CONFLICT')
        audio.rename(saved)
    link_image_path(audio, storage.audio_root)
    return cache


def main():
    began = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    if str(APP) != '/opt/world-engine/world-simulation-shorts-engine':
        raise BootError('IMAGE_LAYOUT_REQUIRED')
    from deployment.gcube.storage import NativePersonalStorage
    from deployment.gcube.gpu import probe_gpu_runtime
    from deployment.security import private_json
    from deployment.start_codespace import _runtime_preflight
    env = dict(os.environ)
    env['WORLD_ENGINE_CHROMIUM_REAL'] = '/usr/bin/chromium'
    code = env.get('WORLD_ENGINE_OWNER_CODE')
    if not isinstance(code, str) or not 16 <= len(code) <= 512 or code != code.strip():
        raise BootError('WORLD_ENGINE_OWNER_CODE_REQUIRED')
    duration = integer_option(env, 'WORLD_ENGINE_MAX_DURATION', 20, 5, 180)
    job_seconds = integer_option(env, 'WORLD_ENGINE_MAX_JOB_SECONDS', 3600, 60, 14400)
    mode = env.get('WORLD_ENGINE_STORAGE_MODE', 'required')
    base = env.get('WORLD_ENGINE_STORAGE_PATH', '/world-storage' if mode == 'required' else '/data')
    account = pwd.getpwnam('engine')
    env['HOME'] = account.pw_dir
    storage = NativePersonalStorage(base, mode=mode, uid=account.pw_uid, gid=account.pw_gid).prepare(
        explicit_owner_code=code)
    # Prove graphics access with the same unprivileged identity as the server.
    def run_probe(command, **kwargs):
        if os.geteuid() == 0:
            kwargs.update(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        return subprocess.run(command, **kwargs)
    probe_env = dict(env)
    probe_env.pop('WORLD_ENGINE_OWNER_CODE', None)
    gpu = probe_gpu_runtime(environ=probe_env, runner=run_probe)
    cache = configure_image_paths(APP, storage, gpu['cache_namespace'])
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    seed_audio(APP / 'assets/image_audio_seed', storage.audio_root)
    _runtime_preflight()
    report = {'gpu': gpu, 'storage': storage.as_dict(),
              'start': {'container_started_at_utc': started_at, 'server_boot_seconds': None},
              'billing': {'provider_stop_verified': False,
                          'message': '유휴 상태도 과금됩니다. MP4 다운로드 후 gcube Workload를 중지하세요.'},
              'limits': {'max_duration': duration, 'maximum_job_seconds': job_seconds}}
    runtime = Path(storage.runtime_root)
    from deployment.gcube.validation_fixture import seed_once
    report['validation_project'] = seed_once(runtime)
    private_json(runtime / 'gcube-runtime.json', report)
    child_env = dict(env)
    child_env.pop('WORLD_ENGINE_OWNER_CODE', None)
    child_env['CHROMIUM_PATH'] = str(APP / 'deployment/gcube/chromium_wrapper.py')
    child_env['WORLD_ENGINE_CHROMIUM_REAL'] = '/usr/bin/chromium'
    child_env['WORLD_ENGINE_RENDER_MODE'] = gpu['render_mode']
    child_env['HOME'] = account.pw_dir
    command = [sys.executable, '-m', 'deployment.gcube.server', '--host', '0.0.0.0',
               '--port', '8000', '--internal-port', '8001', '--state-root', str(runtime),
               '--access-file', str(runtime / 'owner-code.txt'), '--max-duration', str(duration),
               '--maximum-job-seconds', str(job_seconds)]
    if env.get('WORLD_ENGINE_PUBLIC_ORIGIN'):
        command += ['--public-origin', env['WORLD_ENGINE_PUBLIC_ORIGIN']]
    if env.get('WORLD_ENGINE_LOCAL_MODE') == '1':
        command += ['--local-mode']
    server = subprocess.Popen(command, cwd=APP, env=child_env, stdin=subprocess.DEVNULL)
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        if not stopping and server.poll() is None:
            stopping = True
            server.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    from deployment.gcube.telemetry import Telemetry
    telemetry = Telemetry(runtime)
    telemetry.start()
    try:
        deadline = time.monotonic() + 60
        while server.poll() is None and time.monotonic() < deadline:
            try:
                with urlopen('http://127.0.0.1:8000/api/health', timeout=2) as response:
                    if response.status == 200 and json.load(response).get('ok'):
                        report['start']['server_boot_seconds'] = time.monotonic() - began
                        private_json(runtime / 'gcube-runtime.json', report)
                        print('World Engine ready on8000; owner-code is private; no provider stop or GPU speedup is implied.', flush=True)
                        break
            except (OSError, ValueError):
                pass
            time.sleep(.2)
        else:
            if server.poll() is None:
                server.terminate()
            raise BootError('WORLD_ENGINE_BOOT_FAILED')
        return server.wait()
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=25)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        telemetry.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Never log environment values, owner code or raw third-party responses.
        print('GCUBE startup blocked: ' + getattr(error, 'code', type(error).__name__), file=sys.stderr)
        sys.exit(2)
