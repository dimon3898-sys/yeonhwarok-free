/** Actual old Area controls are the short-scene oracle; this is no GPU test. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {normalizePlannerGeometryKeys} from '../planner_key_order.mjs';
import {compileSceneEngineRequest} from '../../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {evaluateAreaFrame} from '../../../web/map_infographic_v1/area_core_v3.mjs';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),root=path.resolve(engine,'recovery/universal-auto-video-v2');
const hook=registerHooks({resolve(specifier,context,next){if(specifier.startsWith('/modules/'))return {url:new URL('file://'+path.join(engine,'web/map_infographic_v1',specifier.slice('/modules/'.length))).href,shortCircuit:true};return next(specifier,context);}});
let compileLongAreaRequest,evaluateLongAreaFrame;
try{({compileLongAreaRequest,evaluateLongAreaFrame}=await import('../long_area_timeline.mjs'));}finally{hook.deregister();}
const legacy=JSON.parse(await readFile(path.join(engine,'recovery/planner-scene-json-v1/fixtures/SCENE_PLAN.json'))),
 project=geo=>[geo[0]*10,-geo[1]*10],visual=controls=>({areas:controls.areas,fronts:controls.fronts,
  origin:controls.origin,stateId:controls.stateId,timeLabel:controls.timeLabel,hold:controls.hold});
test('all360originaleventframesretainexactAreaV3geometry/frontreveal/alpha/state/date',()=>{
 const scene=normalizePlannerGeometryKeys(legacy),before=JSON.stringify(scene),old=compileSceneEngineRequest(scene),next=compileLongAreaRequest(scene);
 for(let frame=scene.timing.event_start_frame;frame<scene.timing.total_frames;frame++){
  const expected=evaluateAreaFrame(old.areaPlan,old.areaPlan.startFrame+frame-old.timing.eventStartFrame,{project}),
   actual=evaluateLongAreaFrame(next.timelinePlan,frame,{project,projectionKey:'EXACT_FIXED_TEST_PROJECTION'});
  assert.deepEqual(visual(actual),visual(expected),'actual old visual controls differed at '+frame);
 }
 assert.equal(JSON.stringify(scene),before);assert.ok(next.timelinePlan.states.every(row=>row.staticPlan.totalFrames===1));
});
test('80–600sglobalclockusesoriginalcoordinates atarbitraryorderedframes andseams',async()=>{
 const python="import json,sys;sys.path.insert(0,sys.argv[1]);from planner import plan_topic;print(json.dumps([plan_topic('한국전쟁 전선 변화',duration_seconds=d)['legacyScenePlan'] for d in [80,120,180,300,600]],ensure_ascii=False))";
 const scenes=JSON.parse((await promisify(execFile)('/usr/bin/python3',['-B','-c',python,root],{maxBuffer:8*1024*1024})).stdout);
 for(const raw of scenes){const scene=normalizePlannerGeometryKeys(raw),before=JSON.stringify(scene),request=compileLongAreaRequest(scene),p=request.timelinePlan,
  frames=new Set([p.eventStartFrame,p.eventStartFrame+1,p.totalFrames-1,p.finalHoldStartFrame,
   ...p.states.slice(1).flatMap(row=>[row.globalStartFrame-1,row.globalStartFrame,row.globalStartFrame+1,
    row.globalStartFrame+Math.floor(row.transitionFrames/2),row.globalStartFrame+row.transitionFrames-1])]);
  const forward=new Map([...frames].filter(f=>f>=p.eventStartFrame&&f<p.totalFrames).map(frame=>[frame,visual(evaluateLongAreaFrame(p,frame,{project,projectionKey:'FIXED'}))]));
  for(const frame of [...forward.keys()].reverse())assert.deepEqual(visual(evaluateLongAreaFrame(p,frame,{project,projectionKey:'FIXED'})),forward.get(frame));
  assert.equal(JSON.stringify(scene),before);assert.ok(p.states.every(row=>row.staticPlan.totalFrames===1));
  assert.equal(evaluateLongAreaFrame(p,p.totalFrames-1,{project,projectionKey:'FIXED'}).stateId,p.states.at(-1).stateId);
  for(const row of p.states.slice(1)){
   const first=evaluateLongAreaFrame(p,row.globalStartFrame,{project,projectionKey:'FIXED'});
   assert.equal(first.stateId,p.states[p.states.indexOf(row)-1].stateId);
   assert.ok(first.fronts.every(item=>item.revealFraction===1),'frontline restarted at transition');
  }
 }
});
test('projectioncacheisboundtoactualprojectionkey andretainsnoprojectionhistory',()=>{
 const scene=normalizePlannerGeometryKeys(legacy),p=compileLongAreaRequest(scene).timelinePlan,frame=p.eventStartFrame+2;
 let shift=0;const moving=geo=>[geo[0]+shift,geo[1]],a=evaluateLongAreaFrame(p,frame,{project:moving,projectionKey:'VIEW_A'});
 shift=50;const b=evaluateLongAreaFrame(p,frame,{project:moving,projectionKey:'VIEW_B'});
 assert.notDeepEqual(a.fronts[0].linePrimitive.screenCoordinates,b.fronts[0].linePrimitive.screenCoordinates);
 assert.equal(b.projectionCache.projectionHistoryLimit,1);assert.equal(b.projectionCache.staticStatesCached,1);
 assert.throws(()=>evaluateLongAreaFrame(p,frame,{project:moving,projectionKey:''}));
 assert.throws(()=>evaluateLongAreaFrame(p,p.totalFrames));
});
