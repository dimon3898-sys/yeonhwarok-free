/** Bounded observation only. No shaders, poses, geometry or draw calls are added. */
const state={configured:false,frame:null,samples:new Set(),factories:{},draws:{},snapshots:[]};
const fail=code=>{throw Error(code);};
export function configureObservation({sampleFrames}){
 if(state.configured||!Array.isArray(sampleFrames)||sampleFrames.length!==3
  ||sampleFrames.some(f=>!Number.isSafeInteger(f)||f<0)||new Set(sampleFrames).size!==3)
  fail('RECONCILIATION_EXACT_OBSERVATION_CONFIG_REQUIRED');
 state.samples=new Set(sampleFrames);state.configured=true;
}
export function observedFactory(kind){
 if(!state.configured)fail('RECONCILIATION_OBSERVER_NOT_CONFIGURED');
 state.factories[kind]=(state.factories[kind]??0)+1;
}
export function beginObservation(frame){
 if(!state.configured||state.frame!==null||!Number.isSafeInteger(frame)||frame<0)
  fail('RECONCILIATION_OBSERVATION_CLOCK_REQUIRED');
 state.frame=frame;state.draws={};state.snapshots=[];
}
function pixels(canvas){
 const gl=canvas.getContext('webgl2');
 if(!gl||canvas.width!==1080||canvas.height!==1920||gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING)!==null)
  fail('RECONCILIATION_ACTUAL_NATIVE_FRAMEBUFFER_REQUIRED');
 // Keep all bindings, state and source pixels unchanged. Existing passes own
 // the current framebuffer; snapshots are read-only and only at three frames.
 gl.finish();if(gl.getError())fail('RECONCILIATION_SOURCE_GL_ERROR');
 const raw=new Uint8Array(canvas.width*canvas.height*4);
 gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,raw);
 if(gl.getError())fail('RECONCILIATION_OBSERVATION_READ_FAILED');
 return raw;
}
export function observeExistingDraw(kind,canvas,operation){
 if(typeof operation!=='function')fail('RECONCILIATION_ACTUAL_DRAW_FUNCTION_REQUIRED');
 // Original source/layout owners make boot-time calls too. They are not
 // counted as captured global frames.
 if(state.frame===null)return operation();
 const sampled=state.samples.has(state.frame),before=sampled?pixels(canvas):null;
 const result=operation();state.draws[kind]=(state.draws[kind]??0)+1;
 if(sampled)state.snapshots.push({kind,before,after:pixels(canvas)});
 return result;
}
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
 .map(b=>b.toString(16).padStart(2,'0')).join('');
export async function finishObservation(){
 if(state.frame===null)fail('RECONCILIATION_OBSERVATION_NOT_ACTIVE');
 const stages=[];
 for(const row of state.snapshots){
  let changedPixels=0;
  for(let i=0;i<row.before.length;i+=4)
   if(row.before[i]!==row.after[i]||row.before[i+1]!==row.after[i+1]
    ||row.before[i+2]!==row.after[i+2]||row.before[i+3]!==row.after[i+3])changedPixels++;
  stages.push({kind:row.kind,beforeRGBA_SHA256:await digest(row.before),
   afterRGBA_SHA256:await digest(row.after),changedPixels,
   evidence:'ACTUAL_EXISTING_DRAW_AND_READPIXELS_NOT_FACTORY_PRESENCE'});
 }
 const result={schema:'WORLD_ENGINE_ACTUAL_PASS_OBSERVATION_V1',frame:state.frame,
  instantiatedFactories:{...state.factories},executedDraws:{...state.draws},pixelStages:stages,
  sampledForStagePixels:state.samples.has(state.frame),sourcePixelsModified:false,
  physicalNvidiaVerified:false,visualQualityApproved:false};
 state.frame=null;state.snapshots=[];return result;
}
