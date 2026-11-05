"""New inner-export deadline check, distinct from the UID1000 helper-start delay."""
from pathlib import Path
import json,os,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'codex-to-gcube-handoff-v1/controller'))
import safe_capture_export as exporter
root=Path(sys.argv[1]);root.mkdir(mode=0o700)
job=root/'handoff-gpu-jobs'/('studio-'+'b'*32);job.mkdir(parents=True,mode=0o700)
capture=job/'capture';capture.mkdir(mode=0o700)
fixture=Path(__file__).resolve().parents[1]/'executions/20261105-user-render-a1/RECOVERED_CURRENT_JOB.json'
value=json.loads(fixture.read_text())['files']['capture/CAPTURE_OPERATION_CHECKPOINT.json']['sanitizedContent'];value['runId']=job.name
source=capture/'CAPTURE_OPERATION_CHECKPOINT.json';source.write_text(json.dumps(value));source.chmod(0o600)
destination=root/('capture-checkpoint-'+job.name)
storage=exporter.active_shared_storage();original=storage._shared_fsync;calls=[]
def delayed(descriptor):
    if not calls:time.sleep(1.3)
    calls.append(True);return original(descriptor)
storage._shared_fsync=delayed
started=time.monotonic()
try:result=exporter.export_active_checkpoint(job,destination,deadline_seconds=15)
finally:storage._shared_fsync=original
elapsed=time.monotonic()-started
assert result['status']=='EXPORTED' and elapsed>=1.3
envelope=json.loads((destination/'CAPTURE_CHECKPOINT.json').read_text())
assert envelope['snapshot']['operations']['frameIndex']==1
report={'schema':'WORLD_ENGINE_INNER_STORAGE_LATENCY_V1','status':'PASS','uid':os.getuid(),
    'injectedInsideFsyncSeconds':1.3,'elapsedSeconds':elapsed,'budgetSeconds':15,
    'mountedReadback':True,'realFUSETested':False,'gpuExecuted':False}
(root/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
