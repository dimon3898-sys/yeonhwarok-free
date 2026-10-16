/** NODE-ONLY profile normalization. Browser setters independently validate the
 * normalized material groups; they never import filesystem-relative planners.
 * Missing V2 settings select A, the exact inherited Quality F render path. */
import {validateReferenceTerritoryProfile} from './gain_style_core.mjs';
import {validateReferenceSourceProfile} from './source_grade_core.mjs';
import {validateReferenceFrontierProfile} from './frontier_profile_core.mjs';
import {validateReferenceUnitProfile} from './unit-size-profile.mjs';
import {validateReferenceCameraProfile} from './camera-profile.mjs';

export const REFERENCE_PROFILE_VERSION='REFERENCE_VISUAL_PROFILE_V2';
export const REFERENCE_PROFILE_FAMILY='REFERENCE_VISUAL_MASTER_V2';
const scalarRules={
 territoryColorStrength:[.84,.72,.90],gainBrightness:[1.12,1,1.25],
 frontierGlowIntensity:[1,0,1],frontierGlowWidth:[2.5,.5,2.5],frontierHaloSigma:[4,.5,4],
 outerGoldIntensity:[.75,0,1],outerGoldWidth:[1,.5,1.5],outerGoldSigma:[2.2,.5,3],outerGoldSupport:[6,4,6],
 terrainContrast:[1.2,1,1.4],landExposure:[1.04,1,1.2],oceanExposure:[1.2,1,1.5],oceanTealMix:[.12,0,.3],
 terrainLightingMinimum:[.76,.65,1],astraEdgeBlending:[48,8,96],unitMarkerScale:[1.14,1,1.25],
 cameraFocusPriority:[.65,0,1],cameraMotionSmoothing:[.8,0,1]
};
const deepFreeze=value=>{if(value&&typeof value==='object'){for(const part of Object.values(value))deepFreeze(part);Object.freeze(value);}return value;};
export const REFERENCE_PARAMETER_CONTRACT=deepFreeze({
 scalarRules:structuredClone(scalarRules),
 territoryTransitionTiming:{default:'SCENE_OWNED',allowed:['SCENE_OWNED'],supported:false,
  reason:'Original control intent and every event frame remain unchanged; no visual time warp.'},
 eventHoldDurationFrames:{default:0,allowed:[0],supported:false,
  reason:'This five-second excerpt keeps advancing; no new event or object hold is invented.'},
 cameraReadHoldFrames:{default:10,allowed:[0,9,10,11,12],supported:true,
  meaning:'Camera position, extent and roll only; event and object clocks continue.'},
 absentProfile:'EXACT_INHERITED_QUALITY_F',productionVariant:'F'
});

export function validateReferenceParameters(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_PARAMETERS_OBJECT_REQUIRED');
 const extra=['territoryTransitionTiming','eventHoldDurationFrames','cameraReadHoldFrames'];
 for(const name of Object.keys(input))if(!Object.hasOwn(scalarRules,name)&&!extra.includes(name))
  throw Error('REFERENCE_UNKNOWN_PARAMETER_'+name);
 const result={};
 for(const [name,[fallback,lo,hi]]of Object.entries(scalarRules)){
  const value=Object.hasOwn(input,name)?input[name]:fallback;
  if(typeof value!=='number'||!Number.isFinite(value)||value<lo||value>hi)throw Error('REFERENCE_PARAMETER_RANGE_'+name);
  result[name]=value;
 }
 result.territoryTransitionTiming=Object.hasOwn(input,'territoryTransitionTiming')?input.territoryTransitionTiming:'SCENE_OWNED';
 if(result.territoryTransitionTiming!=='SCENE_OWNED')throw Error('REFERENCE_TERRITORY_RETIMING_UNSUPPORTED');
 result.eventHoldDurationFrames=Object.hasOwn(input,'eventHoldDurationFrames')?input.eventHoldDurationFrames:0;
 if(result.eventHoldDurationFrames!==0)throw Error('REFERENCE_EVENT_HOLD_UNSUPPORTED');
 result.cameraReadHoldFrames=Object.hasOwn(input,'cameraReadHoldFrames')?input.cameraReadHoldFrames:10;
 if(!Number.isSafeInteger(result.cameraReadHoldFrames)||![0,9,10,11,12].includes(result.cameraReadHoldFrames))
  throw Error('REFERENCE_CAMERA_READ_HOLD_RANGE');
 return deepFreeze(result);
}

