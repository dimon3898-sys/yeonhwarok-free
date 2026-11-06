"""Refresh only opt-in source pins over the preserved reference candidate."""
import json,hashlib,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
REC=ROOT/'world-simulation-shorts-engine/recovery'
sha=lambda b:hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def row(p):
    b=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':sha(b)}
parent=json.loads((REC/'reference-sample-v2/SOURCE_SEAL.json').read_bytes())
manifest=REC/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
data=json.loads(manifest.read_bytes())
allowed={str(REC.relative_to(ROOT))+'/universal-presentation-v2/'+n for n in ['presentation_plan.mjs','PRESENTATION_PROMPT.schema.json']}
for r in data['files']:
    if r['path'] in allowed:r.update(row(ROOT/r['path']))
manifest.write_bytes(encoded(data))
bootstrap=REC/'studio-cold-start-v2/bootstrap.py';s,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$","SOURCE_SHA = '"+sha(manifest.read_bytes())+"'",bootstrap.read_text());assert n==1
bootstrap.write_text(s)
startup=bootstrap.parent/'STARTUP_MANIFEST.json';j=json.loads(startup.read_bytes());j['runtimeManifestSHA256']=sha(manifest.read_bytes());r=row(bootstrap);j['files']['bootstrap.py']={k:r[k] for k in ('bytes','sha256')};startup.write_bytes(encoded(j))
result={'schema':'WORLD_ENGINE_KW20_SOURCE_SEAL_V1','sourceBaseCommit':'bbd2ff9b783d00da208a6296e91183b32905373c','parentImage':parent['parentImage'],'files':[row(ROOT/r['path']) for r in parent['files']],'runtimeManifestSHA256':sha(manifest.read_bytes()),'startupManifestSHA256':sha(startup.read_bytes()),'runtimeSourceRows':len(data['files']),'inputs':[row(HERE/f'KOREAN_WAR_20S_PART_{i:02d}.json') for i in (1,2)],'paidGpuApproved':False}
(HERE/'SOURCE_SEAL.json').write_bytes(encoded(result))
print(json.dumps({'overlaidFiles':len(result['files']),'runtimeRows':len(data['files']),'newRuntimeBehavior':'Optional native boundary visibility only'}))
