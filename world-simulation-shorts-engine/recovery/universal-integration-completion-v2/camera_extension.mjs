/** Source-bound event tracking over preserved V5 math and native public APIs. No new camera spline or projection. */
import {compileMinimumContextPlan,evaluateMinimumContextCameraFrame} from '/modules/camera_director_v5.mjs';
import {geometryScreenSafety,compileProductionFocusPlan} from '/production-v3/production_camera.mjs';
const copy=value=>structuredClone(value),object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v),
 fail=code=>{throw Error(code);},same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),
 near=(a,b)=>Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((v,i)=>Math.abs(v-b[i])<=1e-8),
 validBounds=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3]
  &&b[0]>=-180&&b[2]<=180&&b[1]>=-90&&b[3]<=90;
export const COMPLETION_CAMERA_VERSION='SOURCE_BOUND_V5_EVENT_CAMERA_COMPLETION_V2';
export function normalizeCompletionCamera(input={mode:'V5_EVENT_TRACKING'}){
 if(!object(input)||Object.keys(input).some(key=>!['mode','settleFrames','holdFrames'].includes(key)))fail('COMPLETION_CAMERA_FIELD_UNSUPPORTED');
 const mode=Object.hasOwn(input,'mode')?input.mode:'V5_EVENT_TRACKING';
 if(mode==='PRESERVE_PARENT'){
  if(Object.keys(input).some(key=>key!=='mode'))fail('COMPLETION_CAMERA_PARENT_SETTINGS_UNSUPPORTED');
  return Object.freeze({mode});
 }
 if(mode!=='V5_EVENT_TRACKING')fail('COMPLETION_CAMERA_MODE_UNSUPPORTED');
 const settleFrames=Object.hasOwn(input,'settleFrames')?input.settleFrames:18,
  holdFrames=Object.hasOwn(input,'holdFrames')?input.holdFrames:24;
 if(!Number.isSafeInteger(settleFrames)||settleFrames<6||settleFrames>60)fail('COMPLETION_CAMERA_SETTLE_RANGE');
 if(!Number.isSafeInteger(holdFrames)||holdFrames<0||holdFrames>120)fail('COMPLETION_CAMERA_HOLD_RANGE');
 return Object.freeze({mode,settleFrames,holdFrames});
}
/** Select existing source geometry references only. No country/date inference or generated coordinates. */
export function completionChapterGeometries(plan,chapter){
 const legacy=plan?.legacyScenePlan,schedule=plan?.productionV3?.geometrySchedule;
 if(!legacy||!Array.isArray(schedule)||!chapter)fail('COMPLETION_CAMERA_SOURCE_PLAN_REQUIRED');
 const states=new Set(schedule.filter(row=>row.chapterId===(chapter.chapterId??chapter.id))
  .flatMap(row=>[row.sourceStateId,row.fromStateId,row.toStateId]).filter(Boolean)),
  steps=legacy.time_steps.filter(step=>states.has(step.id)),ids=new Set(steps.flatMap(step=>[
   ...step.area_ids.map(id=>legacy.areas.find(item=>item.id===id)?.geometry_ref),
   ...step.front_line_ids.map(id=>legacy.front_lines.find(item=>item.id===id)?.geometry_ref)])),
  geometries=[...ids].map(id=>legacy.geometries.find(row=>row.id===id)?.geometry);
 if(!geometries.length||geometries.some(geometry=>!geometry))fail('COMPLETION_CAMERA_QUALIFIED_SOURCE_GEOMETRY_REQUIRED');
 return copy(geometries);
}
/** Explicit minimum-context references are geography, never inferred ownership or generated movement. */
export function completionRelationGeometries(plan){
 const legacy=plan?.legacyScenePlan,refs=legacy?.camera_intent?.minimum_context_geometry_refs??[];
 if(!Array.isArray(refs)||refs.length>64||refs.some(ref=>typeof ref!=='string'||!ref))
  fail('COMPLETION_CAMERA_CONTEXT_REFS_REQUIRED');
 const result=refs.map(ref=>legacy.geometries.find(row=>row.id===ref)?.geometry);
 if(result.some(geometry=>!geometry))fail('COMPLETION_CAMERA_CONTEXT_SOURCE_MISSING');
 return copy(result);
}
function checkFrame({bounds,geometries,floor,safeArea,validateBounds,globalFrame}){
 if(!validBounds(bounds)||bounds[2]-bounds[0]<floor[2]-floor[0]-1e-8
  ||bounds[3]-bounds[1]<floor[3]-floor[1]-1e-8)fail('COMPLETION_CAMERA_PARENT_FLOOR_PROTECTED');
 if(!geometryScreenSafety({geometries,bounds,safeArea}).wholeSuppliedGeometrySafe)
  fail('COMPLETION_CAMERA_SOURCE_OUTSIDE_SAFE_AREA');
 const admission=validateBounds(bounds,globalFrame);
 if(admission?.valid!==true)fail(admission?.reason==='ALL_TIMELINE_SOURCE_OUTSIDE_SAFE_AREA'
  ?'COMPLETION_CAMERA_TIMELINE_SOURCE_UNSAFE':'COMPLETION_CAMERA_NATIVE_LAYOUT_UNSAFE');
}
/** Camera-only plans end at existing V5 LOCK. Event text/graphics remain their original owners. */
export function compileCompletionCameraTracking({plan,request,parentFocusPlan,safeArea,camera,
 geometriesForChapter=chapter=>completionChapterGeometries(plan,chapter),validateBounds,approachFrames=48}={}){
 const settings=normalizeCompletionCamera(camera);
 if(settings.mode!=='V5_EVENT_TRACKING')fail('COMPLETION_CAMERA_TRACKING_OPT_IN_REQUIRED');
 if(parentFocusPlan?.version!=='UNIVERSAL_PRODUCTION_CAMERA_V3'||!Array.isArray(parentFocusPlan.entries)
  ||!parentFocusPlan.entries.length||!Number.isSafeInteger(plan?.fps)||plan.fps<1||plan.fps>120
  ||parentFocusPlan.totalFrames!==plan.totalFrames||!validBounds(parentFocusPlan.approvedBounds)
  ||typeof validateBounds!=='function'||!Number.isSafeInteger(approachFrames)||approachFrames<12||approachFrames>120)
  fail('COMPLETION_CAMERA_PARENT_PLAN_AND_LAYOUT_REQUIRED');
 const entries=[],floor=parentFocusPlan.approvedBounds,chapters=plan.productionV3?.eventChapters,
  relationGeometry=completionRelationGeometries(plan);
 for(const [index,row]of parentFocusPlan.entries.entries()){
  const chapter=chapters?.find(item=>(item.chapterId??item.id)===row.chapterId);
  if(!chapter||row.endFrame-row.startFrame<1)fail('COMPLETION_CAMERA_CHAPTER_BINDING_REQUIRED');
  if(index===0){entries.push({...copy(row),kind:'PRESERVE_INITIAL_DETAIL_LOCK',v5Plan:null,
   reason:'Original arrival, first Detail lock and first source reveal are retained'});continue;}
  const prior=chapters.find(item=>(item.chapterId??item.id)===parentFocusPlan.entries[index-1].chapterId),
   geometries=[...geometriesForChapter(prior),...geometriesForChapter(chapter)],
   polygons=geometries.filter(geometry=>['Polygon','MultiPolygon'].includes(geometry?.type));
  if(!polygons.length)fail('COMPLETION_CAMERA_AREA_PRIMARY_SOURCE_REQUIRED');
  const first=entries.at(-1).targetBounds;
  if(!near(first,row.startBounds))fail('COMPLETION_CAMERA_PARENT_CONTINUITY_REQUIRED');
  // V5 owns start/context/final admission. A source plan which cannot preserve
  // the prior literal pose is rejected rather than inventing an arrival cut.
  const scene={primary_region_id:chapter.chapterId??chapter.id,primary_geometry:copy(polygons),
   event_geometry:copy(geometries),event_anchor:copy(request.origin),approved_final_extent:copy(row.targetBounds),
   start_extent:copy(first),canonical_output:[1080,1920],safe_area:copy(safeArea),desired_detail_level:'REGIONAL',
   scale_admission:{status:'LOCAL_NOT_ADMITTED'},event_title:'',location_label:'',primary_label:''},
   v5Plan=compileMinimumContextPlan({scene,profile:{fps:plan.fps,recognitionSeconds:1/plan.fps,
    relationSeconds:1/plan.fps,settleSeconds:settings.settleFrames/plan.fps,lockSeconds:1/plan.fps,
    titleEntrySeconds:1/plan.fps,minimumTitlePerceptionSeconds:1/plan.fps,locationPerceptionSeconds:1/plan.fps,
    nextSeconds:1/plan.fps,approachBaseSeconds:approachFrames/plan.fps},relationGeometry}),
   lock=v5Plan.timeline.find(item=>item.state==='LOCK'),budget=row.endFrame-row.startFrame;
  if(!lock||lock.endFrame+settings.holdFrames>budget)fail('COMPLETION_CAMERA_CHAPTER_MOTION_BUDGET_INSUFFICIENT');
  if(!near(evaluateMinimumContextCameraFrame(v5Plan,0).camera.flatBounds,first))
   fail('COMPLETION_CAMERA_V5_START_WOULD_JUMP');
  for(let offset=0;offset<lock.endFrame;offset++)checkFrame({
   bounds:evaluateMinimumContextCameraFrame(v5Plan,offset).camera.flatBounds,geometries,floor,safeArea,
   validateBounds,globalFrame:row.startFrame+offset});
  checkFrame({bounds:row.targetBounds,geometries,floor,safeArea,validateBounds,globalFrame:row.endFrame-1});
  entries.push({...copy(row),kind:'V5_EVENT_TRACKING',v5Plan,activeFrames:lock.endFrame,
   settleFrames:settings.settleFrames,minimumHoldFrames:settings.holdFrames,actualHoldFrames:budget-lock.endFrame,
   actualV5Turn:v5Plan.naturalMotion.contextTurnSkipped===false,
   originalSourceGeometryCount:geometries.length,explicitContextGeometryCount:relationGeometry.length,
   qualifiedSourceFramingNotExactDailyFront:true});
 }
 return Object.freeze({version:COMPLETION_CAMERA_VERSION,totalFrames:plan.totalFrames,fps:plan.fps,
  settings,entries,floor:copy(floor),initialArrivalUnchanged:true,rollSupported:false,
  closerThanParentFloor:false,geometryInvented:false,nativeLayoutPreflightRequired:true,
  cpuOnlyProof:true,actualGPUOutputVerified:false});
}
export function evaluateCompletionCameraFrame(compiled,frame){
 if(compiled?.version!==COMPLETION_CAMERA_VERSION||!Number.isSafeInteger(frame)||frame<0||frame>=compiled.totalFrames)
  fail('COMPLETION_CAMERA_GLOBAL_FRAME_REQUIRED');
 const row=compiled.entries.find(entry=>frame>=entry.startFrame&&frame<entry.endFrame);
 if(!row)return{frame,kind:'PRESERVE_PARENT_ARRIVAL',ownsBounds:false};
 if(row.kind==='PRESERVE_INITIAL_DETAIL_LOCK')return{frame,kind:row.kind,ownsBounds:false};
 const localFrame=Math.min(frame-row.startFrame,row.activeFrames-1),state=evaluateMinimumContextCameraFrame(row.v5Plan,localFrame),
  hold=frame-row.startFrame>=row.activeFrames;
 return{...copy(state),frame,localFrame,chapterId:row.chapterId,kind:row.kind,ownsBounds:true,
  camera:{...copy(state.camera),flatBounds:copy(state.camera.flatBounds)},
  state:hold?'EVENT_TRACKING_HOLD':state.state,cameraLocked:hold||state.settle.locked===true,
  settle:hold?{phase:'EVENT_TRACKING_HOLD',settled:true,locked:true}:copy(state.settle),
  actualV5Turn:row.actualV5Turn,settleFrames:row.settleFrames,minimumHoldFrames:row.minimumHoldFrames,
  actualHoldFrames:row.actualHoldFrames,rollSupported:false,closerThanParentFloor:false,
  source:'UNCHANGED_V5_MINIMUM_CONTEXT_AND_NATURAL_TURNAROUND',cpuOnlyProof:true,actualGPUOutputVerified:false};
}
const operationNames=['geographicScaleVisualTokens','geographicTerrainLod','evaluateMovingLayout','validateVisibleMovingLayout',
 'nativeGraphicReservations','nativeBoundarySupport'];
