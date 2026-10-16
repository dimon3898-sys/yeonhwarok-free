/** Scene-owned camera readability cadence. V5, event and object clocks stay unchanged. */
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame,assessReferenceCameraMotion}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,geoToPresentationScreen}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {areaGeometryCoordinates} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {evaluateNationalUnitBadgeLayout} from '../../web/map_infographic_v1/national_unit_badge_v1.mjs';

export const REFERENCE_CAMERA_PROFILE_VERSION='REFERENCE_CAMERA_READABILITY_PROFILE_V2';
export const DEFAULT_REFERENCE_CAMERA_PROFILE=Object.freeze({enabled:false,focusPriority:.65,cameraSmoothing:.8,holdDurationFrames:10});
const clone=value=>structuredClone(value),span=b=>[b[2]-b[0],b[3]-b[1]],center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],
 smooth=t=>t*t*(3-2*t),inBox=(p,b)=>p[0]>=b[0]-1e-7&&p[0]<=b[2]+1e-7&&p[1]>=b[1]-1e-7&&p[1]<=b[3]+1e-7,
 contains=(a,b)=>a[0]<=b[0]+1e-8&&a[1]<=b[1]+1e-8&&a[2]>=b[2]-1e-8&&a[3]>=b[3]-1e-8,
 box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3],
 average=points=>points.reduce((a,p)=>[a[0]+p[0]/points.length,a[1]+p[1]/points.length],[0,0]),
 union=boxes=>[Math.min(...boxes.map(b=>b[0])),Math.min(...boxes.map(b=>b[1])),Math.max(...boxes.map(b=>b[2])),Math.max(...boxes.map(b=>b[3]))];

export function validateReferenceCameraProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_CAMERA_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(DEFAULT_REFERENCE_CAMERA_PROFILE,key))
  throw Error('REFERENCE_CAMERA_UNKNOWN_PARAMETER_'+key);
 const p={...DEFAULT_REFERENCE_CAMERA_PROFILE,...clone(input)};
 if(typeof p.enabled!=='boolean')throw Error('REFERENCE_CAMERA_EXPLICIT_ENABLED_REQUIRED');
 for(const key of ['focusPriority','cameraSmoothing'])if(typeof p[key]!=='number'||!Number.isFinite(p[key])||p[key]<0||p[key]>1)
  throw Error('REFERENCE_CAMERA_PROFILE_RANGE_'+key);
 if(!Number.isSafeInteger(p.holdDurationFrames)||![0,9,10,11,12].includes(p.holdDurationFrames))
  throw Error('REFERENCE_CAMERA_READ_HOLD_RANGE');
 return Object.freeze(p);
}

