/** Isolated measured-map presentation. V5, native projection and original assets remain unchanged. */
export const REFERENCE_PRESENTATION_ADAPTER_V2_VERSION='REFERENCE_PRESENTATION_ADAPTER_V2';
const version=REFERENCE_PRESENTATION_ADAPTER_V2_VERSION,copy=value=>structuredClone(value),rad=deg=>deg*Math.PI/180;
const finitePoint=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
const finiteBounds=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const frozen=value=>{if(value&&typeof value==='object'){for(const item of Object.values(value))frozen(item);Object.freeze(value);}return value;};
const rotate=(p,angle)=>{const c=Math.cos(angle),s=Math.sin(angle);return[c*p[0]-s*p[1],s*p[0]+c*p[1]];};
function dimensions(width,height){
 if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<1||height<1)throw Error('PRESENTATION_POSITIVE_INTEGER_DIMENSIONS_REQUIRED');
}
function center(bounds){return[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2];}
function span(bounds){return[bounds[2]-bounds[0],bounds[3]-bounds[1]];}
function monotoneSlope(values,frames,index){
 if(index===0)return(values[1]-values[0])/(frames[1]-frames[0]);
 if(index===values.length-1)return(values[index]-values[index-1])/(frames[index]-frames[index-1]);
 const left=(values[index]-values[index-1])/(frames[index]-frames[index-1]),
  right=(values[index+1]-values[index])/(frames[index+1]-frames[index]);
 if(left===0||right===0||Math.sign(left)!==Math.sign(right))return 0;
 const a=2*(frames[index+1]-frames[index])+(frames[index]-frames[index-1]),
  b=(frames[index+1]-frames[index])+2*(frames[index]-frames[index-1]);
 return(a+b)/(a/left+b/right);
}

/** Derive the exact inverse-sampling rectangle; no screen-space source-footage images are accepted. */
export function presentationSourceUVBounds({rollDegrees,overscan,width=1080,height=1920}={}){
 dimensions(width,height);
 if(!Number.isFinite(rollDegrees)||!Number.isFinite(overscan)||overscan<1)throw Error('PRESENTATION_VALID_ROLL_AND_OVERSCAN_REQUIRED');
 const angle=rad(rollDegrees),c=Math.abs(Math.cos(angle)),s=Math.abs(Math.sin(angle)),
  rx=(c+height/width*s)/(2*overscan),ry=(c+width/height*s)/(2*overscan);
 return[.5-rx,.5-ry,.5+rx,.5+ry];
}

/** The input is measured roll only; position/zoom retain the existing reference-camera track owner. */
export function compileReferencePresentationPlan({rollKeyframes,totalFrames,fps=30,overscan=1.19,width=1080,height=1920}={}){
 dimensions(width,height);
 if(!Number.isSafeInteger(totalFrames)||totalFrames<2||!Number.isSafeInteger(fps)||fps<1)
  throw Error('PRESENTATION_FRAME_TIMING_REQUIRED');
 if(!Number.isFinite(overscan)||overscan<1||overscan>2)throw Error('PRESENTATION_BOUNDED_CONSTANT_OVERSCAN_REQUIRED');
 if(!Array.isArray(rollKeyframes)||rollKeyframes.length<2)throw Error('PRESENTATION_MEASURED_ROLL_KEYFRAMES_REQUIRED');
 const keys=rollKeyframes.map(key=>({frame:key?.frame,rollDegrees:key?.rollDegrees}));
 if(keys.some((key,i)=>!Number.isSafeInteger(key.frame)||key.frame<0||key.frame>=totalFrames
  ||!Number.isFinite(key.rollDegrees)||Math.abs(key.rollDegrees)>45||i>0&&key.frame<=keys[i-1].frame)
  ||keys[0].frame!==0||keys.at(-1).frame!==totalFrames-1)
  throw Error('PRESENTATION_ORDERED_COMPLETE_MEASURED_ROLL_REQUIRED');
 const values=keys.map(k=>k.rollDegrees),frames=keys.map(k=>k.frame),
  slopes=values.map((_,i)=>monotoneSlope(values,frames,i)),
  segments=keys.slice(1).map((key,i)=>{const duration=key.frame-keys[i].frame,a=values[i],delta=values[i+1]-a,
   v0=slopes[i]*duration,v1=slopes[i+1]*duration;
   return{startFrame:keys[i].frame,endFrame:key.frame,coefficients:[a,v0,3*delta-2*v0-v1,-2*delta+v0+v1]};});
 const plan={version,totalFrames,fps,width,height,overscan,keyframes:keys,segments,
  interpolation:'SHARED_MONOTONE_CUBIC_ROLL_C1',rollDirection:'SCREEN_POSITIVE_CLOCKWISE',
  source:'MEASURED_REFERENCE_ROLL_OVER_GENUINE_NATIVE_MAP',focalPoint:[width/2,height/2],
  cameraV5SourceUnchanged:true,nativeProjectionSourceUnchanged:true,sourceFootageSampling:false,
  foregroundPolicy:'GEOGRAPHIC_FRAME_ROTATES_UNIFORMLY;SCREEN_FIXED_OVERLAYS_DRAW_AFTER_PRESENTATION'};
 for(let frame=0;frame<totalFrames;frame++){
  const state=evaluateReferencePresentationFrame(plan,frame);
  if(!state.noCornerClip)throw Error('PRESENTATION_OVERSCAN_INSUFFICIENT_FOR_MEASURED_ROLL');
 }
 return frozen(plan);
}

