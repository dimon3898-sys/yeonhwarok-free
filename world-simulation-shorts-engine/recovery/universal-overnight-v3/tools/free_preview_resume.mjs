/** Free, explicit software-only checkpoint recovery tool. Reuses the original
 * bounded frame capture and encoder; it never starts a Studio/GPU job. */
import assert from 'node:assert/strict';
import path from 'node:path';
import {readFile,writeFile,mkdir,open,link,lstat,rename} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {writeFileSync,renameSync} from 'node:fs';
import {captureLongFrames,longEncodingArgs,assertEncodedSegment,hashFile,assertCapturedLongFrame}
 from '../../universal-auto-video-v2/long_capture.mjs';
import {processIdentity} from '../../rtx-gpu-package-v1/hardware_render.mjs';
import {loadVerifiedPreview} from '../preview_capture.mjs';
import {openSoftwarePreviewRuntime,loadOvernightSoftwarePlan,assertActualSoftwareFrame} from '../free_preview_runner.mjs';
const execute=promisify(execFile),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function fresh(directory){
 assert.ok(path.isAbsolute(directory)&&path.resolve(directory)===directory,'RESUME_ABSOLUTE_OUTPUT_REQUIRED');
 let cursor=path.parse(directory).root;
 for(const part of directory.slice(cursor.length).split(path.sep)){
  cursor=path.join(cursor,part);try{assert.ok(!(await lstat(cursor)).isSymbolicLink(),'RESUME_SYMLINK_FORBIDDEN');}
  catch(error){if(error.code!=='ENOENT')throw error;}
 }
 await mkdir(directory,{mode:0o700,recursive:false});
}
export async function resumeFreePreview({preparedFile,prefixRoot,outputRoot,sourceCheckpointCommit}){
 const prepared=JSON.parse(await readFile(preparedFile,'utf8')),options=prepared.options,
  verified=await loadVerifiedPreview(options),{request,planDocument}=verified,
  sourceFile=path.join(prefixRoot,'fragments/000/FRAMES.ndjson'),raw=await readFile(sourceFile);
 assert.ok(raw.length>0&&raw.length<128*1024*1024&&raw.at(-1)===10,'RESUME_COMPLETE_BOUNDED_PREFIX_REQUIRED');
 const records=raw.toString('utf8').trimEnd().split('\n').map(line=>JSON.parse(line));
 assert.ok(records.length>0&&records.length<150,'RESUME_PARTIAL_PREFIX_REQUIRED');
 assert.equal(request.sceneSlices.length,1,'RESUME_ONE_ORIGINAL_SCENE_REQUIRED');
 const sceneId=request.sceneSlices[0].sceneId,
  plan=await loadOvernightSoftwarePlan({...options,sceneId});
 assert.deepEqual(plan.document,planDocument,'RESUME_FULL_SOURCE_PLAN_UNCHANGED_REQUIRED');
 const prefix=[];
 for(let index=0;index<records.length;index++){
  const row=records[index],globalFrame=request.range.startFrame+index;
  assert.equal(row.localFrame,index,'RESUME_PREFIX_LOCAL_ORDER');assert.equal(row.globalFrame,globalFrame,'RESUME_PREFIX_GLOBAL_ORDER');
  assert.equal(row.diagnostic.overnightV3.sourceManifestSHA256,request.bindings.sourceManifestSHA256,'RESUME_SAME_SOURCE_MANIFEST_REQUIRED');
  const file=path.join(prefixRoot,'fragments/000/frames',String(index).padStart(6,'0')+'.png'),attributes=await lstat(file);
  assert.ok(attributes.isFile()&&!attributes.isSymbolicLink(),'RESUME_PREFIX_REGULAR_PNG_REQUIRED');
  const bytes=await readFile(file);assert.equal(sha(bytes),row.pngSha256,'RESUME_PREFIX_PNG_SHA_MISMATCH');
  assert.equal(bytes.length,row.bytes,'RESUME_PREFIX_PNG_SIZE_MISMATCH');
  const captured={diagnostic:row.diagnostic,raw_rgba_sha256:row.rawRgbaSha256,png_sha256:row.pngSha256,
   png:'data:image/png;base64,'+bytes.toString('base64')};
  assertCapturedLongFrame(captured,globalFrame,plan,{production:false});
  await assertActualSoftwareFrame(captured,globalFrame,plan);prefix.push({row,file});
 }
 await plan.assertSourceUnchanged();await fresh(outputRoot);
 const identity=await processIdentity(),report={schema:'WORLD_ENGINE_FREE_CHECKPOINT_RECOVERY_V3',status:'RUNNING',
  interruption:'EXEC_SERVER_TRANSPORT_DISCONNECTED_PARENT_PROCESS_DIED',sourceCheckpointCommit,
  sourceManifestSHA256:request.bindings.sourceManifestSHA256,bindings:request.bindings,range:request.range,
  initialSavedFrames:records.length,reusedCompleteFrames:records.length,newlyCapturedFrames:0,rerenderedCompleteFrames:0,
  oldPrefixRootPreserved:true,firstCompletedPreviewPreserved:true,sourceGlobalClockReset:false,
  existingSceneChanged:false,softwareProbe:true,hardwareVerified:false,visualQualityApproved:false,
  candidateImageExecutionVerified:false,full80sRendered:false,startedAt:new Date().toISOString(),process:identity};
 const state=async()=>{const pending=path.join(outputRoot,'RECOVERY_STATE.json.writing');
  await writeFile(pending,JSON.stringify(report,null,2)+'\n',{mode:0o600});await rename(pending,path.join(outputRoot,'RECOVERY_STATE.json'));};
 await state();await writeFile(path.join(outputRoot,'PID.json'),JSON.stringify(identity)+'\n',{mode:0o600,flag:'wx'});
 let runtime;
 const started=performance.now(),startFrame=request.range.startFrame+records.length,
  remainder=path.join(outputRoot,'remainder');await mkdir(remainder,{mode:0o700});
 try{
  runtime=await openSoftwarePreviewRuntime({...options,sceneId,loadPlan:loadOvernightSoftwarePlan});
  report.backend=runtime.info.backend;report.phase='CAPTURE_REMAINDER';await state();
  const checkpoints=[0,37,74,112,149].map(offset=>request.range.startFrame+offset),captured=await captureLongFrames({
   captureFrame:frame=>runtime.page.evaluate(async frame=>window.longVideoProof.capture(frame,{png:true}),frame),
   range:{startFrame,endFrame:request.range.endFrame,totalFrames:request.range.totalFrames,fps:30},binding:runtime,
   framesDirectory:path.join(remainder,'frames'),evidenceFile:path.join(remainder,'FRAMES.ndjson'),production:false,
   checkpointFrames:checkpoints.filter(frame=>frame>=startFrame),progress:value=>{
    report.newlyCapturedFrames=value.completedFrames;
    const pending=path.join(outputRoot,'RECOVERY_STATE.json.writing');writeFileSync(pending,JSON.stringify(report,null,2)+'\n',{mode:0o600});
    renameSync(pending,path.join(outputRoot,'RECOVERY_STATE.json'));console.log(JSON.stringify({event:'SOFTWARE_RESUME',
     reusedFrames:records.length,...value,totalPreviewCompleted:records.length+value.completedFrames}));}});
  report.newlyCapturedFrames=captured.completedFrames;
  assert.equal(runtime.errors.length,0,'RESUME_BROWSER_ERRORS');await runtime.close();runtime=null;await plan.assertSourceUnchanged();
  const joined=path.join(outputRoot,'frames');await mkdir(joined,{mode:0o700});
  const merged=await open(path.join(outputRoot,'FRAMES.ndjson'),'wx',0o600);let count=0;
  try{
   const append=async(row,file,segment)=>{
    assert.equal(row.globalFrame,request.range.startFrame+count,'RESUME_NO_FRAME_GAP_OR_DUPLICATE');
    const actual=await hashFile(file);assert.equal(actual.sha256,row.pngSha256,'RESUME_JOIN_SHA_MISMATCH');
    assert.equal(actual.bytes,row.bytes);await link(file,path.join(joined,String(count).padStart(6,'0')+'.png'));
    await merged.write(JSON.stringify({...row,localFrame:count,fragmentLocalFrame:row.localFrame,recoverySegment:segment})+'\n');count++;
   };
   for(const record of prefix)await append(record.row,record.file,'VERIFIED_SAVED_PREFIX');
   for(const line of (await readFile(path.join(remainder,'FRAMES.ndjson'),'utf8')).trimEnd().split('\n')){
    const row=JSON.parse(line);await append(row,path.join(remainder,'frames',String(row.localFrame).padStart(6,'0')+'.png'),'NEW_GLOBAL_REMAINDER');}
   assert.equal(count,150,'RESUME_EXACT_150_FRAMES_REQUIRED');await merged.sync();
  }finally{await merged.close();}
  report.phase='ENCODE_VERIFY';await state();const partial=path.join(outputRoot,'PREVIEW_ENCODING.mp4'),video=path.join(outputRoot,'preview.mp4');
  await execute('ffmpeg',longEncodingArgs({framesDirectory:joined,outputFile:partial,frameCount:150,fps:30}),{maxBuffer:1024*1024,timeout:300000});
  const probe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',partial],{maxBuffer:1024*1024})).stdout);
  assertEncodedSegment(probe,request.range);await execute('ffmpeg',['-hide_banner','-v','error','-xerror','-nostdin','-i',partial,'-f','null','-'],{maxBuffer:1024*1024,timeout:300000});
  await rename(partial,video);report.video={path:video,...await hashFile(video)};report.ffprobe=probe;report.fullDecodeVerified=true;
  const checkpointRoot=path.join(outputRoot,'checkpoints');await mkdir(checkpointRoot,{mode:0o700});report.checkpoints=[];
  for(let index=0;index<checkpoints.length;index++){
   const globalFrame=checkpoints[index],localFrame=globalFrame-request.range.startFrame,
    name=String(index+1).padStart(2,'0')+'_GLOBAL_'+String(globalFrame).padStart(6,'0')+'.png',file=path.join(checkpointRoot,name);
   await link(path.join(joined,String(localFrame).padStart(6,'0')+'.png'),file);
   report.checkpoints.push({file:'checkpoints/'+name,globalFrame,localFrame,...await hashFile(file)});
  }
  report.completedFrames=150;report.status='SOFTWARE_PREVIEW_TECHNICAL_PASS';report.phase='COMPLETE';
  report.captureAndEncodeWallMs=performance.now()-started;report.totalRetainedPrefixFrames=records.length;
  await writeFile(path.join(outputRoot,'SHA256SUMS'),[report.video.sha256+'  preview.mp4',
   ...report.checkpoints.map(row=>row.sha256+'  '+row.file)].join('\n')+'\n',{flag:'wx',mode:0o600});
 }catch(error){report.status='BLOCKED';report.errorCode=String(error.message).slice(0,2048);throw error;}
 finally{await runtime?.close();report.completedAt=new Date().toISOString();await state();
  await writeFile(path.join(outputRoot,'PREVIEW_RECEIPT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});}
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const args=process.argv.slice(2),options={},mapping={'--prepared-file':'preparedFile','--prefix-root':'prefixRoot',
  '--output-root':'outputRoot','--source-checkpoint':'sourceCheckpointCommit'};
  while(args.length){const key=args.shift();assert.ok(mapping[key]&&args.length&&!Object.hasOwn(options,mapping[key]));options[mapping[key]]=args.shift();}
  const report=await resumeFreePreview(options);console.log(JSON.stringify({status:report.status,video:report.video,
   reusedFrames:report.reusedCompleteFrames,newlyCapturedFrames:report.newlyCapturedFrames,rerenderedCompleteFrames:0}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',message:error.message,stack:error.stack}));process.exitCode=2;}
}
