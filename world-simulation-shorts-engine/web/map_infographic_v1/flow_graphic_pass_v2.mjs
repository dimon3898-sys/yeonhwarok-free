/** A finite-support Flow overlay on the original native WebGL2 canvas.
 * The original line pass remains the only route rasterizer. This pass owns
 * its GPU resources, preserves the native renderer's actual state, and never
 * clears, resizes, samples, or copies the finished native frame.
 */
import * as THREE from '/three.js';
import {createEventLinePass,validateEventLineFootprint} from './event_line_pass_v1.mjs';

export const FLOW_GRAPHIC_PASS_V2_VERSION='FLOW_GRAPHIC_GPU_PASS_V2';
const MAX_RESERVATIONS=64,MAX_POLYGONS=8,MAX_POINTS=12;
const clone=value=>structuredClone(value);
const finitePoint=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
const validBox=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const inBox=(p,b)=>p[0]>=b[0]&&p[1]>=b[1]&&p[0]<=b[2]&&p[1]<=b[3];
const roiInside=(b,safe)=>b[0]>=safe[0]&&b[1]>=safe[1]&&b[2]<=safe[2]&&b[3]<=safe[3];
const intersects=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];

/** Snapshot actual GL state, rather than another THREE renderer's cache.
 * Texture enumeration only changes the active unit, which is restored before
 * returning. No native vertex-array attributes or framebuffer are changed.
 */
