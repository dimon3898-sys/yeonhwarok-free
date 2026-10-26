#!/usr/bin/env python3
"""Disposable CPU probe; never starts, resumes or renders a job.

Executed through docker exec stdin, not copied into the production image.
Synthetic credentials/cookies/private input bytes never leave the container.
The one planning submission uses the existing CPU normalizer and read-only
hardware-health inspection; no GPU device is exposed to these containers.
"""
import argparse
import hashlib
import html
from http.cookies import SimpleCookie
import http.client
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path('/var/lib/world-engine-studio-v2/auth')
REPO = Path('/opt/world-engine-handoffs/studio-v2/repo')
REL = 'world-simulation-shorts-engine/recovery/studio-cold-start-v2'
ORIGIN = 'https://world-engine-test.invalid'
HOST = 'world-engine-test.invalid'
FIXTURE_DIGEST = 'sha256:' + 'a' * 64


def require(value, code):
    if not value:
        raise RuntimeError(code)


def request(method, path, payload=None, cookies=None, extra=None, timeout=5):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {'Host': HOST, 'Origin': ORIGIN, 'X-Forwarded-Proto': 'https',
               'Sec-Fetch-Site': 'same-origin'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if cookies:
        headers['Cookie'] = '; '.join(name + '=' + value for name, value in cookies.items())
    if extra:
        headers.update(extra)
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        # Preserve repeated Set-Cookie headers: setup login sends two cookies.
        response_headers = response.getheaders()
        data = response.read(4 * 1024 * 1024 + 1)
        require(len(data) <= 4 * 1024 * 1024, 'CPU_RESPONSE_LIMIT')
        return response.status, response_headers, data
    finally:
        connection.close()


def update_cookies(jar, headers):
    for name, value in headers:
        if name.lower() != 'set-cookie':
            continue
        parsed = SimpleCookie()
        parsed.load(value)
        for key, item in parsed.items():
            require(bool(item['secure']) and bool(item['httponly'])
                    and item['samesite'].lower() == 'strict', 'CPU_SECURE_COOKIE_REQUIRED')
            if item.value:
                jar[key] = item.value
            else:
                jar.pop(key, None)


def decoded(raw):
    value = json.loads(raw)
    require(isinstance(value, dict), 'CPU_JSON_OBJECT_REQUIRED')
    return value


def health(expected='SETUP'):
    status, _, raw = request('GET', '/healthz')
    value = decoded(raw)
    require(status == 200 and value.get('serviceAlive') is True, 'CPU_WEB_HEALTH_UNAVAILABLE')
    require(value.get('mode') == expected, 'CPU_WEB_MODE_UNEXPECTED')
    require(value.get('renderAllowed') is False and value.get('gpuRenderingVerified') is False,
            'CPU_HEALTH_MUST_NOT_GRANT_GPU')
    return {'serviceAlive': True, 'mode': expected, 'renderAllowed': False,
            'gpuRenderingVerified': False}


def inventory():
    workers, bootstraps, old, renderers = [], [], [], []
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            argv = (directory / 'cmdline').read_bytes().split(b'\0')
            paths = [word.decode('utf-8', 'replace') for word in argv if word]
        except (OSError, ProcessLookupError):
            continue
        pid = int(directory.name)
        if any(word.endswith('/studio-cold-start-v2/worker.py') for word in paths):
            workers.append(pid)
        if pid != 1 and any(word.endswith('/studio-cold-start-v2/bootstrap.py') for word in paths):
            bootstraps.append(pid)
        if any(word in {'/opt/world-engine-studio-https-proxy-fix/proxy_server.py',
                        '/opt/world-engine-studio-https-proxy-fix/proxy_bootstrap.py',
                        '/opt/world-engine-studio-https-bootstrap/https_server.py',
                        '/opt/world-engine-studio-https-bootstrap/https_bootstrap.py'} for word in paths):
            old.append(pid)
        if any(word.endswith('/nvidia_worker.py') or word.endswith('/lease_supervisor.py')
               or Path(word).name in {'chromium', 'chromium-browser', 'ffmpeg'} for word in paths):
            renderers.append(pid)
    require(len(workers) == 1 and len(bootstraps) == 1 and not old,
            'CPU_SINGLE_LATEST_STUDIO_REQUIRED')
    require(not renderers, 'CPU_NO_RENDER_PROCESS_REQUIRED')
    private_keys = {b'WORLD_ENGINE_STUDIO_OWNER_CODE', b'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}
    worker_env = (Path('/proc') / str(workers[0]) / 'environ').read_bytes().split(b'\0')
    require(not private_keys.intersection(word.split(b'=', 1)[0] for word in worker_env),
            'CPU_WORKER_SECRET_ENV_LEAK')
    init = Path('/proc/1/cmdline').read_bytes().split(b'\0')
    require(init and Path(init[0].decode()).name in {'tini', 'tini-static'}
            and b'-g' in init and str(REPO / REL / 'bootstrap.py').encode() in init,
            'CPU_DEFAULT_TINI_CHAIN_REQUIRED')
    require(not list(Path('/dev').glob('nvidia*')), 'CPU_NO_GPU_DEVICES_REQUIRED')
    jobs = ROOT / 'production' / 'handoff-gpu-jobs'
    require(not jobs.exists() or not list(jobs.iterdir()), 'CPU_NO_GPU_JOB_REQUIRED')
    require(not (ROOT / 'production' / 'active.json').exists(), 'CPU_NO_START_CLAIM_REQUIRED')
    require(not list(Path('/world-storage').rglob('*.mp4')), 'CPU_NO_MP4_REQUIRED')
    for file in (REPO / REL / 'bootstrap.py', REPO / REL / 'worker.py'):
        for path in (file, *file.parents):
            info = path.stat()
            require(not path.is_symlink() and not os.access(path, os.W_OK),
                    'CPU_PACKAGED_SOURCE_MUST_NOT_BE_ENGINE_WRITABLE')
            require(not info.st_mode & 0o002, 'CPU_PACKAGED_SOURCE_WORLD_WRITABLE')
    return {'workerPid': workers[0], 'workerCount': 1, 'bootstrapCount': 1,
            'oldStudioCount': 0, 'rendererCount': 0, 'gpuJobs': 0,
            'mp4Files': 0, 'workerSecretEnvironmentPresent': False,
            'packagedSourcesEngineReadOnly': True, 'defaultTiniChainVerified': True}


def snapshot():
    result = {}
    for name in ('owner-code', 'production/operator_policy.json'):
        path = ROOT / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and info.st_gid == 1000
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                'CPU_PRIVATE_FILE_CONTRACT_FAILED')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def challenge():
    jar = {}
    status, headers, raw = request('GET', '/setup/challenge')
    value = decoded(raw)
    require(status == 200 and isinstance(value.get('challenge'), str), 'CPU_SETUP_CHALLENGE_FAILED')
    update_cookies(jar, headers)
    require('__Host-world_studio_setup_challenge' in jar, 'CPU_SETUP_CHALLENGE_COOKIE_REQUIRED')
    return jar, value['challenge']


def setup_and_plan():
    health('SETUP')
    before = snapshot()
    status, headers, _ = request('GET', '/')
    require(status == 303 and ('Location', '/setup') in headers,
            'CPU_SETUP_ROOT_MUST_REDIRECT')
    status, _, page = request('GET', '/setup')
    require(status == 200 and b'<form' in page, 'CPU_EXISTING_SETUP_UI_REQUIRED')
    require(not (ROOT / 'https-origin.json').exists(), 'CPU_SETUP_ORIGIN_MUST_START_UNSET')
    # Existing guarded production endpoint is unreachable before owner registration.
    status, _, _ = request('GET', '/api/session')
    require(status == 503, 'CPU_SETUP_MUST_BLOCK_PRODUCTION')
    owner = (ROOT / 'owner-code').read_text()
    jar, nonce = challenge()
    status, _, _ = request('POST', '/api/setup/login',
        {'password': 'not-the-synthetic-owner-password', 'origin': ORIGIN, 'challenge': nonce},
        jar, {'X-Studio-Setup-CSRF': nonce})
    require(status == 401 and not (ROOT / 'https-origin.json').exists(),
            'CPU_WRONG_OWNER_MUST_FAIL_CLOSED')
    jar, nonce = challenge()
    status, _, _ = request('POST', '/api/setup/login',
        {'password': owner, 'origin': ORIGIN, 'challenge': nonce}, jar,
        {'X-Studio-Setup-CSRF': 'invalid-csrf'})
    require(status == 403 and not (ROOT / 'https-origin.json').exists(),
            'CPU_WRONG_SETUP_CSRF_MUST_FAIL_CLOSED')
    jar, nonce = challenge()
    status, _, _ = request('POST', '/api/setup/login',
        {'password': owner, 'origin': ORIGIN, 'challenge': nonce}, jar,
        {'X-Studio-Setup-CSRF': nonce, 'Origin': 'https://foreign-test.invalid'})
    require(status == 403 and not (ROOT / 'https-origin.json').exists(),
            'CPU_FOREIGN_ORIGIN_MUST_FAIL_CLOSED')
    jar, nonce = challenge()
    status, headers, raw = request('POST', '/api/setup/login',
        {'password': owner, 'origin': ORIGIN, 'challenge': nonce}, jar,
        {'X-Studio-Setup-CSRF': nonce})
    value = decoded(raw)
    require(status == 200 and value.get('authenticated') is True and value.get('renderAllowed') is False,
            'CPU_SETUP_OWNER_LOGIN_FAILED')
    update_cookies(jar, headers)
    require('__Host-world_studio_setup' in jar, 'CPU_SETUP_SESSION_COOKIE_REQUIRED')
    require(not (ROOT / 'https-origin.json').exists(), 'CPU_LOGIN_MUST_NOT_COMMIT_ORIGIN')
    commit_csrf = value.get('csrf')
    require(isinstance(commit_csrf, str), 'CPU_SETUP_COMMIT_CSRF_REQUIRED')
    status, _, _ = request('POST', '/api/setup/origin', {'origin': ORIGIN, 'confirm': False},
                           jar, {'X-Studio-Setup-CSRF': commit_csrf})
    require(status == 403 and not (ROOT / 'https-origin.json').exists(),
            'CPU_EXPLICIT_ORIGIN_CONFIRMATION_REQUIRED')
    status, headers, raw = request('POST', '/api/setup/origin', {'origin': ORIGIN, 'confirm': True},
                                  jar, {'X-Studio-Setup-CSRF': commit_csrf})
    value = decoded(raw)
    require(status == 200 and value.get('registered') is True and value.get('reloginRequired') is True
            and value.get('renderAllowed') is False, 'CPU_AUTHENTICATED_ORIGIN_COMMIT_FAILED')
    update_cookies(jar, headers)
    health('CONFIGURED')
    require(snapshot() == before, 'CPU_SETUP_CHANGED_OWNER_OR_POLICY')
    origin = json.loads((ROOT / 'https-origin.json').read_text())
    require(origin.get('origin') == ORIGIN, 'CPU_EXPLICIT_ORIGIN_NOT_PERSISTED')
    status, _, _ = request('GET', '/')
    require(status == 401, 'CPU_PRODUCTION_MUST_REQUIRE_FRESH_LOGIN')
    status, headers, raw = request('POST', '/api/login', {'password': owner})
    value = decoded(raw)
    require(status == 200 and value.get('authenticated') is True, 'CPU_PRODUCTION_LOGIN_FAILED')
    jar = {}
    update_cookies(jar, headers)
    require('world_studio_session' in jar, 'CPU_PRODUCTION_SESSION_REQUIRED')
    csrf = value.get('csrf')
    status, _, raw = request('GET', '/', cookies=jar)
    require(status == 200, 'CPU_AUTHENTICATED_MOBILE_UI_FAILED')
    page = raw.decode()
    match = re.search(r'<textarea id="example-data"[^>]*>(.*?)</textarea>', page, re.S)
    require(match is not None and 'id="start" type="button" disabled' in page,
            'CPU_HANDOFF_MOBILE_UI_REQUIRED')
    example = json.loads(html.unescape(match.group(1)))
    example_file = REPO / 'world-simulation-shorts-engine/recovery/universal-presentation-v2/examples/AVIATION_EUROPE_NL.json'
    require(example == json.loads(example_file.read_text()), 'CPU_AIRCRAFT_EXAMPLE_WIRE_CHANGED')
    # Existing submit performs CPU normalization and preflight inspection only.
    # It does not invoke start(), start_studio_job(), GPU capture or FFmpeg.
    status, _, raw = request('POST', '/api/submissions',
        {'schema': 'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1', 'prompt': example,
         'sceneId': '__timeline__'}, jar, {'X-Studio-CSRF': csrf}, timeout=240)
    value = decoded(raw)
    require(status == 201 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',
            str(value.get('submissionId', ''))), 'CPU_PLANNING_SUBMISSION_FAILED')
    preflight = value.get('preflight', {})
    require(preflight.get('valid') is True and preflight.get('ready') is False
            and preflight.get('requiresGpu') is True and preflight.get('gpuRenderingVerified') is False,
            'CPU_SUBMISSION_MUST_NOT_APPROVE_GPU')
    # Find this one submission by identifier without exposing private file content.
    submission_id = value['submissionId']
    files = list((ROOT / 'production' / 'submissions').glob(submission_id + '.json'))
    require(len(files) == 1, 'CPU_SAVED_SUBMISSION_REQUIRED')
    saved = json.loads(files[0].read_text())
    submission = saved.get('submission', {})
    plan = submission.get('videoPlan', {})
    require(submission.get('schema') == 'WORLD_ENGINE_NVIDIA_STUDIO_SUBMISSION_V1'
            and plan.get('schema') == 'WORLD_ENGINE_NVIDIA_PRESENTATION_PLAN_V1'
            and plan.get('durationSeconds') == 6 and plan.get('totalFrames') == 180
            and plan.get('fps') == 30 and plan.get('resolution') == {'width': 1080, 'height': 1920}
            and plan.get('aspectRatio') == '9:16'
            and plan.get('audioSettings') == {'enabled': False, 'mode': 'SILENT'}
            and plan.get('renderProfile', {}).get('imageDigest') == FIXTURE_DIGEST
            and plan.get('renderProfile', {}).get('backend') == 'vulkan',
            'CPU_LATEST_NVIDIA_PLAN_REQUIRED')
    inventory()
    require(snapshot() == before, 'CPU_PLAN_CHANGED_OWNER_OR_POLICY')
    return {'setupWaitObserved': True, 'setupRootRedirects': True,
            'wrongOwnerRejected': True, 'csrfMismatchRejected': True,
            'foreignOriginRejected': True, 'explicitConfirmationRequired': True,
            'authenticatedOriginCommitted': True, 'freshProductionLoginRequired': True,
            'authenticatedMobileUI': True, 'example': 'AVIATION_EUROPE_NL.json',
            'nvidiaPlanProduced': True, 'planFrames': 180, 'planSeconds': 6,
            'planWidth': 1080, 'planHeight': 1920, 'planFPS': 30, 'silent': True,
            'syntheticDeploymentIdentityBound': True, 'realImageDigestVerified': False,
            'gpuReady': False, 'renderStartRequested': False,
            'privateOwnerPolicyPreserved': True, 'realHTTPSVerified': False,
            'originIsSyntheticTestFixture': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('health', 'inventory', 'setup-plan'))
    args = parser.parse_args()
    try:
        facts = {'health': health, 'inventory': inventory, 'setup-plan': setup_and_plan}[args.mode]()
        print(json.dumps({'status': 'PASS', 'facts': facts}, sort_keys=True))
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r'CPU_[A-Z0-9_]{1,95}', code):
            code = 'CPU_PROBE_BLOCKED'
        print(json.dumps({'status': 'BLOCKED', 'code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
