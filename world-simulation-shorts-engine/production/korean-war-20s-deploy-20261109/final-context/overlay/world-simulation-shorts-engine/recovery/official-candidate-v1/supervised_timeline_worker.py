"""Independent owner of the sealed300 worker; never a renderer/admission bypass."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
from owned_job_supervisor import OwnedJobSupervisor
from timeline_worker import validate_timeline
from candidate_activation_contract import verify_candidate_result

HERE = Path(__file__).resolve().parent

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def validate_supervised_package(raw, expected, job_id, expires_at):
    if len(raw)>24*1024**2 or sha(raw)!=expected:
        raise RuntimeError('UP2_SUPERVISOR_PACKAGE_HASH')
    package=json.loads(raw)
    pipeline, receipt=package.get('sourcePipeline',{}),package.get('executionReceipt',{})
    admission=pipeline.get('sourceAdmission',{})
    wire=admission.get('sourceQualificationWireJSON')
    if (pipeline.get('totalFrames')!=300 or pipeline.get('durationSeconds')!=10
            or package.get('schema')!='WORLD_ENGINE_PRESENTATION_STUDIO_SUBMISSION_V2'
            or receipt.get('jobId')!=job_id or receipt.get('maxWallSeconds')!=900
            or receipt.get('expiresAt')!=expires_at or receipt.get('softwareOnly') is not True
            or admission.get('status')!='PASS' or admission.get('preparedBeforeClaim') is not True
            or not isinstance(wire,str) or sha(wire.encode())!=admission.get('sourceQualificationSHA256')
            or json.loads(wire)!=admission.get('sourceQualification')):
        raise RuntimeError('UP2_SUPERVISOR_SEALED300_REQUIRED')
    validate_timeline(pipeline,sha,canonical)
    return package

def supervise(*, command, deadline, guard_factory, cancelled, publish, fail,
              supervisor_factory=OwnedJobSupervisor):
    owner=supervisor_factory(deadline=deadline,guard_factory=guard_factory,cancelled=cancelled)
    try:
        owner.run(command)
        cleanup=owner.assert_complete()
        # Publication is owned here, never by the inner worker.
        publish(cleanup)
        return cleanup
    except BaseException as error:
        fail(error,{'state':'INCOMPLETE' if owner.active is not None or any(r['state']!='COMPLETE' for r in owner.records) else 'COMPLETE','children':owner.records})
        raise

def main(args):
    started=time.monotonic()
    if args.max_wall_seconds!=900:
        raise RuntimeError('UP2_SUPERVISOR_DEADLINE_INVALID')
    expires=datetime.fromisoformat(args.expires_at.replace('Z','+00:00'))
    if expires.tzinfo is None:
        raise RuntimeError('UP2_SUPERVISOR_EXPIRY_REQUIRED')
    deadline=started+min(900,(expires-datetime.now(timezone.utc)).total_seconds())
    job=args.job_root
    if (not job.is_absolute() or not job.is_dir() or any(p.is_symlink() for p in (job,*job.parents))
            or job.stat().st_uid!=os.getuid() or job.stat().st_mode&0o077):
        raise RuntimeError('UP2_WORKER_PRIVATE_STATE_REQUIRED')
    package_file=job/'compiledpackage.json'
    if package_file.is_symlink():raise RuntimeError('UP2_SUPERVISOR_PACKAGE_UNSAFE')
    with package_file.open('rb') as file:raw=file.read(24*1024**2+1)
    package=validate_supervised_package(raw,args.plan_sha256,job.name,args.expires_at)
    spec=importlib.util.spec_from_file_location('_up2_outer_preserved_utilities',HERE.parent/'universal-data-pipeline-v1/software_worker.py')
    utilities=importlib.util.module_from_spec(spec);sys.modules[spec.name]=utilities;spec.loader.exec_module(utilities)
    cancelled=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:cancelled.set())
    def publish(cleanup):
        pending=job/'pending-result.json'
        if pending.is_symlink():raise RuntimeError('UP2_SUPERVISOR_PENDING_UNSAFE')
        result=json.loads(pending.read_bytes());state=json.loads((job/'state.json').read_bytes())
        if (cancelled.is_set() or time.monotonic()>=deadline-5 or result.get('jobId')!=job.name
                or result.get('state')!='COMPLETED' or state.get('state')!='AWAITING_SUPERVISOR'):
            raise RuntimeError('UP2_SUPERVISOR_PUBLICATION_BLOCKED')
        verify_candidate_result(package['sourcePipeline'],result,sha,canonical)
        utilities.atomic(job/'outer-cleanup.json',cleanup)
        utilities.atomic(job/'result.json',result)
        state.update(state='COMPLETED',phase='PRESENTATION_SOFTWARE_REVIEW_COMPLETE')
        utilities.atomic(job/'state.json',state)
        pending.unlink()
    def fail(error,cleanup):
        for name in ('pending-result.json','result.json'):(job/name).unlink(missing_ok=True)
        (args.export_root/job.name/'CAPTURE_RECEIPT.json').unlink(missing_ok=True)
        state=json.loads((job/'state.json').read_bytes())
        state.update(state='FAILED',phase='OUTER_WORKER_SUPERVISION',errorCode='UP2_OUTER_WORKER_FAILED')
        utilities.atomic(job/'outer-cleanup.json',cleanup);utilities.atomic(job/'state.json',state)
    return supervise(command=[sys.executable,str(HERE/'software_worker.py'),'--job-root',str(job),
        '--export-root',str(args.export_root),'--plan-sha256',args.plan_sha256,'--defer-result'],
        deadline=deadline,guard_factory=utilities.DescendantGuard,cancelled=cancelled.is_set,publish=publish,fail=fail)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--job-root',type=Path,required=True);parser.add_argument('--export-root',type=Path,required=True)
    parser.add_argument('--plan-sha256',required=True);parser.add_argument('--expires-at',required=True)
    parser.add_argument('--max-wall-seconds',type=int,required=True)
    main(parser.parse_args())