export function captureFlowNativeGlState(gl){
 const get=key=>gl.getParameter(gl[key]);
 if(get('TRANSFORM_FEEDBACK_ACTIVE')&&!get('TRANSFORM_FEEDBACK_PAUSED'))
  throw Error('FLOW_NATIVE_TRANSFORM_FEEDBACK_BUSY');
 const capabilities=['BLEND','CULL_FACE','DEPTH_TEST','DITHER','POLYGON_OFFSET_FILL','SAMPLE_ALPHA_TO_COVERAGE',
  'SAMPLE_COVERAGE','SCISSOR_TEST','STENCIL_TEST','RASTERIZER_DISCARD'];
 const parameters=['CURRENT_PROGRAM','VERTEX_ARRAY_BINDING','ARRAY_BUFFER_BINDING','ELEMENT_ARRAY_BUFFER_BINDING',
  'COPY_READ_BUFFER_BINDING','COPY_WRITE_BUFFER_BINDING','PIXEL_PACK_BUFFER_BINDING','PIXEL_UNPACK_BUFFER_BINDING',
  'UNIFORM_BUFFER_BINDING','TRANSFORM_FEEDBACK_BUFFER_BINDING','TRANSFORM_FEEDBACK_BINDING','RENDERBUFFER_BINDING',
  'DRAW_FRAMEBUFFER_BINDING','READ_FRAMEBUFFER_BINDING','ACTIVE_TEXTURE','VIEWPORT','SCISSOR_BOX','COLOR_WRITEMASK',
  'COLOR_CLEAR_VALUE','DEPTH_WRITEMASK','DEPTH_FUNC','DEPTH_RANGE','DEPTH_CLEAR_VALUE','BLEND_COLOR',
  'BLEND_EQUATION_RGB','BLEND_EQUATION_ALPHA','BLEND_SRC_RGB','BLEND_DST_RGB','BLEND_SRC_ALPHA','BLEND_DST_ALPHA',
  'CULL_FACE_MODE','FRONT_FACE','LINE_WIDTH','POLYGON_OFFSET_FACTOR','POLYGON_OFFSET_UNITS',
  'STENCIL_CLEAR_VALUE','STENCIL_FUNC','STENCIL_REF','STENCIL_VALUE_MASK','STENCIL_WRITEMASK',
  'STENCIL_FAIL','STENCIL_PASS_DEPTH_FAIL','STENCIL_PASS_DEPTH_PASS',
  'STENCIL_BACK_FUNC','STENCIL_BACK_REF','STENCIL_BACK_VALUE_MASK','STENCIL_BACK_WRITEMASK',
  'STENCIL_BACK_FAIL','STENCIL_BACK_PASS_DEPTH_FAIL','STENCIL_BACK_PASS_DEPTH_PASS',
  'SAMPLE_COVERAGE_VALUE','SAMPLE_COVERAGE_INVERT','READ_BUFFER','GENERATE_MIPMAP_HINT','FRAGMENT_SHADER_DERIVATIVE_HINT'];
 const pixelStore=['PACK_ALIGNMENT','PACK_ROW_LENGTH','PACK_SKIP_PIXELS','PACK_SKIP_ROWS',
  'UNPACK_ALIGNMENT','UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT','UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES',
  'UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_COLORSPACE_CONVERSION_WEBGL'];
 const state={parameters:Object.fromEntries(parameters.map(key=>[key,get(key)])),
  capabilities:Object.fromEntries(capabilities.map(key=>[key,gl.isEnabled(gl[key])])),
  pixelStore:Object.fromEntries(pixelStore.map(key=>[key,get(key)])),textures:[],attributes:[],uniformBuffers:[],feedbackBuffers:[],
  drawBuffers:Array.from({length:get('MAX_DRAW_BUFFERS')},(_v,i)=>gl.getParameter(gl.DRAW_BUFFER0+i)),
  drawingBufferColorSpace:gl.drawingBufferColorSpace,unpackColorSpace:gl.unpackColorSpace};
 const textureTargets=[['TEXTURE_2D','TEXTURE_BINDING_2D'],['TEXTURE_CUBE_MAP','TEXTURE_BINDING_CUBE_MAP'],
  ['TEXTURE_3D','TEXTURE_BINDING_3D'],['TEXTURE_2D_ARRAY','TEXTURE_BINDING_2D_ARRAY']];
 try{
  for(let unit=0;unit<get('MAX_COMBINED_TEXTURE_IMAGE_UNITS');unit++){
   gl.activeTexture(gl.TEXTURE0+unit);
   state.textures.push({bindings:textureTargets.map(([target,binding])=>({target:gl[target],texture:get(binding)})),sampler:get('SAMPLER_BINDING')});
  }
 }finally{gl.activeTexture(state.parameters.ACTIVE_TEXTURE);}
 for(let index=0;index<get('MAX_VERTEX_ATTRIBS');index++){
  const attribute={};
  for(const key of ['VERTEX_ATTRIB_ARRAY_ENABLED','VERTEX_ATTRIB_ARRAY_SIZE','VERTEX_ATTRIB_ARRAY_STRIDE',
   'VERTEX_ATTRIB_ARRAY_TYPE','VERTEX_ATTRIB_ARRAY_NORMALIZED','VERTEX_ATTRIB_ARRAY_BUFFER_BINDING',
   'VERTEX_ATTRIB_ARRAY_INTEGER','VERTEX_ATTRIB_ARRAY_DIVISOR','CURRENT_VERTEX_ATTRIB'])
   attribute[key]=gl.getVertexAttrib(index,gl[key]);
  attribute.offset=gl.getVertexAttribOffset(index,gl.VERTEX_ATTRIB_ARRAY_POINTER);
  state.attributes.push(attribute);
 }
 for(let index=0;index<get('MAX_UNIFORM_BUFFER_BINDINGS');index++)state.uniformBuffers.push({
  buffer:gl.getIndexedParameter(gl.UNIFORM_BUFFER_BINDING,index),start:gl.getIndexedParameter(gl.UNIFORM_BUFFER_START,index),
  size:gl.getIndexedParameter(gl.UNIFORM_BUFFER_SIZE,index)});
 for(let index=0;index<get('MAX_TRANSFORM_FEEDBACK_SEPARATE_ATTRIBS');index++)state.feedbackBuffers.push({
  buffer:gl.getIndexedParameter(gl.TRANSFORM_FEEDBACK_BUFFER_BINDING,index),start:gl.getIndexedParameter(gl.TRANSFORM_FEEDBACK_BUFFER_START,index),
  size:gl.getIndexedParameter(gl.TRANSFORM_FEEDBACK_BUFFER_SIZE,index)});
 return state;
}

