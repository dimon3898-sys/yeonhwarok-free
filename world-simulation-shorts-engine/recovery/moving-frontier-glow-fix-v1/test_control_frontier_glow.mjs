/** Focused, pure regression for the isolated glow-profile change.
 * No native rendering, story/timing rewrite or broad suite runs here.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,sampleControlBoundary}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileControlFrontierLightMotion,evaluateControlFrontierLightMotion,validateControlFrontierLightProfile,
 controlTerrainLightingFactor} from '../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
const read=relative=>JSON.parse(readFileSync(new URL(relative,import.meta.url),'utf8'));
const scene=read('./fixtures/SCENE_PLAN.json'),parent=read('../map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json'),
 off=read('./fixtures/SCENE_GLOW_OFF.json'),core=read('./fixtures/SCENE_CORE_ONLY.json'),
 cameraPlan=read('../planner-scene-json-v1/fixtures/camera-plan.json'),admitted=read('../reference-reproduction-v1/fixtures/SCENE_PLAN.json'),
 plan=compileTerritoryControlPlan(scene.controlIntent),oldPlan=compileTerritoryControlPlan(parent.controlIntent),
 profile=validateControlFrontierLightProfile(scene.frontierProfile),motion=compileControlFrontierLightMotion(plan,profile);
const frozenKeys=['controlIntent','cameraKeyframes','style','terrainProfile','presentationProfile','combatProfile'];
const compileCamera=input=>compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:176,
 keyframes:input.cameraKeyframes,totalFrames:150,fps:30});

test('Glow-only scenes preserve every camera/control/material/unit input; variants change only edge alpha and descriptive profile name',()=>{
 for(const key of frozenKeys)assert.deepEqual(scene[key],parent[key],key);
 for(const variant of [off,core])for(const key of frozenKeys)assert.deepEqual(variant[key],scene[key],key);
 for(const key of ['luminanceAnchor','minimumLightingFactor','reliefLightingEnabled']){
  assert.equal(scene.frontierProfile[key],parent.frontierProfile[key],key);
  assert.equal(off.frontierProfile[key],scene.frontierProfile[key],key);
  assert.equal(core.frontierProfile[key],scene.frontierProfile[key],key);
 }
 assert.equal(off.frontierProfile.centerAlpha,0);assert.equal(off.frontierProfile.haloAlpha,0);
 assert.equal(core.frontierProfile.centerAlpha,profile.centerAlpha);assert.equal(core.frontierProfile.haloAlpha,0);
 for(const variant of [off,core]){
  const stripped=structuredClone(variant.frontierProfile);stripped.centerAlpha=profile.centerAlpha;stripped.haloAlpha=profile.haloAlpha;
  // Private variant names describe the capture; they are not shader uniforms.
  stripped.profileName=scene.frontierProfile.profileName;
  assert.deepEqual(stripped,scene.frontierProfile);
 }
 for(let index=0;index<=100;index++){
  const rgb=[index/100,index/100,index/100];
  assert.equal(controlTerrainLightingFactor(rgb,profile),controlTerrainLightingFactor(rgb,parent.frontierProfile));
 }
});

test('All 150 glow frames use exactly the same actual scalar boundary and unaltered moving camera',()=>{
 const before=JSON.stringify(scene),camera=compileCamera(scene),oldCamera=compileCamera(parent),
  presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
   totalFrames:150,fps:30,overscan:scene.presentationProfile.overscan,width:1080,height:1920}),floor=admitted.cameraKeyframes.at(-1).bounds;
 assert.equal(motion.domainGeometryBinding,plan.domainGeometryBinding);
 assert.equal(motion.boundaryKeyframeBinding,plan.boundaryKeyframeBinding);
 for(let frame=0;frame<150;frame++){
  const controls=evaluateTerritoryControlFrame(plan,frame),old=evaluateTerritoryControlFrame(oldPlan,frame),
   light=evaluateControlFrontierLightMotion(motion,frame),position=evaluateReferenceCameraTrackFrame(camera,frame),
   state=evaluateReferencePresentationFrame(presentation,frame),bounds=expandNativeBounds({bounds:position.flatBounds,
    referenceStartBounds:camera.startBounds,rollDegrees:state.rollDegrees,overscan:state.overscan,
    width:1080,height:1920,correctMeasuredPan:true});
  assert.deepEqual(controls,old);assert.deepEqual(position,evaluateReferenceCameraTrackFrame(oldCamera,frame));
  assert.equal(light.advancing,true);assert.equal(light.stopAssumedAtOutputEnd,false);
  assert(light.strength>=profile.settledStrength&&light.strength<=1);
  assert.equal(state.noCornerClip,true);assert.equal(position.surveyAdmissionPreserved,true);
  assert(bounds[2]-bounds[0]>=floor[2]-floor[0]);assert(bounds[3]-bounds[1]>=floor[3]-floor[1]);
  for(let knot=0;knot<controls.longitudinalKnots.length;knot++){
   assert.equal(sampleControlBoundary(controls,controls.longitudinalKnots[knot]),controls.boundaryLatitudes[knot]);
   if(knot+1<controls.longitudinalKnots.length){
    const longitude=(controls.longitudinalKnots[knot]+controls.longitudinalKnots[knot+1])/2;
    assert(Math.abs(sampleControlBoundary(controls,longitude)-(controls.boundaryLatitudes[knot]+controls.boundaryLatitudes[knot+1])/2)<1e-10);
   }
  }
 }
 assert.equal(JSON.stringify(scene),before);
});

test('A separate generic private stop gently settles after actual motion; public frame 149 is not falsely faded',()=>{
 const syntheticIntent={semantic_mode:'FACT_BASED_VISUAL_CONTROL',
  source:{source_type:'SYNTHETIC',source_reference:'GENERIC_STYLE_STOP_FIXTURE',verification_status:'SYNTHETIC'},
  domain:[{id:'GENERIC_LAND',geometry:{type:'Polygon',coordinates:[[[0,0],[2,0],[2,2],[0,2],[0,0]]]}}],
  factions:{winner:{id:'FIRST'},loser:{id:'SECOND'}},longitudinal_knots:[0,2],base_boundary_latitudes:[.5,.5],
  advance_direction:'POSITIVE_LATITUDE',fps:30,total_frames:60,start_frame:7,
  boundary_keyframes:[{frame:0,latitudes:[.5,.5]},{frame:20,latitudes:[1.5,1.5]},{frame:59,latitudes:[1.5,1.5]}],interpolation:'LINEAR'},
  stoppedPlan=compileTerritoryControlPlan(syntheticIntent),stoppedMotion=compileControlFrontierLightMotion(stoppedPlan,profile),
  stopFrame=stoppedPlan.startFrame+20,settleFrame=stopFrame+profile.velocityWindowFrames;
 const ramp=Array.from({length:profile.velocityWindowFrames*2+1},(_,offset)=>
  evaluateControlFrontierLightMotion(stoppedMotion,stopFrame-profile.velocityWindowFrames+offset).strength);
 for(let i=1;i<ramp.length;i++)assert(ramp[i]<=ramp[i-1]+1e-12);
 assert(ramp[0]>.9);assert.equal(ramp.at(-1),profile.settledStrength);
 for(const frame of [settleFrame,66,settleFrame,60]){
  const light=evaluateControlFrontierLightMotion(stoppedMotion,frame);
  assert.equal(light.strength,profile.settledStrength);assert.equal(light.advancing,false);
 }
 assert.equal(evaluateControlFrontierLightMotion(motion,149).advancing,true);
 assert.equal(motion.syntheticPulse,false);assert.equal(motion.stopAssumedAtOutputEnd,false);
});

test('Shuffled repeat evaluation is deterministic without flashes, geometry mutation or a second motion engine',()=>{
 const sequential=Array.from({length:150},(_,frame)=>evaluateControlFrontierLightMotion(motion,frame));
 for(const frame of [149,0,74,38,112,74,149])assert.deepEqual(evaluateControlFrontierLightMotion(motion,frame),sequential[frame]);
 assert.equal(profile.reliefLightingEnabled,true);assert(profile.centerWidthPixels<=2.5);
 assert(profile.haloSupportPixels<=10);assert(profile.haloAlpha<=.35);
});
