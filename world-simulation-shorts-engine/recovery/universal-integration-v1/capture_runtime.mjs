/** Source-bound presentation aliases over frozen V4 plus original NVIDIA opener. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import * as front from '../verified-front-data-v4-recovery/front_runtime.mjs';
import * as native from '../universal-auto-video-v2/long_runtime.mjs';
import {extendIntegrationServerPlan} from './runtime_binding.mjs';
export const {sha,engine,repo}=native;
export const root=path.dirname(fileURLToPath(import.meta.url));
const seals=new WeakMap(),hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
export async function verifiedIntegrationSources(request){
 assert.equal(request?.schema,'WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1','INTEGRATION_CAPTURE_REQUEST_REQUIRED');
 assert.ok(hex(request.sourceManifestSHA256),'INTEGRATION_CAPTURE_SOURCE_SHA_REQUIRED');
 const raw=await native.boundedSource(path.join(root,'INTEGRATION_FILES.json'));
 assert.equal(sha(raw),request.sourceManifestSHA256,'INTEGRATION_CAPTURE_MANIFEST_CHANGED');
 const manifest=JSON.parse(raw);assert.equal(manifest.schema,'WORLD_ENGINE_UNIVERSAL_INTEGRATION_FILES_V1');
 const records=[];assert.ok(manifest.files&&Object.keys(manifest.files).length<=128);
 for(const [name,expected]of Object.entries(manifest.files)){
  assert.ok(name&&!path.isAbsolute(name)&&!/[\\\0]/.test(name)&&name.split('/').every(p=>p&&p!=='.'&&p!=='..')&&hex(expected),'INTEGRATION_CAPTURE_SOURCE_NAME_INVALID');
  const file=path.join(root,name),bytes=await native.boundedSource(file);assert.equal(sha(bytes),expected,'INTEGRATION_CAPTURE_SOURCE_CHANGED');
  records.push({name,file,bytes:bytes.length,sha256:expected});
 }
 return{records,manifestSha256:sha(raw)};
}
export async function loadLongRuntimePlan(options={}){
 const file=path.join(path.dirname(options.planFile),'INTEGRATION_REQUEST.json'),
  request=JSON.parse(await native.boundedSource(file)),verified=await verifiedIntegrationSources(request);
 const inherited=await front.loadLongRuntimePlan(options);
 assert.equal(request.videoPlanSHA256,inherited.planSha256,'INTEGRATION_CAPTURE_PLAN_BINDING_REQUIRED');
 const plan=extendIntegrationServerPlan(inherited,{visualProfile:request.integration?.visualProfile,
  records:verified.records,manifestSha256:verified.manifestSha256});
 const oldAssert=inherited.assertSourceUnchanged;
 plan.assertSourceUnchanged=async()=>{await oldAssert();await verifiedIntegrationSources(request);return true;};
 plan.integrationRequest=request;seals.set(plan,sha(Buffer.from(JSON.stringify(plan.serverConfig))));return plan;
}
export function assertIntegratedCapturedFrame(captured,plan){
 const diagnostic=captured?.diagnostic,graphics=diagnostic?.area?.graphics?.productionVisual;
 if(diagnostic?.productionV3?.geometryClock?.eventEnabled||diagnostic?.frontV4?.selection?.sourceActiveFrame)
  assert.ok(graphics,'INTEGRATION_ACTUAL_DRAW_SETTING_EVIDENCE_REQUIRED');
 if(graphics){for(const key of ['territoryOpacity','frontCoreWidthPixels','frontGlowRadiusPixels','frontGlowGain'])
  assert.equal(graphics[key],plan.integrationV1.visualProfile[key],'INTEGRATION_ACTUAL_DRAW_SETTING_MISMATCH');}
 return captured;
}
export async function openLongRuntime({loadedPlan=null,...options}={}){
 const plan=loadedPlan??await loadLongRuntimePlan(options);
 assert.equal(seals.get(plan),sha(Buffer.from(JSON.stringify(plan.serverConfig))),'INTEGRATION_SEALED_SERVER_PLAN_REQUIRED');
 assert.equal(plan.frontExecutionBinding?.hardwareEligible,true,'INTEGRATION_TEST_ONLY_HARDWARE_FORBIDDEN');
 await plan.assertSourceUnchanged();
 // Original immutable NVIDIA admission, browser/backend identity and loopback isolation.
 const runtime=await native.openLongRuntime({...options,loadedPlan:plan});
 try{
  for(const kind of ['area','camera']){
   const actual=runtime.info.evidence?.[kind]?.integrationV1;
   assert.equal(actual?.profileSha256,plan.integrationV1.profileSha256,'INTEGRATION_BROWSER_FACTORY_NOT_SELECTED');
   assert.equal(actual?.existingEngineCalled,true,'INTEGRATION_ORIGINAL_FACTORY_REQUIRED');
  }
  const page=new Proxy(runtime.page,{get(target,key){
   if(key==='evaluate')return async(...args)=>assertIntegratedCapturedFrame(await front.assertFrontCapturedFrame(await target.evaluate(...args),plan),plan);
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});return{...runtime,page};
 }catch(error){await runtime.close();throw error;}
}
