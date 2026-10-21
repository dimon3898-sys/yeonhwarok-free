/** Opt-in source-bound software lane over preserved WORLD ENGINE owners.
 * Original inputs/claims/images stay unchanged. No production GPU admission.
 */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {boundedSource} from '../universal-auto-video-v2/long_runtime.mjs';
import {loadSoftwarePreviewPlan,openSoftwarePreviewRuntime} from '../universal-overnight-v3/free_preview_runner.mjs';
import {loadSourceOptions,validateCommonNativeContext} from '../story-director-16frames-v1/runtime_adapter.mjs';
import {normalizeFrontProfile,sourceLineChunks} from '../verified-front-data-v4-recovery/front_visual.mjs';
import {suppliedFrontObservations} from '../universal-integration-completion-v2/source_observations.mjs';
import {compileSuppliedFrontMotion} from '../universal-integration-completion-v2/frontier_extension.mjs';
import {normalizeIntegrationVisualProfile} from '../universal-integration-v1/presentation.mjs';
import {compileDerivedScene} from './derive_scene.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url)),sha=x=>createHash('sha256').update(x).digest('hex'),
 hash=x=>sha(Buffer.from(JSON.stringify(x))),clone=x=>structuredClone(x);
export const DIRECTOR_BINDINGS=Object.freeze({
 '/universal/long_adapter.mjs':'browser_adapter.mjs',
 '/astra-director-v2/frame_context.mjs':'frame_context.mjs',
 '/production-v3/production_native_camera.mjs':'camera_bridge.mjs',
 '/astra-director-v2/camera_plan.mjs':'camera_plan.mjs',
 '/reference/reference_source_material.mjs':'material_bridge.mjs',
 '/astra-director-v2/material_context.mjs':'material_context.mjs',
 '/astra-director-v2/control_bridge.mjs':'control_bridge.mjs',
 '/astra-director-v2/partial_front_pass.mjs':'partial_front_pass.mjs'});
const PARENT_ALIASES=Object.freeze({
 '/universal/long_adapter.mjs':'/astra-director-v2/parent_adapter.mjs',
 '/reference/reference_source_material.mjs':'/reference/director_parent_source_material.mjs'});
const CAPABILITY_FILES=Object.freeze({'EVENT.CORRECT_CHRONOLOGY':'derive_scene.mjs',
 'SOURCE.NO_PREVIOUS_FALLBACK':'derive_scene.mjs','AREA.SUPPLIED_PARTIAL_FRONT':'browser_adapter.mjs',
 'ASTRA.COMPOSED_TEXTURE':'material_context.mjs','CAMERA.REGIONAL_REVIEW':'camera_bridge.mjs'});

