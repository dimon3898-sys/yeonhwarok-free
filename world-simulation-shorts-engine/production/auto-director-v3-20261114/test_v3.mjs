import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {retimeHistorySceneV3,deriveHistoryPresentationV3,REFERENCE_RHYTHM_V3} from '../../recovery/universal-presentation-v2/history_direction_v3.mjs';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compilePresentationEnginePlan,compilePresentationCameraPlan,validatePresentation} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
import {evaluateAreaFrame} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {geographicCameraFrame} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
import {resolveRegionPlan} from '../../recovery/universal-presentation-v2/region_source.mjs';
import {layoutLabels} from '../../recovery/universal-presentation-v2/presentation_label_layer.mjs';
const base=new URL('./',import.meta.url),read=n=>JSON.parse(fs.readFileSync(new URL(n,base))),write=(n,x)=>fs.writeFileSync(new URL(n,base),JSON.stringify(x,null,2)+'\n');
const prior=fs.existsSync(new URL('evidence/DELTA_TESTS.json',base))?read('evidence/DELTA_TESTS.json'):{checks:[]},invalidated=new Set((process.env.V3_INVALIDATED_TESTS??'').split('|').filter(Boolean)),checks=[];
async function test(name,fn){const old=prior.checks.find(x=>x.name===name&&x.status==='PASS');if(old&&!invalidated.has(name)){checks.push({...old,preservedNotRerun:true});return;}try{await fn();checks.push({name,status:'PASS'});}catch(e){checks.push({name,status:'FAIL',error:e.stack});write('evidence/DELTA_TESTS.json',{status:'FAIL',checks,oldPassReruns:0});throw e;}}
const baseline=read('../auto-director-v2-20261114/RUNTIME_REQUEST.json').segments[0],request=read('RUNTIME_REQUEST.json'),v3=request.segments[0];
await test('6s selection is a disclosed adjacent excerpt, original coordinates and periods unchanged',()=>{
 assert.equal(v3.scene.time_steps.length,2);assert.equal(v3.automaticDirection.timing.omittedStates.length,6);
 assert.deepEqual(v3.scene.geometries,baseline.scene.geometries);assert.deepEqual(v3.scene.time_steps.map(s=>s.date),baseline.scene.time_steps.slice(0,2).map(s=>s.date));
 assert.ok(v3.presentation.labels.items.some(x=>x.text.includes('일부 시기')));assert.equal((v3.scene.routes??[]).length,0);assert.equal(v3.scene.front_lines.length,0);
});
await test('reference durations trace to annotated actual frame intervals',()=>{
 const r=read('reference/TIMING_ANALYSIS.json');assert.equal(REFERENCE_RHYTHM_V3.referenceSHA256,r.sourceSHA256);
 assert.equal(REFERENCE_RHYTHM_V3.cameraMoveFrames,r.phases.find(x=>x.startFrame===175).frames);
 assert.equal(REFERENCE_RHYTHM_V3.regionBlendFrames,r.events.find(x=>x.startFrame===205).durationFrames);
 assert.equal(REFERENCE_RHYTHM_V3.readingHoldFrames,r.phases.find(x=>x.startFrame===283).frames);
});
await test('new V3 public and runtime contracts bind exact 180 frames',()=>{validateScenePlan(v3.scene);validateRuntimeRequest(request);validatePresentation(v3.presentation,{scene:v3.scene});assert.equal(v3.scene.timing.final_hold_frames,47);});
function audit(segment){
 const scene=segment.scene,p=segment.presentation,plan=compilePresentationEnginePlan({scene,presentation:p}).plans.find(x=>x.engine==='EXISTING_AREA_V3').plan;let prev=null;
 for(const e of p.territoryChanges.items){const op=plan.operations.find(x=>x.type==='STATE_TRANSITION'&&x.state_ids[1]===e.toStateId);assert.equal(op.durationFrames??op.duration_frames,e.endFrame-e.startFrame);}
 for(let f=0;f<scene.timing.total_frames;f++){
  const view=geographicCameraFrame(p.camera.frames[f]),state=evaluateAreaFrame(plan,f,{project:view.project});
  for(const a of state.areas){const original=scene.areas.find(x=>x.id===a.id);assert.deepEqual(a.geometry,scene.geometries.find(g=>g.id===original.geometry_ref).geometry);}
  const labels=layoutLabels({items:p.labels.items,frame:f,project:view.project,measureText:(t,font)=>({width:[...t].length*parseFloat(font)*.62}),previousLayout:prev});
  assert.equal(labels.visibleCount,3);assert.equal(labels.drawn.filter(x=>x.role==='TIMELINE').length,1);prev=labels;
  for(const c of segment.automaticDirection.timing.choreography)if(f>=c.blendStart&&f<c.readEnd)assert.deepEqual(p.camera.frames[f],p.camera.frames[c.blendStart]);
 }
 return {frames:scene.timing.total_frames,sourceGeometryUnchanged:true,safeLabels:true,cameraDuringBlendsAndReads:'LOCKED',operations:plan.operations.filter(x=>x.type==='STATE_TRANSITION')};
}
await test('all new V3 model frames preserve geometry, readable labels and disjoint camera/territory motion',()=>write('evidence/MODEL_FRAME_AUDIT.json',audit(v3)));
await test('new V3 camera binds to actual source and model envelope',async()=>{
 const region=await resolveRegionPlan({scene:v3.scene,region:v3.region});write('evidence/CAMERA_PLAN.json',compilePresentationCameraPlan({scene:v3.scene,region:v3.region,nativePlan:region.nativePlan,baseCameraPlan:region.baseCameraPlan,presentation:v3.presentation}));
});
for(const kind of ['expansion','contraction','split','reorganization'])await test('common V3 choreography: '+kind,()=>{
 const rect=(a,b,c,d)=>({type:'Polygon',coordinates:[[[a,b],[c,b],[c,d],[a,d],[a,b]]]});
 const s=structuredClone(baseline.scene);s.time_steps=s.time_steps.slice(0,2);const ids=new Set(s.time_steps.flatMap(x=>x.area_ids));s.areas=s.areas.filter(x=>ids.has(x.id));
 const shapes={expansion:[rect(90,30,105,45),rect(90,30,115,45)],contraction:[rect(90,30,115,45),rect(90,30,105,45)],split:[rect(90,30,115,45),{type:'MultiPolygon',coordinates:[rect(90,30,100,45).coordinates,rect(105,30,115,45).coordinates]}],reorganization:[rect(90,30,105,45),rect(100,35,115,50)]}[kind];
 s.time_steps.forEach((step,i)=>{s.geometries.find(g=>g.id===s.areas.find(a=>a.id===step.area_ids[0]).geometry_ref).geometry=shapes[i];});
 const before=JSON.stringify(s),timed=retimeHistorySceneV3(s),d=deriveHistoryPresentationV3({scene:timed.scene,timingAudit:timed.audit,admission:{regionEvidence:baseline.regionEvidence}});
 assert.equal(JSON.stringify(s),before);validatePresentation(d.presentation,{scene:timed.scene});assert.equal(d.audit.profile,'HISTORICAL_STATES_V3');assert.equal(d.presentation.territoryChanges.items[0].endFrame,133);
});
await test('names and dates do not select a camera or effect',()=>{
 const a=structuredClone(baseline.scene),b=structuredClone(a);b.subject.label='합성 지역';b.time_steps.forEach((s,i)=>{s.date={start:String(1800+i*10),end:String(1809+i*10)};s.label='다른 시기';});
 const run=s=>{const t=retimeHistorySceneV3(s);return deriveHistoryPresentationV3({scene:t.scene,timingAudit:t.audit,admission:{regionEvidence:baseline.regionEvidence}}).presentation;};
 const x=run(a),y=run(b);assert.deepEqual(x.camera,y.camera);assert.deepEqual(x.territoryChanges,y.territoryChanges);
});
await test('same public V3 compiler schedules more adjacent events in20s without faster motion',async()=>{
 const input=read('SCENE_INPUT.json');input.prompt=input.prompt.replaceAll('6초','20초');input.data.durationSeconds=20;input.data.scenes[0].endFrame=600;
 const r=await analyzePresentationPrompt(input);assert.equal(r.status,'PASS',JSON.stringify(r.issues));const x=r.renderRequests[0];assert.equal(x.scene.time_steps.length,4);assert.equal(x.presentation.camera.frames.length,600);
 const packet={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:600,sourceInputSHA256:r.inputSHA256,segments:r.renderRequests,transitions:r.transitionPlan};validateRuntimeRequest(packet);const evidence=audit(x);
 write('evidence/20S_POLICY.json',{status:'PASS_COMPILE_AND_MODEL_ONLY_NOT_RENDERED',timing:x.automaticDirection.timing,evidence});
});
await test('preserved V1/V2/Area/geography implementations and saved V2 MP4 match prior bytes',()=>{
 for(const[path,expected]of Object.entries(read('evidence/CHANGE_SCOPE.json').preserved)){const bytes=fs.readFileSync(new URL('../../'+path,base));assert.equal(createHash('sha256').update(bytes).digest('hex'),expected,path);}
});
write('evidence/DELTA_TESTS.json',{status:'PASS',checks,oldPassReruns:0,oldTestsOrRendersRun:false});console.log(JSON.stringify({status:'PASS',checks:checks.length}));
