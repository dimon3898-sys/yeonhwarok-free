/** Additive V3 binding/verification over the unchanged native long runtime. */
import assert from 'node:assert/strict';
import {readFile,lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export const root=path.dirname(fileURLToPath(import.meta.url)),
 originalRuntimeURL=new URL('../universal-auto-video-v2/long_runtime.mjs',import.meta.url).href;
const originalPath=fileURLToPath(originalRuntimeURL),
 parentSHA='ee50049ad9967b22d5aa7dae09bd9e5295d22882c5d5c3db2b2cd4dec25dc606',
 verifierSHA='c63757663cba3c3e8efd4f9606be5a78ef8ac5e6d9c54a18c1adfab8f6e8ca42',
 hash=bytes=>createHash('sha256').update(bytes).digest('hex'),execute=promisify(execFile),
 hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),verifiedPlans=new WeakMap();
assert.ok(!(await lstat(originalPath)).isSymbolicLink(),'PRODUCTION_PARENT_RUNTIME_SYMLINK_FORBIDDEN');
assert.equal(hash(await readFile(originalPath)),parentSHA,'PRODUCTION_PARENT_RUNTIME_CHANGED');
const parent=await import(originalRuntimeURL);
export const engine=parent.engine,repo=parent.repo,sha=parent.sha,boundedSource=parent.boundedSource,
 engineRelative=parent.engineRelative,validateNativePayload=parent.validateNativePayload;
export const BROWSER_BINDINGS=Object.freeze({
 '/universal/long_adapter.mjs':'production_adapter.mjs',
 '/production-v3/production_visual_profile.mjs':'production_visual_profile.mjs',
 '/production-v3/production_camera.mjs':'production_camera.mjs',
 '/production-v3/production_native_camera.mjs':'production_native_camera.mjs',
 '/production-v3/production_area_pass.mjs':'production_area_pass.mjs',
});

export function validateLongRuntimeDocument(document,sceneId){
 const scene=parent.validateLongRuntimeDocument(document,sceneId);
 assert.equal(document.productionV3?.runtimeProfile,'UNIVERSAL_PRODUCTION_V3','PRODUCTION_DOCUMENT_PROFILE_REQUIRED');
 assert.equal(document.renderProfile?.productionAdapter,'UNIVERSAL_PRODUCTION_V3','PRODUCTION_DOCUMENT_ADAPTER_REQUIRED');
 assert.equal(scene.renderProfile?.productionAdapter,'UNIVERSAL_PRODUCTION_V3','PRODUCTION_SCENE_ADAPTER_REQUIRED');
 assert.ok(Array.isArray(document.productionV3.eventChapters)&&document.productionV3.eventChapters.length>0,'PRODUCTION_CHAPTERS_REQUIRED');
 return scene;
}

async function verifySources(requireStaged){
 assert.equal(sha(await boundedSource(path.join(root,'source_manifest.py'))),verifierSHA,'PRODUCTION_SOURCE_VERIFIER_CHANGED');
 const args=['-B',path.join(root,'source_manifest.py'),'--verify-extension',...(requireStaged?[]:['--source-only'])],
  result=JSON.parse((await execute('/usr/bin/python3',args,{maxBuffer:2*1024*1024})).stdout);
 assert.equal(result.status,'PASS','PRODUCTION_SOURCE_CLOSURE_REQUIRED');
 assert.equal(result.profileId,'UNIVERSAL_PRODUCTION_V3');assert.ok(hex(result.manifestSha256));
 return result;
}

async function validatePythonPlan(planFile){
 const code="import json,sys;sys.path.insert(0,sys.argv[1]);from scene_planner import validate_production_plan;validate_production_plan(json.load(open(sys.argv[2])),require_renderable=True);print('PRODUCTION_PLAN_VALID')",
  response=await execute('/usr/bin/python3',['-B','-c',code,root,planFile],{maxBuffer:1024*1024});
 assert.equal(response.stdout.trim(),'PRODUCTION_PLAN_VALID','PRODUCTION_VERIFIED_PLAN_REQUIRED');
}

