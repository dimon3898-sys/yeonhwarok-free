"""Read-only image packaging check, run as UID1000 without network or GPU."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import subprocess

payload=json.load(sys.stdin); plan=payload['plan']; root=Path(payload['root']); mode=payload['mode']
rec='world-simulation-shorts-engine/recovery/'; handoff=rec+'codex-to-gcube-handoff-v1/'
runtime=handoff+'RUNTIME_SOURCE_MANIFEST.json'; bootstrap=rec+'studio-cold-start-v2/bootstrap.py'; startup=rec+'studio-cold-start-v2/STARTUP_MANIFEST.json'
assert os.geteuid()==1000

def raw(name):
    path=root/name
    assert path.is_file() and not any(p.is_symlink() for p in (path,*path.parents))
    return path.read_bytes()

def sha(value): return hashlib.sha256(value).hexdigest()

if mode=='parent':
    for name,digest in plan['basePins'].items(): assert sha(raw(name))==digest, 'PARENT_FILE_IDENTITY:'+name
    old=json.loads(raw(runtime)); new=payload['runtime']
    a={r['path']:r for r in old['files']}; b={r['path']:r for r in new['files']}
    assert set(a)==set(b) and len(a)==356
    changed={r['path'] for r in plan['overlay']} - {runtime,bootstrap,startup}
    assert {p for p in a if a[p]!=b[p]}==changed and len(changed)==1
    old['files']=new['files']; assert old==new, 'MANIFEST_UNRELATED_CHANGE'
    expected,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$", "SOURCE_SHA = '"+plan['runtimeManifestSHA256']+"'",raw(bootstrap).decode())
    assert n==1 and expected==payload['bootstrap'], 'BOOTSTRAP_UNRELATED_CHANGE'
    original=json.loads(raw(startup)); original['runtimeManifestSHA256']=plan['runtimeManifestSHA256']; original['files']['bootstrap.py']=payload['startup']['files']['bootstrap.py']
    assert original==payload['startup'], 'STARTUP_UNRELATED_CHANGE'
    result={'overlayBasePins':4,'changedRuntimeRows':1,'unchangedRuntimeRows':355}
elif mode=='candidate':
    for row in plan['overlay']:
        body=raw(row['path']); assert len(body)==row['bytes'] and sha(body)==row['sha256'], 'INSTALLED_PIN:'+row['path']
    spec=importlib.util.spec_from_file_location('_installed_bootstrap',root/bootstrap)
    boot=importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
    boot.verify_startup(root/startup,plan['startupManifestSHA256'])
    boot.source_contract(root/runtime,plan['runtimeManifestSHA256'])
    # Execute the exact source-variant gate omitted by the previous image check.
    uri=(root/handoff/'backend/capture_nvidia.mjs').as_uri()
    js="const m=await import("+json.dumps(uri)+");console.log(JSON.stringify(await m.verifyGeneratedSources()));"
    done=subprocess.run(['node','--input-type=module','-e',js],check=True,capture_output=True,text=True,timeout=30)
    variants=json.loads(done.stdout)
    assert len(variants)==3 and {row['variant'] for row in variants}=={'capture_vulkan.generated.mjs','presentation_runtime_vulkan.generated.mjs','region_source_vulkan.generated.mjs'}
    result={'installedOverlayPins':4,'startupManifest':'PASS','runtimeSourceContract':'PASS','runtimeSourceRows':356,'actualVerifyGeneratedSources':'PASS','verifiedVariantPairs':3}
else: raise RuntimeError('PROBE_MODE_INVALID')
print(json.dumps({'status':'PASS','mode':mode,'uid':os.geteuid(),'gpuExecutions':0,**result}))
