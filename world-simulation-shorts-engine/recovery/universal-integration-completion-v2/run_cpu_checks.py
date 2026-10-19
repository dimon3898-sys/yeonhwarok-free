"""Focused completion CPU checks. This runner never calls a render or Docker."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
TESTS = ['test_contract_completion.py', 'test_history_admission.py', 'test_feature_ledger.py',
         'test_revision_bridge.py', 'test_studio_completion_path.py', 'test_completion_package.py',
         'test_image_proof.py', 'test_history_source_binding.py', 'test_camera_extension.mjs', 'test_frontier_extension.mjs',
         'test_event_flow_binding.mjs', 'test_runtime_binding.mjs']


def run(only=None):
    destination = HERE / 'reports/CPU_TEST_RESULTS.json'
    previous = json.loads(destination.read_text()) if only and destination.exists() else None
    known = {row['test']: row for row in (previous or {}).get('suites', [])}
    suites = []
    with tempfile.TemporaryDirectory(prefix='completion-owned-cpu-', dir=HERE.parents[2]) as temp:
        os.chmod(temp, 0o700)
        environment = dict(os.environ, TMPDIR=temp, PYTHONDONTWRITEBYTECODE='1')
        for name in TESTS:
            file = HERE / 'tests' / name
            source_hash = hashlib.sha256(file.read_bytes()).hexdigest()
            if only and name not in only:
                row = known[name]
                if row['testSourceSHA256'] != source_hash or row['status'] != 'PASS':
                    raise RuntimeError('COMPLETION_UNCHANGED_PASS_RECEIPT_REQUIRED')
                suites.append({**row, 'reusedUnchangedResult': True})
                continue
            command = [sys.executable, '-B', str(file)] if file.suffix == '.py' else ['node', '--test', str(file)]
            start = time.monotonic()
            result = subprocess.run(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=180, cwd=HERE.parents[2])
            raw = result.stdout
            match = re.search(r'Ran (\d+) tests?', raw) if file.suffix == '.py' else re.search(r'(?:ℹ|#) tests (\d+)', raw)
            count = int(match.group(1)) if match else 0
            skipped = 0
            for pattern in (r'skipped=(\d+)', r'(?:ℹ|#) skipped (\d+)'):
                found = re.search(pattern, raw)
                if found: skipped = int(found.group(1))
            status = 'PASS' if result.returncode == 0 and count > 0 and skipped == 0 else 'FAIL'
            row = {'test': name, 'status': status, 'exitCode': result.returncode, 'executed': count,
                   'skipped': skipped, 'elapsedSeconds': round(time.monotonic()-start, 3),
                   'testSourceSHA256': source_hash, 'outputSHA256': hashlib.sha256(raw.encode()).hexdigest()}
            suites.append(row)
            print(json.dumps(row), flush=True)
            if status != 'PASS':
                (HERE / 'reports/CPU_FAILURE.txt').write_text(raw)
                break
    value = {'schema': 'WORLD_ENGINE_COMPLETION_CPU_RECEIPT_V1',
             'status': 'PASS' if len(suites) == len(TESTS) and all(row['status']=='PASS' for row in suites) else 'FAIL',
             'recordedAtKST': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
             'executed': sum(row['executed'] for row in suites), 'skipped': sum(row['skipped'] for row in suites),
             'suites': suites, 'gpuExecuted': False, 'swiftShaderDrawExecuted': False,
             'videoRendered': False, 'paidWorkExecuted': False, 'existing132SuiteRepeated': False,
             'evidenceScope': 'Actual frozen parser/CPU math, source selection, real localhost HTTP security, and explicitly labelled no-GPU factory/worker spies.'}
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    return 0 if value['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(run(set(sys.argv[2:]) if len(sys.argv)>1 and sys.argv[1]=='--only' else None))
