/** Source-only terrain material for an isolated reference-quality study.
 * Original raster bytes and frozen Native GIS/projection remain their owners.
 * This pass never samples a finished map frame, sharpens a raster, invents
 * elevation, or adds noise. It grades real source variation before graphics.
 */
import {captureFlowNativeGlState,restoreFlowNativeGlState} from './flow_graphic_pass_v2.mjs';

export const REFERENCE_TERRAIN_MATERIAL_V2_VERSION='REFERENCE_TERRAIN_MATERIAL_V2';
export const DEFAULT_REFERENCE_TERRAIN_PROFILE=Object.freeze({
 profileName:'NE1_REFERENCE_OLIVE_TEAL_VISUAL_V2',
 landTint:Object.freeze([64/255,72/255,25/255]),seaTint:Object.freeze([31/255,78/255,87/255]),
 landSourceAnchor:.85,seaSourceAnchor:.70,landContrast:1.65,seaContrast:1.15,sourceChromaRetention:.08,
});
const box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const rgb=b=>Array.isArray(b)&&b.length===3&&b.every(v=>Number.isFinite(v)&&v>=0&&v<=1);
const contains=(a,b)=>a[0]<=b[0]&&a[1]<=b[1]&&a[2]>=b[2]&&a[3]>=b[3];
const clone=v=>structuredClone(v);
function profileRecord(input={}){
 const p={...clone(DEFAULT_REFERENCE_TERRAIN_PROFILE),...clone(input)};
 if(typeof p.profileName!=='string'||!p.profileName||!rgb(p.landTint)||!rgb(p.seaTint))
  throw Error('REFERENCE_TERRAIN_PROFILE_COLOR_REQUIRED');
 for(const key of ['landSourceAnchor','seaSourceAnchor'])if(!Number.isFinite(p[key])||p[key]<=0||p[key]>1)
  throw Error('REFERENCE_TERRAIN_SOURCE_ANCHOR_INVALID');
 for(const key of ['landContrast','seaContrast'])if(!Number.isFinite(p[key])||p[key]<.25||p[key]>3)
  throw Error('REFERENCE_TERRAIN_POINTWISE_CONTRAST_INVALID');
 if(!Number.isFinite(p.sourceChromaRetention)||p.sourceChromaRetention<0||p.sourceChromaRetention>1)
  throw Error('REFERENCE_TERRAIN_SOURCE_CHROMA_INVALID');
 return p;
}
const vertex=`#version 300 es
precision highp float;out vec2 vUv;
void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
 vUv=p;gl_Position=vec4(p*2.-1.,0.,1.);}`;
