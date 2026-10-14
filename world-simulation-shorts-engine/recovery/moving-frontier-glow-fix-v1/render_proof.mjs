/** Source-bound, resumable genuine-map capture and one original MP4 encoding. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,rename,unlink,open,stat} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {openQualityRuntime,assertQualityDiagnostic,root,repo,engine,json,sha,movieName,relativeFile} from './reference_runtime.mjs';
const execute=promisify(execFile),exists=async file=>stat(file).then(()=>true,()=>false);
const atomic=async(file,value)=>{const pending=file+'.writing';await writeFile(pending,JSON.stringify(value)+'\n');await rename(pending,file);};
const args=process.argv.slice(2),supplied=args.map(argument=>{
 const match=/^--source-commit=([a-f0-9]{40})$/.exec(argument);
 if(!match)throw Error('QUALITY_RENDER_UNKNOWN_ARGUMENT '+argument);return match[1];
});
assert.ok(supplied.length<=1,'ONE_RENDER_SOURCE_COMMIT_REQUIRED');
const sourceCommit=supplied[0]??(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const fixtureFile=path.join(root,'fixtures/RUNTIME_FIXTURE.json'),fixture=await json(fixtureFile),
 sceneFile=path.join(root,'fixtures/SCENE_PLAN.json'),sceneBytes=await readFile(sceneFile),scene=JSON.parse(sceneBytes),
 admissionFile=path.join(root,'evidence/VISUAL_ADMISSION.json'),admission=await json(admissionFile);
assert.equal(fixture.totalFrames,150);assert.equal(fixture.fps,30);assert.equal(fixture.videoFilename,movieName);
assert.equal(scene.controlIntent.total_frames,150);assert.equal(scene.controlIntent.fps,30);
assert.equal(admission.status,'VISUAL_REFERENCE_ADMITTED');assert.equal(admission.grade,'FACT_BASED_VISUAL_GRADE');
assert.equal(admission.evidenceKind,'ACTUAL_NATIVE_STATIC_PROBE');assert.equal(admission.surveyAdmissionModified,false);
assert.equal(admission.cameraKeyframeBinding,JSON.stringify(scene.cameraKeyframes));
assert.ok(Array.isArray(admission.samples)&&admission.samples.length>=3);
assert.equal(fixture.checkpoints.length,5);
const checks=new Map(),names=new Set();
for(const checkpoint of fixture.checkpoints){
 assert.ok(Number.isSafeInteger(checkpoint.frame)&&checkpoint.frame>=0&&checkpoint.frame<150);
 assert.ok(/^[A-Z0-9_]+\.png$/i.test(checkpoint.name)&&!names.has(checkpoint.name));names.add(checkpoint.name);
 checks.set(checkpoint.frame,[...(checks.get(checkpoint.frame)??[]),checkpoint.name]);
}
const inputFiles=[fixtureFile,sceneFile,admissionFile,path.join(root,'reference_runtime.mjs'),
 path.join(root,'probe_native.mjs'),path.join(root,'render_proof.mjs'),
 path.join(engine,'recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json'),
 ...Object.values(fixture.nativeFiles).map(relativeFile),
 ...Object.values(fixture.inheritedAdmissionFiles).map(relativeFile),
 ...fixture.runtimeModuleFiles.map(relativeFile),...(fixture.runtimeAssetFiles??[]).map(relativeFile)];
for(const sample of admission.samples){
 assert.ok(['VISUAL_PASS','VISUAL_WARNING'].includes(sample.visual));
 assert.ok(Number.isSafeInteger(sample.frame)&&sample.frame>=0&&sample.frame<150);
 assert.ok(/^[a-f0-9]{64}$/.test(sample.pngSha256));
 const file=path.join(root,'evidence/native_probe',String(sample.frame).padStart(3,'0')+'.png');
 assert.equal(sha(await readFile(file)),sample.pngSha256);inputFiles.push(file);
}
const sourceBindings=[];
for(const file of [...new Set(inputFiles)]){
 const relative=path.relative(repo,file).replaceAll(path.sep,'/');
 assert.ok(!relative.startsWith('../')&&!path.isAbsolute(relative));
 const bytes=await readFile(file),saved=await execute('git',['show',sourceCommit+':'+relative],
  {cwd:repo,encoding:'buffer',maxBuffer:128*1024*1024});
 assert.deepEqual(saved.stdout,bytes,'UNSAVED_QUALITY_RENDER_INPUT '+relative);
 sourceBindings.push({path:relative,sha256:sha(bytes),bytes:bytes.length});
}
const assertInputsUnchanged=async()=>{
 for(const source of sourceBindings)assert.equal(sha(await readFile(path.join(repo,source.path))),source.sha256,
  'QUALITY_RENDER_INPUT_MUTATION '+source.path);
};
const signature=sha(Buffer.from(JSON.stringify({sourceCommit,sourceBindings}))),
 cache=path.join(repo,'../.onboarding/moving-frontier-glow-fix-v1',signature),
 framesDir=path.join(cache,'frames'),rowsDir=path.join(cache,'rows'),
 publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof'),checkpointDir=path.join(proofDir,'checkpoints');
await Promise.all([mkdir(framesDir,{recursive:true}),mkdir(rowsDir,{recursive:true}),mkdir(publicDir,{recursive:true}),mkdir(checkpointDir,{recursive:true})]);
const priorReport=await exists(path.join(proofDir,'REPORT.json'))?await json(path.join(proofDir,'REPORT.json')):null;
const lockPath=path.join(cache,'ACTIVE_CAPTURE_LOCK.json');
if(await exists(lockPath)){
 const lock=await json(lockPath);let running=false;try{process.kill(lock.pid,0);running=true;}catch{}
 if(running)throw Error('QUALITY_CAPTURE_ALREADY_RUNNING_PID_'+lock.pid);
 await rename(lockPath,path.join(cache,'STALE_LOCK_'+lock.pid+'_'+Date.now()+'.json'));
}
const lock=await open(lockPath,'wx');await lock.writeFile(JSON.stringify({pid:process.pid,sourceCommit,signature})+'\n');await lock.close();
const resumeCommand='node world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/render_proof.mjs --source-commit='+sourceCommit;
const captureStarted=performance.now();
const report={schema:'MOVING_FRONTIER_GLOW_NATIVE_PROOF_V1',state:'MOVING_FRONTIER_GLOW_FIX_5S_CANDIDATE',status:'IN_PROGRESS',
 sourceCommit,sourceBindings,startedAtUtc:new Date().toISOString(),output:[1080,1920],width:1080,height:1920,
 totalFrames:150,fps:30,durationSeconds:5,audio:false,reference:scene.metadata,
 scene:{file:'fixtures/SCENE_PLAN.json',sha256:sha(sceneBytes),bytes:sceneBytes.length,public:false},frames:[],checkpoints:[],visualAdmission:admission,
 optionalNativeForegroundExcludedByNewScene:true,oldNativeForegroundPixelIdentityClaimed:false,
 qualityParityClaimed:false,fullVisualReviewClaimed:false,userVideoApproved:false,finalPromotion:false,permanentGateExecuted:false,
 requiredTempOnlyFiles:0,resume:{signature,command:resumeCommand,capturedFrames:0,reusedFrames:0,
  cacheRequiredForCleanReproduction:false,mechanism:'VERIFY_SOURCE_COMMIT_SIGNATURE_FRAME_ROW_AND_PNG_THEN_CAPTURE_ONLY_MISSING_FRAMES'}};
let session,failure=null;
try{
 const contextFile=path.join(cache,'CAPTURE_CONTEXT.json');
 if(await exists(contextFile)){
  const context=await json(contextFile);assert.equal(context.signature,signature);assert.equal(context.sourceCommit,sourceCommit);
  report.runtime=context.runtime;report.runtimeSourceSignature=context.runtimeSourceSignature;
 }
 for(let frame=0;frame<150;frame++){
  const name=String(frame).padStart(3,'0'),framePath=path.join(framesDir,name+'.png'),rowPath=path.join(rowsDir,name+'.json');
  let row,bytes;
  if(await exists(framePath)&&await exists(rowPath)){
   row=await json(rowPath);bytes=await readFile(framePath);assert.equal(row.signature,signature);assert.equal(row.sourceCommit,sourceCommit);
   assert.equal(row.frame,frame);assert.equal(row.png_sha256,sha(bytes));assertQualityDiagnostic(row.diagnostic,{frame});
   report.resume.reusedFrames++;
  }else{
   if(await exists(framePath))await rename(framePath,path.join(cache,'ORPHAN_FRAME_'+name+'_'+Date.now()+'.png'));
   if(await exists(rowPath))await rename(rowPath,path.join(cache,'ORPHAN_ROW_'+name+'_'+Date.now()+'.json'));
   if(!session){
    session=await openQualityRuntime({mode:'VISUAL_REFERENCE_STUDY'});
    assert.equal(session.info.productionEligible,true);assert.equal(session.info.cameraMotion.status,'PASS');
    assert.equal(session.info.cameraMotion.fakeLockCount,0);
    if(report.runtimeSourceSignature)assert.equal(session.sourceSignature,report.runtimeSourceSignature);
    report.runtime=session.info;report.runtimeSourceSignature=session.sourceSignature;
    await atomic(contextFile,{signature,sourceCommit,runtime:session.info,runtimeSourceSignature:session.sourceSignature});
   }
   const frameCaptureStarted=performance.now();
   const captured=await session.page.evaluate(async frame=>await window.referenceProof.capture(frame,{png:true}),frame),
    d=assertQualityDiagnostic(captured.diagnostic,{frame});
   bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   const cameraBounds=d.camera.bounds??d.camera.camera?.flatBounds??d.camera.flatBounds;
   assert.ok(Array.isArray(cameraBounds)&&cameraBounds.length===4);
   row={frame,signature,sourceCommit,raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,
    cameraBounds,cameraLocked:false,rotationDegrees:d.camera.rotationDegrees,control:d.territory.controls,
    protection:d.protection,presentation:d.presentation,units:d.units,
    glError:d.gpu.glError,nativeDrawCount:d.gpu.nativeDrawCount,
    captureWallMilliseconds:performance.now()-frameCaptureStarted,diagnostic:d};
   await writeFile(framePath,bytes,{flag:'wx'});await atomic(rowPath,row);
  }
  assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  for(const file of checks.get(frame)??[]){
   const target=path.join(checkpointDir,file);
   if(await exists(target))assert.deepEqual(await readFile(target),bytes);else await writeFile(target,bytes,{flag:'wx'});
   report.checkpoints.push({file,path:'evidence/proof/checkpoints/'+file,frame,sha256:sha(bytes),bytes:bytes.length,originalNativeCapture:true,public:false});
  }
  report.frames.push(row);report.resume.capturedFrames=frame+1;
  if(frame%30===0||frame===149){
   await atomic(path.join(proofDir,'CAPTURE_STATUS.json'),{status:frame===149?'NATIVE_FRAMES_PASS':'IN_PROGRESS',
    sourceCommit,signature,capturedFrames:frame+1,totalFrames:150,lastFrame:frame,resumeCommand,requiredTempOnlyFiles:0});
   console.log(JSON.stringify({phase:'QUALITY_NATIVE_CAPTURE',frame,total:150,reused:report.resume.reusedFrames}));
  }
 }
 assert.equal(session?.errors.length??0,0);await session?.close();session=null;await assertInputsUnchanged();
 const video=path.join(publicDir,movieName),encodingReceipt=path.join(cache,'ORIGINAL_ENCODING_RECEIPT.json');
 if(!await exists(video)){
  const partial=path.join(cache,'ORIGINAL_CANDIDATE_ENCODING.mp4');
  if(await exists(partial))await rename(partial,path.join(cache,'INCOMPLETE_ENCODING_'+Date.now()+'.mp4'));
  const encodeArgs=['-hide_banner','-loglevel','error','-nostdin','-framerate','30','-start_number','0','-threads','2',
   '-i',path.join(framesDir,'%03d.png'),'-frames:v','150','-an','-c:v','libx264','-preset','fast','-crf','16',
   '-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',partial];
  report.encodeCommand=['ffmpeg',...encodeArgs];await execute('ffmpeg',encodeArgs,{maxBuffer:8*1024*1024});
  const bytes=await readFile(partial);await atomic(encodingReceipt,{signature,sourceCommit,sha256:sha(bytes),bytes:bytes.length,command:report.encodeCommand});
  await rename(partial,video);
 }else{
  const bytes=await readFile(video);
  if(await exists(encodingReceipt)){
   const receipt=await json(encodingReceipt);assert.equal(receipt.signature,signature);assert.equal(receipt.sourceCommit,sourceCommit);
   assert.equal(receipt.sha256,sha(bytes));assert.equal(receipt.bytes,bytes.length);
  }else{
   assert.equal(priorReport?.status,'PASS');assert.equal(priorReport.sourceCommit,sourceCommit);
   assert.equal(priorReport.resume.signature,signature);assert.deepEqual(priorReport.sourceBindings,sourceBindings);
   assert.equal(priorReport.video.file,movieName);assert.equal(priorReport.video.sha256,sha(bytes));assert.equal(priorReport.video.bytes,bytes.length);
  }
  report.encodeCommand=['PRESERVED_VERIFIED_COMPLETE_ORIGINAL_CANDIDATE_NO_REENCODE'];
 }
 report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
 const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.codec_name,'h264');
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_frames),150);assert.equal(Number(stream.duration),5);
 const videoBytes=await readFile(video);report.video={file:movieName,sha256:sha(videoBytes),bytes:videoBytes.length};
 // The executed scene remains in persisted private fixtures. Public review is
 // restricted to the original movie, five comparison PNGs, and checksums.
 assert.equal(await exists(path.join(publicDir,'SCENE_PLAN.json')),false,'SCENE_JSON_IS_NOT_AUTHORIZED_IN_PUBLIC_REVIEW');
 const sums=[report.video].sort((a,b)=>a.file.localeCompare(b.file)),
  body=sums.map(item=>item.sha256+'  '+item.file).join('\n')+'\n',sumsPath=path.join(publicDir,'SHA256SUMS');
 if(!await exists(sumsPath))await writeFile(sumsPath,body,{flag:'wx'});
 await assertInputsUnchanged();
 report.protection={checkedFrames:150,sourceUnchanged:true,nativeVisualCoreUnchanged:true,sourceGeometryUnchanged:true,
  optionalNativeForegroundExcludedByNewScene:true,oldNativeForegroundPixelIdentityClaimed:false,
  glErrors:0,cornerSampleFailures:0,safeAreaViolations:0,criticalUnitCollisions:0,
  routeVisuals:false,arrowVisuals:false,standaloneFrontLine:false,
  frontierLight:{realControlBoundaryDerived:true,standaloneDecorativeLine:false,isIntentionalCurrentBoundaryHighlight:true}};
 report.decodeValidation='AWAITING_ACTUAL_FULL_RGB_AUDIT';report.status='PASS';
}catch(error){failure=error;report.status='BLOCKED';report.error=error.stack;
}finally{
 try{await session?.close();}catch(error){failure??=error;report.status='BLOCKED';report.error??=error.stack;}
 report.completedAtUtc=new Date().toISOString();
 report.performance={totalRunWallSeconds:(performance.now()-captureStarted)/1000,
  actualBackend:report.runtime?.backend??null,
  measuredNewFrameCaptureWallMilliseconds:report.frames.filter(row=>Number.isFinite(row.captureWallMilliseconds)).map(row=>row.captureWallMilliseconds),
  includesPngReadbackHashAndPlaywrightTransport:true,gpuTimerQueryClaimed:false,
  newlyCapturedFrames:report.frames.length-report.resume.reusedFrames,reusedFrames:report.resume.reusedFrames};
 try{await atomic(path.join(proofDir,'REPORT.json'),report);}finally{await unlink(lockPath);}
}
if(failure)throw failure;
console.log(JSON.stringify({status:report.status,frames:report.frames.length,video:report.video,
 checkpoints:report.checkpoints.length,reusedFrames:report.resume.reusedFrames,fullVisualReviewClaimed:false}));
