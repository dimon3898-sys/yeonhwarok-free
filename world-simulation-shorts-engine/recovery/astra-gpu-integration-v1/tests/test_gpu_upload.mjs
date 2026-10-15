/** Explicit CPU fake-context tests. None certifies WebGL, NVIDIA, pixels or material quality. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {loadUploadBundle,describeUploadBundle,createUploadTextures,planScreenDepthSampling} from '../gpu_upload.mjs';
const sha=value=>createHash('sha256').update(value).digest('hex');
const json=value=>new TextEncoder().encode(JSON.stringify(value));
const zero='0'.repeat(64),one='1'.repeat(64),two='2'.repeat(64);
function fixture(){
 const manifest={schema:'ASTRA_GPU_UPLOAD_BUNDLE_V1',enabled:true,rendererPayloadSHA256:zero,
  gpuUploadExecuted:false,gpuRenderingVerified:false,targetAPI:'WEBGL2_UPLOAD_CONTRACT_UNVERIFIED',
  sampling:{filter:'NEAREST',texelFetch:true,unpackAlignment:1,flipY:false,mipmaps:false,rowOrder:'SOURCE_PRESERVED'},sources:{},artifacts:[]};
 const artifacts=new Map();
 const ref=(id,kind,value)=>{const bytes=new Uint8Array(value.buffer.slice(value.byteOffset,value.byteOffset+value.byteLength)),
  item={file:`${id}.${kind}.bin`,bytes:bytes.byteLength,sha256:sha(bytes),kind};artifacts.set(item.file,bytes);manifest.artifacts.push(item);return {...item};};
 for(const [role,dtype,values,valid,step,quantity,format] of [
  ['terrain','<f4',new Float32Array([100,NaN,-30,-9999]),[1,0,1,0],-1,'HEIGHT',{internalFormat:'R32F',format:'RED',type:'FLOAT',sampler:'sampler2D'}],
  ['bathymetry','<i2',new Int16Array([-100,-32767,5,-20]),[1,0,1,1],1,'SIGNED_ELEVATION',{internalFormat:'R16I',format:'RED_INTEGER',type:'SHORT',sampler:'isampler2D'}],
  ['surfaceTexture','|u1',new Uint8Array([20,30,40,255,50,60,70,0,80,90,100,255,110,120,130,255]),[1,0,1,1],-1,'ENCODED_COLOR',{internalFormat:'RGBA8',format:'RGBA',type:'UNSIGNED_BYTE',sampler:'sampler2D'}],
 ]){
  const id=role+'-00',transform=[10,1,0,step<0?22:20,0,step],rowOrder=step<0?'NORTH_TO_SOUTH':'SOUTH_TO_NORTH';
  const part={id,dimensions:[2,2],shape:role==='surfaceTexture'?[2,2,4]:[2,2],numericDtype:dtype,sourceDtype:dtype,
   byteOrderConversion:'NONE',sourceValueBytesSHA256:sha(new Uint8Array(values.buffer)),
   format,values:ref(id,'values',values),valid:{...ref(id,'valid',new Uint8Array(valid)),format:{internalFormat:'R8UI',format:'RED_INTEGER',type:'UNSIGNED_BYTE',sampler:'usampler2D'}},
   x:{...ref(id,'x',new Float64Array([10.5,11.5])),dtype:'<f8',count:2},
   y:{...ref(id,'y',new Float64Array(step<0?[21.5,20.5]:[20.5,21.5])),dtype:'<f8',count:2},
   crs:'EPSG:4326',transform,bbox:[10,20,12,22],rowOrder,pixelRegistration:role==='bathymetry'?'CELL_CENTER':'Point',
   coordinatesMeaning:'PIXEL_CENTERS',transformMeaning:'GDAL_PIXEL_CORNER',
   metadata:{transform:[...transform],rowOrder,units:role==='surfaceTexture'?'uint8_encoded_color':'m',verticalDatum:role==='terrain'?'EGM2008':'DECLARED_TEST_DATUM',
    nodata:role==='terrain'?{__numeric_metadata__:'NaN'}:-32767,
    ...(role==='surfaceTexture'?{colorSpace:'UNSPECIFIED_ENCODED_PNG_BYTES_PRESERVED',colorConversion:'NONE'}:{}),
    ...(role==='bathymetry'?{quantity:'SIGNED_ELEVATION',positive:'up'}:{})},
   quantity,fallback:'UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID',requiresNativeGISCoverage:true,requiresOceanMask:role==='bathymetry'};
  manifest.sources[role]={status:'available',sourceId:'test-'+role,sourceVersion:'fixture-v1',sourceURL:'https://public.example/'+role,
   CRS:'EPSG:4326','SHA-256':one,attribution:'Explicit synthetic fixture',parts:[part]};
 }
 return {manifest,artifacts};
}
function loader(data,options={}){
 const body=json(data.manifest),seen=[];
 const fetchImpl=async(url,request)=>{seen.push({url,request});const file=new URL(url).pathname.split('/').at(-1),
  bytes=file==='manifest.json'?body:data.artifacts.get(file);
  return bytes===undefined?new Response('',{status:404}):new Response(bytes,{headers:{'Content-Length':String(bytes.byteLength)}});};
 return {seen,load:()=>loadUploadBundle({manifestURL:'https://astra.test/bundle/manifest.json',origin:'https://astra.test',
  expectedManifestSha256:sha(body),fetchImpl,...options})};
}
function changeArtifact(data,part,key,bytes){
 const ref=part[key];ref.bytes=bytes.byteLength;ref.sha256=sha(bytes);data.artifacts.set(ref.file,bytes);
 const original=data.manifest.artifacts.find(item=>item.file===ref.file);original.bytes=ref.bytes;original.sha256=ref.sha256;
}
export class FakeGL{
 constructor({limit=4096,failAt=0}={}){
  this.__ASTRA_CPU_TEST_CONTEXT=true;this.failAt=failAt;this.uploads=[];this.deleted=[];this.created=[];this.error=0;this.active=1003;
  let next=1;for(const key of ['VERSION','MAX_TEXTURE_SIZE','ACTIVE_TEXTURE','PIXEL_UNPACK_BUFFER_BINDING','TEXTURE_BINDING_2D','UNPACK_ALIGNMENT',
   'UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_COLORSPACE_CONVERSION_WEBGL','UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT',
   'UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES','PIXEL_UNPACK_BUFFER','TEXTURE_2D','TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER',
   'TEXTURE_WRAP_S','TEXTURE_WRAP_T','TEXTURE_BASE_LEVEL','TEXTURE_MAX_LEVEL','NEAREST','CLAMP_TO_EDGE','R32F','R16I','RGBA8','R8UI','RED','RED_INTEGER','RGBA','FLOAT','SHORT','UNSIGNED_BYTE'])this[key]=next++;
  this.TEXTURE0=1000;this.NONE=0;this.NO_ERROR=0;this.limit=limit;this.buffer={nativeUnpackBuffer:true};
  this.bindings=new Map([[1000,{nativeTexture0:true}],[1003,{nativeTexture3:true}]]);this.pixels=new Map();
  for(const key of ['UNPACK_ALIGNMENT','UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_COLORSPACE_CONVERSION_WEBGL',
   'UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT','UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES'])this.pixels.set(this[key],key==='UNPACK_ALIGNMENT'?8:key==='UNPACK_COLORSPACE_CONVERSION_WEBGL'?49:1);
 }
 isContextLost(){return false;}
 getError(){const error=this.error;this.error=0;return error;}
 getParameter(key){
  if(key===this.VERSION)return 'WebGL 2.0 CPU FAKE — NOT GPU';if(key===this.MAX_TEXTURE_SIZE)return this.limit;
  if(key===this.ACTIVE_TEXTURE)return this.active;if(key===this.PIXEL_UNPACK_BUFFER_BINDING)return this.buffer;
  if(key===this.TEXTURE_BINDING_2D)return this.bindings.get(this.active)??null;
  if(this.pixels.has(key))return this.pixels.get(key);throw Error('UNKNOWN_FAKE_PARAMETER');
 }
 activeTexture(value){this.active=value;}
 bindBuffer(target,value){assert.equal(target,this.PIXEL_UNPACK_BUFFER);this.buffer=value;}
 pixelStorei(key,value){this.pixels.set(key,value);}
 createTexture(){const texture={id:this.created.length+1};this.created.push(texture);return texture;}
 deleteTexture(texture){this.deleted.push(texture);}
 bindTexture(target,value){assert.equal(target,this.TEXTURE_2D);this.bindings.set(this.active,value);}
 texParameteri(){}
 texImage2D(target,level,internalFormat,width,height,border,format,type,values){
  assert.equal(this.buffer,null);assert.equal(this.pixels.get(this.UNPACK_ALIGNMENT),1);assert.equal(this.pixels.get(this.UNPACK_FLIP_Y_WEBGL),0);
  this.uploads.push({target,level,internalFormat,width,height,border,format,type,values:new values.constructor(values),bytes:new Uint8Array(values.buffer.slice(values.byteOffset,values.byteOffset+values.byteLength))});
  if(this.uploads.length===this.failAt)this.error=1282;
 }
 snapshot(){return {active:this.active,buffer:this.buffer,bindings:[...this.bindings],pixels:[...this.pixels]};}
}
test('same-origin SHA-bound loader preserves metadata and never reports a GPU draw',async()=>{
 const original=fixture(),loads=loader(original),bundle=await loads.load();
 assert.equal(bundle.partCount,3);assert.equal(bundle.gpuRenderingVerified,false);assert.equal(bundle.gpuUploadExecuted,false);
 assert.deepEqual(describeUploadBundle(bundle),original.manifest);assert.equal(loads.seen.length,13);
 for(const call of loads.seen){assert.equal(new URL(call.url).origin,'https://astra.test');assert.equal(call.request.redirect,'error');assert.equal(call.request.credentials,'same-origin');}
 const copied=describeUploadBundle(bundle);copied.sources.terrain.sourceVersion='mutated';assert.equal(describeUploadBundle(bundle).sources.terrain.sourceVersion,'fixture-v1');
});
test('sorted-key producer JSON preserves structural equality without depending on object insertion order',async()=>{
 const data=fixture(),sort=value=>Array.isArray(value)?value.map(sort):value&&typeof value==='object'
  ?Object.fromEntries(Object.keys(value).sort().map(key=>[key,sort(value[key])])):value;
 data.manifest=sort(data.manifest);const bundle=await loader(data).load();assert.equal(bundle.partCount,3);
});
test('explicit CPU fake upload keeps every Float32, signed Int16 and encoded RGBA byte, validity and orientation',async()=>{
 const data=fixture(),bundle=await loader(data).load(),gl=new FakeGL(),before=gl.snapshot(),result=createUploadTextures(gl,bundle,{testOnlyContext:true});
 assert.equal(result.testOnly,true);assert.equal(result.gpuUploadExecuted,false);assert.equal(result.gpuRenderingVerified,false);assert.equal(result.drawExecuted,false);assert.equal(result.renderAllowed,false);
 assert.equal(gl.uploads.length,6);assert.deepEqual(gl.snapshot(),before);
 for(const [i,role] of ['terrain','bathymetry','surfaceTexture'].entries()){
  const part=data.manifest.sources[role].parts[0];assert.deepEqual(gl.uploads[i*2].bytes,data.artifacts.get(part.values.file));
  assert.deepEqual(gl.uploads[i*2+1].bytes,data.artifacts.get(part.valid.file));assert.equal(gl.uploads[i*2+1].internalFormat,gl.R8UI);
 }
 assert.ok(Number.isNaN(gl.uploads[0].values[1]));assert.equal(gl.uploads[0].values[3],-9999);
 assert.deepEqual([...gl.uploads[2].values],[-100,-32767,5,-20]);
 assert.equal(gl.uploads[0].internalFormat,gl.R32F);assert.equal(gl.uploads[2].internalFormat,gl.R16I);assert.equal(gl.uploads[4].internalFormat,gl.RGBA8);
 assert.deepEqual(result.resources[0].coordinates.y,[21.5,20.5]);assert.deepEqual(result.resources[1].coordinates.y,[20.5,21.5]);
 result.dispose();result.dispose();assert.equal(gl.deleted.length,6);
});
test('fake context without explicit TEST_ONLY option cannot enter production upload path',async()=>{
 const bundle=await loader(fixture()).load(),gl=new FakeGL();assert.throws(()=>createUploadTextures(gl,bundle),/ACTUAL_WEBGL2_CONTEXT_REQUIRED/);assert.equal(gl.created.length,0);
});
test('hardware texture-size limits fail before allocating or mutating GL',async()=>{
 const bundle=await loader(fixture()).load(),gl=new FakeGL({limit:1}),before=gl.snapshot();
 assert.throws(()=>createUploadTextures(gl,bundle,{testOnlyContext:true}),/HARDWARE_TEXTURE_LIMIT/);assert.equal(gl.created.length,0);assert.deepEqual(gl.snapshot(),before);
});
test('partial texture failure deletes all created textures and restores bindings and pixel-store state',async()=>{
 const bundle=await loader(fixture()).load(),gl=new FakeGL({failAt:3}),before=gl.snapshot();
 assert.throws(()=>createUploadTextures(gl,bundle,{testOnlyContext:true}),/TEXTURE_UPLOAD_GL_ERROR/);
 assert.equal(gl.created.length,3);assert.deepEqual(gl.deleted,gl.created);assert.deepEqual(gl.snapshot(),before);
});
test('allocation refusal after one texture preserves original GL state and cleans the prior resource',async()=>{
 const bundle=await loader(fixture()).load(),gl=new FakeGL(),before=gl.snapshot(),allocate=gl.createTexture.bind(gl);
 gl.createTexture=()=>gl.created.length===1?null:allocate();
 assert.throws(()=>createUploadTextures(gl,bundle,{testOnlyContext:true}),/TEXTURE_ALLOCATION_FAILED/);
 assert.deepEqual(gl.deleted,gl.created);assert.equal(gl.deleted.length,1);assert.deepEqual(gl.snapshot(),before);
});
test('context loss and preexisting GL errors are refused without allocations',async()=>{
 const bundle=await loader(fixture()).load(),lost=new FakeGL();lost.isContextLost=()=>true;
 assert.throws(()=>createUploadTextures(lost,bundle,{testOnlyContext:true}),/WEBGL2_OR_CONTEXT_LOST/);
 const prior=new FakeGL();prior.error=1280;assert.throws(()=>createUploadTextures(prior,bundle,{testOnlyContext:true}),/PREEXISTING_GL_ERROR/);assert.equal(prior.created.length,0);
});
test('manifest SHA mismatch prevents artifact fetch',async()=>{
 const loads=loader(fixture(),{expectedManifestSha256:zero});await assert.rejects(loads.load(),/MANIFEST_HASH_MISMATCH/);assert.equal(loads.seen.length,1);
});
test('artifact corruption and truncation are separately rejected before GPU use',async()=>{
 const corrupt=fixture(),ref=corrupt.manifest.sources.terrain.parts[0].values;corrupt.artifacts.get(ref.file)[0]^=1;
 await assert.rejects(loader(corrupt).load(),/ARTIFACT_HASH_MISMATCH/);
 const short=fixture(),shortRef=short.manifest.sources.terrain.parts[0].values;short.artifacts.set(shortRef.file,short.artifacts.get(shortRef.file).slice(1));
 await assert.rejects(loader(short).load(),/ARTIFACT_LENGTH_MISMATCH/);
});
test('cross-origin manifests, redirects and unsafe artifact paths are refused',async()=>{
 await assert.rejects(loader(fixture(),{manifestURL:'https://elsewhere.test/manifest.json'}).load(),/SAME_ORIGIN_URL_REQUIRED/);
 await assert.rejects(loader(fixture(),{fetchImpl:async()=>({ok:true,redirected:true})}).load(),/UPLOAD_REDIRECT_FORBIDDEN/);
 const data=fixture();data.manifest.sources.terrain.parts[0].values.file='../escape.bin';await assert.rejects(loader(data).load(),/INVALID_ARTIFACT_REFERENCE/);
});
test('stream byte cap and total artifact budget prevent excess consumption',async()=>{
 const data=fixture(),body=json(data.manifest);
 await assert.rejects(loader(data,{fetchImpl:async()=>new Response(new Uint8Array(2*1024*1024+1))}).load(),/UPLOAD_RESPONSE_TOO_LARGE/);
 await assert.rejects(loader(data,{maxBytes:1}).load(),/BUNDLE_BYTE_LIMIT/);
 const calls=[];await assert.rejects(loadUploadBundle({manifestURL:'https://astra.test/manifest.json',origin:'https://astra.test',expectedManifestSha256:sha(body),
  fetchImpl:async(url,options)=>{calls.push(url);return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}));},timeoutMs:10}),/UPLOAD_TIMEOUT/);
 assert.equal(calls.length,1);
});
test('dtype, endian, CRS, shape and sampling coercions are rejected',async()=>{
 for(const [field,value,error] of [['numericDtype','>f4','DTYPE_OR_FORMAT_UNSUPPORTED'],['sourceDtype','<f8','DTYPE_OR_FORMAT_UNSUPPORTED'],
  ['crs','EPSG:3857','GEOGRAPHIC_CONTRACT_REQUIRED'],['shape',[2,3],'SHAPE_MISMATCH'],['rowOrder','SOUTH_TO_NORTH','REGISTRATION_OR_ROW_ORDER_MISMATCH']]){
  const data=fixture();data.manifest.sources.terrain.parts[0][field]=value;await assert.rejects(loader(data).load(),new RegExp(error));
 }
 const data=fixture();data.manifest.sampling.flipY=true;await assert.rejects(loader(data).load(),/UNSUPPORTED_SAMPLING_POLICY/);
});
test('false original-value SHA and false byte-swap provenance are rejected',async()=>{
 const wrong=fixture();wrong.manifest.sources.terrain.parts[0].sourceValueBytesSHA256=zero;
 await assert.rejects(loader(wrong).load(),/ORIGINAL_VALUE_BYTES_HASH_MISMATCH/);
 const conversion=fixture();conversion.manifest.sources.bathymetry.parts[0].byteOrderConversion='BYTE_SWAP_ONLY';
 await assert.rejects(loader(conversion).load(),/BYTE_ORDER_CONVERSION_MISMATCH/);
 const reversed=fixture();reversed.manifest.sources.terrain.parts[0].sourceDtype='>f4';reversed.manifest.sources.terrain.parts[0].byteOrderConversion='BYTE_SWAP_ONLY';
 await assert.rejects(loader(reversed).load(),/ORIGINAL_VALUE_BYTES_HASH_MISMATCH/);
});
test('half-pixel axis displacement and false extent metadata are rejected',async()=>{
 const moved=fixture(),part=moved.manifest.sources.terrain.parts[0];changeArtifact(moved,part,'x',new Uint8Array(new Float64Array([10,11]).buffer));
 await assert.rejects(loader(moved).load(),/AXIS_TRANSFORM_MISMATCH/);
 const extent=fixture();extent.manifest.sources.terrain.parts[0].bbox=[10,20,13,22];await assert.rejects(loader(extent).load(),/AXIS_BOUNDS_MISMATCH/);
});
test('nonfinite samples require invalid flags and support flags remain actual booleans',async()=>{
 const wrong=fixture(),part=wrong.manifest.sources.terrain.parts[0];changeArtifact(wrong,part,'valid',new Uint8Array([1,1,1,0]));
 await assert.rejects(loader(wrong).load(),/NONFINITE_VALID_SAMPLE/);
 const mask=fixture(),maskPart=mask.manifest.sources.terrain.parts[0];changeArtifact(mask,maskPart,'valid',new Uint8Array([255,0,1,0]));await assert.rejects(loader(mask).load(),/BOOLEAN_VALIDITY_REQUIRED/);
});
test('unknown unavailable source remains explicit and is never fabricated as zero-valued data',async()=>{
 const data=fixture();data.manifest.sources.bathymetry={...data.manifest.sources.bathymetry,status:'unavailable',parts:[]};
 data.manifest.artifacts=data.manifest.artifacts.filter(ref=>!ref.file.startsWith('bathymetry-'));
 const bundle=await loader(data).load(),gl=new FakeGL(),result=createUploadTextures(gl,bundle,{testOnlyContext:true});
 assert.equal(result.resources.length,2);assert.equal(describeUploadBundle(bundle).sources.bathymetry.status,'unavailable');result.dispose();
});
test('disabled bundle creates no textures and preserves explicit inactive state',async()=>{
 const data=fixture();data.manifest.enabled=false;data.manifest.sources={};data.manifest.artifacts=[];
 const bundle=await loader(data).load(),gl=new FakeGL(),result=createUploadTextures(gl,bundle,{testOnlyContext:true});
 assert.equal(bundle.enabled,false);assert.equal(result.resources.length,0);assert.equal(result.gpuUploadExecuted,false);
});
async function nativeContext(){
 const coverage=new Uint8Array([255,0,0,255,0,0,0,255,128,0,0,255,255,0,0,255]);
 const context={source:'UNCHANGED_NATIVE_FACTORY_COVERAGE_RGBA8_BOTTOM_LEFT',actualNativeGIS:true,
  projection:'FLAT_EPSG4326_RECTILINEAR',bounds:[10,20,12,22],frame:42,width:2,height:2,
  geometrySha256:one,cameraStateSha256:two,coverage,coverageSha256:sha(coverage)};
 const expected=Object.fromEntries(['frame','projection','bounds','width','height','geometrySha256','cameraStateSha256'].map(key=>[key,structuredClone(context[key])]));
 return {context,expected};
}
test('depth sampling plan requires native GIS and frame identity; signed elevation is never a coast mask',async()=>{
 const bundle=await loader(fixture()).load(),{context,expected}=await nativeContext(),plan=await planScreenDepthSampling(bundle,context,expected);
 assert.equal(plan.status,'CONTEXT_BOUND_NOT_RENDERED');assert.equal(plan.negativeElevationIsOceanMask,false);
 assert.equal(plan.negativeLandDepressionsRemainLand,true);assert.equal(plan.coastAlignmentVerified,false);assert.equal(plan.renderAllowed,false);
 assert.equal(plan.landCoverageChannel,0);assert.equal(plan.rowZero,'SOUTH');assert.equal(plan.gpuRenderingVerified,false);
 await assert.rejects(planScreenDepthSampling(bundle,{...context,actualNativeGIS:false},expected),/ACTUAL_NATIVE_GIS_CONTEXT_REQUIRED/);
 await assert.rejects(planScreenDepthSampling(bundle,context,{...expected,frame:43}),/GIS_FRAME_PROJECTION_BINDING_MISMATCH/);
 await assert.rejects(planScreenDepthSampling(bundle,context,{...expected,cameraStateSha256:zero}),/GIS_FRAME_PROJECTION_BINDING_MISMATCH/);
 await assert.rejects(planScreenDepthSampling(bundle,context,{...expected,bounds:[9,20,12,22]}),/GIS_FRAME_PROJECTION_BINDING_MISMATCH/);
});
test('coverage SHA/shape corruption and unsupported projection cannot become depth admission',async()=>{
 const bundle=await loader(fixture()).load(),{context,expected}=await nativeContext();
 await assert.rejects(planScreenDepthSampling(bundle,{...context,coverageSha256:zero},expected),/GIS_COVERAGE_HASH_OR_SHAPE_MISMATCH/);
 await assert.rejects(planScreenDepthSampling(bundle,{...context,coverage:new Uint8Array(4)},expected),/GIS_COVERAGE_HASH_OR_SHAPE_MISMATCH/);
 await assert.rejects(planScreenDepthSampling(bundle,{...context,projection:'GLOBE'},expected),/ACTUAL_NATIVE_GIS_CONTEXT_REQUIRED/);
});
