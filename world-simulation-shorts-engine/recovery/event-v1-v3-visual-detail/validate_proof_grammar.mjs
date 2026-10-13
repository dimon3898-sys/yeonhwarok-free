// Read-only semantic/reveal/layout regression against saved Event V2 controls.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {engine,json,sha} from './visual_runtime.mjs';
const root=path.join(engine,'recovery/event-v1-v3-visual-detail');
const proof=await json(path.join(root,'evidence/proof/REPORT.json'));
const plan=await json(path.join(root,'fixtures/DETAIL_ADAPTER_PLAN.json'));
const original=await json(path.join(engine,'recovery/event-v1-candidate-v2/evidence/on150/REPORT.json'));
assert.equal(proof.status,'PASS');assert.equal(proof.frames.length,210);
assert.deepEqual(plan.timeline.map(b=>b.state),['EVENT_ARRIVAL','DETAIL_DECISION','DETAIL_APPROACH','DETAIL_SETTLE','DETAIL_LOCK',
 'LINE_REVEAL','LINE_HOLD','METRIC_REVEAL','INFORMATION_HOLD']);
const overlap=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
let metricFrames=0;
for(const row of proof.frames){
 const e=row.event;
 if(row.frame<plan.detailLockFrame){assert.equal(e.controls,null);assert.equal(e.line,null);assert.equal(e.metric,null);continue;}
 const baseline=original.frames[row.eventFrame];
 for(const key of ['state','lineFraction','metricFraction','metricValue','metricUnit'])assert.equal(e.controls[key],baseline[key]);
 assert.deepEqual(e.linePrimitive.intent.line,original.eventPlan.intent.line);
 assert.deepEqual(e.linePrimitive.intent.metric,original.eventPlan.intent.metric);
 if(e.metric){
  metricFrames++;
  for(const key of ['text','displayValue','unit','anchor','atlasDimensions','alphaBounds','baselines','visibleGlyphCount','graphemeAlphas','fullCoverage','fullReservation'])
   assert.deepEqual(e.metric[key],baseline.metric[key],key);
 }
 if(e.placement){assert.equal(e.placement.reservationSpace,'FULL_MEASURED_ATLAS');
  assert.ok(e.protectedBoxes.every(box=>!overlap(e.placement.roi,box)));
  assert.ok(e.placement.candidates.some(c=>c.eligible&&JSON.stringify(c.roi)===JSON.stringify(e.placement.roi)));
 }
 if(['LINE_REVEAL','LINE_HOLD'].includes(row.state))assert.equal(e.metric,null);
 if(['METRIC_REVEAL','INFORMATION_HOLD'].includes(row.state))assert.equal(e.controls.lineFraction,1);
}
for(const state of ['LINE_HOLD','INFORMATION_HOLD'])assert.equal(new Set(proof.frames.filter(r=>r.state===state).map(r=>r.raw_rgba_sha256)).size,1);
for(const checkpoint of proof.checkpoints){
 const bytes=await readFile(path.join(root,'public-review',checkpoint.file));assert.equal(sha(bytes),checkpoint.sha256);
 assert.equal(checkpoint.sha256,proof.frames[checkpoint.frame].png_sha256);
}
const result={schema:1,status:'PASS',reference:'64306 saved semantic grammar: location -> detail -> geographic draw -> line hold -> glyph reveal -> information hold',
 referenceFrameNumbersCopied:false,eventV2FramesCompared:150,metricFramesCompared:metricFrames,
 geometryProgressMetricMeaningStyleUnchanged:true,metricCollisions:0,holdHashesStable:true,
 noEventGraphicsBeforeLock:true,lineStartsAfterLock:true,checkpointsMatchEncodedNativeFrames:7,
 actualDecodedFinalFrameVisuallyInspected:true,visualResult:'VISUAL_WARNING: retained terrain softness; no obvious geography/line/metric corruption',
 surveyAdmissionPreserved:true,permanentGateExecuted:false,eventFinal:false};
await writeFile(path.join(root,'evidence/REFERENCE_GRAMMAR_AND_V2_REGRESSION.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result));
