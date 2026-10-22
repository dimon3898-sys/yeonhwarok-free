"""Actually execute the original 503 checks with fresh private test outputs.

Every preserved test file remains byte-identical. Only temporary output roots
are relocated by explicit test-process wrappers. No old runner is invoked because
its hardcoded report/cache destinations would write into preserved namespaces.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
PRIVATE = Path('/workspace/reference-director-v1-private-20261022')
PREFIX = 'world-simulation-shorts-engine/recovery/'


def suite_list():
    old, prev, current, udp, up2 = (PREFIX + x + '/' for x in (
        'universal-source-pipeline-v2', 'g2-renderer-recovery-v1', 'g2-final-recovery-v1',
        'universal-data-pipeline-v1', 'universal-presentation-v2'))
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
               for f in sorted((ROOT/current/'tests').glob('test_*.mjs'))]
    suites += [
        ('PROMPT109', ['node', udp+'tests/test_prompt_pipeline.mjs'], 109),
        ('JSON_SCHEMA14', ['python', '-B', udp+'tests/test_prompt_schema.py'], 14),
        ('STUDIO22', ['python', '-B', '-m', 'unittest', 'discover', '-s', udp+'tests', '-p', 'test_studio_adapter.py', '-v'], 22),
        ('CAPTURE10', ['node', udp+'tests/test_capture_generic.mjs'], 10),
        ('NL70', ['node', '--test-reporter=tap', up2+'tests/test_natural_language.mjs'], 70),
        ('PRESENTATION_SCHEMA15', ['python', '-B', up2+'tests/test_presentation_schema.py'], 15),
        ('REGION44', ['node', up2+'tests/region_source.test.mjs'], 44),
        ('PRESENTATION_PLAN23', ['node', up2+'tests/test_presentation_plan.mjs'], 23),
        ('PRESENTATION_PREPARATION17', ['node', up2+'tests/test_presentation_preparation.mjs'], 17),
        ('STUDIO_PRESENTATION36', ['python', '-B', '-m', 'unittest', 'discover', '-s', up2+'tests', '-p', 'test_studio_presentation.py', '-v'], 36),
    ]
    return suites


def run(attempt, only=None, resume_from=None):
    if not re.fullmatch('[A-Za-z0-9_-]+', attempt):
        raise ValueError('UNIQUE_ATTEMPT_REQUIRED')
    target = HERE/'reports/baseline-503'/attempt
    target.mkdir(parents=True, exist_ok=False)
    private = PRIVATE/'baseline-503'/attempt
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(private),
           'REFERENCE_DIRECTOR_TEST_PRIVATE_ROOT': str(private)}
    env.pop('G2_GENERIC_PROBE_ROOT', None)
    report = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_ACTUAL_BASELINE_503_V1',
              'baselineCommit': '82854af429d09aebb4b31c2f168e2f0ddc9560c9',
              'priorResultsReused': False, 'testSourceFilesModified': False,
              'assertionsModified': False, 'oldReportsWritten': False,
              'temporaryOutputRelocationOnly': True, 'privateRoot': str(private),
              'paidGpuExecuted': False, 'paidApiUsed': False,
              'nvidiaVerified': False, 'visualQualityApproved': False, 'results': []}
    previous = None
    if resume_from:
        if only or not re.fullmatch('[A-Za-z0-9_-]+', resume_from):
            raise ValueError('VALID_PRIOR_ATTEMPT_REQUIRED')
        previous_path = HERE/'reports/baseline-503'/resume_from/'RESULTS.json'
        previous = json.loads(previous_path.read_bytes())
        if previous['status'] != 'FAIL' or previous['results'][-1]['status'] != 'FAIL':
            raise ValueError('ONLY_FAILED_SUITE_CAN_BE_RESUMED')
        successful = previous['results'][:-1]
        if any(row['status'] != 'PASS' for row in successful):
            raise ValueError('PREVIOUS_SUCCESSFUL_PREFIX_REQUIRED')
        report['reusedCurrentExecutionPassedSuites'] = successful
        report['priorAttempt'] = {'path': previous_path.relative_to(HERE).as_posix(),
                                 'sha256': hashlib.sha256(previous_path.read_bytes()).hexdigest(),
                                 'failedSuite': previous['results'][-1]['id'],
                                 'note': 'Do not repeat successful suites; rerun failure and continue.'}
        offset = next(i for i,s in enumerate(suite_list()) if s[0] == previous['results'][-1]['id'])
        selected = suite_list()[offset:]
    else:
        selected = [s for s in suite_list() if only is None or s[0] == only]
    if not selected:
        raise ValueError('UNKNOWN_SUITE')
    for name, original, expected in selected:
        command = (['python', '-B', str(HERE/'tools/isolated_test_python.py'), *original[2:]]
                   if original[0] == 'python' else
                   ['node', '--import', str(HERE/'tools/isolated_test_node.mjs'), *original[1:]])
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b'').decode() if isinstance(error.stdout, bytes) else error.stdout or ''
            stderr = (error.stderr or b'').decode() if isinstance(error.stderr, bytes) else error.stderr or ''
            code = 124
        (target/(name+'.stdout.txt')).write_text(stdout)
        (target/(name+'.stderr.txt')).write_text(stderr)
        combined = stdout+'\n'+stderr
        match = re.search(r'Ran (\d+) tests?', combined) if original[0]=='python' else re.search(r'(?:ℹ|#) tests (\d+)', combined)
        count = int(match[1]) if match else None
        skipped_match = re.search(r'skipped(?:=| )(\d+)', combined)
        skipped = int(skipped_match[1]) if skipped_match else 0
        if count is None and original[0]=='node':
            for line in stdout.splitlines():
                try: value = json.loads(line)
                except ValueError: continue
                if isinstance(value, dict) and value.get('status')=='PASS' and type(value.get('tests')) is int:
                    count, skipped = value['tests'], value.get('skipped', 0)
        good = code == 0 and count is not None and skipped == 0 and (expected is None or count == expected)
        row = {'id': name, 'originalCommand': original, 'executedCommand': command,
               'tests': count, 'expected': expected, 'exitCode': code, 'skipped': skipped,
               'status': 'PASS' if good else 'FAIL', 'elapsedSeconds': round(time.monotonic()-started, 3),
               'stdoutFile': name+'.stdout.txt', 'stderrFile': name+'.stderr.txt'}
        report['results'].append(row)
        print(json.dumps(row), flush=True)
        if not good:
            report.update(status='FAIL', failure=name)
            break
    else:
        total = sum(row['tests'] for row in report['results']) + sum(row['tests'] for row in report.get('reusedCurrentExecutionPassedSuites', []))
        report.update(status='PASS' if only or total==503 else 'FAIL', totalTests=total,
                      skipped=0, fail=0, expectedTotal=503 if only is None else selected[0][2])
    (target/'RESULTS.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--only')
    parser.add_argument('--resume-from')
    args=parser.parse_args()
    raise SystemExit(run(args.attempt, args.only, args.resume_from))
