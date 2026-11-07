"""New formal-controller input connection and installed package checks, CPU only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

value=json.load(sys.stdin); plan=value['plan']; root=Path(value['root']); mode=value['mode']
assert os.geteuid()==os.getegid()==1000
rec=root/'world-simulation-shorts-engine/recovery'
handoff=rec/'codex-to-gcube-handoff-v1'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
for row in plan['overlay']:
    raw=(root/row['path']).read_bytes()
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
boot=load('_kw20_installed_boot',rec/'studio-cold-start-v2/bootstrap.py')
boot.verify_startup(rec/'studio-cold-start-v2/STARTUP_MANIFEST.json',plan['startupManifestSHA256'])
boot.source_contract(handoff/'RUNTIME_SOURCE_MANIFEST.json',plan['runtimeManifestSHA256'])
js='const m=await import('+json.dumps((handoff/'backend/capture_nvidia.mjs').as_uri())+');console.log(JSON.stringify(await m.verifyGeneratedSources()));'
variants=json.loads(subprocess.check_output(['node','--input-type=module','-e',js],text=True,timeout=30))
assert len(variants)==3
for path,digest in plan['unchangedContractPins'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,'PRESERVED_CONTRACT_CHANGED:'+path
assert plan['entrypoint'][-2:]==['--export-root','/world-storage']
worker=(handoff/'controller/nvidia_worker.py').read_text()
mirror=(handoff/'controller/capture_diagnostics_safe.py').read_text()
assert 'ActiveCheckpointMirror(job, exports)' in worker and 'checkpoint_mirror.tick()' in worker
assert 'capture-checkpoint-' in mirror and '--active-checkpoint' in mirror
result={'status':'PASS','mode':mode,'uid':1000,'installedFiles':len(plan['overlay']),
    'startupAndSourceManifest':'PASS','actualVariantGate':'PASS','gpuStarts':0,'renderedFrames':0,
    'encoderLaunches':0,'oldPASSReruns':0,'actualGcubeMountReadback':False,
    'preservedCaptureStorageAndComposerPins':len(plan['unchangedContractPins']),
    'activeCheckpointExportRoot':'/world-storage','priorStoragePass':'REUSED_NOT_RERUN'}
if mode=='controller-input-connection':
    sys.path.insert(0,str(handoff/'controller'))
    from nvidia_controller import NvidiaPresentationController
    ctl=NvidiaPresentationController(control_root=Path('/workspace/kw20-native-private'),
        export_root=Path('/world-storage'),image_digest=plan['parentDigest'],
        source_manifest=handoff/'RUNTIME_SOURCE_MANIFEST.json',expected_manifest_sha256=plan['runtimeManifestSHA256'])
    clips=[]
    for index,row in enumerate(plan['inputs']):
        prompt=json.loads((root/row['path']).read_bytes())
        native=ctl._normal({'schema':'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1','prompt':prompt,'sceneId':'__timeline__'})
        video=native['videoPlan']; runtime=video['runtime']
        assert video['durationSeconds']==10 and video['totalFrames']==300 and video['fps']==30
        assert video['simulationType']=='GENERAL' and video['audioSettings']=={'enabled':False,'mode':'SILENT'}
        assert [s['scene'] for s in runtime['segments']]==plan['expectedScenes'][index], 'EXISTING_SCENE_CHANGED'
        assert video['renderProfile']['sourceClosureSHA256']==plan['runtimeManifestSHA256']
        clips.append({'part':index+1,'durationSeconds':10,'frames':300,
            'sceneIds':[s['sceneId'] for s in runtime['segments']],
            'sourceQualificationSHA256':video['sourceQualificationSHA256'],
            'runtimeWireSHA256':video['runtimeWireSHA256'],'existingSceneEquality':True})
    result['clips']=clips
    result['entryPoint']='NvidiaPresentationController._normal -> original compiler -> NVIDIA source admission'
    result['fullHardwarePreflight']='NOT_RUN_REQUIRES_USER_DEPLOYMENT'
elif mode!='installed-package':
    raise RuntimeError('PROBE_MODE_INVALID')
print(json.dumps(result))