export function evaluateReferencePresentationFrame(plan,frame){
 if(plan?.version!==version||!Number.isSafeInteger(frame)||frame<0||frame>=plan.totalFrames)
  throw Error('PRESENTATION_PLAN_FRAME_REQUIRED');
 const exact=plan.keyframes.find(k=>k.frame===frame),segment=plan.segments.find(s=>frame<=s.endFrame)??plan.segments.at(-1),
  u=(frame-segment.startFrame)/(segment.endFrame-segment.startFrame),[a,b,c,d]=segment.coefficients,
  rollDegrees=exact?.rollDegrees??a+u*(b+u*(c+u*d)),
  sourceUVBounds=presentationSourceUVBounds({rollDegrees,overscan:plan.overscan,width:plan.width,height:plan.height}),
  noCornerClip=sourceUVBounds[0]>=0&&sourceUVBounds[1]>=0&&sourceUVBounds[2]<=1&&sourceUVBounds[3]<=1;
 return frozen({version,frame,timeSeconds:frame/plan.fps,rollDegrees,overscan:plan.overscan,width:plan.width,height:plan.height,
  focalPoint:copy(plan.focalPoint),sourceUVBounds,noCornerClip,
  rollVelocityDegreesPerSecond:(b+u*(2*c+u*3*d))/(segment.endFrame-segment.startFrame)*plan.fps,
  cameraV5SourceUnchanged:true,nativeProjectionSourceUnchanged:true,sourceFootageSampling:false});
}

/** Correct the old unrotated measured pan, then enlarge its genuine native rendering extent by constant overscan. */
export function expandNativeBounds({bounds,referenceStartBounds,rollDegrees,overscan=1.19,width=1080,height=1920,correctMeasuredPan=true}={}){
 dimensions(width,height);
 if(!finiteBounds(bounds)||!finiteBounds(referenceStartBounds)||!Number.isFinite(rollDegrees)
  ||!Number.isFinite(overscan)||overscan<1||typeof correctMeasuredPan!=='boolean')throw Error('PRESENTATION_BOUND_FRAMING_REQUIRED');
 const actual=span(bounds),originalCenter=center(referenceStartBounds),oldCenter=center(bounds);
 let c=oldCenter;
 if(correctMeasuredPan){
  const measuredPan=[-(oldCenter[0]-originalCenter[0])*width/actual[0],(oldCenter[1]-originalCenter[1])*height/actual[1]],
   inversePan=rotate(measuredPan,-rad(rollDegrees));
  c=[originalCenter[0]-inversePan[0]*actual[0]/width,originalCenter[1]+inversePan[1]*actual[1]/height];
 }
 const expanded=[actual[0]*overscan,actual[1]*overscan],
  result=[c[0]-expanded[0]/2,c[1]-expanded[1]/2,c[0]+expanded[0]/2,c[1]+expanded[1]/2];
 if(result[0]<-180||result[2]>180||result[1]<-90||result[3]>90)throw Error('PRESENTATION_OVERSCAN_GEOGRAPHIC_DOMAIN_EXCEEDED');
 return result;
}

