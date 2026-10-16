/** Bounded expression profile only. The original evaluated front, motion,
 * ownership classifier and source geometry are not replaced. */
export const REFERENCE_FRONTIER_EXPRESSION_VERSION='REFERENCE_FRONTIER_EXPRESSION_V2';
export const DEFAULT_REFERENCE_FRONTIER_PROFILE=Object.freeze({enabled:false,whiteFront:true,
 frontierIntensity:1,frontierWidth:2.5,frontierHaloSigma:4,minimumLightingFactor:.76,
 outerGoldIntensity:.75,outerGoldWidth:1,outerGoldSigma:2.2,outerGoldSupport:6,
 outerGoldColor:Object.freeze([1,.83,.25]),outerGoldHaloColor:Object.freeze([1,.63,.12])});
const ranges={frontierIntensity:[0,1],frontierWidth:[.5,2.5],frontierHaloSigma:[.5,4],
 minimumLightingFactor:[.65,1],outerGoldIntensity:[0,1],outerGoldWidth:[.5,1.5],
 outerGoldSigma:[.5,3],outerGoldSupport:[4,6]};
const clone=value=>structuredClone(value),rgb=value=>Array.isArray(value)&&value.length===3&&value.every(x=>Number.isFinite(x)&&x>=0&&x<=1);
export function validateReferenceFrontierProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_FRONTIER_PROFILE_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(DEFAULT_REFERENCE_FRONTIER_PROFILE,key))throw Error('REFERENCE_FRONTIER_UNKNOWN_PROFILE_'+key);
 const p={...clone(DEFAULT_REFERENCE_FRONTIER_PROFILE),...clone(input)};
 if(typeof p.enabled!=='boolean'||typeof p.whiteFront!=='boolean')throw Error('REFERENCE_FRONTIER_EXPLICIT_BOOLEAN_REQUIRED');
 for(const [key,[low,high]] of Object.entries(ranges))if(!Number.isFinite(p[key])||p[key]<low||p[key]>high)
  throw Error('REFERENCE_FRONTIER_PROFILE_RANGE_'+key);
 for(const key of ['outerGoldColor','outerGoldHaloColor'])if(!rgb(p[key]))throw Error('REFERENCE_FRONTIER_RGB_REQUIRED');
 if(p.outerGoldSupport<=p.outerGoldSigma||p.outerGoldSupport<=p.outerGoldWidth)throw Error('REFERENCE_FRONTIER_FINITE_SUPPORT_REQUIRED');
 return Object.freeze(p);
}
export function applyReferenceFrontierStyle(original,profile={}){
 const p=validateReferenceFrontierProfile(profile);
 if(!original||typeof original.profileName!=='string'||!Number.isFinite(original.centerAlpha)||!Number.isFinite(original.haloAlpha))
  throw Error('REFERENCE_FRONTIER_ORIGINAL_STYLE_REQUIRED');
 if(!p.enabled)return clone(original);
 return {...clone(original),profileName:original.profileName+'__'+REFERENCE_FRONTIER_EXPRESSION_VERSION,
  centerColor:p.whiteFront?[1,1,1]:clone(original.centerColor),haloColor:p.whiteFront?[1,1,1]:clone(original.haloColor),
  centerWidthPixels:p.frontierWidth,haloSigmaPixels:p.frontierHaloSigma,
  centerAlpha:original.centerAlpha*p.frontierIntensity,haloAlpha:original.haloAlpha*p.frontierIntensity,
  minimumLightingFactor:p.minimumLightingFactor};
}

/** Original flat native renderer maps bounds directly to canonical pixels.
 * Validate the projection itself, rather than accepting a merely same-size mask. */
