/** Restore execution, not visuals: call the unchanged original runtime in an isolated source capsule. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {readFile,writeFile,mkdir,rename,open,unlink,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile), root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const options=Object.fromEntries(process.argv.slice(2).map(x=>{const m=/^--(capsule|original-report|cache)=(.+)$/.exec(x);if(!m)throw Error('UNKNOWN_ARGUMENT');return [m[1],m[2]];}));
for(const key of ['capsule','original-report','cache'])assert.ok(options[key],key+' required');
const capsule=path.resolve(options.capsule), cache=path.resolve(options.cache);
const repoRoot=path.resolve(root,'../../..');
const inside=(child,parent)=>child===parent||child.startsWith(parent+path.sep);
assert.equal(inside(capsule,repoRoot),false,'SOURCE_CAPSULE_MUST_BE_INDEPENDENT');
assert.equal(inside(cache,repoRoot)||inside(cache,capsule)||cache.split(path.sep).includes('.onboarding'),false,'CACHE_MUST_NOT_USE_PROTECTED_REPO_CAPSULE_OR_OLD_ONBOARDING');
const originalBytes=await readFile(options['original-report']);
assert.equal(createHash('sha256').update(originalBytes).digest('hex'),'550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656','ORIGINAL_REPORT_HASH_REQUIRED');
const original=JSON.parse(originalBytes);
assert.equal(original.sourceCommit,'2c097df2d02432a3f9ae4dae5d714dbc9eacd434');
assert.equal(original.frames.length,150);
const hash=x=>createHash('sha256').update(x).digest('hex');
const readJSON=async f=>JSON.parse(await readFile(f,'utf8'));
const exists=async f=>stat(f).then(()=>true,()=>false);
const atomic=async(f,x)=>{await writeFile(f+'.writing',JSON.stringify(x)+'\n');await rename(f+'.writing',f);};
const verifySources=async()=>{for(const item of original.sourceBindings){const bytes=await readFile(path.join(capsule,item.path));assert.equal(hash(bytes),item.sha256,item.path);assert.equal(bytes.length,item.bytes);}};
await verifySources();
await Promise.all([mkdir(path.join(root,'proof'),{recursive:true}),mkdir(path.join(root,'public-review'),{recursive:true})]);
assert.equal(await exists(path.join(root,'public-review/WORLD_ENGINE_65422_EXACT_REPRODUCTION_5S.mp4')),false,'REFUSE_RENDER_WHEN_COMPLETE_VIDEO_ALREADY_EXISTS');
const framesDir=path.join(cache,'frames'), rowsDir=path.join(cache,'rows');
await Promise.all([mkdir(framesDir,{recursive:true}),mkdir(rowsDir,{recursive:true})]);
const lockPath=path.join(cache,'ACTIVE_CAPTURE.json');
const lock=await open(lockPath,'wx');await lock.writeFile(JSON.stringify({pid:process.pid,startedAt:new Date().toISOString()})+'\n');await lock.close();
const runtimeFile=path.join(capsule,'world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs');
const {openQualityRuntime,assertQualityDiagnostic}=await import(pathToFileURL(runtimeFile));
const fixture=await readJSON(path.join(capsule,'world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json'));
const report={schema:'EXACT_65422_REPRODUCTION_CAPTURE_V1',status:'IN_PROGRESS',sourceCommit:original.sourceCommit,
 originalReportSha256:hash(await readFile(options['original-report'])),originalCaptureSignature:original.resume.signature,
 originalRuntimeSourceSignature:original.runtimeSourceSignature,sourceBindings:original.sourceBindings,
 captureKind:'NEW_RENDER_FROM_UNCHANGED_ORIGINAL_RUNTIME',backendKind:'SWIFTSHADER_SOFTWARE',nvidiaVerified:false,
 width:1080,height:1920,fps:30,totalFrames:150,durationSeconds:5,audio:false,
 startedAtUtc:new Date().toISOString(),frames:[],checkpoints:[],reusedFrames:0,newlyRenderedFrames:0,
 originalVideoReused:false,oldCacheReused:false,finalPromotion:false,paidGpuExecuted:false};
let session,failed;const started=performance.now();
try{
 session=await openQualityRuntime({mode:'VISUAL_REFERENCE_STUDY'});
 report.runtime=session.info;report.runtimeSourceSignature=session.sourceSignature;
 assert.equal(session.sourceSignature,original.runtimeSourceSignature,'ORIGINAL_RUNTIME_SOURCE_SIGNATURE_MISMATCH');
 assert.equal(session.info.productionEligible,true);assert.equal(session.info.cameraMotion.status,'PASS');assert.equal(session.info.cameraMotion.fakeLockCount,0);
 for(let frame=0;frame<150;frame++){
  const name=String(frame).padStart(3,'0'),rowFile=path.join(rowsDir,name+'.json'),pngFile=path.join(framesDir,name+'.png');
  let row,bytes;
  if(await exists(rowFile)&&await exists(pngFile)){
   row=await readJSON(rowFile);bytes=await readFile(pngFile);
   assert.equal(row.frame,frame);assert.equal(row.sourceCommit,original.sourceCommit);
   assert.equal(row.png_sha256,hash(bytes));assert.equal(row.runtimeSourceSignature,session.sourceSignature);
   assertQualityDiagnostic(row.diagnostic,{frame});report.reusedFrames++;
  }else{
   assert.equal(await exists(rowFile),false,'ORPHAN_ROW_REQUIRES_REVIEW');assert.equal(await exists(pngFile),false,'ORPHAN_PNG_REQUIRES_REVIEW');
   const captureStarted=performance.now();
   const captured=await session.page.evaluate(async f=>window.referenceProof.capture(f,{png:true}),frame);
   const d=assertQualityDiagnostic(captured.diagnostic,{frame});
   bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(hash(bytes),captured.png_sha256);
   row={frame,sourceCommit:original.sourceCommit,runtimeSourceSignature:session.sourceSignature,
    raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,
    cameraBounds:d.camera.bounds??d.camera.camera?.flatBounds??d.camera.flatBounds,
    rotationDegrees:d.camera.rotationDegrees,control:d.territory.controls,
    protection:d.protection,presentation:d.presentation,units:d.units,
    captureWallMilliseconds:performance.now()-captureStarted,diagnostic:d};
   await writeFile(pngFile,bytes,{flag:'wx'});await atomic(rowFile,row);report.newlyRenderedFrames++;
  }
  assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
  row.originalRawRgbaEqual=row.raw_rgba_sha256===original.frames[frame].raw_rgba_sha256;
  row.originalPngEqual=row.png_sha256===original.frames[frame].png_sha256;
  if(!row.originalRawRgbaEqual&&report.firstRawDivergentFrame===undefined)report.firstRawDivergentFrame=frame;
  report.frames.push(row);
  for(const checkpoint of fixture.checkpoints.filter(x=>x.frame===frame)){
   const file=String(report.checkpoints.length+1).padStart(2,'0')+'_'+checkpoint.name;
   const checkpointPath=path.join(root,'public-review',file);
   if(await exists(checkpointPath))assert.deepEqual(await readFile(checkpointPath),bytes,'CHECKPOINT_REUSE_HASH_REQUIRED');
   else await writeFile(checkpointPath,bytes,{flag:'wx'});
   report.checkpoints.push({file,frame,sha256:hash(bytes),bytes:bytes.length});
  }
  if(frame%15===0||frame===149){
   await atomic(path.join(root,'proof/CAPTURE_STATUS.json'),{status:'CAPTURING',lastFrame:frame,captured:report.frames.length,rawEqual:report.frames.every(x=>x.originalRawRgbaEqual)});
   console.log(JSON.stringify({frame,total:150,rawEqual:row.originalRawRgbaEqual,pngEqual:row.originalPngEqual}));
  }
 }
 assert.equal(session.errors.length,0);await session.close();session=null;await verifySources();
 const video=path.join(root,'public-review/WORLD_ENGINE_65422_EXACT_REPRODUCTION_5S.mp4');
 assert.equal(await exists(video),false,'REFUSE_EXISTING_VIDEO_OVERWRITE');
 const args=['-hide_banner','-loglevel','error','-nostdin','-framerate','30','-start_number','0','-threads','2',
  '-i',path.join(framesDir,'%03d.png'),'-frames:v','150','-an','-c:v','libx264','-preset','fast','-crf','16','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',video];
 report.encodeCommand=['ffmpeg',...args];await execute('ffmpeg',args,{maxBuffer:8*1024*1024});
 const videoBytes=await readFile(video);report.video={file:path.basename(video),sha256:hash(videoBytes),bytes:videoBytes.length};
 report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
 const [stream]=report.ffprobe.streams;assert.equal(report.ffprobe.streams.length,1);assert.equal(stream.codec_name,'h264');
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_frames),150);assert.equal(Number(stream.duration),5);
 await execute('ffmpeg',['-v','error','-nostdin','-i',video,'-f','null','-'],{maxBuffer:1024*1024});
 report.rawRgbaEqualFrames=report.frames.filter(x=>x.originalRawRgbaEqual).length;
 report.pngEqualFrames=report.frames.filter(x=>x.originalPngEqual).length;
 report.status='CAPTURE_AND_ENCODE_PASS_COMPARISON_REQUIRED';
 await atomic(path.join(root,'proof/CAPTURE_STATUS.json'),{status:report.status,totalFrames:150,newlyRenderedFrames:report.newlyRenderedFrames,reusedFrames:report.reusedFrames,rawRgbaEqualFrames:report.rawRgbaEqualFrames,pngEqualFrames:report.pngEqualFrames});
}catch(e){failed=e;report.status='FAIL';report.error=String(e.stack);}
finally{
 try{await session?.close();}catch(e){failed??=e;report.closeError=String(e.stack);}
 report.completedAtUtc=new Date().toISOString();report.wallSeconds=(performance.now()-started)/1000;
 await atomic(path.join(root,'proof/CAPTURE_REPORT.json'),report);await unlink(lockPath);
}
if(failed)throw failed;
console.log(JSON.stringify({status:report.status,frames:report.frames.length,rawEqualFrames:report.rawRgbaEqualFrames,pngEqualFrames:report.pngEqualFrames,video:report.video,seconds:report.wallSeconds}));
