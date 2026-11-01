import test from 'node:test';
import assert from 'node:assert/strict';
import {safeIdentifier,safeTextEvidence,scrubSystemInfo,bounded,runOnce,CAPTURE_INPUT} from './diagnose_webgl_once.mjs';

test('new diagnostic exports no raw credentials, paths or stderr text',()=>{
 const secret='OWNER_CODE=private-value /private/path https://private.example/?token=secret VK_ERROR_INCOMPATIBLE_DRIVER';
 const result=safeTextEvidence(secret);
 assert.deepEqual(result.categories,['VK_ERROR_INCOMPATIBLE_DRIVER']);
 assert.equal(result.rawOmitted,true);assert.match(result.sha256,/^[a-f0-9]{64}$/);
 assert.ok(!JSON.stringify(result).includes('private'));assert.equal(safeIdentifier(secret),null);
});
test('GPU information is closed to the safe device/feature subset',()=>{
 const result=scrubSystemInfo({gpu:{devices:[{vendorId:4318,deviceId:9987,vendorString:'NVIDIA',deviceString:'RTX 4080 SUPER',deviceUUID:'secret'}],auxAttributes:{glRenderer:'ANGLE (NVIDIA, Vulkan)',privatePath:'/private'},featureStatus:{webgl2:'enabled',private:'secret'}},commandLine:'secret'});
 assert.equal(result.devices[0].vendorId,4318);assert.equal(result.aux.glRenderer,'ANGLE (NVIDIA, Vulkan)');
 assert.ok(!JSON.stringify(result).includes('secret'));assert.deepEqual(result.featureStatus,{webgl2:'enabled'});
});
test('new operation timeout rejects without retry',async()=>{
 let calls=0;const pending=(()=>{calls++;return new Promise(()=>{});})();
 await assert.rejects(bounded(pending,5,'DIAG_TEST_TIMEOUT'),/DIAG_TEST_TIMEOUT/);assert.equal(calls,1);
});
test('approval gate rejects before filesystem, profile or browser access',async()=>{
 await assert.rejects(runOnce({approved:false}),/DIAG_SEPARATE_GPU_APPROVAL_REQUIRED/);
});
test('diagnostic input carries the exact existing capture launch inputs',()=>{
 assert.deepEqual(CAPTURE_INPUT,{executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
});
