"""New failure-after-frame1 and slow-storage regressions. CPU processes only."""
from pathlib import Path
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

CONTROLLER = Path(__file__).resolve().parents[2] / 'codex-to-gcube-handoff-v1/controller'
sys.path.insert(0, str(CONTROLLER))
import lease_supervisor as supervisor
import capture_diagnostics_safe as diagnostics
import safe_capture_export as exporter

results = []
out = Path(sys.argv[1]); out.mkdir(mode=0o700)
with tempfile.TemporaryDirectory(prefix='incident-control-') as temp:
    root = Path(temp)
    job = root / 'handoff-gpu-jobs' / ('studio-' + 'a' * 32)
    job.mkdir(parents=True, mode=0o700)
    lease = root / 'CAPTURE.guard'
    fd = os.open(lease, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    checked = []
    def lease_still_held():
        contender = os.open(lease, os.O_RDWR)
        try:
            try:
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                checked.append(True)
            else:
                raise AssertionError('ORIGINAL_LEASE_RELEASED_EARLY')
        finally:
            os.close(contender)
    code = ('import json,time,subprocess,sys; '
        'subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
        'time.sleep(.2); '
        'print(json.dumps({"status":"FAILED","stage":"RENDER_RUNTIME","code":"GCUBE_CAPTURE_RUNTIME_FAILED"}),flush=True); '
        'time.sleep(60)')
    started = time.monotonic()
    try:
        supervisor.supervise_owned_capture([sys.executable, '-u', '-c', code],
            lease_fd=fd, lease_path=lease, parent=supervisor.parent_identity(os.getppid()),
            seconds=5, environment={}, output=job, total_frames=300,
            _cpu_test_before_cleanup=lease_still_held)
    except RuntimeError as error:
        assert str(error) == 'GCUBE_CAPTURE_RUNTIME_FAILED', str(error)
    else:
        raise AssertionError('TERMINAL_FAILURE_NOT_PROPAGATED')
    elapsed = time.monotonic() - started
    receipt = json.loads((job/'LEASE_SUPERVISOR_RESULT.json').read_text())
    assert elapsed < 4, elapsed
    assert checked == [True] and receipt['cleanupVerified']
    assert not receipt['cleanup']['remaining'] and not receipt['cleanup']['errors']
    assert receipt['reason'] == receipt['firstFailure']['code']
    results.append({'case':'terminal_failure_with_live_descendant','status':'PASS',
        'seconds':elapsed,'leaseHeldUntilCleanup':True,'cleanup':receipt['cleanup']})
    os.close(fd)

    capture=job/'capture';capture.mkdir(mode=0o700)
    fixture=Path(__file__).resolve().parents[1]/'executions/20261105-user-render-a1/RECOVERED_CURRENT_JOB.json'
    cp=json.loads(fixture.read_text())['files']['capture/CAPTURE_OPERATION_CHECKPOINT.json']['sanitizedContent']
    cp['runId']=job.name
    source=capture/'CAPTURE_OPERATION_CHECKPOINT.json'
    source.write_text(json.dumps(cp));source.chmod(0o600)
    export=root/'exports';export.mkdir(mode=0o700)
    real_popen=subprocess.Popen; launches=[]
    def delayed_helper(command, **kwargs):
        launches.append(command)
        assert command[-2:]==['--seconds','15'] and kwargs['env']=={}
        script=('import sys,time;sys.path.insert(0,sys.argv[1]);'
            'import safe_capture_export as e;time.sleep(1.3);'
            'e.export_active_checkpoint(sys.argv[2],sys.argv[3],deadline_seconds=15)')
        return real_popen([sys.executable,'-I','-S','-c',script,str(CONTROLLER),str(job),
            str(export/('capture-checkpoint-'+job.name))],**kwargs)
    mirror=diagnostics.ActiveCheckpointMirror(job,export)
    with patch.object(diagnostics.subprocess,'Popen',side_effect=delayed_helper):
        mirror.tick();time.sleep(1.05)
        assert mirror.tick()=='ACTIVE_CHECKPOINT_STARTED'
        limit=time.monotonic()+5
        while time.monotonic()<limit:
            status=mirror.tick()
            if status=='ACTIVE_CHECKPOINT_MOUNTED_WRITE_CONFIRMED':break
            time.sleep(.02)
        assert status=='ACTIVE_CHECKPOINT_MOUNTED_WRITE_CONFIRMED',status
        assert len(launches)==1
        envelope=json.loads((export/('capture-checkpoint-'+job.name)/'CAPTURE_CHECKPOINT.json').read_text())
        assert envelope['snapshot']['operations']['frameIndex']==1
        assert envelope['snapshot']['operations']['firstFailure']['errorCode']=='UP2_ACTUAL_FEATURE_PIXELS_MISSING'
        mirror.close()
    results.append({'case':'storage_slower_than_one_second','status':'PASS',
        'injectedDelaySeconds':1.3,'childCount':1,'fixedSchemaReadback':True})

    class Hanging:
        def __init__(self):self.killed=False
        def poll(self):return -9 if self.killed else None
        def kill(self):self.killed=True
        def wait(self,timeout):return -9
    hanging=Hanging();mirror=diagnostics.ActiveCheckpointMirror(job,export)
    mirror.process=hanging;mirror.started=10;mirror.status='ACTIVE_CHECKPOINT_STARTED'
    with patch.object(diagnostics.time,'monotonic',return_value=24.9):
        assert mirror.tick()=='ACTIVE_CHECKPOINT_STARTED' and not hanging.killed
    with patch.object(diagnostics.time,'monotonic',return_value=25.1):
        assert mirror.tick()=='ACTIVE_CHECKPOINT_TIMEOUT' and hanging.killed
        mirror.tick();assert mirror.process is None and mirror.disabled
    results.append({'case':'storage_budget_still_bounded_no_retry','status':'PASS','budgetSeconds':15})

result={'schema':'WORLD_ENGINE_INCIDENT_CONTROL_FOCUS_V1','status':'PASS','uid':os.getuid(),
    'cases':results,'gpuExecuted':False,'oldPassSuitesRerun':0,'realFUSETested':False}
(out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print('INCIDENT_CONTROL_RESULT='+json.dumps(result))