function sampleCamera(scene,baseCameraPlan,currentNativeFrame){
 const totalFrames=scene.controlIntent.total_frames,fps=scene.controlIntent.fps,
  track=compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes:scene.cameraKeyframes,totalFrames,fps}),
  presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
   totalFrames,fps,overscan:scene.presentationProfile.overscan,width:1080,height:1920}),
  samples=Array.from({length:totalFrames},(_,frame)=>{
   const camera=evaluateReferenceCameraTrackFrame(track,frame),state=evaluateReferencePresentationFrame(presentation,frame),
    nativeBounds=expandNativeBounds({bounds:camera.flatBounds,referenceStartBounds:track.startBounds,
     rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true});
   return {frame,camera,state,nativeBounds,pose:[...camera.center,...camera.extent.map(Math.log),state.rollDegrees],
    project:point=>geoToPresentationScreen(point,nativeBounds,state)};
  });
 let maximumCenterAccelerationPixelsPerFrameSquared=0,maximumRollStepDegrees=0,
  maximumRollAccelerationDegreesPerFrameSquared=0,maximumAnalyticalCenterAccelerationDegreesPerSecondSquared=0;
 for(let f=0;f<samples.length;f++){
  const s=samples[f],a=s.camera.acceleration;
  maximumAnalyticalCenterAccelerationDegreesPerSecondSquared=Math.max(maximumAnalyticalCenterAccelerationDegreesPerSecondSquared,
   Math.hypot(a.longitudeDegreesPerSecondSquared,a.latitudeDegreesPerSecondSquared));
  if(f>0)maximumRollStepDegrees=Math.max(maximumRollStepDegrees,Math.abs(s.pose[4]-samples[f-1].pose[4]));
  if(f>1){const old=samples[f-1],older=samples[f-2],size=old.camera.extent;
   maximumCenterAccelerationPixelsPerFrameSquared=Math.max(maximumCenterAccelerationPixelsPerFrameSquared,
    Math.hypot((s.pose[0]-2*old.pose[0]+older.pose[0])/size[0]*1080,
     (s.pose[1]-2*old.pose[1]+older.pose[1])/size[1]*1920));
   maximumRollAccelerationDegreesPerFrameSquared=Math.max(maximumRollAccelerationDegreesPerFrameSquared,
    Math.abs(s.pose[4]-2*old.pose[4]+older.pose[4]));}
 }
 const readHoldRuns=[];let runStart=0;
 const samePose=(a,b)=>a.every((value,i)=>Math.abs(value-b[i])<=1e-10);
 for(let f=1;f<=samples.length;f++)if(f===samples.length||!samePose(samples[f].pose,samples[f-1].pose)){
  if(f-runStart>=2)readHoldRuns.push({startFrame:runStart,endFrame:f-1,displayedFrames:f-runStart,
   durationSeconds:(f-runStart)/fps,includesRoll:true,role:'CAMERA_READ_HOLD_ONLY',eventClockPaused:false});
  runStart=f;
 }
 const velocityContinuous=track.segments.every((segment,i)=>i===0||segment.startVelocity.every((v,axis)=>
  Math.abs(v-track.segments[i-1].endVelocity[axis])<1e-9));
 const rollVelocityContinuous=presentation.segments.every((segment,i)=>{
  if(i===0)return true;const prior=presentation.segments[i-1],a=prior.coefficients,b=segment.coefficients;
  return Math.abs((a[1]+2*a[2]+3*a[3])/(prior.endFrame-prior.startFrame)
   -b[1]/(segment.endFrame-segment.startFrame))<1e-9;
 });
 return {track,presentation,samples,audit:{...assessReferenceCameraMotion(track),readHoldRuns,
  actualPoseHoldMeasured:true,analyticalCameraVelocityContinuous:velocityContinuous,analyticalRollVelocityContinuous:rollVelocityContinuous,
  maximumCenterAccelerationPixelsPerFrameSquared,maximumRollStepDegrees,
  maximumRollAccelerationDegreesPerFrameSquared,maximumAnalyticalCenterAccelerationDegreesPerSecondSquared,
  accelerationContinuous:false,accelerationContinuityClaim:'NOT_CLAIMED_EXISTING_C1_INTERPOLATION',
  fakeLockCountInterpretation:'PROTECTED_METADATA_UNCHANGED; READ_HOLDS_MEASURED_SEPARATELY'}};
}

function contextFor(scene){
 const plan=compileTerritoryControlPlan(scene.controlIntent),frames=Array.from({length:plan.totalFrames},(_,f)=>
  evaluateTerritoryControlFrame(plan,plan.startFrame+f)),
  front=frames.map(c=>c.longitudinalKnots.map((x,i)=>[x,c.boundaryLatitudes[i]])
   .filter(point=>classifyControlPoint(c,point).inDomain)),
  vertices=scene.controlIntent.domain.flatMap(d=>areaGeometryCoordinates(d.geometry));
 return {frames,front,vertices};
}

