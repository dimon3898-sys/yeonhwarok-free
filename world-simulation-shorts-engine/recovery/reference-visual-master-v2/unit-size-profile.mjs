/** Scene-owned unit readability only. Original artwork, geographic anchors,
 * rotations, role/profile selection and the original layout classifier remain
 * unchanged. One static scale is checked against every supplied frame. */
import {validateNationalUnitBadgeFixture,evaluateNationalUnitBadgeLayout,measureNationalUnitBadge}
 from '../../web/map_infographic_v1/national_unit_badge_v1.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,geoToPresentationScreen}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';

export const REFERENCE_UNIT_SIZE_VERSION='REFERENCE_UNIT_READABILITY_SCALE_V2';
export const DEFAULT_REFERENCE_UNIT_PROFILE=Object.freeze({enabled:false,markerScale:1.14});
const clone=value=>structuredClone(value),box=value=>Array.isArray(value)&&value.length===4
 &&value.every(Number.isFinite)&&value[0]<value[2]&&value[1]<value[3];
export function validateReferenceUnitProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_UNIT_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(DEFAULT_REFERENCE_UNIT_PROFILE,key))
  throw Error('REFERENCE_UNIT_UNKNOWN_PARAMETER_'+key);
 const profile={...DEFAULT_REFERENCE_UNIT_PROFILE,...clone(input)};
 if(typeof profile.enabled!=='boolean')throw Error('REFERENCE_UNIT_EXPLICIT_ENABLED_REQUIRED');
 if(!Number.isFinite(profile.markerScale)||profile.markerScale<1||profile.markerScale>1.25)
  throw Error('REFERENCE_UNIT_SCALE_RANGE');
 return Object.freeze(profile);
}

function frameProjects(scene,baseCameraPlan,currentNativeFrame){
 const totalFrames=scene.controlIntent?.total_frames,fps=scene.controlIntent?.fps;
 const track=compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes:scene.cameraKeyframes,totalFrames,fps}),
  presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(key=>({frame:key.frame,
   rollDegrees:key.rotationDegrees})),totalFrames,fps,overscan:scene.presentationProfile.overscan,width:1080,height:1920});
 return Array.from({length:totalFrames},(_,frame)=>{
  const camera=evaluateReferenceCameraTrackFrame(track,frame),state=evaluateReferencePresentationFrame(presentation,frame),
   bounds=expandNativeBounds({bounds:camera.flatBounds,referenceStartBounds:track.startBounds,
    rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true});
  return point=>geoToPresentationScreen(point,bounds,state);
 });
}
const unitsAtScale=(units,scale)=>units.map(unit=>({...clone(unit),
 size_frames:unit.size_frames.map(size=>Math.min(140,size*scale))}));

function inspectUnits(units,profiles,projects,safeArea){
 let safeAreaViolations=0,criticalCollisions=0,unitOverlapPairFrames=0,minimumSafeMarginPixels=Infinity,
  minimumSizePixels=Infinity,maximumSizePixels=0,minimumArtworkWidthPixels=Infinity,maximumArtworkWidthPixels=0,
  minimumArtworkHeightPixels=Infinity,maximumArtworkHeightPixels=0,minimumFlagWidthPixels=Infinity,maximumFlagWidthPixels=0;
 const firstFailures=[];
 for(let frame=0;frame<projects.length;frame++){
  const layout=evaluateNationalUnitBadgeLayout(units,frame,{project:projects[frame],safeArea,protectedGraphics:[]});
  safeAreaViolations+=layout.safeAreaViolations.length;criticalCollisions+=layout.criticalCollisions.length;
  unitOverlapPairFrames+=layout.unitOverlaps.length;
  if(firstFailures.length<5&&(layout.safeAreaViolations.length||layout.criticalCollisions.length||layout.unitOverlaps.length))
   firstFailures.push({frame,safeAreaViolations:clone(layout.safeAreaViolations),
    criticalCollisions:clone(layout.criticalCollisions),unitOverlaps:clone(layout.unitOverlaps)});
  for(const unit of layout.units){
   minimumSafeMarginPixels=Math.min(minimumSafeMarginPixels,unit.bounds[0]-safeArea[0],unit.bounds[1]-safeArea[1],
    safeArea[2]-unit.bounds[2],safeArea[3]-unit.bounds[3]);
   const measured=measureNationalUnitBadge({sizePx:unit.size_px,rotationDegrees:unit.rotation_degrees,
    aspectRatio:profiles[unit.profile_id].aspect_ratio});
   minimumSizePixels=Math.min(minimumSizePixels,unit.size_px);maximumSizePixels=Math.max(maximumSizePixels,unit.size_px);
   minimumArtworkWidthPixels=Math.min(minimumArtworkWidthPixels,measured.widthPx);
   maximumArtworkWidthPixels=Math.max(maximumArtworkWidthPixels,measured.widthPx);
   minimumArtworkHeightPixels=Math.min(minimumArtworkHeightPixels,measured.heightPx);
   maximumArtworkHeightPixels=Math.max(maximumArtworkHeightPixels,measured.heightPx);
   minimumFlagWidthPixels=Math.min(minimumFlagWidthPixels,measured.flagWidthPx);
   maximumFlagWidthPixels=Math.max(maximumFlagWidthPixels,measured.flagWidthPx);
  }
 }
 return {framesChecked:projects.length,unitCount:units.length,safeAreaViolations,criticalCollisions,unitOverlapPairFrames,
  minimumSafeMarginPixels,sizePixels:[minimumSizePixels,maximumSizePixels],
  artworkWidthPixels:[minimumArtworkWidthPixels,maximumArtworkWidthPixels],
  artworkHeightPixels:[minimumArtworkHeightPixels,maximumArtworkHeightPixels],
  flagWidthPixels:[minimumFlagWidthPixels,maximumFlagWidthPixels],firstFailures,
  safe:safeAreaViolations===0&&criticalCollisions===0&&unitOverlapPairFrames===0};
}

