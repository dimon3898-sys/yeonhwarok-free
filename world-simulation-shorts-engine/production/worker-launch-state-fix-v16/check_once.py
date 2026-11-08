"""CPU-only regression: force the parent/worker publication interleaving.

Executes the actual worker _run and backend studio_status with the frozen
PrivateTree and real /proc identity. Only GPU/approval and capture-launch
boundaries are stubbed. No renderer, encoder or original PASS suite is run.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
CONTROLLER = HERE.parents[1]/'recovery/codex-to-gcube-handoff-v1/controller'
sys.path.insert(0, str(CONTROLLER))
import nvidia_backend as backend
import capture_diagnostics_safe as diagnostics
from lease_supervisor import parent_identity

class Boundary(Exception): pass

def execute(source, case):
    spec = importlib.util.spec_from_file_location('tested_worker', source)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    frozen = backend.cache()
    root = Path(tempfile.mkdtemp(prefix='world-engine-launch-', dir='/opt'))
    job_id = 'studio-' + 'a'*32
    job = root/'handoff-gpu-jobs'/job_id
    job.parent.mkdir(mode=0o700); job.mkdir(mode=0o700)
    identity = parent_identity(os.getpid())
    published = {'pid': identity['pid'], 'processStart': identity['startTicks']}
    state = dict(jobId=job_id, state='QUEUED', phase='SOURCE_VERIFY',
        processedFrames=0, completedScenes=0, totalFrames=300, totalScenes=2,
        executionDeadline=(datetime.now(timezone.utc)+timedelta(seconds=600)).isoformat())
    if case == 'already_published': state.update(published)
    plan = dict(renderProfile={'imageDigest':'sha256:'+'1'*64}, runtimeWireJSON='{}',
                durationSeconds=10, totalFrames=300, fps=30,
                runtime={'segments':[{'endFrame':150}, {'endFrame':300}]})
    with frozen.PrivateTree(job) as directory:
        for name, value in [('PLAN.json',plan),('APPROVAL.json',{}),('state.json',state)]:
            directory.write_json(name,value)
    observed = {'case':case,'leaseEntries':0,'captureLaunches':0}
    write_runtime = worker._write_runtime
    def publish_after_worker_read(path, wire):
        write_runtime(path, wire)
        receipt = dict(published)
        final_state = dict(state, **published)
        if case == 'receipt_pid_mismatch': receipt['pid'] += 1
        if case == 'receipt_start_mismatch': receipt['processStart'] = '0'
        if case == 'state_identity_mismatch': final_state['processStart'] = '0'
        if case == 'state_job_mismatch': final_state['jobId'] = 'studio-'+'b'*32
        with frozen.PrivateTree(path) as directory:
            directory.write_json('state.json', final_state, replace=True)
            directory.write_json('launch.json', receipt)
    def lease(*args):
        observed['leaseEntries'] += 1
        return nullcontext()
    def capture_boundary(*args, **kwargs):
        observed['captureLaunches'] += 1
        with frozen.PrivateTree(job) as directory:
            current = directory.json('state.json')
            observed['savedIdentity'] = {k:current.get(k) for k in ('pid','processStart')}
            # Progress is orthogonal to worker identity. Exercise the exact
            # status method at the user-observed count without drawing frames.
            current.update(processedFrames=158, completedScenes=1)
            directory.write_json('state.json',current,replace=True)
        view = backend.NvidiaPresentationBackend.studio_status(object(), job_id,
                      control_root=root,export_root=root/'exports')
        observed['statusPhase'] = view['phase']
        observed['statusError'] = view.get('errorCode')
        observed['actualWorkerAlive'] = Path('/proc') .joinpath(str(os.getpid()),'stat').is_file()
        raise Boundary('CPU_CAPTURE_BOUNDARY_STOP')
    fake_backend = lambda *args: SimpleNamespace(_verify=lambda *args: None)
    fake_original = SimpleNamespace(storage=SimpleNamespace(PRIVATE_BASE=root))
    fake_mirror = lambda *args: SimpleNamespace(close=lambda:None)
    args=SimpleNamespace(job_root=str(job),control_root=str(root),export_root=str(root/'exports'),
        plan_sha256=worker.sha(worker.canonical(plan)),manifest_file='UNUSED_CPU_FIXTURE',manifest_sha256='0'*64)
    with patch.object(worker,'NvidiaPresentationBackend',fake_backend), \
         patch.object(worker,'approval_limit',lambda *args:None), \
         patch.object(worker,'_write_runtime',publish_after_worker_read), \
         patch.object(worker,'lease_helper',lambda:fake_original), \
         patch.object(worker,'keep_original_lease_until_cleanup',lease), \
         patch.object(worker,'original_lease_descriptor',lambda *args:123), \
         patch.object(worker.subprocess,'Popen',capture_boundary), \
         patch.object(diagnostics,'ActiveCheckpointMirror',fake_mirror), \
         patch.object(diagnostics,'preserve_before_cleanup',lambda *args:None):
        try: worker._run(args)
        except Boundary: observed['stoppedAt']='CPU_CAPTURE_BOUNDARY'
        except RuntimeError as error: observed['stoppedAt']=str(error)
    observed['fixtureDirectory']=str(root)
    return observed

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--baseline',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cases=['interleaved'] if args.baseline else ['interleaved','already_published',
        'receipt_pid_mismatch','receipt_start_mismatch','state_identity_mismatch','state_job_mismatch']
    rows=[]
    for case in cases:
        row=execute(args.source.resolve(),case)
        if args.baseline:
            assert row['actualWorkerAlive'] and row['savedIdentity']=={'pid':None,'processStart':None}, row
            assert row['statusError']=='HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS', row
        elif case in ('interleaved','already_published'):
            assert row['actualWorkerAlive'] and row['savedIdentity']['pid']==os.getpid(), row
            assert row['statusPhase']=='CAPTURE' and row['statusError'] is None, row
        else:
            assert row['stoppedAt']=='HANDOFF_LAUNCH_IDENTITY_MISMATCH', row
            assert row['leaseEntries']==row['captureLaunches']==0, row
        row['status']='PASS';rows.append(row)
    result={'status':'REPRODUCED' if args.baseline else 'PASS',
        'sourceSHA256':hashlib.sha256(args.source.read_bytes()).hexdigest(), 'tests':rows,
        'scope':'NEW_WORKER_LAUNCH_PUBLICATION_RACE_ONLY', 'oldPASSReruns':0,
        'gpuStarts':0,'rendererExecutions':0,'mediaEncodes':0,
        'incidentAttribution':'Possible matching cause; original incident state/launch unavailable'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
