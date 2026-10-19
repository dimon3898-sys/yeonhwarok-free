/** Strict second-layer binding over the immutable V1 and V4 source plans. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {extendIntegrationServerPlan} from '../universal-integration-v1/runtime_binding.mjs';
import {compileSuppliedFrontMotion} from './frontier_extension.mjs';
import {suppliedFrontObservations} from './source_observations.mjs';
const hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export const COMPLETION_BROWSER_BINDINGS=Object.freeze({
 '/universal/long_adapter.mjs':'browser_adapter.mjs',
 '/production-v3/production_native_camera.mjs':'production_camera_bridge.mjs',
 '/production-v3/production_area_pass.mjs':'production_area_bridge.mjs',
 '/completion-v2/camera_extension.mjs':'camera_extension.mjs',
 '/completion-v2/frontier_extension.mjs':'frontier_extension.mjs',
 '/completion-v2/frame_context.mjs':'frame_context.mjs',
 '/completion-v2/event_flow_binding.mjs':'event_flow_binding.mjs'});
export function extendCompletionServerPlan(inherited,{visualProfile,completion,previousRecords,previousManifestSha256,
 records,manifestSha256,sourceCatalog,plan,frontProfile}={}){
 assert.equal(completion?.schema,'WORLD_ENGINE_UNIVERSAL_COMPLETION_V2');
 assert.equal(completion?.profile,'VISUAL_UNIFIED_COMPLETION_V2');
 assert.ok(/^[a-f0-9]{64}$/.test(manifestSha256));
 const base=extendIntegrationServerPlan(inherited,{visualProfile,records:previousRecords,manifestSha256:previousManifestSha256}),
  config=structuredClone(base.serverConfig),bindings=new Map(config.bindings.map(row=>[row.url,row])),
  byName=new Map(records.map(row=>[row.name,row]));
 assert.equal(byName.size,records.length,'COMPLETION_SOURCE_DUPLICATE');
 for(const [url,parent]of [['/universal/long_adapter.mjs','/completion-v2/parent_adapter.mjs'],
  ['/integration-v1/parent_production_native_camera.mjs','/completion-v2/parent_camera.mjs']]){
  assert.ok(bindings.has(url)&&!bindings.has(parent),'COMPLETION_PARENT_FACTORY_ALIAS_REQUIRED');
  bindings.set(parent,{...bindings.get(url),url:parent});
 }
 for(const[url,name]of Object.entries(COMPLETION_BROWSER_BINDINGS)){
  const record=byName.get(name);assert.ok(record&&/^[a-f0-9]{64}$/.test(record.sha256)&&record.bytes>0,'COMPLETION_SOURCE_BINDING_REQUIRED');
  if(!['/universal/long_adapter.mjs','/production-v3/production_native_camera.mjs','/production-v3/production_area_pass.mjs'].includes(url))
   assert.ok(!bindings.has(url),'COMPLETION_BROWSER_ALIAS_COLLISION');
  bindings.set(url,{url,path:record.file,sha256:record.sha256,bytes:record.bytes});
 }
 const observations=suppliedFrontObservations(plan,frontProfile),motion=compileSuppliedFrontMotion({
  observations,totalFrames:plan.totalFrames,profile:completion.frontier});
 config.runtimeConfig.completionV2=structuredClone(completion);
 config.runtimeConfig.completionFrontierMotion=motion;
 config.runtimeConfig.completionSourceCatalog=structuredClone(sourceCatalog);
 config.runtimeConfig.completionIntegrity={schema:'WORLD_ENGINE_COMPLETION_RUNTIME_INTEGRITY_V2',
  manifestSHA256:manifestSha256,profileSHA256:hash(completion),motionSHA256:hash(motion),catalogSHA256:hash(sourceCatalog),
  browserSourceSignature:hash(Object.entries(COMPLETION_BROWSER_BINDINGS).map(([url,name])=>({url,sha256:byName.get(name).sha256}))),
  actualGPUOutputVerified:false};
 config.bindings=[...bindings.values()];
 return{...base,serverConfig:config,completionV2:structuredClone(completion),
  completionIntegrity:structuredClone(config.runtimeConfig.completionIntegrity),
  sourceBindings:[...base.sourceBindings,...records.map(row=>({path:row.file,bytes:row.bytes,sha256:row.sha256}))],
  sourceSignature:hash({parent:base.sourceSignature,completion:config.runtimeConfig.completionIntegrity}),
  sourceSelectionCPUOnly:true};
}
