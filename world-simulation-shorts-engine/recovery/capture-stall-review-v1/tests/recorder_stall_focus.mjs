/** New contract only: active frame/phase after one completed frame, no exception.
 * This does not replay the already-passed G1 crash, timeout or storage suites.
 * Baseline and candidate are copies; operational code is never modified.
 */
import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir, readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const here=path.dirname(fileURLToPath(import.meta.url));
const review=path.resolve(here,'..');
const candidate=path.join(review,'candidate');
const source=JSON.parse(await readFile(path.join(candidate,'SOURCE_SHA256.json'),'utf8'));
const outputArg=process.argv[2];
assert(outputArg,'Usage: node recorder_stall_focus.mjs fresh-output-directory');
const output=path.resolve(outputArg);
assert(output!==candidate&&!output.startsWith(candidate+path.sep));
await mkdir(output,{recursive:false,mode:0o700});
const execute=promisify(execFile),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const put=(file,value)=>writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
const result={schema:'WORLD_ENGINE_STALL_CONTEXT_FOCUS_V1',startedAt:new Date().toISOString(),
 status:'RUNNING',sourceCommit:source.sourceCommit,scope:'CPU_SYNTHETIC_NO_EXCEPTION_ACTIVE_FRAME_EXPORT',
 gpuExecuted:false,browserLaunched:false,renderExecuted:false,operationalCodeChanged:false,
 oldPassRerun:false,incidentCauseConfirmed:false,renderRecoveryPass:false,
 syntheticCase:{durationSeconds:10,totalFrames:300,renderedFrames:1,frameIndex:1,
  operationId:'DRAW',operationPhase:'START',firstFailure:null,frameNumbering:'ZERO_BASED'},
 limits:['Not an execution of incident studio-dd436342d68d518586dec4781daff497',
  'No browser crash, hardware stall, process kill, GPU, or permanent remote export exercised',
  'Synthetic cleanupVerified=true is a fixture, not proof of production cleanup',
  'Generated capture is not wired to the recorder by this candidate',
  'Existing firstFailure, private-storage, size-limit and cleanup-gate PASS suites are reused, not rerun'],
 variants:[],newFieldContracts:[]};

const python=String.raw`
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('stall_export_copy',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
job,dest=Path(sys.argv[2]),Path(sys.argv[3])
result=m.export_failure(job,dest)
response={'export':result,'sizeLimit':m.LIMIT}
if sys.argv[4]=='proposed':
    checkpoint=json.loads((job/'capture/CAPTURE_OPERATION_CHECKPOINT.json').read_text())
    hostile_phase=dict(checkpoint,operationPhase={'token':'NEW_FIELD_SYNTHETIC_SECRET'})
    beyond_frame=dict(checkpoint,frameIndex=300)
    response['newFields']={'invalidPhase':m.safe_operations(hostile_phase),
                          'outOfRangeFrame':m.safe_operations(beyond_frame)}
print(json.dumps(response,separators=(',',':')))
`;

