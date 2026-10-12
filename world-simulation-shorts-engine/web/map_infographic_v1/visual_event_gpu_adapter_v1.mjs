/** Post-arrival Detail composition using the unchanged native map/Event APIs.
 * Visual admission is a separate production contract; the survey record stays
 * intact. Static probes are explicitly uncertified and cannot authorize motion.
 */
import * as THREE from '/three.js';
import {createMapInfographicRenderer} from './renderer.mjs';
import {createEventGpuPipeline} from './event_gpu_pipeline_v1.mjs';
import {evaluateMinimumContextCameraFrame} from './camera_director_v5.mjs';
import {geographicScaleVisualTokens} from './camera_gpu_pipeline_v5.mjs';
import {geographicTerrainLod} from './camera_gpu_pipeline_v2.mjs';
import {compileMovingLayoutContract,evaluateMovingLayout,validateVisibleMovingLayout} from './moving_layout_v4.mjs';
import {compileGuidedRevealPlan,evaluateGuidedRevealFrame} from './camera_reveal_v4.mjs';
import {createMovingGraphicPass} from './graphic_motion_pass_v4.mjs';
import {assertEventPlan,evaluateEventFrame} from './event_timeline_v1.mjs';
import {compileGeographicLinePrimitive} from './event_line_v1.mjs';
import {createEventLinePass,validateEventLineFootprint} from './event_line_pass_v1.mjs';
import {compileMetricAnnotation} from './event_metric_v1.mjs';
import {createEventMetricPass} from './event_metric_pass_v1.mjs';
import {chooseRelatedMetricPlacement,chooseMetricPlacement} from './event_layout_adapter_v1.mjs';
import {evaluateVisualDetailCandidate} from './visual_detail_admission_v1.mjs';

export const EVENT_DETAIL_GPU_ADAPTER_V1_VERSION='EVENT_DETAIL_GPU_ADAPTER_V1';
const clone=value=>structuredClone(value);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const canonical=value=>JSON.stringify(value,(_key,item)=>item&&typeof item==='object'&&!Array.isArray(item)
 ?Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])):item);
const geographicBounds=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)
 &&value[0]<value[2]&&value[1]<value[3]&&value[0]>=-180&&value[2]<=180&&value[1]>=-90&&value[3]<=90;
const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
const roleKey={MARKER:'marker',LOCATION_LABEL:'location',COUNTRY:'country',EVENT_TITLE:'title',TITLE_CONTRAST_PANEL:'title',SCENARIO_DISCLOSURE:'disclosure'};
function protectedReservations(items){
 const boxes=items.map(item=>{
  const [x,y,w,h]=item.box,pad=item.kind==='TEXT'?(item.outlineRadius??item.metrics?.outlineRadius??0)+2:2;
  if(![x,y,w,h,pad].every(Number.isFinite)||w<=0||h<=0||pad<0)throw Error('DETAIL_NATIVE_MEASURED_BOX_REQUIRED');
  return[x-pad,y-pad,x+w+pad,y+h+pad];
 });
 return{boxes,graphics:items.map((item,index)=>({kind:item.role==='MARKER'&&item.kind==='MARKER'?'MARKER':item.kind==='TEXT'?'TEXT':'PANEL',box:boxes[index]}))};
}
function requireProductionCertificate(certificate,target,eventPlan,safeArea){
 if(certificate?.version!=='VISUAL_DETAIL_ADMISSION_V1'||certificate.status!=='VISUAL_DETAIL_ADMITTED'
  ||certificate.grade!=='FACT_BASED_VISUAL_GRADE'||certificate.productionEligible!==true
  ||certificate.evidenceKind!=='ACTUAL_NATIVE_RENDER'||certificate.surveyAdmissionModified!==false
  ||!same(certificate.bounds,target)||!same(certificate.output,[1080,1920])||!same(certificate.safeArea,safeArea)
  ||certificate.eventGeometryBinding!==canonical(eventPlan.intent.line?.geometry)||eventPlan.intent.data_mode!=='PRODUCTION')
  throw Error('DETAIL_GPU_EXACT_PRODUCTION_VISUAL_CERTIFICATE_REQUIRED');
 let input;try{input=JSON.parse(certificate.evidenceBinding);}catch{throw Error('DETAIL_GPU_VISUAL_EVIDENCE_BINDING_REQUIRED');}
 const audit=evaluateVisualDetailCandidate(input);
 if(!audit.productionEligible||audit.status!=='VISUAL_DETAIL_ADMITTED'||audit.evidenceBinding!==certificate.evidenceBinding
  ||!same(audit.candidate.bounds,target)||audit.eventGeometryBinding!==certificate.eventGeometryBinding
  ||audit.surveyDetailStatus!==certificate.surveyDetailStatus)throw Error('DETAIL_GPU_STALE_VISUAL_CERTIFICATE');
}

