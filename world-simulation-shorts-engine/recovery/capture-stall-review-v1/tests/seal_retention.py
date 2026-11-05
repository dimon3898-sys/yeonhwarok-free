"""Update only changed source pins in the existing manifests; no build/render."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import sys

REC = 'world-simulation-shorts-engine/recovery/'
HANDOFF = REC + 'codex-to-gcube-handoff-v1/'
AUDIT = REC + 'capture-stall-review-v1/'
SOURCE_PATHS = [HANDOFF + path for path in (
    'capture_vulkan.generated.mjs', 'backend/capture_operation_diagnostics.mjs',
    'controller/safe_capture_export.py', 'controller/capture_diagnostics_safe.py', 'controller/nvidia_worker.py')]
PINS = {HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json': '3ccfb196433e7094286f2eacf188270cd05cea8c0e6603bcdef688142a953528',
    HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json': 'f4f3f9c5bd9b7881441e2802714d3c43b5876ab49e4c963e8ec5875a5fce15da',
    REC + 'studio-cold-start-v2/bootstrap.py': '006281f58c1dd977c80505b6ff7be0b4e1f6adf38ca11e204fcd5e9a763fed98',
    REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json': '60fc6cd844cf021d0a590682f4ae96964f8036be8d650708e271fbb896efa163'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def wire(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()

def seal(repo):
    previous_seal = repo / AUDIT / 'evidence/RETENTION_SOURCE_SEAL.json'
    expected = dict(PINS)
    if previous_seal.exists():
        previous = json.loads(previous_seal.read_bytes())
        assert previous['sourceBaseCommit'] == 'b52e9367d89e41e0e6a48bb69bda16885d03d302'
        expected.update({row['path']: row['sha256'] for row in previous['files'] if row['path'] in PINS})
    for name, digest in expected.items():
        assert sha((repo / name).read_bytes()) == digest, 'BASE_PIN_CHANGED:' + name
    generated_path = HANDOFF + 'backend/GENERATED_SOURCE_MANIFEST.json'
    generated = json.loads((repo / generated_path).read_bytes())
    variant = next(row for row in generated['variants'] if row['variant'] == 'capture_vulkan.generated.mjs')
    original = repo / variant['original']
    current = repo / HANDOFF / variant['variant']
    assert sha(original.read_bytes()) == variant['originalSHA256']
    variant['variantSHA256'] = sha(current.read_bytes())
    variant['diff'] = '../capture-stall-review-v1/evidence/capture-retention.patch'
    evidence = repo / AUDIT / 'evidence'
    evidence.mkdir(exist_ok=True)
    (evidence / 'capture-retention.patch').write_text(''.join(difflib.unified_diff(
        original.read_text().splitlines(True), current.read_text().splitlines(True),
        fromfile=variant['original'], tofile=HANDOFF + variant['variant'])))
    generated['activeCaptureCheckpoint'] = {'sourceBaseCommit': 'b52e9367d89e41e0e6a48bb69bda16885d03d302',
        'actualGPUValidation': 'NOT_RUN', 'purpose': 'Bounded operation recording and active safe mirror'}
    (repo / generated_path).write_bytes(wire(generated))
    runtime_path = HANDOFF + 'RUNTIME_SOURCE_MANIFEST.json'
    runtime = json.loads((repo / runtime_path).read_bytes())
    before_count = len(runtime['files'])
    changed = SOURCE_PATHS + [generated_path]
    for name in changed:
        row = next(row for row in runtime['files'] if row['path'] == name)
        raw = (repo / name).read_bytes()
        row.update(bytes=len(raw), sha256=sha(raw))
    assert len(runtime['files']) == before_count == 356
    (repo / runtime_path).write_bytes(wire(runtime))
    digest = sha(wire(runtime))
    bootstrap_path = REC + 'studio-cold-start-v2/bootstrap.py'
    bootstrap, count = re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$", "SOURCE_SHA = '" + digest + "'", (repo / bootstrap_path).read_text())
    assert count == 1
    (repo / bootstrap_path).write_text(bootstrap)
    startup_path = REC + 'studio-cold-start-v2/STARTUP_MANIFEST.json'
    startup = json.loads((repo / startup_path).read_bytes())
    startup['runtimeManifestSHA256'] = digest
    startup['files']['bootstrap.py'] = {'bytes': len(bootstrap.encode()), 'sha256': sha(bootstrap.encode())}
    (repo / startup_path).write_bytes(wire(startup))
    paths = changed + [runtime_path, bootstrap_path, startup_path]
    result = {'schema': 'WORLD_ENGINE_RETENTION_SOURCE_SEAL_V1', 'sourceBaseCommit': 'b52e9367d89e41e0e6a48bb69bda16885d03d302',
        'sourceRowsBefore': before_count, 'sourceRowsAfter': len(runtime['files']), 'newRuntimeSources': 0,
        'files': [{'path': name, 'bytes': len((repo / name).read_bytes()), 'sha256': sha((repo / name).read_bytes())} for name in paths],
        'runtimeManifestSHA256': digest, 'gpuExecutions': 0, 'imageBuilds': 0, 'imagePublications': 0}
    (evidence / 'RETENTION_SOURCE_SEAL.json').write_bytes(wire(result))
    return result

if __name__ == '__main__':
    print(json.dumps(seal(Path(sys.argv[1]).resolve())))
