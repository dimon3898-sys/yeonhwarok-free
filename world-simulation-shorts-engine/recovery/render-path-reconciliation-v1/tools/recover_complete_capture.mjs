/** Encode-only recovery of an entirely captured, source-bound software preview.
 * Never imports a browser opener or calls draw/capture; preserves failed inputs.
 */
import assert from 'node:assert/strict';
import path from 'node:path';
import {readFile,writeFile,mkdir,lstat,link,open,rename,chmod,readdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {longEncodingArgs,assertEncodedSegment,hashFile,assertCapturedLongFrame}
 from '../../universal-auto-video-v2/long_capture.mjs';
import {loadVerifiedPreview} from '../../universal-overnight-v3/preview_capture.mjs';
import {loadOvernightSoftwarePlan,assertActualSoftwareFrame} from '../../universal-overnight-v3/free_preview_runner.mjs';
import {extendObservedPlan} from '../trace_binding.mjs';
const execute=promisify(execFile),HERE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),
 REPO=path.resolve(HERE,'../../..'),OWN_REL=path.relative(REPO,HERE),sha=b=>createHash('sha256').update(b).digest('hex');
async function regular(file){const s=await lstat(file);assert.ok(s.isFile()&&!s.isSymbolicLink(),'RECOVERY_REGULAR_FILE_REQUIRED');return s;}
async function fresh(directory){
 assert.ok(path.isAbsolute(directory)&&path.resolve(directory)===directory,'RECOVERY_CANONICAL_OUTPUT_REQUIRED');
 assert.ok(!directory.startsWith(REPO+path.sep),'RECOVERY_OUTPUT_OUTSIDE_REPOSITORY_REQUIRED');
 let cursor=path.parse(directory).root;
 for(const part of directory.slice(cursor.length).split(path.sep)){
  cursor=path.join(cursor,part);try{assert.ok(!(await lstat(cursor)).isSymbolicLink(),'RECOVERY_OUTPUT_SYMLINK_FORBIDDEN');}
  catch(e){if(e.code!=='ENOENT')throw e;}
 }
 await mkdir(directory,{mode:0o700,recursive:false});
}
async function verifyFrozen(checkpoint){
 assert.match(checkpoint,/^[a-f0-9]{40}$/,'RECOVERY_FULL_IMMUTABLE_COMMIT_REQUIRED');
 const manifestFile=path.join(HERE,'RECONCILIATION_FILES.json'),raw=await readFile(manifestFile),manifest=JSON.parse(raw),checked=[];
 for(const name of ['RECONCILIATION_FILES.json',...Object.keys(manifest.files)]){
  assert.equal(path.basename(name),name);const current=await readFile(path.join(HERE,name));
  const committed=(await execute('git',['show',checkpoint+':'+OWN_REL+'/'+name],{cwd:REPO,encoding:'buffer',maxBuffer:16*1024*1024})).stdout;
  assert.ok(current.equals(committed),'RECOVERY_FROZEN_GIT_BYTES_MISMATCH_'+name);
  if(name!=='RECONCILIATION_FILES.json')assert.equal(sha(current),manifest.files[name],'RECOVERY_SOURCE_SHA_MISMATCH');
  checked.push({file:name,sha256:sha(current),bytes:current.length});
 }
 const parent=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(HERE,'package_manifest.py')],{cwd:REPO,maxBuffer:8*1024*1024})).stdout);
 assert.equal(parent.status,'PASS');assert.equal(parent.files,15);assert.equal(parent.parentFiles,82);
 assert.equal(parent.manifestSHA256,sha(raw));assert.equal(parent.previousManifestSHA256,manifest.previousManifestSHA256);
 return {sourceCheckoutCommit:checkpoint,sourceManifestSHA256:sha(raw),allOwnRuntimeGitBytesEqual:true,ownRuntimeFiles:15,
  manifestComparedToGit:true,parentManifestVerification:parent,checked};
}
export async function recoverCompleteCapture({preparedFile,captureRoot,baselineRoot,outputRoot,sourceCheckpoint,logFile}){
 const started=performance.now(),source=await verifyFrozen(sourceCheckpoint),prepared=JSON.parse(await readFile(preparedFile)),options=prepared.options,
  verified=await loadVerifiedPreview(options),{request,planDocument}=verified;
 assert.equal(request.sceneSlices.length,1,'RECOVERY_SINGLE_ORIGINAL_SCENE_REQUIRED');
 const plan=await extendObservedPlan(await loadOvernightSoftwarePlan({...options,sceneId:request.sceneSlices[0].sceneId}));
 assert.deepEqual(plan.document,planDocument,'RECOVERY_ORIGINAL_80S_PLAN_UNCHANGED_REQUIRED');
 assert.equal(source.sourceManifestSHA256,plan.reconciliationObservation.sourceManifestSHA256);
 const failedReceiptBytes=await readFile(path.join(captureRoot,'PREVIEW_RECEIPT.json')),failed=JSON.parse(failedReceiptBytes),log=await readFile(logFile,'utf8');
 assert.equal(failed.status,'BLOCKED','RECOVERY_FAILED_RUN_EXPECTED');assert.equal(failed.hardwareVerified,false);
 assert.deepEqual(failed.range,request.range);assert.deepEqual(failed.bindings,request.bindings);
 assert.ok(log.includes('"completedFrames":150')&&log.includes('ENOENT: no such file or directory')&&log.includes('/RECONCILIATION_FILES.json'),
  'RECOVERY_OBSERVED_COMPLETE_CAPTURE_AND_MISSING_SOURCE_ERROR_REQUIRED');
 const file=path.join(captureRoot,'fragments/000/FRAMES.ndjson'),raw=await readFile(file);
 assert.ok(raw.length>0&&raw.length<128*1024*1024&&raw.at(-1)===10,'RECOVERY_BOUNDED_COMPLETE_NDJSON_REQUIRED');
 const rows=raw.toString('utf8').trimEnd().split('\n').map(JSON.parse);
 assert.equal(rows.length,150,'RECOVERY_EXACT_COMPLETE_150_REQUIRED');assert.equal(request.range.frameCount,150);
 const oldRaw=await readFile(path.join(baselineRoot,'FRAMES.ndjson')),oldRows=oldRaw.toString('utf8').trimEnd().split('\n').map(JSON.parse),
  baseline=new Map(oldRows.map(row=>[row.globalFrame,row]));
 assert.equal(baseline.size,150,'RECOVERY_COMPLETE_PRESERVED_BASELINE_REQUIRED');
 assert.equal((await readdir(path.join(captureRoot,'fragments/000/frames'))).length,150,'RECOVERY_EXACT_PNG_INVENTORY_REQUIRED');
 let sampled=0;
 for(let index=0;index<rows.length;index++){
  const row=rows[index],frame=request.range.startFrame+index;
  assert.equal(row.localFrame,index,'RECOVERY_LOCAL_FRAME_ORDER');assert.equal(row.globalFrame,frame,'RECOVERY_GLOBAL_FRAME_ORDER');
  const png=path.join(captureRoot,'fragments/000/frames',String(index).padStart(6,'0')+'.png');await regular(png);
  const bytes=await readFile(png);assert.equal(sha(bytes),row.pngSha256,'RECOVERY_PNG_SHA');assert.equal(bytes.length,row.bytes,'RECOVERY_PNG_BYTES');
  const captured={diagnostic:row.diagnostic,raw_rgba_sha256:row.rawRgbaSha256,png_sha256:row.pngSha256,
   png:'data:image/png;base64,'+bytes.toString('base64')};
  assertCapturedLongFrame(captured,frame,plan,{production:false});await assertActualSoftwareFrame(captured,frame,plan);
  const trace=row.diagnostic.reconciliation;assert.equal(trace.frame,frame);assert.equal(trace.originalGlobalFrame,frame);
  assert.equal(trace.sourceBinding.sourceManifestSHA256,source.sourceManifestSHA256);
  assert.deepEqual(trace.sourceBinding,plan.reconciliationObservation,'RECOVERY_EXACT_OBSERVER_SOURCE_BINDING');
  assert.equal(trace.sourcePixelsModified,false);assert.equal(trace.physicalNvidiaVerified,false);
  assert.equal(trace.scalarSelected,false);assert.equal(trace.nationalUnitsSelected,false);
  for(const key of ['PRESERVED_V5_CAMERA','ASTRA_REFERENCE_SOURCE','SUPPLIED_AREA_FRONT']){
   assert.equal(trace.instantiatedFactories[key],1);assert.equal(trace.executedDraws[key],1);}
  sampled+=Number(trace.sampledForStagePixels);assert.equal(trace.pixelStages.length,trace.sampledForStagePixels?3:0);
  const previous=baseline.get(frame);assert.ok(previous);assert.equal(previous.rawRgbaSha256,row.rawRgbaSha256,'RECOVERY_BASELINE_RAW_RGBA_EQUAL');
  assert.equal(previous.pngSha256,row.pngSha256,'RECOVERY_BASELINE_PNG_EQUAL');
 }
 assert.equal(sampled,3);await plan.assertSourceUnchanged();
 await fresh(outputRoot);const joined=path.join(outputRoot,'frames');await mkdir(joined,{mode:0o700});
 await writeFile(path.join(outputRoot,'ORIGINAL_FAILED_PREVIEW_RECEIPT.json'),failedReceiptBytes,{flag:'wx',mode:0o600});
 const report={schema:'WORLD_ENGINE_ENCODE_ONLY_COMPLETE_CAPTURE_RECOVERY_V1',status:'ENCODE_IN_PROGRESS',
  sourceCheckoutCommit:sourceCheckpoint,sourceCheckpointCommit:sourceCheckpoint,sourceManifestSHA256:source.sourceManifestSHA256,
  bindings:request.bindings,range:request.range,sceneSlices:request.sceneSlices,requestSHA256:request.requestSHA256,
  sourceCheckRestored:true,initialFailure:'SOURCEFILE_REMOVED_BY_SPARSE_FF',
  actualObservedFailure:'ENOENT_RECONCILIATION_FILES_JSON_DURING_POST_CAPTURE_SOURCE_RECHECK',
  sourceRestorationProof:source,initialFailedReceiptSHA256:sha(failedReceiptBytes),captureNDJSON_SHA256:sha(raw),
  preservedBaselineNDJSON_SHA256:sha(oldRaw),reusedCompleteFrames:150,newlyCapturedFrames:0,rerenderedCompleteFrames:0,
  originalFailureRootPreserved:true,sourceTimelineReset:false,originalSceneChanged:false,frameStateReconstructed:false,
  softwareProbe:true,hardwareVerified:false,nvidiaHardwareVerified:false,candidateImageExecuted:false,
  productionRenderAllowed:false,full80Rendered:false,visualQualityApproved:false,finalPromotion:false,
  actualCapturedFrameValidationCount:150,all150RawRGBAAndPngEqualPreservedBaseline:true,sampledStagePixelFrames:sampled,
  renderRuntimeOpenedByRecovery:false,browserOpenedByRecovery:false,startedAt:new Date().toISOString(),
  originalCaptureAndFailureWallMs:failed.totalWallMs};
 const save=async(name,value)=>writeFile(path.join(outputRoot,name),JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
 try{
  const merged=await open(path.join(outputRoot,'FRAMES.ndjson'),'wx',0o600);
  try{for(let index=0;index<rows.length;index++){
   await link(path.join(captureRoot,'fragments/000/frames',String(index).padStart(6,'0')+'.png'),path.join(joined,String(index).padStart(6,'0')+'.png'));
   await merged.write(JSON.stringify(rows[index])+'\n');}await merged.sync();
  }finally{await merged.close();}
  const partial=path.join(outputRoot,'PREVIEW_ENCODING.mp4'),video=path.join(outputRoot,'preview.mp4'),encodeStart=performance.now();
  await execute('ffmpeg',longEncodingArgs({framesDirectory:joined,outputFile:partial,frameCount:150,fps:30}),{maxBuffer:1024*1024,timeout:300000});
  await chmod(partial,0o600);report.encodeWallMs=performance.now()-encodeStart;
  const probe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',partial],{maxBuffer:1024*1024})).stdout);
  assertEncodedSegment(probe,request.range);
  await execute('ffmpeg',['-hide_banner','-v','error','-xerror','-nostdin','-i',partial,'-f','null','-'],{maxBuffer:1024*1024,timeout:300000});
  await rename(partial,video);report.video={path:video,...await hashFile(video)};report.ffprobe=probe;report.fullDecodeVerified=true;
  const checkpoints=[0,37,74,112,149],checkpointRoot=path.join(outputRoot,'checkpoints');await mkdir(checkpointRoot,{mode:0o700});report.checkpoints=[];
  for(let i=0;i<checkpoints.length;i++){
   const localFrame=checkpoints[i],globalFrame=request.range.startFrame+localFrame,name=String(i+1).padStart(2,'0')+'_GLOBAL_'+String(globalFrame).padStart(6,'0')+'.png',file=path.join(checkpointRoot,name);
   await link(path.join(joined,String(localFrame).padStart(6,'0')+'.png'),file);
   report.checkpoints.push({file:'checkpoints/'+name,globalFrame,localFrame,...await hashFile(file)});
  }
  await plan.assertSourceUnchanged();await verifyFrozen(sourceCheckpoint);
  report.completedFrames=150;report.status='SOFTWARE_PREVIEW_TECHNICAL_PASS';report.completedAt=new Date().toISOString();
  report.recoveryWallMs=performance.now()-started;report.totalWallMs=failed.totalWallMs+report.recoveryWallMs;
  report.timeAccounting='MEASURED_ORIGINAL_CAPTURE_TO_FAILURE_PLUS_SEPARATELY_MEASURED_ENCODE_ONLY_RECOVERY; INTERVENTION_WAIT_EXCLUDED';
  await writeFile(path.join(outputRoot,'SHA256SUMS'),[report.video.sha256+'  preview.mp4',...report.checkpoints.map(r=>r.sha256+'  '+r.file)].join('\n')+'\n',{flag:'wx',mode:0o600});
  await save('PREVIEW_RECEIPT.json',report);
  const result={schema:'WORLD_ENGINE_FREE_PREVIEW_ENCODE_RECOVERY_RESULT_V1',status:'PASS_SOFTWARE_ONLY',range:report.range,
   completedFrames:150,completedAt:report.completedAt,softwareValidation:true,nvidiaHardwareVerified:false,
   gpuExecuted:false,actualWebGLDrawDuringPreservedCapture:true,actualReadPixelsDuringPreservedCapture:true,
   actualMP4Decoded:true,renderingExecutedDuringRecovery:false,reusedCompleteFrames:150,newlyCapturedFrames:0,
   original80sDocumentUnchanged:true,visualQualityApproved:false,full80SecondsRendered:false,productionRenderAllowed:false,
   video:report.video,checkpoints:report.checkpoints,totalWallMs:report.totalWallMs,
   sourceManifest:source.sourceManifestSHA256,sourceCommit:sourceCheckpoint,sourceCheckRestored:true};
  await save('FREE_RENDER_RESULT.json',result);
  await save('RECONCILIATION_CAPTURE.json',{schema:'WORLD_ENGINE_RECONCILIATION_SOFTWARE_CAPTURE_RECOVERED_V1',
   status:'ACTUAL_SOFTWARE_CAPTURE_ENCODE_ONLY_RECOVERY',sourceCheckoutCommit:sourceCheckpoint,
   sourceManifestSHA256:source.sourceManifestSHA256,candidateContainerExecuted:false,candidateImageExecuted:false,
   physicalNvidiaVerified:false,visualQualityApproved:false,newVisualDesignClaimed:false,
   completeCapturedFramesReused:150,newlyRenderedFrames:0,all150RawRGBAAndPngEqualPreservedBaseline:true,
   sourceCheckRestored:true,originalFailedRoot:captureRoot,originalFailureReceiptSHA256:sha(failedReceiptBytes),result});
  return report;
 }catch(error){await save('RECOVERY_FAILURE.json',{...report,status:'BLOCKED',errorCode:String(error.message).slice(0,2048),
  recoveryWallMs:performance.now()-started});throw error;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const args=process.argv.slice(2),options={},mapping={'--prepared-file':'preparedFile','--capture-root':'captureRoot',
  '--baseline-root':'baselineRoot','--output-root':'outputRoot','--source-checkpoint':'sourceCheckpoint','--log-file':'logFile'};
  while(args.length){const key=args.shift();assert.ok(mapping[key]&&args.length&&!Object.hasOwn(options,mapping[key]));options[mapping[key]]=args.shift();}
  const r=await recoverCompleteCapture(options);console.log(JSON.stringify({status:r.status,video:r.video,
   reusedCompleteFrames:150,newlyCapturedFrames:0,renderRuntimeOpenedByRecovery:false,totalWallMs:r.totalWallMs,recoveryWallMs:r.recoveryWallMs}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',message:error.message,stack:error.stack}));process.exitCode=2;}
}
