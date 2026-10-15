/** Additive ASTRA binary consumption only. No draw, material, renderer hook or GPU attestation. */
const SCHEMA='ASTRA_GPU_UPLOAD_BUNDLE_V1', MAX_MANIFEST=2*1024*1024, MAX_BYTES=256*1024*1024;
const roles=new Set(['terrain','bathymetry','surfaceTexture']);
const statuses=new Set(['available','unavailable','auth_required','version_changed','license_unverified','invalid_data']);
const store=new WeakMap(), hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const fail=code=>{throw Error(code);};
const check=(value,code)=>{if(!value)fail(code);};
const canonical=value=>Array.isArray(value)?value.map(canonical):object(value)
 ?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const equal=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};
const clone=value=>JSON.parse(JSON.stringify(value));
const finiteArray=(value,length)=>Array.isArray(value)&&value.length===length&&value.every(Number.isFinite);
const bounds=value=>finiteArray(value,4)&&value[0]>=-180&&value[2]<=180&&value[1]>=-90&&value[3]<=90&&value[0]<value[2]&&value[1]<value[3];
const nativeLittleEndian=()=>new Uint8Array(new Uint16Array([1]).buffer)[0]===1;
async function digest(bytes){check(globalThis.crypto?.subtle,'WEB_CRYPTO_REQUIRED');return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');}
function safeJson(value,depth=0){
 check(depth<=40,'METADATA_DEPTH_LIMIT');
 if(Array.isArray(value)){check(value.length<=100000,'METADATA_ARRAY_LIMIT');value.forEach(v=>safeJson(v,depth+1));}
 else if(object(value)){for(const [key,item] of Object.entries(value)){check(!['__proto__','constructor','prototype'].includes(key),'UNSAFE_JSON_KEY');safeJson(item,depth+1);}}
 else check(value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value),'FINITE_JSON_REQUIRED');
}
function reference(item,kind){
 check(object(item)&&typeof item.file==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(item.file)
  &&!item.file.includes('..')&&item.kind===kind&&integer(item.bytes,1,MAX_BYTES)&&hex(item.sha256),'INVALID_ARTIFACT_REFERENCE');
 return {file:item.file,bytes:item.bytes,sha256:item.sha256,kind:item.kind};
}
async function fetchBytes(url,limit,fetchImpl,signal){
 const result=await fetchImpl(url,{redirect:'error',credentials:'same-origin',cache:'no-store',signal});
 check(result?.ok===true,'UPLOAD_HTTP_FAILED');
 check(!result.redirected&&(!result.url||new URL(result.url).href===url),'UPLOAD_REDIRECT_FORBIDDEN');
 const contentLength=result.headers?.get?.('content-length');
 if(contentLength!==null&&contentLength!==undefined)check(/^\d+$/.test(contentLength)&&Number(contentLength)<=limit,'UPLOAD_RESPONSE_TOO_LARGE');
 check(result.body?.getReader,'BOUNDED_STREAM_REQUIRED');
 const reader=result.body.getReader(),chunks=[];let length=0;
 try{for(;;){const {done,value}=await reader.read();if(done)break;
   check(value instanceof Uint8Array,'BYTE_STREAM_REQUIRED');length+=value.byteLength;
   if(length>limit){await reader.cancel();fail('UPLOAD_RESPONSE_TOO_LARGE');}chunks.push(value);
  }}finally{reader.releaseLock();}
 const bytes=new Uint8Array(length);let offset=0;for(const part of chunks){bytes.set(part,offset);offset+=part.length;}return bytes;
}
const formats={
 terrain:{dtype:'<f4',size:4,quantity:'HEIGHT',channels:1,format:{internalFormat:'R32F',format:'RED',type:'FLOAT',sampler:'sampler2D'}},
 bathymetry:{dtype:'<i2',size:2,quantity:'SIGNED_ELEVATION',channels:1,format:{internalFormat:'R16I',format:'RED_INTEGER',type:'SHORT',sampler:'isampler2D'}},
 surfaceTexture:{dtype:'|u1',size:1,quantity:'ENCODED_COLOR',channels:4,format:{internalFormat:'RGBA8',format:'RGBA',type:'UNSIGNED_BYTE',sampler:'sampler2D'}},
};
const validFormat={internalFormat:'R8UI',format:'RED_INTEGER',type:'UNSIGNED_BYTE',sampler:'usampler2D'};
function validateManifest(manifest){
 safeJson(manifest);check(object(manifest)&&manifest.schema===SCHEMA&&typeof manifest.enabled==='boolean'
  &&hex(manifest.rendererPayloadSHA256)&&manifest.gpuUploadExecuted===false&&manifest.gpuRenderingVerified===false
  &&manifest.targetAPI==='WEBGL2_UPLOAD_CONTRACT_UNVERIFIED','INVALID_UPLOAD_MANIFEST');
 check(equal(manifest.sampling,{filter:'NEAREST',texelFetch:true,unpackAlignment:1,flipY:false,mipmaps:false,rowOrder:'SOURCE_PRESERVED'}),'UNSUPPORTED_SAMPLING_POLICY');
 check(object(manifest.sources)&&Object.keys(manifest.sources).every(role=>roles.has(role)),'UNSUPPORTED_SOURCE_ROLE');
 check(Array.isArray(manifest.artifacts)&&manifest.artifacts.length<=256,'ARTIFACT_COUNT_LIMIT');
 const listed=new Map(),used=new Set(),ids=new Set(),parts=[];
 for(const item of manifest.artifacts){const ref=reference(item,item.kind);check(['values','valid','x','y'].includes(ref.kind)&&!listed.has(ref.file),'DUPLICATE_OR_UNSUPPORTED_ARTIFACT');listed.set(ref.file,ref);}
 const bind=(item,kind,bytes)=>{const ref=reference(item,kind);check(ref.bytes===bytes&&equal(listed.get(ref.file),ref),'ARTIFACT_BINDING_MISMATCH');check(!used.has(ref.file),'SHARED_ARTIFACT_FORBIDDEN');used.add(ref.file);};
 for(const [role,source] of Object.entries(manifest.sources)){
  check(object(source)&&statuses.has(source.status)&&typeof source.sourceId==='string'&&source.sourceId.length>0
   &&typeof source.sourceVersion==='string'&&source.sourceVersion.length>0&&source.CRS==='EPSG:4326'
   &&Array.isArray(source.parts)&&source.parts.length<=16,'INVALID_SOURCE_METADATA');
  check(source.status==='available'||source.parts.length===0,'UNAVAILABLE_SOURCE_HAS_PARTS');
  check(source.status!=='available'||source.parts.length>0,'AVAILABLE_SOURCE_WITHOUT_DATA');
  check(hex(source['SHA-256'])&&typeof source.attribution==='string'&&typeof source.sourceURL==='string','SOURCE_PROVENANCE_REQUIRED');
  const sourceURL=new URL(source.sourceURL);check(sourceURL.protocol==='https:'&&!sourceURL.username&&!sourceURL.password&&!sourceURL.hash,'SOURCE_PROVENANCE_REQUIRED');
  if(source.parts.length)check(manifest.enabled,'DISABLED_BUNDLE_HAS_PARTS');
  for(const part of source.parts){
   check(object(part)&&typeof part.id==='string'&&/^[a-zA-Z0-9_-]{1,64}$/.test(part.id)&&!ids.has(part.id),'INVALID_PART_ID');ids.add(part.id);
   check(Array.isArray(part.dimensions)&&part.dimensions.length===2&&part.dimensions.every(v=>integer(v,1,32768)),'INVALID_TEXTURE_DIMENSIONS');
   const [width,height]=part.dimensions,fmt=formats[role];
   check(equal(part.shape,fmt.channels===1?[height,width]:[height,width,fmt.channels]),'SHAPE_MISMATCH');
   check(part.numericDtype===fmt.dtype&&[fmt.dtype,fmt.dtype.replace('<','>')].includes(part.sourceDtype)
    &&equal(part.format,fmt.format)&&hex(part.sourceValueBytesSHA256),'DTYPE_OR_FORMAT_UNSUPPORTED');
   check(part.byteOrderConversion===(part.sourceDtype.startsWith('>')?'BYTE_SWAP_ONLY':'NONE'),'BYTE_ORDER_CONVERSION_MISMATCH');
   check(part.quantity===fmt.quantity&&part.crs==='EPSG:4326'&&bounds(part.bbox)
    &&part.coordinatesMeaning==='PIXEL_CENTERS'&&part.transformMeaning==='GDAL_PIXEL_CORNER','GEOGRAPHIC_CONTRACT_REQUIRED');
   check(finiteArray(part.transform,6)&&part.transform[1]>0&&part.transform[2]===0&&part.transform[4]===0&&part.transform[5]!==0,'RECTILINEAR_TRANSFORM_REQUIRED');
   check(part.rowOrder===(part.transform[5]<0?'NORTH_TO_SOUTH':'SOUTH_TO_NORTH')
    &&['Point','Area','CELL_CENTER','CELL_CENTERS','UNDECLARED'].includes(part.pixelRegistration),'REGISTRATION_OR_ROW_ORDER_MISMATCH');
   check(object(part.metadata)&&equal(part.metadata.transform,part.transform)
    &&(!Object.hasOwn(part.metadata,'rowOrder')||part.metadata.rowOrder===part.rowOrder),'SOURCE_GEOGRAPHIC_METADATA_MISMATCH');
   if(role!=='surfaceTexture')check(part.metadata.units==='m','METERS_REQUIRED');
   if(role==='bathymetry')check(part.metadata.quantity==='SIGNED_ELEVATION'&&part.metadata.positive==='up','POSITIVE_UP_SIGNED_ELEVATION_REQUIRED');
   if(role==='surfaceTexture')check((!Object.hasOwn(part.metadata,'units')||part.metadata.units==='uint8_encoded_color')
    &&(!Object.hasOwn(part.metadata,'colorConversion')||part.metadata.colorConversion==='NONE'),'ENCODED_COLOR_PRESERVATION_REQUIRED');
   check(part.fallback==='UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID'&&part.requiresNativeGISCoverage===true
    &&part.requiresOceanMask===(role==='bathymetry'),'EXPLICIT_SUPPORT_AND_MASK_REQUIRED');
   bind(part.values,'values',width*height*fmt.channels*fmt.size);bind(part.valid,'valid',width*height);
   check(equal(part.valid.format,validFormat),'VALIDITY_FORMAT_REQUIRED');
   bind(part.x,'x',width*8);bind(part.y,'y',height*8);
   check(part.x.dtype==='<f8'&&part.y.dtype==='<f8'&&part.x.count===width&&part.y.count===height,'AXIS_DTYPE_OR_COUNT_MISMATCH');
   parts.push({role,part,fmt});
  }
 }
 check(used.size===listed.size,'UNREFERENCED_ARTIFACT');
 if(!manifest.enabled)check(parts.length===0,'DISABLED_BUNDLE_HAS_PARTS');
 return {listed,parts};
}
async function validateArrays(parts,bytes){
 for(const item of parts){const {part,role}=item,[width,height]=part.dimensions;
  const x=new Float64Array(bytes.get(part.x.file).buffer),y=new Float64Array(bytes.get(part.y.file).buffer),valid=bytes.get(part.valid.file);
  const t=part.transform;
  for(let i=0;i<width;i++)check(Number.isFinite(x[i])&&Math.abs(x[i]-(t[0]+(i+.5)*t[1]))<=1e-9,'AXIS_TRANSFORM_MISMATCH');
  for(let j=0;j<height;j++)check(Number.isFinite(y[j])&&Math.abs(y[j]-(t[3]+(j+.5)*t[5]))<=1e-9,'AXIS_TRANSFORM_MISMATCH');
  const actual=[x[0]-t[1]/2,Math.min(y[0],y[height-1])-Math.abs(t[5])/2,x[width-1]+t[1]/2,Math.max(y[0],y[height-1])+Math.abs(t[5])/2];
  check(bounds(actual)&&actual.every((value,index)=>Math.abs(value-part.bbox[index])<=1e-9),'AXIS_BOUNDS_MISMATCH');
  check(valid.every(value=>value===0||value===1),'BOOLEAN_VALIDITY_REQUIRED');
  const valuesBytes=bytes.get(part.values.file),sourceBytes=valuesBytes.slice();
  if(part.byteOrderConversion==='BYTE_SWAP_ONLY')for(let i=0;i<sourceBytes.length;i+=item.fmt.size)
   sourceBytes.subarray(i,i+item.fmt.size).reverse();
  check(await digest(sourceBytes)===part.sourceValueBytesSHA256,'ORIGINAL_VALUE_BYTES_HASH_MISMATCH');
  if(role==='terrain'){
   const values=new Float32Array(bytes.get(part.values.file).buffer);
   for(let i=0;i<values.length;i++)check(!valid[i]||Number.isFinite(values[i]),'NONFINITE_VALID_SAMPLE');
  }
  item.x=x;item.y=y;
 }
}
/** Load only SHA-bound same-origin files. The returned opaque handle exposes no mutable samples. */
export async function loadUploadBundle({manifestURL,expectedManifestSha256,origin=globalThis.location?.origin,
 fetchImpl=globalThis.fetch,maxBytes=64*1024*1024,signal,timeoutMs=15000}={}){
 check(typeof origin==='string'&&typeof fetchImpl==='function'&&integer(maxBytes,1,MAX_BYTES)
  &&integer(timeoutMs,1,120000),'BOUNDED_LOAD_CONFIGURATION_REQUIRED');
 const base=new URL(origin),url=new URL(manifestURL,base);
 check(['http:','https:'].includes(base.protocol)&&base.origin===origin&&url.origin===origin&&!url.username&&!url.password&&!url.hash,'SAME_ORIGIN_URL_REQUIRED');
 check(hex(expectedManifestSha256),'MANIFEST_HASH_REQUIRED');
 check(nativeLittleEndian(),'LITTLE_ENDIAN_HOST_REQUIRED');
 const controller=new AbortController(),combined=signal?AbortSignal.any([signal,controller.signal]):controller.signal;
 const timer=setTimeout(()=>controller.abort(Error('UPLOAD_TIMEOUT')),timeoutMs);
 try{
 const raw=await fetchBytes(url.href,MAX_MANIFEST,fetchImpl,combined);check(await digest(raw)===expectedManifestSha256,'MANIFEST_HASH_MISMATCH');
 let manifest;try{manifest=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));}catch{fail('INVALID_MANIFEST_JSON');}
 const {listed,parts}=validateManifest(manifest),bytes=new Map();let total=0;
 // Fail the complete request budget before fetching even the first artifact.
 check([...listed.values()].reduce((sum,ref)=>sum+ref.bytes,0)<=maxBytes,'BUNDLE_BYTE_LIMIT');
 for(const ref of listed.values()){
  total+=ref.bytes;check(total<=maxBytes,'BUNDLE_BYTE_LIMIT');
  const artifactURL=new URL(ref.file,url);check(artifactURL.origin===origin,'SAME_ORIGIN_ARTIFACT_REQUIRED');
  const value=await fetchBytes(artifactURL.href,ref.bytes,fetchImpl,combined);
  check(value.byteLength===ref.bytes,'ARTIFACT_LENGTH_MISMATCH');check(await digest(value)===ref.sha256,'ARTIFACT_HASH_MISMATCH');bytes.set(ref.file,value);
 }
 await validateArrays(parts,bytes);freeze(manifest);
 const handle=Object.freeze({schema:SCHEMA,manifestSha256:expectedManifestSha256,enabled:manifest.enabled,
  partCount:parts.length,artifactBytes:total,gpuUploadExecuted:false,gpuRenderingVerified:false});
 store.set(handle,{manifest,parts,bytes});return handle;
 }finally{clearTimeout(timer);}
}
export function describeUploadBundle(bundle){const value=store.get(bundle);check(value,'VERIFIED_BUNDLE_HANDLE_REQUIRED');return clone(value.manifest);}
function assertContext(gl,testOnlyContext){
 check(typeof testOnlyContext==='boolean','EXPLICIT_TEST_CONTEXT_FLAG_REQUIRED');
 const real=typeof globalThis.WebGL2RenderingContext==='function'&&gl instanceof globalThis.WebGL2RenderingContext;
 check(real&&!testOnlyContext||testOnlyContext&&gl?.__ASTRA_CPU_TEST_CONTEXT===true&&!real,'ACTUAL_WEBGL2_CONTEXT_REQUIRED');
 check(typeof gl.getParameter==='function'&&typeof gl.isContextLost==='function'&&!gl.isContextLost()
  &&/^WebGL 2\.0\b/.test(gl.getParameter(gl.VERSION)),'WEBGL2_OR_CONTEXT_LOST');
 check(gl.getError()===gl.NO_ERROR,'PREEXISTING_GL_ERROR');
 return real;
}
/** Allocate resources only; nothing is drawn or admitted. Explicit fake contexts are always TEST_ONLY. */
export function createUploadTextures(gl,bundle,{testOnlyContext=false}={}){
 const record=store.get(bundle);check(record,'VERIFIED_BUNDLE_HANDLE_REQUIRED');const real=assertContext(gl,testOnlyContext);
 const limit=gl.getParameter(gl.MAX_TEXTURE_SIZE);check(integer(limit,1,65536),'ACTUAL_TEXTURE_LIMIT_REQUIRED');
 for(const {part} of record.parts)check(part.dimensions.every(v=>v<=limit),'HARDWARE_TEXTURE_LIMIT');
 const keys=['UNPACK_ALIGNMENT','UNPACK_FLIP_Y_WEBGL','UNPACK_PREMULTIPLY_ALPHA_WEBGL','UNPACK_COLORSPACE_CONVERSION_WEBGL',
  'UNPACK_ROW_LENGTH','UNPACK_IMAGE_HEIGHT','UNPACK_SKIP_PIXELS','UNPACK_SKIP_ROWS','UNPACK_SKIP_IMAGES'];
 const previous={active:gl.getParameter(gl.ACTIVE_TEXTURE),unpackBuffer:gl.getParameter(gl.PIXEL_UNPACK_BUFFER_BINDING),
  pixels:keys.map(key=>[key,gl.getParameter(gl[key])])};
 const resources=[],entries=[];let failure;
 try{
  gl.activeTexture(gl.TEXTURE0);previous.binding=gl.getParameter(gl.TEXTURE_BINDING_2D);
  gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,null);
  for(const key of keys)gl.pixelStorei(gl[key],key==='UNPACK_ALIGNMENT'?1:key==='UNPACK_COLORSPACE_CONVERSION_WEBGL'?gl.NONE:0);
  const upload=(part,ref,format,values)=>{
   const texture=gl.createTexture();check(texture,'TEXTURE_ALLOCATION_FAILED');resources.push(texture);
   gl.bindTexture(gl.TEXTURE_2D,texture);
   for(const key of ['TEXTURE_MIN_FILTER','TEXTURE_MAG_FILTER'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.NEAREST);
   for(const key of ['TEXTURE_WRAP_S','TEXTURE_WRAP_T'])gl.texParameteri(gl.TEXTURE_2D,gl[key],gl.CLAMP_TO_EDGE);
   for(const key of ['TEXTURE_BASE_LEVEL','TEXTURE_MAX_LEVEL'])gl.texParameteri(gl.TEXTURE_2D,gl[key],0);
   gl.texImage2D(gl.TEXTURE_2D,0,gl[format.internalFormat],...part.dimensions,0,gl[format.format],gl[format.type],values);
   check(gl.getError()===gl.NO_ERROR,'TEXTURE_UPLOAD_GL_ERROR');return texture;
  };
  for(const {part,role,fmt,x,y} of record.parts){
   const raw=record.bytes.get(part.values.file),values=role==='terrain'?new Float32Array(raw.buffer):role==='bathymetry'?new Int16Array(raw.buffer):raw;
   const valueTexture=upload(part,part.values,fmt.format,values),validTexture=upload(part,part.valid,validFormat,record.bytes.get(part.valid.file));
   entries.push(Object.freeze({role,id:part.id,values:valueTexture,valid:validTexture,
    coordinates:freeze({x:Array.from(x),y:Array.from(y),rowOrder:part.rowOrder,flipY:false}),metadata:part}));
  }
 }catch(error){failure=error;}
 finally{
  try{for(const [key,value] of previous.pixels)gl.pixelStorei(gl[key],value);
   gl.bindBuffer(gl.PIXEL_UNPACK_BUFFER,previous.unpackBuffer);
   if(Object.hasOwn(previous,'binding'))gl.bindTexture(gl.TEXTURE_2D,previous.binding);gl.activeTexture(previous.active);
   check(gl.getError()===gl.NO_ERROR,'TEXTURE_STATE_RESTORE_GL_ERROR');
  }catch(error){failure??=error;}
 }
 if(failure){for(const texture of resources)gl.deleteTexture(texture);throw failure;}
 let disposed=false;
 return Object.freeze({schema:'ASTRA_GPU_UPLOAD_RESOURCES_V1',resources:Object.freeze(entries),testOnly:!real,
  gpuUploadExecuted:real&&resources.length>0,gpuRenderingVerified:false,drawExecuted:false,renderAllowed:false,
  dispose(){if(!disposed){for(const texture of resources)gl.deleteTexture(texture);disposed=true;}}});
}
/** Bind a future depth sampler to THIS actual native GIS frame; never infer an ocean mask from elevation sign. */
export async function planScreenDepthSampling(bundle,context,expected){
 const record=store.get(bundle);check(record,'VERIFIED_BUNDLE_HANDLE_REQUIRED');
 check(object(context)&&object(expected)&&context.source==='UNCHANGED_NATIVE_FACTORY_COVERAGE_RGBA8_BOTTOM_LEFT'
  &&context.actualNativeGIS===true&&context.projection==='FLAT_EPSG4326_RECTILINEAR'
  &&bounds(context.bounds)&&integer(context.frame,0,1000000)&&integer(context.width,1,16384)&&integer(context.height,1,16384)
  &&context.width*context.height<=16000000&&hex(context.geometrySha256)&&hex(context.cameraStateSha256),'ACTUAL_NATIVE_GIS_CONTEXT_REQUIRED');
 check(context.coverage instanceof Uint8Array&&context.coverage.byteLength===context.width*context.height*4
  &&hex(context.coverageSha256)&&await digest(context.coverage)===context.coverageSha256,'GIS_COVERAGE_HASH_OR_SHAPE_MISMATCH');
 for(const key of ['frame','projection','bounds','width','height','geometrySha256','cameraStateSha256'])
  check(equal(context[key],expected[key]),'GIS_FRAME_PROJECTION_BINDING_MISMATCH');
 const bathy=record.parts.filter(part=>part.role==='bathymetry');check(bathy.length>0,'BATHYMETRY_UNAVAILABLE');
 return freeze({schema:'ASTRA_SCREEN_DEPTH_SAMPLING_PLAN_V1',status:'CONTEXT_BOUND_NOT_RENDERED',
  bundleSha256:bundle.manifestSha256,frame:context.frame,bounds:clone(context.bounds),projection:context.projection,
  geometrySha256:context.geometrySha256,cameraStateSha256:context.cameraStateSha256,coverageSha256:context.coverageSha256,
  landCoverageChannel:0,rowZero:'SOUTH',geographicMapping:'PIXEL_CENTER_FROM_EXACT_FRAME_BOUNDS',
  samplePolicy:'SAME_FRAME_GIS_OCEAN_COVERAGE_AND_VALID_SOURCE_TEXEL_REQUIRED',
  negativeElevationIsOceanMask:false,negativeLandDepressionsRemainLand:true,coastAlignmentVerified:false,
  sourceParts:bathy.map(({part})=>part.id),gpuRenderingVerified:false,drawExecuted:false,renderAllowed:false});
}