/** Disabled mode delegates before any Detail construction or admission work. */
export async function createEventDetailGpuAdapter({canvas,plans,cameraPlan,scene,heightSource,contextTerrain=null,
 eventPlan=null,targetFraming=null,approvedEventStyle=null,approvedMetricStyle=null,
 mode='STATIC_VISUAL_PROBE',certificate=null,detailEnabled=true,width=1080,height=1920}={}){
 if(detailEnabled===false)return createEventGpuPipeline({canvas,plans,cameraPlan,scene,heightSource,
  contextTerrain,eventPlan,width,height});
 if(detailEnabled!==true)throw Error('DETAIL_ENABLED_BOOLEAN_REQUIRED');
 if(width!==1080||height!==1920)throw Error('DETAIL_CANONICAL_OUTPUT_REQUIRED');
 if(!['STATIC_VISUAL_PROBE','VISUAL_DETAIL_ADMITTED'].includes(mode))throw Error('DETAIL_GPU_EXPLICIT_MODE_REQUIRED');
 const immutableEventPlan=assertEventPlan(eventPlan),target=clone(targetFraming?.bounds??targetFraming),regional=plans?.REGIONAL,
  safeArea=clone(regional?.layout?.safe??[48,72,1032,1848]);
 if(!geographicBounds(target)||!regional||!same(cameraPlan.intent.finalExtent,regional.framing.bounds)
  ||scene.primary_region_id!==regional.primary)throw Error('DETAIL_GPU_ORIGINAL_ARRIVAL_AND_TARGET_REQUIRED');
 if(mode==='VISUAL_DETAIL_ADMITTED')requireProductionCertificate(certificate,target,immutableEventPlan,safeArea);
 if(!immutableEventPlan.intent.line||!approvedEventStyle||!approvedMetricStyle)throw Error('DETAIL_GPU_APPROVED_EVENT_V2_STYLES_REQUIRED');
 const originalInputs=canonical({plans,cameraPlan,scene,heightSource,contextTerrain,eventPlan,approvedEventStyle,approvedMetricStyle}),
  style=clone(approvedEventStyle),metricStyle=clone(approvedMetricStyle),wideSource=contextTerrain??plans.CONTINENT.assets.terrain;
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('DETAIL_GPU_WEBGL2_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
 renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const common={canvas,plan:regional,contextTerrain:wideSource,contextGeometries:plans.CONTINENT.geometries,
  heightSource,width,height,outputRenderer:renderer,outputTarget:null};
 let sourceFactory=null,factory=null,graphics=null,linePass=null,metricPass=null;
 try{
  // Prepare the original measured native coverage once. No target-layout
  // reflow is used for any visible protected graphic.
  sourceFactory=await createMapInfographicRenderer({...common,layoutPlan:regional});
  const nativeLayout=clone(sourceFactory.evidence.layout),nativeLayoutValidation=clone(sourceFactory.evidence.layoutValidation),
   nativeAtlases=sourceFactory.glyphAtlases().map(atlas=>({...atlas}));
  const layoutContract=compileMovingLayoutContract({regionalPlan:regional,measuredLayout:nativeLayout});
  const facade={evidence:{layout:nativeLayout,layoutValidation:nativeLayoutValidation},glyphAtlases:()=>nativeAtlases};
  sourceFactory.dispose();sourceFactory=null;
  // The new visual endpoint is a new Adapter input. The old renderer's actual
  // endpoint guard remains active, and its map geometry/material basis stays
  // the approved Regional basis. Survey evidence is not changed or relabelled.
  const endpointPlan=clone(regional);endpointPlan.framing={...endpointPlan.framing,bounds:clone(target),
   center:[(target[0]+target[2])/2,(target[1]+target[3])/2]};
  factory=await createMapInfographicRenderer({...common,layoutPlan:endpointPlan});
  graphics=await createMovingGraphicPass({renderer,factory:facade,width,height});
  linePass=createEventLinePass({renderer,width,height,style});
  const metricPrimitive=immutableEventPlan.intent.metric?compileMetricAnnotation(immutableEventPlan.intent,{style:metricStyle}):null;
  if(metricPrimitive)metricPass=createEventMetricPass({renderer,primitive:metricPrimitive,width,height,color:[1,1,1]});
  const arrival=evaluateMinimumContextCameraFrame(cameraPlan,cameraPlan.totalFrames-1),
   sourceRevealPlan=compileGuidedRevealPlan({cameraPlan,scene,layoutContract,evaluateCamera:evaluateMinimumContextCameraFrame,
    visualTokensForFrame:state=>geographicScaleVisualTokens(state.camera.flatBounds,plans)}),
   arrivalLayout=evaluateMovingLayout(layoutContract,arrival,{markerSize:regional.scale.marker.pixels,boundaryTokens:regional.theme}),
   arrivalReveal=clone(evaluateGuidedRevealFrame(sourceRevealPlan,arrival,arrivalLayout).reveal),
   params={dem:true,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
  let lastDiagnostic=null,lastPixels=null,clean=null,cleanSignature=null;
  function readPixels(){if(!lastPixels)lastPixels=factory.readPixels();return lastPixels;}
  function draw({bounds,cameraLocked=false,eventFrame=null,eventEnabled=false,protect=false,frame=0}={}){
   if(!geographicBounds(bounds)||typeof cameraLocked!=='boolean'||typeof eventEnabled!=='boolean'||typeof protect!=='boolean'
    ||!Number.isSafeInteger(frame)||frame<0)throw Error('DETAIL_GPU_DRAW_CONTRACT_REQUIRED');
   if(eventEnabled&&(!cameraLocked||!same(bounds,target)))throw Error('DETAIL_GPU_EVENT_REQUIRES_EXACT_DETAIL_LOCK');
   if(eventEnabled&&(!Number.isSafeInteger(eventFrame)||eventFrame<0))throw Error('DETAIL_GPU_EVENT_FRAME_REQUIRED');
   if(!eventEnabled&&eventFrame!==null)throw Error('DETAIL_GPU_NO_EVENT_CONTROLS_BEFORE_LOCK');
   const camera={...clone(arrival),frame,state:cameraLocked?'DETAIL_LOCK':'DETAIL_APPROACH',stateKey:cameraLocked?'DETAIL_LOCK':'DETAIL_APPROACH',
    center:[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2],extent:clone(bounds),geographicExtent:clone(bounds),
    camera:{...clone(arrival.camera),flatBounds:clone(bounds),noCloserThanApprovedStop:same(bounds,regional.framing.bounds)},
    cameraLocked,settle:{phase:cameraLocked?'DETAIL_LOCK':'DETAIL_APPROACH',settled:cameraLocked,locked:cameraLocked},
    visualAdmission:{grade:'FACT_BASED_VISUAL_GRADE',status:mode,productionEligible:mode==='VISUAL_DETAIL_ADMITTED'},
    surveyAdmission:clone(arrival.admission)};
   const visual=geographicScaleVisualTokens(bounds,plans),layout=evaluateMovingLayout(layoutContract,camera,
    {markerSize:visual.markerSize,boundaryTokens:visual}),reveal=clone(arrivalReveal);
   // A geographic label retains its original geographic binding and coverage;
   // it leaves the shot naturally. Other protected roles stay strict.
   const geographicLabelOutsideSafe=layout.validation.failuresByRole.country.some(failure=>failure.code==='SAFE_AREA');
   reveal.country=geographicLabelOutsideSafe?0:arrivalReveal.country;
   const visibleValidation=validateVisibleMovingLayout(layout,reveal),warnings=visibleValidation.failures.filter(f=>f.key==='title'&&f.code==='BOUNDARY_CLEARANCE'),
    critical=visibleValidation.failures.filter(f=>!(f.key==='title'&&f.code==='BOUNDARY_CLEARANCE'));
   if(critical.length)throw Object.assign(Error('DETAIL_GPU_VISIBLE_PROTECTED_LAYOUT_INVALID'),{failures:critical});
   const hiddenGeographicLabels=layout.items.filter(item=>item.role==='COUNTRY'&&!reveal.country).map(item=>({role:item.role,
    reason:'PROJECTION_OUTSIDE_SAFE_AREA',anchorPreserved:true,stylePreserved:true,box:clone(item.box)})),
    reservations=protectedReservations(layout.items.filter(item=>(reveal[roleKey[item.role]]??0)>0)),
    lod=geographicTerrainLod(bounds,wideSource,regional.assets.terrain,width,height),
    signature=canonical({bounds,visual,reveal,layout:layout.items.map(item=>item.box),lod});
   if(protect&&eventEnabled&&cleanSignature!==signature){
    draw({bounds,cameraLocked,eventEnabled:false,frame});clean=new Uint8Array(readPixels());cleanSignature=signature;
   }
   factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
   const native=factory.renderFrame({...params,graphics:false,reveal,primaryMaterial:1});
   if(native.glError!==gl.NO_ERROR)throw Error('DETAIL_GPU_NATIVE_FACTORY_GL_ERROR_'+native.glError);
   let controls=null,linePrimitive=null,footprint=null,placement=null,line=null,metric=null,preparationError=null;
   try{
    if(eventEnabled){
     const project=point=>factory.screen(point);
     controls=evaluateEventFrame(immutableEventPlan,eventFrame,{cameraState:camera,project,safeArea,
      scalePlan:regional,heightSource,protectedBoxes:reservations.boxes});
     linePrimitive=compileGeographicLinePrimitive(immutableEventPlan.intent,{project});
     footprint=validateEventLineFootprint(linePrimitive,{style,safeArea,protectedGraphics:reservations.graphics});
     if(metricPrimitive){
      const commonLayout={anchor:project(immutableEventPlan.intent.metric.anchor),measurement:metricPrimitive,
       safeArea,protectedBoxes:reservations.boxes};
      placement=linePrimitive?chooseRelatedMetricPlacement({...commonLayout,linePrimitive,
       markerOcclusions:footprint.markerOcclusions,linePaddingPixels:footprint.paddingPixels,gap:10})
       :chooseMetricPlacement({...commonLayout,markerSize:visual.markerSize,gap:regional.layout.measured.location.gap});
     }
     if(controls.lineActive)line=linePass.draw({primitive:linePrimitive,visibleFraction:controls.lineFraction,
      safeArea,protectedGraphics:reservations.graphics});
    }
   }catch(error){preparationError=error;}
   const nativeGraphics=graphics.draw({items:layout.items,reveal});
   if(!preparationError&&controls?.metricActive)metric=metricPass.draw({visibleFraction:controls.metricFraction,placement});
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('DETAIL_GPU_COMPOSITION_GL_ERROR_'+glError);
   lastPixels=null;
   const rois=[line?.drawn?line.roi:null,metric?.drawn?metric.roi:null].filter(Boolean).map(roi=>clone(roi));
   lastDiagnostic={...camera,reveal,layoutChoice:clone(layout.choice),warnings,hiddenGeographicLabels,
    gpu:{stage:'POST_ARRIVAL_DETAIL_EXTENSION_UNCHANGED_NATIVE_EVENT_PASSES',glError,factoryCount:1,
     actualCamera:clone(factory.evidence.cameraFrame),actualReveal:clone(factory.evidence.revealState),boundaryPixels:visual,terrainLod:lod,
     layout:clone(layout.items),layoutValidation:{valid:critical.length===0,failures:critical,warnings},
     layoutEligibilityValidation:clone(layout.validation),visibleRoles:clone(nativeGraphics.visibleRoles),
     finishedFrameMix:false,projectionChange:false,graphicPass:graphics.evidence.version},
    event:{enabled:eventEnabled,controls,line,metric,placement,rois,protectedBoxes:reservations.boxes,
     protectedGraphics:reservations.graphics,eventStyle:clone(style),metricStyle:clone(metricStyle),lineFullRoi:footprint?.fullRoi??null,
     linePrimitive:linePrimitive?clone(linePrimitive):null,hiddenGeographicLabels,cameraOwnership:'READ_ONLY_DETAIL_ADAPTER_STATE',
     baseRenderedFresh:true,preparationError:preparationError?.message??null}};
   if(protect&&eventEnabled&&clean){
    const actual=readPixels();let changed=0,outside=0,protectedChanged=0,markerChanged=0;
    for(let index=0;index<width*height;index++){
     const offset=index*4;if(actual[offset]===clean[offset]&&actual[offset+1]===clean[offset+1]
      &&actual[offset+2]===clean[offset+2]&&actual[offset+3]===clean[offset+3])continue;
     changed++;const x=index%width,y=height-1-Math.floor(index/width);
     if(!rois.some(b=>inside(x,y,b)))outside++;
     if(reservations.boxes.some(b=>inside(x,y,b)))protectedChanged++;
     if(reservations.graphics.some(item=>item.kind==='MARKER'&&inside(x,y,item.box)))markerChanged++;
    }
    Object.assign(lastDiagnostic.event,{changed_pixels:changed,outside_roi_changed_pixels:outside,
     protected_changed_pixels:protectedChanged,marker_changed_pixels:markerChanged});
   }
   if(originalInputs!==canonical({plans,cameraPlan,scene,heightSource,contextTerrain,eventPlan,approvedEventStyle,approvedMetricStyle}))
    throw Error('DETAIL_GPU_PROTECTED_INPUT_MUTATION');
   if(preparationError)throw Object.assign(preparationError,{diagnostic:lastDiagnostic,nativeFrameAvailable:true});
   return lastDiagnostic;
  }
  return{draw,readPixels,png:()=>canvas.toDataURL('image/png'),eventPlan:immutableEventPlan,layoutContract,
   evidence:{version:EVENT_DETAIL_GPU_ADAPTER_V1_VERSION,mode,productionEligible:mode==='VISUAL_DETAIL_ADMITTED',
    surveyAdmissionPreserved:true,rendererSourceUnchanged:true,cameraV5SourceUnchanged:true,eventV2SourceUnchanged:true,
    originalNativeLayout:nativeLayout,originalGlyphAtlases: nativeAtlases.map(({name})=>name),
    approvedEventStyle:clone(style),approvedMetricStyle:clone(metricStyle),targetFraming:clone(target),
    composition:'Native map -> unchanged Event Line -> reprojected original native coverage -> unchanged Event Metric',
    endpointPolicy:'New exact visual-admitted Adapter endpoint; unchanged renderer endpoint guard',
    frozenMaterialParameters:params,graphicPass:graphics.evidence},
   get diagnostic(){return lastDiagnostic;},
   dispose(){linePass.dispose();metricPass?.dispose();graphics.dispose();factory.dispose();renderer.dispose();}};
 }catch(error){sourceFactory?.dispose();linePass?.dispose();metricPass?.dispose();graphics?.dispose();factory?.dispose();renderer.dispose();throw error;}
}
