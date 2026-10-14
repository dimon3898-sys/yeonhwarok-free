/** Isolated, source-backed map material for a visual quality study.
 * The original licensed RGB raster and the Native GIS mask remain unchanged.
 * Baked hillshade contrast is artistic material treatment, never a DEM/height
 * reconstruction. The concept illustration is not sampled or traced here.
 */
import {DEFAULT_REFERENCE_OCEAN_PROFILE_V4,buildReferenceOceanGlslV4} from './reference_ocean_material_v4.mjs';

export const REFERENCE_TERRAIN_MATERIAL_V4_VERSION='REFERENCE_TERRAIN_MATERIAL_V4';
export const DEFAULT_REFERENCE_TERRAIN_PROFILE_V4=Object.freeze({
 profileName:'NE1_SOURCE_COLOR_RESTRAINED_WARM_RELIEF_VISUAL_V4',
 landTint:Object.freeze([54/255,65/255,38/255]),landSourceAnchor:.80,landContrast:1.80,
 sourceChromaRetention:.78,bakedShadeLocalContrast:.55,
 warmHighlightColor:Object.freeze([1,.72,.32]),warmHighlightStrength:.15,
 oceanProfile:DEFAULT_REFERENCE_OCEAN_PROFILE_V4,
});
const box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const rgb=b=>Array.isArray(b)&&b.length===3&&b.every(v=>Number.isFinite(v)&&v>=0&&v<=1);
const contains=(a,b)=>a[0]<=b[0]&&a[1]<=b[1]&&a[2]>=b[2]&&a[3]>=b[3];
const clone=v=>structuredClone(v);
export function validateReferenceTerrainProfileV4(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('REFERENCE_TERRAIN_V4_PROFILE_OBJECT_REQUIRED');
 const allowed=new Set(Object.keys(DEFAULT_REFERENCE_TERRAIN_PROFILE_V4));
 for(const key of Object.keys(input))if(!allowed.has(key))throw Error('REFERENCE_TERRAIN_V4_UNKNOWN_PROFILE_FIELD_'+key);
 const p={...clone(DEFAULT_REFERENCE_TERRAIN_PROFILE_V4),...clone(input)};
 if(typeof p.profileName!=='string'||!p.profileName||!rgb(p.landTint)||!rgb(p.warmHighlightColor))
  throw Error('REFERENCE_TERRAIN_V4_PROFILE_COLOR_REQUIRED');
 for(const [key,min,max] of [['landSourceAnchor',.25,1],['landContrast',.25,3],
  ['sourceChromaRetention',0,1],['bakedShadeLocalContrast',0,2],['warmHighlightStrength',0,.3]])
  if(!Number.isFinite(p[key])||p[key]<min||p[key]>max)throw Error('REFERENCE_TERRAIN_V4_PROFILE_RANGE_'+key);
 // Ocean builder validates every embedded profile value before compiling GLSL.
 buildReferenceOceanGlslV4(p.oceanProfile);
 return p;
}
const vertex=`#version 300 es
precision highp float;out vec2 vUv;
void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
 vUv=p;gl_Position=vec4(p*2.-1.,0.,1.);}`;
