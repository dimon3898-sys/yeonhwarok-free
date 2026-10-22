import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {cameraBoundsNumericallyAgree,float64UlpDistance,CAMERA_NUMERIC_CONTRACT} from '../camera_numeric_contract.mjs';

const shifted=(value,ulps)=>{const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,value,false);view.setBigUint64(0,view.getBigUint64(0,false)+BigInt(ulps),false);return view.getFloat64(0,false);};
test('exact canonical V5 bounds agree and signed zero is equivalent',()=>{
 assert.equal(cameraBoundsNumericallyAgree([93,-3,123,43],[93,-3,123,43]).matches,true);
 assert.equal(float64UlpDistance(0,-0),0n);
});
test('256 ULP cap is bounded; 257 ULP is rejected',()=>{
 const bounds=[93,-3,123,43],accepted=[shifted(93,256),-3,123,43],rejected=[shifted(93,257),-3,123,43];
 assert.equal(cameraBoundsNumericallyAgree(accepted,bounds).matches,true);
 assert.equal(cameraBoundsNumericallyAgree(rejected,bounds).reason,'ULP_BOUND_EXCEEDED');
});
test('pixel bound is independently enforced even when one ULP is too large for a tiny span',()=>{
 const bounds=[100,3,100+1e-12,35],changed=[shifted(100,1),3,100+1e-12,35],result=cameraBoundsNumericallyAgree(changed,bounds);
 assert.equal(result.maxUlps,'1');assert.equal(result.matches,false);assert.equal(result.reason,'CANONICAL_PIXEL_BOUND_EXCEEDED');
});
test('one-pixel or semantic camera changes are never treated as arithmetic variation',()=>{
 assert.equal(cameraBoundsNumericallyAgree([93+30/1080,-3,123,43],[93,-3,123,43]).matches,false);
 assert.equal(cameraBoundsNumericallyAgree([93+1e-7,-3,123,43],[93,-3,123,43]).matches,false);
});
test('nonfinite, nonnumeric, degenerate and outside-world camera states are rejected',()=>{
 for(const value of [[NaN,-3,123,43],[Infinity,-3,123,43],['93',-3,123,43],[123,-3,93,43],[93,-3,123],[-181,-3,123,43],[93,-91,123,43]])
  assert.equal(cameraBoundsNumericallyAgree(value,[93,-3,123,43]).matches,false);
});
test('real Chromium probe quantifies old exact failure and new arithmetic-only agreement',async()=>{
 const proof=JSON.parse(await fs.readFile(new URL('../reports/NODE_CHROMIUM_CAMERA_NUMERICS.json',import.meta.url),'utf8'));
 assert.equal(proof.nodeMatchesExpected,true);assert.equal(proof.browserExactMatch,false);assert.equal(proof.differingCoordinates,34);
 assert.equal(proof.admissionsMatch,true);assert.equal(proof.anyBrowserLocalUsed,false);assert.equal(proof.nativeMapRendererCreated,false);assert.equal(proof.webglDraws,0);
 assert.equal(proof.frames,180);assert.equal(proof.maxUlps,'128');assert.ok(proof.maxCanonicalPixelDelta<1e-12);
 assert.equal(proof.boundedNumericsAllAccepted,true);assert.equal(proof.firstBoundedNumericRejection,-1);
 for(const row of proof.differences){
  const bounds=row.axis%2===0?[90,-3,125,43]:[93,-5,123,45],actual=[...bounds],expected=[...bounds];
  actual[row.axis]=row.browser;expected[row.axis]=row.expected;
  assert.equal(cameraBoundsNumericallyAgree(actual,expected).matches,true);
 }
 assert.equal(CAMERA_NUMERIC_CONTRACT.renderState,'ALWAYS_REEVALUATED_BY_BROWSER_CAMERA_V5');
 assert.equal(CAMERA_NUMERIC_CONTRACT.localAdmissionChanged,false);
});
