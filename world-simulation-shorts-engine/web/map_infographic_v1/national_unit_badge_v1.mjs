/** Original national unit tablets on already-resolved geographic frame data.
 * This pass does not infer country, date, story, historical admission or motion.
 * Standard national symbols are fixture geometry; unit container/art is original.
 */
import {evaluateReferenceCombatLayout} from './reference_combat_overlay_v2.mjs';

export const NATIONAL_UNIT_BADGE_V1_VERSION='WORLD_ENGINE_NATIONAL_UNIT_BADGE_V1';
const point=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite);
const color=value=>typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value);
const roles=new Set(['GROUND','AVIATION','SUPPORT']);
const forbidden=['reference_pixels','reference_badge_art','portrait','face_portrait','flag_shapes','source_texture'];
function validateShapes(shapes,depth=0) {
 if(!Array.isArray(shapes)||!shapes.length||depth>4)throw Error('NATIONAL_FLAG_GEOMETRY_REQUIRED');
 for(const shape of shapes) {
  if(!shape||forbidden.some(key=>key in shape))throw Error('NATIONAL_FLAG_ORIGINAL_VECTOR_REQUIRED');
  if(shape.type==='group') {
   if(!point(shape.translate)||!Number.isFinite(shape.rotation??0))throw Error('NATIONAL_FLAG_GROUP_REQUIRED');
   validateShapes(shape.shapes,depth+1);continue;
  }
  if(!['rect','circle','polygon','star','path'].includes(shape.type)
   ||(shape.fill!==undefined&&!color(shape.fill))||(shape.stroke!==undefined&&!color(shape.stroke)))
   throw Error('NATIONAL_FLAG_VECTOR_STYLE_REQUIRED');
  const numeric=Object.entries(shape).filter(([key])=>!['type','fill','stroke','commands','points'].includes(key));
  if(numeric.some(([,value])=>!Number.isFinite(value)))throw Error('NATIONAL_FLAG_FINITE_GEOMETRY_REQUIRED');
  if(shape.type==='rect'&&!(shape.width>0&&shape.height>0))throw Error('NATIONAL_FLAG_RECT_REQUIRED');
  if(['circle','star'].includes(shape.type)&&!(shape.radius>0))throw Error('NATIONAL_FLAG_RADIUS_REQUIRED');
  if(shape.type==='polygon'&&(!Array.isArray(shape.points)||shape.points.length<3||!shape.points.every(point)))
   throw Error('NATIONAL_FLAG_POLYGON_REQUIRED');
  if(shape.type==='path'&&(!Array.isArray(shape.commands)||!shape.commands.length||shape.commands.some(command=>
   !Array.isArray(command)||!['M','L','Q','C','Z'].includes(command[0])||!command.slice(1).every(Number.isFinite))))
   throw Error('NATIONAL_FLAG_PATH_REQUIRED');
 }
}
export function validateNationalFlagProfiles(profiles) {
 if(!profiles||typeof profiles!=='object'||Array.isArray(profiles)||!Object.keys(profiles).length)
  throw Error('NATIONAL_FLAG_PROFILES_REQUIRED');
 for(const [id,profile] of Object.entries(profiles)) {
  if(!profile||profile.id!==id||typeof profile.country_id!=='string'
   ||profile.artwork!=='WORLD_ENGINE_ORIGINAL_ROUNDED_TABLET'||!Number.isFinite(profile.aspect_ratio)
   ||profile.aspect_ratio<1||profile.aspect_ratio>2.5||!roles.has(profile.default_role??'GROUND')
   ||forbidden.some(key=>key in profile))throw Error('NATIONAL_FLAG_DATA_PROFILE_REQUIRED');
  validateShapes(profile.flag_geometry);
 }
 return {profiles:Object.keys(profiles).length,sourceIconArtworkCopied:false,countryBranchInRenderer:false};
}
export function validateNationalUnitBadgeFixture(units,profiles) {
 validateNationalFlagProfiles(profiles);
 if(!Array.isArray(units)||!units.length)throw Error('NATIONAL_UNIT_FIXTURE_REQUIRED');
 const ids=new Set();
 for(const unit of units) {
  if(!unit||typeof unit.id!=='string'||ids.has(unit.id)||!profiles[unit.profile_id]
   ||!roles.has(unit.role??profiles[unit.profile_id].default_role??'GROUND'))throw Error('NATIONAL_UNIT_PROFILE_ROLE_REQUIRED');
  ids.add(unit.id);
  if(!Array.isArray(unit.anchor_frames)||unit.anchor_frames.length<2||!unit.anchor_frames.every(p=>point(p)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90)
   ||!Array.isArray(unit.size_frames)||unit.size_frames.length!==unit.anchor_frames.length
   ||!unit.size_frames.every(size=>Number.isFinite(size)&&size>=72&&size<=140)
   ||!Array.isArray(unit.rotation_frames)||unit.rotation_frames.length!==unit.anchor_frames.length
   ||!unit.rotation_frames.every(Number.isFinite))throw Error('NATIONAL_UNIT_RESOLVED_FRAME_DATA_REQUIRED');
 }
 if(units.some(unit=>unit.anchor_frames.length!==units[0].anchor_frames.length))throw Error('NATIONAL_UNIT_FRAME_COUNT_REQUIRED');
 return {units:units.length,frames:units[0].anchor_frames.length,flags:units.length,
  motionEngine:'NONE_RESOLVED_FRAME_ANCHORS',layoutEngine:'REUSED_REFERENCE_COMBAT_LAYOUT',sourceIconArtworkCopied:false};
}