function inspectLayout(scene,sampling,context,safeArea,baseline=null){
 let unitSafeAreaViolations=0,criticalCollisions=0,unitOverlapPairFrames=0,
  frontSafeAreaViolations=0,newDomainCropVertexFrames=0,fullDomainVisibleFrames=0,
  minimumVisibleDomainVertices=Infinity,minimumFrontMarginPixels=Infinity,minimumUnitMarginPixels=Infinity,
  focusSquared=0,focusFrames=0;
 const domainVisibility=[],firstFailures=[];
 for(const sample of sampling.samples){
  const f=sample.frame,project=sample.project,front=context.front[f].map(project),
   visibility=context.vertices.map(point=>inBox(project(point),[0,0,1080,1920]));
  domainVisibility.push(visibility);const visibleCount=visibility.filter(Boolean).length;
  minimumVisibleDomainVertices=Math.min(minimumVisibleDomainVertices,visibleCount);
  if(visibleCount===visibility.length)fullDomainVisibleFrames++;
  const newCrop=baseline?visibility.reduce((n,visible,i)=>n+Number(baseline.domainVisibility[f][i]&&!visible),0):0;
  newDomainCropVertexFrames+=newCrop;
  for(const p of front){if(!inBox(p,safeArea))frontSafeAreaViolations++;
   minimumFrontMarginPixels=Math.min(minimumFrontMarginPixels,p[0]-safeArea[0],p[1]-safeArea[1],safeArea[2]-p[0],safeArea[3]-p[1]);}
  if(front.length){const focal=average(front),target=center(safeArea);focusSquared+=Math.hypot(focal[0]-target[0],focal[1]-target[1])**2;focusFrames++;}
  const units=evaluateNationalUnitBadgeLayout(scene.combatProfile.units,f,{project,safeArea,protectedGraphics:[]});
  unitSafeAreaViolations+=units.safeAreaViolations.length;criticalCollisions+=units.criticalCollisions.length;unitOverlapPairFrames+=units.unitOverlaps.length;
  for(const unit of units.units)minimumUnitMarginPixels=Math.min(minimumUnitMarginPixels,
   unit.bounds[0]-safeArea[0],unit.bounds[1]-safeArea[1],safeArea[2]-unit.bounds[2],safeArea[3]-unit.bounds[3]);
  if(firstFailures.length<5&&(newCrop||units.safeAreaViolations.length||units.criticalCollisions.length||units.unitOverlaps.length
   ||front.some(p=>!inBox(p,safeArea))))firstFailures.push({frame:f,newDomainCropVertices:newCrop,
    unitSafeAreaViolations:units.safeAreaViolations.length,criticalCollisions:units.criticalCollisions.length,
    unitOverlaps:units.unitOverlaps.length,frontOutsideSafeArea:front.filter(p=>!inBox(p,safeArea)).length});
 }
 return {domainVisibility,audit:{framesChecked:sampling.samples.length,unitSafeAreaViolations,criticalCollisions,unitOverlapPairFrames,
  frontSafeAreaViolations,newDomainCropVertexFrames,totalDomainSourceVertices:context.vertices.length,
  minimumVisibleDomainVertices,fullDomainVisibleFrames,wholeControlDomainVisibleAllFrames:fullDomainVisibleFrames===sampling.samples.length,
  activeFrontSampleFrames:focusFrames,
  minimumFrontMarginPixels,minimumUnitMarginPixels,frontFocusRmsPixels:Math.sqrt(focusSquared/Math.max(1,focusFrames)),firstFailures,
  domainVisibilityScope:'ALL_SUPPLIED_CONTROL_POLYGON_VERTICES; NO_WORLD_VISIBILITY_CLAIM',
  safe:focusFrames===sampling.samples.length&&unitSafeAreaViolations===0&&criticalCollisions===0&&unitOverlapPairFrames===0&&frontSafeAreaViolations===0&&newDomainCropVertexFrames===0}};
}

function opportunities(baseline,context,profile){
 const total=baseline.samples.length,ramp=Math.round(8+profile.cameraSmoothing*12),count=profile.holdDurationFrames,
  begin=Math.max(ramp+2,Math.ceil(total*.2)),end=Math.min(total-ramp-count-2,Math.floor(total*.74)),rows=[];
 for(let frame=begin;frame<=end;frame++){
  const left=Math.max(0,frame-ramp),a=context.frames[left],b=context.frames[frame],
   recentGain=b.boundaryLatitudes.reduce((sum,v,i)=>sum+Math.abs(v-a.boundaryLatitudes[i]),0)/b.boundaryLatitudes.length,
   points=context.front[frame].map(baseline.samples[frame].project),
   focusDistance=points.length?Math.hypot(...average(points).map((v,i)=>v-[540,960][i])):Infinity;
  rows.push({frame,recentGain,focusDistance});
 }
 const maxGain=Math.max(1e-12,...rows.map(r=>r.recentGain)),maxFocus=Math.max(1,...rows.filter(r=>Number.isFinite(r.focusDistance)).map(r=>r.focusDistance));
 for(const row of rows)row.score=profile.focusPriority*row.recentGain/maxGain+(1-profile.focusPriority)*(1-Math.min(1,row.focusDistance/maxFocus));
 const retained=[];
 for(const row of rows.sort((a,b)=>b.score-a.score||a.frame-b.frame)){
  if(retained.every(other=>Math.abs(row.frame-other.frame)>=3))retained.push(row);
  // Keep later safe phases reachable when a broad high-scoring peak fails
  // framing guards. At150 frames the eligible spaced window has at most27.
  if(retained.length===32)break;
 }
 return retained;
}

