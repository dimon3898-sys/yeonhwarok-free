/** Pure CPU contracts for the narrow production capture selector. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import path from 'node:path';
import {resolveQualityCapture,originalCaptureURL,qualityRuntimeURL,assertQualityCaptureReport,
 invalidateQualityCapture} from '../capture_quality.mjs';
const h='a'.repeat(64);
function report(){return {status:'CAPTURE_TECHNICAL_PASS',astraApplied:true,signature:'b'.repeat(64),
 activationSha256:'c'.repeat(64),astraProfileId:'VISUAL_QUALITY_UPGRADE_V1_F',
 runtime:{quality:{profile:'F',cameraSceneSha256:h,profileSha256:h,testOnly:false},evidence:{
 terrainPass:{version:'ASTRA_VALID_SUPPORT_FEATHER_V1',astra:{boundary:{enabled:true}}},
 territoryPass:{qualityTerritory:{expressionChanged:true}}}},
 frames:Array.from({length:150},(_,frame)=>({frame,diagnostic:{qualityActivation:{profile:'F',
 cameraSceneSha256:h,profileSha256:h,testOnly:false},terrain:{version:'ASTRA_VALID_SUPPORT_FEATHER_V1',
 astra:{boundary:{enabled:true}}},territory:{graphics:{qualityTerritory:{expressionChanged:true}}}}}))};}
test('official hook remaps only saved capture exact runtime edge',()=>{
 const next=(specifier,context)=>({url:'next:'+specifier,context});
 assert.deepEqual(resolveQualityCapture('./astra_runtime.mjs',{parentURL:originalCaptureURL},next),
  {url:qualityRuntimeURL,shortCircuit:true});
 for(const [specifier,parentURL]of [['./astra_runtime.mjs','file:///other/capture.mjs'],
  ['./evil.mjs',originalCaptureURL],['../astra-gpu-activation-v1/astra_runtime.mjs',originalCaptureURL]])
  assert.equal(resolveQualityCapture(specifier,{parentURL},next).url,'next:'+specifier);
});
test('integrated capture requires all 150 actual selected material and territory frames',()=>{
 assert.equal(assertQualityCaptureReport(report()),true);
 for(const edit of [r=>r.frames.pop(),r=>r.frames[40].diagnostic.qualityActivation.profile='A',
  r=>r.frames[40].diagnostic.qualityActivation.cameraSceneSha256='d'.repeat(64),
  r=>r.frames[40].diagnostic.qualityActivation.profileSha256='d'.repeat(64),
  r=>r.frames[40].diagnostic.qualityActivation.testOnly=true,
  r=>r.frames[40].diagnostic.terrain.astra.boundary.enabled=false,
  r=>r.frames[40].diagnostic.territory.graphics.qualityTerritory.expressionChanged=false]){
  const value=report();edit(value);assert.throws(()=>assertQualityCaptureReport(value));
 }
});
test('old ASTRA factories with cosmetic F metadata cannot pass quality capture',()=>{
 const value=report();value.runtime.evidence.terrainPass.version='ASTRA_SOURCE_MATERIAL_V1';
 assert.throws(()=>assertQualityCaptureReport(value),/QUALITY_BOUNDARY_FACTORY_REQUIRED/);
 const territory=report();delete territory.runtime.evidence.territoryPass.qualityTerritory;
 assert.throws(()=>assertQualityCaptureReport(territory));
 const frame=report();frame.frames[149].diagnostic.terrain.version='ASTRA_SOURCE_MATERIAL_V1';
 assert.throws(()=>assertQualityCaptureReport(frame));
});
test('failed quality validation atomically blocks only its fresh private capture',async()=>{
 const outputRoot=await mkdtemp('/workspace/test-only-quality-invalid-');
 try{
  const value=report(),directory=path.join(outputRoot,'captures',value.signature);
  await mkdir(directory,{recursive:true,mode:0o700});
  const body=Buffer.from(JSON.stringify(value)+'\n');await writeFile(path.join(directory,'REPORT.json'),body,{mode:0o600});
  await writeFile(path.join(directory,'CAPTURE_STATUS.json'),JSON.stringify({signature:value.signature,status:'IN_PROGRESS'}),{mode:0o600});
  const publicDir=path.join(directory,'public-review');await mkdir(publicDir,{mode:0o700});
  await writeFile(path.join(publicDir,'KEEP.mp4'),Buffer.from('unchanged existing result'));
  const other=path.join(outputRoot,'captures','f'.repeat(64));await mkdir(other,{mode:0o700});
  await writeFile(path.join(other,'REPORT.json'),body,{mode:0o600});
  value.frames[9].diagnostic.qualityActivation.profile='A';assert.throws(()=>assertQualityCaptureReport(value));
  await invalidateQualityCapture(value,{outputRoot});
  const saved=JSON.parse(await readFile(path.join(directory,'REPORT.json')));
  assert.equal(saved.status,'BLOCKED');assert.equal(saved.error,'QUALITY_CAPTURE_VALIDATION_FAILED');
  assert.equal(JSON.parse(await readFile(path.join(directory,'CAPTURE_STATUS.json'))).status,'BLOCKED');
  assert.equal(await readFile(path.join(publicDir,'KEEP.mp4'),'utf8'),'unchanged existing result');
  assert.deepEqual(await readFile(path.join(other,'REPORT.json')),body);
 }finally{await rm(outputRoot,{recursive:true,force:true});}
});
test('quality invalidation refuses a different activation identity',async()=>{
 const outputRoot=await mkdtemp('/workspace/test-only-quality-wrong-');
 try{
  const value=report(),directory=path.join(outputRoot,'captures',value.signature);await mkdir(directory,{recursive:true,mode:0o700});
  const original=JSON.stringify(value);await writeFile(path.join(directory,'REPORT.json'),original,{mode:0o600});
  value.activationSha256='d'.repeat(64);await assert.rejects(()=>invalidateQualityCapture(value,{outputRoot}));
  assert.equal(await readFile(path.join(directory,'REPORT.json'),'utf8'),original);
 }finally{await rm(outputRoot,{recursive:true,force:true});}
});
