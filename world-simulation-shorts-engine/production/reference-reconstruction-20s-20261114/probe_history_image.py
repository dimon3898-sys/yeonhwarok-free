"""Actual immutable-image controller/worker transport; no start or renderer call."""
import hashlib,json,os,sys
from pathlib import Path
root=Path('/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo');H=root/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1';P=root/'world-simulation-shorts-engine/production/reference-reconstruction-20s-20261114'
sys.path.insert(0,str(H/'controller'))
from nvidia_controller import NvidiaPresentationController
from common import validate_plan,verify_manifest,canonical
import nvidia_worker
sha=lambda b:hashlib.sha256(b).hexdigest()
assert os.getuid()==1000 and os.environ['NVIDIA_VISIBLE_DEVICES']=='void'
manifest=H/'RUNTIME_SOURCE_MANIFEST.json';pin=sha(manifest.read_bytes());verify_manifest(manifest,pin,require_external=True)
request=json.loads((P/'FINAL_20S_INPUT.json').read_bytes());work=Path('/history-gate');work.mkdir(exist_ok=True)
(work/'exports').mkdir(mode=0o700)
# Match the real bootstrap precondition: public export root already exists.
# Format-valid fixture digest is never authorization or publication approval.
digest='sha256:'+'a'*64
c=NvidiaPresentationController(control_root=work/'private',export_root=work/'exports',image_digest=digest,source_manifest=manifest,expected_manifest_sha256=pin)
try:
 submission=c._normal(request)
except Exception as error:
 print(json.dumps({'status':'FAIL','code':getattr(error,'code',str(error)),'privateFixtureDiagnostic':getattr(error,'_private_profile_stderr',b'').decode(errors='replace')[:4000],'GPUExecutions':0}),file=sys.stderr)
 raise
plan=submission['videoPlan'];validate_plan(plan,image_digest=digest,source_sha=pin)
assert plan['simulationType']=='HISTORICAL' and plan['durationSeconds']==20 and plan['totalFrames']==600 and plan['fps']==30
assert plan['resolution']=={'width':1080,'height':1920} and plan['renderProfile']['profileId']=='GCUBE_NVIDIA_CONTINUOUS_HISTORY_20S_V1'
segment=plan['runtime']['segments'][0]; authored=request['prompt']
assert segment['presentation']['camera']==authored['presentation']['camera']
assert segment['presentation']['labels']==authored['presentation']['labels']
assert segment['region']['sourceId']=='NASA_BMNG_EURASIA_PYRAMID_V1'
assert len(segment['presentation']['territoryChanges']['items'][0]['continuous']['frames'])==106
assert plan['historicalAdmission']['source']==authored['source']
job=work/'worker-transport';job.mkdir(mode=0o700);nvidia_worker._write_runtime(job,plan['runtimeWireJSON'])
wire=(job/'RUNTIME_REQUEST.json').read_bytes();assert sha(wire)==plan['runtimeWireSHA256'] and json.loads(wire)==plan['runtime']
assert not list(work.rglob('APPROVAL.json')) and not list(work.rglob('authorization.json'))
result={'status':'PASS_ACTUAL_IMAGE_CONTROLLER_WORKER_TRANSPORT','profile':submission['profile'],'durationSeconds':20,'totalFrames':600,'fps':30,'resolution':plan['resolution'],'sourceManifestSHA256':pin,'inputJSONSHA256':sha((P/'FINAL_20S_INPUT.json').read_bytes()),'authoredCanonicalInputSHA256':plan['originalInputSHA256'],'runtimeWireSHA256':sha(wire),'runtimeWireBytes':len(wire),'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'sourceBindings':plan['sourceBindings'],'historicalAdmission':plan['historicalAdmission'],'cameraFrames':len(segment['presentation']['camera']['frames']),'continuousGeometryCount':106,'mapSource':segment['region']['sourceId'],'workerInputBytesUnchanged':True,'imageDigestInPlan':'SYNTHETIC_TEST_BINDING_NOT_DEPLOYMENT_DIGEST','authorizationCreated':False,'GPUExecutions':0,'rendererExecutions':0,'actualGPU':'PENDING_GPU'}
print(json.dumps(result))
