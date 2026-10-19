/** Additive browser aliases over the unchanged, fully source-bound completion. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url)),hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export const OVERNIGHT_BROWSER_BINDINGS=Object.freeze({
 '/universal/long_adapter.mjs':'browser_adapter.mjs',
 '/overnight-v3/visual_extensions.mjs':'visual_extensions.mjs'});
const referenceFiles=['gain_style_core.mjs','frontier_profile_core.mjs','unit-size-profile.mjs','native_domain_coverage.mjs'];
const webFiles=['camera_director_v4.mjs','camera_director_v5.mjs','event_contract_v1.mjs','event_line_pass_v1.mjs',
 'event_line_v1.mjs','event_occlusion_policy_v1.mjs','flow_graphic_pass_v2.mjs','local_detail_admission.mjs',
 'national_unit_badge_v1.mjs','reference_camera_adapter_v1.mjs','reference_combat_overlay_v2.mjs',
 'reference_presentation_adapter_v2.mjs','scale_contract.mjs'];
export async function existingVisualSourceRecords({readSource=readFile}={}){
 const result=[];
 for(const[name,directory,prefix]of [
  ...referenceFiles.map(name=>[name,path.resolve(root,'../reference-visual-master-v2'),'/ref2/']),
  ...webFiles.map(name=>[name,path.resolve(root,'../../web/map_infographic_v1'),'/web/map_infographic_v1/'])]){
  const file=path.join(directory,name),raw=await readSource(file);
  result.push({url:prefix+name,file,bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex')});
 }
 return result;
}
export function extendOvernightServerPlan(inherited,{request,records,manifestSHA256,sourceCatalog,existingRecords=[]}={}){
 assert.equal(request?.schema,'WORLD_ENGINE_OVERNIGHT_CAPTURE_REQUEST_V3');
 assert.equal(request.profile,'OVERNIGHT_SAFE_V3');
 assert.equal(request.overnightV3?.operation,'PREVIEW_5S','OVERNIGHT_PREVIEW_OPERATION_ONLY');
 assert.equal(request.preview?.range?.frameCount,150,'OVERNIGHT_150_FRAMES_ONLY');
 assert.equal(request.sourceManifestSHA256,manifestSHA256,'OVERNIGHT_SOURCE_MANIFEST_BINDING_REQUIRED');
 assert.equal(inherited.completionIntegrity?.profileSHA256,hash(request.parentCaptureRequest.completionV2),
  'OVERNIGHT_ACTUAL_COMPLETION_PARENT_REQUIRED');
 assert.equal(request.preview.bindings?.sourceCatalogSHA256,hash(sourceCatalog),
  'OVERNIGHT_PACKAGE_SOURCE_CATALOG_BINDING_REQUIRED');
 const config=structuredClone(inherited.serverConfig),bindings=new Map(config.bindings.map(row=>[row.url,row])),
  byName=new Map(records.map(row=>[row.name,row]));
 assert.equal(byName.size,records.length,'OVERNIGHT_SOURCE_DUPLICATE');
 const old=bindings.get('/universal/long_adapter.mjs');
 assert.ok(old&&!bindings.has('/overnight-v3/parent_adapter.mjs'),'OVERNIGHT_PARENT_ALIAS_REQUIRED');
 bindings.set('/overnight-v3/parent_adapter.mjs',{...old,url:'/overnight-v3/parent_adapter.mjs'});
 for(const[url,name]of Object.entries(OVERNIGHT_BROWSER_BINDINGS)){
  const row=byName.get(name);assert.ok(row&&/^[a-f0-9]{64}$/.test(row.sha256)&&row.bytes>0,'OVERNIGHT_BROWSER_SOURCE_REQUIRED');
  assert.ok(url==='/universal/long_adapter.mjs'||!bindings.has(url),'OVERNIGHT_ALIAS_COLLISION');
  bindings.set(url,{url,path:row.file,sha256:row.sha256,bytes:row.bytes});
 }
 for(const row of existingRecords){
  assert.ok(row.url.startsWith('/ref2/')||row.url.startsWith('/web/map_infographic_v1/'),'OVERNIGHT_EXISTING_OWNER_ALIAS_REQUIRED');
  const previous=bindings.get(row.url);
  if(previous)assert.equal(previous.sha256,row.sha256,'OVERNIGHT_EXISTING_SOURCE_CONFLICT');
  else bindings.set(row.url,{url:row.url,path:row.file,sha256:row.sha256,bytes:row.bytes});
 }
 const identity={schema:'WORLD_ENGINE_OVERNIGHT_RUNTIME_INTEGRITY_V3',manifestSHA256,
  requestSHA256:hash(request),profileSHA256:hash(request.overnightV3),catalogSHA256:hash(sourceCatalog),
  previewSHA256:hash(request.preview),sourceSelectionCPUOnly:true,actualGPUOutputVerified:false};
 config.runtimeConfig.overnightV3=structuredClone(request.overnightV3);
 config.runtimeConfig.overnightPreview=structuredClone(request.preview);
 config.runtimeConfig.overnightSourceCatalog=structuredClone(sourceCatalog);
 // Only this new, source-sealed server config adopts the additive authority.
 // The frozen parent request, history bytes and parent manifests stay intact.
 config.runtimeConfig.completionSourceCatalog=structuredClone(sourceCatalog);
 config.runtimeConfig.completionIntegrity={...config.runtimeConfig.completionIntegrity,catalogSHA256:hash(sourceCatalog)};
 config.runtimeConfig.overnightIntegrity=identity;config.bindings=[...bindings.values()];
 return{...inherited,serverConfig:config,completionIntegrity:structuredClone(config.runtimeConfig.completionIntegrity),
  overnightRequest:structuredClone(request),overnightIntegrity:identity,
  sourceBindings:[...inherited.sourceBindings,...records,...existingRecords].map(row=>row.file?
   {path:row.file,bytes:row.bytes,sha256:row.sha256}:row),
  sourceSignature:hash({parent:inherited.sourceSignature,overnight:identity,existingRecords}),
  full80sRenderAllowed:false};
}
