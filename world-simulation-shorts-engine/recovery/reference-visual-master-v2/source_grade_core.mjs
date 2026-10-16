/** Grade an already authentic SOURCE material before ownership/frontier/art.
 * This is bounded encoded-RGB grading, not new elevation, normals, GIS or waves. */
export const REFERENCE_SOURCE_GRADE_VERSION='REFERENCE_SOURCE_GRADE_V2';
export const DEFAULT_REFERENCE_SOURCE_PROFILE=Object.freeze({enabled:false,registerDomainCoverage:false,
 terrainLocalContrast:1.2,landExposure:1.04,oceanExposure:1.2,oceanTealMix:.12,screenFeatherPixels:32});
const clone=value=>structuredClone(value),limits={terrainLocalContrast:[1,1.4],landExposure:[1,1.2],
 oceanExposure:[1,1.5],oceanTealMix:[0,.3],screenFeatherPixels:[8,96]};
export function validateReferenceSourceProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_SOURCE_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(DEFAULT_REFERENCE_SOURCE_PROFILE,key))throw Error('REFERENCE_SOURCE_UNKNOWN_PARAMETER_'+key);
 const value={...DEFAULT_REFERENCE_SOURCE_PROFILE,...clone(input)};
 for(const key of ['enabled','registerDomainCoverage'])if(typeof value[key]!=='boolean')throw Error('REFERENCE_SOURCE_BOOLEAN_REQUIRED_'+key);
 for(const [key,[lo,hi]]of Object.entries(limits))if(!Number.isFinite(value[key])||value[key]<lo||value[key]>hi)
  throw Error('REFERENCE_SOURCE_PARAMETER_RANGE_'+key);
 return Object.freeze(value);
}
export function sourceGradeIsNeutral(profile){
 const p=validateReferenceSourceProfile(profile);return !p.enabled||
  p.terrainLocalContrast===1&&p.landExposure===1&&p.oceanExposure===1&&p.oceanTealMix===0;
}
const luminance=rgb=>rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
/** CPU pointwise oracle. localAverage must come from authentic material taps
 * with all five native land coverages fully inside land; no coast embossing. */
export function gradeSourceRgb(rgb,{coverage,localAverage,interiorLand=true,interiorSupport=true,oceanTint,landSupport=0,oceanSupport=0}={},profile={}){
 const p=validateReferenceSourceProfile(profile);
 if(!Array.isArray(rgb)||rgb.length!==3||!rgb.every(v=>Number.isFinite(v)&&v>=0&&v<=1)
  ||!Number.isFinite(coverage)||coverage<0||coverage>1)throw Error('REFERENCE_SOURCE_RGB_COVERAGE_REQUIRED');
 if(![landSupport,oceanSupport].every(v=>Number.isFinite(v)&&v>=0&&v<=1))throw Error('REFERENCE_SOURCE_SUPPORT_WEIGHTS_REQUIRED');
 if(sourceGradeIsNeutral(p))return [...rgb];
 if(coverage*landSupport===0&&(1-coverage)*oceanSupport===0)return [...rgb];
 if(!Array.isArray(oceanTint)||oceanTint.length!==3||!oceanTint.every(v=>Number.isFinite(v)&&v>=0&&v<=1))throw Error('REFERENCE_SOURCE_OCEAN_TINT_REQUIRED');
 const y=luminance(rgb),base=Number.isFinite(localAverage)&&localAverage>0?localAverage:Math.max(y,.001),
 ratio=interiorLand&&interiorSupport?Math.max(.86,Math.min(1.18,Math.pow(Math.max(y,.001)/Math.max(base,.001),p.terrainLocalContrast-1))):1,
 tintY=Math.max(luminance(oceanTint),.001);
 return rgb.map((value,i)=>{
  const land=Math.max(0,Math.min(.98,value*ratio*p.landExposure)),
   ocean=Math.max(0,Math.min(.98,((1-p.oceanTealMix)*value+p.oceanTealMix*y*oceanTint[i]/tintY)*p.oceanExposure));
  return Math.max(0,Math.min(1,value+coverage*landSupport*(land-value)+(1-coverage)*oceanSupport*(ocean-value)));
 });
}
export const SOURCE_GRADE_FRAGMENT=`#version 300 es
precision highp float;in vec2 vUv;out vec4 frag;
uniform sampler2D actualSource,coverageTexture,supportTexture;uniform vec2 screenDimensions;
uniform float terrainLocalContrast,landExposure,oceanExposure,oceanTealMix;uniform vec3 oceanTint;
float y(vec3 value){return dot(value,vec3(.2126,.7152,.0722));}
void main(){
 vec3 source=texture(actualSource,vUv).rgb;float land=clamp(texture(coverageTexture,vUv).r,0.,1.);
 vec2 stepUv=1./screenDimensions;
 vec2 e=vUv+vec2(stepUv.x,0.),w=vUv-vec2(stepUv.x,0.),n=vUv+vec2(0.,stepUv.y),s=vUv-vec2(0.,stepUv.y);
 float local=(4.*y(source)+y(texture(actualSource,e).rgb)+y(texture(actualSource,w).rgb)+
  y(texture(actualSource,n).rgb)+y(texture(actualSource,s).rgb))/8.;
 float interior=min(land,min(min(texture(coverageTexture,e).r,texture(coverageTexture,w).r),
  min(texture(coverageTexture,n).r,texture(coverageTexture,s).r)));
 vec2 support=clamp(texture(supportTexture,vUv).rg,0.,1.);
 float supportedInterior=min(support.r,min(min(texture(supportTexture,e).r,texture(supportTexture,w).r),
  min(texture(supportTexture,n).r,texture(supportTexture,s).r)));
 // Never create a coast outline by contrasting land against neighbouring sea.
 float detail=interior>.999&&supportedInterior>.999?clamp(pow(max(y(source),.001)/max(local,.001),terrainLocalContrast-1.),.86,1.18):1.;
 vec3 gradedLand=clamp(source*detail*landExposure,0.,.98);
 vec3 teal=y(source)*oceanTint/max(y(oceanTint),.001);
 vec3 gradedOcean=clamp(mix(source,teal,oceanTealMix)*oceanExposure,0.,.98);
 vec3 graded=source+land*support.r*(gradedLand-source)+(1.-land)*support.g*(gradedOcean-source);
 frag=vec4(clamp(graded,0.,1.),1.);
}`;
