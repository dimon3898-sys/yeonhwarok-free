// Thin read-only production guard caller; no Event/Camera/Renderer algorithms.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {createHash} from 'node:crypto';
import {readFile,writeFile,realpath,lstat} from 'node:fs/promises';
import path from 'node:path';

function options(){
 const args=process.argv.slice(2),out={};
 for(let i=0;i<args.length;i+=2){
  if(!['--repo','--fixture','--data-gate-file','--report'].includes(args[i])||!args[i+1])
   throw Error('USAGE: --repo REPOSITORY --fixture FILE --data-gate-file FILE --report NEW_PRIVATE_JSON');
  out[args[i].slice(2)]=args[i+1];
 }
 if(!out.repo||!out.fixture||!out.report)throw Error('REPO_FIXTURE_REPORT_REQUIRED');
 return out;
}
const opts=options(),repo=await realpath(path.resolve(opts.repo)),engine=path.join(repo,'world-simulation-shorts-engine');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function repositoryInput(given){
 const absolute=path.resolve(repo,given),actual=await realpath(absolute);
 if(!actual.startsWith(repo+path.sep)||actual!==absolute||!(await lstat(actual)).isFile())
  throw Error('REGULAR_REPOSITORY_INPUT_REQUIRED');
 const bytes=await readFile(actual);
 return {path:path.relative(repo,actual).split(path.sep).join('/'),sha256:sha(bytes),bytes:bytes.length,value:JSON.parse(bytes)};
}
const fixture=await repositoryInput(opts.fixture);
const gate=opts['data-gate-file']?await repositoryInput(opts['data-gate-file']):null;
if(fixture.value.data_gate!=='SUEZ_EVENT_DATA_READY'&&gate?.value.status!=='SUEZ_EVENT_DATA_READY'&&gate?.value.decision!=='SUEZ_EVENT_DATA_READY')
 throw Error('EXTERNAL_VERIFIED_GEOMETRY_DATA_GATE_REQUIRED');
