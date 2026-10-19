import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {assertSoftwareRuntimeInfo,assertActualSoftwareFrame} from '../free_preview_runner.mjs';
import {assertHardwareBackend} from '../../rtx-gpu-package-v1/hardware_runtime.mjs';
const software={backend:'ANGLE SwiftShader Device',testOnly:true,productionEligible:false,gpuRenderingVerified:false};
test('free preview is explicitly software test only, never a production admission',()=>{
 assert.equal(assertSoftwareRuntimeInfo(software),true);
 for(const update of [{testOnly:false},{productionEligible:true},{gpuRenderingVerified:true},{backend:'NVIDIA GeForce RTX 5090'}])
  assert.throws(()=>assertSoftwareRuntimeInfo({...software,...update}));
});
test('preserved production hardware gate still refuses software backend',()=>{
 const admission={probe:{gpu_rendering_verified:true,render_mode:'gpu-required',webgl:{draw_passed:true,unmasked_renderer:software.backend}}};
 assert.throws(()=>assertHardwareBackend(software.backend,admission),/HARDWARE_NVIDIA_REQUIRED/);
});
test('free frame must be the requested global frame with real ASTRA selection',async()=>{
 await assert.rejects(()=>assertActualSoftwareFrame({diagnostic:{frame:0}},1400,{}),/SOFTWARE_GLOBAL_FRAME_REQUIRED/);
 await assert.rejects(()=>assertActualSoftwareFrame({diagnostic:{frame:1400,terrain:{astra:{actualMaterialFactorySelected:false}}}},1400,{}),
  /SOFTWARE_ACTUAL_ASTRA_FACTORY_REQUIRED/);
});
test('free harness invokes only preserved explicit software bootstrap; no production opener',async()=>{
 const source=await readFile(new URL('../free_preview_runner.mjs',import.meta.url),'utf8');
 assert.match(source,/runtimeConfig\.testOnlySoftwareProbe=true/);
 assert.match(source,/use-angle=swiftshader/);
 assert.match(source,/softwareProbe:true/);
 assert.match(source,/capturePreviewWithRuntime/);
 assert.doesNotMatch(source,/(?:native|fronts|production)\.openLongRuntime\s*\(/);
 assert.match(source,/actualMP4Decoded:true/);
});
