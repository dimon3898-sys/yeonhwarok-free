// One original encode; PNG checkpoints are the exact native frames fed into it.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {once} from 'node:events';
import {promisify} from 'node:util';
import path from 'node:path';
import {openPolishRuntime,root,repo,json,sha} from './polish_runtime.mjs';
const execute=promisify(execFile);
assert.equal((await json(path.join(root,'evidence/FOCUSED_VALIDATION.json'))).status,'PASS');
assert.equal((await json(path.join(root,'evidence/OBJECT_SIZE_COMPARISON.json'))).status,'PASS');
const approved=await json(path.join(root,'../event-feature-bundle-v2/evidence/proof/REPORT.json'));
const acceptedIntegration=await json(path.join(root,'../event-feature-bundle-v2/evidence/integration/REPORT.json'));
const disclosure=acceptedIntegration.frames[0].diagnostic.native.gpu.layout.find(x=>x.role==='SCENARIO_DISCLOSURE');
assert(disclosure&&disclosure.kind==='TEXT');
const [disclosureX,disclosureY,disclosureWidth,disclosureHeight]=disclosure.box;
const disclosurePad=(disclosure.outlineRadius??disclosure.metrics?.outlineRadius??0)+2;
const removedDisclosureBox=[disclosureX-disclosurePad,disclosureY-disclosurePad,
 disclosureX+disclosureWidth+disclosurePad,disclosureY+disclosureHeight+disclosurePad];
