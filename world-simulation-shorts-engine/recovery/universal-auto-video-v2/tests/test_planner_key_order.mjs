/** Regression for the actual Python-canonical Scene input seen by the browser. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {normalizePlannerGeometryKeys} from '../planner_key_order.mjs';
import {validateScenePlan} from '../../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileSceneEngineRequest} from '../../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
const document=JSON.parse(await readFile(new URL('../fixtures/PLAN_80S.json',import.meta.url)));
test('actualPython-sortedgeometryreproducesoldvalidatorfailure beforekeyadapter',()=>{
 assert.throws(()=>compileSceneEngineRequest(document.legacyScenePlan),/PLANNER_SCENE_NON_CANONICAL_GEOMETRY/);
});
test('keyadapterpassesoriginalcompiler withoutchangingcoordinates/source/timing/rawinput',()=>{
 const raw=document.legacyScenePlan,before=JSON.stringify(raw),adapted=normalizePlannerGeometryKeys(raw);
 assert.equal(validateScenePlan(adapted).valid,true);
 // Key-order repair exposes the separate protected Area1200frame cap.
 assert.throws(()=>compileSceneEngineRequest(adapted),/AREA_TOTAL_FRAMES_MUST_BIND_COMPLETE_TIMELINE/);
 assert.equal(JSON.stringify(raw),before,'originalSHA-boundinputmutated');
 assert.deepEqual(adapted.geometries,raw.geometries,'onlyobjectpropertyorder maychange');
 for(let i=0;i<raw.geometries.length;i++){
  assert.equal(adapted.geometries[i].geometry.type,raw.geometries[i].geometry.type);
  assert.equal(JSON.stringify(adapted.geometries[i].geometry.coordinates),JSON.stringify(raw.geometries[i].geometry.coordinates));
  assert.deepEqual(Object.keys(adapted.geometries[i]).slice(0,3),['id','geometry','source_id']);
  assert.deepEqual(Object.keys(adapted.geometries[i].geometry),['type','coordinates']);
 }
 assert.deepEqual(adapted.time_steps,raw.time_steps);assert.deepEqual(adapted.source_notes,raw.source_notes);
});
test('keyadapterdoesnotdropunknownmetadata orrepairinvalidgeometry',()=>{
 const row=structuredClone(document.legacyScenePlan);row.geometries[0].unapproved='field';
 assert.throws(()=>normalizePlannerGeometryKeys(row),/GEOMETRY_KEYS_REQUIRED/);
 const nested=structuredClone(document.legacyScenePlan);nested.geometries[0].geometry.unapproved=true;
 assert.throws(()=>normalizePlannerGeometryKeys(nested),/GEOMETRY_PAYLOAD_KEYS_REQUIRED/);
 const bad=structuredClone(document.legacyScenePlan);bad.geometries[0].geometry.coordinates[0][0][0][0]=999;
 assert.throws(()=>compileSceneEngineRequest(normalizePlannerGeometryKeys(bad)));
});