/** Conservative actual artwork support, in screen pixels about its center.
 * The outer tablet/role support stays inside the reused eight-sided envelope.
 */
export function measureNationalUnitBadge({sizePx,rotationDegrees=0,aspectRatio=1.5}={}) {
 if(!Number.isFinite(sizePx)||sizePx<16||!Number.isFinite(rotationDegrees)||!Number.isFinite(aspectRatio)||aspectRatio<1)
  throw Error('NATIONAL_UNIT_MEASUREMENT_REQUIRED');
 const support=[],radius=.240,left=-.436,right=.436,top=-.356,bottom=.356;
 for(const [cx,cy,start] of [[right-radius,top+radius,-90],[right-radius,bottom-radius,0],
  [left+radius,bottom-radius,90],[left+radius,top+radius,180]])
  for(let step=0;step<=24;step++) {
   const angle=(start+step*90/24)*Math.PI/180;support.push([cx+Math.cos(angle)*radius,cy+Math.sin(angle)*radius]);
  }
 for(let step=0;step<48;step++) {
  const angle=step*Math.PI/24;support.push([Math.cos(angle)*.108,.282+Math.sin(angle)*.108]);
 }
 const angle=rotationDegrees*Math.PI/180,cos=Math.cos(angle),sin=Math.sin(angle);
 const projected=support.map(([x,y])=>[(x*cos-y*sin)*sizePx,(x*sin+y*cos)*sizePx]);
 const bounds=[Math.min(...projected.map(p=>p[0])),Math.min(...projected.map(p=>p[1])),
  Math.max(...projected.map(p=>p[0])),Math.max(...projected.map(p=>p[1]))];
 return {sizePx,rotationDegrees,bounds,widthPx:bounds[2]-bounds[0],heightPx:bounds[3]-bounds[1],
  flagWidthPx:sizePx*.64,flagHeightPx:sizePx*.64/aspectRatio,normalizedSupport:support,
  conservativeSupportWithinReusedOctagon:support.every(([x,y])=>Math.abs(x)<=.5*Math.cos(Math.PI/8)+1e-9
   &&Math.abs(y)<=.5*Math.cos(Math.PI/8)+1e-9&&Math.abs(x)+Math.abs(y)<=.5*(Math.cos(Math.PI/8)+Math.sin(Math.PI/8))+1e-9)};
}
export function evaluateNationalUnitBadgeLayout(units,frame,input) {
 const layout=evaluateReferenceCombatLayout(units,frame,input);
 return {...layout,version:NATIONAL_UNIT_BADGE_V1_VERSION,flags:layout.units.length,
  units:layout.units.map(item=>{
   const measured=measureNationalUnitBadge({sizePx:item.size_px,rotationDegrees:item.rotation_degrees});
   return {...item,artworkBounds:measured.bounds.map((value,index)=>value+item.position[index%2]),
    flagWidthPx:measured.flagWidthPx,actualArtworkInsideProtectedFootprint:measured.conservativeSupportWithinReusedOctagon};
  }),sourceIconArtworkCopied:false,sourceBackgroundCopied:false,noRenderedText:true,
  historicalPolicyApplied:false,policyOwner:'CALLER_FIXTURE',speculativeImpactCues:0};
}

