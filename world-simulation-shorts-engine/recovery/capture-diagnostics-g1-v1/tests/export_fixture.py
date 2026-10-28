"""CPU-only private fixtures. Never reads a user's receipt or credentials."""
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2] / 'codex-to-gcube-handoff-v1/controller'
spec = importlib.util.spec_from_file_location('safe_export', ROOT / 'safe_capture_export.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)

def write_private(file, value):
    file.write_text(json.dumps(value) + '\n')
    file.chmod(0o600)

def export_fixture(job, destination, receipt=True):
    job, destination = Path(job), Path(destination)
    write_private(job / 'LEASE_SUPERVISOR_RESULT.json', {'cleanupVerified': True, 'reason': 'HANDOFF_CAPTURE_PROCESS_FAILED'})
    write_private(job / 'FIRST_CAPTURE_FAILURE.json', {'code': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'stage': 'RENDER_RUNTIME'})
    if receipt:
        checkpoint = json.loads((job / 'capture/CAPTURE_OPERATION_CHECKPOINT.json').read_text())
        write_private(job / 'capture/CAPTURE_RECEIPT.json', {'renderedFrames': 0, 'nvidiaVerified': False,
            'failure': {'code': 'page.evaluate: Error: SYNTHETIC_SECRET_NOT_FOR_EXPORT', 'diagnosticStage': 'PAGE_EVALUATE_FIRST_NATIVE_DRAW'},
            'captureOperations': checkpoint})
    return exporter.export_failure(job, destination)

if __name__ == '__main__':
    result = export_fixture(sys.argv[1], sys.argv[2], receipt='--no-receipt' not in sys.argv)
    print(json.dumps({'sha256': result['sha256'], 'status': 'CPU_ONLY_SAFE_EXPORT'}))
