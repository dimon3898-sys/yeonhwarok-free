/** A reference-study extension. Frozen native terrain, GIS, camera and graphics stay owned by their existing APIs. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer,polygons,triangulateRegion} from './renderer.mjs';
import {captureFlowNativeGlState,restoreFlowNativeGlState} from './flow_graphic_pass_v2.mjs';
import {assertTerritoryControlPlan,evaluateTerritoryControlFrame} from './territory_control_adapter_v1.mjs';
import {assertReferenceCameraTrackPlan,evaluateReferenceCameraTrackFrame} from './reference_camera_adapter_v1.mjs';
import {geographicTerrainLod} from './camera_gpu_pipeline_v2.mjs';
import {geographicScaleVisualTokens} from './camera_gpu_pipeline_v5.mjs';
import {evaluateMinimumContextCameraFrame} from './camera_director_v5.mjs';
import {compileMovingLayoutContract,evaluateMovingLayout,validateVisibleMovingLayout} from './moving_layout_v4.mjs';
import {compileGuidedRevealPlan,evaluateGuidedRevealFrame} from './camera_reveal_v4.mjs';
import {createMovingGraphicPass} from './graphic_motion_pass_v4.mjs';

export const TERRITORY_CONTROL_GPU_ADAPTER_V1_VERSION='TERRITORY_CONTROL_GPU_ADAPTER_V1';
const WIDTH=1080,HEIGHT=1920,MAX_KNOTS=64,MAX_RESERVATIONS=64,MAX_TRIANGLES=32768,TILE=32;
const copy=value=>structuredClone(value);
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const rectangle=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)&&value[0]<value[2]&&value[1]<value[3];
const inside=(x,y,b)=>x+.5>=b[0]&&x+.5<=b[2]&&y+.5>=b[1]&&y+.5<=b[3];
const distance=(p,a,b)=>{const dx=b[0]-a[0],dy=b[1]-a[1],n=dx*dx+dy*dy,
 t=n?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)):0;
 return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);};
const boxes=b=>[b[0],b[1],b[2],b[1],b[0],b[3],b[0],b[3],b[2],b[1],b[2],b[3]];

const vertexSource=`#version 300 es
precision highp float;
layout(location=0) in vec2 position;layout(location=1) in vec2 geographic;
uniform vec2 screenSize;out vec2 geo;
void main(){geo=geographic;gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const fragmentSource=`#version 300 es
precision highp float;precision highp int;
in vec2 geo;out vec4 frag;
uniform vec2 screenSize;uniform vec4 safeArea;
uniform vec4 reservations[64];uniform int reservationCount;uniform sampler2D boundaryMask;
uniform vec3 controlKnots[64];uniform int knotCount;uniform float advanceSign;
uniform vec4 losingColor,existingWinningColor,gainedWinningColor;
vec2 boundaries(float lon){
 if(lon<=controlKnots[0].x)return controlKnots[0].yz;
 for(int i=1;i<64;i++){if(i>=knotCount)break;
  if(lon<=controlKnots[i].x){vec3 a=controlKnots[i-1],b=controlKnots[i];
   return mix(a.yz,b.yz,clamp((lon-a.x)/(b.x-a.x),0.,1.));}}
 return controlKnots[knotCount-1].yz;
}
void main(){
 vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);
 if(p.x<safeArea.x||p.y<safeArea.y||p.x>safeArea.z||p.y>safeArea.w)discard;
 for(int i=0;i<64;i++){if(i>=reservationCount)break;vec4 b=reservations[i];
  if(p.x>=b.x&&p.y>=b.y&&p.x<=b.z&&p.y<=b.w)discard;}
 if(texture(boundaryMask,gl_FragCoord.xy/screenSize).r>.5)discard;
 vec2 limit=boundaries(geo.x);
 float movingDistance=advanceSign*(limit.y-geo.y),baseDistance=advanceSign*(geo.y-limit.x);
 float movingAA=max(fwidth(movingDistance)*.5,1.e-7),baseAA=max(fwidth(baseDistance)*.5,1.e-7);
 float winningWeight=smoothstep(-movingAA,movingAA,movingDistance);
 float gainedWeight=smoothstep(-baseAA,baseAA,baseDistance);
 vec4 winner=mix(existingWinningColor,gainedWinningColor,gainedWeight);
 // One field selects both factions. There are no separately overlapping or disappearing region meshes.
 frag=mix(losingColor,winner,winningWeight);if(frag.a<=0.)discard;
}`;
const maskVertex=`#version 300 es
precision highp float;
layout(location=0) in vec2 position;layout(location=1) in vec4 endpoints;layout(location=2) in float radius;
uniform vec2 screenSize;flat out vec4 edge;flat out float support;
void main(){edge=endpoints;support=radius;gl_Position=vec4(position.x/screenSize.x*2.-1.,1.-position.y/screenSize.y*2.,0.,1.);}`;
const maskFragment=`#version 300 es
precision highp float;uniform vec2 screenSize;flat in vec4 edge;flat in float support;out vec4 frag;
float segmentDistance(vec2 p,vec2 a,vec2 b){vec2 ab=b-a;return length(p-a-ab*clamp(dot(p-a,ab)/max(dot(ab,ab),1.e-12),0.,1.));}
void main(){vec2 p=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y);
 if(segmentDistance(p,edge.xy,edge.zw)>support)discard;frag=vec4(1.,0.,0.,1.);}`;

function program(gl,vertex,fragment){
 const shaders=[],output=gl.createProgram();
 try{for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
  const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
  if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('TERRITORY_GPU_SHADER_'+gl.getShaderInfoLog(shader));
  gl.attachShader(output,shader);}
  gl.linkProgram(output);if(!gl.getProgramParameter(output,gl.LINK_STATUS))throw Error('TERRITORY_GPU_LINK_'+gl.getProgramInfoLog(output));
  return output;
 }catch(error){gl.deleteProgram(output);throw error;}finally{shaders.forEach(shader=>gl.deleteShader(shader));}
}
const locations=(gl,p,names)=>Object.fromEntries(names.map(name=>[name,gl.getUniformLocation(p,name)]));
function styleRecord(style){
 const names=['losingColor','existingWinningColor','gainedWinningColor'];
 if(!style||typeof style.profileName!=='string'||!style.profileName.trim())throw Error('TERRITORY_EXPLICIT_MATERIAL_PROFILE_REQUIRED');
 for(const name of names)if(!Array.isArray(style[name])||style[name].length!==4
  ||style[name].some(value=>!Number.isFinite(value)||value<0||value>1))throw Error('TERRITORY_MATERIAL_RGBA_REQUIRED_'+name);
 return copy(style);
}
function sourceDomain(domain){
 if(!Array.isArray(domain)||!domain.length)throw Error('TERRITORY_LAND_DOMAIN_REQUIRED');
 return domain.map(item=>{
  const geometry=item.geometry,record={geometry_type:geometry?.type,coordinates:geometry?.coordinates};
  const parts=polygons(record),result=triangulateRegion(record,p=>[...p]);
  try{const position=result.mesh.getAttribute('position'),index=result.mesh.getIndex();
   if(index.count/3>MAX_TRIANGLES)throw Error('TERRITORY_GPU_TRIANGLE_CAPACITY');
   const geographic=new Float32Array(index.count*2);
   for(let i=0;i<index.count;i++){const vertex=index.getX(i);geographic[i*2]=position.getX(vertex);geographic[i*2+1]=position.getY(vertex);}
   return{id:item.id,geographic,parts:parts.length,holes:parts.reduce((n,p)=>n+p.length-1,0),triangles:index.count/3};
  }finally{result.mesh.dispose();}
 });
}
function boundaryRecords(input){
 if(!Array.isArray(input)||input.length>8192)throw Error('TERRITORY_BOUNDARY_MASK_CAPACITY');
 return input.map(edge=>{if(!point(edge.a)||!point(edge.b)||!Number.isFinite(edge.radiusPx)||edge.radiusPx<0||edge.radiusPx>64)
  throw Error('TERRITORY_ACTUAL_NATIVE_BOUNDARY_SUPPORT_REQUIRED');
  return{a:[...edge.a],b:[...edge.b],radius:edge.radiusPx+1};});
}
function protectionRecords(input){
 if(!Array.isArray(input)||input.length>MAX_RESERVATIONS)throw Error('TERRITORY_NATIVE_RESERVATION_CAPACITY');
 return input.map(item=>{if(!rectangle(item.box))throw Error('TERRITORY_NATIVE_MEASURED_BOUNDS_REQUIRED');return copy(item);});
}

/** The pass owns only event resources. Its background is the native renderer's current framebuffer. */
export function createTerritoryControlPass({canvas,landDomain,style,width=WIDTH,height=HEIGHT}={}){
 if(width!==WIDTH||height!==HEIGHT||canvas?.width!==width||canvas?.height!==height)throw Error('TERRITORY_CANONICAL_OUTPUT_REQUIRED');
 const gl=canvas.getContext('webgl2');if(!gl)throw Error('TERRITORY_NATIVE_WEBGL2_REQUIRED');
 const material=styleRecord(style),domain=sourceDomain(landDomain),binding=JSON.stringify(landDomain),
  nativeState=captureFlowNativeGlState(gl),programs={},buffers=[],vaos=[];
 let fillBuffer,fillVao,maskBuffer,maskVao,boundaryTexture,boundaryFbo,fillUniforms,maskUniforms,disposed=false;
 try{
  programs.fill=program(gl,vertexSource,fragmentSource);programs.mask=program(gl,maskVertex,maskFragment);
  fillUniforms=locations(gl,programs.fill,['screenSize','safeArea','reservations[0]','reservationCount','boundaryMask',
   'controlKnots[0]','knotCount','advanceSign','losingColor','existingWinningColor','gainedWinningColor']);
  maskUniforms=locations(gl,programs.mask,['screenSize']);
  fillBuffer=gl.createBuffer();buffers.push(fillBuffer);fillVao=gl.createVertexArray();vaos.push(fillVao);
  gl.bindVertexArray(fillVao);gl.bindBuffer(gl.ARRAY_BUFFER,fillBuffer);
  for(const [index,offset] of [[0,0],[1,8]]){gl.enableVertexAttribArray(index);gl.vertexAttribPointer(index,2,gl.FLOAT,false,16,offset);}
  maskBuffer=gl.createBuffer();buffers.push(maskBuffer);maskVao=gl.createVertexArray();vaos.push(maskVao);
  gl.bindVertexArray(maskVao);gl.bindBuffer(gl.ARRAY_BUFFER,maskBuffer);
  for(const [index,size,offset] of [[0,2,0],[1,4,8],[2,1,24]]){gl.enableVertexAttribArray(index);gl.vertexAttribPointer(index,size,gl.FLOAT,false,28,offset);}
  boundaryTexture=gl.createTexture();gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,boundaryTexture);
  for(const key of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,key,gl.NEAREST);
  for(const key of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,key,gl.CLAMP_TO_EDGE);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.R8,width,height);boundaryFbo=gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER,boundaryFbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,boundaryTexture,0);
  if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('TERRITORY_BOUNDARY_MASK_FRAMEBUFFER');
 }catch(error){Object.values(programs).forEach(p=>gl.deleteProgram(p));buffers.forEach(b=>gl.deleteBuffer(b));vaos.forEach(v=>gl.deleteVertexArray(v));
  if(boundaryTexture)gl.deleteTexture(boundaryTexture);if(boundaryFbo)gl.deleteFramebuffer(boundaryFbo);throw error;
 }finally{restoreFlowNativeGlState(gl,nativeState);}
 function gpuState(blend){
  gl.viewport(0,0,width,height);for(const flag of [gl.DEPTH_TEST,gl.STENCIL_TEST,gl.CULL_FACE,gl.POLYGON_OFFSET_FILL,
   gl.RASTERIZER_DISCARD,gl.SAMPLE_ALPHA_TO_COVERAGE,gl.SAMPLE_COVERAGE,gl.DITHER])gl.disable(flag);
  gl.depthMask(false);gl.colorMask(true,true,true,true);
  if(blend){gl.enable(gl.BLEND);gl.blendEquationSeparate(gl.FUNC_ADD,gl.FUNC_ADD);
   gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);}else gl.disable(gl.BLEND);
 }
 function mask(boundaries){
  gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,boundaryFbo);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);gpuState(false);gl.disable(gl.SCISSOR_TEST);
  gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);if(!boundaries.length)return;
  const data=new Float32Array(boundaries.length*6*7);let at=0;
  for(const edge of boundaries){const r=edge.radius+1,b=[Math.min(edge.a[0],edge.b[0])-r,Math.min(edge.a[1],edge.b[1])-r,
   Math.max(edge.a[0],edge.b[0])+r,Math.max(edge.a[1],edge.b[1])+r],vertices=boxes(b);
   for(let i=0;i<6;i++){data.set([vertices[i*2],vertices[i*2+1],...edge.a,...edge.b,edge.radius],at);at+=7;}}
  gl.useProgram(programs.mask);gl.bindVertexArray(maskVao);gl.bindBuffer(gl.ARRAY_BUFFER,maskBuffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STREAM_DRAW);
  gl.uniform2fv(maskUniforms.screenSize,[width,height]);gl.drawArrays(gl.TRIANGLES,0,boundaries.length*6);
 }
 return{evidence:{version:TERRITORY_CONTROL_GPU_ADAPTER_V1_VERSION,composition:'FRESH_NATIVE_TERRAIN_PLUS_SINGLE_COMPLEMENTARY_CONTROL_FIELD',
  nativeRendererSourceUnchanged:true,polygonEngine:'UNCHANGED_RENDERER_POLYGONS_AND_TRIANGULATE_REGION',
  continuousComplementaryOwnership:true,standaloneFrontLine:false,routeVisuals:false,arrowVisuals:false,
  finishedFrameBlit:false,cpuRenderer:false,sourceGeometryMutation:false,terrainRetainedByExplicitMaterialAlpha:true,
  stateRestoration:'FROZEN_FLOW_NATIVE_GL_STATE_HELPERS',material:copy(material)},
  draw({controls,project,safeArea,protectedGraphics=[],boundarySegments=[]}={}){
   if(disposed)throw Error('TERRITORY_GPU_DISPOSED');
   if(controls?.version!=='TERRITORY_CONTROL_FRAME_V1'||typeof project!=='function'||!rectangle(safeArea))throw Error('TERRITORY_GPU_CONTROL_NATIVE_CONTEXT_REQUIRED');
   if(JSON.stringify(controls.landDomain)!==binding||controls.domainGeometryBinding!==binding)throw Error('TERRITORY_GPU_SOURCE_DOMAIN_CHANGED');
   const knots=controls.longitudinalKnots,base=controls.baseBoundaryLatitudes,moving=controls.boundaryLatitudes;
   if(!Array.isArray(knots)||knots.length<2||knots.length>MAX_KNOTS||base?.length!==knots.length||moving?.length!==knots.length
    ||![1,-1].includes(controls.advanceSign))throw Error('TERRITORY_GPU_CLASSIFIER_CONTRACT_REQUIRED');
   const reservations=protectionRecords(protectedGraphics),boundaries=boundaryRecords(boundarySegments),state=captureFlowNativeGlState(gl),rois=[],parts=[];
   try{
    mask(boundaries);gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gpuState(true);gl.enable(gl.SCISSOR_TEST);
    const left=Math.max(0,Math.ceil(safeArea[0])),right=Math.min(width,Math.floor(safeArea[2])),
     top=Math.max(0,Math.ceil(safeArea[1])),bottom=Math.min(height,Math.floor(safeArea[3]));
    gl.scissor(left,height-bottom,Math.max(0,right-left),Math.max(0,bottom-top));gl.useProgram(programs.fill);gl.bindVertexArray(fillVao);
    gl.uniform2fv(fillUniforms.screenSize,[width,height]);gl.uniform4fv(fillUniforms.safeArea,safeArea);
    const protectedBoxes=new Float32Array(MAX_RESERVATIONS*4);
    reservations.forEach((r,i)=>protectedBoxes.set([r.box[0]-1,r.box[1]-1,r.box[2]+1,r.box[3]+1],i*4));
    gl.uniform4fv(fillUniforms['reservations[0]'],protectedBoxes);gl.uniform1i(fillUniforms.reservationCount,reservations.length);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,boundaryTexture);gl.uniform1i(fillUniforms.boundaryMask,0);
    const packedKnots=new Float32Array(MAX_KNOTS*3);knots.forEach((lon,i)=>packedKnots.set([lon,base[i],moving[i]],i*3));
    gl.uniform3fv(fillUniforms['controlKnots[0]'],packedKnots);gl.uniform1i(fillUniforms.knotCount,knots.length);
    gl.uniform1f(fillUniforms.advanceSign,controls.advanceSign);
    for(const name of ['losingColor','existingWinningColor','gainedWinningColor'])gl.uniform4fv(fillUniforms[name],material[name]);
    gl.bindBuffer(gl.ARRAY_BUFFER,fillBuffer);
    for(const item of domain){const data=new Float32Array(item.geographic.length*2),points=[];
     for(let i=0;i<item.geographic.length;i+=2){const geo=[item.geographic[i],item.geographic[i+1]],p=project(geo);
      if(!point(p))throw Error('TERRITORY_ACTUAL_NATIVE_PROJECTION_REQUIRED');
      data.set([...p,...geo],i*2);points.push(p);}
     gl.bufferData(gl.ARRAY_BUFFER,data,gl.STREAM_DRAW);gl.drawArrays(gl.TRIANGLES,0,item.geographic.length/2);
     const roi=[Math.max(left,Math.min(...points.map(p=>p[0]))-1),Math.max(top,Math.min(...points.map(p=>p[1]))-1),
      Math.min(right,Math.max(...points.map(p=>p[0]))+1),Math.min(bottom,Math.max(...points.map(p=>p[1]))+1)];
     if(rectangle(roi))rois.push(roi);parts.push({id:item.id,parts:item.parts,holes:item.holes,triangles:item.triangles});}
   }finally{restoreFlowNativeGlState(gl,state);}
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('TERRITORY_GPU_GL_ERROR_'+glError);
   return{version:TERRITORY_CONTROL_GPU_ADAPTER_V1_VERSION,frame:controls.frame,rois,parts,
    controls:{longitudinalKnots:copy(knots),baseBoundaryLatitudes:copy(base),boundaryLatitudes:copy(moving),advanceSign:controls.advanceSign},
    ownership:'ONE_GEOGRAPHIC_SCALAR_FIELD_COMPLEMENTARY_WINNER_AND_LOSER',domainGeometryBinding:binding,
    geometryUnchanged:true,sourcePartsAndHolesPreserved:true,standaloneFrontLine:false,routeVisuals:false,arrowVisuals:false,
    nativeBoundaryGlowPreserved:true,nativeStateRestored:true,boundaryMaskSegments:boundaries.length,
    material:copy(material),safeArea:copy(safeArea),protectedReservations:reservations,glError};
  },dispose(){if(disposed)return;const state=captureFlowNativeGlState(gl);
   try{Object.values(programs).forEach(p=>gl.deleteProgram(p));buffers.forEach(b=>gl.deleteBuffer(b));vaos.forEach(v=>gl.deleteVertexArray(v));
    gl.deleteTexture(boundaryTexture);gl.deleteFramebuffer(boundaryFbo);disposed=true;}finally{restoreFlowNativeGlState(gl,state);}}
 };
}

