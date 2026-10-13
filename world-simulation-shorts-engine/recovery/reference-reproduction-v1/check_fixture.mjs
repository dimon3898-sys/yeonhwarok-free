/** Actual data invariant check; no render, story simulation, or FINAL modification. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,assessReferenceCameraMotion}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
const root=new URL('./',import.meta.url),engine=new URL('../../',root);
const json=async url=>JSON.parse(await readFile(url,'utf8'));
const scene=await json(new URL('fixtures/SCENE_PLAN.json',root));
const fixture=await json(new URL('fixtures/RUNTIME_FIXTURE.json',root));
const old=await json(new URL('recovery/planner-scene-json-v1/data/NATIVE_PENINSULA.json',engine));
const baseCameraPlan=await json(new URL(fixture.nativeFiles.cameraPlan,engine));
const originalCamera=JSON.stringify(baseCameraPlan),domain=JSON.stringify(scene.controlIntent.domain);
for(const item of scene.controlIntent.domain)assert.deepEqual(item.geometry,old.countries[item.id]);
const plan=compileTerritoryControlPlan(scene.controlIntent);
const camera=compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame:fixture.currentNativeFrame,
 keyframes:scene.cameraKeyframes,totalFrames:fixture.totalFrames,fps:fixture.fps});
const cameraMotion=assessReferenceCameraMotion(camera);
assert.equal(cameraMotion.status,'PASS');
function* coordinates(value){
 if(Array.isArray(value)&&value.length===2&&value.every(Number.isFinite))yield value;
 else if(Array.isArray(value))for(const child of value)yield* coordinates(child);
}
const vertices=scene.controlIntent.domain.flatMap(item=>[...coordinates(item.geometry.coordinates)]);
let checks=0,previous=null;
for(let frame=0;frame<150;frame++){
 const control=evaluateTerritoryControlFrame(plan,frame);
 assert.equal(control.geometryUnchanged,true);
 if(previous)for(let i=0;i<control.boundaryLatitudes.length;i++)
  assert.ok(control.boundaryLatitudes[i]>=previous.boundaryLatitudes[i]);
 for(const point of vertices){
  const state=classifyControlPoint(control,point);
  if(state.inDomain){assert.notEqual(state.winner,state.loser);assert.ok(state.owner);}
  else assert.equal(state.owner,null);
  checks++;
 }
 previous=control;
}
assert.equal(JSON.stringify(scene.controlIntent.domain),domain);
assert.equal(JSON.stringify(baseCameraPlan),originalCamera);
const report={status:'PASS',scope:'PURE_ACTUAL_NEW_FIXTURE_MODEL_VALIDATION',frames:150,
 sourceCountryGeometriesUnchanged:true,vertices:vertices.length,pointFrameChecks:checks,
 complementaryOwnership:true,monotonicBoundary:true,cameraMotion,sourceCameraPlanUnchanged:true,
 sourceFinalEdited:false,sceneSHA256:createHash('sha256').update(await readFile(new URL('fixtures/SCENE_PLAN.json',root))).digest('hex'),
 gpuProbe:'SEPARATE_ACTUAL_NATIVE_STATIC_CHECK'};
await writeFile(new URL('evidence/FIXTURE_MODEL_TEST.json',root),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
