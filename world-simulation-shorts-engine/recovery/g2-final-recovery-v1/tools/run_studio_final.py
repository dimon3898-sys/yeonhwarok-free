"""One gated authenticated final G2 software DEMO, detached from the browser."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
HERE = Path(__file__).resolve().parents[1]
OLD = HERE.parent / 'g2-renderer-recovery-v1'
spec = importlib.util.spec_from_file_location('_g2_final_actual_service', HERE / 'studio_service.py')
service = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = service
spec.loader.exec_module(service)


def run(private, source_root):
    service.controller_module.require_final_gates()
    pin = json.loads((OLD / 'fixtures/SOURCE_CATALOG_PIN.json').read_bytes())
    actual = hashlib.sha256((source_root / 'INDEX.json').read_bytes()).hexdigest()
    if actual != pin['indexSHA256']:
        raise RuntimeError('G2_FINAL_SERVER_SOURCE_PIN_MISMATCH')
    if (not private.is_absolute() or private.is_relative_to(HERE.parents[2])
            or any(part.startswith(('source-studio-private-', 'g2-recovery-studio-private-'))
                   for part in private.parts)):
        raise RuntimeError('G2_FINAL_FRESH_PRIVATE_ROOT_REQUIRED')
    private.mkdir(mode=0o700, exist_ok=False)
    state = private / 'state'
    state.mkdir(mode=0o700)
    owner = private / 'owner-code'
    owner.write_text(secrets.token_urlsafe(32))
    owner.chmod(0o600)
    exports = HERE / 'captures'
    exports.mkdir(mode=0o700, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    options = dict(state_root=state, owner_file=owner, export_root=exports, port=port,
        # Provenance selector required by the preserved controller. Execution
        # below is a source checkout, not a claim that this OCI image was run.
        image_digest='sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5',
        source_root=source_root, expected_index_sha256=actual, allow_software_source_review=True)
    app = service.local_application(**options)
    http = service.server.ThreadingHTTPServer(('127.0.0.1', port), service.server.make_handler(app))
    threading.Thread(target=http.serve_forever, daemon=True).start()
    try:
        subprocess.run(['node', str(HERE.parent / 'studio-integration-gates-v1/tools/mobile_client.mjs'),
            f'http://127.0.0.1:{port}', str(private), str(OLD / 'fixtures/DEMO_SOURCE_SCENE.json')],
            check=True, timeout=180, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        mobile = json.loads((private / 'MOBILE_HTTP_START.json').read_bytes())
        job_id = mobile['jobId']
        http.shutdown()
        http.server_close()
        app2 = service.local_application(**options)
        reconnect = app2.controller.start(mobile['submissionId'], 'g2-final-reconnect-20261022', consent=True)
        if reconnect['jobId'] != job_id:
            raise RuntimeError('G2_FINAL_DUPLICATE_JOB_ON_RECONNECT')
        last = None
        for _ in range(190):
            status = app2.controller.status(job_id)
            current = (status['state'], status.get('processedFrames'))
            if current != last:
                print(json.dumps(status), flush=True)
                last = current
            if status['state'] in {'COMPLETED', 'FAILED', 'INTERRUPTED'}:
                break
            time.sleep(5)
        report = {**mobile, 'finalState': status, 'controllerRestartDuplicateJobId': reconnect['jobId'],
            'httpServerStoppedDuringRender': True, 'sourceIndexSHA256': actual,
            'classification': 'SYNTHETIC_DEMO_NOT_HISTORICAL_G3', 'g1ReRendered': False,
            'actualRuntime': 'SOURCE_CHECKOUT_NOT_OCI_IMAGE', 'nvidiaVerified': False,
            'deploymentPerformed': False, 'paidGpuExecuted': False, 'userApproved': False}
        for destination in [HERE / 'reports' / ('STUDIO_FINAL_' + job_id + '.json'),
                            HERE / 'reports/STUDIO_FINAL_EXECUTION.json']:
            with destination.open('x') as output:
                json.dump(report, output, indent=2)
                output.write('\n')
        if status['state'] != 'COMPLETED':
            raise RuntimeError('G2_FINAL_STUDIO_JOB_NOT_COMPLETED')
    finally:
        http.shutdown()
        http.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    run(args.private_root, args.source_root)
