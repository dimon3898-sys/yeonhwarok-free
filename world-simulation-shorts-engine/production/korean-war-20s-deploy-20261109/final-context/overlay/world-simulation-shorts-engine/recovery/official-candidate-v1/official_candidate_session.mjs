import {browserModuleImports} from './browser_module_closure.mjs';
/** Candidate-only immutable loopback data source. Does not listen or create a renderer. */
import path from 'node:path';import {createHash,randomBytes} from 'node:crypto';
import {readPinnedServerFile} from './candidate_asset_snapshot.mjs';
import {verifyPreparedRuntimeRequest} from './capture_presentation.mjs';
import {createCandidateAssetLeaseManager} from './candidate_asset_lease.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const check=(v,c)=>{if(!v)throw Error(c)},hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const canonical=x=>JSON.stringify(x);
const semantic=x=>JSON.stringify(x,(_key,value)=>value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.keys(value).sort().map(key=>[key,value[key]])):value);
const CODE_CAP=16*1024**2,STATIC_CAP=32*1024**2;
/** registry is supplied ONLY by the official worker's server-owned configuration.
 * No request JSON, CLI flag, URL, path or Boolean can add a registry entry.
 */
export async function prepareOfficialCandidateSession({registrationId,registry,assetRegistry}={}){
 check(registry instanceof Map&&registry.has(registrationId),'UP2_OFFICIAL_SERVER_REGISTRATION_REQUIRED');
 const record=structuredClone(registry.get(registrationId));
 const selectedAssetRegistry=new Map([...assetRegistry].map(([k,v])=>[k,structuredClone(v)]));
 check(record.schema==='WORLD_ENGINE_OFFICIAL_CANDIDATE_SESSION_V1'&&record.mode==='CPU_QUALIFIED_GPU_PENDING'&&record.productionAdmitted===false,'UP2_OFFICIAL_REGISTRATION_SCHEMA');
 for(const key of ['originalSemanticSHA256','aggregateQualificationSHA256','chunkRequestSHA256','nativeSourceQualificationSHA256','actualCameraComparisonSHA256','defaultPresentationMapOptionsSHA256','shaderSha256','heightSupportReceiptSHA256'])check(hex(record[key]),'UP2_OFFICIAL_REQUIRED_PIN');
 check(record.materialPolicy==='MODERN_UNFILLED_SOURCE_V1'&&['DISABLED','MASKED_HEIGHT_NORMALIZED_V1'].includes(record.lightingPolicy),'UP2_OFFICIAL_MATERIAL_POLICY');
 check(hex(record.payloadSHA256)&&hash(Buffer.from(canonical(record.payload)))===record.payloadSHA256,'UP2_OFFICIAL_PAYLOAD_PIN');
 check(typeof record.sceneKey==='string'&&record.sceneKey===record.originalSemanticSHA256+':'+record.chunkRequestSHA256+':'+record.sceneId,'UP2_OFFICIAL_SCENE_IDENTITY');
 check(Array.isArray(record.windows)&&record.windows.length>=1&&record.windows.length<=2,'UP2_OFFICIAL_SINGLE_SCENE_WINDOWS');
 const windows=new Map();let cursor=0;
 for(const row of record.windows){check(typeof row.id==='string'&&!windows.has(row.id)&&row.first===cursor&&Number.isSafeInteger(row.end)&&row.end>cursor&&row.end<=240&&row.request?.windowId===row.id&&row.request.layerId===row.layerId&&typeof row.layerId==='string'&&hex(row.windowQualificationSha256),'UP2_OFFICIAL_WINDOW_PARTITION');windows.set(row.id,structuredClone(row));cursor=row.end;}
 check(cursor===record.payload.totalFrames&&Array.isArray(record.frameHeightComplete)&&record.frameHeightComplete.length===cursor&&record.frameHeightComplete.every(v=>typeof v==='boolean'),'UP2_OFFICIAL_FRAME_HEIGHT_BINDING');
 const proof=record.proof;
 check(proof?.continuity?.expectedOriginalSHA256===record.originalSemanticSHA256&&proof.continuity.chunk.requestSHA256===record.chunkRequestSHA256,'UP2_OFFICIAL_ORIGINAL_CHUNK_PROOF');
 check(proof.aggregateQualification?.schema==='WORLD_ENGINE_PRESENTATION_TIMELINE_SOURCES_V1'&&proof.aggregateQualification.originalSHA256===record.originalSemanticSHA256
  &&hash(Buffer.from(proof.aggregateQualificationWireJSON))===record.aggregateQualificationSHA256
  &&semantic(JSON.parse(proof.aggregateQualificationWireJSON))===semantic(proof.aggregateQualification),'UP2_OFFICIAL_AGGREGATE_PROOF');
 const qualified=proof.aggregateQualification.chunks.find(c=>c.requestSHA256===record.chunkRequestSHA256);
 check(qualified&&qualified.sourceQualificationSHA256===record.nativeSourceQualificationSHA256&&record.payload.sourceQualificationSHA256===record.nativeSourceQualificationSHA256,'UP2_OFFICIAL_NATIVE_QUALIFICATION_PROOF');
 check((await verifyPreparedRuntimeRequest(record.payload,proof.continuity)).status==='PASS','UP2_OFFICIAL_NATIVE_SOURCE_CHANGED');
 const resources=new Map();let codeBytes=0,staticBytes=0;
 for(const row of record.resources){
  check(typeof row.url==='string'&&/^\/[A-Za-z0-9_./-]+$/.test(row.url)&&!row.url.includes('..')&&!row.url.startsWith('/modules/')&&!resources.has(row.url),'UP2_OFFICIAL_RESOURCE_URL');
  check(row.kind==='module'||row.kind==='static','UP2_OFFICIAL_RESOURCE_KIND');
  const n=row.pin?.bytes;check(Number.isSafeInteger(n)&&n>0,'UP2_OFFICIAL_RESOURCE_SIZE');
  if(row.kind==='module'){codeBytes+=n;check(codeBytes<=CODE_CAP,'UP2_OFFICIAL_CODE_CAP');}else{staticBytes+=n;check(staticBytes<=STATIC_CAP,'UP2_OFFICIAL_STATIC_CAP');}
  const bytes=await readPinnedServerFile(path.dirname(row.sourcePath),path.basename(row.sourcePath),row.pin);
  resources.set(row.url,{bytes,mime:row.mime,sha256:row.pin.sha256,kind:row.kind});
 }
 // Close the browser module graph over these exact canonical URL bytes.
 // The one preserved layout alias has a pinned conditional browser import.
 for(const [url,resource]of resources){if(resource.kind!=='module')continue;
  const source=resource.bytes.toString('utf8');
  const {imports,unsupportedDynamic}=browserModuleImports(source);
  if(unsupportedDynamic){
   check(url==='/web/map_infographic_v1/graphic_layout.mjs'&&resource.sha256==='e10fc261407d6df9f2b08452030aa93646dd156057a7e7d282501ec0f861bb66'&&unsupportedDynamic===1,'UP2_OFFICIAL_DYNAMIC_IMPORT');
   imports.push('./graphic_layout_legacy.mjs');
  }
  for(const specifier of imports){
   check(specifier.startsWith('.')||specifier.startsWith('/'),'UP2_OFFICIAL_EXTERNAL_MODULE');
   const target=new URL(specifier,'http://official.invalid'+url);
   check(target.origin==='http://official.invalid'&&!target.search&&!target.hash&&resources.get(target.pathname)?.kind==='module','UP2_OFFICIAL_MODULE_CLOSURE');
  }
 }
 for(const url of ['/three.js','/recovery/universal-presentation-v2/presentation_runtime.mjs','/recovery/universal-presentation-v2/official_candidate_bootstrap.mjs','/web/map_infographic_v1/renderer.mjs','/web/map_infographic_v1/official_candidate_admission.mjs'])check(resources.has(url),'UP2_OFFICIAL_REQUIRED_MODULE');
 // Every static native asset is the one actually qualified for this payload.
 for(const segment of record.payload.segments)for(const [role,asset]of Object.entries(segment.nativePlan.assets)){
  const resource=resources.get(asset.url);check(resource?.kind==='static'&&resource.sha256===asset.sha256,'UP2_OFFICIAL_NATIVE_ASSET_PIN_'+role);
 }
 const manager=createCandidateAssetLeaseManager(selectedAssetRegistry),token=randomBytes(32).toString('hex');
 let closed=false,pending=false,lease=null,active=null,next=0,epoch=0;
 const publicRecord={...record};delete publicRecord.resources;delete publicRecord.proof;
 const runtime=Buffer.from(canonical({prepared:record.payload,officialCandidate:{registrationId,sceneKey:record.sceneKey,transitionToken:token,record:publicRecord}}));
 const html=Buffer.from('<!doctype html><meta charset="utf-8"><body style="margin:0"><canvas id="map" width="1080" height="1920"></canvas>');
 const json=(status,value)=>({status,headers:{'content-type':'application/json','cache-control':'no-store'},body:Buffer.from(canonical(value))});
 const assertLive=()=>check(!closed,'UP2_OFFICIAL_SESSION_CLOSED');
 function close(){if(closed)return;closed=true;++epoch;lease=null;active=null;manager.dispose();resources.clear();}
 async function response({method,url,headers={},body=Buffer.alloc(0)}){
  try{
   assertLive();check(typeof url==='string'&&/^\/[A-Za-z0-9_./-]*$/.test(url)&&!url.includes('..'),'UP2_OFFICIAL_HTTP_PATH');
   if(method==='POST'){
    check(url==='/candidate-window'&&headers['x-world-engine-capability']===token&&headers['content-type']==='application/json'&&body.length<=2048,'UP2_OFFICIAL_WINDOW_AUTH');
    const request=JSON.parse(Buffer.from(body));check(Object.keys(request).sort().join(',')==='sceneKey,windowId'&&request.sceneKey===record.sceneKey&&windows.has(request.windowId),'UP2_OFFICIAL_WINDOW_REQUEST');
    check(!pending,'UP2_OFFICIAL_TRANSITION_BUSY');
    if(active===request.windowId&&lease){lease.assertCurrent();return json(200,{windowId:active,epoch,leaseMetadata:lease.metadata});}
    check(record.windows[next]?.id===request.windowId,'UP2_OFFICIAL_WINDOW_ORDER');
    pending=true;lease=null;active=null;const current=++epoch;
    try{const acquired=await manager.transition(windows.get(request.windowId).request);assertLive();check(epoch===current,'UP2_OFFICIAL_TRANSITION_REVOKED');const selected=windows.get(request.windowId);check(acquired.metadata.layerId===selected.layerId&&acquired.metadata.windowQualificationSha256===selected.windowQualificationSha256,'UP2_OFFICIAL_WINDOW_QUALIFICATION');lease=acquired;active=request.windowId;next++;return json(200,{windowId:active,epoch,leaseMetadata:lease.metadata});}
    catch(error){manager.release();lease=null;active=null;throw error;}finally{pending=false;}
   }
   check(method==='GET'||method==='HEAD','UP2_OFFICIAL_HTTP_METHOD');
   let result;
   if(url==='/')result={status:200,headers:{'content-type':'text/html'},body:Buffer.from(html)};
   else if(url==='/runtime.json')result={status:200,headers:{'content-type':'application/json'},body:Buffer.from(runtime)};
   else if(url==='/lease-status')result=json(200,{alive:true,epoch,windowId:active,pending,sceneKey:record.sceneKey,windowQualificationSha256:lease?.metadata.windowQualificationSha256??null});
   else if(url.startsWith('/candidate-assets/sha256/')){check(lease&&!pending,'UP2_OFFICIAL_ASSET_LEASE_REQUIRED');const key=url.slice('/candidate-assets/'.length);result={status:200,headers:{'content-type':'application/octet-stream'},body:lease.read(key)};}
   else{const resource=resources.get(url);check(resource,'UP2_OFFICIAL_RESOURCE_NOT_REGISTERED');result={status:200,headers:{'content-type':resource.mime},body:Buffer.from(resource.bytes)};}
   result.headers={...result.headers,'cache-control':'no-store','content-length':result.body.length};if(method==='HEAD')result.body=Buffer.alloc(0);return result;
  }catch(error){return json(closed?410:400,{error:String(error.message)});}
 }
 return Object.freeze({response,close,assertLive,payload:structuredClone(record.payload),metadata:Object.freeze({registrationId,sceneKey:record.sceneKey,codeBytes,staticBytes,codeCap:CODE_CAP,staticCap:STATIC_CAP,pngCap:67108864,binaryCap:71000064,scope:'PER_SESSION_SERVER_OWNED_RETENTION_NOT_PROCESS_OR_GPU_PEAK',productionAdmitted:false,gpuVerified:false})});
}
