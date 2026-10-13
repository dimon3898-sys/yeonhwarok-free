/** New Area glue around the unchanged V5 Camera, measured graphics and map factory. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer,createProofPreview,createProofFinal,polygons} from './renderer.mjs';
import {geographicTerrainLod} from './camera_gpu_pipeline_v2.mjs';
import {geographicScaleVisualTokens} from './camera_gpu_pipeline_v5.mjs';
import {evaluateMinimumContextCameraFrame} from './camera_director_v5.mjs';
import {compileMovingLayoutContract,evaluateMovingLayout} from './moving_layout_v4.mjs';
import {compileGuidedRevealPlan,evaluateGuidedRevealFrame} from './camera_reveal_v4.mjs';
import {createMovingGraphicPass} from './graphic_motion_pass_v4.mjs';

export const AREA_NATIVE_BRIDGE_V3_VERSION='AREA_NATIVE_BRIDGE_V3';
const copy=value=>structuredClone(value);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const onScreen=(a,b,radius,width,height)=>Math.max(a[0],b[0])+radius>=0
 &&Math.min(a[0],b[0])-radius<=width&&Math.max(a[1],b[1])+radius>=0&&Math.min(a[1],b[1])-radius<=height;

function reservations(items){
 return items.map(item=>{
  if(!['MARKER','TEXT','PANEL'].includes(item.kind)||!Array.isArray(item.box)||item.box.length!==4)
   throw Error('AREA_NATIVE_MEASURED_GRAPHIC_REQUIRED');
  const [x,y,w,h]=item.box,padding=item.kind==='TEXT'?(item.outlineRadius??item.metrics?.outlineRadius??0)+2:2;
  if(![x,y,w,h,padding].every(Number.isFinite)||w<=0||h<=0||padding<0)
   throw Error('AREA_NATIVE_MEASURED_GRAPHIC_BOUNDS_REQUIRED');
  return{kind:item.kind,role:item.role,box:[x-padding,y-padding,x+w+padding,y+h+padding]};
 });
}

/** No Camera/Projection/Reveal math is implemented here. Each draw clears and redraws native pixels. */
export async function createAreaNativeBridge({canvas,plans,cameraPlan,scene,heightSource=null,
 contextTerrain=null,width=1080,height=1920}={}){
 if(createProofPreview!==createProofFinal||createProofFinal!==createMapInfographicRenderer)
  throw Error('AREA_NATIVE_PREVIEW_FINAL_FACTORY_MISMATCH');
 if(width!==1080||height!==1920)throw Error('AREA_NATIVE_CANONICAL_OUTPUT_REQUIRED');
 if(!Number.isSafeInteger(cameraPlan?.totalFrames)||cameraPlan.totalFrames<=0
  ||cameraPlan.directorVersion!=='CAMERA_DIRECTOR_V5')throw Error('AREA_NATIVE_V5_CAMERA_PLAN_REQUIRED');
 if(!same(cameraPlan.intent?.finalExtent,plans?.REGIONAL?.framing?.bounds))
  throw Error('AREA_NATIVE_CAMERA_REGIONAL_BINDING_REQUIRED');
 if(scene?.primary_region_id!==plans.REGIONAL.primary)throw Error('AREA_NATIVE_PRIMARY_BINDING_REQUIRED');
 const wideSource=contextTerrain??plans.CONTINENT.assets.terrain;
 const gl=canvas?.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('AREA_NATIVE_WEBGL2_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 let factory,graphics;
 try{
  factory=await createMapInfographicRenderer({canvas,plan:plans.REGIONAL,layoutPlan:plans.REGIONAL,
   contextTerrain:wideSource,contextGeometries:plans.CONTINENT.geometries,heightSource,width,height,
   outputRenderer:renderer,outputTarget:null});
  graphics=await createMovingGraphicPass({renderer,factory,width,height});
  const layoutContract=compileMovingLayoutContract({regionalPlan:plans.REGIONAL,measuredLayout:factory.evidence.layout});
  const visualTokensForFrame=state=>geographicScaleVisualTokens(state.camera.flatBounds,plans);
  const revealPlan=compileGuidedRevealPlan({cameraPlan,scene,layoutContract,
   evaluateCamera:evaluateMinimumContextCameraFrame,visualTokensForFrame});
  const params={dem:heightSource!==null,verticalExaggeration:2,bakedSuppression:.1,
   correctedLight:true,shadingCorrection:'FINAL'};
  const secondary=new Set(plans.REGIONAL.secondary??[]);
  const boundaryGeometry=plans.REGIONAL.geometries.filter(record=>record.id===plans.REGIONAL.primary||secondary.has(record.id));
  let diagnostic=null,disposed=false,boundaryKey=null,boundaryCache=[];
  function boundarySegments(bounds,visual){
   const signature=JSON.stringify([bounds,visual]);
   if(signature===boundaryKey)return copy(boundaryCache);
   const result=[];
   // Native two-pass blur samples at +/-3.230769 * glowRadius per axis.
   // Half ribbon width + Euclidean blur support + 2px includes bilinear/AA support.
   const primaryRadius=Math.max(visual.primaryWidth,visual.primaryEdgeWidth,visual.glowWidth)/2
    +Math.SQRT2*3.230769*visual.glowRadius+2;
   const secondaryRadius=Math.max(visual.secondaryWidth,visual.secondaryEdgeWidth)/2+2;
   for(const record of boundaryGeometry){
    const primary=record.id===plans.REGIONAL.primary,radiusPx=primary?primaryRadius:secondaryRadius;
    if(!Number.isFinite(radiusPx)||radiusPx<=0)throw Error('AREA_NATIVE_BOUNDARY_SUPPORT_REQUIRED');
    for(const polygon of polygons(record))for(const ring of polygon)for(let index=1;index<ring.length;index++){
     const a=factory.screen(ring[index-1]),b=factory.screen(ring[index]);
     if(!point(a)||!point(b))throw Error('AREA_NATIVE_PROJECTED_BOUNDARY_REQUIRED');
     if(onScreen(a,b,radiusPx,width,height))result.push({a:[...a],b:[...b],radiusPx,
      role:primary?'PRIMARY':'SECONDARY',sourceId:record.id});
    }
   }
   boundaryKey=signature;boundaryCache=result;return copy(result);
  }
  function drawNative(frame){
   if(disposed)throw Error('AREA_NATIVE_BRIDGE_DISPOSED');
   if(!Number.isSafeInteger(frame)||frame<0)throw Error('AREA_NATIVE_FRAME_REQUIRED');
   const nativeFrame=Math.min(frame,cameraPlan.totalFrames-1);
   const camera=evaluateMinimumContextCameraFrame(cameraPlan,nativeFrame),bounds=camera.camera.flatBounds;
   const visual=visualTokensForFrame(camera);
   const layout=evaluateMovingLayout(layoutContract,camera,{markerSize:visual.markerSize,boundaryTokens:visual});
   const guided=evaluateGuidedRevealFrame(revealPlan,camera,layout),reveal=guided.reveal;
   if(reveal.primary!==1||camera.primaryMaterial!==1)throw Error('AREA_NATIVE_PRIMARY_MATERIAL_NOT_CONTINUOUS');
   const lod=geographicTerrainLod(bounds,wideSource,plans.REGIONAL.assets.terrain,width,height);
   factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
   // This redraw is unconditional: a held native view must erase the preceding Area overlay.
   const result=factory.renderFrame({...params,graphics:false,reveal,primaryMaterial:1});
   if(result.glError!==gl.NO_ERROR)throw Error('AREA_NATIVE_FACTORY_GL_ERROR_'+result.glError);
   const nativeGraphics=graphics.draw({items:layout.items,reveal});
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('AREA_NATIVE_GRAPHIC_GL_ERROR_'+error);
   const protectedGraphics=reservations(layout.items),boundaries=boundarySegments(bounds,visual);
   diagnostic={...camera,requestedFrame:frame,nativeFrame,frameClamped:frame!==nativeFrame,
    reveal:copy(reveal),guidedReveal:copy(guided.visibility),revealReadiness:copy(guided.readiness),
    layoutChoice:copy(layout.choice),layoutItems:copy(layout.items),protectedGraphics,
    boundarySegments:boundaries,safeArea:copy(layoutContract.safeArea),
    gpu:{stage:'AREA_EXTENSION_FROZEN_V5_NATIVE_REDRAW',factoryCount:1,glError:0,
     actualCamera:copy(factory.evidence.cameraFrame),actualReveal:copy(factory.evidence.revealState),
     actualPrimaryMaterial:factory.evidence.primaryMaterialReveal,boundaryPixels:copy(visual),terrainLod:copy(lod),
     layout:copy(layout.items),layoutValidation:copy(guided.validation),layoutEligibilityValidation:copy(layout.validation),
     visibleRoles:copy(nativeGraphics.visibleRoles),finishedFrameMix:false,projectionChange:false,
     nativeRedrawn:true,graphicPass:graphics.evidence.version}};
   return diagnostic;
  }
  const readPixels=()=>{
   if(disposed)throw Error('AREA_NATIVE_BRIDGE_DISPOSED');
   const bytes=factory.readPixels(),error=gl.getError();
   if(error!==gl.NO_ERROR)throw Error('AREA_NATIVE_READPIXELS_GL_ERROR_'+error);return bytes;
  };
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  return{drawNative,drawFrame:drawNative,renderer,factory,project:point=>factory.screen(point),
   readPixels,png:()=>canvas.toDataURL('image/png'),cameraPlan,revealPlan,layoutContract,
   get diagnostic(){return diagnostic;},
   get layoutItems(){return copy(diagnostic?.layoutItems??layoutContract.items);},
   get protectedGraphics(){return copy(diagnostic?.protectedGraphics??[]);},
   get boundarySegments(){return copy(diagnostic?.boundarySegments??[]);},
   evidence:{version:AREA_NATIVE_BRIDGE_V3_VERSION,cameraOwner:'UNCHANGED_CAMERA_DIRECTOR_V5',
    rendererOwner:'UNCHANGED_MAP_INFOGRAPHIC_FACTORY',projectionOwner:'ACTUAL_NATIVE_FACTORY_SCREEN',
    layoutOwner:'UNCHANGED_MOVING_LAYOUT_AND_GUIDED_REVEAL',nativeRedraw:'EVERY_DRAW_NO_FINISHED_FRAME_CACHE',
    output:[width,height],factoryCount:1,primaryMaterialAlwaysOn:true,sourceGeometryMutation:false,
    demUsed:heightSource!==null,missingDemPolicy:'EXISTING_BAKED_RELIEF_FACTORY_PATH',frozenMaterialParameters:copy(params),
    nativeBoundaryProtection:'PRIMARY_CORE_EDGE_AND_TWO_AXIS_FINITE_GLOW_SUPPORT_SECONDARY_CORE_EDGE',
    context:gl.getParameter(gl.VERSION),gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
    graphicPass:graphics.evidence,finishedFrameMix:false,softwareOnly:true},
   dispose(){if(disposed)return;graphics.dispose();factory.dispose();renderer.dispose();disposed=true;}};
 }catch(error){graphics?.dispose();factory?.dispose();renderer.dispose();throw error;}
}
