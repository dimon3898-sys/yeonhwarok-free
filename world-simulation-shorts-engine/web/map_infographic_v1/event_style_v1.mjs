/** Event-only style selection over read-only material tokens and native pixels.
 * Colors and framebuffer samples are display sRGB, matching the raw Event pass.
 * Color analysis decodes to linear sRGB exactly once; no native theme is edited.
 */
export const EVENT_LINE_STYLE_V1_VERSION = 'EVENT_LINE_STYLE_V1_AUTOMATIC_CONTRAST';

// Generic saturated accents. The first two are the preferred cool family when
// their measured score wins; warm or violet accents remain available for a
// primary material whose chroma makes a cool accent difficult to distinguish.
export const EVENT_LINE_COLOR_CANDIDATES_SRGB = Object.freeze([
 {name:'BRIGHT_CYAN',family:'CYAN_TEAL',rgb:Object.freeze([.08,.94,1])},
 {name:'BRIGHT_TEAL',family:'CYAN_TEAL',rgb:Object.freeze([.07,1,.84])},
 {name:'CLEAR_AZURE',family:'BLUE',rgb:Object.freeze([.22,.72,1])},
 {name:'BRIGHT_VIOLET',family:'VIOLET',rgb:Object.freeze([.87,.48,1])},
 {name:'BRIGHT_CORAL',family:'CORAL',rgb:Object.freeze([1,.45,.38])},
 {name:'BRIGHT_AMBER',family:'AMBER',rgb:Object.freeze([1,.83,.22])},
].map(Object.freeze));

const finiteUnit = value => Number.isFinite(value) && value>=0 && value<=1;
const cloneRgb = (color,label) => {
 if(!Array.isArray(color)||color.length!==3||!color.every(finiteUnit))throw Error('EVENT_'+label+'_SRGB_REQUIRED');
 return [...color];
};
export const srgbChannelToLinear = value => {
 if(!finiteUnit(value))throw Error('EVENT_COLOR_CHANNEL_RANGE');
 return value<=.04045?value/12.92:((value+.055)/1.055)**2.4;
};
export function relativeLuminanceSrgb(color){
 const rgb=cloneRgb(color,'COLOR').map(srgbChannelToLinear);
 return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
}
export function contrastRatioSrgb(a,b){
 const ya=relativeLuminanceSrgb(a),yb=relativeLuminanceSrgb(b);
 return (Math.max(ya,yb)+.05)/(Math.min(ya,yb)+.05);
}

/** OKLab from linear sRGB (D65). Analysis only, never a renderer color transform. */
export function oklabSrgb(color){
 const [r,g,b]=cloneRgb(color,'COLOR').map(srgbChannelToLinear);
 const l=Math.cbrt(.4122214708*r+.5363325363*g+.0514459929*b);
 const m=Math.cbrt(.2119034982*r+.6806995451*g+.1073969566*b);
 const s=Math.cbrt(.0883024619*r+.2817188376*g+.6299787005*b);
 return [.2104542553*l+.793617785*m-.0040720468*s,
  1.9779984951*l-2.428592205*m+.4505937099*s,
  .0259040371*l+.7827717662*m-.808675766*s];
}
const quantile = (values,fraction) => {
 const sorted=[...values].sort((a,b)=>a-b),at=(sorted.length-1)*fraction;
 const lower=Math.floor(at),weight=at-lower;
 return sorted[lower]*(1-weight)+sorted[Math.min(sorted.length-1,lower+1)]*weight;
};
const stats = values => ({minimum:Math.min(...values),p10:quantile(values,.1),
 median:quantile(values,.5),mean:values.reduce((a,b)=>a+b,0)/values.length,maximum:Math.max(...values)});
const mix = (foreground,background,alpha) => foreground.map((value,index)=>value*alpha+background[index]*(1-alpha));
const difference = (a,b,start=0) => Math.hypot(...a.slice(start).map((value,index)=>value-b[index+start]));

/** Rank all candidates against actual unchanged background samples.
 * Score balances robust luminance contrast with perceptual chromatic separation;
 * neutral white cannot win by luminance alone because it is not an accent.
 * The cool-family preference is only a small deterministic tie preference.
 */
