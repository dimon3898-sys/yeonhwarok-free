/** Stage F CPU Scene/profile/layout regression; no browser or GPU is invoked. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {selectQualityCamera} from '../../visual-quality-upgrade-v1/quality_profiles.mjs';
import {selectReferenceUnitScale,validateReferenceUnitProfile} from '../unit-size-profile.mjs';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 read=async relative=>JSON.parse(await readFile(path.join(engine,relative),'utf8')),
 fixture=await read('recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'),
 original=await read('recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),
 baseCameraPlan=await read(fixture.nativeFiles.cameraPlan),regional=await read(fixture.nativeFiles.regionalPlan),
 inherited=await read(fixture.inheritedAdmissionFiles.scenePlan),
 currentF=selectQualityCamera({scenePlan:original,baseCameraPlan,currentNativeFrame:fixture.currentNativeFrame,
  safeArea:regional.layout.safe,inheritedNativeBounds:inherited.cameraKeyframes.at(-1).bounds}).scenePlan,
 input={scenePlan:currentF,baseCameraPlan,currentNativeFrame:fixture.currentNativeFrame,safeArea:regional.layout.safe};
const withoutSizes=units=>units.map(({size_frames,...rest})=>rest);

test('absent or disabled profile preserves original Scene bytes exactly',()=>{
 const before=JSON.stringify(currentF);
 for(const profile of [undefined,{}, {enabled:false,markerScale:1.25}]){
  const result=selectReferenceUnitScale({...input,profile});
  assert.equal(JSON.stringify(result.scenePlan),before);assert.equal(result.changed,false);assert.equal(result.audit.selectedScale,1);
 }
 assert.equal(JSON.stringify(currentF),before);
});
test('static1.14 improves measured artwork and passes all150 existing layout frames',()=>{
 const before=JSON.stringify(currentF),result=selectReferenceUnitScale({...input,profile:{enabled:true,markerScale:1.14}}),a=result.audit;
 assert.equal(a.selectedScale,1.14);assert.equal(a.effective.framesChecked,150);assert.equal(a.effective.unitCount,8);
 assert.equal(a.effective.safeAreaViolations,0);assert.equal(a.effective.criticalCollisions,0);assert.equal(a.effective.unitOverlapPairFrames,0);
 assert.ok(a.effective.minimumSafeMarginPixels>190);assert.ok(a.effective.artworkWidthPixels[0]>105);
 assert.ok(a.effective.flagWidthPixels[0]>75);assert.ok(a.effective.artworkWidthPixels[0]>a.baseline.artworkWidthPixels[0]);
 for(const unit of result.scenePlan.combatProfile.units)assert.ok(unit.size_frames.every(size=>Math.abs(size-118.56)<1e-9));
 assert.equal(a.sizePumping,false);assert.equal(a.gpuPixelsVerified,false);assert.equal(JSON.stringify(currentF),before);
});
test('requested1.25 clamps using original overlap classifier rather than moving anchors',()=>{
 const result=selectReferenceUnitScale({...input,profile:{enabled:true,markerScale:1.25}}),a=result.audit;
 assert.equal(a.selectedScale,1.14);assert.equal(a.decision,'STATIC_SCALE_SAFETY_CLAMPED');
 assert.ok(a.attempts.some(value=>value.scale===1.25&&value.unitOverlapPairFrames>0));
 assert.equal(a.effective.unitOverlapPairFrames,0);
 assert.deepEqual(withoutSizes(result.scenePlan.combatProfile.units),withoutSizes(currentF.combatProfile.units));
});
test('artwork, national profiles, camera, event, anchors and rotations are unchanged',()=>{
 const result=selectReferenceUnitScale({...input,profile:{enabled:true}}).scenePlan,expected=structuredClone(currentF);
 expected.combatProfile.units=result.combatProfile.units;
 assert.deepEqual(result,expected);
 assert.deepEqual(result.combatProfile.profiles,currentF.combatProfile.profiles);
 assert.deepEqual(withoutSizes(result.combatProfile.units),withoutSizes(currentF.combatProfile.units));
});
test('arbitrary role and country identifiers do not affect the scale contract',()=>{
 const scenePlan=structuredClone(currentF),roles=['SUPPORT','AVIATION','GROUND'];
 scenePlan.combatProfile.units.forEach((unit,index)=>{unit.id='arbitrary-unit-'+index;unit.role=roles[index%3];});
 for(const profile of Object.values(scenePlan.combatProfile.profiles))profile.country_id='GENERIC_CALLER_COUNTRY';
 const result=selectReferenceUnitScale({...input,scenePlan,profile:{enabled:true}});
 assert.equal(result.audit.selectedScale,1.14);assert.equal(result.audit.effective.unitOverlapPairFrames,0);
 assert.deepEqual(withoutSizes(result.scenePlan.combatProfile.units),withoutSizes(scenePlan.combatProfile.units));
 assert.deepEqual(result.scenePlan.combatProfile.profiles,scenePlan.combatProfile.profiles);
});
test('existing national max140 can require original static size for every unit',()=>{
 const scenePlan=structuredClone(currentF);scenePlan.combatProfile.units[0].size_frames.fill(140);
 const result=selectReferenceUnitScale({...input,scenePlan,profile:{enabled:true,markerScale:1.25}});
 assert.equal(result.audit.nationalScaleLimit,1);assert.equal(result.audit.selectedScale,1);assert.equal(result.changed,false);
 assert.deepEqual(result.scenePlan,scenePlan);
});
test('invalid options and unknown parameters fail explicitly',()=>{
 for(const profile of [null,[],false,'F',{enabled:1},{enabled:'true'},{markerScale:NaN},{markerScale:Infinity},
  {markerScale:.99},{markerScale:1.251},{markerScale:true},{country:'caller'},{markerScale:1.14,forceAllow:true}])
  assert.throws(()=>validateReferenceUnitProfile(profile));
 for(const safeArea of [[0,0,1081,1920],[-1,0,1080,1920],[0,0,1080,1921],null])
  assert.throws(()=>selectReferenceUnitScale({...input,safeArea,profile:{enabled:true}}),/REFERENCE_UNIT_SAFE_AREA_REQUIRED/);
});
test('unsafe source anchors are rejected without changing any source field',()=>{
 const scenePlan=structuredClone(currentF);scenePlan.combatProfile.units[1].anchor_frames=structuredClone(scenePlan.combatProfile.units[0].anchor_frames);
 const before=JSON.stringify(scenePlan);
 assert.throws(()=>selectReferenceUnitScale({...input,scenePlan,profile:{enabled:true}}),/REFERENCE_UNIT_BASELINE_LAYOUT_UNSAFE/);
 assert.equal(JSON.stringify(scenePlan),before);
});
test('source national size and timeline mismatches are rejected',()=>{
 const tooSmall=structuredClone(currentF);tooSmall.combatProfile.units[0].size_frames[0]=71;
 assert.throws(()=>selectReferenceUnitScale({...input,scenePlan:tooSmall,profile:{enabled:true}}),/NATIONAL_UNIT_RESOLVED_FRAME_DATA_REQUIRED/);
 const short=structuredClone(currentF);
 for(const unit of short.combatProfile.units){unit.anchor_frames.pop();unit.rotation_frames.pop();unit.size_frames.pop();}
 assert.throws(()=>selectReferenceUnitScale({...input,scenePlan:short,profile:{enabled:true}}),/REFERENCE_UNIT_TIMELINE_BINDING_REQUIRED/);
});
