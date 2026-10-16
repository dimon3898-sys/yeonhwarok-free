/** Separate archival-front source seal over the untouched V3 plan and hardware admission. */
import assert from 'node:assert/strict';
import {readFile,lstat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import * as production from '../universal-production-v3/long_runtime.mjs';
import * as nativeRuntime from '../universal-auto-video-v2/long_runtime.mjs';
import {evaluateProductionGeometryClock} from '../universal-production-v3/production_visual_profile.mjs';
import {FRONT_RUNTIME_PROFILE,normalizeFrontProfile,selectFrontSnapshot,sourceLineChunks} from './front_visual.mjs';

export const root=path.dirname(fileURLToPath(import.meta.url));
export const {engine,repo,sha,boundedSource}=nativeRuntime;
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),seals=new WeakMap(),
 hash=value=>sha(Buffer.from(JSON.stringify(value)));
export const FRONT_BROWSER_BINDINGS=Object.freeze({'/universal/long_adapter.mjs':'front_adapter.mjs','/front-v4/front_visual.mjs':'front_visual.mjs'});
export function validateFrontPlanBinding(document,integrity,{testOnlySoftwareProbe=false}={}){
 assert.equal(typeof testOnlySoftwareProbe,'boolean','FRONT_V4_EXPLICIT_PROBE_MODE_REQUIRED');
 const binding=document?.sourceManifest?.archivalFrontV4;
 if(testOnlySoftwareProbe&&binding===undefined)return{mode:'TEST_ONLY_UNCHANGED_PARENT_FIXTURE',hardwareEligible:false};
 assert.equal(binding?.profileId,FRONT_RUNTIME_PROFILE,'FRONT_V4_EXECUTION_PROFILE_BINDING_REQUIRED');
 assert.equal(binding.profileSha256,integrity.profileSha256,'FRONT_V4_EXECUTION_PROFILE_SHA_MISMATCH');
 assert.equal(binding.sourceManifestSha256,integrity.sourceManifestSha256,'FRONT_V4_EXECUTION_MANIFEST_SHA_MISMATCH');
 return{mode:'HASH_BOUND_ARCHIVAL_EXECUTION_PLAN',hardwareEligible:!testOnlySoftwareProbe};
}
export function validateFrontManifest(manifest){
 assert.equal(manifest?.schema,'WORLD_ENGINE_VERIFIED_FRONT_FILES_V4');assert.equal(manifest.profileId,FRONT_RUNTIME_PROFILE);
 assert.ok(manifest.files&&typeof manifest.files==='object'&&!Array.isArray(manifest.files),'FRONT_V4_MANIFEST_FILES_REQUIRED');
 const entries=Object.entries(manifest.files);assert.ok(entries.length>0&&entries.length<=4096,'FRONT_V4_BOUNDED_SOURCE_CLOSURE_REQUIRED');
 for(const [name,digest]of entries){
  assert.ok(typeof name==='string'&&name&&!path.isAbsolute(name)&&!/[\\\0]/.test(name)
   &&name.split('/').every(part=>part&&part!=='.'&&part!=='..'),'FRONT_V4_CANONICAL_SOURCE_NAME_REQUIRED');
  assert.ok(hex(digest),'FRONT_V4_SOURCE_SHA_REQUIRED');assert.notEqual(name,'FRONT_FILES.json','FRONT_V4_SELF_HASH_FORBIDDEN');
 }
 for(const name of ['front_runtime.mjs','front_capture.mjs',...Object.values(FRONT_BROWSER_BINDINGS)])
  assert.ok(hex(manifest.files[name]),'FRONT_V4_REQUIRED_RUNTIME_NOT_MANIFESTED_'+name);
 return manifest;
}
/** Pure config composition does not admit hardware. Only loadLongRuntimePlan seals a verified instance. */
export function extendFrontServerPlan(inherited,{profile,profileRecord,manifestSha256,records}){
 assert.ok(hex(manifestSha256)&&hex(profileRecord?.sha256)&&path.isAbsolute(profileRecord?.file),'FRONT_V4_BOUND_PROFILE_REQUIRED');
 const normalized=normalizeFrontProfile(profile,{totalFrames:inherited.document.totalFrames,eventChapters:inherited.document.productionV3.eventChapters}),
  byName=new Map(records.map(record=>[record.name,record])),config=structuredClone(inherited.serverConfig),
  bindings=new Map(config.bindings.map(record=>[record.url,record]));
 assert.ok(bindings.has('/universal/long_adapter.mjs'),'FRONT_V4_PARENT_BOOT_EDGE_REQUIRED');
 for(const [url,name]of Object.entries(FRONT_BROWSER_BINDINGS)){
  const row=byName.get(name);assert.ok(row&&hex(row.sha256)&&path.isAbsolute(row.file),'FRONT_V4_BROWSER_CLOSURE_REQUIRED');
  if(url!=='/universal/long_adapter.mjs')assert.ok(!bindings.has(url),'FRONT_V4_BROWSER_EDGE_COLLISION');
  bindings.set(url,{url,path:row.file,bytes:row.bytes,sha256:row.sha256});
 }
 assert.ok(!bindings.has('/front-v4/profile.json'),'FRONT_V4_PROFILE_EDGE_COLLISION');
 bindings.set('/front-v4/profile.json',{url:'/front-v4/profile.json',path:profileRecord.file,bytes:profileRecord.bytes,sha256:profileRecord.sha256});
 const integrity={runtimeProfile:FRONT_RUNTIME_PROFILE,sourceManifestSha256:manifestSha256,profileSha256:profileRecord.sha256,
  browserSourceSignature:hash(Object.entries(FRONT_BROWSER_BINDINGS).map(([url,name])=>({url,sha256:byName.get(name).sha256,bytes:byName.get(name).bytes})))};
 config.runtimeConfig.frontV4=structuredClone(integrity);config.runtimeConfig.universalVideo.frontV4=structuredClone(integrity);
 config.bindings=[...bindings.values()];
 const sourceBindings=[...inherited.sourceBindings,...records.map(row=>({path:path.relative(engine,row.file).replaceAll(path.sep,'/'),bytes:row.bytes,sha256:row.sha256}))],
  sourceSignature=hash({parent:inherited.sourceSignature,frontV4:integrity,sourceBindings});
 return{...inherited,preservedProductionServerConfig:structuredClone(inherited.serverConfig),serverConfig:config,sourceBindings,sourceSignature,frontProfile:normalized,frontIntegrity:integrity,
  frontSourceRecords:records,root};
}
export async function loadLongRuntimePlan(options={}){
 const {frontProfileFile=path.join(root,'FRONT_PROFILE.json'),expectedFrontProfileSha256,
  frontManifestFile=path.join(root,'FRONT_FILES.json'),expectedFrontManifestSha256}=options;
 assert.ok(hex(expectedFrontProfileSha256)&&hex(expectedFrontManifestSha256),'FRONT_V4_EXPLICIT_PROFILE_AND_MANIFEST_SHA_REQUIRED');
 assert.equal(path.dirname(frontManifestFile),root,'FRONT_V4_MANIFEST_ROOT_REQUIRED');
 assert.equal(path.basename(frontManifestFile),'FRONT_FILES.json','FRONT_V4_EXPLICIT_MANIFEST_NAME_REQUIRED');
 const inherited=await production.loadLongRuntimePlan(options),manifestRaw=await boundedSource(frontManifestFile,4*1024*1024);
 assert.equal(sha(manifestRaw),expectedFrontManifestSha256,'FRONT_V4_MANIFEST_SHA_MISMATCH');
 const manifest=validateFrontManifest(JSON.parse(manifestRaw)),records=[{name:'FRONT_FILES.json',file:frontManifestFile,
  bytes:manifestRaw.length,sha256:sha(manifestRaw)}];
 for(const [name,expected]of Object.entries(manifest.files)){
  const file=path.join(root,name),bytes=await boundedSource(file,128*1024*1024);
  assert.equal(sha(bytes),expected,'FRONT_V4_SOURCE_SHA_MISMATCH');records.push({name,file,bytes:bytes.length,sha256:sha(bytes)});
 }
 const profileRecord=records.find(record=>record.file===frontProfileFile);
 assert.ok(profileRecord,'FRONT_V4_PROFILE_NOT_SOURCE_MANIFESTED');
 assert.equal(profileRecord.sha256,expectedFrontProfileSha256,'FRONT_V4_PROFILE_SHA_MISMATCH');
 const profileBytes=await boundedSource(frontProfileFile,16*1024*1024);
 assert.equal(sha(profileBytes),profileRecord.sha256,'FRONT_V4_PROFILE_CHANGED_AFTER_VERIFICATION');
 const plan=extendFrontServerPlan(inherited,{profile:JSON.parse(profileBytes),profileRecord,manifestSha256:sha(manifestRaw),records});
 for(const front of plan.frontProfile.fronts){
  const row=records.find(record=>record.name===front.sourceFile);assert.ok(row,'FRONT_V4_GEOJSON_NOT_MANIFESTED');
  assert.equal(row.sha256,front.geoJsonSha256,'FRONT_V4_GEOJSON_FILE_SHA_MISMATCH');
  const raw=await boundedSource(row.file,16*1024*1024);assert.equal(sha(raw),row.sha256,'FRONT_V4_GEOJSON_CHANGED_AFTER_VERIFICATION');
  const object=JSON.parse(raw),geometry=object.type==='Feature'?object.geometry:object.type==='FeatureCollection'
   ?(assert.equal(object.features?.length,1,'FRONT_V4_ONE_SOURCE_GEOMETRY_PER_FILE_REQUIRED'),object.features[0].geometry):object;
  assert.deepEqual(geometry,front.geometry,'FRONT_V4_PROFILE_GEOMETRY_DIFFERS_FROM_SOURCE_GEOJSON');
 }
 plan.frontExecutionBinding=validateFrontPlanBinding(plan.document,plan.frontIntegrity,{testOnlySoftwareProbe:options.testOnlySoftwareProbe??false});
 plan.assertSourceUnchanged=async()=>{await inherited.assertSourceUnchanged();
  for(const row of records)assert.equal(sha(await boundedSource(row.file,128*1024*1024)),row.sha256,'FRONT_V4_BOUND_SOURCE_CHANGED');return true;};
 seals.set(plan,hash(plan.serverConfig));return plan;
}
export async function assertFrontCapturedFrame(captured,plan){
 const d=captured?.diagnostic;if(!d)return captured;
 assert.ok(Number.isSafeInteger(d.frame)&&d.frame>=plan.scene.startFrame&&d.frame<plan.scene.endFrame,'FRONT_V4_CAPTURE_FRAME_RANGE_REQUIRED');
 assert.equal(d.frontV4?.runtimeProfile,FRONT_RUNTIME_PROFILE);
 assert.deepEqual(d.frontV4.integrity,plan.frontIntegrity,'FRONT_V4_CAPTURE_SOURCE_INTEGRITY_REQUIRED');
 assert.deepEqual(d.universalVideo?.frontV4,plan.frontIntegrity,'FRONT_V4_CAPTURE_RUNTIME_BINDING_REQUIRED');
 const selected=selectFrontSnapshot(plan.frontProfile,d.frame);
 assert.deepEqual(d.frontV4.selection,selected,'FRONT_V4_ACTUAL_MAP_SELECTION_REQUIRED');
 assert.equal(d.frontV4.originalParentPlanUnchanged,true);assert.equal(d.frontV4.noInferredEnemyComplement,true);
 assert.equal(d.frontV4.softwareProbeVariant,'AFTER','FRONT_V4_TEST_SUPPRESSION_FORBIDDEN_IN_CAPTURE');
 assert.equal(d.frontV4.noInferredHistoricalUnits,true);assert.equal(d.frontV4.originalProjectionUsed,true);
 assert.equal(d.frontV4.originalNativeMarkerStyleAndAnchor,true);
 if(selected.sourceActiveFrame){
  const source=plan.frontProfile.fronts.find(row=>row.frontId===selected.frontId),chunks=sourceLineChunks(source.geometry);
  assert.deepEqual(d.area?.controls?.areas,[],'FRONT_V4_UNVERIFIED_OWNERSHIP_FILL_FORBIDDEN');
  assert.deepEqual(d.area?.controls?.fronts?.map(row=>row.geometry),chunks.map(row=>row.geometry),'FRONT_V4_ACTUAL_SOURCE_COORDINATES_REQUIRED');
  assert.equal(d.frontV4.sourceGeometrySha256,hash(source.geometry),'FRONT_V4_ACTUAL_GEOMETRY_HASH_REQUIRED');
  assert.equal(d.area?.date?.geometry?.text,selected.sourceLabel,'FRONT_V4_VISIBLE_SOURCE_DATE_QUALIFIER_REQUIRED');
  assert.equal(d.frontV4.unverifiedSchematicAreaSuppressed,true);
 }else{
  assert.deepEqual(d.productionV3?.geometryClock,evaluateProductionGeometryClock(plan.document,d.frame),'FRONT_V4_SCHEMATIC_CLOCK_CHANGED');
 }
 return captured;
}
export async function openLongRuntime({loadedPlan=null,...options}={}){
 const plan=loadedPlan??await loadLongRuntimePlan(options),seal=seals.get(plan);
 assert.ok(seal,'FRONT_V4_VERIFIED_LOADED_PLAN_REQUIRED');assert.equal(hash(plan.serverConfig),seal,'FRONT_V4_SERVER_CONFIG_CHANGED_BEFORE_HARDWARE');
 assert.equal(plan.frontExecutionBinding?.hardwareEligible,true,'FRONT_V4_SOFTWARE_FIXTURE_HARDWARE_FORBIDDEN');
 validateFrontPlanBinding(plan.document,plan.frontIntegrity);
 await plan.assertSourceUnchanged();
 // The immutable underlying opener still enforces pinned Node/Playwright,
 // browser admission, NVIDIA hardware identity, isolation and loopback-only I/O.
 const runtime=await nativeRuntime.openLongRuntime({...options,loadedPlan:plan});
 try{
  assert.equal(runtime.info.frontV4?.runtimeProfile,FRONT_RUNTIME_PROFILE);
  assert.deepEqual(runtime.info.frontV4.integrity,plan.frontIntegrity,'FRONT_V4_ACTUAL_BOOT_INTEGRITY_REQUIRED');
  const page=new Proxy(runtime.page,{get(target,key){
   if(key==='evaluate')return async(...args)=>assertFrontCapturedFrame(await target.evaluate(...args),plan);
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});return{...runtime,page};
 }catch(error){await runtime.close();throw error;}
}
