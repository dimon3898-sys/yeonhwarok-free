/** Explicit Regional source review over the unchanged reference-camera evaluator.
 * Requested Local design is a separate blocked input, never widened into this
 * profile. No projection, interpolation or V5 implementation is duplicated.
 */
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '/modules/reference_camera_adapter_v1.mjs';
import {geometryBounds,fitGeographicExtent} from '/modules/scale_contract.mjs';
import {geometryScreenSafety} from '/production-v3/production_camera.mjs';
const clone=x=>structuredClone(x),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),
 spans=b=>[b[2]-b[0],b[3]-b[1]],center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],
 valid=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]>=-180&&b[2]<=180
  &&b[1]>=-90&&b[3]<=90&&b[0]<b[2]&&b[1]<b[3];
const fail=(code,detail='')=>{throw Error(code+(detail?' '+detail:''));};
function fields(value,allowed,code){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))fail(code);
}
const union=values=>[Math.min(...values.map(b=>b[0])),Math.min(...values.map(b=>b[1])),
 Math.max(...values.map(b=>b[2])),Math.max(...values.map(b=>b[3]))];
function atCenter(c,s){const b=[c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2];
 if(!valid(b))fail('DIRECTOR_CAMERA_SOURCE_REVIEW_EXTENT_OUTSIDE_SUPPORTED_DOMAIN');return b;}
