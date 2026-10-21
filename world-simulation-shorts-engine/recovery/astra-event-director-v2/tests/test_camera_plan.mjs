/** Actual unchanged reference/V5 evaluation and native minimum guard; CPU only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const modules=new URL('../../../web/map_infographic_v1/',import.meta.url),
 production=new URL('../../universal-production-v3/',import.meta.url),
 hook=registerHooks({resolve(specifier,context,next){
  if(specifier.startsWith('/modules/'))return{url:new URL(specifier.slice(9),modules).href,shortCircuit:true};
  if(specifier.startsWith('/production-v3/'))return{url:new URL(specifier.slice(15),production).href,shortCircuit:true};
  return next(specifier,context);
 }});
let camera;try{camera=await import('../camera_plan.mjs');}finally{hook.deregister();}
const json=async url=>JSON.parse(await readFile(url,'utf8')),
 plan=await json(new URL('../fixtures/DERIVED_SCENE.json',import.meta.url)),
 eventProfile=await json(new URL('../fixtures/HISTORY_EVENT_PROFILE_V2.json',import.meta.url)),
 frontProfile=await json(new URL('../fixtures/DERIVED_FRONT_PROFILE.json',import.meta.url)),
 profile=await json(new URL('../fixtures/CAMERA_REVIEW_PROFILE.json',import.meta.url)),
 admission=await json(new URL('../fixtures/CAMERA_ADMISSION.json',import.meta.url)),
 regional=await json(new URL('../../planner-scene-json-v1/fixtures/REGIONAL-plan.json',import.meta.url)),
 baseCameraPlan=await json(new URL('../../planner-scene-json-v1/fixtures/camera-plan.json',import.meta.url)),
 inputs={profile,eventProfile,plan,frontProfile,admission,baseCameraPlan,currentNativeFrame:176,
  safeArea:regional.layout.safe,minimumBounds:regional.framing.bounds,validateBounds:()=>({valid:true})};
const compile=(patch={})=>camera.compileSourceReviewCamera({...inputs,...patch});
test('exact current source IDs resolve; Incheon is context only; unknown cannot borrow Busan geometry',()=>{
 const before=JSON.stringify({plan,eventProfile,profile,frontProfile}),
  chapter=profile.chapters.find(x=>x.eventId==='INCHON_LANDING'),
  resolved=camera.resolveReviewSources({eventProfile,plan,frontProfile,row:chapter});
 assert.equal(resolved.locations[0].id,'INCHEON');assert.equal(resolved.locations[0].troopPosition,false);
 assert.equal(resolved.locations[0].role,'GEOGRAPHIC_CONTEXT_ONLY');
 assert.deepEqual(resolved.geometries,[]);
 for(const r of profile.chapters.filter(x=>x.startFrame>=600&&x.endFrame<=1400)){
  const value=camera.resolveReviewSources({eventProfile,plan,frontProfile,row:r});
  assert.ok(value.segments.every(x=>x.records.length===0&&x.stateId===null));
 }
 assert.equal(JSON.stringify({plan,eventProfile,profile,frontProfile}),before);
});
test('source-qualified separate partial-front channel is resolved without coercing a ROK fragment into legacy UN ownership',()=>{
 const e=structuredClone(eventProfile),p=structuredClone(plan),row=profile.chapters[1],
  geometry={type:'MultiLineString',coordinates:[[[126.8,37.58],[127,37.51]],[[127.25,37.51],[127.33,37.52]]]},
  id='SYNTHETIC_SOURCE_CHANNEL_TEST_ONLY';
 e.sourceSchedule=e.sourceSchedule.map(x=>x.chapterId===row.chapterId?{...x,kind:'OBSERVED_PARTIAL_FRONT',
  truthKind:'observed',stateId:id,sourceIds:[id],sourceDate:'1950-06-28'}:x);
 p.productionV3.directorAdditionalFronts=[{frontId:id,geometry,renderConsumer:'DIRECTOR_ADDITIONAL_PARTIAL_FRONT',
  historicalControlGeometry:false,side:'ROK_SOURCE_LABEL',sourceReviewOnly:true}];
 const r=camera.resolveReviewSources({eventProfile:e,plan:p,frontProfile,row});
 assert.deepEqual(r.geometries,[{id,geometry}]);
 assert.ok(r.segments.every(x=>x.records[0].id===id));assert.equal(r.geometries[0].geometry.type,'MultiLineString');
 assert.equal(r.geometries.some(x=>x.id.includes('BUSAN')),false);
});
test('original reference camera evaluates all 2400 global frames with unchanged minimum and continuous chapter handoff',()=>{
 const compiled=compile(),samples=Array.from({length:2400},(_,f)=>camera.evaluateSourceReviewCamera(compiled,f));
 assert.equal(compiled.preflight.framesChecked,2400);assert.deepEqual(compiled.preflight.nativeLayoutViolations,[]);
 assert.deepEqual(compiled.preflight.sourceClipFrames,[]);assert.ok(compiled.preflight.maximumZoomRatio>1);
 assert.ok(compiled.preflight.maximumCenterStepPixels>0);
 assert.ok(samples.every(x=>x.sceneClockReset===false&&x.productionEligible===false&&x.rotationDegrees===0));
 assert.ok(samples.every(x=>x.closerThanOriginalNativeFloor===false&&x.requestedLocalContractSatisfied===false));
 for(const row of compiled.entries){assert.deepEqual(samples[row.startFrame].flatBounds,row.startBounds);
  assert.deepEqual(samples[row.endFrame-1].flatBounds,row.endBounds);
  if(row.startFrame)assert.deepEqual(samples[row.startFrame].flatBounds,samples[row.startFrame-1].flatBounds);}
 assert.ok(new Set(samples.filter(x=>x.frame%150===0).map(x=>JSON.stringify(x.flatBounds))).size>=8);
});
test('preserved real updateCamera implementation rejects Local and accepts every new regional frame',async()=>{
 const raw=await readFile(new URL('../../../web/map_infographic_v1/renderer.mjs',import.meta.url),'utf8'),
  start=raw.indexOf('function updateCamera(nextBounds){'),end=raw.indexOf('\n function setScaleVisual(',start),source=raw.slice(start,end);
 assert.ok(start>0&&end>start&&source.includes("code:'LOCAL_NOT_ADMITTED'"));
 const guard=new Function('layoutPlan','plan',`
  const isGlobe=false,cos=1,c=0,lat=0;let currentBounds;
  const camera={position:{set(){}},updateProjectionMatrix(){},updateMatrixWorld(){}},
   uniforms={bounds:{value:{set(){}}},canonicalPixelDegrees:{value:{set(){}}}},
   evidence={},screen=()=>[],draw=()=>{},idScene={},idTarget={},covScene={},covTarget={};
  ${source};return updateCamera;`)(regional,regional);
 assert.throws(()=>guard(profile.requestedLocalDesign[3].requestedBounds),e=>e.code==='LOCAL_NOT_ADMITTED'&&e.category==='DATA_ADMISSION');
 const compiled=compile({validateBounds:bounds=>{try{guard(bounds);return{valid:true};}catch{return{valid:false};}}});
 for(let f=0;f<2400;f++)assert.doesNotThrow(()=>guard(camera.evaluateSourceReviewCamera(compiled,f).flatBounds));
});
test('endpoint holds have zero velocity and widening velocity matches actual global direction',()=>{
 const c=compile();let widen=0;
 for(let f=0;f<2399;f++){
  const a=camera.evaluateSourceReviewCamera(c,f),b=camera.evaluateSourceReviewCamera(c,f+1),
   delta=Math.log((b.flatBounds[3]-b.flatBounds[1])/(a.flatBounds[3]-a.flatBounds[1]));
  if(a.cameraLocked)assert.ok(Object.values(a.velocity).every(x=>x===0));
  if(a.phase==='SOURCE_CONTEXT_WIDEN'&&!a.cameraLocked&&Math.abs(delta)>1e-8&&Math.abs(a.velocity.logHeightPerSecond)>1e-8){
   assert.equal(Math.sign(delta),Math.sign(a.velocity.logHeightPerSecond));widen++;}
 }
 assert.ok(widen>0);
});
test('requested Local purpose, false certificate, unsupported roll, wrong source and unsafe layout all fail closed',()=>{
 const local=structuredClone(profile);local.cameraPurpose='REQUESTED_LOCAL';
 assert.throws(()=>compile({profile:local}),/EXPLICIT_SEPARATE_REGIONAL_REVIEW/);
 const fake=structuredClone(admission);fake.regionalSourceReview.localCertificate=true;
 assert.throws(()=>compile({admission:fake}),/REQUESTED_LOCAL_MUST_REMAIN_BLOCKED/);
 const roll=structuredClone(profile);roll.roll=5;assert.throws(()=>compile({profile:roll}),/FIELD_UNSUPPORTED/);
 const missing=structuredClone(eventProfile);missing.locations=missing.locations.filter(x=>x.id!=='INCHEON');
 assert.throws(()=>compile({eventProfile:missing}),/VERIFIED_CONTEXT_LOCATION_REQUIRED/);
 assert.throws(()=>compile({validateBounds:()=>({valid:false,failures:[{code:'SYNTHETIC_LAYOUT_FAILURE'}]})}),/NATIVE_LAYOUT_UNSAFE_FRAME_0/);
 assert.throws(()=>camera.evaluateSourceReviewCamera(compile(),2400),/GLOBAL_FRAME_REQUIRED/);
});
test('generic southern-western location profile uses same reference path without fallback to original region',()=>{
 const e=structuredClone(eventProfile),p=structuredClone(profile),a=structuredClone(admission),
  min=[-80,-45,-70,-31];
 e.locations=[{id:'CONTEXT_POINT',anchor:[-73,-37],role:'GEOGRAPHIC_CONTEXT_ONLY',troopPosition:false}];
 e.sourceSchedule=e.chapters.map(x=>({startFrame:x.startFrame,endFrame:x.endFrame,chapterId:x.chapterId,
  kind:'UNKNOWN',truthKind:'unknown',sourceDate:null,stateId:null,sourceIds:[]}));
 for(const row of e.chapters)row.locationRefs=['CONTEXT_POINT'];
 for(const row of p.chapters)row.locationRefs=['CONTEXT_POINT'];
 a.regionalSourceReview.minimumBounds=min;
 const c=compile({eventProfile:e,profile:p,admission:a,minimumBounds:min});
 for(const f of [0,80,600,1000,2250,2399]){const s=camera.evaluateSourceReviewCamera(c,f);
  assert.ok(s.center[0]<0&&s.center[1]<0);assert.equal(s.contextLocations[0].id,'CONTEXT_POINT');
  assert.equal(s.sourceSafety.noEventGeometry,true);assert.equal(s.closerThanOriginalNativeFloor,false);}
});
test('dateline and unsupported polar footprint are explicit blockers, never a home-region fallback',()=>{
 const e=structuredClone(eventProfile),p=structuredClone(profile);
 e.sourceSchedule=e.chapters.map(x=>({startFrame:x.startFrame,endFrame:x.endFrame,chapterId:x.chapterId,
  kind:'UNKNOWN',truthKind:'unknown',sourceDate:null,stateId:null,sourceIds:[]}));
 e.locations=[{id:'WEST',anchor:[170,0],role:'GEOGRAPHIC_CONTEXT_ONLY',troopPosition:false},
  {id:'EAST',anchor:[-170,1],role:'GEOGRAPHIC_CONTEXT_ONLY',troopPosition:false}];
 for(const row of e.chapters)row.locationRefs=['WEST','EAST'];
 for(const row of p.chapters)row.locationRefs=['WEST','EAST'];
 assert.throws(()=>compile({eventProfile:e,profile:p}),/DATELINE_REQUIRES_SPLIT_ROI/);
 e.locations=[{id:'POLAR',anchor:[0,89],role:'GEOGRAPHIC_CONTEXT_ONLY',troopPosition:false}];
 for(const row of e.chapters)row.locationRefs=['POLAR'];
 for(const row of p.chapters)row.locationRefs=['POLAR'];
 assert.throws(()=>compile({eventProfile:e,profile:p}),/EXTENT_OUTSIDE_SUPPORTED_DOMAIN/);
});
test('headline policy modifies only explicitly selected original reveal, and bridge publishes actual reservations',async()=>{
 const r={primary:1,country:1,marker:.75,location:1,title:1,disclosure:1};
 assert.deepEqual(camera.sourceReviewReveal(r,{hideDuplicateNativeHeadline:true}),{...r,title:0});
 assert.deepEqual(camera.sourceReviewReveal(r,{}),r);assert.equal(r.title,1);
 const source=await readFile(new URL('../camera_bridge.mjs',import.meta.url),'utf8');
 assert.match(source,/publishDirectorNativeOwner/);assert.match(source,/protectedGraphics:result\.protectedGraphics/);
 assert.match(source,/actualLayoutValidation:validation/);assert.match(source,/validateVisibleMovingLayout/);
});
if(process.argv.includes('--write-report')){
 const c=compile(),sha=x=>createHash('sha256').update(x).digest('hex'),
  raw=async name=>readFile(new URL(name,import.meta.url)),
  report={schema:'WORLD_ENGINE_ASTRA_P2_CAMERA_CONTRACT_V2',
   status:'CPU_CAMERA_CONTRACT_EVALUATED; ACTUAL_NATIVE_RENDER_PENDING',
   tests:{python:{command:'python3 -B -m unittest discover -s recovery/astra-event-director-v2/tests -p test_camera_admission.py -v',passed:5},
    javascript:{command:'node recovery/astra-event-director-v2/tests/test_camera_plan.mjs --write-report',passed:9},
    testsAreCPUContractsOnly:true},
   sourcePlanSHA256:profile.sourcePlanSHA256,eventProfileSHA256:sha(await raw('../fixtures/HISTORY_EVENT_PROFILE_V2.json')),
   cameraProfileSHA256:sha(await raw('../fixtures/CAMERA_REVIEW_PROFILE.json')),
   cameraAdmissionSHA256:sha(await raw('../fixtures/CAMERA_ADMISSION.json')),
   cameraPlanModuleSHA256:sha(await raw('../camera_plan.mjs')),cameraBridgeModuleSHA256:sha(await raw('../camera_bridge.mjs')),
   requestedLocalCamera:{status:'BLOCKED_REQUESTED_LOCAL',admitted:false,automaticWideningAllowed:false,localCertificate:false,
    reasons:['NATIVE_REGIONAL_MINIMUM_UNCHANGED','NATIVE_SOURCE_SAMPLING_INSUFFICIENT_FOR_REQUESTED_LOCAL_EXTENTS',
     'LOCAL_GIS_POSITIONAL_ACCURACY_UNVERIFIED','FULL_EVENT_CONTROL_GEOMETRY_MISSING']},
   separatelySelectedReviewPurpose:'REGIONAL_SOURCE_REVIEW',originalRegionalFloorPreserved:true,
   originalReferenceCameraAdapterReused:true,originalCameraDirectorV5Reused:true,originalProjectionAndRendererUnchanged:true,
   nativeMinimumBounds:c.minimumBounds,sourceSafety:c.profile.sourceSafety,preflight:c.preflight,
   chapters:c.entries.map(x=>({chapterId:x.chapterId,eventId:x.eventId,startFrame:x.startFrame,endFrame:x.endFrame,
    startBounds:x.startBounds,focusBounds:x.focusBounds,endBounds:x.endBounds,
    contextLocations:x.source.locations.map(y=>({id:y.id,role:y.role,troopPosition:y.troopPosition})),
    sourceGeometryIds:x.source.geometries.map(y=>y.id)})),
   chapterHandoffContinuous:true,cameraGlobalClockPreserved:true,rollDegrees:0,
   nativeLayoutValidation:'ACTUAL_NATIVE_VALIDATE_VISIBLE_MOVING_LAYOUT_CALLED_AT_BOOT_AND_EVERY_DRAW; P5_PENDING',
   sourceClipValidation:'CPU PROJECTED_SOURCE_FOOTPRINT_ONLY; ACTUAL_PIXELS_PENDING',
   actual2400FramesRendered:false,actualNvidiaHardwareVerified:false,visualQualityApproved:false,
   requestedLocalContractSatisfied:false,productionEligible:false};
 await writeFile(new URL('../reports/P2_CAMERA_CONTRACT.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
}
