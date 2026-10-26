#!/usr/bin/env python3
"""One CPU-only delta suite for the packaged image's default startup.

Normal targets use the image's own ENTRYPOINT/CMD and packaged files.
No source mount, alternate target command, image pull, GPU device, render,
deployment or automatic retry is allowed. The port-owner fixture alone has
an explicit Python entrypoint to occupy a disposable network namespace.
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

REL = 'world-simulation-shorts-engine/recovery/studio-cold-start-v2'
IN_REPO = '/opt/world-engine-handoffs/studio-v2/repo'
IN_NEW = IN_REPO + '/' + REL
PRIVATE_PARENT = '/var/lib/world-engine-studio-v2'
IN_PRIVATE = PRIVATE_PARENT + '/auth'
FIXTURE_DIGEST = 'sha256:' + 'a' * 64
LABEL = 'world-engine.validation=studio-cold-start-v2'


class Blocked(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Blocked(code)


def run(argv, *, timeout=30, accept_failure=False, input_text=None):
    try:
        result = subprocess.run(argv, input=input_text, stdin=None if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Blocked('CPU_COMMAND_TIMEOUT') from None
    except OSError:
        raise Blocked('CPU_DOCKER_COMMAND_UNAVAILABLE') from None
    if result.returncode and not accept_failure:
        # Never include full argv, environment, HTTP data, Docker errors or logs.
        raise Blocked('CPU_DOCKER_COMMAND_FAILED')
    return result


class Suite:
    def __init__(self, args, temporary):
        self.args, self.temporary = args, temporary
        self.repo = args.repo.resolve(strict=True)
        self.key = secrets.token_hex(6)
        self.containers, self.cases = [], []
        self.current = None
        self.active_case = 'packaged_image_contract'
        require(not re.search(r'\s', args.image) and args.image and not args.image.startswith('-'),
                'CPU_IMAGE_REFERENCE_REQUIRED')
        self.probe_source = (self.repo / REL / 'tests/container_probe.py').read_text()
        self.bundle_sha = hashlib.sha256((self.repo / REL / 'STARTUP_MANIFEST.json').read_bytes()).hexdigest()
        info = json.loads(self.docker('image', 'inspect', args.image).stdout)[0]
        config = info.get('Config', {})
        entrypoint = config.get('Entrypoint', [])
        require(info.get('Os') == 'linux' and info.get('Architecture') == 'amd64'
                and entrypoint[:6] == ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B']
                and IN_NEW + '/bootstrap.py' in entrypoint and config.get('Cmd') in ([], None)
                and config.get('User') in ('', '0', '0:0'), 'CPU_PACKAGED_DEFAULT_ENTRYPOINT_REQUIRED')
        require(not any(row.split('=', 1)[0] in {'WORLD_ENGINE_STUDIO_OWNER_CODE',
                    'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON', 'GH_TOKEN', 'GITHUB_TOKEN'}
                    for row in config.get('Env', [])), 'CPU_IMAGE_MUST_NOT_EMBED_SECRETS')
        self.image_id = info['Id']
        self.pass_case({'defaultEntrypointVerified': True, 'imageCmdEmpty': True,
                        'imageRootUser': True, 'imageContainsOperationalSecrets': False,
                        'imageConfigId': self.image_id})
        policy = {'validUntil': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                  'maxWallSeconds': 1800, 'maxRetries': 0, 'maxCostAmount': '2000',
                  'currency': 'KRW', 'gpuHourlyRate': '360'}
        self.environment = {
            'WORLD_ENGINE_STUDIO_OWNER_CODE': secrets.token_urlsafe(32),
            'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON': json.dumps(policy, separators=(',', ':')),
            'WORLD_ENGINE_STUDIO_STATE_ROOT': IN_PRIVATE,
            'WORLD_ENGINE_STUDIO_PORT': '8080', 'WORLD_ENGINE_STARTUP_MODE': 'normal',
            'WORLD_ENGINE_RENDER_MODE': 'gpu-required', 'GPU_BACKEND': 'vulkan',
            'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': FIXTURE_DIGEST,
            'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST': FIXTURE_DIGEST,
            'PYTHONDONTWRITEBYTECODE': '1'}
        # Omit PUBLIC_ORIGIN deliberately. The test must exercise SETUP mode.
        self.env_file = self.write_environment('valid', self.environment)
        missing_owner = dict(self.environment)
        missing_owner.pop('WORLD_ENGINE_STUDIO_OWNER_CODE')
        self.missing_owner_file = self.write_environment('missing-owner', missing_owner)
        short_policy = dict(policy)
        short_policy['maxWallSeconds'] = 8
        short_environment = dict(self.environment)
        short_environment['WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'] = json.dumps(short_policy, separators=(',', ':'))
        self.short_policy_file = self.write_environment('short-policy', short_environment)
        del self.environment, missing_owner, policy, short_policy, short_environment

    def docker(self, *argv, **kwargs):
        return run(['docker', *argv], **kwargs)

    def write_environment(self, suffix, environment):
        path = self.temporary / (suffix + '.env')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(''.join(key + '=' + value + '\n' for key, value in environment.items()))
        return path

    def start(self, suffix, *, network='none', env_file=None, blocker=False):
        name = 'we-cpu-v2-' + self.key + '-' + suffix
        self.containers.append(name)
        options = ['run', '--detach', '--pull=never', '--name', name,
                   '--label', LABEL, '--label', 'world-engine.cpu-suite=' + self.key,
                   '--restart', 'no', '--read-only', '--network', network,
                   '--no-healthcheck', '--memory', '4g', '--cpus', '2', '--shm-size', '2g',
                   '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=1',
                   '--tmpfs', '/tmp:rw,nosuid,nodev,mode=1777',
                   '--tmpfs', '/run:rw,nosuid,nodev,mode=0755',
                   '--tmpfs', PRIVATE_PARENT + ':rw,nosuid,nodev,mode=0755',
                   '--tmpfs', '/world-storage:rw,nosuid,nodev,mode=0700,uid=1000,gid=1000']
        if blocker:
            # Isolated auxiliary fixture, not a target startup under validation.
            options += ['--entrypoint', '/usr/bin/python3', self.args.image,
                        '-I', '-B', '-m', 'http.server', '8080', '--bind', '127.0.0.1']
        else:
            options += ['--env-file', str(env_file or self.env_file), self.args.image]
        self.docker(*options, timeout=40)
        self.current = name
        if not blocker:
            config = json.loads(self.docker('inspect', '--format', '{{json .Config}}', name).stdout)
            host = json.loads(self.docker('inspect', '--format', '{{json .HostConfig}}', name).stdout)
            mounts = json.loads(self.docker('inspect', '--format', '{{json .Mounts}}', name).stdout)
            require(config.get('Cmd') in ([], None) and IN_NEW + '/bootstrap.py' in config.get('Entrypoint', []),
                    'CPU_TARGET_MUST_USE_IMAGE_DEFAULT_COMMAND')
            require(host.get('ReadonlyRootfs') is True and host.get('RestartPolicy', {}).get('Name') == 'no',
                    'CPU_TARGET_READONLY_NO_RESTART_REQUIRED')
            require(not host.get('DeviceRequests') and not host.get('Devices')
                    and not host.get('Privileged'), 'CPU_GPU_OR_PRIVILEGED_EXECUTION_FORBIDDEN')
            require(not any(item.get('Type') == 'bind' or item.get('Destination', '').startswith(IN_REPO)
                            for item in mounts), 'CPU_SOURCE_MOUNT_FORBIDDEN')
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
        result = []
        for line in raw.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if not isinstance(value, dict):
                continue
            item = {}
            for key in ('stage', 'errorCode'):
                text = value.get(key)
                if isinstance(text, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,119}', text):
                    item[key] = text
            for key in ('pid', 'exitCode', 'servicePort'):
                if type(value.get(key)) is int:
                    item[key] = value[key]
            for key in ('listenerStarted', 'renderAutomaticallyStarted', 'gpuRenderingVerified',
                        'providerStopControlled', 'applicationDeadlineArmed'):
                if type(value.get(key)) is bool:
                    item[key] = value[key]
            if value.get('mode') in {'SETUP', 'CONFIGURED'}:
                item['mode'] = value['mode']
            if value.get('latestController') == 'NvidiaPresentationController':
                item['latestController'] = 'NvidiaPresentationController'
            if item:
                result.append(item)
        return result

    def probe(self, name, mode, *, allow_unready=False):
        result = self.docker('exec', '--interactive', '--user', '1000:1000', name,
            '/usr/bin/python3', '-I', '-B', '-', mode, input_text=self.probe_source,
            timeout=270 if mode == 'setup-plan' else 15, accept_failure=True)
        try:
            value = json.loads(result.stdout)
        except ValueError:
            if allow_unready:
                return None
            raise Blocked('CPU_PROBE_RESULT_INVALID') from None
        if result.returncode or value.get('status') != 'PASS':
            if allow_unready:
                return None
            code = value.get('code', '')
            raise Blocked(code if re.fullmatch(r'CPU_[A-Z0-9_]{1,95}', code) else 'CPU_PROBE_BLOCKED')
        return value['facts']

    def ready(self, name):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            require(self.state(name)['Running'], 'CPU_CONTAINER_EXITED_BEFORE_SETUP')
            if self.probe(name, 'health', allow_unready=True) is not None:
                events = self.records(name)
                started = [event for event in events if event.get('listenerStarted') is True]
                require(len(started) == 1 and started[0].get('mode') == 'SETUP',
                        'CPU_EXACTLY_ONE_SETUP_LISTENER_REQUIRED')
                require(all(event.get('renderAutomaticallyStarted') is not True for event in events),
                        'CPU_AUTOMATIC_RENDER_FORBIDDEN')
                return self.probe(name, 'inventory')
            time.sleep(0.25)
        raise Blocked('CPU_SINGLE_START_READINESS_TIMEOUT')

    def wait_exit(self, name, expected=None):
        deadline = time.monotonic() + 35
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

    def stop(self, name, sig):
        self.docker('kill', '--signal', sig, name)
        exit_code = self.wait_exit(name, expected=143)
        require(any(event.get('stage') == 'COLD_START_WEB_STOPPED' for event in self.records(name)),
                'CPU_GRACEFUL_WORKER_STOP_REQUIRED')
        return exit_code

    def pass_case(self, facts):
        self.cases.append({'case': self.active_case, 'status': 'PASS', **facts})

    def execute(self):
        self.active_case = 'default_entrypoint_setup_owner_plan_and_term'
        name = self.start('setup-term')
        initial = self.ready(name)
        setup = self.probe(name, 'setup-plan')
        after = self.probe(name, 'inventory')
        require(after['workerPid'] == initial['workerPid'], 'CPU_SETUP_MUST_NOT_RESTART_STUDIO')
        events = self.records(name)
        require(sum(event.get('stage') == 'COLD_START_LATEST_CONTROLLER_CONFIRMED'
                    and event.get('latestController') == 'NvidiaPresentationController'
                    for event in events) == 1, 'CPU_EXACT_LATEST_CONTROLLER_FACTORY_REQUIRED')
        exit_code = self.stop(name, 'TERM')
        self.pass_case({'defaultImageStartup': True, 'sourceBindMounts': 0,
                        'sameWorkerAfterSetup': True, 'exitCode': exit_code, **setup})

        self.active_case = 'setup_wait_sigint_and_cleanup'
        name = self.start('setup-int')
        self.ready(name)
        exit_code = self.stop(name, 'INT')
        self.pass_case({'modeAtSignal': 'SETUP', 'signal': 'SIGINT', 'exitCode': exit_code,
                        'gracefulWorkerStop': True, 'renderStartRequested': False})

        self.active_case = 'packaged_worker_error_exit_no_restart'
        name = self.start('child-error')
        info = self.ready(name)
        self.docker('exec', '--user', '1000:1000', name, '/usr/bin/python3', '-I', '-B', '-c',
                    'import os,signal; os.kill(' + str(info['workerPid']) + ',signal.SIGKILL)')
        exit_code = self.wait_exit(name)
        events = self.records(name)
        require(any(event.get('stage') == 'SETUP_SERVICE_EXITED' and event.get('exitCode') == -9
                    for event in events), 'CPU_FAILED_CHILD_EXIT_EVIDENCE_REQUIRED')
        require(sum(event.get('listenerStarted') is True for event in events) == 1,
                'CPU_CHILD_MUST_NOT_RESTART')
        self.pass_case({'workerSignal': 'SIGKILL', 'supervisorExitCode': exit_code,
                        'containerStopped': True, 'automaticRestarts': 0})

        self.active_case = 'packaged_default_port_collision'
        blocker = self.start('port-owner', blocker=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            require(self.state(blocker)['Running'], 'CPU_PORT_FIXTURE_EXITED')
            result = self.docker('exec', blocker, '/usr/bin/python3', '-I', '-B', '-c',
                'import socket; s=socket.create_connection(("127.0.0.1",8080),1); s.close()',
                accept_failure=True)
            if result.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise Blocked('CPU_PORT_FIXTURE_UNAVAILABLE')
        name = self.start('port-conflict', network='container:' + blocker)
        self.wait_exit(name, expected=1)
        events = self.records(name)
        require(any(event.get('errorCode') == 'COLD_START_PORT_ALREADY_IN_USE' for event in events),
                'CPU_PORT_COLLISION_GUARD_REQUIRED')
        require(not any(event.get('listenerStarted') is True for event in events),
                'CPU_PORT_COLLISION_MUST_NOT_START_STUDIO')
        require(self.state(blocker)['Running'], 'CPU_PORT_OWNER_MUST_BE_PRESERVED')
        self.docker('rm', '--force', blocker)
        self.pass_case({'port': 8080, 'latestStudioStarted': False, 'existingListenerPreserved': True})

        self.active_case = 'missing_owner_blocks_before_listener'
        name = self.start('missing-owner', env_file=self.missing_owner_file)
        self.wait_exit(name, expected=1)
        events = self.records(name)
        require(any(event.get('errorCode') == 'STUDIO_OWNER_CONFIGURATION_REQUIRED' for event in events),
                'CPU_MISSING_OWNER_GUARD_REQUIRED')
        require(not any(event.get('listenerStarted') is True for event in events),
                'CPU_MISSING_OWNER_MUST_NOT_START_LISTENER')
        self.pass_case({'ownerRequired': True, 'listenerStarted': False, 'authenticationBypass': False})

        self.active_case = 'setup_wait_application_deadline'
        name = self.start('deadline', env_file=self.short_policy_file)
        self.ready(name)
        observed = time.monotonic()
        exit_code = self.wait_exit(name, expected=124)
        elapsed = time.monotonic() - observed
        events = self.records(name)
        require(elapsed <= 15 and any(event.get('stage') == 'APPLICATION_DEADLINE_REACHED'
                    and event.get('providerStopControlled') is False for event in events),
                'CPU_APPLICATION_DEADLINE_NOT_ENFORCED')
        require(sum(event.get('listenerStarted') is True for event in events) == 1,
                'CPU_DEADLINE_MUST_NOT_RESTART')
        self.pass_case({'applicationPolicySeconds': 8, 'exitCode': exit_code,
                        'automaticRestarts': 0, 'providerStopControlled': False,
                        'providerBillingStopVerified': False})

    def cleanup(self):
        failed = False
        for name in reversed(self.containers):
            try:
                self.docker('rm', '--force', name, timeout=15, accept_failure=True)
                present = self.docker('ps', '--all', '--quiet', '--filter', 'name=^/' + name + '$').stdout.strip()
                failed = failed or bool(present)
            except Blocked:
                failed = True
        return not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--result', '--report', dest='report', type=Path)
    args = parser.parse_args()
    report = {'schema': 'WORLD_ENGINE_STUDIO_COLD_START_CPU_DELTA_V2', 'status': 'BLOCKED',
              'gpuUsed': False, 'renderRequested': False, 'gpuExecuted': False,
              'renderExecuted': False, 'testRetries': 0,
              'realOriginOrStorageValidated': False, 'registryDigestVerified': False,
              'syntheticDeploymentDigestFixture': True, 'originFixtureOnly': True,
              'defaultEntrypointVerified': False, 'cases': []}
    suite = None

    def interrupted(_signum, _frame):
        raise Blocked('CPU_SUITE_INTERRUPTED')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix='world-engine-cpu-v2-') as folder:
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
                    report['imageConfigDigest'] = suite.image_id
                    report['defaultEntrypointVerified'] = bool(suite.cases and
                        suite.cases[0].get('defaultEntrypointVerified') is True)
                    report['testContainersRemoved'] = suite.cleanup()
                    if not report['testContainersRemoved']:
                        report['status'] = 'BLOCKED'
                        report['cleanupError'] = 'CPU_CONTAINER_CLEANUP_NOT_CONFIRMED'
    except Exception:
        report['status'] = 'BLOCKED'
        report['errorCode'] = 'CPU_SUITE_FINALIZATION_BLOCKED'
    if args.report:
        try:
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
