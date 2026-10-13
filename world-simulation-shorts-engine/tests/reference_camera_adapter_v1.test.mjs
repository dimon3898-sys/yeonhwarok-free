import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {evaluateMinimumContextCameraFrame} from '../web/map_infographic_v1/camera_director_v5.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame,assertReferenceCameraTrackPlan,
 assessReferenceCameraMotion} from '../web/map_infographic_v1/reference_camera_adapter_v1.mjs';

const base=JSON.parse(readFileSync(new URL('../recovery/planner-scene-json-v1/fixtures/camera-plan.json',import.meta.url),'utf8'));
const keyframes=()=>[{frame:0,bounds:[-4,-6,4,6]},{frame:75,bounds:[-3.7,-4.4,3.7,6.7]},
 {frame:149,bounds:[-3.4,-2.8,3.4,7.4]}];
const input=()=>({baseCameraPlan:structuredClone(base),currentNativeFrame:176,keyframes:keyframes(),totalFrames:150,fps:30});
const compile=()=>compileReferenceCameraTrack(input());

test('actual base V5 state, admission, and source inputs remain byte unchanged',()=>{
 const source=input(),before=JSON.stringify(source),p=compileReferenceCameraTrack(source);
 assert.equal(JSON.stringify(source),before);
 assert.deepEqual(p.baseCameraState,evaluateMinimumContextCameraFrame(base,176));
 assert.deepEqual(p.admission.survey,base.admission);assert.equal(p.admission.admitted,false);
 assert.equal(p.ownership.eventOwnsCamera,false);assert.equal(p.ownership.arrivalReadinessForged,false);
});
test('150 deterministic samples hit exact keys and follow moving center with shrinking span',()=>{
 const p=compile(),e=assessReferenceCameraMotion(p);
 assert.equal(e.framesChecked,150);assert(e.exactKeyframes);assert.equal(e.qualityParityClaimed,false);
 let latitude=-Infinity,width=Infinity;
 for(let frame=0;frame<150;frame++){
  const camera=evaluateReferenceCameraTrackFrame(p,frame);
  assert(camera.center[1]>=latitude);assert(camera.extent[0]<=width);
  latitude=camera.center[1];width=camera.extent[0];
  assert.equal(camera.cameraLocked,false);assert.equal(camera.settle.locked,false);
  assert.equal(camera.visualAdmission,'STATIC_NATIVE_PROBE_REQUIRED');
  assert.deepEqual(camera.admission,base.admission);
 }
 assert(e.maximumNormalizedCornerStep<.01);
 assert(e.maximumCenterStepPixels<6);
});
test('shared joins preserve continuous position and velocity without resetting the motion',()=>{
 const p=compile(),first=p.segments[0],second=p.segments[1];
 assert.deepEqual(first.to,second.from);assert.deepEqual(first.endVelocity,second.startVelocity);
 assert(evaluateReferenceCameraTrackFrame(p,74).velocity.latitudeDegreesPerSecond>0);
 assert(evaluateReferenceCameraTrackFrame(p,75).velocity.latitudeDegreesPerSecond>0);
 assert(evaluateReferenceCameraTrackFrame(p,76).velocity.latitudeDegreesPerSecond>0);
 assert.equal(assessReferenceCameraMotion(p).accelerationContinuity,'NOT_CLAIMED_C1_TRACK');
});
test('two-keyframe excerpt has sustained motion rather than artificial arrival easing',()=>{
 const source=input();source.keyframes=[source.keyframes[0],source.keyframes.at(-1)];
 const p=compileReferenceCameraTrack(source),a=evaluateReferenceCameraTrackFrame(p,0),b=evaluateReferenceCameraTrackFrame(p,149);
 assert(a.velocity.latitudeDegreesPerSecond>0);assert.deepEqual(a.velocity,b.velocity);
 assert.equal(a.camera.noCloserThanApprovedStop,false);assert.equal(b.camera.noCloserThanApprovedStop,false);
 assert.deepEqual(a.flatBounds,source.keyframes[0].bounds);assert.deepEqual(b.flatBounds,source.keyframes[1].bounds);
});
test('random access, deep input copies and serialized contract reject changed camera claims',()=>{
 const given=input(),p=compileReferenceCameraTrack(given),before=evaluateReferenceCameraTrackFrame(p,110);
 given.keyframes[0].bounds[0]=-99;given.baseCameraPlan.anchor[0]=99;
 for(const frame of[149,0,75,2,140])evaluateReferenceCameraTrackFrame(p,frame);
 assert.deepEqual(evaluateReferenceCameraTrackFrame(p,110),before);
 assert(Object.isFrozen(p.keyframes[0].bounds));assert(Object.isFrozen(p.baseCameraState.admission));
 assert.deepEqual(assertReferenceCameraTrackPlan(JSON.parse(JSON.stringify(p))),p);
 const forged=JSON.parse(JSON.stringify(p));forged.admission.admitted=true;
 assert.throws(()=>assertReferenceCameraTrackPlan(forged),/NON_CANONICAL/);
});
test('invalid geography, unordered fractional frames and denied closest endpoint are rejected',()=>{
 for(const mutate of[s=>{s.keyframes[0].bounds=[1,0,0,1];},s=>{s.keyframes[0].frame=1;},
  s=>{s.keyframes[1].frame=1.2;},s=>{s.keyframes.at(-1).frame=150;},
  s=>{s.keyframes[1].bounds=[-2,-1,2,1];},s=>{s.currentNativeFrame=999;},s=>{s.fps=29;}]){
  const source=input();mutate(source);assert.throws(()=>compileReferenceCameraTrack(source),/REFERENCE_CAMERA/);
 }
 for(const frame of[-1,1.2,150])assert.throws(()=>evaluateReferenceCameraTrackFrame(compile(),frame),/REFERENCE_CAMERA/);
});
test('generic external adapter contains no country, event date, coordinate or route specialization',()=>{
 const source=readFileSync(new URL('../web/map_infographic_v1/reference_camera_adapter_v1.mjs',import.meta.url),'utf8');
 assert(!/Korea|Suez|Egypt|1950|38\.0|125\.|127\.|129\.|COUNTRY_KOR|PHASE_ROUTE/i.test(source));
 assert(!source.includes('compileMinimumContextPlan('));
 assert(!source.includes('cameraLocked:true'));
});
