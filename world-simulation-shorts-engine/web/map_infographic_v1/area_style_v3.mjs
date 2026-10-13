/** Event-owned Area accents selected over unchanged native display-sRGB colors. */
import {evaluateEventLineCandidates,oklabSrgb} from './event_style_v1.mjs';

export const AREA_STYLE_V3_VERSION='AREA_EVENT_STYLE_V3_AUTOMATIC_CONTRAST';
const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};
const distance=(a,b)=>Math.hypot(...a.map((value,index)=>value-b[index]));

/** No country, subject, material, or source geometry receives a special style. */
export function selectAreaStyle({primaryMaterialColor,backgroundSamples,profile={}}={}){
 const samples=backgroundSamples?.length?backgroundSamples:[primaryMaterialColor];
 const evaluation=evaluateEventLineCandidates({primaryMaterialColor,backgroundSamples:samples,alpha:.94});
 const selected=evaluation.selected,reference=oklabSrgb(selected.rgb);
 // A second accent distinguishes an explicitly supplied impact footprint. Its
 // choice remains tied to measured background contrast and the first accent.
 const impact=evaluation.candidates.filter(candidate=>candidate.name!==selected.name).reduce((best,candidate)=>{
  const value=candidate.score+.75*distance(oklabSrgb(candidate.rgb),reference);
  return value>best.value?{candidate,value}:best;
 },{candidate:selected,value:-Infinity}).candidate;
 const opacity=profile.fillOpacity??.16,impactOpacity=profile.impactOpacity??.23;
 if(!Number.isFinite(opacity)||opacity<.08||opacity>.24||!Number.isFinite(impactOpacity)||impactOpacity<.12||impactOpacity>.28)
  throw Error('AREA_STYLE_RESTRAINED_OPACITY_REQUIRED');
 const role=(rgb,fill,width,alpha)=>({fillColor:[...rgb,fill],coreColor:[...rgb,alpha],width,
  glowColor:[...rgb,1],glowRadius:1.4,glowGain:.075});
 return freeze({version:AREA_STYLE_V3_VERSION,
  AREA:role(selected.rgb,opacity,3.2,.82),IMPACT:role(impact.rgb,impactOpacity,3.6,.92),
  PROPAGATION:role(selected.rgb,0,4.4,.94),FRONT:role(selected.rgb,0,4.6,.92),
  selection:{primaryMaterialColor:[...primaryMaterialColor],sampleCount:samples.length,
   sampleSource:backgroundSamples?.length?'ACTUAL_NATIVE_BACKGROUND_SRGB':'PRIMARY_MATERIAL_SRGB_FALLBACK',
   selectedName:selected.name,impactName:impact.name,analysis:evaluation},
  composition:'TRANSLUCENT_EVENT_FILL_AND_FINITE_CONTOUR_NATIVE_BOUNDARY_MASKED'});
}
