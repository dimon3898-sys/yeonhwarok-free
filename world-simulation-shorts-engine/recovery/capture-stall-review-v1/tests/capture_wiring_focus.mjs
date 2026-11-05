/** CPU-only contract for newly connected operation boundaries. No browser/GPU. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash,webcrypto} from 'node:crypto';
import {EventEmitter,once} from 'node:events';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import {createRecorder,initializeBrowserDiagnostics,SCHEMA,PUBLIC_CODES,OPERATIONS,SOURCES,EXCEPTIONS}
 from '../../codex-to-gcube-handoff-v1/backend/capture_operation_diagnostics.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const recovery=path.resolve(here,'../..');
const [baselineArg,outputArg]=process.argv.slice(2);
assert(baselineArg&&outputArg,'Usage: node capture_wiring_focus.mjs original-generated-capture fresh-output');
const output=path.resolve(outputArg);await mkdir(output,{recursive:false,mode:0o700});
const sourceFile=path.join(recovery,'codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs');
const source=await readFile(sourceFile,'utf8'),baseline=await readFile(baselineArg,'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
const save=(file,value)=>writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
const plain=value=>JSON.parse(JSON.stringify(value));
const frameCallback=text=>{
 const start=text.indexOf('const capture=await page.evaluate(async frame=>{');
 assert(start>=0);const first=start+'const capture=await page.evaluate('.length;
 const end=text.indexOf('},frame);diagnosticStage=null;diagnosticFrame=null;',first);
 assert(end>first);return text.slice(first,end+1);
};
const uniqueLine=(text,prefix)=>{const rows=text.split('\n').filter(line=>line.trimStart().startsWith(prefix));assert.equal(rows.length,1);return rows[0].trim();};
const pending=new Promise(()=>{}),live=[];
const result={schema:'WORLD_ENGINE_CAPTURE_WIRING_FOCUS_V1',status:'RUNNING',startedAt:new Date().toISOString(),
 sourceSHA256:sha(source),baselineSHA256:sha(baseline),scope:'NEW_OPERATION_WIRING_ONLY',
 gpuExecuted:false,browserLaunched:false,renderExecuted:false,oldPassRerun:false,
 incidentCauseConfirmed:false,renderRecoveryPass:false,cases:[],staticPreservation:[],
 limits:['VM executes the real changed frame callback against a mock runtime, not pixels or a browser',
 'Paused START callbacks model a wait boundary, not a reproduced GPU hang',
 'Private atomic checkpoint only; durable remote retrieval and forced-container-stop survival are not tested here',
 'Additional per-operation checkpoint fsync/CDP overhead requires a separately approved GPU run']};

async function setup(name,{pause=null,errorOperation=null}={}){
 const root=path.join(output,name);await mkdir(root,{mode:0o700});
 const recorder=createRecorder({outputRoot:root,runId:'studio-'+('c'.repeat(32)),durationSeconds:10,totalFrames:300});
 let ready;const paused=new Promise(resolve=>{ready=resolve;});
 const events=[],nativeCalls=[],pixels=new Uint8Array([20,30,40,255,0,0,0,255]);
 const runtime={
  evidence:{backend:'MOCK_GPU_NOT_EXECUTED'},dispose(){},
  drawFrame(frame){if(errorOperation==='DRAW')throw Error('UP2_FRAME_GL_ERROR');return{frame,glError:0};},
  readPixels(){if(errorOperation==='READBACK')throw Error('UP2_FRAME_GL_ERROR');return pixels;},
  readBasePixels(){return pixels;},png(){return'data:image/png;base64,ZmFrZS1waXhlbHM=';}
 };
 const window={payload:{segments:[{startFrame:0,endFrame:150},{startFrame:150,endFrame:300}]},currentSegment:0,runtime,
  async createRuntime({diagnostics}){nativeCalls.push({kind:'runtime',diagnostics:!!diagnostics});
   if(diagnostics)await diagnostics.run('WEBGL_CONTEXT',()=>null,{sourceId:'PRESENTATION_RUNTIME'});return runtime;},
  async __weCaptureCheckpoint(event){const saved=await recorder.event(event);events.push(plain(event));
   if(event.phase==='START'&&event.frameIndex===1&&event.operationId===pause){ready();return pending;}
   return saved;}};
 const context=vm.createContext({window,crypto:webcrypto,Uint8Array,Error,Number,Object,
  document:{createElement:()=>({}),body:{replaceChildren(){}}},
  async __nativeGuardMock(options){nativeCalls.push({kind:'guard',frameArgument:options.frame??null,localDrawFrame:0});
   if(options.diagnostics)await options.diagnostics.run('DRAW',()=>runtime.drawFrame(0),{sourceId:'NATIVE_GUARD',frame:0});
   else runtime.drawFrame(0);return{mock:true,initialFrame:0};}});
 vm.runInContext('('+initializeBrowserDiagnostics.toString()+')',context)({schema:SCHEMA,codes:PUBLIC_CODES,
  operations:OPERATIONS,sources:SOURCES,exceptions:EXCEPTIONS,durationSeconds:10,totalFrames:300});
 const compile=text=>{const callback=frameCallback(text),needle="await import('/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs')";
  assert.equal(callback.split(needle).length,2);return vm.runInContext('('+callback.replace(needle,'({runThreeNativeDraws:__nativeGuardMock})')+')',context);};
 return{root,recorder,events,nativeCalls,context,paused,ready,current:compile(source),original:compile(baseline)};
}

try{
 // Scope preservation is a diff guard, not a replay of historical rendering PASS.
 assert.equal(uniqueLine(source,"encoder=spawn('ffmpeg'"),uniqueLine(baseline,"encoder=spawn('ffmpeg'"));
 assert.equal(uniqueLine(source,'service=await makeLoopback'),uniqueLine(baseline,'service=await makeLoopback'));
 assert.equal(source.slice(source.indexOf('finally{encoder?.kill')),baseline.slice(baseline.indexOf('finally{encoder?.kill')));
 assert(!source.includes('evaluateDiagnosed('));
 result.staticPreservation=['UNCHANGED_BROWSER_LAUNCH_LINE','UNCHANGED_FFMPEG_LAUNCH_LINE',
  'UNCHANGED_CLEANUP_AND_FINAL_RECEIPT_PATH','EXISTING_PAGE_EVALUATE_AND_SUPERVISOR_DEADLINE_RETAINED'];

 const normal=await setup('normal');
 for(const frame of [0,1])assert.deepEqual(plain(await normal.current(frame)),plain(await normal.original(frame)));
 assert.deepEqual(normal.events.filter(e=>e.frameIndex===1).map(e=>[e.operationId,e.phase]),
  ['DRAW','READBACK','PROOF_VALIDATION','PNG'].flatMap(op=>[[op,'START'],[op,'END']]));
 result.cases.push({case:'unchanged_frame_callback_result',frames:[0,1],status:'PASS'});

 const segmentOriginal=await setup('segment-original'),segmentCurrent=await setup('segment-current');
 assert.deepEqual(plain(await segmentCurrent.current(150)),plain(await segmentOriginal.original(150)));
 assert.deepEqual(segmentCurrent.nativeCalls,[{kind:'runtime',diagnostics:true},{kind:'guard',frameArgument:null,localDrawFrame:0}]);
 const subStages=segmentCurrent.events.filter(e=>['PRESENTATION_RUNTIME','NATIVE_GUARD'].includes(e.sourceId));
 assert(subStages.length>0);assert(subStages.every(e=>e.frameIndex===150));
 assert(subStages.some(e=>e.sourceId==='PRESENTATION_RUNTIME'&&e.operationId==='WEBGL_CONTEXT'));
 assert(subStages.some(e=>e.sourceId==='NATIVE_GUARD'&&e.operationId==='DRAW'));
 result.cases.push({case:'existing_native_hooks_global_frame_context',globalFrame:150,nativeLocalDrawFrame:0,
  nativeFrameArgumentChanged:false,dependency:'NATIVE_GUARD_IMPORT_MOCKED',status:'PASS'});

 for(const operation of ['DRAW','READBACK','PROOF_VALIDATION','PNG']){
  const sample=await setup('pause-'+operation.toLowerCase(),{pause:operation});
  await sample.current(0);assert.equal((await sample.recorder.completeFrame(1)).ok,true);
  const call=sample.current(1);live.push(call);call.catch(()=>{});
  // A test-only deadline fails this mock if its new checkpoint boundary is absent.
  let timer;try{await Promise.race([sample.paused,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('NEW_BOUNDARY_NOT_REACHED')),3000);})]);}finally{clearTimeout(timer);}
  const bytes=await readFile(path.join(sample.root,'CAPTURE_OPERATION_CHECKPOINT.json'));
  const checkpoint=JSON.parse(bytes);
  assert.equal(checkpoint.operationId,operation);assert.equal(checkpoint.operationPhase,'START');
  assert.equal(checkpoint.frameIndex,1);assert.equal(checkpoint.renderedFrames,1);assert.equal(checkpoint.firstFailure,null);
  result.cases.push({case:'paused_browser_boundary',operation,frameIndex:1,renderedFrames:1,status:'PASS',checkpointSHA256:sha(bytes)});
 }

 const errorCase=await setup('domain-error',{errorOperation:'READBACK'});
 let oldMessage,newMessage;
 try{await errorCase.original(1);}catch(error){oldMessage=error.message;}
 try{await errorCase.current(1);}catch(error){newMessage=error.message;}
 assert.equal(oldMessage,'UP2_FRAME_GL_ERROR');assert.equal(newMessage,oldMessage);
 const firstFailure=errorCase.recorder.snapshot().firstFailure;
 assert.equal(firstFailure.errorCode,oldMessage);assert.equal(firstFailure.operationId,'READBACK');assert.equal(firstFailure.frameIndex,1);
 result.cases.push({case:'original_domain_exception_preserved',message:newMessage,operation:firstFailure.operationId,status:'PASS'});

 const encoder=await setup('encoder-boundary');let writes=0,ready;
 const reached=new Promise(resolve=>{ready=resolve;}),stdin=new EventEmitter();
 stdin.write=()=>{writes++;if(writes===1)queueMicrotask(()=>stdin.emit('drain'));return false;};
 const transferLine=uniqueLine(source,'if(probeFrames||checkpoints.has(frame))');
 const transfer=transferLine.slice(transferLine.indexOf('if(encoder){'));
 const progress=uniqueLine(source,'receipt.renderedFrames++;');
 const context=vm.createContext({encoder:{exitCode:null,stdin},encoderExit:pending,once,
  check:(value,code)=>{if(!value)throw Error(code);},operationRecorder:encoder.recorder,receipt:{renderedFrames:0},request:{totalFrames:300},
  process:{stdout:{write(){return true;}}},
  async recordOperation(event){const saved=await encoder.recorder.event(event);assert.equal(saved.ok,true);if(event.frameIndex===1&&event.phase==='START'&&event.operationId==='ENCODER_DRAIN')ready();}});
 const send=vm.runInContext('(async(png,frame)=>{'+transfer+'\n'+progress+'})',context);
 await send(Buffer.from('fixture'),0);
 const call=send(Buffer.from('fixture'),1);live.push(call);call.catch(()=>{});await reached;
 const bytes=await readFile(path.join(encoder.root,'CAPTURE_OPERATION_CHECKPOINT.json'));
 const checkpoint=JSON.parse(bytes);
 assert.equal(checkpoint.operationId,'ENCODER_DRAIN');assert.equal(checkpoint.operationPhase,'START');
 assert.equal(checkpoint.frameIndex,1);assert.equal(checkpoint.renderedFrames,1);assert.equal(checkpoint.firstFailure,null);
 result.cases.push({case:'encoder_drain_wait_boundary',frameIndex:1,renderedFrames:1,status:'PASS',checkpointSHA256:sha(bytes)});
 result.status='NEW_CAPTURE_WIRING_FOCUS_PASS';
}catch(error){result.status='FAIL';result.failure={name:error.name,message:String(error.message).slice(0,1200)};process.exitCode=1;}
finally{result.finishedAt=new Date().toISOString();await save(path.join(output,'RESULT.json'),result);console.log(JSON.stringify(result));}
