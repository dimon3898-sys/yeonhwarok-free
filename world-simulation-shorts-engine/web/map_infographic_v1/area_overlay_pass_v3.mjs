/** Polygon/contour presentation over a fresh, unchanged native WebGL2 frame.
 * Native country Boundary/Glow is protected by a geometry-generated, owned GPU
 * mask. No finished image is sampled, copied, resized, cleared, or replaced.
 */
import {polygons,triangulateRegion} from './renderer.mjs';
import {captureFlowNativeGlState,restoreFlowNativeGlState} from './flow_graphic_pass_v2.mjs';
import {evaluateGeographicLineReveal} from './event_line_v1.mjs';
import {selectAreaStyle} from './area_style_v3.mjs';

export const AREA_OVERLAY_PASS_V3_VERSION='AREA_OVERLAY_GPU_PASS_V3';
const MAX_RESERVATIONS=64,MAX_SEGMENTS=128,MAX_TRIANGLES=16384;
const clone=value=>structuredClone(value);
const finitePoint=point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite);
const validBox=box=>Array.isArray(box)&&box.length===4&&box.every(Number.isFinite)&&box[0]<box[2]&&box[1]<box[3];
const unit=value=>Number.isFinite(value)&&value>=0&&value<=1;
const bounds=(points,padding=0)=>[Math.min(...points.map(p=>p[0]))-padding,Math.min(...points.map(p=>p[1]))-padding,
 Math.max(...points.map(p=>p[0]))+padding,Math.max(...points.map(p=>p[1]))+padding];
