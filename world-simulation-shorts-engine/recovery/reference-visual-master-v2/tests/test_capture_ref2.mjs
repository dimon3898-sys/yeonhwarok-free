/** CPU contracts only. Real production hardware execution is not invoked. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {registerHooks} from 'node:module';
import path from 'node:path';
import {resolveReferenceCapture,originalCaptureURL,referenceRuntimeURL,assertReferenceCaptureReport}
 from '../capture_ref2.mjs';
import {invalidateQualityCapture} from '../../visual-quality-upgrade-v1/capture_quality.mjs';
const h='a'.repeat(64);
function report(){
 const referenceV2={family:'REFERENCE_VISUAL_MASTER_V2',variant:'F',profileSha256:h,actualSceneSha256:h,
  cameraKeyframeSha256:h,candidateCameraSceneSha256:h,baseSceneSha256:h,testOnly:false,qualityApproved:false,
  source:{enabled:true},frontier:{outerGoldIntensity:.75}},
  sourceGrade={version:'REFERENCE_SOURCE_GRADE_V2',enabled:true,testOnly:false,gradeDraws:1,
   sourceMaterialBeforeTerritory:true,combinedOutputTexture:true,actualNativeCoverage:true},
  gainTerritory={actualFactorySelected:true,gainedMaterialDistinct:true,domainGeometryBinding:'CPU_DOMAIN',boundaryKeyframeBinding:'CPU_BOUNDARY'},
  frontier={version:'REFERENCE_FRONTIER_EXPRESSION_V2',originalBoundaryAlgorithm:true,originalMotionAndStopLogic:true,
   outerGoldDomain:{domainSHA256:h,sourceGeometrySHA256:h}},
  units=[{id:'arbitrary-unit',size_frames:Array(150).fill(118.56)}];
 return {status:'CAPTURE_TECHNICAL_PASS',astraApplied:true,signature:'b'.repeat(64),activationSha256:'c'.repeat(64),
  astraProfileId:'REFERENCE_VISUAL_MASTER_V2_F',runtime:{referenceV2,domainGeometryBinding:'CPU_DOMAIN',boundaryKeyframeBinding:'CPU_BOUNDARY',
   runtimeConfig:{bootstrap:{scenePlan:{combatProfile:{units}}}},
   evidence:{terrainPass:{sourceGrade},territoryPass:{gainTerritory},frontierPass:{referenceFrontier:frontier}}},
  frames:Array.from({length:150},(_,frame)=>({frame,diagnostic:{referenceV2:{...referenceV2},terrain:{sourceGrade:{...sourceGrade}},
   territory:{graphics:{gainTerritory:{...gainTerritory}}},frontierLight:{frame,referenceFrontier:{...frontier},
    outerDomainGold:{version:'REFERENCE_NATIVE_DOMAIN_OUTER_GOLD_V2',frame,domainSHA256:h,sourceGeometrySHA256:h,
     sharedInternalOutline:false,allLandRChannelUsed:false,sourceRGBMaskInference:false,fabricatedViewportEdge:false,
     newDecorativeLines:0,newArrows:0,nativeStateRestored:true}},
   units:{units:[{id:'arbitrary-unit',size_px:118.56}],safeAreaViolations:[],criticalCollisions:[],unitOverlaps:[]}}}))};
}
test('fixed Node selector cannot remap another parent or dependency',()=>{
 const next=(specifier,context)=>({url:'next:'+specifier});
 assert.deepEqual(resolveReferenceCapture('./astra_runtime.mjs',{parentURL:originalCaptureURL},next),
  {url:referenceRuntimeURL,shortCircuit:true});
 assert.equal(resolveReferenceCapture('./astra_runtime.mjs',{parentURL:'file:///other.mjs'},next).url,'next:./astra_runtime.mjs');
 assert.equal(resolveReferenceCapture('./quality_runtime.mjs',{parentURL:originalCaptureURL},next).url,'next:./quality_runtime.mjs');
});
test('official Node24 hooks actually resolve the original capture edge without starting GPU',async()=>{
 let selected=0;
 const hook=registerHooks({resolve(specifier,context,next){
  if(context.parentURL===originalCaptureURL&&specifier==='./astra_runtime.mjs')selected++;
  return resolveReferenceCapture(specifier,context,next);
 }});
 let module;try{module=await import(originalCaptureURL);}finally{hook.deregister();}
 assert.equal(selected,1);assert.equal(typeof module.captureAstra,'function');
});
test('all150 actual factories, source-grade output, gain, native outer-domain and units are required',()=>{
 assert.equal(assertReferenceCaptureReport(report()),true);
 for(const edit of [r=>r.frames.pop(),r=>r.frames[7].diagnostic.referenceV2.profileSha256='d'.repeat(64),
  r=>r.frames[7].diagnostic.terrain.sourceGrade.gradeDraws=0,
  r=>r.frames[7].diagnostic.territory.graphics.gainTerritory.actualFactorySelected=false,
  r=>r.frames[7].diagnostic.frontierLight.outerDomainGold.allLandRChannelUsed=true,
  r=>r.frames[7].diagnostic.frontierLight.outerDomainGold.sharedInternalOutline=true,
  r=>r.frames[7].diagnostic.frontierLight.outerDomainGold.domainSHA256='d'.repeat(64),
  r=>r.frames[7].diagnostic.units.units[0].size_px=104,
  r=>r.frames[7].diagnostic.units.unitOverlaps=[['one','two']]]){
  const value=report();edit(value);assert.throws(()=>assertReferenceCaptureReport(value));
 }
});
test('old F material with only reference labels cannot receive F capture approval',()=>{
 for(const edit of [r=>delete r.runtime.evidence.terrainPass.sourceGrade,
  r=>delete r.runtime.evidence.territoryPass.gainTerritory,
  r=>delete r.runtime.evidence.frontierPass.referenceFrontier,
  r=>r.frames[149].diagnostic.terrain.sourceGrade.testOnly=true]){
  const value=report();edit(value);assert.throws(()=>assertReferenceCaptureReport(value));
 }
});
test('legal neutral source and white-only frontier profile do not demand disabled factories',()=>{
 const value=report();value.runtime.referenceV2.source={enabled:true,terrainLocalContrast:1,landExposure:1,oceanExposure:1,oceanTealMix:0};
 value.runtime.referenceV2.frontier.outerGoldIntensity=0;
 delete value.runtime.evidence.terrainPass.sourceGrade;value.runtime.evidence.frontierPass.referenceFrontier.outerGoldDomain=null;
 for(const row of value.frames){delete row.diagnostic.terrain.sourceGrade;row.diagnostic.frontierLight.outerDomainGold=null;}
 assert.equal(assertReferenceCaptureReport(value),true);
});
test('a failed reference validation blocks its own fresh report and preserves unrelated results',async()=>{
 const outputRoot=await mkdtemp('/workspace/test-only-reference-invalid-');
 try{const value=report(),directory=path.join(outputRoot,'captures',value.signature);await mkdir(directory,{recursive:true,mode:0o700});
  await writeFile(path.join(directory,'REPORT.json'),JSON.stringify(value),{mode:0o600});
  const publicDir=path.join(directory,'public-review');await mkdir(publicDir,{mode:0o700});
  await writeFile(path.join(publicDir,'KEEP.mp4'),'do not overwrite');
  const old=path.join(outputRoot,'captures','f'.repeat(64));await mkdir(old,{mode:0o700});
  await writeFile(path.join(old,'REPORT.json'),'unrelated prior result',{mode:0o600});
  value.frames[4].diagnostic.terrain.sourceGrade.gradeDraws=0;assert.throws(()=>assertReferenceCaptureReport(value));
  await invalidateQualityCapture(value,{outputRoot});
  assert.equal(JSON.parse(await readFile(path.join(directory,'REPORT.json'))).status,'BLOCKED');
  assert.equal(JSON.parse(await readFile(path.join(directory,'CAPTURE_STATUS.json'))).status,'BLOCKED');
  assert.equal(await readFile(path.join(publicDir,'KEEP.mp4'),'utf8'),'do not overwrite');
  assert.equal(await readFile(path.join(old,'REPORT.json'),'utf8'),'unrelated prior result');
 }finally{await rm(outputRoot,{recursive:true,force:true});}
});