function paintShapes(context,shapes) {
 for(const shape of shapes) {
  if(shape.type==='group') {
   context.save();context.translate(...shape.translate);context.rotate(shape.rotation??0);
   paintShapes(context,shape.shapes);context.restore();continue;
  }
  context.beginPath();
  if(shape.type==='rect')context.rect(shape.x,shape.y,shape.width,shape.height);
  else if(shape.type==='circle')context.arc(shape.cx,shape.cy,shape.radius,0,Math.PI*2);
  else if(shape.type==='polygon') {
   shape.points.forEach((p,index)=>index?context.lineTo(...p):context.moveTo(...p));context.closePath();
  } else if(shape.type==='star') {
   for(let index=0;index<10;index++) {
    const angle=-Math.PI/2+(shape.rotation??0)+index*Math.PI/5,
     radius=index%2===0?shape.radius:shape.inner_radius??shape.radius*.381966;
    const p=[shape.cx+Math.cos(angle)*radius,shape.cy+Math.sin(angle)*radius];
    index?context.lineTo(...p):context.moveTo(...p);
   }context.closePath();
  } else if(shape.type==='path') {
   for(const [operation,...coords] of shape.commands) {
    if(operation==='M')context.moveTo(...coords);else if(operation==='L')context.lineTo(...coords);
    else if(operation==='Q')context.quadraticCurveTo(...coords);else if(operation==='C')context.bezierCurveTo(...coords);
    else context.closePath();
   }
  }
  if(shape.fill){context.fillStyle=shape.fill;context.fill();}
  if(shape.stroke){context.strokeStyle=shape.stroke;context.lineWidth=shape.stroke_width??.01;context.stroke();}
 }
}
function roleGlyph(context,role) {
 context.save();context.translate(0,.282);
 context.beginPath();context.arc(0,0,.1,0,Math.PI*2);context.fillStyle='#14292e';context.fill();
 context.strokeStyle='#6e8c8f';context.lineWidth=.01;context.stroke();
 if(role==='AVIATION') {
  paintShapes(context,[{type:'polygon',points:[[0,-.068],[.022,-.019],[.072,.035],[.017,.016],
   [.011,.057],[0,.044],[-.011,.057],[-.017,.016],[-.072,.035],[-.022,-.019]],fill:'#bcd0cc'}]);
 } else if(role==='SUPPORT') {
  paintShapes(context,[{type:'rect',x:-.049,y:-.04,width:.098,height:.08,fill:'#b7ceca'},
   {type:'rect',x:-.013,y:-.06,width:.026,height:.12,fill:'#f1e7bf'}]);
 } else {
  const bevel=context.createLinearGradient(-.08,-.05,.08,.035);
  bevel.addColorStop(0,'#dbe0cb');bevel.addColorStop(.52,'#91ada9');bevel.addColorStop(1,'#385359');
  context.beginPath();context.moveTo(-.07,.014);context.bezierCurveTo(-.073,-.08,.065,-.08,.07,.014);
  context.lineTo(-.07,.014);context.closePath();context.fillStyle=bevel;context.fill();
  context.fillStyle='#d0ddce';context.fillRect(-.078,.005,.156,.019);
  context.fillStyle='#3b5358';context.fillRect(-.047,.028,.094,.023);
 }
 context.restore();
}
/** Original tablet, full unobscured flag panel, neutral abstract role glyph.
 * No visible octagon, soldier face, text, neon halo or source badge pixels.
 */
