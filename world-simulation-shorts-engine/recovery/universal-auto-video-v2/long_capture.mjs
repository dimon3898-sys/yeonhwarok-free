/** Bounded scene capture. Native rendering, ASTRA, H.264 settings and NVIDIA
 * admission are reused; the caller owns the existing common GPU lease. */
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile,open,lstat,readdir,rename,unlink,rmdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {createInterface} from 'node:readline';
import {originalEncodingArgs} from '../rtx-gpu-package-v1/hardware_render.mjs';
import {loadLongRuntimePlan,openLongRuntime,sha} from './long_runtime.mjs';
const execute=promisify(execFile),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
export function validateCaptureRange({startFrame,endFrame,totalFrames,fps}){
 assert.ok(Number.isSafeInteger(totalFrames)&&totalFrames>0&&Number.isSafeInteger(fps)&&fps>0,'LONG_COMPLETE_TIMELINE_REQUIRED');
 assert.ok(Number.isSafeInteger(startFrame)&&Number.isSafeInteger(endFrame)&&startFrame>=0
  &&startFrame<endFrame&&endFrame<=totalFrames,'LONG_GLOBAL_HALF_OPEN_RANGE_REQUIRED');
 return {startFrame,endFrame,totalFrames,fps,frameCount:endFrame-startFrame};
}
/** Preserve the existing encoder's codec, quality, threads and pix_fmt. Only
 * image numbering, FPS and exact frame limit differ with the supplied range. */
export function longEncodingArgs({framesDirectory,outputFile,frameCount,fps}){
 validateCaptureRange({startFrame:0,endFrame:frameCount,totalFrames:frameCount,fps});
 const args=originalEncodingArgs(framesDirectory,outputFile);
 args[args.indexOf('-framerate')+1]=String(fps);args[args.indexOf('-i')+1]=path.join(framesDirectory,'%06d.png');
 args[args.indexOf('-frames:v')+1]=String(frameCount);return args;
}
export function assertCapturedLongFrame(captured,frame,binding,{production=true}={}){
 const d=captured?.diagnostic,u=d?.universalVideo;
 assert.ok(hex(captured?.raw_rgba_sha256)&&hex(captured?.png_sha256),'LONG_FRAME_HASH_REQUIRED');
 assert.equal(d?.frame,frame,'LONG_GLOBAL_FRAME_BINDING_REQUIRED');
 for(const key of ['planSha256','legacySceneSha256','sceneRangeSha256'])
  assert.ok(hex(binding[key])&&u?.[key]===binding[key],'LONG_FRAME_PROFILE_BINDING_'+key);
 assert.equal(u.globalFrame,frame,'LONG_FRAME_GLOBAL_CLOCK_REQUIRED');
 assert.equal(u.testOnly,!production,'LONG_EXPLICIT_BACKEND_PROVENANCE_REQUIRED');
 if(production){
  assert.ok(hex(binding.nativePayloadSha256)&&u.nativePayloadSha256===binding.nativePayloadSha256,'LONG_FRAME_NATIVE_PAYLOAD_BINDING_REQUIRED');
  assert.equal(d.sourceIntegrity?.actualAstraSelected,true,'LONG_ACTUAL_ASTRA_REQUIRED');
  assert.equal(d.sourceIntegrity?.fictional65422SceneUsed,false,'LONG_FICTIONAL_SCENE_FORBIDDEN');
  assert.equal(d.sourceIntegrity?.sourceBeforeAreaAndFront,true,'LONG_SOURCE_COMPOSITION_ORDER_REQUIRED');
  assert.equal(d.terrain?.astra?.actualMaterialFactorySelected,true,'LONG_ACTUAL_ASTRA_FACTORY_REQUIRED');
  assert.equal(d.terrain?.astra?.gpuUploadExecuted,true,'LONG_REAL_TEXTURE_UPLOAD_REQUIRED');
  assert.equal(d.terrain?.astra?.testOnly,false,'LONG_PRODUCTION_TEST_MATERIAL_FORBIDDEN');
  assert.equal(d.area?.geometryUnchanged,true,'LONG_SUPPLIED_AREA_GEOMETRY_REQUIRED');
 }
 assert.equal(d.glError??d.gpu?.glError,0,'LONG_FRAME_GL_ERROR');
 assert.ok(typeof captured.png==='string'&&captured.png.startsWith('data:image/png;base64,'),'LONG_PNG_REQUIRED');
 const bytes=Buffer.from(captured.png.slice('data:image/png;base64,'.length),'base64');
 assert.ok(bytes.length>=24&&bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])),'LONG_PNG_SIGNATURE_REQUIRED');
 assert.equal(bytes.readUInt32BE(16),1080,'LONG_OUTPUT_WIDTH_REQUIRED');
 assert.equal(bytes.readUInt32BE(20),1920,'LONG_OUTPUT_HEIGHT_REQUIRED');
 assert.equal(sha(bytes),captured.png_sha256,'LONG_PNG_HASH_MISMATCH');return bytes;
}
export async function hashFile(file){
 const hash=createHash('sha256');let bytes=0;
 for await(const chunk of createReadStream(file)){hash.update(chunk);bytes+=chunk.length;}
 return {sha256:hash.digest('hex'),bytes};
}
/** Capture exactly one frame at a time. No array of PNGs, pixel buffers or
 * all-frame diagnostics is retained. Partial evidence remains after failure. */