/** Canonical top-left coordinates. Used for all geospatial fronts and unit overlays. */
export function projectNativePoint(point,state){
 if(!finitePoint(point)||state?.version!==version)throw Error('PRESENTATION_CANONICAL_POINT_STATE_REQUIRED');
 const c=state.focalPoint,q=rotate([point[0]-c[0],point[1]-c[1]],rad(state.rollDegrees));
 return[c[0]+state.overscan*q[0],c[1]+state.overscan*q[1]];
}
export function unprojectPresentationPoint(point,state){
 if(!finitePoint(point)||state?.version!==version)throw Error('PRESENTATION_CANONICAL_POINT_STATE_REQUIRED');
 const c=state.focalPoint,q=rotate([point[0]-c[0],point[1]-c[1]],-rad(state.rollDegrees));
 return[c[0]+q[0]/state.overscan,c[1]+q[1]/state.overscan];
}
export function geoToPresentationScreen(point,expandedBounds,state){
 if(!finitePoint(point)||!finiteBounds(expandedBounds))throw Error('PRESENTATION_GEOGRAPHIC_POINT_BOUNDS_REQUIRED');
 const [west,south,east,north]=expandedBounds;
 return projectNativePoint([(point[0]-west)/(east-west)*state.width,(north-point[1])/(north-south)*state.height],state);
}
export function presentationScreenToGeo(point,expandedBounds,state){
 if(!finiteBounds(expandedBounds))throw Error('PRESENTATION_GEOGRAPHIC_BOUNDS_REQUIRED');
 const q=unprojectPresentationPoint(point,state),[west,south,east,north]=expandedBounds;
 return[west+q[0]/state.width*(east-west),north-q[1]/state.height*(north-south)];
}

/** Reusable direct measured-frame registration, independent of the render overscan implementation. */
export function referenceScreenToGeo(point,{startBounds,scale=1,rollDegrees=0,displacement=[0,0],width=1080,height=1920}={}){
 dimensions(width,height);
 if(!finitePoint(point)||!finiteBounds(startBounds)||!finitePoint(displacement)||!Number.isFinite(scale)||scale<=0||!Number.isFinite(rollDegrees))
  throw Error('PRESENTATION_REFERENCE_REGISTRATION_REQUIRED');
 const c=[width/2,height/2],q=rotate([point[0]-c[0]-displacement[0],point[1]-c[1]-displacement[1]],-rad(rollDegrees)),
  p=[c[0]+q[0]/scale,c[1]+q[1]/scale];
 return[startBounds[0]+p[0]/width*(startBounds[2]-startBounds[0]),startBounds[3]-p[1]/height*(startBounds[3]-startBounds[1])];
}

const vertexSource=`#version 300 es
precision highp float;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.-1.,0.,1.);}`;
const fragmentSource=`#version 300 es
precision highp float;out vec4 frag;
uniform sampler2D nativeMap;uniform vec2 screenSize;uniform vec2 focal;uniform float overscan;uniform float angle;
void main(){
 vec2 outputPoint=vec2(gl_FragCoord.x,screenSize.y-gl_FragCoord.y),delta=outputPoint-focal;
 float c=cos(angle),s=sin(angle);
 vec2 nativePoint=focal+vec2(c*delta.x+s*delta.y,-s*delta.x+c*delta.y)/overscan;
 frag=texture(nativeMap,vec2(nativePoint.x/screenSize.x,1.-nativePoint.y/screenSize.y));
}`;

