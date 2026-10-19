"""One detached 150-frame job over the original GPU lease and native monitor.

No software validation is reachable from this production module. No retry,
container restart, status query or reconnect launches a second worker.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import importlib.util
import json
import os
import re
import subprocess
import stat
import sys
import time
HERE=Path(__file__).resolve().parent
RECOVERY=HERE.parent
ENV='WORLD_ENGINE_OVERNIGHT_REQUEST_FILE'
JOB=re.compile(r'studio-[a-f0-9]{32}\Z')
_RUNTIME=None


def load(name,path):
    spec=importlib.util.spec_from_file_location('_overnight_'+name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=value;spec.loader.exec_module(value);return value


def runtime():
    global _RUNTIME
    if _RUNTIME is None:
        path=Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt') else RECOVERY/'production-studio-mvp-v1'
        if str(path) not in sys.path:sys.path.insert(0,str(path))
        _RUNTIME=load('frozen_runtime',path/'studio_runtime.py')
    return _RUNTIME


def _bridge():return load('manager_bridge',HERE/'runtime_bridge.py')
def _manifest():return load('manager_manifest',HERE/'package_manifest.py')
def _stamp():return datetime.now(timezone.utc).isoformat()
def _safe(error):return runtime()._safe(error)


def _read_approval(path,plan):
    path=Path(path)
    with runtime()._cache().PrivateTree(path.parent) as root:value=root.json(path.name)
    # Original approval parser checks exact fields, source plan, image, expiry,
    # time/retry bounds and actual-rate budget arithmetic.
    return _approval_module().validate_approval(value,plan)


def _approval_module():
    directory=RECOVERY/'universal-auto-video-v2'
    before=list(sys.path)
    try:
        sys.path.insert(0,str(directory))
        return load('frozen_approval',directory/'orchestrator.py')
    finally:sys.path[:]=before


def preflight(submission,*,control_root,export_root,image_digest):
    # The original checks remain authoritative. They conservatively estimate
    # the whole source-plan disk budget; the capture CLI still emits only150.
    report=runtime().preflight(submission['videoPlan'],submission['profile'],
        control_root=control_root,export_root=export_root)
    return report


def start(submission,approval_path,sfx,request_id,*,control_root,export_root,image_digest):
    _bridge()._authorize_start(submission,control_root,image_digest)
    approval=_read_approval(approval_path,submission['videoPlan'])
    request=_bridge().prepare_runtime_request(submission,image_digest=image_digest,control_root=control_root)
    manifest=_manifest();cache=runtime()._cache()
    job_id='studio-'+manifest.sha(manifest.canonical({'requestId':request_id,'captureSignature':request['captureSignature']}))[:32]
    with cache.PrivateTree(Path(control_root)) as root:
        with root.child('overnight_jobs',create=True) as jobs:
            with jobs.lock():
                try: old=jobs.child(job_id)
                except FileNotFoundError: old=None
                if old is not None:
                    with old:return old.json('STATE.json')
                with jobs.child(job_id,create=True) as job:
                    for name,value in [('SUBMISSION.json',submission),('OVERNIGHT_REQUEST.json',request),
                        ('INTEGRATION_REQUEST.json',request['parentCaptureRequest']),
                        ('PREVIEW_REQUEST.json',request['preview']),('PLAN.json',submission['videoPlan']),
                        ('AUTHORIZATION.json',approval)]:job.write_json(name,value)
                    state={'schema':'WORLD_ENGINE_OVERNIGHT_JOB_V3','jobId':job_id,'state':'QUEUED',
                        'phase':'AUTHORIZED_PREVIEW_150','totalFrames':150,'processedFrames':0,
                        'totalScenes':len(request['preview']['sceneSlices']),'completedScenes':0,
                        'captureSignature':request['captureSignature'],'createdAt':_stamp(),'updatedAt':_stamp(),
                        'gpuRenderingVerified':False,'requiresGpu':True,'full80Allowed':False}
                    job.write_json('STATE.json',state)
                    log=os.open('worker.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=job.fd)
                    try:
                        child=subprocess.Popen([sys.executable,'-B',str(HERE/'execution_manager.py'),'--worker',job_id,
                            '--control-root',str(control_root),'--export-root',str(export_root)],stdin=subprocess.DEVNULL,
                            stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
                    finally:os.close(log)
                    job.write_json('PID.json',runtime()._manager().process_identity(child.pid))
    return state


def status(job_id,*,control_root,export_root):
    if not isinstance(job_id,str) or not JOB.fullmatch(job_id):raise RuntimeError('STUDIO_JOB_ID_INVALID')
    with runtime()._cache().PrivateTree(Path(control_root)) as root,root.child('overnight_jobs') as jobs,jobs.child(job_id) as job:
        state=job.json('STATE.json')
        if state['state']=='QUEUED' and not state.get('supervisorIdentity'):
            state['supervisorIdentity']=job.json('PID.json',optional=True)
    if state['state'] in {'QUEUED','RUNNING'} and state.get('supervisorIdentity'):
        if not runtime()._manager().is_alive(state['supervisorIdentity']):
            return {**state,'state':'INTERRUPTED','phase':'WORKER_NOT_ALIVE','errorCode':'STUDIO_OVERNIGHT_WORKER_INTERRUPTED'}
    return state


def _worker(job_id,control_root,export_root):
    if not JOB.fullmatch(job_id):raise RuntimeError('STUDIO_JOB_ID_INVALID')
    m=runtime();cache=m._cache();manifest=_manifest()
    with cache.PrivateTree(Path(control_root)) as root,root.child('overnight_jobs') as jobs,jobs.child(job_id) as job:
        # Hold a per-attempt lock for the entire worker. No second worker can
        # claim the same attempt, even if started outside the HTTP process.
        with job.lock(wait_seconds=1):
            state=job.json('STATE.json')
            if state['state'] not in {'QUEUED'}:raise RuntimeError('STUDIO_OVERNIGHT_DUPLICATE_WORKER_BLOCKED')
            started=time.monotonic()
            def save(**fields):
                state.update(**fields,updatedAt=_stamp(),elapsedSeconds=round(time.monotonic()-started,6))
                job.write_json('STATE.json',state,replace=True)
            try:
                submission=job.json('SUBMISSION.json');request=job.json('OVERNIGHT_REQUEST.json')
                image=request['imageDigest'];plan=submission['videoPlan']
                _bridge()._authorize_start(submission,control_root,image)
                actual=_bridge().prepare_runtime_request(submission,image_digest=image,control_root=control_root)
                if actual!=request:raise RuntimeError('STUDIO_OVERNIGHT_CAPTURE_IDENTITY_CHANGED')
                approval=_read_approval(job.path/'AUTHORIZATION.json',plan)
                start_time=datetime.now(timezone.utc)
                deadline=min(approval['maxWallSeconds']-(start_time-datetime.fromisoformat(state['createdAt'])).total_seconds(),
                    (datetime.fromisoformat(approval['validUntil'])-start_time).total_seconds())
                def remaining():
                    value=deadline-(time.monotonic()-started)
                    if value<1:raise RuntimeError('STUDIO_APPROVED_DEADLINE_EXCEEDED')
                    return value
                with _approval_module().deadline_guard(remaining()):
                    save(state='RUNNING',phase='ORIGINAL_GPU_ADMISSION',supervisorIdentity=m._manager().process_identity(os.getpid()))
                    adapter=load('frozen_v4_adapter',RECOVERY/'verified-front-data-v4-recovery/render_adapter.py')
                    os.environ['WORLD_ENGINE_INTEGRATION_REQUEST_FILE']=str(job.path/'INTEGRATION_REQUEST.json')
                    os.environ[ENV]=str(job.path/'OVERNIGHT_REQUEST.json')
                    with adapter.common_gpu_lease():
                        with job.child('prepared',create=True) as prepared:
                            adapter.prepare_job(plan,prepared.path,approval={**approval,'remainingWallSeconds':remaining()})
                        owner=adapter.parent;native=owner._SESSION['native'];gpu=native.gpu();inputs=owner._SESSION['inputs']
                        with job.child('native-admission',create=True) as private_admission:
                            config=gpu.LauncherConfig(storage_root=private_admission.path,budget_gib=8.,
                                render_timeout_seconds=min(14400,max(1,int(remaining()))))
                            admission=gpu.admit_gpu(config)
                        if admission.test_only or admission.safe_report.get('gpuRenderingVerified') is not True:
                            raise RuntimeError('TEST_ADMISSION_NOT_EXECUTABLE')
                        environment=dict(admission.environ,WORLD_ENGINE_ASTRA_ACTIVATION_FILE=str(inputs['activationFile']),
                            WORLD_ENGINE_ASTRA_ACTIVATION_SHA256=inputs['activationSha256'],
                            WORLD_ENGINE_INTEGRATION_REQUEST_FILE=str(job.path/'INTEGRATION_REQUEST.json'),
                            WORLD_ENGINE_OVERNIGHT_REQUEST_FILE=str(job.path/'OVERNIGHT_REQUEST.json'))
                        command=['node',str(HERE/'preview_capture.mjs'),'--request-file',str(job.path/'PREVIEW_REQUEST.json'),
                            '--plan-file',str(job.path/'PLAN.json'),'--plan-sha256',request['preview']['bindings']['originalPlanSHA256'],
                            '--admission-file',str(admission.admission_file),'--output-root',str(job.path/'capture')]
                        save(phase='GPU_PREVIEW_CAPTURE')
                        owner._run_native_capture(gpu,admission,config,command,environment,job.path/'native.log',
                            progress=lambda facts:save(processedFrames=min(150,facts.get('completedFrames',0))))
                    remaining()
                    _finish(job,submission,request,export_root,remaining,save)
            except Exception as error:
                save(state='FAILED',phase='PREVIEW_FAILED',errorCode=_safe(error),gpuRenderingVerified=False)
                raise
    return 0


def _seal_created_media(tree,name):
    # Exactly the original finalize policy, confined to this new job's files.
    if not isinstance(name,str) or Path(name).name!=name:
        raise RuntimeError('STUDIO_OVERNIGHT_NEW_MEDIA_NAME_INVALID')
    descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=tree.fd)
    try:
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or info.st_gid!=os.getegid() or info.st_nlink!=1):
            raise RuntimeError('STUDIO_OVERNIGHT_ARTIFACT_OWNER_INVALID')
        os.fchmod(descriptor,0o600)
    finally:os.close(descriptor)


def _finish(job,submission,request,export_root,remaining,save):
    """Reuse original audio scheduling/export; crop samples on the global clock."""
    import studio_delivery
    preview_audio=load('preview_audio',HERE/'preview_audio.py')
    m=runtime();cache=m._cache();r=request['preview']['range'];plan=submission['videoPlan']
    with job.child('capture') as capture:
        receipt=capture.json('PREVIEW_COMPLETE.json')
        if (receipt.get('range')!=r or receipt.get('requestSHA256')!=request['preview']['requestSHA256']
                or receipt.get('softwareProbe') is not False or receipt.get('hardwareVerified') is not True
                or receipt.get('fullDecodeVerified') is not True):
            raise RuntimeError('STUDIO_OVERNIGHT_PREVIEW_RECEIPT_INVALID')
        silent=Path(receipt.get('video',{}).get('path',''))
        if silent!=capture.path/'preview.mp4':
            raise RuntimeError('STUDIO_OVERNIGHT_PREVIEW_HASH_MISMATCH')
        _seal_created_media(capture,silent.name)
        if capture.hash_file(silent.name)['sha256']!=receipt.get('video',{}).get('sha256'):
            raise RuntimeError('STUDIO_OVERNIGHT_PREVIEW_HASH_MISMATCH')
        with job.child('post',create=True) as post,job.child('public',create=True) as public:
            wav=None
            if submission['sfx']['enabled']:
                preview_audio.render_preview_sfx(submission['sfx'],plan,request['preview'],post.path/'preview-sfx.wav')
                remaining();wav=post.path/'preview-sfx.wav'
            audio=preview_audio.mux_preview_sfx(silent,wav,public.path/'WORLD_ENGINE_STUDIO_VIDEO.mp4',plan,request['preview'])
            _seal_created_media(public,'WORLD_ENGINE_STUDIO_VIDEO.mp4')
            if wav is not None:_seal_created_media(post,wav.name)
            summary={'schema':'WORLD_ENGINE_STUDIO_SAFE_QA_V1','technicalVerification':'PASS','frames':150,
                'fps':30,'width':1080,'height':1920,'durationSeconds':5,'audioStreams':1 if wav else 0,
                'sfxEnabled':wav is not None,'videoDecodedPixelsUnchanged':True,'fullDecode':True,
                'visualQuality':'USER_VIDEO_REVIEW_REQUIRED','externalDownloadVerified':False,'finalPromotion':False}
            public.write_json('QUALITY_SUMMARY.json',summary)
            names=['WORLD_ENGINE_STUDIO_VIDEO.mp4','QUALITY_SUMMARY.json']
            checks=''.join(public.hash_file(name)['sha256']+'  '+name+'\n' for name in sorted(names))
            descriptor=os.open('SHA256SUMS',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=public.fd)
            try:
                cache.storage._write_all(descriptor,checks.encode());os.fsync(descriptor)
            finally:os.close(descriptor)
            save(phase='MOUNTED_EXPORT_VERIFICATION',processedFrames=150)
            result=studio_delivery.export_media(public.path,export_root,job.path)
    save(state='COMPLETED',phase='PREVIEW_EXPORTED',processedFrames=150,
        completedScenes=len(request['preview']['sceneSlices']),result=result,gpuRenderingVerified=True,
        externalDownloadVerified=False,visualQuality='USER_VIDEO_REVIEW_REQUIRED')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',required=True)
    parser.add_argument('--control-root',required=True,type=Path);parser.add_argument('--export-root',required=True,type=Path)
    args=parser.parse_args();raise SystemExit(_worker(args.worker,args.control_root,args.export_root))
