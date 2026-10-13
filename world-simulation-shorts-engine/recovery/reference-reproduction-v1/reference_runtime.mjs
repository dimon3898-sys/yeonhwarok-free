/** Pinned loopback runtime for a data-owned reference study above unchanged FINAL APIs. */
import {readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
export {sha,json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
import {sha,json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
export const root=path.dirname(fileURLToPath(import.meta.url));

const modes=new Set(['STATIC_VISUAL_PROBE','VISUAL_REFERENCE_STUDY']);
const inputFlags={regionalPlan:'regional-plan',continentPlan:'continent-plan',scene:'scene',
 cameraPlan:'camera-plan',inputManifest:'input-manifest'};
const relativeFile=value=>{
 if(typeof value!=='string'||!value||path.isAbsolute(value)||value.split(/[\\/]/).some(part=>!part||part==='.'||part==='..'))
  throw Error('REFERENCE_RUNTIME_ENGINE_RELATIVE_INPUT_REQUIRED');
 return path.join(engine,value);
};

/** No fixture defaults infer a subject, framing, camera readiness, or admission. */
export async function openReferenceRuntime({fixtureFile=path.join(root,'fixtures/RUNTIME_FIXTURE.json'),
 scenePlanFile=path.join(root,'fixtures/SCENE_PLAN.json'),mode='STATIC_VISUAL_PROBE',visualAdmission=null,
 visualAdmissionFile=path.join(root,'evidence/VISUAL_ADMISSION.json')}={}){
 if(!modes.has(mode))throw Error('REFERENCE_RUNTIME_EXPLICIT_MODE_REQUIRED');
 const fixture=await json(fixtureFile),scenePlan=await json(scenePlanFile);
 if(!Number.isSafeInteger(fixture.currentNativeFrame)||fixture.currentNativeFrame<0
  ||!Number.isSafeInteger(fixture.totalFrames)||fixture.totalFrames<2
  ||!scenePlan.controlIntent||!Array.isArray(scenePlan.cameraKeyframes)||!scenePlan.style)
  throw Error('REFERENCE_RUNTIME_PERSISTED_CAMERA_CONTROL_STYLE_REQUIRED');
 if(scenePlan.controlIntent.total_frames!==fixture.totalFrames)
  throw Error('REFERENCE_RUNTIME_CAMERA_CONTROL_DURATION_BINDING_REQUIRED');
 const admissionLoadedFromFile=mode==='VISUAL_REFERENCE_STUDY'&&visualAdmission===null;
 if(admissionLoadedFromFile)visualAdmission=await json(visualAdmissionFile);
 const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 if(process.version!=='v24.19.0'||require('playwright/package.json').version!=='1.62.1')
  throw Error('PINNED_REFERENCE_NODE_PLAYWRIGHT_REQUIRED');
 const inputs={};
 for(const key of Object.keys(inputFlags))inputs[key]=relativeFile(fixture.nativeFiles?.[key]);
 const sourceFiles=[fixtureFile,scenePlanFile,...Object.values(inputs),
  path.join(engine,'web/map_infographic_v1/reference_camera_adapter_v1.mjs'),
  path.join(engine,'web/map_infographic_v1/territory_control_adapter_v1.mjs'),
  path.join(engine,'web/map_infographic_v1/territory_control_gpu_adapter_v1.mjs'),fileURLToPath(import.meta.url)];
 if(admissionLoadedFromFile)sourceFiles.push(visualAdmissionFile);
 const sourceBindings=[];
 for(const file of sourceFiles){const bytes=await readFile(file);sourceBindings.push({path:path.relative(engine,file).replaceAll(path.sep,'/'),
  sha256:sha(bytes),bytes:bytes.length});}
 const sourceSignature=sha(Buffer.from(JSON.stringify({mode,sourceBindings,visualAdmission})));
 const assertSourceUnchanged=async()=>{
  for(const source of sourceBindings)if(sha(await readFile(path.join(engine,source.path)))!==source.sha256)
   throw Error('REFERENCE_RUNTIME_BOUND_SOURCE_CHANGED '+source.path);
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
   const timer=setTimeout(()=>{lines.close();reject(Error('REFERENCE_NATIVE_SERVER_TIMEOUT '+stderr));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{
    const record=JSON.parse(line),address=new URL(record.url);
    if(record.event!=='READY'||address.protocol!=='http:'||address.hostname!=='127.0.0.1')
     throw Error('REFERENCE_NATIVE_LOOPBACK_SERVER_REQUIRED');
    resolve(address.origin);
   }catch(error){reject(error);}});
   server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
   server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('REFERENCE_NATIVE_SERVER_EXIT_'+code+' '+stderr));});
  });
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  if(browser.version()!=='154.0.8037.57')throw Error('PINNED_REFERENCE_CHROMIUM_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)
   errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
  await page.goto(url+'/runtime-config.json',{waitUntil:'load',timeout:240000});
  const info=await page.evaluate(async({scenePlan,currentNativeFrame,totalFrames,mode,visualAdmission})=>{
   const load=async url=>{const result=await fetch(url);if(!result.ok)throw Error('REFERENCE_INPUT_HTTP_'+result.status);return result.json();};
   const [REGIONAL,CONTINENT,scene,cameraPlan,input,runtimeConfig]=await Promise.all([
    load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),
    load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json'),load('/runtime-config.json')]);
   const {compileTerritoryControlPlan,evaluateTerritoryControlFrame}=await import('/modules/territory_control_adapter_v1.mjs');
   const {compileReferenceCameraTrack,assessReferenceCameraMotion}=await import('/modules/reference_camera_adapter_v1.mjs');
   const {createTerritoryControlGpuAdapter}=await import('/modules/territory_control_gpu_adapter_v1.mjs');
   const territoryPlan=compileTerritoryControlPlan(scenePlan.controlIntent),
    cameraTrack=compileReferenceCameraTrack({baseCameraPlan:cameraPlan,currentNativeFrame,
     keyframes:scenePlan.cameraKeyframes,totalFrames,fps:territoryPlan.fps});
   const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.appendChild(canvas);
   const pipeline=await createTerritoryControlGpuAdapter({canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,
    heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null,cameraTrack,territoryPlan,
    style:scenePlan.style,mode,visualAdmission});
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
    .map(value=>value.toString(16).padStart(2,'0')).join('');
   window.referenceProof={pipeline,scenePlan,territoryPlan,cameraTrack,
    async capture(frame,{protect=true,png=true,territoryEnabled=true}={}){
     const diagnostic=pipeline.drawFrame(frame,{protect,territoryEnabled}),pixels=pipeline.readPixels();
     diagnostic.territory.controls=evaluateTerritoryControlFrame(territoryPlan,territoryPlan.startFrame+frame);
     const result={diagnostic,raw_rgba_sha256:await digest(pixels)};
     if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),
      value=>value.charCodeAt(0)));}
     return result;
    },dispose(){pipeline.dispose();}};
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info'),
    backend=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
   if(typeof backend!=='string'||!backend.includes('SwiftShader'))throw Error('REFERENCE_SWIFTSHADER_REQUIRED');
   return {evidence:pipeline.evidence,backend,runtimeConfig,cameraMotion:assessReferenceCameraMotion(cameraTrack),
    cameraKeyframeBinding:JSON.stringify(cameraTrack.keyframes),domainGeometryBinding:territoryPlan.domainGeometryBinding,
    boundaryKeyframeBinding:territoryPlan.boundaryKeyframeBinding,actualCameraLocked:false,
    surveyAdmissionModified:false,productionEligible:mode==='VISUAL_REFERENCE_STUDY'};
  },{scenePlan,currentNativeFrame:fixture.currentNativeFrame,totalFrames:fixture.totalFrames,mode,visualAdmission});
  for(const [key,flag] of Object.entries(inputFlags)){
   const expected=sourceBindings.find(source=>path.join(engine,source.path)===inputs[key]);
   if(info.runtimeConfig.inputs[flag]?.sha256!==expected.sha256)throw Error('REFERENCE_SERVER_ACTUAL_INPUT_HASH_MISMATCH_'+key);
  }
  if(errors.length)throw Error(errors[0]);
  await assertSourceUnchanged();
  return {page,errors,fixture,scenePlan,info,mode,sourceBindings,sourceSignature,assertSourceUnchanged,
   async close(){
    if(closed)return;closed=true;
    let closeError;
    try{if(!page.isClosed())await page.evaluate(()=>window.referenceProof?.dispose());}catch(error){closeError=error;}
    try{await browser.close();}catch(error){closeError??=error;}finally{server.kill();}
    await assertSourceUnchanged();
    if(closeError)throw closeError;
   }};
 }catch(error){await browser?.close().catch(()=>{});server.kill();throw error;}
}
