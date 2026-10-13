/** Focused regression: the new material/icon scene may not retime or reshape
 * the previously persisted actual reference movement. This checks all150 states,
 * not just keyframe endpoints. GPU image quality is separately reviewed.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';

const readJson=async url=>JSON.parse(await readFile(url,'utf8'));
const previous=await readJson(new URL('../reference-quality-rework-v2/fixtures/SCENE_PLAN.json',import.meta.url));
const current=await readJson(new URL('./fixtures/SCENE_PLAN.json',import.meta.url));
const fixture=await readJson(new URL('../reference-quality-rework-v2/fixtures/RUNTIME_FIXTURE.json',import.meta.url));
const cameraPlan=await readJson(new URL('../../'+fixture.nativeFiles.cameraPlan,import.meta.url));
const makeTrack=scene=>compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:fixture.currentNativeFrame,
 keyframes:scene.cameraKeyframes,totalFrames:fixture.totalFrames,fps:fixture.fps});
const makePresentation=scene=>compileReferencePresentationPlan({
 rollKeyframes:scene.cameraKeyframes.map(key=>({frame:key.frame,rollDegrees:key.rotationDegrees})),
 totalFrames:fixture.totalFrames,fps:fixture.fps,overscan:scene.presentationProfile.overscan,width:1080,height:1920});

test('all150 control ownership states and original source geometry remain unchanged',()=>{
 assert.equal(current.version,'MAP_VISUAL_SCENE_V3');
 assert.deepEqual(current.controlIntent,previous.controlIntent);
 const before=compileTerritoryControlPlan(previous.controlIntent),after=compileTerritoryControlPlan(current.controlIntent);
 for(let frame=0;frame<150;frame++)assert.deepEqual(evaluateTerritoryControlFrame(after,after.startFrame+frame),
  evaluateTerritoryControlFrame(before,before.startFrame+frame));
});

test('all150 V5-linked camera and coherent roll states remain unchanged with safe corners',()=>{
 assert.deepEqual(current.cameraKeyframes,previous.cameraKeyframes);
 assert.deepEqual(current.presentationProfile,previous.presentationProfile);
 const before=makeTrack(previous),after=makeTrack(current),oldPresentation=makePresentation(previous),newPresentation=makePresentation(current);
 for(let frame=0;frame<150;frame++){
  const oldCamera=evaluateReferenceCameraTrackFrame(before,frame),camera=evaluateReferenceCameraTrackFrame(after,frame),
   oldState=evaluateReferencePresentationFrame(oldPresentation,frame),state=evaluateReferencePresentationFrame(newPresentation,frame);
  assert.deepEqual(camera,oldCamera);assert.deepEqual(state,oldState);assert.equal(state.noCornerClip,true);
  assert.deepEqual(expandNativeBounds({bounds:camera.flatBounds,referenceStartBounds:after.startBounds,
   rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true}),
   expandNativeBounds({bounds:oldCamera.flatBounds,referenceStartBounds:before.startBounds,
    rollDegrees:oldState.rollDegrees,overscan:oldState.overscan,width:1080,height:1920,correctMeasuredPan:true}));
 }
});

test('all8 original geographic unit anchors and heading timing remain unchanged',()=>{
 assert.equal(current.combatProfile.units.length,previous.combatProfile.units.length);
 assert.equal(current.combatProfile.units.length,8);
 for(const unit of current.combatProfile.units){
  const old=previous.combatProfile.units.find(item=>item.id===unit.id);
  assert.ok(old,'NEW_OR_SPECULATIVE_UNIT_FORBIDDEN');
  assert.deepEqual(unit.anchor_frames,old.anchor_frames);assert.deepEqual(unit.rotation_frames,old.rotation_frames);
  assert.equal(unit.anchor_frames.length,150);assert.equal(unit.rotation_frames.length,150);
 }
});

test('single faction fill and no decorative guide coexist with the actual moving-boundary effect',()=>{
 assert.deepEqual(current.style.existingWinningColor,current.style.gainedWinningColor);
 assert.equal(current.style.interfaceWidthPixels,0);assert.equal(current.style.interfaceColor[3],0);
 assert.ok(current.frontierProfile.profileName);assert.ok(current.terrainProfile.profileName);
});
