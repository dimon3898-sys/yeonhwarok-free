/** New reference runtime assembly only: no browser, GPU, old suites or original source edits. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {selectQualityCamera} from '../../visual-quality-upgrade-v1/quality_profiles.mjs';
import {readAdmission as originalReadAdmission,assertHardwareBackend as originalAssertHardwareBackend}
 from '../../astra-gpu-activation-v1/astra_runtime.mjs';
import {referenceV2Profile} from '../ref2_profiles.mjs';
import {deriveReferenceScene,validateReferenceRuntimeManifest,assertReferenceProductionPlan,
 readAdmission,assertHardwareBackend,loadAstraRuntimePlan,loadReferenceRuntimePlan,openAstraRuntime,openReferenceRuntime}
 from '../ref2_runtime.mjs';

const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 read=async file=>JSON.parse(await readFile(path.join(engine,file),'utf8')),
 fixture=await read('recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'),
 originalScene=await read('recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),
 cameraInput={baseCameraPlan:await read(fixture.nativeFiles.cameraPlan),currentNativeFrame:fixture.currentNativeFrame,
  safeArea:(await read(fixture.nativeFiles.regionalPlan)).layout.safe,
  inheritedNativeBounds:(await read(fixture.inheritedAdmissionFiles.scenePlan)).cameraKeyframes.at(-1).bounds},
 baseScene=selectQualityCamera({...cameraInput,scenePlan:originalScene}).scenePlan,
 before=JSON.stringify(baseScene),derived=new Map();
function variant(letter){
 if(!derived.has(letter))derived.set(letter,deriveReferenceScene({baseScene,cameraInput,normalized:referenceV2Profile(letter)}));
 return derived.get(letter);
}
const mandatory=['ref2_runtime.mjs','ref2_adapter.mjs','serve_ref2.py','ref2_profiles.mjs',
 'gain_territory.mjs','gain_style_core.mjs','reference_source_material.mjs','source_grade_core.mjs',
 'source_grade_pass.mjs','native_domain_coverage.mjs','frontier_ref2.mjs','frontier_profile_core.mjs',
 'coverage_outer_glow.mjs','unit-size-profile.mjs','camera-profile.mjs'];
function manifest(){return {schema:'WORLD_ENGINE_REFERENCE_VISUAL_FILES_V2',family:'REFERENCE_VISUAL_MASTER_V2',
 profileId:'REFERENCE_VISUAL_MASTER_V2',files:Object.fromEntries(mandatory.map(name=>[name,'1'.repeat(64)])),
 testFiles:{'gain_ab_probe.mjs':'2'.repeat(64)}};}
function productionPlan(){return {referenceV2:{variant:'F',testOnly:false},
 profile:{profileId:'REFERENCE_VISUAL_MASTER_V2_F'},serverConfig:{runtimeConfig:{testOnlySoftwareProbe:false}}};}

test('old capture aliases reuse the same new runtime and original hardware admission functions',()=>{
 assert.equal(loadAstraRuntimePlan,loadReferenceRuntimePlan);assert.equal(openAstraRuntime,openReferenceRuntime);
 assert.equal(readAdmission,originalReadAdmission);assert.equal(assertHardwareBackend,originalAssertHardwareBackend);
});
test('absent reference profile selects A and preserves the actual old F Scene exactly',()=>{
 assert.equal(referenceV2Profile().variant,'A');assert.deepEqual(variant('A').actualScene,baseScene);
 assert.equal(JSON.stringify(baseScene),before);assert.equal(variant('A').actualScene.combatProfile.units[0].size_frames[0],104);
});
test('D enlarges units once while retaining the exact old F camera and unchanged event geometry/timeline',()=>{
 const result=variant('D').actualScene;
 assert.deepEqual(result.cameraKeyframes,baseScene.cameraKeyframes);
 assert.deepEqual(result.controlIntent,baseScene.controlIntent);
 assert.deepEqual(result.combatProfile.contacts,baseScene.combatProfile.contacts);
 assert.ok(result.combatProfile.units.every(unit=>unit.size_frames.every(size=>Math.abs(size-118.56)<1e-9)));
 const withoutUnits=scene=>({...scene,combatProfile:{...scene.combatProfile,units:[]}});
 assert.deepEqual(withoutUnits(result),withoutUnits(baseScene));
 for(const [i,unit]of result.combatProfile.units.entries()){
  const {size_frames:unused,...rest}=unit,{size_frames:old,...source}=baseScene.combatProfile.units[i];assert.deepEqual(rest,source);
 }
});
test('E and F use identical candidate camera keys audited against the same118.56px units',()=>{
 const e=variant('E'),f=variant('F');
 assert.deepEqual(e.actualScene.cameraKeyframes,f.actualScene.cameraKeyframes);
 assert.deepEqual(e.cameraCandidate.scenePlan,f.cameraCandidate.scenePlan);
 assert.deepEqual(e.actualScene.combatProfile.units,baseScene.combatProfile.units);
 assert.deepEqual(f.actualScene.combatProfile.units,variant('D').actualScene.combatProfile.units);
 assert.equal(f.cameraCandidate.audit.cameraReadHoldOnly,true);
 assert.equal(f.cameraCandidate.audit.eventTimingChanged,false);assert.equal(f.cameraCandidate.audit.objectTimingChanged,false);
 assert.equal(f.cameraCandidate.audit.effective.motion.fakeLockCount,0);
 assert.equal(f.cameraCandidate.audit.effective.motion.readHoldRuns[0].displayedFrames,10);
 assert.deepEqual(f.actualScene.controlIntent,baseScene.controlIntent);
 assert.equal(f.cameraCandidate.audit.effective.layout.newDomainCropVertexFrames,0);
 assert.equal(JSON.stringify(baseScene),before);
});
test('manifest binds required flat runtime and disjoint bounded test-tool closures',()=>{
 const value=manifest();assert.equal(validateReferenceRuntimeManifest(value),value);
 for(const mutate of [m=>delete m.family,m=>delete m.profileId,m=>m.profileId='other',m=>delete m.files['ref2_adapter.mjs'],
  m=>m.files['../outside.mjs']='1'.repeat(64),m=>m.files['unsafe.mjs']='bad',
  m=>m.testFiles['ref2_adapter.mjs']='1'.repeat(64),m=>m.files=[],m=>m.testFiles=[]]){
  const bad=manifest();mutate(bad);assert.throws(()=>validateReferenceRuntimeManifest(bad));
 }
});
test('production rejects A-E, old profile names and software/test-only provenance before GPU admission',()=>{
 const valid=productionPlan();assert.equal(assertReferenceProductionPlan(valid),valid);
 for(const letter of ['A','B','C','D','E']){
  const value=productionPlan();value.referenceV2.variant=letter;assert.throws(()=>assertReferenceProductionPlan(value),/INTEGRATED_F/);
 }
 for(const mutate of [p=>p.profile.profileId='VISUAL_QUALITY_UPGRADE_V1_F',
  p=>p.serverConfig.runtimeConfig.testOnlySoftwareProbe=true,p=>p.referenceV2.testOnly=true,
  p=>delete p.serverConfig.runtimeConfig.testOnlySoftwareProbe,p=>delete p.referenceV2.testOnly]){
  const value=productionPlan();mutate(value);assert.throws(()=>assertReferenceProductionPlan(value));
 }
});
