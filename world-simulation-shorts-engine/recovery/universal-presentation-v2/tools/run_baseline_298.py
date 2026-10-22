"""Actually rerun all 298 original tests; never write their preserved reports."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
OLD = ROOT / 'world-simulation-shorts-engine/recovery/universal-data-pipeline-v1'
PREFIX = OLD.relative_to(ROOT).as_posix() + '/'


def run(attempt):
    if not re.fullmatch('[a-zA-Z0-9_-]+', attempt):
        raise ValueError('REGRESSION_ATTEMPT_ID_REQUIRED')
    target = HERE / 'reports/regressions' / attempt
    target.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('_up2_preserved_143_runner', OLD / 'tools/run_g2_regressions.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    old.HERE = HERE
    # Old ROOT already resolves to this new worktree. Keep every original test
    # file and command unchanged; only the runner's report destination relocates.
    code = old.run(attempt + '-original143')
    original = HERE / 'reports/regressions' / (attempt + '-original143') / 'RESULTS.json'
    prior = json.loads(original.read_bytes())
    report = {'schema': 'WORLD_ENGINE_UP2_BASELINE_298_REGRESSIONS_V1',
              'baselineCommit': 'b0d013832ee38571f9d3dfe685ce63f7083ba90f',
              'priorResultsReused': False, 'originalTestsModified': False,
              'originalReportsWritten': False, 'paidExecution': False,
              'nvidiaVerified': False, 'visualQualityApproved': False,
              'preserved143': {'report': original.relative_to(HERE).as_posix(),
                               'sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                               'status': prior['status'], 'tests': prior.get('totalTests'), 'exitCode': code},
              'results': []}
    if code or prior['status'] != 'PASS' or prior.get('totalTests') != 143:
        report.update(status='FAIL', failure='ORIGINAL_143_FAILED')
        (target / 'RESULTS.json').write_text(json.dumps(report, indent=2) + '\n')
        return 1
    suites = [
        ('PROMPT109', ['node', PREFIX + 'tests/test_prompt_pipeline.mjs'], 109),
        ('JSON_SCHEMA14', ['python', '-B', PREFIX + 'tests/test_prompt_schema.py'], 14),
        ('STUDIO22', ['python', '-B', '-m', 'unittest', 'discover', '-s', PREFIX + 'tests', '-p', 'test_studio_adapter.py', '-v'], 22),
        ('CAPTURE10', ['node', PREFIX + 'tests/test_capture_generic.mjs'], 10),
    ]
    for name, command, expected in suites:
        started = time.monotonic()
        value = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                               capture_output=True, text=True, timeout=240)
        (target / (name + '.stdout.txt')).write_text(value.stdout)
        (target / (name + '.stderr.txt')).write_text(value.stderr)
        combined = value.stdout + '\n' + value.stderr
        match = re.search(r'Ran (\d+) tests?', combined) if command[0] == 'python' else re.search(r'(?:ℹ|#) tests (\d+)', combined)
        count = int(match[1]) if match else None
        skipped_match = re.search(r'skipped(?:=| )(\d+)', combined)
        skipped = int(skipped_match[1]) if skipped_match else 0
        if count is None and command[0] == 'node':
            for line in value.stdout.splitlines():
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if isinstance(data, dict) and data.get('status') == 'PASS' and type(data.get('tests')) is int:
                    count = data['tests']
                    skipped = data.get('skipped', 0)
        good = value.returncode == 0 and count == expected and skipped == 0
        row = {'id': name, 'command': command, 'tests': count, 'expected': expected,
               'exitCode': value.returncode, 'skipped': skipped, 'status': 'PASS' if good else 'FAIL',
               'elapsedSeconds': round(time.monotonic() - started, 3),
               'stdoutFile': name + '.stdout.txt', 'stderrFile': name + '.stderr.txt'}
        report['results'].append(row)
        print(json.dumps(row), flush=True)
        if not good:
            report.update(status='FAIL', failure='BASELINE_298_FAILED_' + name)
            break
    else:
        report.update(status='PASS', totalTests=143 + sum(item['tests'] for item in report['results']),
                      previousPipelineTests=155, fail=0, skipped=0)
    (target / 'RESULTS.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' and report.get('totalTests') == 298 else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    raise SystemExit(run(parser.parse_args().attempt))
