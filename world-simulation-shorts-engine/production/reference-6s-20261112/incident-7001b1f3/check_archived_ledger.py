"""New admission regression using saved CPU bytes; never render or encode."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2]
WORKER = ENGINE / 'recovery/codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
WORKER_SHA = 'd5bf03d4b79d70411c02d542bbebd08d9df0463636f558f02ee271c259b6b3d9'
LEDGER_SHA = '8750c66d0ec1b1d1ae85b60e37fcfa128c09d4f0066027217d2dfe4d278e1841'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

def main(archive, result):
    found = list(archive.rglob('FRAME_EVIDENCE.json'))
    assert len(found) == 1, 'EXACT_ARCHIVED_LEDGER_REQUIRED'
    source = found[0]
    raw = source.read_bytes()
    assert sha(raw) == LEDGER_SHA, 'ARCHIVED_LEDGER_CHANGED'
    # The original artifact puts the ledger under workspace/ and its receipt
    # under repository evidence. Reuse the already committed exact receipt.
    receipt = json.loads((HERE.parent / 'cpu-continuity-a1/CAPTURE_RECEIPT.json').read_bytes())
    assert receipt['frameEvidence'] == {'file': source.name, 'sha256': LEDGER_SHA}
    assert receipt['sourceInputSHA256'] == '4525c72c09c2563dd71153a4fdae5f22d400035a875df771eec98d4d79d9be45'
    assert receipt['totalFrames'] == receipt['renderedFrames'] == 180
    assert receipt['softwareOnly'] is True and receipt['nvidiaVerified'] is False
    assert sha(WORKER.read_bytes()) == WORKER_SHA, 'REUSED_READER_CHANGED'
    prior = json.loads((ENGINE / 'production/capture-json-size-fix-v13/evidence/CPU_RESULT.json').read_bytes())
    assert prior['status'] == 'PASS' and prior['uniqueTests'] == 10
    spec = importlib.util.spec_from_file_location('incident_existing_cache', ENGINE / 'recovery/universal-auto-video-v2/cache.py')
    cache = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cache)
    assert cache.MAX_JSON == 33554432
    assert cache.MAX_JSON < len(raw) <= 180 * 2 * 1024**2, 'ARCHIVED_REGRESSION_SIZE_REQUIRED'
    tree = ast.parse(WORKER.read_text())
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_read_frame_evidence')
    caller = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_validate_capture')
    calls = [n for n in ast.walk(caller) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_read_frame_evidence']
    assert len(calls) == 1 and ast.unparse(calls[0]) == "_read_frame_evidence(directory, receipt.get('frameEvidence'), total_frames)"
    scope = {'os': os, 're': re, 'json': json, 'sha': sha, 'cache': lambda: cache}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(WORKER), 'exec'), scope)
    with tempfile.TemporaryDirectory(prefix='incident-ledger-') as temp:
        private = Path(temp)
        target = private / source.name
        shutil.copyfile(source, target)
        target.chmod(0o600)
        with cache.PrivateTree(private) as directory:
            try:
                directory.json(source.name)
            except cache.CacheError as error:
                assert str(error) == 'JSON_SIZE_INVALID'
            else:
                raise AssertionError('BASELINE_DID_NOT_REPRODUCE')
            parsed = scope['_read_frame_evidence'](directory, receipt['frameEvidence'], 180)
        assert parsed == json.loads(raw), 'FRAME_LEDGER_CHANGED'
        assert len(parsed['frames']) == 180
        assert sha(target.read_bytes()) == LEDGER_SHA
    value = {'status': 'PASS', 'scope': 'NEW_ARCHIVED_REFERENCE180_POST_CAPTURE_ADMISSION',
             'sourceRunId': 43354123053, 'sourceArtifactId': 14005922020,
             'archivedCPUFrameLedgerBytes': len(raw), 'ledgerSHA256': LEDGER_SHA,
             'genericLimitBytes': cache.MAX_JSON, 'frameLedgerLimitBytes': 377487360,
             'baselineError': 'JSON_SIZE_INVALID', 'restoredReaderRoundTrip': 'IDENTICAL',
             'productionCallerBinding': 'PASS', 'reusedWorkerSHA256': WORKER_SHA,
             'oldSecurityTestsReused': 10, 'oldPassReruns': 0,
             'rendererExecutions': 0, 'mediaEncodes': 0, 'GPUExecutions': 0,
             'actualFailedGPUFileBytes': None, 'actualFailedGPUFilename': None,
             'actualFailedMP4Recovered': False}
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value))

if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
