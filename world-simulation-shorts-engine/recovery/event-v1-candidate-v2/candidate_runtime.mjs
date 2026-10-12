// Review Candidate tooling only. It calls the saved Camera and Event public APIs.
import {createHash} from 'node:crypto';
import {readFile,realpath,lstat,writeFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const runtime=path.dirname(fileURLToPath(import.meta.url));
export const engine=path.resolve(runtime,'../..'),repo=path.dirname(engine);
export const WIDTH=1080,HEIGHT=1920,FPS=30,CAMERA_FRAME=249;
export const V1_CANDIDATE_COMMIT='1d5182f7effde2e776f9c9ac21b00f6d681a423a';
export const V1_ON_REPORT='world-simulation-shorts-engine/recovery/event-v1-candidate/evidence/on150-r2/REPORT.json';
export const productionFixture='world-simulation-shorts-engine/recovery/event-data/suez-full-canal-20261012/fixture.json';
export const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export const json=async file=>JSON.parse(await readFile(file,'utf8'));
export async function record(relative){
 const full=path.resolve(repo,relative),within=path.relative(repo,full);
 if(within.startsWith('..')||path.isAbsolute(within)||within.split(path.sep).includes('node_modules')||
  await realpath(full)!==full||!(await lstat(full)).isFile())throw Error('REGULAR_REPOSITORY_INPUT_REQUIRED: '+relative);
 const bytes=await readFile(full);return {path:within.split(path.sep).join('/'),sha256:sha(bytes),bytes:bytes.length};
}
export async function inventory(){
 const v5='world-simulation-shorts-engine/recovery/v5/manifests/final',rows=new Map();
 for(const name of ['SOURCE_MANIFEST','RUNTIME_ASSET_MANIFEST','BUILD_INPUT_MANIFEST','DEPENDENCY_MANIFEST']){
  const manifest=await json(path.join(repo,v5,name+'.json'));
  rows.set(v5+'/'+name+'.json',await record(v5+'/'+name+'.json'));
  for(const field of ['entries','source_files','final_verification_files','plan_inputs','verification_inputs','dependency_locks','verification_only_inputs'])for(const expected of manifest[field]??[]){
   const actual=await record(expected.path);
   if(actual.sha256!==expected.sha256||actual.bytes!==expected.bytes)throw Error('PROTECTED_V5_INPUT_CHANGED: '+expected.path);
   rows.set(expected.path,actual);
  }
 }
 for(const relative of [productionFixture,
  'world-simulation-shorts-engine/recovery/v5/evidence/runtime-diagnostic.json',
  'world-simulation-shorts-engine/recovery/v5/evidence/final/clean-video/runtime-diagnostic.json'])rows.set(relative,await record(relative));
 const {readdir}=await import('node:fs/promises');
 for(const filename of await readdir(path.join(engine,'web/map_infographic_v1'))){
  if(/^event_.*_v1\.mjs$/.test(filename)){
   const relative='world-simulation-shorts-engine/web/map_infographic_v1/'+filename;rows.set(relative,await record(relative));
  }
 }
 for(const filename of await readdir(runtime)){
  if(!/\.(?:mjs|py)$/.test(filename))continue;
  const relative='world-simulation-shorts-engine/recovery/event-v1-candidate-v2/'+filename;rows.set(relative,await record(relative));
 }
 rows.set(V1_ON_REPORT,await record(V1_ON_REPORT));
 return [...rows.values()].sort((a,b)=>a.path.localeCompare(b.path));
}
export async function openRuntime({fixture,includeV5=false}={}){
 const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 if(process.version!=='v24.19.0'||require('playwright/package.json').version!=='1.62.1')throw Error('PINNED_NODE_PLAYWRIGHT_REQUIRED');
 const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,serverError='';server.stderr.on('data',value=>{serverError=(serverError+value).slice(-4096);});
 try{
  const url=await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>reject(Error('SERVER_START_TIMEOUT')),10000);
   createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timeout);try{resolve(JSON.parse(line).url);}catch(error){reject(error);}});
   server.once('error',reject);server.once('exit',code=>{clearTimeout(timeout);reject(Error('SERVER_EXIT_'+code));});
  });
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  if(browser.version()!=='154.0.8037.57')throw Error('PINNED_CHROMIUM_REQUIRED');
  const page=await browser.newPage({viewport:{width:WIDTH,height:HEIGHT},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
  await page.goto(url+'/runtime-config.json',{waitUntil:'load',timeout:240000});
  const info=await page.evaluate(async({fixture,includeV5})=>{
   const {createEventGpuPipeline}=await import('/modules/event_gpu_pipeline_v1.mjs');
   const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
   const {compileEventPlan}=await import('/modules/event_timeline_v1.mjs');
   const load=async pathname=>{const r=await fetch(pathname);if(!r.ok)throw Error('INPUT_HTTP_'+r.status);return r.json();};
   const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
    load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
   const original=JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input,fixture});
   const eventPlan=compileEventPlan(compileEventIntent(fixture.intent),fixture.timeline);
   const common={plans:{REGIONAL,CONTINENT},scene,cameraPlan,heightSource:input.heightSource,contextTerrain:input.contextTerrain,width:1080,height:1920};
   const canvas=document.createElement('canvas');document.body.appendChild(canvas);
   const event=await createEventGpuPipeline({...common,canvas,eventPlan});
   let v5=null;
   if(includeV5){
    const {createV5CameraGpuPipeline}=await import('/modules/camera_gpu_pipeline_v5.mjs');
    const baseCanvas=document.createElement('canvas');document.body.appendChild(baseCanvas);
    v5=await createV5CameraGpuPipeline({...common,canvas:baseCanvas});
   }
   await document.fonts.ready;
   if(!document.fonts.check('36px Gate1Bold')||!document.fonts.check('40px Gate1Bold'))throw Error('PINNED_FONT_NOT_READY');
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info');
   const backend=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
   if(!backend.includes('SwiftShader'))throw Error('SOFTWARE_SWIFTSHADER_REQUIRED');
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
   const signature=d=>JSON.stringify({center:d.center,extent:d.extent,geographicAnchor:d.geographicAnchor,
    reveal:d.reveal,layoutChoice:d.layoutChoice,camera:d.gpu.actualCamera,boundary:d.gpu.boundaryPixels,
    lod:d.gpu.terrainLod,layout:d.gpu.layout,validation:d.gpu.layoutValidation,eligibility:d.gpu.layoutEligibilityValidation});
   const snapshot=p=>{gl.finish();return new Uint8Array(p.readPixels());};
   const pngBytes=p=>Uint8Array.from(atob(p.png().split(',')[1]),x=>x.charCodeAt(0));
   let clean=null,cleanSignature=null;
   window.eventCandidate={eventPlan,cameraPlan,backend,
    async off(frame){
     if(!v5)throw Error('INDEPENDENT_V5_PIPELINE_REQUIRED');
     v5.drawFrame(frame);const a=snapshot(v5),basePng=await digest(pngBytes(v5));
     const diagnostic=event.drawFrame(frame,{eventEnabled:false}),b=snapshot(event);
     let changedBytes=0;for(let i=0;i<a.length;i++)if(a[i]!==b[i])changedBytes++;
     return {frame,changed_bytes:changedBytes,base_raw_rgba_sha256:await digest(a),raw_rgba_sha256:await digest(b),
      base_png_sha256:basePng,png_sha256:await digest(pngBytes(event)),eventEvaluated:diagnostic.event.controls!==null,
      eventDraws:diagnostic.event.line!==null||diagnostic.event.metric!==null,glError:gl.getError()};
    },
    async cleanReference(cameraFrame){
     const d=event.drawFrame(cameraFrame,{eventEnabled:false});clean=snapshot(event);cleanSignature=signature(d);
     return {cameraFrame,raw_rgba_sha256:await digest(clean),png_sha256:await digest(pngBytes(event)),diagnostic:d};
    },
    async capture(cameraFrame,eventFrame,{protect=false,png=false}={}){
     const d=event.drawFrame(cameraFrame,{eventEnabled:true,eventFrame}),actual=snapshot(event),e=d.event;
     const raw=await digest(actual),pngData=png?event.png():null;
     const result={cameraFrame,eventFrame,state:e.controls.state,lineFraction:e.controls.lineFraction,metricFraction:e.controls.metricFraction,
      raw_rgba_sha256:raw,metricValue:e.controls.metricValue,metricUnit:e.controls.metricUnit,
      line:e.line,metric:e.metric,placement:e.placement,rois:e.rois,protectedBoxes:e.protectedBoxes,
      protectedGraphics:e.protectedGraphics,eventStyle:e.eventStyle??e.lineStyle??null,metricStyle:e.metricStyle??null,glError:gl.getError(),
      frozenNativeSignatureUnchanged:cleanSignature===null?null:signature(d)===cleanSignature};
     if(protect){
      if(!clean)throw Error('CLEAN_PROTECTION_REFERENCE_REQUIRED');
      let changed=0,outside=0,protectedChanged=0,markerChanged=0;
      const base32=new Uint32Array(clean.buffer),actual32=new Uint32Array(actual.buffer);
      const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
      for(let index=0;index<actual32.length;index++)if(actual32[index]!==base32[index]){
       changed++;const x=index%1080,y=1919-Math.floor(index/1080);
       if(!e.rois.some(b=>inside(x,y,b)))outside++;
       if(e.protectedBoxes.some(b=>inside(x,y,b)))protectedChanged++;
       if(e.protectedGraphics.some(item=>item.kind==='MARKER'&&inside(x,y,item.box)))markerChanged++;
      }
      Object.assign(result,{changed_pixels:changed,outside_roi_changed_pixels:outside,protected_changed_pixels:protectedChanged,
       marker_changed_pixels:markerChanged});
     }
     if(pngData)result.png=pngData;
     return result;
    },
    unchanged:()=>JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input,fixture})===original,
    dispose(){event.dispose();v5?.dispose();}
   };
   return {cameraPlan,eventPlan,backend,pipeline:event.evidence};
  },{fixture,includeV5});
  if(errors.length)throw Error(errors[0]);
  return {page,info,errors,serverError:()=>serverError,async close(){await page.evaluate(()=>window.eventCandidate?.dispose());await browser.close();server.kill();}};
 }catch(error){await browser?.close();server.kill();throw error;}
}
export async function writeJson(file,value){await writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx'});}
