"""Operator-only launcher for the separately approved, context-only diagnostic.

No environment values, raw child logs, owner codes, or credentials are emitted.
No container or Studio settings are changed. This does not stop provider billing.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import re
import subprocess
import sys

CONTROLLER = Path('/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller')
WORKER = b'/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/world-simulation-shorts-engine/recovery/studio-cold-start-v2/worker.py'
BACKEND_SHA = '06c7bb84236ab9bdef5044a5b6ceac2b3743eae044c163218953f671d31b7bee'


def require(value, code):
    if not value:
        raise RuntimeError(code)


def allowed_environment_names(source):
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_runtime_environment')
    assignment = next(node for node in function.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'names' for target in node.targets))
    names = ast.literal_eval(assignment.value)
    require(isinstance(names, set) and all(isinstance(name, str) for name in names), 'DIAG_RUNTIME_ENV_ALLOWLIST_INVALID')
    return names


def selected_environment(stream, allowed):
    # Read key first. For a non-allowlisted key, discard value bytes individually:
    # no whole-environment buffer, full secret record, or decoded secret is created.
    result, key, value, selected, in_value = {}, bytearray(), bytearray(), None, False
    total = 0
    while True:
        byte = stream.read(1)
        if not byte:
            break
        total += 1
        require(total <= 1024 * 1024, 'DIAG_WORKER_ENV_TOO_LARGE')
        if byte == b'\0':
            if selected is not None:
                result[selected] = value.decode('utf-8', 'surrogateescape')
            key, value, selected, in_value = bytearray(), bytearray(), None, False
        elif not in_value and byte == b'=':
            in_value = True
            name = key.decode('ascii', 'ignore')
            selected = name if name in allowed else None
        elif not in_value:
            require(len(key) < 256, 'DIAG_WORKER_ENV_KEY_TOO_LONG')
            key.extend(byte)
        elif selected is not None:
            require(len(value) < 65536, 'DIAG_WORKER_ENV_VALUE_TOO_LONG')
            value.extend(byte)
    return result


def worker_identity(pid):
    root = Path('/proc') / str(pid)
    status = {line.split(':', 1)[0]: line.split(':', 1)[1].strip() for line in (root / 'status').read_text().splitlines() if ':' in line}
    require(set(map(int, status['Uid'].split())) == {1000} and set(map(int, status['Gid'].split())) == {1000}, 'DIAG_EXISTING_WORKER_IDENTITY_REQUIRED')
    arguments = (root / 'cmdline').read_bytes().split(b'\0')
    require(WORKER in arguments, 'DIAG_EXISTING_WORKER_COMMAND_REQUIRED')
    ticks = (root / 'stat').read_text().rsplit(') ', 1)[1].split()[19]
    return {'pid': pid, 'ticks': ticks, 'groups': sorted(map(int, status['Groups'].split()))}


def safe_stdout(data):
    # Only the diagnostic's bounded final summary is accepted. Other output is discarded.
    lines = data.decode('utf-8', 'replace').splitlines()
    for line in reversed(lines):
        try:
            value = json.loads(line)
            if isinstance(value, dict) and value.get('status') in {'PASS_CONTEXT_ONLY', 'WEBGL2_CONTEXT_CREATED_GPU_IDENTITY_PENDING', 'FAIL', 'BLOCKED'}:
                safe = {'status': value['status']}
                for key in ['contextAttempts', 'browserLaunches', 'renderedFrames']:
                    if type(value.get(key)) is int and 0 <= value[key] <= 1:
                        safe[key] = value[key]
                if value.get('resultFile') == 'WEBGL_DIAGNOSTIC.json':
                    safe['resultFile'] = value['resultFile']
                if isinstance(value.get('code'), str) and re.fullmatch(r'(?:DIAG_[A-Z0-9_]{1,110}|UP2_WEBGL2_REQUIRED)', value['code']):
                    safe['code'] = value['code']
                for key in ['diagnosticProcessExitCode', 'launcherExitCode']:
                    if type(value.get(key)) is int and -128 <= value[key] <= 255:
                        safe[key] = value[key]
                for key in ['providerStopRequired', 'workerEnvironmentReused', 'commonGpuLeaseReused']:
                    if type(value.get(key)) is bool:
                        safe[key] = value[key]
                return safe
        except (ValueError, TypeError):
            pass
    return {'status': 'BLOCKED', 'code': 'DIAG_NO_SAFE_CHILD_SUMMARY'}


def inner(args):
    require(os.geteuid() == os.getegid() == 1000, 'DIAG_UID_GID_1000_REQUIRED')
    sys.path.insert(0, str(CONTROLLER))
    from nvidia_backend import lease_helper
    # Reuse the existing original common GPU lease; no renderer, health, or native draw.
    with lease_helper().common_gpu_lease():
        process = subprocess.Popen(['node', str(args.runner), '--approved-single-diagnostic', '--output=' + args.output],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env=dict(os.environ))
        try:
            stdout, _ = process.communicate(timeout=110)
            result = safe_stdout(stdout[:16384])
            result.update(diagnosticProcessExitCode=process.returncode, providerStopRequired=True,
                          workerEnvironmentReused=True, commonGpuLeaseReused=True)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)
            result = {'status': 'BLOCKED', 'code': 'DIAG_PROCESS_DEADLINE_EXCEEDED', 'providerStopRequired': True}
        print(json.dumps(result, separators=(',', ':')), flush=True)
        return 0 if result.get('status') == 'PASS_CONTEXT_ONLY' else 2


def main(args):
    require(args.approved_single_diagnostic, 'DIAG_SEPARATE_GPU_APPROVAL_REQUIRED')
    source = (CONTROLLER / 'nvidia_backend.py').read_bytes()
    require(hashlib.sha256(source).hexdigest() == BACKEND_SHA, 'DIAG_RUNTIME_ENV_SOURCE_CHANGED')
    allowed = allowed_environment_names(source)
    runner = Path(args.runner)
    require(runner.is_absolute() and runner.is_file() and not runner.is_symlink(), 'DIAG_REGULAR_RUNNER_REQUIRED')
    require(hashlib.sha256(runner.read_bytes()).hexdigest() == args.runner_sha256, 'DIAG_RUNNER_TRANSFER_CHANGED')
    if args.inner:
        return inner(args)
    require(os.geteuid() == 0, 'DIAG_EXISTING_CONTAINER_ADMIN_SESSION_REQUIRED')
    identity = worker_identity(args.worker_pid)
    proc = Path('/proc') / str(args.worker_pid)
    with (proc / 'environ').open('rb') as stream:
        environment = selected_environment(stream, allowed)
    require(worker_identity(args.worker_pid) == identity, 'DIAG_WORKER_CHANGED')
    working_directory = os.readlink(proc / 'cwd')

    def drop_identity():
        os.setgroups(identity['groups'])
        os.setgid(1000)
        os.setuid(1000)

    command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--inner', '--approved-single-diagnostic',
               '--runner', str(runner), '--runner-sha256', args.runner_sha256, '--output', args.output]
    child = subprocess.Popen(command, env=environment, cwd=working_directory, preexec_fn=drop_identity,
                             start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        stdout, _ = child.communicate(timeout=120)
        result = safe_stdout(stdout[:16384])
        result['launcherExitCode'] = child.returncode
        result['providerStopRequired'] = True
        print(json.dumps(result, separators=(',', ':')), flush=True)
        return child.returncode
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=3)
        print(json.dumps({'status': 'BLOCKED', 'code': 'DIAG_LAUNCHER_DEADLINE_EXCEEDED', 'providerStopRequired': True}), flush=True)
        return 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker-pid', type=int)
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--runner-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--approved-single-diagnostic', action='store_true')
    parser.add_argument('--inner', action='store_true', help=argparse.SUPPRESS)
    try:
        sys.exit(main(parser.parse_args()))
    except Exception as error:
        code = str(error)
        if not code.startswith('DIAG_') or not code.replace('_', '').isalnum():
            code = 'DIAG_ENVIRONMENT_LAUNCH_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'code': code, 'providerStopRequired': True}), flush=True)
        sys.exit(2)
