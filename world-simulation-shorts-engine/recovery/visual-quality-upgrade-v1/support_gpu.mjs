import {buildSupportDistance,MAX_SUPPORT_PIXELS} from './distance_support.mjs';
export const QUALITY_VERTEX_GLSL=`#version 300 es
precision highp float;out vec2 vUv;
void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));vUv=p;gl_Position=vec4(p*2.-1.,0.,1.);}`;
export function supportMaskFragment(role){
 if(!['terrain','bathymetry','surfaceTexture'].includes(role))throw Error('QUALITY_SOURCE_ROLE_REQUIRED');
 const type=role==='bathymetry'?'isampler2D':'sampler2D';
 const treatment=role==='terrain'?`
 if(any(lessThan(p,ivec2(1)))||any(greaterThanEqual(p,size-ivec2(1)))){frag=vec4(0.,0.,0.,1.);return;}
 float latitude=sourceOrigin.y+(float(p.y)+.5)*sourceStep.y;ok=ok&&cos(radians(latitude))>=.0001;
 ivec2 offsets[5]=ivec2[5](ivec2(0),ivec2(1,0),ivec2(-1,0),ivec2(0,1),ivec2(0,-1));
 for(int i=0;i<5;i++){ivec2 q=p+offsets[i];float value=texelFetch(valuesTexture,q,0).r;
  ok=ok&&texelFetch(validTexture,q,0).r==1u&&!isnan(value)&&!isinf(value);}
 `:role==='bathymetry'?`ok=ok&&texelFetch(valuesTexture,p,0).r<0;`:
 `ok=ok&&texelFetch(valuesTexture,p,0).a>0.;`;
 return `#version 300 es
precision highp float;precision highp int;precision highp usampler2D;precision highp isampler2D;
uniform ${type} valuesTexture;uniform usampler2D validTexture;uniform vec2 sourceOrigin,sourceStep;out vec4 frag;
void main(){ivec2 p=ivec2(gl_FragCoord.xy),size=textureSize(valuesTexture,0);
 bool ok=texelFetch(validTexture,p,0).r==1u;${treatment}
 frag=vec4(ok?1.:0.,0.,0.,1.);}`;
}
export function qualityProgram(gl,fragment){
 const program=gl.createProgram(),shaders=[];if(!program)throw Error('QUALITY_PROGRAM_ALLOCATION');
 try{
  for(const [type,source] of [[gl.VERTEX_SHADER,QUALITY_VERTEX_GLSL],[gl.FRAGMENT_SHADER,fragment]]){
   const shader=gl.createShader(type);if(!shader)throw Error('QUALITY_SHADER_ALLOCATION');shaders.push(shader);
   gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('QUALITY_SHADER_COMPILE_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('QUALITY_PROGRAM_LINK_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}finally{for(const shader of shaders)gl.deleteShader(shader);}
}
export function resetQualityPixels(gl){
 gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
 for(const key of ['UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT',
 'UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES','PACK_ROW_LENGTH','PACK_SKIP_PIXELS','PACK_SKIP_ROWS'])gl.pixelStorei(gl[key],0);
 gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);gl.pixelStorei(gl.PACK_ALIGNMENT,1);
 gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);
}
export function setupQualityTexture(gl,texture,unit){
 gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);
 for(const key of ['TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.NEAREST);
 for(const key of ['TEXTURE_WRAP_S','TEXTURE_WRAP_T'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.CLAMP_TO_EDGE);
}
/** Read only a BOOLEAN support derivation from already verified GPU resources.
 * Values/valid arrays and original texture bytes are never read back/rewritten.
 * This avoids a duplicate data fetch or access to the upload handle's private
 * CPU arrays. The distance field is an artistic material weight, not new GIS. */
export function createSupportDistanceTextures(gl,entries,{capture,restore}={}){
 const before=capture(gl),programs=new Map(),fields=[],textures=[];
 let fbo,maskTexture,vao,failure;
 try{
  fbo=gl.createFramebuffer();maskTexture=gl.createTexture();vao=gl.createVertexArray();
  if(!fbo||!maskTexture||!vao)throw Error('QUALITY_SUPPORT_RESOURCE_ALLOCATION');
  resetQualityPixels(gl);gl.bindVertexArray(vao);gl.colorMask(true,true,true,true);
  for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD,gl.DITHER])gl.disable(cap);
  gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);gl.readBuffer(gl.COLOR_ATTACHMENT0);
  for(const entry of entries){
   const [width,height]=entry.metadata.dimensions;
   if(width*height>MAX_SUPPORT_PIXELS)throw Error('QUALITY_SUPPORT_PIXEL_LIMIT');
   setupQualityTexture(gl,maskTexture,2);
   gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
   gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,maskTexture,0);
   if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('QUALITY_SUPPORT_FBO_INCOMPLETE');
   if(!programs.has(entry.role))programs.set(entry.role,qualityProgram(gl,supportMaskFragment(entry.role)));
   const program=programs.get(entry.role);gl.useProgram(program);gl.viewport(0,0,width,height);
   gl.uniform2fv(gl.getUniformLocation(program,'sourceOrigin'),[entry.metadata.transform[0],entry.metadata.transform[3]]);
   gl.uniform2fv(gl.getUniformLocation(program,'sourceStep'),[entry.metadata.transform[1],entry.metadata.transform[5]]);
   for(const [unit,texture,key] of [[0,entry.values,'valuesTexture'],[1,entry.valid,'validTexture']]){
    gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);
    gl.uniform1i(gl.getUniformLocation(program,key),unit);
   }
   gl.drawArrays(gl.TRIANGLES,0,3);
   const rgba=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,rgba);
   if(gl.getError()!==gl.NO_ERROR)throw Error('QUALITY_SUPPORT_READBACK_GL_ERROR');
   const mask=new Uint8Array(width*height);
   for(let i=0;i<mask.length;i++){
    if(rgba[i*4]!==0&&rgba[i*4]!==255)throw Error('QUALITY_BOOLEAN_READBACK_REQUIRED');
    mask[i]=rgba[i*4]===255?1:0;
   }
   const built=buildSupportDistance(mask,width,height),texture=gl.createTexture();
   if(!texture)throw Error('QUALITY_DISTANCE_TEXTURE_ALLOCATION');textures.push(texture);
   setupQualityTexture(gl,texture,2);
   gl.texImage2D(gl.TEXTURE_2D,0,gl.R32F,width,height,0,gl.RED,gl.FLOAT,built.distances);
   if(gl.getError()!==gl.NO_ERROR)throw Error('QUALITY_DISTANCE_UPLOAD_GL_ERROR');
   fields.push({entry,texture,statistics:{...built.statistics,role:entry.role,id:entry.id,
    bbox:[...entry.metadata.bbox],transform:[...entry.metadata.transform],
    supportDefinition:entry.role==='terrain'?'VALID_FINITE_CENTER_AND_FOUR_DERIVATIVE_NEIGHBOURS_NONPOLAR_NORMAL':
     entry.role==='bathymetry'?'VALID_NEGATIVE_ELEVATION_SEPARATE_FROM_NATIVE_GIS_OCEAN_MASK':'VALID_AND_POSITIVE_ALPHA',
    distanceSampling:'MANUAL_BILINEAR_DERIVED_WEIGHT_ONLY',sourceSampling:'UNCHANGED_NATIVE_TEXEL_FETCH'}});
  }
 }catch(error){failure=error;}
 finally{
  for(const program of programs.values())gl.deleteProgram(program);
  if(fbo)gl.deleteFramebuffer(fbo);if(maskTexture)gl.deleteTexture(maskTexture);if(vao)gl.deleteVertexArray(vao);
  try{restore(gl,before);}catch(error){failure??=error;}
 }
 if(failure){for(const texture of textures)gl.deleteTexture(texture);throw failure;}
 let disposed=false;
 return {fields,dispose(){if(disposed)return;for(const texture of textures)gl.deleteTexture(texture);disposed=true;}};
}
