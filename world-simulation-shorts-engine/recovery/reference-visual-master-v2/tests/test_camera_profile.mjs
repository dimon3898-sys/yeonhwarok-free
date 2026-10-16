/** Stage G focused CPU cadence checks. No browser, native GPU or renderer launch. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {selectQualityCamera} from '../../visual-quality-upgrade-v1/quality_profiles.mjs';
import {selectReferenceUnitScale} from '../unit-size-profile.mjs';
import {selectReferenceCamera,auditReferenceCamera,validateReferenceCameraProfile} from '../camera-profile.mjs';
const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 read=async p=>JSON.parse(await readFile(path.join(engine,p),'utf8')),
 fixture=await read('recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'),
 original=await read('recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),
 input={baseCameraPlan:await read(fixture.nativeFiles.cameraPlan),currentNativeFrame:fixture.currentNativeFrame,
  safeArea:(await read(fixture.nativeFiles.regionalPlan)).layout.safe,
  inheritedNativeBounds:(await read(fixture.inheritedAdmissionFiles.scenePlan)).cameraKeyframes.at(-1).bounds},
 // This constructs the saved old-F input ONCE. The new planner never calls it.
 oldF=selectQualityCamera({...input,scenePlan:original}).scenePlan,
 units=selectReferenceUnitScale({...input,scenePlan:oldF,profile:{enabled:true}}).scenePlan,
 current={...input,scenePlan:units};
let selected;
const main=()=>selected??=selectReferenceCamera({...current,profile:{enabled:true}});

test('absent/disabled profile preserves old F Scene and all150 sampled camera poses exactly',()=>{
 const before=JSON.stringify(oldF),base=auditReferenceCamera({...input,scenePlan:oldF});
 for(const profile of [undefined,{}, {enabled:false,holdDurationFrames:12,cameraSmoothing:0}]){
  const result=selectReferenceCamera({...input,scenePlan:oldF,profile});
  assert.equal(JSON.stringify(result.scenePlan),before);assert.equal(result.changed,false);
  assert.deepEqual(auditReferenceCamera({...input,scenePlan:result.scenePlan}).poses,base.poses);
 }
 assert.equal(JSON.stringify(oldF),before);
});
test('default enabled candidate has an actual10-frame position/extent/roll read hold and C1 velocity continuity',()=>{
 const result=main(),a=result.audit,motion=a.effective.motion;
 assert.equal(result.changed,true);const {startFrame,endFrame}=a.selected;
 assert.ok(startFrame>0&&endFrame<149);assert.equal(endFrame-startFrame+1,10);
 assert.equal(a.selected.displayedFrames,10);assert.equal(a.selected.rampFrames,18);
 assert.deepEqual(motion.readHoldRuns.map(r=>[r.startFrame,r.endFrame,r.displayedFrames]),[[startFrame,endFrame,10]]);
 assert.equal(motion.analyticalCameraVelocityContinuous,true);assert.equal(motion.analyticalRollVelocityContinuous,true);
 assert.equal(motion.fakeLockCount,0);assert.equal(motion.actualPoseHoldMeasured,true);
 assert.equal(a.cameraReadHoldOnly,true);assert.equal(a.eventHoldSupported,false);
 const pose=auditReferenceCamera({...current,scenePlan:result.scenePlan}).poses;
 for(let f=startFrame+1;f<=endFrame;f++)pose[f].pose.forEach((v,i)=>assert.ok(Math.abs(v-pose[startFrame].pose[i])<1e-10));
 assert.ok(pose[startFrame-1].pose.some((v,i)=>Math.abs(v-pose[startFrame].pose[i])>1e-10));
 assert.ok(pose[endFrame+1].pose.some((v,i)=>Math.abs(v-pose[startFrame].pose[i])>1e-10));
});
test('greedy opportunity search retains later safe alternatives beyond the twelve highest-scoring attempts',()=>{
 const starts=[...new Set(main().audit.attempts.map(a=>a.startFrame))];
 assert.ok(starts.length>12&&starts.length<=32);
 starts.forEach((value,i)=>starts.slice(0,i).forEach(prior=>assert.ok(Math.abs(value-prior)>=3)));
 assert.equal(starts.at(-1),main().audit.selected.startFrame);
 assert.ok(main().audit.attempts.slice(0,12*3).every(a=>!a.admitted));
});
test('same118.56px units pass original SAT/layout while native floor/envelope and every previously visible domain vertex stay safe',()=>{
 const a=main().audit,picked=a.attempts.find(v=>v.admitted),layout=a.effective.layout;
 assert.equal(picked.floorRespected,true);assert.equal(picked.sourceEnvelopeRespected,true);
 assert.equal(picked.continuity,true);assert.equal(layout.newDomainCropVertexFrames,0);
 assert.equal(layout.unitSafeAreaViolations,0);assert.equal(layout.criticalCollisions,0);assert.equal(layout.unitOverlapPairFrames,0);
 assert.equal(layout.frontSafeAreaViolations,0);assert.equal(layout.activeFrontSampleFrames,150);
 assert.equal(a.baseline.layout.wholeControlDomainVisibleAllFrames,false);
 assert.equal(layout.wholeControlDomainVisibleAllFrames,false); // Existing inactive-domain crop is disclosed, not forged away.
 assert.equal(layout.framesChecked,150);assert.ok(a.effective.motion.maximumCenterAccelerationPixelsPerFrameSquared<=1);
 assert.ok(units.combatProfile.units.every(u=>u.size_frames.every(v=>Math.abs(v-118.56)<1e-9)));
});
test('only new Scene camera keys change; geometry, control and all150 unit/territory source frames stay exact',()=>{
 const result=main().scenePlan,{cameraKeyframes:unused,...rest}=result,
  {cameraKeyframes:prior,...baseline}=units;
 assert.deepEqual(rest,baseline);assert.equal(result.cameraKeyframes.length,150);
 assert.deepEqual(result.cameraKeyframes[0],prior[0]);
 assert.deepEqual(result.cameraKeyframes.at(-1),prior.at(-1));
 assert.deepEqual(result.controlIntent,units.controlIntent);assert.deepEqual(result.combatProfile,units.combatProfile);
 assert.equal(main().audit.eventFrameIndicesUnchanged,true);assert.equal(main().audit.objectFrameIndicesUnchanged,true);
 assert.equal(main().audit.eventTimingChanged,false);assert.equal(main().audit.objectTimingChanged,false);
});
test('CameraSmoothing and FocusPriority have bounded measurable scene effects when their candidates are safe',()=>{
 const lowSmooth=selectReferenceCamera({...current,profile:{enabled:true,cameraSmoothing:.7}}),
  lowFocus=selectReferenceCamera({...current,profile:{enabled:true,focusPriority:.5}});
 assert.equal(lowSmooth.changed,true);assert.equal(lowFocus.changed,true);
 assert.notEqual(lowSmooth.audit.selected.rampFrames,main().audit.selected.rampFrames);
 assert.notEqual(lowFocus.audit.selected.startFrame,main().audit.selected.startFrame);
 assert.notDeepEqual(lowSmooth.scenePlan.cameraKeyframes,main().scenePlan.cameraKeyframes);
 assert.notDeepEqual(lowFocus.scenePlan.cameraKeyframes,main().scenePlan.cameraKeyframes);
});
test('unsafe smoothing candidate falls back to exact old F instead of weakening any guard',()=>{
 const result=selectReferenceCamera({...current,profile:{enabled:true,cameraSmoothing:.2}});
 assert.equal(result.changed,false);assert.equal(result.audit.decision,'USE_OLD_F_NO_SAFE_CAMERA_CANDIDATE');
 assert.deepEqual(result.scenePlan,units);assert.ok(result.audit.attempts.length>0);
 assert.ok(result.audit.attempts.every(a=>!a.admitted));
 assert.equal(result.audit.gpuVideoVerified,false);
});
test('zero read hold is explicit disabled camera cadence, not an event hold or fabricated lock',()=>{
 const result=selectReferenceCamera({...current,profile:{enabled:true,holdDurationFrames:0}});
 assert.equal(result.changed,false);assert.equal(result.audit.decision,'CAMERA_READ_HOLD_DISABLED');
 assert.deepEqual(result.scenePlan,units);assert.deepEqual(result.audit.effective.motion.readHoldRuns,[]);
 assert.equal(result.audit.eventHoldSupported,false);
});
test('unknown/unsafe camera controls and non-camera event retiming are rejected explicitly',()=>{
 for(const profile of [null,[],false,{enabled:1},{cameraSmoothing:NaN},{cameraSmoothing:-.01},{cameraSmoothing:1.01},
  {focusPriority:Infinity},{focusPriority:-1},{holdDurationFrames:1},{holdDurationFrames:8},{holdDurationFrames:13},
  {holdDurationFrames:10.5},{EventHoldDuration:10},{eventHoldDuration:0},{country:'subject'},{forceAllow:true}])
  assert.throws(()=>validateReferenceCameraProfile(profile));
 for(const count of [0,9,10,11,12])assert.equal(validateReferenceCameraProfile({holdDurationFrames:count}).holdDurationFrames,count);
 assert.throws(()=>selectReferenceCamera({...current,safeArea:[0,0,1081,1920],profile:{enabled:true}}),/SAFE_CONTEXT/);
});
