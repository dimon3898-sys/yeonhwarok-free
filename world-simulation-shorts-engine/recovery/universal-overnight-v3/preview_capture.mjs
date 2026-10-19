/** Exact global-frame preview adapter, not a new renderer or scene compiler.
 * Original complete Scene JSON and per-scene seals remain untouched. Only 150
 * source frames are drawn. The original bounded capture and H.264 encoder are
 * reused. Production callers retain the existing common GPU lease and policy.
 */
import assert from 'node:assert/strict';
import {readFile,mkdir,lstat,readdir,writeFile,link,rename,open} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {createInterface} from 'node:readline';
import {captureLongFrames,longEncodingArgs,assertEncodedSegment,hashFile}
 from '../universal-auto-video-v2/long_capture.mjs';

const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url)),
 sourceRoot=path.resolve(here,'../../..'),sha=bytes=>createHash('sha256').update(bytes).digest('hex');

export function validatePreviewRange(range){
 assert.deepEqual(Object.keys(range??{}).sort(),['endFrame','fps','frameConvention','frameCount','localPtsFrameOrigin','startFrame','totalFrames'].sort(),
  'PREVIEW_EXACT_RANGE_FIELDS_REQUIRED');
 assert.equal(range.fps,30,'PREVIEW_30FPS_REQUIRED');assert.equal(range.frameCount,150,'PREVIEW_150_FRAMES_REQUIRED');
 assert.equal(range.frameConvention,'GLOBAL_HALF_OPEN');assert.equal(range.localPtsFrameOrigin,0);
 assert.ok(Number.isSafeInteger(range.totalFrames)&&range.totalFrames>=150&&range.totalFrames<=72000);
 assert.ok(Number.isSafeInteger(range.startFrame)&&Number.isSafeInteger(range.endFrame)
  &&range.startFrame>=0&&range.endFrame-range.startFrame===150&&range.endFrame<=range.totalFrames,
 'PREVIEW_EXACT_GLOBAL_HALF_OPEN_RANGE_REQUIRED');return range;
}

export async function loadVerifiedPreview({requestFile,planFile,expectedPlanSha256}){
 assert.ok(typeof expectedPlanSha256==='string'&&/^[a-f0-9]{64}$/.test(expectedPlanSha256),'PREVIEW_PLAN_SHA_REQUIRED');
 for(const file of [requestFile,planFile])assert.ok(typeof file==='string'&&path.isAbsolute(file)&&path.resolve(file)===file,
  'PREVIEW_CANONICAL_INPUT_PATH_REQUIRED');
 const checked=await execute('/usr/bin/python3',['-B',path.join(here,'preview_contract.py'),
  '--verify-request',requestFile,'--plan-file',planFile],{maxBuffer:2*1024*1024,timeout:30000});
 const request=JSON.parse(checked.stdout),raw=await readFile(planFile);
 assert.equal(sha(raw),expectedPlanSha256,'PREVIEW_ACTUAL_PLAN_SHA_MISMATCH');
 assert.equal(request.bindings.originalPlanSHA256,expectedPlanSha256,'PREVIEW_REQUEST_PLAN_SHA_MISMATCH');
 validatePreviewRange(request.range);return{request,planDocument:JSON.parse(raw),planFile};
}

async function freshPrivateOutput(directory){
 assert.ok(typeof directory==='string'&&path.isAbsolute(directory)&&path.resolve(directory)===directory,'PREVIEW_CANONICAL_OUTPUT_REQUIRED');
 assert.ok(directory!==sourceRoot&&!directory.startsWith(sourceRoot+path.sep),'PREVIEW_SOURCE_TREE_OUTPUT_FORBIDDEN');
 let current=path.parse(directory).root;
 for(const part of directory.slice(current.length).split(path.sep)){
  current=path.join(current,part);try{assert.ok(!(await lstat(current)).isSymbolicLink(),'PREVIEW_OUTPUT_SYMLINK_FORBIDDEN');}
  catch(error){if(error.code!=='ENOENT')throw error;}
 }
 await mkdir(directory,{recursive:true,mode:0o700});const attrs=await lstat(directory);
 assert.ok(attrs.isDirectory()&&(attrs.mode&0o077)===0,'PREVIEW_PRIVATE_OUTPUT_REQUIRED');
 assert.equal((await readdir(directory)).length,0,'PREVIEW_EXISTING_OUTPUT_PRESERVED');
}

