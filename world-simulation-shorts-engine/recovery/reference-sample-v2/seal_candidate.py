"""Update exact source pins from the current immutable baseline; no build or GPU."""
import json,hashlib,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
rec=root/'world-simulation-shorts-engine/recovery'
here=rec/'reference-sample-v2';handoff=rec/'codex-to-gcube-handoff-v1'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
encoded=lambda x:(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def row(p):
 raw=p.read_bytes();return {'path':p.relative_to(root).as_posix(),'bytes':len(raw),'sha256':sha(raw)}
generatedPath=handoff/'backend/GENERATED_SOURCE_MANIFEST.json';generated=json.loads(generatedPath.read_bytes())
verifierPath=handoff/'backend/capture_nvidia.mjs';verifier=verifierPath.read_text()
for item in generated['variants']:
 original=root/item['original'];variant=handoff/item['variant'];new=sha(original.read_bytes());old=item['originalSHA256']
 if new!=old:
  assert verifier.count(old)==1
  verifier=verifier.replace(old,new)
 item.update(originalSHA256=new,variantSHA256=sha(variant.read_bytes()))
generated['referenceSampleV2']={'sourceBaseCommit':'e12c5e8bfc1de3e6c1484e77554b9d6ee5bee1a6','optInPreset':'REFERENCE_FOCUS_V2','GPUValidation':'NOT_RUN'}
verifierPath.write_text(verifier);generatedPath.write_bytes(encoded(generated))
runtimePath=handoff/'RUNTIME_SOURCE_MANIFEST.json'
baseline=Path(sys.argv[1]).resolve();baselineRaw=baseline.read_bytes()
assert sha(baselineRaw)=='d1d6521942df3fc09d6901b0d9f6496fa28cd4d27076d10f2d9ea0eda214d484'
runtime=json.loads(baselineRaw);changed=[]
allowed={str(p.relative_to(root)) for p in [generatedPath,verifierPath,handoff/'presentation_runtime_vulkan.generated.mjs',rec/'universal-presentation-v2/presentation_plan.mjs',rec/'universal-presentation-v2/presentation_runtime.mjs',rec/'universal-presentation-v2/PRESENTATION_PROMPT.schema.json']}
for prior in runtime['files']:
 if prior['path'] not in allowed:continue
 file=root/prior['path']
 if not file.exists():continue
 current=row(file)
 if current!=prior:changed.append(current['path']);prior.update(current)
runtimePath.write_bytes(encoded(runtime))
bootPath=rec/'studio-cold-start-v2/bootstrap.py';boot=bootPath.read_text()
boot,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$","SOURCE_SHA = '"+sha(runtimePath.read_bytes())+"'",boot);assert n==1;bootPath.write_text(boot)
startupPath=bootPath.parent/'STARTUP_MANIFEST.json';startup=json.loads(startupPath.read_bytes());startup['runtimeManifestSHA256']=sha(runtimePath.read_bytes());b=row(bootPath);startup['files']['bootstrap.py']={k:b[k] for k in ['bytes','sha256']};startupPath.write_bytes(encoded(startup))
files=sorted(set(changed+[p.relative_to(root).as_posix() for p in [runtimePath,bootPath,startupPath]]))
result={'schema':'WORLD_ENGINE_REFERENCE_SAMPLE_SOURCE_SEAL_V2','sourceBaseCommit':'e12c5e8bfc1de3e6c1484e77554b9d6ee5bee1a6',
 'parentImage':'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:af3ad26a305c160a916ac231122a31824cbee4759338c044bab0d6c9dab1691a',
 'files':[row(root/p) for p in files],'runtimeSourceRows':len(runtime['files']),'runtimeManifestSHA256':sha(runtimePath.read_bytes()),
 'startupManifestSHA256':sha(startupPath.read_bytes()),'input':row(here/'REFERENCE_SAMPLE_10S_V2.json')}
(here/'SOURCE_SEAL.json').write_bytes(encoded(result));print(json.dumps({'files':files,'count':len(files)}))
