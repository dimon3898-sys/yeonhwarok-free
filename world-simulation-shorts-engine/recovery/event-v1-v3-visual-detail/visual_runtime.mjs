// Candidate runtime only: same pinned server/browser and protected input files.
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {openRuntime,repo,engine,productionFixture,json,sha} from '../event-v1-candidate-v2/candidate_runtime.mjs';
export {repo,engine,productionFixture,json,sha};
export async function openVisualRuntime(){
 const fixture=await json(path.join(repo,productionFixture));
 const approved=await json(path.join(engine,'recovery/event-v1-candidate-v2/evidence/on150/REPORT.json'));
 const session=await openRuntime({fixture});
 await session.page.evaluate(async({fixture,approvedEventStyle,approvedMetricStyle})=>{
  const {createEventDetailGpuAdapter}=await import('/modules/visual_event_gpu_adapter_v1.mjs');
  const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('INPUT_HTTP_'+r.status);return r.json();};
  const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),
   load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
  const common={plans:{REGIONAL,CONTINENT},scene,cameraPlan,heightSource:input.heightSource,contextTerrain:input.contextTerrain,
   eventPlan:window.eventCandidate.eventPlan,approvedEventStyle,approvedMetricStyle};
  let pipeline=null,canvas=null;
  const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
  window.visualDetail={
   async initialize({targetFraming,mode='STATIC_VISUAL_PROBE',certificate=null,detailEnabled=true}){
    pipeline?.dispose();canvas?.remove();canvas=document.createElement('canvas');document.body.appendChild(canvas);
    pipeline=await createEventDetailGpuAdapter({...common,canvas,targetFraming,mode,certificate,detailEnabled});
    return {evidence:pipeline.evidence};
   },
   async capture({bounds,cameraLocked=true,eventFrame=149,eventEnabled=true,protect=false,png=true,disabledFrame=null}){
    let clean=null;
    if(protect){pipeline.draw({bounds,cameraLocked,eventEnabled:false});glFinish();clean=new Uint8Array(pipeline.readPixels());}
    const diagnostic=disabledFrame===null?pipeline.draw({bounds,cameraLocked,eventFrame:eventEnabled?eventFrame:null,eventEnabled}):pipeline.drawFrame(disabledFrame,{eventEnabled:false});
    glFinish();const pixels=new Uint8Array(pipeline.readPixels()),result={diagnostic,raw_rgba_sha256:await digest(pixels)};
    const encoded=png?pipeline.png():null;
    if(encoded){result.png=encoded;result.png_sha256=await digest(Uint8Array.from(atob(encoded.split(',')[1]),c=>c.charCodeAt(0)));}
    if(clean){
     const ev=diagnostic.event,inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
     const a=new Uint32Array(clean.buffer),b=new Uint32Array(pixels.buffer);let changed=0,outside=0,protectedChanged=0,markerChanged=0;
     for(let i=0;i<b.length;i++)if(a[i]!==b[i]){changed++;const x=i%1080,y=1919-Math.floor(i/1080);
      if(!ev.rois.some(r=>inside(x,y,r)))outside++;
      if(ev.protectedBoxes.some(r=>inside(x,y,r)))protectedChanged++;
      if(ev.protectedGraphics.some(r=>r.kind==='MARKER'&&inside(x,y,r.box)))markerChanged++;
     }
     Object.assign(result,{changed_pixels:changed,outside_roi_changed_pixels:outside,protected_changed_pixels:protectedChanged,marker_changed_pixels:markerChanged});
    }
    return result;
   },
   dispose(){pipeline?.dispose();canvas?.remove();pipeline=null;}
  };
  function glFinish(){canvas.getContext('webgl2').finish();}
 },{fixture,approvedEventStyle:approved.frames.at(-1).eventStyle,approvedMetricStyle:approved.frames.at(-1).metricStyle});
 return {...session,fixture,approved,async close(){await session.page.evaluate(()=>window.visualDetail?.dispose());await session.close();}};
}
export async function savedCandidateInputs(){
 const root=path.join(engine,'recovery/event-v1-v3-visual-detail');
 const audit=await json(path.join(engine,'recovery/suez-detail-data-admission-v1/evidence/DETAIL_QUALITY_AUDIT.json'));
 const fixture=await json(path.join(repo,productionFixture));
 return {root,fixture,candidates:audit.audits.map(a=>a.candidate),sourceFixtureSha256:sha(await readFile(path.join(repo,productionFixture)))};
}