assert.equal(fixture.value.intent?.data_mode,'PRODUCTION');
assert.equal(fixture.value.intent?.line?.source?.verification_status,'VERIFIED');
assert.equal(fixture.value.intent?.metric?.source?.verification_status,'VERIFIED');
const source=JSON.parse(await readFile(path.join(engine,'recovery/event-v1/manifests/SOURCE_MANIFEST.json'),'utf8'));
async function verifySource(){
 const rows=[];
 for(const item of source.entries){
  const bytes=await readFile(path.join(repo,item.path));
  const row={path:item.path,sha256:sha(bytes),bytes:bytes.length};
  assert.equal(row.sha256,item.sha256,'LOCKED_SOURCE_HASH: '+item.path);
  assert.equal(row.bytes,item.bytes,'LOCKED_SOURCE_SIZE: '+item.path);
  rows.push(row);
 }
 return rows;
}
const before=await verifySource();
const golden=JSON.parse(await readFile(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'),'utf8'));
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
assert.equal(require('playwright/package.json').version,'1.62.1');
const report={schema:1,scope:'PRODUCTION_FIXTURE_RUNTIME_COMPATIBILITY_NOT_EVENT_FINAL',data_gate:'SUEZ_EVENT_DATA_READY',
 fixture:{path:fixture.path,sha256:fixture.sha256,bytes:fixture.bytes},
 data_gate_record:gate?{path:gate.path,sha256:gate.sha256,bytes:gate.bytes}:null,
 started_at_utc:new Date().toISOString(),locked_source_count:before.length,source_hash_validation:'PASS',
 renderer_modified:false,camera_modified:false,event_core_modified:false,mp4_generated:false,png_generated:false,status:'STARTED'};
const server=spawn('/usr/bin/python3',['-B',path.join(engine,'recovery/v5/serve.py')],{stdio:['ignore','pipe','pipe']});
let browser,serverError='';server.stderr.on('data',bytes=>{serverError=(serverError+bytes.toString()).slice(-8192);});
try{
 const url=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{server.kill();reject(Error('SERVER_TIMEOUT'));},10000);
  createInterface({input:server.stdout}).once('line',line=>{clearTimeout(timer);try{resolve(JSON.parse(line).url);}catch(error){reject(error);}});
  server.once('error',error=>{clearTimeout(timer);reject(error);});
  server.once('exit',code=>{clearTimeout(timer);reject(Error('SERVER_EXIT_'+code));});
 });
 browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 assert.equal(browser.version(),'154.0.8037.57');report.chromium=browser.version();report.node=process.version;
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
 await page.route('**/*',route=>new URL(route.request().url()).origin===url?route.continue():route.abort('blockedbyclient'));
 await page.goto(url+'/runtime-config.json');
 Object.assign(report,await page.evaluate(async({fixture,expected})=>{
  const {createEventGpuPipeline}=await import('/modules/event_gpu_pipeline_v1.mjs');
  const {compileEventIntent}=await import('/modules/event_contract_v1.mjs');
  const {compileEventPlan}=await import('/modules/event_timeline_v1.mjs');
  const load=async p=>{const response=await fetch(p);if(!response.ok)throw Error('INPUT_HTTP_'+response.status);return response.json();};
  const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([
   load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
  const unchanged=JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input});
  const intent=compileEventIntent(fixture.intent),eventPlan=compileEventPlan(intent,fixture.timeline);
  if(eventPlan.fps!==30||eventPlan.totalFrames!==150)throw Error('CANONICAL_FIVE_SECOND_EVENT_PLAN_REQUIRED');
  const canvas=document.createElement('canvas');document.body.appendChild(canvas);
  const pipeline=await createEventGpuPipeline({canvas,plans:{REGIONAL,CONTINENT},cameraPlan,scene,
   heightSource:input.heightSource,contextTerrain:input.contextTerrain,eventPlan});
  try{
   const gl=canvas.getContext('webgl2'),debug=gl.getExtension('WEBGL_debug_renderer_info');
   const backend=gl.getParameter(debug.UNMASKED_RENDERER_WEBGL);if(!backend.includes('SwiftShader'))throw Error('SOFTWARE_GPU_REQUIRED');
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
   const capture=async()=>{
    gl.finish();const pixels=new Uint8Array(pipeline.readPixels());
    if(pixels.byteLength!==1080*1920*4||gl.getError()!==gl.NO_ERROR)throw Error('CANONICAL_GPU_READBACK_REQUIRED');
    const png=Uint8Array.from(atob(pipeline.png().split(',')[1]),char=>char.charCodeAt(0));
    return {raw_rgba_sha256:await digest(pixels),png_sha256:await digest(png)};
   };
   const off=[];
   for(const frame of [0,144,205,249]){
    pipeline.drawFrame(frame,{eventEnabled:false});
    const actual=await capture(),golden=expected.find(value=>value.frame===frame);
    if(!golden)throw Error('V5_APPROVED_FRAME_REFERENCE_REQUIRED');
    const match=actual.raw_rgba_sha256===golden.raw_rgba_sha256&&actual.png_sha256===golden.png_sha256;
    off.push({frame,...actual,expected_raw_rgba_sha256:golden.raw_rgba_sha256,expected_png_sha256:golden.png_sha256,result:match?'BIT_EXACT':'MISMATCH'});
    if(!match)throw Error('EVENT_OFF_V5_PIXEL_MISMATCH_'+frame);
   }
   let eventOn;
   try{
    const diagnostic=pipeline.drawFrame(249,{eventEnabled:true,eventFrame:0});
    eventOn={status:'READINESS_PASS_ONLY_NOT_150_FRAME_PROOF',eventFrame:0,cameraFrame:249,
     controls:diagnostic.event.controls,rois:diagnostic.event.rois,protectedBoxes:diagnostic.event.protectedBoxes,
     lineFullRoi:diagnostic.event.lineFullRoi,placement:diagnostic.event.placement};
   }catch(error){eventOn={status:'BLOCKED',eventFrame:0,cameraFrame:249,error:String(error.message)};}
   // prepareEvent can fail after native map drawing; never publish that canvas.
   pipeline.drawFrame(249,{eventEnabled:false});const restored=await capture(),last=off.at(-1);
   const offRestored=restored.raw_rgba_sha256===last.raw_rgba_sha256&&restored.png_sha256===last.png_sha256;
   if(!offRestored)throw Error('EVENT_OFF_RESTORE_PIXEL_MISMATCH');
   if(JSON.stringify({REGIONAL,CONTINENT,scene,cameraPlan,input})!==unchanged)throw Error('LOCKED_INPUTS_MUTATED');
   return {backend,eventPlan:{fps:eventPlan.fps,totalFrames:eventPlan.totalFrames,durationSeconds:eventPlan.durationSeconds,
    timeline:eventPlan.timeline,geometryVertices:intent.line.geometry.coordinates.length},
    event_off:{result:'PASS',frames:off},event_on:eventOn,event_off_restored:{result:'BIT_EXACT',...restored},
    locked_inputs_unchanged:true,glError:gl.getError(),status:eventOn.status==='BLOCKED'?'PRODUCTION_PROOF_BLOCKED':'PRODUCTION_PREFLIGHT_READY'};
  }finally{pipeline.dispose();canvas.remove();}
 },{fixture:fixture.value,expected:golden.frames}));
 assert.equal(errors.length,0);assert.equal(report.glError,0);
 const after=await verifySource();assert.deepEqual(after,before);report.source_hashes_unchanged=true;
}catch(error){report.status='ERROR';report.error=String(error.message);process.exitCode=1;}
finally{
 await browser?.close();server.kill();report.server_stderr=serverError;report.completed_at_utc=new Date().toISOString();
 await writeFile(path.resolve(opts.report),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:report.status,eventOFF:report.event_off?.result,eventON:report.event_on,
  offRestored:report.event_off_restored?.result,sourceUnchanged:report.source_hashes_unchanged,report:path.resolve(opts.report)}));
}
