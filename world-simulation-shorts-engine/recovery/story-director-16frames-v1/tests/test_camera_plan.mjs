/** CPU camera contract checks only. No pixels or hardware are claimed. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFile} from 'node:fs/promises';
const modules=new URL('../../../web/map_infographic_v1/',import.meta.url),
 production=new URL('../../universal-production-v3/',import.meta.url),
 hook=registerHooks({resolve(specifier,context,next){
  if(specifier.startsWith('/modules/'))return{url:new URL(specifier.slice('/modules/'.length),modules).href,shortCircuit:true};
  if(specifier.startsWith('/production-v3/'))return{url:new URL(specifier.slice('/production-v3/'.length),production).href,shortCircuit:true};
  return next(specifier,context);
 }});
let camera;try{camera=await import('../camera_plan.mjs');}finally{hook.deregister();}
const json=async url=>JSON.parse(await readFile(url,'utf8')),
 plan=await json(new URL('../../verified-front-data-v4-recovery/VIDEO_PLAN_80S.json',import.meta.url)),
 frontProfile=await json(new URL('../../verified-front-data-v4-recovery/FRONT_PROFILE.json',import.meta.url)),
 profile=await json(new URL('../DIRECTOR_CAMERA_PROFILE.json',import.meta.url)),
 baseCameraPlan=await json(new URL('../../planner-scene-json-v1/fixtures/camera-plan.json',import.meta.url));
test('all 12 existing chapters and actual source references are exact, source remains unchanged',()=>{
 const before=JSON.stringify({plan,frontProfile}),settings=camera.validateDirectorCameraProfile(profile,plan);
 for(const row of settings.chapters){const resolved=camera.resolveDirectorChapterGeometry({plan,frontProfile,row});
  assert.equal(resolved.geometries.length,row.geometryRefs.length);
  assert.ok(resolved.locations.every(item=>item.meaning==='GEOGRAPHIC_CONTEXT_ONLY_NOT_HISTORICAL_UNIT_POSITION'));
 }
 assert.equal(JSON.stringify({plan,frontProfile}),before);
});
test('actual original reference-camera adapter evaluates global 2400 frames, pan/zoom/holds and boundaries',()=>{
 const compiled=camera.compileStoryDirectorCamera({profile,plan,frontProfile,baseCameraPlan,currentNativeFrame:176,
  safeArea:[48,72,1032,1848],validateBounds:()=>({valid:true})});
 assert.equal(compiled.nativeLayoutPreflight.framesChecked,2400);
 const samples=Array.from({length:2400},(_,frame)=>camera.evaluateStoryDirectorCamera(compiled,frame));
 assert.ok(compiled.nativeLayoutPreflight.maximumZoomRatio>1.1);
 assert.ok(compiled.nativeLayoutPreflight.maximumCenterStepPixels>0);
 assert.ok(samples.some(row=>row.cameraOnlyLocalClockReversed));
 assert.equal(samples.every(row=>row.sceneClockReset===false&&row.productionEligible===false),true);
 for(const entry of compiled.entries){const first=samples[entry.startFrame],last=samples[entry.endFrame-1];
  assert.deepEqual(first.flatBounds,entry.startBounds);assert.deepEqual(last.flatBounds,entry.targetBounds);
  if(entry.startFrame)assert.deepEqual(first.flatBounds,samples[entry.startFrame-1].flatBounds);
 }
 assert.equal(new Set(samples.filter(row=>row.frame%150===0).map(row=>JSON.stringify(row.flatBounds))).size>=8,true);
});
test('unsupported or missing source fields fail, no arbitrary historical coordinate fallback',()=>{
 const altered=structuredClone(profile);altered.chapters[0].eventId='UNSOURCED_EVENT';
 assert.throws(()=>camera.validateDirectorCameraProfile(altered,plan),/ORIGINAL_CHAPTER_BINDING/);
 const row=structuredClone(profile.chapters[0]);row.geometryRefs=['UNSOURCED_GEOMETRY'];
 assert.throws(()=>camera.resolveDirectorChapterGeometry({plan,frontProfile,row}),/SOURCE_GEOMETRY_MISSING/);
});
