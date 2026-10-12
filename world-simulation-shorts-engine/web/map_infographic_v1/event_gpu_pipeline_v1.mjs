/** Thin Event composition over the unchanged geographic Camera/Renderer APIs.
 * Every frame starts from the native map, so Event OFF cannot retain an overlay.
 */
import * as THREE from '/three.js';
import {createMapInfographicRenderer,createProofPreview,createProofFinal} from './renderer.mjs';
import {geographicTerrainLod} from './camera_gpu_pipeline_v2.mjs';
import {evaluateMinimumContextCameraFrame} from './camera_director_v5.mjs';
import {geographicScaleVisualTokens} from './camera_gpu_pipeline_v5.mjs';
import {compileMovingLayoutContract,evaluateMovingLayout} from './moving_layout_v4.mjs';
import {compileGuidedRevealPlan,evaluateGuidedRevealFrame} from './camera_reveal_v4.mjs';
import {createMovingGraphicPass} from './graphic_motion_pass_v4.mjs';
import {assertEventPlan,evaluateEventFrame} from './event_timeline_v1.mjs';
import {compileGeographicLinePrimitive} from './event_line_v1.mjs';
import {createEventLinePass,validateEventLineFootprint} from './event_line_pass_v1.mjs';
import {compileMetricAnnotation} from './event_metric_v1.mjs';
import {createEventMetricPass} from './event_metric_pass_v1.mjs';
import {chooseMetricPlacement} from './event_layout_adapter_v1.mjs';

export const EVENT_GPU_PIPELINE_V1_VERSION='EVENT_GPU_PIPELINE_V1';
const sameBounds=(a,b)=>Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((value,index)=>value===b[index]);

function lineStyle(role,theme){
 if(!['PRIMARY','SECONDARY'].includes(role))throw Error('EVENT_LINE_UNKNOWN_STYLE_ROLE');
 const prefix=role==='PRIMARY'?'primary':'secondary';
 return {width:theme[prefix+'Width'],coreColor:theme[prefix+'CoreColor'],
  glowRadius:theme.glowRadius,glowGain:theme.glowGain,glowColor:theme.glowColor};
}
function metricStyle(profile){
 if(!profile)throw Error('EVENT_EXISTING_MEASURED_LOCATION_STYLE_REQUIRED');
 const keys=['fontSize','minFontSize','fontFamily','lineHeight','outlineRadius','maxWidth','maxLines'];
 return Object.fromEntries(keys.filter(key=>profile[key]!==undefined).map(key=>[key,profile[key]]));
}
function protectedRectangles(items){
 return items.map(item=>{
  const box=item.box;
  if(!Array.isArray(box)||box.length!==4||!box.every(Number.isFinite)||box[2]<=0||box[3]<=0)
   throw Error('EVENT_NATIVE_LAYOUT_BOX_REQUIRED');
  const outline=item.outlineRadius??item.metrics?.outlineRadius??0;
  if(!Number.isFinite(outline)||outline<0)throw Error('EVENT_NATIVE_TEXT_OUTLINE_REQUIRED');
  const padding=item.kind==='TEXT'?outline+2:2;
  return [box[0]-padding,box[1]-padding,box[0]+box[2]+padding,box[1]+box[3]+padding];
 });
}

/** Camera/Reveal are evaluated exclusively by their protected public APIs.
 * EventPlan and eventFrame are separate caller-owned inputs, not Camera edits.
 */
