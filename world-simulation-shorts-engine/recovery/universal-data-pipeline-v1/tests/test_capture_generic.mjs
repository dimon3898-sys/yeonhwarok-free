import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {analyzePrompt} from '../prompt_pipeline.mjs';
import {buildRuntimePayload,SOURCE_REGIONS} from '../capture_generic.mjs';
import {evaluateMinimumContextCameraFrame} from '../../../web/map_infographic_v1/camera_director_v5.mjs';

const base=new URL('../',import.meta.url);
const clone=x=>structuredClone(x);
async function request(name){const input=await fs.readFile(new URL('examples/'+name+'.json',base),'utf8'),result=analyzePrompt(input);assert.equal(result.status,'PASS');return result.renderRequests[0];}

for(const name of ['FICTIONAL_NAMIBIA','AVIATION_GERMANY','TRADE_CHILE']){
 test(name+' preserves actual supplied Scene and binds actual source bytes',async()=>{
  const r=await request(name),before=JSON.stringify(r.scene),payload=await buildRuntimePayload({scene:r.scene,sourceRegionId:r.renderSettings.sourceRegionId,inputTrace:r.inputTrace});
  assert.equal(JSON.stringify(r.scene),before);assert.deepEqual(payload.scene,r.scene);
  assert.deepEqual(payload.cameraPlan.intent.anchor,r.scene.camera_intent.anchor);
  assert.deepEqual(payload.cameraPlan.intent.eventGeometry,r.scene.geometries.filter(g=>r.scene.camera_intent.target_geometry_refs.includes(g.id)).map(g=>g.geometry));
  assert.equal(payload.serverBindings.assets.length,4);assert.ok(payload.serverBindings.assets.every(a=>/^[a-f0-9]{64}$/.test(a.sha256)&&a.bytes>0));
  assert.ok(payload.serverBindings.minimumSourceGutterPixels>=1);assert.equal(payload.serverBindings.syntheticSeedFieldsUsed,false);
  assert.equal(payload.serverBindings.inputGeometryBinding,JSON.stringify(r.scene.geometries));
  const camera=evaluateMinimumContextCameraFrame(payload.cameraPlan,payload.cameraPlan.totalFrames-1);assert.equal(camera.cameraLocked,true);assert.equal(camera.settle.locked,true);assert.equal(camera.admission.localUsed,false);
 });
}
test('server style catalog uses registered IDs without topic-name dispatch',()=>{
 assert.deepEqual([...SOURCE_REGIONS],['namibia_desert_coast','europe_germany','south_america_chile','korean_peninsula','nepal_himalaya']);
});
test('unknown source region is explicitly unsupported',async()=>{
 const r=await request('AVIATION_GERMANY');await assert.rejects(buildRuntimePayload({scene:r.scene,sourceRegionId:'../../private'}),/UDP_SOURCE_REGION_UNSUPPORTED/);
});
test('out-of-source geographic anchor is not replaced by default seed anchor',async()=>{
 const r=await request('AVIATION_GERMANY'),scene=clone(r.scene);scene.camera_intent.anchor=[-140,-40];
 await assert.rejects(buildRuntimePayload({scene,sourceRegionId:r.renderSettings.sourceRegionId}));
});
test('invalid supplied route coordinates are not replaced by stored G2 DEMO geometry',async()=>{
 const r=await request('AVIATION_GERMANY'),scene=clone(r.scene),route=scene.routes[0];scene.geometries.find(g=>g.id===route.geometry_ref).geometry.coordinates[0]=[200,20];
 await assert.rejects(buildRuntimePayload({scene,sourceRegionId:r.renderSettings.sourceRegionId}));
});
test('software proof rejects long whole-film capture',async()=>{
 const r=await request('AVIATION_GERMANY'),scene=clone(r.scene);scene.timing.total_frames=2400;scene.timing.duration_seconds=80;
 await assert.rejects(buildRuntimePayload({scene,sourceRegionId:r.renderSettings.sourceRegionId}));
});
test('actual supplied route survives in engine binding',async()=>{
 const r=await request('AVIATION_GERMANY'),scene=clone(r.scene),route=scene.routes[0],geometry=scene.geometries.find(g=>g.id===route.geometry_ref);
 geometry.geometry.coordinates[1][0]+=.2;
 const changed=await buildRuntimePayload({scene,sourceRegionId:r.renderSettings.sourceRegionId});
 assert.equal(changed.serverBindings.inputGeometryBinding,JSON.stringify(scene.geometries));assert.notEqual(changed.serverBindings.inputGeometryBinding,JSON.stringify(r.scene.geometries));
 assert.deepEqual(changed.scene.geometries.find(g=>g.id===route.geometry_ref).geometry,geometry.geometry);
});
test('renderer source is composition, not an imported completed DEMO',async()=>{
 const source=await fs.readFile(new URL('generic_runtime.mjs',base),'utf8');
 for(const owner of ['createMapInfographicRenderer','evaluateAreaFrame','compileFlowRoute','evaluateFlowFrame','createFlowGraphicPass','auditRuntimeLayout'])assert.ok(source.includes(owner));
 for(const forbidden of ['createUniversalSourceRuntime','DEMO_SOURCE_SCENE','demo/frames/','drawImage(','fetch(\'https:'])assert.ok(!source.includes(forbidden));
 assert.ok(source.includes('UDP_FREE_SOFTWARE_BACKEND_REQUIRED'));assert.ok(source.includes('primaryMaterial:0'));
});