function padded(b,f){return atCenter(center(b),spans(b).map(v=>v*f));}
function regionalReviewExtent(b,minimum){
 const a=spans(b),m=spans(minimum),factor=Math.max(1,m[0]/a[0],m[1]/a[1]);
 // This is the explicitly requested Regional review, not admission of a Local
 // design. Both purposes and original requested extents remain in provenance.
 return factor===1?clone(b):padded(b,factor);
}
export function sourceReviewReveal(reveal,profile){
 if(!reveal||typeof reveal!=='object')fail('DIRECTOR_ORIGINAL_REVEAL_REQUIRED');
 const result=clone(reveal);if(profile.hideDuplicateNativeHeadline===true)result.title=0;return result;
}
export function validateCameraReviewProfile(profile,eventProfile,plan,admission){
 fields(profile,['schema','version','sourcePlanSHA256','eventProfileSHA256','purpose','cameraPurpose',
  'requestedLocalContractSatisfied','productionEligible','fps','totalFrames','requestedLocalDesign',
  'hideDuplicateNativeHeadline','hideDuplicateHeadlineReason','nativeMinimumPolicy','initialContextPadding',
  'phaseRule','minimumEndpointHoldFrames','sourceSafety','chapters'],'DIRECTOR_CAMERA_PROFILE_FIELD_UNSUPPORTED');
 if(profile.schema!=='WORLD_ENGINE_EVENT_DIRECTOR_CAMERA_REVIEW_V2'||profile.version!==2
  ||profile.purpose!=='QUALIFIED_SOURCE_REVIEW'||profile.cameraPurpose!=='REGIONAL_SOURCE_REVIEW'
  ||profile.requestedLocalContractSatisfied!==false||profile.productionEligible!==false
  ||profile.sourcePlanSHA256!==eventProfile?.sourcePlanSHA256
  ||profile.fps!==plan?.fps||profile.totalFrames!==plan?.totalFrames
  ||!Array.isArray(profile.chapters)||profile.chapters.length!==eventProfile?.chapters?.length
  ||profile.nativeMinimumPolicy!=='PRESERVE_ACTUAL_REGIONAL_FACTORY_MINIMUM')
  fail('DIRECTOR_CAMERA_EXPLICIT_SEPARATE_REGIONAL_REVIEW_REQUIRED');
 if(admission?.schema!=='WORLD_ENGINE_EVENT_DIRECTOR_CAMERA_ADMISSION_V2'||admission.version!==2
  ||admission.sourcePlanSHA256!==profile.sourcePlanSHA256
  ||admission.requestedCamera?.ready!==false||admission.requestedCamera?.automaticWideningAllowed!==false
  ||admission.regionalSourceReview?.purpose!=='REGIONAL_SOURCE_REVIEW'
  ||admission.regionalSourceReview?.requestedLocalContractSatisfied!==false
  ||admission.regionalSourceReview?.localCertificate!==false
  ||admission.regionalSourceReview?.originalRegionalFloorPreserved!==true)
  fail('DIRECTOR_CAMERA_REQUESTED_LOCAL_MUST_REMAIN_BLOCKED');
 if(typeof profile.hideDuplicateNativeHeadline!=='boolean'||!Number.isFinite(profile.initialContextPadding)
  ||profile.initialContextPadding<1||profile.initialContextPadding>2
  ||!Number.isSafeInteger(profile.minimumEndpointHoldFrames)||profile.minimumEndpointHoldFrames<1)
  fail('DIRECTOR_CAMERA_REVIEW_PARAMETERS_INVALID');
 fields(profile.phaseRule,['eventHoldEnd','panEnd','focusEnd','sourceHoldEnd','resultHoldEnd','endContextFrame'],
  'DIRECTOR_CAMERA_PHASE_FIELD_UNSUPPORTED');
 const phases=['eventHoldEnd','panEnd','focusEnd','sourceHoldEnd','resultHoldEnd','endContextFrame'].map(k=>profile.phaseRule[k]);
 if(phases.some((v,i)=>!Number.isSafeInteger(v)||v<1||(i&&v<=phases[i-1])))fail('DIRECTOR_CAMERA_PHASE_ORDER_REQUIRED');
 for(const[i,row]of profile.chapters.entries()){
  fields(row,['chapterId','eventId','startFrame','endFrame','locationRefs','padding','endContextPadding','sourceReviewOnly'],
   'DIRECTOR_CAMERA_CHAPTER_FIELD_UNSUPPORTED');
  const source=eventProfile.chapters[i],native=plan.productionV3.eventChapters[i];
  if(['chapterId','eventId','startFrame','endFrame'].some(k=>row[k]!==source[k]||row[k]!==native[k])
   ||!same(row.locationRefs,source.locationRefs)||!Array.isArray(row.locationRefs)||!row.locationRefs.length
   ||row.sourceReviewOnly!==true||!Number.isFinite(row.padding)||row.padding<1||row.padding>1.5
   ||!Number.isFinite(row.endContextPadding)||row.endContextPadding<1||row.endContextPadding>1.5
   ||row.endFrame-row.startFrame!==profile.phaseRule.endContextFrame+1)
   fail('DIRECTOR_CAMERA_CHAPTER_SOURCE_BINDING_REQUIRED',row.chapterId);
 }
 return clone(profile);
}

export function resolveReviewSources({eventProfile,plan,frontProfile,row}){
 const locations=new Map(eventProfile.locations.map(x=>[x.id,x])),legacy=plan.legacyScenePlan,
  geometries=new Map(legacy.geometries.map(x=>[x.id,x.geometry])),
  fronts=new Map([...frontProfile.fronts,...(plan.productionV3.directorAdditionalFronts??[])].map(x=>[x.frontId,x.geometry]));
 const resolvedLocations=row.locationRefs.map(id=>{
  const p=locations.get(id);
  if(!p||p.role!=='GEOGRAPHIC_CONTEXT_ONLY'||p.troopPosition!==false||!Array.isArray(p.anchor)
   ||p.anchor.length!==2||!p.anchor.every(Number.isFinite))fail('DIRECTOR_CAMERA_VERIFIED_CONTEXT_LOCATION_REQUIRED',id);
  return clone(p);
 });
 const segments=eventProfile.sourceSchedule.filter(x=>x.chapterId===row.chapterId).map(source=>{
  let records=[];
  if(source.kind==='SCHEMATIC_HELD_CORE'){
   const state=legacy.time_steps.find(x=>x.id===source.stateId);if(!state)fail('DIRECTOR_CAMERA_SOURCE_STATE_REQUIRED');
   const ids=[...state.area_ids.map(id=>legacy.areas.find(x=>x.id===id)?.geometry_ref),
    ...state.front_line_ids.map(id=>legacy.front_lines.find(x=>x.id===id)?.geometry_ref)];
   records=[...new Set(ids)].map(id=>{const geometry=geometries.get(id);if(!geometry)fail('DIRECTOR_CAMERA_SOURCE_GEOMETRY_REQUIRED',id);return{id,geometry:clone(geometry)};});
  }else if(source.kind==='OBSERVED_PARTIAL_FRONT'){
   const geometry=fronts.get(source.stateId);if(!geometry)fail('DIRECTOR_CAMERA_SOURCE_FRONT_REQUIRED',source.stateId);
   records=[{id:source.stateId,geometry:clone(geometry)}];
  }else if(source.kind!=='UNKNOWN'||source.stateId!==null||source.sourceIds?.length)
   fail('DIRECTOR_CAMERA_UNKNOWN_SOURCE_FALLBACK_FORBIDDEN');
  return{...clone(source),records};
 });
 if(!segments.length)fail('DIRECTOR_CAMERA_SOURCE_SCHEDULE_REQUIRED');
 return{locations:resolvedLocations,segments,
  geometries:[...new Map(segments.flatMap(x=>x.records).map(x=>[x.id,x])).values()]};
}

