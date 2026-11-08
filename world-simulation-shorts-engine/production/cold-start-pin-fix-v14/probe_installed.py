"""Exercise the new installed parent/child startup contract, without a service."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

request=json.load(sys.stdin)
root,plan=Path(request['root']),request['plan']
for row in plan['overlay']:
    raw=(root/row['path']).read_bytes()
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
startup=root/'world-simulation-shorts-engine/recovery/studio-cold-start-v2'
manifest=startup/'STARTUP_MANIFEST.json'
module=load('_installed_v14_bootstrap',startup/'bootstrap.py')
module.verify_startup(manifest,plan['startupManifestSHA256'])
child=load('_installed_v14_child',startup/'worker.py')
child.bootstrap(manifest,plan['startupManifestSHA256'])
source=root/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
_,contract=module.source_contract(source,plan['runtimeManifestSHA256'])
assert contract.expected_sha256==module.SOURCE_SHA==plan['runtimeManifestSHA256']
worker=root/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
assert hashlib.sha256(worker.read_bytes()).hexdigest()=='d5bf03d4b79d70411c02d542bbebd08d9df0463636f558f02ee271c259b6b3d9'
print(json.dumps({'status':'PASS','scope':'NEW_PARENT_CHILD_STARTUP_AND_RUNTIME_HANDOFF',
    'runtimeManifestUnchanged':True,'v13WorkerPreserved':True,'oldPASSReruns':0,'gpuStarts':0,'renderedFrames':0}))