export function createNationalUnitBadgeArtwork(profile,resolution=256,{role=profile?.default_role??'GROUND'}={}) {
 validateNationalFlagProfiles({[profile?.id]:profile});
 if(!Number.isSafeInteger(resolution)||resolution<96||resolution>1024||!roles.has(role))
  throw Error('NATIONAL_UNIT_ARTWORK_SIZE_ROLE_REQUIRED');
 const canvas=document.createElement('canvas');canvas.width=canvas.height=resolution;
 const context=canvas.getContext('2d',{alpha:true});
 context.translate(resolution/2,resolution/2);context.scale(resolution,resolution);
 context.lineJoin='round';context.lineCap='round';
 const bevel=context.createLinearGradient(-.43,-.35,.43,.35);
 bevel.addColorStop(0,'#8ca3a0');bevel.addColorStop(.08,'#233f47');bevel.addColorStop(.55,'#142d35');bevel.addColorStop(1,'#071a20');
 context.beginPath();context.roundRect(-.43,-.35,.86,.7,.234);context.fillStyle=bevel;context.fill();
 context.strokeStyle='#c7d1bf';context.lineWidth=.012;context.stroke();
 context.beginPath();context.roundRect(-.407,-.327,.814,.654,.21);
 context.strokeStyle='#06161b';context.lineWidth=.014;context.stroke();
 const flagWidth=.64,flagHeight=flagWidth/profile.aspect_ratio;
 context.save();context.translate(-flagWidth/2,-.245-(flagHeight-.36)/2);
 context.scale(flagHeight,flagHeight);paintShapes(context,profile.flag_geometry);context.restore();
 context.strokeStyle='#e0e2d1';context.lineWidth=.006;
 context.strokeRect(-flagWidth/2,-.245-(flagHeight-.36)/2,flagWidth,flagHeight);
 roleGlyph(context,role);return canvas;
}

