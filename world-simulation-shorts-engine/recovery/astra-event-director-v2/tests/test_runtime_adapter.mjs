import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {loadEventDirectorPlan,DIRECTOR_BINDINGS} from '../runtime_adapter.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),
 replay=JSON.parse(await readFile(path.join(ROOT,'reports/ORIGINAL_SOURCE_REPLAY.json'))),
 options={preparedFile:replay.preparedPath,normalizationFile:path.join(ROOT,'fixtures/NORMALIZED_SOURCE_REVIEW.json'),
  cameraProfileFile:path.join(ROOT,'fixtures/CAMERA_REVIEW_PROFILE.json'),cameraAdmissionFile:path.join(ROOT,'fixtures/CAMERA_ADMISSION.json')};
test('actual selected derived plan uses exact bytes and old native/legacy geometry, with every new consumer source-bound',async()=>{
 const plan=await loadEventDirectorPlan(options),request=JSON.parse(await readFile(options.normalizationFile));
 assert.equal(plan.derivedSceneSHA256,request.runtimeBindingManifest.actualDerivation.actualDerivedSceneSHA256);
 assert.equal(plan.document.productionV3.directorAdditionalFronts.length,1);
 assert.equal(plan.document.productionV3.directorAdditionalFronts[0].classification,'OBSERVED_ROK_FRONT');
 for(const url of Object.keys(DIRECTOR_BINDINGS))assert.ok(plan.serverConfig.bindings.some(x=>x.url===url));
 assert.equal(plan.serverConfig.runtimeConfig.astraEventDirector.productionEligible,false);
 assert.deepEqual(plan.document.legacyScenePlan,request.sourcePlan.legacyScenePlan);
 assert.equal(plan.scene.startFrame,0);assert.equal(plan.scene.endFrame,2400);await plan.assertSourceUnchanged();
});
test('a camera file changed after strict normalization is refused before opening a browser',async()=>{
 const folder=await mkdtemp('/workspace/astra-camera-tamper-');
 try{const file=path.join(folder,'CAMERA.json');await writeFile(file,(await readFile(options.cameraProfileFile))+' ');
  await assert.rejects(loadEventDirectorPlan({...options,cameraProfileFile:file}),/DIRECTOR_CAMERA_PROFILE_ADMISSION_SHA_REQUIRED/);
 }finally{await rm(folder,{recursive:true});}
});
test('a blocked production request cannot select the free source-review renderer',async()=>{
 const folder=await mkdtemp('/workspace/astra-normalizer-tamper-');
 try{const file=path.join(folder,'NORMALIZED.json'),value=JSON.parse(await readFile(options.normalizationFile));
  value.normalizedRequest.purpose='PRODUCTION';await writeFile(file,JSON.stringify(value));
  await assert.rejects(loadEventDirectorPlan({...options,normalizationFile:file}),/DIRECTOR_FREE_SOURCE_REVIEW_ONLY/);
 }finally{await rm(folder,{recursive:true});}
});
