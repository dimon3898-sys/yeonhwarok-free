"""Only new source/director/camera/control/material tests; no full old audit/GPU."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
commands = [['python3', '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py', '-v']]
commands += [['node', str(ROOT / 'tests' / name)] for name in [
    'test_derive_scene.mjs', 'test_camera_plan.mjs', 'test_control_bridge.mjs',
    'test_partial_front_pass.mjs', 'test_material_context.mjs', 'test_runtime_adapter.mjs']]
results = []
for command in commands:
    start = time.monotonic()
    run = subprocess.run(command, cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    matches = re.findall(r'(?:Ran |tests )(\d+)', run.stdout)
    row = {'command': command, 'exitCode': run.returncode, 'status': 'PASS' if run.returncode == 0 else 'FAIL',
        'testCount': int(matches[-1]) if matches else None, 'seconds': time.monotonic() - start, 'output': run.stdout}
    results.append(row)
    print(json.dumps({k: row[k] for k in ['status', 'testCount', 'seconds']}), flush=True)
report = {'schema': 'WORLD_ENGINE_ASTRA_V2_FOCUSED_TESTS_V1', 'results': results,
    'testCount': sum(r['testCount'] or 0 for r in results), 'status': 'PASS' if all(r['exitCode'] == 0 for r in results) else 'FAIL',
    'testsAreCPUOrExplicitMocks': True, 'nvidiaHardwareVerified': False, 'visualQualityApproved': False,
    'sourceHashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in {'.mjs', '.py'} and '.private' not in p.parts and '__pycache__' not in p.parts}}
(ROOT / 'reports/FOCUSED_TESTS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
if report['status'] != 'PASS':
    raise SystemExit(1)
