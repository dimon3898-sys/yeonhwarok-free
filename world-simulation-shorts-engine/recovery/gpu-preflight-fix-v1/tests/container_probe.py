#!/usr/bin/env python3
"""Read-only dependency and real tmpfs probes; never starts Studio or a browser."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO = Path('/opt/world-engine-handoffs/studio-v2/repo')
BACKEND = REPO / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_backend.py'
BACKEND_SHA256 = '4329dc7c28dc7ca5e9c368e398d3f5fa87ec1a1ad3fcfb76971fa5a176365c56'
DEPS = Path('/opt/world-engine/cinematic-world-map')
GIB = 1024 ** 3
EXPECTED_RESERVE = """def reserve():
    if shutil.disk_usage(control_root).free < 2 * 1024**3:
        raise RuntimeError('HANDOFF_PRIVATE_DISK_RESERVE_REQUIRED')
    stat = os.statvfs('/dev/shm')
    if stat.f_frsize * stat.f_blocks < 2 * 1024**3:
        raise RuntimeError('HANDOFF_TWO_GIB_SHARED_MEMORY_REQUIRED')
"""


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source():
    require(BACKEND.is_file(), 'CPU_PACKAGED_BACKEND_REQUIRED')
    raw = BACKEND.read_bytes()
    require(sha(raw) == BACKEND_SHA256, 'CPU_ORIGINAL_BACKEND_CHANGED')
    return raw


def module():
    source()
    sys.path.insert(0, str(BACKEND.parent))
    spec = importlib.util.spec_from_file_location('_cpu_original_nvidia_backend', BACKEND)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def file_fact(path, *, hashed=False):
    path = Path(path)
    require(path.is_file(), 'CPU_EXISTING_DEPENDENCY_FILE_MISSING')
    info = path.stat()
    result = {'path': str(path), 'realPath': str(path.resolve(strict=True)),
              'bytes': info.st_size, 'mode': oct(info.st_mode & 0o7777),
              'readable': os.access(path, os.R_OK),
              'executable': os.access(path, os.X_OK)}
    if hashed:
        result['sha256'] = sha(path.read_bytes())
    return result


def dependency_case(case):
    backend = module()
    facts = {'originalBackendPath': str(BACKEND), 'originalBackendSHA256': BACKEND_SHA256,
             'existingImageRootPresent': 'WORLD_ENGINE_NODE_DEPS' in os.environ,
             'browserLaunched': False, 'installationPerformed': False}
    if case == 'missing-root':
        # The deliberately absent input reproduces this specific configuration
        # failure. It is not represented as an observation of the GPU session.
        try:
            backend.dependency_facts(environ={}, export_root='/world-storage')
        except RuntimeError as error:
            require(str(error) == 'HANDOFF_EXISTING_PLAYWRIGHT_ROOT_REQUIRED',
                    'CPU_MISSING_ROOT_WRONG_FAILURE')
            facts.update({'expectedBlockVerified': True, 'observedCode': str(error),
                          'rootInput': 'INTENTIONALLY_ABSENT'})
            return facts
        raise RuntimeError('CPU_MISSING_ROOT_NOT_BLOCKED')
    if case == 'existing-root':
        facts['rootInput'] = 'EXPLICIT_EXISTING_PATH'
        metadata = backend.dependency_facts(
            environ={'WORLD_ENGINE_NODE_DEPS': str(DEPS)}, export_root='/world-storage')
    else:
        require(case == 'inherited-root', 'CPU_DEPENDENCY_CASE_INVALID')
        require(os.environ.get('WORLD_ENGINE_NODE_DEPS') == str(DEPS),
                'CPU_CANDIDATE_IMAGE_ROOT_ENV_REQUIRED')
        facts['rootInput'] = 'INHERITED_IMAGE_ENVIRONMENT'
        metadata = backend.dependency_facts(export_root='/world-storage')
        require(backend._runtime_environment().get('WORLD_ENGINE_NODE_DEPS') == str(DEPS),
                'CPU_RENDER_CHILD_ROOT_NOT_PRESERVED')
        facts['renderChildRootPreserved'] = True
    # Resolve the real module entry files using this same installed Node tree.
    script = ("const p=require('node:path'),fs=require('node:fs');"
              "const r=require('node:module').createRequire(p.join(process.argv[1],'package.json'));"
              "process.stdout.write(JSON.stringify(Object.fromEntries(['playwright','playwright-core'].map(n=>"
              "[n,{entry:fs.realpathSync(r.resolve(n)),package:fs.realpathSync(r.resolve(n+'/package.json'))}]))));")
    result = subprocess.run(['node', '-e', script, str(DEPS)], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=10, check=False)
    require(result.returncode == 0 and len(result.stdout) < 8192, 'CPU_MODULE_FILE_RESOLUTION_FAILED')
    resolved = json.loads(result.stdout)
    files = [file_fact(DEPS / 'package.json', hashed=True)]
    for name in ('playwright', 'playwright-core'):
        for key in ('entry', 'package'):
            path = Path(resolved[name][key])
            require(path.is_relative_to(DEPS), 'CPU_MODULE_ESCAPES_EXISTING_ROOT')
            files.append(file_fact(path, hashed=True))
    for name in ('node', 'ffmpeg', 'ffprobe'):
        path = shutil.which(name)
        require(path is not None, 'CPU_EXISTING_EXECUTABLE_MISSING')
        fact = file_fact(path)
        require(fact['executable'], 'CPU_EXISTING_EXECUTABLE_NOT_EXECUTABLE')
        files.append(fact)
    chromium = file_fact('/usr/bin/chromium', hashed=True)
    require(chromium['executable'], 'CPU_CHROMIUM_NOT_EXECUTABLE')
    files.append(chromium)
    facts.update({'dependencyRoot': str(DEPS), 'metadata': metadata, 'files': files})
    return facts


def exact_reserve(control_root):
    tree = ast.parse(source(), filename=str(BACKEND))
    classes = [x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'NvidiaPresentationBackend']
    require(len(classes) == 1, 'CPU_ORIGINAL_PREFLIGHT_CLASS_REQUIRED')
    methods = [x for x in classes[0].body if isinstance(x, ast.FunctionDef) and x.name == 'preflight']
    require(len(methods) == 1, 'CPU_ORIGINAL_PREFLIGHT_REQUIRED')
    nodes = [x for x in methods[0].body if isinstance(x, ast.FunctionDef) and x.name == 'reserve']
    require(len(nodes) == 1, 'CPU_ORIGINAL_RESERVE_REQUIRED')
    reserve = nodes[0]
    expected = ast.parse(EXPECTED_RESERVE).body[0]
    canonical = lambda node: ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
    require(canonical(reserve) == canonical(expected), 'CPU_ORIGINAL_RESERVE_AST_CHANGED')
    # Compile the original entire nested function unchanged. Actual os/shutil
    # and a real disposable directory are the only supplied dependencies.
    scope = {'os': os, 'shutil': shutil, 'control_root': control_root}
    code = compile(ast.Module(body=[reserve], type_ignores=[]), str(BACKEND), 'exec')
    exec(code, scope)
    return scope['reserve'], sha(canonical(reserve).encode())


def shm_case(requested):
    require(requested in (2000000000, 2 * GIB, 3000000000), 'CPU_SHM_CASE_INVALID')
    info = os.statvfs('/dev/shm')
    total = info.f_frsize * info.f_blocks
    page = os.sysconf('SC_PAGE_SIZE')
    require(requested <= total < requested + page, 'CPU_ACTUAL_SHM_SIZE_MISMATCH')
    mounts = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        before, after = line.split(' - ', 1)
        fields, filesystem = before.split(), after.split()
        if fields[4] == '/dev/shm':
            mounts.append({'mountPoint': fields[4], 'mountOptions': fields[5],
                           'filesystem': filesystem[0], 'superOptions': filesystem[2]})
    require(len(mounts) == 1 and mounts[0]['filesystem'] == 'tmpfs'
            and 'rw' in mounts[0]['mountOptions'].split(','), 'CPU_SHM_WRITABLE_TMPFS_REQUIRED')
    content = b'WORLD_ENGINE_CPU_PREFLIGHT_SHM_NON_SENSITIVE_PROBE\n'
    descriptor, filename = tempfile.mkstemp(prefix='we-preflight-', dir='/dev/shm')
    path = Path(filename)
    try:
        require(os.fstat(descriptor).st_uid == 1000, 'CPU_SHM_PROBE_OWNER_MISMATCH')
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        require(path.read_bytes() == content, 'CPU_SHM_READBACK_MISMATCH')
    finally:
        path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='we-preflight-private-') as directory:
        disk = shutil.disk_usage(directory)
        require(disk.free >= 2 * GIB, 'CPU_FIXTURE_PRIVATE_DISK_TOO_SMALL')
        reserve, reserve_hash = exact_reserve(directory)
        observed = 'PASS'
        try:
            reserve()
        except RuntimeError as error:
            observed = str(error)
        expected = 'HANDOFF_TWO_GIB_SHARED_MEMORY_REQUIRED' if total < 2 * GIB else 'PASS'
        require(observed == expected, 'CPU_ORIGINAL_SHM_GATE_WRONG_RESULT')
    return {'originalBackendPath': str(BACKEND), 'originalBackendSHA256': BACKEND_SHA256,
            'originalReserveBodyASTSHA256': reserve_hash, 'originalReserveBodyUnchanged': True,
            'requestedBytes': requested, 'actualTotalBytes': total, 'pageBytes': page,
            'availableBytes': info.f_frsize * info.f_bavail, 'mount': mounts[0],
            'uid1000WriteReadUnlinkVerified': True, 'privateDiskFreeBytes': disk.free,
            'requiredSharedMemoryBytes': 2 * GIB, 'observedGateResult': observed,
            'expectedBlockVerified': total < 2 * GIB}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, choices=('missing-root', 'existing-root', 'inherited-root', 'shm'))
    parser.add_argument('--requested-shm-bytes', type=int)
    args = parser.parse_args()
    result = {'schema': 'WORLD_ENGINE_GPU_PREFLIGHT_CPU_PROBE_V1', 'case': args.case,
              'gpuExecuted': False, 'browserLaunched': False, 'renderExecuted': False,
              'authenticationInitialized': False}
    try:
        require(os.geteuid() == 1000 and os.getegid() == 1000, 'CPU_UID_GID_1000_REQUIRED')
        facts = shm_case(args.requested_shm_bytes) if args.case == 'shm' else dependency_case(args.case)
        result.update({'status': 'PASS', 'facts': facts})
        code = 0
    except Exception as error:
        message = str(error)
        safe = message if re.fullmatch(r'[A-Z][A-Z0-9_]{1,119}', message) else 'CPU_PROBE_OPERATION_FAILED'
        result.update({'status': 'BLOCKED', 'errorCode': safe})
        code = 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
