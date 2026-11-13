"""Pin only new registered-camera dependencies and the changed NVIDIA adapters."""
from pathlib import Path
import hashlib,json,re,subprocess
P=Path(__file__).resolve().parent;E=P.parents[1];R=E.parent;REC=E/'recovery';BASE='0f6a73b'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def row(p):return {'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)}
changed=set(subprocess.check_output(['git','diff',BASE,'--name-only'],cwd=R,text=True).splitlines())
variantFile=REC/'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json';g=json.loads(variantFile.read_text());verifier=variantFile.parent/'capture_nvidia.mjs';code=verifier.read_text()
for v in g['variants']:
 original=R/v['original'];new=sha(original);old=v['originalSHA256'];assert code.count(old)==1;code=code.replace(old,new);v['originalSHA256']=new;v['variantSHA256']=sha(variantFile.parent.parent/v['variant'])
g['coreRendererChanged']=True;g['registeredGeographicCamera']={'sourceBaseCommit':BASE,'actualGPUValidation':'NOT_RUN','CPUVisualValidation':'PENDING','privateWorkspaceAndDiagnosticsPreserved':True};save(variantFile,g);verifier.write_text(code)
changed.update(str(p.relative_to(R))for p in [variantFile,verifier])
m=REC/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json';d=json.loads(m.read_text());updated=[]
for r in d['files']:
 if r['path'] in changed:r.update(row(R/r['path']));updated.append(r['path'])
extras=[E/'web/map_infographic_v1/geographic_camera_v1.mjs',REC/'universal-presentation-v2/geographic_terrain_source.mjs',P/'REFERENCE_6S_REGISTERED_INPUT.json',P/'REGISTERED_RUNTIME_REQUEST.json']
for name in ['NATIVE_COUNTRY_OVERRIDES.json','TERRAIN_PYRAMID.json','SOURCE_USE.json','GEOTIFF_REGISTRATION.json','overview.png','regional.png','detail.png']:extras.append(P/'sources'/name)
known={r['path'] for r in d['files']}
for p in extras:
 if str(p.relative_to(R)) not in known:d['files'].append(row(p));updated.append(str(p.relative_to(R)))
d['files'].sort(key=lambda r:r['path']);save(m,d)
b=REC/'studio-cold-start-v2/bootstrap.py';s,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$","SOURCE_SHA = '"+sha(m)+"'",b.read_text());assert n==1;b.write_text(s)
st=b.parent/'STARTUP_MANIFEST.json';d=json.loads(st.read_text());d['runtimeManifestSHA256']=sha(m);d['files']['bootstrap.py']={k:v for k,v in row(b).items() if k!='path'};save(st,d)
save(P/'REGISTERED_SOURCE_PIN_DELTA.json',{'status':'PINS_UPDATED_GPU_NOT_EXECUTED','updatedRuntimeRows':updated,'runtimeManifestSHA256':sha(m),'startupManifestSHA256':sha(st),'originalPassReexecutions':0,'GPUExecutions':0})
print('Pinned',len(updated),'runtime rows')
