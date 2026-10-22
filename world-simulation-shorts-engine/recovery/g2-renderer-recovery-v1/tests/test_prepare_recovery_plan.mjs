import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {prepareRecoveryNative} from '../tools/prepare_recovery_plan.mjs';
const HERE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
// The preceding Python source tests restore the SHA-pinned public ZIP. Do not
// launch a hidden child command or copy an old rendered frame for this test.
const pin=JSON.parse(await readFile(path.join(HERE,'../universal-source-pipeline-v2/fixtures/SOURCE_CATALOG_PIN.json')));
const sourceRoot='/tmp/world-engine-source-'+pin.indexSHA256.slice(0,16);
const native=JSON.parse(await readFile(path.join(sourceRoot,'demo/NATIVE.json'))),receipt=JSON.parse(await readFile(path.join(HERE,'fixtures/RECOVERY_STYLE_RECEIPT.json')));

test('real native source replacement preserves camera, geometry, layout and original object',async()=>{
 const before=JSON.stringify(native),result=await prepareRecoveryNative({native,receipt});
 assert.equal(JSON.stringify(native),before);
 for(const k of ['cameraPlan','cameraSchedule'])assert.deepEqual(result[k],native[k]);
 for(const k of ['anchor','framing','geometries','layout','primary','secondary','text','theme'])assert.deepEqual(result.nativePlan[k],native.nativePlan[k]);
 assert.equal(result.nativePlan.assets.terrain.sha256,receipt.terrainAsset.sha256);
 assert.deepEqual(result.nativePlan.assets.terrain.bounds,receipt.terrainAsset.bounds);
 assert.equal(result.nativePlan.assets.terrain.classification,'BAKED HILLSHADE');
 assert.equal(result.nativePlan.scale.lod.rasterCoverage,'FULL_REGIONAL_CROP');
 assert.deepEqual(result.nativePlan.scale.lod.projectedPixelsPerNativeRgbTexel,[.9,1]);
 assert.notEqual(result.nativePlan.scale.lod.terrain.sha256,native.nativePlan.scale.lod.terrain.sha256);
 for(const b of native.sourceBindings.filter(x=>x.role!=='terrain'))assert.deepEqual(result.sourceBindings.find(x=>x.role===b.role),b);
});
test('forged native window and georeference metadata are rejected before source selection',async()=>{
 const bad=structuredClone(receipt);bad.terrainAsset.bounds[0]-=1;
 await assert.rejects(prepareRecoveryNative({native,receipt:bad}),/NATIVE_WINDOW_GEOGRAPHIC_BINDING/);
});
test('source corruption or fake dimensions cannot become an admitted source',async()=>{
 const bad=structuredClone(receipt);bad.terrainAsset.sha256='0'.repeat(64);
 await assert.rejects(prepareRecoveryNative({native,receipt:bad}),/SOURCE_PNG_HASH_OR_DIMENSION/);
});
test('camera outside source support and extra magnification cannot silently fall back',async()=>{
 const bad=structuredClone(native);bad.cameraSchedule[0].flatBounds[0]-=10;
 await assert.rejects(prepareRecoveryNative({native:bad,receipt}),/COMPLETE_SOURCE_VIEWPORT/);
 const zoom=structuredClone(native);zoom.cameraSchedule[0].flatBounds=[100,4,110,20];
 await assert.rejects(prepareRecoveryNative({native:zoom,receipt}),/NATIVE_PIXEL_BUDGET/);
});
