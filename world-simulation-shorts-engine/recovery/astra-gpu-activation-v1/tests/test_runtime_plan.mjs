/** CPU-only closure/binding plan tests. No browser, upload or rendering occurs. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm,symlink} from 'node:fs/promises';
import path from 'node:path';
import {loadAstraRuntimePlan,engine,sha} from '../astra_runtime.mjs';

async function fixture(){
 const dir=await mkdtemp('/workspace/astra-plan-test-'),bytes=Buffer.from([1,2,3,4]),
  scene='recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json',
  bundle={schema:'ASTRA_GPU_UPLOAD_BUNDLE_V1',enabled:true,rendererPayloadSHA256:'1'.repeat(64),
   artifacts:[{file:'values.bin',bytes:bytes.length,sha256:sha(bytes)}]};
 await writeFile(path.join(dir,'values.bin'),bytes);
 const bundleBytes=Buffer.from(JSON.stringify(bundle));await writeFile(path.join(dir,'manifest.json'),bundleBytes);
 const profile={schema:'ASTRA_GPU_ACTIVATION_PROFILE_V1',profileId:'CPU_PLAN_TEST_ONLY',
  fixtureFile:'recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json',scenePlanFile:scene,
  visualAdmissionFile:'recovery/moving-frontier-glow-fix-v1/evidence/VISUAL_ADMISSION.json',
  scenePlanByteSha256:sha(await readFile(path.join(engine,scene))),rendererPayloadSha256:bundle.rendererPayloadSHA256,
  bundleManifestFile:path.join(dir,'manifest.json'),bundleManifestSha256:sha(bundleBytes),materialProfile:{}};
 const activationFile=path.join(dir,'activation.json');
 const save=async()=>{const raw=Buffer.from(JSON.stringify(profile));await writeFile(activationFile,raw);
  return {activationFile,expectedActivationSha256:sha(raw)};};
 return {dir,profile,bundle,save,cleanup:()=>rm(dir,{recursive:true,force:true})};
}

test('CPU plan selects exact original module closure, material decorator, sources and baseline fallback',async()=>{
 const f=await fixture();try{
  const plan=await loadAstraRuntimePlan(await f.save()),map=new Map(plan.serverConfig.bindings.map(r=>[r.url,r]));
  assert.ok(map.has('/modules/map_engine_unit_gpu_adapter_v4.mjs'));
  assert.ok(map.has('/modules/reference_terrain_material_v4.mjs'));
  assert.ok(map.has('/astra/astra_material.mjs'));assert.ok(map.has('/astra-upload/gpu_upload.mjs'));
  assert.ok(map.has('/astra-data/UPLOAD_MANIFEST.json'));assert.ok(map.has('/astra-data/values.bin'));
  assert.equal(plan.serverConfig.runtimeConfig.testOnlySoftwareProbe,false);
  assert.equal(plan.serverConfig.runtimeConfig.astra.scope,'SOURCE_SUPPORT_ONLY_WITH_UNCHANGED_BASELINE_FALLBACK');
  assert.equal(plan.fixture.totalFrames,150);assert.equal(plan.scenePlan.controlIntent.fps,30);
  assert.equal(await plan.assertSourceUnchanged(),true);
 }finally{await f.cleanup();}
});
test('activation bytes must match caller SHA',async()=>{
 const f=await fixture();try{const opts=await f.save();opts.expectedActivationSha256='0'.repeat(64);
  await assert.rejects(loadAstraRuntimePlan(opts),/ACTIVATION_HASH_MISMATCH/);
 }finally{await f.cleanup();}
});
test('saved scene byte hash prevents altered camera/timing inputs',async()=>{
 const f=await fixture();try{f.profile.scenePlanByteSha256='0'.repeat(64);
  await assert.rejects(loadAstraRuntimePlan(await f.save()),/SAVED_SCENE_BYTE_HASH_MISMATCH/);
 }finally{await f.cleanup();}
});
test('bundle payload must bind the prepared saved scene profile',async()=>{
 const f=await fixture();try{f.profile.rendererPayloadSha256='0'.repeat(64);
  await assert.rejects(loadAstraRuntimePlan(await f.save()),/RENDERER_PAYLOAD_HASH_MISMATCH/);
 }finally{await f.cleanup();}
});
test('artifact values are SHA checked without numerical conversion',async()=>{
 const f=await fixture();try{await writeFile(path.join(f.dir,'values.bin'),Buffer.from([9,9,9,9]));
  await assert.rejects(loadAstraRuntimePlan(await f.save()),/BOUND_SOURCE_SHA_MISMATCH/);
 }finally{await f.cleanup();}
});
test('artifact source symlink fails before source transmission',async()=>{
 const f=await fixture();try{await rm(path.join(f.dir,'values.bin'));await symlink('/etc/hosts',path.join(f.dir,'values.bin'));
  await assert.rejects(loadAstraRuntimePlan(await f.save()),/SOURCE_SYMLINK_FORBIDDEN/);
 }finally{await f.cleanup();}
});
test('source change after planning is rejected by retained binding',async()=>{
 const f=await fixture();try{const plan=await loadAstraRuntimePlan(await f.save());
  await writeFile(path.join(f.dir,'values.bin'),Buffer.from([5,5,5,5]));
  await assert.rejects(plan.assertSourceUnchanged(),/BOUND_SOURCE_CHANGED/);
 }finally{await f.cleanup();}
});
