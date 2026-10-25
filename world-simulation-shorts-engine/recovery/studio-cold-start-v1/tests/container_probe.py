#!/usr/bin/env python3
"""Read-only assertions inside disposable CPU validation containers.

Only the login action uses synthetic credentials created for this test container.
No submit, preflight, start, resume, render, or export API is called.
Never print credentials, cookies, request headers, private records, or raw errors.
"""
import argparse
import hashlib
import html
import http.client
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path('/var/lib/world-engine-cpu-test/auth')
REPO = Path('/opt/world-engine-handoffs/cpu-validation/repo')
ORIGIN = 'https://world-engine-test.invalid'
HOST = 'world-engine-test.invalid'


def require(value, code):
    if not value:
        raise RuntimeError(code)


def request(method, path, payload=None, cookie=None, port=8080):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {'Host': HOST, 'Origin': ORIGIN, 'X-Forwarded-Proto': 'https',
               'Sec-Fetch-Site': 'same-origin'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if cookie:
        headers['Cookie'] = cookie
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(4 * 1024 * 1024)
        return response.status, dict(response.getheaders()), data
    finally:
        connection.close()


def health():
    status, _, raw = request('GET', '/healthz')
    value = json.loads(raw)
    require(status == 200 and value.get('serviceAlive') is True, 'CPU_WEB_HEALTH_UNAVAILABLE')
    require(value.get('mode') == 'CONFIGURED', 'CPU_WEB_NOT_CONFIGURED')
    require(value.get('renderAllowed') is False and value.get('gpuRenderingVerified') is False,
            'CPU_HEALTH_MUST_NOT_GRANT_GPU')
    return {'serviceAlive': True, 'mode': 'CONFIGURED', 'renderAllowed': False,
            'gpuRenderingVerified': False}


def inventory():
    workers, old, admission, bootstraps = [], [], [], []
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            argv = (directory / 'cmdline').read_bytes().split(b'\0')
            paths = [word.decode('utf-8', 'replace') for word in argv if word]
        except (OSError, ProcessLookupError):
            continue
        pid = int(directory.name)
        if any(word.endswith('/studio-cold-start-v1/worker.py') for word in paths):
            workers.append(pid)
        if pid != 1 and any(word.endswith('/studio-cold-start-v1/bootstrap.py') for word in paths):
            bootstraps.append(pid)
        if any(word in {'/opt/world-engine-studio-https-proxy-fix/proxy_server.py',
                        '/opt/world-engine-studio-https-proxy-fix/proxy_bootstrap.py',
                        '/opt/world-engine-studio-https-bootstrap/https_server.py',
                        '/opt/world-engine-studio-https-bootstrap/https_bootstrap.py'} for word in paths):
            old.append(pid)
        if '/opt/world-engine-storage-fix/launch.py' in paths:
            admission.append(pid)
    require(len(workers) == 1 and len(bootstraps) == 1 and not old, 'CPU_SINGLE_LATEST_STUDIO_REQUIRED')
    private_keys = {b'WORLD_ENGINE_STUDIO_OWNER_CODE', b'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}
    worker_env = (Path('/proc') / str(workers[0]) / 'environ').read_bytes().split(b'\0')
    require(not private_keys.intersection(word.split(b'=', 1)[0] for word in worker_env),
            'CPU_WORKER_SECRET_ENV_LEAK')
    require(not list(Path('/dev').glob('nvidia*')), 'CPU_VALIDATION_MUST_NOT_HAVE_NVIDIA_DEVICES')
    try:
        status, _, raw = request('GET', '/healthz', port=8000)
        value = json.loads(raw)
        gpu_ready = status == 200 and value.get('gpuRenderingVerified') is True
    except (OSError, ValueError, http.client.HTTPException):
        gpu_ready = False
    require(not gpu_ready, 'CPU_VALIDATION_MUST_NOT_REPORT_GPU_READY')
    jobs = ROOT / 'production' / 'handoff-gpu-jobs'
    require(not jobs.exists() or not list(jobs.iterdir()), 'CPU_NO_GPU_JOB_REQUIRED')
    require(not list(Path('/world-storage').rglob('*.mp4')), 'CPU_NO_MP4_REQUIRED')
    return {'workerPid': workers[0], 'workerCount': 1, 'bootstrapCount': 1,
            'oldStudioCount': 0, 'gpuAdmissionAliveCount': len(admission),
            'workerSecretEnvironmentPresent': False, 'gpuReady': False,
            'gpuJobs': 0, 'mp4Files': 0}


def private_snapshot():
    result = {}
    for name in ('owner-code', 'production/operator_policy.json'):
        path = ROOT / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and info.st_gid == 1000
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                'CPU_PRIVATE_FILE_CONTRACT_FAILED')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def ui():
    # The private record contains a newly generated test-only password.
    # It never leaves this isolated container or appears in stdout/stderr.
    status, _, _ = request('GET', '/')
    require(status == 401, 'CPU_UI_AUTHENTICATION_REQUIRED')
    owner = (ROOT / 'owner-code').read_text()
    status, headers, raw = request('POST', '/api/login', {'password': owner})
    value = json.loads(raw)
    require(status == 200 and value.get('authenticated') is True, 'CPU_SYNTHETIC_LOGIN_FAILED')
    cookie_header = headers.get('Set-Cookie', '')
    cookie = cookie_header.split(';', 1)[0]
    require(cookie.startswith('world_studio_session=') and '; Secure' in cookie_header
            and '; HttpOnly' in cookie_header and '; SameSite=Strict' in cookie_header,
            'CPU_SECURE_SESSION_COOKIE_REQUIRED')
    status, _, raw = request('GET', '/', cookie=cookie)
    require(status == 200, 'CPU_AUTHENTICATED_MOBILE_UI_FAILED')
    text = raw.decode('utf-8')
    match = re.search(r'<textarea id="example-data"[^>]*>(.*?)</textarea>', text, re.S)
    require(match is not None, 'CPU_HANDOFF_MOBILE_UI_REQUIRED')
    embedded = json.loads(html.unescape(match.group(1)))
    expected_path = REPO / 'world-simulation-shorts-engine/recovery/universal-presentation-v2/examples/AVIATION_EUROPE_NL.json'
    require(embedded == json.loads(expected_path.read_text()), 'CPU_AIRCRAFT_EXAMPLE_WIRE_CHANGED')
    require('id="start" type="button" disabled' in text, 'CPU_RENDER_BUTTON_MUST_START_DISABLED')
    status, _, raw = request('GET', '/api/session', cookie=cookie)
    session = json.loads(raw)
    require(status == 200 and session.get('authenticated') is True
            and session.get('gpuExecutionVerified') is False, 'CPU_SESSION_CONTRACT_FAILED')
    return {'authenticatedMobileUI': True, 'example': 'AVIATION_EUROPE_NL.json',
            'exampleWireMatches': True, 'renderStartRequested': False,
            'realHTTPSVerified': False, 'originIsSyntheticTestFixture': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('health', 'inventory', 'snapshot', 'ui'))
    args = parser.parse_args()
    try:
        result = {'health': health, 'inventory': inventory, 'snapshot': private_snapshot, 'ui': ui}[args.mode]()
        print(json.dumps({'status': 'PASS', 'facts': result}, sort_keys=True))
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'CPU_[A-Z0-9_]{1,95}', code):
            code = 'CPU_PROBE_UNAVAILABLE'
        print(json.dumps({'status': 'BLOCKED', 'code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
