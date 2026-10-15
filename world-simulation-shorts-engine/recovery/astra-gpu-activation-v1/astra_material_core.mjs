/** ASTRA source-material stage. Runs before territory/frontier/presentation/artwork.
 * The caller owns the unchanged baseline factory and authentic upload resources.
 * No screen overlay, replacement camera, resampling grid or synthetic height.
 */
export const ASTRA_MATERIAL_VERSION='ASTRA_SOURCE_MATERIAL_V1';
export const DEFAULT_ASTRA_PROFILE=Object.freeze({surfaceMix:.85,surfaceGain:1,
 reliefStrength:.65,depthMix:.75,depthScaleMeters:4000,edgeFadeSourcePixels:1});
const ranges={surfaceMix:[0,1],surfaceGain:[.25,2],reliefStrength:[0,1],depthMix:[0,1],
 depthScaleMeters:[50,12000],edgeFadeSourcePixels:[0,4]};
const clone=value=>structuredClone(value);
const fail=code=>{throw Error(code);};
export function validateAstraProfile(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))fail('ASTRA_PROFILE_OBJECT_REQUIRED');
 for(const key of Object.keys(input))if(!Object.hasOwn(ranges,key))fail('ASTRA_PROFILE_UNKNOWN_'+key);
 const value={...DEFAULT_ASTRA_PROFILE,...clone(input)};
 for(const [key,[lo,hi]] of Object.entries(ranges))
  if(!Number.isFinite(value[key])||value[key]<lo||value[key]>hi)fail('ASTRA_PROFILE_RANGE_'+key);
 return Object.freeze(value);
}
/** CPU reference of EXACT shader cell selection: transform is pixel CORNER,
 * upload row0 is preserved, and texelFetch selects a native source cell. */
