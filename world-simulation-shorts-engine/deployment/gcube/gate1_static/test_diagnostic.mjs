import assert from 'node:assert/strict';
import {classify, createDiagnostic, redact, stages} from './diagnostic.mjs';
const cases = [
  ['launch error', 'BROWSER_LAUNCH', 'vulkan', 'CHROMIUM_LAUNCH_FAILED'],
  ['Timeout 30000ms exceeded', 'BROWSER_LAUNCH', 'egl', 'CHROMIUM_LAUNCH_TIMEOUT'],
  ['VK_ERROR_INITIALIZATION_FAILED', 'BROWSER_LAUNCH', 'vulkan', 'VULKAN_INITIALIZATION_FAILED'],
  ['EGL_NOT_INITIALIZED', 'BROWSER_LAUNCH', 'egl', 'EGL_INITIALIZATION_FAILED'],
  ['target closed', 'PAGE_CREATE', 'egl', 'BROWSER_PAGE_CREATE_FAILED'],
  ['net::ERR_CONNECTION_REFUSED', 'PAGE_LOAD', 'vulkan', 'BROWSER_PAGE_LOAD_FAILED'],
  ['execution context destroyed', 'WEBGL2_CREATE', 'egl', 'WEBGL2_EVALUATION_FAILED'],
  ['evaluation error', 'READPIXELS', 'egl', 'READPIXELS_EVALUATION_FAILED'],
  ['WEBGL2_REQUIRED', 'WEBGL2_CREATE', 'egl', 'WEBGL2_REQUIRED'],
  ['SOFTWARE_RENDERER_REJECTED', 'GPU_IDENTITY', 'egl', 'SOFTWARE_RENDERER_REJECTED'],
  ['NVIDIA_RENDERER_REQUIRED', 'GPU_IDENTITY', 'egl', 'NVIDIA_RENDERER_REQUIRED'],
];
let completed = 0;
function test(name, run) { const began = Date.now(); console.log(JSON.stringify({stage:'START', test:name})); run(); console.log(JSON.stringify({stage:'END', test:name, result:'PASS', elapsed:(Date.now()-began)/1000, completed:++completed, total:14})); }
for (const [message, stage, backend, expected] of cases) test(stage + ':' + message, () => assert.equal(classify(Error(message), stage, backend), expected));
test('diagnostic all explicit stages before launch', () => {const {diagnostic,set}=createDiagnostic('egl'); set('BROWSER_LAUNCH','FAIL'); assert.deepEqual(diagnostic.stages.map(x=>x.name), stages); assert.equal(diagnostic.stages.find(x=>x.name==='BROWSER_LAUNCH').result,'FAIL');});
test('secret and credential redaction', () => {const text=redact('privatevalue https://user:secret@proxy token=abc Authorization: Bearer jwt', {API_TOKEN:'privatevalue'}); for(const value of ['privatevalue','secret@','abc','jwt']) assert(!text.includes(value));});
test('diagnostic capture bounded', () => assert.equal(redact('x'.repeat(100000)).length,65536));
