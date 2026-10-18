#!/usr/bin/env python3
"""Actual free CPU-container safety probe for the additive proxy entry.

The frozen HTTPS V1 Docker driver is reused without changing its source. These
are explicit CPU synthetic-origin cases, not observed gCube proxy headers or
NVIDIA/GPU success. Only this probe's own containers are removed.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time

HERE = Path(__file__).resolve().parents[1]
PARENT = (Path('/opt/world-engine-studio-https-bootstrap') if HERE.is_relative_to('/opt')
          else HERE.parent / 'studio-https-bootstrap-v1')
if hashlib.sha256((PARENT / 'tests/container_probe.py').read_bytes()).hexdigest() != 'dc5ec87d604e7dc5ad3b413ab292f125163fb6ffa13208b8c051cb1f6673d8b2':
    raise RuntimeError('PROXY_FROZEN_CPU_DRIVER_CHANGED')
spec = importlib.util.spec_from_file_location('_frozen_https_container_probe', PARENT / 'tests/container_probe.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

BASE_DIGEST = 'sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833'
EXTENSION_ROOT = '/opt/world-engine-studio-https-proxy-fix'
old.EXTENSION_ROOT = EXTENSION_ROOT
old.BASE_DIGEST = BASE_DIGEST
TEST_ORIGIN = old.TEST_ORIGIN
BOOT = ("import runpy,sys;sys.path.insert(0," + repr(EXTENSION_ROOT) + ");"
        "runpy.run_path(" + repr(EXTENSION_ROOT + '/proxy_bootstrap.py') + ",run_name='__main__')")


class Probe(old.Probe):
    def launch(self, case, **kwargs):
        kwargs.setdefault('command', BOOT)
        name, row = super().launch(case, **kwargs)
        row['scope'] = 'ACTUAL_CPU_CONTAINER_SYNTHETIC_ORIGIN'
        row['actualGcubeProxyHeadersObserved'] = False
        return name, row

    def policy_preflight(self, port, row, cookie, csrf):
        # Use the frozen, already-shipped verified preset without starting a
        # render job. This checks actual authenticated HTTP preflight and the
        # original missing-policy gate, rather than a hardware-success mock.
        body = {'prompt': json.dumps({'schema': 'WORLD_ENGINE_STUDIO_PROMPT_V1',
                'preset': 'VERIFIED_FRONT_V4_80S', 'title': 'CPU TEST ONLY',
                'durationSeconds': 80, 'profile': 'V4_ARCHIVAL_80S'}),
            'durationSeconds': 80, 'profile': 'V4_ARCHIVAL_80S', 'sfx': {'enabled': False}}
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
        try:
            connection.request('POST', '/api/preflight', body=json.dumps(body).encode(),
                headers={'Host': 'studio-ci.invalid', 'Origin': TEST_ORIGIN,
                    'Sec-Fetch-Site': 'same-origin', 'Content-Type': 'application/json',
                    'Cookie': cookie, 'X-Studio-CSRF': csrf})
            response = connection.getresponse()
            payload = json.loads(response.read(512 * 1024))
        finally:
            connection.close()
        # The inherited bootstrap GateController rejects a missing operator
        # policy before parsing a production plan or contacting GPU admission.
        error = payload.get('error', {}) if isinstance(payload, dict) else {}
        if (response.status != 503 or error.get('code') != 'STUDIO_OPERATOR_POLICY_REQUIRED'
                or payload.get('renderAllowed') is not False):
            raise AssertionError('CPU_AUTHENTICATED_PREFLIGHT_MISSING_POLICY_NOT_BLOCKED')
        row.setdefault('checks', {})['authenticatedPreflightMissingPolicyBlocked'] = {
            'result': 'PASS', 'http': response.status, 'ready': False,
            'errorCode': 'STUDIO_OPERATOR_POLICY_REQUIRED'}

    def assert_protection(self, port, row, cookie, csrf):
        self.assert_denied(row, 'wrongHostBlocked', self.request(port, '/api/session',
            cookie=cookie, host='attacker.invalid'))
        self.assert_denied(row, 'wrongOriginBlocked', self.request(port, '/api/session',
            cookie=cookie, origin='https://attacker.invalid'))
        self.assert_denied(row, 'normalCsrfPreserved', self.request(port, '/api/start',
            method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-proxy-no-render-csrf-0001', 'consent': True},
            cookie=cookie, csrf='not-valid-normal-csrf'))
        self.assert_denied(row, 'missingPolicyStillBlocksStart', self.request(port, '/api/start',
            method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-proxy-no-render-start-0001', 'consent': True},
            cookie=cookie, csrf=csrf))

    def wait_cpu_legacy_exit(self, name, row):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not self.state(name).get('Running'):
                raise AssertionError('CPU_PROXY_UI_EXITED_WITH_LEGACY_CHILD')
            logs = old.run(['docker', 'logs', name], check=False).stdout
            for line in logs[-old.MAX_LOG:].splitlines():
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if (isinstance(value, dict) and value.get('stage') == 'GPU_ADMISSION_EXITED'
                        and type(value.get('exitCode')) is int):
                    row.setdefault('checks', {})['uiSurvivesActualCpuLegacyChildExit'] = {
                        'result': 'PASS', 'legacyExitCode': value['exitCode'],
                        'legacyFirstFailureStage': 'NOT_INFERRED', 'gpuRenderingVerified': False}
                    return
            time.sleep(0.25)
        raise AssertionError('CPU_LEGACY_CHILD_EXIT_NOT_OBSERVED')

    def execute(self):
        name, row = self.launch('PROXY_OWNER_CODE_MISSING_FAILS_CLOSED', owner=False)
        self.wait_exit(name, row, 1, 'STUDIO_OWNER_CONFIGURATION_REQUIRED')

        name, row = self.launch('PROXY_ORIGIN_MISSING_AUTHENTICATED_SETUP_RESTART')
        port = self.wait_health(name, row, 'SETUP')
        # Observe the actual CPU legacy child's exit without guessing which
        # legacy prerequisite failed. The UI must remain alive afterwards.
        self.wait_cpu_legacy_exit(name, row)
        self.assert_denied(row, 'unconfiguredProductionBlocked', self.request(port,
            '/api/start', method='POST', body={'submissionId': 'never-created',
                'idempotencyKey': 'cpu-proxy-no-render-setup-0001', 'consent': True}))
        self.assert_denied(row, 'unauthenticatedOriginMutationBlocked', self.request(port,
            '/api/setup/origin', method='POST', body={'origin': TEST_ORIGIN, 'confirm': True},
            csrf='not-valid-setup-csrf', setup=True))
        old_setup_cookie, old_setup_csrf = self.setup(port, row)
        self.wait_health(name, row, 'CONFIGURED')
        self.assert_denied(row, 'committedSetupSessionRevoked', self.request(port,
            '/api/setup/origin', method='POST', body={'origin': TEST_ORIGIN, 'confirm': True},
            cookie=old_setup_cookie, csrf=old_setup_csrf, setup=True))
        cookie, csrf = self.normal_login(port)
        self.assert_protection(port, row, cookie, csrf)
        old.run(['docker', 'restart', '--time', '15', name], timeout=35)
        port = self.wait_health(name, row, 'CONFIGURED')
        status, _, _ = self.request(port, '/login')
        if status != 200:
            raise AssertionError('CPU_PROXY_ORIGIN_RESTART_NOT_PERSISTED')
        row['checks']['sameContainerRestartOriginPersisted'] = {'result': 'PASS', 'http': status}
        self.logs(name, row)
        row['status'] = 'PASS'

        name, row = self.launch('PROXY_CONFIGURED_ORIGIN_AUTH_AND_POLICY_GATES', origin=TEST_ORIGIN)
        port = self.wait_health(name, row, 'CONFIGURED')
        cookie, csrf = self.normal_login(port)
        self.assert_protection(port, row, cookie, csrf)
        self.policy_preflight(port, row, cookie, csrf)
        self.logs(name, row)
        row['status'] = 'PASS'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--extension', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.image.rsplit('@', 1)[-1] != BASE_DIGEST:
        raise SystemExit('CPU_IMMUTABLE_APPROVED_HTTPS_BASE_REQUIRED')
    extension = args.extension.resolve()
    if not extension.is_dir() or not (extension / 'proxy_bootstrap.py').is_file():
        raise SystemExit('CPU_STAGED_PROXY_EXTENSION_REQUIRED')
    driver = old.run(['docker', 'info', '--format', '{{.Driver}}']).stdout.strip()
    if driver == 'vfs':
        raise SystemExit('CPU_PROBE_REFUSES_CONSTRAINED_VFS_DAEMON')
    report = {'schema': 'WORLD_ENGINE_STUDIO_HTTPS_PROXY_CONTAINER_PROBE_V1', 'status': 'FAIL',
        'scope': 'ACTUAL_FREE_CPU_DOCKER_SYNTHETIC_ORIGIN_ONLY',
        'approvedBaseDigest': BASE_DIGEST, 'storageDriver': driver,
        'gpuRenderingVerified': False, 'actualGcubeProxyHeadersObserved': False,
        'renderJobStarted': False, 'paidGpuDeploymentPerformed': False,
        'requestTransport': 'LOOPBACK_HTTP_BACKEND_WITH_EXPLICIT_TEST_HTTPS_ORIGIN',
        'requiresSeparateMobileTlsResult': True, 'cases': []}
    exit_code = 1
    with tempfile.TemporaryDirectory(prefix='studio-https-proxy-container-') as temporary:
        private_root = Path(temporary)
        os.chmod(private_root, 0o700)
        probe = Probe(args.image, extension, private_root)
        try:
            probe.execute()
            report['status'] = 'PASS'
            exit_code = 0
        except Exception as error:
            report['failure'] = {'type': type(error).__name__,
                'code': old.safe_text(str(error), probe.private_values)}
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
