/** Planner-only composition of the frozen native, Area, Flow and measured-label APIs. */
import {createAreaNativeBridge} from './area_native_bridge_v3.mjs';
import {assertAreaPlan,evaluateAreaFrame} from './area_core_v3.mjs';
import {createAreaOverlayPass} from './area_overlay_pass_v3.mjs';
import {createAreaAnnotation} from './area_annotation_v3.mjs';
import {assertFlowPlan,compileFlowRoute,evaluateFlowFrame} from './flow_core_v2.mjs';
import {createFlowGraphicPass} from './flow_graphic_pass_v2.mjs';
import {compileFlowVisualProfile,assertFlowVisualProfile,applyFlowVisualProfile} from './flow_visual_profile_v2.mjs';
import {selectEventLineStyle} from './event_style_v1.mjs';
import {validateEventLineFootprint} from './event_line_pass_v1.mjs';
import {geometryBounds} from './scale_contract.mjs';

export const PLANNER_CAUSAL_GPU_ADAPTER_V1_VERSION='PLANNER_CAUSAL_GPU_ADAPTER_V1';
const WIDTH=1080,HEIGHT=1920,TILE=32;
const copy=value=>structuredClone(value);
const clamp=value=>Math.max(0,Math.min(1,value));
const inside=(x,y,box)=>x+.5>=box[0]&&x+.5<=box[2]&&y+.5>=box[1]&&y+.5<=box[3];
const integer=(value,minimum=0)=>Number.isSafeInteger(value)&&value>=minimum;
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const rectangle=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)
 &&value[0]<value[2]&&value[1]<value[3];