try{
 for(const row of source.files){
  assert.equal(sha(await readFile(path.join(candidate,row.baselineCopy))),row.baselineSHA256);
  assert.equal(sha(await readFile(path.join(candidate,row.candidateCopy))),row.candidateSHA256);
 }
 for(const variant of ['baseline','proposed']){
  const root=path.join(output,variant);await mkdir(root,{mode:0o700});
  const job=path.join(root,'studio-'+(variant==='baseline'?'a':'b').repeat(32));
  const capture=path.join(job,'capture');await mkdir(capture,{recursive:true,mode:0o700});
  const recorderPath=path.join(candidate,variant,'backend/capture_operation_diagnostics.mjs');
  const {createRecorder}=await import(pathToFileURL(recorderPath).href);
  const recorder=createRecorder({outputRoot:capture,runId:path.basename(job),
   durationSeconds:10,totalFrames:300});
  // Only the new no-exception, first-frame-completed contract is composed here.
  assert.equal((await recorder.event({phase:'END',operationId:'PNG',frameIndex:0})).ok,true);
  assert.equal((await recorder.completeFrame(1)).ok,true);
  assert.equal((await recorder.event({phase:'START',operationId:'DRAW',frameIndex:1})).ok,true);
  const checkpointBytes=await readFile(path.join(capture,'CAPTURE_OPERATION_CHECKPOINT.json'));
  const checkpoint=JSON.parse(checkpointBytes);
  assert.equal(checkpoint.renderedFrames,1);assert.equal(checkpoint.frameIndex,1);
  assert.equal(checkpoint.operationId,'DRAW');assert.equal(checkpoint.firstFailure,null);
  assert.equal(checkpoint.totalFrames,300);assert(checkpointBytes.length<16384);
  await put(path.join(job,'LEASE_SUPERVISOR_RESULT.json'),{cleanupVerified:true});
  const exporter=path.join(candidate,variant,'controller/safe_capture_export.py');
  const {stdout}=await execute('python3',['-B','-c',python,exporter,job,path.join(root,'safe-export'),variant],
   {timeout:10000,maxBuffer:65536});
  const collected=JSON.parse(stdout);
  const wire=await readFile(path.join(root,'safe-export/CAPTURE_DIAGNOSTIC.json'));
  const retrieved=JSON.parse(wire),operations=retrieved.capture.operations;
  assert.deepEqual(retrieved,collected.export.diagnostic);
  assert.equal(sha(wire),collected.export.sha256);
  assert.equal(retrieved.capture.renderedFrames,1);
  assert.equal(operations.firstFailure,null);assert.equal(operations.operationId,'DRAW');
  assert.equal(operations.totalFrames,300);assert.equal(retrieved.missingEvidence.capture,true);
  assert(wire.length<collected.sizeLimit);
  if(variant==='baseline'){
   assert.equal(Object.hasOwn(checkpoint,'operationPhase'),false);
   assert.equal(Object.hasOwn(operations,'operationPhase'),false);
   assert.equal(Object.hasOwn(operations,'frameIndex'),false);
  }else{
   assert.equal(checkpoint.operationPhase,'START');assert.equal(operations.operationPhase,'START');
   assert.equal(operations.frameIndex,1);
   assert.equal(collected.newFields.invalidPhase.operationPhase,null);
   assert.equal(collected.newFields.invalidPhase.frameIndex,1);
   assert.equal(collected.newFields.outOfRangeFrame.operationPhase,'START');
   assert.equal(collected.newFields.outOfRangeFrame.frameIndex,null);
   assert(!JSON.stringify(collected.newFields).includes('NEW_FIELD_SYNTHETIC_SECRET'));
   result.newFieldContracts=[{field:'operationPhase',case:'non_string_sensitive_object',result:'NULL_NO_VALUE_DISCLOSURE'},
    {field:'frameIndex',case:'300_outside_zero_based_300_frame_scope',result:'NULL'}];
   await put(path.join(root,'NEW_FIELD_CONTRACTS.json'),collected.newFields);
  }
  result.variants.push({variant,status:variant==='baseline'?'EXPECTED_EXISTING_GAP_OBSERVED':'NEW_CONTRACT_PASS',
   checkpoint:{sha256:sha(checkpointBytes),bytes:checkpointBytes.length,operationId:checkpoint.operationId,
    operationPhase:checkpoint.operationPhase??null,frameIndex:checkpoint.frameIndex,renderedFrames:checkpoint.renderedFrames},
   safeExport:{sha256:sha(wire),bytes:wire.length,operationId:operations.operationId,
    operationPhase:operations.operationPhase??null,frameIndex:operations.frameIndex??null,
    hasOperationPhase:Object.hasOwn(operations,'operationPhase'),hasFrameIndex:Object.hasOwn(operations,'frameIndex')}});
 }
 result.status='CANDIDATE_CONTEXT_EXPORT_FOCUS_PASS';
}catch(error){
 result.status='FAIL';result.failure={name:error?.name??'Error',message:String(error?.message??error).slice(0,2000)};
 process.exitCode=1;
}finally{
 result.finishedAt=new Date().toISOString();await put(path.join(output,'RESULT.json'),result);
 const files=[];
 async function walk(dir){for(const entry of await readdir(dir,{withFileTypes:true})){
  const file=path.join(dir,entry.name);if(entry.isDirectory())await walk(file);else files.push(file);}}
 await walk(output);
 const sums=[];for(const file of files.sort())sums.push(sha(await readFile(file))+'  '+path.relative(output,file));
 await writeFile(path.join(output,'SHA256SUMS'),sums.join('\n')+'\n',{flag:'wx',mode:0o600});
 console.log(JSON.stringify(result));
}
