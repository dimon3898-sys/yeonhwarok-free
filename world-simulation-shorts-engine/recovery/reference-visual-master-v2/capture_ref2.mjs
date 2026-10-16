/** One fixed official Node runtime edge over the unchanged original ASTRA
 * capture. No nested quality capture hook, source rewrite or framebuffer copy. */
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {invalidateQualityCapture} from '../visual-quality-upgrade-v1/capture_quality.mjs';
import {sourceGradeIsNeutral} from './source_grade_core.mjs';
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
export const originalCaptureURL=new URL('../astra-gpu-activation-v1/capture_astra.mjs',import.meta.url).href;
export const referenceRuntimeURL=new URL('./ref2_runtime.mjs',import.meta.url).href;
export function resolveReferenceCapture(specifier,context,nextResolve){
 if(context.parentURL===originalCaptureURL&&specifier==='./astra_runtime.mjs')
  return {url:referenceRuntimeURL,shortCircuit:true};
 return nextResolve(specifier,context);
}
const hash=value=>assert.match(value,/^[a-f0-9]{64}$/);
export function assertReferenceCaptureReport(report){
 assert.equal(report.status,'CAPTURE_TECHNICAL_PASS');assert.equal(report.astraApplied,true);
 assert.equal(report.astraProfileId,'REFERENCE_VISUAL_MASTER_V2_F');
 const runtime=report.runtime,profile=runtime?.referenceV2,evidence=runtime?.evidence;
 assert.equal(profile?.family,'REFERENCE_VISUAL_MASTER_V2');assert.equal(profile.variant,'F');
 assert.equal(profile.testOnly,false);assert.equal(profile.qualityApproved,false);
 for(const key of ['profileSha256','actualSceneSha256','cameraKeyframeSha256','candidateCameraSceneSha256','baseSceneSha256'])hash(profile[key]);
 const gradeRequired=!sourceGradeIsNeutral(profile.source),goldRequired=profile.frontier.outerGoldIntensity>0;
 if(gradeRequired){assert.equal(evidence.terrainPass.sourceGrade.version,'REFERENCE_SOURCE_GRADE_V2');
  assert.equal(evidence.terrainPass.sourceGrade.enabled,true);assert.equal(evidence.terrainPass.sourceGrade.testOnly,false);}
 assert.equal(evidence.territoryPass.gainTerritory.actualFactorySelected,true);
 assert.equal(evidence.territoryPass.gainTerritory.gainedMaterialDistinct,true);
 assert.equal(evidence.frontierPass.referenceFrontier.version,'REFERENCE_FRONTIER_EXPRESSION_V2');
 assert.equal(evidence.frontierPass.referenceFrontier.originalBoundaryAlgorithm,true);
 assert.equal(evidence.frontierPass.referenceFrontier.originalMotionAndStopLogic,true);
 const domain=evidence.frontierPass.referenceFrontier.outerGoldDomain;
 if(goldRequired){hash(domain.domainSHA256);hash(domain.sourceGeometrySHA256);}
 const units=runtime.runtimeConfig.bootstrap.scenePlan.combatProfile.units;assert.ok(Array.isArray(units)&&units.length>0);
 assert.equal(report.frames.length,150);
 for(let frame=0;frame<150;frame++){
  const row=report.frames[frame],d=row.diagnostic,actual=d.referenceV2;
  assert.equal(row.frame,frame);assert.equal(actual?.variant,'F');assert.equal(actual.family,'REFERENCE_VISUAL_MASTER_V2');
  assert.equal(actual.testOnly,false);
  for(const key of ['profileSha256','actualSceneSha256','cameraKeyframeSha256'])
   assert.equal(actual[key],profile[key],'REFERENCE_FRAME_BINDING_MISMATCH_'+key);
  if(gradeRequired){
   assert.equal(d.terrain.sourceGrade.enabled,true);assert.equal(d.terrain.sourceGrade.gradeDraws,1);
   assert.equal(d.terrain.sourceGrade.sourceMaterialBeforeTerritory,true);assert.equal(d.terrain.sourceGrade.combinedOutputTexture,true);
   assert.equal(d.terrain.sourceGrade.actualNativeCoverage,true);assert.equal(d.terrain.sourceGrade.testOnly,false);
  }
  assert.equal(d.territory.graphics.gainTerritory.actualFactorySelected,true);
  assert.equal(d.territory.graphics.gainTerritory.gainedMaterialDistinct,true);
  assert.equal(d.territory.graphics.gainTerritory.domainGeometryBinding,runtime.domainGeometryBinding);
  assert.equal(d.territory.graphics.gainTerritory.boundaryKeyframeBinding,runtime.boundaryKeyframeBinding);
  assert.equal(d.frontierLight.referenceFrontier.originalBoundaryAlgorithm,true);
  const gold=d.frontierLight.outerDomainGold;
  if(goldRequired){
  assert.equal(gold.version,'REFERENCE_NATIVE_DOMAIN_OUTER_GOLD_V2');
  assert.equal(gold.domainSHA256,domain.domainSHA256);assert.equal(gold.sourceGeometrySHA256,domain.sourceGeometrySHA256);
  assert.equal(gold.sharedInternalOutline,false);assert.equal(gold.allLandRChannelUsed,false);
  assert.equal(gold.sourceRGBMaskInference,false);assert.equal(gold.fabricatedViewportEdge,false);
  assert.equal(gold.newDecorativeLines,0);assert.equal(gold.newArrows,0);
  assert.equal(gold.frame,d.frontierLight.frame);assert.equal(gold.nativeStateRestored,true);
  }
  assert.equal(d.units.units.length,units.length);
  for(const unit of units){const actualUnit=d.units.units.find(item=>item.id===unit.id);
   assert.ok(actualUnit);assert.equal(actualUnit.size_px,unit.size_frames[frame]);}
  assert.equal(d.units.safeAreaViolations.length,0);assert.equal(d.units.criticalCollisions.length,0);
  assert.equal(d.units.unitOverlaps.length,0);
 }
 return true;
}
async function verifyExtension(){
 const result=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'prepare_ref2.py'),
  '--verify-extension'],{maxBuffer:1024*1024})).stdout);
 assert.equal(result.status,'PASS');hash(result.manifestSha256);return result;
}
export async function captureReferenceV2(options){
 const before=await verifyExtension(),hook=registerHooks({resolve:resolveReferenceCapture});let inherited;
 try{inherited=await import(originalCaptureURL);}finally{hook.deregister();}
 const report=await inherited.captureAstra(options);
 try{assertReferenceCaptureReport(report);assert.deepEqual(await verifyExtension(),before,'REFERENCE_EXTENSION_CHANGED_DURING_CAPTURE');}
 catch(error){
  try{await invalidateQualityCapture(report,options);}catch(persistError){console.error(JSON.stringify({schema:'WORLD_ENGINE_REFERENCE_CAPTURE_V2',
   status:'BLOCKED',errorCode:'REFERENCE_CAPTURE_VALIDATION_FAILED',captureStatePersisted:false,gpuRenderingVerified:false}));}
  throw error;
 }
 console.log(JSON.stringify({schema:'WORLD_ENGINE_REFERENCE_CAPTURE_V2',status:'CAPTURE_TECHNICAL_PASS',
  profile:'REFERENCE_VISUAL_MASTER_V2_F',captureId:report.signature,sourceSignature:report.runtimeSourceSignature,
  videoQualityApproved:false}));return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const args=process.argv.slice(2),options={};
  while(args.length){const key=args.shift();assert.ok(['--admission-file','--output-root'].includes(key)&&args.length,
   'EXPLICIT_RENDER_ARGUMENTS_REQUIRED');assert.ok(!Object.hasOwn(options,key),'DUPLICATE_RENDER_ARGUMENT');options[key]=args.shift();}
  await captureReferenceV2({admissionFile:options['--admission-file'],outputRoot:options['--output-root']});
 }catch(error){console.error(JSON.stringify({schema:'WORLD_ENGINE_REFERENCE_CAPTURE_V2',status:'BLOCKED',
  errorCode:/^[A-Z][A-Z0-9_]{1,95}$/.test(error?.message??'')?error.message:'REFERENCE_CAPTURE_FAILED',
  gpuRenderingVerified:false,videoQualityApproved:false}));process.exitCode=2;}
}
