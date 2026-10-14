import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,
 geoToPresentationScreen,presentationScreenToGeo} from '../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {validateNationalUnitBadgeFixture,evaluateNationalUnitBadgeLayout}
 from '../web/map_infographic_v1/national_unit_badge_v1.mjs';
const load=p=>JSON.parse(readFileSync(new URL(p,import.meta.url),'utf8'));
const scene=load('../recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json'),
 parent=load('../recovery/map-visual-upgrade-v1/fixtures/SCENE_PLAN.json'),
 admitted=load('../recovery/reference-reproduction-v1/fixtures/SCENE_PLAN.json'),
 cameraPlan=load('../recovery/planner-scene-json-v1/fixtures/camera-plan.json'),
 nativePlan=load('../recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json'),
 camera=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:176,
  keyframes:scene.cameraKeyframes,totalFrames:150,fps:30}),
 parentCamera=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:176,
  keyframes:parent.cameraKeyframes,totalFrames:150,fps:30}),
 presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
  totalFrames:150,fps:30,overscan:scene.presentationProfile.overscan,width:1080,height:1920}),
 controls=compileTerritoryControlPlan(scene.controlIntent),
 parentControls=compileTerritoryControlPlan(parent.controlIntent);
const actualFrame=frame=>{
 const cameraFrame=evaluateReferenceCameraTrackFrame(camera,frame),
  state=evaluateReferencePresentationFrame(presentation,frame),
  bounds=expandNativeBounds({bounds:cameraFrame.flatBounds,referenceStartBounds:camera.startBounds,
   rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true});
 return {cameraFrame,state,bounds,project:geo=>geoToPresentationScreen(geo,bounds,state)};
};

test('New material/unit scene preserves the complete saved camera, rotation and control geometry/timeline',()=>{
 assert.equal(scene.schema,'MAP_ENGINE_UNIT_SCENE_V4');
 assert.equal(scene.version,'MAP_ENGINE_UNIT_SCENE_V4');
 assert.deepEqual(scene.cameraKeyframes,parent.cameraKeyframes);
 assert.deepEqual(scene.presentationProfile,parent.presentationProfile);
 assert.deepEqual(scene.controlIntent,parent.controlIntent);
 for(let frame=0;frame<150;frame++){
  assert.deepEqual(evaluateReferenceCameraTrackFrame(camera,frame),evaluateReferenceCameraTrackFrame(parentCamera,frame));
  assert.deepEqual(evaluateTerritoryControlFrame(controls,frame),evaluateTerritoryControlFrame(parentControls,frame));
 }
});

test('All 150 native views preserve the existing admitted floor and co-register map graphics without corner clipping',()=>{
 const floor=admitted.cameraKeyframes.at(-1).bounds;
 for(let frame=0;frame<150;frame++){
  const {cameraFrame,state,bounds,project}=actualFrame(frame);
  assert(bounds[2]-bounds[0]>=floor[2]-floor[0]);assert(bounds[3]-bounds[1]>=floor[3]-floor[1]);
  assert.equal(cameraFrame.surveyAdmissionPreserved,true);assert.equal(cameraFrame.cameraLocked,false);
  assert.equal(state.noCornerClip,true);
  for(const unit of scene.combatProfile.units){
   const geo=unit.anchor_frames[frame],roundtrip=presentationScreenToGeo(project(geo),bounds,state);
   assert(Math.hypot(roundtrip[0]-geo[0],roundtrip[1]-geo[1])<1e-10);
  }
 }
});

test('Complementary territory has exactly one owner at every sampled land point and cannot retreat',()=>{
 assert.deepEqual(scene.style.existingWinningColor,scene.style.gainedWinningColor);
 assert.equal(scene.style.interfaceWidthPixels,0);assert.equal(scene.style.interfaceColor[3],0);
 const previous=new Map();let samples=0;
 for(let frame=0;frame<150;frame++){
  const state=evaluateTerritoryControlFrame(controls,frame);
  for(let lon=124.4;lon<=130.9;lon+=.2)for(let lat=34;lat<=42.7;lat+=.2){
   const point=[lon,lat],control=classifyControlPoint(state,point),key=point.join(',');
   if(!control.inDomain)continue;samples++;
   assert.equal(Number(control.winner)+Number(control.loser),1);
   if(previous.get(key))assert(control.winner);
   previous.set(key,control.winner);
  }
 }
 assert(samples>40000);
});

test('All original eight unit paths remain recorded while resolved national tablets stay safe and collision-free for 150 frames',()=>{
 const before=JSON.stringify(scene.combatProfile),fixture=validateNationalUnitBadgeFixture(scene.combatProfile.units,scene.combatProfile.profiles);
 assert.equal(fixture.units,8);assert.equal(fixture.frames,150);
 assert.deepEqual(scene.combatProfile.units.map(unit=>unit.id),parent.combatProfile.units.map(unit=>unit.id));
 for(const unit of scene.combatProfile.units){
  const original=parent.combatProfile.units.find(value=>value.id===unit.id);
  assert.deepEqual(unit.source_anchor_frames,original.anchor_frames);
  assert.deepEqual(unit.rotation_frames,original.rotation_frames);
 }
 for(let frame=0;frame<150;frame++){
  const {project}=actualFrame(frame),layout=evaluateNationalUnitBadgeLayout(scene.combatProfile.units,frame,
   {project,safeArea:nativePlan.layout.safe,protectedGraphics:[]});
  assert.deepEqual(layout.safeAreaViolations,[]);assert.deepEqual(layout.criticalCollisions,[]);
  assert.deepEqual(layout.unitOverlaps,[]);assert.equal(layout.noRenderedText,true);
  assert.equal(layout.sourceIconArtworkCopied,false);assert.equal(layout.historicalPolicyApplied,false);
  assert(layout.units.every(unit=>unit.actualArtworkInsideProtectedFootprint&&unit.flagWidthPx>=46));
 }
 assert.equal(JSON.stringify(scene.combatProfile),before);
});