// These distances only reject overlay coverage at protected native pixels; they never change motion.
function pointSegmentDistance(p,a,b){
 const dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy;
 const t=length?clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length):0;
 return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
}
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
function segmentDistance(a,b,c,d){
 const ac=cross(a,b,c),ad=cross(a,b,d),ca=cross(c,d,a),cb=cross(c,d,b);
 if(((ac>0&&ad<0)||(ac<0&&ad>0))&&((ca>0&&cb<0)||(ca<0&&cb>0)))return 0;
 return Math.min(pointSegmentDistance(a,c,d),pointSegmentDistance(b,c,d),
  pointSegmentDistance(c,a,b),pointSegmentDistance(d,a,b));
}
function routeBounds(primitive,padding){
 const points=primitive.screenCoordinates;
 return[Math.min(...points.map(p=>p[0]))-padding,Math.min(...points.map(p=>p[1]))-padding,
  Math.max(...points.map(p=>p[0]))+padding,Math.max(...points.map(p=>p[1]))+padding];
}
function supports(intent,style,profile){
 const graphic=intent.object_graphic,scale=profile.objectScale,size=Math.max(graphic.width_px,graphic.height_px)*scale;
 const actor=Math.max(...graphic.polygons.flatMap(polygon=>polygon.points)
  .map(([x,y])=>Math.hypot(x*graphic.width_px*scale,y*graphic.height_px*scale)))+1;
 return{route:style.width/2+Math.max(.5,style.glowRadius)+1,actor,
  directional:11,pulse:size*.68*profile.arrivalRadiusScale+2};
}
function checkBoundaries(id,primitive,support,boundaries,safeArea){
 const maximum=Math.max(...Object.values(support)),roi=routeBounds(primitive,maximum);
 if(roi[0]<safeArea[0]||roi[1]<safeArea[1]||roi[2]>safeArea[2]||roi[3]>safeArea[3])
  throw Object.assign(Error('PLANNER_CAUSAL_SWEPT_SUPPORT_OUTSIDE_SAFE_AREA'),{trackId:id,roi,safeArea});
 let minimumClearancePixels=Infinity;
 for(const edge of boundaries){
  if(!point(edge.a)||!point(edge.b)||!Number.isFinite(edge.radiusPx)||edge.radiusPx<=0)
   throw Error('PLANNER_CAUSAL_NATIVE_BOUNDARY_SUPPORT_REQUIRED');
  for(let index=1;index<primitive.screenCoordinates.length;index++){
   const distance=segmentDistance(primitive.screenCoordinates[index-1],primitive.screenCoordinates[index],edge.a,edge.b);
   const clearance=distance-edge.radiusPx;
   minimumClearancePixels=Math.min(minimumClearancePixels,clearance-maximum);
   if(clearance<=maximum)throw Object.assign(Error('PLANNER_CAUSAL_NATIVE_BOUNDARY_COLLISION'),
    {trackId:id,sourceId:edge.sourceId,segment:index-1,clearancePixels:clearance,support:copy(support)});
  }
 }
 return{passed:true,fullRouteAndSweptSupport:true,supportPixels:copy(support),sweptRoi:roi,
  boundarySegmentCount:boundaries.length,minimumClearancePixels:Number.isFinite(minimumClearancePixels)?minimumClearancePixels:null,
  nativeGeometryUnchanged:true,noBoundaryOcclusionException:true};
}
function boundaryIndex(boundaries){
 const tiles=new Map(),columns=Math.ceil(WIDTH/TILE);
 for(const edge of boundaries){
  const radius=edge.radiusPx,left=Math.max(0,Math.floor((Math.min(edge.a[0],edge.b[0])-radius)/TILE)),
   right=Math.min(columns-1,Math.floor((Math.max(edge.a[0],edge.b[0])+radius)/TILE)),
   top=Math.max(0,Math.floor((Math.min(edge.a[1],edge.b[1])-radius)/TILE)),
   bottom=Math.min(Math.ceil(HEIGHT/TILE)-1,Math.floor((Math.max(edge.a[1],edge.b[1])+radius)/TILE));
  for(let y=top;y<=bottom;y++)for(let x=left;x<=right;x++){
   const key=y*columns+x;if(!tiles.has(key))tiles.set(key,[]);tiles.get(key).push(edge);
  }
 }
 return(x,y)=>(tiles.get(Math.floor(y/TILE)*columns+Math.floor(x/TILE))??[])
  .some(edge=>pointSegmentDistance([x+.5,y+.5],edge.a,edge.b)<=edge.radiusPx);
}
function opacityAt(frame,entry){
 const local=frame-entry.plan.startFrame,last=entry.plan.totalFrames-1;
 const fadeIn=entry.fadeInFrames<=1?1:clamp(local/(entry.fadeInFrames-1));
 const fadeOut=entry.fadeOutFrames<=1?1:clamp((last-local)/(entry.fadeOutFrames-1));
 return Math.min(fadeIn,fadeOut);
}

/** Browser authoring preflight only: no renderer, context, shader, resource or frame draw is created. */
export function preflightPlannerCausalFlowTrack({id,plan,project,safeArea,protectedGraphics,boundarySegments,
 theme,primaryMaterialColor,visualProfile}={}){
 const flow=assertFlowPlan(plan);
 if(typeof id!=='string'||!id.trim()||typeof project!=='function'||!rectangle(safeArea)
  ||!Array.isArray(protectedGraphics)||!Array.isArray(boundarySegments))
  throw Error('PLANNER_CAUSAL_PREFLIGHT_NATIVE_CONTEXT_REQUIRED');
 const profile=visualProfile?assertFlowVisualProfile(visualProfile):compileFlowVisualProfile({
  profileName:'GENERIC_CAUSAL_MOBILE',roleGroup:'GENERIC',objectScale:1,routeLeadPixels:28,
  directionalLeadBodyRatio:.78,arrivalRadiusScale:1,arrivalPeakProgress:.22});
 const primitive=compileFlowRoute(flow.intent,{project}),style=selectEventLineStyle({
  role:flow.routeEventPlan.intent.line.style_role,theme,primaryMaterialColor});
 const protection=checkBoundaries(id,primitive,supports(flow.intent,style,profile),boundarySegments,safeArea);
 const footprint=validateEventLineFootprint(primitive,{style,safeArea,protectedGraphics});
 return{...protection,primitive,totalLengthPixels:primitive.totalLengthPixels,style,
  fullRouteRoi:copy(footprint.fullRoi),routeFootprintProtection:footprint.policy,
  nativeTextAndPanelCollisionCheck:true};
}

