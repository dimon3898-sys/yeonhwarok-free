"""Run only the newly added retention contracts as actual UID1000."""
from pathlib import Path
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

BASE = 'b52e9367d89e41e0e6a48bb69bda16885d03d302'
REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
AUDIT = REC + 'capture-stall-review-v1/'
repo, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
assert os.getuid() == 0
assert not output.exists()
output.mkdir(mode=0o755)
seal = json.loads((repo / AUDIT / 'evidence/RETENTION_SOURCE_SEAL.json').read_bytes())
for row in seal['files']:
    raw = (repo / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], row['path']
manifest = json.loads((repo / HANDOFF / 'RUNTIME_SOURCE_MANIFEST.json').read_bytes())
assert len(manifest['files']) == 356
for row in seal['files'][:6]:
    pin = next(item for item in manifest['files'] if item['path'] == row['path'])
    assert pin == row
for row in seal['files']:
    if row['path'].endswith('.py'):
        ast.parse((repo / row['path']).read_text())
node = shutil.which('node')
for name in ('capture_vulkan.generated.mjs', 'backend/capture_operation_diagnostics.mjs'):
    subprocess.run([node, '--check', str(repo / HANDOFF / name)], check=True)
aggregate = {'schema': 'WORLD_ENGINE_RETENTION_CPU_CI_V1', 'sourceBaseCommit': BASE,
    'headSHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    'sourceSealSHA256': hashlib.sha256((repo / AUDIT / 'evidence/RETENTION_SOURCE_SEAL.json').read_bytes()).hexdigest(),
    'uidUnderTest': 1000, 'status': 'RUNNING', 'gpuExecutions': 0, 'imageBuilds': 0,
    'oldPassSuitesRerun': 0, 'tests': []}
try:
    with tempfile.TemporaryDirectory(prefix='we-retention-ci-') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        tree = root / 'source'
        for name in ('codex-to-gcube-handoff-v1', 'capture-stall-review-v1'):
            shutil.copytree(repo / REC / name, tree / REC / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for file in tree.rglob('*'):
            file.chmod(0o755 if file.is_dir() else 0o644)
        baseline = root / 'baseline.mjs'
        baseline.write_bytes(subprocess.check_output(['git', 'show', BASE + ':' + HANDOFF + 'capture_vulkan.generated.mjs'], cwd=repo))
        test_output = root / 'results'
        test_output.mkdir(mode=0o700)
        os.chown(test_output, 1000, 1000)
        tests = tree / AUDIT / 'tests'
        commands = [
            ('wiring', [node, str(tests / 'capture_wiring_focus.mjs'), str(baseline), str(test_output / 'wiring')]),
            ('active', [sys.executable, '-B', str(tests / 'active_checkpoint_focus.py'), str(test_output / 'active')]),
            ('forced', [sys.executable, '-B', str(tests / 'forced_stop_retention.py'), str(test_output / 'forced'), node])]
        for name, command in commands:
            execution = subprocess.run(command, cwd=root, user=1000, group=1000, extra_groups=[],
                env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, text=True, timeout=30)
            (output / (name + '.stdout')).write_text(execution.stdout)
            (output / (name + '.stderr')).write_text(execution.stderr)
            if (test_output / name).exists():
                shutil.copytree(test_output / name, output / name)
            aggregate['tests'].append({'name': name, 'exitCode': execution.returncode})
            print(execution.stdout)
            if execution.returncode:
                print(execution.stderr)
                raise AssertionError(name + '_FAILED')
        # New source seal verification, not a rerun of historical GPU/quality tests.
        aggregate['sourcePinsVerified'] = len(seal['files'])
        aggregate['status'] = 'CPU_RETENTION_CONTRACTS_PASS'
except BaseException as error:
    aggregate['status'] = 'FAIL'
    aggregate['error'] = type(error).__name__ + ':' + str(error)[:1000]
    raise
finally:
    (output / 'CI_RESULT.json').write_text(json.dumps(aggregate, indent=2) + '\n')
    for file in output.rglob('*'):
        file.chmod(0o755 if file.is_dir() else 0o644)
    print('RETENTION_CI_RESULT=' + json.dumps(aggregate))
    # The small fixed-schema envelopes can be recovered verbatim via job logs.
    for file in sorted((output / 'forced').glob('*.json')):
        print('RETENTION_FILE=' + json.dumps({'name': file.name, 'content': file.read_text()}))