/** Copies ONLY the current genuinely rendered native map into an owned same-context GPU texture. */
export async function createReferencePresentationPass({canvas,width=1080,height=1920}={}){
 dimensions(width,height);
 if(canvas?.width!==width||canvas?.height!==height)throw Error('PRESENTATION_CANVAS_DIMENSIONS_REQUIRED');
 const gl=canvas.getContext('webgl2');if(!gl)throw Error('PRESENTATION_NATIVE_WEBGL2_REQUIRED');
 const {captureFlowNativeGlState,restoreFlowNativeGlState}=await import('./flow_graphic_pass_v2.mjs');
 const initial=captureFlowNativeGlState(gl),program=gl.createProgram(),shaders=[],texture=gl.createTexture(),vao=gl.createVertexArray(),
  textureFormat=gl.getContextAttributes().alpha?'RGBA8':'RGB8';
 let disposed=false;
 try{
  for(const [type,source]of[[gl.VERTEX_SHADER,vertexSource],[gl.FRAGMENT_SHADER,fragmentSource]]){
   const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('PRESENTATION_SHADER_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('PRESENTATION_LINK_'+gl.getProgramInfoLog(program));
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);
  // WebGL2 copyTexSubImage2D requires a compatible base format: an alpha:false default framebuffer is RGB, not RGBA.
  gl.texStorage2D(gl.TEXTURE_2D,1,gl[textureFormat],width,height);
  for(const [name,value]of[[gl.TEXTURE_MIN_FILTER,gl.LINEAR],[gl.TEXTURE_MAG_FILTER,gl.LINEAR],
   [gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE],[gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE]])gl.texParameteri(gl.TEXTURE_2D,name,value);
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('PRESENTATION_INITIAL_GL_ERROR_'+error);
 }catch(error){gl.deleteProgram(program);gl.deleteTexture(texture);gl.deleteVertexArray(vao);throw error;}
 finally{shaders.forEach(shader=>gl.deleteShader(shader));restoreFlowNativeGlState(gl,initial);}
 const uniforms=Object.fromEntries(['nativeMap','screenSize','focal','overscan','angle'].map(name=>[name,gl.getUniformLocation(program,name)]));
 function draw({state,plan,frame}={}){
  if(disposed)throw Error('PRESENTATION_PASS_DISPOSED');
  const sample=state??evaluateReferencePresentationFrame(plan,frame);
  if(sample.version!==version||sample.width!==width||sample.height!==height||!sample.noCornerClip)
   throw Error('PRESENTATION_BOUND_NO_CORNER_CLIP_STATE_REQUIRED');
  const before=captureFlowNativeGlState(gl);
  try{
   gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);
   gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
   gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);
   const copyError=gl.getError();if(copyError!==gl.NO_ERROR)throw Error('PRESENTATION_NATIVE_COPY_GL_ERROR_'+copyError);
   gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
   gl.viewport(0,0,width,height);gl.colorMask(true,true,true,true);
   for(const capability of ['BLEND','DEPTH_TEST','STENCIL_TEST','SCISSOR_TEST','CULL_FACE','RASTERIZER_DISCARD'])gl.disable(gl[capability]);
   gl.bindVertexArray(vao);gl.useProgram(program);gl.uniform1i(uniforms.nativeMap,0);
   gl.uniform2f(uniforms.screenSize,width,height);gl.uniform2fv(uniforms.focal,sample.focalPoint);
   gl.uniform1f(uniforms.overscan,sample.overscan);gl.uniform1f(uniforms.angle,rad(sample.rollDegrees));
   gl.drawArrays(gl.TRIANGLES,0,3);
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('PRESENTATION_DRAW_GL_ERROR_'+error);
  }finally{restoreFlowNativeGlState(gl,before);}
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('PRESENTATION_RESTORE_GL_ERROR_'+error);
  return{version,frame:sample.frame,rollDegrees:sample.rollDegrees,overscan:sample.overscan,
   noCornerClip:true,cornerSamplesInside:true,
   minimumCornerInsetPixels:Math.min(sample.sourceUVBounds[0]*width,sample.sourceUVBounds[1]*height,
    (1-sample.sourceUVBounds[2])*width,(1-sample.sourceUVBounds[3])*height),
   sourceUVBounds:copy(sample.sourceUVBounds),glError:error,nativeStateRestored:true,
   source:'CURRENT_NATIVE_GEOGRAPHIC_FRAMEBUFFER',textureFormat,sourceFootageSampling:false,
   cpuPixelReadback:false,nativeProjectionSourceUnchanged:true,cameraV5SourceUnchanged:true};
 }
 function dispose(){if(!disposed){disposed=true;gl.deleteProgram(program);gl.deleteTexture(texture);gl.deleteVertexArray(vao);}}
 return{draw,dispose,evidence:{version,composition:'GENUINE_NATIVE_MAP_GPU_COPY_UNIFORM_ROTATE_CROP',
  textureFormat,sourceFootageSampling:false,sourceGeometryMutation:false,originalSourceChanged:false}};
}
