/** Pure import/source/frame-contract tests, no Chromium, GL or encoding. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {verifiedIntegrationSources,assertIntegratedCapturedFrame,root} from '../capture_runtime.mjs';
import {resolveCapture} from '../long_capture.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
test('complete current source closure is read without opening any hardware',async()=>{
 const raw=await readFile(root+'/INTEGRATION_FILES.json');const proof=await verifiedIntegrationSources({schema:'WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1',sourceManifestSHA256:sha(raw)});
 assert.ok(proof.records.length>=16);assert.ok(proof.records.some(r=>r.name==='capture_runtime.mjs'));
});
test('wrong manifest identity rejects before loading parent runtime',async()=>{
 await assert.rejects(verifiedIntegrationSources({schema:'WORLD_ENGINE_INTEGRATED_CAPTURE_REQUEST_V1',sourceManifestSHA256:'0'.repeat(64)}),/INTEGRATION_CAPTURE_MANIFEST_CHANGED/);
});
test('fixed capture import is scoped; unrelated paths cannot override runtime',()=>{
 const fallback=()=>({url:'unchanged'}),context={parentURL:new URL('../../universal-auto-video-v2/long_capture.mjs?universal-integration-v1-fixed-entry',import.meta.url).href};
 assert.match(resolveCapture('./long_runtime.mjs',context,fallback).url,/universal-integration-v1\/capture_runtime.mjs$/);
 assert.equal(resolveCapture('./long_runtime.mjs',{parentURL:'file:///unrelated.mjs'},fallback).url,'unchanged');
 assert.equal(resolveCapture('./unrecognized.mjs',context,fallback).url,'unchanged');
});
test('actual frame style proof cannot silently report parent defaults',()=>{
 const visualProfile={territoryOpacity:.74,frontCoreWidthPixels:6.4,frontGlowRadiusPixels:14,frontGlowGain:.58};
 const plan={integrationV1:{visualProfile}},frame={diagnostic:{area:{graphics:{productionVisual:{...visualProfile}}}}};
 assert.equal(assertIntegratedCapturedFrame(frame,plan),frame);
 frame.diagnostic.area.graphics.productionVisual.frontGlowGain=.42;
 assert.throws(()=>assertIntegratedCapturedFrame(frame,plan),/INTEGRATION_ACTUAL_DRAW_SETTING_MISMATCH/);
});

test('event draw proof is mandatory while initial arrival may have no overlay',()=>{
 const plan={integrationV1:{visualProfile:{}}};
 assert.throws(()=>assertIntegratedCapturedFrame({diagnostic:{productionV3:{geometryClock:{eventEnabled:true}}}},plan),/INTEGRATION_ACTUAL_DRAW_SETTING_EVIDENCE_REQUIRED/);
 assert.throws(()=>assertIntegratedCapturedFrame({diagnostic:{frontV4:{selection:{sourceActiveFrame:true}}}},plan),/INTEGRATION_ACTUAL_DRAW_SETTING_EVIDENCE_REQUIRED/);
 assert.doesNotThrow(()=>assertIntegratedCapturedFrame({diagnostic:{productionV3:{geometryClock:{eventEnabled:false}}}},plan));
});
