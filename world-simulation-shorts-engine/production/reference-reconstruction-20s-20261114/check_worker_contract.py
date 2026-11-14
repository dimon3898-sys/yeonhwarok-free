"""Synthetic 600-frame output contract fixture. Never a render or GPU proof."""
import ast,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent;E=P.parents[1];R=E.parent;H=E/'recovery/codex-to-gcube-handoff-v1'
sys.path.insert(0,str(H/'controller'))
import nvidia_worker as w
import safe_capture_export as safe
from common import HISTORY_PROFILE,duration_contract
sha=lambda b:hashlib.sha256(b).hexdigest();checks=[]
def passed(name,evidence=None):checks.append({'name':name,'status':'PASS','evidence':evidence})
def rejects(call,code):
 try:call()
 except RuntimeError as e:assert str(e)==code,(str(e),code)
 else:raise AssertionError('Expected '+code)
# The publication barrier/lease-release function stays byte-identical in AST;
# only the separately tested new profile selector changes before the same run.
name='world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
old=subprocess.check_output(['git','show','926d3930b6018e9be0bd6ed675bcbde84256f805:'+name],cwd=R,text=True)
new=(R/name).read_text()
def functions(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
a,b=functions(old),functions(new)
for name in ['keep_original_lease_until_cleanup','_write_runtime','run']:assert a[name]==b[name]
# Work publication / owner lease order must not move across the new profile.
old_run=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name=='_run')
new_run=next(n for n in ast.parse(new).body if isinstance(n,ast.FunctionDef) and n.name=='_run')
normalized=ast.unparse(new_run).replace('backend._verify(plan, profile_for(plan))','backend._verify(plan, PROFILE)')
assert normalized==ast.unparse(old_run)
passed('UNCHANGED_WORKER_PUBLICATION_LEASE_AND_CLEANUP_AST',{'baselineCommit':'926d3930b6018e9be0bd6ed675bcbde84256f805'})
plan={'durationSeconds':20,'totalFrames':600,'fps':30,'simulationType':'HISTORICAL','renderProfile':{'profileId':HISTORY_PROFILE},'historicalAdmission':{'schema':'WORLD_ENGINE_AUTHORED_HISTORY_ADMISSION_V1','status':'PASS','scope':'HISTORICAL_CONTINUOUS_600F_V1','simulationType':'HISTORICAL','paidExecutionAllowed':False},'runtimeWireSHA256':'1'*64,'sourceQualificationSHA256':'2'*64,'runtime':{'segments':[{}]}}
assert duration_contract(plan)['totalFrames']==600
for d in [6,10]:assert duration_contract({'durationSeconds':d,'totalFrames':d*30,'fps':30})['totalFrames']==d*30
rejects(lambda:duration_contract({**plan,'simulationType':'GENERAL'}),'HANDOFF_REVIEWED_CONTINUOUS_HISTORY_REQUIRED')
passed('WORKER_DURATION_AND_HISTORY_PROFILE_BOUNDARY')
with tempfile.TemporaryDirectory(prefix='world-600-unit-') as directory:
 out=Path(directory);video=b'CONTRACT_FIXTURE_ONLY_NOT_A_VIDEO';(out/'VIDEO.mp4').write_bytes(video)
 rows={'schema':'WORLD_ENGINE_NVIDIA_PRESENTATION_FRAMES_V1','durationSeconds':20,'totalFrames':600,'frames':[{'frame':i,'diagnostic':{'glError':0}} for i in range(600)]}
 wire=json.dumps(rows,separators=(',',':')).encode();(out/'FRAME_EVIDENCE.json').write_bytes(wire);(out/'FRAME_EVIDENCE.json').chmod(0o600)
 proof={'segmentIndex':0,'schema':'WORLD_ENGINE_NATIVE_MAP_STABILITY_V1','status':'PASS','backend':'NVIDIA Vulkan SYNTHETIC_TEST_FIXTURE','draws':[{'index':i,'frame':0,'glError':0,'rgbaBytes':1080*1920*4,'nonBlackPixels':1080*1920,'rawRGBA256':'3'*64}for i in range(3)]}
 receipt={'schema':'WORLD_ENGINE_NVIDIA_TWENTY_SECOND_CAPTURE_V1','durationSeconds':20,'status':'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED','packageSHA256':plan['runtimeWireSHA256'],'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'softwareOnly':False,'nvidiaVerified':True,'renderedFrames':600,'totalFrames':600,'visualQualityApproved':False,'video':{'sha256':sha(video)},'historicalAdmission':plan['historicalAdmission'],'nativeStability':[proof],'frameEvidence':{'file':'FRAME_EVIDENCE.json','sha256':sha(wire)}}
 def save():
  (out/'CAPTURE_RECEIPT.json').write_text(json.dumps(receipt));(out/'CAPTURE_RECEIPT.json').chmod(0o600)
 save()
 with w.cache().PrivateTree(out) as tree:
  assert len(w._read_frame_evidence(tree,receipt['frameEvidence'],600)['frames'])==600
  rejects(lambda:w._read_frame_evidence(tree,{**receipt['frameEvidence'],'sha256':'0'*64},600),'HANDOFF_FRAME_EVIDENCE_SHA256_MISMATCH')
 passed('NEW_600_LEDGER_READER_AND_HASH_REJECTION')
 calls=[]
 def probe(command,**kwargs):
  calls.append(command[0]);assert command[0] in ['ffprobe','ffmpeg']
  info={'streams':[{'codec_type':'video','codec_name':'h264','width':1080,'height':1920,'r_frame_rate':'30/1','nb_read_frames':'600'}],'format':{'duration':'20.000'}}
  return subprocess.CompletedProcess(command,0,stdout=json.dumps(info).encode() if command[0]=='ffprobe' else b'',stderr=b'')
 with patch.object(w.subprocess,'run',probe):
  result=w._validate_capture(out,plan);assert result['frames']==600 and result['durationSeconds']==20
  receipt['historicalAdmission']={};save();rejects(lambda:w._validate_capture(out,plan),'HANDOFF_HISTORY_RECEIPT_BINDING_CHANGED')
 assert calls==['ffprobe','ffmpeg']
 passed('600_RECEIPT_BINDING_WITH_SYNTHETIC_MEDIA_METADATA',{'mockedSubprocesses':calls,'realMediaValidated':False,'fixtureDeletedOnExit':True})
assert safe.frame_limit({'durationSeconds':20,'totalFrames':600})==600
assert safe.frame_limit({'durationSeconds':20,'totalFrames':599})==180
assert safe.safe_failure({'operationId':'DRAW','sourceId':'PRESENTATION_RUNTIME','frameIndex':599,'errorCode':'UP2_FRAME_GL_ERROR'},total_frames=600)['frameIndex']==599
assert w.cache().MAX_JSON==32*1024**2
passed('600_PUBLIC_DIAGNOSTICS_WITH_UNCHANGED_GENERIC_JSON_LIMIT')
report={'schema':'WORLD_ENGINE_600_WORKER_CONTRACT_TESTS_V1','status':'PASS_CHANGED_CONTRACT_ONLY','checks':checks,'fixtureOnly':True,'actualGPU':'PENDING_GPU','GPUExecutions':0,'actualRendererExecutions':0,'oldPassReruns':0}
(P/'WORKER_CONTRACT_TESTS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(checks)}))
