"""Verify newly installed admission wiring and seals, without a renderer."""
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

plan = json.load(sys.stdin)
root = Path(plan['root'])
assert os.getuid() == 1000
for row in plan['files']:
    raw = (root / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
boot = root / 'world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py'
spec = importlib.util.spec_from_file_location('incident_boot', boot)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.verify_startup(boot.parent / 'STARTUP_MANIFEST.json', plan['startupManifestSHA256'])
manifest = root / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
module.source_contract(manifest, plan['runtimeManifestSHA256'])
controller = manifest.parent / 'controller'
sys.path.insert(0, str(controller))
import nvidia_worker
assert Path(nvidia_worker.__file__) == controller / 'nvidia_worker.py'
assert callable(nvidia_worker._read_frame_evidence)
assert "frames = _read_frame_evidence(directory, receipt.get('frameEvidence'), total_frames)" in inspect.getsource(nvidia_worker._validate_capture)
assert nvidia_worker.cache().MAX_JSON == 33554432
print(json.dumps({'status': 'PASS_NEW_INSTALLED_READER_AND_SEALS', 'workerSHA256': plan['reusedWorkerSHA256'],
                  'uid': 1000, 'overlayFiles': 4, 'genericLimitBytes': 33554432,
                  'runtimeManifestSHA256': plan['runtimeManifestSHA256'],
                  'startupManifestSHA256': plan['startupManifestSHA256'],
                  'GPUExecutions': 0, 'rendererExecutions': 0, 'oldPassReruns': 0}))