export function sourceCellAtGeo(part,geo){
 const t=part.transform,[w,h]=part.dimensions;
 if(!Array.isArray(geo)||geo.length!==2||!geo.every(Number.isFinite))fail('ASTRA_FINITE_GEO_REQUIRED');
 const x=(geo[0]-t[0])/t[1],y=(geo[1]-t[3])/t[5],i=Math.floor(x),j=Math.floor(y);
 return i<0||j<0||i>=w||j>=h?null:{i,j,index:j*w+i,cellPosition:[x,y]};
}
export function terrainNormalAtCell(part,values,valid,i,j){
 const [w,h]=part.dimensions,t=part.transform;
 if(i<1||j<1||i>=w-1||j>=h-1)return null;
 const ids=[j*w+i,j*w+i-1,j*w+i+1,(j-1)*w+i,(j+1)*w+i];
 if(ids.some(k=>valid[k]!==1||!Number.isFinite(values[k])))return null;
 const lat=t[3]+(j+.5)*t[5],cos=Math.cos(lat*Math.PI/180);
 if(cos<1e-4)return null;
 const dx=(values[ids[2]]-values[ids[1]])/(2*111319.49079327358*cos*t[1]);
 const dy=(values[ids[4]]-values[ids[3]])/(2*111319.49079327358*t[5]);
 const len=Math.hypot(dx,dy,1);return[-dx/len,-dy/len,1/len];
}
export function materialGate(role,coverage,value,valid){
 if(!Number.isFinite(coverage)||coverage<0||coverage>1)fail('ASTRA_GIS_COVERAGE_REQUIRED');
 if(valid!==1)return 0;
 if(role==='bathymetry')return Number.isFinite(value)&&value<0?1-coverage:0;
 if(!['surfaceTexture','terrain'].includes(role))fail('ASTRA_ROLE_REQUIRED');
 if(role==='terrain'&&!Number.isFinite(value))return 0;
 return coverage;
}
export const ASTRA_VERTEX_GLSL=`#version 300 es
precision highp float;out vec2 vUv;
void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));vUv=p;gl_Position=vec4(p*2.-1.,0.,1.);}`;
export function buildAstraFragment(role){
 if(!['terrain','bathymetry','surfaceTexture'].includes(role))fail('ASTRA_ROLE_REQUIRED');
 const sampler=role==='bathymetry'?'isampler2D':'sampler2D';
 let treatment;
 if(role==='surfaceTexture')treatment=`
 vec4 source=texelFetch(valuesTexture,p,0);
 if(source.a<=0.){frag=vec4(base,1.);return;}
 // Original encoded RGB, not a traced/reference image. Keep baseline palette
 // and colour variation; territory ownership is applied by the ORIGINAL pass.
 vec3 styled=source.rgb*surfaceGain;
 vec3 color=mix(base,clamp(styled,0.,.94),surfaceMix*land*support*source.a);
 frag=vec4(color,1.);`;
 if(role==='terrain')treatment=`
 // Five genuine valid neighbours are required. NoData never becomes sea/zero.
 ivec2 size=textureSize(valuesTexture,0);
 if(any(lessThan(p,ivec2(1)))||any(greaterThanEqual(p,size-ivec2(1)))){frag=vec4(base,1.);return;}
 ivec2 e=p+ivec2(1,0),w=p-ivec2(1,0),n=p+ivec2(0,1),s=p-ivec2(0,1);
 if(texelFetch(validTexture,e,0).r!=1u||texelFetch(validTexture,w,0).r!=1u||
    texelFetch(validTexture,n,0).r!=1u||texelFetch(validTexture,s,0).r!=1u){frag=vec4(base,1.);return;}
 float z=texelFetch(valuesTexture,p,0).r,ze=texelFetch(valuesTexture,e,0).r,
 zw=texelFetch(valuesTexture,w,0).r,zn=texelFetch(valuesTexture,n,0).r,zs=texelFetch(valuesTexture,s,0).r;
 if(isnan(z)||isinf(z)||isnan(ze)||isinf(ze)||isnan(zw)||isinf(zw)||
    isnan(zn)||isinf(zn)||isnan(zs)||isinf(zs)){frag=vec4(base,1.);return;}
 float latitude=sourceOrigin.y+(float(p.y)+.5)*sourceStep.y;
 float metricCos=cos(radians(latitude));
 if(metricCos<.0001){frag=vec4(base,1.);return;}
 vec2 gradient=vec2((ze-zw)/(222638.98158654716*metricCos*sourceStep.x),
                    (zn-zs)/(222638.98158654716*sourceStep.y));
 vec3 normal=normalize(vec3(-gradient,1.));
 // Height in metres and physical finite differences; not height-from-colour.
 vec3 light=normalize(vec3(-.45,.65,.62));
 float planar=max(light.z,.01),diffuse=max(dot(normal,light),0.);
 float illumination=clamp((.42+.58*diffuse)/(.42+.58*planar),.72,1.26);
 float altitude=clamp(z/5000.,-.2,1.);
 vec3 lit=base*illumination*(1.+.045*altitude);
 float warm=warmHighlightStrength*max(diffuse-planar,0.);
 lit+=warmHighlightColor*warm;
 frag=vec4(clamp(mix(base,lit,reliefStrength*land*support),0.,.94),1.);`;
 if(role==='bathymetry')treatment=`
 // Negative elevation is NOT the ocean mask. Native SAME-FRAME GIS must
 // identify an ocean fraction too; below-sea-level land remains land.
 float elevation=float(texelFetch(valuesTexture,p,0).r);
 if(elevation>=0.){frag=vec4(base,1.);return;}
 float depth=-elevation,t=clamp(log(1.+depth)/log(1.+depthScaleMeters),0.,1.);
 vec3 depthColor=t<.5?mix(nearshoreTint,midTint,t*2.):mix(midTint,deepTint,(t-.5)*2.);
 frag=vec4(clamp(mix(base,depthColor,depthMix*(1.-land)*support),0.,.94),1.);`;
 return `#version 300 es
precision highp float;precision highp int;precision highp usampler2D;precision highp isampler2D;
in vec2 vUv;out vec4 frag;
uniform sampler2D baselineTexture,coverageTexture;
uniform ${sampler} valuesTexture;uniform usampler2D validTexture;
uniform vec4 bounds;uniform vec2 sourceOrigin,sourceStep;
uniform float surfaceMix,surfaceGain,reliefStrength,depthMix,depthScaleMeters,edgeFadeSourcePixels;
uniform vec3 warmHighlightColor,nearshoreTint,midTint,deepTint;uniform float warmHighlightStrength;
void main(){
 vec3 base=texture(baselineTexture,vUv).rgb;
 float land=clamp(texture(coverageTexture,vUv).r,0.,1.);
 vec2 geo=mix(bounds.xy,bounds.zw,vUv);
 vec2 at=(geo-sourceOrigin)/sourceStep;ivec2 p=ivec2(floor(at));
 ivec2 dimensions=textureSize(valuesTexture,0);
 if(any(lessThan(p,ivec2(0)))||any(greaterThanEqual(p,dimensions))||
    texelFetch(validTexture,p,0).r!=1u){frag=vec4(base,1.);return;}
 // Only blend existing valid source data near its edge; no source value
 // interpolation, clamped outside sample or invented geographic support.
 float edge=min(min(at.x,at.y),min(float(dimensions.x)-at.x,float(dimensions.y)-at.y));
 float support=edgeFadeSourcePixels>0.?smoothstep(0.,edgeFadeSourcePixels,edge):1.;
 ${treatment}
}`;
}
function programFor(gl,role){
 const program=gl.createProgram(),shaders=[];
 if(!program)fail('ASTRA_PROGRAM_ALLOCATION');
 try{
  for(const [type,text] of [[gl.VERTEX_SHADER,ASTRA_VERTEX_GLSL],[gl.FRAGMENT_SHADER,buildAstraFragment(role)]]){
   const shader=gl.createShader(type);if(!shader)fail('ASTRA_SHADER_ALLOCATION');shaders.push(shader);
   gl.shaderSource(shader,text);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))fail('ASTRA_SHADER_COMPILE_'+role+'_'+gl.getShaderInfoLog(shader));
   gl.attachShader(program,shader);
  }
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))fail('ASTRA_PROGRAM_LINK_'+role+'_'+gl.getProgramInfoLog(program));
  return program;
 }catch(error){gl.deleteProgram(program);throw error;}
 finally{for(const shader of shaders)gl.deleteShader(shader);}
}
const rolesInOrder=['surfaceTexture','terrain','bathymetry'];
const uniforms=['baselineTexture','coverageTexture','valuesTexture','validTexture','bounds','sourceOrigin','sourceStep',
 ...Object.keys(DEFAULT_ASTRA_PROFILE),'warmHighlightColor','warmHighlightStrength','nearshoreTint','midTint','deepTint'];
