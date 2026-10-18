#!/usr/bin/env python3
"""Focused free CPU Docker before/after probe; never starts a render job.

Run on an overlay2 GitHub runner, not the constrained local VFS daemon. The
approved immutable base is reused with a read-only extension overlay before
building a candidate image. Only containers created by this probe are removed.
"""
from __future__ import annotations

import argparse
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time

BASE_DIGEST = 'sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94'
EXTENSION_ROOT = '/opt/world-engine-studio-https-bootstrap'
ORIGINAL_ROOT = '/opt/world-engine-production-studio'
TEST_ORIGIN = 'https://studio-ci.invalid'
TEST_DIGEST = 'sha256:' + 'a' * 64
MAX_LOG = 32768


def run(argv, *, timeout=90, check=True):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        # Deliberately exclude stdout/stderr/arguments; a safe context report is
        # recorded separately without leaking env-file values or credentials.
        raise RuntimeError('CPU_DOCKER_COMMAND_FAILED')
    return result


def safe_text(value, private_values=()):
    result = str(value)
    for secret in private_values:
        if secret:
            result = result.replace(secret, '[REDACTED_TEST_CREDENTIAL]')
    result = re.sub(r'(?i)((?:token|password|owner_code|authorization|secret)["\s:=]+)[^\s,}\"]+',
                    r'\1[REDACTED]', result)
    return result[-MAX_LOG:]


def error_code(document):
    error = document.get('error', {}) if isinstance(document, dict) else {}
    return error.get('code') if isinstance(error, dict) else None


