"""Installed identity/import check only. No previous tests or render entry."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

request = json.load(sys.stdin)
root, plan = Path(request['root']), request['plan']
for row in plan['overlay']:
    raw = (root / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
controller = root / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller'
sys.path.insert(0, str(controller))
import common
result = common.verify_manifest(root / 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json',
    plan['runtimeManifestSHA256'], repo=root, require_external=True)
import nvidia_worker
assert Path(nvidia_worker.__file__) == controller / 'nvidia_worker.py'
assert callable(nvidia_worker._read_frame_evidence)
assert nvidia_worker.cache().MAX_JSON == 32 * 1024**2
print(json.dumps({'status':'PASS','scope':'NEW_INSTALLED_WORKER_IDENTITY_AND_IMPORT_ONLY',
    'verifiedFiles':result['verifiedFiles'],'gpuStarts':0,'renderedFrames':0,'oldPASSReruns':0,
    'focusedTestsRerun':0,'globalCacheLimitUnchanged':True}))