export async function loadEventDirectorPlan({preparedFile,normalizationFile,cameraProfileFile,cameraAdmissionFile}={}){
 assert.equal(typeof preparedFile,'string','DIRECTOR_CANONICAL_PREPARATION_REQUIRED');
 assert.equal(typeof normalizationFile,'string','DIRECTOR_NORMALIZER_EXECUTION_RECEIPT_REQUIRED');
 const sources=await loadSourceOptions(preparedFile),parent=await loadSoftwarePreviewPlan(sources),records=[];
 async function record(file,url=null){const raw=await boundedSource(path.resolve(file),32*1024*1024),
  row={path:path.resolve(file),bytes:raw.length,sha256:sha(raw)};
  if(url)row.url=url;records.push(row);return{raw,row};}
 const normalized=JSON.parse((await record(normalizationFile)).raw),
  profileData=await record(path.join(ROOT,'fixtures/HISTORY_EVENT_PROFILE_V2.json')),
  catalogData=await record(path.join(ROOT,'fixtures/HISTORY_SOURCE_CATALOG.json')),
  compiler=await record(path.join(ROOT,'derive_scene.mjs')),
  receipt=JSON.parse((await record(path.join(ROOT,'reports/DERIVATION.json'))).raw),
  compiled=compileDerivedScene({sourceBytes:await boundedSource(sources.planFile),profileBytes:profileData.raw,
   catalogBytes:catalogData.raw,frontProfileBytes:await boundedSource(path.join(ROOT,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'))}),
  sceneData=await record(path.join(ROOT,'fixtures/DERIVED_SCENE.json')),
  frontData=await record(path.join(ROOT,'fixtures/DERIVED_FRONT_PROFILE.json'));
 assert.deepEqual(sceneData.raw,compiled.bytes,'DIRECTOR_ACTUAL_DERIVED_SCENE_BYTES_REQUIRED');
 assert.deepEqual(frontData.raw,compiled.frontBytes,'DIRECTOR_ACTUAL_DERIVED_FRONT_BYTES_REQUIRED');
 assert.equal(receipt.compilerSHA256,compiler.row.sha256,'DIRECTOR_COMPILER_SHA_REQUIRED');
 assert.equal(receipt.derivedSceneSHA256,sceneData.row.sha256);
 assert.equal(receipt.sourcePlanSHA256,sources.expectedPlanSha256);
 assert.equal(normalized.schema,'WORLD_ENGINE_EVENT_DIRECTOR_NORMALIZED_V1','DIRECTOR_EXPLICIT_NORMALIZER_RECEIPT_REQUIRED');
 assert.equal(normalized.normalizedRequest?.purpose,'QUALIFIED_SOURCE_REVIEW','DIRECTOR_FREE_SOURCE_REVIEW_ONLY');
 assert.equal(normalized.runtimeBindingManifest?.actualDerivation?.actualDerivedSceneSHA256,sceneData.row.sha256,
  'DIRECTOR_NORMALIZER_TO_RUNTIME_SCENE_BINDING_REQUIRED');
 assert.equal(normalized.reviewReady,true,'DIRECTOR_SOURCE_REVIEW_PREFLIGHT_REQUIRED');
 for(const[name,capability]of Object.entries(normalized.runtimeBindingManifest.capabilities)){
  if(!capability.available)continue;
  assert.ok(CAPABILITY_FILES[name],'DIRECTOR_CAPABILITY_NOT_REGISTERED_AT_RUNTIME');
  const {row}=await record(path.join(ROOT,CAPABILITY_FILES[name]));
  assert.equal(row.sha256,capability.sha256,'DIRECTOR_CAPABILITY_SOURCE_CHANGED_AFTER_NORMALIZATION');
 }
 assert.equal(profileData.row.sha256,normalized.normalizedRequest.eventDirectorProfileRef.sha256,'DIRECTOR_PROFILE_NORMALIZER_SHA_REQUIRED');
 assert.equal(catalogData.row.sha256,normalized.normalizedRequest.sourceCatalogRef.sha256,'DIRECTOR_CATALOG_NORMALIZER_SHA_REQUIRED');
 const profile=JSON.parse(profileData.raw),document=compiled.document,
  frontProfile=normalizeFrontProfile(compiled.frontProfile,{totalFrames:document.totalFrames,eventChapters:document.productionV3.eventChapters}),
  nativeContext=validateCommonNativeContext(document),config=clone(parent.serverConfig),
  bindings=new Map(config.bindings.map(x=>[x.url,x])),oldScene=clone(parent.scene),scene={
   sceneId:'ASTRA_V2_QUALIFIED_GLOBAL_SOURCE_REVIEW',startFrame:0,endFrame:document.totalFrames,
   globalFrameOffset:0,frameConvention:'GLOBAL_HALF_OPEN',renderProfile:clone(oldScene.renderProfile),
   captureWindowOnly:true,originalSceneRanges:nativeContext.sourceSceneRanges};
 for(const[url,alias]of Object.entries(PARENT_ALIASES)){
  const old=bindings.get(url);assert.ok(old&&!bindings.has(alias),'DIRECTOR_ORIGINAL_FACTORY_ALIAS_REQUIRED');
  bindings.set(alias,{...old,url:alias});
 }
 for(const[url,name]of Object.entries(DIRECTOR_BINDINGS)){
  const {row}=await record(path.join(ROOT,name),url);bindings.set(url,{...row});
 }
 for(const[url,name]of Object.entries({'/astra-director-v2/control.json':'CONTROL_TIMELINE.json',
  '/astra-director-v2/profile.json':'HISTORY_EVENT_PROFILE_V2.json','/astra-director-v2/catalog.json':'HISTORY_SOURCE_CATALOG.json'})){
  const {row}=await record(path.join(ROOT,'fixtures',name),url);bindings.set(url,{...row});
 }
 bindings.set('/front-v4/profile.json',{...frontData.row,url:'/front-v4/profile.json'});
 const frontIntegrity={...clone(parent.frontIntegrity),profileSha256:frontData.row.sha256,
  derivedSchedule:true,originalProfileSHA256:JSON.parse(catalogData.raw).originalFrontProfileSHA256,
  derivedSceneSHA256:sceneData.row.sha256,originalSourceProgramsUnchanged:true};
 config.runtimeConfig.frontV4=clone(frontIntegrity);
 const uv=config.runtimeConfig.universalVideo;
 uv.plan=clone(document);uv.planSha256=sceneData.row.sha256;uv.scene=clone(scene);uv.sceneRangeSha256=hash(scene);
 uv.frontV4=clone(frontIntegrity);
 const observations=suppliedFrontObservations(document,frontProfile);
 for(const observation of observations){
  const selected=profile.sourceSchedule.find(x=>observation.frame>=x.startFrame&&observation.frame<x.endFrame),
   extra=document.productionV3.directorAdditionalFronts.find(x=>x.frontId===selected.stateId);
  if(extra)observation.fronts.push(...sourceLineChunks(extra.geometry).map((chunk,index)=>({id:extra.frontId+'-part-'+index,geometry:chunk.geometry})));
 }
 const motion=compileSuppliedFrontMotion({observations,
  totalFrames:document.totalFrames,profile:config.runtimeConfig.completionV2.frontier});
 config.runtimeConfig.completionFrontierMotion=motion;
 config.runtimeConfig.completionIntegrity.motionSHA256=hash(motion);
 const visual=normalizeIntegrationVisualProfile({...config.runtimeConfig.integrationV1.visualProfile,
  territoryOpacity:profile.presentation.territoryOpacity});
 config.runtimeConfig.integrationV1.visualProfile=visual;
 config.runtimeConfig.integrationV1.profileSha256=hash(visual);
 const cameraProfileRecord=await record(cameraProfileFile),cameraAdmissionRecord=await record(cameraAdmissionFile),
  cameraProfile=JSON.parse(cameraProfileRecord.raw),cameraAdmission=JSON.parse(cameraAdmissionRecord.raw);
 assert.equal(cameraAdmissionRecord.row.sha256,normalized.normalizedRequest.cameraAdmissionRef.sha256,
  'DIRECTOR_CAMERA_NORMALIZER_SHA_REQUIRED');
 assert.equal(cameraProfileRecord.row.sha256,cameraAdmission.cameraProfileSHA256,
  'DIRECTOR_CAMERA_PROFILE_ADMISSION_SHA_REQUIRED');
 config.runtimeConfig.astraEventDirector={schema:'WORLD_ENGINE_EVENT_DIRECTOR_RUNTIME_V2',purpose:'QUALIFIED_SOURCE_REVIEW',
  profile,profileSHA256:profileData.row.sha256,catalogSHA256:catalogData.row.sha256,
  sourcePlanSHA256:sources.expectedPlanSha256,derivedSceneSHA256:sceneData.row.sha256,
  normalizerReceiptSHA256:sha(await boundedSource(normalizationFile)),normalization:normalized,
  cameraProfile,cameraAdmission,originalLegacySceneSHA256:receipt.legacySceneSHA256,
  fullControlReady:false,productionEligible:false,visualQualityApproved:false,
  noSilentPresetFallback:true};
 config.runtimeConfig.testOnlySoftwareProbe=true;
 config.bindings=[...bindings.values()];
 const configSHA=hash(config),checkParent=parent.assertSourceUnchanged;
 const loaded={...parent,document,scene,sceneRangeSha256:hash(scene),planSha256:sceneData.row.sha256,
  frontProfile,frontIntegrity,serverConfig:config,
  completionIntegrity:clone(config.runtimeConfig.completionIntegrity),
  sourcePlanSHA256:sources.expectedPlanSha256,derivedSceneSHA256:sceneData.row.sha256,
  sourceBindings:[...parent.sourceBindings,...records.map(x=>({path:x.path,bytes:x.bytes,sha256:x.sha256}))],
  directorSourceRecords:clone(records),
  sourceSignature:hash({parent:parent.sourceSignature,configSHA,sourceRecords:records}),
  async assertSourceUnchanged(){await checkParent();assert.equal(hash(config),configSHA,'DIRECTOR_RUNTIME_CONFIG_MUTATED');
   for(const r of records)assert.equal(sha(await boundedSource(r.path,32*1024*1024)),r.sha256,'DIRECTOR_SELECTED_SOURCE_CHANGED');
   return true;}};
 await loaded.assertSourceUnchanged();return loaded;
}
export async function openEventDirectorRuntime(options={}){
 return openSoftwarePreviewRuntime({...options,loadPlan:loadEventDirectorPlan});
}
