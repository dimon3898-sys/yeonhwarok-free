import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {prepareNative} from '../tools/prepare_native.mjs';
import {evaluateMinimumContextCameraFrame} from '../../../web/map_infographic_v1/camera_director_v5.mjs';
const seed='/workspace/exact-65422-capsule-20261020/world-simulation-shorts-engine/recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json';
const config=JSON.parse(await readFile(new URL('../fixtures/NATIVE_DEMO_CONFIG.json',import.meta.url)));
const digest=b=>createHash('sha256').update(b).digest('hex');
let prepared;
test('actual source preparation reuses world GIS/assets without changing original G1 source',async()=>{
 const before=await readFile(seed);prepared=await prepareNative({seedPlanFile:seed,config});
 assert.equal(prepared.nativePlan.primary,'COUNTRY_VNM');assert.equal(JSON.parse(before).primary,'COUNTRY_KOR');
 assert.equal(digest(await readFile(seed)),digest(before));assert.equal(prepared.nativePlan.geometries.length,JSON.parse(before).geometries.length);
 assert.equal(prepared.sourceBindings.length,5);assert.equal(prepared.evidence.protectedG1PlanChanged,false);
});
test('every output camera state is an actual integer Camera V5 evaluation',()=>{
 assert.equal(prepared.cameraSchedule.length,180);
 for(const row of prepared.cameraSchedule){const actual=evaluateMinimumContextCameraFrame(prepared.cameraPlan,row.sourceFrame);
  assert.deepEqual(row.flatBounds,actual.camera.flatBounds);assert.equal(actual.admission.localUsed,false);}
 assert.equal(prepared.cameraSchedule[0].sourceFrame,0);assert.equal(prepared.cameraSchedule.at(-1).sourceFrame,0);
 assert.ok(prepared.cameraSchedule.some(x=>x.clockDirection==='FORWARD'));assert.ok(prepared.cameraSchedule.some(x=>x.clockDirection==='HOLD'));assert.ok(prepared.cameraSchedule.some(x=>x.clockDirection==='REVERSE'));
});
test('camera stays no closer than explicit regional source detail floor',()=>{
 for(const row of prepared.cameraSchedule){assert.ok(row.flatBounds[2]-row.flatBounds[0]>=20-1e-9);assert.ok(row.flatBounds[3]-row.flatBounds[1]>=32-1e-9);}
 assert.equal(prepared.evidence.localAdmissionGranted,false);assert.equal(prepared.evidence.resampledGlobalDerivativeClaimed,false);
});
test('unknown config fields fail rather than disappear',async()=>{
 await assert.rejects(prepareNative({seedPlanFile:seed,config:{...config,secretFallback:true}}),/GENERIC_NATIVE_CONFIG_INVALID/);
});
test('missing actual source geometry cannot become another country fallback',async()=>{
 await assert.rejects(prepareNative({seedPlanFile:seed,config:{...config,primary_id:'NOT_A_SOURCE_ID'}}),/GENERIC_NATIVE_SOURCE_PRIMARY_REQUIRED/);
});
test('unsupported long production request cannot use this free bounded demo preparer',async()=>{
 await assert.rejects(prepareNative({seedPlanFile:seed,config:{...config,total_frames:2400}}),/GENERIC_NATIVE_CONFIG_INVALID/);
});
test('calling a tiny view REGIONAL cannot bypass the explicit source pixel budget',async()=>{
 await assert.rejects(prepareNative({seedPlanFile:seed,config:{...config,final_bounds:[106,17,107,19]}}),/GENERIC_DEMO_NATIVE_PIXEL_BUDGET_EXCEEDED/);
});
