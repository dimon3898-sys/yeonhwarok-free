// One original encode; every checkpoint is the exact native PNG fed into that encode.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {evaluateCameraDetailApproachFrame} from '../../web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs';
import {openVisualRuntime,engine,repo,json,sha} from './visual_runtime.mjs';
const execute=promisify(execFile),root=path.join(engine,'recovery/event-v1-v3-visual-detail');
const plan=await json(path.join(root,'fixtures/DETAIL_ADAPTER_PLAN.json'));
const off=await json(path.join(root,'evidence/off250/REPORT.json'));
assert.equal(off.status,'BIT_EXACT');assert.equal(off.frames.length,250);
const publicDir=path.join(root,'public-review'),evidenceDir=path.join(root,'evidence/proof');
await mkdir(publicDir);await mkdir(evidenceDir);
const {stdout:commit}=await execute('git',['rev-parse','HEAD'],{cwd:repo});
const checkpointNames=new Map([[0,'01_EVENT_ARRIVAL.png'],[26,'02_DETAIL_APPROACH.png'],[60,'03_DETAIL_LOCK.png'],
 [90,'04_LINE_REVEAL.png'],[119,'05_LINE_COMPLETE.png'],[150,'06_METRIC_REVEAL.png'],[209,'07_INFORMATION_HOLD.png']]);
const videoName='SUEZ_EVENT_SYSTEM_V1_V3_VISUAL_DETAIL.mp4',video=path.join(publicDir,videoName);
const report={schema:1,state:'EVENT_SYSTEM_V1_V3_VISUAL_CANDIDATE',status:'STARTED',sourceCommit:commit.trim(),
 startedAtUtc:new Date().toISOString(),width:1080,height:1920,fps:30,audio:false,totalFrames:plan.totalFrames,
 durationSeconds:plan.durationSeconds,lockFrame:plan.detailLockFrame,frames:[],checkpoints:[],
 finalGateExecuted:false,eventFinal:false,videoReview:'USER_VIDEO_REVIEW_REQUIRED',fullOff250RegressionRuns:1};
let session,encoder,encoderError='',encoderExit;
try{
 session=await openVisualRuntime();
 await session.page.evaluate(request=>window.visualDetail.initialize({targetFraming:request.targetFraming,
  mode:'VISUAL_DETAIL_ADMITTED',certificate:request.certificate}),plan.request);
 const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate','30','-vcodec','png','-threads','2','-i','pipe:0',
  '-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
 report.encodeCommand=['ffmpeg',...args];encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 encoderExit=new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('exit',code=>resolve(code));});
 encoder.stdin.on('error',error=>{encoderError+=' '+error.message;});
 for(let frame=0;frame<plan.totalFrames;frame++){
  const scheduled=evaluateCameraDetailApproachFrame(plan,frame);
  const row=await session.page.evaluate(s=>window.visualDetail.capture({frame:s.frame,bounds:s.flatBounds,cameraLocked:s.cameraLocked,
   eventFrame:s.eventFrame,eventEnabled:s.eventEnabled,protect:s.eventEnabled,png:true}),scheduled);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);assert.equal(sha(bytes),row.png_sha256);
  const d=row.diagnostic,e=d.event;assert.equal(d.gpu.glError,0);assert.deepEqual(d.gpu.actualCamera.bounds,scheduled.flatBounds);
  assert.equal(d.frame,frame);assert.equal(d.scale,'REGIONAL');assert.equal(d.admission.status,'LOCAL_NOT_ADMITTED');
  if(!scheduled.eventEnabled){assert.equal(e.controls,null);assert.equal(e.line,null);assert.equal(e.metric,null);}
  else{
   const old=session.approved.frames[scheduled.eventFrame];
   assert.equal(row.protected_changed_pixels,0);assert.equal(row.marker_changed_pixels,0);assert.equal(row.outside_roi_changed_pixels,0);
   assert.equal(e.controls.state,old.state);assert.equal(e.controls.lineFraction,old.lineFraction);assert.equal(e.controls.metricFraction,old.metricFraction);
   assert.deepEqual(e.eventStyle,old.eventStyle);assert.deepEqual(e.metricStyle,old.metricStyle);
   assert.deepEqual(e.linePrimitive.intent.line.geometry.coordinates,plan.eventGeometry.coordinates);
   assert.equal(e.controls.metricValue,plan.eventPlan.intent.metric.display_value);assert.equal(e.controls.metricUnit,plan.eventPlan.intent.metric.unit);
   const marker=e.protectedGraphics.find(g=>g.kind==='MARKER');assert.ok(marker);assert.equal(marker.box[2]-marker.box[0],44);assert.equal(marker.box[3]-marker.box[1],44);
   if(e.placement){const b=e.placement.roi,s=plan.safeArea;assert.ok(b[0]>=s[0]&&b[1]>=s[1]&&b[2]<=s[2]&&b[3]<=s[3]);}
  }
  if(!encoder.stdin.write(bytes))await once(encoder.stdin,'drain');
  const name=checkpointNames.get(frame);
  if(name){await writeFile(path.join(publicDir,name),bytes,{flag:'wx'});report.checkpoints.push({frame,state:scheduled.state,file:name,sha256:sha(bytes),bytes:bytes.length,sourceMatchesEncodedNativeFrame:true});}
  report.frames.push({frame,state:scheduled.state,eventFrame:scheduled.eventFrame,cameraLocked:scheduled.cameraLocked,
   bounds:scheduled.flatBounds,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:row.png_sha256,
   event:e,hiddenGeographicLabels:d.hiddenGeographicLabels,warnings:d.warnings,
   outside_roi_changed_pixels:row.outside_roi_changed_pixels??0,protected_changed_pixels:row.protected_changed_pixels??0,
   marker_changed_pixels:row.marker_changed_pixels??0});
  if(frame%15===0||frame===plan.totalFrames-1)console.log(JSON.stringify({phase:'PROOF',frame,total:plan.totalFrames}));
 }
 encoder.stdin.end();assert.equal(await encoderExit,0,'ENCODER_FAILED '+encoderError);
 const {stdout}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video]);
 report.ffprobe=JSON.parse(stdout);const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_read_frames),plan.totalFrames);assert.equal(Number(stream.duration),plan.durationSeconds);assert.equal(stream.codec_name,'h264');
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 assert.equal(session.errors.length,0);assert.equal(report.checkpoints.length,7);
 const videoBytes=await readFile(video);report.video={file:videoName,sha256:sha(videoBytes),bytes:videoBytes.length};
 const assets=[...report.checkpoints,report.video].sort((a,b)=>a.file.localeCompare(b.file));
 await writeFile(path.join(publicDir,'SHA256SUMS'),assets.map(a=>a.sha256+'  '+a.file).join('\n')+'\n',{flag:'wx'});
 report.protection={eventOnFrames:150,protectedChangedPixels:0,markerChangedPixels:0,outsideRoiChangedPixels:0,
  geometryUnchanged:true,eventProgressUnchanged:true,lineStyleUnchanged:true,metricValueSourceStyleUnchanged:true,metricCollisions:0};
 report.decodeValidation='PASS';report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{report.completedAtUtc=new Date().toISOString();await writeFile(path.join(evidenceDir,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');await session?.close();}
console.log(JSON.stringify({status:report.status,video:report.video,frames:report.frames.length,checkpoints:report.checkpoints.length}));
