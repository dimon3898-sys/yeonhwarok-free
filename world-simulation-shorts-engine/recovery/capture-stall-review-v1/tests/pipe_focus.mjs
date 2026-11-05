/** CPU-only replay of retained PNG bytes through exact production pipe fragments. */
import {readFile,writeFile,mkdir,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {once} from 'node:events';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const recovery=path.resolve(here,'../..');
const sourceFile=path.join(recovery,'codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs');
const sourceManifest=path.join(recovery,'codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json');
const [inputDirectory,outputDirectory]=process.argv.slice(2);
assert(inputDirectory&&outputDirectory,'Usage: node pipe_focus.mjs existing-a6-pixels fresh-output');
const input=path.resolve(inputDirectory),output=path.resolve(outputDirectory);
assert(!output.startsWith(input+path.sep)&&output!==input);
await mkdir(output,{recursive:false,mode:0o700});
const sha=x=>createHash('sha256').update(x).digest('hex');
const execute=promisify(execFile);
const source=await readFile(sourceFile,'utf8');
const manifest=JSON.parse(await readFile(sourceManifest,'utf8'));
const admitted=manifest.files.find(row=>row.path.endsWith('/capture_vulkan.generated.mjs'));
assert.equal(sha(source),admitted.sha256,'Test must use the image-admitted capture source');
const uniqueLine=prefix=>{const rows=source.split('\n').filter(line=>line.trimStart().startsWith(prefix));assert.equal(rows.length,1);return rows[0].trim();};
const launch=uniqueLine("encoder=spawn('ffmpeg'");
const writeLine=uniqueLine('if(probeFrames||checkpoints.has(frame))');
const transfer=writeLine.slice(writeLine.indexOf('if(encoder){check('));
assert(transfer.startsWith('if(encoder){check(')&&transfer.endsWith('}'));
const progress=uniqueLine('receipt.renderedFrames++;process.stdout.write(');
const endLine=uniqueLine('if(encoder){encoder.stdin.end();');
const finish=endLine.slice('if(encoder){'.length,endLine.indexOf('encoder=null;')+'encoder=null;'.length);
assert(finish.startsWith('encoder.stdin.end();')&&finish.endsWith('encoder=null;'));
const fragmentHashes=Object.fromEntries(Object.entries({launch,transfer,progress,finish}).map(([key,value])=>[key,sha(value)]));
const evidence=JSON.parse(await readFile(path.join(input,'FRAME_EVIDENCE.json'),'utf8'));
const filenames=(await readdir(input)).filter(name=>/^FRAME_\d{3}\.png$/.test(name)).sort();
assert.equal(filenames.length,22,'Only the preserved 22 sparse frames are in scope');
const inputs=[];
for(const name of filenames){
 const bytes=await readFile(path.join(input,name)),originalFrame=Number(name.slice(6,9));
 assert.equal(sha(bytes),evidence.frames.find(row=>row.frame===originalFrame)?.pngSHA256,'Fixture delivery identity');
 assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
 inputs.push({name,originalFrame,bytes,sha256:sha(bytes)});
}
const result={schema:'WORLD_ENGINE_EXISTING_PNG_PIPE_FOCUS_V1',startedAt:new Date().toISOString(),
 status:'RUNNING',sourceRef:'da86936fdfdbd33e9472b3ba80bf4ae28bfa83ac',sourceSHA256:sha(source),fragmentHashes,
 scope:'22_EXISTING_SPARSE_PNGS_CPU_PIPE_ONLY',gpuExecuted:false,browserLaunched:false,
 operationalCodeChanged:false,oldPassRerun:false,newRenderFrames:0,fixtureEncodedFrames:22,
 incidentCauseConfirmed:false,renderRecoveryPass:false,referenceQualityPass:false,
 limits:['Local CPU runtime is not the stopped gCube container','No actual frame1 browser evaluation',
 '22 sparse frames do not represent a continuous 10-second video','No GPU or production process supervision exercised'],
 fixtureSource:'quality-labels-cpu-41534356177/A6/pixels',
 inputs:inputs.map(({name,originalFrame,bytes,sha256})=>({name,originalFrame,bytes:bytes.length,sha256})),
 environment:{node:process.version,platform:process.platform,architecture:process.arch,
 ffmpeg:(await execute('ffmpeg',['-version'],{timeout:5000,maxBuffer:65536})).stdout.split('\n')[0],
 ffprobe:(await execute('ffprobe',['-version'],{timeout:5000,maxBuffer:65536})).stdout.split('\n')[0]},
 progress:[],transfers:[],testOnlyDeadlineSeconds:60};
let child=null,closed=false,exit=null,timeout=null,deadlineTriggered=false,stdinFinished=false,closePromise;
const creditText='CPU transport fixture from preserved A6 PNGs; not a continuous rendered Scene.';
const context=vm.createContext({path,outputRoot:output,creditText,once,
 check:(value,code)=>{if(!value)throw Error(code);},
 receipt:{renderedFrames:0},request:{totalFrames:inputs.length},
 process:{stdout:{write(line){const row=JSON.parse(line);result.progress.push({...row,observedMs:performance.now()-started});return true;}}},
 spawn:(command,args,options)=>{
  assert.equal(command,'ffmpeg');assert.equal(child,null,'Exactly one encode invocation');
  result.argv=args.map(value=>value===path.join(output,'VIDEO.mp4')?'OUTPUT/VIDEO.mp4':value);
  result.stdio=options.stdio;
  child=spawn(command,args,options);
  child.once('exit',(code,signal)=>{exit={code,signal};});
  child.stdin.once('finish',()=>{stdinFinished=true;});
  closePromise=new Promise(resolve=>child.once('close',(code,signal)=>{closed=true;resolve({code,signal});}));
  return child;
 }});
vm.runInContext('var encoder,encoderExit,ffmpegStderr="";',context);
const initialize=vm.runInContext(`(async()=>{${launch}})`,context);
const send=vm.runInContext(`(async(png,frame)=>{${transfer}\n${progress}})`,context);
const complete=vm.runInContext(`(async()=>{${finish}})`,context);
const started=performance.now();
const deadline=new Promise((_,reject)=>{timeout=setTimeout(()=>{deadlineTriggered=true;reject(Error('TEST_ONLY_PIPE_DEADLINE'));},60000);});
try{
 await Promise.race([(async()=>{
  await initialize();
  for(let index=0;index<inputs.length;index++){
   const begin=performance.now(),before=result.progress.length;
   await send(inputs[index].bytes,index);
   assert.equal(result.progress.length,before+1);
   result.transfers.push({index,originalFrame:inputs[index].originalFrame,completed:true,milliseconds:performance.now()-begin});
  }
  await complete();await closePromise;
 })(),deadline]);
 clearTimeout(timeout);
 assert.deepEqual(exit,{code:0,signal:null});assert(closed&&stdinFinished);
 assert.deepEqual(result.progress.map(row=>row.renderedFrames),Array.from({length:22},(_,i)=>i+1));
 assert.deepEqual(result.progress.map(row=>row.frame),Array.from({length:22},(_,i)=>i));
 assert(result.progress.every(row=>row.totalFrames===22&&row.stage==='ACTUAL_FRAME_DRAW'));
 const video=path.join(output,'VIDEO.mp4');
 const probe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video],{timeout:30000,maxBuffer:1048576})).stdout);
 const stream=probe.streams.find(row=>row.codec_type==='video');
 assert.equal(probe.streams.length,1);assert.equal(stream.codec_name,'h264');
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);
 assert.equal(stream.r_frame_rate,'30/1');assert.equal(Number(stream.nb_read_frames),22);
 assert(Math.abs(Number(probe.format.duration)-22/30)<1/30);
 assert.equal(probe.format.tags.comment,creditText);assert.equal(probe.format.tags.copyright,creditText);
 await execute('ffmpeg',['-v','error','-i',video,'-f','null','-'],{timeout:30000,maxBuffer:1048576});
 const bytes=await readFile(video);
 result.output={name:'VIDEO.mp4',bytes:bytes.length,sha256:sha(bytes),frames:22,width:1080,height:1920,
 fps:30,codec:'h264',durationSeconds:Number(probe.format.duration),audio:false,fullDecode:'PASS',
 classification:'CPU_SPARSE_FRAME_TRANSPORT_FIXTURE_NOT_DELIVERABLE_VIDEO'};
 result.status='PASS';
}catch(error){
 result.status='FAIL';result.failure={name:error.name,message:String(error.message).slice(0,500)};
 process.exitCode=1;
}finally{
 clearTimeout(timeout);
 if(child&&!closed){child.kill('SIGKILL');await Promise.race([closePromise,new Promise(resolve=>setTimeout(resolve,3000))]);}
 let pidAbsent=true;if(child?.pid)try{process.kill(child.pid,0);pidAbsent=false;}catch(error){if(error.code!=='ESRCH')pidAbsent=false;}
 result.cleanup={exit,closeObserved:closed,stdinFinished,pidAbsent,deadlineTriggered};
 if(!closed||!pidAbsent){result.status='FAIL';process.exitCode=1;}
 result.elapsedSeconds=(performance.now()-started)/1000;result.finishedAt=new Date().toISOString();
 await writeFile(path.join(output,'PIPE_RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});
 console.log(JSON.stringify({status:result.status,transferred:result.progress.length,total:22,
 elapsedSeconds:result.elapsedSeconds,output:result.output,cleanup:result.cleanup,failure:result.failure}));
}
