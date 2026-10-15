/** Source-stage boundary-only visual revision. Native data/projection/coverage,
 * original value sampling and downstream territory/frontier remain unchanged. */
import {qualityProgram,createSupportDistanceTextures,setupQualityTexture,resetQualityPixels} from './support_gpu.mjs';
export const QUALITY_MATERIAL_VERSION='ASTRA_VALID_SUPPORT_FEATHER_V1';
const clone=value=>structuredClone(value),roles=['surfaceTexture','terrain','bathymetry'];
export function validateBoundaryProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('QUALITY_BOUNDARY_PROFILE_REQUIRED');
 const boundary=input.boundary??true,screenFeatherPixels=input.screenFeatherPixels??32;
 if(typeof boundary!=='boolean'||!Number.isFinite(screenFeatherPixels)||screenFeatherPixels<8||screenFeatherPixels>96)
  throw Error('QUALITY_BOUNDARY_PROFILE_RANGE');
 return Object.freeze({boundary,screenFeatherPixels});
}
export function effectiveFeather(part,bounds,width,height,pixels){
 const sx=Math.abs((bounds[2]-bounds[0])/width/part.transform[1]),
 sy=Math.abs((bounds[3]-bounds[1])/height/part.transform[5]);
 return {screenFeatherPixels:pixels,sourcePixelsPerScreenPixel:[sx,sy],
  sourceFeatherPixels:pixels*Math.max(sx,sy),minimumScreenFeatherPixels:pixels,
  maximumScreenFeatherPixels:pixels*Math.max(sx,sy)/Math.max(1e-12,Math.min(sx,sy))};
}
export function buildQualityFragment(role){
 if(!roles.includes(role))throw Error('QUALITY_SOURCE_ROLE_REQUIRED');
 const sampler=role==='bathymetry'?'isampler2D':'sampler2D';
 let treatment;
 if(role==='surfaceTexture')treatment=`
 vec4 value=texelFetch(valuesTexture,p,0);if(value.a<=0.){frag=vec4(base,1.);return;}
 vec3 sourceColor=clamp(value.rgb*surfaceGain,0.,.94);
 frag=vec4(mix(base,sourceColor,surfaceMix*land*support*value.a),1.);`;
 if(role==='terrain')treatment=`
 if(any(lessThan(p,ivec2(1)))||any(greaterThanEqual(p,dimensions-ivec2(1)))){frag=vec4(base,1.);return;}
 ivec2 offsets[5]=ivec2[5](ivec2(0),ivec2(1,0),ivec2(-1,0),ivec2(0,1),ivec2(0,-1));
 float heights[5];for(int i=0;i<5;i++){ivec2 q=p+offsets[i];heights[i]=texelFetch(valuesTexture,q,0).r;
  if(texelFetch(validTexture,q,0).r!=1u||isnan(heights[i])||isinf(heights[i])){frag=vec4(base,1.);return;}}
 float latitude=sourceOrigin.y+(float(p.y)+.5)*sourceStep.y,metricCos=cos(radians(latitude));
 if(metricCos<.0001){frag=vec4(base,1.);return;}
 vec2 gradient=vec2((heights[1]-heights[2])/(222638.98158654716*metricCos*sourceStep.x),
                   (heights[3]-heights[4])/(222638.98158654716*sourceStep.y));
 vec3 normal=normalize(vec3(-gradient,1.)),light=normalize(vec3(-.45,.65,.62));
 float planar=max(light.z,.01),diffuse=max(dot(normal,light),0.);
 float illumination=clamp((.42+.58*diffuse)/(.42+.58*planar),.72,1.26);
 float altitude=clamp(heights[0]/5000.,-.2,1.);
 vec3 lit=base*illumination*(1.+.045*altitude)+warmHighlightColor*warmHighlightStrength*max(diffuse-planar,0.);
 frag=vec4(clamp(mix(base,lit,reliefStrength*land*support),0.,.94),1.);`;
 if(role==='bathymetry')treatment=`
 float elevation=float(texelFetch(valuesTexture,p,0).r);
 if(elevation>=0.){frag=vec4(base,1.);return;}
 float t=clamp(log(1.-elevation)/log(1.+depthScaleMeters),0.,1.);
 vec3 depthColor=t<.5?mix(nearshoreTint,midTint,t*2.):mix(midTint,deepTint,(t-.5)*2.);
 frag=vec4(clamp(mix(base,depthColor,depthMix*(1.-land)*support),0.,.94),1.);`;
 return `#version 300 es
precision highp float;precision highp int;precision highp usampler2D;precision highp isampler2D;
in vec2 vUv;out vec4 frag;
uniform sampler2D baselineTexture,coverageTexture,distanceTexture;
uniform ${sampler} valuesTexture;uniform usampler2D validTexture;
uniform vec4 bounds;uniform vec2 sourceOrigin,sourceStep,screenDimensions;
uniform float screenFeatherPixels,surfaceMix,surfaceGain,reliefStrength,depthMix,depthScaleMeters;
uniform vec3 warmHighlightColor,nearshoreTint,midTint,deepTint;uniform float warmHighlightStrength;
float distanceAt(ivec2 p){ivec2 n=textureSize(distanceTexture,0);
 return any(lessThan(p,ivec2(0)))||any(greaterThanEqual(p,n))?-.5:texelFetch(distanceTexture,p,0).r;}
float supportDistance(vec2 at){vec2 q=at-.5;ivec2 p=ivec2(floor(q));vec2 f=fract(q);
 return mix(mix(distanceAt(p),distanceAt(p+ivec2(1,0)),f.x),
            mix(distanceAt(p+ivec2(0,1)),distanceAt(p+ivec2(1)),f.x),f.y);}
void main(){
 vec3 base=texture(baselineTexture,vUv).rgb;
 // Native GIS is NEVER blurred or used as a source support-distance field.
 float land=clamp(texture(coverageTexture,vUv).r,0.,1.);
 vec2 geo=mix(bounds.xy,bounds.zw,vUv),at=(geo-sourceOrigin)/sourceStep;
 ivec2 p=ivec2(floor(at)),dimensions=textureSize(valuesTexture,0);
 if(any(lessThan(p,ivec2(0)))||any(greaterThanEqual(p,dimensions))||
    texelFetch(validTexture,p,0).r!=1u){frag=vec4(base,1.);return;}
 vec2 sourcePerScreenPixel=abs((bounds.zw-bounds.xy)/screenDimensions/sourceStep);
 float distanceScreenPixels=supportDistance(at)/max(max(sourcePerScreenPixel.x,sourcePerScreenPixel.y),1.e-12);
 float support=smoothstep(0.,screenFeatherPixels,distanceScreenPixels);
 if(support<=0.){frag=vec4(base,1.);return;}
 ${treatment}
}`;
}
const uniformKeys=['baselineTexture','coverageTexture','distanceTexture','valuesTexture','validTexture','bounds',
 'sourceOrigin','sourceStep','screenDimensions','screenFeatherPixels','surfaceMix','surfaceGain','reliefStrength',
 'depthMix','depthScaleMeters','warmHighlightColor','warmHighlightStrength','nearshoreTint','midTint','deepTint'];
