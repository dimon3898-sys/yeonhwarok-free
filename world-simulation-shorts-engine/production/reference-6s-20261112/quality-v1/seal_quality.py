"""Seal only the two admitted quality deltas and their NVIDIA/source pins."""
from pathlib import Path
import hashlib, json, re

P = Path(__file__).resolve().parent
E = P.parents[2]
R = E.parent
REC = E / 'recovery'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value):
    p.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
def row(p):
    return {'path': str(p.relative_to(R)), 'bytes': p.stat().st_size, 'sha256': sha(p)}

assert json.loads((P/'CPU_VISUAL_REVIEW.json').read_text())['status'] == 'PASS_CHANGED_SCOPE'
worker = REC/'codex-to-gcube-handoff-v1/controller/nvidia_worker.py'
assert sha(worker) == 'f96763045ae38f24b0dba6f609e049454464f8d8489e2762987155c1e1cf0171'
gfile = REC/'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json'
g = json.loads(gfile.read_text())
verifier = gfile.parent/'capture_nvidia.mjs'
code = verifier.read_text()
for v in g['variants']:
    original, variant = R/v['original'], gfile.parent.parent/v['variant']
    if original.name == 'presentation_runtime.mjs':
        assert code.count(v['originalSHA256']) == 1
        code = code.replace(v['originalSHA256'], sha(original))
        v['originalSHA256'], v['variantSHA256'] = sha(original), sha(variant)
    else:
        assert sha(original) == v['originalSHA256'] and sha(variant) == v['variantSHA256']
g['optionalBoundaryTraceQuality'] = {'CPUVisualValidation':'PASS_CHANGED_SCOPE','actualGPUValidation':'NOT_RUN','runtimeChanges':'Three matching boundary preset/frame/evidence connections only; NVIDIA diagnostics preserved'}
save(gfile,g); verifier.write_text(code)
changed = [E/'web/map_infographic_v1/boundary_trace_v1.mjs',E/'web/map_infographic_v1/renderer.mjs',REC/'universal-presentation-v2/presentation_plan.mjs',REC/'universal-presentation-v2/presentation_runtime.mjs',REC/'codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs',gfile,verifier,P/'REFERENCE_6S_QUALITY_INPUT.json',P/'RUNTIME_REQUEST.json']
m = REC/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
oldsha = sha(m)
assert oldsha == '4fe86620560c0131f31022ad309481edc99066b04990be7c92ef9f1f8cffd454'
d = json.loads(m.read_text()); rows = {r['path']:r for r in d['files']}
for p in changed: rows[str(p.relative_to(R))] = row(p)
d['files'] = sorted(rows.values(),key=lambda r:r['path']); save(m,d)
b = REC/'studio-cold-start-v2/bootstrap.py'
s,n = re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$", "SOURCE_SHA = '"+sha(m)+"'", b.read_text()); assert n==1
b.write_text(s)
st=b.parent/'STARTUP_MANIFEST.json';d=json.loads(st.read_text());d['runtimeManifestSHA256']=sha(m);d['files']['bootstrap.py']={k:v for k,v in row(b).items() if k!='path'};save(st,d)
save(P/'PACKAGE.json',{'parentImage':'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8f7a91201840b84769523ec4cd2430df54470403883d57c40e26d3d1e36ce329','oldRuntimeManifestSHA256':oldsha,'runtimeManifestSHA256':sha(m),'startupManifestSHA256':sha(st),'files':[row(p) for p in changed+[m,b,st]],'rebuildReason':'Existing image lacks optional native boundary trace and changed CPU/NVIDIA runtime bindings; old image remains immutable','oldPassReruns':0,'GPUExecutions':0})
print(json.dumps({'status':'SEALED_CHANGED_QUALITY_SCOPE','files':len(changed)+3,'GPUExecutions':0}))