function makeCandidate(scene,baseline,profile,start,padding){
 const result=clone(scene),count=profile.holdDurationFrames,end=start+count-1,
  ramp=Math.round(8+profile.cameraSmoothing*12),left=start-ramp,right=end+ramp,
  region=baseline.samples.slice(left,right+1),holdBounds=union(region.map(s=>s.camera.flatBounds)),
  c=center(holdBounds),size=span(holdBounds).map(v=>v*(1+padding)),
  holdPose=[...c,...size.map(Math.log),baseline.samples[Math.round((start+end)/2)].state.rollDegrees];
 result.cameraKeyframes=baseline.samples.map(sample=>{
  const f=sample.frame;let weight=0;
  if(f>=start&&f<=end)weight=1;
  else if(f>left&&f<start)weight=smooth((f-left)/ramp);
  else if(f>end&&f<right)weight=1-smooth((f-end)/ramp);
  const pose=sample.pose.map((v,i)=>v+(holdPose[i]-v)*weight),extents=pose.slice(2,4).map(Math.exp);
  return {frame:f,bounds:[pose[0]-extents[0]/2,pose[1]-extents[1]/2,pose[0]+extents[0]/2,pose[1]+extents[1]/2],rotationDegrees:pose[4]};
 });
 // Preserve exact canonical endpoints, rather than a log/exp roundtrip.
 result.cameraKeyframes[0]=clone(scene.cameraKeyframes[0]);result.cameraKeyframes.at(-1).bounds=clone(scene.cameraKeyframes.at(-1).bounds);
 result.cameraKeyframes.at(-1).rotationDegrees=scene.cameraKeyframes.at(-1).rotationDegrees;
 return result;
}

/** New profile absent/disabled is exact old F. The caller must provide the
 * actual current F Scene (optionally after the separately verified unit scale).
 * This function never invokes the previous quality-camera selector again. */
