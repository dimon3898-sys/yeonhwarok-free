/** Fixed-schema diagnostics only. Never exports arbitrary messages or stacks. */
import {open,rename,unlink,lstat} from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import path from 'node:path';

export const SCHEMA='WORLD_ENGINE_CAPTURE_OPERATIONS_V1';
export const OPERATIONS=Object.freeze(['INPUT_CANVAS','RUNTIME_IMPORT','RUNTIME_CREATE','WEBGL_CONTEXT',
 'RENDERER_IDENTIFICATION','MAP_TEXTURE_PREPARATION','GRAPHICS_PREPARATION','NATIVE_GUARD_IMPORT',
 'NATIVE_CONTEXT_PROOF','DRAW','READBACK','PROOF_VALIDATION','PNG','ENCODER','EXPORT','CLEANUP']);
export const SOURCES=Object.freeze(['CAPTURE_ADAPTER','PRESENTATION_RUNTIME','NATIVE_GUARD']);
export const FAILURE_KINDS=Object.freeze(['DOMAIN_ERROR','UNCLASSIFIED_EXCEPTION','MODULE_IMPORT_FAILURE',
 'ASSET_HTTP_FAILURE','PAGE_TIMEOUT','PAGE_CRASH','PAGE_CLOSED','EVALUATION_TRANSPORT_FAILURE','STORAGE_FAILURE']);
export const EXCEPTIONS=Object.freeze(['Error','TypeError','RangeError','ReferenceError','SyntaxError','TimeoutError','DOMException','UNKNOWN']);
export const PUBLIC_CODES=Object.freeze([
 'UNCLASSIFIED_EXCEPTION','CAPTURE_ASSET_HTTP_FAILED','CAPTURE_PAGE_TIMEOUT','CAPTURE_PAGE_CRASH',
 'CAPTURE_PAGE_CLOSED','CAPTURE_EVALUATION_TRANSPORT_FAILED','CAPTURE_DIAGNOSTIC_SCHEMA_INVALID',
 'DIAGNOSTIC_STORAGE_PERMISSION','DIAGNOSTIC_STORAGE_NO_SPACE','DIAGNOSTIC_STORAGE_TOO_LARGE','DIAGNOSTIC_STORAGE_IO',
 'GCUBE_ACTUAL_NATIVE_RUNTIME_REQUIRED','GCUBE_ACTUAL_RENDERER_INFO_REQUIRED','GCUBE_INITIAL_SEGMENT_REQUIRED',
 'GCUBE_NATIVE_CONTEXT_REQUIRED','GCUBE_NATIVE_DRAW_FAILED','GCUBE_NATIVE_READBACK_INVALID',
 'GCUBE_NATIVE_REPEATED_PIXEL_MISMATCH','GCUBE_NATIVE_STABILITY_DRAWS_INVALID','GCUBE_NATIVE_STABILITY_PROOF_REQUIRED',
 'GCUBE_NVIDIA_RENDERER_REQUIRED','GCUBE_NVIDIA_VULKAN_REQUIRED','GCUBE_STABILITY_INITIAL_FRAME_REQUIRED',
 'GCUBE_REVIEW_DEADLINE_EXCEEDED','UP2_WEBGL2_REQUIRED','UP2_BLACK_FRAME','UP2_FRAME_GL_ERROR',
 'UP2_ENCODER_EARLY_EXIT','UP2_ENCODER_CLOSED','UP2_PRIVATE_PLAYWRIGHT_REQUIRED','UP2_ACTUAL_DRAW_GL_ERROR',
 'UP2_ACTUAL_FEATURE_PIXELS_MISSING','UP2_ACTUAL_NATIVE_SOURCE_REQUIRED','UP2_ANALYSIS_PROJECTION_MISMATCH',
 'UP2_AREA_NOT_DRAWN','UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE','UP2_BROWSER_CAMERA_TRANSPORT_DRIFT',
 'UP2_CAMERA_KEYFRAME_TRANSPORT_CHANGED','UP2_CAMERA_OWNER_REQUIRED','UP2_CANONICAL_CANVAS_REQUIRED',
 'UP2_CPU_CAMERA_SAMPLES_REQUIRED','UP2_CPU_CAMERA_SAMPLE_INVALID','UP2_CURRENT_COORDINATE_MISMATCH',
 'UP2_CURRENT_LAYOUT_FAILED','UP2_CURRENT_SOURCE_COVERAGE_FAILED','UP2_ENGINE_FRAME_BINDING_REQUIRED',
 'UP2_ENGINE_UNSUPPORTED','UP2_FLOW_OBJECT_NOT_DRAWN','UP2_FLOW_ROUTE_NOT_DRAWN','UP2_FRAME_NOT_DRAWN',
 'UP2_FRAME_RANGE','UP2_FREE_FRAME_SCOPE','UP2_MARKER_RESERVATION_CAPACITY','UP2_ORIGINAL_MARKER_DESIGN_REQUIRED',
 'UP2_SOURCE_BINDING_REQUIRED','UP2_SOURCE_MUTATION','UP2_SUPPLIED_MARKER_FULL_ROI_OUTSIDE_SAFE']);