/** Restore the bindings the original renderer still has in its own cache. */
export function restoreFlowNativeGlState(gl,state){
 const p=state.parameters;
 gl.useProgram(p.CURRENT_PROGRAM);
 gl.bindVertexArray(p.VERTEX_ARRAY_BINDING);
 state.attributes.forEach((a,index)=>{
  if(a.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING){
   gl.bindBuffer(gl.ARRAY_BUFFER,a.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING);
   if(a.VERTEX_ATTRIB_ARRAY_INTEGER)gl.vertexAttribIPointer(index,a.VERTEX_ATTRIB_ARRAY_SIZE,a.VERTEX_ATTRIB_ARRAY_TYPE,a.VERTEX_ATTRIB_ARRAY_STRIDE,a.offset);
   else gl.vertexAttribPointer(index,a.VERTEX_ATTRIB_ARRAY_SIZE,a.VERTEX_ATTRIB_ARRAY_TYPE,a.VERTEX_ATTRIB_ARRAY_NORMALIZED,a.VERTEX_ATTRIB_ARRAY_STRIDE,a.offset);
  }
  if(a.VERTEX_ATTRIB_ARRAY_ENABLED)gl.enableVertexAttribArray(index);else gl.disableVertexAttribArray(index);
  gl.vertexAttribDivisor(index,a.VERTEX_ATTRIB_ARRAY_DIVISOR);
  const value=a.CURRENT_VERTEX_ATTRIB;
  if(value instanceof Int32Array)gl.vertexAttribI4iv(index,value);
  else if(value instanceof Uint32Array)gl.vertexAttribI4uiv(index,value);
  else gl.vertexAttrib4fv(index,value);
 });
 gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,p.ELEMENT_ARRAY_BUFFER_BINDING);
 gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK,p.TRANSFORM_FEEDBACK_BINDING);
 function restoreIndexed(target,index,record){
  if(record.buffer&&record.size>0)gl.bindBufferRange(target,index,record.buffer,record.start,record.size);
  else gl.bindBufferBase(target,index,record.buffer);
 }
 state.uniformBuffers.forEach((record,index)=>restoreIndexed(gl.UNIFORM_BUFFER,index,record));
 state.feedbackBuffers.forEach((record,index)=>restoreIndexed(gl.TRANSFORM_FEEDBACK_BUFFER,index,record));
 for(const [target,binding] of [['ARRAY_BUFFER','ARRAY_BUFFER_BINDING'],['COPY_READ_BUFFER','COPY_READ_BUFFER_BINDING'],
  ['COPY_WRITE_BUFFER','COPY_WRITE_BUFFER_BINDING'],['PIXEL_PACK_BUFFER','PIXEL_PACK_BUFFER_BINDING'],
  ['PIXEL_UNPACK_BUFFER','PIXEL_UNPACK_BUFFER_BINDING'],['UNIFORM_BUFFER','UNIFORM_BUFFER_BINDING'],
  ['TRANSFORM_FEEDBACK_BUFFER','TRANSFORM_FEEDBACK_BUFFER_BINDING']])gl.bindBuffer(gl[target],p[binding]);
 gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,p.DRAW_FRAMEBUFFER_BINDING);
 gl.bindFramebuffer(gl.READ_FRAMEBUFFER,p.READ_FRAMEBUFFER_BINDING);
 gl.drawBuffers(p.DRAW_FRAMEBUFFER_BINDING?state.drawBuffers:[state.drawBuffers[0]]);
 gl.readBuffer(p.READ_BUFFER);
 gl.bindRenderbuffer(gl.RENDERBUFFER,p.RENDERBUFFER_BINDING);
 state.textures.forEach((unit,index)=>{
  gl.activeTexture(gl.TEXTURE0+index);
  unit.bindings.forEach(binding=>gl.bindTexture(binding.target,binding.texture));
  gl.bindSampler(index,unit.sampler);
 });
 gl.activeTexture(p.ACTIVE_TEXTURE);
 for(const [capability,enabled] of Object.entries(state.capabilities)){
  if(enabled)gl.enable(gl[capability]);else gl.disable(gl[capability]);
 }
 gl.viewport(...p.VIEWPORT);gl.scissor(...p.SCISSOR_BOX);
 gl.colorMask(...p.COLOR_WRITEMASK);gl.clearColor(...p.COLOR_CLEAR_VALUE);
 gl.depthMask(p.DEPTH_WRITEMASK);gl.depthFunc(p.DEPTH_FUNC);gl.depthRange(...p.DEPTH_RANGE);gl.clearDepth(p.DEPTH_CLEAR_VALUE);
 gl.blendEquationSeparate(p.BLEND_EQUATION_RGB,p.BLEND_EQUATION_ALPHA);
 gl.blendFuncSeparate(p.BLEND_SRC_RGB,p.BLEND_DST_RGB,p.BLEND_SRC_ALPHA,p.BLEND_DST_ALPHA);gl.blendColor(...p.BLEND_COLOR);
 gl.cullFace(p.CULL_FACE_MODE);gl.frontFace(p.FRONT_FACE);gl.lineWidth(p.LINE_WIDTH);
 gl.polygonOffset(p.POLYGON_OFFSET_FACTOR,p.POLYGON_OFFSET_UNITS);
 gl.clearStencil(p.STENCIL_CLEAR_VALUE);
 gl.stencilFuncSeparate(gl.FRONT,p.STENCIL_FUNC,p.STENCIL_REF,p.STENCIL_VALUE_MASK);
 gl.stencilMaskSeparate(gl.FRONT,p.STENCIL_WRITEMASK);
 gl.stencilOpSeparate(gl.FRONT,p.STENCIL_FAIL,p.STENCIL_PASS_DEPTH_FAIL,p.STENCIL_PASS_DEPTH_PASS);
 gl.stencilFuncSeparate(gl.BACK,p.STENCIL_BACK_FUNC,p.STENCIL_BACK_REF,p.STENCIL_BACK_VALUE_MASK);
 gl.stencilMaskSeparate(gl.BACK,p.STENCIL_BACK_WRITEMASK);
 gl.stencilOpSeparate(gl.BACK,p.STENCIL_BACK_FAIL,p.STENCIL_BACK_PASS_DEPTH_FAIL,p.STENCIL_BACK_PASS_DEPTH_PASS);
 gl.sampleCoverage(p.SAMPLE_COVERAGE_VALUE,p.SAMPLE_COVERAGE_INVERT);
 gl.hint(gl.GENERATE_MIPMAP_HINT,p.GENERATE_MIPMAP_HINT);
 gl.hint(gl.FRAGMENT_SHADER_DERIVATIVE_HINT,p.FRAGMENT_SHADER_DERIVATIVE_HINT);
 for(const [key,value] of Object.entries(state.pixelStore))gl.pixelStorei(gl[key],value);
 if(state.drawingBufferColorSpace!==undefined)gl.drawingBufferColorSpace=state.drawingBufferColorSpace;
 if(state.unpackColorSpace!==undefined)gl.unpackColorSpace=state.unpackColorSpace;
}

