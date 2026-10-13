import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {compileScenePlan} from '../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan,compileSceneEngineRequest} from '../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {assertFlowPlan} from '../web/map_infographic_v1/flow_core_v2.mjs';
import {assertAreaPlan,evaluateAreaFrame} from '../web/map_infographic_v1/area_core_v3.mjs';
import {assertEventPlan} from '../web/map_infographic_v1/event_timeline_v1.mjs';

const fixture=async name=>JSON.parse(await readFile(new URL('../recovery/planner-scene-json-v1/fixtures/SYNTHETIC_'+name+'.json',import.meta.url),'utf8'));

test('transport Scene JSON compiles the existing Flow V2 contract without changing supplied route or object',async()=>{
 const input=await fixture('A'),scene=compileScenePlan(input),before=JSON.stringify(scene),binding=compileExistingEnginePlan(scene);
 assert.equal(binding.plans.length,1);const flow=assertFlowPlan(binding.plans[0].plan);
 assert.equal(binding.plans[0].engine,'EXISTING_FLOW_V2');
 assert.deepEqual(flow.intent.route_geometry,scene.geometries.find(g=>g.id===scene.routes[0].geometry_ref).geometry);
 assert.deepEqual(flow.intent.object_graphic,scene.moving_objects[0].graphic);
 assert.equal(flow.totalFrames,scene.timing.total_frames-scene.timing.event_start_frame);
 assert.equal(JSON.stringify(scene),before);assert.equal(binding.newEngine,false);
});

test('disaster Scene JSON compiles existing propagation and impact operations only',async()=>{
 const input=await fixture('B'),scene=compileScenePlan(input),binding=compileExistingEnginePlan(scene);
 const area=assertAreaPlan(binding.plans[0].plan);
 assert.equal(binding.plans[0].engine,'EXISTING_AREA_V3');
 assert.ok(area.operations.some(op=>op.type==='PROPAGATION_WAVE'));
 assert.ok(area.operations.some(op=>op.type==='IMPACT_ZONE'));
 assert.equal(area.physicalSimulation,undefined);assert.equal(area.intent.physicalSimulation,false);
 assert.deepEqual(area.intent.impacts[0].geometry,scene.geometries.find(g=>g.id===scene.impact_zones[0].geometry_ref).geometry);
});

test('war Scene JSON binds exact state geometry and chronological dates to frozen Area timeline',async()=>{
 const input=await fixture('C'),scene=compileScenePlan(input),request=compileSceneEngineRequest(scene),binding=compileExistingEnginePlan(scene);
 const area=assertAreaPlan(request.areaPlan);
 assert.deepEqual(area,binding.plans[0].plan);
 assert.equal(request.sourceGeometryBinding,JSON.stringify(scene.geometries));
 for(const [index,state]of area.intent.states.entries()){
  assert.equal(state.time_label,scene.time_steps[index].date);
  const areaId=scene.time_steps[index].area_ids[0],row=scene.areas.find(value=>value.id===areaId);
  assert.deepEqual(state.areas[0].geometry,scene.geometries.find(g=>g.id===row.geometry_ref).geometry);
 }
 const final=evaluateAreaFrame(area,area.endFrame-1);
 assert.equal(final.stateId,scene.time_steps.at(-1).id);assert.equal(final.hold,true);
 assert.equal(final.cameraOwnership,'READ_ONLY');assert.equal(final.timeLabel,scene.time_steps.at(-1).date);
});

test('line/metric Scene JSON uses the existing Event V1 timeline and fixed value source',async()=>{
 const input=await fixture('A'),facts=structuredClone(input.facts),route=facts.routes[0],geo=facts.geometries.find(g=>g.id===route.geometry_ref);
 facts.subject={id:'line_subject',label:'가상 경계',aliases:['가상 경계'],event_family:'LINE_METRIC'};
 facts.routes=[];facts.geographic_lines=[{id:'line',geometry_ref:geo.id,direction:'FORWARD',style_role:'PRIMARY'}];
 facts.metrics=[{id:'metric',display_value:'120',unit:'km',anchor:geo.geometry.coordinates[0],source_id:geo.source_id}];
 const scene=compileScenePlan({topic:'가상 경계 길이는 얼마일까?',facts}),binding=compileExistingEnginePlan(scene);
 const plan=assertEventPlan(binding.plans[0].plan);
 assert.equal(binding.plans[0].engine,'EXISTING_EVENT_V1');assert.equal(plan.intent.metric.display_value,'120');
 assert.deepEqual(plan.intent.line.geometry,geo.geometry);
 assert.equal(plan.totalFrames,scene.timing.total_frames-scene.timing.event_start_frame);
});

test('missing object graphic is a data request rather than an invented transport object',async()=>{
 const input=await fixture('A');delete input.facts.routes[0].object_graphic;
 const scene=compileScenePlan(input);
 assert.throws(()=>compileExistingEnginePlan(scene),error=>error.code==='DATA_REQUIRED');
});
