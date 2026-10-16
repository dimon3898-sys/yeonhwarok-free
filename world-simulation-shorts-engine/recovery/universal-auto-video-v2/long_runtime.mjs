/** Variable-duration range runtime over frozen native/Area/ASTRA factories.
 * The inherited five-second scene is NEVER booted or time-warped. It supplies
 * the source/data closure only; a verified Scene JSON supplies every event. */
import assert from 'node:assert/strict';
import {readFile,lstat,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadReferenceRuntimePlan,readAdmission,assertHardwareBackend,engine,repo,sha} from '../reference-visual-master-v2/ref2_runtime.mjs';
export {engine,repo,sha};
export const root=path.dirname(fileURLToPath(import.meta.url));
const execute=promisify(execFile),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const flags={regionalPlan:['regional-plan','regional'],continentPlan:['continent-plan','continent'],
 scene:['scene','scene'],cameraPlan:['camera-plan','camera-plan'],inputManifest:['input-manifest','input-manifest']};
export async function boundedSource(file,limit=16*1024*1024){
 assert.ok(typeof file==='string'&&path.isAbsolute(file)&&path.resolve(file)===file,'LONG_CANONICAL_SOURCE_REQUIRED');
 let current=path.parse(file).root;
 for(const part of file.slice(current.length).split(path.sep)){
  current=path.join(current,part);assert.ok(!(await lstat(current)).isSymbolicLink(),'LONG_SOURCE_SYMLINK_FORBIDDEN');
 }
 const before=await lstat(file);assert.ok(before.isFile()&&before.size<=limit,'LONG_BOUNDED_REGULAR_SOURCE_REQUIRED');
 const raw=await readFile(file),after=await lstat(file);
 assert.ok(raw.length===before.size&&after.ino===before.ino&&after.dev===before.dev&&after.mtimeMs===before.mtimeMs
  &&after.size===before.size,'LONG_SOURCE_CHANGED_WHILE_READING');return raw;
}
export function engineRelative(value){
 assert.ok(typeof value==='string'&&value&&!path.isAbsolute(value)&&!/[\\\x00]/.test(value)
  &&value.split('/').every(p=>p&&p!=='.'&&p!=='..'),'LONG_ENGINE_RELATIVE_SOURCE_REQUIRED');
 return path.join(engine,value);
}
export function validateLongRuntimeDocument(document,sceneId){
 assert.equal(document?.schema,'WORLD_ENGINE_UNIVERSAL_VIDEO_V2');
 assert.ok(Number.isSafeInteger(document.totalFrames)&&document.totalFrames>0&&Number.isSafeInteger(document.fps)&&document.fps>0);
 assert.ok(Number.isFinite(document.durationSeconds)&&Math.abs(document.durationSeconds*document.fps-document.totalFrames)<1e-9,'LONG_DURATION_BINDING_REQUIRED');
 assert.deepEqual(document.resolution,{width:1080,height:1920});assert.equal(document.aspectRatio,'9:16');
 assert.ok(Array.isArray(document.scenes)&&document.scenes.length>0,'LONG_SCENES_REQUIRED');
 let next=0;for(const scene of document.scenes){
  assert.equal(scene.startFrame,next,'LONG_CONTIGUOUS_HALF_OPEN_SCENES_REQUIRED');
  assert.ok(Number.isSafeInteger(scene.endFrame)&&scene.endFrame>next&&scene.endFrame<=document.totalFrames);
  next=scene.endFrame;
 }assert.equal(next,document.totalFrames,'LONG_COMPLETE_FRAME_COVERAGE_REQUIRED');
 const selected=document.scenes.filter(scene=>scene.sceneId===sceneId);assert.equal(selected.length,1,'LONG_UNIQUE_SCENE_REQUIRED');
 const scene=selected[0],profile=scene.renderProfile;
 assert.equal(profile?.gpuMode,'gpu-required');assert.equal(profile?.adapter,'UNIVERSAL_AREA_ASTRA_V2');
 assert.equal(profile?.status,'READY','LONG_NATIVE_PAYLOAD_REQUIRED');
 assert.equal(profile.nativePayload?.validationStatus,'VERIFIED');assert.ok(hex(profile.nativePayload?.sha256));
 assert.equal(document.legacyScenePlan?.timing?.total_frames,document.totalFrames);
 assert.equal(document.legacyScenePlan?.timing?.fps,document.fps);
 assert.equal(document.legacyScenePlan?.event_type,'WAR','LONG_SUPPORTED_AREA_POLYGON_TIMELINE_REQUIRED');
 assert.ok(Array.isArray(document.sourceManifest?.records)&&document.sourceManifest.records.length>0,'LONG_VERIFIED_SOURCES_REQUIRED');
 for(const source of document.sourceManifest.records)assert.equal(source.verification_status,'VERIFIED','LONG_UNVERIFIED_FACT_SOURCE');
 assert.equal(document.sourceManifest.semanticPolicy?.inventMissingHistory,false);
 assert.equal(document.audioSettings?.enabled,false,'LONG_CURRENT_ENCODER_SILENT_ONLY');
 return scene;
}
export function validateNativePayload(payload){
 assert.equal(payload?.schema,'WORLD_ENGINE_UNIVERSAL_NATIVE_INPUT_V1');
 assert.equal(payload.sourcePolicy,'EXISTING_VERIFIED_NATIVE_INPUTS');
 assert.ok(Number.isSafeInteger(payload.cameraStartFrame)&&payload.cameraStartFrame>=0,'LONG_NATIVE_CAMERA_OFFSET_REQUIRED');
 assert.ok(payload.nativeFiles&&Object.keys(payload.nativeFiles).length===Object.keys(flags).length,'LONG_FIVE_NATIVE_INPUTS_REQUIRED');
 for(const key of Object.keys(flags)){
  const row=payload.nativeFiles[key];assert.ok(row&&hex(row.sha256),'LONG_NATIVE_INPUT_SHA_REQUIRED_'+key);engineRelative(row.path);
 }return payload;
}
async function validatePythonPlan(file){
 const code="import json,sys;sys.path.insert(0,sys.argv[1]);from contracts import validate_plan;validate_plan(json.load(open(sys.argv[2])),require_renderable=True);print('LONG_PLAN_VALID')";
 const result=await execute('/usr/bin/python3',['-B','-c',code,root,file],{maxBuffer:1024*1024});
 assert.equal(result.stdout.trim(),'LONG_PLAN_VALID','LONG_SCENE_CONTRACT_REJECTED');
}
/** Data preparation only. No Chromium, GPU context or source draw is created. */
export async function loadLongRuntimePlan({planFile,expectedPlanSha256,sceneId,
 activationFile=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_FILE,
 expectedActivationSha256=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_SHA256}={}){
 assert.ok(hex(expectedPlanSha256),'LONG_PLAN_SHA_REQUIRED');
 const raw=await boundedSource(planFile),planSha256=sha(raw);assert.equal(planSha256,expectedPlanSha256,'LONG_PLAN_SHA_MISMATCH');
 const document=JSON.parse(raw),scene=validateLongRuntimeDocument(document,sceneId);await validatePythonPlan(planFile);
 const payloadRef=scene.renderProfile.nativePayload,payloadFile=path.isAbsolute(payloadRef.path)?payloadRef.path:engineRelative(payloadRef.path),
  payloadBytes=await boundedSource(payloadFile),nativePayloadSha256=sha(payloadBytes);
 assert.equal(nativePayloadSha256,payloadRef.sha256,'LONG_NATIVE_PAYLOAD_SHA_MISMATCH');
 const payload=validateNativePayload(JSON.parse(payloadBytes));
 // The old F plan is verified for immutable asset closure and supported ASTRA
 // uploads, not rendered. None of its fictional control/camera/unit scene is
 // included in this runtime's bootstrap below.
 const inherited=await loadReferenceRuntimePlan({activationFile,expectedActivationSha256}),
  config=structuredClone(inherited.serverConfig),records=[],bindings=new Map(config.bindings.map(row=>[row.url,row])),
  sourceBindings=[...inherited.sourceBindings],nativeInputs={};
 const bind=async(file,url=null,expected=null)=>{
  const bytes=await boundedSource(file,128*1024*1024),hash=sha(bytes);
  if(expected!==null)assert.equal(hash,expected,'LONG_NATIVE_SOURCE_SHA_MISMATCH');
  const record={path:path.relative(engine,file).replaceAll(path.sep,'/'),bytes:bytes.length,sha256:hash};
  records.push({file,...record});sourceBindings.push(record);
  if(url)bindings.set(url,{url,path:file,bytes:bytes.length,sha256:hash});return record;
 };
 await bind(planFile,null,planSha256);await bind(payloadFile,null,nativePayloadSha256);
 const native={};
 for(const [key,[flag,url]]of Object.entries(flags)){
  const file=engineRelative(payload.nativeFiles[key].path),record=await bind(file,'/inputs/'+url+'.json',payload.nativeFiles[key].sha256);
  nativeInputs[flag]=record;native[key]=JSON.parse(await boundedSource(file));
 }
 assert.equal(native.scene.primary_region_id,native.regionalPlan.primary,'LONG_NATIVE_REGION_BINDING_REQUIRED');
 assert.deepEqual(native.scene.event_anchor,document.legacyScenePlan.camera_intent.anchor,'LONG_ACTUAL_EVENT_ANCHOR_BINDING_REQUIRED');
 assert.equal(native.scene.primary_region_id,document.legacyScenePlan.camera_intent.native_context?.primary_country_id,'LONG_ACTUAL_COUNTRY_BINDING_REQUIRED');
 assert.equal(native.cameraPlan.directorVersion,'CAMERA_DIRECTOR_V5');assert.equal(native.cameraPlan.fps,document.fps);
 assert.deepEqual(native.cameraPlan.intent.finalExtent,native.regionalPlan.framing.bounds,'LONG_ACTUAL_V5_REGIONAL_EXTENT_REQUIRED');
 for(const plan of [native.regionalPlan,native.continentPlan])for(const asset of Object.values(plan.assets??{})){
  if(!asset?.url)continue;assert.ok(typeof asset.url==='string'&&!/[?#%\\\x00]/.test(asset.url)&&!asset.url.split('/').some(part=>part==='.'||part==='..')&&hex(asset.sha256),'LONG_NATIVE_ASSET_BINDING_REQUIRED');
  let file;
  if(asset.url.startsWith('/static/'))file=path.join(engine,'web',asset.url.slice(8));
  else if(asset.url.startsWith('/v3/assets/'))file=path.join(repo,'cinematic-world-map/assets',asset.url.slice(11));
  else throw Error('LONG_NATIVE_ASSET_MOUNT_UNSUPPORTED');
  await bind(file,asset.url,asset.sha256);
 }
 for(const name of ['long_runtime.mjs','long_capture.mjs','long_adapter.mjs','native_boundary_restore.mjs','planner_geometry_serialization.mjs','long_area_timeline.mjs','serve_long.py'])
  await bind(path.join(root,name),name.endsWith('.mjs')?'/universal/'+name:null);
 const legacySceneSha256=sha(Buffer.from(JSON.stringify(document.legacyScenePlan))),
  sceneRangeSha256=sha(Buffer.from(JSON.stringify(scene))),
  universalVideo={schema:'WORLD_ENGINE_UNIVERSAL_RUNTIME_V2',plan:document,scene,planSha256,legacySceneSha256,
   sceneRangeSha256,nativePayloadSha256,cameraStartFrame:payload.cameraStartFrame,totalFrames:document.totalFrames,
   fps:document.fps,frameConvention:'GLOBAL_HALF_OPEN',testOnly:false,gpuVisualQualityVerified:false};
 config.runtimeConfig.universalVideo=universalVideo;config.runtimeConfig.inputs=nativeInputs;
 config.runtimeConfig.output=[1080,1920];config.runtimeConfig.fps=document.fps;
 config.runtimeConfig.bootstrap={mode:'UNIVERSAL_AREA_ASTRA_V2',totalFrames:document.totalFrames,cameraStartFrame:payload.cameraStartFrame};
 config.runtimeConfig.referenceV2.source={...config.runtimeConfig.referenceV2.source,registerDomainCoverage:false};
 config.bindings=[...bindings.values()];
 const sourceSignature=sha(Buffer.from(JSON.stringify({parent:inherited.sourceSignature,planSha256,nativePayloadSha256,sceneRangeSha256,sourceBindings}))),
  assertSourceUnchanged=async()=>{await inherited.assertSourceUnchanged();
   for(const record of records)assert.equal(sha(await boundedSource(record.file,128*1024*1024)),record.sha256,'LONG_BOUND_SOURCE_CHANGED');return true;};
 return {document,scene,payload,planSha256,legacySceneSha256,sceneRangeSha256,nativePayloadSha256,
  sourceBindings,sourceSignature,assertSourceUnchanged,serverConfig:config,inherited,engine,repo,root};
}
/** Actual production hardware only. Software probes must use their separately
 * marked harness, never this function or a manufactured admission. */
export async function openLongRuntime({admissionFile=process.env.RTX_GPU_ADMISSION_FILE,loadedPlan=null,onPendingCleanup,...options}={}){
 const verification=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(root,'universal_files.py'),'--verify-extension'],{maxBuffer:1024*1024})).stdout);
 assert.equal(verification.status,'PASS','LONG_PACKAGED_SOURCE_CONTRACT_REQUIRED');
 const plan=loadedPlan??await loadLongRuntimePlan(options),admission=await readAdmission(admissionFile),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
 const temporary=await mkdtemp(path.join(tmpdir(),'world-engine-long-http-')),file=path.join(temporary,'CONFIG.json'),raw=Buffer.from(JSON.stringify(plan.serverConfig));
 await writeFile(file,raw,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(root,'serve_long.py'),'--config',file,'--expected-config-sha256',sha(raw)],
  {cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,browserStarting,aborted=false,closed=false,stderr='';
 const cleanup=async()=>{server.kill();await(browser??await browserStarting?.catch(()=>null))?.close().catch(()=>{});await rm(temporary,{recursive:true,force:true});};
 onPendingCleanup?.(async()=>{aborted=true;await cleanup();});server.stderr.on('data',bytes=>{stderr=(stderr+bytes).slice(-2048);});
 try{
  const origin=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('LONG_LOOPBACK_TIMEOUT'));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{const record=JSON.parse(line),url=new URL(record.url);
    assert.ok(record.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1','LONG_LOOPBACK_ONLY');resolve(url.origin);
   }catch(error){reject(error);}});
   for(const event of ['error','exit'])server.once(event,()=>{clearTimeout(timer);lines.close();reject(Error('LONG_LOOPBACK_SERVER_FAILED'));});
  });
  if(aborted)throw Error('LONG_RUNTIME_ABORTED');
  browserStarting=require('playwright').chromium.launch({executablePath:path.join(engine,'deployment/gcube/chromium_wrapper.py'),headless:true,
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox']});
  browser=await browserStarting;if(aborted)throw Error('LONG_RUNTIME_ABORTED');
  assert.equal(browser.version(),admission.probe.browser_version,'SAME_ADMITTED_BROWSER_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{
   if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>Object.hasOwn(window,'longVideoBoot'),null,{timeout:240000});
  const info=await page.evaluate(()=>window.longVideoBoot);assertHardwareBackend(info.backend,admission);
  assert.equal(info.testOnly,false);assert.equal(info.universalVideo?.testOnly,false);
  for(const key of ['planSha256','legacySceneSha256','sceneRangeSha256'])assert.equal(info.universalVideo[key],plan[key],'LONG_ACTUAL_RUNTIME_BINDING_'+key);
  if(errors.length)throw Error('LONG_BROWSER_INITIALIZATION_FAILED');await plan.assertSourceUnchanged();
  return {...plan,page,errors,info,admission,async close(){if(closed)return;closed=true;let failure;
   try{if(!page.isClosed())await page.evaluate(()=>window.longVideoProof?.dispose());}catch(error){failure=error;}
   try{await cleanup();await plan.assertSourceUnchanged();}catch(error){failure??=error;}if(failure)throw failure;}};
 }catch(error){await cleanup();throw error;}
}
