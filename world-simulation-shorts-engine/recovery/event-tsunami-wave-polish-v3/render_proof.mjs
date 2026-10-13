/** Encode original native wave frames once; retained PNGs are the exact encoder inputs. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {openWaveRuntime,root,repo,json,sha} from './wave_runtime.mjs';
const execute=promisify(execFile);
assert.equal((await json(path.join(root,'evidence/WAVE_REGRESSION.json'))).status,'PASS');
assert.equal((await json(path.join(root,'data/FIXTURE_PROTECTION.json'))).status,'PASS');
const fixture=await json(path.join(root,'fixtures/REAL_FIXTURE.json'));
const publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof');
const sourceCommit=(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const ownSource=['world-simulation-shorts-engine/web/map_infographic_v1/wave_visual_v3.mjs',
 'world-simulation-shorts-engine/web/map_infographic_v1/wave_gpu_adapter_v3.mjs',
 path.relative(repo,path.join(root,'render_proof.mjs')),path.relative(repo,path.join(root,'wave_runtime.mjs')),
 path.relative(repo,path.join(root,'fixtures/REAL_FIXTURE.json'))];
for(const file of ownSource){
 assert.equal((await execute('git',['diff','HEAD','--',file],{cwd:repo})).stdout,'','UNCOMMITTED_WAVE_SOURCE');
 await execute('git',['cat-file','-e',sourceCommit+':'+file],{cwd:repo});
}
await mkdir(publicDir);await mkdir(proofDir);
const report={schema:1,state:'EVENT_FEATURE_BUNDLE_V3_TSUNAMI_WAVE_POLISH_CANDIDATE',status:'STARTED',sourceCommit,
 startedAtUtc:new Date().toISOString(),width:1080,height:1920,fps:30,audio:false,frames:[],checkpoints:[],
 userVideoApproved:false,eventFinal:false,permanentGateExecuted:false};
const names=new Map(fixture.presentation.checkpoints.map(row=>[row.frame,row.file]));
const video=path.join(publicDir,fixture.presentation.videoFilename);
let session,encoder,encoderExit,encoderStopped=null,encoderError='';
try{
 session=await openWaveRuntime();report.totalFrames=session.presentation.totalFrames;report.durationSeconds=report.totalFrames/30;
 assert.ok(report.durationSeconds>=8&&report.durationSeconds<=10);
 report.wavePlanTiming={startFrame:session.wavePlan.startFrame,firstContactFrame:session.wavePlan.firstContactFrame,
  completeFrame:session.wavePlan.completeFrame,holdFrames:session.wavePlan.totalFrames-session.wavePlan.completeFrame,
  eventStartFrame:session.presentation.eventStartFrame};
 const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate','30','-vcodec','png','-threads','2','-i','pipe:0',
  '-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
 report.encodeCommand=['ffmpeg',...args];encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 encoderExit=new Promise(resolve=>{const stop=r=>{encoderStopped??=r;resolve(encoderStopped);};
  encoder.once('error',e=>stop({error:e.message}));encoder.once('exit',code=>stop({code}));
  encoder.stdin.once('error',e=>{encoderError+=' '+e.message;stop({error:e.message});});});
 for(let frame=0;frame<report.totalFrames;frame++){
  const row=await session.page.evaluate(f=>window.waveProof.capture(f,{protect:true,png:true}),frame);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;const d=row.diagnostic,w=d.wave;
  assert.equal(sha(bytes),row.png_sha256);assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  assert.equal(d.glError,0);
  for(const key of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])assert.equal(w.protection[key],0);
  assert.equal(w.closedPropagationRing,false);assert.equal(w.geometryUnchanged,true);
  if(frame<session.presentation.eventStartFrame)assert.equal(w.enabled,false);
  else{
   assert.equal(d.camera.cameraLocked,true);assert.equal(w.graphics.nativeStateRestored,true);
   assert.equal(w.controls.physicalSimulation,false);assert.equal(w.diagnostics.closedRingCount,0);
   assert.ok(w.diagnostics.majorFrontCount<=3);assert.equal(w.diagnostics.repeatBlink,false);
  }
  assert.equal(encoderStopped,null,'WAVE_ENCODER_STOPPED_EARLY '+JSON.stringify(encoderStopped));
  if(!encoder.stdin.write(bytes)){
   const drain=once(encoder.stdin,'drain').then(()=>({drained:true}),e=>({error:e.message}));
   const result=await Promise.race([drain,encoderExit]);assert.equal(result.drained,true,'WAVE_ENCODER_BACKPRESSURE '+JSON.stringify(result));
  }
  const checkpoint=names.get(frame);
  if(checkpoint){await writeFile(path.join(publicDir,checkpoint),bytes,{flag:'wx'});
   report.checkpoints.push({frame,state:d.state,file:checkpoint,sha256:sha(bytes),bytes:bytes.length,sourceMatchesEncodedNativeFrame:true});}
  // Persist measured results without duplicating native geometry or full line-engine caches per frame.
  report.frames.push({frame,state:d.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:row.png_sha256,
   cameraBounds:d.camera.camera.flatBounds,cameraLocked:d.camera.cameraLocked,cameraNativeFrame:d.camera.nativeFrame,
   wave:{enabled:w.enabled,protection:w.protection,geometryUnchanged:w.geometryUnchanged,
    controls:w.controls?{physicalSimulation:w.controls.physicalSimulation,
     propagations:w.controls.propagations.map(item=>({id:item.id,geometry:item.geometry,alpha:item.alpha}))}:null,
    closedPropagationRing:w.closedPropagationRing,coastContactSequential:w.coastContactSequential,
    nativeSourceUnchanged:w.nativeSourceUnchanged,diagnostics:w.diagnostics,originPulse:w.originPulse?{
     active:w.originPulse.active,progress:w.originPulse.progress,amplitude:w.originPulse.amplitude,repeatCount:w.originPulse.repeatCount}:null,
    annotation:w.annotation,graphics:w.graphics?{nativeStateRestored:w.graphics.nativeStateRestored,rois:w.graphics.rois,
     style:w.graphics.style,coastContact:w.graphics.coastContact?{
      rois:w.graphics.coastContact.rois,nativeStateRestored:w.graphics.coastContact.nativeStateRestored}:null}:null},
   protectedGraphics:d.camera.protectedGraphics,layoutValidation:d.camera.gpu.layoutValidation,glError:d.glError});
  if(frame%15===0||frame===report.totalFrames-1)console.log(JSON.stringify({phase:'WAVE_PROOF',frame,total:report.totalFrames,state:d.state}));
 }
 const end=report.frames.at(-1);
 assert.equal(end.state,'HOLD','PROOF_MUST_END_AFTER_EVENT_COMPLETION');
 assert.equal(end.wave.diagnostics.majorFrontCount,0,'PROOF_MUST_NOT_CUT_ACTIVE_FRONT');
 assert.equal(end.wave.diagnostics.coastContactCount,0,'PROOF_MUST_NOT_CUT_ACTIVE_CONTACT');
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'WAVE_ENCODER_FAILED '+encoderError);
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
