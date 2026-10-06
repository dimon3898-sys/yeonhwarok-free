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
import threading
import time
import uuid
from urllib.request import ProxyHandler, build_opener

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


def run_graphics_probe(command, **kwargs):
    """Bound the private Node/Chromium probe and reap its own process group.

    A timeout must not leave a GPU browser running while the status screen is
    blocked. Other preflight commands keep subprocess.run's existing behavior.
    """
    if not command or command[0] != 'node':
        return subprocess.run(command, **kwargs)
    timeout = kwargs.pop('timeout', 60)
    check = kwargs.pop('check', False)
    if kwargs.pop('capture_output', False):
        if 'stdout' in kwargs or 'stderr' in kwargs:
            raise ValueError('capture_output conflicts with stdout/stderr')
        kwargs['stdout'] = kwargs['stderr'] = subprocess.PIPE
    with subprocess.Popen(command, start_new_session=True, **kwargs) as process:
        try:
            output, error = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # The process group was created by this call, never a provider or
            # unrelated engine process. Preserve the root/engine identity opts.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                output, error = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                output = error = None
            raise subprocess.TimeoutExpired(command, timeout, output=output, stderr=error) from None
        if check and process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, output=output, stderr=error)
        return subprocess.CompletedProcess(command, process.returncode, output, error)


def prepare_gpu_environment(env):
    """Apply only bounded NVIDIA loader selectors to the explicit child env."""
    from deployment.gcube.graphics_runtime import GraphicsRuntimeError, prepare_graphics_runtime
    try:
        updates, facts = prepare_graphics_runtime(env)
    except GraphicsRuntimeError as error:
        allowed = {'GPU_GRAPHICS_RUNTIME_PATH_UNSAFE', 'GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE'}
        code = str(error) if str(error) in allowed else 'GPU_BROWSER_PROBE_FAILED'
        failure = BootError(code)
        failure.diagnostics = {'schema_version': 1, 'render_mode': 'gpu-required',
                               'gpu_profile': 'egl', 'failed_stage': 'C', 'reason_code': code,
                               'stages': [{'id': 'C', 'status': 'FAIL', 'reason_code': code}]}
        raise failure from None
    allowed_updates = {'__EGL_VENDOR_LIBRARY_FILENAMES', 'VK_DRIVER_FILES', 'VK_ICD_FILENAMES'}
    env.update({name: value for name, value in updates.items() if name in allowed_updates})
    return facts


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


def managed_runtime_link(source, target, storage, link_root):
    """Update only a fixed image link in its private writable runtime directory.

    Immutable image parents remain root-owned. A provider may run the bootstrap
    as UID 1000, so it must not need to rename or unlink files in those parents.
    """
    source, target, link_root = Path(source), Path(target).resolve(), Path(link_root)
    name = 'audio' if source.name == 'audio' else 'cache'
    leaf = link_root / name
    if (not source.is_symlink() or os.readlink(source) != str(leaf)):
        return False
    if link_root.is_symlink() or not link_root.is_dir() or link_root.resolve() != link_root:
        raise BootError('IMAGE_WRITABLE_PATH_CONFLICT')
    info = link_root.stat()
    uid, gid = getattr(storage, 'uid', os.geteuid()), getattr(storage, 'gid', os.getegid())
    if info.st_uid != uid or info.st_gid != gid or stat.S_IMODE(info.st_mode) != 0o700:
        raise BootError('IMAGE_WRITABLE_PATH_CONFLICT')
    if leaf.exists() or leaf.is_symlink():
        if not leaf.is_symlink() or leaf.lstat().st_uid != uid or leaf.lstat().st_gid != gid:
            raise BootError('IMAGE_WRITABLE_PATH_CONFLICT')
        previous = Path(os.readlink(leaf))
        allowed = (previous == Path(storage.audio_root).resolve() if name == 'audio' else
                   previous.parent == Path(storage.cache_root).resolve() and
                   re.fullmatch(r'(?:cpu|gpu)-[a-f0-9]{64}', previous.name))
        if not previous.is_absolute() or not allowed:
            raise BootError('IMAGE_WRITABLE_PATH_CONFLICT')
        if previous == target:
            return True
    pending = link_root / ('.' + name + '-' + uuid.uuid4().hex)
    try:
        pending.symlink_to(target, target_is_directory=True)
        if os.geteuid() == 0:
            os.chown(pending, uid, gid, follow_symlinks=False)
        os.replace(pending, leaf)  # Only the image-owned runtime symlink changes.
    finally:
        if pending.is_symlink():
            pending.unlink()
    return True


def configure_image_paths(app, storage, namespace, *, link_root='/run/world-engine'):
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
    if not managed_runtime_link(Path(app) / 'cache', cache, storage, link_root):
        link_image_path(Path(app) / 'cache', cache)
    audio = Path(app) / 'assets/audio'
    saved = Path(app) / 'assets/image_audio_seed'
    if not audio.is_symlink() and audio.is_dir():
        if saved.exists():
            raise BootError('IMAGE_AUDIO_SEED_CONFLICT')
        audio.rename(saved)
    if not managed_runtime_link(audio, storage.audio_root, storage, link_root):
        link_image_path(audio, storage.audio_root)
    return cache


