/** v018 material-only detail LOD over the unchanged v017 camera renderer.
 * Regional RGB is real Natural Earth land-cover/shaded relief, never a DEM,
 * emissive night source, or a synthetic sharpening operation.
 */
import * as THREE from 'three';
import {SceneSecondEventRenderer} from './second_event_camera.js';

export const VISUAL_QUALITY_VERSION='v018';
const clamp=(value,low=0,high=1)=>Math.max(low,Math.min(high,value));
const smooth=value=>{const x=clamp(value);return x*x*(3-2*x);};
const finite=(value,low,high)=>Number.isFinite(value)&&value>=low&&value<=high;
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const fail=rule=>{throw Error(`VISUAL_QUALITY_${rule}`);};

export function qualityWeight(height,profile){
 const regional=profile.regional_detail;
 return smooth((regional.wide_height-height)/(regional.wide_height-regional.close_height));
}

export function validateQualityProfile(profile){
 if(profile?.version!==VISUAL_QUALITY_VERSION)fail('PROFILE_VERSION_INVALID');
 const detail=profile.regional_detail,surface=profile.surface,filtering=profile.filtering;
 if(!detail||!finite(detail.max_blend,0,.75)||!finite(detail.close_height,.01,1)||
    !finite(detail.wide_height,detail.close_height+.01,5)||!finite(detail.edge_feather_degrees,.01,10))fail('REGIONAL_PROFILE_INVALID');
 if(!surface||!finite(surface.close_exposure_scale,.5,1)||!finite(surface.ocean_specular_scale,0,1)||
    !finite(surface.city_power,.82,1.5)||!finite(surface.city_gain_scale,0,1)||!finite(surface.city_focus_limit,1,3))fail('SURFACE_PROFILE_INVALID');
 if(!filtering||!finite(filtering.anisotropy_request,1,16))fail('FILTER_PROFILE_INVALID');
 trustedStaticURL(detail.manifest_url,'/static/earth-detail/v018/');
 return profile;
}

