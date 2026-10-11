/** Explicit single-geographic-camera GPU graph consuming separate plans.
 * No Camera/Reveal mathematics, completed-frame substitution or visual tuning.
 */
import * as THREE from '/three.js';
import {createMapInfographicRenderer,createProofPreview,createProofFinal} from './renderer.mjs';
import {geographicTerrainLod} from './camera_gpu_pipeline_v2.mjs';
import {evaluateReferenceCameraFrame} from './camera_director_v4.mjs';
import {compileMovingLayoutContract,evaluateMovingLayout} from './moving_layout_v4.mjs';
import {compileGuidedRevealPlan,evaluateGuidedRevealFrame} from './camera_reveal_v4.mjs';
import {createMovingGraphicPass} from './graphic_motion_pass_v4.mjs';

export const GUIDED_CAMERA_GPU_VERSION='CAMERA_GPU_PIPELINE_V4';
const sizeKeys=['primaryWidth','secondaryWidth','primaryEdgeWidth','secondaryEdgeWidth','glowWidth','glowRadius','glowGain'];
const clamp=value=>Math.max(0,Math.min(1,value));
const sameBounds=(a,b)=>a.length===b.length&&a.every((value,index)=>value===b[index]);

/** Approved Scale visual tokens follow geographic size, independently of time. */
export function geographicScaleVisualTokens(bounds,plans){
 const wide=plans.CONTINENT.framing.bounds,regional=plans.REGIONAL.framing.bounds;
 const wideWidth=wide[2]-wide[0],regionalWidth=regional[2]-regional[0],currentWidth=bounds[2]-bounds[0];
 if(currentWidth<=0||wideWidth<=regionalWidth)throw Error('INVALID_GEOGRAPHIC_SCALE_TOKEN_EXTENTS');
 const progress=sameBounds(bounds,regional)?1:clamp(Math.log(wideWidth/currentWidth)/Math.log(wideWidth/regionalWidth));
 const result={};
 for(const key of sizeKeys){
  const a=plans.CONTINENT.theme[key],b=plans.REGIONAL.theme[key];
  if(!Number.isFinite(a)||!Number.isFinite(b))throw Error('FROZEN_SCALE_TOKEN_MISSING');
  result[key]=a+(b-a)*progress;
 }
 const a=plans.CONTINENT.scale.marker.pixels,b=plans.REGIONAL.scale.marker.pixels;
 result.markerSize=a+(b-a)*progress;
 return result;
}

