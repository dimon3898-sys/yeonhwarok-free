/** Restore only the frozen native Boundary/Glow support after source compositing.
 * Snapshot remains GPU-owned. Its protected corridors intentionally retain the
 * original terrain as well as native boundary pixels; they are not pure ASTRA.
 * The original opaque canvas is RGB8, so an RGBA8 copy is not compatible here.
 */
export const NATIVE_BOUNDARY_RESTORE_VERSION='UNIVERSAL_NATIVE_BOUNDARY_RESTORE_V1';
export const MAX_NATIVE_BOUNDARY_SEGMENTS=8192;
const MAX_PIXELS=1080*1920,MAX_COORDINATE=1e8;
const point=p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isFinite(n)&&Math.abs(n)<=MAX_COORDINATE);
const keyRequired=key=>{
 if(typeof key!=='string'||!/^[a-f0-9]{64}$/.test(key))throw Error('NATIVE_BOUNDARY_IMMUTABLE_KEY_REQUIRED');
 return key;
};

/** Same original support contract as Area V3: finite native radius plus one
 * conservative pixel. This validates/copies data but never edits source edges.
 */
function nativeBoundaryRecords(segments){
 if(!Array.isArray(segments)||segments.length>MAX_NATIVE_BOUNDARY_SEGMENTS)
  throw Error('NATIVE_BOUNDARY_SEGMENT_CAPACITY');
 return segments.map(segment=>{
  const a=Array.isArray(segment)?segment.slice(0,2):segment?.a,
   b=Array.isArray(segment)?segment.slice(2,4):segment?.b,
   radius=Array.isArray(segment)?segment[4]:segment?.radiusPx??segment?.radius_px??segment?.paddingPixels;
  if(!point(a)||!point(b)||!Number.isFinite(radius)||radius<0||radius>64)
   throw Error('NATIVE_BOUNDARY_ACTUAL_FINITE_SUPPORT_REQUIRED');
  return {a:[...a],b:[...b],radius:radius+1};
 });
}
export function compileNativeBoundaryGeometry(segments){
 const records=nativeBoundaryRecords(segments);
 const vertices=new Float32Array(records.length*6*7);
 let cursor=0;
 for(const {a,b,radius}of records){
  const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),
   tx=length?dx/length:1,ty=length?dy/length:0,
   x0=a[0]-tx*radius,y0=a[1]-ty*radius,x1=b[0]+tx*radius,y1=b[1]+ty*radius,
   nx=-ty*radius,ny=tx*radius,
   corners=[[x0+nx,y0+ny],[x1+nx,y1+ny],[x0-nx,y0-ny],[x1-nx,y1-ny]];
  for(const index of [0,1,2,2,1,3]){
   const p=corners[index];vertices.set([p[0],p[1],...a,...b,radius],cursor);cursor+=7;
  }
 }
 return {records,vertices,vertexCount:records.length*6,signature:JSON.stringify(records),
  segmentCount:records.length,vertexBufferBytes:vertices.byteLength};
}

const VERTEX=`#version 300 es
precision highp float;
layout(location=0)in vec2 position;
layout(location=1)in vec4 endpoints;
layout(location=2)in float radius;
uniform vec2 screenSize;flat out vec4 edge;flat out float support;
void main(){edge=endpoints;support=radius;
 gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const FRAGMENT=`#version 300 es
