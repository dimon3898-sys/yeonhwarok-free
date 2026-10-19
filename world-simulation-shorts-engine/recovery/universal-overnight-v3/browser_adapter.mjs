/** Original pixels first; optional source-backed owners inside the capture draw. */
import {bootLongRuntime as bootParent} from '/overnight-v3/parent_adapter.mjs';
import {readFrameContext} from '/completion-v2/frame_context.mjs';
import {compileVisualExtensions,createVisualExtensionsPass} from '/overnight-v3/visual_extensions.mjs';
import {completionProtectedGraphics} from '/completion-v2/event_flow_binding.mjs';
const digest=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value))))]
 .map(v=>v.toString(16).padStart(2,'0')).join('');
export async function bootLongRuntime(options={}){
 const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
 if(!response.ok)throw Error('OVERNIGHT_RUNTIME_CONFIG_REQUIRED');
 const config=await response.json(),profile=config.overnightV3,preview=config.overnightPreview,integrity=config.overnightIntegrity;
 if(profile?.schema!=='WORLD_ENGINE_OVERNIGHT_SAFE_V3'||profile.profile!=='OVERNIGHT_SAFE_V3'
  ||profile.operation!=='PREVIEW_5S'||preview?.range?.frameCount!==150
  ||integrity?.schema!=='WORLD_ENGINE_OVERNIGHT_RUNTIME_INTEGRITY_V3'
  ||await digest(profile)!==integrity.profileSHA256||await digest(preview)!==integrity.previewSHA256
  ||await digest(config.overnightSourceCatalog)!==integrity.catalogSHA256)
  throw Error('OVERNIGHT_BROWSER_BINDING_REQUIRED');
 const binding=await compileVisualExtensions({request:profile.visualExtensions,
  trustedSources:config.overnightSourceCatalog.trustedSources,fps:config.universalVideo.fps,
  totalFrames:config.universalVideo.totalFrames,allowSynthetic:false}),parent=await bootParent(options),
  pipeline=window.longVideoProof?.pipeline,canvas=document.querySelector('canvas');
 if(!pipeline||!canvas)throw Error('OVERNIGHT_ACTUAL_PARENT_PIPELINE_REQUIRED');
 const regionalResponse=await fetch('/inputs/regional.json',{cache:'no-store',redirect:'error'});
 if(!regionalResponse.ok)throw Error('OVERNIGHT_NATIVE_REGIONAL_REQUIRED');
 const regional=await regionalResponse.json(),pass=await createVisualExtensionsPass({canvas,binding}),
  draw=pipeline.drawFrame.bind(pipeline),dispose=pipeline.dispose.bind(pipeline);
 pipeline.drawFrame=async frame=>{
  if(!Number.isSafeInteger(frame)||frame<preview.range.startFrame||frame>=preview.range.endFrame)
   throw Error('OVERNIGHT_PREVIEW_FRAME_OUTSIDE_APPROVED_RANGE');
  const diagnostic=await draw(frame),native=readFrameContext(canvas),
   result=pass.drawFrame(frame,{project:pipeline.project,safeArea:regional.layout.safe,
    protectedGraphics:completionProtectedGraphics(diagnostic),
    parentGeographicFrontPresent:(diagnostic.area?.controls?.fronts?.length??0)>0,
    parentTerritoryFillPresent:(diagnostic.area?.controls?.areas?.length??0)>0,
    nativeBoundarySourceVerified:native?.frame===frame&&Array.isArray(native.boundarySegments),
    boundarySegments:native?.boundarySegments,internalBoundarySegments:native?.internalBoundarySegments,
    actualTerrainSnapshot:native?.actualTerrainSnapshot,nativeRoleCoverage:native?.nativeRoleCoverage,
    presentationScale:1});
  const gl=canvas.getContext('webgl2');gl.finish();const error=gl.getError();if(error)throw Error('OVERNIGHT_COMPOSITION_GL_ERROR_'+error);
  return{...diagnostic,overnightV3:{profile:profile.profile,profileSHA256:integrity.profileSHA256,
   sourceManifestSHA256:integrity.manifestSHA256,frame,visualExtensions:result,
   frameRangePreserved:true,sourceTimelineReset:false,actualGPUOutputVerified:false}};
 };
 pipeline.dispose=()=>{pass.dispose();dispose();};window.longVideoProof.dispose=pipeline.dispose;
 return{...parent,overnightV3:{profile:profile.profile,integrity,previewRange:preview.range,
  sourceOwnersReused:true,sourceTimelineReset:false,actualGPUOutputVerified:false}};
}
