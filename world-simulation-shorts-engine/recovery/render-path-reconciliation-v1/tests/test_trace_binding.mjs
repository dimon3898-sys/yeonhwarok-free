import test from 'node:test';
import assert from 'node:assert/strict';
import {extendObservedPlan,OBSERVED_EDGES} from '../trace_binding.mjs';
const fixture=()=>({serverConfig:{runtimeConfig:{testOnlySoftwareProbe:true},
 bindings:OBSERVED_EDGES.map(([url],index)=>({url,path:'/preserved/owner-'+index,
  sha256:String(index+1).repeat(64),bytes:index+1}))},
 overnightRequest:{sourceManifestSHA256:'c'.repeat(64),preview:{range:{startFrame:300,endFrame:450,frameCount:150}}},
 planSha256:'d'.repeat(64),assertSourceUnchanged:async()=>true});
test('observed import edges retain every exact parent and original plan',async()=>{
 const old=fixture(),snapshot=JSON.stringify(old),next=await extendObservedPlan(old);
 assert.equal(JSON.stringify(old),snapshot);
 for(const [url,parent] of OBSERVED_EDGES){
  const original=old.serverConfig.bindings.find(row=>row.url===url);
  assert.deepEqual(next.serverConfig.bindings.find(row=>row.url===parent),{...original,url:parent});
  assert.notEqual(next.serverConfig.bindings.find(row=>row.url===url).sha256,original.sha256);
 }
 assert.deepEqual(next.reconciliationObservation.sampleFrames,[300,374,449]);
 assert.equal(next.reconciliationObservation.productionRenderAllowed,false);
 assert.equal(await next.assertSourceUnchanged(),true);
});
test('production entry cannot select explicit software observation',async()=>{
 const old=fixture();old.serverConfig.runtimeConfig.testOnlySoftwareProbe=false;
 await assert.rejects(()=>extendObservedPlan(old),/RECONCILIATION_SOFTWARE_ONLY/);
});
test('missing original executable edge cannot silently fall back',async()=>{
 const old=fixture();old.serverConfig.bindings.shift();
 await assert.rejects(()=>extendObservedPlan(old),/RECONCILIATION_EXACT_ORIGINAL_EDGE_REQUIRED/);
});
test('alias collision cannot overwrite an existing runtime source',async()=>{
 const old=fixture();old.serverConfig.bindings.push({...old.serverConfig.bindings[0],url:OBSERVED_EDGES[0][1]});
 await assert.rejects(()=>extendObservedPlan(old),/RECONCILIATION_EXACT_ORIGINAL_EDGE_REQUIRED/);
});
test('parent source validation is retained and error is not suppressed',async()=>{
 const old=fixture();old.assertSourceUnchanged=async()=>{throw Error('PRESERVED_SOURCE_CHANGED');};
 const next=await extendObservedPlan(old);
 await assert.rejects(()=>next.assertSourceUnchanged(),/PRESERVED_SOURCE_CHANGED/);
});
