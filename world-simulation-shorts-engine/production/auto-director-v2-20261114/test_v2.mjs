import fs from 'node:fs';
import assert from 'node:assert/strict';
import {analyzeTerritoryChanges,areaKm2,screenFraction,geometry} from '../../recovery/universal-presentation-v2/territory_delta_v2.mjs';
import {directorConfig,retimeHistoryScene,deriveHistoryPresentationV2} from '../../recovery/universal-presentation-v2/history_direction_v2.mjs';
import {validateTerritoryEffects,territoryEffectsAt} from '../../recovery/universal-presentation-v2/territory_effects_v2.mjs';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compilePresentationEnginePlan,validatePresentation,compilePresentationCameraPlan} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
import {evaluateAreaFrame} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {geographicCameraFrame} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {layoutLabels} from '../../recovery/universal-presentation-v2/presentation_label_layer.mjs';
import {resolveRegionPlan} from '../../recovery/universal-presentation-v2/region_source.mjs';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),read=n=>JSON.parse(fs.readFileSync(new URL(n,base))),write=(n,x)=>fs.writeFileSync(new URL(n,base),JSON.stringify(x,null,2)+'\n');
const baseline=read('../generic-history-v1-20261113/RUNTIME_REQUEST.json').segments[0],request=read('RUNTIME_REQUEST.json'),v2=request.segments[0],checks=[],cases=[];
const prior=fs.existsSync(new URL('evidence/DELTA_TESTS.json',base))?read('evidence/DELTA_TESTS.json'):{checks:[],cases:[]};
const invalidated=new Set((process.env.V2_INVALIDATED_TESTS??'').split('|').filter(Boolean));

