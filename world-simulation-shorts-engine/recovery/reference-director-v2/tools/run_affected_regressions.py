"""Run unchanged, directly adjacent contracts after the authorized renderer edit.

This is not the full historical503 test rerun, and not a native pixel test.
Only new private/report paths are written. Original test assertions are unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
ORIGINAL_RENDERER_SHA = 'e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38'
SUITES = [
    ('PRESERVED_CAMERA_V5_21', 'world-simulation-shorts-engine/tests/camera_director_v5.test.mjs', 21,
     'Preserved minimum context, canonical portrait aspect, closest-stop and admission ownership'),
    ('PRESERVED_REFERENCE_BOUNDS_7', 'world-simulation-shorts-engine/tests/reference_camera_adapter_v1.test.mjs', 7,
     'Preserved deterministic bounds track, fixed admitted endpoint and locked-state truth'),
    ('PRESERVED_VISUAL_DETAIL_ADMISSION_17', 'world-simulation-shorts-engine/tests/visual_detail_admission_v1.test.mjs', 17,
     'Preserved independent source-detail/readability admission, not an opt-in bypass'),
    ('PRESERVED_PRESENTATION_PLAN_23', 'world-simulation-shorts-engine/recovery/universal-presentation-v2/tests/test_presentation_plan.mjs', 23,
     'Existing presentation selection, projection round-trip, source viewport and moving-admission contract'),
]


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def run(attempt):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', attempt):
        raise RuntimeError('R2_SAFE_TEST_ATTEMPT_REQUIRED')
    baseline = json.loads((HERE / 'reports/PROTECTION_BASELINE.json').read_bytes())
    expected = {row['path']: row['sha256'] for row in baseline['trackedFiles']}
    renderer_sha = sha(ROOT / 'world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs')
    if renderer_sha == ORIGINAL_RENDERER_SHA:
        raise RuntimeError('R2_AFTER_EDIT_REGRESSION_REQUIRES_ACTUAL_AUTHORIZED_RENDERER_CHANGE')
    report_dir = HERE / 'reports/affected-regressions' / attempt
    report_dir.mkdir(parents=True, exist_ok=False)
    private = Path('/workspace/reference-director-v2-private-20261022/affected-regressions') / attempt
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(private)}
    rows = []
    for name, file, count, reason in SUITES:
        if sha(ROOT / file) != expected[file]:
            raise RuntimeError('R2_ORIGINAL_TEST_SOURCE_CHANGED:' + file)
        command = ['node', '--test', '--test-isolation=none', '--test-reporter=tap', file]
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        (report_dir / (name + '.stdout.tap')).write_text(result.stdout)
        (report_dir / (name + '.stderr.txt')).write_text(result.stderr)
        def metric(key):
            match = re.search(r'^# ' + key + r' (\d+)\s*$', result.stdout, re.M)
            return int(match[1]) if match else None
        tests, passed, failed, skipped = (metric(key) for key in ('tests', 'pass', 'fail', 'skipped'))
        good = result.returncode == 0 and tests == passed == count and failed == skipped == 0
        rows.append({'suite': name, 'testSource': file, 'testSourceSHA256': expected[file],
            'selectionReason': reason, 'command': command, 'exitCode': result.returncode,
            'expectedCount': count, 'tests': tests, 'pass': passed, 'fail': failed, 'skip': skipped,
            'status': 'PASS' if good else 'FAIL', 'seconds': time.monotonic() - started})
        if not good:
            break
    good = len(rows) == len(SUITES) and all(row['status'] == 'PASS' for row in rows)
    value = {'schema': 'WORLD_ENGINE_REFERENCE_DIRECTOR_AFFECTED_REGRESSION_RESULT_V2',
        'status': 'PASS' if good else 'FAIL', 'baselineCommit': baseline['baselineCommit'],
        'rendererSHA256AtRun': renderer_sha, 'rendererOriginalSHA256': ORIGINAL_RENDERER_SHA,
        'oldTestsChanged': False, 'newAssertionsInvented': False,
        'selectedTests': sum(row[2] for row in SUITES),
        'actualPassedTests': sum(row['pass'] or 0 for row in rows), 'suites': rows,
        'full503RerunClaimed': False, 'nativeMapDrawVerifiedByTheseTests': False,
        'oldReferenceV1SealedPreflight': 'NOT_RUN_AS_REGRESSION_PASS: intentionally pins the old protected-renderer SHA and must reject an authorized changed renderer; old tests and seals are not relaxed.',
        'original503Proof': 'Preserved historical proof from5cc9b98; not relabeled as a new full run',
        'paidGpuOrApiUsed': False}
    with (report_dir / 'RESULTS.json').open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': value['status'], 'actualPassedTests': value['actualPassedTests'],
        'selectedTests': value['selectedTests'], 'report': str(report_dir / 'RESULTS.json')}))
    return 0 if good else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', default='after-renderer-01')
    args = parser.parse_args()
    raise SystemExit(run(args.attempt))
