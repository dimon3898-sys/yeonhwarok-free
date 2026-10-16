/** Focused CPU contracts. These synthetic inputs never claim archival or GPU verification. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {FRONT_PROFILE_SCHEMA,FRONT_RUNTIME_PROFILE,normalizeFrontProfile,selectFrontSnapshot,sourceLineChunks,selectSourceFrontBoundaryPolicy} from '../front_visual.mjs';
import {FRONT_BROWSER_BINDINGS,extendFrontServerPlan,validateFrontManifest,validateFrontPlanBinding,assertFrontCapturedFrame,openLongRuntime} from '../front_runtime.mjs';
import {resolveFrontCapture,originalCaptureURL,frontRuntimeURL} from '../front_capture.mjs';
import {evaluateProductionGeometryClock} from '../../universal-production-v3/production_visual_profile.mjs';
import {measureSourceProjection,selectFrontProbeFrames,softwareConfigFor,compareSourceFrontPixels} from '../software_probe_front.mjs';
const h='a'.repeat(64),g='b'.repeat(64),hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
function fixture(){
 const chapters=[{chapterId:'earlier',startFrame:0,endFrame:30,displayLabel:'1951.01',title:'CONTEXT'},
  {chapterId:'later',startFrame:30,endFrame:60,displayLabel:'1951.02',title:'ACTUAL SOURCE DATE QUALIFIED'}],
  source={classification:'OBSERVED_UN_FRONT',documentSha256:h,rasterSha256:g,pageIndex0:22,
   registrationMode:'REFERENCE_CONTROL_AFFINE_APPROXIMATION',registrationResidualMeters:2345,
   cartographicAccuracy:'UNKNOWN_NOT_CERTIFIED',reviewStatus:'SOURCE_LINE_AND_TRACE_REVIEWED',reference:'SYNTHETIC_TEST_ONLY_SOURCE'},
  front={frontId:'TEST_ONLY_FRONT',mapDate:'1951-01-24',geometry:{type:'MultiLineString',coordinates:[[[20,-20],[21,-21]],[[23,-23],[24,-24]]]},
   source,partialSegments:true,verifiedSourceExtent:'PARTIAL_CONTROL_HULL',sourceFile:'data/TEST_ONLY.geojson',geoJsonSha256:h},
  profile={schema:FRONT_PROFILE_SCHEMA,runtimeProfile:FRONT_RUNTIME_PROFILE,semanticPolicy:{inferOccupiedAreas:false,
   interpolateUnobservedDates:false,exactMilitaryDemarcationLineClaimed:false},fronts:[front],schedule:[{startFrame:30,endFrame:60,
   frontId:front.frontId,mode:'ARCHIVAL_FRONT_ONLY',chapterId:'later',eventDate:'1951-02-01',sourceLabel:'1951.01.24 UN-FRONT-APPROX-PARTIAL'}]},
  scene={sceneId:'s0',startFrame:0,endFrame:60},document={totalFrames:60,productionV3:{eventChapters:chapters,geometrySchedule:[{
   startFrame:0,endFrame:60,mode:'HOLD_SUPPLIED_SNAPSHOT',sourceStartFrame:3,sourceEndFrame:3,sourceStateId:'ORIGINAL',snapshotDate:'1950-09-01'}]},
   legacyScenePlan:{timing:{event_start_frame:0,total_frames:60}}},
  inherited={document,scene,sourceSignature:g,sourceBindings:[],productionIntegrity:{runtimeProfile:'UNIVERSAL_PRODUCTION_V3'},
   serverConfig:{runtimeConfig:{universalVideo:{plan:document}},bindings:[{url:'/universal/long_adapter.mjs',path:'/FROZEN/production_adapter.mjs',bytes:10,sha256:g},
    {url:'/universal/long_area_timeline.mjs',path:'/FROZEN/long_area_timeline.mjs',bytes:30,sha256:g}]}},
  records=Object.entries(FRONT_BROWSER_BINDINGS).map(([url,name])=>({name,file:'/TEST_ONLY/'+name,bytes:50,sha256:h})),
  descriptor={profile,profileRecord:{file:'/TEST_ONLY/FRONT_PROFILE.json',bytes:100,sha256:h},manifestSha256:g,records};
 return{chapters,source,front,profile,inherited,descriptor};
}
test('same pure selector supports western/southern geometry, partial gaps, and explicit date-qualified context',()=>{
 const f=fixture(),before=structuredClone(f.profile),p=normalizeFrontProfile(f.profile,{totalFrames:60,eventChapters:f.chapters});
 assert.equal(selectFrontSnapshot(p,29).sourceActiveFrame,false);
 const at=selectFrontSnapshot(p,30);assert.equal(at.sourceActiveFrame,true);assert.equal(at.mapDate,'1951-01-24');assert.equal(at.eventDate,'1951-02-01');
 assert.equal(at.unverifiedSchematicAreaSuppressed,true);assert.equal(at.exactOccupiedBoundaryClaimed,false);assert.equal(at.areas,0);
 assert.equal(at.coordinatesInterpolated,false);assert.equal(at.exactMilitaryDemarcationLineClaimed,false);assert.deepEqual(f.profile,before);
 assert.deepEqual(sourceLineChunks(f.front.geometry).map(row=>row.geometry.coordinates),f.front.geometry.coordinates);
});
test('line chunking preserves every source edge and never bridges a missing map segment',()=>{
 const points=Array.from({length:300},(_,i)=>[i/10-20,Math.sin(i/100)-20]),g={type:'MultiLineString',coordinates:[points,[[-1,-1],[0,-2]]]},
  chunks=sourceLineChunks(g),edges=part=>part.slice(1).map((p,i)=>[part[i],p]);
 assert.deepEqual(chunks.flatMap(row=>edges(row.geometry.coordinates)),g.coordinates.flatMap(edges));
 assert.equal(chunks.length,4);assert.ok(chunks.every(row=>row.geometry.coordinates.length<=129));
});
test('unreviewed, future-dated, exact-MDL, closed polygon and invented-ownership sources are rejected',()=>{
 const mutations=[p=>p.fronts[0].source.reviewStatus='UNREVIEWED',p=>p.fronts[0].source.classification='POSSIBLE_MLR',
  p=>p.fronts[0].mapDate='1952-01-01',p=>p.semanticPolicy.inferOccupiedAreas=true,p=>p.semanticPolicy.interpolateUnobservedDates=true,
  p=>p.semanticPolicy.exactMilitaryDemarcationLineClaimed=true,p=>p.fronts[0].source.cartographicAccuracy='SURVEY_CERTIFIED',
  p=>p.fronts[0].geometry={type:'Polygon',coordinates:[]},p=>p.fronts[0].partialSegments=false,
  p=>p.fronts[0].geometry={type:'LineString',coordinates:[[0,0],[1,1],[0,0]]}];
 for(const mutate of mutations){const f=fixture();mutate(f.profile);assert.throws(()=>normalizeFrontProfile(f.profile,{totalFrames:60,eventChapters:f.chapters}));}
});
test('half-open schedules cannot overlap, escape a chapter, or select unknown sources',()=>{
 for(const mutate of [p=>p.schedule.push({...p.schedule[0],startFrame:59}),p=>p.schedule[0].startFrame=29,
  p=>p.schedule[0].frontId='NOT_PRESENT',p=>p.schedule[0].endFrame=61]){
  const f=fixture();mutate(f.profile);assert.throws(()=>normalizeFrontProfile(f.profile,{totalFrames:60,eventChapters:f.chapters}));
 }
 const f=fixture(),p=normalizeFrontProfile(f.profile,{totalFrames:60,eventChapters:f.chapters});assert.throws(()=>selectFrontSnapshot(p,60));
});
test('browser extension preserves the original plan, helpers, ASTRA bindings and prior sealed config',()=>{
 const f=fixture(),before=structuredClone(f.inherited),plan=extendFrontServerPlan(f.inherited,f.descriptor),
  bindings=new Map(plan.serverConfig.bindings.map(row=>[row.url,row]));
 assert.deepEqual(f.inherited,before);assert.deepEqual(plan.document,before.document);
 assert.deepEqual(plan.preservedProductionServerConfig,before.serverConfig);
 assert.equal(bindings.get('/universal/long_adapter.mjs').path,'/TEST_ONLY/front_adapter.mjs');
 assert.equal(bindings.get('/universal/long_area_timeline.mjs').sha256,g);assert.equal(bindings.get('/front-v4/profile.json').sha256,h);
 assert.deepEqual(plan.serverConfig.runtimeConfig.universalVideo.frontV4,plan.frontIntegrity);
 assert.notEqual(plan.sourceSignature,f.inherited.sourceSignature);
});
test('source manifest rejects traversal, self-hash, missing runtime and invalid SHA',()=>{
 const valid={schema:'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4',profileId:FRONT_RUNTIME_PROFILE,
  files:Object.fromEntries(['front_runtime.mjs','front_capture.mjs','front_adapter.mjs','front_visual.mjs'].map(name=>[name,h]))};
 assert.equal(validateFrontManifest(valid),valid);
 for(const [name,value]of [['../OTHER',h],['/absolute',h],['FRONT_FILES.json',h],['SECRET','no-hash']]){
  const bad=structuredClone(valid);bad.files[name]=value;assert.throws(()=>validateFrontManifest(bad));
 }
 const missing=structuredClone(valid);delete missing.files['front_capture.mjs'];assert.throws(()=>validateFrontManifest(missing));
});
function capturedFor(plan,frame){
 const selected=selectFrontSnapshot(plan.frontProfile,frame),source=plan.frontProfile.fronts[0];
 return{diagnostic:{frame,universalVideo:{frontV4:structuredClone(plan.frontIntegrity)},frontV4:{runtimeProfile:FRONT_RUNTIME_PROFILE,
  integrity:structuredClone(plan.frontIntegrity),selection:selected,sourceGeometrySha256:hash(source.geometry),softwareProbeVariant:'AFTER',originalParentPlanUnchanged:true,
  noInferredEnemyComplement:true,noInferredHistoricalUnits:true,originalProjectionUsed:true,originalNativeMarkerStyleAndAnchor:true,
  unverifiedSchematicAreaSuppressed:true},area:{controls:{areas:[],fronts:sourceLineChunks(source.geometry).map(row=>({geometry:row.geometry}))},
   date:{geometry:{text:selected.sourceLabel}}},productionV3:{geometryClock:evaluateProductionGeometryClock(plan.document,frame)}}};
}
test('capture verifier checks actual archival geometry, provenance, date glyph, and zero inferred fill',async()=>{
 const f=fixture(),plan=extendFrontServerPlan(f.inherited,f.descriptor),good=capturedFor(plan,31);
 assert.equal(await assertFrontCapturedFrame(good,plan),good);
 for(const mutate of [d=>d.area.controls.areas.push({id:'INVENTED'}),d=>d.area.controls.fronts[0].geometry.coordinates[0][0]++,
  d=>d.frontV4.selection.mapDate='1953-07-27',d=>d.frontV4.integrity.profileSha256=g,
  d=>d.area.date.geometry.text='UNQUALIFIED',d=>d.frontV4.noInferredHistoricalUnits=false]){
  const bad=structuredClone(good);mutate(bad.diagnostic);await assert.rejects(assertFrontCapturedFrame(bad,plan));
 }
 const fallback=capturedFor(plan,29);assert.equal(await assertFrontCapturedFrame(fallback,plan),fallback);
 fallback.diagnostic.productionV3.geometryClock.sourceGeometryFrame++;await assert.rejects(assertFrontCapturedFrame(fallback,plan));
});
test('hardware opener rejects manufactured or mutated unsealed loaded plans before starting any browser',async()=>{
 const f=fixture(),plan=extendFrontServerPlan(f.inherited,f.descriptor);
 await assert.rejects(openLongRuntime({loadedPlan:plan}),/FRONT_V4_VERIFIED_LOADED_PLAN_REQUIRED/);
});
test('only the explicitly marked software probe may load an unbound old plan; hardware requires exact profile and manifest hashes',()=>{
 const integrity={profileSha256:h,sourceManifestSha256:g},document={sourceManifest:{}};
 assert.throws(()=>validateFrontPlanBinding(document,integrity),/FRONT_V4_EXECUTION_PROFILE_BINDING_REQUIRED/);
 assert.equal(validateFrontPlanBinding(document,integrity,{testOnlySoftwareProbe:true}).hardwareEligible,false);
 document.sourceManifest.archivalFrontV4={profileId:FRONT_RUNTIME_PROFILE,profileSha256:h,sourceManifestSha256:g};
 assert.equal(validateFrontPlanBinding(document,integrity).hardwareEligible,true);
 document.sourceManifest.archivalFrontV4.profileSha256=g;assert.throws(()=>validateFrontPlanBinding(document,integrity));
 assert.throws(()=>validateFrontPlanBinding(document,integrity,{testOnlySoftwareProbe:true}));
});
test('synthetic projection contract measures only retained source edges and rejects crop or unresolved length',async()=>{
 const front={geometry:{type:'MultiLineString',coordinates:[[[20,20],[30,30]],[[40,30],[60,30]]]}},
  page={evaluate:async(_callback,parts)=>structuredClone(parts)},actual=await measureSourceProjection(page,front,{safeArea:[0,0,100,100]});
 assert.equal(actual.retainedCoordinateCount,4);assert.equal(actual.sourcePartCount,2);
 assert.ok(Math.abs(actual.projectedLengthPixels-(Math.sqrt(200)+20))<1e-9);assert.equal(actual.allRetainedSegmentsInSafeArea,true);
 await assert.rejects(measureSourceProjection(page,front,{safeArea:[25,0,100,100]}),/CROPPED_BY_SAFE_AREA/);
 await assert.rejects(measureSourceProjection({evaluate:async()=>[[[10,10],[10,10.1]]]},front,{safeArea:[0,0,100,100]}),/SOURCE_PROJECTED_LENGTH_SUBPIXEL/);
});
test('software harness explicitly marks scene range, probe-only source suppression, and sample scope',()=>{
 const f=fixture(),p=normalizeFrontProfile(f.profile,{totalFrames:60,eventChapters:f.chapters}),
  document={totalFrames:60,scenes:[{sceneId:'s0',startFrame:0,endFrame:30},{sceneId:'s1',startFrame:30,endFrame:60}]},
  selected=selectFrontProbeFrames(document,p);assert.deepEqual(selected.frames,[0,44,59]);
 const base={runtimeConfig:{frontV4:{runtimeProfile:FRONT_RUNTIME_PROFILE},universalVideo:{}}},scene=document.scenes[1],
  config=softwareConfigFor(base,scene,'SUPPRESS_ARCHIVAL_FRONT');
 assert.equal(config.runtimeConfig.testOnlySoftwareProbe,true);assert.equal(config.runtimeConfig.universalVideo.testOnly,true);
 assert.equal(config.runtimeConfig.frontV4ProbeVariant,'SUPPRESS_ARCHIVAL_FRONT');assert.deepEqual(base.runtimeConfig.universalVideo,{});
 assert.throws(()=>softwareConfigFor(base,scene,'NVIDIA_PASS'));
});
test('only a source-front-only pass changes border priority; the original native mask and all source coordinates stay unchanged',()=>{
 const segments=[{a:[10,20],b:[30,40],radiusPx:14}],controls={areas:[],fronts:[{geometry:{type:'LineString',coordinates:[[10,10],[11,11]]}}],impacts:[],propagations:[]},
  original=structuredClone({segments,controls}),source=selectSourceFrontBoundaryPolicy({sourceActiveFrame:true,controls,boundarySegments:segments}),
  fallback=selectSourceFrontBoundaryPolicy({sourceActiveFrame:false,controls,boundarySegments:segments});
 assert.equal(source.policy,'ARCHIVAL_SOURCE_FRONT_ABOVE_STATIC_COUNTRY_BOUNDARY');assert.deepEqual(source.boundarySegments,[]);
 assert.equal(source.nativeBoundaryRestoreUnchanged,true);assert.equal(source.protectedGraphicMasksUnchanged,true);
 assert.equal(source.changedNativeBoundaryPixelsAllowedOnlyWithinActualSourceFrontSupport,true);
 assert.equal(fallback.policy,'PRESERVED_NATIVE_BOUNDARY_OCCLUSION');assert.equal(fallback.boundarySegments,segments);
 assert.deepEqual({segments,controls},original);
});
test('source border-priority policy rejects mixed area/impact/propagation passes and ambiguous activation',()=>{
 const base={areas:[],fronts:[{id:'SOURCE_ONLY'}],impacts:[],propagations:[]};
 for(const mutate of [c=>c.areas.push({}),c=>c.fronts=[],c=>c.impacts.push({}),c=>c.propagations.push({})]){
  const controls=structuredClone(base);mutate(controls);
  assert.throws(()=>selectSourceFrontBoundaryPolicy({sourceActiveFrame:true,controls,boundarySegments:[]}),/SOURCE_FRONT_ONLY_BOUNDARY_PRIORITY_REQUIRED/);
 }
 assert.throws(()=>selectSourceFrontBoundaryPolicy({sourceActiveFrame:'true',controls:base,boundarySegments:[]}));
});
test('synthetic readback guard requires visible source core and rejects unrelated pixels, protected text, unsafe pixels or expanded glow',()=>{
 const before=new Uint8Array(1080*1920*4),after=before.slice(),set=(x,y)=>{const i=((1919-y)*1080+x)*4;after.set([255,255,255,255],i);},
  options={safeArea:[0,0,1080,1920],protectedGraphics:[],projectedParts:[[[95.5,100.5],[110.5,100.5]]],frontCoreWidthPixels:4.8,frontGlowRadiusPixels:10};
 set(100,100);const valid=compareSourceFrontPixels(before,after,options);
 assert.equal(valid.changedPixelCount,1);assert.equal(valid.sourceCoreChangedPixelCount,1);
 assert.equal(valid.outsideSourceCorridorChangedPixelCount,0);assert.equal(valid.sourceSupportRadiusPixels,12.9);
 set(130,100);assert.throws(()=>compareSourceFrontPixels(before,after,options),/PIXELS_CHANGED_OUTSIDE_ACTUAL_SOURCE_CORRIDOR/);
 after.fill(0);set(100,100);
 assert.throws(()=>compareSourceFrontPixels(before,after,{...options,protectedGraphics:[{kind:'TEXT',box:[99,99,103,103]}]}),/CHANGED_PROTECTED_GRAPHIC_PIXELS/);
 assert.throws(()=>compareSourceFrontPixels(before,after,{...options,safeArea:[0,0,50,50]}),/CHANGED_OUTSIDE_SAFE_AREA/);
 assert.throws(()=>compareSourceFrontPixels(before,after,{...options,frontCoreWidthPixels:7}),/APPROVED_SOURCE_STYLE_SUPPORT_EXCEEDED/);
 after.fill(0);assert.throws(()=>compareSourceFrontPixels(before,after,options),/MUST_CHANGE_ACTUAL_PIXELS/);
 after.fill(0);set(100,110);assert.throws(()=>compareSourceFrontPixels(before,after,options),/SOURCE_WHITE_CORE_NOT_VISIBLE/);
});
test('capture hook changes only the exact frozen capture import edge',()=>{
 let count=0;const next=()=>{count++;return'UNCHANGED';};
 assert.deepEqual(resolveFrontCapture('./long_runtime.mjs',{parentURL:originalCaptureURL},next),{url:frontRuntimeURL,shortCircuit:true});
 for(const [specifier,parentURL]of [['./long_runtime.mjs','file:///OTHER'],['../long_runtime.mjs',originalCaptureURL],['./other.mjs',originalCaptureURL]])
  assert.equal(resolveFrontCapture(specifier,{parentURL},next),'UNCHANGED');assert.equal(count,3);
});
test('original immutable runtime and bounded capture remain exact',async()=>{
 for(const [name,expected]of [['long_runtime.mjs','ee50049ad9967b22d5aa7dae09bd9e5295d22882c5d5c3db2b2cd4dec25dc606'],
  ['long_capture.mjs','a4a6904dabd9a3306ffeafe0c1b0035f6062af81a56f62a0eb55dd055924d4d0']]){
  const bytes=await readFile(new URL('../../universal-auto-video-v2/'+name,import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),expected);
 }
});
