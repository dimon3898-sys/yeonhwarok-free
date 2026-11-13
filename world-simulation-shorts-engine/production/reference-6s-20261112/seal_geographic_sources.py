"""Update only source pins invalidated by the GEOGRAPHIC connection.
No build, GPU execution, renderer regeneration or historical PASS replay.
"""
from pathlib import Path
import hashlib,json,re,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REC=ROOT/'world-simulation-shorts-engine/recovery'
BASE='c75478463085aea8c2689044636fce4ac9f4975e'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def row(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':digest(p)}
changed=set(subprocess.check_output(['git','diff',BASE,'--name-only'],cwd=ROOT,text=True).splitlines())
variants=REC/'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json'
verifier=variants.parent/'capture_nvidia.mjs'
g=json.loads(variants.read_text());v=verifier.read_text()
for r in g['variants']:
    if r['original'] not in changed:continue
    old=r['originalSHA256'];new=digest(ROOT/r['original'])
    assert v.count(old)==1
    v=v.replace(old,new)
    r['originalSHA256']=new
    r['variantSHA256']=digest(variants.parent.parent/r['variant'])
g['geographicConnection']={'sourceBaseCommit':BASE,'actualGPUValidation':'NOT_RUN','cpuVisualValidation':'NOT_RUN','oldDiagnosticsPreserved':True}
save(variants,g);verifier.write_text(v)
changed.update(str(p.relative_to(ROOT)) for p in [variants,verifier])
manifest=REC/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
j=json.loads(manifest.read_text());updated=[]
for r in j['files']:
    if r['path'] in changed:
        r.update(row(ROOT/r['path']));updated.append(r['path'])
extras=[REC/'universal-data-pipeline-v1/reviewed_geographic_registry.mjs',REC/'universal-data-pipeline-v1/evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json']
known={r['path'] for r in j['files']}
for p in extras:
    if str(p.relative_to(ROOT)) not in known:j['files'].append(row(p));updated.append(str(p.relative_to(ROOT)))
j['files'].sort(key=lambda r:r['path']);save(manifest,j)
bootstrap=REC/'studio-cold-start-v2/bootstrap.py'
s,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$","SOURCE_SHA = '"+digest(manifest)+"'",bootstrap.read_text());assert n==1
bootstrap.write_text(s)
startup=bootstrap.parent/'STARTUP_MANIFEST.json';s=json.loads(startup.read_text());s['runtimeManifestSHA256']=digest(manifest);s['files']['bootstrap.py']={k:v for k,v in row(bootstrap).items() if k!='path'};save(startup,s)
result={'schema':'WORLD_ENGINE_REFERENCE_6S_SOURCE_PIN_DELTA_V1','status':'PINS_UPDATED_NOT_IMAGE_BUILD_OR_VISUAL_PASS','baseCommit':BASE,'changedRuntimeRows':updated,'runtimeManifestSHA256':digest(manifest),'startupManifestSHA256':digest(startup),'GPUExecutions':0}
save(HERE/'SOURCE_PIN_DELTA.json',result);print(json.dumps(result))
