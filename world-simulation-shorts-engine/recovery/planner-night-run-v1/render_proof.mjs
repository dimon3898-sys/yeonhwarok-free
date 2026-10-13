/** Resumable native frame capture and one original encoding; no model-side job service is assumed. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,rename,unlink,open,stat} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {openNightRuntime,root,repo,engine,json,sha} from './night_runtime.mjs';
const execute=promisify(execFile),exists=async file=>stat(file).then(()=>true,()=>false);
const encode=value=>JSON.stringify(value)+'\n';
const atomic=async(file,value)=>{const temporary=file+'.writing';await writeFile(temporary,encode(value));await rename(temporary,file);};
const sourceCommit=(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const fixture=await json(path.join(root,'fixtures/RUNTIME_FIXTURE.json'));
const scenePath=path.join(root,'fixtures/SCENE_PLAN.json'),sceneBytes=await readFile(scenePath),scene=JSON.parse(sceneBytes);
assert.equal((await json(path.join(root,'evidence/INTEGRATION.json'))).status,'PASS');
assert.equal((await json(path.join(root,'evidence/FOCUSED_TESTS.json'))).status,'PASS');
assert.equal(scene.timing.total_frames,420);assert.equal(scene.timing.fps,30);
const inputs=['web/map_infographic_v1/planner_scene_v1.mjs','web/map_infographic_v1/planner_scene_v1.schema.json',
 'web/map_infographic_v1/planner_causal_adapter_v1.mjs','web/map_infographic_v1/planner_causal_gpu_adapter_v1.mjs',
 'recovery/planner-night-run-v1/render_proof.mjs','recovery/planner-night-run-v1/night_runtime.mjs',
 'recovery/planner-night-run-v1/fixtures/SCENE_PLAN.json','recovery/planner-night-run-v1/fixtures/RUNTIME_FIXTURE.json',
 'recovery/planner-night-run-v1/fixtures/CAUSAL_PLAN.json'];
const bindings=[];
for(const file of inputs){
 const relative='world-simulation-shorts-engine/'+file,bytes=await readFile(path.join(engine,file));
 const saved=await execute('git',['show',sourceCommit+':'+relative],{cwd:repo,encoding:'buffer',maxBuffer:8*1024*1024});
 assert.deepEqual(saved.stdout,bytes,'UNSAVED_NIGHT_RENDER_INPUT '+relative);
 bindings.push({path:relative,sha256:sha(bytes),bytes:bytes.length});
}
const signature=sha(Buffer.from(JSON.stringify({sourceCommit,sceneSha256:sha(sceneBytes),bindings})));
const cache=path.join(repo,'../.onboarding/planner-night-run-v1',signature),framesDir=path.join(cache,'frames'),rowsDir=path.join(cache,'rows');
const publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof');
await Promise.all([mkdir(framesDir,{recursive:true}),mkdir(rowsDir,{recursive:true}),mkdir(publicDir,{recursive:true}),mkdir(proofDir,{recursive:true})]);
const lockPath=path.join(cache,'ACTIVE_CAPTURE_LOCK.json');
if(await exists(lockPath)){
 const lock=await json(lockPath);let running=false;try{process.kill(lock.pid,0);running=true;}catch{}
 if(running)throw Error('NIGHT_CAPTURE_ALREADY_RUNNING_PID_'+lock.pid);
 await rename(lockPath,path.join(cache,'STALE_LOCK_'+lock.pid+'.json'));
}
const lock=await open(lockPath,'wx');await lock.writeFile(encode({pid:process.pid,sourceCommit,signature}));await lock.close();
const sceneExport=path.join(publicDir,'SCENE_PLAN.json');
if(await exists(sceneExport))assert.deepEqual(await readFile(sceneExport),sceneBytes);else await writeFile(sceneExport,sceneBytes,{flag:'wx'});
const report={schema:1,state:'PLANNER_NIGHT_CAUSAL_VISUAL_CANDIDATE',status:'IN_PROGRESS',sourceCommit,
 startedAtUtc:new Date().toISOString(),width:1080,height:1920,fps:30,audio:false,totalFrames:420,durationSeconds:14,
 frames:[],checkpoints:[],scene:{file:'SCENE_PLAN.json',sha256:sha(sceneBytes),bytes:sceneBytes.length},
 causalTracks:scene.causal_tracks,selectedFeatures:scene.selected_features,sourceBindings:bindings,
 userVideoApproved:false,plannerFinal:false,eventFinal:false,permanentGateExecuted:false,fullVisualReviewClaimed:false,
 resume:{signature,capturedFrames:0,reusedFrames:0,cacheRequiredForCleanReproduction:false,
  command:'node recovery/planner-night-run-v1/render_proof.mjs',mechanism:'VERIFY_SAVED_FRAME_HASHES_AND_CAPTURE_ONLY_MISSING_FRAMES'}};
const checks=new Map();for(const row of fixture.presentation.checkpoints){const names=checks.get(row.frame)??[];names.push(row.file??row.name);checks.set(row.frame,names);}
let session;
try{
 for(let frame=0;frame<420;frame++){
  const name=String(frame).padStart(3,'0'),framePath=path.join(framesDir,name+'.png'),rowPath=path.join(rowsDir,name+'.json');
  let row,bytes;
  if(await exists(framePath)&&await exists(rowPath)){
   row=await json(rowPath);bytes=await readFile(framePath);
   assert.equal(row.frame,frame);assert.equal(row.png_sha256,sha(bytes));report.resume.reusedFrames++;
  }else{
   // Preserve a disconnected write without mistaking it for a completed verified frame.
   if(await exists(framePath))await rename(framePath,path.join(cache,'ORPHAN_FRAME_'+name+'_'+Date.now()+'.png'));
   if(await exists(rowPath))await rename(rowPath,path.join(cache,'ORPHAN_ROW_'+name+'_'+Date.now()+'.json'));
   session??=await openNightRuntime();
   const captured=await session.page.evaluate(frame=>window.nightProof.capture(frame,{protect:true,png:true}),frame);
   const d=captured.diagnostic;bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   assert.equal(d.glError,0);assert.equal(d.nativeDrawCount,1);assert.equal(d.camera.cameraLocked,true);
   for(const key of ['protectedChangedPixels','markerChangedPixels','textChangedPixels','outsideRoiChangedPixels',
    'safeAreaChangedPixels','protectedBoundaryChangedPixels'])assert.equal(d.protection[key],0);
   row={frame,state:d.state,raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,
    cameraBounds:d.camera.camera.flatBounds,cameraLocked:d.camera.cameraLocked,cameraNativeFrame:d.camera.nativeFrame,
    area:d.area,flowTracks:d.flowTracks,protection:d.protection,rois:d.rois,causalSchedule:d.causalSchedule,
    protectedGraphics:d.camera.protectedGraphics,layoutValidation:d.camera.gpu.layoutValidation,nativeDrawCount:d.nativeDrawCount,glError:d.glError};
   await writeFile(framePath,bytes,{flag:'wx'});await atomic(rowPath,row);
  }
  assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  for(const file of checks.get(frame)??[]){const target=path.join(publicDir,file);
   if(await exists(target))assert.deepEqual(await readFile(target),bytes);else await writeFile(target,bytes,{flag:'wx'});
   report.checkpoints.push({file,frame,sha256:sha(bytes),bytes:bytes.length,sourceMatchesEncodedNativeFrame:true});
  }
  report.frames.push(row);report.resume.capturedFrames=frame+1;
  if(frame%30===0||frame===419){
   await atomic(path.join(proofDir,'CAPTURE_STATUS.json'),{status:frame===419?'NATIVE_FRAMES_PASS':'IN_PROGRESS',sourceCommit,
    signature,capturedFrames:frame+1,totalFrames:420,lastFrame:frame,resumeCommand:report.resume.command,requiredTempOnlyFiles:0});
   console.log(JSON.stringify({phase:'NIGHT_NATIVE_CAPTURE',frame,total:420,state:row.area.controls.stateId,reused:report.resume.reusedFrames}));
  }
 }
 assert.equal(session?.errors.length??0,0);assert.equal(report.frames.at(-1).area.controls.hold,true);
 await session?.close();session=null;
 const video=path.join(publicDir,fixture.presentation.videoFilename);
 if(!await exists(video)){
  const partial=path.join(cache,'ORIGINAL_CANDIDATE_ENCODING.mp4');
  if(await exists(partial))await rename(partial,path.join(cache,'INCOMPLETE_ENCODING_'+Date.now()+'.mp4'));
  const args=['-hide_banner','-loglevel','error','-nostdin','-framerate','30','-start_number','0','-threads','2',
   '-i',path.join(framesDir,'%03d.png'),'-frames:v','420','-an','-c:v','libx264','-preset','faster','-crf','16',
   '-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',partial];
  report.encodeCommand=['ffmpeg',...args];await execute('ffmpeg',args,{maxBuffer:8*1024*1024});await rename(partial,video);
 }else report.encodeCommand=['PRESERVED_COMPLETE_ORIGINAL_CANDIDATE_NO_REENCODE'];
 report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video])).stdout);
 const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.codec_name,'h264');
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_read_frames),420);assert.equal(Number(stream.duration),14);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 const videoBytes=await readFile(video);report.video={file:fixture.presentation.videoFilename,sha256:sha(videoBytes),bytes:videoBytes.length};
 const sums=[...report.checkpoints,report.video,report.scene].sort((a,b)=>a.file.localeCompare(b.file));
 const body=sums.map(item=>item.sha256+'  '+item.file).join('\n')+'\n',sumsPath=path.join(publicDir,'SHA256SUMS');
 if(await exists(sumsPath))assert.equal(await readFile(sumsPath,'utf8'),body);else await writeFile(sumsPath,body,{flag:'wx'});
 assert.deepEqual(await readFile(scenePath),sceneBytes);
 report.protection={checkedFrames:420,protectedChangedPixels:0,markerChangedPixels:0,textChangedPixels:0,
  outsideRoiChangedPixels:0,safeAreaChangedPixels:0,protectedBoundaryChangedPixels:0,geometryUnchanged:true};
 report.decodeValidation='PASS';report.status='PASS';
}catch(error){report.status='BLOCKED';report.error=error.stack;throw error;}
finally{
 try{await session?.close();}finally{report.completedAtUtc=new Date().toISOString();await atomic(path.join(proofDir,'REPORT.json'),report);await unlink(lockPath);}
}
console.log(JSON.stringify({status:report.status,frames:report.frames.length,video:report.video,
 scene:report.scene,checkpoints:report.checkpoints.length,reusedFrames:report.resume.reusedFrames}));