const sameBox=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const visualProfile=await json(path.join(root,'fixtures/VISUAL_PROFILE.json'));
assert.equal(visualProfile.objectScale,1.2);
const publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof');
await mkdir(publicDir);await mkdir(proofDir);
const sourceCommit=(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const names=new Map([[72,'01_ROUTE_START.png'],[88,'02_OBJECT_DEPARTURE.png'],[120,'03_OBJECT_TRAVEL.png'],
 [170,'04_TRAVEL_APPROACH.png'],[192,'05_ENDPOINT_PULSE.png'],[239,'06_FINAL_HOLD.png']]);
const filename='SUEZ_EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH.mp4',video=path.join(publicDir,filename);
const report={schema:1,state:'EVENT_FEATURE_BUNDLE_V2_POLISH_CANDIDATE',status:'STARTED',sourceCommit,
 startedAtUtc:new Date().toISOString(),width:1080,height:1920,fps:30,audio:false,frames:[],checkpoints:[],
 userVideoApproved:false,eventFinal:false,permanentGateExecuted:false};
let session,encoder,encoderExit,encoderStopped=null,encoderError='';
try{
 session=await openPolishRuntime({visualProfile});report.totalFrames=session.detailPlan.totalFrames;report.durationSeconds=report.totalFrames/30;
 assert.equal(report.totalFrames,240);assert.equal(report.durationSeconds,8);
 const args=['-hide_banner','-loglevel','error','-nostdin','-f','image2pipe','-framerate','30','-vcodec','png','-threads','2','-i','pipe:0',
  '-an','-c:v','libx264','-preset','faster','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
 report.encodeCommand=['ffmpeg',...args];encoder=spawn('ffmpeg',args,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 encoderExit=new Promise(resolve=>{const stop=r=>{encoderStopped??=r;resolve(encoderStopped);};
  encoder.once('error',e=>stop({error:e.message}));encoder.once('exit',code=>stop({code}));
  encoder.stdin.once('error',e=>{encoderError+=' '+e.message;stop({error:e.message});});});
 for(let frame=0;frame<report.totalFrames;frame++){
  const row=await session.page.evaluate(f=>window.flowProof.capture(f,{protect:true,png:true}),frame);
  const bytes=Buffer.from(row.png.split(',')[1],'base64');delete row.png;const d=row.diagnostic;
  assert.equal(sha(bytes),row.png_sha256);assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  assert.equal(d.glError,0);assert.equal(d.flow.protection.protectedChangedPixels,0);
  assert.equal(d.flow.protection.markerChangedPixels,0);assert.equal(d.flow.protection.outsideRoiChangedPixels,0);
  if(frame<session.detailPlan.detailLockFrame){assert.equal(d.flow.enabled,false);assert.equal(d.flow.controls,null);}
  else{assert.equal(d.camera.cameraLocked,true);assert.equal(d.flow.graphics.nativeStateRestored,true);
   assert.deepEqual(d.flow.primitive.intent.line.geometry,session.flowPlan.intent.route_geometry);assert.equal(d.flow.style.width,7);
   const expectedControls=structuredClone(approved.frames[frame].flow.controls);
   const priorBoxes=expectedControls.eventControls.readiness.protectedBoxes;
   expectedControls.eventControls.readiness.protectedBoxes=priorBoxes.filter(box=>!sameBox(box,removedDisclosureBox));
   assert.equal(priorBoxes.length-expectedControls.eventControls.readiness.protectedBoxes.length,1,'ONLY_REMOVED_DISCLOSURE_RESERVATION_ALLOWED');
   assert.deepEqual(d.native.event.protectedGraphics,approved.frames[frame].protectedGraphics.filter(g=>!sameBox(g.box,removedDisclosureBox)),
    'RETAINED_PROTECTED_GRAPHICS_CHANGED');
   assert.deepEqual(d.flow.controls,expectedControls,'ACCEPTED_CORE_MOTION_OR_TIMELINE_CHANGED');
   for(const key of ['objectFraction','objectPosition','objectHeading','headingLookAheadPixels','localFrame','state'])
    assert.deepEqual(d.flow.visualControls[key],d.flow.controls[key],'PRESENTATION_CHANGED_OBJECT_MOTION_'+key);
   assert.deepEqual(d.flow.visualProfile.afterSize,[62.4,36]);}
  assert.deepEqual(d.camera.flatBounds,approved.frames[frame].cameraBounds,'CAMERA_CHANGED');
  assert.equal(d.native.gpu.layout.some(item=>item.role==='SCENARIO_DISCLOSURE'),false,'TEST_TEXT_REAPPEARED');
  assert.equal(encoderStopped,null,'FLOW_ENCODER_STOPPED_EARLY '+JSON.stringify(encoderStopped));
  if(!encoder.stdin.write(bytes)){
   const drain=once(encoder.stdin,'drain').then(()=>({drained:true}),e=>({error:e.message}));
   const result=await Promise.race([drain,encoderExit]);assert.equal(result.drained,true,'FLOW_ENCODER_BACKPRESSURE '+JSON.stringify(result));
  }
  const checkpoint=names.get(frame);
  if(checkpoint){await writeFile(path.join(publicDir,checkpoint),bytes,{flag:'wx'});
   report.checkpoints.push({frame,state:d.state,file:checkpoint,sha256:sha(bytes),bytes:bytes.length,sourceMatchesEncodedNativeFrame:true});}
  report.frames.push({frame,state:d.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:row.png_sha256,
   cameraBounds:d.camera.flatBounds,cameraLocked:d.camera.cameraLocked,flow:d.flow,
   protectedGraphics:d.native.event.protectedGraphics,layoutValidation:d.native.gpu.layoutValidation,
   layoutItems:d.native.gpu.layout,visibleRoles:d.native.gpu.visibleRoles,glError:d.glError});
  if(frame%15===0||frame===239)console.log(JSON.stringify({phase:'FLOW_POLISH_PROOF',frame,total:report.totalFrames,state:d.state}));
 }
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'FLOW_ENCODER_FAILED '+encoderError);
 const probe=(await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video])).stdout;
 report.ffprobe=JSON.parse(probe);const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_read_frames),240);assert.equal(Number(stream.duration),8);assert.equal(stream.codec_name,'h264');
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 assert.equal(session.errors.length,0);assert.equal(report.checkpoints.length,6);
 const bytes=await readFile(video);report.video={file:filename,sha256:sha(bytes),bytes:bytes.length};
 const checks=[...report.checkpoints,report.video].sort((a,b)=>a.file.localeCompare(b.file));
 await writeFile(path.join(publicDir,'SHA256SUMS'),checks.map(r=>r.sha256+'  '+r.file).join('\n')+'\n',{flag:'wx'});
 report.protection={eventOnFrames:180,protectedChangedPixels:0,markerChangedPixels:0,outsideRoiChangedPixels:0,geometryUnchanged:true,cameraUnchanged:true,coreObjectMotionUnchanged:true,headingUnchanged:true,
 allowedProtectedContextChange:'REMOVED_SCENARIO_DISCLOSURE_MEASURED_BOX_ONLY',removedDisclosureBox};
 report.visualProfile=visualProfile;report.polish={beforeSize:[52,30],afterSize:[62.4,36],routeVisualCompletionFrame:157,
 arrivalPeakFrame:192,arrivalPulseCount:1,holdFrames:34,removedPublicText:['이동 예시'],coreTimingUnchanged:true};
 report.decodeValidation='PASS';report.status='PASS';
}catch(error){report.status='FAIL';report.error=error.message;throw error;}
finally{
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
 try{await session?.close();}catch(error){report.status='FAIL';report.cleanupError=error.message;throw error;}
 finally{report.completedAtUtc=new Date().toISOString();await writeFile(path.join(proofDir,'REPORT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});}
}
console.log(JSON.stringify({status:report.status,video:report.video,frames:report.frames.length,checkpoints:report.checkpoints.length}));