export async function createPlannerCausalGpuAdapter({canvas,plans,cameraPlan,scene,heightSource=null,
 contextTerrain=null,causalPlan,presentation={}}={}){
 if(!integer(causalPlan?.totalFrames,1)||!Array.isArray(causalPlan.flowTracks))
  throw Error('PLANNER_CAUSAL_PLAN_REQUIRED');
 const areaPlan=assertAreaPlan(causalPlan.areaPlan),safeArea=copy(plans?.REGIONAL?.layout?.safe);
 if(!rectangle(safeArea))throw Error('PLANNER_CAUSAL_NATIVE_SAFE_AREA_REQUIRED');
 const cameraStartFrame=presentation.cameraStartFrame,eventStartFrame=presentation.eventStartFrame??0;
 if(!integer(cameraStartFrame))throw Error('PLANNER_CAUSAL_EXPLICIT_CAMERA_START_FRAME_REQUIRED');
 if(!integer(eventStartFrame))throw Error('PLANNER_CAUSAL_INTEGER_CAMERA_CLOCK_REQUIRED');
 if(eventStartFrame+areaPlan.totalFrames!==causalPlan.totalFrames)
  throw Error('PLANNER_CAUSAL_AREA_SCENE_CLOCK_BINDING_REQUIRED');
 const ids=new Set();
 const entries=causalPlan.flowTracks.map(value=>{
  const plan=assertFlowPlan(value.plan),fadeInFrames=value.fadeInFrames??6,fadeOutFrames=value.fadeOutFrames??10;
  if(typeof value.id!=='string'||!value.id.trim()||ids.has(value.id))throw Error('PLANNER_CAUSAL_UNIQUE_TRACK_ID_REQUIRED');
  ids.add(value.id);
  if(plan.fps!==areaPlan.fps||plan.endFrame>causalPlan.totalFrames||!integer(fadeInFrames)||!integer(fadeOutFrames))
   throw Error('PLANNER_CAUSAL_FLOW_SCENE_CLOCK_BINDING_REQUIRED');
  return{id:value.id,plan,track:copy(value.track??{}),fadeInFrames,fadeOutFrames,passes:new Map(),
   profile:value.visualProfile?assertFlowVisualProfile(value.visualProfile):
    compileFlowVisualProfile({profileName:'GENERIC_CAUSAL_MOBILE',roleGroup:'GENERIC',objectScale:1,
     routeLeadPixels:28,directionalLeadBodyRatio:.78,arrivalRadiusScale:1,arrivalPeakProgress:.22}),
   style:selectEventLineStyle({role:plan.routeEventPlan.intent.line.style_role,theme:plans.REGIONAL.theme,
    primaryMaterialColor:plans.REGIONAL.theme.primary})};
 });
 let native,overlay,annotation,last=null,disposed=false;
 try{
  native=await createAreaNativeBridge({canvas,plans,cameraPlan,scene,heightSource,contextTerrain});
  overlay=createAreaOverlayPass({canvas});
  for(const entry of entries)entry.passes.set(1,createFlowGraphicPass({canvas,style:entry.style}));
  if(presentation.annotations?.length)annotation=createAreaAnnotation({renderer:native.renderer,
   labels:presentation.annotations,dataMode:areaPlan.intent.data_mode,geographicAnchor:areaPlan.intent.origin,
   safeArea,width:WIDTH,height:HEIGHT});
 }catch(error){for(const entry of entries)for(const pass of entry.passes.values())pass.dispose();
  annotation?.dispose();overlay?.dispose();native?.dispose();throw error;}
 const gl=canvas.getContext('webgl2');
 const pixels=()=>{
  if(disposed)throw Error('PLANNER_CAUSAL_ADAPTER_DISPOSED');
  const bytes=new Uint8Array(WIDTH*HEIGHT*4);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
  gl.readPixels(0,0,WIDTH,HEIGHT,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('PLANNER_CAUSAL_READ_PIXELS_GL_ERROR_'+error);
  return bytes;
 };
 function drawFrame(frame,{areaEnabled=true,flowEnabled=true,protect=false}={}){
  if(disposed)throw Error('PLANNER_CAUSAL_ADAPTER_DISPOSED');
  if(!integer(frame)||frame>=causalPlan.totalFrames)throw Error('PLANNER_CAUSAL_FRAME_OUT_OF_RANGE');
  if([areaEnabled,flowEnabled,protect].some(value=>typeof value!=='boolean'))throw Error('PLANNER_CAUSAL_DRAW_BOOLEAN_REQUIRED');
  const nativeFrame=native.drawNative(cameraStartFrame+frame),active=areaEnabled&&frame>=eventStartFrame;
  const activeEntries=flowEnabled?entries.filter(entry=>frame>=entry.plan.startFrame&&frame<entry.plan.endFrame):[];
  if((active||activeEntries.length)&&(nativeFrame.cameraLocked!==true||nativeFrame.settle?.locked!==true))
   throw Error('PLANNER_CAUSAL_ACTUAL_NATIVE_CAMERA_LOCK_REQUIRED');
  // Project and reject every active overlay before either event pass writes pixels.
  const projected=entries.map(entry=>({entry,primitive:compileFlowRoute(entry.plan.intent,{project:native.project})}));
  const pending=activeEntries.map(entry=>{
   const checked=preflightPlannerCausalFlowTrack({id:entry.id,plan:entry.plan,project:native.project,safeArea,
    protectedGraphics:nativeFrame.protectedGraphics,boundarySegments:nativeFrame.boundarySegments,
    theme:plans.REGIONAL.theme,primaryMaterialColor:plans.REGIONAL.theme.primary,visualProfile:entry.profile});
   const {primitive,style,totalLengthPixels,fullRouteRoi,...preflight}=checked;
   const sourceControls=evaluateFlowFrame(entry.plan,frame,{primitive,eventContext:{cameraState:nativeFrame,
    project:native.project,safeArea,scalePlan:plans.REGIONAL,heightSource,
    protectedBoxes:nativeFrame.protectedGraphics.filter(item=>item.kind!=='MARKER').map(item=>item.box)}});
   const visual=applyFlowVisualProfile({flowPlan:entry.plan,controls:sourceControls,primitive,profile:entry.profile});
   const opacity=opacityAt(frame,entry),objectGraphic=copy(visual.objectGraphic),
    objectAge=frame-entry.plan.startFrame-entry.plan.timing.object_start_frame,
    objectOpacity=Math.min(opacity,entry.fadeInFrames<=1?1:clamp(objectAge/(entry.fadeInFrames-1)));
   for(const polygon of objectGraphic.polygons)polygon.color[3]*=objectOpacity;
   const controls={...copy(visual.controls),departurePulse:{...copy(visual.controls.departurePulse),
    alpha:visual.controls.departurePulse.alpha*opacity},arrivalPulse:{...copy(visual.controls.arrivalPulse),
    alpha:visual.controls.arrivalPulse.alpha*opacity}};
   controls.pulse=copy(controls.arrivalPulse.active?controls.arrivalPulse:controls.departurePulse);
   return{entry,primitive,preflight,sourceControls,controls,objectGraphic,opacity,objectOpacity,visualMetadata:visual.metadata};
  });
  let areaControls=null,text=null;
  if(active){
   areaControls=evaluateAreaFrame(areaPlan,areaPlan.startFrame+frame-eventStartFrame,{project:native.project});
   if(annotation){
    const middle=[(safeArea[0]+safeArea[2])/2,(safeArea[1]+safeArea[3])/2];
    const routeReservations=projected.map(({entry,primitive})=>routeBounds(primitive,
     Math.max(...Object.values(supports(entry.plan.intent,entry.style,entry.profile)))));
    const placement=annotation.place({anchor:native.project(areaControls.origin),
     anchorCandidates:[middle,[middle[0],safeArea[1]+180],[middle[0],safeArea[3]-240],
      [safeArea[2]-260,middle[1]],[safeArea[0]+260,middle[1]]],safeArea,
     protectedGraphics:nativeFrame.protectedGraphics,protectedBoxes:routeReservations,
     boundarySegments:nativeFrame.boundarySegments});
    const selected=presentation.annotations.find(label=>label.id===areaControls.stateId);
    if(!selected)throw Error('PLANNER_CAUSAL_AREA_STATE_ANNOTATION_REQUIRED');
    text={id:selected.id,placement,reservation:placement.reservation};
   }
  }
  const reservations=[...nativeFrame.protectedGraphics,...(text?[text.reservation]:[])];
  if(reservations.length>64)throw Error('PLANNER_CAUSAL_NATIVE_RESERVATION_CAPACITY');
  for(const item of pending)validateEventLineFootprint(item.primitive,
   {style:item.entry.style,safeArea,protectedGraphics:reservations});
  gl.finish();const before=protect?pixels():null;
  let areaGraphics=null;const rois=[];
  if(active){
   const bounds=nativeFrame.camera.flatBounds,
    mediumExclusions=presentation.propagationMedium==='WATER'||presentation.impactMedium==='WATER'
     ?plans.REGIONAL.geometries.filter(record=>{const b=geometryBounds(record);
      return b[0]<bounds[2]&&b[2]>bounds[0]&&b[1]<bounds[3]&&b[3]>bounds[1];
     }).map(record=>({type:record.geometry_type,coordinates:record.coordinates})):[];
   areaGraphics=overlay.draw({controls:areaControls,project:native.project,safeArea,protectedGraphics:reservations,
    primaryMaterialColor:plans.REGIONAL.theme.primary,boundarySegments:nativeFrame.boundarySegments,
    propagationExclusionGeometries:presentation.propagationMedium==='WATER'?mediumExclusions:[],
    impactExclusionGeometries:presentation.impactMedium==='WATER'?mediumExclusions:[]});
   rois.push(...areaGraphics.rois);
  }
  const flowTracks=pending.map(item=>{
   // The frozen line pass caches style at construction. Cache only the finite fade-clock values;
   // all variants use that existing pass and preserve the selected color and geometric footprint.
   const fadeStyle=copy(item.entry.style);
   fadeStyle.coreColor[3]*=item.opacity;fadeStyle.glowColor[3]*=item.opacity;
   if(!item.entry.passes.has(item.opacity))item.entry.passes.set(item.opacity,
    createFlowGraphicPass({canvas,style:fadeStyle}));
   const graphics=item.entry.passes.get(item.opacity).draw({primitive:item.primitive,controls:item.controls,safeArea,
    protectedGraphics:reservations,flowIntent:{...item.entry.plan.intent,object_graphic:item.objectGraphic}});
   rois.push(...graphics.rois);
   return{id:item.entry.id,enabled:true,track:copy(item.entry.track),sourceControls:item.sourceControls,
    controls:item.controls,graphics,primitive:item.primitive,preflight:item.preflight,opacity:item.opacity,
    objectOpacity:item.objectOpacity,actorVisible:item.sourceControls.objectVisible&&item.objectOpacity>0,
    source:copy(item.entry.plan.intent.route_source),style:fadeStyle,visualProfile:item.visualMetadata,
    motion:{engine:'UNCHANGED_FLOW_CORE_V2',heading:'UNCHANGED_FLOW_SAMPLE_ROUTE',
     sourcePlanStartFrame:item.entry.plan.startFrame,sourcePlanEndFrame:item.entry.plan.endFrame,
     objectPositionUnchanged:JSON.stringify(item.controls.objectPosition)===JSON.stringify(item.sourceControls.objectPosition),
     objectHeadingUnchanged:item.controls.heading===item.sourceControls.heading,physics:false}};
  });
  if(text){text={...text,...annotation.draw({id:text.id,placement:text.placement})};if(text.roi)rois.push(text.roi);}
  gl.finish();
  const protection={checked:protect,changedPixels:0,protectedChangedPixels:0,markerChangedPixels:0,
   textChangedPixels:0,outsideRoiChangedPixels:0,safeAreaChangedPixels:0,protectedBoundaryChangedPixels:0};
  if(protect){
   const after=pixels(),a=new Uint32Array(before.buffer),b=new Uint32Array(after.buffer),
    onBoundary=boundaryIndex(nativeFrame.boundarySegments);
   for(let index=0;index<b.length;index++)if(a[index]!==b[index]){
    const x=index%WIDTH,y=HEIGHT-1-Math.floor(index/WIDTH);protection.changedPixels++;
    if(!rois.some(roi=>inside(x,y,roi)))protection.outsideRoiChangedPixels++;
    if(!inside(x,y,safeArea))protection.safeAreaChangedPixels++;
    const overlaps=nativeFrame.protectedGraphics.filter(item=>inside(x,y,item.box));
    if(overlaps.length)protection.protectedChangedPixels++;
    if(overlaps.some(item=>item.kind==='MARKER'))protection.markerChangedPixels++;
    if(overlaps.some(item=>item.kind==='TEXT'||item.kind==='PANEL'))protection.textChangedPixels++;
    if(onBoundary(x,y))protection.protectedBoundaryChangedPixels++;
   }
   if(protection.protectedChangedPixels||protection.markerChangedPixels||protection.textChangedPixels
    ||protection.outsideRoiChangedPixels||protection.safeAreaChangedPixels||protection.protectedBoundaryChangedPixels)
    throw Object.assign(Error('PLANNER_CAUSAL_NATIVE_PIXEL_PROTECTION_FAILED'),{frame,protection});
  }
  const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('PLANNER_CAUSAL_COMPOSITION_GL_ERROR_'+glError);
  const {boundarySegments,...cameraDiagnostic}=nativeFrame;
  cameraDiagnostic.boundaryProtection={segmentCount:boundarySegments.length,
   source:'ACTUAL_NATIVE_PRIMARY_SECONDARY_RING_PROJECTION',finiteGlowSupport:true};
  last={frame,state:areaControls?.state??nativeFrame.state,camera:cameraDiagnostic,
   area:{enabled:active,controls:areaControls,graphics:areaGraphics,annotation:text,protection,geometryUnchanged:true},
   flowTracks,protection,rois:copy(rois),nativeDrawCount:1,width:WIDTH,height:HEIGHT,glError:0};
  return last;
 }
 return{drawFrame,project:native.project,readPixels:pixels,png:()=>canvas.toDataURL('image/png'),
  get diagnostic(){return last;},evidence:{version:PLANNER_CAUSAL_GPU_ADAPTER_V1_VERSION,
   cameraOwnership:'UNCHANGED_CAMERA_DIRECTOR_V5',projection:'ACTUAL_NATIVE_FACTORY_SCREEN',
   native:native.evidence,overlay:overlay.evidence,annotation:annotation?.evidence??null,
   flowPasses:entries.map(entry=>({id:entry.id,evidence:entry.passes.get(1).evidence})),factoryCount:1,
   sameWebGL2Context:true,nativeDrawsPerFrame:1,finishedFrameBlit:false,newShaders:false,newMotionEngine:false,
   boundaryProtection:'FULL_ROUTE_AND_SWEPT_FLOW_SUPPORT_REJECT_NATIVE_BOUNDARY_INTERSECTION',
   opacityOwnership:'PRESENTATION_FIXTURE_RGBA_PULSE_ALPHA_AND_CACHED_EXISTING_STYLE_VARIANTS',physics:false},
  dispose(){if(disposed)return;for(const entry of entries)for(const pass of entry.passes.values())pass.dispose();
   annotation?.dispose();overlay.dispose();native.dispose();disposed=true;}};
}
