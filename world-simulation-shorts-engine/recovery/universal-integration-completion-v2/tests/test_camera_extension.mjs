/** CPU math and explicitly injected native-API spies. No GL context, image, video or paid operation. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const modules=new URL('../../../web/map_infographic_v1/',import.meta.url),production=new URL('../../universal-production-v3/',import.meta.url),
 hook=registerHooks({resolve(specifier,context,next){
  if(specifier.startsWith('/modules/'))return{url:new URL(specifier.slice('/modules/'.length),modules).href,shortCircuit:true};
  if(specifier.startsWith('/production-v3/'))return{url:new URL(specifier.slice('/production-v3/'.length),production).href,shortCircuit:true};
  return next(specifier,context);
 }});
let api,v5Api,productionApi;try{api=await import('../camera_extension.mjs');
 v5Api=await import(new URL('camera_director_v5.mjs',modules));
 productionApi=await import(new URL('production_camera.mjs',production));}finally{hook.deregister();}
const {normalizeCompletionCamera,compileCompletionCameraTracking,evaluateCompletionCameraFrame,
 createCompletionNativeCamera,completionChapterGeometries,completionRelationGeometries}=api;
function fixture({start=[-85,-45,-55,-15],target=[-83,-43,-63,-23],floor=[-80,-40,-60,-20],hemisphere='SW'}={}){
 const point=(x,y)=>hemisphere==='SW'?[x,y]:[-x,-y],polygon=coords=>({type:'Polygon',coordinates:[coords.map(p=>point(...p))]}),
  a=polygon([[-76,-35],[-74,-35],[-74,-33],[-76,-33],[-76,-35]]),
  b=polygon([[-74,-34],[-72,-34],[-72,-32],[-74,-32],[-74,-34]]),
  flip=bounds=>hemisphere==='SW'?bounds:[-bounds[2],-bounds[3],-bounds[0],-bounds[1]],
  chapters=[{chapterId:'first',startFrame:0,endFrame:120},{chapterId:'second',startFrame:120,endFrame:330}],
  plan={fps:30,totalFrames:330,productionV3:{eventChapters:chapters,geometrySchedule:[
   {chapterId:'first',sourceStateId:'a'},{chapterId:'second',sourceStateId:'b'}]},legacyScenePlan:{
   time_steps:[{id:'a',area_ids:['a-area'],front_line_ids:[]},{id:'b',area_ids:['b-area'],front_line_ids:[]}],
   areas:[{id:'a-area',geometry_ref:'a-geo'},{id:'b-area',geometry_ref:'b-geo'}],front_lines:[],
   geometries:[{id:'a-geo',geometry:a},{id:'b-geo',geometry:b}]}},
  parentFocusPlan={version:'UNIVERSAL_PRODUCTION_CAMERA_V3',totalFrames:330,approvedBounds:flip(floor),entries:[
   {...chapters[0],startBounds:flip(start),targetBounds:flip(start)},
   {...chapters[1],startBounds:flip(start),targetBounds:flip(target)}]};
 return{plan,request:{origin:point(-70,-30),timing:{eventStartFrame:0}},parentFocusPlan,safeArea:[80,120,1000,1800],
  camera:{mode:'V5_EVENT_TRACKING',settleFrames:18,holdFrames:24},validateBounds:()=>({valid:true}),approachFrames:48};
}
test('exact camera settings, conditional preserve mode and unsupported fields',()=>{
 assert.deepEqual(normalizeCompletionCamera(),{mode:'V5_EVENT_TRACKING',settleFrames:18,holdFrames:24});
 assert.deepEqual(normalizeCompletionCamera({mode:'PRESERVE_PARENT'}),{mode:'PRESERVE_PARENT'});
 for(const input of [{mode:'ROLL'},{mode:null},{mode:'PRESERVE_PARENT',settleFrames:18},{roll:1},null,[],
  {settleFrames:5},{settleFrames:61},{settleFrames:6.5},{holdFrames:-1},{holdFrames:121},{holdFrames:null}])
  assert.throws(()=>normalizeCompletionCamera(input));
});
test('source references select existing polygons exactly; no new coordinates',()=>{
 const input=fixture(),before=JSON.stringify(input.plan),result=completionChapterGeometries(input.plan,input.plan.productionV3.eventChapters[1]);
 assert.deepEqual(result,[input.plan.legacyScenePlan.geometries[1].geometry]);assert.equal(JSON.stringify(input.plan),before);
 result[0].coordinates[0][0][0]=0;assert.equal(input.plan.legacyScenePlan.geometries[1].geometry.coordinates[0][0][0],-74);
});
test('actual V5 pan and admitted zoom-in from a wider synthetic source pose retain floor and settle/hold',()=>{
 const input=fixture(),before=JSON.stringify(input),compiled=compileCompletionCameraTracking(input),entry=compiled.entries[1];
 assert.equal(compiled.entries[0].kind,'PRESERVE_INITIAL_DETAIL_LOCK');assert.equal(entry.v5Plan.directorVersion,'CAMERA_DIRECTOR_V5');
 assert.equal(entry.v5Plan.naturalMotion.realZoomNeeded,true);assert.equal(entry.v5Plan.naturalMotion.phaseCurveResets,false);
 assert.equal(entry.v5Plan.timeline.find(row=>row.state==='SETTLE').durationFrames,18);
 assert.ok(entry.actualHoldFrames>=24);assert.equal(entry.minimumHoldFrames,24);
 let movement=false,zoom=false,settles=0;
 for(let frame=120;frame<330;frame++){
  const row=evaluateCompletionCameraFrame(compiled,frame),bounds=row.camera.flatBounds;
  assert.ok(bounds[2]-bounds[0]>=20-1e-8);assert.ok(bounds[3]-bounds[1]>=20-1e-8);
  assert.equal(row.rollSupported,false);assert.equal(row.closerThanParentFloor,false);
  assert.equal(row.actualGPUOutputVerified,false);
  movement ||= Math.abs(row.velocity.longitudeDegreesPerSecond)>1e-8;
  zoom ||= Math.abs(row.velocity.logWidthPerSecond)>1e-8;
  if(row.state==='SETTLE')settles++;
 }
 assert.equal(movement,true);assert.equal(zoom,true);assert.equal(settles,18);
 const final=evaluateCompletionCameraFrame(compiled,329);assert.equal(final.cameraLocked,true);assert.equal(final.state,'EVENT_TRACKING_HOLD');
 assert.deepEqual(final.camera.flatBounds,input.parentFocusPlan.entries[1].targetBounds);
 assert.equal(JSON.stringify(input),before);
});
test('same source-bound V5 compiler operates in opposite hemisphere',()=>{
 for(const hemisphere of ['SW','NE']){
  const input=fixture({hemisphere}),compiled=compileCompletionCameraTracking(input),first=evaluateCompletionCameraFrame(compiled,120),last=evaluateCompletionCameraFrame(compiled,329);
  assert.deepEqual(first.camera.flatBounds,input.parentFocusPlan.entries[1].startBounds);
  assert.deepEqual(last.camera.flatBounds,input.parentFocusPlan.entries[1].targetBounds);
 }
});
test('explicit existing context geometry selects actual V5 context turn and zoom reversal without source crop',()=>{
 const input=fixture(),context={type:'Polygon',coordinates:[[[-88,-48],[-52,-48],[-52,-12],[-88,-12],[-88,-48]]]};
 input.plan.legacyScenePlan.camera_intent={minimum_context_geometry_refs:['declared-context']};
 input.plan.legacyScenePlan.geometries.push({id:'declared-context',geometry:context});
 input.plan.totalFrames=input.parentFocusPlan.totalFrames=800;
 input.plan.productionV3.eventChapters[1].endFrame=input.parentFocusPlan.entries[1].endFrame=800;
 assert.deepEqual(completionRelationGeometries(input.plan),[context]);
 const compiled=compileCompletionCameraTracking(input),entry=compiled.entries[1];
 assert.equal(entry.actualV5Turn,true);assert.equal(entry.explicitContextGeometryCount,1);
 assert.equal(entry.v5Plan.naturalMotion.contextTurnSkipped,false);
 assert.ok(entry.v5Plan.timeline.some(row=>row.state==='DIRECTIONAL_TURN'));
 let out=false,inside=false;
 for(let frame=120;frame<800;frame++){
  const row=evaluateCompletionCameraFrame(compiled,frame);
  out ||= row.velocity.logWidthPerSecond>1e-6;inside ||= row.velocity.logWidthPerSecond< -1e-6;
 }
 assert.equal(out,true);assert.equal(inside,true);
});
test('settle, hold and preserved approach controls have real consumers',()=>{
 const a=compileCompletionCameraTracking(fixture()),b=compileCompletionCameraTracking({...fixture(),approachFrames:72,
  camera:{mode:'V5_EVENT_TRACKING',settleFrames:30,holdFrames:36}});
 assert.notEqual(a.entries[1].activeFrames,b.entries[1].activeFrames);
 assert.equal(b.entries[1].v5Plan.profile.approachBaseSeconds,72/30);
 assert.equal(b.entries[1].v5Plan.timeline.find(row=>row.state==='SETTLE').durationFrames,30);
 assert.equal(b.entries[1].minimumHoldFrames,36);assert.ok(b.entries[1].actualHoldFrames>=36);
});
test('unsafe layouts, closer targets, discontinuities and short budgets fail before native redraw',()=>{
 assert.throws(()=>compileCompletionCameraTracking({...fixture(),validateBounds:()=>({valid:false})}),/LAYOUT_UNSAFE/);
 const tooClose=fixture({target:[-78,-38,-66,-26]});assert.throws(()=>compileCompletionCameraTracking(tooClose),/FLOOR_PROTECTED/);
 const jump=fixture();jump.parentFocusPlan.entries[1].startBounds=[-84,-45,-54,-15];
 assert.throws(()=>compileCompletionCameraTracking(jump),/CONTINUITY_REQUIRED/);
 const short=fixture();short.plan.totalFrames=140;short.parentFocusPlan.totalFrames=140;
 short.plan.productionV3.eventChapters[1].endFrame=140;short.parentFocusPlan.entries[1].endFrame=140;
 assert.throws(()=>compileCompletionCameraTracking(short),/BUDGET_INSUFFICIENT/);
 const widen=fixture({start:[-80,-40,-60,-20],target:[-85,-45,-55,-15]});
 assert.throws(()=>compileCompletionCameraTracking(widen),/V5_START_WOULD_JUMP|SOURCE_OUTSIDE_SAFE_AREA/);
});
test('preserve mode calls exact original factory without touching native APIs',()=>{
 let calls=0;const input={original:true},owner={drawNative:frame=>({frame})};
 assert.equal(createCompletionNativeCamera(input,{camera:{mode:'PRESERVE_PARENT'},originalFactory:actual=>{
  assert.equal(actual,input);calls++;return owner;}}),owner);assert.equal(calls,1);
});
test('actual wrapper uses public native factory, scale, LOD, layout and reservation consumers (CPU spies)',()=>{
 const input=fixture(),calls=[],floor=input.parentFocusPlan.approvedBounds,native={cameraPlan:{totalFrames:30},layoutContract:{retained:true},project:p=>p,
  evidence:{frozenMaterialParameters:{preserved:true}},drawNative:frame=>({frame,camera:{flatBounds:floor},reveal:{location:1},cameraLocked:true,settle:{locked:true}}),
  factory:{evidence:{cameraFrame:{bounds:floor}},
   updateCamera(bounds){calls.push(['camera',bounds]);this.evidence.cameraFrame={bounds:[...bounds]};},
   setScaleVisual(value){calls.push(['scale',value]);},setTerrainLod(value){calls.push(['lod',value]);},
   renderFrame(value){calls.push(['render',value]);return{glError:0};}}},
  marker={id:'original-marker',box:[20,20,40,40]},reservations=[{kind:'MARKER',box:[20,20,60,60]}],boundary=[{originalBoundary:true}],
  ops={geographicScaleVisualTokens:bounds=>({markerSize:40,sourceBounds:bounds}),geographicTerrainLod:()=>({weight:.5}),
   evaluateMovingLayout:(_contract,state)=>({items:[marker],bounds:state.camera.flatBounds}),
   validateVisibleMovingLayout:()=>({valid:true}),nativeGraphicReservations:items=>{assert.equal(items[0],marker);return reservations;},
   nativeBoundarySupport:()=>boundary},original={focusPlan:input.parentFocusPlan,evidence:{originalV5:true},
   drawNative:frame=>({frame,camera:{flatBounds:input.parentFocusPlan.entries[0].startBounds},cameraLocked:true,
    settle:{locked:true},reveal:{location:1},productionCamera:{parentSourceUnchanged:true},gpu:{terrainLod:{weight:0}}})},
  args={native,plans:{REGIONAL:{framing:{bounds:floor},layout:{safe:input.safeArea},assets:{terrain:{}}},CONTINENT:{assets:{terrain:{}}}},
   plan:input.plan,request:input.request,profile:{cameraApproachFrames:48},cameraStartFrame:0},
  owner=createCompletionNativeCamera(args,{camera:input.camera,originalFactory:()=>{calls.push(['old-production-factory']);throw Error('Old unrelated focus path must not run');},operations:ops});
 const frame=owner.drawNative(150);
 assert.equal(calls.filter(row=>row[0]==='old-production-factory').length,0);assert.equal(calls.filter(row=>row[0]==='render').length,1);
 assert.equal(frame.protectedGraphics,reservations);assert.equal(frame.boundarySegments,boundary);assert.equal(frame.layoutItems[0],marker);
 const actualRender=calls.find(row=>row[0]==='render')[1];assert.equal(actualRender.preserved,true);assert.equal(actualRender.graphics,false);
 assert.equal(owner.evidence.completionV2.hardwareVerified,false);assert.equal(owner.evidence.completionV2.originalNativeV5FactoryReused,true);
 assert.equal(owner.drawNative(10).frame,10);assert.throws(()=>owner.drawNative(330),/GLOBAL_FRAME_REQUIRED/);
});
test('browser bridge calls exact parent and checks completion/integration metadata',async()=>{
 const source=await readFile(new URL('../production_camera_bridge.mjs',import.meta.url),'utf8');
 for(const expected of ['/completion-v2/parent_camera.mjs','createCompletionNativeCamera','loadIntegrationRuntimeConfig',
  'mergeIntegrationProductionProfile','WORLD_ENGINE_UNIVERSAL_COMPLETION_V2','VISUAL_UNIFIED_COMPLETION_V2'])assert.ok(source.includes(expected));
 assert.doesNotMatch(source,/createShader|shaderSource|requestAnimationFrame|Quaternion/);
});
test('actual preserved 80s/12chapter inputs traverse all2400 camera CPU frames; native draws/layout are explicit spies',async()=>{
 const engine=new URL('../../../',import.meta.url),load=async relative=>JSON.parse(await readFile(new URL(relative,engine))),
  payload=await load('recovery/universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json'),inputs={};
 for(const [name,reference]of Object.entries(payload.nativeFiles)){
  const raw=await readFile(new URL(reference.path,engine));
  assert.equal(createHash('sha256').update(raw).digest('hex'),reference.sha256,'ACTUAL_NATIVE_FIXTURE_SOURCE_SHA_REQUIRED');
  inputs[name]=JSON.parse(raw);
 }
 const planRaw=await readFile(new URL('recovery/verified-front-data-v4-recovery/VIDEO_PLAN_80S.json',engine)),
  plan=JSON.parse(planRaw),before=JSON.stringify(plan),r=inputs.regionalPlan,c=inputs.continentPlan,cam=inputs.cameraPlan,
  eventStart=plan.legacyScenePlan.timing.event_start_frame,chapters=plan.productionV3.eventChapters
   .filter(row=>row.endFrame>eventStart).map((row,index)=>({...row,startFrame:index===0?eventStart:row.startFrame}));
 // Isolate the confirmed mathematical failure path. This is a layout-allowed
 // CPU reproduction, not an assertion that the old GPU job failed the same way.
 assert.throws(()=>productionApi.compileProductionFocusPlan({chapters,totalFrames:2400,approvedBounds:r.framing.bounds,
  safeArea:r.layout.safe,anchor:plan.legacyScenePlan.camera_intent.anchor,
  geometriesForChapter:chapter=>completionChapterGeometries(plan,chapter),approachFrames:48,preserveInitialView:true,
  validateBounds:()=>({valid:true})}),/PRODUCTION_FOCUS_NO_SAFE_CURRENT_VIEW_chapter-08/);
 let layoutCalls=0,drawCalls=0;
 const native={cameraPlan:cam,layoutContract:{CPU_NATIVE_LAYOUT_SPY_ONLY:true},project:point=>point,
  evidence:{frozenMaterialParameters:{}},drawNative:frame=>({...v5Api.evaluateMinimumContextCameraFrame(cam,Math.min(frame,cam.totalFrames-1)),
   reveal:{country:1,marker:1,location:1,title:1}}),factory:{evidence:{cameraFrame:{}},
   updateCamera(bounds){this.evidence.cameraFrame={flatBounds:[...bounds]};},setScaleVisual(){},setTerrainLod(){},
   renderFrame(){drawCalls++;return{glError:0};}}},
  operations={geographicScaleVisualTokens:()=>({markerSize:40}),geographicTerrainLod:()=>({weight:1}),
   evaluateMovingLayout:()=>{layoutCalls++;return{items:[]};},validateVisibleMovingLayout:()=>({valid:true}),
   nativeGraphicReservations:()=>[],nativeBoundarySupport:()=>[]},
  owner=createCompletionNativeCamera({native,plans:{REGIONAL:r,CONTINENT:c},plan,
   request:{origin:plan.legacyScenePlan.camera_intent.anchor,timing:{eventStartFrame:eventStart}},
   profile:{cameraApproachFrames:48},cameraStartFrame:payload.cameraStartFrame},
   {camera:{mode:'V5_EVENT_TRACKING',settleFrames:18,holdFrames:24},operations,
    originalFactory:()=>{throw Error('COMPLETION_TRACKING_MUST_USE_NATIVE_V5_OWNER');}}),
  allGeometry=chapters.flatMap(chapter=>completionChapterGeometries(plan,chapter)),frames=new Map();
 for(let frame=0;frame<2400;frame++){
  const actual=owner.drawNative(frame),bounds=actual.camera.flatBounds;frames.set(frame,bounds);
  assert.ok(bounds.every(Number.isFinite));assert.ok(bounds[2]-bounds[0]>=r.framing.bounds[2]-r.framing.bounds[0]-1e-8);
  assert.ok(bounds[3]-bounds[1]>=r.framing.bounds[3]-r.framing.bounds[1]-1e-8);
  if(frame>=eventStart)assert.equal(productionApi.geometryScreenSafety({geometries:allGeometry,bounds,safeArea:r.layout.safe})
   .wholeSuppliedGeometrySafe,true,'ALL_SUPPLIED_TIMELINE_SOURCE_REMAINS_SAFE');
 }
 for(const chapter of chapters.slice(1)){
  const a=frames.get(chapter.startFrame-1),b=frames.get(chapter.startFrame);
  assert.ok(a.every((value,index)=>Math.abs(value-b[index])<1e-8),'NO_CHAPTER_CAMERA_JUMP');
 }
 assert.equal(owner.completionFocusPlan.entries.length,12);
 assert.equal(owner.completionFocusPlan.entries.filter(row=>row.kind==='V5_EVENT_TRACKING').length,11);
 assert.equal(owner.completionFocusPlan.entries.filter(row=>row.actualV5Turn===true).length,10);
 assert.ok(owner.completionFocusPlan.entries.slice(1).every(row=>row.settleFrames===18&&row.actualHoldFrames>=24));
 assert.ok(layoutCalls>2400);assert.ok(drawCalls>0);assert.equal(JSON.stringify(plan),before);
 assert.equal(createHash('sha256').update(planRaw).digest('hex'),'2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6');
 assert.equal(owner.evidence.completionV2.hardwareVerified,false);
});
