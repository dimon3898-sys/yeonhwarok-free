"""Operator-only launcher for the separately approved, context-only diagnostic.

No environment values, raw child logs, owner codes, or credentials are emitted.
No container or Studio settings are changed. This does not stop provider billing.
"""
from __future__ import annotations
import argparse
import ast
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import re
import subprocess
import sys

CONTROLLER = Path('/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller')
WORKER = b'/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/world-simulation-shorts-engine/recovery/studio-cold-start-v2/worker.py'
BACKEND_SHA = '1b3114d43640a8e63b244e5134ca6ab4b1342d196fdf0b79539ed9f3a99d02d1'
STARTUP_BOOTSTRAP = Path('/opt/world-engine-production-studio/bootstrap.py')
STARTUP_BOOTSTRAP_SHA = '9791501263fe146de64510a8747619bb0003ea53f296ec12a7b3335a9bba203a'
IMAGE_DIGEST = 'sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf'
IMAGE_WORKDIR = Path('/opt/world-engine-storage-fix')
STAGES = frozenset({'ARGUMENTS', 'APPROVAL', 'SOURCE_PIN', 'ENV_ALLOWLIST', 'RUNNER_PIN',
    'ADMIN_IDENTITY', 'WORKER_IDENTITY', 'WORKER_ENV_READ', 'WORKER_IDENTITY_RECHECK',
    'WORKER_CWD', 'STARTUP_ENV_CONTRACT', 'IMAGE_CWD_CONTRACT',
    'CHILD_LAUNCH', 'CHILD_WAIT', 'CHILD_TIMEOUT_CLEANUP',
    'INNER_IDENTITY', 'LEASE_IMPORT', 'COMMON_GPU_LEASE', 'DIAGNOSTIC_LAUNCH',
    'DIAGNOSTIC_WAIT', 'DIAGNOSTIC_TIMEOUT_CLEANUP', 'RESULT_OUTPUT', 'UNKNOWN'})
EXCEPTION_TYPES = frozenset({'FileNotFoundError', 'PermissionError', 'ProcessLookupError',
    'NotADirectoryError', 'IsADirectoryError', 'TimeoutExpired', 'OSError', 'RuntimeError',
    'ValueError', 'TypeError', 'KeyError', 'IndexError', 'StopIteration', 'SyntaxError',
    'UnicodeError', 'OtherException'})
diagnostic_stage = 'ARGUMENTS'


def mark_stage(value):
    global diagnostic_stage
    diagnostic_stage = value if value in STAGES else 'UNKNOWN'


def safe_exception(error, stage):
    """Record only closed metadata, never exception text, paths or environment values."""
    code = str(error)
    if not code.startswith('DIAG_') or not code.replace('_', '').isalnum():
        code = 'DIAG_ENVIRONMENT_LAUNCH_FAILED'
    name = type(error).__name__
    number = getattr(error, 'errno', None)
    if type(number) is not int or number not in errno.errorcode:
        number = None
    return {'status': 'BLOCKED', 'code': code, 'providerStopRequired': True,
            'diagnosticStage': stage if stage in STAGES else 'UNKNOWN',
            'exceptionType': name if name in EXCEPTION_TYPES else 'OtherException',
            'errno': number, 'errnoName': errno.errorcode.get(number)}


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