function segment({startFrame,endFrame,from,to,baseCameraPlan,currentNativeFrame,fps,hold}){
 if(endFrame<=startFrame)fail('DIRECTOR_CAMERA_SEGMENT_RANGE_REQUIRED');
 const start=spans(from),end=spans(to),larger=end.every((v,i)=>v>=start[i]-1e-9),
  smaller=end.every((v,i)=>v<=start[i]+1e-9);
 if(!larger&&!smaller)fail('DIRECTOR_CAMERA_MIXED_EXTENT_DIRECTION_UNSUPPORTED');
 const reverse=larger&&!smaller,first=reverse?to:from,last=reverse?from:to,
  duration=endFrame-startFrame+1,endpointHold=Math.min(hold,Math.floor((duration-2)/3));
 const keys=endpointHold>0?[{frame:0,bounds:first},{frame:endpointHold,bounds:first},
  {frame:duration-1-endpointHold,bounds:last},{frame:duration-1,bounds:last}]
  :[{frame:0,bounds:first},{frame:duration-1,bounds:last}];
 const track=compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes:keys,totalFrames:duration,fps});
 return{startFrame,endFrame,from:clone(from),to:clone(to),reverse,track};
}

export function compileSourceReviewCamera({profile,eventProfile,plan,frontProfile,admission,
 baseCameraPlan,currentNativeFrame,safeArea,minimumBounds,validateBounds=()=>({valid:true}),output=[1080,1920]}={}){
 const settings=validateCameraReviewProfile(profile,eventProfile,plan,admission);
 if(!valid(minimumBounds)||!same(minimumBounds,admission.regionalSourceReview.minimumBounds))
  fail('DIRECTOR_CAMERA_ACTUAL_NATIVE_MINIMUM_BINDING_REQUIRED');
 const saved=JSON.stringify({profile,eventProfile,plan,frontProfile}),entries=[],phase=settings.phaseRule,
  safePadding=Math.max(output[0]/(safeArea[2]-safeArea[0]-48),output[1]/(safeArea[3]-safeArea[1]-48));
 let previous=padded(minimumBounds,settings.initialContextPadding);
 const initialContextBounds=clone(previous);
 for(const[i,row]of settings.chapters.entries()){
  const sources=resolveReviewSources({eventProfile,plan,frontProfile,row}),
   boxes=[...sources.geometries.map(x=>geometryBounds(x.geometry)),...sources.locations.map(x=>[...x.anchor,...x.anchor])],
   required=union(boxes);
  if(required[2]-required[0]>180)fail('DIRECTOR_CAMERA_DATELINE_REQUIRES_SPLIT_ROI');
  // fitGeographicExtent owns aspect/projection fitting; minimum is unchanged.
  const contextOnlyDegenerate=required[0]===required[2]||required[1]===required[3],
   focus=contextOnlyDegenerate?atCenter(center(required),spans(minimumBounds).map(v=>v*row.padding)):
    regionalReviewExtent(fitGeographicExtent(required,{output,padding:safePadding*row.padding}),minimumBounds),
   pan=atCenter(center(focus),spans(previous).map((v,a)=>Math.max(v,spans(focus)[a]))),
   end=i===settings.chapters.length-1?initialContextBounds:padded(focus,row.endContextPadding),
   args={baseCameraPlan,currentNativeFrame,fps:plan.fps,hold:settings.minimumEndpointHoldFrames},
   segments=[segment({...args,startFrame:row.startFrame+phase.eventHoldEnd,endFrame:row.startFrame+phase.panEnd,from:previous,to:pan}),
    segment({...args,startFrame:row.startFrame+phase.panEnd,endFrame:row.startFrame+phase.focusEnd,from:pan,to:focus}),
    segment({...args,startFrame:row.startFrame+phase.resultHoldEnd,endFrame:row.endFrame-1,from:focus,to:end})];
  entries.push({...clone(row),source:sources,contextOnlyDegenerate,
   contextOnlyFramingMeaning:contextOnlyDegenerate?'EXPLICIT_REGIONAL_CITY_CONTEXT; NOT_AN_INFERRED_EVENT_FOOTPRINT':null,
   startBounds:clone(previous),panBounds:pan,focusBounds:focus,endBounds:clone(end),segments});
  previous=clone(end);
 }
 const compiled={schema:'WORLD_ENGINE_COMPILED_SOURCE_REVIEW_CAMERA_V2',profile:settings,entries,
  totalFrames:plan.totalFrames,fps:plan.fps,minimumBounds:clone(minimumBounds),safeArea:clone(safeArea),output:clone(output),
  requestedCameraStatus:'BLOCKED_REQUESTED_LOCAL',cameraPurpose:'REGIONAL_SOURCE_REVIEW',
  requestedLocalContractSatisfied:false,originalReferenceAdapterReused:true,originalV5BaseReused:true,
  nativeProjectionAndFactoryUnchanged:true,productionEligible:false,visualQualityApproved:false};
 let prior=null,maxCenterStep=0,maxZoom=1;const violations=[],sourceClips=[];
 for(let frame=0;frame<compiled.totalFrames;frame++){
  const actual=evaluateSourceReviewCamera(compiled,frame),check=validateBounds(actual.flatBounds,frame),s=spans(actual.flatBounds);
  if(s.some((v,a)=>v<spans(minimumBounds)[a]-1e-9))fail('DIRECTOR_CAMERA_NATIVE_FLOOR_VIOLATION');
  if(check.valid!==true)violations.push({frame,failures:clone(check.failures??[])});
  if(!actual.sourceSafety.wholeSuppliedGeometrySafe)sourceClips.push({frame,sourceRefs:actual.activeSourceGeometryRefs});
  maxZoom=Math.max(maxZoom,spans(initialContextBounds)[1]/s[1]);
  if(prior){const a=center(prior),b=center(actual.flatBounds),p=spans(prior);
   maxCenterStep=Math.max(maxCenterStep,Math.hypot((b[0]-a[0])/p[0]*output[0],(b[1]-a[1])/p[1]*output[1]));}
  prior=actual.flatBounds;
 }
 compiled.preflight={framesChecked:compiled.totalFrames,nativeLayoutViolations:violations,
  sourceClipFrames:sourceClips,maximumCenterStepPixels:maxCenterStep,maximumZoomRatio:maxZoom,
  actual2400FramesRendered:false,visualQualityApproved:false};
 if(violations.length)fail('DIRECTOR_CAMERA_NATIVE_LAYOUT_UNSAFE_FRAME_'+violations[0].frame,JSON.stringify(violations[0]));
 if(sourceClips.length)fail('DIRECTOR_CAMERA_ACTIVE_SOURCE_OUTSIDE_SAFE_AREA_FRAME_'+sourceClips[0].frame);
 if(JSON.stringify({profile,eventProfile,plan,frontProfile})!==saved)fail('DIRECTOR_CAMERA_ORIGINAL_INPUT_MUTATED');
 return compiled;
}

