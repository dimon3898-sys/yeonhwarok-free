#!/usr/bin/env python3
"""One-attempt CPU container delta suite; no image pull, GPU, auth or render."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

GIB = 1024 ** 3
LABEL_KEY = 'world-engine.preflight-cpu-suite'
PROBE_TARGET = '/opt/world-engine-preflight-probe.py'


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def command(arguments, *, timeout=30, allow_failure=False):
    try:
        result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('CPU_COMMAND_TIMEOUT') from None
    except OSError:
        raise RuntimeError('CPU_DOCKER_UNAVAILABLE') from None
    if not allow_failure and result.returncode:
        raise RuntimeError('CPU_DOCKER_COMMAND_FAILED')
    require(len(result.stdout) < 1024 * 1024 and len(result.stderr) < 1024 * 1024,
            'CPU_COMMAND_OUTPUT_LIMIT_EXCEEDED')
    return result


def safe_code(error):
    text = str(error)
    return text if re.fullmatch(r'[A-Z][A-Z0-9_]{1,119}', text) else 'CPU_SUITE_OPERATION_FAILED'


class Suite:
    def __init__(self, args):
        self.args = args
        self.key = secrets.token_hex(8)
        self.names = []
        self.cases = []
        self.probe = Path(__file__).resolve().with_name('container_probe.py')
        require(self.probe.is_file() and ',' not in str(self.probe)
                and '\n' not in str(self.probe), 'CPU_PROBE_FILE_REQUIRED')
        require(args.image and not args.image.startswith('-') and not re.search(r'\s', args.image),
                'CPU_IMAGE_REFERENCE_INVALID')
        self.image_id = command(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image]).stdout.strip()
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', self.image_id), 'CPU_IMAGE_ID_INVALID')

    def case(self, name, probe_case, *, shm=2 * GIB):
        container = 'we-preflight-' + self.key + '-' + name
        self.names.append(container)
        arguments = ['docker', 'run', '--pull=never', '--name', container,
            '--label', LABEL_KEY + '=' + self.key,
            '--label', 'world-engine.validation=gpu-preflight-fix-v1',
            '--restart', 'no', '--network', 'none',
            '--no-healthcheck', '--runtime', 'runc', '--user', '1000:1000', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--pids-limit', '128',
            '--memory', '512m', '--cpus', '1', '--shm-size', str(shm),
            '--mount', 'type=bind,src=' + str(self.probe) + ',dst=' + PROBE_TARGET + ',readonly',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', '/usr/bin/python3',
            self.args.image, '-I', '-B', PROBE_TARGET, '--case', probe_case]
        if probe_case == 'shm':
            arguments += ['--requested-shm-bytes', str(shm)]
        outcome = command(arguments, timeout=60, allow_failure=True)
        # Do not expose arbitrary Docker stderr or any process environment.
        row = {'name': name, 'attempt': 1, 'containerName': container,
               'requestedSharedMemoryBytes': shm, 'exitCode': outcome.returncode}
        self.cases.append(row)
        try:
            result = json.loads(outcome.stdout)
        except (json.JSONDecodeError, TypeError):
            raise RuntimeError('CPU_PROBE_JSON_REQUIRED') from None
        require(isinstance(result, dict) and result.get('schema') == 'WORLD_ENGINE_GPU_PREFLIGHT_CPU_PROBE_V1',
                'CPU_PROBE_SCHEMA_INVALID')
        row['probe'] = result
        require(outcome.returncode == 0 and result.get('status') == 'PASS',
                result.get('errorCode', 'CPU_PROBE_FAILED'))
        observed = json.loads(command(['docker', 'inspect', container]).stdout)
        require(isinstance(observed, list) and len(observed) == 1, 'CPU_CONTAINER_INSPECT_INVALID')
        observed = observed[0]
        host, config = observed['HostConfig'], observed['Config']
        require(config.get('Labels', {}).get(LABEL_KEY) == self.key, 'CPU_CONTAINER_OWNERSHIP_REQUIRED')
        require(observed.get('Image') == self.image_id, 'CPU_CONTAINER_IMAGE_ID_CHANGED')
        require(host.get('NetworkMode') == 'none' and host.get('Runtime') == 'runc'
                and host.get('Privileged') is False
                and not host.get('DeviceRequests') and not host.get('Devices')
                and host.get('RestartPolicy', {}).get('Name') == 'no'
                and config.get('User') == '1000:1000'
                and config.get('Entrypoint') == ['/usr/bin/python3']
                and host.get('ShmSize') == shm,
                'CPU_CONTAINER_ISOLATION_CONTRACT_FAILED')
        require(observed.get('State', {}).get('Running') is False
                and observed['State'].get('ExitCode') == 0, 'CPU_CONTAINER_NOT_FINISHED')
        row.update({'status': 'PASS', 'containerId': observed['Id'], 'imageConfigId': observed['Image'],
                    'network': 'none', 'gpuDeviceRequests': 0, 'explicitDeviceMounts': 0,
                    'user': '1000:1000', 'restartPolicy': 'no', 'exited': True})

    def run(self):
        if self.args.mode == 'baseline':
            # Missing-root reproduction already passed in run40296356971.
            # Validate only the newly evidenced OCI root; no passed-case rerun.
            self.case('existing-root', 'existing-root')
        else:
            self.case('inherited-root', 'inherited-root')
            self.case('decimal-2gb', 'shm', shm=2000000000)
            self.case('binary-2gib', 'shm', shm=2 * GIB)
            self.case('decimal-3gb', 'shm', shm=3000000000)

    def cleanup(self):
        removed = []
        for name in reversed(self.names):
            inspection = command(['docker', 'inspect', '--format',
                '{{ index .Config.Labels "' + LABEL_KEY + '" }}', name], allow_failure=True)
            if inspection.returncode:
                # No removal is attempted for absent or uninspectable targets.
                raise RuntimeError('CPU_OWNED_CONTAINER_CLEANUP_UNVERIFIED')
            require(inspection.stdout.strip() == self.key, 'CPU_CLEANUP_OWNERSHIP_MISMATCH')
            command(['docker', 'rm', '--force', name], timeout=30)
            removed.append(name)
        return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=('baseline', 'candidate'))
    args = parser.parse_args()
    result = {'schema': 'WORLD_ENGINE_GPU_PREFLIGHT_CPU_SUITE_V1', 'mode': args.mode,
              'image': args.image, 'startedAt': datetime.now(timezone.utc).isoformat(),
              'automaticRetries': 0, 'gpuExecuted': False, 'renderExecuted': False,
              'browserLaunched': False, 'authenticationInitialized': False,
              'fullPreflightRepeated': False, 'scope': ['RENDER_DEPENDENCIES', 'DISK_AND_SHARED_MEMORY']}
    suite = None
    try:
        require(not args.result.exists(), 'CPU_RESULT_ALREADY_EXISTS')
        suite = Suite(args)
        suite.run()
        result['status'] = 'PASS'
    except Exception as error:
        result.update({'status': 'BLOCKED', 'errorCode': safe_code(error)})
    finally:
        if suite is not None:
            result['cases'] = suite.cases
            result['imageConfigId'] = suite.image_id
            result['imageConfigDigest'] = suite.image_id
            result['probeSHA256'] = hashlib.sha256(suite.probe.read_bytes()).hexdigest()
            try:
                result['removedOwnedContainers'] = suite.cleanup()
            except Exception as error:
                result.update({'status': 'BLOCKED', 'cleanupErrorCode': safe_code(error)})
        result['finishedAt'] = datetime.now(timezone.utc).isoformat()
        args.result.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.result.open('x') as stream:
                json.dump(result, stream, sort_keys=True, indent=2)
                stream.write('\n')
        except FileExistsError:
            print(json.dumps({'status': 'BLOCKED', 'errorCode': 'CPU_RESULT_ALREADY_EXISTS'}))
            return 1
    print('WORLD_ENGINE_PREFLIGHT_CPU_RESULT=' + json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
