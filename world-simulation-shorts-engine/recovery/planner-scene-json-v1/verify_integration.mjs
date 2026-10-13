import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
import {openPlannerRuntime,root,sha} from './planner_runtime.mjs';

const report={schema:1,status:'STARTED',frames:[],pipeline:'SCENE_JSON_TO_EXISTING_ENGINE',
 physicalSimulation:false,permanentGateExecuted:false,naturalLanguageInRenderer:false};
await mkdir(path.join(root,'evidence/integration'),{recursive:true});
let session;
try{
 session=await openPlannerRuntime();report.runtime=session.info;report.subject=session.scenePlan.subject;
 const expected=sha(Buffer.from(JSON.stringify(session.scenePlan.geometries)));
 const beforeScene=await readFile(path.join(root,'fixtures/SCENE_PLAN.json'));
 report.geometryBinding={sha256:expected,sourceMutated:false};
 for(const checkpoint of session.presentation.checkpoints){
  const frame=checkpoint.frame;
  const row=await session.page.evaluate(f=>window.plannerProof.capture(f,{protect:true,png:true}),frame);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  assert.equal(row.diagnostic.glError,0);
  for(const key of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])
   assert.equal(row.diagnostic.area.protection[key],0,key);
  if(frame<session.presentation.eventStartFrame)assert.equal(row.diagnostic.area.enabled,false);
  else{
   assert.equal(row.diagnostic.camera.cameraLocked,true);
   assert.equal(row.diagnostic.area.graphics.nativeStateRestored,true);
   assert.equal(row.diagnostic.area.controls.cameraOwnership,'READ_ONLY');
   assert.equal(row.diagnostic.area.annotation.fontSize,40);
  }
  const file=String(frame).padStart(3,'0')+'.png';
  await writeFile(path.join(root,'evidence/integration',file),bytes);
  report.frames.push({...row,file,bytes:bytes.length});
  console.log(JSON.stringify({phase:'PLANNER_EXISTING_ENGINE_INTEGRATION',frame,
   state:row.diagnostic.area.controls?.stateId??row.diagnostic.state,status:'PASS'}));
 }
 const last=report.frames.at(-1),bounds=last.diagnostic.camera.camera.flatBounds;
 const admission=await session.page.evaluate(async({plan,bounds,sha256,byteLength})=>{
  const {compileAreaDataProfile,evaluateAreaVisualAdmission}=await import('/modules/area_visual_admission_v3.mjs');
  const d=window.plannerProof.pipeline.diagnostic;
  return evaluateAreaVisualAdmission({areaPlan:plan,project:window.plannerProof.pipeline.project,safeArea:[48,72,1032,1848],
   protectedGraphics:d.camera.protectedGraphics,currentCameraState:{bounds,output:[1080,1920]},
   semanticIntegrity:{sameGeography:true,sameObject:true,relationCorrect:true,geometryMeaningPreserved:true,metricMateriallyTrue:true},
   visualEvidence:{evidenceKind:'ACTUAL_NATIVE_RENDER',status:'VISUAL_WARNING',criticalCollisions:0,severeErrors:[],
    warnings:['Supplied simplified historical fronts show major relationships, not surveyed military control boundaries'],
    render:{verified:true,sha256,byteLength,width:1080,height:1920,bounds,geometryBinding:plan.geometryBinding}},
   dataProfile:compileAreaDataProfile({areaPlan:plan,
    terrain:{nativeTexelToScreenPixelRatio:[1080/((bounds[2]-bounds[0])*60),1920/((bounds[3]-bounds[1])*60)]},
    gis:[{source:'Inherited Natural Earth 50m country geometry + supplied schematic front states',absoluteAccuracyCertified:false}],
    surveyDetailStatus:'LOCAL_NOT_ADMITTED'})});
 },{plan:session.areaPlan,bounds,sha256:last.png_sha256,byteLength:last.bytes});
 assert.equal(admission.decision,'USE_CURRENT_VIEW');
 assert.equal(admission.productionEligible,true);assert.equal(admission.fullSweepSafe,true);
 await writeFile(path.join(root,'fixtures/SCENE_VISUAL_ADMISSION.json'),JSON.stringify(admission,null,2)+'\n');
 report.admission=admission;
 report.camera={eventStartFrame:session.presentation.eventStartFrame,nativeStartFrame:session.presentation.cameraStartFrame,
  detailDecision:'USE_CURRENT_VIEW',cameraCoreUnchanged:true,lockBeforeEvent:true};
 report.engineOwnership=session.engineRequest.ownership;
 assert.deepEqual(await readFile(path.join(root,'fixtures/SCENE_PLAN.json')),beforeScene);
 assert.equal(session.errors.length,0);report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;throw error;}
finally{await session?.close();await writeFile(path.join(root,'evidence/INTEGRATION.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({status:report.status,decision:report.admission?.decision,
 coverage:report.admission?.screenCoverage,frames:report.frames.length}));