/** Invoke the exact original camera factory, then redraw only through its native factory/layout APIs. */
export function createCompletionNativeCamera(input,{camera,originalFactory,operations}={}){
 const settings=normalizeCompletionCamera(camera);
 if(typeof originalFactory!=='function')fail('COMPLETION_CAMERA_ORIGINAL_FACTORY_REQUIRED');
 if(settings.mode==='PRESERVE_PARENT')return originalFactory(input);
 if(typeof input?.native?.drawNative!=='function'||operationNames.some(name=>typeof operations?.[name]!=='function'))
  fail('COMPLETION_CAMERA_NATIVE_PUBLIC_APIS_REQUIRED');
 if(!Number.isSafeInteger(input.cameraStartFrame)||input.cameraStartFrame<0||!Number.isSafeInteger(input.request?.timing?.eventStartFrame))
  fail('COMPLETION_CAMERA_NATIVE_CLOCK_REQUIRED');
 const {native,plans,plan,request,contextTerrain,profile,cameraStartFrame}=input,ops=operations,
  reference=native.drawNative(native.cameraPlan.totalFrames-1),safeArea=plans.REGIONAL.layout.safe,
  chapters=plan.productionV3.eventChapters.filter(row=>row.endFrame>request.timing.eventStartFrame)
   .map((row,index)=>({...row,startFrame:index===0?request.timing.eventStartFrame:row.startFrame})),
  allGeometry=chapters.flatMap(chapter=>completionChapterGeometries(plan,chapter)),
  validateBounds=bounds=>{
   // The previous parent focus compiler checked only adjacent source states.
   // A locally safe earlier pan could strand a later, larger supplied state.
   // Strengthen its caller predicate without changing that compiler or source.
   if(!geometryScreenSafety({geometries:allGeometry,bounds,safeArea}).wholeSuppliedGeometrySafe)
    return{valid:false,reason:'ALL_TIMELINE_SOURCE_OUTSIDE_SAFE_AREA'};
   const visual=ops.geographicScaleVisualTokens(bounds,plans),state={...reference,camera:{...reference.camera,flatBounds:bounds}},
    layout=ops.evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual});
   return ops.validateVisibleMovingLayout(layout,reference.reveal);
  },focusPlan=compileProductionFocusPlan({chapters,totalFrames:plan.totalFrames,approvedBounds:plans.REGIONAL.framing.bounds,
   safeArea,anchor:request.origin,geometriesForChapter:chapter=>completionChapterGeometries(plan,chapter),
   approachFrames:profile.cameraApproachFrames,preserveInitialView:true,validateBounds}),
  tracking=compileCompletionCameraTracking({plan,request,parentFocusPlan:focusPlan,safeArea,
   camera:settings,validateBounds,approachFrames:profile.cameraApproachFrames});
 return{focusPlan,completionFocusPlan:tracking,
  drawNative(globalFrame){
   const selected=evaluateCompletionCameraFrame(tracking,globalFrame),base=native.drawNative(cameraStartFrame+globalFrame);
   if(!selected.ownsBounds)return{...base,productionCamera:{decision:'PRESERVE_PARENT_ARRIVAL_AND_FIRST_DETAIL_LOCK',
    cameraLocked:base.cameraLocked,parentSourceUnchanged:true,completionV2:{...selected,originalV5NativeSource:true}}};
   if(base.cameraLocked!==true||base.settle?.locked!==true)fail('COMPLETION_CAMERA_PARENT_DETAIL_AND_SOURCE_REQUIRED');
   const bounds=selected.camera.flatBounds,visual=ops.geographicScaleVisualTokens(bounds,plans),
    state={...base,camera:{...base.camera,flatBounds:bounds},cameraLocked:selected.cameraLocked,settle:copy(selected.settle)},
    layout=ops.evaluateMovingLayout(native.layoutContract,state,{markerSize:visual.markerSize,boundaryTokens:visual}),
    validation=ops.validateVisibleMovingLayout(layout,base.reveal);
   if(validation.valid!==true)fail('COMPLETION_CAMERA_DRAW_LAYOUT_UNSAFE');
   let lod=base.gpu?.terrainLod;
   if(!same(bounds,base.camera.flatBounds)){
    lod=ops.geographicTerrainLod(bounds,contextTerrain??plans.CONTINENT.assets.terrain,plans.REGIONAL.assets.terrain,1080,1920);
    native.factory.updateCamera(bounds);native.factory.setScaleVisual(visual);native.factory.setTerrainLod(lod.weight);
    const rendered=native.factory.renderFrame({...native.evidence.frozenMaterialParameters,graphics:false,reveal:base.reveal,primaryMaterial:1});
    if(rendered.glError)fail('COMPLETION_CAMERA_NATIVE_REDRAW_FAILED');
   }
   return{...state,layoutItems:layout.items,protectedGraphics:ops.nativeGraphicReservations(layout.items),
    boundarySegments:ops.nativeBoundarySupport({regional:plans.REGIONAL,visual,project:native.project}),
    productionCamera:{parentSourceUnchanged:true,completionV2:{...selected,actualNativeCamera:copy(native.factory.evidence.cameraFrame),
     protectedGraphicsSafe:true,originalProjectionAndFactory:true,extraNativeDraw:!same(bounds,base.camera.flatBounds)}},
    gpu:{...base.gpu,actualCamera:copy(native.factory.evidence.cameraFrame),boundaryPixels:visual,terrainLod:copy(lod),
     layout:copy(layout.items),layoutValidation:validation}};
  },evidence:{version:COMPLETION_CAMERA_VERSION,completionV2:{version:COMPLETION_CAMERA_VERSION,settings,
   originalProductionV3FactoryInvoked:false,originalNativeV5FactoryReused:true,
   originalProductionFocusCompilerReused:true,allTimelineGeometrySafetyStrengthened:true,
   originalV5EvaluatorInvoked:true,nativeProjectionAndLayoutRetained:true,
   rollSupported:false,closerThanParentFloor:false,hardwareVerified:false,visualOutputVerified:false}}};
}
