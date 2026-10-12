#!/usr/bin/env node
// CPU WebGL2 capture and streaming encoding. Camera/Reveal live in their modules.
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {readFile,writeFile,mkdir,realpath,lstat} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {spawn,execFile} from 'node:child_process';
import {createInterface} from 'node:readline';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const runtime=path.dirname(fileURLToPath(import.meta.url));
const engine=path.resolve(runtime,'../..'),repo=path.dirname(engine);
const execute=promisify(execFile),PYTHON='/usr/bin/python3';
const WIDTH=1080,HEIGHT=1920,FPS=30;
const BROWSER_ARGS=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage'];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function hashFile(file){
 const hash=createHash('sha256');let bytes=0;
 for await(const chunk of createReadStream(file)){hash.update(chunk);bytes+=chunk.length;}
 return {sha256:hash.digest('hex'),bytes};
}
async function record(file){
 const absolute=path.resolve(repo,file);
 if(path.relative(repo,absolute).startsWith('..')||await realpath(absolute)!==absolute||!(await lstat(absolute)).isFile())
  throw Error('REGULAR_REPOSITORY_INPUT_REQUIRED');
 return {path:path.relative(repo,absolute).split(path.sep).join('/'),...await hashFile(absolute)};
}
async function inventory(){
 const dependency=JSON.parse(await readFile(path.join(runtime,'manifests/DEPENDENCY_MANIFEST.json'),'utf8'));
 const records={};
 for(const item of dependency.required_files){
  const row=await record(item.path);
  if(row.sha256!==item.sha256||row.bytes!==item.bytes)throw Error('CANDIDATE_INPUT_CHANGED: '+item.path);
  records[row.path]=row;
 }
 const local=['compile_inputs.mjs','harness.mjs','index.html','serve.py','render_candidate.mjs',
  'inputs/scene.json','inputs/camera-plan.json','inputs/INPUT_PROVENANCE.json'];
 for(const file of local){const row=await record(path.relative(repo,path.join(runtime,file)));records[row.path]=row;}
 for(const file of ['camera_director_v5.mjs','camera_gpu_pipeline_v5.mjs']){
  const row=await record(path.relative(repo,path.join(engine,'web/map_infographic_v1',file)));records[row.path]=row;
 }
 for(const file of ['SOURCE_MANIFEST.json','HASH_MANIFEST.json','DEPENDENCY_MANIFEST.json','IMPORT_MANIFEST.json','SHA256SUMS']){
  const row=await record(path.relative(repo,path.join(runtime,'manifests',file)));records[row.path]=row;
 }
 const {stdout:commit}=await execute('git',['rev-parse','HEAD'],{cwd:repo});
 return {source_commit:commit.trim(),records};
}
function options(){
 const args=process.argv.slice(2),opts={phase:'checkpoints'};
 for(let i=0;i<args.length;i+=2){
  if(!['--output-dir','--phase'].includes(args[i])||!args[i+1])throw Error('USAGE: --output-dir NEW_DIRECTORY [--phase checkpoints|video]');
  opts[args[i].slice(2)]=args[i+1];
 }
 if(!opts['output-dir']||!['checkpoints','video'].includes(opts.phase))throw Error('OUTPUT_AND_PHASE_REQUIRED');
 return opts;
}
async function startServer(){
 const child=spawn(PYTHON,['-B',path.join(runtime,'serve.py')],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let stderr='';child.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-4096);});
 const ready=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:child.stdout});
  const timer=setTimeout(()=>{child.kill();reject(Error('SERVER_START_TIMEOUT'));},10000);
  child.once('error',reject);child.once('exit',code=>{clearTimeout(timer);reject(Error('SERVER_EXIT_'+code));});
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{resolve(JSON.parse(line));}catch(error){child.kill();reject(error);}});
 });
 if(ready.event!=='READY')throw Error('SERVER_READY_REQUIRED');
 return {child,url:ready.url,stderr:()=>stderr};
}
async function compare(expected,actual){
 const {stdout}=await execute(PYTHON,['-B',path.join(repo,'tools/compare_v4_png.py'),expected,actual],{cwd:repo,maxBuffer:1024*1024});
 const result=JSON.parse(stdout);
 if(!['BIT_EXACT','PIXEL_EXACT'].includes(result.classification)||result.changed_pixels!==0)throw Error('PROTECTED_ENDPOINT_PIXEL_MISMATCH');
 return result;
}
function checkpointMap(info){
 const p=info.cameraPlan,r=info.revealPlan,cp=p.checkpoints;
 const context=cp.MINIMUM_CONTEXT??cp.CONTEXT??Math.max(0,p.motion.startFrame-1);
 const turn=cp.DIRECTIONAL_TURN??p.motion.startFrame;
 const approach=p.timeline.find(state=>state.state==='EVENT_APPROACH');
 const approachFrame=Math.floor((approach.startFrame+approach.endFrame-1)/2);
 const guide=r.schedule.location===null?r.schedule.marker:r.schedule.location;
 if(!Number.isInteger(guide))throw Error('CONDITION_BASED_MARKER_GUIDE_REQUIRED');
 return {
  '01_PRIMARY_START.png':cp.PRIMARY_START,
  '02_MINIMUM_CONTEXT.png':context,
  '03_DIRECTIONAL_TURN.png':turn,
  '04_EVENT_APPROACH.png':approachFrame,
  '05_MARKER_GUIDE.png':Math.min(Math.max(guide+Math.ceil(r.profile.stableEligibilitySeconds*p.fps),approachFrame+1),p.motion.endFrame-1),
  '06_REGIONAL_LOCK.png':cp.REGIONAL_LOCK,
  '07_FINAL_HOLD.png':cp.FINAL_HOLD
 };
}
async function main(){
 const opts=options(),inputs=await inventory(),out=path.resolve(opts['output-dir']);
 if(out===repo||out.startsWith(repo+path.sep)||await realpath(path.dirname(out))!==path.dirname(out))throw Error('PRIVATE_REGULAR_OUTPUT_DIRECTORY_REQUIRED');
 await mkdir(out);
 const report={schema:1,state:'V5_CANDIDATE',user_review:'USER_VIDEO_REVIEW_REQUIRED',phase:opts.phase,
  source_commit:inputs.source_commit,required_inputs:inputs.records,node:process.version,started_at_utc:new Date().toISOString(),
  viewport:[WIDTH,HEIGHT],fps:FPS,audio:false,backend_required:'Software WebGL2 SwiftShader',
  command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()},frames:[],errors:[],
  final_permanent_gate:'NOT_RUN_PENDING_USER_VIDEO_APPROVAL',status:'STARTED'};
 let server,browser,encoder,encoderExit,encoderError='';
 try{
  const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
  if(require('playwright/package.json').version!=='1.62.1')throw Error('PINNED_PLAYWRIGHT_REQUIRED');
  server=await startServer();
  const {chromium}=require('playwright');
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:BROWSER_ARGS});
  report.chromium=browser.version();if(report.chromium!=='154.0.8037.57')throw Error('PINNED_CHROMIUM_REQUIRED');
  const page=await browser.newPage({viewport:{width:WIDTH,height:HEIGHT},deviceScaleFactor:1});
  const pageErrors=[];
  await page.route('**/*',route=>new URL(route.request().url()).origin===server.url?route.continue():route.abort('blockedbyclient'));
  page.on('pageerror',error=>pageErrors.push(String(error.message)));
  page.on('response',response=>{if(response.status()>=400)pageErrors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.goto(server.url,{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>['READY','ERROR'].includes(window.v5Runtime?.state),null,{timeout:240000});
  const startup=await page.evaluate(()=>({state:window.v5Runtime.state,error:window.v5Runtime.error}));
  if(startup.error||pageErrors.length)throw Error(startup.error||pageErrors[0]);
  const info=await page.evaluate(()=>window.v5Runtime.info);
  report.cameraPlan=info.cameraPlan;report.revealPlan=info.revealPlan;report.pipeline=info.evidence;
  report.checkpoints=checkpointMap(info);
  if(info.cameraPlan.directorVersion!=='CAMERA_DIRECTOR_V5'||info.cameraPlan.fps!==FPS||
    !Number.isInteger(info.cameraPlan.totalFrames)||info.cameraPlan.totalFrames<=0)throw Error('V5_CAMERA_PLAN_REQUIRED');
  for(const frame of Object.values(report.checkpoints))if(!Number.isInteger(frame)||frame<0||frame>=info.cameraPlan.totalFrames)throw Error('INVALID_CHECKPOINT_FRAME');
  async function capture(frame){
   const value=await page.evaluate(frame=>window.v5Runtime.captureFrame(frame),frame);
   if(pageErrors.length)throw Error(pageErrors[0]);
   if(!value.backend.renderer.includes('SwiftShader'))throw Error('SOFTWARE_SWIFTSHADER_REQUIRED');
   report.backend=value.backend;
   const f=value.diagnostic;
   if(f.gpu.glError!==0||!f.gpu.layoutValidation.valid||f.primaryMaterial!==1||
     f.gpu.actualPrimaryMaterial!==1||f.admission.status!=='LOCAL_NOT_ADMITTED'||f.admission.localUsed||
     JSON.stringify(f.geographicAnchor)!==JSON.stringify(info.cameraPlan.anchor)||
     f.gpu.factoryCount!==1||f.gpu.finishedFrameMix||f.gpu.projectionChange)throw Error('PROTECTED_RUNTIME_CONTRACT_FAILED');
   const bytes=Buffer.from(value.png.slice('data:image/png;base64,'.length),'base64');
   if(!value.png.startsWith('data:image/png;base64,')||bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||
     bytes.readUInt32BE(16)!==WIDTH||bytes.readUInt32BE(20)!==HEIGHT)throw Error('CANONICAL_PNG_REQUIRED');
   return {bytes,sha256:sha(bytes),raw_rgba_sha256:value.raw_rgba_sha256,diagnostic:f};
  }
  // Compare actual frozen endpoints before any full-video encoding.
  const hold=await capture(report.checkpoints['07_FINAL_HOLD.png']);
  await writeFile(path.join(out,'07_FINAL_HOLD.png'),hold.bytes,{flag:'wx'});
  report.final_hold_comparison=await compare(path.join(engine,'recovery/v4/review/reproduced-final-hold.png'),path.join(out,'07_FINAL_HOLD.png'));
  const start=await capture(0);await writeFile(path.join(out,'01_PRIMARY_START.png'),start.bytes,{flag:'wx'});
  report.primary_start_comparison=await compare(path.join(engine,'recovery/v4/approved-proof/01_PRIMARY_START.png'),path.join(out,'01_PRIMARY_START.png'));
  const selected=new Set(Object.values(report.checkpoints));
  const frames=opts.phase==='video'?Array.from({length:info.cameraPlan.totalFrames},(_,i)=>i):[...selected].sort((a,b)=>a-b);
  if(opts.phase==='video'){
   const video=path.join(out,'SUEZ_CAMERA_DIRECTOR_V5.mp4');
   const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate',String(FPS),'-vcodec','png','-threads','2',
    '-i','pipe:0','-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
   report.encode_command=['ffmpeg',...args];
   encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
   encoder.stderr.on('data',chunk=>{encoderError=(encoderError+chunk).slice(-8192);});
   encoder.stdin.on('error',error=>{encoderError+=' '+error.message;});
   encoderExit=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('exit',(code,signal)=>resolve({code,signal}));});
  }
  const diagnosticFile=path.join(out,'frame-diagnostics.jsonl');
  const diagnosticStream=(await import('node:fs')).createWriteStream(diagnosticFile,{flags:'wx'});
  try{
   for(const frame of frames){
    const captured=await capture(frame);
    for(const [filename,checkpoint]of Object.entries(report.checkpoints))if(checkpoint===frame&&
      !['01_PRIMARY_START.png','07_FINAL_HOLD.png'].includes(filename))await writeFile(path.join(out,filename),captured.bytes,{flag:'wx'});
    if(frame===report.checkpoints['07_FINAL_HOLD.png']&&captured.sha256!==hold.sha256)throw Error('RANDOM_ACCESS_FINAL_HOLD_CHANGED');
    if(encoder&&!encoder.stdin.write(captured.bytes))await once(encoder.stdin,'drain');
    const row={frame,png_sha256:captured.sha256,raw_rgba_sha256:captured.raw_rgba_sha256};report.frames.push(row);
    if(!diagnosticStream.write(JSON.stringify({frame,...captured.diagnostic})+'\n'))await once(diagnosticStream,'drain');
    if(frame%15===0||frame===frames.at(-1))console.log(JSON.stringify({event:'FRAME_CAPTURED',frame,total:info.cameraPlan.totalFrames,state:captured.diagnostic.state}));
   }
  }finally{diagnosticStream.end();await once(diagnosticStream,'finish');}
  if(encoder){
   encoder.stdin.end();const exited=await encoderExit;
   if(exited.code!==0)throw Error('ENCODER_FAILED: '+encoderError);
   const video=path.join(out,'SUEZ_CAMERA_DIRECTOR_V5.mp4');
   const {stdout}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video],{maxBuffer:1024*1024});
   report.ffprobe=JSON.parse(stdout);const streams=report.ffprobe.streams,v=streams[0];
   if(streams.length!==1||v.codec_type!=='video'||v.codec_name!=='h264'||v.width!==WIDTH||v.height!==HEIGHT||
     v.avg_frame_rate!=='30/1'||Number(v.nb_read_frames)!==info.cameraPlan.totalFrames||
     Math.abs(Number(v.duration)-info.cameraPlan.totalFrames/FPS)>.001)throw Error('V5_VIDEO_METADATA_FAILED');
   report.video={path:'SUEZ_CAMERA_DIRECTOR_V5.mp4',...await hashFile(video)};
  }
  const after=await inventory();if(JSON.stringify(after)!==JSON.stringify(inputs))throw Error('INPUT_CHANGED_DURING_CAPTURE');
  report.status='CAPTURE_COMPLETE';report.command.exit_code=0;
  await page.evaluate(()=>window.v5Runtime.dispose());
 }catch(error){report.status='ERROR';report.command.exit_code=1;report.errors.push(String(error.message));throw error;}
 finally{
  if(encoder&&!encoder.stdin.destroyed)encoder.stdin.destroy();
  if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
  if(browser)await browser.close().catch(()=>{});
  if(server){server.child.kill('SIGTERM');report.server_stderr=server.stderr();}
  report.completed_at_utc=new Date().toISOString();
  await writeFile(path.join(out,'runtime-diagnostic.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 }
 console.log(JSON.stringify({status:report.status,frames:report.frames.length,video:report.video,
  finalHold:report.final_hold_comparison.classification,user_review:'USER_VIDEO_REVIEW_REQUIRED'}));
}
main().catch(error=>{console.error(JSON.stringify({status:'ERROR',message:String(error.message)}));process.exitCode=1;});