export function assertRuntimeSlice({plan,runtime,slice,request,planDocument,softwareProbe}){
 assert.deepEqual(plan.document,planDocument,'PREVIEW_ORIGINAL_PLAN_UNCHANGED_REQUIRED');
 const original=planDocument.scenes.find(row=>row.sceneId===slice.sceneId);
 assert.ok(original,'PREVIEW_ORIGINAL_SCENE_REQUIRED');assert.deepEqual(plan.scene,original,'PREVIEW_ORIGINAL_SCENE_UNCHANGED_REQUIRED');
 assert.ok(slice.startFrame>=original.startFrame&&slice.endFrame<=original.endFrame,'PREVIEW_SLICE_OUTSIDE_ORIGINAL_SCENE');
 assert.equal(plan.planSha256,request.bindings.originalPlanSHA256,'PREVIEW_RUNTIME_SOURCE_SHA_MISMATCH');
 assert.equal(typeof plan.assertSourceUnchanged,'function','PREVIEW_SOURCE_RECHECK_REQUIRED');
 assert.equal(typeof runtime.close,'function','PREVIEW_RUNTIME_CLEANUP_REQUIRED');
 assert.equal(typeof runtime.page?.evaluate,'function','PREVIEW_ACTUAL_CAPTURE_PAGE_REQUIRED');
 assert.ok(Array.isArray(runtime.errors),'PREVIEW_BROWSER_ERROR_LOG_REQUIRED');
 if(softwareProbe){
  assert.equal(runtime.info?.testOnly,true,'PREVIEW_EXPLICIT_SOFTWARE_PROVENANCE_REQUIRED');
  assert.match(runtime.info?.backend??'',/SwiftShader/i,'PREVIEW_REAL_SWIFTSHADER_REQUIRED');
 }else{
  assert.equal(runtime.info?.testOnly,false,'PREVIEW_PRODUCTION_SOFTWARE_FORBIDDEN');
  assert.match(runtime.info?.backend??'',/\bNVIDIA\b/i,'PREVIEW_NVIDIA_BACKEND_REQUIRED');
  assert.doesNotMatch(runtime.info?.backend??'',/swiftshader|llvmpipe|lavapipe|software/i,'PREVIEW_PRODUCTION_SOFTWARE_FORBIDDEN');
 }
 return true;
}

