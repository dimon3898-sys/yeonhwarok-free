/** Separate actual GPU ASTRA lane; immutable original engines and admission are reused. */
import assert from 'node:assert/strict';
import {readFile,lstat,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {sha,json,repo,engine,readAdmission,assertHardwareBackend,relativeFile} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
export {sha,json,repo,engine,readAdmission,assertHardwareBackend,assertQualityDiagnostic} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
export const root=path.dirname(fileURLToPath(import.meta.url));
export {movieName} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const flags={regionalPlan:['regional-plan','regional'],continentPlan:['continent-plan','continent'],
 scene:['scene','scene'],cameraPlan:['camera-plan','camera-plan'],inputManifest:['input-manifest','input-manifest']};
const files=['astra_runtime.mjs','astra_adapter.mjs','astra_material.mjs','astra_material_core.mjs','serve_astra.py'];

async function boundBytes(file,limit=128*1024*1024){
 assert.ok(typeof file==='string'&&path.isAbsolute(file),'ASTRA_ABSOLUTE_SOURCE_REQUIRED');
 const absolute=path.resolve(file);assert.equal(file,absolute,'ASTRA_CANONICAL_SOURCE_REQUIRED');
 let cursor=path.parse(absolute).root;
 for(const part of absolute.slice(cursor.length).split(path.sep)){
  cursor=path.join(cursor,part);const entry=await lstat(cursor);
  assert.ok(!entry.isSymbolicLink(),'ASTRA_SOURCE_SYMLINK_FORBIDDEN');
 }
 const attrs=await lstat(absolute);
 assert.ok(attrs.isFile()&&attrs.size<=limit,'ASTRA_BOUNDED_REGULAR_SOURCE_REQUIRED');
 const bytes=await readFile(absolute),after=await lstat(absolute);
 assert.ok(bytes.length===attrs.size&&after.ino===attrs.ino&&after.dev===attrs.dev
  &&after.mtimeMs===attrs.mtimeMs&&after.size===attrs.size,'ASTRA_SOURCE_CHANGED_WHILE_READING');
 return bytes;
}
const safeHttpPath=value=>typeof value==='string'&&value.startsWith('/')&&!/[\\?#\x00]/.test(value)
 &&!value.split('/').some(p=>p==='.'||p==='..'||decodeURIComponent(p)!==p);

/** CPU-only planning and SHA binding. It does not start a server, browser, or GPU. */
export async function loadAstraRuntimePlan({
 activationFile=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_FILE,
 expectedActivationSha256=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_SHA256,
 mode='VISUAL_REFERENCE_STUDY'}={}){
 assert.ok(['STATIC_VISUAL_PROBE','VISUAL_REFERENCE_STUDY'].includes(mode),'ASTRA_EXPLICIT_RUNTIME_MODE_REQUIRED');
 assert.ok(hex(expectedActivationSha256),'ASTRA_ACTIVATION_SHA_REQUIRED');
 const activationBytes=await boundBytes(activationFile,2*1024*1024);
 assert.equal(sha(activationBytes),expectedActivationSha256,'ASTRA_ACTIVATION_HASH_MISMATCH');
 const profile=JSON.parse(activationBytes),activationSha256=sha(activationBytes);
 assert.equal(profile.schema,'ASTRA_GPU_ACTIVATION_PROFILE_V1');
 assert.ok(typeof profile.profileId==='string'&&/^[A-Z0-9_-]{1,80}$/.test(profile.profileId),'ASTRA_PROFILE_ID_REQUIRED');
 assert.ok(hex(profile.bundleManifestSha256),'ASTRA_BUNDLE_SHA_REQUIRED');
 assert.ok(profile.materialProfile&&typeof profile.materialProfile==='object'&&!Array.isArray(profile.materialProfile),'ASTRA_MATERIAL_PROFILE_REQUIRED');
 const fixtureFile=relativeFile(profile.fixtureFile),scenePlanFile=relativeFile(profile.scenePlanFile),
  visualAdmissionFile=relativeFile(profile.visualAdmissionFile),
  fixture=JSON.parse(await boundBytes(fixtureFile)),scenePlan=JSON.parse(await boundBytes(scenePlanFile)),
  visualAdmission=JSON.parse(await boundBytes(visualAdmissionFile));
 assert.ok(hex(profile.scenePlanByteSha256)&&hex(profile.rendererPayloadSha256),'ASTRA_SCENE_PAYLOAD_BINDING_REQUIRED');
 assert.equal(sha(await boundBytes(scenePlanFile)),profile.scenePlanByteSha256,'ASTRA_SAVED_SCENE_BYTE_HASH_MISMATCH');
 assert.equal(fixture.totalFrames,150);assert.equal(fixture.fps,30);
 assert.ok(Number.isSafeInteger(fixture.currentNativeFrame)&&fixture.currentNativeFrame>=0);
 assert.equal(scenePlan.schema,'MAP_ENGINE_UNIT_SCENE_V4');assert.equal(scenePlan.version,'MAP_ENGINE_UNIT_SCENE_V4');
 assert.equal(scenePlan.controlIntent.total_frames,fixture.totalFrames);assert.equal(scenePlan.controlIntent.fps,fixture.fps);
 assert.ok(Array.isArray(scenePlan.cameraKeyframes)&&scenePlan.cameraKeyframes.length>=2);
 assert.equal(visualAdmission.status,'VISUAL_REFERENCE_ADMITTED');assert.equal(visualAdmission.grade,'FACT_BASED_VISUAL_GRADE');
 assert.equal(visualAdmission.evidenceKind,'ACTUAL_NATIVE_STATIC_PROBE');assert.equal(visualAdmission.surveyAdmissionModified,false);
 assert.equal(visualAdmission.cameraKeyframeBinding,JSON.stringify(scenePlan.cameraKeyframes));
 const bundleFile=path.isAbsolute(profile.bundleManifestFile)?profile.bundleManifestFile:relativeFile(profile.bundleManifestFile),
  bundleRoot=path.dirname(bundleFile),bundleBytes=await boundBytes(bundleFile,2*1024*1024),
  bundle=JSON.parse(bundleBytes);
 assert.equal(sha(bundleBytes),profile.bundleManifestSha256,'ASTRA_BUNDLE_MANIFEST_HASH_MISMATCH');
 assert.equal(bundle.schema,'ASTRA_GPU_UPLOAD_BUNDLE_V1');assert.equal(bundle.enabled,true);
 assert.equal(bundle.rendererPayloadSHA256,profile.rendererPayloadSha256,'ASTRA_RENDERER_PAYLOAD_HASH_MISMATCH');
 assert.ok(Array.isArray(bundle.artifacts)&&bundle.artifacts.length>0&&bundle.artifacts.length<=256,'ASTRA_SOURCE_ARTIFACTS_REQUIRED');
 const inheritedSceneFile=relativeFile(fixture.inheritedAdmissionFiles.scenePlan),
  inheritedAdmissionFile=relativeFile(fixture.inheritedAdmissionFiles.visualAdmission),
  inheritedScene=JSON.parse(await boundBytes(inheritedSceneFile)),inheritedAdmissionBytes=await boundBytes(inheritedAdmissionFile),
  admittedNativeFraming={bounds:inheritedScene.cameraKeyframes.at(-1).bounds,
   visualAdmission:JSON.parse(inheritedAdmissionBytes),sha256:sha(inheritedAdmissionBytes)};
 const sourceBindings=[],actualFiles=new Map(),bindings=new Map();
 async function bind(file,url=null,expected=null,label=null){
  const bytes=await boundBytes(file),hash=sha(bytes);
  if(expected){assert.equal(hash,expected.sha256,'ASTRA_BOUND_SOURCE_SHA_MISMATCH');
   if(expected.bytes!==undefined)assert.equal(bytes.length,expected.bytes,'ASTRA_BOUND_SOURCE_LENGTH_MISMATCH');}
  if(!actualFiles.has(file)){
   const record={path:label??path.relative(engine,file).replaceAll(path.sep,'/'),sha256:hash,bytes:bytes.length};
   sourceBindings.push(record);actualFiles.set(file,record);
  }
  if(url){assert.ok(safeHttpPath(url),'ASTRA_EXACT_HTTP_PATH_REQUIRED');
   const record={url,path:file,sha256:hash,bytes:bytes.length},prior=bindings.get(url);
   assert.ok(!prior||JSON.stringify(prior)===JSON.stringify(record),'ASTRA_DUPLICATE_HTTP_BINDING');bindings.set(url,record);}
  return actualFiles.get(file);
 }
 await bind(activationFile,null,null,'@activation.json');
 for(const file of [fixtureFile,scenePlanFile,visualAdmissionFile,inheritedSceneFile,inheritedAdmissionFile])await bind(file);
 const inputs={};
 for(const [key,[flag,url]] of Object.entries(flags)){
  const file=relativeFile(fixture.nativeFiles[key]);inputs[flag]=await bind(file,'/inputs/'+url+'.json');
 }
 assert.ok(Array.isArray(fixture.runtimeModuleFiles)&&fixture.runtimeModuleFiles.length>=5,'ASTRA_SAVED_MODULE_CLOSURE_REQUIRED');
 for(const relative of fixture.runtimeModuleFiles){const file=relativeFile(relative);
  if(relative.startsWith('web/map_infographic_v1/'))await bind(file,'/modules/'+path.basename(file));
  else if(relative==='web/vendor/three/0.170.0/three.module.js')await bind(file,'/three.js');
  else throw Error('ASTRA_UNSUPPORTED_NATIVE_MODULE_PATH');}
 for(const relative of fixture.runtimeAssetFiles??[])await bind(relativeFile(relative));
 // Source descriptors already contain immutable licensed asset hashes. No arbitrary directory mounts.
 for(const name of ['regionalPlan','continentPlan']){
  const native=JSON.parse(await boundBytes(relativeFile(fixture.nativeFiles[name])));
  for(const asset of Object.values(native.assets??{})){
   if(!asset?.url)continue;assert.ok(safeHttpPath(asset.url)&&hex(asset.sha256),'ASTRA_NATIVE_ASSET_BINDING_REQUIRED');
   let file;
   if(asset.url.startsWith('/static/'))file=path.join(engine,'web',asset.url.slice(8));
   else if(asset.url.startsWith('/v3/assets/'))file=path.join(repo,'cinematic-world-map/assets',asset.url.slice(11));
   else throw Error('ASTRA_UNSUPPORTED_NATIVE_ASSET_MOUNT');
   await bind(file,asset.url,{sha256:asset.sha256,bytes:asset.bytes});
  }
 }
 for(const filename of files)await bind(path.join(root,filename),filename.endsWith('.mjs')?'/astra/'+filename:null);
 await bind(path.join(engine,'recovery/astra-gpu-integration-v1/gpu_upload.mjs'),'/astra-upload/gpu_upload.mjs');
 await bind(path.join(engine,'recovery/rtx-gpu-package-v1/hardware_runtime.mjs'));
 await bind(path.join(engine,'recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs'));
 await bind(bundleFile,'/astra-data/UPLOAD_MANIFEST.json',{sha256:profile.bundleManifestSha256},'@astra-data/UPLOAD_MANIFEST.json');
 let total=0;const seen=new Set();
 for(const artifact of bundle.artifacts){
  assert.ok(typeof artifact.file==='string'&&/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(artifact.file)
   &&!artifact.file.includes('..')&&!seen.has(artifact.file)&&hex(artifact.sha256)
   &&Number.isSafeInteger(artifact.bytes)&&artifact.bytes>0,'ASTRA_EXACT_ARTIFACT_REQUIRED');
  seen.add(artifact.file);total+=artifact.bytes;assert.ok(total<=128*1024*1024,'ASTRA_BUNDLE_BYTE_LIMIT');
  await bind(path.join(bundleRoot,artifact.file),'/astra-data/'+artifact.file,artifact,'@astra-data/'+artifact.file);
 }
 const astra={enabled:true,profileId:profile.profileId,activationSha256,bundleManifestSha256:profile.bundleManifestSha256,
  materialProfile:profile.materialProfile,scope:'SOURCE_SUPPORT_ONLY_WITH_UNCHANGED_BASELINE_FALLBACK'};
 const runtimeConfig={schema:'ASTRA_RUNTIME_HTTP_V1',output:[1080,1920],fps:30,inputs,astra,testOnlySoftwareProbe:false,
  bootstrap:{scenePlan,currentNativeFrame:fixture.currentNativeFrame,totalFrames:fixture.totalFrames,mode,admittedNativeFraming}};
 const sourceSignature=sha(Buffer.from(JSON.stringify({mode,sourceBindings}))),
  assertSourceUnchanged=async()=>{
   for(const [file,record] of actualFiles)assert.equal(sha(await boundBytes(file)),record.sha256,'ASTRA_RUNTIME_BOUND_SOURCE_CHANGED '+record.path);
   return true;};
 return {profile,activationSha256,bundleManifestSha256:profile.bundleManifestSha256,fixture,scenePlan,visualAdmission,
  sourceBindings,sourceSignature,assertSourceUnchanged,mode,
  serverConfig:{schema:'ASTRA_RUNTIME_SERVER_CONFIG_V1',bundleRoot,bindings:[...bindings.values()],runtimeConfig}};
}

export async function openAstraRuntime({admissionFile=process.env.RTX_GPU_ADMISSION_FILE,onPendingCleanup=null,...options}={}){
 const plan=await loadAstraRuntimePlan(options),admission=await readAdmission(admissionFile),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
 const control=await mkdtemp(path.join(tmpdir(),'world-engine-astra-http-')),
  configFile=path.join(control,'HTTP_CONFIG.json'),configBytes=Buffer.from(JSON.stringify(plan.serverConfig));
 await writeFile(configFile,configBytes,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(root,'serve_astra.py'),'--config',configFile,
  '--expected-config-sha256',sha(configBytes)],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,browserStarting,closed=false,aborted=false,stderr='';
 const cleanup=async()=>{server.kill();await(browser??await browserStarting?.catch(()=>null))?.close().catch(()=>{});await rm(control,{recursive:true,force:true});};
 onPendingCleanup?.(async()=>{aborted=true;await cleanup();});
 server.stderr.on('data',value=>{stderr=(stderr+value).slice(-4096);});
 try{
  const origin=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('ASTRA_LOOPBACK_TIMEOUT '+stderr));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{
    const record=JSON.parse(line),url=new URL(record.url);
    assert.ok(record.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1','ASTRA_LOOPBACK_REQUIRED');resolve(url.origin);
   }catch(error){reject(error);}});
   server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
   server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('ASTRA_LOOPBACK_EXIT_'+code+' '+stderr));});
  });
  if(aborted)throw Error('ASTRA_RUNTIME_ABORTED');
  browserStarting=require('playwright').chromium.launch({executablePath:path.join(engine,'deployment/gcube/chromium_wrapper.py'),
   headless:true,ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox']});
  browser=await browserStarting;if(aborted)throw Error('ASTRA_RUNTIME_ABORTED');
  assert.equal(browser.version(),admission.probe.browser_version,'SAME_ADMITTED_BROWSER_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>Object.hasOwn(window,'astraBoot'),null,{timeout:240000});
  const info=await page.evaluate(()=>window.astraBoot);
  assertHardwareBackend(info.backend,admission);
  assert.equal(info.astra.activationSha256,plan.activationSha256);assert.equal(info.astra.bundleManifestSha256,plan.bundleManifestSha256);
  assert.equal(info.astra.actualMaterialFactorySelected,true);
  assert.equal(info.testOnly,false,'ASTRA_SOFTWARE_PROBE_FORBIDDEN_IN_HARDWARE_CAPTURE');
  for(const [flag,record] of Object.entries(plan.serverConfig.runtimeConfig.inputs))
   assert.equal(info.runtimeConfig.inputs[flag]?.sha256,record.sha256,'ASTRA_ACTUAL_INPUT_HASH_MISMATCH_'+flag);
  if(errors.length)throw Error(errors[0]);await plan.assertSourceUnchanged();
  return {...plan,page,errors,info,admission,async close(){
   if(closed)return;closed=true;let failure;
   try{if(!page.isClosed())await page.evaluate(()=>window.referenceProof?.dispose());}catch(error){failure=error;}
   try{await cleanup();}catch(error){failure??=error;}
   await plan.assertSourceUnchanged();if(failure)throw failure;
  }};
 }catch(error){await cleanup();throw error;}
}
