"""Create an isolated runtime overlay: existing exact-polygon contour/glow only."""
import json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
V4=HERE.parent/'korean-war-20s-visual-v4'
REC='world-simulation-shorts-engine/recovery/'
seal=json.loads((V4/'SOURCE_SEAL.json').read_bytes())
sha=lambda b:hashlib.sha256(b).hexdigest()
encoded=lambda x:(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
cpu=REC+'universal-presentation-v2/presentation_runtime.mjs'
nv=REC+'codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs'
generated=REC+'codex-to-gcube-handoff-v1/backend/GENERATED_SOURCE_MANIFEST.json'
verifier=REC+'codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs'
manifest=REC+'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json'
bootstrap=REC+'studio-cold-start-v2/bootstrap.py';startup=REC+'studio-cold-start-v2/STARTUP_MANIFEST.json'
rows={r['path']:(ROOT/r['path']).read_bytes() for r in seal['files']}
rows[cpu]=(ROOT/cpu).read_bytes()
changes=[]
for path in [cpu,nv]:
    before=rows[path];text=before.decode()
    needle='style.AREA.coreColor[3]=0;style.AREA.glowGain=0;'
    assert text.count(needle)==1
    text=text.replace(needle,'style.AREA.coreColor=[1,.97,.78,.94];style.AREA.width=3.2;style.AREA.glowColor=[1,.85,.03,1];style.AREA.glowRadius=3.5;style.AREA.glowGain=.22;')
    needle='coreColor:accent?[.08,.95,1,1]:[1,.87,.1,.2]'
    assert text.count(needle)==1
    text=text.replace(needle,'coreColor:accent?[.08,.95,1,1]:[1,.87,.1,0]')
    needle="for(const area of controls.areas)if(area.alpha>0)presentationAreaViewport({geometry:area.geometry,project,safeArea:safe,presentation:p});"
    assert text.count(needle)==1
    text=text.replace(needle,"const visibleAreas=[],culledAreaIds=[];for(const area of controls.areas){const visibility=area.alpha>0?presentationAreaViewport({geometry:area.geometry,project,safeArea:safe,presentation:p,allowOffscreenComponents:true}):{visible:true};if(visibility.visible!==false)visibleAreas.push(area);else culledAreaIds.push(area.id);}for(const id of groups)if(controls.areas.some(a=>(a.state_id??'__DEFAULT__')===id&&a.alpha>0&&a.coverage>0))assert(visibleAreas.some(a=>(a.state_id??'__DEFAULT__')===id&&a.alpha>0&&a.coverage>0),'UP2_ACTIVE_STATE_ENTIRELY_OUTSIDE_VIEWPORT');")
    needle="areas:controls.areas.filter(a=>(a.state_id??'__DEFAULT__')===id)"
    assert text.count(needle)==1;text=text.replace(needle,"areas:visibleAreas.filter(a=>(a.state_id??'__DEFAULT__')===id)")
    needle="for(const item of controls.areas)if(item.alpha>0&&item.coverage>0)"
    assert text.count(needle)==1;text=text.replace(needle,"for(const item of visibleAreas)if(item.alpha>0&&item.coverage>0)")
    needle="sourceFronts:controls.fronts.map"
    assert text.count(needle)==1;text=text.replace(needle,"culledAreaIds,sourceFronts:controls.fronts.map")
    rows[path]=text.encode()
    changes.append({'path':path,'beforeSHA256':sha(before),'afterSHA256':sha(rows[path])})
plan=REC+'universal-presentation-v2/presentation_plan.mjs'
before=rows[plan];text=before.decode()
needle="export function presentationAreaViewport({geometry,project,safeArea,presentation,width=1080,height=1920})"
assert text.count(needle)==1;text=text.replace(needle,"export function presentationAreaViewport({geometry,project,safeArea,presentation,width=1080,height=1920,allowOffscreenComponents=false})")
needle="ok(visible,'UP2_AREA_SOURCE_OUTSIDE_VIEWPORT');"
assert text.count(needle)==1;text=text.replace(needle,"if(!visible&&allowOffscreenComponents===true)return{safeArea:viewport,clipped:true,visible:false,sourceGeometryChanged:false};"+needle)
rows[plan]=text.encode();changes.append({'path':plan,'beforeSHA256':sha(before),'afterSHA256':sha(rows[plan])})
g=json.loads(rows[generated]);verify=rows[verifier].decode()
for variant in g['variants']:
    original=variant['original']
    if original in rows:
        new=sha(rows[original]);old=variant['originalSHA256']
        if new!=old:
            assert verify.count(old)==1;verify=verify.replace(old,new)
        variant['originalSHA256']=new
    vp=REC+'codex-to-gcube-handoff-v1/'+variant['variant']
    if vp in rows:variant['variantSHA256']=sha(rows[vp])
rows[generated]=encoded(g);rows[verifier]=verify.encode()
m=json.loads(rows[manifest])
for row in m['files']:
    if row['path'] in rows and row['path']!=manifest:
        raw=rows[row['path']];row.update({'bytes':len(raw),'sha256':sha(raw)})
rows[manifest]=encoded(m)
old=seal['runtimeManifestSHA256'];new=sha(rows[manifest])
boot=rows[bootstrap].decode();assert boot.count("SOURCE_SHA = '"+old+"'")==1
rows[bootstrap]=boot.replace("SOURCE_SHA = '"+old+"'","SOURCE_SHA = '"+new+"'").encode()
s=json.loads(rows[startup]);s['runtimeManifestSHA256']=new
s['files']['bootstrap.py']={'bytes':len(rows[bootstrap]),'sha256':sha(rows[bootstrap])};rows[startup]=encoded(s)
newrows=[]
for path,raw in rows.items():
    target=HERE/'overlay'/path;target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(raw)
    newrows.append({'path':path,'overlayPath':str(target.relative_to(ROOT)),'bytes':len(raw),'sha256':sha(raw)})
seal.update({'schema':'WORLD_ENGINE_KW20_VIEWPORT_OVERLAY_V8','files':newrows,'runtimeManifestSHA256':new,'startupManifestSHA256':sha(rows[startup])})
with (HERE/'SOURCE_SEAL.json').open('xb') as f:f.write(encoded(seal))
receipt={'schema':'WORLD_ENGINE_KW20_VIEWPORT_CHANGE_V8','sourceRuntime':'1b6e4c93b624b1a4cb54258b2d2bb13d89fc7196','changes':changes,'newRuntimeManifestSHA256':new,'geometryCameraLabelsTimingInputsChanged':False,'existingEnginesReused':['Exact polygon triangulation','Chunked existing Area contour pass','Existing glow shader'],'suppressed':'Only the non-accent generalized context line; cyan campaign direction remains unchanged','newSourceGeometry':False,'existingFilesOverwritten':0,'oldPassSuitesRerun':0,'qualityPass':False}
with (HERE/'OVERLAY_RECEIPT.json').open('xb') as f:f.write(encoded(receipt))
print(json.dumps(receipt))