export async function createGuidedCameraGpuPipeline({canvas,plans,cameraPlan,scene,heightSource,contextTerrain=null,width=1080,height=1920}){
 if(createProofPreview!==createProofFinal||createProofFinal!==createMapInfographicRenderer)throw Error('PREVIEW_FINAL_FACTORY_MISMATCH');
 if(width!==1080||height!==1920)throw Error('CANONICAL_CAMERA_PROOF_OUTPUT_REQUIRED');
 if(!sameBounds(cameraPlan.intent.finalExtent,plans.REGIONAL.framing.bounds))throw Error('APPROVED_REGIONAL_FRAMING_CHANGED');
 if(scene.primary_region_id!==plans.REGIONAL.primary)throw Error('SCENE_PRIMARY_REGION_MISMATCH');
 const wideSource=contextTerrain??plans.CONTINENT.assets.terrain;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WEBGL2_CONTEXT_FAILED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 console.info('CAMERA_V4_INIT START SINGLE_MAP_FACTORY');
 const factory=await createMapInfographicRenderer({canvas,plan:plans.REGIONAL,layoutPlan:plans.REGIONAL,
  contextTerrain:wideSource,contextGeometries:plans.CONTINENT.geometries,heightSource,width,height,
  outputRenderer:renderer,outputTarget:null});
 const graphics=await createMovingGraphicPass({renderer,factory,width,height});
 const layoutContract=compileMovingLayoutContract({regionalPlan:plans.REGIONAL,measuredLayout:factory.evidence.layout});
 const visualTokensForFrame=state=>geographicScaleVisualTokens(state.camera.flatBounds,plans);
 const revealPlan=compileGuidedRevealPlan({cameraPlan,scene,layoutContract,evaluateCamera:evaluateReferenceCameraFrame,visualTokensForFrame});
 console.info('CAMERA_V4_INIT END SINGLE_MAP_FACTORY_AND_EXPLICIT_GRAPHIC_PASS');
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 const params={dem:true,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
 let lastSignature=null,lastPixels=null,lastDiagnostic=null,lastGraphics=null;
 function drawFrame(frame){
  const camera=evaluateReferenceCameraFrame(cameraPlan,frame),bounds=camera.camera.flatBounds;
  const visual=visualTokensForFrame(camera);
  const layout=evaluateMovingLayout(layoutContract,camera,{markerSize:visual.markerSize,boundaryTokens:visual});
  const guided=evaluateGuidedRevealFrame(revealPlan,camera,layout);
  const reveal=guided.reveal;
  if(reveal.primary!==1||camera.primaryMaterial!==1)throw Error('PRIMARY_MATERIAL_NOT_CONTINUOUS');
  const lod=geographicTerrainLod(bounds,wideSource,plans.REGIONAL.assets.terrain,width,height);
  const signature=JSON.stringify([bounds,lod.weight,visual,reveal,layout.items.map(item=>item.box)]);
  if(lastSignature!==signature){
   factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
   const result=factory.renderFrame({...params,graphics:false,reveal,primaryMaterial:1});
   if(result.glError!==gl.NO_ERROR)throw Error('FROZEN_FACTORY_GL_ERROR_'+result.glError);
   lastGraphics=graphics.draw({items:layout.items,reveal});
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('GUIDED_GRAPHIC_PASS_GL_ERROR_'+error);
   lastPixels=null;lastSignature=signature;
  }
  lastDiagnostic={...camera,reveal:structuredClone(reveal),guidedReveal:guided.visibility,
   revealReadiness:guided.readiness,layoutChoice:layout.choice,
   gpu:{stage:'SINGLE_GEOGRAPHIC_CAMERA_WITH_EXPLICIT_GUIDED_GRAPHICS',factoryCount:1,context:'WebGL2',glError:0,
    finishedFrameMix:false,projectionChange:false,actualCamera:structuredClone(factory.evidence.cameraFrame),
    actualReveal:structuredClone(factory.evidence.revealState),actualPrimaryMaterial:factory.evidence.primaryMaterialReveal,
    boundaryPixels:visual,terrainLod:lod,graphicPass:graphics.evidence.version,
    layout:structuredClone(layout.items),layoutValidation:guided.validation,layoutEligibilityValidation:layout.validation,layoutChoice:layout.choice,
    visibleRoles:[...lastGraphics.visibleRoles],geographicAnchor:[...camera.geographicAnchor]}};
  return lastDiagnostic;
 }
 function readPixels(){
  if(!lastPixels){lastPixels=factory.readPixels();const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('GUIDED_READPIXELS_GL_ERROR_'+error);}
  return lastPixels;
 }
 return{drawFrame,readPixels,png:()=>canvas.toDataURL('image/png'),cameraPlan,revealPlan,layoutContract,
  evidence:{version:GUIDED_CAMERA_GPU_VERSION,context:gl.getParameter(gl.VERSION),
   gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),factoryCount:1,
   previewFinalSameFactory:true,composition:'Frozen map factory + explicit GPU moving graphic pass in one default framebuffer',
   finishedFrameMix:false,projectionChanges:0,frozenMaterialParameters:params,primaryMaterialPolicy:'ALWAYS_ON_FROM_FRAME_0',
   cameraRevealOwnership:'Separate immutable CameraPlan / RevealPlan / Layout contract; pure frame evaluation',
   scaleVisualPolicy:'Unchanged CONTINENT/REGIONAL design tokens interpolated by actual geographic viewport size',
   nativeContextSource:{sourceSha256:wideSource.source?.sha256??null,nativeWindowSha256:wideSource.sha256,
    bounds:[...wideSource.bounds],dimensions:wideSource.dimensions??null,pixelSpacing:wideSource.pixelSpacing??null,
    method:wideSource.lodPreparation?.method??'Existing approved CONTINENT source descriptor'},
   graphicPass:graphics.evidence,softwareOnly:true,nvidia:'NOT_RUN',factories:{REGIONAL:factory.evidence}},
  get diagnostic(){return lastDiagnostic;},dispose(){graphics.dispose();factory.dispose();renderer.dispose();}};
}
