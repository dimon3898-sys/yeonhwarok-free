import ast, tempfile, json, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
p=Path(__file__).resolve().parents[2]/'codex-to-gcube-handoff-v1/controller'
sys.path.insert(0,str(p))
from capture_diagnostics_safe import export_after_cleanup
worker=(p/'nvidia_worker.py').read_text()
tree=ast.parse(worker)
assert any(isinstance(n,ast.ImportFrom) and n.module=='capture_diagnostics_safe' for n in ast.walk(tree))
assert "if not unresolved and cleanup_verified:" in worker
assert "state['executionDeadline']" in worker
results={}
for case in ['failure_with_receipt','failure_without_receipt','invalid_failure_fields','expired_deadline']:
 with tempfile.TemporaryDirectory() as d:
  root=Path(d); job=root/('studio-'+'a'*32);(job/'capture').mkdir(parents=True); exports=root/'exports';exports.mkdir()
  (job/'FIRST_CAPTURE_FAILURE.json').write_text(json.dumps({'code':'GCUBE_CAPTURE_RUNTIME_FAILED' if case!='invalid_failure_fields' else 'SENSITIVE password=123', 'stage':'RENDER_RUNTIME','secret':'NEVER_EXPORT'}))
  (job/'LEASE_SUPERVISOR_RESULT.json').write_text(json.dumps({'reason':'GCUBE_CAPTURE_RUNTIME_FAILED','cleanupVerified':True,'secret':'NEVER_EXPORT'}))
  if case=='failure_with_receipt':(job/'capture'/'CAPTURE_RECEIPT.json').write_text(json.dumps({'failure':{'code':'GCUBE_CAPTURE_RUNTIME_FAILED','secret':'NEVER_EXPORT'}}))
  for f in job.rglob('*.json'):f.chmod(0o600)
  deadline=(datetime.now(timezone.utc)+timedelta(seconds=-1 if case=='expired_deadline' else 60)).isoformat()
  if case=='expired_deadline':
   try:export_after_cleanup(job,exports,deadline)
   except TimeoutError:results[case]='PASS';continue
   raise AssertionError('expired deadline accepted')
  output=export_after_cleanup(job,exports,deadline)
  target=exports/('capture-diagnostic-'+job.name)/'CAPTURE_DIAGNOSTIC.json'
  b=target.read_bytes();data=json.loads(b)
  assert b'NEVER_EXPORT' not in b and b'password' not in b
  assert output['status']=='EXPORTED'
  assert (target.parent/'SHA256SUMS').read_text().startswith(hashlib.sha256(b).hexdigest())
  assert data['missingEvidence']['capture']==(case!='failure_with_receipt')
  if case=='invalid_failure_fields':assert data['firstFailure']['code'] is None
  assert data['supervisor']['cleanupVerified'] is True
  before=target.read_bytes()
  assert export_after_cleanup(job,exports,deadline)['status']=='EXPORT_FAILED'
  assert target.read_bytes()==before
  results[case]='PASS'
print(json.dumps(results,sort_keys=True))
