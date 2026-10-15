/** A bounded visual material for the ORIGINAL cumulative newly-gained mask.
 * No age field, geometry, classifier, event, timeline or faction is invented.
 */
export const REFERENCE_GAIN_STYLE_VERSION='REFERENCE_CUMULATIVE_GAIN_STYLE_V2';
export const DEFAULT_REFERENCE_TERRITORY_PROFILE=Object.freeze({enabled:false,gainBrightness:1.12,gainedAlpha:.84});
const clone=value=>structuredClone(value),rgba=value=>Array.isArray(value)&&value.length===4
 &&value.every(channel=>Number.isFinite(channel)&&channel>=0&&channel<=1);

export function validateReferenceTerritoryProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_GAIN_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(DEFAULT_REFERENCE_TERRITORY_PROFILE,key))
  throw Error('REFERENCE_GAIN_UNKNOWN_PARAMETER_'+key);
 const value={...DEFAULT_REFERENCE_TERRITORY_PROFILE,...clone(input)};
 if(typeof value.enabled!=='boolean')throw Error('REFERENCE_GAIN_EXPLICIT_ENABLED_REQUIRED');
 if(!Number.isFinite(value.gainBrightness)||value.gainBrightness<1||value.gainBrightness>1.25)
  throw Error('REFERENCE_GAIN_BRIGHTNESS_RANGE');
 if(!Number.isFinite(value.gainedAlpha)||value.gainedAlpha<0||value.gainedAlpha>.90)
  throw Error('REFERENCE_GAIN_ALPHA_RANGE');
 return Object.freeze(value);
}

export function applyReferenceTerritoryStyle(style,profile={}){
 const selected=validateReferenceTerritoryProfile(profile);
 if(!style||typeof style!=='object'||Array.isArray(style)||typeof style.profileName!=='string')
  throw Error('REFERENCE_GAIN_SOURCE_STYLE_REQUIRED');
 for(const name of ['losingColor','existingWinningColor','gainedWinningColor'])
  if(!rgba(style[name]))throw Error('REFERENCE_GAIN_RGBA_REQUIRED_'+name);
 const result=clone(style);
 if(!selected.enabled)return result;
 const original=style.gainedWinningColor,peak=Math.max(...original.slice(0,3));
 // A common RGB multiplier preserves source hue and saturation. Existing
 // high-valued source channels are never darkened to satisfy the headroom cap.
 const cap=Math.max(.98,peak),scale=peak>0?Math.min(selected.gainBrightness,cap/peak):1;
 result.gainedWinningColor=[...original.slice(0,3).map(channel=>channel*scale),
  original[3]===0?0:Math.max(original[3],selected.gainedAlpha)];
 result.profileName=style.profileName+'__'+REFERENCE_GAIN_STYLE_VERSION;
 return result;
}

export function describeReferenceGainStyle(sourceStyle,effectiveStyle,profile={}){
 const selected=validateReferenceTerritoryProfile(profile);
 for(const style of [sourceStyle,effectiveStyle])
  for(const name of ['existingWinningColor','gainedWinningColor'])if(!rgba(style?.[name]))
   throw Error('REFERENCE_GAIN_EVIDENCE_RGBA_REQUIRED');
 const gained=effectiveStyle.gainedWinningColor,held=effectiveStyle.existingWinningColor,
  original=sourceStyle.gainedWinningColor,peak=Math.max(...original.slice(0,3));
 return {version:REFERENCE_GAIN_STYLE_VERSION,enabled:selected.enabled,
  gainedMaterialDistinct:gained.some((channel,index)=>Math.abs(channel-held[index])>1e-12),
  profile:clone(selected),sourceGainedColor:clone(original),effectiveGainedColor:clone(gained),
  effectiveHeldColor:clone(held),effectiveLosingColor:clone(effectiveStyle.losingColor),
  appliedBrightness:peak>0?Math.max(...gained.slice(0,3))/peak:1,
  retainedSourceTerrainFraction:1-gained[3],sourceHuePreserved:true,
  classification:'UNCHANGED_ORIGINAL_BASE_AND_MOVING_BOUNDARY_CUMULATIVE_GAIN',
  cumulativeGain:true,recentGainAgeAvailable:false,temporalSettleImplemented:false,
  geometryChanged:false,timeChanged:false,sourceStyleMutated:false,standaloneFrontLine:false,
  newLines:false,newArrows:false,gpuPixelsVerified:false};
}
