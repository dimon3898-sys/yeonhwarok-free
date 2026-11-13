import fs from 'node:fs';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compilePresentationEnginePlan,compilePresentationCameraPlan,validatePresentation} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
import {evaluateAreaFrame} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {geographicCameraFrame,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {validateRuntimeRequest} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
import {resolveRegionPlan} from '../../recovery/universal-presentation-v2/region_source.mjs';
import {layoutLabels} from '../../recovery/universal-presentation-v2/presentation_label_layer.mjs';
import {continuousTerritoryAt,applyContinuousTerritory} from '../../recovery/universal-presentation-v2/continuous_territory_runtime.mjs';
import {retimeContinuousHistory} from '../../recovery/universal-presentation-v2/history_continuous_v1.mjs';
const base=new URL('./',import.meta.url),read=n=>JSON.parse(fs.readFileSync(new URL(n,base))),write=(n,x)=>fs.writeFileSync(new URL(n,base),JSON.stringify(x,null,2)+'\n');
const raw=fs.readFileSync(new URL('RUNTIME_REQUEST.json',base)),r=JSON.parse(raw),s=r.segments[0],p=s.presentation,checks=[],rows=[];
let overlap=0,maxCameraStep=0,maxLogZoom=0;
try{
 if(process.env.CONTINUOUS_RESUME==='timing'){const prior=read('evidence/MODEL_TESTS.json');checks.push(...prior.checks);rows.push(...prior.frames);for(let f=1;f<rows.length;f++){const v=geographicCameraFrame(rows[f-1].camera),q=v.project(rows[f].camera.center);maxCameraStep=Math.max(maxCameraStep,Math.hypot(q[0]-540,q[1]-960));maxLogZoom=Math.max(maxLogZoom,Math.abs(Math.log(rows[f].camera.scale/rows[f-1].camera.scale)));if(rows[f].index>0&&rows[f].index<105&&JSON.stringify(rows[f].camera)!==JSON.stringify(rows[f-1].camera))overlap++;}}else{
 validateRuntimeRequest(r);validateScenePlan(s.scene);validatePresentation(p,{scene:s.scene});checks.push('formal public/runtime/scene contracts');
 const plan=compilePresentationEnginePlan({scene:s.scene,presentation:p}).plans.find(x=>x.engine==='EXISTING_AREA_V3').plan;
 let last=null,labels=null;
 for(let f=0;f<180;f++){
  const view=geographicCameraFrame(p.camera.frames[f]),area=applyContinuousTerritory(evaluateAreaFrame(plan,f,{project:view.project}),p.territoryChanges,f),c=continuousTerritoryAt(p.territoryChanges,f);
  assert.equal(area.areas.length,1);assert.equal(area.areas[0].alpha,1);assert.equal(area.areas[0].coverage,1);
  selectGeographicTerrain(s.regionEvidence.sourceLevels,p.camera.frames[f],{maximumTextureSize:8192});
  labels=layoutLabels({items:p.labels.items,frame:f,project:view.project,measureText:(t,font)=>({width:[...t].length*parseFloat(font)*.62}),previousLayout:labels});assert.equal(labels.visibleCount,3);
  const pts=c.geometry.type==='Polygon'?c.geometry.coordinates.flat():c.geometry.coordinates.flat(2),screen=pts.map(view.project);
  assert.ok(screen.every(q=>q[0]>=64&&q[0]<=1016&&q[1]>=64&&q[1]<=1856),'whole territory safe '+f);
  if(f){const oldView=geographicCameraFrame(p.camera.frames[f-1]),q=oldView.project(view.pose.center),step=Math.hypot(q[0]-540,q[1]-960);maxCameraStep=Math.max(maxCameraStep,step);maxLogZoom=Math.max(maxLogZoom,Math.abs(Math.log(view.pose.scale/p.camera.frames[f-1].scale)));if(c.active&&c.index>0&&JSON.stringify(view.pose)!==JSON.stringify(p.camera.frames[f-1]))overlap++;}
  const signature=JSON.stringify(c.geometry);rows.push({frame:f,index:c.index,geometrySHA256:createHash('sha256').update(signature).digest('hex'),geometryChanges:last!==null&&last!==signature,boundaryAlpha:c.boundaryAlpha,boundaryVertices:c.boundaryBand.coordinates.flat(2).length,camera:p.camera.frames[f],labels:labels.drawn.map(l=>({text:l.text,box:l.box})),valid:c.audit.valid});last=signature;
 }
 assert.ok(overlap>=30);assert.ok(maxCameraStep*30<=264.45,'reference slow push-in screen speed bound');assert.ok(maxLogZoom*30<.7373,'reference push-in log scale bound');
 const e=p.territoryChanges.items[0];assert.deepEqual(rows.slice(e.startFrame+1,e.endFrame).map(x=>x.geometryChanges),Array(e.endFrame-e.startFrame-1).fill(true));checks.push('180 model frames; actual geometry change; label safety; source density; camera overlap and bounded speed');
 const region=await resolveRegionPlan({scene:s.scene,region:s.region});write('evidence/CAMERA_PLAN.json',compilePresentationCameraPlan({scene:s.scene,region:s.region,nativePlan:region.nativePlan,baseCameraPlan:region.baseCameraPlan,presentation:p}));checks.push('source-bound formal camera envelope');}
 const e=p.territoryChanges.items[0];
 const old=read('../auto-director-v2-20261114/FORMAL_SCENE.json'),long=structuredClone(old);long.timing.total_frames=600;long.timing.duration_seconds=20;
 const timed=retimeContinuousHistory(long);assert.equal(timed.scene.time_steps.length,4);validateScenePlan(timed.scene);assert.ok(timed.audit.choreography.every(x=>x.endFrame-x.startFrame>=e.endFrame-e.startFrame));write('evidence/20S_TIMING.json',{status:'PASS_TIMING_ONLY_NOT_RENDERED',audit:timed.audit});checks.push('20s three adjacent events without faster compression');
 const renamed=structuredClone(old);renamed.subject.label='Synthetic topic';renamed.time_steps.forEach((x,i)=>{x.date={start:String(1800+i*10),end:String(1809+i*10)};});
 const x=retimeContinuousHistory(old),y=retimeContinuousHistory(renamed);assert.deepEqual(x.audit.choreography.map(({sourcePeriods,...c})=>c),y.audit.choreography.map(({sourcePeriods,...c})=>c));checks.push('no country/date-dependent timing');
 write('evidence/MODEL_TESTS.json',{status:'PASS',runtimeSHA256:createHash('sha256').update(raw).digest('hex'),checks,overlap,maxCameraPixelsPerSecond:maxCameraStep*30,maxLogZoomPerSecond:maxLogZoom*30,frames:rows,oldPassReruns:0});console.log(JSON.stringify({status:'PASS',checks,overlap,maxCameraStep,maxLogZoom}));
}catch(e){write('evidence/MODEL_TESTS.json',{status:'FAIL',checks,error:e.stack,frames:rows});throw e;}