/** The native factory is called ONCE by the decorator. Its exact frame GIS,
 * draw arguments and default framebuffer are reused; only this material output
 * snapshot is passed downstream. capture/restore are the original GL helpers. */
export function createAstraCompositionPass({gl,baseline,uploads,profile={},baselineProfile,width,height,capture,restore}={}){
 const p=validateAstraProfile(profile);
 if(!gl||!baseline||!uploads||!Array.isArray(uploads.resources)||typeof capture!=='function'||typeof restore!=='function')fail('ASTRA_COMPOSITION_BINDING_REQUIRED');
 if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<1||height<1)fail('ASTRA_DIMENSIONS_REQUIRED');
 if(uploads.resources.some(r=>!rolesInOrder.includes(r.role)))fail('ASTRA_ROLE_REQUIRED');
 const entries=rolesInOrder.flatMap(role=>uploads.resources.filter(r=>r.role===role)),state=capture(gl),programs=new Map();
 let vao,coverageTexture,snapshotTexture,disposed=false,last=null;
 const release=()=>{for(const record of programs.values())gl.deleteProgram(record.program);
  if(vao)gl.deleteVertexArray(vao);for(const tex of [coverageTexture,snapshotTexture])if(tex)gl.deleteTexture(tex);};
 try{
  for(const role of rolesInOrder.filter(role=>entries.some(r=>r.role===role))){
   const program=programFor(gl,role);programs.set(role,{program,locations:Object.fromEntries(uniforms.map(key=>[key,gl.getUniformLocation(program,key)]))});
  }
  vao=gl.createVertexArray();coverageTexture=gl.createTexture();snapshotTexture=gl.createTexture();
  if(!vao||!coverageTexture||!snapshotTexture)fail('ASTRA_RESOURCE_ALLOCATION');
  gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);resetUnpack(gl);
  for(const [unit,texture] of [[0,coverageTexture],[1,snapshotTexture]]){
   gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);
   for(const key of ['TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.NEAREST);
   for(const key of ['TEXTURE_WRAP_S','TEXTURE_WRAP_T'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.CLAMP_TO_EDGE);
  }
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGBA8,width,height);
  gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);
  gl.texStorage2D(gl.TEXTURE_2D,1,gl.RGB8,width,height);
 }catch(error){release();throw error;}finally{restore(gl,state);}
 if(gl.getError()!==gl.NO_ERROR){release();fail('ASTRA_RESOURCE_GL_ERROR');}
 const evidence={...clone(baseline.evidence),version:ASTRA_MATERIAL_VERSION,baselineMaterialVersion:baseline.evidence?.version,
  astra:{actualMaterialFactorySelected:true,uploadedTextureCount:entries.length*2,
   selectedSourceRoles:rolesInOrder.filter(role=>entries.some(r=>r.role===role)),
   composition:'SOURCE_MATERIAL_BEFORE_TERRITORY_FRONTIER',sourceSampling:'NATIVE_TEXEL_FETCH_SOURCE_ROW_ORDER',
   physicalElevationLightingUsed:entries.some(r=>r.role==='terrain'),heightFromColor:false,sourceValueInterpolation:false,
   oceanMask:'UNCHANGED_SAME_FRAME_NATIVE_GIS_FRACTIONAL_LAND_COVERAGE',negativeElevationIsOceanMask:false,
   partialCoverage:true,outsideOrInvalid:'UNCHANGED_BASELINE',outputTexture:'ACTUAL_COMBINED_RGB8_DEFAULT_FRAMEBUFFER',
   profile:clone(p),parts:entries.map(r=>({role:r.role,id:r.id,bbox:clone(r.metadata.bbox),dimensions:clone(r.metadata.dimensions),
    transform:clone(r.metadata.transform),sourceValueBytesSHA256:r.metadata.sourceValueBytesSHA256})),
   testOnly:uploads.testOnly===true,gpuRenderingVerified:false,renderAllowed:false,actualHardwareVisualReviewRequired:true}};
 return {evidence,get outputTexture(){if(disposed)fail('ASTRA_DISPOSED');return snapshotTexture;},
  get snapshotFrame(){return clone(last);},
  draw(args={}){
   if(disposed)fail('ASTRA_DISPOSED');
   // Baseline validates source bounds, canonical coverage/frame and raw flag.
   const native=baseline.draw(args),before=capture(gl);let passes=0;
   try{
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);gl.drawBuffers([gl.BACK]);
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER,null);gl.readBuffer(gl.BACK);gl.viewport(0,0,width,height);
    for(const cap of [gl.BLEND,gl.CULL_FACE,gl.DEPTH_TEST,gl.SCISSOR_TEST,gl.STENCIL_TEST,gl.RASTERIZER_DISCARD])gl.disable(cap);
    gl.colorMask(true,true,true,true);gl.bindVertexArray(vao);
    gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);resetUnpack(gl);
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,coverageTexture);gl.bindSampler(0,null);
    gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,args.coverage);
    const snapshot=()=>{gl.activeTexture(gl.TEXTURE0+1);gl.bindTexture(gl.TEXTURE_2D,snapshotTexture);gl.bindSampler(1,null);
     gl.copyTexSubImage2D(gl.TEXTURE_2D,0,0,0,0,0,width,height);};
    snapshot();
    // Raw diagnostic source is intentionally baseline-only; no ASTRA pass.
    if(!args.rawSource)for(const entry of entries){
     const {program,locations:l}=programs.get(entry.role);gl.useProgram(program);
     for(const [unit,texture,key] of [[0,snapshotTexture,'baselineTexture'],[1,coverageTexture,'coverageTexture'],
      [2,entry.values,'valuesTexture'],[3,entry.valid,'validTexture']]){
      gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindSampler(unit,null);gl.uniform1i(l[key],unit);
     }
     gl.uniform4fv(l.bounds,args.bounds);gl.uniform2fv(l.sourceOrigin,[entry.metadata.transform[0],entry.metadata.transform[3]]);
     gl.uniform2fv(l.sourceStep,[entry.metadata.transform[1],entry.metadata.transform[5]]);
     for(const [key,value] of Object.entries(p))gl.uniform1f(l[key],value);
     gl.uniform3fv(l.warmHighlightColor,baselineProfile.warmHighlightColor);
     gl.uniform1f(l.warmHighlightStrength,baselineProfile.warmHighlightStrength);
     for(const key of ['nearshoreTint','midTint','deepTint'])gl.uniform3fv(l[key],baselineProfile.oceanProfile[key]);
     gl.drawArrays(gl.TRIANGLES,0,3);snapshot();passes++;
    }
   }finally{restore(gl,before);}
   const code=gl.getError();if(code!==gl.NO_ERROR)fail('ASTRA_DRAW_GL_ERROR_'+code);
   last={...native,version:ASTRA_MATERIAL_VERSION,baselineMaterialVersion:native.version,
    actualMaterialSnapshot:true,snapshotFormat:'RGB8',astra:{drawPasses:passes,selected:!args.rawSource&&entries.length>0,
     actualMaterialFactorySelected:true,uploadedTextureCount:entries.length*2,
     selectedSourceRoles:rolesInOrder.filter(role=>entries.some(r=>r.role===role)),
     sourceMaterialBeforeTerritory:true,combinedOutputTexture:true,actualNativeCoverage:true,
     gpuUploadExecuted:uploads.gpuUploadExecuted===true,testOnly:uploads.testOnly===true,gpuRenderingVerified:false,renderAllowed:false}};
   return clone(last);
  },dispose(){if(disposed)return;release();uploads.dispose();baseline.dispose();disposed=true;}};
}
function resetUnpack(gl){
 gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
 for(const key of ['UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT',
  'UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES'])gl.pixelStorei(gl[key],0);
 gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);
}
