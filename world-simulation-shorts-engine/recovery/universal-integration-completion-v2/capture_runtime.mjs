/** Immutable completion source plan plus the original native NVIDIA opener. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import * as front from '../verified-front-data-v4-recovery/front_runtime.mjs';
import * as native from '../universal-auto-video-v2/long_runtime.mjs';
import {extendCompletionServerPlan} from './runtime_binding.mjs';
export const {sha,engine,repo}=native;
export const root=path.dirname(fileURLToPath(import.meta.url));
const seals=new WeakMap();
export function selectCompletionParentInputs(inherited){
 assert.ok(inherited?.document&&Number.isSafeInteger(inherited.document.totalFrames)&&inherited.frontProfile,
  'COMPLETION_ACTUAL_PARENT_DOCUMENT_REQUIRED');
 return{plan:inherited.document,frontProfile:inherited.frontProfile};
}
async function sources(directory,name,expected){
 const raw=await native.boundedSource(path.join(directory,name));
 assert.equal(sha(raw),expected,'COMPLETION_SOURCE_MANIFEST_CHANGED');
 const manifest=JSON.parse(raw),records=[];
 for(const[name,expected]of Object.entries(manifest.files)){
  assert.ok(name&&path.basename(name)===name&&!name.includes('\\'),'COMPLETION_SOURCE_NAME_REQUIRED');
  const file=path.join(directory,name),bytes=await native.boundedSource(file);
  assert.equal(sha(bytes),expected,'COMPLETION_SOURCE_CHANGED');records.push({name,file,bytes:bytes.length,sha256:expected});
 }
 return{manifest,records};
}
export async function loadLongRuntimePlan(options={}){
 const request=JSON.parse(await native.boundedSource(path.join(path.dirname(options.planFile),'INTEGRATION_REQUEST.json')));
 assert.equal(request?.completionV2?.profile,'VISUAL_UNIFIED_COMPLETION_V2','COMPLETION_CAPTURE_PROFILE_REQUIRED');
 const own=await sources(root,'COMPLETION_FILES.json',request.sourceManifestSHA256),
  previous=await sources(path.join(root,'../universal-integration-v1'),'INTEGRATION_FILES.json',request.previousManifestSHA256);
 assert.equal(own.manifest.previousManifestSHA256,request.previousManifestSHA256);
 const inherited=await front.loadLongRuntimePlan(options);
 assert.equal(request.videoPlanSHA256,inherited.planSha256,'COMPLETION_CAPTURE_PLAN_CHANGED');
 const plan=extendCompletionServerPlan(inherited,{visualProfile:request.integration.visualProfile,
  completion:request.completionV2,previousRecords:previous.records,previousManifestSha256:request.previousManifestSHA256,
  records:own.records,manifestSha256:request.sourceManifestSHA256,
  sourceCatalog:JSON.parse(await native.boundedSource(path.join(root,'SOURCE_DATA_CATALOG.json'))),
  ...selectCompletionParentInputs(inherited)});
 const old=inherited.assertSourceUnchanged;
 plan.assertSourceUnchanged=async()=>{await old();await sources(root,'COMPLETION_FILES.json',request.sourceManifestSHA256);
  await sources(path.join(root,'../universal-integration-v1'),'INTEGRATION_FILES.json',request.previousManifestSHA256);return true;};
 seals.set(plan,sha(Buffer.from(JSON.stringify(plan.serverConfig))));return plan;
}
export function assertCompletionFrame(captured,plan){
 const d=captured?.diagnostic;
 assert.equal(d?.completionV2?.profileSHA256,plan.completionIntegrity.profileSHA256,'COMPLETION_ACTUAL_FRAME_PROFILE_REQUIRED');
 assert.equal(d.completionV2.frame,d.frame,'COMPLETION_GLOBAL_CLOCK_MISMATCH');
 if(d.area?.graphics&&plan.completionV2.frontier.enabled){
  assert.ok(d.area.graphics.completionFrontier,'COMPLETION_ACTUAL_FRONTIER_OWNER_REQUIRED');
  assert.equal(d.area.graphics.completionFrontier.motionConnected,true,'COMPLETION_FRONTIER_SOURCE_CLOCK_NOT_CONNECTED');
 }
 return front.assertFrontCapturedFrame(captured,plan);
}
export async function openLongRuntime({loadedPlan=null,...options}={}){
 const plan=loadedPlan??await loadLongRuntimePlan(options);
 assert.equal(seals.get(plan),sha(Buffer.from(JSON.stringify(plan.serverConfig))),'COMPLETION_SEALED_SERVER_PLAN_REQUIRED');
 assert.equal(plan.frontExecutionBinding?.hardwareEligible,true,'COMPLETION_HARDWARE_PROFILE_REQUIRED');
 await plan.assertSourceUnchanged();
 const runtime=await native.openLongRuntime({...options,loadedPlan:plan});
 try{
  assert.equal(runtime.info.completionV2?.integrity?.profileSHA256,plan.completionIntegrity.profileSHA256,
   'COMPLETION_ACTUAL_BROWSER_BOOT_NOT_SELECTED');
  const page=new Proxy(runtime.page,{get(target,key){
   if(key==='evaluate')return async(...args)=>assertCompletionFrame(await target.evaluate(...args),plan);
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});return{...runtime,page};
 }catch(error){await runtime.close();throw error;}
}
