/** One flat geographic camera and one approved map factory. No frame dissolve. */
import {createMapInfographicRenderer,createProofPreview,createProofFinal} from './renderer.mjs';
import {evaluateContinuousCameraFrame,cameraEase} from './camera_director_v2.mjs';

export const CONTINUOUS_CAMERA_GPU_VERSION='CAMERA_GPU_PIPELINE_V2';
const sizeKeys=['primaryWidth','secondaryWidth','primaryEdgeWidth','secondaryEdgeWidth','glowWidth','glowRadius','glowGain'];
const clamp=x=>Math.max(0,Math.min(1,x));

/** LOD follows actual source density/coverage, independently of timeline states. */
export function geographicTerrainLod(bounds,wideSource,regionalSource,width=1080,height=1920){
 const wb=wideSource.bounds,rb=regionalSource.bounds,d=wideSource.dimensions;
 const spacing=wideSource.pixelSpacing??[(wb[2]-wb[0])/d[0],(wb[3]-wb[1])/d[1]];
 const projectedPixelsPerTexel=Math.max(width*spacing[0]/(bounds[2]-bounds[0]),height*spacing[1]/(bounds[3]-bounds[1]));
 const ix=Math.max(0,Math.min(bounds[2],rb[2])-Math.max(bounds[0],rb[0]));
 const iy=Math.max(0,Math.min(bounds[3],rb[3])-Math.max(bounds[1],rb[1]));
 const coverageFraction=clamp(ix*iy/((bounds[2]-bounds[0])*(bounds[3]-bounds[1])));
 const densityReadiness=cameraEase(clamp((projectedPixelsPerTexel-.5)/.5));
 const coverageReadiness=cameraEase(coverageFraction);
 const weight=densityReadiness*coverageReadiness;
 return {weight,projectedPixelsPerTexel,coverageFraction,densityReadiness,coverageReadiness,
  method:'Source texel density and real geographic viewport coverage; C2 source-only handoff',
  sampling:'Same geographic coordinates before material, never completed-frame RGB',nativeSpacing:spacing};
}

export async function createContinuousCameraGpuPipeline({canvas,plans,cameraPlan,heightSource,width=1080,height=1920}){
 if(createProofPreview!==createProofFinal||createProofFinal!==createMapInfographicRenderer)throw Error('PREVIEW_FINAL_FACTORY_MISMATCH');
 if(width!==1080||height!==1920)throw Error('Continuous proof requires canonical output');
 console.info('CAMERA_V2_INIT START SINGLE_MAP_FACTORY');
 const factory=await createMapInfographicRenderer({canvas,plan:plans.REGIONAL,layoutPlan:plans.REGIONAL,
  contextTerrain:plans.CONTINENT.assets.terrain,contextGeometries:plans.CONTINENT.geometries,heightSource,width,height});
 console.info('CAMERA_V2_INIT END SINGLE_MAP_FACTORY');
 const gl=canvas.getContext('webgl2');
 if(!gl)throw Error('WEBGL2_CONTEXT_FAILED');
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 const params={dem:true,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
 let lastSignature=null,lastPixels=null,lastDiagnostic=null;
 function tokens(t){
  const a=plans.CONTINENT.theme,b=plans.REGIONAL.theme,result={};
  for(const key of sizeKeys)result[key]=a[key]+(b[key]-a[key])*t;
  result.markerSize=plans.CONTINENT.scale.marker.pixels+(plans.REGIONAL.scale.marker.pixels-plans.CONTINENT.scale.marker.pixels)*t;
  return result;
 }
 function drawFrame(frame){
  const state=evaluateContinuousCameraFrame(cameraPlan,frame),bounds=state.camera.flatBounds;
  const lod=geographicTerrainLod(bounds,plans.CONTINENT.assets.terrain,plans.REGIONAL.assets.terrain,width,height);
  const visual=tokens(state.easingProgress);
  const signature=JSON.stringify([bounds,lod.weight,visual,state.reveal]);
  if(lastSignature!==signature){
   factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
   factory.renderFrame({...params,reveal:state.reveal});
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('CONTINUOUS_CAMERA_GL_ERROR_'+error);
   lastPixels=null;lastSignature=signature;
  }
  const actualCamera=structuredClone(factory.evidence.cameraFrame);
  lastDiagnostic={...state,gpu:{stage:'SINGLE_GEOGRAPHIC_CAMERA',factoryCount:1,context:'WebGL2',glError:0,
   finishedFrameMix:false,projectionChange:false,actualCamera,actualReveal:structuredClone(factory.evidence.revealState),
   boundaryPixels:visual,terrainLod:lod,layoutFrozen:true,layoutVisible:state.reveal.location>0||state.reveal.title>0}};
  return lastDiagnostic;
 }
 function readPixels(){
  if(!lastPixels){lastPixels=factory.readPixels();const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('CONTINUOUS_READPIXELS_GL_ERROR_'+error);}
  return lastPixels;
 }
 return {drawFrame,readPixels,png:()=>canvas.toDataURL('image/png'),
  evidence:{version:CONTINUOUS_CAMERA_GPU_VERSION,context:gl.getParameter(gl.VERSION),
   gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
   factoryCount:1,previewFinalSameFactory:true,composition:'Single map factory; one actual geographic camera; raw source LOD only',
   finishedFrameMix:false,projectionChanges:0,frozenMaterialParameters:params,layoutLocked:true,softwareOnly:true,nvidia:'NOT_RUN',
   factories:{REGIONAL:factory.evidence}},get diagnostic(){return lastDiagnostic},dispose(){factory.dispose();}};
}
