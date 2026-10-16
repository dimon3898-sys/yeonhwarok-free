/** CPU boundary/capture tests. Fake PNG headers are test-only transport fixtures;
 * production performs ffprobe plus full FFmpeg decode, and requires NVIDIA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,rm,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {sha} from '../long_runtime.mjs';
import {validateCaptureRange,longEncodingArgs,assertCapturedLongFrame,captureLongFrames,assertEncodedSegment,cleanupEncodedFrames} from '../long_capture.mjs';
const h='a'.repeat(64),binding={planSha256:h,legacySceneSha256:'b'.repeat(64),sceneRangeSha256:'c'.repeat(64)};
const range={startFrame:599,endFrame:603,totalFrames:2400,fps:30};
function captured(frame){const bytes=Buffer.alloc(32);Buffer.from([137,80,78,71,13,10,26,10]).copy(bytes);bytes.writeUInt32BE(1080,16);bytes.writeUInt32BE(1920,20);bytes.writeUInt32BE(frame,24);
 return {png:'data:image/png;base64,'+bytes.toString('base64'),png_sha256:sha(bytes),raw_rgba_sha256:h,
 diagnostic:{frame,glError:0,universalVideo:{...binding,globalFrame:frame,testOnly:true}}};}
test('half-open absolute ranges support80–600s with no150-frame loop',()=>{
 for(const seconds of [80,120,180,300,600]){const frames=seconds*30;
  assert.equal(validateCaptureRange({startFrame:frames-201,endFrame:frames,totalFrames:frames,fps:30}).frameCount,201);}
 for(const value of [{...range,endFrame:2401},{...range,startFrame:603},{...range,startFrame:-1},{...range,endFrame:600.5}])
  assert.throws(()=>validateCaptureRange(value));
});
test('variable encoding changes only frame contract and keeps originalH264 quality',()=>{
 const args=longEncodingArgs({framesDirectory:'/private/frames',outputFile:'/private/segment.mp4',frameCount:1800,fps:24});
 for(const [key,value]of [['-framerate','24'],['-frames:v','1800'],['-c:v','libx264'],['-crf','16'],['-preset','fast'],['-pix_fmt','yuv420p']])
  assert.equal(args[args.indexOf(key)+1],value);
 assert.equal(args[args.indexOf('-i')+1],'/private/frames/%06d.png');assert.ok(args.includes('-an'));
});
test('production refuses software evidence, timing/hash/dimension tampering',()=>{
 assertCapturedLongFrame(captured(599),599,binding,{production:false});
 assert.throws(()=>assertCapturedLongFrame(captured(599),599,binding));
 for(const mutate of [r=>r.diagnostic.frame=0,r=>r.diagnostic.universalVideo.globalFrame=0,
  r=>r.diagnostic.universalVideo.planSha256='d'.repeat(64),r=>r.diagnostic.glError=1280,r=>r.png_sha256='d'.repeat(64)]){
  const r=captured(599);mutate(r);assert.throws(()=>assertCapturedLongFrame(r,599,binding,{production:false}));
 }
});
test('streaming storesglobal599–602 once, oneinflightframe, NDJSONnotallframearray',async()=>{
 const dir=await mkdtemp('/tmp/long-capture-unit-');let inflight=0,peak=0;const seen=[];
 try{const result=await captureLongFrames({captureFrame:async frame=>{seen.push(frame);inflight++;peak=Math.max(peak,inflight);
  await Promise.resolve();inflight--;return captured(frame);},range,binding,framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),
  checkpointFrames:[599,602],production:false});
 assert.deepEqual(seen,[599,600,601,602]);assert.equal(peak,1);assert.equal(result.completedFrames,4);
 assert.equal(result.boundedMemory.allFrameDiagnosticsInMemory,false);assert.equal(result.checkpoints.length,2);
 assert.deepEqual(await readdir(path.join(dir,'frames')),['000000.png','000001.png','000002.png','000003.png']);
 const rows=(await readFile(path.join(dir,'FRAMES.ndjson'),'utf8')).trim().split('\n').map(JSON.parse);
 assert.deepEqual(rows.map(r=>r.globalFrame),seen);assert.deepEqual(rows.map(r=>r.localFrame),[0,1,2,3]);
 assert.equal(result.frameEvidenceSha256,sha(Buffer.from(await readFile(path.join(dir,'FRAMES.ndjson')))));
 }finally{await rm(dir,{recursive:true});}
});
test('capture failure preserves priorframe/evidence without producing falsecomplete',async()=>{
 const dir=await mkdtemp('/tmp/long-capture-failure-');
 try{await assert.rejects(captureLongFrames({captureFrame:async frame=>{if(frame===601)throw Error('TEST_FAILURE');return captured(frame);},
  range,binding,framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),production:false}),/TEST_FAILURE/);
 assert.equal((await readdir(path.join(dir,'frames'))).length,2);
 assert.equal((await readFile(path.join(dir,'FRAMES.ndjson'),'utf8')).trim().split('\n').length,2);
 }finally{await rm(dir,{recursive:true});}
});
test('segmentmetadata rejects wrongframes/resolution/audio/fps/duration',()=>{
 const probe={streams:[{codec_name:'h264',width:1080,height:1920,avg_frame_rate:'30/1',nb_frames:'4',duration:String(4/30)}]};
 assert.equal(assertEncodedSegment(probe,range),true);
 for(const mutate of [r=>r.streams.push({codec_name:'aac'}),r=>r.streams[0].nb_frames='150',r=>r.streams[0].height=1080,
  r=>r.streams[0].duration='5',r=>r.streams[0].avg_frame_rate='24/1']){
  const p=structuredClone(probe);mutate(p);assert.throws(()=>assertEncodedSegment(p,range));
 }
});

test('new intermediate cleanup requires exact perframeSHA and preserves prior outputs',async()=>{
 const dir=await mkdtemp('/tmp/long-cleanup-');
 try{await writeFile(path.join(dir,'KEEP_OLD.mp4'),'previous approved result');
  await captureLongFrames({captureFrame:async frame=>captured(frame),range,binding,
   framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),production:false});
  const result=await cleanupEncodedFrames({framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),frameCount:4});
  assert.equal(result.removedOwnIntermediateFrames,4);assert.equal(result.existingResultsDeleted,0);
  assert.equal(await readFile(path.join(dir,'KEEP_OLD.mp4'),'utf8'),'previous approved result');
  assert.ok((await readdir(dir)).includes('FRAMES.ndjson'));assert.ok(!(await readdir(dir)).includes('frames'));
 }finally{await rm(dir,{recursive:true});}
});
test('cleanup refuses changed intermediate frame rather than deleting it',async()=>{
 const dir=await mkdtemp('/tmp/long-cleanup-corrupt-');
 try{await captureLongFrames({captureFrame:async frame=>captured(frame),range,binding,
   framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),production:false});
  await writeFile(path.join(dir,'frames','000000.png'),'modified');
  await assert.rejects(cleanupEncodedFrames({framesDirectory:path.join(dir,'frames'),evidenceFile:path.join(dir,'FRAMES.ndjson'),frameCount:4}),/LONG_CLEANUP_CHANGED_FRAME_REFUSED/);
  assert.equal((await readdir(path.join(dir,'frames'))).length,4);
 }finally{await rm(dir,{recursive:true});}
});
test('productionframecannotclaimASTRAwithonlygenericrenderlabel',()=>{
 const actualBinding={...binding,nativePayloadSha256:'d'.repeat(64)},make=()=>{
  const r=captured(599);r.diagnostic.universalVideo={...r.diagnostic.universalVideo,nativePayloadSha256:actualBinding.nativePayloadSha256,testOnly:false};
  r.diagnostic.sourceIntegrity={actualAstraSelected:true,fictional65422SceneUsed:false,sourceBeforeAreaAndFront:true};
  r.diagnostic.terrain={astra:{actualMaterialFactorySelected:true,gpuUploadExecuted:true,testOnly:false}};
  r.diagnostic.area={geometryUnchanged:true};return r;
 };
 assertCapturedLongFrame(make(),599,actualBinding);
 for(const mutate of [r=>r.diagnostic.terrain.astra.gpuUploadExecuted=false,
  r=>r.diagnostic.terrain.astra.testOnly=true,r=>r.diagnostic.sourceIntegrity.fictional65422SceneUsed=true,
  r=>r.diagnostic.universalVideo.nativePayloadSha256='e'.repeat(64)]){
  const r=make();mutate(r);assert.throws(()=>assertCapturedLongFrame(r,599,actualBinding));
 }
});