const fragment=`#version 300 es
precision highp float;in vec2 vUv;out vec4 frag;
uniform sampler2D sourceTexture,coverageTexture;
uniform vec4 bounds,sourceBounds;
uniform vec3 landTint,seaTint;
uniform float landSourceAnchor,seaSourceAnchor,landContrast,seaContrast,sourceChromaRetention;
uniform bool rawSource;
void main(){
 vec2 geo=mix(bounds.xy,bounds.zw,vUv),sourceUv=(geo-sourceBounds.xy)/(sourceBounds.zw-sourceBounds.xy);
 vec3 source=texture(sourceTexture,sourceUv).rgb;
 if(rawSource){frag=vec4(source,1.);return;}
 // Display-domain grading, explicitly separate from the frozen Native linear-light material.
 // Texture variation comes exclusively from the registered original raster.
 float y=max(dot(source,vec3(.2126,.7152,.0722)),.001);
 vec3 residual=mix(vec3(1.),clamp(source/y,vec3(.75),vec3(1.25)),sourceChromaRetention);
 vec3 land=landTint*pow(y/landSourceAnchor,landContrast)*residual;
 vec3 sea=seaTint*pow(y/seaSourceAnchor,seaContrast);
 float coverage=clamp(texture(coverageTexture,vUv).r,0.,1.);
 frag=vec4(clamp(mix(sea,land,coverage),0.,1.),1.);
}`;
function createProgram(gl){
 const shaders=[],program=gl.createProgram();
 try{
  for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
   const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('REFERENCE_TERRAIN_SHADER_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))
   throw Error('REFERENCE_TERRAIN_LINK_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{for(const shader of shaders)gl.deleteShader(shader);}
}
const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
 .map(value=>value.toString(16).padStart(2,'0')).join('');

/** coverage is factory.coverage(): Native RGBA8 readPixels, row 0=SOUTH/bottom.
 * bounds are that same actual axisaligned Native camera frame (including any
 * orchestration overscan). Draw this before territory, units, and foreground.
 * A later coherent presentation roll must transform ALL map layers together.
 */
export async function createReferenceTerrainMaterialPass({canvas,source,profile={},width=1080,height=1920}={}){
 if(!canvas||canvas.width!==width||canvas.height!==height||width!==1080||height!==1920)
  throw Error('REFERENCE_TERRAIN_CANONICAL_CANVAS_REQUIRED');
 if(!source||typeof source.url!=='string'||!box(source.bounds)||!/^[a-f0-9]{64}$/.test(source.sha256)
  ||!Array.isArray(source.dimensions)||source.dimensions.length!==2||source.dimensions.some(v=>!Number.isInteger(v)||v<2))
  throw Error('REFERENCE_TERRAIN_VERIFIED_RASTER_DESCRIPTOR_REQUIRED');
 const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('REFERENCE_TERRAIN_WEBGL2_REQUIRED');
 const input=clone(source),p=profileRecord(profile),response=await fetch(input.url);
 if(!response.ok)throw Error('REFERENCE_TERRAIN_SOURCE_HTTP_'+response.status);
 const bytes=await response.arrayBuffer();if(await digest(bytes)!==input.sha256)
  throw Error('REFERENCE_TERRAIN_ORIGINAL_SOURCE_HASH_MISMATCH');
 // ImageBitmap owns the explicit north-up PNG → south-up geographic texture conversion.
 // Browser colour conversion and premultiplication are disabled for original sRGB byte samples.
 const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}),
  {imageOrientation:'flipY',colorSpaceConversion:'none',premultiplyAlpha:'none'});
 if(bitmap.width!==input.dimensions[0]||bitmap.height!==input.dimensions[1]){
  bitmap.close();throw Error('REFERENCE_TERRAIN_ORIGINAL_SOURCE_DIMENSIONS_MISMATCH');
 }
 const state=captureFlowNativeGlState(gl);let program,vao,sourceTexture,coverageTexture,disposed=false;
 const locations={};
 try{
  program=createProgram(gl);vao=gl.createVertexArray();sourceTexture=gl.createTexture();coverageTexture=gl.createTexture();
  gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.pixelStorei(gl.UNPACK_ROW_LENGTH,0);gl.pixelStorei(gl.UNPACK_IMAGE_HEIGHT,0);
  gl.pixelStorei(gl.UNPACK_SKIP_PIXELS,0);gl.pixelStorei(gl.UNPACK_SKIP_ROWS,0);gl.pixelStorei(gl.UNPACK_SKIP_IMAGES,0);
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,sourceTexture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,gl.RGBA,gl.UNSIGNED_BYTE,bitmap);gl.generateMipmap(gl.TEXTURE_2D);
  gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
  for(const key of ['sourceTexture','coverageTexture','bounds','sourceBounds','landTint','seaTint',
   'landSourceAnchor','seaSourceAnchor','landContrast','seaContrast','sourceChromaRetention','rawSource'])
   locations[key]=gl.getUniformLocation(program,key);
 }catch(error){if(program)gl.deleteProgram(program);if(vao)gl.deleteVertexArray(vao);
  if(sourceTexture)gl.deleteTexture(sourceTexture);if(coverageTexture)gl.deleteTexture(coverageTexture);throw error;
 }finally{bitmap.close();restoreFlowNativeGlState(gl,state);}
 if(gl.getError()!==gl.NO_ERROR)throw Error('REFERENCE_TERRAIN_RESOURCE_GL_ERROR');
 const evidence={version:REFERENCE_TERRAIN_MATERIAL_V2_VERSION,source:input,sourceBytes:bytes.byteLength,profile:clone(p),
  actualSourceShaVerified:true,sourceDimensionsUnchanged:true,sourceClassification:'REAL_REGISTERED_BAKED_HILLSHADE_AND_BATHYMETRIC_TEXTURE',
  ownership:'NEW_REFERENCE_STUDY_MATERIAL_ONLY',nativeCoreModified:false,finishedFrameSampling:false,
  syntheticNoise:false,sharpening:false,upscaledDetailClaimed:false,newDem:false,
  coverageSource:'UNCHANGED_NATIVE_FACTORY_COVERAGE_READPIXELS_RGBA8_BOTTOM_LEFT',
  sourceOrientation:'ORIGINAL_NORTH_UP_PNG_EXPLICIT_IMAGEBITMAP_FLIPY_TO_GEOGRAPHIC_UV',
  quality:'DATA_LIMITED_REFERENCE_TEXTURE_FIDELITY',referenceTextureParityClaimed:false};
 return {evidence,
  draw({bounds,coverage,rawSource=false}={}){
   if(disposed)throw Error('REFERENCE_TERRAIN_PASS_DISPOSED');
   if(!box(bounds)||!contains(input.bounds,bounds))throw Error('REFERENCE_TERRAIN_ACTUAL_VIEW_MUST_FIT_ORIGINAL_SOURCE');
   if(!(coverage instanceof Uint8Array)||coverage.byteLength!==width*height*4||typeof rawSource!=='boolean')
    throw Error('REFERENCE_TERRAIN_ACTUAL_NATIVE_COVERAGE_REQUIRED');
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
    gl.uniform3fv(locations.landTint,p.landTint);gl.uniform3fv(locations.seaTint,p.seaTint);
    for(const key of ['landSourceAnchor','seaSourceAnchor','landContrast','seaContrast','sourceChromaRetention'])
     gl.uniform1f(locations[key],p[key]);
    gl.uniform1i(locations.rawSource,rawSource?1:0);gl.drawArrays(gl.TRIANGLES,0,3);
   }finally{restoreFlowNativeGlState(gl,previous);}
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('REFERENCE_TERRAIN_DRAW_GL_ERROR_'+glError);
   return {version:REFERENCE_TERRAIN_MATERIAL_V2_VERSION,bounds:clone(bounds),profileName:p.profileName,rawSource,
    nativeStateRestored:true,glError,sourceSha256:input.sha256,coveragePixels:width*height,
    sourceTexelsPerScreenPixel:[(bounds[2]-bounds[0])/(input.bounds[2]-input.bounds[0])*input.dimensions[0]/width,
     (bounds[3]-bounds[1])/(input.bounds[3]-input.bounds[1])*input.dimensions[1]/height],
    screenPixelsPerSourceTexel:[width*(input.bounds[2]-input.bounds[0])/(bounds[2]-bounds[0])/input.dimensions[0],
     height*(input.bounds[3]-input.bounds[1])/(bounds[3]-bounds[1])/input.dimensions[1]],
    referenceTextureParityClaimed:false};
  },
  dispose(){if(disposed)return;gl.deleteProgram(program);gl.deleteVertexArray(vao);
   gl.deleteTexture(sourceTexture);gl.deleteTexture(coverageTexture);disposed=true;},
 };
}
