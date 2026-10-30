import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {analyzePresentationPrompt} from '../universal-presentation-v2/presentation_prompt.mjs';
import {validateRuntimeRequest} from '../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs';
import {validateExecutionPermit,canonicalJSON,sha,PROFILE} from '../codex-to-gcube-handoff-v1/backend/profile_contract.mjs';
import {createRecorder,attachPageDiagnostics} from '../codex-to-gcube-handoff-v1/backend/capture_operation_diagnostics.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const sample=JSON.parse(await fs.readFile(path.join(here,'GENERIC_CAMERA_TERRITORY_10S.json'),'utf8'));
// Source admission is an injected boundary: previous map/source PASS is reused,
// not rerun or asserted as a new source qualification or a GPU draw.
const qualified=async()=>({status:'PASS',regionEvidence:{contextCountryId:'COUNTRY_NAM',sourceId:'REUSED_SOURCE_TEST_BOUNDARY'},regionGateSHA256:'b'.repeat(64)});
const compile=opts=>analyzePresentationPrompt(structuredClone(sample),{qualifyRegion:qualified,...opts});
let analyzed;
function request(result){return{schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,
 sourceInputSHA256:'a'.repeat(64),segments:result.renderRequests.map(row=>Object.fromEntries(['sceneId','startFrame','endFrame','scene','region','presentation','inputTrace'].map(k=>[k,row[k]]))),transitions:result.transitionPlan};}
function seal(runtime,patch={}){
 const wire=canonicalJSON(runtime),now=Date.parse('2030-01-01T00:00:00Z');
 const plan={schema:'WORLD_ENGINE_NVIDIA_PRESENTATION_PLAN_V1',durationSeconds:10,totalFrames:300,fps:30,aspectRatio:'9:16',resolution:{width:1080,height:1920},audioSettings:{enabled:false,mode:'SILENT'},simulationType:'FICTIONAL',renderProfile:{profileId:PROFILE,backend:'vulkan',imageDigest:'sha256:'+'c'.repeat(64),sourceClosureSHA256:'d'.repeat(64)},runtime,runtimeWireJSON:wire,runtimeWireSHA256:sha(wire),sourceQualificationSHA256:'e'.repeat(64),...patch};
 const planWire=canonicalJSON(plan),approval={schema:'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1',approved:true,planSHA256:sha(planWire),imageDigest:plan.renderProfile.imageDigest,validUntil:'2030-01-01T01:00:00Z',maxWallSeconds:900,maxRetries:0,maxCostAmount:'1',currency:'USD',gpuHourlyRate:'1'};
 return{plan,planWire,approval,packageWire:wire,expectedPlanSHA256:sha(planWire),expectedPackageSHA256:sha(wire),now};
}

