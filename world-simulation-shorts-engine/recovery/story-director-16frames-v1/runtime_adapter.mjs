/**
 * Read-only, software-only director view over the existing 80-second renderer.
 * This is a capture-window adapter, not a replacement renderer or Scene parser.
 * Source chapter clocks, polygon/front geometry, ASTRA inputs and payload hashes
 * are consumed by their original owners. No Studio/GPU admission is created.
 */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {boundedSource} from '../universal-auto-video-v2/long_runtime.mjs';
import {loadSoftwarePreviewPlan,openSoftwarePreviewRuntime}
 from '../universal-overnight-v3/free_preview_runner.mjs';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const hash=value=>sha(Buffer.from(JSON.stringify(value)));
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const clone=value=>structuredClone(value);

/** Reuse the actual earlier source preparation receipt, without regenerating it. */
export async function loadSourceOptions(preparedFile){
 assert.equal(typeof preparedFile,'string','DIRECTOR_PREPARED_SOURCE_RECEIPT_REQUIRED');
 const raw=await boundedSource(path.resolve(preparedFile)),receipt=JSON.parse(raw),
  options=receipt.options;
 assert.equal(receipt.status,'PASS','DIRECTOR_VALID_SOURCE_PREPARATION_REQUIRED');
 assert.ok(options&&path.isAbsolute(options.planFile)&&hex(options.expectedPlanSha256)
  &&typeof options.sceneId==='string'&&options.sceneId,'DIRECTOR_SOURCE_OPTIONS_REQUIRED');
 assert.equal(sha(await boundedSource(options.planFile)),options.expectedPlanSha256,
  'DIRECTOR_PREPARED_PLAN_SHA_MISMATCH');
 assert.ok(path.isAbsolute(options.activationFile)&&hex(options.expectedActivationSha256),
  'DIRECTOR_EXISTING_ASTRA_ACTIVATION_REQUIRED');
 assert.equal(sha(await boundedSource(options.activationFile)),options.expectedActivationSha256,
  'DIRECTOR_EXISTING_ASTRA_ACTIVATION_SHA_MISMATCH');
 assert.ok(path.isAbsolute(options.submissionFile),'DIRECTOR_FROZEN_SUBMISSION_REQUIRED');
 const submission=JSON.parse(await boundedSource(options.submissionFile)),
  document=JSON.parse(await boundedSource(options.planFile));
 assert.deepEqual(submission.videoPlan,document,'DIRECTOR_SUBMISSION_PLAN_BINDING_REQUIRED');
 return{planFile:options.planFile,expectedPlanSha256:options.expectedPlanSha256,
  sceneId:options.sceneId,activationFile:options.activationFile,
  expectedActivationSha256:options.expectedActivationSha256,submissionFile:options.submissionFile};
}

/** All chapters may share one native context only when this is proven by data. */
export function validateCommonNativeContext(document){
 assert.equal(document?.schema,'WORLD_ENGINE_UNIVERSAL_VIDEO_V2');
 assert.ok(Number.isSafeInteger(document.totalFrames)&&document.totalFrames>0);
 assert.ok(Array.isArray(document.scenes)&&document.scenes.length>0);
 const payloads=document.scenes.map(scene=>scene.renderProfile?.nativePayload);
 assert.ok(payloads.every(row=>row&&hex(row.sha256)&&row.validationStatus==='VERIFIED'),
  'DIRECTOR_VERIFIED_NATIVE_PAYLOAD_REQUIRED');
 assert.ok(payloads.every(row=>JSON.stringify(row)===JSON.stringify(payloads[0])),
  'DIRECTOR_MULTIPLE_NATIVE_CONTEXTS_REQUIRE_SEPARATE_STATE_RESTORE');
 let next=0;
 for(const scene of document.scenes){
  assert.equal(scene.startFrame,next,'DIRECTOR_CONTIGUOUS_SOURCE_CHAPTERS_REQUIRED');
  assert.ok(Number.isSafeInteger(scene.endFrame)&&scene.endFrame>next);
  next=scene.endFrame;
 }
 assert.equal(next,document.totalFrames,'DIRECTOR_COMPLETE_SOURCE_TIME_REQUIRED');
 return{payload:clone(payloads[0]),sourceSceneRanges:document.scenes.map(scene=>({
  sceneId:scene.sceneId,startFrame:scene.startFrame,endFrame:scene.endFrame,
  nativePayloadSHA256:scene.renderProfile.nativePayload.sha256}))};
}

/**
 * The source document remains byte-identical. A separate, explicitly labelled
 * sampling range exposes global indices to the existing deterministic consumer.
 */
