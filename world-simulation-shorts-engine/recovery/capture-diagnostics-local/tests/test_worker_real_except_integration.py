"""Execute the exact except handler AST from the existing worker draft with bounded fixtures."""
import ast, sys, tempfile, json, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
P=Path(__file__).resolve().parents[2]/'codex-to-gcube-handoff-v1/controller'
sys.path.insert(0,str(P))
source=ast.parse((P/'nvidia_worker.py').read_text())
fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_run')
outer=next(n for n in ast.walk(fn) if isinstance(n,ast.Try) and any(isinstance(h.type,ast.Name) and h.type.id=='BaseException' for h in n.handlers))
handler=next(h for h in outer.handlers if isinstance(h.type,ast.Name) and h.type.id=='BaseException')
# Retain original production exception handler unmodified, with local fixtures for dependencies.
wrapper=ast.FunctionDef(name='exercise',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='supervisor'),ast.arg(arg='cleanup_verified'),ast.arg(arg='job'),ast.arg(arg='exports'),ast.arg(arg='state'),ast.arg(arg='save')],vararg=None,kwonlyargs=[],kw_defaults=[],kwarg=None,defaults=[]),body=[ast.Try(body=[ast.Raise(exc=ast.Call(func=ast.Name(id='RuntimeError',ctx=ast.Load()),args=[ast.Constant(value='GCUBE_CAPTURE_RUNTIME_FAILED')],keywords=[]),cause=None)],handlers=[handler],orelse=[],finalbody=[])],decorator_list=[])
module=ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[]))
namespace={'_code':lambda e:str(e),'__builtins__':__builtins__}
exec(compile(module,'worker_original_exception_handler','exec'),namespace)
results={}
for case in ['cleanup_verified','cleanup_unverified','supervisor_alive','destination_exists','deadline_expired']:
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);job=root/('studio-'+'a'*32);(job/'capture').mkdir(parents=True); exports=root/'exports';exports.mkdir()
  (job/'FIRST_CAPTURE_FAILURE.json').write_text(json.dumps({'code':'GCUBE_CAPTURE_RUNTIME_FAILED','stage':'RENDER_RUNTIME','secret':'NEVER_EXPORT'}))
  (job/'LEASE_SUPERVISOR_RESULT.json').write_text(json.dumps({'reason':'GCUBE_CAPTURE_RUNTIME_FAILED','cleanupVerified':True,'secret':'NEVER_EXPORT'}))
  (job/'capture'/'CAPTURE_RECEIPT.json').write_text(json.dumps({'failure':{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','secret':'NEVER_EXPORT'}}))
  for f in job.rglob('*.json'):f.chmod(0o600)
  dest=exports/('capture-diagnostic-'+job.name)
  if case=='destination_exists':dest.mkdir()
  state={'executionDeadline':(datetime.now(timezone.utc)+timedelta(seconds=-1 if case=='deadline_expired' else 60)).isoformat()}
  states=[]
  class FakeSupervisor:
   def poll(self):return None if case=='supervisor_alive' else 1
  def save(**kw):states.append(kw)
  try:namespace['exercise'](FakeSupervisor(),case not in ['cleanup_unverified'],job,exports,state,save)
  except RuntimeError as exc:assert str(exc)=='GCUBE_CAPTURE_RUNTIME_FAILED'
  else:raise AssertionError('original error swallowed')
  exists=(dest/'CAPTURE_DIAGNOSTIC.json').exists()
  assert exists==(case=='cleanup_verified'),(case,exists)
  assert states and states[0]['state']==('RUNNING' if case in ['cleanup_unverified','supervisor_alive'] else 'FAILED')
  if exists:
   b=(dest/'CAPTURE_DIAGNOSTIC.json').read_bytes()
   assert b'NEVER_EXPORT' not in b
   expected=hashlib.sha256(b).hexdigest()
   assert (dest/'SHA256SUMS').read_text().startswith(expected)
  results[case]='PASS'
print(json.dumps(results,sort_keys=True))
