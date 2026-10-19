"""Versioned metadata/identity handoff into unchanged detached/GPU managers.

All render paths are source/data/image/quality/cost gated before private worker
records are created. Current supplied data fails those prerequisites. This
module does not grant approval or create a workload.
"""
from __future__ import annotations
from contextlib import contextmanager
import importlib.util,json,os,sys,threading
from pathlib import Path
HERE=Path(__file__).resolve().parent
ENV='WORLD_ENGINE_INTEGRATION_REQUEST_FILE'
_LOCK=threading.RLock()
_RUNTIME=None


def _module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
 sys.modules[name]=m;spec.loader.exec_module(m);return m


def runtime():
 global _RUNTIME
 if _RUNTIME is None:
  original=HERE.parent/'production-studio-mvp-v1/studio_runtime.py'
  # Verify both new and frozen sources before loading a fresh private instance.
  manifest=_module('_integration_execution_manifest',HERE/'package_manifest.py');manifest.verify_sources()
  original=manifest.parent_path('production-studio-mvp-v1/studio_runtime.py')
  if str(original.parent) not in sys.path:sys.path.insert(0,str(original.parent))
  # Frozen post-production has lazy bare imports; verify/resolve those here.
  import importlib
  for name in ['studio_audio','studio_delivery','studio_common']:
   helper=importlib.import_module(name)
   if Path(helper.__file__).resolve().parent!=original.parent.resolve():raise RuntimeError('INTEGRATION_PARENT_HELPER_ORIGIN_INVALID')
  _RUNTIME=_module('_integration_fresh_studio_runtime',original)
  _RUNTIME.HERE=HERE
  _RUNTIME.PROFILES=dict(_RUNTIME.PROFILES,V4_ARCHIVAL_80S='universal-integration-v1')
 return _RUNTIME


def read_request():
 value=os.environ.get(ENV)
 if not value:raise RuntimeError('INTEGRATION_PRIVATE_REQUEST_REQUIRED')
 m=runtime();path=Path(value)
 if not path.is_absolute() or path.name!='INTEGRATION_REQUEST.json':raise RuntimeError('INTEGRATION_PRIVATE_REQUEST_UNSAFE')
 with m._cache().PrivateTree(path.parent) as root:request=root.json(path.name)
 if request.get('schema')!='WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1' or request.get('oldCacheReuseAllowed') is not False:
  raise RuntimeError('INTEGRATION_PRIVATE_REQUEST_INVALID')
 fixed={k:v for k,v in request.items() if k not in {'captureSignature','globalGPUAdmissionRequired','rendererOutputVerified'}}
 if m._cache().canonical_sha256(fixed)!=request.get('captureSignature'):
  raise RuntimeError('INTEGRATION_PRIVATE_REQUEST_CHANGED')
 return request


@contextmanager
def request_environment(file):
 with _LOCK:
  previous=os.environ.get(ENV);os.environ[ENV]=str(file)
  try:yield
  finally:
   if previous is None:os.environ.pop(ENV,None)
   else:os.environ[ENV]=previous


def start(submission,approval_path,sfx,request_id,*,control_root,export_root,image_digest):
 # Caller has evaluated the authoritative full-video gate. The bridge repeats
 # that gate for direct code callers before invoking this internal primitive.
 bridge=_module('_integration_start_bridge',HERE/'runtime_bridge.py')
 bridge._authorize_start(submission,control_root,image_digest)
 m=runtime()
 request=bridge.prepare_runtime_request(submission,image_digest=image_digest)
 with m._cache().PrivateTree(Path(control_root)) as root:
  with root.child('runtime_inputs',create=True) as inputs:
   with inputs.child(request['captureSignature'],create=True) as scoped:
    old=scoped.json('INTEGRATION_REQUEST.json',optional=True)
    if old is None:scoped.write_json('INTEGRATION_REQUEST.json',request)
    elif old!=request:raise RuntimeError('INTEGRATION_IMMUTABLE_REQUEST_COLLISION')
    file=scoped.path/'INTEGRATION_REQUEST.json';runtime_root=scoped.path
 with request_environment(file):
  scoped_request=m._cache().canonical_sha256({'requestId':request_id,'captureSignature':request['captureSignature']})
  state=m.start_studio_job(submission['videoPlan'],submission['profile'],approval_path,sfx,scoped_request,
   control_root=runtime_root,export_root=export_root)
 _index_job(control_root,state['jobId'],request['captureSignature'])
 return state


