"""Execute all original 143 G2 test cases unchanged; logs only in the new namespace.

The original runner is deliberately not invoked because it writes a protected
old report. Its exact test commands, strict no-SKIP rule and ordering are reused.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
PREFIX = 'world-simulation-shorts-engine/recovery/'


def run(attempt):
    if not re.fullmatch('[a-zA-Z0-9_-]+', attempt):
        raise ValueError('REGRESSION_ATTEMPT_ID_INVALID')
    target = HERE / 'reports/regressions' / attempt
    target.mkdir(parents=True, exist_ok=False)
    old, prev, current = (PREFIX + x + '/' for x in ('universal-source-pipeline-v2', 'g2-renderer-recovery-v1', 'g2-final-recovery-v1'))
    suites = [
        ('EXISTING_35', ['python', '-B', '-m', 'unittest', 'discover', '-s', old+'tests', '-p', 'test_*.py', '-v'], 35),
        ('EXISTING_NATIVE_8', ['node', old+'tests/test_native_preparation.mjs'], 8),
        ('EXISTING_CAMERA_6', ['node', old+'tests/test_camera_numerics.mjs'], 6),
        ('EXISTING_GEOMETRY_3', ['node', old+'tests/test_source_geometry_contract.mjs'], 3),
        ('PRIOR_RECOVERY_37', ['python', '-B', '-m', 'unittest', 'discover', '-s', prev+'tests', '-p', 'test_*.py', '-v'], 37),
        ('PRIOR_CAPTURE_8', ['node', prev+'tests/test_capture_recovery.mjs'], 8),
        ('PRIOR_PLAN_4', ['node', prev+'tests/test_prepare_recovery_plan.mjs'], 4),
        ('FINAL_PYTHON', ['python', '-B', '-m', 'unittest', 'discover', '-s', current+'tests', '-p', 'test_*.py', '-v'], None),
    ]
    suites += [('FINAL_JS_'+f.stem, ['node', str(f.relative_to(ROOT))], None)
               for f in sorted((ROOT / current / 'tests').glob('test_*.mjs'))]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'G2_GENERIC_PROBE_ROOT': '/workspace/universal-data-pipeline-v1-private-20261022/g2-generic-probes'}
    results = []
    report = {'schema': 'WORLD_ENGINE_UDP_ORIGINAL_143_REGRESSIONS_V1', 'status': 'IN_PROGRESS',
              'originalRunner': current+'tools/run_cpu_regressions.py', 'originalTestsModified': False,
              'preservedOldReportWritten': False, 'priorRunResultsReused': False,
              'baselineCommit': 'e39969cbc76a071d34a38440d9551425e6d5e545',
              'softwareOnly': True, 'nvidiaVerified': False, 'visualQualityApproved': False,
              'environmentOverrides': {'PYTHONDONTWRITEBYTECODE': '1', 'G2_GENERIC_PROBE_ROOT': env['G2_GENERIC_PROBE_ROOT']},
              'results': results}
    for name, command, expected in suites:
        started = time.monotonic()
        p = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=240)
        stdout, stderr = p.stdout, p.stderr
        (target / (name+'.stdout.txt')).write_text(stdout)
        (target / (name+'.stderr.txt')).write_text(stderr)
        combined = stdout+'\n'+stderr
        match = re.search(r'Ran (\d+) tests?', combined) if command[0] == 'python' else re.search(r'(?:ℹ|#) tests (\d+)', combined)
        count = int(match[1]) if match else None
        skipped_match = re.search(r'skipped(?:=| )(\d+)', combined)
        skipped = int(skipped_match[1]) if skipped_match else 0
        if count is None and command[0] == 'node':
            summaries = []
            for line in stdout.splitlines():
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict) and {'status', 'tests', 'skipped'} <= value.keys():
                    summaries.append(value)
            if len(summaries) == 1 and summaries[0]['status'] == 'PASS' and type(summaries[0]['tests']) is int and summaries[0]['tests'] > 0:
                count, skipped = summaries[0]['tests'], summaries[0]['skipped']
        good = p.returncode == 0 and count is not None and skipped == 0 and (expected is None or count == expected)
        row = {'id': name, 'command': command, 'elapsedSeconds': round(time.monotonic()-started, 3),
               'exitCode': p.returncode, 'tests': count, 'expected': expected, 'skipped': skipped,
               'status': 'PASS' if good else 'FAIL', 'stdoutFile': name+'.stdout.txt', 'stderrFile': name+'.stderr.txt'}
        results.append(row)
        print(json.dumps(row), flush=True)
        if not good:
            report.update(status='FAIL', failure='ORIGINAL_G2_REGRESSION_FAILED_'+name)
            break
    else:
        total = sum(r['tests'] for r in results)
        report.update(status='PASS' if total == 143 else 'FAIL', totalTests=total,
                      preserved101=sum(r['tests'] for r in results[:7]), additional42=sum(r['tests'] for r in results[7:]), allSkipped=0)
    (target / 'RESULTS.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    raise SystemExit(run(parser.parse_args().attempt))
