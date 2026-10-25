#!/usr/bin/env python3
"""One CPU-only Docker suite against the unchanged, pinned production image.

No image build/push, GPU device, external container network, real credential,
render endpoint or automatic test retry is used. Readiness polling observes a
single start; failure aborts the suite. All containers and synthetic credentials
are ephemeral. Output contains only allowlisted test evidence.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import tempfile
import time

DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
SOURCE_SHA = '138f5ff4761e2fa3589e15493ded5401afe1ec4dfa0dc5ad5a725e03e53b9270'
ENGINE = 'world-simulation-shorts-engine'
REL = ENGINE + '/recovery/studio-cold-start-v1'
SOURCE_REL = ENGINE + '/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
IN_REPO = '/opt/world-engine-handoffs/cpu-validation/repo'
IN_NEW = IN_REPO + '/' + REL
IN_PRIVATE = '/var/lib/world-engine-cpu-test/auth'
LABEL = 'world-engine.validation=studio-cold-start-v1'


class Blocked(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Blocked(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, *, timeout=20, accept_failure=False):
    # Do not use check=True: exception representations can include full commands.
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Blocked('CPU_COMMAND_TIMEOUT') from None
    except OSError:
        raise Blocked('CPU_COMMAND_UNAVAILABLE') from None
    if not accept_failure and result.returncode:
        raise Blocked('CPU_DOCKER_COMMAND_FAILED')
    return result


class Suite:
    def __init__(self, args, temporary):
        self.args = args
        self.repo = args.repo.resolve(strict=True)
        self.temporary = temporary
        self.key = secrets.token_hex(6)
        self.containers = []
        self.cases = []
        self.active_case = 'prerequisites'
        self.current = None
        self.bundle = self.repo / REL / 'STARTUP_MANIFEST.json'
        self.source = self.repo / SOURCE_REL
        require(',' not in str(self.repo) and '\n' not in str(self.repo), 'CPU_MOUNT_PATH_INVALID')
        require(args.image.endswith('@' + DIGEST) and not re.search(r'\s', args.image),
                'CPU_PINNED_IMAGE_REQUIRED')
        require(self.bundle.is_file() and self.source.is_file(), 'CPU_INPUT_MANIFEST_REQUIRED')
        self.bundle_sha = sha(self.bundle)
        require(sha(self.source) == SOURCE_SHA, 'CPU_SOURCE_MANIFEST_IDENTITY_CHANGED')
        self.initial_source_sha = sha(self.source)
        self.bootstrap = ['/usr/bin/python3', '-I', '-B', IN_NEW + '/bootstrap.py',
                          '--startup-manifest', IN_NEW + '/STARTUP_MANIFEST.json',
                          '--startup-manifest-sha256', self.bundle_sha,
                          '--source-manifest', IN_REPO + '/' + SOURCE_REL,
                          '--source-manifest-sha256', SOURCE_SHA, '--export-root', '/world-storage']
        # Inspect only local availability. Never implicitly pull or rebuild an image.
        run(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image])
        policy = {'validUntil': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                  'maxWallSeconds': 1800, 'maxRetries': 0, 'maxCostAmount': '2000',
                  'currency': 'KRW', 'gpuHourlyRate': '1300'}
        self.env_file = temporary / 'synthetic-input.env'
        env = {'WORLD_ENGINE_STUDIO_OWNER_CODE': secrets.token_urlsafe(32),
               'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON': json.dumps(policy, separators=(',', ':')),
               'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': 'https://world-engine-test.invalid',
               'WORLD_ENGINE_STUDIO_STATE_ROOT': IN_PRIVATE,
               'WORLD_ENGINE_STUDIO_PORT': '8080', 'WORLD_ENGINE_STARTUP_MODE': 'normal',
               'WORLD_ENGINE_RENDER_MODE': 'gpu-required', 'GPU_BACKEND': 'vulkan',
               'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': DIGEST, 'PYTHONDONTWRITEBYTECODE': '1'}
        fd = os.open(self.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(''.join(key + '=' + value + '\n' for key, value in env.items()))
        # Fixture values are not returned, logged, included in reports or sent to GitHub.
        del env

    def docker(self, *argv, **kwargs):
        return run(['docker', *argv], **kwargs)

    def name(self, suffix):
        return 'we-cpu-' + self.key + '-' + suffix

    def start(self, suffix, *, network='none', extra_mounts=(), blocker=False):
        name = self.name(suffix)
        self.containers.append(name)
        options = ['run', '--detach', '--pull=never', '--name', name,
                   '--label', LABEL, '--label', 'world-engine.cpu-startup-suite=' + self.key,
                   '--restart', 'no', '--read-only', '--network', network,
                   '--no-healthcheck', '--memory', '3g', '--cpus', '2',
                   '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=1',
                   '--tmpfs', '/tmp:rw,nosuid,nodev,mode=1777',
                   '--tmpfs', '/run:rw,nosuid,nodev,mode=0755',
                   '--tmpfs', '/var/lib/world-engine-cpu-test:rw,nosuid,nodev,mode=0755',
                   '--tmpfs', '/world-storage:rw,nosuid,nodev,mode=0700,uid=1000,gid=1000',
                   '--mount', 'type=bind,source=' + str(self.repo) + ',destination=' + IN_REPO + ',readonly']
        for mount in extra_mounts:
            options.extend(['--mount', mount])
        if blocker:
            options += ['--entrypoint', '/usr/bin/python3', self.args.image,
                        '-I', '-B', '-m', 'http.server', '8080', '--bind', '127.0.0.1']
        else:
            options += ['--env-file', str(self.env_file), '--entrypoint', '/usr/bin/tini',
                        self.args.image, '-g', '--', *self.bootstrap]
        self.docker(*options, timeout=40)
        self.current = name
        return name

    def state(self, name):
        result = self.docker('inspect', '--format', '{{json .State}}', name)
        try:
            value = json.loads(result.stdout)
            return {key: value[key] for key in ('Running', 'ExitCode', 'OOMKilled', 'Status')}
        except (ValueError, KeyError):
            raise Blocked('CPU_CONTAINER_STATE_INVALID') from None

    def records(self, name):
        raw = self.docker('logs', name).stdout
        records = []
        for line in raw.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if not isinstance(value, dict):
                continue
            stage, code = value.get('stage'), value.get('errorCode')
            item = {}
            if isinstance(stage, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', stage):
                item['stage'] = stage
            if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
                item['errorCode'] = code
            for key in ('pid', 'exitCode', 'servicePort'):
                if type(value.get(key)) is int:
                    item[key] = value[key]
            for key in ('listenerStarted', 'renderAutomaticallyStarted', 'gpuRenderingVerified'):
                if type(value.get(key)) is bool:
                    item[key] = value[key]
            if value.get('latestController') == 'NvidiaPresentationController':
                item['latestController'] = 'NvidiaPresentationController'
            if value.get('exampleName') == 'AVIATION_EUROPE_NL.json':
                item['exampleName'] = 'AVIATION_EUROPE_NL.json'
            if item:
                records.append(item)
        return records

    def probe(self, name, mode, *, allow_unready=False):
        result = self.docker('exec', '--user', '1000:1000', name, '/usr/bin/python3', '-I', '-B',
                             IN_NEW + '/tests/container_probe.py', mode, timeout=12,
                             accept_failure=True)
        try:
            parsed = json.loads(result.stdout)
        except ValueError:
            if allow_unready:
                return None
            raise Blocked('CPU_PROBE_RESULT_INVALID') from None
        if result.returncode or parsed.get('status') != 'PASS':
            if allow_unready:
                return None
            code = parsed.get('code', '')
            raise Blocked(code if re.fullmatch(r'CPU_[A-Z0-9_]{1,95}', code) else 'CPU_PROBE_BLOCKED')
        return parsed['facts']

    def ready(self, name):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            require(self.state(name)['Running'], 'CPU_CONTAINER_EXITED_BEFORE_READY')
            if self.probe(name, 'health', allow_unready=True) is not None:
                events = self.records(name)
                started = [event for event in events if event.get('stage') == 'WORLD_ENGINE_COLD_START_WEB_STARTED']
                require(len(started) == 1 and started[0].get('listenerStarted') is True
                        and started[0].get('latestController') == 'NvidiaPresentationController'
                        and started[0].get('exampleName') == 'AVIATION_EUROPE_NL.json',
                        'CPU_LATEST_CONTROLLER_START_RECORD_REQUIRED')
                # Check actual Docker mount/enforcement settings, not just the invocation.
                value = json.loads(self.docker('inspect', '--format',
                    '{{json .HostConfig.ReadonlyRootfs}}', name).stdout)
                require(value is True, 'CPU_IMAGE_ROOT_MUST_BE_READ_ONLY')
                mounts = json.loads(self.docker('inspect', '--format', '{{json .Mounts}}', name).stdout)
                require(any(item.get('Destination') == IN_REPO and item.get('RW') is False for item in mounts),
                        'CPU_RUNTIME_MOUNT_MUST_BE_READ_ONLY')
                return self.probe(name, 'inventory')
            time.sleep(0.25)
        raise Blocked('CPU_SINGLE_START_READINESS_TIMEOUT')

    def wait_exit(self, name, *, expected=None, timeout=35):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.state(name)
            if not value['Running']:
                require(value['Status'] == 'exited' and value['OOMKilled'] is False,
                        'CPU_CONTAINER_ABNORMAL_STOP')
                require(value['ExitCode'] == expected if expected is not None else value['ExitCode'] != 0,
                        'CPU_CONTAINER_EXIT_CODE_UNEXPECTED')
                return value['ExitCode']
            time.sleep(0.25)
        raise Blocked('CPU_CHILD_CLEANUP_TIMEOUT')

    def stop(self, name, sig, *, expected=143):
        self.docker('kill', '--signal', sig, name)
        return self.wait_exit(name, expected=expected)

    def pass_case(self, facts):
        self.cases.append({'case': self.active_case, 'status': 'PASS', **facts})

    def execute(self):
        self.active_case = 'startup_auth_scene_duplicate_and_sigterm'
        name = self.start('term')
        initial = self.ready(name)
        snapshot = self.probe(name, 'snapshot')
        ui = self.probe(name, 'ui')
        duplicate = self.docker('exec', name, *self.bootstrap, accept_failure=True)
        require(duplicate.returncode != 0, 'CPU_DUPLICATE_START_MUST_FAIL')
        duplicate_codes = []
        for line in duplicate.stdout.splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    duplicate_codes.append(value.get('errorCode'))
            except ValueError:
                pass
        require(any(code in {'COLD_START_ROOT_TINI_ENTRYPOINT_REQUIRED', 'COLD_START_ALREADY_ATTEMPTED'}
                    for code in duplicate_codes),
                'CPU_DUPLICATE_PARENT_GUARD_REQUIRED')
        after = self.probe(name, 'inventory')
        require(after['workerPid'] == initial['workerPid'], 'CPU_DUPLICATE_CHANGED_PRIMARY_PROCESS')
        require(self.probe(name, 'snapshot') == snapshot, 'CPU_PRIVATE_INPUT_CHANGED')
        self.probe(name, 'health')
        exit_code = self.stop(name, 'TERM')
        require(any(item.get('stage') == 'COLD_START_WEB_STOPPED' for item in self.records(name)),
                'CPU_WORKER_GRACEFUL_STOP_RECORD_REQUIRED')
        self.pass_case({'exitCode': exit_code, 'workerCount': 1, 'oldStudioCount': 0,
                        'duplicateStartRejected': True, 'privateInputsPreserved': True,
                        'sourceMountReadOnly': True, 'imageRootReadOnly': True, **ui})

        self.active_case = 'sigint_forwarding_and_cleanup'
        name = self.start('int')
        self.ready(name)
        exit_code = self.stop(name, 'INT')
        require(any(item.get('stage') == 'COLD_START_WEB_STOPPED' for item in self.records(name)),
                'CPU_SIGINT_GRACEFUL_STOP_RECORD_REQUIRED')
        self.pass_case({'exitCode': exit_code, 'gracefulWorkerStop': True})

        self.active_case = 'worker_normal_exit_stops_supervisor'
        name = self.start('child-normal')
        inventory = self.ready(name)
        self.docker('exec', '--user', '1000:1000', name, '/usr/bin/python3', '-I', '-B', '-c',
                    'import os,signal; os.kill(' + str(inventory['workerPid']) + ',signal.SIGTERM)')
        exit_code = self.wait_exit(name, expected=1)
        events = self.records(name)
        require(any(item.get('stage') == 'COLD_START_WEB_STOPPED' for item in events)
                and any(item.get('stage') == 'SETUP_SERVICE_EXITED' and item.get('exitCode') == 0
                        for item in events), 'CPU_NORMAL_CHILD_EXIT_EVIDENCE_REQUIRED')
        self.pass_case({'workerExitCode': 0, 'supervisorExitCode': exit_code, 'containerStopped': True})

        self.active_case = 'worker_error_exit_stops_supervisor'
        name = self.start('child-error')
        inventory = self.ready(name)
        self.docker('exec', '--user', '1000:1000', name, '/usr/bin/python3', '-I', '-B', '-c',
                    'import os,signal; os.kill(' + str(inventory['workerPid']) + ',signal.SIGKILL)')
        exit_code = self.wait_exit(name)
        events = self.records(name)
        require(any(item.get('stage') == 'SETUP_SERVICE_EXITED' and item.get('exitCode') == -9
                    for item in events), 'CPU_FAILED_CHILD_EXIT_EVIDENCE_REQUIRED')
        require(sum(item.get('stage') == 'WORLD_ENGINE_COLD_START_WEB_STARTED' for item in events) == 1,
                'CPU_CHILD_MUST_NOT_RESTART')
        self.pass_case({'workerSignal': 'SIGKILL', 'supervisorExitCode': exit_code,
                        'containerStopped': True, 'automaticRestarts': 0})

        self.active_case = 'port_collision_fails_closed'
        blocker = self.start('port-owner', blocker=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            require(self.state(blocker)['Running'], 'CPU_PORT_FIXTURE_EXITED')
            connected = self.docker('exec', blocker, '/usr/bin/python3', '-I', '-B', '-c',
                'import socket; s=socket.create_connection(("127.0.0.1",8080),1); s.close()',
                accept_failure=True)
            if connected.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise Blocked('CPU_PORT_FIXTURE_UNAVAILABLE')
        name = self.start('port-conflict', network='container:' + blocker)
        self.wait_exit(name, expected=1)
        events = self.records(name)
        require(any(item.get('errorCode') == 'COLD_START_PORT_ALREADY_IN_USE' for item in events),
                'CPU_PORT_COLLISION_GUARD_REQUIRED')
        require(not any(item.get('stage') == 'WORLD_ENGINE_COLD_START_WEB_STARTED' for item in events),
                'CPU_PORT_COLLISION_MUST_NOT_START_STUDIO')
        require(self.state(blocker)['Running'], 'CPU_PORT_OWNER_MUST_BE_PRESERVED')
        self.docker('rm', '--force', blocker)
        self.pass_case({'port': 8080, 'latestStudioStarted': False, 'existingListenerPreserved': True})

        self.active_case = 'existing_private_root_preserved'
        fixture = self.temporary / 'existing-private'
        fixture.mkdir(mode=0o755)
        sentinel = fixture / 'owner-code'
        sentinel.write_bytes(secrets.token_bytes(32))
        sentinel.chmod(0o600)
        before = sha(sentinel)
        name = self.start('existing-private', extra_mounts=(
            'type=bind,source=' + str(fixture) + ',destination=' + IN_PRIVATE + ',readonly',))
        self.wait_exit(name, expected=1)
        events = self.records(name)
        require(any(item.get('errorCode') == 'COLD_START_FRESH_PRIVATE_ROOT_REQUIRED' for item in events),
                'CPU_EXISTING_PRIVATE_ROOT_GUARD_REQUIRED')
        require(sha(sentinel) == before and list(fixture.iterdir()) == [sentinel],
                'CPU_EXISTING_PRIVATE_ROOT_CHANGED')
        require(not any(item.get('stage') == 'WORLD_ENGINE_COLD_START_WEB_STARTED' for item in events),
                'CPU_EXISTING_PRIVATE_ROOT_MUST_NOT_START')
        self.pass_case({'existingPrivateRootPreserved': True, 'latestStudioStarted': False})
        require(sha(self.source) == self.initial_source_sha and sha(self.bundle) == self.bundle_sha,
                'CPU_SOURCE_OR_STARTUP_MANIFEST_CHANGED')

    def cleanup(self):
        failed = False
        for name in reversed(self.containers):
            try:
                self.docker('rm', '--force', name, timeout=15, accept_failure=True)
                remaining = self.docker('ps', '--all', '--quiet', '--filter', 'name=^/' + name + '$').stdout.strip()
                failed = failed or bool(remaining)
            except Blocked:
                failed = True
        return not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = {'schema': 'WORLD_ENGINE_STUDIO_COLD_START_CPU_TEST_V1', 'status': 'BLOCKED',
              'imageDigest': DIGEST, 'gpuUsed': False, 'renderRequested': False,
              'testRetries': 0, 'realOriginOrStorageValidated': False, 'cases': []}
    suite = None

    def interrupted(signum, frame):
        raise Blocked('CPU_SUITE_INTERRUPTED')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix='world-engine-cpu-startup-') as folder:
            try:
                suite = Suite(args, Path(folder))
                suite.execute()
                report['status'] = 'PASS'
            except Exception as error:
                code = str(error)
                report['errorCode'] = code if re.fullmatch(r'CPU_[A-Z0-9_]{1,95}', code) else 'CPU_SUITE_BLOCKED'
                if suite is not None:
                    report['failedCase'] = suite.active_case
                    if suite.current is not None:
                        try:
                            report['lastContainerEvents'] = suite.records(suite.current)
                        except Blocked:
                            pass
            finally:
                if suite is not None:
                    report['cases'] = suite.cases
                    report['startupManifestSHA256'] = suite.bundle_sha
                    report['testContainersRemoved'] = suite.cleanup()
                    if not report['testContainersRemoved']:
                        report['status'] = 'BLOCKED'
                        report['cleanupError'] = 'CPU_CONTAINER_CLEANUP_NOT_CONFIRMED'
    except Exception:
        report['status'] = 'BLOCKED'
        report['errorCode'] = 'CPU_SUITE_FINALIZATION_BLOCKED'
    if args.report:
        try:
            # Refuse to overwrite any prior result or source file.
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=True, indent=2)
                stream.write('\n')
        except OSError:
            report['status'] = 'BLOCKED'
            report['errorCode'] = 'CPU_REPORT_WRITE_FAILED'
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