function shader(gl,type,source) {
 const value=gl.createShader(type);if(!value)throw Error('NATIONAL_UNIT_SHADER_ALLOCATION');
 try {
  gl.shaderSource(value,source);gl.compileShader(value);
  if(!gl.getShaderParameter(value,gl.COMPILE_STATUS))throw Error('NATIONAL_UNIT_SHADER:'+gl.getShaderInfoLog(value));
  return value;
 } catch(error) {gl.deleteShader(value);throw error;}
}
export async function createNationalUnitBadgeOverlay({canvas,width=1080,height=1920,units,profiles}={}) {
 const fixture=validateNationalUnitBadgeFixture(units,profiles);
 if(!canvas||canvas.width!==width||canvas.height!==height)throw Error('NATIONAL_UNIT_NATIVE_CANVAS_REQUIRED');
 const gl=canvas.getContext('webgl2');if(!gl)throw Error('NATIONAL_UNIT_WEBGL2_REQUIRED');
 const {captureFlowNativeGlState,restoreFlowNativeGlState}=await import('./flow_graphic_pass_v2.mjs');
 const surface=document.createElement('canvas');surface.width=width;surface.height=height;
 const context=surface.getContext('2d',{alpha:true}),artwork=new Map();
 for(const unit of units) {
  const role=unit.role??profiles[unit.profile_id].default_role??'GROUND',key=unit.profile_id+'|'+role;
  if(!artwork.has(key))artwork.set(key,createNationalUnitBadgeArtwork(profiles[unit.profile_id],256,{role}));
 }
 const saved=captureFlowNativeGlState(gl);let program,texture,vao,buffer,vertex,fragment,disposed=false;
 const releaseStaged=()=>{
  if(vertex){gl.deleteShader(vertex);vertex=null;}if(fragment){gl.deleteShader(fragment);fragment=null;}
  if(program){gl.deleteProgram(program);program=null;}if(texture){gl.deleteTexture(texture);texture=null;}
  if(vao){gl.deleteVertexArray(vao);vao=null;}if(buffer){gl.deleteBuffer(buffer);buffer=null;}
  artwork.clear();
 };
 try {
  program=gl.createProgram();
  if(!program)throw Error('NATIONAL_UNIT_PROGRAM_ALLOCATION');
  vertex=shader(gl,gl.VERTEX_SHADER,'#version 300 es\nprecision highp float;\nlayout(location=0) in vec2 p;out vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0.,1.);}');
  fragment=shader(gl,gl.FRAGMENT_SHADER,'#version 300 es\nprecision highp float;\nuniform sampler2D symbols;in vec2 uv;out vec4 color;void main(){color=texture(symbols,vec2(uv.x,1.-uv.y));}');
  gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);
  vertex=fragment=null;
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('NATIONAL_UNIT_LINK:'+gl.getProgramInfoLog(program));
  vao=gl.createVertexArray();buffer=gl.createBuffer();
  if(!vao||!buffer)throw Error('NATIONAL_UNIT_GEOMETRY_ALLOCATION');
  gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);
  texture=gl.createTexture();if(!texture)throw Error('NATIONAL_UNIT_TEXTURE_ALLOCATION');
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);
  for(const [key,value] of [['TEXTURE_MIN_FILTER','LINEAR'],['TEXTURE_MAG_FILTER','LINEAR'],
   ['TEXTURE_WRAP_S','CLAMP_TO_EDGE'],['TEXTURE_WRAP_T','CLAMP_TO_EDGE']])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl[value]);
 } catch(error) {releaseStaged();throw error;}
 finally {
  try {restoreFlowNativeGlState(gl,saved);}catch(error){releaseStaged();throw error;}
 }
 return {version:NATIONAL_UNIT_BADGE_V1_VERSION,fixture,evidence:{version:NATIONAL_UNIT_BADGE_V1_VERSION,
  artwork:'ORIGINAL_ROUNDED_TABLET_ABSTRACT_ROLE_WITH_STANDARD_NATIONAL_FLAG',
  flagsFromFixture:true,countryBranchInRenderer:false,historicalPolicyApplied:false,
  layoutEngine:'REUSED_REFERENCE_COMBAT_LAYOUT',sourceIconArtworkCopied:false,
  sourceVideoPixelsAsTexture:false,frameBackgroundReadOrCopied:false,noRenderedText:true,
  noRoutesArrowsOrText:true,speculativeImpactCues:0,motionEngine:'NONE_RESOLVED_FRAME_ANCHORS'},
  draw({frame,project,protectedGraphics=[],safeArea=[48,72,width-48,height-72]}={}) {
   if(disposed)throw Error('NATIONAL_UNIT_DISPOSED');
   const controls=evaluateNationalUnitBadgeLayout(units,frame,{project,protectedGraphics,safeArea});
   context.clearRect(0,0,width,height);
   for(const item of controls.units) {
    const unit=units.find(value=>value.id===item.id),role=unit.role??profiles[item.profile_id].default_role??'GROUND';
    context.save();context.translate(...item.position);context.rotate(item.rotation_degrees*Math.PI/180);
    context.drawImage(artwork.get(item.profile_id+'|'+role),-item.size_px/2,-item.size_px/2,item.size_px,item.size_px);
    context.restore();
   }
   const native=captureFlowNativeGlState(gl);
   try {
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,width,height);gl.disable(gl.SCISSOR_TEST);
    for(const capability of ['DEPTH_TEST','CULL_FACE','STENCIL_TEST','RASTERIZER_DISCARD'])gl.disable(gl[capability]);
    gl.enable(gl.BLEND);gl.blendEquation(gl.FUNC_ADD);gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA,gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
    gl.colorMask(true,true,true,true);gl.useProgram(program);gl.bindVertexArray(vao);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);gl.pixelStorei(gl.UNPACK_ALIGNMENT,4);
    gl.pixelStorei(gl.UNPACK_ROW_LENGTH,0);gl.pixelStorei(gl.UNPACK_SKIP_PIXELS,0);gl.pixelStorei(gl.UNPACK_SKIP_ROWS,0);
    gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,gl.RGBA,gl.UNSIGNED_BYTE,surface);
    gl.uniform1i(gl.getUniformLocation(program,'symbols'),0);gl.drawArrays(gl.TRIANGLES,0,6);
    const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('NATIONAL_UNIT_DRAW_GL_ERROR:'+error);
   } finally {restoreFlowNativeGlState(gl,native);}
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('NATIONAL_UNIT_RESTORE_GL_ERROR:'+error);
   return {...controls,glError:error,frameBackgroundReadOrCopied:false,noRenderedText:true};
  },dispose(){if(disposed)return;gl.deleteProgram(program);gl.deleteTexture(texture);gl.deleteVertexArray(vao);
   gl.deleteBuffer(buffer);artwork.clear();disposed=true;},
 };
}
