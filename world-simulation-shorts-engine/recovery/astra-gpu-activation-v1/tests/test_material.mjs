import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {DEFAULT_ASTRA_PROFILE,validateAstraProfile,sourceCellAtGeo,terrainNormalAtCell,materialGate,
 buildAstraFragment,createAstraCompositionPass} from '../astra_material_core.mjs';

const part=(northUp=true)=>({dimensions:[5,5],bbox:[-2,-2,3,3],transform:northUp?[-2,1,0,3,0,-1]:[-2,1,0,-2,0,1],
 sourceValueBytesSHA256:'a'.repeat(64)});
const baselineProfile={warmHighlightColor:[1,.72,.32],warmHighlightStrength:.15,
 oceanProfile:{nearshoreTint:[.12,.35,.4],midTint:[.07,.24,.32],deepTint:[.04,.1,.18]}};
function fakeGl(){
 let constant=0,id=0;
 const gl={events:[],state:{active:100,bindings:{},program:null,vao:null,frame:'native',pixels:{}},error:0,
  resources:[],deleted:[],failCompile:false,frameContent:'baseline'};
 for(const name of ['VERTEX_SHADER','FRAGMENT_SHADER','COMPILE_STATUS','LINK_STATUS','PIXEL_UNPACK_BUFFER','TEXTURE_2D',
 'TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER','TEXTURE_WRAP_S','TEXTURE_WRAP_T','NEAREST','CLAMP_TO_EDGE','RGBA8','RGB8',
 'UNPACK_ALIGNMENT','UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT',
 'UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES','UNPACK_COLORSPACE_CONVERSION_WEBGL','DRAW_FRAMEBUFFER',
 'READ_FRAMEBUFFER','BACK','BLEND','CULL_FACE','DEPTH_TEST','SCISSOR_TEST','STENCIL_TEST','RASTERIZER_DISCARD','RGBA',
 'UNSIGNED_BYTE','TRIANGLES'])gl[name]=++constant;
 gl.TEXTURE0=100;gl.NO_ERROR=0;gl.NONE=0;
 for(const [name,type] of [['createTexture','texture'],['createShader','shader'],['createProgram','program'],['createVertexArray','vao']])
  gl[name]=()=>{const resource={id:++id,type};gl.resources.push(resource);return resource;};
 gl.shaderSource=(shader,source)=>shader.source=source;
 gl.compileShader=()=>{};gl.getShaderParameter=()=>!gl.failCompile;gl.getShaderInfoLog=()=> 'CPU_TEST_COMPILER_FAILURE';
 gl.attachShader=(program,shader)=>{if(shader.source.includes('uniform sampler2D baselineTexture')){
  program.role=shader.source.includes('Negative elevation is NOT')?'bathymetry':shader.source.includes('Five genuine')?'terrain':'surfaceTexture';
 }};
 gl.linkProgram=()=>{};gl.getProgramParameter=()=>true;gl.getProgramInfoLog=()=>'';
 gl.getUniformLocation=(_program,key)=>key;
 for(const [name,type] of [['deleteTexture','texture'],['deleteShader','shader'],['deleteProgram','program'],['deleteVertexArray','vao']])
  gl[name]=value=>gl.deleted.push({type,value});
 gl.activeTexture=unit=>gl.state.active=unit;
 gl.bindTexture=(_target,tex)=>gl.state.bindings[gl.state.active]=tex;
 gl.bindSampler=(unit,value)=>gl.state['sampler'+unit]=value;
 gl.bindBuffer=(target,value)=>gl.state['buffer'+target]=value;
 gl.pixelStorei=(key,value)=>gl.state.pixels[key]=value;
 gl.texParameteri=()=>{};gl.texStorage2D=(_target,_levels,format,w,h)=>{
  Object.assign(gl.state.bindings[gl.state.active],{format,w,h});};
 gl.bindFramebuffer=(target,value)=>gl.state['fbo'+target]=value;
 for(const key of ['drawBuffers','readBuffer','viewport','disable','colorMask'])gl[key]=(...args)=>gl.state[key]=args;
 gl.bindVertexArray=vao=>gl.state.vao=vao;gl.useProgram=program=>gl.state.program=program;
 for(const key of ['uniform1i','uniform1f','uniform2fv','uniform3fv','uniform4fv'])gl[key]=()=>{};
 gl.texSubImage2D=(...args)=>{gl.events.push({event:'coverage',bytes:args.at(-1)});};
 gl.copyTexSubImage2D=()=>{const texture=gl.state.bindings[gl.state.active];texture.content=gl.frameContent;
  gl.events.push({event:'snapshot',texture,content:texture.content});};
 gl.drawArrays=()=>{const role=gl.state.program.role,input=gl.state.bindings[100];
  gl.frameContent=input.content+'->'+role;gl.events.push({event:'draw',role,input:input.content});};
 gl.getError=()=>{const code=gl.error;gl.error=0;return code;};
 return gl;
}
function fixture(roles=['terrain','bathymetry','surfaceTexture']){
 const gl=fakeGl(),nativeTexture={native:true},calls={baselineDraw:0,baselineDispose:0,uploadDispose:0};
 const baseline={evidence:{version:'ORIGINAL_V4'},outputTexture:nativeTexture,
  draw(args){calls.baselineDraw++;gl.events.push({event:'baseline',args});gl.frameContent='baseline';
   return {version:'ORIGINAL_V4',frame:args.frame,bounds:args.bounds};},dispose(){calls.baselineDispose++;}};
 const uploads={testOnly:true,gpuUploadExecuted:false,resources:roles.map((role,i)=>({role,id:'source_'+i,
  values:{id:'values_'+i},valid:{id:'valid_'+i},metadata:part()})),dispose(){calls.uploadDispose++;}};
 // This explicit fake isolates API ordering; it does not compile GLSL or prove
 // actual WebGL/NVIDIA pixels. Real adapter uses original full native helpers.
 const capture=()=>({...gl.state,bindings:{...gl.state.bindings},pixels:{...gl.state.pixels}});
 const restore=(_gl,state)=>{gl.state=state;};
 return {gl,baseline,uploads,calls,capture,restore,options:{gl,baseline,uploads,baselineProfile,width:3,height:5,capture,restore}};
}
const drawArgs=()=>({bounds:[-1,-1,1,1],coverage:new Uint8Array(3*5*4),frame:5,fps:30});