export async function captureLongFrames({captureFrame,range,binding,framesDirectory,evidenceFile,progress,
 production=true,checkpointFrames=[]}){
 const checked=validateCaptureRange(range),names=new Set(checkpointFrames);
 assert.ok(checkpointFrames.length<=5&&checkpointFrames.every(f=>Number.isSafeInteger(f)&&f>=checked.startFrame&&f<checked.endFrame)
  &&names.size===checkpointFrames.length,'LONG_BOUNDED_CHECKPOINTS_REQUIRED');
 await mkdir(framesDirectory,{mode:0o700});const evidence=await open(evidenceFile,'wx',0o600),
  rolling=createHash('sha256'),checkpoints=[];
 let completedFrames=0,captureWallMs=0,frameWriteWallMs=0;
 try{
  for(let globalFrame=checked.startFrame;globalFrame<checked.endFrame;globalFrame++){
   const captureStarted=performance.now(),captured=await captureFrame(globalFrame),
    bytes=assertCapturedLongFrame(captured,globalFrame,binding,{production});
   captureWallMs+=performance.now()-captureStarted;
   const localFrame=globalFrame-checked.startFrame,file=String(localFrame).padStart(6,'0')+'.png',writeStarted=performance.now();
   await writeFile(path.join(framesDirectory,file),bytes,{mode:0o600,flag:'wx'});
   const row={localFrame,globalFrame,rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256,
    bytes:bytes.length,diagnostic:captured.diagnostic};
   const line=JSON.stringify(row)+'\n';rolling.update(line);await evidence.write(line);completedFrames++;
   frameWriteWallMs+=performance.now()-writeStarted;
   if(names.has(globalFrame))checkpoints.push({file,globalFrame,sha256:captured.png_sha256,bytes:bytes.length});
   if(completedFrames%checked.fps===0||completedFrames===checked.frameCount){await evidence.sync();
    progress?.({phase:'SCENE_CAPTURE',globalFrame,completedFrames,totalFrames:checked.frameCount});}
  }
  await evidence.sync();
 }finally{await evidence.close();}
 return {completedFrames,frameEvidenceSha256:rolling.digest('hex'),checkpoints,
  timings:{captureDrawReadbackPngWallMs:captureWallMs,frameWriteWallMs},
  boundedMemory:{simultaneousCapturedFrames:1,allFrameDiagnosticsInMemory:false,encodedFileStreamHashed:true}};
}
/** Delete only receipt-bound new intermediate PNGs after a verified MP4.
 * Source hashes, receipts, copied checkpoints and older jobs are never removed. */