const vertexSource=`#version 300 es
precision highp float;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.-1.,0.,1.);}`;
const fragmentSource=`#version 300 es
precision highp float;precision highp int;
out vec4 frag;
uniform float screenHeight;uniform vec4 safeArea;
uniform vec4 reservations[64];uniform int reservationCount;
uniform int mode;uniform vec2 center;uniform float heading;uniform vec2 graphicSize;
uniform vec2 points[96];uniform int pointCounts[8];uniform vec4 polygonColors[8];uniform int polygonCount;
uniform vec4 accent;uniform float pulseRadius,pulseAlpha;
float segmentDistance(vec2 p,vec2 a,vec2 b){vec2 ab=b-a;return length(p-a-ab*clamp(dot(p-a,ab)/max(dot(ab,ab),1.e-8),0.,1.));}
float polygonDistance(vec2 p,int polygon){
 int n=pointCounts[polygon],offset=polygon*12;bool inside=false;float distance=1.e20;
 for(int i=0;i<12;i++){if(i>=n)break;int j=(i+1==n)?0:i+1;
  vec2 a=points[offset+i]*graphicSize,b=points[offset+j]*graphicSize;
  distance=min(distance,segmentDistance(p,a,b));
  if((a.y>p.y)!=(b.y>p.y)){float x=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);if(p.x<x)inside=!inside;}
 }
 return inside?-distance:distance;
}
void main(){
 vec2 p=vec2(gl_FragCoord.x,screenHeight-gl_FragCoord.y);
 if(p.x<safeArea.x||p.y<safeArea.y||p.x>safeArea.z||p.y>safeArea.w)discard;
 for(int i=0;i<64;i++){if(i>=reservationCount)break;vec4 b=reservations[i];
  if(p.x>=b.x&&p.y>=b.y&&p.x<=b.z&&p.y<=b.w)discard;
 }
 vec2 delta=p-center;float c=cos(heading),s=sin(heading);vec2 local=vec2(c*delta.x+s*delta.y,-s*delta.x+c*delta.y);
 vec4 color=vec4(0.);
 if(mode==0){
  for(int i=0;i<8;i++){if(i>=polygonCount)break;
   float alpha=(1.-smoothstep(-.5,.5,polygonDistance(local,i)))*polygonColors[i].a;
   float combined=alpha+color.a*(1.-alpha);
   if(combined>0.)color=vec4((polygonColors[i].rgb*alpha+color.rgb*color.a*(1.-alpha))/combined,combined);
  }
 }else if(mode==1){
  float d=min(segmentDistance(local,vec2(-7.,-6.),vec2(2.,0.)),segmentDistance(local,vec2(2.,0.),vec2(-7.,6.)));
  color=vec4(accent.rgb,(1.-smoothstep(1.,2.,d))*accent.a);
 }else{
  float d=abs(length(delta)-pulseRadius);
  color=vec4(accent.rgb,(1.-smoothstep(.8,1.8,d))*pulseAlpha);
 }
 if(color.a<=0.)discard;frag=color;
}`;

