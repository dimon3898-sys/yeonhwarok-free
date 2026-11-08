"""Create an inactive private NVIDIA registry from a pinned prior registry.
Original files are never overwritten. No activation, browser, worker or network.
"""
from pathlib import Path
import hashlib,json,sys

def prepare(source, expected, candidate_recovery, destination):
 source=Path(source);raw=source.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('PRIOR_REGISTRY_PIN_CHANGED')
 data=json.loads(raw);target=Path(destination)
 if target.exists(): raise ValueError('NEW_DESTINATION_REQUIRED')
 target.mkdir(mode=0o700,parents=True)
 resources=[]
 for relative,url in [
  ('official-candidate-v1/presentation_runtime_nvidia.generated.mjs','/recovery/universal-presentation-v2/presentation_runtime.mjs'),
  ('codex-to-gcube-handoff-v1/backend/native_guard_candidate.mjs','/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs')]:
  b=(Path(candidate_recovery)/relative).read_bytes();digest=hashlib.sha256(b).hexdigest();file=target/(digest+'.mjs')
  file.write_bytes(b);file.chmod(0o600)
  resources.append({'url':url,'kind':'module','mime':'text/javascript','sourcePath':str(file.resolve()),'pin':{'bytes':len(b),'sha256':digest}})
 for registration in data['registrations']:
  r=registration['record']
  if r['mode']!='CPU_QUALIFIED_GPU_PENDING' or r['productionAdmitted'] is not False: raise ValueError('PRIOR_REGISTRY_SCOPE')
  for new in resources:
   r['resources']=[old for old in r['resources'] if old['url']!=new['url']]+[new]
 out=target/'OFFICIAL_NATIVE_REGISTRY.json';out.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');out.chmod(0o600)
 return {'schema':'WORLD_ENGINE_NATIVE_REGISTRY_PREPARATION_V1','status':'PREPARED_INACTIVE','registrations':len(data['registrations']),
  'priorRegistrySHA256':expected,'registrySHA256':hashlib.sha256(out.read_bytes()).hexdigest(),
  'replacedRuntimeResources':len(data['registrations']),'addedNativeGuards':len(data['registrations']),
  'resourcePins':[{k:r[k] for k in ('url','pin')} for r in resources],
  'activated':False,'gpuExecuted':False,'visualQualityApproved':False}
if __name__=='__main__':
 if len(sys.argv)!=5: raise SystemExit('SOURCE EXPECTED_SHA CANDIDATE_RECOVERY NEW_PRIVATE_DESTINATION')
 print(json.dumps(prepare(*sys.argv[1:]),indent=2))