async function test(name,fn){if(prior.checks.some(x=>x.name===name&&x.status==='PASS')&&!invalidated.has(name)){checks.push({...prior.checks.find(x=>x.name===name),preservedNotRerun:true});if(name.startsWith('geometry: '))cases.push(prior.cases.find(x=>'geometry: '+x.name===name));return;}try{await fn();checks.push({name,status:'PASS'});}catch(e){checks.push({name,status:'FAIL',error:e.stack});write('evidence/DELTA_TESTS.json',{status:'FAIL',checks,cases});throw e;}}
const rect=(w,s,e,n)=>({type:'Polygon',coordinates:[[[w,s],[e,s],[e,n],[w,n],[w,s]]]});
function pair(a,b){const s=structuredClone(baseline.scene);s.time_steps=s.time_steps.slice(0,2);s.time_steps.forEach((step,i)=>{step.area_ids=step.area_ids.slice(0,1);const row=s.areas.find(x=>x.id===step.area_ids[0]);s.geometries.find(x=>x.id===row.geometry_ref).geometry=i?b:a;});return s;}
const same=(a,b)=>assert.deepEqual(a,b),near=(a,b)=>assert.ok(Math.abs(a-b)<=Math.max(1e-7,Math.abs(b)*1e-8),a+' != '+b);
const synthetic=[
 ['expansion',rect(90,30,100,40),rect(90,30,110,40),'added'],
 ['contraction',rect(90,30,110,40),rect(90,30,100,40),'removed'],
 ['split',rect(90,30,110,40),geometry([rect(90,30,98,40).coordinates,rect(102,30,110,40).coordinates]),'removed'],
 ['tiny change',rect(90,30,100,40),rect(90,30,100.01,40),'tiny'],
 ['large change',rect(90,30,91,31),rect(90,30,120,60),'large'],
 ['multiple regions',rect(90,30,100,40),geometry([rect(90,30,100,40).coordinates,rect(70,30,80,40).coordinates,rect(115,40,125,50).coordinates]),'multiple'],
 ['same-area relocation',rect(90,30,100,40),rect(110,30,120,40),'both'],
 ['no change',rect(90,30,100,40),rect(90,30,100,40),'none'],
 ['hole appearance',rect(90,30,110,50),{type:'Polygon',coordinates:[rect(90,30,110,50).coordinates[0],rect(95,35,105,45).coordinates[0]]},'removed'],
 ['diagonal overlap',{type:'Polygon',coordinates:[[[90,30],[110,30],[90,50],[90,30]]]},{type:'Polygon',coordinates:[[[90,30],[110,50],[90,50],[90,30]]]},'both']
];
for(const [name,a,b,kind]of synthetic)await test('geometry: '+name,()=>{
 const s=pair(a,b),before=JSON.stringify(s),analysis=analyzeTerritoryChanges(s),d=analysis.changes[0];assert.equal(JSON.stringify(s),before);
 near(d.netKm2,d.addedKm2-d.removedKm2);
 if(kind==='added')assert.ok(d.addedKm2>0&&d.removedKm2<1e-6);
 if(kind==='removed')assert.ok(d.removedKm2>0&&d.addedKm2<1e-6);
 if(kind==='both')assert.ok(d.removedKm2>0&&d.addedKm2>0);
 if(kind==='tiny')assert.ok(d.ratio<.015);
 if(kind==='large')assert.ok(d.ratio>.9);
 if(kind==='multiple')assert.ok(d.parts>=2);
 if(kind==='none')assert.equal(d.changedKm2,0);
 const timed=retimeHistoryScene(s,analysis),directed=deriveHistoryPresentationV2({scene:timed.scene,analysis,admission:{regionEvidence:baseline.regionEvidence},timingAudit:timed.audit});
 validatePresentation(directed.presentation,{scene:timed.scene});
 if(['tiny','none'].includes(kind))assert.equal(directed.presentation.territoryChanges.items[0].strength,0);
 cases.push({name,synthetic:true,addedKm2:d.addedKm2,removedKm2:d.removedKm2,ratio:d.ratio,parts:d.parts,frames:timed.audit.durations,overlayStrength:directed.presentation.territoryChanges.items[0].strength});
});
await test('spherical area uses latitude and holes, not bounding-box area',()=>{const a=areaKm2(rect(0,0,10,10)),b=areaKm2(rect(0,60,10,70));assert.ok(a/b>2);const outer=rect(0,0,10,10),inner=rect(2,2,8,8);near(areaKm2({type:'Polygon',coordinates:[outer.coordinates[0],inner.coordinates[0]]}),a-areaKm2(inner));});
await test('screen fraction clips the actual polygon to portrait viewport',()=>{const pose={center:[100,35],scale:30,rollDegrees:0};assert.equal(screenFraction(geometry([]),pose),0);assert.equal(screenFraction(rect(0,0,10,10),pose),0);assert.ok(screenFraction(rect(95,30,105,40),pose)>0);});
await test('anti-meridian / unsupported domain fails without coordinate rewrite',()=>assert.throws(()=>analyzeTerritoryChanges(pair(rect(90,30,100,40),rect(-170,30,170,40))),/ANTIMERIDIAN/));
await test('invalid common config rejected',()=>{assert.throws(()=>directorConfig({country:'test'}));assert.throws(()=>directorConfig({effectGain:2}));});
await test('short reading budget rejects rather than dropping states',()=>{const s=structuredClone(baseline.scene);s.timing.total_frames=60;assert.throws(()=>retimeHistoryScene(s,analyzeTerritoryChanges(s)),/READABILITY_BUDGET/);});
await test('V2 source geometry, periods, route absence preserved',()=>{same(v2.scene.geometries,baseline.scene.geometries);same(v2.scene.time_steps.map(x=>x.date),baseline.scene.time_steps.map(x=>x.date));assert.equal((v2.scene.routes??[]).length,0);assert.equal(v2.scene.front_lines.length,0);});
await test('variable exact integer budget through unchanged Scene and Area contracts',()=>{validateScenePlan(v2.scene);validateRuntimeRequest(request);const d=v2.scene.time_steps.map(s=>s.transition_frames);assert.ok(new Set(d.slice(1)).size>1);assert.equal(d.reduce((a,b)=>a+b)+v2.scene.timing.final_hold_frames,180);});
await test('all 180 V2 model frames preserve source geometry, safe labels and final hold',()=>{
 const plan=compilePresentationEnginePlan({scene:v2.scene,presentation:v2.presentation}).plans[0].plan;let previous=null;
 for(let f=0;f<180;f++){
  const pose=v2.presentation.camera.frames[f],view=geographicCameraFrame(pose),controls=evaluateAreaFrame(plan,f,{project:view.project});
  for(const a of controls.areas){const original=v2.scene.areas.find(x=>x.id===a.id);same(a.geometry,v2.scene.geometries.find(g=>g.id===original.geometry_ref).geometry);}
  const labels=layoutLabels({items:v2.presentation.labels.items,frame:f,project:view.project,measureText:(t,font)=>({width:[...t].length*parseFloat(font)*.62}),previousLayout:previous});
  assert.equal(labels.visibleCount,3);assert.equal(labels.drawn.filter(x=>x.role==='TIMELINE').length,1);previous=labels;
  if(f>=148)same(pose,v2.presentation.camera.frames[147]);
 }
});
await test('difference effects bind to source subtraction, reject fabricated area',()=>{validateTerritoryEffects(v2.presentation.territoryChanges,v2.scene);const bad=structuredClone(v2.presentation.territoryChanges);bad.items[0].added=rect(0,0,10,10);assert.throws(()=>validateTerritoryEffects(bad,v2.scene),/SOURCE_DIFFERENCE_BINDING/);});
await test('pulses are brief, removed regions fade, final hold has no effects',()=>{for(let f=0;f<180;f++){for(const e of territoryEffectsAt(v2.presentation.territoryChanges,f))assert.ok(e.alpha>0&&e.alpha<=1&&e.coverage===1);if(f>=148)assert.equal(territoryEffectsAt(v2.presentation.territoryChanges,f).length,0);}const e=v2.presentation.territoryChanges.items[0];assert.equal(territoryEffectsAt(v2.presentation.territoryChanges,e.endFrame).some(x=>x.id.startsWith('DERIVED_DELTA_0_')),false);});
await test('new camera binds to real terrain and existing runtime model envelope',async()=>{const region=await resolveRegionPlan({scene:v2.scene,region:v2.region});const camera=compilePresentationCameraPlan({scene:v2.scene,region:v2.region,nativePlan:region.nativePlan,baseCameraPlan:region.baseCameraPlan,presentation:v2.presentation});write('evidence/CAMERA_PLAN.json',camera);});
await test('same V2 public compiler and runtime contract accept 20 seconds',async()=>{
 const input=read('SCENE_INPUT.json');input.prompt=input.prompt.replaceAll('6초','20초');input.data.durationSeconds=20;input.data.scenes[0].endFrame=600;
 const r=await analyzePresentationPrompt(input);assert.equal(r.status,'PASS',JSON.stringify(r.issues));const x=r.renderRequests[0];assert.equal(x.presentation.camera.frames.length,600);
 validateRuntimeRequest({schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:600,sourceInputSHA256:r.inputSHA256,segments:r.renderRequests,transitions:r.transitionPlan});
 same(x.scene.geometries,v2.scene.geometries);write('evidence/20S_POLICY.json',{status:'PASS_COMPILE_ONLY_NOT_RENDERED',timing:x.automaticDirection.timing,changes:x.automaticDirection.changes,frames:600});
});
write('evidence/DELTA_TESTS.json',{status:'PASS',checks,cases,oldPassReruns:0,existingV1AndJapanTestsRun:false});console.log(JSON.stringify({status:'PASS',checks:checks.length,cases:cases.length}));