test('new10: actual V2 compiler accepts explicit two-event 300-frame opt-in',async()=>{
 analyzed=await compile({allowTenSecondStudioSample:true});
 assert.equal(sample.schema,'WORLD_ENGINE_PRESENTATION_PROMPT_V2');
 assert.equal(analyzed.status,'PASS',JSON.stringify(analyzed.issues));
 assert.equal(analyzed.totalFrames,300);
 assert.deepEqual(analyzed.renderRequests.map(r=>[r.startFrame,r.endFrame]),[[0,150],[150,300]]);
 assert.equal(analyzed.renderRequests.length,2);
 assert.ok(analyzed.renderRequests.every(r=>r.scene.source_notes.some(s=>s.verification_status==='SYNTHETIC_TEST')));
});
test('new10: opt-in does not widen the unchanged FREE limit',async()=>{
 const denied=await compile({});
 assert.notEqual(denied.status,'PASS');
 assert.ok(denied.issues.some(x=>x.code==='BOUNDED_COMPOSITE_PREVIEW_LIMIT'));
 const eighty=structuredClone(sample);eighty.data.durationSeconds=80;eighty.prompt=eighty.prompt.replace('10초','80초');
 const blocked=await analyzePresentationPrompt(eighty,{qualifyRegion:qualified,allowTenSecondStudioSample:true});
 assert.notEqual(blocked.status,'PASS');
});
test('new10: both capture validators require the explicit 10/300 pair',async()=>{
 const runtime=request(analyzed);assert.equal(validateRuntimeRequest(runtime),true);
 const target=path.join(here,'../codex-to-gcube-handoff-v1/.ten-second-installed-capture-test.mjs');
 await fs.copyFile(path.join(here,'../capture-page-evaluation-evidence-v1/candidate_capture_vulkan.mjs'),target);
 try{const installed=await import(pathToFileURL(target));assert.equal(installed.validateRuntimeRequest(runtime),true);
  for(const mutate of [r=>delete r.durationSeconds,r=>r.totalFrames=299,r=>r.durationSeconds=80,r=>r.segments[1].startFrame=149]){
   const bad=structuredClone(runtime);mutate(bad);assert.throws(()=>installed.validateRuntimeRequest(bad));assert.throws(()=>validateRuntimeRequest(bad));
  }
 }finally{await fs.unlink(target);}
});
test('new10: frame indices cover 0..299 once with exact scene-local timing',()=>{
 const seen=[];
 for(let frame=0;frame<300;frame++){
  const segment=analyzed.renderRequests.find(r=>frame>=r.startFrame&&frame<r.endFrame);
  assert.ok(segment);const local=frame-segment.startFrame;assert.ok(local>=0&&local<segment.scene.timing.total_frames);seen.push(frame);
 }
 assert.deepEqual(seen,Array.from({length:300},(_,i)=>i));
 assert.deepEqual(analyzed.transitionPlan,[{type:'CUT',frame:150}]);
 for(const row of analyzed.renderRequests){
  assert.equal(row.scene.timing.fps,30);assert.equal(row.scene.timing.total_frames,150);
  const keys=row.presentation.camera.keyframes;assert.equal(keys[0].frame,0);assert.equal(keys.at(-1).frame,149);
  assert.ok(keys.every(k=>k.frame>=0&&k.frame<150));
 }
});
test('new10: exact approval wire remains mandatory and wall time stays capped600',()=>{
 const permit=seal(request(analyzed));const valid=validateExecutionPermit(permit);
 assert.equal(valid.maxWallSeconds,600);assert.equal(valid.maxRetries,0);
 assert.throws(()=>validateExecutionPermit({...permit,approval:{...permit.approval,approved:false}}));
 assert.throws(()=>validateExecutionPermit({...permit,packageWire:permit.packageWire+' '}));
 assert.throws(()=>validateExecutionPermit({...permit,now:Date.parse('2031-01-01T00:00:00Z')}));
 assert.throws(()=>validateExecutionPermit(seal(request(analyzed),{durationSeconds:6})));
 assert.throws(()=>validateExecutionPermit({...permit,approval:{...permit.approval,maxCostAmount:'0.00001'}}));
});
test('new10: diagnostic recorder and browser bridge preserve frame299 without leaking errors',async()=>{
 const writes=[],recorder=createRecorder({outputRoot:'/unused-test-boundary',durationSeconds:10,totalFrames:300,write:async(_,value)=>writes.push(value)});
 await recorder.completeFrame(300);await recorder.event({operationId:'DRAW',phase:'FAIL',frameIndex:299,failure:{operationId:'DRAW',sourceId:'CAPTURE_ADAPTER',frameIndex:299,errorCode:'UP2_FRAME_GL_ERROR',exceptionType:'Error',message:'PRIVATE_RAW_ERROR'}});
 const snapshot=recorder.snapshot();assert.equal(snapshot.totalFrames,300);assert.equal(snapshot.renderedFrames,300);assert.equal(snapshot.firstFailure.frameIndex,299);
 assert.ok(!JSON.stringify(writes).includes('PRIVATE_RAW_ERROR'));
 let browserConfig;await attachPageDiagnostics({exposeFunction:async()=>{},evaluate:async(_,config)=>browserConfig=config},recorder);
 assert.equal(browserConfig.durationSeconds,10);assert.equal(browserConfig.totalFrames,300);
 const six=createRecorder({outputRoot:'/unused-test-boundary',write:async()=>{}}).snapshot();
 assert.ok(!('durationSeconds'in six));assert.ok(!('totalFrames'in six));
 assert.throws(()=>createRecorder({durationSeconds:10,totalFrames:180}));
});
test('new10: owner consent displays server-bound 10s and rejects old missing metadata',async()=>{
 const source=await fs.readFile(path.join(here,'../codex-to-gcube-handoff-v1/mobile/app.js'),'utf8');
 const heading={},details={},text={nodeType:3,textContent:''},elements={prompt:{value:JSON.stringify(sample)},consent:{parentNode:{childNodes:[text]}}};
 const state={requestedDuration:6},document={title:'',querySelector:q=>q==='header h1'?heading:details};
 const context={state,document,$:id=>elements[id],TextEncoder,JSON,fail:code=>{throw Error(code);}};
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('function body()'),source.indexOf('function approvedBudget')),context);
 vm.runInContext(source.slice(source.indexOf('function drawDuration('),source.indexOf('function drawPreflight(')),context);
 const input=vm.runInContext('body()',context);assert.equal(input.schema,'WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1');assert.equal(state.requestedDuration,10);
 assert.equal(vm.runInContext('drawDuration({})',context),false);
 assert.equal(vm.runInContext('drawDuration({durationSeconds:10,totalFrames:180})',context),false);
 assert.equal(vm.runInContext('drawDuration({durationSeconds:10,totalFrames:300})',context),true);assert.match(text.textContent,/10초 영상/);assert.match(details.textContent,/300프레임/);
 state.requestedDuration=6;assert.equal(vm.runInContext('drawDuration({})',context),true);assert.equal(heading.textContent,'6초 GPU 검수');assert.equal(text.textContent,'표시된 승인 한도 안에서 6초 영상 1개를 제작합니다.');
});
test('new10: source-admission failure stays blocked; labels remain metadata only',async()=>{
 const denied=await compile({allowTenSecondStudioSample:true,qualifyRegion:async()=>({status:'INVALID',issues:[{status:'INVALID',code:'TEST_EXISTING_SOURCE_GATE_BLOCKED',field:'$.region'}]})});
 assert.notEqual(denied.status,'PASS');assert.equal(denied.renderRequests.length,0);
 assert.ok(analyzed.renderRequests.every(r=>r.displayMetadataOnly.includes('locations[].label')));
 const labeled=structuredClone(sample);labeled.prompt+=' 라벨을 표시해줘.';
 const unsupported=await analyzePresentationPrompt(labeled,{qualifyRegion:qualified,allowTenSecondStudioSample:true});
 assert.notEqual(unsupported.status,'PASS');assert.ok(unsupported.issues.some(x=>x.code==='UNSUPPORTED_VISIBLE_LABELS'));
});
test('new6compat: default serialized compiler output matches pinned baseline on a new fixture',async()=>{
 const input=JSON.parse(await fs.readFile(path.join(here,'fixtures/DEFAULT_6S_INPUT.json'),'utf8'));
 const expected=JSON.parse(await fs.readFile(path.join(here,'fixtures/DEFAULT_6S_EXPECTED.json'),'utf8'));
 const output=await analyzePresentationPrompt(input,{qualifyRegion:qualified});
 assert.equal(output.status,'PASS');assert.equal(output.totalFrames,180);
 assert.equal(sha(JSON.stringify(output)),expected.expectedSerializedResultSHA256);
});
