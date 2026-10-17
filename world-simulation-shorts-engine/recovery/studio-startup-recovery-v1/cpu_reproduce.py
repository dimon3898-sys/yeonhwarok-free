#!/usr/bin/env python3
"""Read-only immutable Studio image startup probes on a free hosted CPU runner.

No GPU device, render request, registry push, deployment or production secret is
used. Synthetic HTTPS origin / owner bytes exist only inside disposable test
containers. The three default-entrypoint probes are actual container starts;
the optional-policy probe invokes only the original configuration function.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


IMAGE = ('ghcr.io/dimon3898-sys/world-simulation-shorts-engine@'
         'sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94')
DIGEST = IMAGE.split('@', 1)[1]
ENTRYPOINT = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B',
              '/opt/world-engine-production-studio/bootstrap.py']
TEST_ORIGIN = 'https://studio-startup-test.invalid'
TEST_OWNER = 'TEST_ONLY_NOT_AN_OPERATOR_CREDENTIAL_20261018'
CODE = re.compile(r'[A-Z][A-Z0-9_]{1,99}')
SAFE_KEYS = {'schema', 'status', 'state', 'stage', 'errorCode', 'code',
             'renderAllowed', 'gpuRenderingVerified', 'configurationValidated',
             'operatorPolicyPresent', 'probeOnly'}


def command(arguments, *, timeout=120):
    return subprocess.run(arguments, capture_output=True, timeout=timeout,
                          check=False, env=dict(os.environ))


def docker(*arguments, timeout=120):
    return command(['docker', *arguments], timeout=timeout)


def required_json(arguments):
    result = docker(*arguments)
    if result.returncode:
        raise RuntimeError('CPU_DOCKER_COMMAND_FAILED')
    return json.loads(result.stdout)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sanitized_json_lines(raw):
    records = []
    for line in raw.decode('utf-8', errors='replace').splitlines():
        try:
            source = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(source, dict):
            continue
        row = {}
        for key in SAFE_KEYS & source.keys():
            value = source[key]
            if isinstance(value, bool) or value is None:
                row[key] = value
            elif isinstance(value, str) and CODE.fullmatch(value):
                row[key] = value
        if row:
            records.append(row)
    return records


def stream_record(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'sanitizedRecords': sanitized_json_lines(raw),
            'rawPublished': False}


def run_case(name, *, environment, expected_code=None, expected_exit=1,
             isolated_configuration=False):
    suffix = os.environ.get('GITHUB_RUN_ID', str(os.getpid()))
    container = f'studio-startup-cpu-{suffix}-{name}'
    create = ['create', '--name', container, '--network', 'none', '--memory', '1g',
              '--cpus', '1', '--pids-limit', '128', '--label',
              'world-engine.purpose=isolated-cpu-startup-reproduction']
    for key, value in environment.items():
        create.extend(['--env', f'{key}={value}'])
    if isolated_configuration:
        create.extend(['--entrypoint', '/usr/bin/python3'])
    create.append(IMAGE)
    if isolated_configuration:
        # This imports the byte-identical installed bootstrap and executes only
        # its configuration function. No supervisor or GPU admission is run.
        source = (
            'import json,os,sys; '
            "sys.path.insert(0,'/opt/world-engine-production-studio'); "
            'import bootstrap; bootstrap.prepare_configuration(os.environ); '
            "print(json.dumps({'schema':'STUDIO_CPU_CONFIGURATION_PROBE_V1',"
            "'configurationValidated':True,'operatorPolicyPresent':False,"
            "'probeOnly':True,'renderAllowed':False,'gpuRenderingVerified':False}))"
        )
        create.extend(['-B', '-c', source])
    result = docker(*create)
    if result.returncode:
        raise RuntimeError('CPU_TEST_CONTAINER_CREATE_FAILED')
    began = time.monotonic()
    timed_out = False
    try:
        started = docker('start', '--attach', container, timeout=60)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Only this newly created test container is stopped; no existing object
        # or image is deleted, restarted or pruned by this harness.
        docker('stop', '--time', '5', container)
        started = None
    state = required_json(['inspect', '--format', '{{json .State}}', container])
    stdout = docker('logs', container).stdout
    stderr = docker('logs', container).stderr
    records = sanitized_json_lines(stdout) + sanitized_json_lines(stderr)
    errors = [row.get('errorCode', row.get('code')) for row in records
              if row.get('errorCode', row.get('code'))]
    actual_code = errors[0] if errors else None
    passed = (not timed_out and state.get('Status') == 'exited'
              and state.get('ExitCode') == expected_exit
              and actual_code == expected_code)
    if isolated_configuration:
        passed = passed and any(row.get('configurationValidated') is True
                                and row.get('probeOnly') is True for row in records)
    return {
        'case': name, 'status': 'PASS' if passed else 'FAIL',
        'testScope': 'CONFIGURATION_FUNCTION_ONLY' if isolated_configuration
                     else 'ACTUAL_ORIGINAL_CONTAINER_ENTRYPOINT',
        'syntheticInputsOnly': True, 'deploymentConfigurationChanged': False,
        'expectedExitCode': expected_exit, 'actualContainerExitCode': state.get('ExitCode'),
        'dockerAttachExitCode': started.returncode if started is not None else None,
        'expectedFirstErrorCode': expected_code, 'firstRecordedErrorCode': actual_code,
        'containerState': state.get('Status'), 'oomKilled': state.get('OOMKilled'),
        'timedOut': timed_out, 'elapsedSeconds': round(time.monotonic() - began, 3),
        'stdout': stream_record(stdout), 'stderr': stream_record(stderr),
        'nvidiaHardwareVerified': False, 'gcube5373CauseConfirmed': False,
    }


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else 'studio-startup-cpu-results')
    output.mkdir(parents=True, exist_ok=False)
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or os.environ.get('GITHUB_REPOSITORY') != 'dimon3898-sys/yeonhwarok-free'
            or os.environ.get('RESULT_REPOSITORY_PRIVATE') != 'false'):
        raise RuntimeError('PUBLIC_FREE_STANDARD_GITHUB_RUNNER_REQUIRED')
    info = required_json(['info', '--format', '{{json .}}'])
    driver = info.get('Driver')
    root = info.get('DockerRootDir', '/var/lib/docker')
    if driver not in {'overlay2', 'overlayfs'}:
        raise RuntimeError('SAFE_OVERLAY_DOCKER_STORAGE_REQUIRED')
    free = shutil.disk_usage(root).free
    if free < 20 * 1024**3:
        raise RuntimeError('FREE_DOCKER_DISK_20_GIB_REQUIRED')
    pulled = docker('pull', IMAGE, timeout=600)
    if pulled.returncode:
        raise RuntimeError('IMMUTABLE_BASELINE_PULL_FAILED')
    image = required_json(['image', 'inspect', IMAGE])[0]
    config = image.get('Config', {})
    if (config.get('Entrypoint') != ENTRYPOINT or config.get('Cmd') not in (None, [])
            or image.get('Architecture') != 'amd64' or image.get('Os') != 'linux'
            or IMAGE not in image.get('RepoDigests', [])):
        raise RuntimeError('ORIGINAL_IMAGE_STARTUP_CONTRACT_MISMATCH')
    cases = [
        run_case('missing-origin', environment={},
                 expected_code='STUDIO_HTTPS_ORIGIN_REQUIRED'),
        run_case('missing-owner', environment={'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': TEST_ORIGIN},
                 expected_code='STUDIO_OWNER_CONFIGURATION_REQUIRED'),
        run_case('generic-aliases', environment={
            'PUBLIC_ORIGIN': TEST_ORIGIN, 'OWNER_CODE': TEST_OWNER,
            'IMAGE_DIGEST': DIGEST}, expected_code='STUDIO_HTTPS_ORIGIN_REQUIRED'),
        run_case('optional-policy-absent', environment={
            'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': TEST_ORIGIN,
            'WORLD_ENGINE_STUDIO_OWNER_CODE': TEST_OWNER}, expected_exit=0,
            isolated_configuration=True),
    ]
    result = {
        'schema': 'WORLD_ENGINE_STUDIO_STARTUP_CPU_REPRODUCTION_V1',
        'image': IMAGE, 'platform': 'linux/amd64',
        'entrypoint': config.get('Entrypoint'), 'cmd': config.get('Cmd'),
        'dockerStorageDriver': driver, 'freeDockerBytesBeforePull': free,
        'cases': cases,
        'result': 'PASS' if all(row['status'] == 'PASS' for row in cases) else 'FAIL',
        'protectedSourceModified': False, 'imagesBuiltOrPushed': False,
        'gpuDevicesRequested': False, 'nvidiaHardwareVerified': False,
        'gcube5373LogsObtained': False, 'gcube5373CauseConfirmed': False,
        'rawEnvironmentPublished': False, 'rawLogsPublished': False,
        'limitation': 'CPU fixture failures do not establish the live workload failure cause.',
    }
    write_json(output / 'results.json', result)
    rows = []
    for file in sorted(output.glob('*.json')):
        rows.append(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}\n')
    (output / 'SHA256SUMS').write_text(''.join(rows))
    for row in cases:
        print(json.dumps({key: row[key] for key in ('case', 'status', 'actualContainerExitCode',
              'firstRecordedErrorCode', 'testScope')}, sort_keys=True), flush=True)
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = str(error)
        code = code if CODE.fullmatch(code) else 'CPU_STARTUP_REPRODUCTION_FAILED'
        blocked = {'status': 'BLOCKED', 'errorCode': code,
                   'nvidiaHardwareVerified': False,
                   'gcube5373CauseConfirmed': False}
        output = Path(sys.argv[1] if len(sys.argv) > 1 else 'studio-startup-cpu-results')
        if output.is_dir() and not output.is_symlink():
            target = output / 'results.json'
            if not target.exists():
                write_json(target, blocked)
                (output / 'SHA256SUMS').write_text(
                    f'{hashlib.sha256(target.read_bytes()).hexdigest()}  results.json\n')
        print(json.dumps(blocked), flush=True)
        raise SystemExit(2)
