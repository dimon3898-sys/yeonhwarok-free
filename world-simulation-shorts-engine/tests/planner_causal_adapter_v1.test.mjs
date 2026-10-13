import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {compileCausalEnginePlan,evaluateCausalSchedule} from '../web/map_infographic_v1/planner_causal_adapter_v1.mjs';
import {compileSceneEngineRequest} from '../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {evaluateAreaFrame} from '../web/map_infographic_v1/area_core_v3.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '../web/map_infographic_v1/flow_core_v2.mjs';
const legacy=JSON.parse(await readFile(new URL('../recovery/planner-scene-json-v1/fixtures/SCENE_PLAN.json',import.meta.url),'utf8'));
const scene=JSON.parse(await readFile(new URL('../recovery/planner-night-run-v1/fixtures/SCENE_PLAN.json',import.meta.url),'utf8'));
const plan=compileCausalEnginePlan(scene);
test('Legacy scene delegates its exact existing Area plan without motion',()=>{
 const result=compileCausalEnginePlan(legacy);
 assert.deepEqual(result.areaPlan,compileSceneEngineRequest(legacy).areaPlan);
 assert.deepEqual(result.flowTracks,[]);
});
test('Movement and contact complete before the stock territorial transition begins',()=>{
 assert.equal(plan.flowTracks.length,3);assert.equal(plan.totalFrames,420);
 for(const entry of plan.flowTracks){
  assert.equal(entry.plan.arrivalFrame,entry.track.contact_frame);
  const before=evaluateAreaFrame(plan.areaPlan,entry.track.contact_frame-1,{project:point=>point});
  assert.equal(before.stateId,entry.track.from_state_id);
  assert.equal(evaluateCausalSchedule(plan,entry.track.contact_frame)[plan.causalTracks.findIndex(item=>item.id===entry.id)].phase,'CONTACT');
  assert.equal(evaluateAreaFrame(plan.areaPlan,entry.track.control_end_frame-1,{project:point=>point}).stateId,entry.track.to_state_id);
 }
});
test('New schedules preserve every supplied historical state and geometry',()=>{
 assert.deepEqual(plan.areaPlan.intent.states,compileSceneEngineRequest(scene).areaPlan.intent.states);
 for(const original of legacy.geometries)assert.deepEqual(scene.geometries.find(item=>item.id===original.id),original);
 assert.equal(plan.ownership.newRenderer,false);assert.equal(plan.ownership.physics,false);
});
test('Absolute random-access Flow positions and heading remain the existing evaluator result',()=>{
 const project=point=>[400+(point[0]-127)*120,1000-(point[1]-37)*120];
 const context={cameraState:{scale:'REGIONAL',projection:'FLAT_GEOGRAPHIC',cameraLocked:true,settle:{locked:true},
  camera:{flatBounds:[120,30,135,45]},admission:{status:'LOCAL_NOT_ADMITTED',effectiveScale:'REGIONAL',localUsed:false}},
  project,safeArea:[0,0,2000,2000],
  scalePlan:{...scene.scale_intent,scale:'REGIONAL'},heightSource:null,protectedBoxes:[]};
 for(const entry of plan.flowTracks){
  const primitive=compileFlowRoute(entry.plan.intent,{project});
  const frame=entry.plan.startFrame+entry.plan.timing.object_start_frame+Math.floor(entry.plan.timing.travel_frames/2);
  const first=evaluateFlowFrame(entry.plan,frame,{primitive,eventContext:context});
  assert.deepEqual(evaluateFlowFrame(entry.plan,frame,{primitive,eventContext:context}),first);
  assert.ok(first.objectFraction>0&&first.objectFraction<1);
  assert.equal(first.heading,first.objectHeading);
 }
});
test('Settlement is actor-free and permits no armistice contact cue; final hold is retained',()=>{
 const closure=plan.causalTracks.at(-1);assert.equal(closure.contact_kind,'NONE');
 assert.equal(closure.route_id,undefined);assert.equal(plan.flowTracks.some(item=>item.id===closure.id),false);
 for(let frame=closure.motion_start_frame;frame<closure.end_frame;frame++)
  assert.equal(evaluateCausalSchedule(plan,frame).at(-1).contactCueAllowed,false);
 assert.equal(evaluateAreaFrame(plan.areaPlan,419,{project:point=>point}).hold,true);
});
