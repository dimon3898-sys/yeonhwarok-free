import test from 'node:test';
import assert from 'node:assert/strict';
import {compileWaveVisualPlan,assertWaveVisualPlan,evaluateWaveVisualFrame} from '../web/map_infographic_v1/wave_visual_v3.mjs';
import {evaluateGeographicLineReveal} from '../web/map_infographic_v1/event_line_v1.mjs';

const source={source_type:'SYNTHETIC_TEST',source_reference:'fixture://wave-visual-focused',verification_status:'SYNTHETIC_TEST'};
const input={origin:[2,0],coastGeometry:{type:'LineString',coordinates:[[-.1,-2],[-.06,-1.4],[.17,-.9],[.04,-.45],
 [.23,.1],[.12,.65],[-.11,1.1],[.05,1.75],[-.17,2.3]]},source,data_mode:'SYNTHETIC_TEST',
 fps:30,total_frames:240,start_frame:12,travel_frames:130,stagger_frames:18,wave_count:3,fade_frames:24,contact_frames:20,pulse_frames:24};
const project=point=>[480+point[0]*95,960-point[1]*130];
const evaluate=(plan,frame)=>evaluateWaveVisualFrame(plan,frame,{project});

test('Focused wave plan is immutable, open, staggered, distinct and deterministic',()=>{
 const before=JSON.stringify(input),plan=compileWaveVisualPlan(input),saved=JSON.stringify(plan);
 assert(Object.isFrozen(plan));assert.deepEqual(plan.coastGeometry,input.coastGeometry);
 assert.equal(plan.waveCount,3);assert.equal(plan.physicalSimulation,false);
 assert.deepEqual(plan.waves.map(wave=>wave.startFrame),[12,30,48]);
 assert.equal(new Set(plan.waves.map(wave=>JSON.stringify([wave.span,wave.bend,wave.phase]))).size,3);
 const shownCounts=[];
 for(let frame=0;frame<plan.totalFrames;frame++){
  const value=evaluate(plan,frame);shownCounts.push(value.diagnostics.majorFrontCount);
  assert(value.diagnostics.majorFrontCount<=3);assert.equal(value.diagnostics.closedRingCount,0);
  for(const item of [...value.fronts,...value.coastfrontHighlights,...(value.originPulse.front?[value.originPulse.front]:[])]){
   assert(item.alpha>=0&&item.alpha<=1);assert.notDeepEqual(item.geometry.coordinates[0],item.geometry.coordinates.at(-1));
   assert(item.geometry.coordinates.flat().every(Number.isFinite));
   assert.deepEqual(item.lineReveal,evaluateGeographicLineReveal(item.linePrimitive,1));
   assert.deepEqual(item.geometry.coordinates.map(project),item.linePrimitive.screenCoordinates);
  }
 }
 assert(shownCounts.includes(3));assert.equal(shownCounts[0],0);
 const expected=evaluate(plan,75);for(const frame of [239,10,199,80,0])evaluate(plan,frame);
 assert.deepEqual(evaluate(plan,75),expected);assert.equal(JSON.stringify(input),before);assert.equal(JSON.stringify(plan),saved);
 assert.deepEqual(compileWaveVisualPlan(JSON.parse(JSON.stringify(input))),plan);
 assert.deepEqual(assertWaveVisualPlan(JSON.parse(JSON.stringify(plan))),plan);
 const curve=evaluate(plan,75).fronts.find(item=>item.id==='WAVE_1'),radii=curve.geometry.coordinates
  .map(point=>Math.hypot(point[0]-plan.origin[0],point[1]-plan.origin[1]));
 assert(Math.max(...radii)-Math.min(...radii)>.1,'front is not a constant-radius circle');
});

