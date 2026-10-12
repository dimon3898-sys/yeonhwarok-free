// Focused private integration checks; no MP4, production fixture or public Proof.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(engine);
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const baseline=JSON.parse(await readFile(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'),'utf8'));
const fixtures=await Promise.all(['a','b'].map(async id=>JSON.parse(await readFile(path.join(engine,`recovery/event-v1/fixtures/synthetic-${id}.json`),'utf8'))));
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{stdio:['ignore','pipe','inherit']});
let browser;
try{
 const url=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('SERVER_TIMEOUT')),10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);resolve(JSON.parse(line).url);});
  server.once('error',reject);server.once('exit',code=>reject(Error('SERVER_EXIT_'+code)));
 });
 assert.equal(require('playwright/package.json').version,'1.62.1');
 browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 assert.equal(browser.version(),'154.0.8037.57');
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
 await page.goto(url+'/runtime-config.json');
 const report=await page.evaluate(async({fixtures,expected})=>{
  const {createEventGpuPipeline}=await import('/modules/event_gpu_pipeline_v1.mjs');
  const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
  const {compileEventPlan}=await import('/modules/event_timeline_v1.mjs');
  const load=async p=>{const r=await fetch(p);if(!r.ok)throw Error('HTTP_'+r.status);return r.json();};
  const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
   load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
  const original=JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input});
  const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
  const results=[];
  for(let fixtureIndex=0;fixtureIndex<fixtures.length;fixtureIndex++){
   const fixture=fixtures[fixtureIndex],intent=compileEventIntent(fixture.intent),eventPlan=compileEventPlan(intent,fixture.timeline);
   const canvas=document.createElement('canvas');document.body.appendChild(canvas);
   const pipeline=await createEventGpuPipeline({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,heightSource:input.heightSource,
    contextTerrain:input.contextTerrain,eventPlan});
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info');
   const gpu=gl.getParameter(debug.UNMASKED_RENDERER_WEBGL);if(!gpu.includes('SwiftShader'))throw Error('SOFTWARE_GPU_REQUIRED');
   const snapshot=()=>{gl.finish();return new Uint8Array(pipeline.readPixels());};
   const hash=()=>digest(snapshot());
   const off=[];
   if(fixtureIndex===0)for(const frame of [0,144,205,249]){
    pipeline.drawFrame(frame,{eventEnabled:false});
    const pngBytes=Uint8Array.from(atob(pipeline.png().split(',')[1]),c=>c.charCodeAt(0)),golden=expected.find(x=>x.frame===frame);
    off.push({frame,raw_rgba_sha256:await hash(),expected:golden.raw_rgba_sha256,png_sha256:await digest(pngBytes),expected_png_sha256:golden.png_sha256});
   }
   pipeline.drawFrame(205,{eventEnabled:false});const clean=snapshot(),cleanHash=await digest(clean);
   const checkpoints=[0,5,9,12,17,21,22,25],on=[];
   let previousFull=null;
   for(const eventFrame of checkpoints){
    const diagnostic=pipeline.drawFrame(205,{eventEnabled:true,eventFrame}),actual=snapshot();
    const rois=diagnostic.event.rois,protectedBoxes=diagnostic.event.protectedBoxes;
    let changed=0,outside=0,protectedChanged=0;
    const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
    for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
     const i=((1919-y)*1080+x)*4;
     if(actual[i]!==clean[i]||actual[i+1]!==clean[i+1]||actual[i+2]!==clean[i+2]||actual[i+3]!==clean[i+3]){
      changed++;if(!rois.some(b=>inside(x,y,b)))outside++;if(protectedBoxes.some(b=>inside(x,y,b)))protectedChanged++;
     }
    }
    const currentHash=await digest(actual);
    if(eventFrame===22)previousFull=currentHash;
    on.push({eventFrame,state:diagnostic.event.controls.state,changed,outside,protectedChanged,rois,placement:diagnostic.event.placement?.placement,
     lineFraction:diagnostic.event.controls.lineFraction,metricFraction:diagnostic.event.controls.metricFraction,raw_rgba_sha256:currentHash,
     holdStable:eventFrame===25?currentHash===previousFull:null});
   }
   pipeline.drawFrame(205,{eventEnabled:false});const offRestored=await hash()===cleanHash;
   const glError=gl.getError();pipeline.dispose();canvas.remove();
   results.push({fixture:fixtureIndex===0?'Synthetic A':'Synthetic B',dataMode:intent.data_mode,gpu,off,on,offRestored,glError});
  }
  return {status:'PASS',scope:'COMMON_CORE_FOCUSED_SYNTHETIC_NOT_PRODUCTION_PROOF',results,
   baselineInputsUnchanged:JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input})===original};
 },{fixtures,expected:baseline.frames.filter(x=>[0,144,205,249].includes(x.frame))});
 assert.equal(errors.length,0);assert.equal(report.baselineInputsUnchanged,true);
 for(const row of report.results){
  for(const off of row.off){assert.equal(off.raw_rgba_sha256,off.expected,'Event OFF frame '+off.frame);assert.equal(off.png_sha256,off.expected_png_sha256);}
  assert.equal(row.offRestored,true);assert.equal(row.glError,0);
  assert.equal(row.on[0].changed,0);
  for(const on of row.on){assert.equal(on.outside,0);assert.equal(on.protectedChanged,0);}
  assert.ok(row.on.at(-1).changed>0);assert.equal(row.on.at(-1).holdStable,true);
 }
 const arg=process.argv.indexOf('--report');
 if(arg>=0){if(!process.argv[arg+1])throw Error('REPORT_PATH_REQUIRED');await writeFile(process.argv[arg+1],JSON.stringify(report,null,2)+'\n');}
 console.log(JSON.stringify(report));
}finally{await browser?.close();server.kill();}