export async function cleanupEncodedFrames({framesDirectory,evidenceFile,frameCount}){
 assert.ok(Number.isSafeInteger(frameCount)&&frameCount>0,'LONG_CLEANUP_FRAME_COUNT_REQUIRED');
 const attrs=await lstat(framesDirectory);assert.ok(attrs.isDirectory()&&!attrs.isSymbolicLink(),'LONG_CLEANUP_OWN_DIRECTORY_REQUIRED');
 const lines=createInterface({input:createReadStream(evidenceFile),crlfDelay:Infinity});let count=0;
 try{for await(const line of lines){
  const row=JSON.parse(line);assert.equal(row.localFrame,count,'LONG_CLEANUP_ORDERED_RECEIPTS_REQUIRED');
  assert.ok(count<frameCount&&hex(row.pngSha256),'LONG_CLEANUP_BOUND_RECEIPT_REQUIRED');
  const name=String(count).padStart(6,'0')+'.png',file=path.join(framesDirectory,name),stat=await lstat(file);
  assert.ok(stat.isFile()&&!stat.isSymbolicLink(),'LONG_CLEANUP_REGULAR_FRAME_REQUIRED');
  const actual=await hashFile(file);assert.equal(actual.sha256,row.pngSha256,'LONG_CLEANUP_CHANGED_FRAME_REFUSED');
  assert.equal(actual.bytes,row.bytes,'LONG_CLEANUP_CHANGED_FRAME_SIZE_REFUSED');await unlink(file);count++;
 }}finally{lines.close();}
 assert.equal(count,frameCount,'LONG_CLEANUP_COMPLETE_RECEIPT_REQUIRED');
 assert.equal((await readdir(framesDirectory)).length,0,'LONG_CLEANUP_UNEXPECTED_FILE_PRESERVED');await rmdir(framesDirectory);
 return {removedOwnIntermediateFrames:count,existingResultsDeleted:0,method:'EXACT_CREATED_FRAME_RECEIPT_SHA_ONLY_AFTER_VERIFIED_MP4'};
}
export function assertEncodedSegment(probe,range){
 const checked=validateCaptureRange(range);assert.ok(probe&&Array.isArray(probe.streams));
 assert.equal(probe.streams.length,1,'LONG_SILENT_VIDEO_ONLY_REQUIRED');const stream=probe.streams[0];
 assert.equal(stream.codec_name,'h264');assert.equal(stream.width,1080);assert.equal(stream.height,1920);
 assert.equal(stream.avg_frame_rate,String(checked.fps)+'/1');assert.equal(Number(stream.nb_frames),checked.frameCount);
 assert.ok(Math.abs(Number(stream.duration)-checked.frameCount/checked.fps)<=.001,'LONG_SEGMENT_DURATION_MISMATCH');return true;
}
const codeOf=error=>/^[A-Z][A-Z0-9_]{2,95}$/.test(error?.message??'')?error.message:'LONG_CAPTURE_FAILED';
async function privateEmptyDirectory(directory){
 assert.ok(typeof directory==='string'&&path.isAbsolute(directory)&&path.resolve(directory)===directory,'LONG_CANONICAL_OUTPUT_REQUIRED');
 let current=path.parse(directory).root;
 for(const part of directory.slice(current.length).split(path.sep)){
  current=path.join(current,part);try{assert.ok(!(await lstat(current)).isSymbolicLink(),'LONG_OUTPUT_SYMLINK_FORBIDDEN');}
  catch(error){if(error.code!=='ENOENT')throw error;}
 }
 await mkdir(directory,{recursive:true,mode:0o700});const attrs=await lstat(directory);
 assert.ok(attrs.isDirectory()&&(attrs.mode&0o077)===0,'LONG_PRIVATE_OUTPUT_REQUIRED');
 assert.equal((await readdir(directory)).length,0,'LONG_OUTPUT_EXISTS_REQUIRES_REVIEW');
}
export async function captureLongScene(options){
 const started=performance.now(),plan=await loadLongRuntimePlan(options),outputRoot=options.outputRoot;
 assert.ok(!path.resolve(outputRoot).startsWith(path.resolve(plan.repo)+path.sep),'LONG_SOURCE_TREE_OUTPUT_FORBIDDEN');
 await privateEmptyDirectory(outputRoot);
 const report={schema:'WORLD_ENGINE_LONG_SCENE_CAPTURE_V2',status:'IN_PROGRESS',sceneId:plan.scene.sceneId,
  startFrame:plan.scene.startFrame,endFrame:plan.scene.endFrame,totalFrames:plan.scene.endFrame-plan.scene.startFrame,
  fps:plan.document.fps,planSha256:plan.planSha256,legacySceneSha256:plan.legacySceneSha256,
  sceneRangeSha256:plan.sceneRangeSha256,sourceSignature:plan.sourceSignature,hardwareVerified:false,
  gpuVisualQualityVerified:false,finalPromotion:false,startedAt:new Date().toISOString()};
 let runtime,error,pendingCleanup,aborted=false;const stop=()=>{aborted=true;void Promise.resolve().then(()=>runtime?runtime.close():pendingCleanup?.()).catch(()=>{});};
 process.once('SIGTERM',stop);process.once('SIGINT',stop);
 try{
  const openStarted=performance.now();runtime=await openLongRuntime({...options,loadedPlan:plan,onPendingCleanup:cleanup=>{pendingCleanup=cleanup;}});
  if(aborted)throw Error('LONG_CAPTURE_INTERRUPTED');
  report.runtimeInitializationWallMs=performance.now()-openStarted;
  report.hardwareVerified=true;report.backend=runtime.info.backend;
  const range={startFrame:plan.scene.startFrame,endFrame:plan.scene.endFrame,totalFrames:plan.document.totalFrames,fps:plan.document.fps};
  const result=await captureLongFrames({captureFrame:async frame=>{
   if(aborted)throw Error('LONG_CAPTURE_INTERRUPTED');
   return runtime.page.evaluate(async frame=>window.longVideoProof.capture(frame,{png:true}),frame);
  },range,binding:plan,framesDirectory:path.join(outputRoot,'frames'),evidenceFile:path.join(outputRoot,'FRAMES.ndjson'),
   checkpointFrames:[...new Set([range.startFrame,Math.floor((range.startFrame+range.endFrame-1)/2),range.endFrame-1])],
   progress:value=>console.log(JSON.stringify(value))});
  Object.assign(report,result);assert.equal(runtime.errors.length,0,'LONG_BROWSER_RUNTIME_ERROR');
  await runtime.close();runtime=null;await plan.assertSourceUnchanged();
  const encodeStarted=performance.now(),partial=path.join(outputRoot,'SEGMENT_ENCODING.mp4'),video=path.join(outputRoot,'segment.mp4');
  const encoding=longEncodingArgs({framesDirectory:path.join(outputRoot,'frames'),outputFile:partial,
   frameCount:range.endFrame-range.startFrame,fps:range.fps});
  await execute('ffmpeg',encoding,{maxBuffer:1024*1024});report.encodingWallMs=performance.now()-encodeStarted;
  const probe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',partial],{maxBuffer:1024*1024})).stdout);
  assertEncodedSegment(probe,range);
  const decodeStarted=performance.now();await execute('ffmpeg',['-hide_banner','-v','error','-xerror','-nostdin','-i',partial,'-f','null','-'],{maxBuffer:1024*1024});
  report.decodeVerificationWallMs=performance.now()-decodeStarted;
  await rename(partial,video);report.video={path:video,...await hashFile(video)};report.ffprobe=probe;
  const checkpointDirectory=path.join(outputRoot,'checkpoints');await mkdir(checkpointDirectory,{mode:0o700});
  const preserved=[];
  for(const checkpoint of report.checkpoints){
   const bytes=await readFile(path.join(outputRoot,'frames',checkpoint.file));assert.equal(sha(bytes),checkpoint.sha256,'LONG_CHECKPOINT_SHA_MISMATCH');
   const name=String(checkpoint.globalFrame).padStart(6,'0')+'.png';await writeFile(path.join(checkpointDirectory,name),bytes,{flag:'wx',mode:0o600});
   preserved.push({...checkpoint,file:'checkpoints/'+name});
  }
  report.checkpoints=preserved;report.cleanup=await cleanupEncodedFrames({framesDirectory:path.join(outputRoot,'frames'),
   evidenceFile:path.join(outputRoot,'FRAMES.ndjson'),frameCount:report.completedFrames});
  await writeFile(path.join(outputRoot,'SHA256SUMS'),report.video.sha256+'  segment.mp4\n',{flag:'wx',mode:0o600});
  await plan.assertSourceUnchanged();report.status='SCENE_TECHNICAL_PASS';
  await writeFile(path.join(outputRoot,'SEGMENT_COMPLETE.json'),JSON.stringify({schema:'WORLD_ENGINE_LONG_SEGMENT_COMPLETE_V2',
   sceneId:report.sceneId,startFrame:range.startFrame,endFrame:range.endFrame,path:'segment.mp4',sha256:report.video.sha256,
   bytes:report.video.bytes,planSha256:plan.planSha256,sceneRangeSha256:plan.sceneRangeSha256,hardwareVerified:true,
   ffprobe:report.ffprobe,fullDecodeVerified:true,visualQualityVerified:false})+'\n',{flag:'wx',mode:0o600});
 }catch(failure){error=failure;report.status='BLOCKED';report.errorCode=codeOf(failure);}
 finally{
  try{await runtime?.close();}catch(failure){error??=failure;report.status='BLOCKED';report.errorCode??=codeOf(failure);}
  report.completedAt=new Date().toISOString();report.totalWallMs=performance.now()-started;
  await writeFile(path.join(outputRoot,'SCENE_RECEIPT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
  process.removeListener('SIGTERM',stop);process.removeListener('SIGINT',stop);
 }
 if(error)throw error;return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const args=process.argv.slice(2),options={},mapping={'--plan-file':'planFile','--plan-sha256':'expectedPlanSha256',
  '--scene-id':'sceneId','--admission-file':'admissionFile','--output-root':'outputRoot'};
 while(args.length){const flag=args.shift();assert.ok(mapping[flag]&&args.length&&!Object.hasOwn(options,mapping[flag]),'LONG_EXPLICIT_ARGUMENT_REQUIRED');options[mapping[flag]]=args.shift();}
 const report=await captureLongScene(options);console.log(JSON.stringify({status:report.status,path:report.video.path,
  sha256:report.video.sha256,sceneId:report.sceneId,hardwareVerified:true,visualQualityVerified:false}));
 }catch(error){console.error(JSON.stringify({schema:'WORLD_ENGINE_LONG_CAPTURE_FAILURE_V2',status:'BLOCKED',errorCode:codeOf(error),
  visualQualityVerified:false}));process.exitCode=2;}
}
