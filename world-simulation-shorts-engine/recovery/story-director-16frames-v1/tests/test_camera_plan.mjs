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
 baseCameraPlan=await json(new URL('../../planner-scene-json-v1/fixtures/camera-plan.json',import.meta.url)),
 regional=await json(new URL('../../planner-scene-json-v1/fixtures/REGIONAL-plan.json',import.meta.url)),
 minimumBounds=regional.framing.bounds;
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
  safeArea:[48,72,1032,1848],minimumBounds,validateBounds:()=>({valid:true})});
 assert.equal(compiled.nativeLayoutPreflight.framesChecked,2400);
 assert.equal(compiled.nativeLayoutPreflight.sourceCropFrameCount,0);
 const samples=Array.from({length:2400},(_,frame)=>camera.evaluateStoryDirectorCamera(compiled,frame));
 assert.ok(compiled.nativeLayoutPreflight.maximumZoomRatio>1);
 assert.ok(compiled.nativeLayoutPreflight.maximumCenterStepPixels>0);
 assert.ok(samples.some(row=>row.cameraOnlyLocalClockReversed));
 assert.equal(samples.every(row=>row.sceneClockReset===false&&row.productionEligible===false),true);
 assert.equal(samples.every(row=>row.closerThanOriginalNativeFloor===false),true);
 for(const entry of compiled.entries){const first=samples[entry.startFrame],last=samples[entry.endFrame-1];
  assert.deepEqual(first.flatBounds,entry.startBounds);assert.deepEqual(last.flatBounds,entry.targetBounds);
  if(entry.startFrame)assert.deepEqual(first.flatBounds,samples[entry.startFrame-1].flatBounds);
 }
 assert.equal(new Set(samples.filter(row=>row.frame%150===0).map(row=>JSON.stringify(row.flatBounds))).size>=8,true);
});
test('unchanged real renderer updateCamera guard rejects the observed old target and accepts every floored frame',async()=>{
 const renderer=await readFile(new URL('../../../web/map_infographic_v1/renderer.mjs',import.meta.url),'utf8'),
  start=renderer.indexOf('function updateCamera(nextBounds){'),end=renderer.indexOf('\n function setScaleVisual(',start),
  exactSource=renderer.slice(start,end);
 assert.ok(start>0&&end>start&&exactSource.includes("code:'LOCAL_NOT_ADMITTED'"));
 const actualGuard=new Function('layoutPlan','plan',`
  const isGlobe=false,cos=1,c=0,lat=0;let currentBounds;
  const camera={position:{set(){}},updateProjectionMatrix(){},updateMatrixWorld(){}},
   uniforms={bounds:{value:{set(){}}},canonicalPixelDegrees:{value:{set(){}}}},
   evidence={},screen=()=>[],draw=()=>{},idScene={},idTarget={},covScene={},covTarget={};
  ${exactSource};return updateCamera;`)(regional,regional);
 const observedFailedTarget=[124.42457529230768,32.05734157622228,130.13704670769232,40.25691642377772];
 assert.throws(()=>actualGuard(observedFailedTarget),error=>error.code==='LOCAL_NOT_ADMITTED'&&error.category==='DATA_ADMISSION');
 const compiled=camera.compileStoryDirectorCamera({profile,plan,frontProfile,baseCameraPlan,currentNativeFrame:176,
  safeArea:[48,72,1032,1848],minimumBounds,validateBounds:bounds=>{
   try{actualGuard(bounds);return{valid:true};}catch{return{valid:false};}
  }});
 for(let frame=0;frame<2400;frame++)assert.doesNotThrow(()=>actualGuard(camera.evaluateStoryDirectorCamera(compiled,frame).flatBounds));
});
test('camera-only reverse velocity matches global bounds and every hold reports zero velocity',()=>{
 const compiled=camera.compileStoryDirectorCamera({profile,plan,frontProfile,baseCameraPlan,currentNativeFrame:176,
  safeArea:[48,72,1032,1848],minimumBounds,validateBounds:()=>({valid:true})});
 let checked=0;
 for(let frame=1;frame<2398;frame++){
  const row=camera.evaluateStoryDirectorCamera(compiled,frame),next=camera.evaluateStoryDirectorCamera(compiled,frame+1),
   delta=Math.log((next.flatBounds[3]-next.flatBounds[1])/(row.flatBounds[3]-row.flatBounds[1]));
  if(row.cameraLocked)assert.ok(Object.values(row.velocity).every(value=>value===0));
  if(row.cameraOnlyLocalClockReversed&&Math.abs(delta)>1e-8&&Math.abs(row.velocity.logHeightPerSecond)>1e-8){
   assert.equal(Math.sign(row.velocity.logHeightPerSecond),Math.sign(delta));checked++;
  }
 }
 assert.ok(checked>0);
});
test('unsupported or missing source fields fail, no arbitrary historical coordinate fallback',()=>{
 const altered=structuredClone(profile);altered.chapters[0].eventId='UNSOURCED_EVENT';
 assert.throws(()=>camera.validateDirectorCameraProfile(altered,plan),/ORIGINAL_CHAPTER_BINDING/);
 const row=structuredClone(profile.chapters[0]);row.geometryRefs=['UNSOURCED_GEOMETRY'];
 assert.throws(()=>camera.resolveDirectorChapterGeometry({plan,frontProfile,row}),/SOURCE_GEOMETRY_MISSING/);
});
test('explicit duplicate headline policy changes only original title reveal, source is immutable',()=>{
 const original={primary:1,country:1,marker:.75,location:1,title:1,disclosure:1},before=structuredClone(original),
  visible=camera.directorVisibleReveal(original,{hideDuplicateNativeHeadline:true});
 assert.deepEqual(original,before);assert.deepEqual(visible,{...original,title:0});
 assert.deepEqual(camera.directorVisibleReveal(original,{}),original);
 assert.notEqual(visible,original);
});