test('Travel sections move continuously, approach supplied coast, absorb locally, then leave a short hold',()=>{
 const plan=compileWaveVisualPlan(input);let maximumStep=0;
 for(const wave of plan.waves){
  let previous=null;
  for(let frame=wave.startFrame+1;frame<Math.floor(Math.min(...wave.samples.map(sample=>sample.arrivalFrame)));frame++){
   const front=evaluate(plan,frame).fronts.find(item=>item.id===wave.id);
   assert(front);assert.equal(front.geometry.coordinates.length,plan.sampleCount);
   if(previous)for(let index=0;index<front.geometry.coordinates.length;index++){
    const p=project(previous.geometry.coordinates[index]),q=project(front.geometry.coordinates[index]);
    maximumStep=Math.max(maximumStep,Math.hypot(q[0]-p[0],q[1]-p[1]));
   }
   previous=front;
  }
 }
 assert(maximumStep<8,'no per-frame camera-independent curve jump');
 const contactPhase=evaluate(plan,Math.ceil(plan.firstContactFrame)+10);
 assert(contactPhase.fronts.some(item=>item.phase==='COAST_ABSORPTION'));
 assert(contactPhase.fronts.some(item=>item.alpha>0));
 const hold=evaluate(plan,239);assert.equal(hold.hold,true);assert.equal(hold.fronts.length,0);
 assert.equal(hold.coastfrontHighlights.length,0);assert(plan.totalFrames-plan.completeFrame>=24);
});

test('Coast arrival is distance-ordered, local, one-shot, and never an entire-coast simultaneous flash',()=>{
 const plan=compileWaveVisualPlan(input),events=new Map(),activeCounts=[];
 for(let frame=0;frame<plan.totalFrames;frame++){
  const value=evaluate(plan,frame);activeCounts.push(value.coastfrontHighlights.length);
  for(const item of value.coastfrontHighlights){
   const previous=events.get(item.id)??[];previous.push(frame);events.set(item.id,previous);
   const contact=plan.contacts.find(contact=>contact.id===item.id);
   assert.deepEqual(item.geometry,contact.geometry);assert.equal(item.singleOccurrence,true);
   assert.equal(item.arrivalFrame,contact.arrivalFrame);
   assert(item.linePrimitive.totalLengthPixels<150);
  }
 }
 assert.equal(events.size,plan.contactCount);assert(Math.max(...activeCounts)<plan.contactCount);
 for(const frames of events.values())for(let index=1;index<frames.length;index++)assert.equal(frames[index],frames[index-1]+1);
 const ordered=[...plan.contacts].sort((a,b)=>a.distance-b.distance);
 assert(ordered.every((contact,index)=>index===0||contact.arrivalFrame>=ordered[index-1].arrivalFrame));
});

test('Origin pulse occurs once, remains an open front and uses measured screen scale',()=>{
 const plan=compileWaveVisualPlan(input),frames=[];
 for(let frame=0;frame<plan.totalFrames;frame++){
  const value=evaluate(plan,frame);if(value.originPulse.active){frames.push(frame);
   const points=value.originPulse.front.geometry.coordinates.map(project),origin=project(plan.origin),
    extent=Math.max(...points.map(point=>Math.hypot(point[0]-origin[0],point[1]-origin[1])));
   assert(extent>24&&extent<90);assert.equal(value.originPulse.repeatCount,1);
  }
 }
 assert(frames.length>0);assert.equal(frames[0],plan.startFrame+1);
 for(let index=1;index<frames.length;index++)assert.equal(frames[index],frames[index-1]+1);
 assert.equal(evaluate(plan,80).originPulse.active,false);
});

test('Malformed source, closed ring, excess wave count, no hold and invalid frames are rejected',()=>{
 assert.throws(()=>compileWaveVisualPlan({...input,wave_count:4}),/TWO_OR_THREE/);
 assert.throws(()=>compileWaveVisualPlan({...input,total_frames:150}),/POST_ARRIVAL_HOLD/);
 assert.throws(()=>compileWaveVisualPlan({...input,data_mode:'PRODUCTION'}),/VERIFIED_PRODUCTION_SOURCE/);
 assert.throws(()=>compileWaveVisualPlan({...input,coastGeometry:{type:'LineString',coordinates:[[0,0],[0,1],[0,0]]}}),/CLOSED_COAST_RING/);
 const plan=compileWaveVisualPlan(input);
 assert.throws(()=>evaluate(plan,-1),/FRAME_INTEGER/);assert.throws(()=>evaluate(plan,240),/FRAME_OUT_OF_RANGE/);
 assert.throws(()=>evaluateWaveVisualFrame(plan,20),/EXISTING_PROJECTION/);
 const stale=JSON.parse(JSON.stringify(plan));stale.waves[0].samples[0].duration++;
 assert.throws(()=>assertWaveVisualPlan(stale),/NON_CANONICAL/);
});