def run_engine(status, stopping_event):
    began = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    if str(APP) != '/opt/world-engine/world-simulation-shorts-engine':
        raise BootError('IMAGE_LAYOUT_REQUIRED')
    from deployment.gcube.storage import NativePersonalStorage
    from deployment.gcube.graphics_start import select_graphics_profile
    from deployment.gcube.gpu_access import collect_device_groups
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
    graphics_facts = prepare_gpu_environment(env)
    # Only descriptor selectors returned by the bounded NVIDIA loader helper
    # change. The same explicit env is passed to admission and the engine child;
    # no user credentials or global process environment are added to logs.
    print('GCUBE NVIDIA graphics loader: ' + json.dumps(graphics_facts, ensure_ascii=False,
          separators=(',', ':'), allow_nan=False), flush=True)
    device_groups = collect_device_groups()
    # Prove graphics access with the same unprivileged identity as the server.
    def run_probe(command, **kwargs):
        if os.geteuid() == 0:
            kwargs.update(user=account.pw_uid, group=account.pw_gid, extra_groups=device_groups)
        return run_graphics_probe(command, **kwargs)
    probe_env = dict(env)
    probe_env.pop('WORLD_ENGINE_OWNER_CODE', None)
    gpu = select_graphics_profile(probe_env, runner=run_probe)
    gpu['graphics_runtime_preparation'] = graphics_facts
    cache = configure_image_paths(APP, storage, gpu['cache_namespace'])
    if os.geteuid() == 0:
        os.setgroups(device_groups)
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
    child_env['WORLD_ENGINE_GPU_PROFILE'] = gpu['gpu_profile']
    child_env['HOME'] = account.pw_dir
    command = [sys.executable, '-m', 'deployment.gcube.server', '--host', '0.0.0.0',
               '--port', '8000', '--internal-port', '8001', '--state-root', str(runtime),
               '--access-file', str(runtime / 'owner-code.txt'), '--max-duration', str(duration),
               '--maximum-job-seconds', str(job_seconds)]
    if env.get('WORLD_ENGINE_PUBLIC_ORIGIN'):
        command += ['--public-origin', env['WORLD_ENGINE_PUBLIC_ORIGIN']]
    if env.get('WORLD_ENGINE_LOCAL_MODE') == '1':
        command += ['--local-mode']
    from deployment.gcube.telemetry import Telemetry
    telemetry = Telemetry(runtime)
    # Port 8000 is live during the bounded preflight. Release its read-only
    # startup listener only when the private/authenticated engine can take over.
    status.close()
    if stopping_event.is_set():
        return 0
    server = subprocess.Popen(command, cwd=APP, env=child_env, stdin=subprocess.DEVNULL)
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping_event.set()
        if not stopping and server.poll() is None:
            stopping = True
            server.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if stopping_event.is_set():
        stop(None, None)
    health_opener = build_opener(ProxyHandler({}))
    try:
        telemetry.start()
        deadline = time.monotonic() + 60
        while server.poll() is None and time.monotonic() < deadline:
            try:
                with health_opener.open('http://127.0.0.1:8000/api/health', timeout=2) as response:
                    value = json.load(response)
                    if response.status == 200 and value.get('ok') and value.get('engine_ready') is True:
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


def main():
    """Keep liveness separate from permission to render or engine readiness.

    A rejected GPU or missing configuration remains a visibly blocked, read-only
    status service. It never admits a render, creates an owner login, changes
    storage policy, retries forever, or silently selects a CPU renderer.
    """
    from deployment.gcube.boot_status import BootStatusServer
    status = BootStatusServer().start()
    stopping = threading.Event()

    def stop(_signum, _frame):
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        try:
            result = run_engine(status, stopping)
            if stopping.is_set():
                return result
            raise BootError('WORLD_ENGINE_PROCESS_EXITED')
        except Exception as error:
            if stopping.is_set():
                return 0
            code = getattr(error, 'code', 'STARTUP_BLOCKED')
            diagnostics = getattr(error, 'diagnostics', None)
            if isinstance(code, str) and code.startswith('GPU_') and isinstance(diagnostics, dict):
                status.set_phase('blocked', error_code=code, gpu_diagnostics=diagnostics)
            else:
                status.set_phase('blocked', error_code=code)
            status.start()
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            print('GCUBE startup blocked: ' + status.error_code, file=sys.stderr, flush=True)
            observed = status.gpu_diagnostics
            if isinstance(observed, dict) and observed:
                print('GCUBE GPU diagnosis: ' + json.dumps(observed, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False), file=sys.stderr, flush=True)
            while not stopping.wait(1):
                pass
            return 0
    finally:
        status.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Never log environment values, owner code or raw third-party responses.
        from deployment.gcube.boot_status import safe_error_code
        print('GCUBE startup blocked: ' + safe_error_code(getattr(error, 'code', None)), file=sys.stderr)
        sys.exit(2)