const intersect=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
const shaderVertex=`#version 300 es
precision highp float;
layout(location=0) in vec2 position;uniform vec2 screenSize;
void main(){gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const maskVertex=`#version 300 es
precision highp float;
layout(location=0) in vec2 position;layout(location=1) in vec4 endpoints;layout(location=2) in float radius;
uniform vec2 screenSize;flat out vec4 edge;flat out float support;
void main(){edge=endpoints;support=radius;gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const distanceFunction=`float segmentDistance(vec2 p,vec2 a,vec2 b){vec2 ab=b-a;return length(p-a-ab*clamp(dot(p-a,ab)/max(dot(ab,ab),1.e-12),0.,1.));}`;
const maskFragment=`#version 300 es
precision highp float;uniform vec2 screenSize;flat in vec4 edge;flat in float support;out vec4 frag;
${distanceFunction}
void main(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);if(segmentDistance(p,edge.xy,edge.zw)>support)discard;frag=vec4(1.,0.,0.,1.);}`;
const protection=`uniform vec2 screenSize;uniform vec4 safeArea;
uniform vec4 reservations[64];uniform int reservationCount;uniform sampler2D boundaryMask;
uniform vec2 coverageOrigin;uniform float coverageRadius;uniform bool coverageLimited;
bool hidden(vec2 p){
 if(p.x<safeArea.x||p.y<safeArea.y||p.x>safeArea.z||p.y>safeArea.w)return true;
 for(int i=0;i<64;i++){if(i>=reservationCount)break;vec4 b=reservations[i];
  if(p.x>=b.x&&p.y>=b.y&&p.x<=b.z&&p.y<=b.w)return true;}
 if(texture(boundaryMask,gl_FragCoord.xy/screenSize).r>.5)return true;
 if(coverageLimited&&length(p-coverageOrigin)>coverageRadius+.5)return true;
 return false;
}`;
const fillFragment=`#version 300 es
precision highp float;out vec4 frag;${protection}
uniform vec4 fillColor,coreColor;uniform float width;
void main(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);if(hidden(p))discard;
 float edge=0.;if(coverageLimited)edge=(1.-smoothstep(width*.5,width*.5+1.,abs(length(p-coverageOrigin)-coverageRadius)))*coreColor.a;
 float alpha=edge+fillColor.a*(1.-edge);if(alpha<=0.)discard;
 frag=vec4(mix(fillColor.rgb,coreColor.rgb,edge/max(alpha,1.e-12)),alpha);
}`;
const contourFragment=`#version 300 es
precision highp float;precision highp int;out vec4 frag;${protection}
uniform vec4 segments[128];uniform int segmentCount;uniform float radius,halo,gain;
uniform vec4 coreColor,glowColor;${distanceFunction}
void main(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);if(hidden(p))discard;
 float d=1.e20;for(int i=0;i<128;i++){if(i>=segmentCount)break;d=min(d,segmentDistance(p,segments[i].xy,segments[i].zw));}
 float core=(1.-smoothstep(max(0.,radius-.5),radius+.5,d))*coreColor.a;
 float glow=(1.-smoothstep(radius,radius+halo,d))*gain*glowColor.a;
 float alpha=core+glow*(1.-core);if(alpha<=0.)discard;
 frag=vec4(mix(glowColor.rgb,coreColor.rgb,core/max(alpha,1.e-12)),alpha);
}`;

function compileProgram(gl,vertex,fragment){
 const shaders=[],program=gl.createProgram();
 try{
  for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
   const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('AREA_GPU_SHADER_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('AREA_GPU_LINK_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{shaders.forEach(shader=>gl.deleteShader(shader));}
}
function uniformLocations(gl,program,names){return Object.fromEntries(names.map(name=>[name,gl.getUniformLocation(program,name)]));}
function protectedRecords(input){
 if(!Array.isArray(input)||input.length>MAX_RESERVATIONS)throw Error('AREA_NATIVE_RESERVATION_CAPACITY');
 return input.map(item=>{const box=Array.isArray(item)?item:item?.box;if(!validBox(box))throw Error('AREA_NATIVE_RESERVATION_BOX_REQUIRED');
  return{kind:item.kind??'PROTECTED_GRAPHIC',box:[...box]};});
}
function boundaryRecords(input){
 if(!Array.isArray(input)||input.length>8192)throw Error('AREA_BOUNDARY_MASK_CAPACITY');
 return input.map(item=>{
  const a=Array.isArray(item)?item.slice(0,2):item.a,b=Array.isArray(item)?item.slice(2,4):item.b;
  const radius=Array.isArray(item)?item[4]:(item.radiusPx??item.radius_px??item.paddingPixels);
  if(!finitePoint(a)||!finitePoint(b)||!Number.isFinite(radius)||radius<0||radius>64)throw Error('AREA_BOUNDARY_SUPPORT_REQUIRED');
  // Measured bounds include integer edge pixels; fragments sample pixel centres.
  // Keep one additional pixel of conservative support around native coverage.
  return{a:[...a],b:[...b],radius:radius+1};
 });
}
const boxTriangles=box=>[box[0],box[1],box[2],box[1],box[0],box[3],box[0],box[3],box[2],box[1],box[2],box[3]];
function projectedPolygon(geometry,project){
 if(!geometry||!['Polygon','MultiPolygon'].includes(geometry.type))throw Error('AREA_GPU_POLYGON_REQUIRED');
 const record={geometry_type:geometry.type,coordinates:geometry.coordinates};
 const parts=polygons(record);if(parts.length===0)throw Error('AREA_GPU_EMPTY_POLYGON');
 const result=triangulateRegion(record,point=>{
  const projected=project([...point]);if(!finitePoint(projected))throw Error('AREA_NATIVE_PROJECTION_REQUIRED');return projected;
 });
 try{
  const vertices=result.mesh.getAttribute('position'),indices=result.mesh.getIndex();
  if(indices.count/3>MAX_TRIANGLES)throw Error('AREA_GPU_TRIANGLE_CAPACITY');
  const triangles=new Float32Array(indices.count*2);
  for(let index=0;index<indices.count;index++){
   const vertex=indices.getX(index);triangles[index*2]=vertices.getX(vertex);triangles[index*2+1]=vertices.getY(vertex);
  }
  return{triangles,rings:result.rings,parts:parts.length,holes:parts.reduce((count,part)=>count+part.length-1,0)};
 }finally{result.mesh.dispose();}
}

/** All new resources belong to this pass; frozen native scenes are never edited. */
export function createAreaOverlayPass({canvas,width=1080,height=1920,style=null}={}){
 if(!canvas||width!==1080||height!==1920||canvas.width!==width||canvas.height!==height)throw Error('AREA_CANONICAL_NATIVE_CANVAS_REQUIRED');
 const gl=canvas.getContext('webgl2');if(!gl)throw Error('AREA_NATIVE_WEBGL2_REQUIRED');
 const programs={},buffers=[],vaos=[],original=captureFlowNativeGlState(gl);
 let boundaryTexture=null,boundaryFbo=null,disposed=false;
 const names=['screenSize','safeArea','reservations[0]','reservationCount','boundaryMask','coverageOrigin','coverageRadius','coverageLimited',
  'fillColor','coreColor','glowColor','width','radius','halo','gain','segments[0]','segmentCount'];
 let fillUniforms,contourUniforms,maskUniforms,positionBuffer,positionVao,maskBuffer,maskVao;
 try{
  programs.fill=compileProgram(gl,shaderVertex,fillFragment);programs.contour=compileProgram(gl,shaderVertex,contourFragment);
  programs.mask=compileProgram(gl,maskVertex,maskFragment);
  fillUniforms=uniformLocations(gl,programs.fill,names);contourUniforms=uniformLocations(gl,programs.contour,names);
  maskUniforms=uniformLocations(gl,programs.mask,['screenSize']);
  positionBuffer=gl.createBuffer();buffers.push(positionBuffer);positionVao=gl.createVertexArray();vaos.push(positionVao);
  gl.bindVertexArray(positionVao);gl.bindBuffer(gl.ARRAY_BUFFER,positionBuffer);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);
  maskBuffer=gl.createBuffer();buffers.push(maskBuffer);maskVao=gl.createVertexArray();vaos.push(maskVao);
  gl.bindVertexArray(maskVao);gl.bindBuffer(gl.ARRAY_BUFFER,maskBuffer);
  for(const [index,size,offset] of [[0,2,0],[1,4,8],[2,1,24]]){gl.enableVertexAttribArray(index);gl.vertexAttribPointer(index,size,gl.FLOAT,false,28,offset);}
  boundaryTexture=gl.createTexture();gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,boundaryTexture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.R8,width,height);
  boundaryFbo=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,boundaryFbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,boundaryTexture,0);
  if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('AREA_BOUNDARY_MASK_FRAMEBUFFER');
 }catch(error){Object.values(programs).forEach(program=>gl.deleteProgram(program));buffers.forEach(buffer=>gl.deleteBuffer(buffer));
  vaos.forEach(vao=>gl.deleteVertexArray(vao));if(boundaryTexture)gl.deleteTexture(boundaryTexture);if(boundaryFbo)gl.deleteFramebuffer(boundaryFbo);throw error;}
 finally{restoreFlowNativeGlState(gl,original);}
 const evidence={version:AREA_OVERLAY_PASS_V3_VERSION,composition:'FRESH_NATIVE_FRAME_PLUS_EVENT_POLYGON_AND_CONTOUR',
  polygonEngine:'UNCHANGED_RENDERER_POLYGONS_AND_TRIANGULATE_REGION',lineEvaluator:'UNCHANGED_GEOGRAPHIC_LINE_REVEAL_V1',
  boundaryProtection:'GEOMETRY_GENERATED_OWNED_R8_GPU_MASK',protectedGraphics:'ALL_NATIVE_RESERVATIONS_MASKED_NO_AREA_EXCEPTION',
  sameWebGL2Context:true,finishedFrameBlit:false,cpuRenderer:false,canvasResize:false,sourceGeometryMutation:false,
  stateRestoration:'COMPLETE_NATIVE_WEBGL2_STATE',maxReservations:MAX_RESERVATIONS,maxLineSegments:MAX_SEGMENTS,maxTriangles:MAX_TRIANGLES};
 function gpuState(blend){
  gl.viewport(0,0,width,height);gl.disable(gl.DEPTH_TEST);gl.disable(gl.STENCIL_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.POLYGON_OFFSET_FILL);
  gl.disable(gl.RASTERIZER_DISCARD);gl.disable(gl.SAMPLE_ALPHA_TO_COVERAGE);gl.disable(gl.SAMPLE_COVERAGE);gl.disable(gl.DITHER);
  gl.depthMask(false);gl.colorMask(true,true,true,true);
  if(blend){gl.enable(gl.BLEND);gl.blendEquationSeparate(gl.FUNC_ADD,gl.FUNC_ADD);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);}
  else gl.disable(gl.BLEND);
 }
 function scissor(roi,safe){
  const left=Math.max(0,Math.floor(Math.max(roi[0],safe[0]))),right=Math.min(width,Math.ceil(Math.min(roi[2],safe[2]))),
   top=Math.max(0,Math.floor(Math.max(roi[1],safe[1]))),bottom=Math.min(height,Math.ceil(Math.min(roi[3],safe[3])));
  if(left>=right||top>=bottom)return false;gl.enable(gl.SCISSOR_TEST);gl.scissor(left,height-bottom,right-left,bottom-top);return true;
 }
 function boundaryMask(records){
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,boundaryFbo);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);gpuState(false);gl.disable(gl.SCISSOR_TEST);
  // Clear only the pass-owned coverage texture, never the native framebuffer.
  gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
  if(!records.length)return;
  const data=new Float32Array(records.length*6*7);let index=0;
  for(const edge of records){const roi=bounds([edge.a,edge.b],edge.radius+1),triangles=boxTriangles(roi);
   for(let vertex=0;vertex<6;vertex++){data.set([triangles[vertex*2],triangles[vertex*2+1],...edge.a,...edge.b,edge.radius],index);index+=7;}}
  gl.useProgram(programs.mask);gl.bindVertexArray(maskVao);gl.bindBuffer(gl.ARRAY_BUFFER,maskBuffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STREAM_DRAW);
  gl.uniform2fv(maskUniforms.screenSize,[width,height]);gl.drawArrays(gl.TRIANGLES,0,records.length*6);
 }
 function common(uniforms,reservations,safeArea,coverage){
  gl.uniform2fv(uniforms.screenSize,[width,height]);gl.uniform4fv(uniforms.safeArea,safeArea);
  const boxes=new Float32Array(MAX_RESERVATIONS*4);reservations.forEach((item,index)=>boxes.set(
   [item.box[0]-1,item.box[1]-1,item.box[2]+1,item.box[3]+1],index*4));
  gl.uniform4fv(uniforms['reservations[0]'],boxes);gl.uniform1i(uniforms.reservationCount,reservations.length);
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,boundaryTexture);gl.uniform1i(uniforms.boundaryMask,0);
  gl.uniform2fv(uniforms.coverageOrigin,coverage.origin);gl.uniform1f(uniforms.coverageRadius,coverage.radius);
  gl.uniform1i(uniforms.coverageLimited,coverage.limited?1:0);
 }
 function vertices(data){gl.bindVertexArray(positionVao);gl.bindBuffer(gl.ARRAY_BUFFER,positionBuffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STREAM_DRAW);}
 function contour(paths,roleStyle,alpha,coverage,reservations,safeArea){
  const segments=[];for(const path of paths)for(let index=1;index<path.length;index++)segments.push([...path[index-1],...path[index]]);
  if(!segments.length||alpha<=0)return[];
  // Chunking changes only GPU capacity, not source contours or reveal progress.
  const records=[];
  for(let offset=0;offset<segments.length;offset+=MAX_SEGMENTS){
   const chunk=segments.slice(offset,offset+MAX_SEGMENTS),points=chunk.flatMap(segment=>[segment.slice(0,2),segment.slice(2)]),
    padding=roleStyle.width/2+roleStyle.glowRadius+1,roi=bounds(points,padding);
   if(!scissor(roi,safeArea))continue;
   gl.useProgram(programs.contour);vertices(new Float32Array(boxTriangles(roi)));common(contourUniforms,reservations,safeArea,coverage);
   const packed=new Float32Array(MAX_SEGMENTS*4);chunk.forEach((segment,index)=>packed.set(segment,index*4));
   gl.uniform4fv(contourUniforms['segments[0]'],packed);gl.uniform1i(contourUniforms.segmentCount,chunk.length);
   gl.uniform1f(contourUniforms.radius,roleStyle.width/2);gl.uniform1f(contourUniforms.halo,roleStyle.glowRadius);gl.uniform1f(contourUniforms.gain,roleStyle.glowGain*alpha);
   gl.uniform4fv(contourUniforms.coreColor,[...roleStyle.coreColor.slice(0,3),roleStyle.coreColor[3]*alpha]);gl.uniform4fv(contourUniforms.glowColor,roleStyle.glowColor);
   gl.drawArrays(gl.TRIANGLES,0,6);records.push({roi,segments:chunk.length});
  }return records;
 }
 function drawArea(item,roleStyle,project,reservations,safeArea){
  if(!unit(item.alpha)||!unit(item.coverage))throw Error('AREA_GPU_FRAME_ALPHA_COVERAGE_REQUIRED');
  if(item.alpha===0||item.coverage===0)return{id:item.id,drawn:false};
  const geometry=projectedPolygon(item.geometry,project),points=geometry.rings.flat(),
   geographicOrigin=item.coverageOrigin??(item.geometry.type==='Polygon'?item.geometry.coordinates[0][0]:item.geometry.coordinates[0][0][0]),origin=project(geographicOrigin);
  if(!finitePoint(origin))throw Error('AREA_GPU_COVERAGE_ORIGIN_REQUIRED');
  const radius=Math.max(...points.map(point=>Math.hypot(point[0]-origin[0],point[1]-origin[1])))*item.coverage;
  const coverage={origin,radius,limited:item.coverage<1},roi=bounds(points,roleStyle.width/2+roleStyle.glowRadius+1);
  if(!scissor(roi,safeArea))return{id:item.id,drawn:false};
  gl.useProgram(programs.fill);vertices(geometry.triangles);common(fillUniforms,reservations,safeArea,coverage);
  gl.uniform4fv(fillUniforms.fillColor,[...roleStyle.fillColor.slice(0,3),roleStyle.fillColor[3]*item.alpha]);
  gl.uniform4fv(fillUniforms.coreColor,[...roleStyle.coreColor.slice(0,3),roleStyle.coreColor[3]*item.alpha]);gl.uniform1f(fillUniforms.width,roleStyle.width);
  gl.drawArrays(gl.TRIANGLES,0,geometry.triangles.length/2);
  const contours=contour(geometry.rings,roleStyle,item.alpha,coverage,reservations,safeArea);
  return{id:item.id,drawn:true,roi,parts:geometry.parts,holes:geometry.holes,triangles:geometry.triangles.length/6,
   coverage:item.coverage,alpha:item.alpha,coverageOrigin:clone(origin),coverageRadiusPixels:radius,contours,sourcePartsAndHolesPreserved:true};
 }
 function drawLine(item,roleStyle,project,reservations,safeArea){
  if(!unit(item.alpha)||!unit(item.revealFraction??1))throw Error('AREA_GPU_FRONT_CONTROLS_REQUIRED');
  if(item.alpha===0||item.revealFraction===0)return{id:item.id,drawn:false};
  if(!item.linePrimitive)throw Error('AREA_GPU_EXISTING_V1_LINE_PRIMITIVE_REQUIRED');
  const reveal=evaluateGeographicLineReveal(item.linePrimitive,item.revealFraction??1);
  const current=item.geometry.coordinates.map(point=>project([...point]));if(item.linePrimitive.direction==='REVERSE')current.reverse();
  if(JSON.stringify(current)!==JSON.stringify(item.linePrimitive.screenCoordinates))throw Error('AREA_GPU_STALE_PROJECTED_FRONT');
  const records=contour([reveal.path],roleStyle,item.alpha,{origin:[0,0],radius:0,limited:false},reservations,safeArea);
  return{id:item.id,drawn:records.length>0,reveal,contours:records,roi:records.length?bounds(records.flatMap(record=>[[record.roi[0],record.roi[1]],[record.roi[2],record.roi[3]]])):null,
   evaluator:'UNCHANGED_GEOGRAPHIC_LINE_REVEAL_V1'};
 }
 return{evidence,draw({controls,project,safeArea,protectedGraphics=[],primaryMaterialColor,backgroundSamples,boundarySegments=[]}={}){
  if(disposed)throw Error('AREA_GPU_DISPOSED');
  if(!controls||typeof project!=='function'||!validBox(safeArea))throw Error('AREA_GPU_DRAW_CONTRACT_REQUIRED');
  const reservations=protectedRecords(protectedGraphics),boundaries=boundaryRecords(boundarySegments),
   styles=style??selectAreaStyle({primaryMaterialColor,backgroundSamples}),state=captureFlowNativeGlState(gl);
  let result;
  try{
   boundaryMask(boundaries);gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gpuState(true);
   const areas=(controls.areas??[]).map(item=>drawArea(item,styles.AREA,project,reservations,safeArea));
   const propagations=(controls.propagations??[]).map(item=>drawLine(item,styles.PROPAGATION,project,reservations,safeArea));
   const impacts=(controls.impacts??[]).map(item=>drawArea(item,styles.IMPACT,project,reservations,safeArea));
   const fronts=(controls.fronts??[]).map(item=>drawLine(item,styles.FRONT,project,reservations,safeArea));
   const items=[...areas,...propagations,...impacts,...fronts];
   result={version:AREA_OVERLAY_PASS_V3_VERSION,areas,propagations,impacts,fronts,rois:items.filter(item=>item.drawn&&item.roi).map(item=>clone(item.roi)),
    style:clone(styles),safeArea:clone(safeArea),protectedReservations:clone(reservations),boundaryMaskSegments:boundaries.length,
    nativeBoundaryGlowPreserved:true,nativeStateRestored:true,sourceGeometryMutation:false,
    reservedOverlap:items.filter(item=>item.drawn&&item.roi).flatMap(item=>reservations.filter(reservation=>intersect(item.roi,reservation.box)).map(reservation=>({id:item.id,kind:reservation.kind,box:clone(reservation.box),rasterMasked:true})))};
  }finally{restoreFlowNativeGlState(gl,state);}
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Object.assign(Error('AREA_GPU_GL_ERROR_'+error),{diagnostic:result});return result;
 },dispose(){
  if(disposed)return;const state=captureFlowNativeGlState(gl);
  try{Object.values(programs).forEach(program=>gl.deleteProgram(program));buffers.forEach(buffer=>gl.deleteBuffer(buffer));
   vaos.forEach(vao=>gl.deleteVertexArray(vao));gl.deleteTexture(boundaryTexture);gl.deleteFramebuffer(boundaryFbo);disposed=true;}
  finally{restoreFlowNativeGlState(gl,state);}
 }};
}
