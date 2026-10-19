"""Focused new CPU suites only; retained completion157 result is never rerun."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
TESTS = ['test_package.py', 'test_data_readiness.py', 'test_ledger.py', 'test_preview_contract.py',
         'test_preview_audio.py', 'test_studio_overnight.py', 'test_visual_extensions.mjs',
         'test_preview_capture.mjs', 'test_free_preview_runner.mjs', 'test_runtime_binding.mjs',
         'test_runtime_authority.py', 'test_source_extension.py']


def main(only=None):
    results = []
    previous_path = ROOT / 'reports/CPU_TEST_RESULTS.json'
    previous = {row['test']: row for row in json.loads(previous_path.read_text())['suites']} if only else {}
    for name in TESTS:
        path = ROOT / 'tests' / name
        if only and name not in only:
            row = previous[name]
            if row['status'] != 'PASS' or row['testSHA256'] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise RuntimeError('OVERNIGHT_UNCHANGED_CPU_RECEIPT_REQUIRED:' + name)
            results.append({**row, 'reusedUnchangedResult': True})
            continue
        cmd = [sys.executable, '-B', str(path)] if path.suffix == '.py' else ['node', str(path)]
        started = time.monotonic()
        run = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True, timeout=180)
        output = run.stdout + run.stderr
        count = re.search(r'Ran (\d+) tests?', output) if path.suffix == '.py' else re.search(r'(?:ℹ|#) tests (\d+)', output)
        executed = int(count.group(1)) if count else 0
        skipped = re.search(r'skipped=(\d+)|(?:ℹ|#) skipped (\d+)', output)
        skips = int(next(x for x in skipped.groups() if x is not None)) if skipped else 0
        result = {'test': name, 'status': 'PASS' if run.returncode == 0 and executed and not skips else 'FAIL',
            'exitCode': run.returncode, 'executed': executed, 'skipped': skips,
            'elapsedSeconds': round(time.monotonic() - started, 3),
            'testSHA256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'outputSHA256': hashlib.sha256(output.encode()).hexdigest()}
        results.append(result)
        print(json.dumps(result), flush=True)
        if result['status'] != 'PASS':
            (ROOT / 'reports/CPU_FAILURE.txt').write_text(output)
            break
    report = {'schema': 'WORLD_ENGINE_OVERNIGHT_CPU_RESULTS_V3',
        'status': 'PASS' if len(results) == len(TESTS) and all(x['status'] == 'PASS' for x in results) else 'FAIL',
        'executed': sum(x['executed'] for x in results), 'skipped': sum(x['skipped'] for x in results),
        'suites': results, 'existingCompletion157Repeated': False, 'gpuExecuted': False,
        'paidWorkExecuted': False, 'CPUTraceIsRenderedFrameEvidence': False}
    (ROOT / 'reports/CPU_TEST_RESULTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main(set(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == '--only' else None))
