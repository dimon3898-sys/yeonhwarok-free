/** Additive source-bound aliases over an inherited, already verified V4 server plan. No hardware admission. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {normalizeIntegrationVisualProfile,INTEGRATION_SCHEMA,INTEGRATION_PROFILE} from './presentation.mjs';
import {evaluateProductionGeometryClock} from '../universal-production-v3/production_visual_profile.mjs';
import {normalizeFrontProfile,selectFrontSnapshot} from '../verified-front-data-v4-recovery/front_visual.mjs';
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const INTEGRATION_BROWSER_BINDINGS=Object.freeze({
 '/production-v3/production_area_pass.mjs':'production_area_bridge.mjs',
 '/production-v3/production_native_camera.mjs':'production_camera_bridge.mjs',
 '/integration-v1/presentation.mjs':'presentation.mjs'});
const PARENT_BINDINGS=Object.freeze({
 '/production-v3/production_area_pass.mjs':'/integration-v1/parent_production_area_pass.mjs',
 '/production-v3/production_native_camera.mjs':'/integration-v1/parent_production_native_camera.mjs'});
/** Records must be verified by the caller from a local immutable source manifest before this pure composition. */
export function extendIntegrationServerPlan(inherited,{visualProfile={},records,manifestSha256}={}){
 assert.ok(inherited?.serverConfig&&hex(inherited.sourceSignature)&&Array.isArray(inherited.sourceBindings),
  'INTEGRATION_VERIFIED_PARENT_SERVER_PLAN_REQUIRED');
 assert.ok(hex(manifestSha256)&&Array.isArray(records)&&records.length>0&&records.length<=128,
  'INTEGRATION_BOUNDED_MANIFEST_REQUIRED');
 const normalized=normalizeIntegrationVisualProfile(visualProfile),config=structuredClone(inherited.serverConfig),
  bindings=new Map(config.bindings.map(row=>[row.url,row])),byName=new Map();
 assert.equal(bindings.size,config.bindings.length,'INTEGRATION_PARENT_DUPLICATE_URL');
 assert.equal(config.runtimeConfig?.frontV4?.runtimeProfile,'VERIFIED_ARCHIVAL_FRONT_V4',
  'INTEGRATION_REAL_ARCHIVAL_PARENT_REQUIRED');
 assert.ok(!Object.hasOwn(config.runtimeConfig,'integrationV1'),'INTEGRATION_ALREADY_BOUND');
 for(const row of records){
  assert.ok(typeof row.name==='string'&&row.name&&!path.isAbsolute(row.name)&&!/[\\\0]/.test(row.name)
   &&row.name.split('/').every(part=>part&&part!=='.'&&part!=='..')&&!byName.has(row.name)&&hex(row.sha256)
   &&path.isAbsolute(row.file)&&path.resolve(row.file)===row.file&&Number.isSafeInteger(row.bytes)&&row.bytes>0,
   'INTEGRATION_EXACT_SOURCE_RECORD_REQUIRED');byName.set(row.name,row);
 }
 for(const [url,alias]of Object.entries(PARENT_BINDINGS)){
  const parent=bindings.get(url);assert.ok(parent&&hex(parent.sha256),'INTEGRATION_PARENT_PUBLIC_FACTORY_MISSING');
  assert.ok(!bindings.has(alias),'INTEGRATION_PARENT_ALIAS_COLLISION');bindings.set(alias,{...parent,url:alias});
 }
 for(const [url,name]of Object.entries(INTEGRATION_BROWSER_BINDINGS)){
  const record=byName.get(name);assert.ok(record,'INTEGRATION_BROWSER_SOURCE_NOT_MANIFESTED_'+name);
  if(!Object.hasOwn(PARENT_BINDINGS,url))assert.ok(!bindings.has(url),'INTEGRATION_BROWSER_ALIAS_COLLISION');
  bindings.set(url,{url,path:record.file,bytes:record.bytes,sha256:record.sha256});
 }
 const signature=hash(Object.entries(INTEGRATION_BROWSER_BINDINGS).map(([url,name])=>({url,
  sha256:byName.get(name).sha256,bytes:byName.get(name).bytes}))),
  integrity={schema:INTEGRATION_SCHEMA,profile:INTEGRATION_PROFILE,visualProfile:{...normalized},
   profileSha256:hash(normalized),sourceManifestSha256:manifestSha256,browserSourceSignature:signature};
 config.runtimeConfig.integrationV1=integrity;config.bindings=[...bindings.values()];
 const sourceBindings=[...inherited.sourceBindings,...records.map(row=>({
  path:inherited.engine?path.relative(inherited.engine,row.file).replaceAll(path.sep,'/'):row.file,bytes:row.bytes,sha256:row.sha256}))];
 return{...inherited,serverConfig:config,sourceBindings,
  sourceSignature:hash({parent:inherited.sourceSignature,integrationV1:integrity,sourceBindings}),
  integrationV1:structuredClone(integrity),integrationSourceRecords:structuredClone(records),
  preservedFrontServerConfig:structuredClone(inherited.serverConfig)};
}
/** Source clock trace only: uses the exact existing V3 and V4 evaluators, never renders or synthesizes control. */
export function* integrationFrameSelections({plan,frontProfile,startFrame=0,endFrame=plan?.totalFrames}={}){
 assert.ok(Number.isSafeInteger(plan?.totalFrames)&&plan.totalFrames>0&&Number.isSafeInteger(startFrame)
  &&Number.isSafeInteger(endFrame)&&startFrame>=0&&endFrame>startFrame&&endFrame<=plan.totalFrames,
  'INTEGRATION_EXACT_FRAME_RANGE_REQUIRED');
 const normalized=normalizeFrontProfile(frontProfile,{totalFrames:plan.totalFrames,eventChapters:plan.productionV3?.eventChapters});
 for(let frame=startFrame;frame<endFrame;frame++){
  const geometryClock=evaluateProductionGeometryClock(plan,frame),selection=selectFrontSnapshot(normalized,frame);
  yield{frame,geometryClock,selection,areaPolicy:selection.sourceActiveFrame?'NO_INFERRED_OCCUPATION_FILL':
   geometryClock.eventEnabled?'PRESERVED_QUALIFIED_SCHEMATIC_AREAS':'NO_EVENT_GEOMETRY',
   exactOwnershipClaimed:false,inventedUnitPositions:false,hardwareVerified:false,visualOutputVerified:false};
 }
}
