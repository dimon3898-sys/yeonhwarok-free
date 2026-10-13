// Proof tooling: existing read-only V5 server, pinned browser, new fixture data and V2 adapter.
import {readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import path from 'node:path';
export const root=path.dirname(fileURLToPath(import.meta.url)),engine=path.resolve(root,'../..'),repo=path.dirname(engine);
export const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export const json=async file=>JSON.parse(await readFile(file,'utf8'));
export async function openFlowRuntime(){
 const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 if(process.version!=='v24.19.0'||require('playwright/package.json').version!=='1.62.1')throw Error('PINNED_FLOW_NODE_PLAYWRIGHT_REQUIRED');
 const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py'),
  '--regional-plan','recovery/event-feature-bundle-v2/fixtures/REGIONAL-plan.json',
  '--continent-plan','recovery/event-feature-bundle-v2/fixtures/CONTINENT-plan.json',
  '--scene','recovery/event-feature-bundle-v2/fixtures/scene.json'],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const url=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('FLOW_SERVER_TIMEOUT')),10000);
   createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);try{resolve(JSON.parse(line).url);}catch(e){reject(e);}});
   server.once('error',reject);server.once('exit',code=>{clearTimeout(timer);reject(Error('FLOW_SERVER_EXIT_'+code));});
  });
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  if(browser.version()!=='154.0.8037.57')throw Error('PINNED_FLOW_CHROMIUM_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
  await page.route('**/*',r=>new URL(r.request().url()).origin===url?r.continue():r.abort('blockedbyclient'));
  await page.goto(url+'/runtime-config.json',{waitUntil:'load',timeout:240000});
  const flowPlan=await json(path.join(root,'fixtures/FLOW_PLAN.json')),detailPlan=await json(path.join(root,'fixtures/DETAIL_ADAPTER_PLAN.json'));
  const v2=await json(path.join(engine,'recovery/event-v1-candidate-v2/evidence/on150/REPORT.json'));
  const info=await page.evaluate(async({flowPlan,detailPlan,eventStyle,metricStyle})=>{
   const {createFlowGpuAdapter}=await import('/modules/flow_gpu_adapter_v2.mjs');
   const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('FLOW_INPUT_HTTP_'+r.status);return r.json();};
   const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),
    load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
   const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.appendChild(canvas);
   const pipeline=await createFlowGpuAdapter({canvas,plans:{REGIONAL,CONTINENT},scene,cameraPlan,
    heightSource:input.heightSource,contextTerrain:input.contextTerrain,flowPlan,detailPlan,
    approvedEventStyle:eventStyle,approvedMetricStyle:metricStyle});
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
   window.flowProof={async capture(frame,{flowEnabled=true,protect=false,png=true}={}){
    const diagnostic=pipeline.drawFrame(frame,{flowEnabled,protect}),pixels=pipeline.readPixels();
    const result={diagnostic,raw_rgba_sha256:await digest(pixels)};
    if(png){result.png=pipeline.png();result.png_sha256=await digest(Uint8Array.from(atob(result.png.split(',')[1]),c=>c.charCodeAt(0)));}
    return result;
   },dispose(){pipeline.dispose();}};
   const gl=canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info');
   const backend=gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);if(!backend.includes('SwiftShader'))throw Error('FLOW_SWIFTSHADER_REQUIRED');
   return {evidence:pipeline.evidence,backend};
  },{flowPlan,detailPlan,eventStyle:v2.frames.at(-1).eventStyle,metricStyle:v2.frames.at(-1).metricStyle});
  if(errors.length)throw Error(errors[0]);
  return {page,errors,flowPlan,detailPlan,info,async close(){await page.evaluate(()=>window.flowProof?.dispose());await browser.close();server.kill();}};
 }catch(error){await browser?.close();server.kill();throw error;}
}
