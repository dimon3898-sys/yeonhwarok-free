/** Source-bound opt-in wrapper; all geographic motion and redraw APIs remain preserved owners. */
import {createProductionNativeCamera as originalFactory,nativeGraphicReservations,nativeBoundarySupport}
 from '/completion-v2/parent_camera.mjs';
import {geographicScaleVisualTokens} from '/modules/camera_gpu_pipeline_v5.mjs';
import {geographicTerrainLod} from '/modules/camera_gpu_pipeline_v2.mjs';
import {evaluateMovingLayout,validateVisibleMovingLayout} from '/modules/moving_layout_v4.mjs';
import {mergeIntegrationProductionProfile,loadIntegrationRuntimeConfig} from '/integration-v1/presentation.mjs';
import {createCompletionNativeCamera,normalizeCompletionCamera} from '/completion-v2/camera_extension.mjs';
import {publishNativeFrame} from '/completion-v2/frame_context.mjs';
const response=await fetch('/runtime-config.json',{cache:'no-store',redirect:'error'});
if(!response.ok)throw Error('COMPLETION_CAMERA_RUNTIME_HTTP_FAILED');
const config=await response.json(),completion=config?.completionV2;
if(completion?.schema!=='WORLD_ENGINE_UNIVERSAL_COMPLETION_V2'||completion.profile!=='VISUAL_UNIFIED_COMPLETION_V2')
 throw Error('COMPLETION_CAMERA_EXPLICIT_RUNTIME_REQUIRED');
const camera=normalizeCompletionCamera(completion.camera),integration=await loadIntegrationRuntimeConfig();
export function createProductionNativeCamera(input){
 const profile=mergeIntegrationProductionProfile(input.profile,integration.visualProfile);
 const owner=createCompletionNativeCamera({...input,profile},{camera,originalFactory,operations:{
  geographicScaleVisualTokens,geographicTerrainLod,evaluateMovingLayout,validateVisibleMovingLayout,
  nativeGraphicReservations,nativeBoundarySupport}});
 return{...owner,drawNative(globalFrame){
  const result=owner.drawNative(globalFrame);
  // The preserved adapter removes these segments only from its public
  // diagnostic. Keep exact private frame context for later protected overlays.
  publishNativeFrame({frame:globalFrame,native:result,boundarySegments:result.boundarySegments});
  return result;
 }};
}
export {nativeGraphicReservations,nativeBoundarySupport};