const frame=n=>Number.isSafeInteger(n)&&n>=0&&n<180?n:null;
export function safeFailure(value){
 if(!value||typeof value!=='object'||!OPERATIONS.includes(value.operationId)||!SOURCES.includes(value.sourceId))return null;
 const code=PUBLIC_CODES.includes(value.errorCode)?value.errorCode:'UNCLASSIFIED_EXCEPTION';
 return{operationId:value.operationId,sourceId:value.sourceId,line:null,column:null,frameIndex:frame(value.frameIndex),
  failureKind:FAILURE_KINDS.includes(value.failureKind)?value.failureKind:'UNCLASSIFIED_EXCEPTION',
  errorCode:code,recognized:code!=='UNCLASSIFIED_EXCEPTION',exceptionType:EXCEPTIONS.includes(value.exceptionType)?value.exceptionType:'UNKNOWN'};
}
export function classifyException(error,operationId='INPUT_CANVAS',sourceId='CAPTURE_ADAPTER',frameIndex=null){
 const disk=['EACCES','EPERM','ENOSPC','EDQUOT','EFBIG','EIO'].includes(error?.code);
 const exact=disk?storageCode(error):PUBLIC_CODES.includes(error?.message)?error.message:'UNCLASSIFIED_EXCEPTION';
 return safeFailure({operationId,sourceId,frameIndex,errorCode:exact,exceptionType:error?.name,
  failureKind:disk?'STORAGE_FAILURE':exact==='CAPTURE_ASSET_HTTP_FAILED'?'ASSET_HTTP_FAILURE':exact!=='UNCLASSIFIED_EXCEPTION'?'DOMAIN_ERROR':
   ['RUNTIME_IMPORT','NATIVE_GUARD_IMPORT'].includes(operationId)?'MODULE_IMPORT_FAILURE':'UNCLASSIFIED_EXCEPTION'});
}
export function storageCode(error){
 return ['EACCES','EPERM'].includes(error?.code)?'DIAGNOSTIC_STORAGE_PERMISSION':
  ['ENOSPC','EDQUOT'].includes(error?.code)?'DIAGNOSTIC_STORAGE_NO_SPACE':
  error?.code==='EFBIG'?'DIAGNOSTIC_STORAGE_TOO_LARGE':'DIAGNOSTIC_STORAGE_IO';
}
export async function atomicPrivateJSON(file,value,{maximum=16384}={}){
 const bytes=Buffer.from(JSON.stringify(value)+'\n');
 if(bytes.length>maximum)throw Object.assign(new Error('DIAGNOSTIC_STORAGE_TOO_LARGE'),{code:'EFBIG'});
 const parent=path.dirname(file),info=await lstat(parent);
 if(!info.isDirectory()||info.isSymbolicLink()||info.uid!==process.getuid()||(info.mode&0o077))
  throw Object.assign(new Error('DIAGNOSTIC_STORAGE_PERMISSION'),{code:'EACCES'});
 const temporary=path.join(parent,'.diagnostic-'+randomUUID()+'.tmp');let handle;
 try{
  handle=await open(temporary,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
  await handle.writeFile(bytes);await handle.sync();await handle.close();handle=null;
  await rename(temporary,file);
  const directory=await open(parent,constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);
  try{await directory.sync();}finally{await directory.close();}
 }finally{await handle?.close();await unlink(temporary).catch(error=>{if(error.code!=='ENOENT')throw error;});}
}
export function createRecorder({outputRoot,runId=null,imageDigest=null,sceneSHA256=null,write=atomicPrivateJSON}={}){
 const state={schema:SCHEMA,runId:/^studio-[a-f0-9]{32}$/.test(runId??'')?runId:null,
  imageDigest:/^sha256:[a-f0-9]{64}$/.test(imageDigest??'')?imageDigest:null,
  sceneSHA256:/^[a-f0-9]{64}$/.test(sceneSHA256??'')?sceneSHA256:null,
  operationId:null,lastCompletedOperation:null,frameIndex:null,firstFailure:null,cleanupFailure:null,
  nativeProofCompleted:false,renderedFrames:0,sequence:0,evidenceStatus:'NOT_WRITTEN',storageError:null};
 let chain=Promise.resolve();
 function persist(){
  chain=chain.then(async()=>{
   state.sequence++;state.evidenceStatus='LOCAL_ATOMIC_CHECKPOINT';
   try{await write(path.join(outputRoot,'CAPTURE_OPERATION_CHECKPOINT.json'),structuredClone(state));}
   catch(error){state.storageError=storageCode(error);state.evidenceStatus='LOCAL_WRITE_FAILED';}
  });return chain.then(()=>({ok:state.evidenceStatus==='LOCAL_ATOMIC_CHECKPOINT',code:state.storageError}));
 }
 const api={snapshot:()=>structuredClone(state),persist,
  async event(raw){
   if(!raw||!OPERATIONS.includes(raw.operationId)||!['START','END','FAIL','CLEANUP_FAIL'].includes(raw.phase))
    throw Error('CAPTURE_DIAGNOSTIC_SCHEMA_INVALID');
   state.operationId=raw.operationId;state.frameIndex=frame(raw.frameIndex);
   if(raw.phase==='END')state.lastCompletedOperation=raw.operationId;
   const failure=safeFailure(raw.failure);
   if(raw.phase==='FAIL'&&failure&&!state.firstFailure)state.firstFailure=failure;
   if(raw.phase==='CLEANUP_FAIL'&&failure&&!state.cleanupFailure)state.cleanupFailure=failure;
   return persist();
  },
  async fail(failure,{cleanup=false}={}){return api.event({operationId:failure?.operationId??'INPUT_CANVAS',phase:cleanup?'CLEANUP_FAIL':'FAIL',failure});},
  async completeFrame(count){if(Number.isSafeInteger(count)&&count>=0&&count<=180)state.renderedFrames=count;return persist();},
  async proofCompleted(){state.nativeProofCompleted=true;return persist();}
 };return api;
}

// Self-contained function serialized by Playwright; no Node closures cross realms.
export function initializeBrowserDiagnostics(config){
 const{codes,operations,sources,exceptions}=config;let firstFailure=null,cleanupFailure=null,active='INPUT_CANVAS',source='CAPTURE_ADAPTER',frameIndex=null;
 function classify(error){const known=codes.includes(error?.message),code=known?error.message:'UNCLASSIFIED_EXCEPTION';
  return{operationId:active,sourceId:source,line:null,column:null,frameIndex,errorCode:code,recognized:known,
   exceptionType:exceptions.includes(error?.name)?error.name:'UNKNOWN',failureKind:code==='CAPTURE_ASSET_HTTP_FAILED'?'ASSET_HTTP_FAILURE':
    known?'DOMAIN_ERROR':['RUNTIME_IMPORT','NATIVE_GUARD_IMPORT'].includes(active)?'MODULE_IMPORT_FAILURE':'UNCLASSIFIED_EXCEPTION'};}
 async function send(phase,failure=null){const result=await window.__weCaptureCheckpoint({phase,operationId:active,sourceId:source,frameIndex,failure});
  if(result?.ok!==true&&!firstFailure)throw Error(codes.includes(result?.code)?result.code:'DIAGNOSTIC_STORAGE_IO');}
 const api={
  async run(operationId,task,{sourceId='CAPTURE_ADAPTER',frame=null}={}){
   if(!operations.includes(operationId)||!sources.includes(sourceId))throw Error('CAPTURE_DIAGNOSTIC_SCHEMA_INVALID');
   const previous=[active,source,frameIndex];active=operationId;source=sourceId;frameIndex=Number.isSafeInteger(frame)&&frame>=0&&frame<180?frame:null;
   try{await send('START');const value=await task();await send('END');[active,source,frameIndex]=previous;return value;}
   catch(error){if(!firstFailure)firstFailure=classify(error);await send('FAIL',firstFailure).catch(()=>{});throw error;}
  },
  async cleanup(task){try{await task();}catch(error){const previous=[active,source];active='CLEANUP';
    if(!cleanupFailure)cleanupFailure=classify(error);await send('CLEANUP_FAIL',cleanupFailure).catch(()=>{});[active,source]=previous;}},
  async capture(task){try{return{schema:config.schema,ok:true,value:await task(),firstFailure,cleanupFailure};}
   catch(error){if(!firstFailure)firstFailure=classify(error);await send('FAIL',firstFailure).catch(()=>{});
    return{schema:config.schema,ok:false,firstFailure,cleanupFailure};}}
 };Object.defineProperty(window,'__worldEngineDiagnostics',{value:Object.freeze(api),configurable:false});
}
export async function attachPageDiagnostics(page,recorder){
 await page.exposeFunction('__weCaptureCheckpoint',raw=>recorder.event(raw));
 await page.evaluate(initializeBrowserDiagnostics,{schema:SCHEMA,codes:PUBLIC_CODES,operations:OPERATIONS,sources:SOURCES,exceptions:EXCEPTIONS});
}
export async function evaluateDiagnosed(page,callback,arg,{recorder,timeoutMs}={}){
 let crashed=false,timer;const onCrash=()=>{crashed=true;};page.on('crash',onCrash);
 try{
  if(!Number.isFinite(timeoutMs)||timeoutMs<=0)throw Object.assign(new Error('CAPTURE_PAGE_TIMEOUT'),{name:'TimeoutError'});
  const result=await Promise.race([page.evaluate(callback,arg),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Object.assign(new Error('CAPTURE_PAGE_TIMEOUT'),{name:'TimeoutError'})),Math.min(timeoutMs,2147483647));})]);
  if(result?.schema!==SCHEMA||typeof result.ok!=='boolean')throw Error('CAPTURE_DIAGNOSTIC_SCHEMA_INVALID');
  const failure=safeFailure(result.firstFailure);
  if(result.ok===false){if(!failure)throw Error('CAPTURE_DIAGNOSTIC_SCHEMA_INVALID');await recorder.fail(failure);throw Object.assign(Error(failure.errorCode),{captureFailure:failure});}
  if(result.cleanupFailure)await recorder.fail(safeFailure(result.cleanupFailure),{cleanup:true});
  return result.value;
 }catch(error){
  if(error?.captureFailure)throw error;
  const state=recorder.snapshot(),kind=crashed?'PAGE_CRASH':page.isClosed()?'PAGE_CLOSED':error?.name==='TimeoutError'?'PAGE_TIMEOUT':'EVALUATION_TRANSPORT_FAILURE';
  const code={PAGE_CRASH:'CAPTURE_PAGE_CRASH',PAGE_CLOSED:'CAPTURE_PAGE_CLOSED',PAGE_TIMEOUT:'CAPTURE_PAGE_TIMEOUT',EVALUATION_TRANSPORT_FAILURE:'CAPTURE_EVALUATION_TRANSPORT_FAILED'}[kind];
  const failure=safeFailure({operationId:state.operationId??'INPUT_CANVAS',sourceId:'CAPTURE_ADAPTER',frameIndex:state.frameIndex,errorCode:code,failureKind:kind,exceptionType:error?.name});
  await recorder.fail(failure);throw Object.assign(Error(code),{captureFailure:failure});
 }finally{clearTimeout(timer);page.off('crash',onCrash);}
}
export async function preserveCleanup(recorder,tasks){
 for(const task of tasks)try{await task();}catch(error){await recorder.fail(classifyException(error,'CLEANUP'),{cleanup:true});}
 return recorder.snapshot();
}
