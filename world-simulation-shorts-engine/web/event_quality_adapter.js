/** v019 close-view radiance only; native v018 detail and camera are inherited.
 * No artificial city detail, blur, post-AA, lighting clock, or new texture.
 */
import {SceneVisualQualityRenderer, digestBytes, trustedStaticURL} from './visual_quality_adapter.js';

export const EVENT_QUALITY_VERSION='v019';
const clamp=(v,lo=0,hi=1)=>Math.max(lo,Math.min(hi,v));
const smooth=v=>{const x=clamp(v);return x*x*(3-2*x);};
const finite=(v,lo,hi)=>Number.isFinite(v)&&v>=lo&&v<=hi;
const sha=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const fail=rule=>{throw Error(`EVENT_QUALITY_${rule}`);};

export function validateEventQualityProfile(value){
 if(value?.version!==EVENT_QUALITY_VERSION||value.parent_version!=='v018')fail('PROFILE_VERSION_INVALID');
 for(const [name,low,high] of [['day_input_scale',.4,1],['ocean_specular_scale',.1,1],['city_contribution_scale',.01,1]])
  if(!finite(value[name],low,high))fail('RESPONSE_INVALID');
 if(!finite(value.daylight_start,0,.5)||!finite(value.daylight_full,value.daylight_start+.001,.5))fail('DAYLIGHT_GATE_INVALID');
 if(value.city_mask!=='existing_native_regional_land_mask'||value.additional_textures!==0)fail('MASK_SOURCE_INVALID');
 return value;
}

/** Analytical shader response, not a GPU rasterizer or rendered AFTER frame. */
export function eventQualityResponse({diffuse,readable,spec,lights,nd,weight,landMask=1},profile){
 const unchanged={diffuse:[...diffuse],readable:[...readable],spec,lights:[...lights]};
 if(weight<=0)return unchanged;
 const daylight=smooth((nd-profile.daylight_start)/(profile.daylight_full-profile.daylight_start));
 const dayScale=1+(profile.day_input_scale-1)*weight*daylight;
 const specScale=1+(profile.ocean_specular_scale-1)*weight*daylight;
 const cityScale=1+(profile.city_contribution_scale-1)*weight;
 const maskScale=1+(clamp(landMask)-1)*weight;
 return {diffuse:diffuse.map(v=>v*dayScale),readable:readable.map(v=>v*dayScale),
  spec:spec*dayScale*specScale,lights:lights.map(v=>v*cityScale*maskScale)};
}

function replaceOnce(shader,original,replacement,rule){
 if(shader.split(original).length!==2)fail(`SHADER_CONTRACT_${rule}`);
 return shader.replace(original,replacement);
}

export function eventQualitySurfaceShader(shader,count){
 if(count!==2)fail('PRESERVED_MASK_COUNT_INVALID');
 // These are the *existing* v018 samplers/geographic bounds. No map is
 // generated, fetched or uploaded to fabricate smaller urban light clusters.
 const masks=Array.from({length:count},(_,i)=>`
  {vec4 bounds=uVQBounds${i};vec2 q=(ll-bounds.xy)/(bounds.zw-bounds.xy);
   if(q.x>=0.&&q.x<=1.&&q.y>=0.&&q.y<=1.){
    float edge=min(min(ll.x-bounds.x,bounds.z-ll.x),min(ll.y-bounds.y,bounds.w-ll.y));
    float confidence=smoothstep(0.,uVQEdgeFeather,edge);
    return mix(1.,clamp(texture2D(uVQMask${i},q).r,0.,1.),confidence);
   }}
 `).join('\n');
 const helpers=`
uniform float uEQWeight,uEQDayScale,uEQSpecularScale,uEQCityScale,uEQDaylightStart,uEQDaylightFull;
float eventQualityLandMask(vec2 uv){
 if(uEQWeight<=0.)return 1.;
 vec2 ll=vec2(uv.x*360.-180.,uv.y*180.-90.);
 ${masks}
 return 1.;
}
`;
 const policy=`
// Weight zero is the exact v018 WIDE calculation, with no added arithmetic.
if(uEQWeight>0.){
 float daylight=smoothstep(uEQDaylightStart,uEQDaylightFull,nd);
 float dayScale=mix(1.,uEQDayScale,uEQWeight*daylight);
 diffuse*=dayScale;readable*=dayScale;
 spec*=dayScale*mix(1.,uEQSpecularScale,uEQWeight*daylight);
 lights*=mix(1.,uEQCityScale,uEQWeight)*mix(1.,eventQualityLandMask(uv),uEQWeight);
}
`;
 let result=replaceOnce(shader,'void main(){',helpers+'\nvoid main(){','MAIN');
 result=replaceOnce(result,'gl_FragColor=vec4((diffuse+readable+',policy+'\ngl_FragColor=vec4((diffuse+readable+','SURFACE_OUTPUT');
 return result;
}