export async function createEventGpuPipeline({canvas,plans,cameraPlan,scene,heightSource,
 contextTerrain=null,eventPlan=null,width=1080,height=1920}){
 if(createProofPreview!==createProofFinal||createProofFinal!==createMapInfographicRenderer)throw Error('PREVIEW_FINAL_FACTORY_MISMATCH');
 if(width!==1080||height!==1920)throw Error('CANONICAL_CAMERA_PROOF_OUTPUT_REQUIRED');
 if(!sameBounds(cameraPlan.intent.finalExtent,plans.REGIONAL.framing.bounds))throw Error('APPROVED_REGIONAL_FRAMING_CHANGED');
 if(scene.primary_region_id!==plans.REGIONAL.primary)throw Error('SCENE_PRIMARY_REGION_MISMATCH');
 const immutableEventPlan=eventPlan===null?null:assertEventPlan(eventPlan);
 if(immutableEventPlan?.intent.line)lineStyle(immutableEventPlan.intent.line.style_role,plans.REGIONAL.theme);
 const wideSource=contextTerrain??plans.CONTINENT.assets.terrain;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WEBGL2_CONTEXT_FAILED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const factory=await createMapInfographicRenderer({canvas,plan:plans.REGIONAL,layoutPlan:plans.REGIONAL,
  contextTerrain:wideSource,contextGeometries:plans.CONTINENT.geometries,heightSource,width,height,
  outputRenderer:renderer,outputTarget:null});
 const graphics=await createMovingGraphicPass({renderer,factory,width,height});
 const layoutContract=compileMovingLayoutContract({regionalPlan:plans.REGIONAL,measuredLayout:factory.evidence.layout});
 const visualTokensForFrame=state=>geographicScaleVisualTokens(state.camera.flatBounds,plans);
 const revealPlan=compileGuidedRevealPlan({cameraPlan,scene,layoutContract,
  evaluateCamera:evaluateMinimumContextCameraFrame,visualTokensForFrame});
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 const params={dem:true,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
 let linePass=null,metricPass=null,metricPrimitive=null,lastDiagnostic=null,lastPixels=null;

 function prepareEvent(camera,layout,visual,eventFrame){
  if(!immutableEventPlan)throw Error('EVENT_PLAN_REQUIRED_WHEN_ENABLED');
  const protectedBoxes=protectedRectangles(layout.items),safeArea=layoutContract.safeArea;
  // Preserve every native reservation. The native MARKER role alone owns the exemption.
  const protectedGraphics=layout.items.map((item,index)=>({
   kind:item.role==='MARKER'&&item.kind!=='TEXT'&&item.kind!=='PANEL'?'MARKER':item.kind==='TEXT'?'TEXT':'PANEL',
   box:protectedBoxes[index],
  }));
  const project=point=>factory.screen(point);
  const controls=evaluateEventFrame(immutableEventPlan,eventFrame,{cameraState:camera,project,safeArea,
   scalePlan:plans.REGIONAL,heightSource,protectedBoxes});
  let linePrimitive=null,lineFootprint=null,placement=null;
  if(immutableEventPlan.intent.line){
   const style=lineStyle(immutableEventPlan.intent.line.style_role,plans.REGIONAL.theme);
   linePrimitive=compileGeographicLinePrimitive(immutableEventPlan.intent,{project});
   lineFootprint=validateEventLineFootprint(linePrimitive,{style,safeArea,protectedGraphics});
   if(!linePass)linePass=createEventLinePass({renderer,width,height,style});
  }
  if(immutableEventPlan.intent.metric){
   const profile=plans.REGIONAL.layout.measured?.location;
   if(!metricPrimitive)metricPrimitive=compileMetricAnnotation(immutableEventPlan.intent,{style:metricStyle(profile)});
   placement=chooseMetricPlacement({anchor:project(immutableEventPlan.intent.metric.anchor),measurement:metricPrimitive,
    safeArea,protectedBoxes,markerSize:visual.markerSize,gap:profile.gap,lineRoi:lineFootprint?.fullRoi??null});
   if(!metricPass)metricPass=createEventMetricPass({renderer,primitive:metricPrimitive,width,height,color:[1,1,1]});
  }
  return {controls,linePrimitive,lineFootprint,placement,safeArea,protectedBoxes,protectedGraphics};
 }

 function drawFrame(cameraFrame,{eventFrame=null,eventEnabled=false}={}){
  if(typeof eventEnabled!=='boolean')throw Error('EVENT_ENABLED_BOOLEAN_REQUIRED');
  const camera=evaluateMinimumContextCameraFrame(cameraPlan,cameraFrame),bounds=camera.camera.flatBounds;
  const visual=visualTokensForFrame(camera);
  const layout=evaluateMovingLayout(layoutContract,camera,{markerSize:visual.markerSize,boundaryTokens:visual});
  const guided=evaluateGuidedRevealFrame(revealPlan,camera,layout),reveal=guided.reveal;
  if(reveal.primary!==1||camera.primaryMaterial!==1)throw Error('PRIMARY_MATERIAL_NOT_CONTINUOUS');
  const lod=geographicTerrainLod(bounds,wideSource,plans.REGIONAL.assets.terrain,width,height);
  factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
  const result=factory.renderFrame({...params,graphics:false,reveal,primaryMaterial:1});
  if(result.glError!==gl.NO_ERROR)throw Error('FROZEN_FACTORY_GL_ERROR_'+result.glError);
  // Readiness and full reserved footprints are checked before any Event drawing.
  const prepared=eventEnabled?prepareEvent(camera,layout,visual,eventFrame):null;
  let line=null,metric=null;
  if(prepared?.controls.lineActive)line=linePass.draw({primitive:prepared.linePrimitive,
   visibleFraction:prepared.controls.lineFraction,safeArea:prepared.safeArea,protectedGraphics:prepared.protectedGraphics});
  const nativeGraphics=graphics.draw({items:layout.items,reveal});
  if(prepared?.controls.metricActive)metric=metricPass.draw({visibleFraction:prepared.controls.metricFraction,
   placement:prepared.placement});
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('EVENT_COMPOSITION_GL_ERROR_'+error);
  lastPixels=null;
  const rois=[line?.drawn?line.roi:null,metric?.drawn?metric.roi:null].filter(Boolean).map(roi=>[...roi]);
  lastDiagnostic={...camera,reveal:structuredClone(reveal),guidedReveal:guided.visibility,
   revealReadiness:guided.readiness,layoutChoice:layout.choice,
   gpu:{stage:'FROZEN_GEOGRAPHIC_MAP_WITH_THIN_EVENT_COMPOSITION',factoryCount:1,context:'WebGL2',glError:0,
    finishedFrameMix:false,projectionChange:false,actualCamera:structuredClone(factory.evidence.cameraFrame),
    actualReveal:structuredClone(factory.evidence.revealState),actualPrimaryMaterial:factory.evidence.primaryMaterialReveal,
    boundaryPixels:visual,terrainLod:lod,graphicPass:graphics.evidence.version,
    layout:structuredClone(layout.items),layoutValidation:guided.validation,layoutEligibilityValidation:layout.validation,
    layoutChoice:layout.choice,visibleRoles:[...nativeGraphics.visibleRoles],geographicAnchor:[...camera.geographicAnchor]},
   event:{enabled:eventEnabled,cameraOwnership:'READ_ONLY',baseRenderedFresh:true,rois,
    controls:prepared?.controls??null,protectedBoxes:prepared?.protectedBoxes??[],
    protectedGraphics:prepared?.protectedGraphics??[],
    line,metric,placement:prepared?.placement??null,lineFullRoi:prepared?.lineFootprint?.fullRoi??null}};
  return lastDiagnostic;
 }
 function readPixels(){
  if(!lastPixels){lastPixels=factory.readPixels();const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('EVENT_READPIXELS_GL_ERROR_'+error);}
  return lastPixels;
 }
 return {drawFrame,readPixels,png:()=>canvas.toDataURL('image/png'),cameraPlan,revealPlan,layoutContract,
  eventPlan:immutableEventPlan,evidence:{version:EVENT_GPU_PIPELINE_V1_VERSION,context:gl.getParameter(gl.VERSION),
   gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),factoryCount:1,
   composition:'Fresh unchanged map -> separate Event Line -> unchanged native graphics -> separate measured Event Metric',
   cameraOwnership:'READ_ONLY_PUBLIC_API',softwareOnly:true,frozenMaterialParameters:params,
   eventOffPolicy:'No Event readiness evaluation or Event GPU draws; native base rendered fresh'},
  get diagnostic(){return lastDiagnostic;},
  dispose(){linePass?.dispose();metricPass?.dispose();graphics.dispose();factory.dispose();renderer.dispose();}};
}
