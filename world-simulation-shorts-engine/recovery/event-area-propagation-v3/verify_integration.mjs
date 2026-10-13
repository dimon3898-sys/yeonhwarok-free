import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {openAreaRuntime,root,sha} from './area_runtime.mjs';
const report={schema:1,status:'STARTED',frames:[],physicalSimulation:false,permanentGateExecuted:false};
await mkdir(path.join(root,'evidence/integration'),{recursive:true});
let session;
try{
 session=await openAreaRuntime();report.runtime=session.info;report.subject=session.fixture.subject;
 for(const frame of session.presentation.checkpoints.map(row=>row.frame)){
  const row=await session.page.evaluate(f=>window.areaProof.capture(f,{protect:true,png:true}),frame);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  assert.equal(row.diagnostic.glError,0);
  assert.equal(row.diagnostic.area.protection.protectedChangedPixels,0);
  assert.equal(row.diagnostic.area.protection.outsideRoiChangedPixels,0);
  if(frame<session.presentation.eventStartFrame)assert.equal(row.diagnostic.area.enabled,false);
  else{assert.equal(row.diagnostic.camera.cameraLocked,true);assert.equal(row.diagnostic.area.graphics.nativeStateRestored,true);
   assert.ok(row.diagnostic.area.graphics.propagationExclusionPolygonCount>0);}
  const file=String(frame).padStart(3,'0')+'.png';await writeFile(path.join(root,'evidence/integration',file),bytes);
  report.frames.push({...row,file,bytes:bytes.length});console.log(JSON.stringify({phase:'AREA_INTEGRATION',frame,state:row.diagnostic.state,status:'PASS'}));
 }
 const last=report.frames.at(-1),bounds=last.diagnostic.camera.camera.flatBounds;
 const admission=await session.page.evaluate(async({plan,bounds,sha256,byteLength,terrain})=>{
  const {compileAreaDataProfile,evaluateAreaVisualAdmission}=await import('/modules/area_visual_admission_v3.mjs');
  const d=window.areaProof.pipeline.diagnostic;
  return evaluateAreaVisualAdmission({areaPlan:plan,project:window.areaProof.pipeline.project,safeArea:[48,72,1032,1848],
   protectedGraphics:d.camera.protectedGraphics,currentCameraState:{bounds,output:[1080,1920]},
   semanticIntegrity:{sameGeography:true,sameObject:true,relationCorrect:true,geometryMeaningPreserved:true,metricMateriallyTrue:true},
   visualEvidence:{evidenceKind:'ACTUAL_NATIVE_RENDER',status:'VISUAL_WARNING',criticalCollisions:0,severeErrors:[],
    warnings:['Illustrative propagation/coast focus, not a measured inundation boundary or scientific timing'],
    render:{verified:true,sha256,byteLength,width:1080,height:1920,bounds,geometryBinding:plan.geometryBinding}},
   dataProfile:compileAreaDataProfile({areaPlan:plan,terrain,gis:[{source:'Existing Natural Earth 50m country polygons',absoluteAccuracyCertified:false}],surveyDetailStatus:'LOCAL_NOT_ADMITTED'})});
 },{plan:session.areaPlan,bounds,sha256:last.png_sha256,byteLength:last.bytes,
  terrain:{nativeTexelToScreenPixelRatio:[1080/((bounds[2]-bounds[0])*60),1920/((bounds[3]-bounds[1])*60)]}});
 assert.equal(admission.decision,'USE_CURRENT_VIEW');assert.equal(admission.productionEligible,true);assert.equal(admission.fullSweepSafe,true);
 await writeFile(path.join(root,'fixtures/AREA_VISUAL_ADMISSION.json'),JSON.stringify(admission,null,2)+'\n');
 report.admission=admission;report.camera={eventStartFrame:session.presentation.eventStartFrame,
  nativeStartFrame:session.presentation.cameraStartFrame,detailDecision:'USE_CURRENT_VIEW',cameraCoreUnchanged:true,lockBeforeArea:true};
 assert.equal(session.errors.length,0);report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;throw error;}
finally{await session?.close();await writeFile(path.join(root,'evidence/INTEGRATION.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({status:report.status,decision:report.admission?.decision,coverage:report.admission?.screenCoverage,frames:report.frames.length}));