class Probe:
    def __init__(self, image, extension, private_root):
        self.image = image
        self.extension = extension
        self.private_root = private_root
        self.owner = secrets.token_urlsafe(32)
        self.private_values = [self.owner]
        self.containers = []
        self.cases = []

    def request(self, port, path, *, method='GET', body=None, cookie=None,
                origin=TEST_ORIGIN, host='studio-ci.invalid', csrf=None, setup=False):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        headers = {'Host': host, 'Origin': origin, 'Sec-Fetch-Site': 'same-origin'}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-Studio-Setup-CSRF' if setup else 'X-Studio-CSRF'] = csrf
        raw = None
        if body is not None:
            raw = json.dumps(body, separators=(',', ':')).encode()
            headers['Content-Type'] = 'application/json'
        try:
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            payload = response.read(2 * 1024 * 1024)
            try:
                document = json.loads(payload)
            except (ValueError, UnicodeError):
                document = {'htmlBytes': len(payload)}
            cookies = []
            for key, value in response.getheaders():
                if key.lower() == 'set-cookie':
                    parsed = SimpleCookie(value)
                    for name, morsel in parsed.items():
                        cookies.append(f'{name}={morsel.value}')
                        if morsel.value:
                            self.private_values.append(morsel.value)
            for key in ('csrf', 'challenge'):
                if isinstance(document, dict) and isinstance(document.get(key), str):
                    self.private_values.append(document[key])
            return response.status, document, '; '.join(cookies)
        finally:
            connection.close()

    def launch(self, case, *, origin=None, owner=True, digest=TEST_DIGEST,
               extension=True, command=None):
        name = 'we-https-cpu-' + secrets.token_hex(8)
        env = {'WORLD_ENGINE_RENDER_MODE': 'gpu-required',
               'WORLD_ENGINE_STUDIO_PORT': '8080',
               'WORLD_ENGINE_STARTUP_MODE': 'normal'}
        if owner:
            env['WORLD_ENGINE_STUDIO_OWNER_CODE'] = self.owner
        if origin is not None:
            env['WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'] = origin
        if digest is not None:
            env['WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'] = digest
        envfile = self.private_root / (name + '.env')
        descriptor = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as target:
            for key, value in sorted(env.items()):
                target.write(key + '=' + value + '\n')
        argv = ['docker', 'run', '--detach', '--name', name, '--network', 'bridge',
                '--memory', '8g', '--cpus', '2', '--shm-size', '2g',
                '--publish', '127.0.0.1::8080', '--env-file', str(envfile)]
        if extension:
            argv += ['--mount', f'type=bind,source={self.extension},target={EXTENSION_ROOT},readonly']
        if command:
            argv += ['--entrypoint', '/usr/bin/python3', self.image, '-B', '-c', command]
        elif extension:
            argv += ['--entrypoint', '/usr/bin/tini', self.image, '-g', '--',
                     '/usr/bin/python3', '-B', EXTENSION_ROOT + '/https_bootstrap.py']
        else:
            argv += [self.image]
        run(argv, timeout=40)
        self.containers.append(name)
        row = {'case': case, 'scope': 'ACTUAL_CPU_CONTAINER', 'extensionOverlay': extension,
               'status': 'RUNNING', 'gpuRenderingVerified': False,
               'renderJobStarted': False}
        self.cases.append(row)
        return name, row

    def state(self, name):
        return json.loads(run(['docker', 'inspect', '--format', '{{json .State}}', name]).stdout)

    def logs(self, name, row):
        result = run(['docker', 'logs', name], check=False)
        row['stdout'] = safe_text(result.stdout, self.private_values)
        row['stderr'] = safe_text(result.stderr, self.private_values)
        state = self.state(name)
        row['running'] = state.get('Running') is True
        row['exitCode'] = state.get('ExitCode') if not row['running'] else None
        row['oomKilled'] = state.get('OOMKilled') is True

    def wait_exit(self, name, row, expected_code, expected_error=None):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            state = self.state(name)
            if not state.get('Running'):
                break
            time.sleep(0.25)
        self.logs(name, row)
        if row['running'] or row['exitCode'] != expected_code:
            raise AssertionError('CPU_EXPECTED_CONTAINER_EXIT_NOT_OBSERVED')
        if expected_error and expected_error not in row['stdout'] + row['stderr']:
            raise AssertionError('CPU_EXPECTED_ERROR_CODE_NOT_OBSERVED')
        row['status'] = 'PASS'

    def wait_health(self, name, row, expected_mode):
        port_text = run(['docker', 'port', name, '8080/tcp']).stdout.strip()
        port = int(port_text.rsplit(':', 1)[1])
        deadline = time.monotonic() + 45
        last = None
        while time.monotonic() < deadline:
            if not self.state(name).get('Running'):
                self.logs(name, row)
                raise AssertionError('CPU_SETUP_CONTAINER_EXITED')
            try:
                status, value, _ = self.request(port, '/healthz', host='127.0.0.1:' + str(port),
                                                origin=TEST_ORIGIN)
                if status == 200:
                    last = value
                    if value.get('mode') == expected_mode:
                        break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.25)
        else:
            self.logs(name, row)
            row['healthObserved'] = last
            raise AssertionError('CPU_SETUP_HEALTH_NOT_READY')
        if last.get('renderAllowed') is not False or last.get('gpuRenderingVerified') is not False:
            raise AssertionError('CPU_HEALTH_CANNOT_CLAIM_GPU_OR_RENDER_ADMISSION')
        row['health'] = last
        return port

    def assert_denied(self, row, label, response, codes=None):
        status, document, _cookie = response
        if status < 400 or status > 599:
            raise AssertionError('CPU_UNSAFE_REQUEST_WAS_NOT_DENIED_' + label.upper())
        code = error_code(document)
        if codes and code not in codes:
            raise AssertionError('CPU_UNEXPECTED_DENIAL_' + label.upper())
        row.setdefault('checks', {})[label] = {'status': status, 'errorCode': code, 'result': 'PASS'}

    def setup(self, port, row):
        status, challenge, challenge_cookie = self.request(port, '/setup/challenge')
        if status != 200 or not challenge_cookie or not isinstance(challenge.get('challenge'), str):
            raise AssertionError('CPU_SETUP_CHALLENGE_FAILED')
        self.assert_denied(row, 'wrongOwnerCodeBlocked', self.request(port,
            '/api/setup/login', method='POST', body={'password': self.owner + '-wrong',
                'origin': TEST_ORIGIN, 'challenge': challenge['challenge']},
            cookie=challenge_cookie, csrf=challenge['challenge'], setup=True))
        status, challenge, challenge_cookie = self.request(port, '/setup/challenge')
        if status != 200 or not challenge_cookie or not isinstance(challenge.get('challenge'), str):
            raise AssertionError('CPU_FRESH_SETUP_CHALLENGE_FAILED')
        status, login, setup_cookie = self.request(port, '/api/setup/login', method='POST',
            body={'password': self.owner, 'origin': TEST_ORIGIN, 'challenge': challenge['challenge']},
            cookie=challenge_cookie, csrf=challenge['challenge'], setup=True)
        if status != 200 or not login.get('authenticated') or not setup_cookie or not login.get('csrf'):
            raise AssertionError('CPU_SETUP_OWNER_AUTH_FAILED')
        status, saved, _ = self.request(port, '/api/setup/origin', method='POST',
            body={'origin': TEST_ORIGIN, 'confirm': True}, cookie=setup_cookie,
            csrf=login['csrf'], setup=True)
        if status != 200 or saved.get('registered') is not True or saved.get('origin') != TEST_ORIGIN:
            raise AssertionError('CPU_SETUP_ORIGIN_COMMIT_FAILED')
        row.setdefault('checks', {})['ownerAuthenticatedRegistration'] = {'result': 'PASS', 'http': status}
        return setup_cookie, login['csrf']

    def normal_login(self, port):
        status, value, cookie = self.request(port, '/api/login', method='POST',
                                             body={'password': self.owner})
        if status != 200 or not value.get('authenticated') or not cookie or not value.get('csrf'):
            raise AssertionError('CPU_NORMAL_OWNER_LOGIN_FAILED')
        return cookie, value['csrf']

    def execute(self):
        name, row = self.launch('BASELINE_HTTPS_ORIGIN_MISSING', extension=False)
        self.wait_exit(name, row, 1, 'STUDIO_HTTPS_ORIGIN_REQUIRED')
        name, row = self.launch('BASELINE_OWNER_CODE_MISSING', extension=False,
                               origin=TEST_ORIGIN, owner=False)
        self.wait_exit(name, row, 1, 'STUDIO_OWNER_CONFIGURATION_REQUIRED')
        # The old supervisor exits at CPU GPU admission before constructing the
        # UI. Isolate the unchanged image's actual constructor for this defect.
        code = ("import sys;sys.path.insert(0,'/opt/world-engine-production-studio')\n"
                "from studio_controller import StudioController\n"
                "from pathlib import Path\n"
                "try:\n"
                " StudioController(control_root=Path('/tmp/studio-digest-test'),"
                "export_root=Path('/world-storage'),image_digest='not-a-digest')\n"
                "except Exception as error:\n"
                " print(getattr(error,'code','UNEXPECTED_BASELINE_ERROR'));sys.exit(1)\n")
        name, row = self.launch('BASELINE_INVALID_DIGEST_CONSTRUCTOR', extension=False,
                               origin=TEST_ORIGIN, command=code)
        self.wait_exit(name, row, 1, 'STUDIO_IMAGE_DIGEST_REQUIRED')
        code = ("import sys,os;sys.path.insert(0,'/opt/world-engine-production-studio');"
                "import bootstrap;bootstrap.prepare_configuration(os.environ);"
                "print('STUDIO_POLICY_OPTIONAL_AT_BOOTSTRAP')")
        name, row = self.launch('BASELINE_OPERATOR_POLICY_MISSING_CONFIGURATION_ONLY',
                               extension=False, origin=TEST_ORIGIN, command=code)
        self.wait_exit(name, row, 0, 'STUDIO_POLICY_OPTIONAL_AT_BOOTSTRAP')

        name, row = self.launch('EXTENSION_OWNER_CODE_MISSING', owner=False)
        self.wait_exit(name, row, 1, 'STUDIO_OWNER_CONFIGURATION_REQUIRED')

        name, row = self.launch('EXTENSION_ORIGIN_MISSING_SETUP_AND_RESTART')
        port = self.wait_health(name, row, 'SETUP')
        # Wait past the actual no-NVIDIA legacy child exit. UI must remain
        # alive rather than mirroring the GPU child's exit in a restart loop.
        time.sleep(3)
        self.assert_denied(row, 'unconfiguredProductionBlocked', self.request(port,
            '/api/start', method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-no-render-key-0001', 'consent': True}))
        self.assert_denied(row, 'unauthenticatedSetupMutation', self.request(port,
            '/api/setup/origin', method='POST', body={'origin': TEST_ORIGIN, 'confirm': True},
            csrf='not-a-valid-test-csrf', setup=True))
        old_setup_cookie, old_setup_csrf = self.setup(port, row)
        self.wait_health(name, row, 'CONFIGURED')
        self.assert_denied(row, 'committedSetupSessionRevoked', self.request(port,
            '/api/setup/origin', method='POST', body={'origin': TEST_ORIGIN, 'confirm': True},
            cookie=old_setup_cookie, csrf=old_setup_csrf, setup=True))
        cookie, csrf = self.normal_login(port)
        self.assert_denied(row, 'wrongHostBlocked', self.request(port, '/api/session',
            cookie=cookie, host='attacker.invalid'))
        self.assert_denied(row, 'wrongOriginBlocked', self.request(port, '/api/session',
            cookie=cookie, origin='https://attacker.invalid'))
        self.assert_denied(row, 'normalCsrfPreserved', self.request(port, '/api/start',
            method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-no-render-key-0002', 'consent': True}, cookie=cookie,
            csrf='not-valid-normal-csrf'))
        self.assert_denied(row, 'missingGpuOrPolicyStillBlocksStart', self.request(port,
            '/api/start', method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-no-render-key-0003', 'consent': True}, cookie=cookie, csrf=csrf))
        run(['docker', 'restart', '--time', '15', name], timeout=35)
        port = self.wait_health(name, row, 'CONFIGURED')
        status, _, _ = self.request(port, '/login')
        if status != 200:
            raise AssertionError('CPU_REGISTERED_ORIGIN_RESTART_NOT_PERSISTED')
        row['checks']['sameContainerRestartOriginPersisted'] = {'result': 'PASS', 'http': status}
        self.logs(name, row)
        row['status'] = 'PASS'

        name, row = self.launch('EXTENSION_INVALID_DIGEST_WEB_ALIVE',
                               origin=TEST_ORIGIN, digest='not-a-digest')
        port = self.wait_health(name, row, 'CONFIGURED')
        cookie, csrf = self.normal_login(port)
        self.assert_denied(row, 'invalidDigestStartBlocked', self.request(port,
            '/api/start', method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-no-render-key-0004', 'consent': True}, cookie=cookie, csrf=csrf))
        self.logs(name, row)
        row['status'] = 'PASS'

        name, row = self.launch('EXTENSION_OPERATOR_POLICY_MISSING_WEB_ALIVE', origin=TEST_ORIGIN)
        port = self.wait_health(name, row, 'CONFIGURED')
        cookie, csrf = self.normal_login(port)
        self.assert_denied(row, 'policyMissingStartBlocked', self.request(port,
            '/api/start', method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-no-render-key-0005', 'consent': True}, cookie=cookie, csrf=csrf))
        self.logs(name, row)
        row['status'] = 'PASS'

    def cleanup(self):
        for name in reversed(self.containers):
            run(['docker', 'rm', '--force', name], check=False, timeout=30)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--extension', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.image.rsplit('@', 1)[-1] != BASE_DIGEST:
        raise SystemExit('CPU_IMMUTABLE_APPROVED_BASE_REQUIRED')
    extension = args.extension.resolve()
    if not extension.is_dir() or not (extension / 'https_bootstrap.py').is_file():
        raise SystemExit('CPU_STAGED_EXTENSION_REQUIRED')
    driver = run(['docker', 'info', '--format', '{{.Driver}}']).stdout.strip()
    if driver == 'vfs':
        raise SystemExit('CPU_PROBE_REFUSES_CONSTRAINED_VFS_DAEMON')
    report = {'schema': 'WORLD_ENGINE_STUDIO_HTTPS_CONTAINER_PROBE_V1', 'status': 'FAIL',
        'scope': 'ACTUAL_FREE_CPU_DOCKER_ONLY', 'approvedBaseDigest': BASE_DIGEST,
        'storageDriver': driver, 'gpuRenderingVerified': False,
        'requestTransport': 'LOOPBACK_HTTP_BACKEND_WITH_EXPLICIT_TEST_HTTPS_ORIGIN',
        'requiresSeparateMobileTlsResult': True,
        'actualGcubeFirstExitCauseConfirmed': False, 'renderJobStarted': False,
        'paidGpuDeploymentPerformed': False, 'cases': []}
    exit_code = 1
    with tempfile.TemporaryDirectory(prefix='studio-https-container-probe-') as temporary:
        private_root = Path(temporary)
        os.chmod(private_root, 0o700)
        probe = Probe(args.image, extension, private_root)
        try:
            probe.execute()
            report['status'] = 'PASS'
            exit_code = 0
        except Exception as error:
            report['failure'] = {'type': type(error).__name__,
                'code': safe_text(str(error), probe.private_values)}
            for name, row in zip(probe.containers, probe.cases):
                if row['status'] == 'RUNNING':
                    try:
                        probe.logs(name, row)
                    except Exception:
                        pass
                    row['status'] = 'FAIL'
        finally:
            report['cases'] = probe.cases
            probe.cleanup()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'cases': len(report['cases']),
        'scope': report['scope'], 'gpuRenderingVerified': False}, sort_keys=True))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
