/** Generic opacity policy over the EXISTING territorial ownership material.
 * No classifier, geometry, faction hue, front, camera or timeline is created.
 */
export const QUALITY_TERRITORY_STYLE_VERSION='QUALITY_TERRITORY_OPACITY_V1';
export const DEFAULT_QUALITY_TERRITORY_PROFILE=Object.freeze({minimumAlpha:.72,maximumAlpha:.82,opacityGain:1.10});
const ranges={minimumAlpha:[0,.82],maximumAlpha:[.5,.90],opacityGain:[1,1.5]};
const clone=value=>structuredClone(value);
const colorNames=['losingColor','existingWinningColor','gainedWinningColor'];
const rgba=value=>Array.isArray(value)&&value.length===4&&value.every(v=>Number.isFinite(v)&&v>=0&&v<=1);
export function validateQualityTerritoryProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('QUALITY_TERRITORY_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(ranges,key))throw Error('QUALITY_TERRITORY_UNKNOWN_PROFILE_'+key);
 const p={...DEFAULT_QUALITY_TERRITORY_PROFILE,...clone(input)};
 for(const [key,[low,high]] of Object.entries(ranges))
  if(!Number.isFinite(p[key])||p[key]<low||p[key]>high)throw Error('QUALITY_TERRITORY_PROFILE_RANGE_'+key);
 if(p.minimumAlpha>p.maximumAlpha)throw Error('QUALITY_TERRITORY_ALPHA_ORDER_REQUIRED');
 return Object.freeze(p);
}
export function applyQualityTerritoryStyle(style,profile={}){
 if(!style||typeof style!=='object'||Array.isArray(style)||typeof style.profileName!=='string')
  throw Error('QUALITY_TERRITORY_SOURCE_STYLE_REQUIRED');
 const p=validateQualityTerritoryProfile(profile),result=clone(style);
 for(const name of colorNames){
  if(!rgba(style[name]))throw Error('QUALITY_TERRITORY_RGBA_REQUIRED_'+name);
  const original=style[name][3];
  // An explicitly invisible original role stays invisible. An already more
  // opaque role is never weakened. New opacity is capped by the profile.
  result[name][3]=original===0?0:Math.max(original,Math.min(p.maximumAlpha,Math.max(p.minimumAlpha,original*p.opacityGain)));
 }
 result.profileName=style.profileName+'__'+QUALITY_TERRITORY_STYLE_VERSION;
 return result;
}
/** Exact normalized framebuffer SRC_ALPHA / ONE_MINUS_SRC_ALPHA RGB oracle.
 * Encoded/working channel values match the inherited framebuffer convention;
 * no claim of colourimetric sRGB conversion or GPU pixels is made here.
 */
export function compositeTerritorySample(background,color){
 if(!Array.isArray(background)||background.length!==3||!background.every(v=>Number.isFinite(v)&&v>=0&&v<=1)||!rgba(color))
  throw Error('QUALITY_TERRITORY_RGB_SAMPLE_REQUIRED');
 return background.map((value,index)=>color[index]*color[3]+value*(1-color[3]));
}
export function territorySeparation(background,style){
 const winner=compositeTerritorySample(background,style.existingWinningColor),
  loser=compositeTerritorySample(background,style.losingColor);
 return {winner,loser,rgbDistance:Math.hypot(...winner.map((value,index)=>value-loser[index])),
  retainedBackgroundFraction:{winner:1-style.existingWinningColor[3],loser:1-style.losingColor[3]}};
}
