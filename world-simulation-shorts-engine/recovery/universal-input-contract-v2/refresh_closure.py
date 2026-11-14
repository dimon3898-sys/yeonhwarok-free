"""Rebind the existing image closure to current source bytes; never render."""
from pathlib import Path
import hashlib,json,re
D=Path(__file__).resolve().parent;E=D.parents[1];R=E.parent;P=E/'production/reference-reconstruction-20s-20261114';H=E/'recovery/codex-to-gcube-handoff-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=H/'RUNTIME_SOURCE_MANIFEST.json';d=json.loads(m.read_text());paths={row['path'] for row in d['files']}
# Preserve all prior closure members, plus dependencies of the newly connected
# geographic/history consumers and the reproducible adapter derivation.
for root in [E/'recovery/universal-presentation-v2',E/'recovery/universal-data-pipeline-v1',E/'web/map_infographic_v1']:
 for f in root.iterdir():
  if f.is_file() and f.suffix in {'.mjs','.js','.py','.json'} and not f.name.startswith(('test_','ci_')):paths.add(str(f.relative_to(R)))
for f in (E/'recovery/universal-presentation-v2/sources').rglob('*'):
 if f.is_file():paths.add(str(f.relative_to(R)))
for f in (H/'backend').iterdir():
 if f.is_file() and (f.name=='CURRENT_GPU_DERIVATION.json' or f.name.endswith('.current.patch')):paths.add(str(f.relative_to(R)))
cat=json.loads((E/'recovery/universal-presentation-v2/HISTORY_SOURCE_CATALOG.json').read_text())
for row in cat['records']:
 for key in ['sourceInput','runtime']:paths.add(row[key]['path'])
paths.add(str((P/'FINAL_20S_INPUT.json').relative_to(R)))
# Static relative module imports are included transitively, not guessed at run time.
queue=list(paths)
while queue:
 f=R/queue.pop()
 if f.suffix not in {'.mjs','.js'}:continue
 for reference in re.findall(r"(?:from\s*|import\s*\(|import\s*)['\"]([^'\"]+)['\"]",f.read_text()):
  if not reference.startswith('.'):continue
  target=(f.parent/reference).resolve()
  if not target.is_relative_to(R) or not target.is_file():raise RuntimeError('GPU_IMPORT_CLOSURE_MISSING:'+str(target))
  name=str(target.relative_to(R))
  if name not in paths:paths.add(name);queue.append(name)
rows=[]
for name in sorted(paths):
 f=R/name
 if not f.is_file() or f.is_symlink():raise RuntimeError('GPU_CLOSURE_FILE_MISSING:'+name)
 rows.append({'path':name,'sha256':sha(f),'bytes':f.stat().st_size})
d['files']=rows;d['baseCommit']='66e94bb19fbb8bdd32f42b5f051f4e190bae74d5';d['supportedProfiles']=['GCUBE_NVIDIA_SIX_SECOND_REVIEW_V1','GCUBE_NVIDIA_CONTINUOUS_HISTORY_20S_V1','GCUBE_NVIDIA_HISTORICAL_V2'];d['externalDataPolicy']='OPERATOR_PINNED_CATALOG_OUTSIDE_IMAGE';d['gpuExecuted']=False
m.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
# Startup owns an explicit source pin; update both parent code and its manifest.
b=E/'recovery/studio-cold-start-v2/bootstrap.py';s=b.read_text();s,n=re.subn(r"SOURCE_SHA = '[a-f0-9]{64}'","SOURCE_SHA = '"+sha(m)+"'",s);assert n==1;b.write_text(s)
st=b.parent/'STARTUP_MANIFEST.json';t=json.loads(st.read_text());t['runtimeManifestSHA256']=sha(m)
for name in t['files']:
 f=st.parent/name;t['files'][name]={'bytes':f.stat().st_size,'sha256':sha(f)}
st.write_text(json.dumps(t,indent=2,sort_keys=True)+'\n')
print(json.dumps({'scope':'IMAGE_SOURCE_CLOSURE_BINDING_ONLY','files':len(rows),'runtimeManifestSHA256':sha(m),'startupManifestSHA256':sha(st),'GPUExecutions':0}))
