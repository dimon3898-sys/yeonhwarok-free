"""UID1000 real-image source/Controller/Worker compatibility, no GPU start."""
import hashlib,json,os,sys
from pathlib import Path
root=Path('/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo');E=root/'world-simulation-shorts-engine';H=E/'recovery/codex-to-gcube-handoff-v1';sys.path.insert(0,str(H/'controller'))
from nvidia_controller import NvidiaPresentationController
from common import validate_plan,verify_manifest,sha
import nvidia_worker
assert os.getuid()==1000 and os.environ['NVIDIA_VISIBLE_DEVICES']=='void'
manifest=H/'RUNTIME_SOURCE_MANIFEST.json';pin=sha(manifest.read_bytes());verify_manifest(manifest,pin,require_external=True)
work=Path('/contract-gate');(work/'exports').mkdir(mode=0o700);digest='sha256:'+'a'*64
c=NvidiaPresentationController(control_root=work/'private',export_root=work/'exports',image_digest=digest,source_manifest=manifest,expected_manifest_sha256=pin)
rows=[]
for i in range(1,4):
 file=Path('/reviewed-inputs')/f'MONGOL_6S_PART_0{i}.json';request=json.loads(file.read_bytes())
 try:submission=c._normal(request)
 except Exception as exc:
  print(json.dumps({'status':'FAIL','code':getattr(exc,'code',str(exc)),'testStderr':getattr(exc,'_private_profile_stderr',b'').decode(errors='replace')[:4000],'GPUExecutions':0}),file=sys.stderr);raise
 plan=submission['videoPlan'];validate_plan(plan,image_digest=digest,source_sha=pin)
 assert plan['simulationType']=='HISTORICAL' and plan['durationSeconds']==6 and plan['totalFrames']==180 and plan['fps']==30
 assert plan['resolution']=={'width':1080,'height':1920} and plan['renderProfile']['profileId']=='GCUBE_NVIDIA_HISTORICAL_V2'
 segment=plan['runtime']['segments'][0];assert segment['presentation']['camera']==request['prompt']['presentation']['camera'];assert segment['presentation']['labels']==request['prompt']['presentation']['labels'];assert segment['timelineWindow']==request['prompt']['timeline']['window']
 assert len(segment['presentation']['territoryChanges']['items'][0]['continuous']['frames'])==106
 job=work/f'worker-{i}';job.mkdir(mode=0o700);nvidia_worker._write_runtime(job,plan['runtimeWireJSON']);wire=(job/'RUNTIME_REQUEST.json').read_bytes();assert sha(wire)==plan['runtimeWireSHA256']
 rows.append({'input':file.name,'inputSHA256':sha(file.read_bytes()),'runtimeWireSHA256':sha(wire),'window':segment['timelineWindow'],'workerInputBytesUnchanged':True,'sourceQualificationSHA256':plan['sourceQualificationSHA256']})
assert not list(work.rglob('APPROVAL.json')) and not list(work.rglob('authorization.json'))
print(json.dumps({'status':'PASS_ACTUAL_IMAGE_EXTERNAL_DATA_CONTROLLER_WORKER','sourceManifestSHA256':pin,'uid':os.getuid(),'inputs':rows,'externalDataRoot':os.environ['WORLD_ENGINE_DATA_ROOT'],'catalogSHA256':os.environ['WORLD_ENGINE_DATA_CATALOG_SHA256'],'GPUExecutions':0,'rendererExecutions':0,'actualGPU':'PENDING_GPU'}))
