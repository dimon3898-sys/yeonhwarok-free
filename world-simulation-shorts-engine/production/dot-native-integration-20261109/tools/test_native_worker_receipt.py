"""Negative receipts deliberately forge GPU claims; all must fail before subprocesses."""
from pathlib import Path
import sys,json,hashlib,tempfile,shutil,os
root=Path(sys.argv[2]).resolve()
repository=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(repository/'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller'))
import nvidia_worker as worker
plan=json.loads((Path(sys.argv[3]).resolve()).read_text())['videoPlan']
sha=lambda b:hashlib.sha256(b).hexdigest()
folder=Path(tempfile.mkdtemp(prefix='we-negative-receipt-',dir=Path(sys.argv[4]).resolve()))
checks=[]
try:
 raw=b'{"frames":[]}';(folder/'FRAME_EVIDENCE.json').write_bytes(raw);(folder/'FRAME_EVIDENCE.json').chmod(0o600)
 (folder/'VIDEO.mp4').write_bytes(b'NOT_A_VIDEO_NEGATIVE_FIXTURE');(folder/'VIDEO.mp4').chmod(0o600)
 receipt={'schema':'WORLD_ENGINE_NVIDIA_TEN_SECOND_CAPTURE_V1','status':'TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED','packageSHA256':plan['runtimeWireSHA256'],'sourceQualificationSHA256':plan['sourceQualificationSHA256'],'softwareOnly':False,'nvidiaVerified':True,'renderedFrames':300,'totalFrames':300,'durationSeconds':10,'visualQualityApproved':False,'video':{'sha256':sha((folder/'VIDEO.mp4').read_bytes())},'frameEvidence':{'file':'FRAME_EVIDENCE.json','sha256':sha(raw)}}
 cases=[('BINDING_MISSING',{},'HANDOFF_CANDIDATE_CAPTURE_BINDING_CHANGED'),('ACTIVATION_MISSING',{'nativeCandidateSHA256':plan['nativeCandidateSHA256']},'HANDOFF_CANDIDATE_CAPTURE_ACTIVATION_CHANGED'),('CORRECT_PINS_DO_NOT_REPLACE_GPU_PROOF',{'nativeCandidateSHA256':plan['nativeCandidateSHA256'],'candidateActivationSHA256':plan['nativeCandidate']['activationSHA256']},'HANDOFF_NATIVE_STABILITY_SEGMENTS_REQUIRED')]
 original=worker.subprocess.run
 worker.subprocess.run=lambda *a,**k:(_ for _ in ()).throw(AssertionError('NEGATIVE_RECEIPT_MUST_FAIL_BEFORE_SUBPROCESS'))
 try:
  for name,fields,expected in cases:
   p=folder/'CAPTURE_RECEIPT.json';p.write_text(json.dumps({**receipt,**fields}));p.chmod(0o600)
   try:worker._validate_capture(folder,plan)
   except RuntimeError as error:assert str(error)==expected,(name,str(error))
   else:raise AssertionError('FORGED_RECEIPT_ACCEPTED')
   checks.append(name)
 finally:worker.subprocess.run=original
finally:shutil.rmtree(folder)
result={'schema':'WORLD_ENGINE_NATIVE_WORKER_RECEIPT_NEGATIVE_TEST_V1','status':'PASS','newChecks':len(checks),'checks':checks,'fixtures':'DELIBERATELY_FORGED_NOT_GPU_EVIDENCE','workerStarted':False,'gpuExecuted':False,'rendererExecuted':False}
(root/'NATIVE_WORKER_RECEIPT_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
