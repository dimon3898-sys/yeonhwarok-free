import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateReferenceFrontierProfile,applyReferenceFrontierStyle,assertOuterDomainContext,
 sampleOuterDomainResponse,outerGoldScreenBlend} from '../frontier_profile_core.mjs';
import {createCoverageOuterGlowPass,OUTER_DOMAIN_GOLD_FRAGMENT} from '../coverage_outer_glow.mjs';
import {createNativeDomainBinding,describeNativeDomainBinding,publishNativeDomainCoverage,getNativeDomainCoverage}
 from '../native_domain_coverage.mjs';
import {validateControlFrontierLightProfile} from '../../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
const source={profileName:'PRESERVED',centerColor:[1,.985,.94],haloColor:[1,.7,.25],centerWidthPixels:2.5,
 haloSigmaPixels:3.5,haloSupportPixels:10,centerAlpha:1,haloAlpha:.35,settledStrength:.08,velocityWindowFrames:12,
 luminanceAnchor:.36,minimumLightingFactor:.83,reliefLightingEnabled:true};
const enabled={enabled:true},domainInput=()=>{
 const make=(id,w,e)=>({id,geometry:{type:'Polygon',coordinates:[[[w,0],[e,0],[e,1],[w,1],[w,0]]]}}),
  domain=[make('ROLE_A',0,1),make('ROLE_B',1,2)];
 return {primary:'ROLE_A',secondary:['ROLE_B'],geometries:domain.map(x=>({id:x.id,geometry_type:x.geometry.type,coordinates:structuredClone(x.geometry.coordinates)})),domain};
};
test('expression profile is disabled by default and rejects unbounded/original API bypass controls',()=>{
 assert.equal(validateReferenceFrontierProfile().enabled,false);
 for(const value of [{frontierWidth:2.51},{frontierHaloSigma:4.01},{outerGoldSupport:7},{outerGoldIntensity:1.1},
  {minimumLightingFactor:.2},{outerGoldSupport:4,outerGoldSigma:4},{ignoreDomain:true},{country:'X'},{enabled:1}])
  assert.throws(()=>validateReferenceFrontierProfile(value));
});
test('selected original white style remains inside original public validator and preserves motion/geometry settings',()=>{
 const before=structuredClone(source),out=applyReferenceFrontierStyle(source,enabled);
 assert.deepEqual(source,before);assert.deepEqual(out.centerColor,[1,1,1]);assert.deepEqual(out.haloColor,[1,1,1]);
 assert.equal(out.minimumLightingFactor,.76);assert.doesNotThrow(()=>validateControlFrontierLightProfile(out));
 for(const key of ['velocityWindowFrames','settledStrength','haloSupportPixels','luminanceAnchor','reliefLightingEnabled'])assert.equal(out[key],source[key]);
 assert.deepEqual(applyReferenceFrontierStyle(source),source);
});
test('actual adjacent native role union cancels the shared internal border and ignores unrelated R-only land',async()=>{
 const canvas={},token=await createNativeDomainBinding(domainInput()),width=64,height=32,coverage=new Uint8Array(width*height*4);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const p=(y*width+x)*4;coverage[p]=255;
  if(x>=4&&x<=59&&y>=4&&y<=27)coverage[p+(x<=31?2:1)]=255;
 }
 const before=coverage.slice();publishNativeDomainCoverage(canvas,token,{coverage,bounds:[0,0,2,1],frame:3,width,height});
 const context=getNativeDomainCoverage(canvas,{frame:3,domainSHA256:token.domainSHA256});
 assert.deepEqual(coverage,before);
 for(const x of [31,32])assert.deepEqual(sampleOuterDomainResponse(context.domainCoverage,width,height,x,16,enabled),{core:0,halo:0});
 assert.ok(sampleOuterDomainResponse(context.domainCoverage,width,height,4,16,enabled).core>.99);
 assert.deepEqual(sampleOuterDomainResponse(context.domainCoverage,width,height,0,0,enabled),{core:0,halo:0});
});
test('solid viewport-clipped union has no fabricated image-border coastline and rounding noise creates no internal outline',()=>{
 const solid=new Uint8Array(64*32).fill(255);
 for(const [x,y] of [[0,0],[63,0],[0,31],[63,31],[30,16]])assert.deepEqual(sampleOuterDomainResponse(solid,64,32,x,y,enabled),{core:0,halo:0});
 solid[16*64+31]=254;solid[16*64+32]=253;
 assert.deepEqual(sampleOuterDomainResponse(solid,64,32,31,16,enabled),{core:0,halo:0});
});
test('finite outer halo is zero beyond support, is monotone locally and never mutates mask bytes',()=>{
 const width=40,height=32,mask=new Uint8Array(width*height);for(let y=0;y<height;y++)for(let x=20;x<width;x++)mask[y*width+x]=255;
 const before=mask.slice(),values=[19,18,16,14,12].map(x=>sampleOuterDomainResponse(mask,width,height,x,16,enabled).halo);
 assert.ok(values[0]>values[1]&&values[1]>values[2]&&values[2]>values[3]);assert.equal(values[4],0);assert.deepEqual(mask,before);
});
test('screen blend preserves pure white original front exactly and cannot darken existing terrain',()=>{
 assert.deepEqual(outerGoldScreenBlend([1,1,1],{core:1,halo:1},enabled),[1,1,1]);
 const color=[.2,.4,.7],out=outerGoldScreenBlend(color,{core:.4,halo:.8},enabled);
 assert.ok(out.every((v,i)=>v>=color[i]&&v<=1));assert.deepEqual(outerGoldScreenBlend(color,{core:0,halo:0},enabled),color);
 assert.deepEqual(outerGoldScreenBlend(color,{core:1,halo:1}),color);
});
test('same frame, exact domain geometry, source-role binding and actual projection are mandatory',async()=>{
 const canvas={},binding=await createNativeDomainBinding(domainInput()),meta=describeNativeDomainBinding(binding),
  width=4,height=4,bytes=new Uint8Array(width*height*4),bounds=[0,0,2,1];
 publishNativeDomainCoverage(canvas,binding,{coverage:bytes,bounds,frame:3,width,height});
 const context=getNativeDomainCoverage(canvas,{frame:3,domainSHA256:binding.domainSHA256}),
  args={controls:{frame:3,localFrame:3},domainMetadata:meta,width,height,project:p=>[p[0]/2*4,(1-p[1])*4]};
 assert.equal(assertOuterDomainContext(context,args),true);
 assert.throws(()=>assertOuterDomainContext({...context,frame:2},args),/SAME_FRAME/);
 assert.throws(()=>assertOuterDomainContext({...context,domainSHA256:'0'.repeat(64)},args),/DOMAIN_BINDING/);
 assert.throws(()=>assertOuterDomainContext({...context,sourceGeometrySHA256:'0'.repeat(64)},args),/DOMAIN_BINDING/);
 assert.throws(()=>assertOuterDomainContext(context,{...args,project:p=>[p[0]/2*4+1,(1-p[1])*4]}),/PROJECTION_MISMATCH/);
});
test('new wrapper delegates original by exact alias, validates context before original draw, and adds no geometry or route',async()=>{
 const wrapper=await readFile(new URL('../frontier_ref2.mjs',import.meta.url),'utf8');
 assert.match(wrapper,/from '\/modules\/reference_control_frontier_light_v3.mjs\?baseline'/);
 assert.match(wrapper,/if\(!selected.enabled\)return createOriginal\(options\)/);
 assert.ok(wrapper.indexOf('assertOuterDomainContext(context')<wrapper.indexOf('const diagnostic=original.draw(args)'));
 assert.match(wrapper,/gold\?\.draw/);assert.doesNotMatch(wrapper,/boundaryLatitudes\s*=|camera\.position|lineTo\(|new THREE/);
 assert.match(OUTER_DOMAIN_GOLD_FRAGMENT,/ring<4/);assert.match(OUTER_DOMAIN_GOLD_FRAGMENT,/clamp\(p,ivec2\(0\)/);
 assert.match(OUTER_DOMAIN_GOLD_FRAGMENT,/reservationCount/);assert.doesNotMatch(OUTER_DOMAIN_GOLD_FRAGMENT,/actualTerrain|sourceTexture|screenImage|route|arrow/i);
});

function fakeGl(){
 const gl={events:[],error:0,deleted:[],state:{tag:'ORIGINAL'}};let i=0;
 for(const key of ['TEXTURE_2D','R8','DRAW_FRAMEBUFFER','BACK','DEPTH_TEST','STENCIL_TEST','CULL_FACE','SCISSOR_TEST',
  'POLYGON_OFFSET_FILL','RASTERIZER_DISCARD','SAMPLE_ALPHA_TO_COVERAGE','SAMPLE_COVERAGE','DITHER','TEXTURE0',
  'RED','UNSIGNED_BYTE','BLEND','FUNC_ADD','ONE','ONE_MINUS_SRC_COLOR','ZERO','TRIANGLES'])gl[key]=++i;
 gl.NO_ERROR=0;gl.createTexture=()=>({texture:true});gl.createVertexArray=()=>({vao:true});gl.getUniformLocation=(_p,key)=>key;
 for(const key of ['bindFramebuffer','drawBuffers','viewport','disable','depthMask','colorMask','useProgram','bindVertexArray','activeTexture','bindTexture','bindSampler','uniform1i','uniform1f','uniform2f','uniform3fv','uniform4fv','enable','blendEquationSeparate','blendFuncSeparate','texStorage2D'])
  gl[key]=(...args)=>{gl.events.push({name:key,args});gl.state={tag:key};};
 gl.texSubImage2D=(...args)=>gl.events.push({name:'upload',args});gl.drawArrays=(...args)=>gl.events.push({name:'draw',args});
 for(const key of ['deleteProgram','deleteTexture','deleteVertexArray'])gl[key]=value=>gl.deleted.push([key,value]);
 gl.getError=()=>{const value=gl.error;gl.error=0;return value;};return gl;
}
test('CPU mock verifies single bounded draw, R8 original-union upload, screen blend, reservations and full state restoration',()=>{
 const gl=fakeGl(),profile=enabled,capture=()=>structuredClone(gl.state),restore=(_gl,state)=>{gl.state=state;},
  pass=createCoverageOuterGlowPass({gl,profile,capture,restore,programFactory:()=>({program:true}),resetPixels:()=>{},setupTexture:()=>{}}),
  context={domainCoverage:new Uint8Array(1080*1920),width:1080,height:1920,rowZero:'SOUTH',frame:7,nativeFrame:7,
   domainSHA256:'a'.repeat(64),sourceGeometrySHA256:'b'.repeat(64),bounds:[0,0,2,1]},before=structuredClone(gl.state),
  result=pass.draw({context,presentationScale:1.08,protectedGraphics:[{box:[10,10,30,30]}]});
 assert.deepEqual(gl.state,before);assert.equal(gl.events.filter(x=>x.name==='draw').length,1);
 assert.equal(gl.events.find(x=>x.name==='upload').args.at(-1),context.domainCoverage);
 assert.deepEqual(gl.events.find(x=>x.name==='blendFuncSeparate').args,[gl.ONE,gl.ONE_MINUS_SRC_COLOR,gl.ZERO,gl.ONE]);
 assert.equal(result.sourceCoverageNeighborTaps,16);assert.equal(result.protectedReservations,1);assert.equal(result.allLandRChannelUsed,false);
 assert.throws(()=>pass.draw({context:{...context,rowZero:'NORTH'},presentationScale:1}),/ACTUAL_FRAME/);
 pass.dispose();assert.equal(gl.deleted.length,3);assert.throws(()=>pass.draw({context,presentationScale:1}),/DISPOSED/);
});