export function evaluateEventLineCandidates({primaryMaterialColor,backgroundSamples,alpha=.94}){
 const material=cloneRgb(primaryMaterialColor,'PRIMARY_MATERIAL');
 if(!finiteUnit(alpha)||alpha===0)throw Error('EVENT_CORE_ALPHA_REQUIRED');
 if(!Array.isArray(backgroundSamples)||backgroundSamples.length===0)throw Error('EVENT_BACKGROUND_SAMPLES_REQUIRED');
 const samples=backgroundSamples.map(sample=>cloneRgb(sample,'BACKGROUND_SAMPLE'));
 const materialLab=oklabSrgb(material);
 const sampleLabs=samples.map(oklabSrgb);
 const candidates=EVENT_LINE_COLOR_CANDIDATES_SRGB.map(candidate=>{
  const composite=samples.map(background=>mix(candidate.rgb,background,alpha));
  const candidateLab=oklabSrgb(candidate.rgb);
  const luminanceContrast=stats(composite.map((color,index)=>contrastRatioSrgb(color,samples[index])));
  const colorDistance=stats(composite.map((color,index)=>difference(oklabSrgb(color),sampleLabs[index])));
  const chromaticDistance=stats(composite.map((color,index)=>difference(oklabSrgb(color),sampleLabs[index],1)));
  const primaryMaterialChromaticDistance=difference(candidateLab,materialLab,1);
  // log2 is a symmetric, bounded-growth luminance term. OKLab distances use
  // their native unit scale, including the actual background's output hue.
  const score=.30*Math.log2(luminanceContrast.p10)+1.60*chromaticDistance.p10
   +.75*colorDistance.mean+.35*primaryMaterialChromaticDistance
   +(candidate.family==='CYAN_TEAL'?.015:0);
  return {...candidate,rgb:[...candidate.rgb],luminance:relativeLuminanceSrgb(candidate.rgb),
   luminanceContrast,colorDistance,chromaticDistance,primaryMaterialChromaticDistance,score};
 });
 return {space:'DISPLAY_SRGB_DECODED_ONCE_TO_LINEAR_SRGB_D65',sampleCount:samples.length,
  primaryMaterialColor:material,backgroundSamples:samples,backgroundLuminance:stats(samples.map(relativeLuminanceSrgb)),
  backgroundMean:samples.reduce((sum,rgb)=>sum.map((value,index)=>value+rgb[index]/samples.length),[0,0,0]),
  alpha,scoreFormula:'0.30*log2(p10_luminance_ratio) + 1.60*p10_OKLab_chroma_distance + 0.75*mean_OKLab_distance + 0.35*material_OKLab_chroma_distance + 0.015_cool_tie_preference',
  candidates,selected:candidates.reduce((best,item)=>item.score>best.score?item:best)};
}

/** A modest one-step width increase and compact same-family Event glow.
 * No geometry, geographic data, marker, typography or native visual is read or
 * modified. Missing native samples fall back explicitly to the material hue.
 */
export function selectEventLineStyle({role,theme,primaryMaterialColor,backgroundSamples}){
 if(!['PRIMARY','SECONDARY'].includes(role))throw Error('EVENT_LINE_UNKNOWN_STYLE_ROLE');
 if(!theme||typeof theme!=='object'||Array.isArray(theme))throw Error('EVENT_NATIVE_THEME_REQUIRED');
 const prefix=role==='PRIMARY'?'primary':'secondary',baseWidth=theme[prefix+'Width'];
 if(!Number.isFinite(baseWidth)||baseWidth<=0||!Number.isFinite(theme.glowRadius)||theme.glowRadius<=0
  ||!finiteUnit(theme.glowGain))throw Error('EVENT_NATIVE_STYLE_TOKENS_REQUIRED');
 const material=primaryMaterialColor??theme.primary;
 const nativeSamples=backgroundSamples!==undefined;
 const coreAlpha=.94,glowGain=Math.min(theme.glowGain,.10);
 // The existing capsule pass combines same-color core and glow coverage at
 // the line centre; model that exact alpha before comparing display pixels.
 const centreAlpha=coreAlpha+glowGain*(1-coreAlpha);
 const evaluation=evaluateEventLineCandidates({primaryMaterialColor:material,
  backgroundSamples:nativeSamples?backgroundSamples:[material],alpha:centreAlpha});
 const selected=evaluation.selected,width=baseWidth+Math.min(2,.4*baseWidth);
 const result={width,coreColor:[...selected.rgb,coreAlpha],
  glowRadius:Math.min(theme.glowRadius,1.25),glowGain,glowColor:[...selected.rgb,1],
  selection:{version:EVENT_LINE_STYLE_V1_VERSION,role,nativeBaseWidth:baseWidth,widthIncreasePixels:width-baseWidth,
   coreAlpha,centerCompositeAlpha:centreAlpha,
   sampleSource:nativeSamples?'ACTUAL_NATIVE_FRAMEBUFFER_SRGB':'PRIMARY_MATERIAL_SRGB_FALLBACK',
   selectedName:selected.name,selectedFamily:selected.family,...evaluation}};
 return result;
}