/** A caller supplies its actual current/candidate scene. No fixture, subject,
 * country, event, date, camera path or geographic coordinate is selected here.
 * Requested static scales are reduced in 1% steps only when the existing
 * national size limits or existing layout classifier require it. */
export function selectReferenceUnitScale({scenePlan,baseCameraPlan,currentNativeFrame,safeArea,profile={}}={}){
 const selected=validateReferenceUnitProfile(profile);
 if(!scenePlan||typeof scenePlan!=='object'||Array.isArray(scenePlan))throw Error('REFERENCE_UNIT_SCENE_REQUIRED');
 const originalBinding=JSON.stringify(scenePlan),result=clone(scenePlan);
 if(!selected.enabled)return {scenePlan:result,changed:false,audit:{version:REFERENCE_UNIT_SIZE_VERSION,
  enabled:false,profile:clone(selected),selectedScale:1,decision:'UNCHANGED_PROFILE_ABSENT_OR_DISABLED',
  artworkChanged:false,anchorsChanged:false,rotationChanged:false,unitCountChanged:false,sourceSceneMutated:false,
  gpuPixelsVerified:false}};
 if(!box(safeArea)||safeArea[0]<0||safeArea[1]<0||safeArea[2]>1080||safeArea[3]>1920)
  throw Error('REFERENCE_UNIT_SAFE_AREA_REQUIRED');
 const {units,profiles}=scenePlan.combatProfile??{},fixture=validateNationalUnitBadgeFixture(units,profiles),
  projects=frameProjects(scenePlan,baseCameraPlan,currentNativeFrame);
 if(projects.length!==fixture.frames)throw Error('REFERENCE_UNIT_TIMELINE_BINDING_REQUIRED');
 const baseline=inspectUnits(units,profiles,projects,safeArea);
 if(!baseline.safe)throw Error('REFERENCE_UNIT_BASELINE_LAYOUT_UNSAFE');
 const nationalScaleLimit=units.reduce((limit,unit)=>unit.size_frames.reduce((value,size)=>Math.min(value,140/size),limit),Infinity),
  attempts=[];let scale=Math.min(selected.markerScale,nationalScaleLimit),effective=baseline,effectiveUnits=clone(units);
 for(;;){
  const candidate=unitsAtScale(units,scale),audit=inspectUnits(candidate,profiles,projects,safeArea);
  attempts.push({scale,safe:audit.safe,safeAreaViolations:audit.safeAreaViolations,
   criticalCollisions:audit.criticalCollisions,unitOverlapPairFrames:audit.unitOverlapPairFrames});
  if(audit.safe){effective=audit;effectiveUnits=candidate;break;}
  if(scale===1)throw Error('REFERENCE_UNIT_BASELINE_LAYOUT_UNSAFE');
  scale=Math.max(1,Math.floor((scale-1e-9)*100)/100);
 }
 result.combatProfile.units=effectiveUnits;
 validateNationalUnitBadgeFixture(result.combatProfile.units,result.combatProfile.profiles);
 if(JSON.stringify(scenePlan)!==originalBinding)throw Error('REFERENCE_UNIT_SOURCE_SCENE_MUTATED');
 const changed=JSON.stringify(result.combatProfile.units)!==JSON.stringify(units);
 return {scenePlan:result,changed,audit:{version:REFERENCE_UNIT_SIZE_VERSION,enabled:true,profile:clone(selected),
  requestedScale:selected.markerScale,selectedScale:scale,nationalScaleLimit,
  decision:changed?(scale<selected.markerScale?'STATIC_SCALE_SAFETY_CLAMPED':'STATIC_SCALE_REQUESTED_SAFE'):'ORIGINAL_SIZE_REQUIRED',
  searchQuantum:.01,attempts,baseline,effective,sourceFrameSizesPreservedWhenDisabled:true,
  selectionOwner:'EXPLICIT_SCENE_PROFILE_AND_EXISTING_ALL_FRAME_LAYOUT',layoutEngine:'UNCHANGED_NATIONAL_UNIT_BADGE_V1',
  sourceArtwork:'UNCHANGED_ORIGINAL_ROUNDED_TABLET_FLAG_AND_ROLE',artworkChanged:false,anchorsChanged:false,
  rotationChanged:false,unitCountChanged:false,nationalProfilesChanged:false,visibilityTimingChanged:false,
  cameraChanged:false,eventTimingChanged:false,sourceSceneMutated:false,sizePumping:false,gpuPixelsVerified:false}};
}
