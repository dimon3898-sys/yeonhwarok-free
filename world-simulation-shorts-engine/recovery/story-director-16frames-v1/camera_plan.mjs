/** Explicit director data over the original 65422 reference-camera adapter.
 * No camera spline, geographic projection, source geometry or V5 source is copied.
 * Camera-only local sample reversal supports a wider endpoint; the Scene clock
 * always remains the caller's original 0..2399 global integer frame.
 */
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '/modules/reference_camera_adapter_v1.mjs';
import {geometryBounds,fitGeographicExtent} from '/modules/scale_contract.mjs';
import {geometryScreenSafety} from '/production-v3/production_camera.mjs';
const clone=value=>structuredClone(value),span=b=>[b[2]-b[0],b[3]-b[1]],
 same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),
 union=rows=>[Math.min(...rows.map(b=>b[0])),Math.min(...rows.map(b=>b[1])),
  Math.max(...rows.map(b=>b[2])),Math.max(...rows.map(b=>b[3]))],
 center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2];
function fail(code){throw Error(code);}
export function directorVisibleReveal(reveal,profile){
 if(!reveal||typeof reveal!=='object')fail('DIRECTOR_ORIGINAL_REVEAL_REQUIRED');
 const result=clone(reveal);
 if(profile?.hideDuplicateNativeHeadline===true)result.title=0;
 return result;
}
export function validateDirectorCameraProfile(profile,plan){
 if(profile?.schema!=='WORLD_ENGINE_STORY_DIRECTOR_CAMERA_V1'||profile.mode!=='SOFTWARE_PREVIEW'
  ||profile.productionEligible!==false||profile.fps!==plan?.fps||profile.totalFrames!==plan?.totalFrames
  ||!Array.isArray(profile.chapters)||profile.chapters.length!==plan?.productionV3?.eventChapters?.length)
  fail('DIRECTOR_CAMERA_EXPLICIT_BOUND_SOFTWARE_PROFILE_REQUIRED');
 if(profile.hideDuplicateNativeHeadline!==undefined&&typeof profile.hideDuplicateNativeHeadline!=='boolean')
  fail('DIRECTOR_CAMERA_HEADLINE_POLICY_BOOLEAN_REQUIRED');
 for(const [index,row]of profile.chapters.entries()){
  const source=plan.productionV3.eventChapters[index];
  if(row.chapterId!==source.chapterId||row.eventId!==source.eventId||row.startFrame!==source.startFrame
   ||row.endFrame!==source.endFrame||!Array.isArray(row.geometryRefs)||!row.geometryRefs.length
   ||!Array.isArray(row.locationIds)||!Number.isFinite(row.padding)||row.padding<1||row.padding>1.5
   ||!Number.isSafeInteger(row.approachFrames)||row.approachFrames<30||row.approachFrames>180)
   fail('DIRECTOR_CAMERA_ORIGINAL_CHAPTER_BINDING_REQUIRED');
 }
 return clone(profile);
}
export function resolveDirectorChapterGeometry({plan,frontProfile,row}){
 const geometryById=new Map(plan.legacyScenePlan.geometries.map(item=>[item.id,item.geometry])),
  fronts=new Map((frontProfile?.fronts??[]).map(item=>[item.frontId,item.geometry])),
  locationById=new Map(plan.legacyScenePlan.locations.map(item=>[item.id,item.anchor]));
 const geometries=row.geometryRefs.map(id=>{
  const geometry=geometryById.get(id)??fronts.get(id);if(!geometry)fail('DIRECTOR_CAMERA_SOURCE_GEOMETRY_MISSING_'+id);
  return clone(geometry);
 }),locations=row.locationIds.map(id=>{
  const anchor=locationById.get(id);if(!anchor)fail('DIRECTOR_CAMERA_SOURCE_LOCATION_MISSING_'+id);
  return{id,anchor:[...anchor],meaning:'GEOGRAPHIC_CONTEXT_ONLY_NOT_HISTORICAL_UNIT_POSITION'};
 });
 return{geometries,locations,geometryRefs:[...row.geometryRefs]};
}
function paddedBounds(bounds,factor){
 const c=center(bounds),s=span(bounds).map(v=>v*factor);
 return[c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2];
}
export function directorBoundsAtAdmittedFloor(bounds,minimumBounds){
 if(!Array.isArray(minimumBounds)||minimumBounds.length!==4||!minimumBounds.every(Number.isFinite)
  ||minimumBounds[0]>=minimumBounds[2]||minimumBounds[1]>=minimumBounds[3])
  fail('DIRECTOR_CAMERA_ACTUAL_NATIVE_CLOSEST_EXTENT_REQUIRED');
 const actual=span(bounds),minimum=span(minimumBounds),factor=Math.max(1,minimum[0]/actual[0],minimum[1]/actual[1]);
 return factor===1?[...bounds]:paddedBounds(bounds,factor);
}
function compileSegment({baseCameraPlan,currentNativeFrame,start,target,totalFrames,fps,holdFrames}){
 // The existing reference adapter requires its last endpoint to be closest.
 // Preserve that contract and reverse only the camera sampler when widening.
 const reverse=span(target).some((value,index)=>value>span(start)[index]+1e-9),
  from=reverse?target:start,to=reverse?start:target,
  duration=Math.max(4,totalFrames),hold=Math.min(holdFrames,Math.floor((duration-2)/3)),
  keys=[{frame:0,bounds:from},{frame:hold,bounds:from},
   {frame:duration-1-hold,bounds:to},{frame:duration-1,bounds:to}];
 // Regional aspect changes with latitude. A directional mix of spans can
 // violate the original closest-endpoint rule. A same-area padded endpoint
 // is not silently invented: reject and let the caller report the limitation.
 const track=compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes:keys,totalFrames:duration,fps});
 return{track,reverse,totalFrames:duration};
}
export function compileStoryDirectorCamera({profile,plan,frontProfile,baseCameraPlan,currentNativeFrame,
 safeArea,minimumBounds,validateBounds=()=>({valid:true}),output=[1080,1920]}={}){
 const settings=validateDirectorCameraProfile(profile,plan),entries=[],attempts=[],
  padding=Math.max(output[0]/(safeArea[2]-safeArea[0]-48),output[1]/(safeArea[3]-safeArea[1]-48));
 let previous=null;
 if(Array.isArray(settings.initialContextGeometryRefs)&&settings.initialContextGeometryRefs.length){
  const initial=resolveDirectorChapterGeometry({plan,frontProfile,row:{
   geometryRefs:settings.initialContextGeometryRefs,locationIds:settings.initialContextLocationIds??[]}}),
   required=union([...initial.geometries.map(geometryBounds),...initial.locations.map(item=>[...item.anchor,...item.anchor])]);
  previous=directorBoundsAtAdmittedFloor(fitGeographicExtent(required,{output,padding:padding*(settings.initialContextPadding??1.08)}),minimumBounds);
  if(validateBounds(previous,0)?.valid!==true)fail('DIRECTOR_CAMERA_INITIAL_CONTEXT_NATIVE_LAYOUT_UNSAFE');
 }
 for(const row of settings.chapters){
  const source=resolveDirectorChapterGeometry({plan,frontProfile,row}),
   required=union([...source.geometries.map(geometryBounds),...source.locations.map(item=>[...item.anchor,...item.anchor])]),
   desired=directorBoundsAtAdmittedFloor(fitGeographicExtent(required,{output,padding:padding*row.padding}),minimumBounds);
  let target=null,admission=null;
  // Existing native layout is the admission owner. Wider source views are
  // tried; no original text, marker or layout item is repositioned or hidden.
  for(const factor of [1,1.1,1.25,1.5,1.8,2.2]){
   const candidate=paddedBounds(desired,factor),native=validateBounds(candidate,row.startFrame),
    safety=geometryScreenSafety({geometries:source.geometries,bounds:candidate,safeArea,output});
   attempts.push({chapterId:row.chapterId,factor,wholeSourceSafe:safety.wholeSuppliedGeometrySafe,
    nativeLayoutValid:native?.valid===true,failures:clone(native?.failures??[])});
   if(native?.valid===true&&safety.wholeSuppliedGeometrySafe){target=candidate;admission={factor,native,safety};break;}
  }
  if(!target)fail('DIRECTOR_CAMERA_NO_SAFE_SOURCE_VIEW_'+row.chapterId+' '+JSON.stringify({
   desired,sourceGeometryRefs:row.geometryRefs,locationIds:row.locationIds,
   attempts:attempts.filter(item=>item.chapterId===row.chapterId)}));
  const start=previous??target,approachFrames=Math.min(row.approachFrames,row.endFrame-row.startFrame),
   segment=compileSegment({baseCameraPlan,currentNativeFrame,start,target,totalFrames:approachFrames,
    fps:plan.fps,holdFrames:settings.minimumEndpointHoldFrames??16});
  entries.push({...clone(row),startBounds:[...start],targetBounds:[...target],source,segment,admission,
   actualHoldFrames:row.endFrame-row.startFrame-approachFrames});
  previous=[...target];
 }
 const compiled={schema:'WORLD_ENGINE_COMPILED_STORY_DIRECTOR_CAMERA_V1',entries,attempts,
  totalFrames:plan.totalFrames,fps:plan.fps,output:[...output],safeArea:[...safeArea],minimumBounds:[...minimumBounds],
  originalV5SourceChanged:false,originalReferenceAdapterChanged:false,newCameraMath:false,
  productionEligible:false,nvidiaHardwareVerified:false,visualAdmission:'ACTUAL_SOFTWARE_FRAME_REVIEW_REQUIRED'};
 // Native layout checks cover every original frame, including transitions.
 // Source-front transitions stay their original owner. Source cropping is
 // recorded rather than a fake geometry claim or a disabled safety guard.
 const violations=[],sourceCropFrames=[];let previousSample=null,maximumCenterStepPixels=0,maximumZoomRatio=1;
 for(let frame=0;frame<compiled.totalFrames;frame++){
  const sample=evaluateStoryDirectorCamera(compiled,frame),layout=validateBounds(sample.flatBounds,frame);
  if(layout?.valid!==true)violations.push({frame,failures:clone(layout.failures??[])});
  if(sample.sourceSafety?.wholeSuppliedGeometrySafe===false)sourceCropFrames.push({frame,
   sourceGeometryRefs:sample.activeSourceGeometryRefs,projectedBounds:sample.sourceSafety.projectedBounds});
  if(previousSample){const s=span(previousSample.flatBounds),a=center(previousSample.flatBounds),b=center(sample.flatBounds);
   maximumCenterStepPixels=Math.max(maximumCenterStepPixels,Math.hypot((b[0]-a[0])/s[0]*output[0],(b[1]-a[1])/s[1]*output[1]));}
  maximumZoomRatio=Math.max(maximumZoomRatio,span(entries[0].startBounds)[1]/span(sample.flatBounds)[1]);
  previousSample=sample;
 }
 compiled.nativeLayoutPreflight={framesChecked:compiled.totalFrames,violations,maximumCenterStepPixels,maximumZoomRatio,
  sourceCropFrameCount:sourceCropFrames.length,sourceCropFrames,
  sourceCropInterpretation:'ACTUAL_DISPLAYED_SOURCE_SAFE_AREA; CAMERA_TRANSITION_MAY_NEED_REWORK; NEVER_A_VISUAL_PASS',
  hardwareVerified:false,visualQualityApproved:false};
 if(violations.length)fail('DIRECTOR_CAMERA_NATIVE_LAYOUT_UNSAFE_FRAME_'+violations[0].frame);
 return compiled;
}
export function evaluateStoryDirectorCamera(compiled,frame){
 if(compiled?.schema!=='WORLD_ENGINE_COMPILED_STORY_DIRECTOR_CAMERA_V1'||!Number.isSafeInteger(frame)
  ||frame<0||frame>=compiled.totalFrames)fail('DIRECTOR_CAMERA_GLOBAL_FRAME_REQUIRED');
 const row=compiled.entries.find(item=>frame>=item.startFrame&&frame<item.endFrame),
  local=frame-row.startFrame,inside=local<row.segment.totalFrames,
  sampleFrame=inside?(row.segment.reverse?row.segment.totalFrames-1-local:local)
   :(row.segment.reverse?0:row.segment.totalFrames-1),
  sample=evaluateReferenceCameraTrackFrame(row.segment.track,sampleFrame),
  locked=!inside||same(sample.flatBounds,row.targetBounds),s=span(sample.flatBounds),c=center(sample.flatBounds),
  sourceSegment=row.displayedSourceSegments?.find(item=>frame>=item.startFrame&&frame<item.endFrame),
  activeSourceGeometryRefs=sourceSegment?.geometryRefs??row.geometryRefs,
  actualSource=activeSourceGeometryRefs.map(id=>row.source.geometries[row.source.geometryRefs.indexOf(id)]),
  sourceSafety=actualSource.length?geometryScreenSafety({geometries:actualSource,bounds:sample.flatBounds,
   safeArea:compiled.safeArea,output:compiled.output}):{wholeSuppliedGeometrySafe:true,projectedBounds:null,noEventGeometry:true},
  velocity=Object.fromEntries(Object.entries(sample.velocity).map(([key,value])=>[key,
   !inside||locked?0:row.segment.reverse?-value:value]));
 return{...clone(sample),frame,globalFrame:frame,timeSeconds:frame/compiled.fps,chapterId:row.chapterId,eventId:row.eventId,
  camera:{...clone(sample.camera),flatBounds:[...sample.flatBounds]},flatBounds:[...sample.flatBounds],
  cameraLocked:locked,settle:{phase:locked?'DIRECTOR_SOURCE_CONTEXT_HOLD':'DIRECTOR_CAMERA_APPROACH',settled:locked,locked},
  velocity,
  cameraOnlySampleFrame:sampleFrame,cameraOnlyLocalClockReversed:row.segment.reverse,
  sceneClockReset:false,sourceGeometryRefs:[...row.geometryRefs],contextLocations:clone(row.source.locations),
  activeSourceGeometryRefs:[...activeSourceGeometryRefs],sourceSafety,
  center:c,pixelsPerDegree:[compiled.output[0]/s[0],compiled.output[1]/s[1]],
  geographicToPixelMatrix:[compiled.output[0]/s[0],0,-sample.flatBounds[0]*compiled.output[0]/s[0],
   0,-compiled.output[1]/s[1],sample.flatBounds[3]*compiled.output[1]/s[1],0,0,1],
  rotationDegrees:0,rotationStatus:'BLOCKED_CURRENT_HISTORICAL_COMPOSITOR_HAS_NO_ROLL_CONSUMER',
  preservedNativeMinimumBounds:[...compiled.minimumBounds],
  closerThanOriginalNativeFloor:s.some((value,index)=>value<span(compiled.minimumBounds)[index]-1e-9),
  closerZoomStatus:'BLOCKED_NATIVE_LOCAL_NOT_ADMITTED; PAN_AND_WIDER_TO_REGIONAL_ONLY',
  admission:{visual:'SOFTWARE_PREVIEW_USER_REVIEW_REQUIRED',local:'NOT_ADMITTED',nvidia:'NOT_RUN'},
  productionEligible:false,visualQualityApproved:false};
}
