/** Separate NVIDIA bootstrap over unchanged 65422 renderer/camera/frontier APIs. */
import {readFile,lstat} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import path from 'node:path';
export {sha,json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
import {sha,json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
export {assertQualityDiagnostic} from '../moving-frontier-glow-fix-v1/reference_runtime.mjs';
export const packageRoot=path.dirname(fileURLToPath(import.meta.url));
export const root=path.join(engine,'recovery/moving-frontier-glow-fix-v1');
export const movieName='WORLD_ENGINE_RTX_GPU_65422_5S_SILENT.mp4';
// The original fixture filename remains unchanged; this output uses a new path.
const legacyMovieName='WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4';
const inputFlags={regionalPlan:'regional-plan',continentPlan:'continent-plan',scene:'scene',cameraPlan:'camera-plan',inputManifest:'input-manifest'};
export const relativeFile=value=>{
 if(typeof value!=='string'||!value||path.isAbsolute(value)||value.split(/[\\/]/).some(part=>!part||part==='.'||part==='..'))
  throw Error('QUALITY_RUNTIME_ENGINE_RELATIVE_INPUT_REQUIRED');
 return path.join(engine,value);
};
export function assertHardwareBackend(backend,admission){
 assert.equal(admission.probe.gpu_rendering_verified,true);
 assert.equal(admission.probe.render_mode,'gpu-required');
 assert.equal(admission.probe.webgl.draw_passed,true);
 assert.ok(typeof backend==='string'&&!/swiftshader|llvmpipe|lavapipe|softpipe|software/i.test(backend)&&/\bNVIDIA\b/i.test(backend),'HARDWARE_NVIDIA_REQUIRED');
 assert.equal(backend,admission.probe.webgl.unmasked_renderer??admission.probe.webgl.renderer,'SAME_PHYSICAL_RENDERER_REQUIRED');
 return true;
}
export async function readAdmission(file){
 assert.equal(process.env.WORLD_ENGINE_RENDER_MODE,'gpu-required','GPU_REQUIRED_MODE_REQUIRED');
 assert.ok(typeof file==='string'&&path.isAbsolute(file),'PRIVATE_GPU_ADMISSION_FILE_REQUIRED');
 const attributes=await lstat(file);
 assert.ok(attributes.isFile()&&!attributes.isSymbolicLink(),'REGULAR_GPU_ADMISSION_REQUIRED');
 assert.equal(attributes.mode&0o077,0,'PRIVATE_GPU_ADMISSION_PERMISSIONS_REQUIRED');
 assert.ok(attributes.size<=256*1024,'BOUNDED_GPU_ADMISSION_REQUIRED');
 const data=JSON.parse(await readFile(file,'utf8'));
 assert.equal(data.status,'GPU_VERIFIED');assert.equal(data.testOnly,false);
 assert.equal(data.gpuRenderingVerified,true);
 const age=Date.now()-Date.parse(data.observedAt);
 assert.ok(Number.isFinite(age)&&age>=-1000&&age<=300000,'FRESH_GPU_ADMISSION_REQUIRED');
 assert.equal(data.probe.gpu_rendering_verified,true);
 assert.equal(data.probe.render_mode,'gpu-required');
 assert.equal(data.probe.gpu_profile,process.env.WORLD_ENGINE_GPU_PROFILE);
 assert.equal(data.probe.profile_fingerprint,process.env.RTX_GPU_PROBE_FINGERPRINT);
 assertHardwareBackend(data.probe.webgl.unmasked_renderer??data.probe.webgl.renderer,data);
 return data;
}
/** All runtime inputs are persisted and hashed; neither subject nor view is inferred. */
export async function openHardwareRuntime({fixtureFile=path.join(root,'fixtures/RUNTIME_FIXTURE.json'),
 scenePlanFile=path.join(root,'fixtures/SCENE_PLAN.json'),mode='STATIC_VISUAL_PROBE',
 visualAdmissionFile=path.join(root,'evidence/VISUAL_ADMISSION.json'),
 admissionFile=process.env.RTX_GPU_ADMISSION_FILE}={}){
 if(!['STATIC_VISUAL_PROBE','VISUAL_REFERENCE_STUDY'].includes(mode))throw Error('EXPLICIT_QUALITY_RUNTIME_MODE_REQUIRED');
 const fixture=await json(fixtureFile),scenePlan=await json(scenePlanFile);
 assert.equal(fixture.totalFrames,150);assert.equal(fixture.fps,30);assert.equal(fixture.videoFilename,legacyMovieName);
 assert.ok(Number.isSafeInteger(fixture.currentNativeFrame)&&fixture.currentNativeFrame>=0);
 assert.equal(scenePlan.controlIntent.total_frames,150);assert.equal(scenePlan.controlIntent.fps,30);
 assert.ok(Array.isArray(scenePlan.cameraKeyframes)&&scenePlan.cameraKeyframes.length>=2);
 assert.equal(scenePlan.schema,'MAP_ENGINE_UNIT_SCENE_V4');
 assert.equal(scenePlan.version,'MAP_ENGINE_UNIT_SCENE_V4');
 assert.ok(scenePlan.style&&scenePlan.terrainProfile&&scenePlan.presentationProfile&&scenePlan.combatProfile&&scenePlan.frontierProfile);
 // Only the existing current-front glow profile may vary, including private
 // glow-off/parent-style probes. All other scene/style/input bodies are locked.
 const savedSceneFile=path.join(engine,'recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json'),savedScene=await json(savedSceneFile);
 const sceneRelative=path.relative(root,path.resolve(scenePlanFile));
 assert.ok(sceneRelative&&!sceneRelative.startsWith('..')&&!path.isAbsolute(sceneRelative),'PRIVATE_NEW_ROOT_SCENE_REQUIRED');
 assert.deepEqual(scenePlan,{...savedScene,frontierProfile:scenePlan.frontierProfile},'ALL_SCENE_FIELDS_EXCEPT_CURRENT_FRONT_GLOW_ARE_LOCKED');
 const mutableGlowKeys=new Set(['profileName','centerColor','haloColor','centerWidthPixels','haloSigmaPixels',
  'haloSupportPixels','centerAlpha','haloAlpha','settledStrength','velocityWindowFrames']);
 const nonGlow=profile=>Object.fromEntries(Object.entries(profile).filter(([key])=>!mutableGlowKeys.has(key)));
 assert.deepEqual(nonGlow(scenePlan.frontierProfile),nonGlow(savedScene.frontierProfile),'TERRAIN_RELIEF_LIGHTING_IS_LOCKED');
 const visualAdmission=mode==='VISUAL_REFERENCE_STUDY'?await json(visualAdmissionFile):null;
 if(visualAdmission){
  assert.equal(visualAdmission.status,'VISUAL_REFERENCE_ADMITTED');
  assert.equal(visualAdmission.grade,'FACT_BASED_VISUAL_GRADE');
  assert.equal(visualAdmission.evidenceKind,'ACTUAL_NATIVE_STATIC_PROBE');
  assert.equal(visualAdmission.surveyAdmissionModified,false);
  assert.equal(visualAdmission.cameraKeyframeBinding,JSON.stringify(scenePlan.cameraKeyframes));
 }
 const admission=await readAdmission(admissionFile);
 const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
 const inputs=Object.fromEntries(Object.keys(inputFlags).map(key=>[key,relativeFile(fixture.nativeFiles?.[key])]));
 const inheritedPaths=fixture.inheritedAdmissionFiles;
 assert.ok(inheritedPaths&&typeof inheritedPaths.scenePlan==='string'&&typeof inheritedPaths.visualAdmission==='string',
  'PERSISTED_INHERITED_NATIVE_ADMISSION_INPUTS_REQUIRED');
 const inheritedSceneFile=relativeFile(inheritedPaths.scenePlan),inheritedAdmissionFile=relativeFile(inheritedPaths.visualAdmission),
  inheritedSceneBytes=await readFile(inheritedSceneFile),inheritedAdmissionBytes=await readFile(inheritedAdmissionFile),
  inheritedScene=JSON.parse(inheritedSceneBytes),inheritedAdmission=JSON.parse(inheritedAdmissionBytes),
  admittedNativeFraming={bounds:inheritedScene.cameraKeyframes.at(-1).bounds,
   visualAdmission:inheritedAdmission,sha256:sha(inheritedAdmissionBytes)};
 const modulePaths=fixture.runtimeModuleFiles;
 assert.ok(Array.isArray(modulePaths)&&modulePaths.length>=5,'PERSISTED_QUALITY_RUNTIME_MODULE_CLOSURE_REQUIRED');
 const assetPaths=fixture.runtimeAssetFiles??[];
 const sourceFiles=[fixtureFile,scenePlanFile,savedSceneFile,...Object.values(inputs),inheritedSceneFile,inheritedAdmissionFile,...modulePaths.map(relativeFile),
  ...assetPaths.map(relativeFile),fileURLToPath(import.meta.url)];
 if(visualAdmission)sourceFiles.push(visualAdmissionFile);
 const sourceBindings=[];
 for(const file of [...new Set(sourceFiles)]){
  const bytes=await readFile(file);sourceBindings.push({path:path.relative(engine,file).replaceAll(path.sep,'/'),
   sha256:sha(bytes),bytes:bytes.length});
 }
 const sourceSignature=sha(Buffer.from(JSON.stringify({mode,sourceBindings})));
 const assertSourceUnchanged=async()=>{
  for(const source of sourceBindings)if(sha(await readFile(path.join(engine,source.path)))!==source.sha256)
   throw Error('QUALITY_RUNTIME_BOUND_SOURCE_CHANGED '+source.path);
  return true;
 };
 const args=['-B',path.join(engine,'recovery/v5/serve.py')];
 for(const [key,flag] of Object.entries(inputFlags))args.push('--'+flag,fixture.nativeFiles[key]);
 const server=spawn('/usr/bin/python3',args,{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,stderr='',closed=false;
 server.stderr.on('data',value=>{stderr=(stderr+value).slice(-4096);});
 try{
  const url=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout});
   const timer=setTimeout(()=>{lines.close();reject(Error('QUALITY_NATIVE_SERVER_TIMEOUT '+stderr));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{
    const record=JSON.parse(line),address=new URL(record.url);
    if(record.event!=='READY'||address.protocol!=='http:'||address.hostname!=='127.0.0.1')
     throw Error('QUALITY_NATIVE_LOOPBACK_SERVER_REQUIRED');
    resolve(address.origin);
   }catch(error){reject(error);}});
   server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
   server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('QUALITY_NATIVE_SERVER_EXIT_'+code+' '+stderr));});
  });
  browser=await require('playwright').chromium.launch({
   executablePath:path.join(engine,'deployment/gcube/chromium_wrapper.py'),headless:true,
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox']});
  assert.equal(browser.version(),admission.probe.browser_version,'SAME_ADMITTED_BROWSER_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)
   errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
  await page.goto(url+'/runtime-config.json',{waitUntil:'load',timeout:240000});
  const info=await page.evaluate(async({scenePlan,currentNativeFrame,totalFrames,mode,admittedNativeFraming})=>{
   const load=async url=>{const result=await fetch(url);if(!result.ok)throw Error('QUALITY_INPUT_HTTP_'+result.status);return result.json();};
   const [REGIONAL,CONTINENT,scene,cameraPlan,input,runtimeConfig]=await Promise.all([
    load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),
    load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json'),load('/runtime-config.json')]);
   const {compileTerritoryControlPlan,evaluateTerritoryControlFrame}=await import('/modules/territory_control_adapter_v1.mjs');
   const {compileReferenceCameraTrack,assessReferenceCameraMotion}=await import('/modules/reference_camera_adapter_v1.mjs');
   const {createMapEngineUnitGpuAdapterV4}=await import('/modules/map_engine_unit_gpu_adapter_v4.mjs');
   const territoryPlan=compileTerritoryControlPlan(scenePlan.controlIntent),
    cameraTrack=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame,
     keyframes:scenePlan.cameraKeyframes,totalFrames,fps:territoryPlan.fps});
   const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.appendChild(canvas);
   const pipeline=await createMapEngineUnitGpuAdapterV4({canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,
    heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null,cameraTrack,territoryPlan,scenePlan,
    admittedNativeFraming});
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
    .map(value=>value.toString(16).padStart(2,'0')).join('');
   window.referenceProof={pipeline,scenePlan,territoryPlan,cameraTrack,
    async capture(frame,{png=true,territoryEnabled=true,combatEnabled=true}={}){
     const diagnostic=await pipeline.drawFrame(frame,{territoryEnabled,combatEnabled}),pixels=pipeline.readPixels();
     diagnostic.territory.controls=evaluateTerritoryControlFrame(territoryPlan,territoryPlan.startFrame+frame);
     const result={diagnostic,raw_rgba_sha256:await digest(pixels)};
     if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),
      value=>value.charCodeAt(0)));}
     return result;
    },dispose(){pipeline.dispose();}};
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info'),
    backend=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
   if(typeof backend!=='string'||/swiftshader|llvmpipe|lavapipe|softpipe|software/i.test(backend)||!/\bNVIDIA\b/i.test(backend))
    throw Error('HARDWARE_NVIDIA_RENDERER_REQUIRED');
   return {evidence:pipeline.evidence,backend,runtimeConfig,cameraMotion:assessReferenceCameraMotion(cameraTrack),
    cameraKeyframeBinding:JSON.stringify(scenePlan.cameraKeyframes),domainGeometryBinding:territoryPlan.domainGeometryBinding,
    boundaryKeyframeBinding:territoryPlan.boundaryKeyframeBinding,actualCameraLocked:false,
    surveyAdmissionModified:false,productionEligible:mode==='VISUAL_REFERENCE_STUDY',
    optionalNativeForegroundExcludedByNewScene:true,oldNativeForegroundPixelIdentityClaimed:false,
    inheritedNativeAdmissionSha256:admittedNativeFraming.sha256,inheritedNativeFramingBounds:admittedNativeFraming.bounds};
  },{scenePlan,currentNativeFrame:fixture.currentNativeFrame,totalFrames:fixture.totalFrames,mode,admittedNativeFraming});
  assertHardwareBackend(info.backend,admission);
  for(const [key,flag] of Object.entries(inputFlags)){
   const expected=sourceBindings.find(source=>path.join(engine,source.path)===inputs[key]);
   assert.equal(info.runtimeConfig.inputs[flag]?.sha256,expected.sha256,'QUALITY_SERVER_ACTUAL_INPUT_HASH_MISMATCH_'+key);
  }
  if(errors.length)throw Error(errors[0]);
  await assertSourceUnchanged();
  return {page,errors,fixture,scenePlan,info,mode,sourceBindings,sourceSignature,assertSourceUnchanged,admission,
   async close(){
    if(closed)return;closed=true;let closeError;
    try{if(!page.isClosed())await page.evaluate(()=>window.referenceProof?.dispose());}catch(error){closeError=error;}
    try{await browser.close();}catch(error){closeError??=error;}finally{server.kill();}
    await assertSourceUnchanged();if(closeError)throw closeError;
   }};
 }catch(error){await browser?.close().catch(()=>{});server.kill();throw error;}
}
