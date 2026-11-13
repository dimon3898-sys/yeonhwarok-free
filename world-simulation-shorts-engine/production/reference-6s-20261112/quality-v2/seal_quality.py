"""Seal this quality delta only after review of its actual CPU output."""
from pathlib import Path
import hashlib,json,re
P=Path(__file__).resolve().parent;E=P.parents[2];R=E.parent;REC=E/'recovery'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def row(p):return {'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)}
assert json.loads((P/'CPU_VISUAL_REVIEW.json').read_text())['status']=='PASS_CHANGED_SCOPE'
assert json.loads((P/'cpu-a4/CHANGED_FEATURES_RESULT.json').read_text())['all30HoldPixelsIdentical'] is True
assert sha(REC/'codex-to-gcube-handoff-v1/controller/nvidia_worker.py')=='f96763045ae38f24b0dba6f609e049454464f8d8489e2762987155c1e1cf0171'
gfile=REC/'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json';g=json.loads(gfile.read_text());verifier=gfile.parent/'capture_nvidia.mjs';code=verifier.read_text()
for v in g['variants']:
 original,variant=R/v['original'],gfile.parent.parent/v['variant']
 if original.name=='presentation_runtime.mjs':
  assert code.count(v['originalSHA256'])==1
  code=code.replace(v['originalSHA256'],sha(original));v['originalSHA256']=sha(original);v['variantSHA256']=sha(variant)
 else:assert sha(original)==v['originalSHA256'] and sha(variant)==v['variantSHA256']
g['optionalBoundaryTraceQuality']['runtimeChanges']='Quality-v2: matching optional derived-camera semantic transport check; mandatory1e-9 geographic drift gate and all NVIDIA diagnostics preserved'
save(gfile,g);verifier.write_text(code)
changed=[E/'web/map_infographic_v1'/f for f in ['boundary_trace_v1.mjs','renderer.mjs','geographic_camera_v1.mjs','camera_curve_v1.mjs']]+[REC/'universal-presentation-v2'/f for f in ['presentation_plan.mjs','presentation_runtime.mjs','geographic_terrain_source.mjs']]+[REC/'codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs',gfile,verifier,P/'REFERENCE_6S_QUALITY_INPUT.json',P/'RUNTIME_REQUEST.json']
m=REC/'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json';oldsha=sha(m);assert oldsha=='d7a5b3d3686298111cc773a25cb79dcbda582f1dea049d04add793467274ac51'
d=json.loads(m.read_text());rows={r['path']:r for r in d['files']}
for p in changed:rows[str(p.relative_to(R))]=row(p)
d['files']=sorted(rows.values(),key=lambda r:r['path']);save(m,d)
b=REC/'studio-cold-start-v2/bootstrap.py';s,n=re.subn(r"(?m)^SOURCE_SHA = '[a-f0-9]{64}'$","SOURCE_SHA = '"+sha(m)+"'",b.read_text());assert n==1;b.write_text(s)
st=b.parent/'STARTUP_MANIFEST.json';d=json.loads(st.read_text());d['runtimeManifestSHA256']=sha(m);d['files']['bootstrap.py']={k:v for k,v in row(b).items() if k!='path'};save(st,d)
save(P/'PACKAGE.json',{'parentImage':'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:cf52ba25cb46b16b6bee0ba3149d1e8048a3d6a5abf05f1cfda932f7094665a8','oldRuntimeManifestSHA256':oldsha,'runtimeManifestSHA256':sha(m),'startupManifestSHA256':sha(st),'files':[row(p) for p in changed+[m,b,st]],'approvedCameraTrack':json.loads((P/'CAMERA_TRACK.json').read_text()),'rebuildReason':'New optional complete native trace and generic C2 camera code are absent from prior immutable image','oldPassReruns':0,'GPUExecutions':0})
print(json.dumps({'status':'SEALED_CHANGED_QUALITY_V2_SCOPE','files':len(changed)+3,'GPUExecutions':0}))