async function fetchProfile(selection){
 if(!sha(selection.profile_sha256))fail('SOURCE_HASH_REQUIRED');
 const url=trustedStaticURL(selection.profile_url);
 if(url!=='/static/event_quality_v019.json')fail('SOURCE_URL_INVALID');
 const response=await fetch(url,{credentials:'same-origin',redirect:'error'});
 if(!response.ok)fail('PROFILE_FETCH_FAILED');
 const bytes=await response.arrayBuffer(),hash=await digestBytes(bytes);
 if(hash!==selection.profile_sha256)fail('SOURCE_HASH_MISMATCH');
 let value;try{value=JSON.parse(new TextDecoder().decode(bytes));}catch{fail('PROFILE_JSON_INVALID');}
 return {value:validateEventQualityProfile(value),hash};
}

export class SceneEventQualityRenderer extends SceneVisualQualityRenderer{
 constructor(scene,plan){
  if(scene.event_quality?.version!==EVENT_QUALITY_VERSION)fail('EXPLICIT_V019_OPT_IN_REQUIRED');
  super(scene,plan);this.eventQualityReady=false;
 }
 async init(){
  await super.init();
  const loaded=await fetchProfile(this.sceneSpec.event_quality);
  this.eventQualityProfile=loaded.value;this.eventQualityProfileHash=loaded.hash;
  this.installEventQualitySurface();this.eventQualityReady=true;this.frame(0);return this;
 }
 installEventQualitySurface(){
  const m=this.map.surface,p=this.eventQualityProfile;
  m.fragmentShader=eventQualitySurfaceShader(m.fragmentShader,this.qualityTiles.length);
  Object.assign(m.uniforms,{uEQWeight:{value:0},uEQDayScale:{value:p.day_input_scale},
   uEQSpecularScale:{value:p.ocean_specular_scale},uEQCityScale:{value:p.city_contribution_scale},
   uEQDaylightStart:{value:p.daylight_start},uEQDaylightFull:{value:p.daylight_full}});
  m.needsUpdate=true;
 }
 mapAt(t){
  super.mapAt(t);if(!this.eventQualityReady)return;
  // Observe the existing v018 material LOD weight; no camera/timing changes.
  this.map.surface.uniforms.uEQWeight.value=this.map.surface.uniforms.uVQWeight.value;
 }
 audit(t){
  const value=super.audit(t);if(!this.eventQualityReady)return value;
  const u=this.map.surface.uniforms,p=this.eventQualityProfile;
  value.eventQuality={version:EVENT_QUALITY_VERSION,parent_version:'v018',profile_sha256:this.eventQualityProfileHash,
   material_weight:u.uEQWeight.value,day_input_scale:p.day_input_scale,ocean_specular_scale:p.ocean_specular_scale,
   city_contribution_scale:p.city_contribution_scale,city_mask:p.city_mask,
   additional_textures:0,additional_texture_uploads:0,
   source_semantics:'Existing 8K night footprints are subdued using existing native land masks; no higher-resolution urban data is inferred',
   controls:'Close-view surface input before the unchanged HDR film transform; night surface fill and post/cloud/atmosphere unchanged',
   preserved:{camera:true,timing:true,wide:true,regional_lod:true,post:true,cloud:true,atmosphere:true,text:true,audio:true}};
  return value;
 }
}