const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const roleKey={MARKER:'marker',LOCATION_LABEL:'location',COUNTRY:'country',EVENT_TITLE:'title',TITLE_CONTRAST_PANEL:'title',SCENARIO_DISCLOSURE:'disclosure'};
function measuredReservations(items){
 return items.map(item=>{const [x,y,w,h]=item.box,pad=item.kind==='TEXT'?(item.outlineRadius??item.metrics?.outlineRadius??0)+2:2;
  if(![x,y,w,h,pad].every(Number.isFinite)||w<=0||h<=0||pad<0)throw Error('TERRITORY_NATIVE_MEASURED_GRAPHIC_REQUIRED');
  return{kind:item.kind==='MARKER'?'MARKER':item.kind==='TEXT'?'TEXT':'PANEL',role:item.role,box:[x-pad,y-pad,x+w+pad,y+h+pad]};});
}
function nativeBoundaries(plans,factory,visual){
 const secondary=new Set(plans.REGIONAL.secondary??[]),records=plans.REGIONAL.geometries.filter(item=>item.id===plans.REGIONAL.primary||secondary.has(item.id)),result=[];
 const primaryRadius=Math.max(visual.primaryWidth,visual.primaryEdgeWidth,visual.glowWidth)/2+Math.SQRT2*3.230769*visual.glowRadius+2,
  secondaryRadius=Math.max(visual.secondaryWidth,visual.secondaryEdgeWidth)/2+2;
 for(const record of records){const radiusPx=record.id===plans.REGIONAL.primary?primaryRadius:secondaryRadius;
  if(!Number.isFinite(radiusPx)||radiusPx<=0)throw Error('TERRITORY_NATIVE_FINITE_BOUNDARY_SUPPORT_REQUIRED');
  for(const polygon of polygons(record))for(const ring of polygon)for(let i=1;i<ring.length;i++){
   const a=factory.screen(ring[i-1]),b=factory.screen(ring[i]);if(!point(a)||!point(b))throw Error('TERRITORY_NATIVE_BOUNDARY_PROJECTION_REQUIRED');
   if(Math.max(a[0],b[0])+radiusPx<0||Math.min(a[0],b[0])-radiusPx>WIDTH
    ||Math.max(a[1],b[1])+radiusPx<0||Math.min(a[1],b[1])-radiusPx>HEIGHT)continue;
   result.push({a:[...a],b:[...b],radiusPx,sourceId:record.id,role:record.id===plans.REGIONAL.primary?'PRIMARY':'SECONDARY'});
  }}return result;
}
function indexedBoundaryCheck(boundaries){
 const index=new Map(),columns=Math.ceil(WIDTH/TILE);
 for(const edge of boundaries){const r=edge.radiusPx,left=Math.max(0,Math.floor((Math.min(edge.a[0],edge.b[0])-r)/TILE)),
  right=Math.min(columns-1,Math.floor((Math.max(edge.a[0],edge.b[0])+r)/TILE)),
  top=Math.max(0,Math.floor((Math.min(edge.a[1],edge.b[1])-r)/TILE)),bottom=Math.min(Math.ceil(HEIGHT/TILE)-1,Math.floor((Math.max(edge.a[1],edge.b[1])+r)/TILE));
  for(let y=top;y<=bottom;y++)for(let x=left;x<=right;x++){const key=y*columns+x;if(!index.has(key))index.set(key,[]);index.get(key).push(edge);}}
 return(x,y)=>(index.get(Math.floor(y/TILE)*columns+Math.floor(x/TILE))??[]).some(edge=>distance([x+.5,y+.5],edge.a,edge.b)<=edge.radiusPx);
}
function requireVisualAdmission(receipt,cameraTrack,territoryPlan){
 if(receipt?.status!=='VISUAL_REFERENCE_ADMITTED'||receipt.grade!=='FACT_BASED_VISUAL_GRADE'
  ||receipt.evidenceKind!=='ACTUAL_NATIVE_STATIC_PROBE'||receipt.surveyAdmissionModified!==false
  ||!same(receipt.output,[WIDTH,HEIGHT])||receipt.cameraKeyframeBinding!==JSON.stringify(cameraTrack.keyframes)
  ||receipt.domainGeometryBinding!==territoryPlan.domainGeometryBinding
  ||!Array.isArray(receipt.samples)||!receipt.samples.length
  ||receipt.samples.some(sample=>!Number.isSafeInteger(sample.frame)||sample.frame<0||sample.frame>=cameraTrack.totalFrames
   ||typeof sample.pngSha256!=='string'||!/^[a-f0-9]{64}$/.test(sample.pngSha256)||sample.visual!=='VISUAL_PASS'))
  throw Error('TERRITORY_ACTUAL_BOUND_NATIVE_VISUAL_PROBE_REQUIRED');
}