test('profile accepts bounded generic controls, rejects scene/camera/unsupported switches',()=>{
 assert.deepEqual(validateAstraProfile(),DEFAULT_ASTRA_PROFILE);
 for(const input of [{depthMix:2},{surfaceGain:0},{reliefStrength:NaN},{edgeFadeSourcePixels:-1},
  {country:'fixture'},{ignoreNoData:true},{forceOcean:true},{cameraZoom:2}])assert.throws(()=>validateAstraProfile(input));
});
test('source centers retain north-up half-pixel and original row zero',()=>{
 const p=part();assert.deepEqual(sourceCellAtGeo(p,[-1.5,2.5]),{i:0,j:0,index:0,cellPosition:[.5,.5]});
 assert.deepEqual(sourceCellAtGeo(p,[2.5,-1.5]),{i:4,j:4,index:24,cellPosition:[4.5,4.5]});
});
test('south-up source is not silently flipped; source edge/outside uses fallback',()=>{
 const p=part(false);assert.equal(sourceCellAtGeo(p,[-1.5,-1.5]).index,0);
 assert.equal(sourceCellAtGeo(p,[2.5,2.5]).index,24);
 for(const geo of [[-2.001,0],[3,0],[0,3],[0,-2.001]])assert.equal(sourceCellAtGeo(p,geo),null);
});
test('arbitrary Western/Southern source transforms use same cell mapping',()=>{
 const p={dimensions:[3,2],transform:[-123,.02,0,-35,0,-.02]};
 assert.equal(sourceCellAtGeo(p,[-122.99,-35.01]).index,0);
 assert.equal(sourceCellAtGeo(p,[-122.95,-35.03]).index,5);
});
test('native height/validity arrays are not mutated and all five DEM neighbours are mandatory',()=>{
 const p=part(),values=new Float32Array(25).fill(120),valid=new Uint8Array(25).fill(1),before=values.slice();
 assert.ok(terrainNormalAtCell(p,values,valid,2,2).every((value,index)=>Math.abs(value-[0,0,1][index])<1e-12));
 for(const i of [11,13,7,17,12]){valid[i]=0;assert.equal(terrainNormalAtCell(p,values,valid,2,2),null);valid[i]=1;}
 values[7]=NaN;assert.equal(terrainNormalAtCell(p,values,valid,2,2),null);values[7]=120;
 assert.equal(terrainNormalAtCell(p,values,valid,0,2),null);assert.deepEqual(values,before);
});
test('physical normal uses true metres, geographic latitude, signed source row direction',()=>{
 const values=new Float32Array(25),valid=new Uint8Array(25).fill(1);
 for(const northUp of [true,false]){
  const p=part(northUp);for(let j=0;j<5;j++)for(let i=0;i<5;i++)values[j*5+i]=i*100+(northUp?-j:j)*50;
  const normal=terrainNormalAtCell(p,values,valid,2,2);
  assert.ok(normal[0]<0&&normal[1]<0&&normal[2]>.99);
 }
 const polar={...part(),transform:[0,.001,0,90.0025,0,-.001]};
 assert.equal(terrainNormalAtCell(polar,values,valid,2,2),null);
});
test('fractional native GIS land coverage gates each source without sign-derived ocean',()=>{
 assert.equal(materialGate('terrain',.25,-30,1),.25);
 assert.equal(materialGate('surfaceTexture',.25,10,1),.25);
 assert.equal(materialGate('bathymetry',.25,-300,1),.75);
 assert.equal(materialGate('bathymetry',1,-300,1),0);
 assert.equal(materialGate('bathymetry',0,25,1),0);
 assert.equal(materialGate('bathymetry',0,-32768,0),0);
 assert.equal(materialGate('terrain',1,20,0),0);
 assert.equal(materialGate('terrain',1,NaN,1),0);
});
test('shader binds exact source transform and texelFetch validity instead of interpolated/noData zero',()=>{
 for(const role of ['terrain','bathymetry','surfaceTexture']){
  const src=buildAstraFragment(role);
  assert.match(src,/geo=mix\(bounds.xy,bounds.zw,vUv\)/);
  assert.match(src,/at=\(geo-sourceOrigin\)\/sourceStep/);
  assert.match(src,/texelFetch\(validTexture,p,0\).r!=1u/);
  assert.doesNotMatch(src,/texture\(valuesTexture|clamp\(p,|discard|gl_FragDepth/);
 }
 assert.match(buildAstraFragment('bathymetry'),/isampler2D valuesTexture/);
 assert.match(buildAstraFragment('bathymetry'),/depthMix\*\(1.-land\)\*support/);
 assert.match(buildAstraFragment('terrain'),/metricCos\*sourceStep.x/);
});
test('actual combined RGB8 source snapshot follows baseline then surface/terrain/depth',()=>{
 const f=fixture(),pass=createAstraCompositionPass(f.options),args=drawArgs();
 const saved={...f.gl.state,bindings:{...f.gl.state.bindings},pixels:{...f.gl.state.pixels}};
 assert.notEqual(pass.outputTexture,f.baseline.outputTexture);
 assert.equal(pass.outputTexture.format,f.gl.RGB8);
 const result=pass.draw(args);
 assert.equal(pass.outputTexture.content,'baseline->surfaceTexture->terrain->bathymetry');
 assert.deepEqual(f.gl.events.filter(e=>['baseline','draw'].includes(e.event)).map(e=>e.role??e.event),
  ['baseline','surfaceTexture','terrain','bathymetry']);
 assert.equal(f.gl.events.find(e=>e.event==='coverage').bytes,args.coverage);
 assert.equal(result.astra.drawPasses,3);assert.equal(result.astra.combinedOutputTexture,true);
 assert.equal(result.astra.gpuRenderingVerified,false);assert.equal(result.astra.testOnly,true);
 assert.equal(result.astra.gpuUploadExecuted,false);
 assert.deepEqual(f.gl.state,saved);assert.equal(f.calls.baselineDraw,1);
});
test('raw source diagnostic skips ASTRA and returns same-frame original snapshot',()=>{
 const f=fixture(),pass=createAstraCompositionPass(f.options),result=pass.draw({...drawArgs(),rawSource:true});
 assert.equal(pass.outputTexture.content,'baseline');assert.equal(result.astra.drawPasses,0);
 assert.equal(result.astra.selected,false);assert.equal(f.calls.baselineDraw,1);
});
test('unavailable role is omitted explicitly, never an invented texture',()=>{
 const f=fixture(['surfaceTexture']),pass=createAstraCompositionPass(f.options);
 assert.deepEqual(pass.evidence.astra.selectedSourceRoles,['surfaceTexture']);
 assert.equal(pass.evidence.astra.physicalElevationLightingUsed,false);
 pass.draw(drawArgs());assert.equal(pass.outputTexture.content,'baseline->surfaceTexture');
});
test('draw errors restore caller state and do not publish a successful snapshot frame',()=>{
 const f=fixture(),pass=createAstraCompositionPass(f.options),saved=f.capture();
 f.gl.error=1282;assert.throws(()=>pass.draw(drawArgs()),/ASTRA_DRAW_GL_ERROR_1282/);
 assert.equal(pass.snapshotFrame,null);assert.deepEqual(f.gl.state,saved);
});
test('shader errors release owned construction resources and original state',()=>{
 const f=fixture();f.gl.failCompile=true;const saved=f.gl.state;
 assert.throws(()=>createAstraCompositionPass(f.options),/ASTRA_SHADER_COMPILE/);
 assert.ok(f.gl.deleted.some(x=>x.type==='program'));assert.ok(f.gl.deleted.some(x=>x.type==='shader'));
 assert.deepEqual(f.gl.state,saved);
});
test('idempotent dispose releases ASTRA plus original pass and forbids stale texture/draw',()=>{
 const f=fixture(),pass=createAstraCompositionPass(f.options);pass.dispose();pass.dispose();
 assert.equal(f.calls.baselineDispose,1);assert.equal(f.calls.uploadDispose,1);
 assert.equal(f.gl.deleted.filter(x=>x.type==='texture').length,2);
 assert.throws(()=>pass.draw(drawArgs()),/ASTRA_DISPOSED/);assert.throws(()=>pass.outputTexture,/ASTRA_DISPOSED/);
});
test('snapshot metadata cannot mutate future frames; no FINAL or hardware quality assertion',()=>{
 const f=fixture(),pass=createAstraCompositionPass(f.options),result=pass.draw(drawArgs());
 result.bounds[0]=99;result.astra.selectedSourceRoles.push('invented');
 assert.equal(pass.snapshotFrame.bounds[0],-1);assert.equal(pass.snapshotFrame.astra.selectedSourceRoles.length,3);
 assert.equal(pass.evidence.astra.actualHardwareVisualReviewRequired,true);
 assert.equal(pass.evidence.astra.gpuRenderingVerified,false);
});
test('standard import-map wrapper selects original V4 factory bytes with query bypass',async()=>{
 const src=await readFile(new URL('../astra_material.mjs',import.meta.url),'utf8');
 assert.match(src,/from '\/modules\/reference_terrain_material_v4.mjs\?baseline'/);
 assert.match(src,/const baseline=await createBaseline\(options\)/);
 assert.match(src,/createUploadTextures\(gl,configuration.bundle/);
 assert.match(src,/createAstraCompositionPass\(/);
 assert.match(src,/new WeakMap\(\)/);assert.doesNotMatch(src,/dem\s*:|camera\.position|frontier\s*=|territory\s*=/);
});
