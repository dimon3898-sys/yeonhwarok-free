/** Original native-frame encode; no finished-frame compositing or media re-encoding. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {openAreaRuntime,root,repo,json,sha} from './area_runtime.mjs';
const execute=promisify(execFile);
assert.equal((await json(path.join(root,'evidence/SYNTHETIC.json'))).status,'PASS');
assert.equal((await json(path.join(root,'evidence/INTEGRATION.json'))).status,'PASS');
assert.equal((await json(path.join(root,'fixtures/AREA_VISUAL_ADMISSION.json'))).productionEligible,true);
const fixture=await json(path.join(root,'fixtures/REAL_FIXTURE.json'));
const publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof');
await mkdir(publicDir);await mkdir(proofDir);
const sourceCommit=(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const report={schema:1,state:'EVENT_FEATURE_BUNDLE_V3_AREA_CANDIDATE',status:'STARTED',sourceCommit,
 startedAtUtc:new Date().toISOString(),width:1080,height:1920,fps:30,audio:false,frames:[],checkpoints:[],
 userVideoApproved:false,eventFinal:false,permanentGateExecuted:false};
const names=new Map(fixture.presentation.checkpoints.map(row=>[row.frame,row.file])),video=path.join(publicDir,fixture.presentation.videoFilename);
let session,encoder,encoderExit,encoderStopped=null,encoderError='';
try{
 session=await openAreaRuntime();report.totalFrames=session.presentation.totalFrames;report.durationSeconds=report.totalFrames/30;
 assert.ok(report.durationSeconds>=8&&report.durationSeconds<=12);
 const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate','30','-vcodec','png','-threads','2','-i','pipe:0',
  '-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
 report.encodeCommand=['ffmpeg',...args];encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 encoderExit=new Promise(resolve=>{const stop=r=>{encoderStopped??=r;resolve(encoderStopped);};
  encoder.once('error',e=>stop({error:e.message}));encoder.once('exit',code=>stop({code}));
  encoder.stdin.once('error',e=>{encoderError+=' '+e.message;stop({error:e.message});});});
 for(let frame=0;frame<report.totalFrames;frame++){
  const row=await session.page.evaluate(f=>window.areaProof.capture(f,{protect:true,png:true}),frame);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;const d=row.diagnostic;
  assert.equal(sha(bytes),row.png_sha256);assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  assert.equal(d.glError,0);
  for(const key of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])assert.equal(d.area.protection[key],0);
  if(frame<session.presentation.eventStartFrame)assert.equal(d.area.enabled,false);
  else{assert.equal(d.camera.cameraLocked,true);assert.equal(d.area.graphics.nativeStateRestored,true);assert.equal(d.area.controls.physicalSimulation,false);}
  assert.equal(encoderStopped,null,'AREA_ENCODER_STOPPED_EARLY '+JSON.stringify(encoderStopped));
  if(!encoder.stdin.write(bytes)){
   const drain=once(encoder.stdin,'drain').then(()=>({drained:true}),e=>({error:e.message}));
   const result=await Promise.race([drain,encoderExit]);assert.equal(result.drained,true,'AREA_ENCODER_BACKPRESSURE '+JSON.stringify(result));
  }
  const checkpoint=names.get(frame);
  if(checkpoint){await writeFile(path.join(publicDir,checkpoint),bytes,{flag:'wx'});
   report.checkpoints.push({frame,state:d.state,file:checkpoint,sha256:sha(bytes),bytes:bytes.length,sourceMatchesEncodedNativeFrame:true});}
  report.frames.push({frame,state:d.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:row.png_sha256,
   cameraBounds:d.camera.camera.flatBounds,cameraLocked:d.camera.cameraLocked,cameraNativeFrame:d.camera.nativeFrame,
   area:d.area,protectedGraphics:d.camera.protectedGraphics,layoutValidation:d.camera.gpu.layoutValidation,glError:d.glError});
  if(frame%15===0||frame===report.totalFrames-1)console.log(JSON.stringify({phase:'AREA_PROOF',frame,total:report.totalFrames,state:d.state}));
 }
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'AREA_ENCODER_FAILED '+encoderError);
 report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video])).stdout);
 const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.width,1080);assert.equal(stream.height,1920);
 assert.equal(stream.avg_frame_rate,'30/1');assert.equal(Number(stream.nb_read_frames),report.totalFrames);assert.equal(Number(stream.duration),report.durationSeconds);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 assert.equal(session.errors.length,0);assert.equal(report.checkpoints.length,8);
 const bytes=await readFile(video);report.video={file:fixture.presentation.videoFilename,sha256:sha(bytes),bytes:bytes.length};
 const checks=[...report.checkpoints,report.video].sort((a,b)=>a.file.localeCompare(b.file));
 await writeFile(path.join(publicDir,'SHA256SUMS'),checks.map(row=>row.sha256+'  '+row.file).join('\n')+'\n',{flag:'wx'});
 report.protection={eventOnFrames:report.totalFrames-session.presentation.eventStartFrame,protectedChangedPixels:0,markerChangedPixels:0,
  outsideRoiChangedPixels:0,safeAreaChangedPixels:0,geometryUnchanged:true,lockBeforeEvent:true};
 report.decodeValidation='PASS';report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.stack;throw error;}
finally{
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
 try{await session?.close();}catch(error){report.status='FAIL';report.cleanupError=error.message;throw error;}
 finally{report.completedAtUtc=new Date().toISOString();await writeFile(path.join(proofDir,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});}
}
console.log(JSON.stringify({status:report.status,video:report.video,frames:report.frames.length,checkpoints:report.checkpoints.length}));