export function createQualityCompositionPass({gl,baseline,uploads,profile,qualityProfile={},baselineProfile,width,height,capture,restore}={}){
 const q=validateBoundaryProfile(qualityProfile);
 if(!q.boundary)throw Error('QUALITY_FALSE_MUST_SELECT_UNCHANGED_BASELINE_FACTORY');
 const entries=roles.flatMap(role=>uploads.resources.filter(r=>r.role===role)),before=capture(gl);
 let support,vao,coverageTexture,snapshotTexture,disposed=false,last=null;
 const programs=new Map();
 const release=()=>{for(const record of programs.values())gl.deleteProgram(record.program);
  if(vao)gl.deleteVertexArray(vao);for(const texture of [coverageTexture,snapshotTexture])if(texture)gl.deleteTexture(texture);support?.dispose();};
 try{
  support=createSupportDistanceTextures(gl,entries,{capture,restore});
  for(const role of roles.filter(role=>entries.some(r=>r.role===role))){
   const program=qualityProgram(gl,buildQualityFragment(role));programs.set(role,
    {program,locations:Object.fromEntries(uniformKeys.map(key=>[key,gl.getUniformLocation(program,key)]))});
  }
  vao=gl.createVertexArray();coverageTexture=gl.createTexture();snapshotTexture=gl.createTexture();
  if(!vao||!coverageTexture||!snapshotTexture)throw Error('QUALITY_MATERIAL_RESOURCE_ALLOCATION');
  resetQualityPixels(gl);setupQualityTexture(gl,coverageTexture,0);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGBA8,width,height);
  setupQualityTexture(gl,snapshotTexture,1);gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGB8,width,height);
 }catch(error){release();throw error;}finally{restore(gl,before);}
 if(gl.getError()!==gl.NO_ERROR){release();throw Error('QUALITY_MATERIAL_RESOURCE_GL_ERROR');}
 const stats=support.fields.map(field=>field.statistics);
 const evidence={...clone(baseline.evidence),version:QUALITY_MATERIAL_VERSION,baselineMaterialVersion:baseline.evidence?.version,
  astra:{actualMaterialFactorySelected:true,uploadedTextureCount:entries.length*2,
   selectedSourceRoles:roles.filter(role=>entries.some(r=>r.role===role)),
   composition:'SOURCE_MATERIAL_BEFORE_TERRITORY_FRONTIER',sourceSampling:'NATIVE_TEXEL_FETCH_SOURCE_ROW_ORDER',
   partialCoverage:true,outsideOrInvalid:'UNCHANGED_BASELINE',outputTexture:'ACTUAL_COMBINED_RGB8_DEFAULT_FRAMEBUFFER',
   testOnly:uploads.testOnly===true,gpuRenderingVerified:false,renderAllowed:false,
   boundary:{enabled:true,screenFeatherPixels:q.screenFeatherPixels,sourceMasks:clone(stats),
    sourceValuesChanged:false,sourceCoordinatesChanged:false,nativeCoastCoverageFiltered:false,
    internalNoDataSupportDistance:true,sourceMaskReadback:'BOOLEAN_ONLY_FROM_AUTHENTIC_UPLOADED_RESOURCES'}}};
 return {evidence,get outputTexture(){if(disposed)throw Error('QUALITY_MATERIAL_DISPOSED');return snapshotTexture;},
  get snapshotFrame(){return clone(last);},draw(args={}){
   if(disposed)throw Error('QUALITY_MATERIAL_DISPOSED');
   const native=baseline.draw(args),state=capture(gl);let passes=0;
   try{
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);gl.viewport(0,0,width,height);
    for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD])gl.disable(cap);
    gl.colorMask(true,true,true,true);gl.bindVertexArray(vao);resetQualityPixels(gl);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);gl.bindSampler(0,null);
    gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,args.coverage);
    const snapshot=()=>{gl.activeTexture(gl.TEXTURE0+1);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);gl.bindSampler(1,null);
     gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);};snapshot();
    if(!args.rawSource)for(const field of support.fields){
     const entry=field.entry,{program,locations:l}=programs.get(entry.role);gl.useProgram(program);
     for(const [unit,texture,key] of [[0,snapshotTexture,'baselineTexture'],[1,coverageTexture,'coverageTexture'],
      [2,entry.values,'valuesTexture'],[3,entry.valid,'validTexture'],[4,field.texture,'distanceTexture']]){
      gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);gl.uniform1i(l[key],unit);}
     gl.uniform4fv(l.bounds,args.bounds);gl.uniform2fv(l.sourceOrigin,[entry.metadata.transform[0],entry.metadata.transform[3]]);
     gl.uniform2fv(l.sourceStep,[entry.metadata.transform[1],entry.metadata.transform[5]]);
     gl.uniform2f(l.screenDimensions,width,height);gl.uniform1f(l.screenFeatherPixels,q.screenFeatherPixels);
     for(const key of ['surfaceMix','surfaceGain','reliefStrength','depthMix','depthScaleMeters'])gl.uniform1f(l[key],profile[key]);
     gl.uniform3fv(l.warmHighlightColor,baselineProfile.warmHighlightColor);gl.uniform1f(l.warmHighlightStrength,baselineProfile.warmHighlightStrength);
     for(const key of ['nearshoreTint','midTint','deepTint'])gl.uniform3fv(l[key],baselineProfile.oceanProfile[key]);
     gl.drawArrays(gl.TRIANGLES,0,3);snapshot();passes++;
    }
   }finally{restore(gl,state);}
   const error=gl.getError();if(error!==gl.NO_ERROR)throw Error('QUALITY_MATERIAL_DRAW_GL_ERROR_'+error);
   last={...native,version:QUALITY_MATERIAL_VERSION,actualMaterialSnapshot:true,snapshotFormat:'RGB8',astra:{
    drawPasses:passes,selected:!args.rawSource&&entries.length>0,actualMaterialFactorySelected:true,uploadedTextureCount:entries.length*2,
    selectedSourceRoles:roles.filter(role=>entries.some(r=>r.role===role)),sourceMaterialBeforeTerritory:true,
    combinedOutputTexture:true,actualNativeCoverage:true,gpuUploadExecuted:uploads.gpuUploadExecuted===true,
    testOnly:uploads.testOnly===true,gpuRenderingVerified:false,renderAllowed:false,boundary:{enabled:true,
     screenFeatherPixels:q.screenFeatherPixels,sourceMasks:clone(stats),
     effectiveWeights:support.fields.map(field=>({role:field.entry.role,id:field.entry.id,
      ...effectiveFeather(field.entry.metadata,args.bounds,width,height,q.screenFeatherPixels)})),
     internalNoDataSupportDistance:true,nativeCoastCoverageFiltered:false,sourceValuesChanged:false}}};
   return clone(last);
  },dispose(){if(disposed)return;release();uploads.dispose();baseline.dispose();disposed=true;}};
}
