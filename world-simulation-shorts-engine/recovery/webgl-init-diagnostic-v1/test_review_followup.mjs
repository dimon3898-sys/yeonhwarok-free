import test from 'node:test';
import assert from 'node:assert/strict';
import {safeFailureCode,contextIdentity} from './diagnose_webgl_once.mjs';
test('unknown uppercase exception text cannot become a public error code',()=>{
 assert.equal(safeFailureCode('PRIVATE_TOKEN_VALUE'),'DIAG_OPERATION_FAILED');
 assert.equal(safeFailureCode('DIAG_CONTEXT_EVALUATION_TIMEOUT'),'DIAG_CONTEXT_EVALUATION_TIMEOUT');
 assert.equal(safeFailureCode('HANDOFF_NONROOT_SANDBOX_REQUIRED'),'HANDOFF_NONROOT_SANDBOX_REQUIRED');
 assert.equal(safeFailureCode('DIAG_VALUE=/private'),'DIAG_OPERATION_FAILED');
});
test('software renderer string cannot become NVIDIA Vulkan identity PASS',()=>{
 assert.equal(contextIdentity('NVIDIA Vulkan SwiftShader',true).nvidiaVerified,false);
 assert.equal(contextIdentity('NVIDIA Vulkan llvmpipe',true).vulkanVerified,false);
 assert.equal(contextIdentity('ANGLE NVIDIA Vulkan',false).nvidiaVerified,false);
 assert.equal(contextIdentity('ANGLE NVIDIA Vulkan',true).nvidiaVerified,true);
 assert.equal(contextIdentity('ANGLE NVIDIA Vulkan',true).identityEvidence,'WEBGL_RENDERER_STRINGS_ONLY_NOT_NATIVE_DRAW_PROOF');
});
