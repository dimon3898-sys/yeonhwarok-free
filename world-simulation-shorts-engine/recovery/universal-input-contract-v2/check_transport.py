"""New normalized requests and in-memory receipt contracts. No Worker start, GPU or FFmpeg."""
import ast,copy,hashlib,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
D=Path(__file__).resolve().parent;E=D.parents[1];R=E.parent;H=E/'recovery/codex-to-gcube-handoff-v1';P=E/'production/mongol-three-6s-20261114'
sys.path.insert(0,str(H/'controller'))
from common import validate_plan,sha,canonical
import nvidia_worker as w
from nvidia_backend import _runtime_environment,_capture_diagnostic_environment
root=Path(sys.argv[1]);manifest=H/'RUNTIME_SOURCE_MANIFEST.json';pin=sha(manifest.read_bytes());digest='sha256:'+'a'*64
checks=[];inputs=[]
def good(name,fn):
 fn();checks.append({'name':name,'status':'PASS'})
def reject(name,fn,code):
 try:fn()
 except RuntimeError as exc:assert str(exc)==code,(name,str(exc),code)
 else:raise AssertionError('Accepted '+name)
 checks.append({'name':name,'status':'PASS_REJECTED','expectedCode':code})
for i in range(1,4):
 raw=(root/f'normalized-0{i}.json').read_bytes();result=json.loads(raw);plan=result['videoPlan'];validate_plan(plan,image_digest=digest,source_sha=pin)
 job=root/f'worker-transport-0{i}';
 if not job.exists():job.mkdir(mode=0o700);w._write_runtime(job,plan['runtimeWireJSON'])
 wire=(job/'RUNTIME_REQUEST.json').read_bytes();assert sha(wire)==plan['runtimeWireSHA256'] and json.loads(wire)==plan['runtime']
 s=plan['runtime']['segments'][0];assert s['timelineWindow']=={'startFrame':(i-1)*180,'endFrame':i*180};assert len(s['presentation']['camera']['frames'])==600
 inputs.append({'file':f'MONGOL_6S_PART_0{i}.json','status':'PASS_REAL_CONTROLLER_AND_WORKER_FILE_TRANSPORT','inputSHA256':sha((P/f'MONGOL_6S_PART_0{i}.json').read_bytes()),'normalizedSHA256':sha(raw),'runtimeWireSHA256':sha(wire),'runtimeBytes':len(wire),'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'window':s['timelineWindow'],'profile':plan['renderProfile']['profileId'],'mapSource':s['region']['sourceId'],'historicalAdmission':plan['historicalAdmission'],'workerInputBytesUnchanged':True,'outputDirectory':str(job),'testDigest':'FORMAT_VALID_FIXTURE_NOT_IMAGE_ATTESTATION'})
 checks.append({'name':f'PART_{i}_REAL_CONTROLLER_TO_WORKER_INPUT','status':'PASS'})
# Only synthetic values in memory exercise the new receipt checks. Nothing here is a render receipt.
plan=json.loads((root/'normalized-02.json').read_text())['videoPlan'];body=b'CONTRACT_TEST_NOT_VIDEO';hex64='c'*64
receipt={'schema':'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1','status':'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED','packageSHA256':plan['runtimeWireSHA256'],'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'softwareOnly':False,'nvidiaVerified':True,'renderedFrames':180,'totalFrames':180,'visualQualityApproved':False,'video':{'sha256':sha(body)},'historicalAdmission':copy.deepcopy(plan['historicalAdmission']),'nativeStability':[{'segmentIndex':0,'schema':'WORLD_ENGINE_NATIVE_MAP_STABILITY_V1','status':'PASS','backend':'NVIDIA Vulkan IN_MEMORY_CONTRACT_FIXTURE','draws':[{'index':j,'frame':0,'glError':0,'rgbaBytes':1080*1920*4,'nonBlackPixels':1080*1920,'rawRGBA256':hex64} for j in range(3)]}]}
frames={'frames':[{'frame':j,'diagnostic':{'glError':0,'sourceFrame':180+j,'outputFrame':j}} for j in range(180)]}
class MemoryOutput:
 def __truediv__(self,name):return self
 def read_bytes(self):return body
class MemoryTree:
 def __init__(self,*a,**k):pass
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def json(self,name):assert name=='CAPTURE_RECEIPT.json';return receipt
metadata={'streams':[{'codec_type':'video','codec_name':'h264','width':1080,'height':1920,'r_frame_rate':'30/1','nb_read_frames':'180'}],'format':{'duration':'6.0'}}
def fake_command(args,**kwargs):
 assert args[0] in {'ffprobe','ffmpeg'}
 return SimpleNamespace(returncode=0,stderr=b'',stdout=json.dumps(metadata).encode() if args[0]=='ffprobe' else b'')
with patch.object(w,'cache',return_value=SimpleNamespace(PrivateTree=MemoryTree)),patch.object(w,'_read_frame_evidence',return_value=frames),patch.object(w.subprocess,'run',side_effect=fake_command):
 good('IN_MEMORY_WINDOW_RECEIPT_ACCEPTED',lambda:w._validate_capture(MemoryOutput(),plan))
 receipt['historicalAdmission']['timeline']['window']['startFrame']=0
 reject('RECEIPT_ADMISSION_TAMPER',lambda:w._validate_capture(MemoryOutput(),plan),'HANDOFF_HISTORY_RECEIPT_BINDING_CHANGED')
 receipt['historicalAdmission']=copy.deepcopy(plan['historicalAdmission']);frames['frames'][0]['diagnostic']['sourceFrame']=0
 reject('RECEIPT_GLOBAL_RESET',lambda:w._validate_capture(MemoryOutput(),plan),'HANDOFF_HISTORY_WINDOW_FRAME_EVIDENCE_INVALID')
 frames['frames'][0]['diagnostic']['sourceFrame']=180;frames['frames'][179]['diagnostic']['outputFrame']=178
 reject('RECEIPT_LOCAL_FRAME_TAMPER',lambda:w._validate_capture(MemoryOutput(),plan),'HANDOFF_HISTORY_WINDOW_FRAME_EVIDENCE_INVALID')
config=json.loads(Path('/tmp/world_engine_data_config.json').read_text());env={'WORLD_ENGINE_DATA_ROOT':config['dataRoot'],'WORLD_ENGINE_DATA_CATALOG_SHA256':config['catalogSHA256'],'GPU_BACKEND':'vulkan','UNTRUSTED_EXTRA':'excluded','NODE_OPTIONS':'excluded'}
for cleaner in [_runtime_environment,_capture_diagnostic_environment]:
 cleaned=cleaner(env);assert cleaned['WORLD_ENGINE_DATA_ROOT']==config['dataRoot'] and cleaned['WORLD_ENGINE_DATA_CATALOG_SHA256']==config['catalogSHA256'];assert 'UNTRUSTED_EXTRA' not in cleaned and 'NODE_OPTIONS' not in cleaned
checks.append({'name':'OPERATOR_DATA_CONFIG_BACKEND_WORKER_CAPTURE_ENVIRONMENT','status':'PASS'})
# Ensure old safety functions remain byte/AST-identical to the actual baseline.
base='66e94bb19fbb8bdd32f42b5f051f4e190bae74d5'
for filename,names in [('nvidia_backend.py',['approval_limit','start_studio_job']),('nvidia_worker.py',['_read_frame_evidence','_write_runtime','_run'])]:
 path=H/'controller'/filename;old=subprocess.check_output(['git','show',base+':'+str(path.relative_to(R))],cwd=R,text=True)
 def funcs(s):return {x.name:ast.dump(x,include_attributes=False) for x in ast.walk(ast.parse(s)) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
 a,b=funcs(old),funcs(path.read_text())
 for name in names:assert a[name]==b[name],name
 checks.append({'name':filename+'_UNCHANGED_APPROVAL_LEASE_LEDGER_AND_START_FUNCTIONS','status':'PASS_AST_IDENTICAL'})
assert not list(root.rglob('APPROVAL.json')) and not list(root.rglob('authorization.json'))
report={'schema':'WORLD_ENGINE_V2_TRANSPORT_CONTRACT_EVIDENCE','status':'PASS_CHANGED_SCOPE_ONLY','inputs':inputs,'checks':checks,'sourceManifestSHA256':pin,'receiptTestMode':'IN_MEMORY_MOCKED_MEDIA_ONLY_NOT_GPU_EVIDENCE','receiptArtifactsCreated':0,'actualFFmpegExecutions':0,'actualWorkerStarts':0,'rendererExecutions':0,'GPUExecutions':0,'authorizationCreated':False,'actualImage':'PENDING_IMAGE','actualGPU':'PENDING_GPU'}
(D/'TRANSPORT_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'inputs':3,'checks':len(checks),'GPUExecutions':0}))
