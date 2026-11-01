/** Standalone, opt-in context-only observation. Does not import or execute capture/render code. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {createServer} from 'node:http';
import childProcess from 'node:child_process';
import {promisify} from 'node:util';

export const IMAGE_DIGEST='sha256:2f0f1ee316e4474adf1502335307297385c746c998dda66f43d204a7418aaf50';
export const PROFILE_SHA256='4306430e64633d67745b706b7c4992b77d12bb1bf3a8d64352b82d07936d17b2';
const PROFILE='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/profile_contract.mjs';
export const CAPTURE_INPUT={executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']};
const html='<!doctype html><meta charset="utf-8"><body style="margin:0"><canvas id="map" width="1080" height="1920"></canvas>';
const sha=value=>createHash('sha256').update(value).digest('hex');
const check=(value,code)=>{if(!value)throw Error(code);};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function bounded(promise,ms,code) {let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(code)),ms);})]);}finally{clearTimeout(timer);}}
export const safeIdentifier=value=>typeof value==='string'&&value.length<=256&&/^[A-Za-z0-9 ._,():+\-]*$/.test(value)?value:null;
export const safeFailureCode=message=>/^(?:DIAG|HANDOFF)_[A-Z0-9_]{1,110}$/.test(message??'')?message:'DIAG_OPERATION_FAILED';
export function contextIdentity(identity,available) {const software=/swiftshader|llvmpipe|lavapipe|software/i.test(identity);return {nvidiaVerified:Boolean(available)&&/NVIDIA/i.test(identity)&&!software,vulkanVerified:Boolean(available)&&/Vulkan/i.test(identity)&&!software,softwareRendererObserved:software,identityEvidence:'WEBGL_RENDERER_STRINGS_ONLY_NOT_NATIVE_DRAW_PROOF'};}
export function classify(text='') {
 const matches=[];
 for(const [code,pattern] of [
  ['VK_ERROR_INITIALIZATION_FAILED',/VK_ERROR_INITIALIZATION_FAILED/],['VK_ERROR_INCOMPATIBLE_DRIVER',/VK_ERROR_INCOMPATIBLE_DRIVER/],
  ['VK_ERROR_DEVICE_LOST',/VK_ERROR_DEVICE_LOST/],['VK_ERROR_EXTENSION_NOT_PRESENT',/VK_ERROR_EXTENSION_NOT_PRESENT/],
  ['VK_ERROR_FEATURE_NOT_PRESENT',/VK_ERROR_FEATURE_NOT_PRESENT/],['VK_ERROR_OUT_OF_DEVICE_MEMORY',/VK_ERROR_OUT_OF_DEVICE_MEMORY/],
  ['EGL_NOT_INITIALIZED',/EGL_NOT_INITIALIZED/],['EGL_BAD_MATCH',/EGL_BAD_MATCH/],['EGL_BAD_ALLOC',/EGL_BAD_ALLOC/],
  ['ANGLE_INITIALIZATION_FAILED',/(?:ANGLE.*(?:initializ.*fail|error)|(?:fail|error).*initializ.*ANGLE)/i],
  ['GPU_PROCESS_LAUNCH_FAILED',/GPU process.*(?:fail|crash)|Failed to launch GPU process/i],
  ['SANDBOX_INITIALIZATION_FAILED',/No usable sandbox|Failed to move to new namespace|sandbox.*(?:initializ.*fail|denied)/i],
  ['PERMISSION_DENIED',/Permission denied|Operation not permitted/i],['CONTEXT_CREATION_FAILED',/Could not create.*context|Failed to create.*context/i],
  ['WEBGL_DISABLED',/WebGL.*disabled|WebGL.*not supported/i],['CONTEXT_LOST',/CONTEXT_LOST|context.*lost/i]]) if(pattern.test(text))matches.push(code);
 return matches;
}
export function safeTextEvidence(text='') {return {categories:classify(text),sha256:sha(text),bytes:Buffer.byteLength(text),rawOmitted:true};}
export function scrubSystemInfo(value={}) {
 const gpu=value.gpu??{},aux=gpu.auxAttributes??{},allowed={};
 for(const key of ['glRenderer','glVendor','glVersion','glImplementationParts','glImplementation','vulkanVersion'])if(typeof aux[key]==='string')allowed[key]=safeIdentifier(aux[key]);
 const featureStatus={};for(const key of ['webgl','webgl2','gpu_compositing','rasterization','vulkan'])if(typeof gpu.featureStatus?.[key]==='string')featureStatus[key]=safeIdentifier(gpu.featureStatus[key]);
 return {devices:(gpu.devices??[]).slice(0,8).map(row=>({vendorId:Number.isSafeInteger(row.vendorId)?row.vendorId:null,deviceId:Number.isSafeInteger(row.deviceId)?row.deviceId:null,vendorString:safeIdentifier(row.vendorString),deviceString:safeIdentifier(row.deviceString),driverVersion:safeIdentifier(row.driverVersion)})),aux:allowed,featureStatus};
}
async function durableFile(directory,name,bytes) {
 const file=path.join(directory,name),handle=await fs.open(file,'wx',0o600);
 try{await handle.writeFile(bytes);await handle.sync();}finally{await handle.close();}
 check(sha(await fs.readFile(file))===sha(bytes),'DIAG_EXPORT_READBACK_MISMATCH');
}
export async function runOnce({outputDirectory,approved=false}={}) {
 check(approved===true,'DIAG_SEPARATE_GPU_APPROVAL_REQUIRED');
 check(process.getuid?.()===1000&&process.getgid?.()===1000,'DIAG_UID_GID_1000_REQUIRED');
 check(process.env.WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST===IMAGE_DIGEST,'DIAG_CURRENT_IMAGE_REQUIRED');
 check(process.env.GPU_BACKEND==='vulkan'&&process.env.WORLD_ENGINE_RENDER_MODE==='gpu-required','DIAG_CAPTURE_RUNTIME_ENV_REQUIRED');
 check(!process.env.DEBUG,'DIAG_RAW_DEBUG_LOGGING_FORBIDDEN');
 check(typeof outputDirectory==='string'&&/^\/world-storage\/WORLD_ENGINE\/webgl-init-[A-Za-z0-9_-]{1,80}$/.test(outputDirectory),'DIAG_FRESH_EXPORT_PATH_REQUIRED');
 const parent=path.dirname(outputDirectory);check(await fs.realpath(parent)===parent,'DIAG_EXPORT_PARENT_SYMLINK_FORBIDDEN');
 // Exclusive reservation prevents accidental reuse; a failed attempt is never retried.
 await fs.mkdir(outputDirectory,{mode:0o700});
 const report={schema:'WORLD_ENGINE_WEBGL_INITIALIZATION_DIAGNOSTIC_V1',status:'RUNNING',imageDigest:IMAGE_DIGEST,startedAt:new Date().toISOString(),contextAttempts:0,browserLaunches:0,renderedFrames:0,retries:0,stage:'PREPARATION',sourceJobId:'studio-37dfbc8dab786a4d7c99cde6fae2f821',providerBillingStopControlled:false,limitations:['Context-only observation; no scene preparation, module imports, native draw, labels, frames or encoder.','No alternative flags or second context. Successful WebGL2 is not a 300-frame render PASS.','Export fsync and readback do not prove remote storage provider persistence.']};
 let browser,server,child,exitObserved=false,closeObserved=false,restoreSpawn=()=>{},stderrTail='',stderrBytes=0;
 const stderrHash=createHash('sha256'),categories=new Set();
 const appendStderr=chunk=>{try{const data=Buffer.from(chunk),remaining=Math.max(0,1024*1024-stderrBytes);stderrBytes+=data.length;if(!remaining)return;const part=data.subarray(0,remaining);stderrHash.update(part);const sample=stderrTail+part.toString('utf8');classify(sample).forEach(code=>categories.add(code));stderrTail=sample.slice(-4096);}catch{report.stderrObserverError=true;}};
 try{
  await durableFile(outputDirectory,'RESERVATION.json',Buffer.from(JSON.stringify({schema:report.schema,status:'RESERVED_NOT_RUN',sourceJobId:report.sourceJobId,imageDigest:IMAGE_DIGEST,startedAt:report.startedAt,maxBrowserLaunches:1,maxContextAttempts:1,renderedFrames:0})+'\n'));
  check(sha(await fs.readFile(PROFILE))===PROFILE_SHA256,'DIAG_CAPTURE_PROFILE_SOURCE_CHANGED');
  const {buildVulkanLaunchOptions}=await import(pathToFileURL(PROFILE).href);
  const launch=buildVulkanLaunchOptions(structuredClone(CAPTURE_INPUT),{uid:process.getuid(),rootTestOptIn:false});
  report.profile={...launch.evidence,profileSHA256:PROFILE_SHA256,viewport:{width:1080,height:1920},deviceScaleFactor:1,canvas:{width:1080,height:1920,kind:'ATTACHED_DOM_CANVAS'},contextAttributes:{alpha:false,antialias:false,preserveDrawingBuffer:true},selectedStartupProfile:['vulkan','egl'].includes(process.env.WORLD_ENGINE_GPU_PROFILE)?process.env.WORLD_ENGINE_GPU_PROFILE:'UNAVAILABLE'};
  const deps=process.env.WORLD_ENGINE_NODE_DEPS;check(typeof deps==='string'&&path.isAbsolute(deps),'DIAG_EXISTING_PLAYWRIGHT_ROOT_REQUIRED');
  const original=childProcess.spawn;
  childProcess.spawn=function(...args){if(args[0]==='/usr/bin/chromium'&&child)throw Error('DIAG_SECOND_BROWSER_LAUNCH_FORBIDDEN');const result=original.apply(this,args);try{if(args[0]==='/usr/bin/chromium'){child=result;report.observedBrowserProcesses=1;result.stderr?.on('data',appendStderr);result.once('close',()=>{closeObserved=true;});result.once('exit',(code,signal)=>{exitObserved=true;report.browserExit={observed:true,code:Number.isInteger(code)?code:null,signal:/^SIG[A-Z0-9]+$/.test(signal??'')?signal:null};});}}catch{report.spawnObserverError=true;}return result;};
  restoreSpawn=()=>{childProcess.spawn=original;};
  const require=createRequire(path.join(deps,'package.json')),{chromium}=require('playwright');
  report.dependencies={node:process.version,playwright:require('playwright/package.json').version};
  server=createServer((req,res)=>{if(req.method!=='GET'||req.url!=='/'){res.writeHead(404);res.end();return;}res.writeHead(200,{'content-type':'text/html','cache-control':'no-store'});res.end(html);});
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const origin='http://127.0.0.1:'+server.address().port;
  report.stage='BROWSER_LAUNCH';report.browserLaunches=1;
  try{browser=await bounded(chromium.launch(launch.options),35000,'DIAG_BROWSER_LAUNCH_TIMEOUT');}finally{restoreSpawn();}
  report.dependencies.chromium=browser.version();
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
  page.setDefaultTimeout(20000);page.setDefaultNavigationTimeout(20000);
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin,{waitUntil:'load'});report.stage='WEBGL_CONTEXT_CREATION';report.contextAttempts=1;
  const context=await bounded(page.evaluate(async()=>{
   const events=[],canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);
   canvas.addEventListener('webglcontextcreationerror',event=>events.push(String(event.statusMessage??'').slice(0,4096)),{once:true});
   const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
   if(!gl){await new Promise(resolve=>setTimeout(resolve,100));return {available:false,events};}
   const extension=gl.getExtension('WEBGL_debug_renderer_info');
   return {available:true,events,vendor:gl.getParameter(gl.VENDOR),renderer:gl.getParameter(gl.RENDERER),version:gl.getParameter(gl.VERSION),unmaskedVendor:extension?gl.getParameter(extension.UNMASKED_VENDOR_WEBGL):null,unmaskedRenderer:extension?gl.getParameter(extension.UNMASKED_RENDERER_WEBGL):null,contextLost:gl.isContextLost()};
  }),20000,'DIAG_CONTEXT_EVALUATION_TIMEOUT');
  report.webgl={available:context.available,events:context.events.map(safeTextEvidence)};
  for(const key of ['vendor','renderer','version','unmaskedVendor','unmaskedRenderer'])if(context[key]!==undefined)report.webgl[key]=safeIdentifier(context[key]);
  if(context.available)report.webgl.contextLost=context.contextLost;
  const identity=[report.webgl.unmaskedVendor,report.webgl.unmaskedRenderer,report.webgl.renderer].filter(Boolean).join(' ');
  Object.assign(report.webgl,contextIdentity(identity,context.available));
  report.status=context.available?'WEBGL2_CONTEXT_CREATED_GPU_IDENTITY_PENDING':'FAIL';
  if(!context.available)report.failure={code:'UP2_WEBGL2_REQUIRED',stage:'WEBGL_CONTEXT_CREATION',frameIndex:null};
  else if(report.webgl.nvidiaVerified&&report.webgl.vulkanVerified&&!context.contextLost)report.status='PASS_CONTEXT_ONLY';
  report.stage='READ_ONLY_GPU_INFORMATION';
  try{report.browserGPU=await bounded((async()=>{const session=await browser.newBrowserCDPSession();try{return scrubSystemInfo(await session.send('SystemInfo.getInfo'));}finally{await session.detach();}})(),5000,'DIAG_CDP_INFORMATION_TIMEOUT');}catch(error){report.browserGPU={status:'UNAVAILABLE',error:safeTextEvidence(String(error?.message??''))};}
 }catch(error){report.status='BLOCKED';report.failure={code:safeFailureCode(error?.message),stage:report.stage,exceptionType:['Error','TypeError','TimeoutError'].includes(error?.name)?error.name:'OtherError',message:safeTextEvidence(String(error?.message??''))};}
 finally{
  restoreSpawn();report.stage='CLEANUP';
  try{if(browser){await bounded(browser.close(),10000,'DIAG_BROWSER_CLOSE_TIMEOUT');report.browserCloseCompleted=true;}else report.browserCloseCompleted=false;}catch(error){report.browserCloseCompleted=false;report.cleanupError=safeTextEvidence(String(error?.message??''));}
  if(child&&!exitObserved){try{child.kill('SIGTERM');await delay(1000);if(!exitObserved){child.kill('SIGKILL');await delay(1000);}}catch{report.ownedChildTerminationError=true;}}
  if(child&&!closeObserved)await delay(1000);
  report.cleanup={ownedChromiumExitObserved:exitObserved,ownedChromiumCloseObserved:closeObserved,ownedChromiumProcessObserved:Boolean(child),descendantCleanupVerified:false,providerStopStillRequired:true};
  if(server){server.closeAllConnections?.();try{await bounded(new Promise(resolve=>server.close(resolve)),2000,'DIAG_LOOPBACK_CLOSE_TIMEOUT');}catch{report.loopbackCloseIncomplete=true;}}
  // Independent read-only recognition, also collected after a browser-launch failure.
  try{const {stdout}=await promisify(childProcess.execFile)('nvidia-smi',['--query-gpu=name,driver_version','--format=csv,noheader,nounits'],{timeout:5000,maxBuffer:8192});report.nvidia={status:'QUERY_COMPLETE',devices:stdout.trim().split('\n').slice(0,8).map(line=>{const [model,driverVersion]=line.split(',').map(value=>value.trim());return {model:safeIdentifier(model),driverVersion:safeIdentifier(driverVersion)};})};}catch(error){report.nvidia={status:'QUERY_UNAVAILABLE',exitCode:Number.isInteger(error?.code)?error.code:null,error:safeTextEvidence(String(error?.message??''))};}
  report.browserExit??={observed:exitObserved,code:null,signal:null};
  report.browserStderr={categories:[...categories].sort(),bytesObserved:stderrBytes,hashedBytes:Math.min(stderrBytes,1024*1024),sha256:stderrHash.digest('hex'),truncated:stderrBytes>1024*1024,rawOmitted:true};
  report.finishedAt=new Date().toISOString();report.stage='RESULT_WRITTEN';
  const bytes=Buffer.from(JSON.stringify(report,null,2)+'\n');await durableFile(outputDirectory,'WEBGL_DIAGNOSTIC.json',bytes);await durableFile(outputDirectory,'SHA256SUMS',Buffer.from(sha(bytes)+'  WEBGL_DIAGNOSTIC.json\n'));
 }
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2),output=args.find(value=>value.startsWith('--output='))?.slice('--output='.length);
 runOnce({outputDirectory:output,approved:args.includes('--approved-single-diagnostic')}).then(report=>{process.stdout.write(JSON.stringify({status:report.status,contextAttempts:report.contextAttempts,browserLaunches:report.browserLaunches,renderedFrames:0,resultFile:'WEBGL_DIAGNOSTIC.json'})+'\n');process.exitCode=report.status==='PASS_CONTEXT_ONLY'?0:2;}).catch(error=>{process.stdout.write(JSON.stringify({status:'BLOCKED',code:safeFailureCode(error?.message),rawOmitted:true})+'\n');process.exitCode=2;});
}