export function extendDirectorCaptureWindow(inherited,{profile=null,profileSHA256=null,
 bindingRecords=[]}={}){
 assert.equal(inherited?.serverConfig?.runtimeConfig?.testOnlySoftwareProbe,true,
  'DIRECTOR_SOFTWARE_ONLY_CONTEXT_REQUIRED');
 assert.ok(hex(inherited.planSha256)&&hex(inherited.legacySceneSha256));
 const sourceDocumentHash=hash(inherited.document),context=validateCommonNativeContext(inherited.document),
  originalScene=clone(inherited.scene),captureWindow={
   sceneId:'DIRECTOR_GLOBAL_SOURCE_CAPTURE_WINDOW',startFrame:0,endFrame:inherited.document.totalFrames,
   globalFrameOffset:0,frameConvention:'GLOBAL_HALF_OPEN',captureWindowOnly:true,
   renderProfile:clone(originalScene.renderProfile),
   eventSelection:'UNCHANGED_SOURCE_DOCUMENT_GLOBAL_CHAPTER_EVALUATOR',
   originalSceneRanges:context.sourceSceneRanges},
  sceneRangeSha256=hash(captureWindow),config=clone(inherited.serverConfig),
  bindings=new Map(config.bindings.map(row=>[row.url,row]));
 if(profile!==null){
  assert.ok(hex(profileSHA256),'DIRECTOR_PROFILE_BYTE_HASH_REQUIRED');
  assert.ok(profile&&typeof profile==='object'&&!Array.isArray(profile));
 }
 for(const row of bindingRecords){
  assert.ok(typeof row.url==='string'&&row.url.startsWith('/')&&!/[?#\\\0]/.test(row.url)
   &&path.isAbsolute(row.path)&&hex(row.sha256)&&Number.isSafeInteger(row.bytes)&&row.bytes>0,
   'DIRECTOR_EXACT_BROWSER_BINDING_REQUIRED');
  assert.ok(row.url.startsWith('/director-v1/')||row.url==='/production-v3/production_native_camera.mjs',
   'DIRECTOR_UNAPPROVED_SOURCE_EDGE_REPLACEMENT');
  if(row.url==='/production-v3/production_native_camera.mjs'){
   const original=bindings.get(row.url);
   assert.ok(original&&!bindings.has('/director-v1/preserved_camera.mjs'),
    'DIRECTOR_EXISTING_CAMERA_OWNER_REQUIRED');
   bindings.set('/director-v1/preserved_camera.mjs',{...original,url:'/director-v1/preserved_camera.mjs'});
  }else assert.ok(!bindings.has(row.url),'DIRECTOR_BROWSER_ALIAS_COLLISION');
  bindings.set(row.url,{...row});
 }
 config.runtimeConfig.universalVideo.scene=clone(captureWindow);
 config.runtimeConfig.universalVideo.sceneRangeSha256=sceneRangeSha256;
 config.runtimeConfig.storyDirector={schema:'WORLD_ENGINE_80S_DIRECTOR_CAPTURE_V1',
  mode:'SOFTWARE_PREVIEW',sourcePlanSHA256:inherited.planSha256,
  sourceLegacySceneSHA256:inherited.legacySceneSha256,sourceDocumentObjectSHA256:sourceDocumentHash,
  sourceSceneRanges:context.sourceSceneRanges,captureWindow:clone(captureWindow),
  captureWindowSHA256:sceneRangeSha256,originalSelectedScene:originalScene,
  profile:clone(profile),profileSHA256,browserBindings:clone(bindingRecords),
  noSourceGeometryChanged:true,noCounterfactual65422SceneUsed:true,
  singleRuntimeGlobalTime:true,productionEligible:false,nvidiaHardwareVerified:false};
 config.bindings=[...bindings.values()];
 assert.equal(hash(config.runtimeConfig.universalVideo.plan),sourceDocumentHash,
  'DIRECTOR_ORIGINAL_SOURCE_DOCUMENT_CHANGED');
 assert.equal(hash(inherited.document),sourceDocumentHash);
 return{...inherited,scene:captureWindow,sceneRangeSha256,serverConfig:config,
  storyDirector:clone(config.runtimeConfig.storyDirector),
  sourceSignature:hash({parent:inherited.sourceSignature,
   storyDirector:config.runtimeConfig.storyDirector}),
  assertSourceUnchanged:async()=>{
   await inherited.assertSourceUnchanged();
   assert.equal(hash(inherited.document),sourceDocumentHash,'DIRECTOR_SOURCE_DOCUMENT_MUTATED');
   assert.equal(hash(config.runtimeConfig.universalVideo.plan),sourceDocumentHash,
    'DIRECTOR_BROWSER_DOCUMENT_MUTATED');
   assert.equal(hash(config.runtimeConfig.universalVideo.scene),sceneRangeSha256,
    'DIRECTOR_CAPTURE_WINDOW_MUTATED');
   return true;
  }};
}

export async function loadDirectorPlan({directorProfileFile=null,cameraBridgeFile=null,
 browserBindings=[],...sourceOptions}={}){
 const inherited=await loadSoftwarePreviewPlan(sourceOptions),records=[];
 async function record(file,url=null){
  const absolute=path.resolve(file),raw=await boundedSource(absolute,16*1024*1024),
   item={path:absolute,sha256:sha(raw),bytes:raw.length};
  if(url)item.url=url;
  records.push(item);return{raw,item};
 }
 await record(path.join(HERE,'runtime_adapter.mjs'));
 let profile=null,profileSHA256=null;
 if(directorProfileFile){
  const {raw,item}=await record(directorProfileFile);
  profile=JSON.parse(raw);profileSHA256=item.sha256;
 }
 if(cameraBridgeFile)await record(cameraBridgeFile,'/production-v3/production_native_camera.mjs');
 for(const row of browserBindings){
  assert.ok(row&&typeof row.file==='string'&&typeof row.url==='string',
   'DIRECTOR_BROWSER_SOURCE_FILE_REQUIRED');
  await record(row.file,row.url);
 }
 const plan=extendDirectorCaptureWindow(inherited,{profile,profileSHA256,
  bindingRecords:records.filter(row=>row.url)}),check=plan.assertSourceUnchanged;
 plan.directorSourceRecords=clone(records);
 plan.assertSourceUnchanged=async()=>{
  await check();
  for(const row of records)assert.equal(sha(await boundedSource(row.path,16*1024*1024)),row.sha256,
   'DIRECTOR_SOURCE_CHANGED_AFTER_SELECTION');
  return true;
 };
 await plan.assertSourceUnchanged();return plan;
}

/** Software opener uses the original source-bound WebGL2 draw/readPixels path. */
export async function openDirectorRuntime(options={}){
 return openSoftwarePreviewRuntime({...options,loadPlan:loadDirectorPlan});
}

