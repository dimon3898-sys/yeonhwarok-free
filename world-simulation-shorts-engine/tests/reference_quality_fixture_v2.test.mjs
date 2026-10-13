import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,
 geoToPresentationScreen,presentationScreenToGeo} from '../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
const load=p=>JSON.parse(readFileSync(new URL(p,import.meta.url),'utf8'));
const scene=load('../recovery/reference-quality-rework-v2/fixtures/SCENE_PLAN.json'),
 prior=load('../recovery/reference-reproduction-v1/fixtures/SCENE_PLAN.json'),
 cameraPlan=load('../recovery/planner-scene-json-v1/fixtures/camera-plan.json'),
 camera=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame:176,
  keyframes:scene.cameraKeyframes,totalFrames:150,fps:30}),
 presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
  totalFrames:150,fps:30,overscan:scene.presentationProfile.overscan,width:1080,height:1920});

test('All 150 genuine Native views stay wider than the unchanged inherited visual endpoint',()=>{
 const floor=prior.cameraKeyframes.at(-1).bounds;
 for(let f=0;f<150;f++){
  const c=evaluateReferenceCameraTrackFrame(camera,f),p=evaluateReferencePresentationFrame(presentation,f),
   b=expandNativeBounds({bounds:c.flatBounds,referenceStartBounds:camera.startBounds,
    rollDegrees:p.rollDegrees,overscan:p.overscan,width:1080,height:1920});
  assert(b[2]-b[0]>=floor[2]-floor[0]);assert(b[3]-b[1]>=floor[3]-floor[1]);
  assert(p.noCornerClip);assert.equal(c.surveyAdmissionPreserved,true);assert.equal(c.cameraLocked,false);
 }
});

test('Measured complementary territory advances over precisely the original country geometries',()=>{
 assert.deepEqual(scene.controlIntent.domain,prior.controlIntent.domain);
 const plan=compileTerritoryControlPlan(scene.controlIntent),before=JSON.stringify(scene.controlIntent);
 let samples=0,previous=new Map();
 for(let f=0;f<150;f++){
  const control=evaluateTerritoryControlFrame(plan,f);
  for(let lon=124.4;lon<=130.9;lon+=.2)for(let lat=34;lat<=42.7;lat+=.2){
   const q=[lon,lat],r=classifyControlPoint(control,q),key=q.join(',');
   if(!r.inDomain)continue;samples++;assert.equal(Number(r.winner)+Number(r.loser),1);
   if(previous.get(key))assert(r.winner);previous.set(key,r.winner);
  }
 }
 assert(samples>40000);assert.equal(JSON.stringify(scene.controlIntent),before);
 assert.equal(scene.style.interfaceWidthPixels,0);assert.equal(scene.style.interfaceColor[3],0);
});

test('All eight measured units use the same roll-aware geography as the actual rendered map',()=>{
 assert.equal(scene.combatProfile.units.length,8);
 for(let f=0;f<150;f++){
  const c=evaluateReferenceCameraTrackFrame(camera,f),p=evaluateReferencePresentationFrame(presentation,f),
   b=expandNativeBounds({bounds:c.flatBounds,referenceStartBounds:camera.startBounds,
    rollDegrees:p.rollDegrees,overscan:p.overscan,width:1080,height:1920});
  for(const unit of scene.combatProfile.units){
   const q=unit.anchor_frames[f];
   const roundtrip=presentationScreenToGeo(geoToPresentationScreen(q,b,p),b,p);
   assert(Math.hypot(roundtrip[0]-q[0],roundtrip[1]-q[1])<1e-10);
  }
 }
});
