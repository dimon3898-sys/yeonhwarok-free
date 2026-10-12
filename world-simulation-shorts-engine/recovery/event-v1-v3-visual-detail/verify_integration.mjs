// Focused native integration before long regression/proof; no video or FINAL gate.
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
import {evaluateCameraDetailApproachFrame} from '../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';
import {openVisualRuntime,engine,json} from './visual_runtime.mjs';
const root=path.join(engine,'recovery/event-v1-v3-visual-detail');
const plan=await json(path.join(root,'fixtures/DETAIL_ADAPTER_PLAN.json'));
const report={schema:1,status:'STARTED',frames:[],sourceGeometryUnchanged:true,eventV2StyleUnchanged:true,
 surveyAdmissionPreserved:true,finalGateExecuted:false};
let session;
try{
 session=await openVisualRuntime();
 await session.page.evaluate(request=>window.visualDetail.initialize({targetFraming:request.targetFraming,
  mode:'VISUAL_DETAIL_ADMITTED',certificate:request.certificate}),plan.request);
 for(const frame of [0,26,47,59,60,90,119,135,164,209]){
  const scheduled=evaluateCameraDetailApproachFrame(plan,frame);
  const row=await session.page.evaluate(s=>window.visualDetail.capture({bounds:s.flatBounds,cameraLocked:s.cameraLocked,
   eventEnabled:s.eventEnabled,eventFrame:s.eventFrame,protect:s.eventEnabled,png:false}),scheduled);
  assert.equal(row.diagnostic.gpu.glError,0);
  assert.deepEqual(row.diagnostic.gpu.actualCamera.bounds,scheduled.flatBounds);
  assert.equal(row.diagnostic.admission.status,'LOCAL_NOT_ADMITTED');assert.equal(row.diagnostic.scale,'REGIONAL');
  if(!scheduled.eventEnabled){assert.equal(row.diagnostic.event.controls,null);assert.equal(row.diagnostic.event.line,null);assert.equal(row.diagnostic.event.metric,null);}
  else{
   assert.equal(row.protected_changed_pixels,0);assert.equal(row.marker_changed_pixels,0);assert.equal(row.outside_roi_changed_pixels,0);
   const e=row.diagnostic.event,old=session.approved.frames[scheduled.eventFrame];
   assert.equal(e.controls.lineFraction,old.lineFraction);assert.equal(e.controls.metricFraction,old.metricFraction);
   assert.deepEqual(e.eventStyle,old.eventStyle);assert.deepEqual(e.metricStyle,old.metricStyle);
   assert.equal(e.controls.metricValue,session.fixture.intent.metric.display_value);
  }
  if(frame===0){
   const original=await json(path.join(engine,'recovery/v5/evidence/runtime-diagnostic.json'));
   assert.equal(row.raw_rgba_sha256,original.frames[249].raw_rgba_sha256);
  }
  report.frames.push({frame,scheduled,...row});
 }
 assert.equal(session.errors.length,0);report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{await writeFile(path.join(root,'evidence/INTEGRATION_SMOKE.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});await session?.close();}
console.log(JSON.stringify({status:report.status,frames:report.frames.length,lockFrame:plan.detailLockFrame}));
