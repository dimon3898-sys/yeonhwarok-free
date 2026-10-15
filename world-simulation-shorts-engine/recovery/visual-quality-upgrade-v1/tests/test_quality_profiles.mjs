/** CPU-only scene/camera contracts. Numerical camera audits do not approve video quality. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {qualityProfile,selectQualityCamera} from '../quality_profiles.mjs';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 json=p=>JSON.parse(readFileSync(path.join(engine,p))),scene=json('recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),
 fixture=json('recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'),
 inputs={scenePlan:scene,baseCameraPlan:json(fixture.nativeFiles.cameraPlan),currentNativeFrame:fixture.currentNativeFrame,
  safeArea:json(fixture.nativeFiles.regionalPlan).layout.safe,
  inheritedNativeBounds:json(fixture.inheritedAdmissionFiles.scenePlan).cameraKeyframes.at(-1).bounds};
let result;
const selected=()=>result??=selectQualityCamera(inputs);

test('A..F are orthogonal explicit visual comparisons; existing frontier is preserved',()=>{
 const p=Object.fromEntries('ABCDEF'.split('').map(k=>[k,qualityProfile(k)]));
 assert.equal(p.A.boundary,false);assert.equal(p.A.territory,false);assert.equal(p.A.camera,false);
 assert.equal(p.B.boundary,true);assert.equal(p.B.territory,false);assert.equal(p.B.camera,false);
 assert.equal(p.C.boundary,false);assert.equal(p.C.territory,true);assert.equal(p.C.camera,false);
 assert.equal(p.D.frontierAudit,true);assert.equal(p.D.frontierChanged,false);assert.equal(p.D.camera,false);
 assert.equal(p.E.camera,true);assert.equal(p.E.boundary,false);assert.equal(p.E.territory,false);
 assert.equal(p.F.camera,true);assert.equal(p.F.boundary,true);assert.equal(p.F.territory,true);
 for(const profile of Object.values(p))assert.equal(profile.frontierChanged,false);
 assert.throws(()=>qualityProfile('force'),/EXPLICIT_PROFILE/);
});
test('scene-owned camera extension leaves original control/geometry/time/unit design and all other fields exact',()=>{
 const before=JSON.stringify(scene),camera=selected();assert.equal(JSON.stringify(scene),before);
 const {cameraKeyframes:oldKeys,...oldRest}=scene,{cameraKeyframes:newKeys,...newRest}=camera.scenePlan;
 assert.deepEqual(newRest,oldRest);assert.deepEqual(newKeys[0],oldKeys[0]);
 assert.deepEqual(newKeys.map(k=>[k.frame,k.rotationDegrees]),oldKeys.map(k=>[k.frame,k.rotationDegrees]));
 assert.equal(camera.eventTimingChanged,false);assert.equal(camera.cameraV5SourceChanged,false);
 assert.equal(camera.actualGpuVisualQualityVerified,false);
});
test('minimal admitted candidate preserves every frame native floor, source envelope and original unit safe layout',()=>{
 const camera=selected();assert.equal(camera.changed,true);
 const index=camera.candidates.findIndex(c=>c.admitted),chosen=camera.candidates[index];
 assert.equal(index,0);assert.equal(chosen.zoom,camera.selected.zoom);assert.equal(chosen.centering,camera.selected.centering);
 assert.equal(chosen.nativeFloorRespected,true);assert.equal(chosen.originalNativeEnvelopeRespected,true);
 assert.equal(chosen.continuity,true);assert.equal(chosen.summary.safeAreaViolations,0);
 assert.equal(chosen.summary.criticalCollisions,0);assert.equal(chosen.summary.motion.framesChecked,150);
 assert.equal(chosen.summary.motion.fakeLockCount,0);
});
test('front prioritization samples the actual supplied land domain and improves measured screen margin/focus',()=>{
 const camera=selected();
 assert.ok(camera.baseline.points.every(p=>p.activeLandFrontSamples>0&&p.activeLandFrontSamples<scene.controlIntent.longitudinal_knots.length));
 assert.ok(camera.selected.summary.frontFocusRmsPixels<camera.baseline.frontFocusRmsPixels);
 assert.ok(camera.selected.summary.meanFrontWidthPixels>camera.baseline.meanFrontWidthPixels);
 assert.ok(camera.selected.summary.minimumFrontMarginPixels>camera.baseline.minimumFrontMarginPixels);
 assert.equal(camera.selected.summary.motion.positionContinuous,true);assert.equal(camera.selected.summary.motion.velocityContinuous,true);
});
test('camera choice is deterministic and E/F share the same camera candidate',()=>{
 assert.deepEqual(selectQualityCamera(inputs),selected());
 const choose=p=>qualityProfile(p).camera?selected().scenePlan:scene;
 assert.deepEqual(choose('E').cameraKeyframes,choose('F').cameraKeyframes);
 for(const letter of 'ABCD')assert.deepEqual(choose(letter).cameraKeyframes,scene.cameraKeyframes);
});
test('no safe candidate retains exact protected camera instead of weakening admission',()=>{
 const blocked=selectQualityCamera({...inputs,inheritedNativeBounds:[-179,-89,179,89]});
 assert.equal(blocked.changed,false);assert.equal(blocked.decision,'USE_PROTECTED_CAMERA_NO_SAFE_IMPROVEMENT');
 assert.deepEqual(blocked.scenePlan.cameraKeyframes,scene.cameraKeyframes);
 assert.ok(blocked.candidates.every(c=>!c.admitted&&!c.nativeFloorRespected));
});
