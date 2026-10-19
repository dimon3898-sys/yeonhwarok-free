/** Sealed test-only import-edge instrumentation over existing source bytes. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const sha=raw=>createHash('sha256').update(raw).digest('hex');
export const OBSERVED_EDGES=Object.freeze([
 ['/universal/long_adapter.mjs','/universal/reconciliation_parent_adapter.mjs','observer_adapter.mjs'],
 ['/reference/reference_source_material.mjs','/reference/reconciliation_parent_source.mjs','source_observer.mjs'],
 ['/production-v3/production_area_pass.mjs','/production-v3/reconciliation_parent_area.mjs','area_observer.mjs'],
 ['/production-v3/production_native_camera.mjs','/production-v3/reconciliation_parent_camera.mjs','camera_observer.mjs']]);
export async function extendObservedPlan(plan){
 assert.equal(plan.serverConfig.runtimeConfig.testOnlySoftwareProbe,true,'RECONCILIATION_SOFTWARE_ONLY');
 const raw=await readFile(path.join(HERE,'RECONCILIATION_FILES.json')),manifest=JSON.parse(raw),own=[];
 for(const name of [...OBSERVED_EDGES.map(row=>row[2]),'pass_observer.mjs']){
  const file=path.join(HERE,name),bytes=await readFile(file);
  assert.equal(sha(bytes),manifest.files[name],'RECONCILIATION_SOURCE_CHANGED');
  own.push({name,path:file,sha256:sha(bytes),bytes:bytes.length});
 }
 const config=structuredClone(plan.serverConfig),bindings=new Map(config.bindings.map(row=>[row.url,row])),parents=[];
 for(const [url,alias,name] of OBSERVED_EDGES){
  const old=bindings.get(url),replacement=own.find(row=>row.name===name);
  assert.ok(old&&!bindings.has(alias),'RECONCILIATION_EXACT_ORIGINAL_EDGE_REQUIRED');
  bindings.set(alias,{...old,url:alias});parents.push({...old});
  bindings.set(url,{url,path:replacement.path,sha256:replacement.sha256,bytes:replacement.bytes});
 }
 const observer=own.find(row=>row.name==='pass_observer.mjs');
 assert.ok(!bindings.has('/reconciliation/pass_observer.mjs'));
 bindings.set('/reconciliation/pass_observer.mjs',{url:'/reconciliation/pass_observer.mjs',...observer});
 const r=plan.overnightRequest.preview.range;
 config.bindings=[...bindings.values()];
 config.runtimeConfig.reconciliationObservation={schema:'WORLD_ENGINE_SOURCE_BOUND_OBSERVATION_V1',
  sourceManifestSHA256:sha(raw),preservedOvernightManifestSHA256:plan.overnightRequest.sourceManifestSHA256,
  planSHA256:plan.planSha256,originalEdges:parents,sampleFrames:[r.startFrame,r.startFrame+74,r.endFrame-1],
  range:structuredClone(r),productionRenderAllowed:false,physicalNvidiaVerified:false};
 const oldCheck=plan.assertSourceUnchanged;
 return {...plan,serverConfig:config,reconciliationObservation:config.runtimeConfig.reconciliationObservation,
  assertSourceUnchanged:async()=>{
   await oldCheck();assert.equal(sha(await readFile(path.join(HERE,'RECONCILIATION_FILES.json'))),sha(raw));
   for(const row of own)assert.equal(sha(await readFile(row.path)),row.sha256);
   return true;
  }};
}
