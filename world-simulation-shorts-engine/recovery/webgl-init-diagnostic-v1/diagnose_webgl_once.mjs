/** Standalone, opt-in context-only observation. Does not import or execute capture/render code. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {createServer} from 'node:http';
import childProcess from 'node:child_process';
import {promisify} from 'node:util';

export const IMAGE_DIGEST='sha256:9e9301dec376a780f4fb2287fe092282baaef3d6cfdfc93532ea6763d9f9b0cf';
export const PROFILE_SHA256='4e78b2d9f18107d70fda3c266c48d72103f7eaa63015b4dd1c1bb65e697e79a6';
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
// Finite public graphics vocabulary, not a general-purpose log redactor. Unknown
// words, identifiers and numbers never enter the excerpt, even if they look safe.
const nativeSymbols=new Set(`ANGLE Vulkan EGL WebGL WebGL2 NVIDIA
VK_SUCCESS VK_ERROR_OUT_OF_HOST_MEMORY VK_ERROR_OUT_OF_DEVICE_MEMORY VK_ERROR_INITIALIZATION_FAILED
VK_ERROR_DEVICE_LOST VK_ERROR_MEMORY_MAP_FAILED VK_ERROR_LAYER_NOT_PRESENT VK_ERROR_EXTENSION_NOT_PRESENT
VK_ERROR_FEATURE_NOT_PRESENT VK_ERROR_INCOMPATIBLE_DRIVER VK_ERROR_FORMAT_NOT_SUPPORTED VK_ERROR_UNKNOWN
VK_ERROR_SURFACE_LOST_KHR VK_ERROR_NATIVE_WINDOW_IN_USE_KHR
EGL_NOT_INITIALIZED EGL_BAD_ACCESS EGL_BAD_ALLOC EGL_BAD_ATTRIBUTE EGL_BAD_CONFIG EGL_BAD_CONTEXT
EGL_BAD_CURRENT_SURFACE EGL_BAD_DISPLAY EGL_BAD_MATCH EGL_BAD_NATIVE_PIXMAP EGL_BAD_NATIVE_WINDOW
EGL_BAD_PARAMETER EGL_BAD_SURFACE EGL_CONTEXT_LOST
vkCreateInstance vkEnumeratePhysicalDevices vkCreateDevice vkGetInstanceProcAddr vkGetDeviceProcAddr
eglInitialize eglGetDisplay eglCreateContext eglMakeCurrent InitializeSandbox InitializeVulkan
CreateVulkanInstance CreateVulkanDevice InitializeGLOneOff GetPlatformDisplay
VK_KHR_surface VK_KHR_xcb_surface VK_KHR_xlib_surface VK_KHR_wayland_surface VK_EXT_headless_surface
VK_KHR_swapchain VK_KHR_get_physical_device_properties2 VK_KHR_portability_enumeration
VK_KHR_external_memory VK_KHR_external_memory_fd VK_KHR_external_semaphore VK_KHR_external_semaphore_fd
VK_KHR_external_fence VK_KHR_external_fence_fd VK_KHR_maintenance1 VK_KHR_maintenance2
VK_KHR_maintenance3 VK_KHR_bind_memory2 VK_KHR_get_memory_requirements2 VK_KHR_sampler_ycbcr_conversion
VK_EXT_memory_budget VK_EXT_external_memory_host VK_EXT_graphics_pipeline_library
VK_EXT_robustness2 VK_EXT_transform_feedback VK_EXT_vertex_attribute_divisor
robustBufferAccess independentBlend geometryShader samplerAnisotropy textureCompressionBC
shaderClipDistance shaderCullDistance shaderInt16 shaderInt64`.split(/\s+/));
const nativeWords=new Set(`a an and are as at available backend bad buffer can cannot check checking compatible context
could create created creating creation current denied device devices did display driver egl enable enabled enabling
enumerate enumerating error extension extensions failed failing failure feature features find found from function gpu
has have incompatible initialize initialized initializing initialization instance insufficient internal invalid is it
layer layers library loader loading lost memory missing native need needed no not null of on one only operation
out permission physical present process required requires result return returned returning sandbox selected selecting
selection shader shared supported support surface system the this to unable unavailable unknown unsupported usable
use using valid vendor version vulkan was were with without would code errno`.split(/\s+/));
const nativeSourceFiles=new Set(['Display.cpp','DisplayVk.cpp','RendererVk.cpp','vk_renderer.cpp','vulkan_functions.cpp',
 'angle_platform_impl.cc','gl_display.cc','gl_surface_egl.cc','gl_factory.cc','gpu_init.cc','gpu_process_host.cc',
 'viz_main_impl.cc','shared_context_state.cc','vulkan_implementation.cc','vulkan_implementation_angle.cc',
 'vulkan_instance.cc','vulkan_device_queue.cc']);
const nativeLimits=Object.freeze({inputBytes:262144,lineBytes:8192,events:32,excerptBytes:512});
const nativeResults=new Set([...Array.from({length:19},(_,index)=>index-13),
 ...Array.from({length:15},(_,index)=>12288+index),-1000000000,-1000000001]);
export const validOutputDirectory=value=>typeof value==='string'&&/^\/world-storage\/webgl-init-[A-Za-z0-9_-]{1,80}$/.test(value);
export function safeNativeDetail(raw,{source='BROWSER_STDERR'}={}) {
 if(!['BROWSER_STDERR','WEBGL_CONTEXT_CREATION_EVENT'].includes(source))return null;
 const bytes=Buffer.isBuffer(raw)?raw:Buffer.from(String(raw));
 if(bytes.length>nativeLimits.lineBytes)return null;
 const text=bytes.toString('utf8'),words=text.match(/[A-Za-z_][A-Za-z_0-9]*/g)??[];
 if(/\b(?:argv|command[_ ]?line|environment|environ)\b|(?:^|\s)--[A-Za-z]/i.test(text))return null;
 const native=words.some(word=>nativeSymbols.has(word));
 if(!native&&!(source==='WEBGL_CONTEXT_CREATION_EVENT'&&/context/i.test(text)))return null;
 if(!classify(text).length&&!/error|fail|not|unsupported|missing|denied|unable/i.test(text))return null;
 const evidence={source,categories:classify(text),sha256:sha(bytes),bytes:bytes.length,
  excerptFormat:'FINITE_PUBLIC_VOCABULARY_REDACTED_NOT_RAW',rawOmitted:true,
  omittedTokens:0,sensitiveLineOmitted:false,excerptTruncated:false,sourceFrames:[]};
 // A native prefix cannot make an authentication-bearing line eligible for text export.
 if(/owner[_ -]?code|password|secret|token|authorization|bearer|cookie|api[_ -]?key|credential/i.test(text)){
  evidence.sensitiveLineOmitted=true;evidence.excerpt='[sensitive line omitted]';return evidence;
 }
 for(const match of text.matchAll(/\b([A-Za-z_]+\.(?:cc|cpp))(?::|\()(\d{1,5})\)?/g)){
  if(nativeSourceFiles.has(match[1])&&evidence.sourceFrames.length<4)evidence.sourceFrames.push({file:match[1],line:Number(match[2])});
 }
 const cleaned=text.replace(/\u001b\[[0-9;]*[A-Za-z]/g,' ')
  .replace(/(?:https?|file|ftp):\/\/\S+/gi,' [omitted] ')
  .replace(/(?:[A-Za-z]:[\\/]|\/)[^\s"'<>]*/g,' [omitted] ')
  .replace(/\[[^\]\n]{0,512}\]/g,' [omitted] ');
 const tokens=cleaned.match(/[A-Za-z_][A-Za-z_0-9]*|-?\d+|[():,=]/g)??[];
 const kept=[];let numberAllowed=false;
 for(const token of tokens){
  let value;
  if(nativeSymbols.has(token)){value=token;numberAllowed=false;}
  else if(nativeWords.has(token.toLowerCase())){value=token.toLowerCase();numberAllowed=['error','result','code','errno'].includes(value);}
  else if(/^-?\d+$/.test(token)&&numberAllowed&&nativeResults.has(Number(token))){value=String(Number(token));numberAllowed=false;}
  else if(/^[():,=]$/.test(token)){value=token;}
  else{value='[omitted]';evidence.omittedTokens++;numberAllowed=false;}
  if(value==='[omitted]'&&kept.at(-1)==='[omitted]')continue;
  const next=[...kept,value].join(' ');
  if(Buffer.byteLength(next)>nativeLimits.excerptBytes){evidence.excerptTruncated=true;break;}
  kept.push(value);
 }
 evidence.excerpt=kept.join(' ');return evidence;
}
export function createNativeDetailCollector(){
 const events=[];let pending=Buffer.alloc(0),discardLine=false,bytesObserved=0,acceptedBytes=0,
  droppedLines=0,omittedEvents=0,ignoredLines=0,finished=false;
 const consume=line=>{const event=safeNativeDetail(line);if(!event){ignoredLines++;return;}
  if(events.length<nativeLimits.events)events.push(event);else omittedEvents++;};
 return {
  append(chunk){if(finished)return;const data=Buffer.from(chunk);bytesObserved+=data.length;
   const remaining=Math.max(0,nativeLimits.inputBytes-acceptedBytes),part=data.subarray(0,remaining);acceptedBytes+=part.length;
   let start=0;
   for(let i=0;i<=part.length;i++){if(i!==part.length&&part[i]!==10)continue;const piece=part.subarray(start,i);
    if(!discardLine){if(pending.length+piece.length>nativeLimits.lineBytes){pending=Buffer.alloc(0);discardLine=true;droppedLines++;}
     else pending=Buffer.concat([pending,piece]);}
    if(i<part.length){if(!discardLine)consume(pending);pending=Buffer.alloc(0);discardLine=false;}start=i+1;
   }
   // Never export an incomplete line cut by the total input limit.
   if(part.length<data.length&&pending.length){pending=Buffer.alloc(0);discardLine=true;droppedLines++;}
  },
  finish(){if(!finished){if(pending.length&&!discardLine)consume(pending);pending=Buffer.alloc(0);finished=true;}
   return {events,bytesObserved,acceptedBytes,inputLimitBytes:nativeLimits.inputBytes,lineLimitBytes:nativeLimits.lineBytes,
    eventLimit:nativeLimits.events,excerptLimitBytes:nativeLimits.excerptBytes,droppedLines,omittedEvents,ignoredLines,
    truncated:bytesObserved>acceptedBytes||droppedLines>0||omittedEvents>0,rawOmitted:true};}
 };
}
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
 check(validOutputDirectory(outputDirectory),'DIAG_FRESH_EXPORT_PATH_REQUIRED');
 const parent=path.dirname(outputDirectory);check(await fs.realpath(parent)===parent,'DIAG_EXPORT_PARENT_SYMLINK_FORBIDDEN');
 // Exclusive reservation prevents accidental reuse; a failed attempt is never retried.
 await fs.mkdir(outputDirectory,{mode:0o700});
 const report={schema:'WORLD_ENGINE_WEBGL_INITIALIZATION_DIAGNOSTIC_V1',status:'RUNNING',imageDigest:IMAGE_DIGEST,startedAt:new Date().toISOString(),contextAttempts:0,browserLaunches:0,renderedFrames:0,retries:0,stage:'PREPARATION',sourceJobId:'studio-891495c5c00dde815522baad54a6eb88',sourceJobIdMeaning:'COMPARISON_FAILED_JOB_NOT_THIS_DIAGNOSTIC',providerBillingStopControlled:false,limitations:['Context-only observation; no scene preparation, module imports, native draw, labels, frames or encoder.','No alternative flags or second context. Successful WebGL2 is not a 300-frame render PASS.','Export fsync and readback do not prove remote storage provider persistence.','Native excerpts retain only finite public graphics vocabulary; unknown reasons are omitted and excerpts are not full raw stderr.']};
 let browser,server,child,exitObserved=false,closeObserved=false,restoreSpawn=()=>{},stderrTail='',stderrBytes=0;
 const stderrHash=createHash('sha256'),categories=new Set(),nativeDetails=createNativeDetailCollector();
 const appendStderr=chunk=>{try{const data=Buffer.from(chunk);nativeDetails.append(data);const remaining=Math.max(0,1024*1024-stderrBytes);stderrBytes+=data.length;if(!remaining)return;const part=data.subarray(0,remaining);stderrHash.update(part);const sample=stderrTail+part.toString('utf8');classify(sample).forEach(code=>categories.add(code));stderrTail=sample.slice(-4096);}catch{report.stderrObserverError=true;}};
 try{
  await durableFile(outputDirectory,'RESERVATION.json',Buffer.from(JSON.stringify({schema:report.schema,status:'RESERVED_NOT_RUN',sourceJobId:report.sourceJobId,sourceJobIdMeaning:report.sourceJobIdMeaning,imageDigest:IMAGE_DIGEST,startedAt:report.startedAt,maxBrowserLaunches:1,maxContextAttempts:1,renderedFrames:0})+'\n'));
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
  report.webgl={available:context.available,events:context.events.map(safeTextEvidence),nativeDetails:context.events.slice(0,1).map(text=>safeNativeDetail(text,{source:'WEBGL_CONTEXT_CREATION_EVENT'})).filter(Boolean)};
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
  report.browserStderr={categories:[...categories].sort(),bytesObserved:stderrBytes,hashedBytes:Math.min(stderrBytes,1024*1024),sha256:stderrHash.digest('hex'),truncated:stderrBytes>1024*1024,rawOmitted:true,nativeDetails:nativeDetails.finish()};
  report.finishedAt=new Date().toISOString();report.stage='RESULT_WRITTEN';
  const bytes=Buffer.from(JSON.stringify(report,null,2)+'\n');await durableFile(outputDirectory,'WEBGL_DIAGNOSTIC.json',bytes);await durableFile(outputDirectory,'SHA256SUMS',Buffer.from(sha(bytes)+'  WEBGL_DIAGNOSTIC.json\n'));
 }
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2),output=args.find(value=>value.startsWith('--output='))?.slice('--output='.length);
 runOnce({outputDirectory:output,approved:args.includes('--approved-single-diagnostic')}).then(report=>{process.stdout.write(JSON.stringify({status:report.status,contextAttempts:report.contextAttempts,browserLaunches:report.browserLaunches,renderedFrames:0,resultFile:'WEBGL_DIAGNOSTIC.json'})+'\n');process.exitCode=report.status==='PASS_CONTEXT_ONLY'?0:2;}).catch(error=>{process.stdout.write(JSON.stringify({status:'BLOCKED',code:safeFailureCode(error?.message),rawOmitted:true})+'\n');process.exitCode=2;});
}
