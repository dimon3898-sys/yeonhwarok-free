"""Three serial, gated real Studio prompt-to-video jobs on free software rendering.

The preserved mobile browser client exercises real login, Origin, CSRF,
preflight, submission, explicit start and duplicate touch. The browser and HTTP
server then close while the detached worker continues. No production GPU API,
image deployment or automatically restarted claim is involved.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('_udp_actual_studio_service', HERE / 'studio_adapter.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def require_gates(file, expected):
    raw = file.read_bytes()
    if file.is_symlink() or hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('UDP_A_E_GATE_HASH_MISMATCH')
    data = json.loads(raw)
    if (data.get('schema') != 'WORLD_ENGINE_UDP_PHASE_GATES_V1'
            or data.get('baselineCommit') != 'e39969cbc76a071d34a38440d9551425e6d5e545'
            or data.get('protectionFiles') != 307 or data.get('protectionStatus') != 'PASS'
            or any(data.get('phase' + name, {}).get('status') != 'PASS' for name in 'ABCDE')
            or data.get('paidExecutionAllowed') is not False):
        raise RuntimeError('UDP_A_E_REQUIRED_GATES_NOT_PASSED')
    return data


def run_one(private, request_file, name, *, evidence_registry=None, registry_pin=None):
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,60}', name):
        raise RuntimeError('UDP_DEMO_PUBLIC_NAME_INVALID')
    private.mkdir(mode=0o700, exist_ok=False)
    state = private / 'state'
    state.mkdir(mode=0o700)
    owner = private / 'owner-code'
    with owner.open('x') as file:
        file.write(secrets.token_urlsafe(32))
    owner.chmod(0o600)
    request = json.loads(request_file.read_bytes())
    if request.get('schema') != service.REQUEST_SCHEMA:
        # Explicitly prepare a saved standard prompt as one chosen Scene. Never
        # substitute a fixed fixture or select a successful neighbour silently.
        scenes = request.get('scenes', [])
        if len(scenes) != 1:
            raise RuntimeError('UDP_RUNNER_EXPLICIT_SCENE_REQUEST_REQUIRED')
        request = {'schema': service.REQUEST_SCHEMA, 'prompt': request, 'sceneId': scenes[0]['sceneId']}
    bound_request = private / 'ACTUAL_STUDIO_REQUEST.json'
    bound_request.write_bytes(service.canonical(request))
    bound_request.chmod(0o600)
    exports = private / 'exports'
    exports.mkdir(mode=0o700)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    options = {'state_root': state, 'owner_file': owner, 'export_root': exports, 'port': port,
        'allow_free_data_review': True, 'evidence_registry': evidence_registry,
        'expected_registry_sha256': registry_pin}
    app = service.local_application(**options)
    http = service.server.ThreadingHTTPServer(('127.0.0.1', port), service.server.make_handler(app))
    threading.Thread(target=http.serve_forever, daemon=True).start()
    closed = False
    try:
        client = HERE.parent / 'studio-integration-gates-v1/tools/mobile_client.mjs'
        subprocess.run(['node', str(client), f'http://127.0.0.1:{port}', str(private), str(bound_request)],
            check=True, timeout=180, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        mobile = json.loads((private / 'MOBILE_HTTP_START.json').read_bytes())
        job_id = mobile['jobId']
        http.shutdown(); http.server_close(); closed = True
        # Reconnect creates only a new authenticated-service controller. It does
        # not start a new render or clear the previous claim.
        app2 = service.local_application(**options)
        reconnect = app2.controller.start(mobile['submissionId'], 'udp-reconnected-browser-new-key', consent=True)
        if reconnect['jobId'] != job_id:
            raise RuntimeError('UDP_RECONNECT_DUPLICATE_JOB')
        started = time.monotonic()
        previous = None
        while time.monotonic() - started < 930:
            status = app2.controller.status(job_id)
            summary = (status['state'], status.get('phase'), status.get('processedFrames'))
            if summary != previous:
                print(json.dumps({'name': name, **status}), flush=True)
                previous = summary
            if status['state'] in {'COMPLETED', 'FAILED', 'INTERRUPTED'}:
                break
            time.sleep(3)
        else:
            raise RuntimeError('UDP_STUDIO_POLL_DEADLINE_EXCEEDED')
        report = {**mobile, 'finalState': status, 'controllerRestartDuplicateJobId': reconnect['jobId'],
            'httpServerStoppedDuringRender': True, 'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE',
            'paidGpuExecuted': False, 'paidApiUsed': False, 'nvidiaVerified': False,
            'historicalG3': 'BLOCKED', 'userQualityApproved': False,
            'requestSHA256': hashlib.sha256(bound_request.read_bytes()).hexdigest(),
            'sourceFixtureSHA256': hashlib.sha256(request_file.read_bytes()).hexdigest(),
            'explicitSceneId': request['sceneId'], 'publicName': name}
        report_file = HERE / 'reports' / (name + '_STUDIO_EXECUTION.json')
        with report_file.open('x') as file:
            json.dump(report, file, indent=2); file.write('\n')
        if status['state'] != 'COMPLETED':
            raise RuntimeError('UDP_STUDIO_DEMO_NOT_COMPLETED')
        result = app2.controller.result(job_id)
        public = HERE / 'public-review'
        public.mkdir(exist_ok=True)
        capture = exports / job_id
        files = [(capture / 'VIDEO.mp4', public / (name + '.mp4')),
                 (capture / 'CAPTURE_RECEIPT.json', public / (name + '_CAPTURE_RECEIPT.json')),
                 (capture / 'FRAME_EVIDENCE.json', public / (name + '_FRAME_EVIDENCE.json'))]
        for png in sorted(capture.glob('*.png')):
            files.append((png, public / (name + '_' + png.name)))
        for source, destination in files:
            if source.is_symlink() or not source.is_file():
                raise RuntimeError('UDP_STUDIO_REQUIRED_OUTPUT_MISSING')
            with source.open('rb') as input_file, destination.open('xb') as output_file:
                shutil.copyfileobj(input_file, output_file)
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
                raise RuntimeError('UDP_STUDIO_PUBLIC_COPY_HASH_MISMATCH')
        return {'name': name, 'jobId': job_id, 'state': status['state'], 'result': result,
            'actualAuthenticatedStudio': True, 'requestSHA256': report['requestSHA256'],
            'outputs': [p.name for _, p in files], 'executionReport': str(report_file.relative_to(HERE))}
    finally:
        if not closed:
            http.shutdown(); http.server_close()


def run(args):
    require_gates(args.gate_file, args.expected_gate_sha256)
    private = args.private_root
    if (not private.is_absolute() or private.is_relative_to(REPO)
            or any(p.is_symlink() for p in (private, *private.parents)) or len(args.request) != len(args.name)
            or len(args.request) < 3):
        raise RuntimeError('UDP_FRESH_PRIVATE_ROOT_AND_THREE_PROMPTS_REQUIRED')
    private.mkdir(mode=0o700, exist_ok=False)
    results = []
    for index, (request, name) in enumerate(zip(args.request, args.name)):
        # Serial jobs make the resource and timeout bound explicit; never batch
        # three GPU contexts or render unrequested neighbouring scenes.
        results.append(run_one(private / ('case-' + str(index + 1)), request, name,
            evidence_registry=args.evidence_registry, registry_pin=args.expected_registry_sha256))
    report = {'schema': 'WORLD_ENGINE_UDP_REAL_STUDIO_DEMOS_V1', 'jobs': results,
        'gateSHA256': args.expected_gate_sha256, 'softwareOnly': True, 'nvidiaVerified': False,
        'paidExecuted': False, 'qualityStatus': 'QUALITY_REVIEW_REQUIRED', 'historicalG3': 'BLOCKED'}
    with (HERE / 'reports/STUDIO_DEMOS.json').open('x') as file:
        json.dump(report, file, indent=2); file.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--gate-file', type=Path, required=True)
    parser.add_argument('--expected-gate-sha256', required=True)
    parser.add_argument('--request', type=Path, action='append', required=True)
    parser.add_argument('--name', action='append', required=True)
    parser.add_argument('--evidence-registry', type=Path)
    parser.add_argument('--expected-registry-sha256')
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2))
