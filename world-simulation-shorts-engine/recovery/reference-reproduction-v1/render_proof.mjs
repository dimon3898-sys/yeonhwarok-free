/** Resume verified native frames, then encode their original pixels once. No FINAL gate is executed. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,rename,unlink,open,stat} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {openReferenceRuntime,assertReferenceDiagnostic,root,repo,engine,json,sha} from './reference_runtime.mjs';

const execute=promisify(execFile),exists=async file=>stat(file).then(()=>true,()=>false);
const encode=value=>JSON.stringify(value)+'\n';
const atomic=async(file,value)=>{const pending=file+'.writing';await writeFile(pending,encode(value));await rename(pending,file);};
const suppliedCommit=process.argv.slice(2).map(argument=>{
 const match=/^--source-commit=([a-f0-9]{40})$/.exec(argument);
 if(!match)throw Error('REFERENCE_RENDER_UNKNOWN_ARGUMENT '+argument);
 return match[1];
});
if(suppliedCommit.length>1)throw Error('REFERENCE_RENDER_ONE_SOURCE_COMMIT_REQUIRED');
const sourceCommit=suppliedCommit[0]??(await execute('git',['rev-parse','HEAD'],{cwd:repo})).stdout.trim();
const fixture=await json(path.join(root,'fixtures/RUNTIME_FIXTURE.json')),
 sceneFile=path.join(root,'fixtures/SCENE_PLAN.json'),sceneBytes=await readFile(sceneFile),scene=JSON.parse(sceneBytes),
 admissionFile=path.join(root,'evidence/VISUAL_ADMISSION.json'),admission=await json(admissionFile);
assert.equal(fixture.totalFrames,150);assert.equal(fixture.fps,30);
assert.equal(fixture.videoFilename,'WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4');
assert.equal(scene.controlIntent.total_frames,150);assert.equal(scene.controlIntent.fps,30);
assert.equal(admission.status,'VISUAL_REFERENCE_ADMITTED');assert.equal(admission.grade,'FACT_BASED_VISUAL_GRADE');
assert.equal(admission.evidenceKind,'ACTUAL_NATIVE_STATIC_PROBE');assert.equal(admission.surveyAdmissionModified,false);
assert.deepEqual(admission.output,[1080,1920]);
assert.ok(Array.isArray(admission.samples)&&admission.samples.length>=3);
for(const sample of admission.samples){
 assert.equal(sample.visual,'VISUAL_PASS');assert.ok(/^[a-f0-9]{64}$/.test(sample.pngSha256));
 assert.ok(Number.isSafeInteger(sample.frame)&&sample.frame>=0&&sample.frame<150);
}
assert.equal(admission.cameraKeyframeBinding,JSON.stringify(scene.cameraKeyframes));
assert.equal(fixture.checkpoints.length,5);
const checkpointNames=new Set(),checks=new Map();
for(const checkpoint of fixture.checkpoints){
 assert.ok(Number.isSafeInteger(checkpoint.frame)&&checkpoint.frame>=0&&checkpoint.frame<150);
 assert.ok(typeof checkpoint.name==='string'&&/^[A-Z0-9_]+\.png$/i.test(checkpoint.name));
 assert.ok(!checkpointNames.has(checkpoint.name));checkpointNames.add(checkpoint.name);
 const names=checks.get(checkpoint.frame)??[];names.push(checkpoint.name);checks.set(checkpoint.frame,names);
}
const inputFiles=[
 'web/map_infographic_v1/territory_control_adapter_v1.mjs',
 'web/map_infographic_v1/reference_camera_adapter_v1.mjs',
 'web/map_infographic_v1/territory_control_gpu_adapter_v1.mjs',
 'recovery/reference-reproduction-v1/reference_runtime.mjs',
 'recovery/reference-reproduction-v1/probe_native.mjs',
 'recovery/reference-reproduction-v1/render_proof.mjs',
 'recovery/reference-reproduction-v1/fixtures/SCENE_PLAN.json',
 'recovery/reference-reproduction-v1/fixtures/RUNTIME_FIXTURE.json',
 'recovery/reference-reproduction-v1/evidence/VISUAL_ADMISSION.json',
 ...Object.values(fixture.nativeFiles)
];
for(const sample of admission.samples){
 const file=String(sample.frame).padStart(3,'0')+'.png',relative='recovery/reference-reproduction-v1/evidence/native_probe/'+file;
 assert.equal(sha(await readFile(path.join(engine,relative))),sample.pngSha256);
 inputFiles.push(relative);
}
const sourceBindings=[];
for(const file of [...new Set(inputFiles)]){
 assert.ok(typeof file==='string'&&!path.isAbsolute(file)&&!file.split(/[\\/]/).some(part=>!part||part==='.'||part==='..'));
 const relative='world-simulation-shorts-engine/'+file,bytes=await readFile(path.join(engine,file)),
  saved=await execute('git',['show',sourceCommit+':'+relative],{cwd:repo,encoding:'buffer',maxBuffer:16*1024*1024});
 assert.deepEqual(saved.stdout,bytes,'UNSAVED_REFERENCE_RENDER_INPUT '+relative);
 sourceBindings.push({path:relative,sha256:sha(bytes),bytes:bytes.length});
}
const assertInputsUnchanged=async()=>{
 for(const source of sourceBindings)assert.equal(sha(await readFile(path.join(repo,source.path))),source.sha256,
  'REFERENCE_RENDER_INPUT_MUTATION '+source.path);
};
const signature=sha(Buffer.from(JSON.stringify({sourceCommit,sourceBindings}))),
 cache=path.join(repo,'../.onboarding/reference-reproduction-v1',signature),
 framesDir=path.join(cache,'frames'),rowsDir=path.join(cache,'rows'),
 publicDir=path.join(root,'public-review'),proofDir=path.join(root,'evidence/proof'),checkpointDir=path.join(proofDir,'checkpoints');
await Promise.all([mkdir(framesDir,{recursive:true}),mkdir(rowsDir,{recursive:true}),
 mkdir(publicDir,{recursive:true}),mkdir(checkpointDir,{recursive:true})]);
const priorReport=await exists(path.join(proofDir,'REPORT.json'))?await json(path.join(proofDir,'REPORT.json')):null;
const lockPath=path.join(cache,'ACTIVE_CAPTURE_LOCK.json');
if(await exists(lockPath)){
 const lock=await json(lockPath);let running=false;try{process.kill(lock.pid,0);running=true;}catch{}
 if(running)throw Error('REFERENCE_CAPTURE_ALREADY_RUNNING_PID_'+lock.pid);
 await rename(lockPath,path.join(cache,'STALE_LOCK_'+lock.pid+'_'+Date.now()+'.json'));
}
const lock=await open(lockPath,'wx');await lock.writeFile(encode({pid:process.pid,sourceCommit,signature}));await lock.close();
const resumeCommand='node recovery/reference-reproduction-v1/render_proof.mjs --source-commit='+sourceCommit;
const report={schema:'REFERENCE_REPRODUCTION_NATIVE_PROOF_V1',state:'REFERENCE_REPRODUCTION_5S_CANDIDATE',status:'IN_PROGRESS',
 sourceCommit,sourceBindings,startedAtUtc:new Date().toISOString(),output:[1080,1920],width:1080,height:1920,
 totalFrames:150,fps:30,durationSeconds:5,audio:false,reference:scene.metadata,
 scene:{file:'SCENE_PLAN.json',sha256:sha(sceneBytes),bytes:sceneBytes.length},
 frames:[],checkpoints:[],visualAdmission:admission,
 protectionSemantic:'BACKGROUND_MATERIAL_BEFORE_UNCHANGED_FOREGROUND',
 translucentEdgePixelIdentityClaimed:false,backgroundOutsideSafeAreaIsExpected:true,
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
   row=await json(rowPath);bytes=await readFile(framePath);
   assert.equal(row.signature,signature);assert.equal(row.sourceCommit,sourceCommit);
   assert.equal(row.frame,frame);assert.equal(row.png_sha256,sha(bytes));
   assertReferenceDiagnostic(row.diagnostic,{frame,protect:true});report.resume.reusedFrames++;
  }else{
   if(await exists(framePath))await rename(framePath,path.join(cache,'ORPHAN_FRAME_'+name+'_'+Date.now()+'.png'));
   if(await exists(rowPath))await rename(rowPath,path.join(cache,'ORPHAN_ROW_'+name+'_'+Date.now()+'.json'));
   if(!session){
    session=await openReferenceRuntime({mode:'VISUAL_REFERENCE_STUDY'});
    assert.equal(session.info.productionEligible,true);
    assert.equal(session.info.cameraMotion.status,'PASS');assert.equal(session.info.cameraMotion.fakeLockCount,0);
    if(report.runtimeSourceSignature)assert.equal(session.sourceSignature,report.runtimeSourceSignature);
    report.runtime=session.info;report.runtimeSourceSignature=session.sourceSignature;
    await atomic(contextFile,{signature,sourceCommit,runtime:session.info,runtimeSourceSignature:session.sourceSignature});
   }
   const captured=await session.page.evaluate(frame=>window.referenceProof.capture(frame,{protect:true,png:true}),frame),
    d=assertReferenceDiagnostic(captured.diagnostic,{frame,protect:true});
   assert.equal(d.visualAdmission.productionEligible,true);
   bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   row={frame,signature,sourceCommit,raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,
    cameraBounds:d.camera.camera.flatBounds,cameraLocked:false,control:d.territory.controls,
    protection:d.protection,glError:d.gpu.glError,nativeDrawCount:d.gpu.nativeDrawCount,
    layoutValidation:d.gpu.layoutValidation,protectedGraphics:d.protectedGraphics,diagnostic:d};
   await writeFile(framePath,bytes,{flag:'wx'});await atomic(rowPath,row);
  }
  assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  for(const file of checks.get(frame)??[]){
   const target=path.join(checkpointDir,file);
   if(await exists(target))assert.deepEqual(await readFile(target),bytes);else await writeFile(target,bytes,{flag:'wx'});
   report.checkpoints.push({file,path:'evidence/proof/checkpoints/'+file,frame,sha256:sha(bytes),bytes:bytes.length,
    originalNativeCapture:true,public:false});
  }
  report.frames.push(row);report.resume.capturedFrames=frame+1;
  if(frame%30===0||frame===149){
   await atomic(path.join(proofDir,'CAPTURE_STATUS.json'),{status:frame===149?'NATIVE_FRAMES_PASS':'IN_PROGRESS',
    sourceCommit,signature,capturedFrames:frame+1,totalFrames:150,lastFrame:frame,resumeCommand,
    requiredTempOnlyFiles:0,partialAlphaForegroundPixelChangesExpected:true});
   console.log(JSON.stringify({phase:'REFERENCE_NATIVE_CAPTURE',frame,total:150,reused:report.resume.reusedFrames}));
  }
 }
 assert.equal(session?.errors.length??0,0);await session?.close();session=null;
 await assertInputsUnchanged();
 const video=path.join(publicDir,fixture.videoFilename),encodingReceipt=path.join(cache,'ORIGINAL_ENCODING_RECEIPT.json');
 if(!await exists(video)){
  const partial=path.join(cache,'ORIGINAL_CANDIDATE_ENCODING.mp4');
  if(await exists(partial))await rename(partial,path.join(cache,'INCOMPLETE_ENCODING_'+Date.now()+'.mp4'));
  const args=['-hide_banner','-loglevel','error','-nostdin','-framerate','30','-start_number','0','-threads','2',
   '-i',path.join(framesDir,'%03d.png'),'-frames:v','150','-an','-c:v','libx264','-preset','fast','-crf','16',
   '-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',partial];
  report.encodeCommand=['ffmpeg',...args];await execute('ffmpeg',args,{maxBuffer:8*1024*1024});
  const bytes=await readFile(partial);
  await atomic(encodingReceipt,{signature,sourceCommit,sha256:sha(bytes),bytes:bytes.length,command:report.encodeCommand});
  await rename(partial,video);
 }else{
  const bytes=await readFile(video);
  if(await exists(encodingReceipt)){
   const receipt=await json(encodingReceipt);
   assert.equal(receipt.signature,signature);assert.equal(receipt.sourceCommit,sourceCommit);
   assert.equal(receipt.sha256,sha(bytes));assert.equal(receipt.bytes,bytes.length);
  }else{
   // A clean checkout may retain the original committed proof without the disposable frame cache.
   assert.equal(priorReport?.status,'PASS');assert.equal(priorReport.sourceCommit,sourceCommit);
   assert.equal(priorReport.resume.signature,signature);assert.deepEqual(priorReport.sourceBindings,sourceBindings);
   assert.equal(priorReport.video.file,fixture.videoFilename);assert.equal(priorReport.video.sha256,sha(bytes));
   assert.equal(priorReport.video.bytes,bytes.length);
  }
  report.encodeCommand=['PRESERVED_VERIFIED_COMPLETE_ORIGINAL_CANDIDATE_NO_REENCODE'];
 }
 report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video])).stdout);
 const stream=report.ffprobe.streams[0];assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.codec_name,'h264');
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_read_frames),150);assert.equal(Number(stream.duration),5);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 const videoBytes=await readFile(video);report.video={file:fixture.videoFilename,sha256:sha(videoBytes),bytes:videoBytes.length};
 const sceneExport=path.join(publicDir,'SCENE_PLAN.json');
 if(await exists(sceneExport))assert.deepEqual(await readFile(sceneExport),sceneBytes);else await writeFile(sceneExport,sceneBytes,{flag:'wx'});
 // The comparison producer later adds only authorized reference-comparison figures.
 const sums=[report.video,report.scene].sort((a,b)=>a.file.localeCompare(b.file)),
  body=sums.map(item=>item.sha256+'  '+item.file).join('\n')+'\n',sumsPath=path.join(publicDir,'SHA256SUMS');
 if(await exists(sumsPath))assert.equal(await readFile(sumsPath,'utf8'),body);else await writeFile(sumsPath,body,{flag:'wx'});
 await assertInputsUnchanged();
 const unexpected=['protectedChangedPixels','markerChangedPixels','textChangedPixels','outsideRoiChangedPixels',
  'safeAreaChangedPixels','protectedBoundaryChangedPixels'],expected=['backgroundOutsideSafeAreaChangedPixels',
  'partialAlphaForegroundChangedPixels','transparentReservationBackgroundChangedPixels'];
 report.protection={checkedFrames:150,semantic:report.protectionSemantic,geometryUnchanged:true,
  opaqueForegroundAndSupportPreserved:true,sourceForegroundAndProjectionUnchanged:true,
  allForegroundPixelsIdenticalClaimed:false,
  critical:Object.fromEntries(unexpected.map(key=>[key,Math.max(...report.frames.map(row=>row.protection[key]))])),
  expectedBackgroundDependent:Object.fromEntries(expected.map(key=>[key,{maximum:Math.max(...report.frames.map(row=>row.protection[key])),
   sum:report.frames.reduce((total,row)=>total+row.protection[key],0)}]))};
 report.decodeValidation='PASS';report.status='PASS';
}catch(error){failure=error;report.status='BLOCKED';report.error=error.stack;
}finally{
 try{await session?.close();}catch(error){failure??=error;report.status='BLOCKED';report.error??=error.stack;}
 report.completedAtUtc=new Date().toISOString();
 try{await atomic(path.join(proofDir,'REPORT.json'),report);}finally{await unlink(lockPath);}
}
if(failure)throw failure;
console.log(JSON.stringify({status:report.status,frames:report.frames.length,video:report.video,
 checkpoints:report.checkpoints.length,reusedFrames:report.resume.reusedFrames,fullVisualReviewClaimed:false}));
