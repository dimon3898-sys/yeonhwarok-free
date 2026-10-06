"""Repeatable, private Codespaces startup; refresh only a verified idle server.

No hosting account, public port configuration, render, or owner-code rotation is
performed. Readiness records change only after a replacement is healthy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
PROC_ROOT = Path('/proc')
sys.path.insert(0, str(APP))
from deployment.security import SecurityError, codespaces_origin, ensure_access_file, private_json


class StartupError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _runtime_preflight():
    manifest = json.loads((APP/'data/production_rhythm_promotion_v001.json').read_text())
    mismatches = [name for name, digest in manifest['source_manifest'].items()
                  if hashlib.sha256((APP/name).read_bytes()).hexdigest() != digest]
    if mismatches:
        raise StartupError('CERTIFIED_SOURCE_MISMATCH', 'Certified source mismatch: '+', '.join(mismatches))
    for exe in ('ffmpeg', 'ffprobe', 'node', 'chromium'):
        if not shutil.which(exe):
            raise StartupError('MISSING_DEPENDENCY', 'Missing runtime dependency: '+exe)
    modules = REPO/'cinematic-world-map/node_modules'
    image_modules = Path('/opt/world-engine/cinematic-world-map/node_modules')
    if not modules.exists() and image_modules.is_dir():
        modules.symlink_to(image_modules, target_is_directory=True)
    if not (modules/'playwright').is_dir():
        raise StartupError('MISSING_DEPENDENCY', 'Run frozen npm ci in cinematic-world-map before startup.')
    from engine.production import production_default_status
    from engine.assets import validate_assets
    import numpy, scipy, PIL, jsonschema
    if not production_default_status().get('active'):
        raise StartupError('CERTIFICATE_INCOMPLETE', 'Production certificate/assets are incomplete; preserving the approved default.')
    if not validate_assets().get('passed'):
        raise StartupError('ASSETS_INVALID', 'Required preserved assets failed validation.')
    return len(manifest['source_manifest'])


def _source_fingerprint(args, origin):
    # Include policy/worker/startup code outside the independently certified core.
    names = ('deployment/__init__.py', 'deployment/security.py',
             'deployment/mobile_server.py', 'deployment/resume_evidence.py',
             'deployment/start_codespace.py', 'deployment/codespaces_autostart.py',
             'data/production_rhythm_promotion_v001.json')
    files = {name: hashlib.sha256((APP/name).read_bytes()).hexdigest() for name in names}
    contract = {'files': files, 'port': args.port, 'internal_port': args.internal_port,
                'public_origin': origin, 'interpreter': str(Path(sys.executable).absolute())}
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def _options(argv):
    options = {}
    for i in range(0, len(argv), 2):
        if i+1 >= len(argv) or not argv[i].startswith('--') or argv[i] in options:
            return None
        options[argv[i]] = argv[i+1]
    return options


def _snapshot(pid):
    """Capture process start identity and argv without trusting a pid file alone."""
    root = PROC_ROOT/str(pid)
    try:
        if root.stat().st_uid != os.getuid():
            raise StartupError('PROCESS_NOT_OWNED', 'The recorded process has a different owner.')
        before = (root/'stat').read_text()
        parts = before[before.rfind(')')+2:].split()
        if parts[0] == 'Z':
            return None
        ticks = int(parts[19])  # Linux stat field 22; field 3 starts this slice.
        argv = (root/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
        executable = str((root/'exe').resolve(strict=True))
        after = (root/'stat').read_text()
        after_parts = after[after.rfind(')')+2:].split()
        if (int(after_parts[19]) != ticks or after_parts[0] == 'Z' or root.stat().st_uid != os.getuid() or
                str((root/'exe').resolve(strict=True)) != executable or
                (root/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0') != argv):
            raise StartupError('PROCESS_CHANGED', 'Process identity changed during inspection.')
        return {'pid': pid, 'start_ticks': ticks, 'argv': argv, 'executable': executable}
    except (FileNotFoundError, ProcessLookupError):
        return None
    except (OSError, UnicodeError, ValueError, IndexError):
        raise StartupError('PROCESS_UNVERIFIABLE', 'The recorded process cannot be safely identified.') from None


def _owned_process(pid, state, args):
    process = _snapshot(pid)
    if process is None:
        return None
    argv = process['argv']
    options = _options(argv[3:]) if argv[1:3] == ['-m', 'deployment.mobile_server'] else None
    allowed = {'--state-root', '--access-file', '--host', '--port', '--internal-port', '--public-origin'}
    if (len(argv) < 3 or argv[0] != str(Path(sys.executable).absolute()) or
            process['executable'] != str(Path(sys.executable).resolve()) or options is None or
            set(options)-allowed or options.get('--state-root') != str(state) or
            options.get('--access-file') != str(state/'owner-code.txt') or
            options.get('--host') != '0.0.0.0' or options.get('--port') != str(args.port) or
            options.get('--internal-port') != str(args.internal_port)):
        raise StartupError('PROCESS_NOT_OWNED', 'PID does not identify this exact deployment server; it was not stopped.')
    return process


def _assert_idle(state):
    jobs = state/'jobs'
    if jobs.is_symlink():
        raise StartupError('JOB_RECEIPT_UNREADABLE', 'Job receipts cannot be safely inspected.')
    for path in jobs.glob('job_*.json'):
        try:
            if path.is_symlink():
                raise ValueError()
            record = json.loads(path.read_text())
            if not isinstance(record, dict):
                raise ValueError()
            if re.fullmatch(r'job_[a-f0-9]{12}\.failure\.json', path.name):
                continue  # Worker diagnostics have no ticket job_id/status.
            if not re.fullmatch(r'job_[a-f0-9]{12}', record.get('job_id', '')):
                raise ValueError()
            if path.name != record['job_id']+'.json' or record.get('status') not in {
                    'queued', 'rendering', 'interrupted', 'complete', 'failed', 'blocked', 'cancelled'}:
                raise ValueError()
            if record['status'] in {'queued', 'rendering'}:
                raise StartupError('ACTIVE_JOBS', 'Queued or rendering jobs prevent server refresh; existing state was preserved.')
        except (OSError, ValueError, TypeError):
            raise StartupError('JOB_RECEIPT_UNREADABLE', 'A job receipt is unreadable; refresh was refused.') from None
    _assert_no_worker(state)


def _assert_no_worker(state):
    # Workers are separate sessions: a stale/failed receipt alone cannot prove idle.
    for root in PROC_ROOT.iterdir():
        if not root.name.isdecimal():
            continue
        try:
            if root.stat().st_uid != os.getuid():
                continue
            argv = (root/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
            is_worker = (argv[1:3] == ['-m', 'deployment.mobile_server'] or
                         (len(argv) > 1 and argv[1] == str(APP/'deployment/mobile_server.py')))
            if is_worker and '--worker-ticket' in argv:
                options = _options(argv[3:] if argv[1] == '-m' else argv[2:])
                if options is None:
                    raise StartupError('WORKER_UNVERIFIABLE', 'A deployment worker cannot be safely inspected.')
                if options.get('--state-root') == str(state):
                    raise StartupError('ACTIVE_WORKER', 'A render worker is still running; refresh was refused.')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, UnicodeError):
            raise StartupError('WORKER_UNVERIFIABLE', 'An owned process cannot be inspected for active workers.') from None


def _stop_owned(process, state, args):
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise StartupError('SAFE_REFRESH_UNAVAILABLE', 'This platform cannot safely pin a process identity for refresh.')
    fd = os.pidfd_open(process['pid'])
    try:
        current = _owned_process(process['pid'], state, args)
        if current != process:
            raise StartupError('PROCESS_CHANGED', 'Process identity changed before refresh; no signal was sent.')
        _assert_idle(state)  # Recheck immediately before graceful shutdown.
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        # Linux pidfd becomes readable on exit; no PID reuse can receive this signal.
        if not select.select([fd], [], [], 15)[0]:
            raise StartupError('SHUTDOWN_TIMEOUT', 'Graceful shutdown exceeded 15 seconds; no force kill or replacement was attempted.')
    finally:
        os.close(fd)


def _healthy(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            value = json.loads(response.read(4096))
            return response.status == 200 and isinstance(value, dict) and value.get('ok') is True and value.get('authentication_required') is True
    except (OSError, ValueError, TypeError):
        return False


def _ports_free(args):
    for port in (args.port, args.internal_port):
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                raise StartupError('PORT_IN_USE', f'Port {port} belongs to an existing service; nothing was stopped.')


def _wait_ready(process, state, args):
    deadline = time.monotonic()+15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise StartupError('SERVER_EXITED', 'Server exited; inspect the private runtime server.log.')
        if _healthy(args.port):
            owned = _owned_process(process.pid, state, args)
            if owned is not None:
                return owned
        time.sleep(.25)
    raise StartupError('READINESS_TIMEOUT', 'Readiness timed out; previous records and project state were preserved.')


def _read_record(path, *, pid=False):
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink():
            raise ValueError()
        value = int(path.read_text().strip()) if pid else json.loads(path.read_text())
        if (pid and value <= 0) or (not pid and not isinstance(value, dict)):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise StartupError('STARTUP_RECORD_INVALID', 'Existing startup records are unreadable; they were preserved.') from None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=7860)
    parser.add_argument('--internal-port', type=int, default=7861)
    parser.add_argument('--state-root', type=Path, default=APP/'deployment/runtime/mobile')
    parser.add_argument('--refresh', action='store_true', help='Gracefully restart only this verified idle deployment server.')
    parser.add_argument('--no-sync', action='store_true', help='Internal second stage: start from the already checked checkout.')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or not 1 <= args.internal_port <= 65535 or args.port == args.internal_port:
        raise StartupError('INVALID_PORTS', 'Choose two different ports in the range 1–65535.')
    # Keep the cached Codespaces postStartCommand path unchanged. Once this
    # script is pulled, every container start can update main before importing
    # the gateway in a fresh child process. Local development remains offline.
    if os.environ.get('CODESPACES') == 'true' and not args.no_sync:
        from deployment.codespaces_autostart import automatic_start
        return automatic_start(args)
    origin = codespaces_origin(args.port)
    state = args.state_root.resolve()
    if args.state_root.is_symlink() or not state.is_relative_to(APP/'deployment/runtime'):
        raise StartupError('UNSAFE_STATE_ROOT', 'State must be inside the new deployment/runtime directory.')
    count = _runtime_preflight()
    fingerprint = _source_fingerprint(args, origin)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    access = state/'owner-code.txt'
    ensure_access_file(access)
    pidfile, markerfile = state/'server.pid', state/'startup-ready.json'
    pid, marker = _read_record(pidfile, pid=True), _read_record(markerfile)
    old = _owned_process(pid, state, args) if pid is not None else None
    refreshed = False
    if old is not None:
        if marker is not None and (marker.get('pid') != pid or marker.get('start_ticks') != old['start_ticks']):
            raise StartupError('PROCESS_CHANGED', 'Startup record belongs to another process instance; nothing was stopped.')
        same_source = marker is not None and marker.get('source_fingerprint') == fingerprint
        if same_source and not args.refresh and _healthy(args.port):
            print(json.dumps({'status': 'already_running', 'port': args.port, 'pid': pid, 'access_file': str(access)}))
            return 0
        _assert_idle(state)
        _stop_owned(old, state, args)
        refreshed = True
    else:
        # Fresh startup may recover queued receipts, but cannot overlap a worker.
        _assert_no_worker(state)
    _ports_free(args)
    command = [str(Path(sys.executable).absolute()), '-m', 'deployment.mobile_server',
               '--state-root', str(state), '--access-file', str(access), '--host', '0.0.0.0',
               '--port', str(args.port), '--internal-port', str(args.internal_port)]
    if origin:
        command += ['--public-origin', origin]
    logpath = state/'server.log'
    if logpath.is_symlink():
        raise StartupError('UNSAFE_LOG_PATH', 'The private log path is a symlink; startup was refused.')
    fd = os.open(logpath, os.O_WRONLY|os.O_CREAT|os.O_APPEND|getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'ab', buffering=0) as log:
        process = subprocess.Popen(command, cwd=APP, stdout=log, stderr=log,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        ready = _wait_ready(process, state, args)
    except StartupError:
        # Only a newly spawned, still exact-owned and idle child can be cleaned up.
        # Failure to prove that leaves it for inspection, never a force kill.
        try:
            owned = _owned_process(process.pid, state, args)
            if owned is not None:
                _stop_owned(owned, state, args)
        except (StartupError, OSError):
            pass
        raise
    private_json(markerfile, {'format': 'world-codespaces-ready-v1', 'pid': ready['pid'],
                             'start_ticks': ready['start_ticks'], 'source_fingerprint': fingerprint,
                             'port': args.port, 'internal_port': args.internal_port, 'public_origin': origin,
                             'interpreter': str(Path(sys.executable).absolute())})
    private_json(pidfile, ready['pid'])
    print(json.dumps({'status': 'refreshed' if refreshed else 'started', 'port': args.port,
                      'pid': process.pid, 'access_file': str(access), 'source_hashes_verified': count}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (StartupError, SecurityError) as error:
        print(f'Startup blocked: {error.code}. {error}', file=sys.stderr)
        raise SystemExit(2)
