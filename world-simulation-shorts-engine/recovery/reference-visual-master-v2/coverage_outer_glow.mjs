/** A single 16-neighbor source-coverage expression pass. No contour geometry,
 * fake coast/route/front line, SDF engine or source-frame overlay is generated. */
import {validateReferenceFrontierProfile} from './frontier_profile_core.mjs';
export const OUTER_DOMAIN_GOLD_FRAGMENT=`#version 300 es
precision highp float;precision highp int;in vec2 vUv;out vec4 frag;
uniform sampler2D domainCoverage;uniform vec2 screenDimensions;
uniform float presentationScale,outerGoldWidth,outerGoldSigma,outerGoldSupport,outerGoldIntensity;
uniform vec3 outerGoldColor,outerGoldHaloColor;
uniform vec4 safeArea,reservations[64];uniform int reservationCount;
float readCoverage(ivec2 p){
 // Unknown beyond the viewport is never presumed to be water. Consequently
 // a cropped full land rectangle has no fabricated glowing frame border.
 return texelFetch(domainCoverage,clamp(p,ivec2(0),textureSize(domainCoverage,0)-ivec2(1)),0).r;
}
void main(){
 vec2 screen=vec2(gl_FragCoord.x,screenDimensions.y-gl_FragCoord.y);
 if(screen.x<safeArea.x||screen.y<safeArea.y||screen.x>safeArea.z||screen.y>safeArea.w)discard;
 for(int i=0;i<64;i++){if(i>=reservationCount)break;vec4 box=reservations[i];
  if(screen.x>=box.x&&screen.y>=box.y&&screen.x<=box.z&&screen.y<=box.w)discard;}
 ivec2 pixel=ivec2(gl_FragCoord.xy);float c=readCoverage(pixel),core=0.,halo=0.;
 for(int ring=0;ring<4;ring++){
  float radius=ring==0?outerGoldWidth:outerGoldSupport*float(ring)/3.;
  radius/=presentationScale;int r=max(1,int(floor(radius+.5)));
  vec4 taps=vec4(readCoverage(pixel-ivec2(r,0)),readCoverage(pixel+ivec2(r,0)),
   readCoverage(pixel-ivec2(0,r)),readCoverage(pixel+ivec2(0,r)));
  float response=max(max(abs(taps.x-c),abs(taps.y-c)),max(abs(taps.z-c),abs(taps.w-c)));
  // The original separate MSAA role channels can round within two LSB. This
  // only suppresses illumination from that quantization; native bytes stay intact.
  response=max(0.,response-2./255.)/(1.-2./255.);
  if(ring==0)core=max(0.,c-min(min(taps.x,taps.y),min(taps.z,taps.w))-2./255.)/(1.-2./255.);
  halo=max(halo,response*exp(-.5*pow(radius/(outerGoldSigma/presentationScale),2.)));
 }
 core=clamp(core,0.,1.)*.95*outerGoldIntensity;halo=clamp(halo,0.,1.)*.28*outerGoldIntensity;
 vec3 color=outerGoldColor*core+outerGoldHaloColor*halo*(1.-core);
 if(max(max(color.r,color.g),color.b)<=0.)discard;
 frag=vec4(color,0.);
}`;
export function createCoverageOuterGlowPass({gl,width=1080,height=1920,profile={},capture,restore,programFactory,resetPixels,setupTexture}={}){
 const p=validateReferenceFrontierProfile(profile);
 if(!p.enabled||p.outerGoldIntensity<=0)throw Error('REFERENCE_OUTER_DISABLED_MUST_DELEGATE');
 if(!gl||width!==1080||height!==1920||typeof capture!=='function'||typeof restore!=='function'||
  typeof programFactory!=='function'||typeof resetPixels!=='function'||typeof setupTexture!=='function')
  throw Error('REFERENCE_OUTER_NATIVE_GPU_CONTRACT_REQUIRED');
 const before=capture(gl);let program,texture,vao,disposed=false;
 const release=()=>{if(program)gl.deleteProgram(program);if(texture)gl.deleteTexture(texture);if(vao)gl.deleteVertexArray(vao);};
 const keys=['domainCoverage','screenDimensions','presentationScale','outerGoldWidth','outerGoldSigma','outerGoldSupport','outerGoldIntensity','outerGoldColor','outerGoldHaloColor','safeArea','reservations[0]','reservationCount'];
 let u;
 try{
  program=programFactory(gl,OUTER_DOMAIN_GOLD_FRAGMENT);texture=gl.createTexture();vao=gl.createVertexArray();
  if(!program||!texture||!vao)throw Error('REFERENCE_OUTER_GPU_ALLOCATION');
  u=Object.fromEntries(keys.map(key=>[key,gl.getUniformLocation(program,key)]));resetPixels(gl);
  setupTexture(gl,texture,0);gl.texStorage2D(gl.TEXTURE_2D,1,gl.R8,width,height);
 }catch(error){release();throw error;}finally{restore(gl,before);}
 if(gl.getError()!==gl.NO_ERROR){release();throw Error('REFERENCE_OUTER_RESOURCE_GL_ERROR');}
 return {draw({context,presentationScale,safeArea=[0,0,width,height],protectedGraphics=[]}={}){
  if(disposed)throw Error('REFERENCE_OUTER_DISPOSED');
  if(!context||!(context.domainCoverage instanceof Uint8Array)||context.domainCoverage.length!==width*height||
   context.width!==width||context.height!==height||context.rowZero!=='SOUTH'||
   !Number.isFinite(presentationScale)||presentationScale<1||presentationScale>2)
   throw Error('REFERENCE_OUTER_ACTUAL_FRAME_REQUIRED');
  const box=value=>Array.isArray(value)&&value.length===4&&value.every(Number.isFinite)&&value[0]<value[2]&&value[1]<value[3];
  if(!box(safeArea)||!Array.isArray(protectedGraphics)||protectedGraphics.length>64||protectedGraphics.some(r=>!box(r.box)))
   throw Error('REFERENCE_OUTER_PROTECTED_GRAPHICS_REQUIRED');
  const state=capture(gl);
  try{
   gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.viewport(0,0,width,height);
   for(const flag of [gl.DEPTH_TEST,gl.STENCIL_TEST,gl.CULL_FACE,gl.SCISSOR_TEST,gl.POLYGON_OFFSET_FILL,
    gl.RASTERIZER_DISCARD,gl.SAMPLE_ALPHA_TO_COVERAGE,gl.SAMPLE_COVERAGE,gl.DITHER])gl.disable(flag);
   gl.depthMask(false);gl.colorMask(true,true,true,true);resetPixels(gl);gl.useProgram(program);gl.bindVertexArray(vao);
   gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(0,null);
   gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,width,height,gl.RED,gl.UNSIGNED_BYTE,context.domainCoverage);
   gl.uniform1i(u.domainCoverage,0);gl.uniform2f(u.screenDimensions,width,height);gl.uniform1f(u.presentationScale,presentationScale);
   gl.uniform4fv(u.safeArea,safeArea);const reservations=new Float32Array(64*4);
   protectedGraphics.forEach((record,index)=>reservations.set(record.box,index*4));
   gl.uniform4fv(u['reservations[0]'],reservations);gl.uniform1i(u.reservationCount,protectedGraphics.length);
   for(const key of ['outerGoldWidth','outerGoldSigma','outerGoldSupport','outerGoldIntensity'])gl.uniform1f(u[key],p[key]);
   for(const key of ['outerGoldColor','outerGoldHaloColor'])gl.uniform3fv(u[key],p[key]);
   // Screen composition preserves a pure white existing front exactly. It
   // cannot darken territory/terrain or replace the original destination alpha.
   gl.enable(gl.BLEND);gl.blendEquationSeparate(gl.FUNC_ADD,gl.FUNC_ADD);
   gl.blendFuncSeparate(gl.ONE,gl.ONE_MINUS_SRC_COLOR,gl.ZERO,gl.ONE);gl.drawArrays(gl.TRIANGLES,0,3);
  }finally{restore(gl,state);}
  const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('REFERENCE_OUTER_DRAW_GL_ERROR_'+error);
  return {version:'REFERENCE_NATIVE_DOMAIN_OUTER_GOLD_V2',frame:context.frame,nativeFrame:context.nativeFrame,
   domainSHA256:context.domainSHA256,sourceGeometrySHA256:context.sourceGeometrySHA256,bounds:[...context.bounds],
   union:'ACTUAL_SAME_FRAME_NATIVE_PRIMARY_PLUS_SECONDARY',coverageRowZero:'SOUTH',
   coverageBytesChanged:false,geographicGeometryGenerated:false,sharedInternalOutline:false,allLandRChannelUsed:false,
   fabricatedViewportEdge:false,sourceRGBMaskInference:false,newArrows:0,newDecorativeLines:0,
   sourceCoverageNeighborTaps:16,singlePass:true,blend:'SCREEN_RGB_DESTINATION_ALPHA_PRESERVED',
   pureWhiteDestinationPreserved:true,protectedReservations:protectedGraphics.length,safeArea:[...safeArea],
   nominalOutputCorePixels:p.outerGoldWidth,nominalOutputSupportPixels:p.outerGoldSupport,
   nativeCoreSampling:'MINIMUM_ONE_NATIVE_PIXEL_INTEGER_NEIGHBORHOOD',presentationScale,
   estimatedAdditionalGpuBytes:width*height,driverOverheadIncluded:false,nativeStateRestored:true,glError:error};
 },dispose(){if(disposed)return;release();disposed=true;}};
}