/** Pure binding composition. Only loadLongRuntimePlan registers plans eligible
 * for production hardware dispatch; this helper alone cannot authorize it. */
export function extendProductionServerPlan(inherited,{manifestSha256,browserRecords,sourceRecords}){
 validateLongRuntimeDocument(inherited.document,inherited.scene.sceneId);
 assert.ok(hex(manifestSha256)&&Array.isArray(browserRecords)&&Array.isArray(sourceRecords));
 const config=structuredClone(inherited.serverConfig),bindings=new Map(config.bindings.map(record=>[record.url,record]));
 assert.ok(bindings.has('/universal/long_adapter.mjs'),'PRODUCTION_PARENT_BOOTSTRAP_EDGE_REQUIRED');
 assert.deepEqual(browserRecords.map(record=>record.url).sort(),Object.keys(BROWSER_BINDINGS).sort(),'PRODUCTION_EXACT_BROWSER_CLOSURE_REQUIRED');
 for(const record of browserRecords){
  assert.ok(hex(record.sha256)&&path.isAbsolute(record.path)&&Number.isSafeInteger(record.bytes)&&record.bytes>0,'PRODUCTION_VERIFIED_BROWSER_SOURCE_REQUIRED');
  if(record.url!=='/universal/long_adapter.mjs')assert.ok(!bindings.has(record.url),'PRODUCTION_BROWSER_EDGE_COLLISION');
  bindings.set(record.url,{...record});
 }
 const browserSourceSignature=sha(Buffer.from(JSON.stringify(browserRecords.map(record=>({url:record.url,bytes:record.bytes,sha256:record.sha256}))))),
  integrity=Object.freeze({runtimeProfile:'UNIVERSAL_PRODUCTION_V3',sourceManifestSha256:manifestSha256,browserSourceSignature});
 config.runtimeConfig.productionAdapter='UNIVERSAL_PRODUCTION_V3';
 config.runtimeConfig.universalVideo.productionV3=structuredClone(integrity);
 config.bindings=[...bindings.values()];
 const sourceBindings=[...inherited.sourceBindings,...sourceRecords.map(record=>({path:path.relative(engine,record.file).replaceAll(path.sep,'/'),bytes:record.bytes,sha256:record.sha256}))],
  sourceSignature=sha(Buffer.from(JSON.stringify({parent:inherited.sourceSignature,productionV3:integrity,sourceBindings})));
 return {...inherited,serverConfig:config,sourceBindings,sourceSignature,productionIntegrity:integrity,
  productionSourceRecords:sourceRecords,root};
}

export async function loadLongRuntimePlan(options={}){
 const verification=await verifySources(false);
 await validatePythonPlan(options.planFile);
 const inherited=await parent.loadLongRuntimePlan(options);
 validateLongRuntimeDocument(inherited.document,inherited.scene.sceneId);
 const manifestFile=path.join(root,'PRODUCTION_FILES.json'),raw=await boundedSource(manifestFile,64*1024*1024);
 assert.equal(sha(raw),verification.manifestSha256,'PRODUCTION_MANIFEST_CHANGED_AFTER_VERIFICATION');
 const manifest=JSON.parse(raw),records=[{file:manifestFile,bytes:raw.length,sha256:sha(raw)}],byName=new Map();
 for(const [name,expected]of Object.entries({...manifest.files,...manifest.testFiles})){
  assert.ok(typeof name==='string'&&name&&!path.isAbsolute(name)&&name.split('/').every(part=>part&&part!=='.'&&part!=='..')&&!/[\\\0]/.test(name),'PRODUCTION_CANONICAL_MANIFEST_SOURCE_REQUIRED');
  const file=path.join(root,name),bytes=await boundedSource(file,64*1024*1024),record={file,bytes:bytes.length,sha256:sha(bytes)};
  assert.equal(record.sha256,expected,'PRODUCTION_SOURCE_CHANGED_AFTER_VERIFICATION');records.push(record);byName.set(name,record);
 }
 const browserRecords=Object.entries(BROWSER_BINDINGS).map(([url,name])=>{
  const record=byName.get(name);assert.ok(record,'PRODUCTION_BROWSER_SOURCE_NOT_MANIFESTED_'+name);
  return{url,path:record.file,bytes:record.bytes,sha256:record.sha256};
 }),plan=extendProductionServerPlan(inherited,{manifestSha256:sha(raw),browserRecords,sourceRecords:records});
 plan.assertSourceUnchanged=async()=>{
  await inherited.assertSourceUnchanged();
  for(const record of records)assert.equal(sha(await boundedSource(record.file,64*1024*1024)),record.sha256,'PRODUCTION_BOUND_SOURCE_CHANGED');
  return true;
 };
 verifiedPlans.set(plan,sha(Buffer.from(JSON.stringify(plan.serverConfig))));
 return plan;
}

