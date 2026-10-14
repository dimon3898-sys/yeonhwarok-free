/** Isolated hardware capture. Original renderer, geometry, timeline and encoder stay unchanged. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile,rename,unlink,open,stat,readdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {openHardwareRuntime,readAdmission,assertQualityDiagnostic,root,repo,packageRoot,json,sha,movieName} from './hardware_runtime.mjs';
const execute=promisify(execFile),exists=async file=>stat(file).then(()=>true,()=>false);
const atomic=async(file,value)=>{const pending=file+'.writing';await writeFile(pending,JSON.stringify(value)+'\n',{mode:0o600});await rename(pending,file);};

export async function processIdentity(pid=process.pid){
 assert.ok(Number.isSafeInteger(pid)&&pid>0,'VALID_CAPTURE_PID_REQUIRED');
 const bootId=(await readFile('/proc/sys/kernel/random/boot_id','utf8')).trim();
 const state=await readFile('/proc/'+pid+'/stat','utf8'),fields=state.slice(state.lastIndexOf(')')+2).trim().split(/\s+/);
 assert.ok(fields.length>=20&&/^\d+$/.test(fields[19]),'PROCESS_START_ID_REQUIRED');
 return {pid,bootId,startTime:fields[19]};
}
export async function isActiveCapture(lock,identity=processIdentity){
 if(!Number.isSafeInteger(lock?.pid)||lock.pid<=0||typeof lock.bootId!=='string'||typeof lock.startTime!=='string')return false;
 try{const actual=await identity(lock.pid);return actual.bootId===lock.bootId&&actual.startTime===lock.startTime;}
 catch(error){if(error.code==='ENOENT'||error.code==='ESRCH')return false;throw error;}
}

// These are the exact encoding arguments of the approved original capture.
// Only frame directory and new output file differ; neither original MP4 nor source is overwritten.
export function originalEncodingArgs(framesDir,partial){
 return ['-hide_banner','-loglevel','error','-nostdin','-framerate','30','-start_number','0','-threads','2',
  '-i',path.join(framesDir,'%03d.png'),'-frames:v','150','-an','-c:v','libx264','-preset','fast','-crf','16',
  '-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',partial];
}

export async function captureHardware({admissionFile,outputRoot}){
 assert.ok(typeof outputRoot==='string'&&path.isAbsolute(outputRoot),'PERSISTENT_ABSOLUTE_OUTPUT_REQUIRED');
 // Direct invocation must also fail closed, even when every PNG is already cached.
 const admission=await readAdmission(admissionFile),stagedRoot=path.dirname(repo);
 const verify=async()=>JSON.parse((await execute('/usr/bin/python3',['-B',path.join(packageRoot,'stage_package.py'),
  'verify-context','--package-root',stagedRoot],{maxBuffer:1024*1024})).stdout);
 const source=await verify();assert.equal(source.status,'PASS');
 assert.equal(source.sourceContractSha256,admission.sourceVerification.sourceContractSha256);
 const receiptBytes=await readFile(path.join(stagedRoot,'STAGING_RECEIPT.json'));
 const fixture=await json(path.join(root,'fixtures/RUNTIME_FIXTURE.json'));
 assert.equal(fixture.totalFrames,150);assert.equal(fixture.fps,30);
 const signature=sha(Buffer.from(JSON.stringify({stagingReceiptSha256:sha(receiptBytes),
  hardwareProfileFingerprint:admission.probe.profile_fingerprint,browser:admission.probe.browser_version,
  model:admission.allocation.model,driver:admission.allocation.driver_version})));
 const runRoot=path.join(outputRoot,'captures',signature),framesDir=path.join(runRoot,'frames'),
  rowsDir=path.join(runRoot,'rows'),publicDir=path.join(runRoot,'public-review');
 assert.ok(!path.resolve(runRoot).startsWith(path.resolve(repo)+path.sep),'SOURCE_TREE_OUTPUT_FORBIDDEN');
 await mkdir(runRoot,{recursive:true,mode:0o700});
 for(const dir of [framesDir,rowsDir,publicDir])await mkdir(dir,{recursive:true,mode:0o700});
 const checks=new Map(),names=new Set();
 for(const check of fixture.checkpoints){
  assert.ok(Number.isSafeInteger(check.frame)&&check.frame>=0&&check.frame<150);
  assert.ok(/^[A-Z0-9_]+\.png$/i.test(check.name)&&!names.has(check.name));names.add(check.name);
  checks.set(check.frame,[...(checks.get(check.frame)??[]),check.name]);
 }
 const lockPath=path.join(runRoot,'ACTIVE_CAPTURE_LOCK.json');
 if(await exists(lockPath)){
  const prior=await json(lockPath);
  if(await isActiveCapture(prior))throw Error('GPU_CAPTURE_ALREADY_RUNNING');
  await rename(lockPath,path.join(runRoot,'STALE_LOCK_'+Date.now()+'.json'));
 }
 const identity=await processIdentity();
 const lock=await open(lockPath,'wx',0o600);await lock.writeFile(JSON.stringify({...identity,signature})+'\n');await lock.close();
 const report={schema:'RTX_GPU_HARDWARE_CAPTURE_V1',status:'IN_PROGRESS',signature,sourceVerification:source,
  stagingReceiptSha256:sha(receiptBytes),hardware:admission.probe,frames:[],checkpoints:[],
  output:[1080,1920],totalFrames:150,fps:30,durationSeconds:5,audio:false,
  qualityParityClaimed:false,userVideoApproved:false,finalPromotion:false,requiredTempOnlyFiles:0,
  reusedFrames:0,startedAt:new Date().toISOString()};
 let session,failure,pendingCleanup;
 const terminate=()=>{const cleanup=session?()=>session.close():pendingCleanup;
  if(cleanup)Promise.resolve().then(cleanup).finally(()=>process.exit(143));else process.exit(143);};
 process.once('SIGTERM',terminate);
 try{
  // Always create and draw-test the real hardware context before reading a saved frame.
  session=await openHardwareRuntime({mode:'VISUAL_REFERENCE_STUDY',admissionFile,onPendingCleanup:cleanup=>{pendingCleanup=cleanup;}});
  assert.equal(session.info.productionEligible,true);assert.equal(session.info.cameraMotion.status,'PASS');
  assert.equal(session.info.cameraMotion.fakeLockCount,0);report.runtime=session.info;
  const fresh=await session.page.evaluate(async()=>window.referenceProof.capture(0,{png:false}));
  assertQualityDiagnostic(fresh.diagnostic,{frame:0});report.freshHardwareFrameZeroSha256=fresh.raw_rgba_sha256;
  for(let frame=0;frame<150;frame++){
   const name=String(frame).padStart(3,'0'),pngPath=path.join(framesDir,name+'.png'),rowPath=path.join(rowsDir,name+'.json');
   let bytes,row;
   if(await exists(pngPath)&&await exists(rowPath)){
    row=await json(rowPath);bytes=await readFile(pngPath);
    assert.equal(row.signature,signature);assert.equal(row.frame,frame);assert.equal(row.png_sha256,sha(bytes));
    assertQualityDiagnostic(row.diagnostic,{frame});report.reusedFrames++;
    if(frame===0)assert.equal(row.raw_rgba_sha256,fresh.raw_rgba_sha256,'SAVED_HARDWARE_FRAME_MUST_MATCH_FRESH_DRAW');
   }else{
    for(const file of [pngPath,rowPath])if(await exists(file))await rename(file,file+'.orphan-'+Date.now());
    const captured=await session.page.evaluate(async frame=>window.referenceProof.capture(frame,{png:true}),frame);
    assertQualityDiagnostic(captured.diagnostic,{frame});bytes=Buffer.from(captured.png.split(',')[1],'base64');
    assert.equal(sha(bytes),captured.png_sha256);
    row={signature,frame,raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,diagnostic:captured.diagnostic};
    await writeFile(pngPath,bytes,{flag:'wx',mode:0o600});await atomic(rowPath,row);
   }
   assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
   for(const filename of checks.get(frame)??[]){
    const target=path.join(publicDir,filename);
    if(await exists(target))assert.deepEqual(await readFile(target),bytes);else await writeFile(target,bytes,{flag:'wx',mode:0o600});
    report.checkpoints.push({file:filename,frame,sha256:sha(bytes),bytes:bytes.length});
   }
   report.frames.push(row);
   if(frame%30===0||frame===149){
    await atomic(path.join(runRoot,'CAPTURE_STATUS.json'),{signature,lastFrame:frame,reusedFrames:report.reusedFrames,status:'IN_PROGRESS'});
    console.log(JSON.stringify({phase:'RTX_NATIVE_CAPTURE',frame,total:150,reused:report.reusedFrames}));
   }
  }
  assert.equal(session.errors.length,0);await session.close();session=null;await verify();
  const video=path.join(publicDir,movieName),encodingReceipt=path.join(runRoot,'ENCODING_RECEIPT.json');
  if(!await exists(video)){
   const partial=path.join(runRoot,'NEW_HARDWARE_ENCODING.mp4');
   if(await exists(partial))await rename(partial,partial+'.incomplete-'+Date.now());
   const command=originalEncodingArgs(framesDir,partial);
   await execute('ffmpeg',command,{maxBuffer:8*1024*1024});
   const bytes=await readFile(partial);
   await atomic(encodingReceipt,{signature,sha256:sha(bytes),bytes:bytes.length,command:['ffmpeg',...command]});
   await rename(partial,video);
  }else{
   const bytes=await readFile(video),receipt=await json(encodingReceipt);
   assert.equal(receipt.signature,signature);assert.equal(receipt.sha256,sha(bytes));assert.equal(receipt.bytes,bytes.length);
  }
  report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
  assert.equal(report.ffprobe.streams.length,1);const stream=report.ffprobe.streams[0];
  assert.equal(stream.codec_name,'h264');assert.equal(stream.width,1080);assert.equal(stream.height,1920);
  assert.equal(stream.avg_frame_rate,'30/1');assert.equal(Number(stream.nb_frames),150);assert.equal(Number(stream.duration),5);
  const videoBytes=await readFile(video);report.video={file:movieName,sha256:sha(videoBytes),bytes:videoBytes.length};
  const sums=[report.video,...report.checkpoints].sort((a,b)=>a.file.localeCompare(b.file)),
   body=sums.map(item=>item.sha256+'  '+item.file).join('\n')+'\n',sumsPath=path.join(publicDir,'SHA256SUMS');
  if(await exists(sumsPath))assert.equal(await readFile(sumsPath,'utf8'),body);else await writeFile(sumsPath,body,{flag:'wx',mode:0o600});
  assert.deepEqual((await readdir(publicDir)).sort(),[movieName,'SHA256SUMS',...names].sort(),'PUBLIC_ALLOWLIST_REQUIRED');
  await verify();report.status='CAPTURE_TECHNICAL_PASS';report.publicDirectory=publicDir;
  report.next='USER_VIDEO_REVIEW_REQUIRED';
 }catch(error){failure=error;report.status='BLOCKED';report.error=String(error.message);}
 finally{
  try{await session?.close();}catch(error){failure??=error;report.status='BLOCKED';report.error??=String(error.message);}
  report.completedAt=new Date().toISOString();
  try{await atomic(path.join(runRoot,'REPORT.json'),report);}finally{await unlink(lockPath);}
  process.removeListener('SIGTERM',terminate);
 }
 if(failure)throw failure;
 console.log(JSON.stringify({status:report.status,video:report.video,publicDirectory:report.publicDirectory,visualQualityVerified:false}));
 return report;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2),options={};
 while(args.length){const key=args.shift();assert.ok(['--admission-file','--output-root'].includes(key)&&args.length,'EXPLICIT_RENDER_ARGUMENTS_REQUIRED');
  assert.ok(!Object.hasOwn(options,key),'DUPLICATE_RENDER_ARGUMENT');options[key]=args.shift();}
 await captureHardware({admissionFile:options['--admission-file'],outputRoot:options['--output-root']});
}