export function referenceV2Profile(variant='A',parameters={}){
 if(typeof variant!=='string'||!['A','B','C','D','E','F'].includes(variant))throw Error('REFERENCE_VARIANT_A_TO_F_REQUIRED');
 const p=validateReferenceParameters(parameters),gain=variant==='B'||variant==='F',source=variant==='C'||variant==='F',
  front=variant==='D'||variant==='F',units=front,camera=variant==='E'||variant==='F';
 const result={version:REFERENCE_PROFILE_VERSION,variant,profileId:REFERENCE_PROFILE_FAMILY+'_'+variant,parameters:p,
  territory:validateReferenceTerritoryProfile({enabled:gain,gainBrightness:p.gainBrightness,gainedAlpha:p.territoryColorStrength}),
  source:validateReferenceSourceProfile({enabled:source,registerDomainCoverage:front&&p.outerGoldIntensity>0,
   terrainLocalContrast:p.terrainContrast,landExposure:p.landExposure,oceanExposure:p.oceanExposure,
   oceanTealMix:p.oceanTealMix,screenFeatherPixels:p.astraEdgeBlending}),
  frontier:validateReferenceFrontierProfile({enabled:front,whiteFront:true,frontierIntensity:p.frontierGlowIntensity,
   frontierWidth:p.frontierGlowWidth,frontierHaloSigma:p.frontierHaloSigma,minimumLightingFactor:p.terrainLightingMinimum,
   outerGoldIntensity:p.outerGoldIntensity,outerGoldWidth:p.outerGoldWidth,outerGoldSigma:p.outerGoldSigma,
   outerGoldSupport:p.outerGoldSupport}),
  units:validateReferenceUnitProfile({enabled:units,markerScale:p.unitMarkerScale}),
  camera:validateReferenceCameraProfile({enabled:camera,focusPriority:p.cameraFocusPriority,
   cameraSmoothing:p.cameraMotionSmoothing,holdDurationFrames:p.cameraReadHoldFrames}),
  capabilities:{territoryColorStrength:true,territoryTransitionTiming:false,frontierGlowIntensity:true,
   frontierGlowWidth:true,terrainContrast:true,astraEdgeBlending:true,unitMarkerScale:true,
   cameraFocusPriority:true,cameraMotionSmoothing:true,eventHoldDuration:false,cameraReadHold:true,
   perPixelGainAge:false,newPhysics:false},
  comparison:{inheritedBase:'QUALITY_F',sameOldFCamera:['A','B','C','D'],matchedCandidateCamera:['E','F'],
   candidateCameraValidatedAgainstScaledUnits:true,scenarioTimeWarp:false},
  compositionOrder:['UNCHANGED_NATIVE_CAMERA_GIS_COVERAGE','UNCHANGED_BASE_MATERIAL','EXISTING_SUPPORTED_ASTRA',
   'OPTIONAL_SUPPORTED_SOURCE_GRADE','UNCHANGED_OWNERSHIP_MASK_OPTIONAL_GAIN_STYLE',
   'ORIGINAL_TERRAIN_LIGHTING_AND_MOVING_WHITE_FRONT','OPTIONAL_ACTUAL_DOMAIN_OUTER_GOLD',
   'UNCHANGED_PRESENTATION','ORIGINAL_NATIONAL_ARTWORK_OPTIONAL_SAFE_SIZE'],
  qualityApproved:false,hardwareVerified:false,finalPromotion:false};
 return deepFreeze(result);
}