def startup_environment(allowed, environ):
    """Project the pinned, pure startup transform onto capture's existing allowlist.

    Read only this container-exec process's allowed keys. Never inspect another
    process's environ/cwd, read owner files, or rerun startup configuration.
    This is a reconstruction, not a live comparison with the worker environment.
    """
    require(environ.get('WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST') == IMAGE_DIGEST
            and environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') == IMAGE_DIGEST,
            'DIAG_STARTUP_IMAGE_CONTRACT_CHANGED')
    raw = STARTUP_BOOTSTRAP.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == STARTUP_BOOTSTRAP_SHA,
            'DIAG_STARTUP_ENV_SOURCE_CHANGED')
    tree = ast.parse(raw)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'child_environment')
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'SECRET_ENV'
                              for target in node.targets))
    # Execute only this reviewed pure function, never the module or prepare_configuration.
    namespace = {'SECRET_ENV': ast.literal_eval(assignment.value)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<pinned-startup-environment>', 'exec'), namespace)
    root = Path(environ.get('WORLD_ENGINE_STUDIO_STATE_ROOT', ''))
    home = Path(pwd.getpwuid(1000).pw_dir)
    require(root.is_absolute() and '..' not in root.parts
            and not root.is_relative_to('/world-storage'), 'DIAG_EXISTING_STATE_ROOT_REQUIRED')
    require(home.is_absolute(), 'DIAG_EXISTING_UID1000_HOME_REQUIRED')
    for path in (root, root / 'xdg-runtime', home):
        require(path.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)),
                'DIAG_EXISTING_STARTUP_DIRECTORY_REQUIRED')
    for path in (root, root / 'xdg-runtime'):
        info = path.stat()
        require(info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700,
                'DIAG_EXISTING_PRIVATE_DIRECTORY_REQUIRED')
    config = {'root': root, 'owner': root / 'owner-code',
              'origin': environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', ''), 'home': home,
              'xdg': {key: root / suffix for key, suffix in
                      [('XDG_RUNTIME_DIR', 'xdg-runtime'), ('XDG_CONFIG_HOME', 'xdg-config'),
                       ('XDG_CACHE_HOME', 'xdg-cache')]}}
    selected = {key: environ[key] for key in allowed if key in environ}
    require(all(isinstance(value, str) and len(value) < 65536 for value in selected.values()),
            'DIAG_CAPTURE_ENV_VALUE_INVALID')
    transformed = namespace['child_environment'](selected, studio=True, config=config)
    return {key: value for key, value in transformed.items() if key in allowed}


def startup_working_directory():
    # From the unchanged OCI config; startup, worker and backend inherit cwd.
    require(Path.cwd() == IMAGE_WORKDIR and IMAGE_WORKDIR.is_dir()
            and not any(p.is_symlink() for p in (IMAGE_WORKDIR, *IMAGE_WORKDIR.parents)),
            'DIAG_IMAGE_WORKING_DIRECTORY_REQUIRED')
    return str(IMAGE_WORKDIR)


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
                for key in ['providerStopRequired', 'workerEnvironmentDirectlyCompared', 'commonGpuLeaseReused']:
                    if type(value.get(key)) is bool:
                        safe[key] = value[key]
                if value.get('environmentSource') == 'PINNED_STARTUP_CONTRACT':
                    safe['environmentSource'] = value['environmentSource']
                if value.get('diagnosticStage') in STAGES:
                    safe['diagnosticStage'] = value['diagnosticStage']
                if value.get('exceptionType') in EXCEPTION_TYPES:
                    safe['exceptionType'] = value['exceptionType']
                number = value.get('errno')
                if type(number) is int and number in errno.errorcode:
                    safe['errno'] = number
                    safe['errnoName'] = errno.errorcode[number]
                elif 'errno' in value and number is None:
                    safe['errno'] = None
                    safe['errnoName'] = None
                return safe
        except (ValueError, TypeError):
            pass
    return {'status': 'BLOCKED', 'code': 'DIAG_NO_SAFE_CHILD_SUMMARY'}