export function selectReferenceCamera({scenePlan,baseCameraPlan,currentNativeFrame,safeArea,inheritedNativeBounds,profile={}}={}){
 const selected=validateReferenceCameraProfile(profile);
 if(!scenePlan||typeof scenePlan!=='object'||Array.isArray(scenePlan))throw Error('REFERENCE_CAMERA_SCENE_REQUIRED');
 const binding=JSON.stringify(scenePlan),unchanged=()=>({scenePlan:clone(scenePlan),changed:false,audit:{version:REFERENCE_CAMERA_PROFILE_VERSION,
  enabled:selected.enabled,profile:clone(selected),decision:'UNCHANGED_PROFILE_ABSENT_OR_DISABLED',eventTimingChanged:false,
  objectTimingChanged:false,eventHoldSupported:false,sourceSceneMutated:false,cameraV5SourceChanged:false,gpuVideoVerified:false}});
 if(!selected.enabled)return unchanged();
 if(!box(safeArea)||safeArea[0]<0||safeArea[1]<0||safeArea[2]>1080||safeArea[3]>1920||!box(inheritedNativeBounds))
  throw Error('REFERENCE_CAMERA_SAFE_CONTEXT_REQUIRED');
 const baseline=sampleCamera(scenePlan,baseCameraPlan,currentNativeFrame),context=contextFor(scenePlan),
  baseLayout=inspectLayout(scenePlan,baseline,context,safeArea),envelope=union(baseline.samples.map(s=>s.nativeBounds)),
  floor=span(inheritedNativeBounds),attempts=[];
 if(!baseLayout.audit.safe)throw Error('REFERENCE_CAMERA_BASELINE_LAYOUT_UNSAFE');
 if(selected.holdDurationFrames===0){const result=unchanged();result.audit={...result.audit,decision:'CAMERA_READ_HOLD_DISABLED',
  baseline:{motion:baseline.audit,layout:baseLayout.audit},effective:{motion:baseline.audit,layout:baseLayout.audit}};return result;}
 let resultScene=null,effective=null,picked=null;
 for(const opportunity of opportunities(baseline,context,selected)){
  for(const padding of [0,.004,.008]){
   let motion,layout,error=null;
   const candidate=makeCandidate(scenePlan,baseline,selected,opportunity.frame,padding);
   try{motion=sampleCamera(candidate,baseCameraPlan,currentNativeFrame);layout=inspectLayout(candidate,motion,context,safeArea,baseLayout);}
   catch(e){error=e.message;}
   const floorRespected=Boolean(motion)&&motion.samples.every(s=>span(s.nativeBounds).every((v,i)=>v>=floor[i]-1e-9)),
    sourceEnvelopeRespected=Boolean(motion)&&motion.samples.every(s=>contains(envelope,s.nativeBounds)),
    hold=motion?.audit.readHoldRuns.find(run=>run.startFrame===opportunity.frame&&run.displayedFrames===selected.holdDurationFrames),
    continuity=Boolean(motion)&&motion.audit.maximumCenterStepPixels<=Math.max(1080*.008,baseline.audit.maximumCenterStepPixels*1.6)
     &&motion.audit.maximumCenterAccelerationPixelsPerFrameSquared<=Math.max(1,baseline.audit.maximumCenterAccelerationPixelsPerFrameSquared*5)
     &&motion.audit.maximumRollStepDegrees<=Math.max(.5,baseline.audit.maximumRollStepDegrees*2),
    focusRespected=Boolean(layout)&&layout.audit.frontFocusRmsPixels<=baseLayout.audit.frontFocusRmsPixels*1.15,
    admitted=!error&&floorRespected&&sourceEnvelopeRespected&&Boolean(hold)&&continuity&&focusRespected&&layout.audit.safe;
   attempts.push({startFrame:opportunity.frame,score:opportunity.score,padding,admitted,error,floorRespected,sourceEnvelopeRespected,
    exactRequestedPoseHold:Boolean(hold),continuity,focusRespected,layout:layout?.audit??null,motion:motion?.audit??null});
   if(admitted){resultScene=candidate;effective={motion:motion.audit,layout:layout.audit};picked={startFrame:hold.startFrame,
    endFrame:hold.endFrame,displayedFrames:hold.displayedFrames,rampFrames:Math.round(8+selected.cameraSmoothing*12),padding,
    opportunityScore:opportunity.score};break;}
  }
  if(resultScene)break;
 }
 if(JSON.stringify(scenePlan)!==binding)throw Error('REFERENCE_CAMERA_SOURCE_SCENE_MUTATED');
 return {scenePlan:resultScene??clone(scenePlan),changed:Boolean(resultScene),audit:{version:REFERENCE_CAMERA_PROFILE_VERSION,
  enabled:true,profile:clone(selected),decision:resultScene?'SAFE_CAMERA_READ_HOLD_SELECTED':'USE_OLD_F_NO_SAFE_CAMERA_CANDIDATE',
  selected:picked,attempts,baseline:{motion:baseline.audit,layout:baseLayout.audit},effective:effective??{motion:baseline.audit,layout:baseLayout.audit},
  originalNativeEnvelope:envelope,inheritedNativeFloor:clone(inheritedNativeBounds),
  eventFrameIndicesUnchanged:true,objectFrameIndicesUnchanged:true,eventTimingChanged:false,objectTimingChanged:false,
  eventHoldSupported:false,cameraReadHoldOnly:true,sourceSceneMutated:false,cameraV5SourceChanged:false,
  actualGpuVideoSmoothnessVerified:false,gpuVideoVerified:false}};
}

/** Independent CPU audit for profile consumers and disabled A-regression tests. */
export function auditReferenceCamera({scenePlan,baseCameraPlan,currentNativeFrame,safeArea}={}){
 const sampled=sampleCamera(scenePlan,baseCameraPlan,currentNativeFrame),context=contextFor(scenePlan),
  layout=inspectLayout(scenePlan,sampled,context,safeArea);
 return {motion:sampled.audit,layout:layout.audit,
  poses:sampled.samples.map(sample=>({frame:sample.frame,pose:clone(sample.pose),bounds:clone(sample.camera.flatBounds),
   nativeBounds:clone(sample.nativeBounds),velocity:clone(sample.camera.velocity),acceleration:clone(sample.camera.acceleration),
   rollVelocityDegreesPerSecond:sample.state.rollVelocityDegreesPerSecond})),gpuVideoVerified:false};
}