export function evaluateSourceReviewCamera(compiled,frame){
 if(compiled?.schema!=='WORLD_ENGINE_COMPILED_SOURCE_REVIEW_CAMERA_V2'||!Number.isSafeInteger(frame)
  ||frame<0||frame>=compiled.totalFrames)fail('DIRECTOR_CAMERA_GLOBAL_FRAME_REQUIRED');
 const row=compiled.entries.find(x=>frame>=x.startFrame&&frame<x.endFrame),phase=compiled.profile.phaseRule,
  local=frame-row.startFrame,segment=row.segments.find(x=>frame>=x.startFrame&&frame<=x.endFrame);
 let sample,bounds,phaseName,hold;
 if(segment){
  const cameraFrame=segment.reverse?segment.track.totalFrames-1-(frame-segment.startFrame):frame-segment.startFrame;
  sample=evaluateReferenceCameraTrackFrame(segment.track,cameraFrame);bounds=sample.flatBounds;
  phaseName=frame<=row.startFrame+phase.panEnd?'SOURCE_CONTEXT_PAN':frame<=row.startFrame+phase.focusEnd?'REGIONAL_SOURCE_FOCUS':'SOURCE_CONTEXT_WIDEN';
  hold=same(bounds,segment.from)||same(bounds,segment.to);
 }else{bounds=local<phase.eventHoldEnd?row.startBounds:row.focusBounds;hold=true;
  phaseName=local<phase.eventHoldEnd?'EVENT_CONTEXT_HOLD':local<phase.sourceHoldEnd?'QUALIFIED_SOURCE_HOLD':'SOURCE_RESULT_HOLD';}
 const s=spans(bounds),actualSource=row.source.segments.find(x=>frame>=x.startFrame&&frame<x.endFrame),
  safety=actualSource.records.length?geometryScreenSafety({geometries:actualSource.records.map(x=>x.geometry),
   bounds,safeArea:compiled.safeArea,output:compiled.output}):{wholeSuppliedGeometrySafe:true,noEventGeometry:true,projectedBounds:null},
  velocity=sample?Object.fromEntries(Object.entries(sample.velocity).map(([k,v])=>[k,hold?0:segment.reverse?-v:v])):
   {longitudeDegreesPerSecond:0,latitudeDegreesPerSecond:0,logWidthPerSecond:0,logHeightPerSecond:0};
 return{...(sample?clone(sample):{}),frame,globalFrame:frame,timeSeconds:frame/compiled.fps,
  chapterId:row.chapterId,eventId:row.eventId,phase:phaseName,flatBounds:clone(bounds),center:center(bounds),
  camera:{...(sample?clone(sample.camera):{}),flatBounds:clone(bounds)},
  cameraLocked:hold,settle:{phase:phaseName,settled:hold,locked:hold},velocity,
  contextLocations:clone(row.source.locations),activeSourceGeometryRefs:actualSource.records.map(x=>x.id),
  sourceTruthKind:actualSource.truthKind,sourceDate:actualSource.sourceDate,sourceSafety:safety,
  cameraPurpose:'REGIONAL_SOURCE_REVIEW',requestedCameraStatus:'BLOCKED_REQUESTED_LOCAL',
  requestedLocalContractSatisfied:false,preservedNativeMinimumBounds:clone(compiled.minimumBounds),
  closerThanOriginalNativeFloor:s.some((v,a)=>v<spans(compiled.minimumBounds)[a]-1e-9),
  pixelsPerDegree:[compiled.output[0]/s[0],compiled.output[1]/s[1]],
  rotationDegrees:0,rollSupported:false,sceneClockReset:false,
  noUnknownSourceFallback:true,productionEligible:false,visualQualityApproved:false};
}