async function captureExactPreview(options,{loadSceneRuntime,softwareProbe}){
 const verified=await loadVerifiedPreview(options),{request,planDocument}=verified,outputRoot=options.outputRoot;
 await freshPrivateOutput(outputRoot);
 const started=performance.now(),report={schema:'WORLD_ENGINE_EXACT_PREVIEW_RECEIPT_V3',status:'IN_PROGRESS',
  requestSHA256:request.requestSHA256,bindings:request.bindings,range:request.range,sceneSlices:request.sceneSlices,
  sourceTimelineReset:false,originalSceneChanged:false,frameStateReconstructed:false,
  softwareProbe,hardwareVerified:false,visualQualityApproved:false,finalPromotion:false,
  startedAt:new Date().toISOString(),fragments:[],completedFrames:0};
 const checkpoints=[0,37,74,112,149].map(offset=>request.range.startFrame+offset),joinedFrames=path.join(outputRoot,'frames'),
  evidence=await open(path.join(outputRoot,'FRAMES.ndjson'),'wx',0o600);
 await mkdir(joinedFrames,{mode:0o700});let runtime,error;
 try{
  for(let index=0;index<request.sceneSlices.length;index++){
   const slice=request.sceneSlices[index],fragmentRoot=path.join(outputRoot,'fragments',String(index).padStart(3,'0'));
   await mkdir(fragmentRoot,{recursive:true,mode:0o700});
   const entry=await loadSceneRuntime({sceneId:slice.sceneId,planDocument,request,planFile:options.planFile}),
    plan=entry.plan??entry.loadedPlan??entry;
   runtime=entry.runtime??entry;
   assertRuntimeSlice({plan,runtime,slice,request,planDocument,softwareProbe});await plan.assertSourceUnchanged();
   const capture=await captureLongFrames({captureFrame:frame=>runtime.page.evaluate(
    async frame=>window.longVideoProof.capture(frame,{png:true}),frame),
    range:{startFrame:slice.startFrame,endFrame:slice.endFrame,totalFrames:request.range.totalFrames,fps:30},
    binding:plan,framesDirectory:path.join(fragmentRoot,'frames'),evidenceFile:path.join(fragmentRoot,'FRAMES.ndjson'),
    production:!softwareProbe,checkpointFrames:checkpoints.filter(frame=>frame>=slice.startFrame&&frame<slice.endFrame),
    progress:value=>options.progress?.({...value,previewCompletedFrames:report.completedFrames+value.completedFrames,
     previewTotalFrames:150})});
   assert.equal(runtime.errors.length,0,'PREVIEW_BROWSER_RUNTIME_ERROR');
   const backend=runtime.info.backend;await runtime.close();runtime=null;await plan.assertSourceUnchanged();
   // Link only newly created, receipt-bound frames. No source/cache/result is
   // moved, reset or deleted. Encoding uses original local zero-based numbering.
   const rows=createInterface({input:createReadStream(path.join(fragmentRoot,'FRAMES.ndjson')),crlfDelay:Infinity});let rowCount=0;
   for await(const line of rows){
    const row=JSON.parse(line);
    const localFrame=row.globalFrame-request.range.startFrame;
    assert.equal(row.globalFrame,slice.startFrame+row.localFrame,'PREVIEW_GLOBAL_EVIDENCE_ORDER_MISMATCH');
    assert.equal(localFrame,report.completedFrames,'PREVIEW_NO_MISSING_OR_DUPLICATE_GLOBAL_FRAMES');
    const source=path.join(fragmentRoot,'frames',String(row.localFrame).padStart(6,'0')+'.png'),
     attrs=await lstat(source),actual=await hashFile(source);
    assert.ok(attrs.isFile()&&!attrs.isSymbolicLink(),'PREVIEW_CREATED_REGULAR_FRAME_REQUIRED');
    assert.equal(actual.sha256,row.pngSha256,'PREVIEW_CREATED_FRAME_CHANGED');assert.equal(actual.bytes,row.bytes);
    await link(source,path.join(joinedFrames,String(localFrame).padStart(6,'0')+'.png'));
    await evidence.write(JSON.stringify({...row,fragmentIndex:index,fragmentLocalFrame:row.localFrame,localFrame})+'\n');
    report.completedFrames++;rowCount++;
   }
   assert.equal(rowCount,slice.endFrame-slice.startFrame,'PREVIEW_FRAGMENT_FRAME_COUNT_MISMATCH');
   await evidence.sync();report.fragments.push({sceneId:slice.sceneId,startFrame:slice.startFrame,endFrame:slice.endFrame,
    planSha256:plan.planSha256,sceneRangeSha256:plan.sceneRangeSha256,legacySceneSha256:plan.legacySceneSha256,
    backend,...capture});
  }
  assert.equal(report.completedFrames,150,'PREVIEW_COMPLETE_150_FRAMES_REQUIRED');
  await evidence.close();report.captureWallMs=performance.now()-started;
  const encodingStart=performance.now(),partial=path.join(outputRoot,'PREVIEW_ENCODING.mp4'),video=path.join(outputRoot,'preview.mp4');
  await execute('ffmpeg',longEncodingArgs({framesDirectory:joinedFrames,outputFile:partial,frameCount:150,fps:30}),
   {maxBuffer:1024*1024,timeout:300000});
  report.encodingWallMs=performance.now()-encodingStart;
  const probe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',partial],
   {maxBuffer:1024*1024,timeout:60000})).stdout);
  assertEncodedSegment(probe,request.range);
  await execute('ffmpeg',['-hide_banner','-v','error','-xerror','-nostdin','-i',partial,'-f','null','-'],
   {maxBuffer:1024*1024,timeout:300000});
  await rename(partial,video);report.video={path:video,...await hashFile(video)};report.ffprobe=probe;report.fullDecodeVerified=true;
  const checkpointRoot=path.join(outputRoot,'checkpoints');await mkdir(checkpointRoot,{mode:0o700});report.checkpoints=[];
  for(let index=0;index<checkpoints.length;index++){
   const globalFrame=checkpoints[index],local=globalFrame-request.range.startFrame,
    file=String(index+1).padStart(2,'0')+'_GLOBAL_'+String(globalFrame).padStart(6,'0')+'.png';
   await link(path.join(joinedFrames,String(local).padStart(6,'0')+'.png'),path.join(checkpointRoot,file));
   report.checkpoints.push({file:'checkpoints/'+file,globalFrame,localFrame:local,...await hashFile(path.join(checkpointRoot,file))});
  }
  report.hardwareVerified=!softwareProbe;report.status=softwareProbe?'SOFTWARE_PREVIEW_TECHNICAL_PASS':'PREVIEW_TECHNICAL_PASS';
  await writeFile(path.join(outputRoot,'SHA256SUMS'),[report.video.sha256+'  preview.mp4',
   ...report.checkpoints.map(row=>row.sha256+'  '+row.file)].join('\n')+'\n',{flag:'wx',mode:0o600});
  await writeFile(path.join(outputRoot,'PREVIEW_COMPLETE.json'),JSON.stringify({schema:'WORLD_ENGINE_PREVIEW_COMPLETE_V3',
   requestSHA256:request.requestSHA256,range:request.range,video:report.video,hardwareVerified:report.hardwareVerified,
   softwareProbe,fullDecodeVerified:true,visualQualityApproved:false},null,2)+'\n',{flag:'wx',mode:0o600});
 }catch(failure){error=failure;report.status='BLOCKED';report.errorCode=/^[A-Z][A-Z0-9_]{2,95}$/.test(failure?.message??'')?
  failure.message:'PREVIEW_CAPTURE_FAILED';}
 finally{
  try{await runtime?.close();}catch(failure){error??=failure;report.status='BLOCKED';report.errorCode??='PREVIEW_RUNTIME_CLEANUP_FAILED';}
  await evidence.close().catch(()=>{});report.completedAt=new Date().toISOString();report.totalWallMs=performance.now()-started;
  await writeFile(path.join(outputRoot,'PREVIEW_RECEIPT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx',mode:0o600});
 }
 if(error)throw error;return report;
}