/** External-camera glue follows the existing Detail adapter's public native APIs.
 * The fixed Area bridge cannot accept these bounds without manufacturing a V5 plan.
 * This extension therefore reuses the native factory directly, keeping its endpoint
 * guard and all FINAL source intact. No survey admission or camera lock is forged.
 */
export async function createTerritoryControlGpuAdapter({canvas,plans,cameraPlan,scene,heightSource=null,contextTerrain=null,
 cameraTrack,territoryPlan,style,mode='STATIC_VISUAL_PROBE',visualAdmission=null}={}){
 const track=assertReferenceCameraTrackPlan(cameraTrack),controlPlan=assertTerritoryControlPlan(territoryPlan),
  regional=plans?.REGIONAL,safeArea=copy(regional?.layout?.safe),target=copy(track.targetBounds),material=styleRecord(style);
 if(!['STATIC_VISUAL_PROBE','VISUAL_REFERENCE_STUDY'].includes(mode))throw Error('TERRITORY_EXPLICIT_VISUAL_MODE_REQUIRED');
 if(!rectangle(safeArea)||!same(track.baseCameraPlan,cameraPlan)||!same(cameraPlan?.intent?.finalExtent,regional?.framing?.bounds)
  ||scene?.primary_region_id!==regional?.primary||track.totalFrames!==controlPlan.totalFrames||track.fps!==controlPlan.fps)
  throw Error('TERRITORY_ACTUAL_BASE_CAMERA_AND_CONTROL_BINDING_REQUIRED');
 if(mode==='VISUAL_REFERENCE_STUDY')requireVisualAdmission(visualAdmission,track,controlPlan);
 const inputBinding=JSON.stringify({plans,cameraPlan,scene,heightSource,contextTerrain,cameraTrack,territoryPlan,style}),
  wideSource=contextTerrain??plans.CONTINENT.assets.terrain,gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
 if(!gl||canvas.width!==WIDTH||canvas.height!==HEIGHT)throw Error('TERRITORY_CANONICAL_NATIVE_CANVAS_REQUIRED');
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(WIDTH,HEIGHT,false);
 renderer.autoClear=false;renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const common={canvas,plan:regional,contextTerrain:wideSource,contextGeometries:plans.CONTINENT.geometries,
  heightSource,width:WIDTH,height:HEIGHT,outputRenderer:renderer,outputTarget:null};
 let measuredFactory,factory,graphics,territory,disposed=false,last=null;
 try{
  measuredFactory=await createMapInfographicRenderer({...common,layoutPlan:regional});
  const nativeLayout=copy(measuredFactory.evidence.layout),nativeLayoutValidation=copy(measuredFactory.evidence.layoutValidation),
   nativeAtlases=measuredFactory.glyphAtlases().map(atlas=>({...atlas})),
   layoutContract=compileMovingLayoutContract({regionalPlan:regional,measuredLayout:nativeLayout}),
   facade={evidence:{layout:nativeLayout,layoutValidation:nativeLayoutValidation},glyphAtlases:()=>nativeAtlases};
  measuredFactory.dispose();measuredFactory=null;
  const endpointPlan=copy(regional);endpointPlan.framing={...endpointPlan.framing,bounds:copy(target),
   center:[(target[0]+target[2])/2,(target[1]+target[3])/2]};
  factory=await createMapInfographicRenderer({...common,layoutPlan:endpointPlan});
  graphics=await createMovingGraphicPass({renderer,factory:facade,width:WIDTH,height:HEIGHT});
  territory=createTerritoryControlPass({canvas,landDomain:controlPlan.intent.domain,style:material});
  const arrival=evaluateMinimumContextCameraFrame(cameraPlan,cameraPlan.totalFrames-1),
   sourceRevealPlan=compileGuidedRevealPlan({cameraPlan,scene,layoutContract,evaluateCamera:evaluateMinimumContextCameraFrame,
    visualTokensForFrame:state=>geographicScaleVisualTokens(state.camera.flatBounds,plans)}),
   arrivalLayout=evaluateMovingLayout(layoutContract,arrival,{markerSize:regional.scale.marker.pixels,boundaryTokens:regional.theme}),
   arrivalReveal=copy(evaluateGuidedRevealFrame(sourceRevealPlan,arrival,arrivalLayout).reveal),
   params={dem:heightSource!==null,verticalExaggeration:2,bakedSuppression:.1,correctedLight:true,shadingCorrection:'FINAL'};
  function pixels(){
   if(disposed)throw Error('TERRITORY_ADAPTER_DISPOSED');
   const bytes=factory.readPixels(),error=gl.getError();if(error!==gl.NO_ERROR)throw Error('TERRITORY_NATIVE_READ_PIXELS_GL_ERROR_'+error);
   return bytes;
  }
  function drawFrame(frame,{protect=true,territoryEnabled=true}={}){
   if(disposed)throw Error('TERRITORY_ADAPTER_DISPOSED');
   if(typeof protect!=='boolean'||typeof territoryEnabled!=='boolean')throw Error('TERRITORY_DRAW_BOOLEAN_REQUIRED');
   const schedule=evaluateReferenceCameraTrackFrame(track,frame),bounds=schedule.flatBounds,
    camera={...copy(arrival),...copy(schedule),extent:copy(bounds),geographicExtent:copy(bounds),
     camera:{...copy(arrival.camera),...copy(schedule.camera)},surveyAdmission:copy(schedule.admission),
     visualAdmission:{grade:'FACT_BASED_VISUAL_GRADE',status:mode,productionEligible:mode==='VISUAL_REFERENCE_STUDY'}},
    visual=geographicScaleVisualTokens(bounds,plans),layout=evaluateMovingLayout(layoutContract,camera,{markerSize:visual.markerSize,boundaryTokens:visual}),
    reveal=copy(arrivalReveal);
   const countryOutsideSafe=layout.validation.failuresByRole.country.some(f=>f.code==='SAFE_AREA');
   reveal.country=countryOutsideSafe?0:arrivalReveal.country;
   const visibleValidation=validateVisibleMovingLayout(layout,reveal),
    warnings=visibleValidation.failures.filter(f=>f.key==='title'&&f.code==='BOUNDARY_CLEARANCE'),
    critical=visibleValidation.failures.filter(f=>!(f.key==='title'&&f.code==='BOUNDARY_CLEARANCE'));
   if(critical.length)throw Object.assign(Error('TERRITORY_VISIBLE_PROTECTED_LAYOUT_INVALID'),{frame,failures:critical});
   const reservations=measuredReservations(layout.items.filter(item=>(reveal[roleKey[item.role]]??0)>0)),
    lod=geographicTerrainLod(bounds,wideSource,regional.assets.terrain,WIDTH,HEIGHT);
   factory.updateCamera(bounds);factory.setScaleVisual(visual);factory.setTerrainLod(lod.weight);
   const native=factory.renderFrame({...params,graphics:false,reveal,primaryMaterial:1});
   if(native.glError!==gl.NO_ERROR)throw Error('TERRITORY_NATIVE_FACTORY_GL_ERROR_'+native.glError);
   const nativeGraphics=graphics.draw({items:layout.items,reveal}),boundaries=nativeBoundaries(plans,factory,visual);
   gl.finish();const before=protect?pixels():null,controls=evaluateTerritoryControlFrame(controlPlan,controlPlan.startFrame+frame),
    controlGraphics=territoryEnabled?territory.draw({controls,project:point=>factory.screen(point),safeArea,
     protectedGraphics:reservations,boundarySegments:boundaries}):null,rois=controlGraphics?.rois??[];
   gl.finish();
   const protection={checked:protect,changedPixels:0,protectedChangedPixels:0,markerChangedPixels:0,textChangedPixels:0,
    outsideRoiChangedPixels:0,safeAreaChangedPixels:0,protectedBoundaryChangedPixels:0};
   if(protect){const after=pixels(),first=new Uint32Array(before.buffer),second=new Uint32Array(after.buffer),onBoundary=indexedBoundaryCheck(boundaries);
    for(let i=0;i<second.length;i++)if(first[i]!==second[i]){
     const x=i%WIDTH,y=HEIGHT-1-Math.floor(i/WIDTH);protection.changedPixels++;
     if(!inside(x,y,safeArea))protection.safeAreaChangedPixels++;
     if(!rois.some(roi=>inside(x,y,roi)))protection.outsideRoiChangedPixels++;
     const overlaps=reservations.filter(item=>inside(x,y,item.box));
     if(overlaps.length)protection.protectedChangedPixels++;
     if(overlaps.some(item=>item.kind==='MARKER'))protection.markerChangedPixels++;
     if(overlaps.some(item=>item.kind==='TEXT'||item.kind==='PANEL'))protection.textChangedPixels++;
     if(onBoundary(x,y))protection.protectedBoundaryChangedPixels++;
    }
    if(protection.protectedChangedPixels||protection.markerChangedPixels||protection.textChangedPixels
     ||protection.outsideRoiChangedPixels||protection.safeAreaChangedPixels||protection.protectedBoundaryChangedPixels)
     throw Object.assign(Error('TERRITORY_NATIVE_PIXEL_PROTECTION_FAILED'),{frame,protection});
   }
   const glError=gl.getError();if(glError!==gl.NO_ERROR)throw Error('TERRITORY_NATIVE_COMPOSITION_GL_ERROR_'+glError);
   if(inputBinding!==JSON.stringify({plans,cameraPlan,scene,heightSource,contextTerrain,cameraTrack,territoryPlan,style}))
    throw Error('TERRITORY_PROTECTED_INPUT_MUTATION');
   last={frame,state:'REFERENCE_TERRITORY_CONTROL',camera,cameraLocked:false,settle:copy(schedule.settle),
    gpu:{stage:'REFERENCE_CONTROL_EXTENSION_OVER_UNCHANGED_NATIVE_FACTORY',glError,factoryCount:1,nativeDrawCount:1,
     actualCamera:copy(factory.evidence.cameraFrame),actualReveal:copy(factory.evidence.revealState),boundaryPixels:visual,terrainLod:lod,
     layout:copy(layout.items),layoutValidation:{valid:critical.length===0,failures:critical,warnings},
     visibleRoles:copy(nativeGraphics.visibleRoles),finishedFrameMix:false,projectionChange:false,graphicPass:graphics.evidence.version},
    territory:{enabled:territoryEnabled,graphics:controlGraphics,domainGeometryBinding:controlPlan.domainGeometryBinding,
     boundaryKeyframeBinding:controlPlan.boundaryKeyframeBinding,semanticMode:controls.semanticMode,
     geometryUnchanged:true,continuousComplementaryOwnership:true,standaloneFrontLine:false,routeVisuals:false,arrowVisuals:false},
    protection,rois,protectedGraphics:reservations,boundaryProtection:{segmentCount:boundaries.length,
     source:'ACTUAL_NATIVE_PRIMARY_SECONDARY_RING_PROJECTION',finiteGlowSupport:true},
    sourceV5Unchanged:true,surveyAdmissionPreserved:true,admission:copy(arrival.admission),
    visualAdmission:{mode,status:visualAdmission?.status??'STATIC_PROBE_ONLY',productionEligible:mode==='VISUAL_REFERENCE_STUDY'}};
   return last;
  }
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  return{drawFrame,draw:drawFrame,readPixels:pixels,png:()=>canvas.toDataURL('image/png'),project:p=>factory.screen(p),
   evidence:{version:TERRITORY_CONTROL_GPU_ADAPTER_V1_VERSION,mode,productionEligible:mode==='VISUAL_REFERENCE_STUDY',
    factoryCount:1,measurementFactoryDisposedBeforeActiveFactory:true,composition:'FRESH_NATIVE_TERRAIN_AND_FROZEN_GRAPHICS_PLUS_COMPLEMENTARY_EVENT_MATERIAL',
    rendererSourceUnchanged:true,cameraV5SourceUnchanged:true,layoutSourceUnchanged:true,sourceGeometryMutation:false,
    nativeEndpointGuardActive:true,targetFraming:{bounds:copy(target)},originalNativeLayout:nativeLayout,
    originalGlyphAtlases:nativeAtlases.map(atlas=>atlas.name),surveyAdmissionPreserved:true,surveyAdmission:copy(arrival.admission),
    actualCameraLocked:false,arrivalReadinessForged:false,externalMotionOwner:track.ownership.camera,
    gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
    finishedFrameMix:false,projectionChange:false,frozenMaterialParameters:copy(params),graphicPass:graphics.evidence,
    territoryPass:territory.evidence,adapterReason:'FIXED_AREA_NATIVE_BRIDGE_API_CANNOT_CONSUME_EXTERNAL_CAMERA_WITHOUT_V5_PLAN_FORGERY'},
   get diagnostic(){return last;},dispose(){if(disposed)return;territory.dispose();graphics.dispose();factory.dispose();renderer.dispose();disposed=true;}};
 }catch(error){measuredFactory?.dispose();territory?.dispose();graphics?.dispose();factory?.dispose();renderer.dispose();throw error;}
}
