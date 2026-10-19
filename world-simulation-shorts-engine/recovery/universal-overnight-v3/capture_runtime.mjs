/** New sealed selection; the original NVIDIA opener remains mandatory. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import * as parent from '../universal-integration-completion-v2/capture_runtime.mjs';
import * as native from '../universal-auto-video-v2/long_runtime.mjs';
import {extendOvernightServerPlan,existingVisualSourceRecords} from './runtime_binding.mjs';
const execute=promisify(execFile),root=path.dirname(fileURLToPath(import.meta.url)),seals=new WeakMap(),
 hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export const {sha,engine,repo}=native;
async function ownSources(expected){
 const raw=await native.boundedSource(path.join(root,'OVERNIGHT_FILES.json'));
 assert.equal(sha(raw),expected,'OVERNIGHT_CAPTURE_SOURCE_MANIFEST_CHANGED');
 const manifest=JSON.parse(raw),records=[];
 for(const[name,digest]of Object.entries(manifest.files)){
  assert.ok(path.basename(name)===name&&!name.includes('\\'),'OVERNIGHT_SOURCE_NAME_REQUIRED');
  const file=path.join(root,name),bytes=await native.boundedSource(file);
  assert.equal(sha(bytes),digest,'OVERNIGHT_CAPTURE_SOURCE_CHANGED');records.push({name,file,bytes:bytes.length,sha256:digest});
 }return records;
}
export async function extendLoadedOvernightPlan(inherited,options={}){
 const requestFile=options.overnightRequestFile??process.env.WORLD_ENGINE_OVERNIGHT_REQUEST_FILE
  ??path.join(path.dirname(options.planFile),'OVERNIGHT_REQUEST.json'),
  checked=await execute('/usr/bin/python3',['-B',path.join(root,'runtime_authority.py'),
   '--request-file',requestFile,'--plan-file',options.planFile],{maxBuffer:8*1024*1024,timeout:45000}),
  request=JSON.parse(checked.stdout),records=await ownSources(request.sourceManifestSHA256),
  existingRecords=await existingVisualSourceRecords({readSource:native.boundedSource}),
  catalogResult=await execute('/usr/bin/python3',['-B',path.join(root,'data_readiness.py'),'--catalog'],
   {maxBuffer:4*1024*1024,timeout:45000}),catalog=JSON.parse(catalogResult.stdout),
  plan=extendOvernightServerPlan(inherited,{request,records,manifestSHA256:request.sourceManifestSHA256,
   sourceCatalog:catalog,existingRecords}),old=inherited.assertSourceUnchanged;
 const requestHash=sha(await native.boundedSource(requestFile));
 plan.assertSourceUnchanged=async()=>{await old();await ownSources(request.sourceManifestSHA256);
  assert.equal(sha(await native.boundedSource(requestFile)),requestHash,'OVERNIGHT_REQUEST_CHANGED_DURING_CAPTURE');
  for(const row of existingRecords)assert.equal(sha(await native.boundedSource(row.file)),row.sha256,'OVERNIGHT_EXISTING_OWNER_CHANGED');
  return true;};
 seals.set(plan,hash(plan.serverConfig));return plan;
}
export async function loadLongRuntimePlan(options={}){
 const inherited=await parent.loadLongRuntimePlan(options);
 return extendLoadedOvernightPlan(inherited,options);
}
export function assertOvernightFrame(captured,plan){
 const diagnostic=captured?.diagnostic,range=plan.overnightRequest.preview.range;
 assert.equal(diagnostic?.overnightV3?.profileSHA256,plan.overnightIntegrity.profileSHA256,
  'OVERNIGHT_ACTUAL_BROWSER_PROFILE_REQUIRED');
 assert.equal(diagnostic.overnightV3.frame,diagnostic.frame,'OVERNIGHT_ACTUAL_GLOBAL_FRAME_REQUIRED');
 assert.ok(diagnostic.frame>=range.startFrame&&diagnostic.frame<range.endFrame,'OVERNIGHT_CAPTURE_RANGE_EXCEEDED');
 return parent.assertCompletionFrame(captured,plan);
}
export async function openLongRuntime({loadedPlan=null,...options}={}){
 const plan=loadedPlan??await loadLongRuntimePlan(options);
 assert.equal(seals.get(plan),hash(plan.serverConfig),'OVERNIGHT_SEALED_CONFIG_REQUIRED');
 assert.equal(plan.frontExecutionBinding?.hardwareEligible,true,'OVERNIGHT_NATIVE_HARDWARE_PROFILE_REQUIRED');
 await plan.assertSourceUnchanged();
 const runtime=await native.openLongRuntime({...options,loadedPlan:plan});
 try{
  assert.equal(runtime.info.overnightV3?.integrity?.profileSHA256,plan.overnightIntegrity.profileSHA256,
   'OVERNIGHT_ACTUAL_BOOT_REQUIRED');
  const page=new Proxy(runtime.page,{get(target,key){
   if(key==='evaluate')return async(...args)=>assertOvernightFrame(await target.evaluate(...args),plan);
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});return{...runtime,page};
 }catch(error){await runtime.close();throw error;}
}