function compileShader(gl,type,source){
 const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
 if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){
  const diagnostic=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw Error('FLOW_GPU_SHADER_'+diagnostic);
 }
 return shader;
}
function createOverlayProgram(gl){
 const shaders=[],program=gl.createProgram();
 try{
  shaders.push(compileShader(gl,gl.VERTEX_SHADER,vertexSource),compileShader(gl,gl.FRAGMENT_SHADER,fragmentSource));
  shaders.forEach(shader=>gl.attachShader(program,shader));gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('FLOW_GPU_LINK_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{shaders.forEach(shader=>gl.deleteShader(shader));}
}
function graphicRecord(intent){
 const input=intent?.object_graphic;
 if(!input||!Number.isFinite(input.width_px)||!Number.isFinite(input.height_px)||input.width_px<24||input.width_px>80
  ||input.height_px<12||input.height_px>80||!Array.isArray(input.polygons)||input.polygons.length<1||input.polygons.length>MAX_POLYGONS)
  throw Error('FLOW_FIXTURE_VECTOR_GRAPHIC_REQUIRED');
 for(const polygon of input.polygons){
  if(!Array.isArray(polygon.points)||polygon.points.length<3||polygon.points.length>MAX_POINTS
   ||!polygon.points.every(point=>finitePoint(point)&&point.every(v=>v>=-.5&&v<=.5))
   ||!Array.isArray(polygon.color)||polygon.color.length!==4||!polygon.color.every(v=>Number.isFinite(v)&&v>=0&&v<=1))
   throw Error('FLOW_FIXTURE_VECTOR_POLYGON_REQUIRED');
 }
 return clone(input);
}
function objectRoi(position,heading,graphic){
 const c=Math.cos(heading),s=Math.sin(heading),points=graphic.polygons.flatMap(polygon=>polygon.points).map(([x,y])=>{
  const px=x*graphic.width_px,py=y*graphic.height_px;return[position[0]+c*px-s*py,position[1]+s*px+c*py];
 });
 return[Math.min(...points.map(p=>p[0]))-1,Math.min(...points.map(p=>p[1]))-1,
  Math.max(...points.map(p=>p[0]))+1,Math.max(...points.map(p=>p[1]))+1];
}
function reservationsRecord(graphics){
 if(!Array.isArray(graphics)||graphics.length>MAX_RESERVATIONS||!graphics.every(item=>
  item&&['MARKER','TEXT','PANEL'].includes(item.kind)&&validBox(item.box)))throw Error('FLOW_TYPED_PROTECTION_REQUIRED');
 return graphics.map(item=>clone(item));
}

/** Existing native pixels are preserved underneath every reserved graphic.
 * Routes keep the original strict Text/Panel collision gate; only the original
 * Marker occlusion is allowed for a route. Objects, chevrons and pulse rings
 * rasterize below all native reservations without moving those reservations.
 */
export function createFlowGraphicPass({canvas,style,width=1080,height=1920}={}){
 if(!canvas||width!==1080||height!==1920||canvas.width!==width||canvas.height!==height)
  throw Error('FLOW_CANONICAL_NATIVE_CANVAS_REQUIRED');
 const gl=canvas.getContext('webgl2');if(!gl)throw Error('FLOW_NATIVE_WEBGL2_REQUIRED');
 const originalState=captureFlowNativeGlState(gl);
 let renderer=null,linePass=null,program=null,vao=null,disposed=false;
 try{
  // Calling setSize/setPixelRatio would reset the approved native framebuffer.
  // The new renderer takes the existing canvas dimensions and owns only its
  // own caches/resources. It is reset before every shared-context render.
  renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});
  renderer.autoClear=false;renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
  linePass=createEventLinePass({renderer,width,height,style});
  program=createOverlayProgram(gl);vao=gl.createVertexArray();
 }catch(error){linePass?.dispose();renderer?.dispose();if(program)gl.deleteProgram(program);if(vao)gl.deleteVertexArray(vao);throw error;}
 finally{restoreFlowNativeGlState(gl,originalState);}
 const uniformNames=['screenHeight','safeArea','reservations[0]','reservationCount','mode','center','heading','graphicSize',
  'points[0]','pointCounts[0]','polygonColors[0]','polygonCount','accent','pulseRadius','pulseAlpha'];
 const uniforms=Object.fromEntries(uniformNames.map(name=>[name,gl.getUniformLocation(program,name)]));
 const evidence={version:FLOW_GRAPHIC_PASS_V2_VERSION,composition:'Fresh native canvas -> unchanged V1 route -> finite-support Flow vector GPU',
  routeEngine:'EVENT_LINE_GPU_PASS_V1',geometryEngine:'GEOGRAPHIC_LINE_REVEAL_V1',nativeRendererSourceUnchanged:true,
  sameWebGL2Context:true,finishedFrameBlit:false,cpuRenderer:false,canvasResize:false,stateRestoration:'COMPLETE_NATIVE_WEBGL2_STATE',
  objectPhysics:false,objectGeometrySource:'FIXTURE_VECTOR_POLYGONS',protectedGraphics:'UNCHANGED_NATIVE_RESERVATIONS',
  maxReservations:MAX_RESERVATIONS,maxPolygons:MAX_POLYGONS,maxPolygonPoints:MAX_POINTS,style:clone(style)};
 function drawOverlay({mode,position,heading,roi,safeArea,reservations,graphic=null,radius=0,alpha=0}){
  if(!validBox(roi)||!roiInside(roi,safeArea))throw Error('FLOW_GRAPHIC_FULL_ROI_OUTSIDE_SAFE_AREA');
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
  gl.useProgram(program);gl.bindVertexArray(vao);gl.viewport(0,0,width,height);
  gl.disable(gl.DEPTH_TEST);gl.disable(gl.STENCIL_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.POLYGON_OFFSET_FILL);
  gl.disable(gl.RASTERIZER_DISCARD);gl.disable(gl.SAMPLE_ALPHA_TO_COVERAGE);gl.disable(gl.SAMPLE_COVERAGE);
  gl.depthMask(false);gl.colorMask(true,true,true,true);gl.enable(gl.BLEND);
  gl.blendEquationSeparate(gl.FUNC_ADD,gl.FUNC_ADD);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
  const left=Math.max(0,Math.floor(roi[0])),top=Math.max(0,Math.floor(roi[1])),right=Math.min(width,Math.ceil(roi[2])),bottom=Math.min(height,Math.ceil(roi[3]));
  gl.enable(gl.SCISSOR_TEST);gl.scissor(left,height-bottom,right-left,bottom-top);
  gl.uniform1f(uniforms.screenHeight,height);gl.uniform4fv(uniforms.safeArea,safeArea);
  const boxes=new Float32Array(MAX_RESERVATIONS*4);reservations.forEach((item,index)=>boxes.set(item.box,index*4));
  gl.uniform4fv(uniforms['reservations[0]'],boxes);gl.uniform1i(uniforms.reservationCount,reservations.length);
  gl.uniform1i(uniforms.mode,mode);gl.uniform2fv(uniforms.center,position);gl.uniform1f(uniforms.heading,heading);
  gl.uniform4fv(uniforms.accent,style.coreColor);gl.uniform1f(uniforms.pulseRadius,radius);gl.uniform1f(uniforms.pulseAlpha,alpha);
  if(graphic){
   const points=new Float32Array(MAX_POLYGONS*MAX_POINTS*2),counts=new Int32Array(MAX_POLYGONS),colors=new Float32Array(MAX_POLYGONS*4);
   graphic.polygons.forEach((polygon,index)=>{
    counts[index]=polygon.points.length;polygon.points.forEach((point,j)=>points.set(point,(index*MAX_POINTS+j)*2));
    colors.set(polygon.color,index*4);
   });
   gl.uniform2fv(uniforms.graphicSize,[graphic.width_px,graphic.height_px]);gl.uniform2fv(uniforms['points[0]'],points);
   gl.uniform1iv(uniforms['pointCounts[0]'],counts);gl.uniform4fv(uniforms['polygonColors[0]'],colors);
   gl.uniform1i(uniforms.polygonCount,graphic.polygons.length);
  }else gl.uniform1i(uniforms.polygonCount,0);
  gl.drawArrays(gl.TRIANGLES,0,3);
  const covering=reservations.filter(item=>intersects(roi,item.box));
  return{drawn:true,roi:clone(roi),position:clone(position),heading,occluded:covering.length>0,
   protectedOverlaps:covering.map(item=>({kind:item.kind,box:clone(item.box)})),nativeProtection:'RASTER_ONLY_UNINTERRUPTED_MOTION'};
 }
 return{evidence,
  draw({primitive,controls,safeArea,protectedGraphics=[],flowIntent}={}){
   if(disposed)throw Error('FLOW_GPU_DISPOSED');
   if(!validBox(safeArea)||!controls||!Number.isFinite(controls.routeFraction)||controls.routeFraction<0||controls.routeFraction>1)
    throw Error('FLOW_GPU_DRAW_CONTRACT_REQUIRED');
   const reservations=reservationsRecord(protectedGraphics),graphic=graphicRecord(flowIntent);
   // Validate the complete immutable route before drawing any new pixels.
   const footprint=validateEventLineFootprint(primitive,{style,safeArea,protectedGraphics:reservations});
   const state=captureFlowNativeGlState(gl);
   let result;
   try{
    renderer.resetState();
    const route=linePass.draw({primitive,visibleFraction:controls.routeFraction,safeArea,protectedGraphics:reservations});
    let directional=null,object=null;const pulses=[];
    if(controls.directionalActive){
     const position=controls.directionalPosition,heading=controls.directionalHeading;
     if(!finitePoint(position)||!Number.isFinite(heading))throw Error('FLOW_DIRECTIONAL_POSITION_REQUIRED');
     const radius=11,roi=[position[0]-radius,position[1]-radius,position[0]+radius,position[1]+radius];
     directional=drawOverlay({mode:1,position,heading,roi,safeArea,reservations});
    }
    if(controls.objectVisible??controls.movingObjectVisible){
     const position=controls.objectPosition,heading=controls.heading??controls.objectHeading;
     if(!finitePoint(position)||!Number.isFinite(heading))throw Error('FLOW_OBJECT_POSITION_REQUIRED');
     object=drawOverlay({mode:0,position,heading,roi:objectRoi(position,heading,graphic),safeArea,reservations,graphic});
     object.graphicDimensions=[graphic.width_px,graphic.height_px];object.objectRole=flowIntent.object_role;
    }
    for(const [endpoint,pulse] of [['DEPARTURE',controls.departurePulse],['ARRIVAL',controls.arrivalPulse]])if(pulse?.active){
     const position=pulse.anchor??pulse.position,radius=pulse.radius,alpha=pulse.alpha;
     if(!finitePoint(position)||!Number.isFinite(radius)||radius<0||radius>64||!Number.isFinite(alpha)||alpha<0||alpha>1)
      throw Error('FLOW_ENDPOINT_PULSE_CONTRACT_REQUIRED');
     const support=radius+2,roi=[position[0]-support,position[1]-support,position[0]+support,position[1]+support];
     pulses.push({...drawOverlay({mode:2,position,heading:0,roi,safeArea,reservations,radius,alpha}),endpoint,radius,alpha,
      repetition:'ONCE_PER_ENDPOINT',progress:pulse.progress});
    }
    result={version:FLOW_GRAPHIC_PASS_V2_VERSION,route,directional,object,pulses,
     rois:[route.drawn?route.roi:null,directional?.roi,object?.roi,...pulses.map(p=>p.roi)].filter(Boolean).map(clone),
     routeFraction:controls.routeFraction,objectFraction:controls.objectFraction,heading:controls.heading??controls.objectHeading,
     routeFullRoi:clone(footprint.fullRoi),renderedCenterWidthPixels:style.width,
     protectedReservations:reservations.map(item=>clone(item)),arcLengthOwnership:'UNCHANGED_V1_CORE',nativeStateRestored:true};
   }finally{restoreFlowNativeGlState(gl,state);}
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Object.assign(Error('FLOW_GPU_GL_ERROR_'+glError),{diagnostic:result});
   return result;
  },
  dispose(){
   if(disposed)return;const state=captureFlowNativeGlState(gl);
   try{linePass.dispose();renderer.dispose();gl.deleteProgram(program);gl.deleteVertexArray(vao);disposed=true;}
   finally{restoreFlowNativeGlState(gl,state);}
  },
 };
}