def inner(args):
    mark_stage('INNER_IDENTITY')
    require(os.geteuid() == os.getegid() == 1000, 'DIAG_UID_GID_1000_REQUIRED')
    mark_stage('LEASE_IMPORT')
    sys.path.insert(0, str(CONTROLLER))
    from nvidia_backend import lease_helper
    # Reuse the existing original common GPU lease; no renderer, health, or native draw.
    mark_stage('COMMON_GPU_LEASE')
    with lease_helper().common_gpu_lease():
        mark_stage('DIAGNOSTIC_LAUNCH')
        process = subprocess.Popen(['node', str(args.runner), '--approved-single-diagnostic', '--output=' + args.output],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env=dict(os.environ))
        try:
            mark_stage('DIAGNOSTIC_WAIT')
            stdout, _ = process.communicate(timeout=110)
            result = safe_stdout(stdout[:16384])
            result.update(diagnosticProcessExitCode=process.returncode, providerStopRequired=True,
                          environmentSource='PINNED_STARTUP_CONTRACT',
                          workerEnvironmentDirectlyCompared=False, commonGpuLeaseReused=True)
        except subprocess.TimeoutExpired as error:
            failure = safe_exception(error, 'DIAGNOSTIC_WAIT')
            mark_stage('DIAGNOSTIC_TIMEOUT_CLEANUP')
            process.kill()
            process.communicate(timeout=3)
            result = {'status': 'BLOCKED', 'code': 'DIAG_PROCESS_DEADLINE_EXCEEDED', 'providerStopRequired': True}
            result.update({key: failure[key] for key in ['diagnosticStage', 'exceptionType', 'errno', 'errnoName']})
        mark_stage('RESULT_OUTPUT')
        print(json.dumps(result, separators=(',', ':')), flush=True)
        return 0 if result.get('status') == 'PASS_CONTEXT_ONLY' else 2


def main(args):
    mark_stage('APPROVAL')
    require(args.approved_single_diagnostic, 'DIAG_SEPARATE_GPU_APPROVAL_REQUIRED')
    mark_stage('SOURCE_PIN')
    source = (CONTROLLER / 'nvidia_backend.py').read_bytes()
    require(hashlib.sha256(source).hexdigest() == BACKEND_SHA, 'DIAG_RUNTIME_ENV_SOURCE_CHANGED')
    mark_stage('ENV_ALLOWLIST')
    allowed = allowed_environment_names(source)
    mark_stage('RUNNER_PIN')
    runner = Path(args.runner)
    require(runner.is_absolute() and runner.is_file() and not runner.is_symlink(), 'DIAG_REGULAR_RUNNER_REQUIRED')
    require(hashlib.sha256(runner.read_bytes()).hexdigest() == args.runner_sha256, 'DIAG_RUNNER_TRANSFER_CHANGED')
    if args.inner:
        return inner(args)
    mark_stage('ADMIN_IDENTITY')
    require(os.geteuid() == 0, 'DIAG_EXISTING_CONTAINER_ADMIN_SESSION_REQUIRED')
    mark_stage('WORKER_IDENTITY')
    identity = worker_identity(args.worker_pid)
    mark_stage('STARTUP_ENV_CONTRACT')
    environment = startup_environment(allowed, os.environ)
    mark_stage('WORKER_IDENTITY_RECHECK')
    require(worker_identity(args.worker_pid) == identity, 'DIAG_WORKER_CHANGED')
    mark_stage('IMAGE_CWD_CONTRACT')
    working_directory = startup_working_directory()

    def drop_identity():
        os.setgroups(identity['groups'])
        os.setgid(1000)
        os.setuid(1000)

    command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--inner', '--approved-single-diagnostic',
               '--runner', str(runner), '--runner-sha256', args.runner_sha256, '--output', args.output]
    mark_stage('CHILD_LAUNCH')
    child = subprocess.Popen(command, env=environment, cwd=working_directory, preexec_fn=drop_identity,
                             start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        mark_stage('CHILD_WAIT')
        stdout, _ = child.communicate(timeout=120)
        result = safe_stdout(stdout[:16384])
        result['launcherExitCode'] = child.returncode
        result['providerStopRequired'] = True
        mark_stage('RESULT_OUTPUT')
        print(json.dumps(result, separators=(',', ':')), flush=True)
        return child.returncode
    except subprocess.TimeoutExpired as error:
        failure = safe_exception(error, 'CHILD_WAIT')
        mark_stage('CHILD_TIMEOUT_CLEANUP')
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=3)
        failure['code'] = 'DIAG_LAUNCHER_DEADLINE_EXCEEDED'
        print(json.dumps(failure), flush=True)
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
        print(json.dumps(safe_exception(error, diagnostic_stage)), flush=True)
        sys.exit(2)