precision highp float;precision highp int;
uniform sampler2D nativeSnapshot;uniform vec2 screenSize;
flat in vec4 edge;flat in float support;out vec4 frag;
void main(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y),ab=edge.zw-edge.xy;
 float distance=length(p-edge.xy-ab*clamp(dot(p-edge.xy,ab)/max(dot(ab,ab),1.e-12),0.,1.));
 if(distance>support)discard;
 // copyTexSubImage2D and gl_FragCoord both use the lower-left GL origin.
 frag=vec4(texelFetch(nativeSnapshot,ivec2(gl_FragCoord.xy),0).rgb,1.);}`;

function programFor(gl){
 const program=gl.createProgram(),shaders=[];
 if(!program)throw Error('NATIVE_BOUNDARY_PROGRAM_ALLOCATION');
 try{
  for(const [type,source]of [[gl.VERTEX_SHADER,VERTEX],[gl.FRAGMENT_SHADER,FRAGMENT]]){
   const shader=gl.createShader(type);if(!shader)throw Error('NATIVE_BOUNDARY_SHADER_ALLOCATION');
   shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('NATIVE_BOUNDARY_SHADER_COMPILE '+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('NATIVE_BOUNDARY_PROGRAM_LINK '+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{for(const shader of shaders)gl.deleteShader(shader);}
}

/** Asynchronous only to reuse the original browser GL-state helpers. Optional
 * stateHelpers exists for focused CPU/mock tests, never as a GPU admission path.
 */
export async function createNativeBoundaryRestore({gl,width=1080,height=1920,stateHelpers=null}={}){
 if(!gl||typeof gl.copyTexSubImage2D!=='function'||typeof gl.texStorage2D!=='function')
  throw Error('NATIVE_BOUNDARY_WEBGL2_REQUIRED');
 if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<1||height<1
  ||width*height>MAX_PIXELS||width!==gl.drawingBufferWidth||height!==gl.drawingBufferHeight)
  throw Error('NATIVE_BOUNDARY_BOUNDED_DRAWING_BUFFER_REQUIRED');
 if(gl.getContextAttributes()?.alpha!==false)throw Error('NATIVE_BOUNDARY_OPAQUE_RGB8_CANVAS_REQUIRED');
 const helpers=stateHelpers??await import('/modules/flow_graphic_pass_v2.mjs'),
  captureState=helpers.captureFlowNativeGlState,restoreState=helpers.restoreFlowNativeGlState;
 if(typeof captureState!=='function'||typeof restoreState!=='function')throw Error('NATIVE_BOUNDARY_STATE_HELPERS_REQUIRED');
 let texture=null,program=null,vao=null,buffer=null,disposed=false,snapshotKey=null,geometry=null,
  captures=0,captureCacheHits=0,geometryUploads=0,restores=0;
 const release=()=>{if(texture)gl.deleteTexture(texture);if(program)gl.deleteProgram(program);
  if(vao)gl.deleteVertexArray(vao);if(buffer)gl.deleteBuffer(buffer);};
 const original=captureState(gl);
 try{
  program=programFor(gl);texture=gl.createTexture();vao=gl.createVertexArray();buffer=gl.createBuffer();
  if(!texture||!vao||!buffer)throw Error('NATIVE_BOUNDARY_RESOURCE_ALLOCATION');
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
  gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGB8,width,height);
  gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  for(const [location,size,offset]of [[0,2,0],[1,4,8],[2,1,24]]){
   gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,size,gl.FLOAT,false,28,offset);gl.vertexAttribDivisor(location,0);
  }
 }catch(error){release();throw error;}finally{restoreState(gl,original);}
 if(gl.getError()!==gl.NO_ERROR){release();throw Error('NATIVE_BOUNDARY_RESOURCE_GL_ERROR');}
 const screenSize=gl.getUniformLocation(program,'screenSize'),snapshotLocation=gl.getUniformLocation(program,'nativeSnapshot');
 const live=()=>{if(disposed)throw Error('NATIVE_BOUNDARY_RESTORE_DISPOSED');
  if(gl.drawingBufferWidth!==width||gl.drawingBufferHeight!==height)throw Error('NATIVE_BOUNDARY_DRAWING_BUFFER_CHANGED');};
 const evidence=()=>({version:NATIVE_BOUNDARY_RESTORE_VERSION,snapshotKey,
  snapshotFormat:'RGB8',snapshotBytes:width*height*3,opaqueAlpha:1,
  segmentCount:geometry?.segmentCount??0,vertexBufferBytes:geometry?.vertexBufferBytes??0,
  captures,captureCacheHits,geometryUploads,restores,cpuImageReadback:false,frameHistoryRetained:false,
  support:'ACTUAL_NATIVE_BOUNDARY_SEGMENTS_RADIUS_PLUS_ONE_PIXEL',
  protectedCorridorMaterial:'ORIGINAL_NATIVE_TERRAIN_AND_BOUNDARY_NOT_PURE_ASTRA',
  actualNvidiaVerified:false});
 return {
  capture({key}={}){
   live();keyRequired(key);
   if(key===snapshotKey){captureCacheHits++;return {...evidence(),cacheHit:true};}
   const state=captureState(gl);snapshotKey=null;geometry=null;
   try{
    gl.disable(gl.DITHER);gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
    gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);
   }finally{restoreState(gl,state);}
   if(gl.getError()!==gl.NO_ERROR)throw Error('NATIVE_BOUNDARY_CAPTURE_GL_ERROR');
   snapshotKey=key;captures++;return {...evidence(),cacheHit:false};
  },
  restore({key,segments}={}){
   live();keyRequired(key);
   if(snapshotKey!==key)throw Error('NATIVE_BOUNDARY_SNAPSHOT_KEY_MISMATCH');
   // Validate the current actual native geometry on every call, but build the
   // vertex array only once per immutable camera/reveal key.
   const signature=JSON.stringify(nativeBoundaryRecords(segments));
   if(geometry&&geometry.signature!==signature)throw Error('NATIVE_BOUNDARY_GEOMETRY_CHANGED_UNDER_IMMUTABLE_KEY');
   const compiled=geometry?null:compileNativeBoundaryGeometry(segments);
   const state=captureState(gl);
   try{
    gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
    if(!geometry){gl.bufferData(gl.ARRAY_BUFFER,compiled.vertices,gl.STATIC_DRAW);
     geometry={signature:compiled.signature,segmentCount:compiled.segmentCount,vertexCount:compiled.vertexCount,
      vertexBufferBytes:compiled.vertexBufferBytes};geometryUploads++;}
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,width,height);
    for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.DITHER,gl.POLYGON_OFFSET_FILL,gl.SAMPLE_ALPHA_TO_COVERAGE,
     gl.SAMPLE_COVERAGE,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD])gl.disable(cap);
    gl.colorMask(true,true,true,true);gl.useProgram(program);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
    gl.uniform1i(snapshotLocation,0);gl.uniform2f(screenSize,width,height);
    if(geometry.vertexCount)gl.drawArrays(gl.TRIANGLES,0,geometry.vertexCount);
   }finally{restoreState(gl,state);}
   if(gl.getError()!==gl.NO_ERROR)throw Error('NATIVE_BOUNDARY_RESTORE_GL_ERROR');
   restores++;return evidence();
  },
  get evidence(){return evidence();},
  dispose(){if(disposed)return;const state=captureState(gl);try{release();}finally{restoreState(gl,state);}
   disposed=true;snapshotKey=null;geometry=null;}
 };
}
