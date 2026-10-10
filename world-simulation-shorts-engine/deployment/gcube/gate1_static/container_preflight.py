"""Bounded CPU container release checks. No NVIDIA/gCube execution."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

image = sys.argv[1]
evidence = Path(sys.argv[2])
evidence.mkdir(parents=True, exist_ok=True)
name = 'gate1-static-preflight-' + secrets.token_hex(6)
owner = secrets.token_urlsafe(24)
started = time.monotonic()
completed = 0


def report(stage, result='PASS'):
    global completed
    if result == 'PASS':
        completed += 1
    row = {'stage': stage, 'result': result, 'elapsed_seconds': round(time.monotonic() - started, 3), 'completed': completed}
    print(json.dumps(row), flush=True)
    with (evidence / 'container-preflight.jsonl').open('a') as out:
        out.write(json.dumps(row) + '\n')


def command(arguments, timeout=60):
    return subprocess.run(arguments, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout).stdout


try:
    command(['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::8000', '--shm-size=1g',
             '-e', 'WORLD_ENGINE_OWNER_CODE=' + owner, image])
    port = int(command(['docker', 'port', name, '8000/tcp']).strip().rsplit(':', 1)[1])
    def request(method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        values = dict(headers or {})
        if body is not None:
            values['Content-Type'] = 'application/json'
            body = json.dumps(body)
        connection.request(method, path, body, values)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result
    deadline = time.monotonic() + 60
    while True:
        try:
            code, _, body = request('GET', '/healthz')
            value = json.loads(body)
            if code == 200 and value['ok'] and value['authentication_required'] and not value['auto_render']:
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError('CONTAINER_HEALTH_TIMEOUT')
        print(json.dumps({'stage': 'WAIT_FOR_HEALTH', 'result': 'IN_PROGRESS', 'elapsed_seconds': round(time.monotonic() - started, 3)}), flush=True)
        time.sleep(1)
    report('CONTAINER_BOOT_HEALTH_NO_AUTO_RENDER')
    assert request('GET', '/api/session')[0] == 401
    assert request('GET', '/download/notfound/png')[0] == 401
    report('CONTAINER_UNAUTHENTICATED_DENIED')
    code, headers, body = request('POST', '/auth/login', {'password': owner})
    assert code == 200 and json.loads(body)['authenticated']
    authenticated = {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-Proof-CSRF': json.loads(body)['csrf']}
    report('CONTAINER_LOGIN')
    code, _, body = request('GET', '/api/session', headers=authenticated)
    identity = json.loads(body)['source']
    assert code == 200 and identity['shaderHash'] == '17d843163cf6648d8f6cc3199240c2962f69398c39f673354e5e7e802ad17d38'
    report('CONTAINER_FROZEN_IDENTITY')
    assert request('POST', '/api/generate', {'mode': 'cpu'}, authenticated)[0] == 400
    report('CONTAINER_CPU_REQUEST_REJECTED')
    code, _, body = request('GET', '/')
    assert code == 200 and b'GENERATE STATIC PROOF' in body and b'DOWNLOAD PNG' in body
    report('CONTAINER_STATIC_PROOF_UI')
    # No paid GPU is attached. Explicitly check that CPU CI cannot succeed.
    code, _, body = request('POST', '/api/check-gpu', {}, authenticated)
    assert code == 202
    job = json.loads(body)['job']
    deadline = time.monotonic() + 390
    while True:
        code, _, body = request('GET', '/api/jobs/' + job, headers=authenticated)
        result = json.loads(body)
        print(json.dumps({'stage': 'GPU_REJECTION_CPU_CI', 'result': result['status'], 'elapsed_seconds': round(time.monotonic() - started, 3), 'last_stage': result['events'][-1]['stage'] if result['events'] else 'START'}), flush=True)
        if result['status'] != 'RUNNING':
            break
        if time.monotonic() > deadline:
            raise RuntimeError('GPU_REJECTION_DEADLINE')
        time.sleep(2)
    assert result['status'] == 'FAIL'
    assert request('GET', '/download/' + job + '/png', headers=authenticated)[0] == 409
    report('CONTAINER_NO_GPU_NO_SUCCESS_NO_PNG')
    code, headers, body = request('GET', '/download/' + job + '/diagnostic', headers=authenticated)
    assert code == 200 and 'attachment;' in headers['Content-Disposition']
    diagnostic = json.loads(body)
    assert diagnostic['capability_result']['result'] == 'FAIL'
    (evidence / 'container-no-gpu.diagnostic.json').write_bytes(body)
    report('CONTAINER_FAILURE_DIAGNOSTIC_DOWNLOAD')
    time.sleep(2)
    assert json.loads(request('GET', '/healthz')[2])['ok']
    report('CONTAINER_HEALTH_AFTER_FAILURE')
    command(['docker', 'exec', name, 'python', '-c', 'import subprocess; subprocess.run(["/usr/bin/chromium","--version"],check=True,timeout=10); subprocess.run(["node","--version"],check=True,timeout=10)'])
    report('CONTAINER_BROWSER_NODE_PRESENT')
except Exception:
    report('CONTAINER_PREFLIGHT_FAILED', 'FAIL')
    raise
finally:
    subprocess.run(['docker', 'logs', name], stdout=(evidence / 'container.log').open('w'), stderr=subprocess.STDOUT, timeout=10)
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
