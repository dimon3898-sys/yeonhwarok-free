/** CPU-only contracts and original pure evaluators. Injected owners below do not draw WebGL. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {normalizeIntegrationVisualProfile,mergeIntegrationProductionProfile,loadIntegrationRuntimeConfig,
 bindProductionFactory,INTEGRATION_SCHEMA,INTEGRATION_PROFILE,VISUAL_FIELDS} from '../presentation.mjs';
import {extendIntegrationServerPlan,INTEGRATION_BROWSER_BINDINGS,integrationFrameSelections} from '../runtime_binding.mjs';
import {normalizeProductionVisualProfile,productionAreaStyle} from '../../universal-production-v3/production_visual_profile.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex'),
 sha=raw=>createHash('sha256').update(raw).digest('hex'),defaults={territoryOpacity:.62,frontCoreWidthPixels:4.8,
 frontGlowRadiusPixels:10,frontGlowGain:.42,cameraApproachFrames:48};
const binding=profile=>({schema:INTEGRATION_SCHEMA,profile:INTEGRATION_PROFILE,visualProfile:profile,
 profileSha256:hash(profile),sourceManifestSha256:'1'.repeat(64),browserSourceSignature:'2'.repeat(64)});
const parent=()=>({sourceSignature:'3'.repeat(64),sourceBindings:[],serverConfig:{runtimeConfig:{
 frontV4:{runtimeProfile:'VERIFIED_ARCHIVAL_FRONT_V4'},universalVideo:{plan:{neverRewrite:'parent-frozen-plan'}}},bindings:[
 {url:'/production-v3/production_area_pass.mjs',path:'/frozen/area.mjs',bytes:100,sha256:'4'.repeat(64)},
 {url:'/production-v3/production_native_camera.mjs',path:'/frozen/camera.mjs',bytes:200,sha256:'5'.repeat(64)}]}});
async function records(){return Promise.all(Object.values(INTEGRATION_BROWSER_BINDINGS).map(async name=>{
 const file=path.join(root,name),raw=await readFile(file);return{name,file,bytes:raw.length,sha256:sha(raw)};}));}

test('strict five-field defaults and each original allowed boundary',()=>{
 assert.deepEqual(normalizeIntegrationVisualProfile(),defaults);
 for(const [key,rule]of Object.entries(VISUAL_FIELDS))for(const value of [rule.min,rule.max])
  assert.equal(normalizeIntegrationVisualProfile({[key]:value})[key],value);
});
test('unknown visual fields, null, bool, strings, nonfinite and ranges fail closed',()=>{
 for(const value of [null,[],true,'x'])assert.throws(()=>normalizeIntegrationVisualProfile(value));
 assert.throws(()=>normalizeIntegrationVisualProfile({unitScale:2}),/FIELD_UNSUPPORTED/);
 for(const key of Object.keys(defaults))for(const value of [null,true,'1',NaN,Infinity,VISUAL_FIELDS[key].min-.01,VISUAL_FIELDS[key].max+.01])
  assert.throws(()=>normalizeIntegrationVisualProfile({[key]:value}));
 assert.throws(()=>normalizeIntegrationVisualProfile({cameraApproachFrames:48.5}));
});
test('parent colors and marker/ownership policies survive unchanged',()=>{
 const original=normalizeProductionVisualProfile(),before=JSON.stringify(original),merged=mergeIntegrationProductionProfile(original,{territoryOpacity:.74});
 assert.equal(merged.territoryOpacity,.74);for(const key of Object.keys(original))if(key!=='territoryOpacity')assert.deepEqual(merged[key],original[key]);
 assert.equal(JSON.stringify(original),before);assert.throws(()=>mergeIntegrationProductionProfile({},defaults));
});
test('unchanged productionAreaStyle consumes all four exposed Area values',()=>{
 const supplied={territoryOpacity:.77,frontCoreWidthPixels:6.5,frontGlowRadiusPixels:15,frontGlowGain:.6,cameraApproachFrames:72},
  merged=mergeIntegrationProductionProfile(normalizeProductionVisualProfile(),supplied),style=productionAreaStyle(merged,[.7,.2,.1]);
 assert.equal(style.AREA.fillColor[3],.77);assert.equal(style.FRONT.width,6.5);
 assert.equal(style.FRONT.glowRadius,15);assert.equal(style.FRONT.glowGain,.6);
 assert.deepEqual(style.FRONT.coreColor,[1,.98,.91,1]);assert.deepEqual(style.FRONT.glowColor,[1,.66,.16,1]);
 assert.equal(style.IMPACT.width,0);assert.equal(style.PROPAGATION.width,0);
});
test('browser config requires explicit binding and verifies exact profile SHA',async()=>{
 const good=binding(defaults),calls=[];
 const loaded=await loadIntegrationRuntimeConfig({fetchConfig:async(...args)=>{calls.push(args);return{ok:true,json:async()=>({integrationV1:good})};}});
 assert.deepEqual(loaded.visualProfile,defaults);assert.deepEqual(calls,[['/runtime-config.json',{cache:'no-store',redirect:'error'}]]);
 for(const bad of [undefined,{...good,profile:'legacy'},{...good,profileSha256:'0'.repeat(64)},
  {...good,visualProfile:{...defaults,unexpected:true}},{...good,browserSourceSignature:''}])
  await assert.rejects(loadIntegrationRuntimeConfig({fetchConfig:async()=>({ok:true,json:async()=>({integrationV1:bad})})}));
 await assert.rejects(loadIntegrationRuntimeConfig({fetchConfig:async()=>({ok:false})}),/HTTP_FAILED/);
});
test('Area wrapper forwarding test uses injected CPU owner, not a WebGL pass',()=>{
 const calls=[],controls={areas:[{id:'supplied-southern-region',geometry:{type:'Polygon',coordinates:[[
  [-58,-34],[-57,-34],[-57,-33],[-58,-34]]]} }],fronts:[{id:'observed-segment'}]},
  protectedGraphics=[{box:[10,10,100,100]}],boundarySegments=[{a:[0,0],b:[10,10],radiusPx:2}],before=JSON.stringify(controls),
  originalDraw=input=>{calls.push(['draw',input]);return{geometryUnchanged:true};},
  factory=input=>{calls.push(['factory',input]);return{draw:originalDraw,evidence:{originalShadersChanged:false},dispose(){}};},
  bound=bindProductionFactory(factory,binding(defaults),'AREA'),input={canvas:{CPU_STUB:true},profile:normalizeProductionVisualProfile(),bindings:[],probeVariant:'AFTER'},owner=bound(input);
 assert.equal(calls.length,1);assert.equal(calls[0][1].canvas,input.canvas);assert.equal(calls[0][1].profile.cameraApproachFrames,48);
 const drawInput={controls,protectedGraphics,boundarySegments};assert.equal(owner.draw,originalDraw);owner.draw(drawInput);
 assert.equal(calls[1][1],drawInput);assert.equal(calls[1][1].protectedGraphics,protectedGraphics);
 assert.equal(calls[1][1].boundarySegments,boundarySegments);assert.equal(JSON.stringify(controls),before);
 assert.equal(owner.evidence.integrationV1.hardwareVerified,false);assert.equal(owner.evidence.originalShadersChanged,false);
});
test('camera wrapper forwards actual approach parameter to unchanged factory contract (CPU injected owner)',()=>{
 let received;const visual={...defaults,cameraApproachFrames:96},drawNative=frame=>({frame}),
  owner=bindProductionFactory(input=>{received=input;return{drawNative,evidence:{closerThanParentFloor:false}};},binding(visual),'CAMERA')
   ({native:{CPU_STUB:true},profile:normalizeProductionVisualProfile(),plan:{region:'synthetic-western-hemisphere'}});
 assert.equal(received.profile.cameraApproachFrames,96);assert.equal(owner.drawNative,drawNative);
 assert.deepEqual(owner.drawNative(73),{frame:73});assert.equal(owner.evidence.closerThanParentFloor,false);
 assert.equal(owner.evidence.integrationV1.visualOutputVerified,false);
});
test('actual preserved conservative focus evaluator consumes approach duration and retains path/floor',async()=>{
 const cameraURL=new URL('../../universal-production-v3/production_camera.mjs',import.meta.url),
  detailURL=new URL('../../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs',import.meta.url),
  hook=registerHooks({resolve(specifier,context,next){
   if(context.parentURL===cameraURL.href&&specifier==='/modules/camera_detail_approach_adapter_v1.mjs')
    return{url:detailURL.href,shortCircuit:true};return next(specifier,context);
  }});let original;
 try{original=await import(cameraURL.href);}finally{hook.deregister();}
 const chapters=[{chapterId:'a',startFrame:0,endFrame:120},{chapterId:'b',startFrame:120,endFrame:240}],args={
  chapters,totalFrames:240,approvedBounds:[-80,-40,-60,-20],safeArea:[80,120,1000,1800],anchor:[-70,-30],preserveInitialView:true,
  geometriesForChapter:chapter=>[{type:'LineString',coordinates:chapter.chapterId==='a'?[[-75,-35],[-66,-25]]:[[-73,-34],[-65,-24]]}]},
  fast=original.compileProductionFocusPlan({...args,approachFrames:12}),slow=original.compileProductionFocusPlan({...args,approachFrames:96});
 assert.equal(fast.entries[1].approachFrames,12);assert.equal(slow.entries[1].approachFrames,96);
 assert.deepEqual(fast.entries[1].startBounds,slow.entries[1].startBounds);assert.deepEqual(fast.entries[1].targetBounds,slow.entries[1].targetBounds);
 assert.notDeepEqual(original.evaluateProductionFocusFrame(fast,125).flatBounds,original.evaluateProductionFocusFrame(slow,125).flatBounds);
 assert.deepEqual(original.evaluateProductionFocusFrame(fast,239).flatBounds,original.evaluateProductionFocusFrame(slow,239).flatBounds);
 for(const plan of [fast,slow])for(let frame=0;frame<240;frame++){
  const state=original.evaluateProductionFocusFrame(plan,frame),bounds=state.flatBounds;
  assert.ok(bounds[2]-bounds[0]>=20-1e-9);assert.ok(bounds[3]-bounds[1]>=20-1e-9);
  assert.equal(state.localAdmissionGranted,false);assert.equal(state.surveyAdmissionModified,false);
 }
});
test('source aliases preserve exact parent records; parent plan is not mutated',async()=>{
 const original=parent(),before=JSON.stringify(original),sourceRecords=await records(),result=extendIntegrationServerPlan(original,
  {visualProfile:{territoryOpacity:.73},records:sourceRecords,manifestSha256:'6'.repeat(64)}),urls=new Map(result.serverConfig.bindings.map(row=>[row.url,row]));
 assert.equal(JSON.stringify(original),before);assert.deepEqual(result.serverConfig.runtimeConfig.universalVideo,original.serverConfig.runtimeConfig.universalVideo);
 assert.deepEqual(urls.get('/integration-v1/parent_production_area_pass.mjs'),{...original.serverConfig.bindings[0],url:'/integration-v1/parent_production_area_pass.mjs'});
 assert.deepEqual(urls.get('/integration-v1/parent_production_native_camera.mjs'),{...original.serverConfig.bindings[1],url:'/integration-v1/parent_production_native_camera.mjs'});
 for(const [url,name]of Object.entries(INTEGRATION_BROWSER_BINDINGS))assert.equal(urls.get(url).sha256,sourceRecords.find(row=>row.name===name).sha256);
 assert.equal(result.integrationV1.profileSha256,hash({...defaults,territoryOpacity:.73}));
 assert.notEqual(result.sourceSignature,original.sourceSignature);
});
test('missing parent, collisions, duplicate/unmanifested/relative records and unknown fields are rejected',async()=>{
 const good=await records(),args={records:good,manifestSha256:'6'.repeat(64)};
 const missing=parent();missing.serverConfig.bindings.pop();assert.throws(()=>extendIntegrationServerPlan(missing,args));
 const collision=parent();collision.serverConfig.bindings.push({url:'/integration-v1/presentation.mjs'});assert.throws(()=>extendIntegrationServerPlan(collision,args));
 for(const bad of [good.slice(1),[...good,good[0]],good.map(row=>({...row,file:'relative'})),good.map(row=>({...row,name:'../unsafe'}))])
  assert.throws(()=>extendIntegrationServerPlan(parent(),{...args,records:bad}));
 assert.throws(()=>extendIntegrationServerPlan(parent(),{...args,visualProfile:{country:'specific'}}));
 const already=parent();already.serverConfig.runtimeConfig.integrationV1={};assert.throws(()=>extendIntegrationServerPlan(already,args));
});
test('all 2400 source-bound frames retain actual V3/V4 selection and no inferred occupation',async()=>{
 const base=new URL('../../verified-front-data-v4-recovery/',import.meta.url),planRaw=await readFile(new URL('VIDEO_PLAN_80S.json',base)),
  frontRaw=await readFile(new URL('FRONT_PROFILE.json',base)),plan=JSON.parse(planRaw),frontProfile=JSON.parse(frontRaw),
  before=JSON.stringify({plan,frontProfile}),counts={},rows=[];
 for(const row of integrationFrameSelections({plan,frontProfile})){
  assert.equal(row.frame,rows.length);assert.equal(row.geometryClock.globalFrame,row.frame);assert.equal(row.selection.globalFrame,row.frame);
  counts[row.areaPolicy]=(counts[row.areaPolicy]??0)+1;
  if(row.selection.sourceActiveFrame){assert.equal(row.selection.areas,0);assert.equal(row.selection.coordinatesInterpolated,false);}
  assert.equal(row.exactOwnershipClaimed,false);assert.equal(row.inventedUnitPositions,false);assert.equal(row.hardwareVerified,false);rows.push(row);
 }
 assert.equal(plan.totalFrames,2400);assert.equal(plan.fps,30);assert.equal(rows.length,2400);
 assert.deepEqual(counts,{NO_EVENT_GEOMETRY:60,PRESERVED_QUALIFIED_SCHEMATIC_AREAS:1490,NO_INFERRED_OCCUPATION_FILL:850});
 assert.equal(JSON.stringify({plan,frontProfile}),before);assert.equal(sha(planRaw),'2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6');
});
test('arbitrary southern/western source fixtures use same existing evaluators without special-region branches',()=>{
 const plan={totalFrames:10,productionV3:{eventChapters:[{chapterId:'example',startFrame:0,endFrame:10}],geometrySchedule:[
  {startFrame:0,endFrame:10,mode:'ARRIVAL_NO_EVENT',chapterId:'example'}]}},source={
  classification:'OBSERVED_UN_FRONT',documentSha256:'1'.repeat(64),rasterSha256:'2'.repeat(64),pageIndex0:0,
  registrationMode:'REFERENCE_CONTROL_AFFINE_APPROXIMATION',registrationResidualMeters:20,cartographicAccuracy:'UNKNOWN_NOT_CERTIFIED',
  reviewStatus:'SOURCE_LINE_AND_TRACE_REVIEWED',reference:'SYNTHETIC CPU FIXTURE, NOT HISTORY'},frontProfile={
  schema:'WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4',runtimeProfile:'VERIFIED_ARCHIVAL_FRONT_V4',semanticPolicy:{inferOccupiedAreas:false,
   interpolateUnobservedDates:false,exactMilitaryDemarcationLineClaimed:false},fronts:[{frontId:'synthetic',mapDate:'2000-01-01',source,
   partialSegments:true,verifiedSourceExtent:'PARTIAL_CONTROL_HULL',geoJsonSha256:'3'.repeat(64),sourceFile:'synthetic.json',
   geometry:{type:'LineString',coordinates:[[-70,-30],[-69,-31],[-68,-30.5]]}}],schedule:[{
    startFrame:2,endFrame:8,mode:'ARCHIVAL_FRONT_ONLY',frontId:'synthetic',eventDate:'2000-01-02',sourceLabel:'Synthetic example',chapterId:'example'}]};
 const rows=[...integrationFrameSelections({plan,frontProfile})];assert.equal(rows.length,10);
 assert.equal(rows.filter(row=>row.selection.sourceActiveFrame).length,6);assert.equal(rows[2].selection.frontId,'synthetic');
 assert.throws(()=>[...integrationFrameSelections({plan,frontProfile,startFrame:-1})]);
 assert.throws(()=>[...integrationFrameSelections({plan,frontProfile,endFrame:11})]);
});
test('browser wrappers explicitly import original public factories, with no local renderer/shader implementation',async()=>{
 for(const [name,symbol,alias]of [['production_area_bridge.mjs','createProductionAreaPass','parent_production_area_pass.mjs'],
  ['production_camera_bridge.mjs','createProductionNativeCamera','parent_production_native_camera.mjs']]){
  const source=await readFile(path.join(root,name),'utf8');assert.match(source,new RegExp(symbol));assert.ok(source.includes('/integration-v1/'+alias));
  assert.match(source,/await loadIntegrationRuntimeConfig\(\)/);assert.match(source,/bindProductionFactory/);
  assert.doesNotMatch(source,/createShader|shaderSource|bufferData|drawArrays|requestAnimationFrame/);
 }
});
