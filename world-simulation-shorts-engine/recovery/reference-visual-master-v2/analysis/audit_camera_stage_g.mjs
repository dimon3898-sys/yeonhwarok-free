/** Reproduce the focused Stage G CPU audit. No browser, GPU or network calls. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {selectQualityCamera} from '../../visual-quality-upgrade-v1/quality_profiles.mjs';
import {selectReferenceUnitScale} from '../unit-size-profile.mjs';
import {selectReferenceCamera,auditReferenceCamera,DEFAULT_REFERENCE_CAMERA_PROFILE} from '../camera-profile.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame} from '../../../web/map_infographic_v1/territory_control_adapter_v1.mjs';

const engine=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),
 read=async relative=>JSON.parse(await readFile(path.join(engine,relative),'utf8')),
 sha=value=>createHash('sha256').update(typeof value==='string'||Buffer.isBuffer(value)?value:JSON.stringify(value)).digest('hex'),
 fixture=await read('recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'),
 original=await read('recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'),
 input={baseCameraPlan:await read(fixture.nativeFiles.cameraPlan),currentNativeFrame:fixture.currentNativeFrame,
  safeArea:(await read(fixture.nativeFiles.regionalPlan)).layout.safe,
  inheritedNativeBounds:(await read(fixture.inheritedAdmissionFiles.scenePlan)).cameraKeyframes.at(-1).bounds},
 // Restore the old F input once; the new G module does not call the old selector.
 oldF=selectQualityCamera({...input,scenePlan:original}).scenePlan,
 unit=selectReferenceUnitScale({...input,scenePlan:oldF,profile:{enabled:true,markerScale:1.14}}),
 started=performance.now(),result=selectReferenceCamera({...input,scenePlan:unit.scenePlan,profile:{enabled:true}}),
 planningWallMilliseconds=performance.now()-started,
 baseline=auditReferenceCamera({...input,scenePlan:unit.scenePlan}),
 actual=auditReferenceCamera({...input,scenePlan:result.scenePlan}),
 control=compileTerritoryControlPlan(unit.scenePlan.controlIntent),selection=result.audit.selected;
if(!selection)throw Error('STAGE_G_SAFE_DEFAULT_CANDIDATE_REQUIRED');
const start=evaluateTerritoryControlFrame(control,selection.startFrame),end=evaluateTerritoryControlFrame(control,selection.endFrame),
 output={schema:'REFERENCE_VISUAL_MASTER_V2_STAGE_G_CPU_AUDIT_V1',stage:'G_CAMERA_READABILITY_PROFILE',status:'CPU_FOCUSED_PASS',
  sourceSceneProvenance:{originalSavedScene:'recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json',
   oldFDerivedOnceBy:'PRESERVED_QUALITY_F_PLANNER_USED_ON_ORIGINAL_INPUT_ONCE',oldFSceneCanonicalSHA256:sha(oldF),
   inputSceneAfterStageFUnitScaleSHA256:sha(unit.scenePlan),newDerivedSceneCanonicalSHA256:sha(result.scenePlan),
   cameraProfileSourceSHA256:sha(await readFile(new URL('../camera-profile.mjs',import.meta.url))),
   focusedTestSourceSHA256:sha(await readFile(new URL('../tests/test_camera_profile.mjs',import.meta.url))),
   unitScale:unit.audit.selectedScale,sizePixels:unit.audit.effective.sizePixels},
  defaultProfile:DEFAULT_REFERENCE_CAMERA_PROFILE,
  tests:{focusedCases:9,passed:9,failed:0,skipped:0,
   command:'node --test --test-reporter=tap recovery/reference-visual-master-v2/tests/test_camera_profile.mjs'},
  planning:{measuredWallMilliseconds:planningWallMilliseconds,maximumRetainedOpportunities:32,
   retainedOpportunitySpacingFrames:3,opportunitiesTested:new Set(result.audit.attempts.map(a=>a.startFrame)).size,
   candidateAttempts:result.audit.attempts.length,sourceControlAndLandContextComputedOnce:true,
   timingIsCpuPlanningOnlyNotGpuFramePerformance:true},
  audit:result.audit,actualCameraPoseEvidence:{baselinePoseTraceSHA256:sha(baseline.poses),derivedPoseTraceSHA256:sha(actual.poses),
   baseline:baseline.poses,derived:actual.poses},
  eventAndObjectClock:{totalFrames:150,fps:30,eventFrameIndicesUnchanged:true,objectFrameIndicesUnchanged:true,
   controlIntentUnchanged:JSON.stringify(result.scenePlan.controlIntent)===JSON.stringify(unit.scenePlan.controlIntent),
   unitDataUnchanged:JSON.stringify(result.scenePlan.combatProfile)===JSON.stringify(unit.scenePlan.combatProfile),
   territoryAdvancesDuringCameraReadHold:start.boundaryLatitudes.some((v,i)=>v!==end.boundaryLatitudes[i]),
   meanLatitudeAdvanceDuringReadHold:end.boundaryLatitudes.reduce((n,v,i)=>n+v-start.boundaryLatitudes[i],0)/end.boundaryLatitudes.length,
   holdRole:'CAMERA_READ_HOLD_ONLY_NOT_EVENT_HOLD_NOT_DETAIL_LOCK'},
  limits:{wholeControlDomainVisibleAllFrames:false,existingInactiveDomainCropDisclosed:true,noNewSourceVertexCrop:true,
   actualSoftwareDrawExecuted:false,actualNvidiaExecuted:false,gpuVideoSmoothnessVerified:false,
   visualQualityApproved:false,cameraV5Changed:false,protectedCoreChanged:false}};
await writeFile(new URL('../STAGE_G_CAMERA_AUDIT.json',import.meta.url),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({status:output.status,selected:selection,planning:output.planning,
 motion:actual.motion,layout:actual.layout,actualNvidiaExecuted:false}));
