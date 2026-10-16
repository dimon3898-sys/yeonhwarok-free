/** Additive redraw through public native APIs; no V5, projection or glyph source changes. */
import {geographicScaleVisualTokens} from '/modules/camera_gpu_pipeline_v5.mjs';
import {geographicTerrainLod} from '/modules/camera_gpu_pipeline_v2.mjs';
import {evaluateMovingLayout,validateVisibleMovingLayout} from '/modules/moving_layout_v4.mjs';
import {polygons} from '/modules/renderer.mjs';
import {compileProductionFocusPlan,evaluateProductionFocusFrame} from '/production-v3/production_camera.mjs';
const copy=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function nativeGraphicReservations(items){
 return items.map(item=>{const [x,y,w,h]=item.box,p=item.kind==='TEXT'?(item.outlineRadius??item.metrics?.outlineRadius??0)+2:2;
  if(![x,y,w,h,p].every(Number.isFinite)||w<=0||h<=0)throw Error('PRODUCTION_NATIVE_MEASURED_BOUNDS_REQUIRED');
  return{kind:item.kind,role:item.role,box:[x-p,y-p,x+w+p,y+h+p]};});
}
export function nativeBoundarySupport({regional,visual,project,width=1080,height=1920}){
 const secondary=new Set(regional.secondary??[]),result=[],primaryRadius=Math.max(visual.primaryWidth,visual.primaryEdgeWidth,visual.glowWidth)/2
  +Math.SQRT2*3.230769*visual.glowRadius+2,secondaryRadius=Math.max(visual.secondaryWidth,visual.secondaryEdgeWidth)/2+2;
 for(const record of regional.geometries.filter(row=>row.id===regional.primary||secondary.has(row.id))){
  const primary=record.id===regional.primary,radiusPx=primary?primaryRadius:secondaryRadius;
  for(const polygon of polygons(record))for(const ring of polygon)for(let i=1;i<ring.length;i++){
   const a=project(ring[i-1]),b=project(ring[i]);
   if(![...a,...b,radiusPx].every(Number.isFinite))throw Error('PRODUCTION_NATIVE_BOUNDARY_PROJECTION_REQUIRED');
   if(Math.max(a[0],b[0])+radiusPx>=0&&Math.min(a[0],b[0])-radiusPx<=width
    &&Math.max(a[1],b[1])+radiusPx>=0&&Math.min(a[1],b[1])-radiusPx<=height)
    result.push({a:[...a],b:[...b],radiusPx,role:primary?'PRIMARY':'SECONDARY',sourceId:record.id});
  }
 }
 if(result.length>8192)throw Error('PRODUCTION_NATIVE_BOUNDARY_MASK_CAPACITY');return result;
}
export function createProductionNativeCamera({native,plans,plan,request,cameraStartFrame,heightSource,contextTerrain,profile}){
 const original=JSON.stringify({plans,plan:plan.legacyScenePlan}),chapters=plan.productionV3.eventChapters,
  reference=native.drawNative(native.cameraPlan.totalFrames-1),safe=plans.REGIONAL.layout.safe,
  geometryById=new Map(plan.legacyScenePlan.geometries.map(row=>[row.id,row.geometry])),
  schedule=plan.productionV3.geometrySchedule,
  forChapter=chapter=>{
   const rows=schedule.filter(row=>row.chapterId===(chapter.chapterId??chapter.id)),states=new Set(rows.flatMap(row=>[row.sourceStateId,row.fromStateId,row.toStateId]).filter(Boolean)),
    steps=plan.legacyScenePlan.time_steps.filter(step=>states.has(step.id)),ids=new Set(steps.flatMap(step=>[
     ...step.area_ids.map(id=>plan.legacyScenePlan.areas.find(item=>item.id===id)?.geometry_ref),
     ...step.front_line_ids.map(id=>plan.legacyScenePlan.front_lines.find(item=>item.id===id)?.geometry_ref)]));
   const result=[...ids].map(id=>geometryById.get(id));if(!result.length||result.some(g=>!g))throw Error('PRODUCTION_CAMERA_CHAPTER_SOURCE_GEOMETRY_REQUIRED');return result;
  },focusChapters=chapters.filter(row=>row.endFrame>request.timing.eventStartFrame).map((row,index)=>({...row,
   startFrame:index===0?request.timing.eventStartFrame:row.startFrame})),
  focus=compileProductionFocusPlan({chapters:focusChapters,totalFrames:plan.totalFrames,approvedBounds:plans.REGIONAL.framing.bounds,
   safeArea:safe,anchor:request.origin,geometriesForChapter:forChapter,approachFrames:profile.cameraApproachFrames,preserveInitialView:true,
   validateBounds(bounds){try{
    const state={...reference,camera:{...reference.camera,flatBounds:bounds}},visual=geographicScaleVisualTokens(bounds,plans),
     layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual}),
     validation=validateVisibleMovingLayout(layout,reference.reveal);return{valid:validation.valid};
   }catch{return{valid:false};}}});
 function drawNative(globalFrame){
  const base=native.drawNative(cameraStartFrame+globalFrame);if(globalFrame<request.timing.eventStartFrame)return{...base,
   productionCamera:{decision:'PRESERVE_PARENT_ARRIVAL',cameraLocked:base.cameraLocked,surveyAdmissionModified:false}};
  if(base.cameraLocked!==true||base.settle?.locked!==true)throw Error('PRODUCTION_EVENT_REQUIRES_ACTUAL_PARENT_DETAIL_LOCK');
  const selected=evaluateProductionFocusFrame(focus,globalFrame),bounds=selected.flatBounds,
   visual=geographicScaleVisualTokens(bounds,plans),state={...base,camera:{...base.camera,flatBounds:bounds},
    cameraLocked:selected.cameraLocked,settle:copy(selected.settle)},
   layout=evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual}),
   validation=validateVisibleMovingLayout(layout,base.reveal);
  if(!validation.valid)throw Error('PRODUCTION_ACTUAL_PROTECTED_GRAPHIC_LAYOUT_INVALID');
  let lod=base.gpu?.terrainLod;
  if(!same(bounds,base.camera.flatBounds)){
   lod=geographicTerrainLod(bounds,contextTerrain??plans.CONTINENT.assets.terrain,plans.REGIONAL.assets.terrain,1080,1920);
   native.factory.updateCamera(bounds);native.factory.setScaleVisual(visual);native.factory.setTerrainLod(lod.weight);
   const result=native.factory.renderFrame({...native.evidence.frozenMaterialParameters,graphics:false,reveal:base.reveal,primaryMaterial:1});
   if(result.glError)throw Error('PRODUCTION_NATIVE_REDRAW_GL_ERROR_'+result.glError);
  }
  if(JSON.stringify({plans,plan:plan.legacyScenePlan})!==original)throw Error('PRODUCTION_NATIVE_SOURCE_MUTATION');
  return{...state,layoutItems:layout.items,protectedGraphics:nativeGraphicReservations(layout.items),
   boundarySegments:nativeBoundarySupport({regional:plans.REGIONAL,visual,project:native.project}),
   productionCamera:{...selected,actualNativeCamera:copy(native.factory.evidence.cameraFrame),
    protectedGraphicsSafe:true,parentSourceUnchanged:true,additionalNativeDraw:!same(bounds,base.camera.flatBounds),
    actualNvidiaPerformanceMeasured:false},safeArea:copy(safe),gpu:{...base.gpu,actualCamera:copy(native.factory.evidence.cameraFrame),
     boundaryPixels:copy(visual),terrainLod:copy(lod),layout:copy(layout.items),layoutValidation:validation,
     layoutEligibilityValidation:copy(layout.validation),cameraDiagnosticOwner:'ACTUAL_EXTENSION_FACTORY_AND_LAYOUT'}};
 }
 return{drawNative,focusPlan:focus,evidence:{version:'PRODUCTION_NATIVE_CAMERA_EXTENSION_V3',
  source:'UNCHANGED_V5_BASELINE_PLUS_ORIGINAL_FACTORY_LAYOUT_SCALE_AND_DETAIL_EASING',
  closerThanParentFloor:false,localAdmissionGranted:false,originalMarkerArtAndAnchorUnchanged:true,
  originalScaleMarkerSizePreserved:true,extraNativeRedrawPossible:true,nvidiaPerformanceMeasured:false}};
}
