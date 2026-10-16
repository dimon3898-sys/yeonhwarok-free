/** GPU source-grade pass only; ownership/frontier/presentation/units follow it.
 * Reuse the original upload and quality distance helpers without source edits. */
import {qualityProgram,createSupportDistanceTextures,setupQualityTexture,resetQualityPixels} from '/quality/support_gpu.mjs';
import {SOURCE_GRADE_FRAGMENT,validateReferenceSourceProfile,REFERENCE_SOURCE_GRADE_VERSION} from './source_grade_core.mjs';
const supportFragment=`#version 300 es
precision highp float;precision highp int;in vec2 vUv;out vec4 frag;
uniform sampler2D distanceTexture;uniform vec4 bounds;uniform vec2 sourceOrigin,sourceStep,screenDimensions;
uniform float screenFeatherPixels;uniform bool oceanRole;
float at(ivec2 p){ivec2 n=textureSize(distanceTexture,0);
 return any(lessThan(p,ivec2(0)))||any(greaterThanEqual(p,n))?-.5:texelFetch(distanceTexture,p,0).r;}
void main(){vec2 geo=mix(bounds.xy,bounds.zw,vUv),position=(geo-sourceOrigin)/sourceStep;
 ivec2 p=ivec2(floor(position)),n=textureSize(distanceTexture,0);
 if(any(lessThan(p,ivec2(0)))||any(greaterThanEqual(p,n))||at(p)<0.){frag=vec4(0.);return;}
 vec2 q=position-.5,f=fract(q);ivec2 i=ivec2(floor(q));
 float distance=mix(mix(at(i),at(i+ivec2(1,0)),f.x),mix(at(i+ivec2(0,1)),at(i+ivec2(1)),f.x),f.y);
 vec2 sourcePerPixel=abs((bounds.zw-bounds.xy)/screenDimensions/sourceStep);
 float weight=smoothstep(0.,screenFeatherPixels,distance/max(max(sourcePerPixel.x,sourcePerPixel.y),1.e-12));
 frag=oceanRole?vec4(0.,weight,0.,1.):vec4(weight,0.,0.,1.);
}`;
const clone=value=>structuredClone(value),budget=256*1024*1024;
export function estimateExtraSourceGpuBytes(resources,width,height){
 const source=resources.reduce((sum,r)=>sum+r.metadata.dimensions[0]*r.metadata.dimensions[1]*(r.role==='bathymetry'?3:5),0),
 distance=resources.reduce((sum,r)=>sum+r.metadata.dimensions[0]*r.metadata.dimensions[1]*4,0),
 screen=width*height*(4+4+3),transient=Math.max(0,...resources.map(r=>r.metadata.dimensions[0]*r.metadata.dimensions[1]*4));
 return {additionalUploadPacks:1,persistentSourceTextureBytes:source,persistentDistanceTextureBytes:distance,
  persistentScreenTextureBytes:screen,peakTransientBooleanTextureBytes:transient,
  estimatedAdditionalGpuBytes:source+distance+screen+transient,budgetBytes:budget,
  estimateIncludesDriverOverhead:false,actualVramMeasured:false};
}
export function createReferenceSourceGradePass({gl,baseline,uploads,profile,width,height,oceanTint,capture,restore}={}){
 const p=validateReferenceSourceProfile(profile),memory=estimateExtraSourceGpuBytes(uploads.resources,width,height);
 if(!p.enabled)throw Error('REFERENCE_SOURCE_DISABLED_MUST_DELEGATE_ORIGINAL');
 if(memory.estimatedAdditionalGpuBytes>budget)throw Error('REFERENCE_SOURCE_EXTRA_GPU_BUDGET_EXCEEDED');
 const before=capture(gl),programs={},uniforms={};let support,vao,coverageTexture,supportTexture,snapshotTexture,fbo,disposed=false,last=null;
 const release=()=>{for(const program of Object.values(programs))gl.deleteProgram(program);
  if(vao)gl.deleteVertexArray(vao);if(fbo)gl.deleteFramebuffer(fbo);
  for(const texture of [coverageTexture,supportTexture,snapshotTexture])if(texture)gl.deleteTexture(texture);support?.dispose();};
 try{
  support=createSupportDistanceTextures(gl,uploads.resources,{capture,restore});
  programs.support=qualityProgram(gl,supportFragment);programs.grade=qualityProgram(gl,SOURCE_GRADE_FRAGMENT);
  for(const [key,names] of [['support',['distanceTexture','bounds','sourceOrigin','sourceStep','screenDimensions','screenFeatherPixels','oceanRole']],
   ['grade',['actualSource','coverageTexture','supportTexture','screenDimensions','terrainLocalContrast','landExposure','oceanExposure','oceanTealMix','oceanTint']]])
   uniforms[key]=Object.fromEntries(names.map(name=>[name,gl.getUniformLocation(programs[key],name)]));
  vao=gl.createVertexArray();fbo=gl.createFramebuffer();coverageTexture=gl.createTexture();supportTexture=gl.createTexture();snapshotTexture=gl.createTexture();
  if(!vao||!fbo||!coverageTexture||!supportTexture||!snapshotTexture)throw Error('REFERENCE_SOURCE_RESOURCE_ALLOCATION');
  resetQualityPixels(gl);
  for(const [unit,texture,format]of [[0,coverageTexture,gl.RGBA8],[1,supportTexture,gl.RGBA8],[2,snapshotTexture,gl.RGB8]]){
   setupQualityTexture(gl,texture,unit);gl.texStorage2D(gl.TEXTURE_2D,1,format,width,height);}
  gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,supportTexture,0);
  if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('REFERENCE_SOURCE_SUPPORT_FBO_INCOMPLETE');
 }catch(error){release();throw error;}finally{restore(gl,before);}
 if(gl.getError()!==gl.NO_ERROR){release();throw Error('REFERENCE_SOURCE_RESOURCE_GL_ERROR');}
 const sourceGrade={version:REFERENCE_SOURCE_GRADE_VERSION,enabled:true,profile:clone(p),
  scope:'ACTUAL_VALID_ASTRA_SUPPORT_ONLY_BASELINE_EXACT_OUTSIDE',sourceValuesChanged:false,sourceCoordinatesChanged:false,
  heightFromColor:false,physicalNormalsReconstructed:false,coastOutlineGenerated:false,nativeCoastCoverageFiltered:false,
  landSupport:'MAX_OF_VALID_SURFACE_AND_VALID_FIVE_NEIGHBOUR_DEM_SUPPORT',oceanSupport:'VALID_NEGATIVE_GEBCO_AND_NATIVE_GIS_OCEAN',
  supportMasks:support.fields.map(field=>clone(field.statistics)),memory,testOnly:uploads.testOnly===true,
  gpuPixelsVerified:false,gpuRenderingVerified:false,actualNvidiaVerified:false};
 return {evidence:{...clone(baseline.evidence),sourceGrade},get outputTexture(){if(disposed)throw Error('REFERENCE_SOURCE_DISPOSED');return snapshotTexture;},
  get snapshotFrame(){return clone(last);},draw(args={}){
   if(disposed)throw Error('REFERENCE_SOURCE_DISPOSED');
   const native=baseline.draw(args),state=capture(gl);let supportDraws=0;
   try{
    resetQualityPixels(gl);gl.bindVertexArray(vao);gl.viewport(0,0,width,height);
    for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD,gl.DITHER])gl.disable(cap);
    gl.colorMask(true,true,true,true);
    if(!args.rawSource){
     gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,fbo);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
     gl.clearBufferfv(gl.COLOR,0,new Float32Array([0,0,0,0]));
     gl.enable(gl.BLEND);gl.blendEquation(gl.MAX);gl.blendFunc(gl.ONE,gl.ONE);gl.useProgram(programs.support);
     const u=uniforms.support;gl.uniform4fv(u.bounds,args.bounds);gl.uniform2f(u.screenDimensions,width,height);
     gl.uniform1f(u.screenFeatherPixels,p.screenFeatherPixels);gl.uniform1i(u.distanceTexture,0);
     for(const field of support.fields){
      gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,field.texture);gl.bindSampler(0,null);
      gl.uniform2fv(u.sourceOrigin,[field.entry.metadata.transform[0],field.entry.metadata.transform[3]]);
      gl.uniform2fv(u.sourceStep,[field.entry.metadata.transform[1],field.entry.metadata.transform[5]]);
      gl.uniform1i(u.oceanRole,field.entry.role==='bathymetry'?1:0);gl.drawArrays(gl.TRIANGLES,0,3);supportDraws++;
     }
     gl.disable(gl.BLEND);gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);gl.useProgram(programs.grade);
     const v=uniforms.grade;
     for(const [unit,texture,key]of [[0,baseline.outputTexture,'actualSource'],[1,coverageTexture,'coverageTexture'],[2,supportTexture,'supportTexture']]){
      gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);gl.uniform1i(v[key],unit);}
     gl.activeTexture(gl.TEXTURE0+1);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);
     gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,args.coverage);
     gl.uniform2f(v.screenDimensions,width,height);gl.uniform3fv(v.oceanTint,oceanTint);
     for(const key of ['terrainLocalContrast','landExposure','oceanExposure','oceanTealMix'])gl.uniform1f(v[key],p[key]);
     gl.drawArrays(gl.TRIANGLES,0,3);
    }
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);
    gl.activeTexture(gl.TEXTURE0+2);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);gl.bindSampler(2,null);
    gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);
   }finally{restore(gl,state);}
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('REFERENCE_SOURCE_DRAW_GL_ERROR_'+error);
   last={...native,sourceGrade:{...clone(sourceGrade),frame:args.frame,sourceMaterialBeforeTerritory:true,
    combinedOutputTexture:true,actualMaterialSnapshot:true,snapshotFormat:'RGB8',actualNativeCoverage:true,
    supportDraws,gradeDraws:args.rawSource?0:1,rawSourceBaselineOnly:args.rawSource===true}};
   return clone(last);
  },dispose(){if(disposed)return;release();uploads.dispose();baseline.dispose();disposed=true;}};
}
