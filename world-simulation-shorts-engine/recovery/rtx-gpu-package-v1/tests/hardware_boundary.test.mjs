import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,chmod,rm,symlink,readFile} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {assertHardwareBackend,readAdmission,root} from '../hardware_runtime.mjs';
import {originalEncodingArgs} from '../hardware_render.mjs';
// Synthetic unit data checks rejection paths only; this is never hardware evidence.
const backend='ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 SUPER, OpenGL)';
const make=()=>({status:'GPU_VERIFIED',testOnly:false,gpuRenderingVerified:true,observedAt:new Date().toISOString(),
 probe:{gpu_rendering_verified:true,render_mode:'gpu-required',gpu_profile:'egl',profile_fingerprint:'a'.repeat(64),
  webgl:{draw_passed:true,unmasked_renderer:backend}}});
test('backend rejects software despite forged positive fields',()=>{
 for(const value of ['Google SwiftShader','NVIDIA llvmpipe','ANGLE NVIDIA lavapipe','ANGLE Intel UHD','NVIDIA software'])
  assert.throws(()=>assertHardwareBackend(value,make()));
});
test('draw and physical backend identity must agree',()=>{
 const data=make();assert.equal(assertHardwareBackend(backend,data),true);
 data.probe.webgl.draw_passed=false;assert.throws(()=>assertHardwareBackend(backend,data));
 data.probe.webgl.draw_passed=true;assert.throws(()=>assertHardwareBackend(backend.replace('4080 SUPER','4090'),data));
});
test('private fresh admission rejects test-only, stale, broad permissions and symlinks',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'rtx-boundary-')),file=path.join(dir,'admission.json'),old={...process.env};
 process.env.WORLD_ENGINE_RENDER_MODE='gpu-required';process.env.WORLD_ENGINE_GPU_PROFILE='egl';process.env.RTX_GPU_PROBE_FINGERPRINT='a'.repeat(64);
 try{
  const data=make();await writeFile(file,JSON.stringify(data),{mode:0o600});assert.equal((await readAdmission(file)).status,'GPU_VERIFIED');
  data.testOnly=true;await writeFile(file,JSON.stringify(data));await assert.rejects(readAdmission(file));
  data.testOnly=false;data.observedAt='2000-01-01T00:00:00Z';await writeFile(file,JSON.stringify(data));await assert.rejects(readAdmission(file));
  await writeFile(file,JSON.stringify(make()));await chmod(file,0o644);await assert.rejects(readAdmission(file));
  await chmod(file,0o600);const link=path.join(dir,'link');await symlink(file,link);await assert.rejects(readAdmission(link));
  process.env.WORLD_ENGINE_RENDER_MODE='cpu';await assert.rejects(readAdmission(file));
 }finally{for(const key of ['WORLD_ENGINE_RENDER_MODE','WORLD_ENGINE_GPU_PROFILE','RTX_GPU_PROBE_FINGERPRINT']){
  if(old[key]===undefined)delete process.env[key];else process.env[key]=old[key];}await rm(dir,{recursive:true});}
});
test('approved encoder options are reused with new paths only',async()=>{
 const original=await readFile(path.join(root,'render_proof.mjs'),'utf8');
 const match=original.match(/const encodeArgs=(\[\s*'-hide_banner'[\s\S]+?partial\]);/);assert.ok(match);
 const evaluate=new Function('path','framesDir','partial','return '+match[1]);
 assert.deepEqual(originalEncodingArgs('/persistent/frames','/persistent/new.mp4'),evaluate(path,'/persistent/frames','/persistent/new.mp4'));
});