def _index_job(control_root,job_id,signature):
 m=runtime()
 if not m.JOB.fullmatch(job_id) or len(signature)!=64 or any(c not in '0123456789abcdef' for c in signature):raise RuntimeError('INTEGRATION_JOB_INDEX_INVALID')
 value={'schema':'WORLD_ENGINE_INTEGRATION_JOB_SCOPE_V1','jobId':job_id,'captureSignature':signature}
 with m._cache().PrivateTree(Path(control_root)) as root:
  with root.child('runtime_jobs',create=True) as jobs:
   with jobs.lock():
    old=jobs.json(job_id+'.json',optional=True)
    if old is None:jobs.write_json(job_id+'.json',value)
    elif old!=value:raise RuntimeError('INTEGRATION_JOB_SCOPE_COLLISION')


def job_scope(control_root,job_id):
 m=runtime()
 if not isinstance(job_id,str) or not m.JOB.fullmatch(job_id):raise RuntimeError('INTEGRATION_JOB_ID_INVALID')
 with m._cache().PrivateTree(Path(control_root)) as root:
  with root.child('runtime_jobs') as jobs:record=jobs.json(job_id+'.json')
 signature=record.get('captureSignature')
 if record.get('schema')!='WORLD_ENGINE_INTEGRATION_JOB_SCOPE_V1' or record.get('jobId')!=job_id or not isinstance(signature,str) or len(signature)!=64 or any(c not in '0123456789abcdef' for c in signature):raise RuntimeError('INTEGRATION_JOB_INDEX_INVALID')
 scope=Path(control_root)/'runtime_inputs'/signature
 with request_environment(scope/'INTEGRATION_REQUEST.json'):
  if read_request()['captureSignature']!=signature:raise RuntimeError('INTEGRATION_JOB_SCOPE_COLLISION')
 return scope


def status(job_id,*,control_root,export_root):
 scope=job_scope(control_root,job_id)
 with request_environment(scope/'INTEGRATION_REQUEST.json'):
  return runtime().studio_status(job_id,control_root=scope,export_root=export_root)


def authorize_request(plan=None):
 request=read_request();m=runtime();scope=Path(os.environ[ENV]).parent
 if scope.parent.name!='runtime_inputs' or scope.name!=request['captureSignature']:raise RuntimeError('INTEGRATION_CAPTURE_SCOPE_INVALID')
 profile='V4_ARCHIVAL_80S'
 if plan is None:plan=m.bind_render_image(m.default_plan(profile),profile,request['imageDigest'])
 if m._cache().canonical_sha256(plan)!=request['videoPlanSHA256']:raise RuntimeError('INTEGRATION_CAPTURE_PLAN_BINDING_REQUIRED')
 bridge=_module('_integration_worker_authority',HERE/'runtime_bridge.py')
 return bridge._authorize_start({'videoPlan':plan,'profile':profile,'integration':request['integration']},scope.parent.parent,request['imageDigest'])


def recover(job_id,approval_path,request_id,*,control_root,export_root,image_digest):
 scope=job_scope(control_root,job_id);m=runtime()
 with request_environment(scope/'INTEGRATION_REQUEST.json'):
  with m._cache().PrivateTree(scope) as root:
   with root.child(job_id) as job:plan=job.json('PLAN.json')
  authorize_request(plan)
  state=m.start_studio_recovery(job_id,approval_path,request_id,control_root=scope,export_root=export_root)
 _index_job(control_root,state['jobId'],scope.name);return state


if __name__=='__main__':raise SystemExit('INTEGRATION_NO_DIRECT_PUBLIC_EXECUTION')
