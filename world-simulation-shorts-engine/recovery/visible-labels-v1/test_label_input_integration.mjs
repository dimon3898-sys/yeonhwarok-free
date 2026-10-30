/** New label-input connection only; previous duration/map/GPU suites are skipped. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {analyzePresentationPrompt} from '../universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest} from '../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const input=JSON.parse(await fs.readFile(path.join(HERE,'GENERIC_LABELS_10S.json'),'utf8'));
// Reuse the source-admission boundary; this task does not repeat prior map PASS.
const source=async()=>({status:'PASS',regionEvidence:{contextCountryId:'COUNTRY_NAM',sourceId:'EXISTING_SOURCE_BOUNDARY_FIXTURE'},regionGateSHA256:'b'.repeat(64)});
let result;
test('new-label-input01 actual V2 sample compiles explicit visible-label consumers for both events',async()=>{
 result=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true,qualifyRegion:source});
 assert.equal(result.status,'PASS',JSON.stringify(result.issues));
 assert.equal(result.totalFrames,300);assert.equal(result.renderRequests.length,2);
 assert.deepEqual(result.renderRequests.map(r=>r.presentation.labels.items.map(l=>l.role)),[['COUNTRY','EVENT','NUMERIC'],['COUNTRY','EVENT','NUMERIC']]);
 assert.ok(result.inputDerivations.some(d=>d.origin==='EXPLICIT_LABEL_CONSUMER_WITH_SUPPLIED_LOCATION_EVENT_AND_FRAME_BINDINGS'));
 for(const row of result.renderRequests){
  assert.ok(row.scene.source_notes.some(s=>s.verification_status==='SYNTHETIC_TEST'));
  for(const label of row.presentation.labels.items){
   assert.deepEqual(label.anchor,row.scene.locations.find(l=>l.id===label.locationId).anchor);
   if(label.eventId){const event=row.presentation.highlights.find(h=>h.id===label.eventId);assert.equal(event.locationId,label.locationId);assert.ok(label.startFrame>=event.startFrame&&label.endFrame<=event.endFrame);}
  }
 }
 await fs.mkdir(path.join(HERE,'evidence'),{recursive:true});
 await fs.writeFile(path.join(HERE,'evidence/COMPILED_LABEL_PREVIEW_INPUT.json'),JSON.stringify({schema:'WORLD_ENGINE_CPU_LABEL_PREVIEW_INPUT_V1',scope:'ACTUAL_V2_COMPILED_LABEL_METADATA_WITH_SOURCE_ADMISSION_TEST_BOUNDARY',cpuOnly:true,gpuExecuted:false,sourceAdmissionReexecuted:false,region:input.region,scenes:result.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,labels:r.presentation.labels,highlights:r.presentation.highlights,camera:r.presentation.camera,locations:r.scene.locations,geometry:r.scene.geometries,sourceNotes:r.scene.source_notes}))},null,2)+'\n');
});
test('new-label-input02 adding label metadata does not change the existing scene geometry or event timing',async()=>{
 const noLabels=structuredClone(input);delete noLabels.presentation.labels;delete noLabels.presentation.sceneOverrides['synthetic-event-b'].labels;
 noLabels.prompt=noLabels.prompt.slice(0,noLabels.prompt.indexOf(' 제공한 나라 이름표'));
 const baseline=await analyzePresentationPrompt(noLabels,{allowTenSecondStudioSample:true,qualifyRegion:source});
 assert.equal(baseline.status,'PASS',JSON.stringify(baseline.issues));
 for(let i=0;i<2;i++){
  assert.deepEqual(result.renderRequests[i].scene,baseline.renderRequests[i].scene);
  assert.deepEqual(result.renderRequests[i].enginePlan,baseline.renderRequests[i].enginePlan);
  assert.deepEqual(result.renderRequests[i].presentation.camera,baseline.renderRequests[i].presentation.camera);
  assert.ok(!('labels'in baseline.renderRequests[i].presentation));
 }
});
test('new-label-input03 optional labels stay inside the preserved 10s capture request contract',()=>{
 const runtime={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:'a'.repeat(64),segments:result.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,scene:r.scene,region:r.region,presentation:r.presentation})),transitions:result.transitionPlan};
 assert.equal(validateRuntimeRequest(runtime),true);
 assert.deepEqual(runtime.segments.map(s=>[s.startFrame,s.endFrame]),[[0,150],[150,300]]);
 assert.equal(runtime.segments.at(-1).endFrame-1,299);
});
test('new-label-input04 source rejection cannot be bypassed by the visible-label option',async()=>{
 const blocked=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true,qualifyRegion:async()=>({status:'INVALID',issues:[{status:'INVALID',code:'NEW_LABEL_SOURCE_REJECTED',field:'$.region'}]})});
 assert.notEqual(blocked.status,'PASS');assert.equal(blocked.renderRequests.length,0);
});
