"""Copy-on-write native visual resources; original private assets remain intact."""
from pathlib import Path
import hashlib,json,re,sys
sha=lambda b:hashlib.sha256(b).hexdigest()
def prepare(prior,pin,visual,native,destination):
 prior,visual,native,out=map(Path,[prior,visual,native,destination]);raw=prior.read_bytes()
 assert sha(raw)==pin and not out.exists(),'PRIOR_PIN_OR_NEW_DESTINATION'
 data=json.loads(raw);assert data['productionAdmitted'] is False and data['mode']=='CPU_QUALIFIED_GPU_PENDING'
 sources={
 '/web/map_infographic_v1/official_material_shader.mjs':visual/'official_material_shader.mjs',
 '/recovery/universal-presentation-v2/presentation_label_layer.mjs':visual/'presentation_label_layer.mjs',
 '/recovery/universal-presentation-v2/presentation_plan.mjs':visual/'presentation_plan.mjs',
 '/recovery/universal-presentation-v2/presentation_runtime.mjs':native/'official-candidate-v1/presentation_runtime_nvidia.generated.mjs'}
 source_bytes={u:p.read_bytes() for u,p in sources.items()};shader=source_bytes['/web/map_infographic_v1/official_material_shader.mjs']
 new_shader=re.search(rb'export const SHADER_SHA256="([0-9a-f]{64})";',shader).group(1).decode()
 old_shader='a12cbde55d19c0624f71b71d5cb997323104d6daac381fde2f59f9d644a7f09f'
 out.mkdir(mode=0o700,parents=True);files={};changes=[]
 def emit(raw):
  h=sha(raw);p=out/(h+'.mjs')
  if not p.exists():p.write_bytes(raw);p.chmod(0o600)
  return str(p.resolve()),{'sha256':h,'bytes':len(raw)}
 for u,b in source_bytes.items():files[u]=emit(b)
 for registration in data['registrations']:
  r=registration['record'];assert r['shaderSha256']==old_shader and r['productionAdmitted'] is False
  r['shaderSha256']=new_shader
  for resource in r['resources']:
   u=resource['url']
   if u in files:resource['sourcePath'],resource['pin']=files[u]
   elif u=='/web/map_infographic_v1/official_candidate_registration.mjs':
    b=Path(resource['sourcePath']).read_bytes();assert sha(b)==resource['pin']['sha256'] and old_shader.encode() in b
    b=b.replace(old_shader.encode(),new_shader.encode());resource['sourcePath'],resource['pin']=emit(b)
  assert set(sources)<=set(x['url'] for x in r['resources'])
  changes.append(registration['id'])
 new=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert len(new)<24*1024**2
 target=out/'OFFICIAL_NATIVE_REGISTRY.json';target.write_bytes(new);target.chmod(0o600)
 return {'schema':'WORLD_ENGINE_NATIVE_VISUAL_REGISTRY_V1','status':'PREPARED_INACTIVE','priorRegistrySHA256':pin,'registrySHA256':sha(new),'registryBytes':len(new),'scenes':len(changes),'resourcesReplacedPerScene':4,'fixedShaderRegistrationModules':len(changes),'sourcePixelsChanged':False,'sourcePixelsRecopied':False,'heightWindowsUnchanged':True,'privateActivation':False,'gpuExecuted':False,'productionInstallationVerified':False}
if __name__=='__main__':
 if len(sys.argv)!=6:raise SystemExit('PRIOR EXPECTED_SHA VISUAL_MODULES NATIVE_RECOVERY NEW_PRIVATE_DIRECTORY')
 print(json.dumps(prepare(*sys.argv[1:]),indent=2))
