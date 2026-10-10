import assert from 'node:assert/strict';
import {admission} from './capability.mjs';
const valid = {webgl2: true, debugRendererAvailable: true, renderer: 'ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 SUPER, Vulkan)',
  actualPixelDraw: true, maxTextureSize: 32768, maxRenderbufferSize: 32768, maxTextureUnits: 32, maxSamples: 8};
const tests = [
  ['RTX4080S_ACCEPTED', () => assert.equal(admission(valid).result, 'PASS')],
  ['SWIFTSHADER_REJECTED', () => assert(admission({...valid, renderer: 'ANGLE Google SwiftShader'}).failures.includes('SOFTWARE_RENDERER_REJECTED'))],
  ['LLVMPipe_REJECTED', () => assert(admission({...valid, renderer: 'llvmpipe'}).failures.includes('SOFTWARE_RENDERER_REJECTED'))],
  ['WRONG_GPU_REJECTED', () => assert(admission({...valid, renderer: 'NVIDIA RTX 3070'}).failures.includes('RTX4080S_REQUIRED'))],
  ['MISSING_WEBGL2', () => assert(admission({...valid, webgl2: false}).failures.includes('WEBGL2_REQUIRED'))],
  ['MISSING_IDENTITY', () => assert(admission({...valid, debugRendererAvailable: false}).failures.includes('GPU_IDENTITY_UNAVAILABLE'))],
  ['FAILED_DRAW_REJECTED', () => assert(admission({...valid, actualPixelDraw: false}).failures.includes('ACTUAL_PIXEL_DRAW_FAILED'))],
  ['TEXTURE_LIMIT_REJECTED', () => assert(admission({...valid, maxTextureSize: 4096}).failures.includes('MAX_TEXTURE_SIZE_INSUFFICIENT'))],
  ['BUFFER_LIMIT_REJECTED', () => assert(admission({...valid, maxRenderbufferSize: 1024}).failures.includes('MAX_RENDERBUFFER_SIZE_INSUFFICIENT'))],
  ['TEXTURE_UNITS_REJECTED', () => assert(admission({...valid, maxTextureUnits: 4}).failures.includes('TEXTURE_UNITS_INSUFFICIENT'))],
  ['COVERAGE_MSAA_REJECTED', () => assert(admission({...valid, maxSamples: 2}).failures.includes('MSAA_COVERAGE_CAPABILITY_INSUFFICIENT'))],
  ['SOFTWARE_TEST_MARKED', () => assert.equal(admission({...valid, renderer: 'Google SwiftShader'}, {softwareTest: true}).result, 'SOFTWARE_TEST_ONLY')],
];
for (let i = 0; i < tests.length; i++) {
  const start = performance.now();
  console.log(JSON.stringify({test: tests[i][0], stage: 'START', completed: i, total: tests.length}));
  tests[i][1]();
  console.log(JSON.stringify({test: tests[i][0], result: 'PASS', elapsed_ms: performance.now() - start, completed: i + 1, total: tests.length}));
}