export function assertOuterDomainContext(context,{controls,project,domainMetadata,width=1080,height=1920}={}){
 if(!context||context.rowZero!=='SOUTH'||context.width!==width||context.height!==height||
  !(context.domainCoverage instanceof Uint8Array)||context.domainCoverage.length!==width*height)
  throw Error('REFERENCE_OUTER_NATIVE_COVERAGE_REQUIRED');
 if(!controls||context.frame!==controls.frame||context.nativeFrame!==controls.localFrame)
  throw Error('REFERENCE_OUTER_SAME_FRAME_REQUIRED');
 if(!domainMetadata||context.domainSHA256!==domainMetadata.domainSHA256||
  context.sourceGeometrySHA256!==domainMetadata.sourceGeometrySHA256||
  JSON.stringify(context.roleIds)!==JSON.stringify(domainMetadata.selectedRoleIds))
  throw Error('REFERENCE_OUTER_DOMAIN_BINDING_REQUIRED');
 const b=context.bounds;
 if(!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite)||b[0]>=b[2]||b[1]>=b[3]||typeof project!=='function')
  throw Error('REFERENCE_OUTER_NATIVE_BOUNDS_REQUIRED');
 for(const [geo,expected] of [[[b[0],b[1]],[0,height]],[[b[2],b[3]],[width,0]],
  [[(b[0]+b[2])/2,(b[1]+b[3])/2],[width/2,height/2]]]){
  const actual=project(geo);
  if(!Array.isArray(actual)||actual.length!==2||!actual.every(Number.isFinite)||Math.hypot(actual[0]-expected[0],actual[1]-expected[1])>.01)
   throw Error('REFERENCE_OUTER_CAMERA_PROJECTION_MISMATCH');
 }
 return true;
}

/** CPU oracle for the SAME finite neighborhood response as the GPU style.
 * No mask is repaired, blurred, expanded, traced or inferred from source RGB.
 * Clamping at canvas edges avoids inventing a coastline at a viewport crop. */
export function sampleOuterDomainResponse(coverage,width,height,x,y,profile={},presentationScale=1){
 const p=validateReferenceFrontierProfile(profile);
 if(!(coverage instanceof Uint8Array)||coverage.length!==width*height||!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||
  !Number.isSafeInteger(x)||!Number.isSafeInteger(y)||x<0||y<0||x>=width||y>=height||!Number.isFinite(presentationScale)||presentationScale<1||presentationScale>2)
  throw Error('REFERENCE_OUTER_SAMPLE_REQUIRED');
 const read=(px,py)=>coverage[Math.max(0,Math.min(height-1,py))*width+Math.max(0,Math.min(width-1,px))]/255,
  c=read(x,y),radii=[p.outerGoldWidth,p.outerGoldSupport/3,p.outerGoldSupport*2/3,p.outerGoldSupport].map(r=>r/presentationScale);
 let core=0,halo=0;
 for(let i=0;i<4;i++){
  const radius=Math.max(1,Math.floor(radii[i]+.5)),values=[read(x-radius,y),read(x+radius,y),read(x,y-radius),read(x,y+radius)],
   response=Math.max(0,Math.max(...values.map(v=>Math.abs(v-c)))-2/255)/(1-2/255);
  if(i===0)core=Math.max(0,c-Math.min(...values)-2/255)/(1-2/255);
  halo=Math.max(halo,response*Math.exp(-.5*Math.pow(radii[i]/(p.outerGoldSigma/presentationScale),2)));
 }
 return {core:Math.min(1,core),halo:Math.min(1,halo)};
}
export function outerGoldScreenBlend(destination,response,profile={}){
 const p=validateReferenceFrontierProfile(profile);
 if(!rgb(destination)||!response||!Number.isFinite(response.core)||!Number.isFinite(response.halo)||
  response.core<0||response.core>1||response.halo<0||response.halo>1)throw Error('REFERENCE_OUTER_BLEND_SAMPLE_REQUIRED');
 if(!p.enabled||p.outerGoldIntensity===0)return [...destination];
 const core=response.core*.95*p.outerGoldIntensity,halo=response.halo*.28*p.outerGoldIntensity;
 return destination.map((value,index)=>{const source=p.outerGoldColor[index]*core+p.outerGoldHaloColor[index]*halo*(1-core);
  return source+value*(1-source);});
}
