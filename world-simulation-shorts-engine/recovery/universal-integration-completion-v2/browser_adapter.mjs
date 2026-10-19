/** Reuse the entire preserved map; append only supplied-data owners before capture. */
import {bootLongRuntime as bootParent} from '/completion-v2/parent_adapter.mjs';
import {setFrameContext,readFrameContext,clearFrameContext} from '/completion-v2/frame_context.mjs';
import {compileCompletionEventFlow,createCompletionEventFlowPass,completionProtectedGraphics} from '/completion-v2/event_flow_binding.mjs';
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))]
 .map(v=>v.toString(16).padStart(2,'0')).join('');
export async function bootLongRuntime(options={}){
 const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('COMPLETION_RUNTIME_CONFIG_REQUIRED');
 const config=await response.json(),completion=config.completionV2,integrity=config.completionIntegrity;
 if(completion?.schema!=='WORLD_ENGINE_UNIVERSAL_COMPLETION_V2'||completion.profile!=='VISUAL_UNIFIED_COMPLETION_V2'
  ||integrity?.schema!=='WORLD_ENGINE_COMPLETION_RUNTIME_INTEGRITY_V2'
  ||await digest(completion)!==integrity.profileSHA256
  ||await digest(config.completionFrontierMotion)!==integrity.motionSHA256
  ||await digest(config.completionSourceCatalog)!==integrity.catalogSHA256)throw Error('COMPLETION_BROWSER_PROFILE_BINDING_REQUIRED');
 const binding=compileCompletionEventFlow(completion.eventFlow,{fps:config.universalVideo.fps,
  totalFrames:config.universalVideo.totalFrames,trustedSources:config.completionSourceCatalog.trustedSources,allowSynthetic:false}),
  parent=await bootParent(options),proof=window.longVideoProof,pipeline=proof?.pipeline,canvas=document.querySelector('canvas');
 if(!pipeline||!canvas)throw Error('COMPLETION_ACTUAL_PARENT_PIPELINE_REQUIRED');
 const [regional,input]=await Promise.all(['/inputs/regional.json','/inputs/input-manifest.json'].map(async url=>{
  const r=await fetch(url,{cache:'no-store',redirect:'error'});if(!r.ok)throw Error('COMPLETION_NATIVE_INPUT_REQUIRED');return r.json();})),
  hasData=['events','flows','areas'].some(key=>binding.request[key].length),
  extra=hasData?await createCompletionEventFlowPass({canvas,binding,theme:regional.theme}):null,
  draw=pipeline.drawFrame.bind(pipeline),dispose=pipeline.dispose.bind(pipeline);
 pipeline.drawFrame=async frame=>{
  setFrameContext(canvas,{frame});
  const diagnostic=await draw(frame),reservations=completionProtectedGraphics(diagnostic),native=readFrameContext(canvas);
  if(hasData&&!Array.isArray(native?.boundarySegments))throw Error('COMPLETION_NATIVE_BOUNDARY_CONTEXT_REQUIRED');
  const result=extra?.drawFrame(frame,{project:pipeline.project,cameraState:native?.native??diagnostic.camera,
    scalePlan:regional,heightSource:input.heightSource??null,safeArea:regional.layout.safe,protectedGraphics:reservations,
    boundarySegments:native.boundarySegments,nativeBoundarySourceVerified:native.frame===frame&&Array.isArray(native.boundarySegments),
    parentGeographicFrontPresent:(diagnostic.area?.controls?.fronts?.length??0)>0})??{frame,events:[],flows:[],areas:[],
     reason:'NO_SOURCE_BOUND_ADDITIONAL_EVENTS_REQUESTED',gpuOutputVerified:false};
  const gl=canvas.getContext('webgl2');gl.finish();const error=gl.getError();if(error)throw Error('COMPLETION_COMPOSITION_GL_ERROR_'+error);
  return{...diagnostic,completionV2:{profile:completion.profile,profileSHA256:integrity.profileSHA256,
   sourceManifestSHA256:integrity.manifestSHA256,frame,eventFlow:result,
   frameContextBound:true,finishedFrameBlit:false,actualOutputVerified:false}};
 };
 pipeline.dispose=()=>{extra?.dispose();clearFrameContext(canvas);dispose();};
 // Original capture refers to this pipeline object, so it invokes the wrapper
 // before its own readPixels. No finished image is overlaid after capture.
 proof.dispose=pipeline.dispose;
 return{...parent,completionV2:{profile:completion.profile,integrity,eventFlowDataPresent:hasData,
  originalMapRendererCalled:true,newRendererCopied:false,actualGPUOutputVerified:false}};
}