export function trustedStaticURL(value,prefix='/static/'){
 if(typeof value!=='string'||!value.startsWith(prefix)||/[\\%\x00-\x20\x7f?#]/.test(value)||value.includes('..'))fail('SOURCE_URL_INVALID');
 const origin=globalThis.location?.origin||'http://localhost';
 const url=new URL(value,origin);
 if(url.origin!==origin||!url.pathname.startsWith(prefix)||url.search||url.hash)fail('SOURCE_URL_INVALID');
 return value;
}

export function validateDetailManifest(manifest){
 if(manifest?.version!==VISUAL_QUALITY_VERSION||!Array.isArray(manifest.textures)||manifest.textures.length!==4)fail('MANIFEST_INVALID');
 const rgb=manifest.textures.filter(source=>source.role==='regional_day_relief');
 const masks=manifest.textures.filter(source=>source.role==='regional_land_mask');
 if(rgb.length!==2||masks.length!==2)fail('DETAIL_SOURCE_INVALID');
 const paired=rgb.map(source=>{
  const matched=masks.filter(mask=>mask.region_id===source.region_id);
  if(matched.length!==1)fail('DETAIL_SOURCE_INVALID');
  const mask=matched[0];
  if(JSON.stringify(mask.bounds)!==JSON.stringify(source.bounds)||mask.width!==source.width||mask.height!==source.height)fail('DETAIL_SOURCE_INVALID');
  return {...source,mask_url:mask.url,mask_sha256:mask.sha256,mask_width:mask.width,mask_height:mask.height};
 });
 const ids=new Set();
 for(const source of paired){
  if(typeof source.id!=='string'||ids.has(source.id)||source.role!=='regional_day_relief'||
     !sha(source.sha256)||!sha(source.mask_sha256)||!Number.isInteger(source.width)||!Number.isInteger(source.height)||
     source.width<1||source.height<1||source.width>8192||source.height>8192||
     source.mask_width!==source.width||source.mask_height!==source.height||
     !Array.isArray(source.bounds)||source.bounds.length!==4||!source.bounds.every(Number.isFinite)||
     source.bounds[0]>=source.bounds[2]||source.bounds[1]>=source.bounds[3]||
     source.bounds[0]<-180||source.bounds[2]>180||source.bounds[1]<-90||source.bounds[3]>90||
     !Array.isArray(source.source_resolution)||source.source_resolution.join(',')!=='21600,10800')fail('DETAIL_SOURCE_INVALID');
  ids.add(source.id);trustedStaticURL(source.url,'/static/earth-detail/v018/');trustedStaticURL(source.mask_url,'/static/earth-detail/v018/');
 }
 return {...manifest,textures:paired};
}

export async function digestBytes(bytes){
 if(!globalThis.crypto?.subtle)fail('SOURCE_HASH_UNAVAILABLE');
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(value=>value.toString(16).padStart(2,'0')).join('');
}

async function fetchJSON(url,expectedHash){
 trustedStaticURL(url);
 const response=await fetch(url,{credentials:'same-origin',redirect:'error'});
 if(!response.ok)fail('SOURCE_FETCH_FAILED');
 const bytes=await response.arrayBuffer(),actualHash=await digestBytes(bytes);
 if(expectedHash&&(!sha(expectedHash)||expectedHash!==actualHash))fail('SOURCE_HASH_MISMATCH');
 let value;try{value=JSON.parse(new TextDecoder().decode(bytes));}catch{fail('SOURCE_JSON_INVALID');}
 return {value,sha256:actualHash};
}

export function configureQualityTexture(texture,capabilities,request,srgb){
 const image=texture.image,maximum=capabilities.maxTextureSize;
 if(!image?.width||!image?.height||!finite(maximum,1,65536)||image.width>maximum||image.height>maximum)fail('TEXTURE_UPLOAD_SIZE_INVALID');
 const supported=capabilities.getMaxAnisotropy();
 texture.wrapS=THREE.ClampToEdgeWrapping;texture.wrapT=THREE.ClampToEdgeWrapping;
 texture.minFilter=THREE.LinearMipmapLinearFilter;texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=true;
 texture.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;
 texture.anisotropy=Math.max(1,Math.min(request,Number.isFinite(supported)?supported:1));texture.needsUpdate=true;
 return texture;
}

async function loadVerifiedTexture(source,urlKey,hashKey,widthKey,heightKey,renderer,srgb,request){
 const url=trustedStaticURL(source[urlKey],'/static/earth-detail/v018/');
 const response=await fetch(url,{credentials:'same-origin',redirect:'error'});
 if(!response.ok)fail('TEXTURE_FETCH_FAILED');
 const bytes=await response.arrayBuffer();
 if(await digestBytes(bytes)!==source[hashKey])fail('TEXTURE_SOURCE_HASH_MISMATCH');
 // The unchanged renderer CSP permits self/data images, not blob images.
 // Decode exactly the bytes whose hash was verified; never fetch a second copy.
 const array=new Uint8Array(bytes);let binary='';
 for(let i=0;i<array.length;i+=32768)binary+=String.fromCharCode(...array.subarray(i,i+32768));
 const imageURL='data:image/png;base64,'+btoa(binary);
 const texture=await new THREE.TextureLoader().loadAsync(imageURL);
 if(texture.image.width!==source[widthKey]||texture.image.height!==source[heightKey]){texture.dispose();fail('TEXTURE_SOURCE_SIZE_MISMATCH');}
 return configureQualityTexture(texture,renderer.capabilities,request,srgb);
}

function replaceOnce(shader,original,replacement,rule){
 if(shader.split(original).length!==2)fail(`SHADER_CONTRACT_${rule}`);
 return shader.replace(original,replacement);
}

/** The legacy shader stays byte-identical on disk and at wide weight zero. */
export function qualitySurfaceShader(shader,count){
 if(!Number.isInteger(count)||count<1||count>4)fail('SHADER_TILE_COUNT_INVALID');
 const uniforms=Array.from({length:count},(_,index)=>`uniform sampler2D uVQDetail${index},uVQMask${index};uniform vec4 uVQBounds${index};`).join('\n');
 const samples=Array.from({length:count},(_,index)=>`
  {
   vec4 bounds=uVQBounds${index};vec2 q=(ll-bounds.xy)/(bounds.zw-bounds.xy);
   if(q.x>=0.&&q.x<=1.&&q.y>=0.&&q.y<=1.){
    float edge=min(min(ll.x-bounds.x,bounds.z-ll.x),min(ll.y-bounds.y,bounds.w-ll.y));
    float weight=uVQWeight*uVQMaxBlend*smoothstep(0.,uVQEdgeFeather,edge);
    float mask=clamp(texture2D(uVQMask${index},q).r,0.,1.);
    vec3 detail=texture2D(uVQDetail${index},q).rgb;
    // Preserve the approved ocean palette; only actual land albedo receives
    // the geographically registered higher-resolution RGB source.
    day=mix(day,detail,weight*mask);land=mix(land,mask,weight);
   }
  }`).join('\n');
 const functions=`
uniform float uVQWeight,uVQMaxBlend,uVQEdgeFeather,uVQExposureScale,uVQSpecularScale,uVQCityPower,uVQCityGainScale,uVQCityFocusLimit;
${uniforms}
vec4 visualQualityRegional(vec3 day,vec2 uv){
 float land=smoothstep(.005,.025,max(day.r,day.g)-day.b*.70);
 if(uVQWeight<=0.)return vec4(day,land);
 // No height/normal displacement is inferred from this RGB source.
 vec2 ll=vec2(uv.x*360.-180.,uv.y*180.-90.);
${samples}
 return vec4(day,land);
}
`;
 let result=replaceOnce(shader,'void main(){',functions+'\nvoid main(){','MAIN');
 result=replaceOnce(result,'vec3 day=texture2D(uDay,uv).rgb;','vec3 day=texture2D(uDay,uv).rgb;vec4 vqRegional=visualQualityRegional(day,uv);day=vqRegional.rgb;','DAY');
 // The helper intentionally uses the same original mask expression, so anchor
 // the production replacement to its preceding surface-normal calculation.
 result=replaceOnce(result,'float nd=dot(normal,uSun);float land=smoothstep(.005,.025,max(day.r,day.g)-day.b*.70);','float nd=dot(normal,uSun);float land=vqRegional.a;','LAND');
 result=replaceOnce(result,'city=pow(max(city-.001,0.),.82);','city=pow(max(city-.001,0.),mix(.82,uVQCityPower,uVQWeight));','CITY_POWER');
 result=replaceOnce(result,'float focus=1.+seoul*uFocus.x+tokyo*uFocus.y+singapore*uFocus.z;','float focus=1.+seoul*uFocus.x+tokyo*uFocus.y+singapore*uFocus.z;focus=mix(focus,min(focus,uVQCityFocusLimit),uVQWeight);','CITY_FOCUS');
 result=replaceOnce(result,'*city*dark*focus*.80*uCityGain;','*city*dark*focus*.80*uCityGain*mix(1.,uVQCityGainScale,uVQWeight);','CITY_GAIN');
 result=replaceOnce(result,'vec3(1.,.90,.74)*spec+lights','vec3(1.,.90,.74)*spec*uVQSpecularScale+lights','SPECULAR');
 // Bound the confirmed daytime washout without reducing the night geography
 // fill. The illumination clock, sun, cloud and atmosphere remain unchanged.
 result=replaceOnce(result,')*uExposure,1.);',')*uExposure*mix(1.,uVQExposureScale,smoothstep(-.05,.15,nd)),1.);','EXPOSURE');
 return result;
}

function textureAudit(texture,renderer){
 const image=texture.image,width=image?.width||0,height=image?.height||0;
 return {width,height,source_loaded:width>0&&height>0,gpu_upload_observed:Boolean(renderer.properties.get(texture).__webglTexture),
  expected_gpu_upload_resolution:[width,height],upload_resolution_evidence:'Source dimensions are checked against MAX_TEXTURE_SIZE before upload; dimensions are not a driver-query measurement',
  format:'RGBA_UNSIGNED_BYTE_DECODED_IMAGE',color_space:texture.colorSpace,min_filter:texture.minFilter,mag_filter:texture.magFilter,
  mipmaps:texture.generateMipmaps,anisotropy:texture.anisotropy,
  estimated_texture_storage_bytes:Math.ceil(width*height*4*(texture.generateMipmaps?4/3:1)),storage_evidence:'RGBA plus full mip chain estimate; not measured VRAM'};
}

export class SceneVisualQualityRenderer extends SceneSecondEventRenderer{
 constructor(scene,plan){
  if(scene.visual_quality?.version!==VISUAL_QUALITY_VERSION)fail('EXPLICIT_V018_OPT_IN_REQUIRED');
  super(scene,plan);this.qualityReady=false;
 }
 async init(){
  await super.init();
  if(!sha(this.sceneSpec.visual_quality.profile_sha256)||!sha(this.sceneSpec.visual_quality.manifest_sha256))fail('SOURCE_HASH_REQUIRED');
  const selection=this.sceneSpec.visual_quality,loaded=await fetchJSON(selection.profile_url||'/static/visual_quality_v018.json',selection.profile_sha256);
  this.qualityProfile=validateQualityProfile(loaded.value);this.qualityProfileHash=loaded.sha256;
  const manifest=await fetchJSON(this.qualityProfile.regional_detail.manifest_url,selection.manifest_sha256);
  this.qualityManifest=validateDetailManifest(manifest.value);this.qualityManifestHash=manifest.sha256;
  const request=this.qualityProfile.filtering.anisotropy_request;
  this.qualityTiles=await Promise.all(this.qualityManifest.textures.map(async source=>({source,
   day:await loadVerifiedTexture(source,'url','sha256','width','height',this.gl,true,request),
   mask:await loadVerifiedTexture(source,'mask_url','mask_sha256','mask_width','mask_height',this.gl,false,request)})));
  this.installQualitySurface();this.qualityReady=true;this.frame(0);return this;
 }
 installQualitySurface(){
  const material=this.map.surface,profile=this.qualityProfile,request=profile.filtering.anisotropy_request;
  material.fragmentShader=qualitySurfaceShader(material.fragmentShader,this.qualityTiles.length);
  Object.assign(material.uniforms,{uVQWeight:{value:0},uVQMaxBlend:{value:profile.regional_detail.max_blend},uVQEdgeFeather:{value:profile.regional_detail.edge_feather_degrees},
   uVQExposureScale:{value:1},uVQSpecularScale:{value:1},uVQCityPower:{value:profile.surface.city_power},
   uVQCityGainScale:{value:profile.surface.city_gain_scale},uVQCityFocusLimit:{value:profile.surface.city_focus_limit}});
  for(const [index,tile] of this.qualityTiles.entries())Object.assign(material.uniforms,{[`uVQDetail${index}`]:{value:tile.day},[`uVQMask${index}`]:{value:tile.mask},[`uVQBounds${index}`]:{value:new THREE.Vector4(...tile.source.bounds)}});
  // Match the hardware capability instead of silently requesting unsupported
  // anisotropy. Do not change existing wrap/color-space/filter behavior.
  for(const name of ['uDay','uNight','uTopo','uCloud']){
   const texture=material.uniforms[name].value;
   if(texture.image.width>this.gl.capabilities.maxTextureSize||texture.image.height>this.gl.capabilities.maxTextureSize)fail('TEXTURE_UPLOAD_SIZE_INVALID');
   texture.anisotropy=Math.max(1,Math.min(request,this.gl.capabilities.getMaxAnisotropy()));texture.needsUpdate=true;
  }
  material.needsUpdate=true;
 }
 mapAt(t){
  super.mapAt(t);if(!this.qualityReady)return;
  const weight=qualityWeight(this.camera.position.length()-1,this.qualityProfile),surface=this.qualityProfile.surface,u=this.map.surface.uniforms;
  u.uVQWeight.value=weight;u.uVQExposureScale.value=1+(surface.close_exposure_scale-1)*weight;
  u.uVQSpecularScale.value=1+(surface.ocean_specular_scale-1)*weight;
 }
 audit(t){
  const value=super.audit(t);if(!this.qualityReady)return value;
  const renderer=this.gl,base=Object.fromEntries(['uDay','uNight','uCloud','uTopo'].map(name=>[name,textureAudit(this.map.surface.uniforms[name].value,renderer)]));
  const tiles=this.qualityTiles.map(({source,day,mask})=>({id:source.id,role:source.role,source_sha256:source.sha256,mask_sha256:source.mask_sha256,
   bounds:source.bounds,original_source_resolution:source.source_resolution,day:textureAudit(day,renderer),land_mask:textureAudit(mask,renderer)}));
  value.visualQuality={version:VISUAL_QUALITY_VERSION,profile_sha256:this.qualityProfileHash,manifest_sha256:this.qualityManifestHash,
   material_weight:this.map.surface.uniforms.uVQWeight.value,regional_max_blend:this.qualityProfile.regional_detail.max_blend,
   close_exposure_scale:this.map.surface.uniforms.uVQExposureScale.value,ocean_specular_scale:this.map.surface.uniforms.uVQSpecularScale.value,
   city_power:this.qualityProfile.surface.city_power,city_gain_scale:this.qualityProfile.surface.city_gain_scale,
   source_semantics:'Real regional RGB land-cover/shaded relief and GIS land mask; no DEM or higher-resolution night-light data',
   night_source_limit:'Original 8K night-map bright clusters retain their native footprint; no blur or synthetic lights are used',
   filtering:{requested_anisotropy:this.qualityProfile.filtering.anisotropy_request,supported_anisotropy:renderer.capabilities.getMaxAnisotropy(),max_texture_size:renderer.capabilities.maxTextureSize},
   base_textures:base,regional_textures:tiles,estimated_texture_storage_bytes:Object.values(base).reduce((sum,item)=>sum+item.estimated_texture_storage_bytes,0)+tiles.reduce((sum,item)=>sum+item.day.estimated_texture_storage_bytes+item.land_mask.estimated_texture_storage_bytes,0),
   texture_storage_evidence:'Calculated image/mipmap storage, not measured GPU memory',
   preserved:{camera:true,text:true,routes:true,entities:true,lighting_timing:true,cloud:true,atmosphere:true,normal_map:true,render_resolution:[this.w,this.h]}};
  return value;
 }
}
