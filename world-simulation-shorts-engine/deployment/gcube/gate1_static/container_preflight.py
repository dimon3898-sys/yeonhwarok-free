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
RENDERER_SHA = 'e0108a8bf3cb3828529b9077925b9429455dbccd2c695f797f2578ac904b067d'
SOFTWARE_D_SHA = '29323353b1e76af7dfbc54407a9cdbdbb559fbfefe9ffac08d70f65f54e98a8d'
DEM_SHA = '08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8'
PNG_NAME = 'SUEZ_TERRAIN_SHADING_RTX4080S.png'


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
    session = json.loads(body)
    identity = session['source']
    assert code == 200 and identity['shaderHash'] == RENDERER_SHA
    assert identity['softwareProofHash'] == SOFTWARE_D_SHA
    assert identity['softwareDFinalHash'] == SOFTWARE_D_SHA
    assert identity['heightSourceHash'] == DEM_SHA
    assert len(identity['demSourceHashes']) == 4
    assert session['png_filename'] == PNG_NAME
    assert session['purpose'] == 'GATE1_TERRAIN_SHADING_STATIC_PROOF'
    assert not session['gpu_probe_ready']
    report('CONTAINER_FROZEN_IDENTITY')
    # Container startup already hashes every admitted asset. Re-read the
    # packaged contracts and renderer bytes here, independent of UI labels.
    source_check = '''import hashlib,json,os
from pathlib import Path
p=Path(os.environ['STATIC_PROOF_BUNDLE']);m=json.loads((p/'manifest.json').read_text())
h=json.loads((p/'height-source.json').read_text());r=json.loads((p/'render-parameters.json').read_text())
assert hashlib.sha256((p/'renderer.mjs').read_bytes()).hexdigest()==%r
assert h['sha256']==%r and h['byteLength']==207360000 and h['dimensions']==[7200,7200]
assert h['CRS']=='EPSG:4326' and h['scale']==1 and h['offset']==0 and h['NoData'] is None
assert h['format']=='little-endian IEEE754 Float32 / GPU R32F'
assert len(h['originals'])==4
assert m['source_identity']['demSourceHashes']==[v['sha256'] for v in h['originals']]
assert r=={'dem':True,'correctedLight':True,'verticalExaggeration':2,'bakedSuppression':0.1,'shadingCorrection':'OUTPUT'}
route=next(v for v in m['routes'] if v['url']==h['url']);a=p/route['file']
assert a.stat().st_size==h['byteLength']
d=hashlib.sha256()
with a.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''): d.update(block)
assert d.hexdigest()==h['sha256']
print(json.dumps({'renderer_source_hash':%r,'dem_hash':d.hexdigest(),'render_parameters':r,'dem_original_hashes':[v['sha256'] for v in h['originals']]}))
''' % (RENDERER_SHA, DEM_SHA, RENDERER_SHA)
    source_result = command(['docker', 'exec', name, 'python', '-c', source_check], timeout=30)
    (evidence / 'container-source-preservation.json').write_text(source_result)
    report('CONTAINER_DEM_D_PARAMETERS_SOURCE_HASH_PRESERVED')
    code, _, body = request('POST', '/api/generate', {}, authenticated)
    assert code == 403 and json.loads(body)['error'] == 'GPU_PROBE_REQUIRED'
    report('CONTAINER_GENERATION_REQUIRES_SUCCESSFUL_GPU_CHECK')
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
    assert headers['Content-Disposition'] == 'attachment; filename="SUEZ_TERRAIN_SHADING_RTX4080S.diagnostic.json"'
    assert diagnostic['capability_result']['result'] == 'FAIL'
    assert set(diagnostic['attempts']) == {'vulkan', 'egl'}
    for record in [diagnostic, *diagnostic['attempts'].values()]:
        assert record['renderer_source_hash'] == RENDERER_SHA
        assert record['software_d_final_hash'] == SOFTWARE_D_SHA
        assert record['dem_hash'] == DEM_SHA
        assert len(record['dem_source_hashes']) == 4
        assert [row['sha256'] for row in record['dem_source_hashes']] == identity['demSourceHashes']
        assert record['scene_hash'] == identity['sceneHash']
        assert record['shader_version'] == identity['shaderVersion']
        assert record['theme_version'] == identity['themeVersion']
        assert record['render_parameters'] == {'dem': True, 'correctedLight': True, 'verticalExaggeration': 2,
                                               'bakedSuppression': 0.1, 'shadingCorrection': 'OUTPUT'}
        assert record['output_resolution'] == [1080, 1920]
        assert record['gl_error'] == 'NOT_RUN' or isinstance(record['gl_error'], int)
    for backend, attempt in diagnostic['attempts'].items():
        assert attempt['backend'] == backend
        assert attempt['error_code'] != 'STATIC_PROOF_FAILED'
        assert attempt['failed_stage']
        assert attempt['environment']['uid'] == 1000
        assert attempt['environment']['directories']['HOME']['path'] == '/home/engine'
        assert all(row['accessible'] for row in attempt['environment']['directories'].values())
        assert attempt['environment']['directories']['XDG_RUNTIME_DIR']['mode'] == '0o700'
        assert attempt['environment']['chromium_real_executable'] == '/usr/bin/chromium'
        assert 'libraries' in attempt['inventory'] and 'devices' in attempt['inventory']
        assert 'egl' in attempt['graphics_runtime'] and 'vulkan' in attempt['graphics_runtime']
        assert 'stderr' in attempt['worker_process'] and 'stdout' in attempt['worker_process']
        assert 'exit_code' in attempt['chromium_process'] and 'signal' in attempt['chromium_process']
        assert 'chromium_stderr' in attempt and 'chromium_stdout' in attempt
        assert [row['name'] for row in attempt['stages']] == ['START', 'ENVIRONMENT', 'GRAPHICS_RUNTIME', 'BROWSER_LAUNCH', 'PAGE_CREATE', 'PAGE_LOAD', 'WEBGL2_CREATE', 'GPU_IDENTITY', 'READPIXELS', 'RESULT']
        assert all(row['result'] != 'PASS' for row in attempt['stages'] if row['name'] == 'RESULT')
    report('CONTAINER_BACKEND_DIAGNOSTICS_AND_BOOTSTRAP_ENVIRONMENT')
    (evidence / 'container-no-gpu.diagnostic.json').write_bytes(body)
    report('CONTAINER_FAILURE_DIAGNOSTIC_DOWNLOAD')
    code, _, body = request('POST', '/api/generate', {}, authenticated)
    assert code == 403 and json.loads(body)['error'] == 'GPU_PROBE_REQUIRED'
    assert not json.loads(request('GET', '/api/session', headers=authenticated)[2])['gpu_probe_ready']
    report('CONTAINER_FAILED_GPU_CHECK_CANNOT_GENERATE')
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