function fragment(profile){return `#version 300 es
precision highp float;in vec2 vUv;out vec4 frag;
uniform sampler2D sourceTexture,coverageTexture;
uniform vec4 bounds,sourceBounds;
uniform vec2 sourceDimensions,screenDimensions;
uniform vec3 landTint,warmHighlightColor;
uniform float landSourceAnchor,landContrast,sourceChromaRetention,bakedShadeLocalContrast,warmHighlightStrength,frameTimeSec;
uniform bool rawSource;
${buildReferenceOceanGlslV4(profile.oceanProfile)}
float sourceY(vec2 uv){return max(dot(texture(sourceTexture,uv).rgb,vec3(.2126,.7152,.0722)),.001);}
float coastNeighbourAverage(float radiusPixels){
 vec2 stepUv=vec2(radiusPixels)/screenDimensions;
 return .25*(texture(coverageTexture,vUv+vec2(stepUv.x,0.)).r+
  texture(coverageTexture,vUv-vec2(stepUv.x,0.)).r+
  texture(coverageTexture,vUv+vec2(0.,stepUv.y)).r+
  texture(coverageTexture,vUv-vec2(0.,stepUv.y)).r);
}
void main(){
 vec2 geo=mix(bounds.xy,bounds.zw,vUv),sourceUv=(geo-sourceBounds.xy)/(sourceBounds.zw-sourceBounds.xy);
 vec3 source=texture(sourceTexture,sourceUv).rgb;
 if(rawSource){frag=vec4(source,1.);return;}
 float y=max(dot(source,vec3(.2126,.7152,.0722)),.001);
 vec2 nativeTexel=1./sourceDimensions;
 float north=sourceY(sourceUv+vec2(0.,nativeTexel.y)),south=sourceY(sourceUv-vec2(0.,nativeTexel.y)),
  east=sourceY(sourceUv+vec2(nativeTexel.x,0.)),west=sourceY(sourceUv-vec2(nativeTexel.x,0.));
 // Local tone separation samples actual baked shade; it does not infer height,
 // generate new ridges or add independent geographic texture.
 float localBase=(4.*y+north+south+east+west)/8.;
 float bakedShade=pow(clamp(y/max(localBase,.001),.90,1.10),bakedShadeLocalContrast);
 vec3 residual=mix(vec3(1.),clamp(source/y,vec3(.65),vec3(1.35)),sourceChromaRetention);
 vec3 land=landTint*pow(y/landSourceAnchor,landContrast)*bakedShade*residual;
 // Warm light is restricted to already-bright, locally varying land features.
 // No global contour/coast outline and no new physical surface-normal claim.
 float actualLandColour=smoothstep(-.025,.035,min(source.r-source.b,source.g-source.b));
 float feature=smoothstep(.005,.040,length(vec2(east-west,north-south)));
 float brightFace=smoothstep(.0015,.020,max(y-localBase,0.));
 float warm=warmHighlightStrength*feature*brightFace*actualLandColour;
 land+=warmHighlightColor*warm;
 float coverage=clamp(texture(coverageTexture,vUv).r,0.,1.);
 // A subtle transition comes from the unchanged actual GIS land mask. It is
 // a proximity style, not measured depth, and never expands the shoreline.
 // Weighted neighbourhood averages replace max/dilation support: a distant
 // land tap cannot turn a complete 10px sea strip into the same bright teal.
 // This modifies only sea colour; the original coverage silhouette still
 // exclusively selects land versus sea in the final mix below.
 float coastalProximity=.55*coastNeighbourAverage(2.)+
  .30*coastNeighbourAverage(6.)+.15*coastNeighbourAverage(12.);
 vec3 sea=worldEngineOceanMaterial(geo,source,coastalProximity,frameTimeSec);
 frag=vec4(clamp(mix(sea,land,coverage),0.,.94),1.);
}`;}
function createProgram(gl,profile){
 const shaders=[],program=gl.createProgram();
 try{
  for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment(profile)]]){
   const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('REFERENCE_TERRAIN_V4_SHADER_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))
   throw Error('REFERENCE_TERRAIN_V4_LINK_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{for(const shader of shaders)gl.deleteShader(shader);}
}
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
 .map(value=>value.toString(16).padStart(2,'0')).join('');

/** Native coverage is RGBA8 readPixels row0=SOUTH. Source PNG is north-up.
 * outputTexture is an owned RGB8 snapshot of THIS material's actual default
 * framebuffer, valid after draw(). It is not a reference-movie texture. A later
 * coherent presentation must transform map/terrain/control together.
 */
export async function createReferenceTerrainMaterialPassV4({canvas,source,profile={},width=1080,height=1920}={}){
 // Profiles stay pure/importable for the Node fixture builder. Native THREE
 // resources are needed only when an actual browser material is constructed.
 const {captureFlowNativeGlState,restoreFlowNativeGlState}=await import('./flow_graphic_pass_v2.mjs');
 if(!canvas||canvas.width!==width||canvas.height!==height||width!==1080||height!==1920)
  throw Error('REFERENCE_TERRAIN_V4_CANONICAL_CANVAS_REQUIRED');
 if(!source||typeof source.url!=='string'||!box(source.bounds)||!/^[a-f0-9]{64}$/.test(source.sha256)
  ||!Array.isArray(source.dimensions)||source.dimensions.length!==2||source.dimensions.some(v=>!Number.isInteger(v)||v<2))
  throw Error('REFERENCE_TERRAIN_V4_VERIFIED_RASTER_DESCRIPTOR_REQUIRED');
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('REFERENCE_TERRAIN_V4_WEBGL2_REQUIRED');
 const input=clone(source),p=validateReferenceTerrainProfileV4(profile),response=await fetch(input.url);
 if(!response.ok)throw Error('REFERENCE_TERRAIN_V4_SOURCE_HTTP_'+response.status);
 const bytes=await response.arrayBuffer();if(await digest(bytes)!==input.sha256)
  throw Error('REFERENCE_TERRAIN_V4_ORIGINAL_SOURCE_HASH_MISMATCH');
 const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}),
  {imageOrientation:'flipY',colorSpaceConversion:'none',premultiplyAlpha:'none'});
 if(bitmap.width!==input.dimensions[0]||bitmap.height!==input.dimensions[1]){
  bitmap.close();throw Error('REFERENCE_TERRAIN_V4_ORIGINAL_SOURCE_DIMENSIONS_MISMATCH');
 }
 const state=captureFlowNativeGlState(gl);let program,vao,sourceTexture,coverageTexture,snapshotTexture,disposed=false,last=null;
 const locations={};
 try{
  program=createProgram(gl,p);vao=gl.createVertexArray();sourceTexture=gl.createTexture();coverageTexture=gl.createTexture();snapshotTexture=gl.createTexture();
  gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.pixelStorei(gl.UNPACK_ROW_LENGTH,0);gl.pixelStorei(gl.UNPACK_IMAGE_HEIGHT,0);
  gl.pixelStorei(gl.UNPACK_SKIP_PIXELS,0);gl.pixelStorei(gl.UNPACK_SKIP_ROWS,0);gl.pixelStorei(gl.UNPACK_SKIP_IMAGES,0);
  for(const [unit,texture] of [[gl.TEXTURE0,sourceTexture],[gl.TEXTURE1,coverageTexture],[gl.TEXTURE2,snapshotTexture]]){
   gl.activeTexture(unit);gl.bindTexture(gl.TEXTURE_2D,texture);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  }
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,sourceTexture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,gl.RGBA,gl.UNSIGNED_BYTE,bitmap);gl.generateMipmap(gl.TEXTURE_2D);
  gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
  // The canvas is alpha:false / RGB8. Exact RGB format compatibility is
  // required for copyTexSubImage2D; RGBA8 caused the previous GL1282 failure.
  gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGB8,width,height);
  for(const key of ['sourceTexture','coverageTexture','bounds','sourceBounds','sourceDimensions','screenDimensions','landTint',
   'warmHighlightColor','landSourceAnchor','landContrast','sourceChromaRetention','bakedShadeLocalContrast','warmHighlightStrength','frameTimeSec','rawSource'])
   locations[key]=gl.getUniformLocation(program,key);
 }catch(error){if(program)gl.deleteProgram(program);if(vao)gl.deleteVertexArray(vao);
  for(const texture of [sourceTexture,coverageTexture,snapshotTexture])if(texture)gl.deleteTexture(texture);throw error;
 }finally{bitmap.close();restoreFlowNativeGlState(gl,state);}
 const resourceError=gl.getError();
 if(resourceError!==gl.NO_ERROR){
  // This failure happens after state restoration. Construction rejects before
  // the caller owns the pass, so it must release every created object here.
  if(program)gl.deleteProgram(program);if(vao)gl.deleteVertexArray(vao);
  for(const texture of [sourceTexture,coverageTexture,snapshotTexture])if(texture)gl.deleteTexture(texture);
  throw Error('REFERENCE_TERRAIN_V4_RESOURCE_GL_ERROR_'+resourceError);
 }
 const evidence={version:REFERENCE_TERRAIN_MATERIAL_V4_VERSION,source:input,sourceBytes:bytes.byteLength,profile:clone(p),
  actualSourceShaVerified:true,sourceDimensionsUnchanged:true,sourceClassification:'LICENSED_REGISTERED_BAKED_RELIEF_AND_WATER_RGB',
  ownership:'NEW_VISUAL_STUDY_MATERIAL_ONLY',nativeCoreModified:false,referenceMovieSampling:false,
  syntheticLandDetail:false,newElevation:false,heightFromColor:false,physicalNormalsClaimed:false,sourceShadeLocalToneTreatment:true,
  warmLight:'RESTRAINED_ACTUAL_BAKED_BRIGHT_FEATURE_TINT_NOT_UNIFORM_CONTOUR_GLOW',
  coverageSource:'UNCHANGED_NATIVE_FACTORY_COVERAGE_RGBA8_BOTTOM_LEFT',snapshotFormat:'RGB8_ACTUAL_MATERIAL_DEFAULT_FRAMEBUFFER_COPY',
  sourceOrientation:'NORTH_UP_ORIGINAL_PNG_EXPLICIT_IMAGEBITMAP_FLIPY',
  quality:'DATA_LIMITED_NO_KOREA_DEM_OR_SATELLITE_SCALE_TEXTURE',referenceEquivalentClaimed:false,
  treatment:'SOURCE_CHROMA_PRESERVATION_REDUCED_LOCAL_EMBOSS_AND_RESTRAINED_WARM_FACES',
  physicalElevationLightingAvailableInNativeCore:true,physicalElevationLightingUsed:false};
 return {evidence,get outputTexture(){if(disposed)throw Error('REFERENCE_TERRAIN_V4_DISPOSED');return snapshotTexture;},
  get snapshotFrame(){return clone(last);},
  draw({bounds,coverage,frame=0,fps=30,rawSource=false}={}){
   if(disposed)throw Error('REFERENCE_TERRAIN_V4_DISPOSED');
   if(!box(bounds)||!contains(input.bounds,bounds))throw Error('REFERENCE_TERRAIN_V4_VIEW_OUTSIDE_SOURCE');
   if(!(coverage instanceof Uint8Array)||coverage.byteLength!==width*height*4||typeof rawSource!=='boolean'
    ||!Number.isInteger(frame)||frame<0||!Number.isFinite(fps)||fps<=0)
    throw Error('REFERENCE_TERRAIN_V4_ACTUAL_COVERAGE_FRAME_REQUIRED');
   const previous=captureFlowNativeGlState(gl);
   try{
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,width,height);
    for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD])gl.disable(cap);
    gl.colorMask(true,true,true,true);gl.useProgram(program);gl.bindVertexArray(vao);
    gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.pixelStorei(gl.UNPACK_ROW_LENGTH,0);gl.pixelStorei(gl.UNPACK_IMAGE_HEIGHT,0);
    gl.pixelStorei(gl.UNPACK_SKIP_PIXELS,0);gl.pixelStorei(gl.UNPACK_SKIP_ROWS,0);gl.pixelStorei(gl.UNPACK_SKIP_IMAGES,0);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,sourceTexture);gl.bindSampler(0,null);
    gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);gl.bindSampler(1,null);
    gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,coverage);
    gl.uniform1i(locations.sourceTexture,0);gl.uniform1i(locations.coverageTexture,1);
    gl.uniform4fv(locations.bounds,bounds);gl.uniform4fv(locations.sourceBounds,input.bounds);
    gl.uniform2fv(locations.sourceDimensions,input.dimensions);gl.uniform2f(locations.screenDimensions,width,height);
    gl.uniform3fv(locations.landTint,p.landTint);gl.uniform3fv(locations.warmHighlightColor,p.warmHighlightColor);
    for(const key of ['landSourceAnchor','landContrast','sourceChromaRetention','bakedShadeLocalContrast','warmHighlightStrength'])
     gl.uniform1f(locations[key],p[key]);
    gl.uniform1f(locations.frameTimeSec,frame/fps);gl.uniform1i(locations.rawSource,rawSource?1:0);gl.drawArrays(gl.TRIANGLES,0,3);
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);
    gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);gl.bindSampler(2,null);
    gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);
   }finally{restoreFlowNativeGlState(gl,previous);}
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('REFERENCE_TERRAIN_V4_DRAW_GL_ERROR_'+glError);
   last={version:REFERENCE_TERRAIN_MATERIAL_V4_VERSION,bounds:clone(bounds),frame,fps,frameTimeSec:frame/fps,
    profileName:p.profileName,rawSource,nativeStateRestored:true,glError,sourceSha256:input.sha256,
    snapshotFormat:'RGB8',snapshotOrientation:'BOTTOM_LEFT_FRAMEBUFFER',actualMaterialSnapshot:true,
    sourceTexelsPerScreenPixel:[(bounds[2]-bounds[0])/(input.bounds[2]-input.bounds[0])*input.dimensions[0]/width,
     (bounds[3]-bounds[1])/(input.bounds[3]-input.bounds[1])*input.dimensions[1]/height],
    newElevation:false,referenceEquivalentClaimed:false};
   return clone(last);
  },
  dispose(){if(disposed)return;gl.deleteProgram(program);gl.deleteVertexArray(vao);
   for(const texture of [sourceTexture,coverageTexture,snapshotTexture])gl.deleteTexture(texture);disposed=true;},
 };
}

// Name alias for orchestration; one implementation and one owned material pass.
export const createMapTerrainMaterialPassV4=createReferenceTerrainMaterialPassV4;