/** Explicit software-only harness. A real SwiftShader page is mandatory; this
 * cannot grant production GPU admission or label a mock frame NVIDIA PASS. */
export async function capturePreviewWithRuntime(options){
 assert.equal(options.softwareProbe,true,'PREVIEW_SOFTWARE_HARNESS_EXPLICIT_ONLY');
 assert.equal(typeof options.loadSceneRuntime,'function','PREVIEW_ACTUAL_SOFTWARE_RUNTIME_REQUIRED');
 return captureExactPreview(options,{loadSceneRuntime:options.loadSceneRuntime,softwareProbe:true});
}

/** Production path: unchanged hardware opener, admission and actual frame
 * assertions. Policy, source-image proof and common GPU lease remain caller's. */
export async function capturePreview(options){
 const source=await import('./capture_runtime.mjs');
 return captureExactPreview(options,{softwareProbe:false,loadSceneRuntime:async({sceneId})=>{
  const plan=await source.loadLongRuntimePlan({...options,sceneId});
  const runtime=await source.openLongRuntime({...options,loadedPlan:plan});return{plan,runtime};
 }});
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const args=process.argv.slice(2),options={},mapping={'--request-file':'requestFile','--plan-file':'planFile',
   '--plan-sha256':'expectedPlanSha256','--admission-file':'admissionFile','--output-root':'outputRoot'};
  while(args.length){const key=args.shift();assert.ok(mapping[key]&&args.length&&!Object.hasOwn(options,mapping[key]),'PREVIEW_ARGUMENT_INVALID');options[mapping[key]]=args.shift();}
  assert.equal(Object.keys(options).length,5,'PREVIEW_EXACT_ARGUMENTS_REQUIRED');
  const report=await capturePreview(options);console.log(JSON.stringify({status:report.status,range:report.range,
   video:report.video,hardwareVerified:report.hardwareVerified,visualQualityApproved:false}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',errorCode:/^[A-Z][A-Z0-9_]{2,95}$/.test(error?.message??'')?
  error.message:'PREVIEW_CAPTURE_FAILED',visualQualityApproved:false}));process.exitCode=2;}
}
