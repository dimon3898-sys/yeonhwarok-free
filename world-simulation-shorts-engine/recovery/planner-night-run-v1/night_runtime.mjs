/** Pinned native session. All geographic rendering belongs to the existing factory. */
import {readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
export {sha,json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
import {json,repo,engine} from '../planner-scene-json-v1/planner_runtime.mjs';
export const root=path.dirname(fileURLToPath(import.meta.url));

export async function openNightRuntime({selectionOnly=false}={}){
 const old=await json(path.join(engine,'recovery/planner-scene-json-v1/fixtures/RUNTIME_FIXTURE.json'));
 const fixture=selectionOnly?old:await json(path.join(root,'fixtures/RUNTIME_FIXTURE.json'));
 const scenePlan=selectionOnly?null:await json(path.join(root,'fixtures/SCENE_PLAN.json'));
 const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 if(process.version!=='v24.19.0'||require('playwright/package.json').version!=='1.62.1')throw Error('PINNED_NIGHT_RUNTIME_REQUIRED');
 const flags={regionalPlan:'regional-plan',continentPlan:'continent-plan',scene:'scene',cameraPlan:'camera-plan',inputManifest:'input-manifest'};
 const args=['-B',path.join(engine,'recovery/v5/serve.py')];
 for(const [key,flag] of Object.entries(flags))args.push('--'+flag,fixture.nativeFiles[key]);
 const server=spawn('/usr/bin/python3',args,{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,stderr='';server.stderr.on('data',value=>{stderr=(stderr+value).slice(-4096);});
 try{
  const url=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('NIGHT_NATIVE_SERVER_TIMEOUT '+stderr)),10000);
   createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);try{resolve(JSON.parse(line).url);}catch(error){reject(error);}});
   server.once('error',reject);server.once('exit',code=>{clearTimeout(timer);reject(Error('NIGHT_NATIVE_SERVER_EXIT_'+code));});
  });
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  if(browser.version()!=='154.0.8037.57')throw Error('PINNED_NIGHT_CHROMIUM_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{
   if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);
  });
  await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
  await page.goto(url+'/runtime-config.json',{waitUntil:'load',timeout:240000});
  const info=await page.evaluate(async({selectionOnly,scenePlan,presentation,selectionCameraFrame})=>{
   const load=async url=>{const result=await fetch(url);if(!result.ok)throw Error('NIGHT_INPUT_HTTP_'+result.status);return result.json();};
   const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),
    load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
   const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.appendChild(canvas);
   const settings={canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,heightSource:input.heightSource??null,contextTerrain:input.contextTerrain??null};
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
   if(selectionOnly){
    const {createAreaNativeBridge}=await import('/modules/area_native_bridge_v3.mjs');
    const native=await createAreaNativeBridge(settings),frame=native.drawNative(selectionCameraFrame);
    if(frame.cameraLocked!==true||frame.settle?.locked!==true)throw Error('NIGHT_SELECTION_ACTUAL_CAMERA_LOCK_REQUIRED');
    window.nightSelection={native,frame,plans:{REGIONAL,CONTINENT},safeArea:REGIONAL.layout.safe,canvas,
     dispose(){native.dispose();}};
    return {native:native.evidence,cameraBounds:frame.camera.flatBounds,locked:true};
   }
   const {compileCausalEnginePlan,evaluateCausalSchedule}=await import('/modules/planner_causal_adapter_v1.mjs');
   const {createPlannerCausalGpuAdapter}=await import('/modules/planner_causal_gpu_adapter_v1.mjs');
   const causalPlan=compileCausalEnginePlan(scenePlan);
   const pipeline=await createPlannerCausalGpuAdapter({...settings,causalPlan,presentation});
   window.nightProof={pipeline,scenePlan,causalPlan,async capture(frame,{protect=true,png=true,flowEnabled=true,areaEnabled=true}={}){
    const diagnostic=pipeline.drawFrame(frame,{protect,flowEnabled,areaEnabled}),pixels=pipeline.readPixels();
    diagnostic.causalSchedule=evaluateCausalSchedule(causalPlan,frame);
    const result={diagnostic,raw_rgba_sha256:await digest(pixels)};
    if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),value=>value.charCodeAt(0)));}
    return result;
   },dispose(){pipeline.dispose();}};
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info');
   const backend=gl.getParameter(debug.UNMASKED_RENDERER_WEBGL);if(!backend.includes('SwiftShader'))throw Error('NIGHT_SWIFTSHADER_REQUIRED');
   return {evidence:pipeline.evidence,backend,geometryBinding:causalPlan.sourceGeometryBinding};
  },{selectionOnly,scenePlan,presentation:fixture.presentation,
   selectionCameraFrame:old.presentation.cameraStartFrame+old.presentation.eventStartFrame});
  if(errors.length)throw Error(errors[0]);
  return {page,errors,fixture,scenePlan,info,async close(){
   await page.evaluate(()=>{window.nightProof?.dispose();window.nightSelection?.dispose();});await browser.close();server.kill();
  }};
 }catch(error){await browser?.close();server.kill();throw error;}
}