/** Validate actual output evidence before the inherited capture writes it. */
export async function assertProductionCapturedFrame(captured,plan){
 const diagnostic=captured?.diagnostic;
 if(!diagnostic)return captured; // Non-capture page.evaluate, e.g. cleanup.
 const frame=diagnostic.frame,production=diagnostic.productionV3;
 assert.ok(Number.isSafeInteger(frame)&&frame>=plan.scene.startFrame&&frame<plan.scene.endFrame,'PRODUCTION_CAPTURE_GLOBAL_FRAME_REQUIRED');
 assert.equal(production?.runtimeProfile,'UNIVERSAL_PRODUCTION_V3');
 assert.deepEqual(production.integrity,plan.productionIntegrity,'PRODUCTION_CAPTURE_SOURCE_INTEGRITY_REQUIRED');
 assert.equal(production.probeVariant,'AFTER','PRODUCTION_SOFTWARE_AB_VARIANT_FORBIDDEN');
 const chapter=plan.document.productionV3.eventChapters.find(row=>frame>=row.startFrame&&frame<row.endFrame);
 assert.ok(chapter,'PRODUCTION_FRAME_CHAPTER_GAP');assert.deepEqual(production.chapter,chapter,'PRODUCTION_ACTUAL_CHAPTER_BINDING_REQUIRED');
 const {evaluateProductionGeometryClock}=await import('./production_visual_profile.mjs'),
  expected=evaluateProductionGeometryClock(plan.document,frame);
 assert.deepEqual(production.geometryClock,expected,'PRODUCTION_ACTUAL_GEOMETRY_CLOCK_BINDING_REQUIRED');
 assert.equal(production.noInferredEnemyComplement,true);assert.equal(production.noInferredHistoricalUnits,true);
 assert.equal(production.originalProjectionUsed,true);assert.equal(production.originalNativeMarkerStyleAndAnchor,true);
 return captured;
}

export async function openLongRuntime({loadedPlan=null,...options}={}){
 await verifySources(true);
 const plan=loadedPlan??await loadLongRuntimePlan(options),seal=verifiedPlans.get(plan);
 assert.ok(seal,'PRODUCTION_LOADED_PLAN_NOT_VERIFIED');
 assert.equal(sha(Buffer.from(JSON.stringify(plan.serverConfig))),seal,'PRODUCTION_SERVER_CONFIG_CHANGED_BEFORE_HARDWARE');
 const runtime=await parent.openLongRuntime({...options,loadedPlan:plan});
 try{
  assert.deepEqual(runtime.info.universalVideo.productionV3,plan.productionIntegrity,'PRODUCTION_ACTUAL_BOOT_INTEGRITY_REQUIRED');
  assert.equal(runtime.info.productionV3?.runtimeProfile,'UNIVERSAL_PRODUCTION_V3');
  const page=new Proxy(runtime.page,{get(target,key){
   if(key==='evaluate')return async(...args)=>assertProductionCapturedFrame(await target.evaluate(...args),plan);
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});
  return{...runtime,page};
 }catch(error){await runtime.close();throw error;}
}
