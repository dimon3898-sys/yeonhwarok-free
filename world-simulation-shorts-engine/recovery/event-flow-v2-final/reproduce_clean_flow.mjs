// Final verification only. Import the unchanged approved runtime from an actual remote checkout.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {once} from 'node:events';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const execute=promisify(execFile),argv=process.argv.slice(2);
assert.equal(argv.length,4);assert.equal(argv[0],'--checkout');assert.equal(argv[2],'--output-dir');
const checkout=await realpath(argv[1]),out=path.resolve(argv[3]);
assert.ok(!out.startsWith(checkout+path.sep),'Verification outputs cannot overwrite approved checkout files');
const base='world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=async p=>JSON.parse(await readFile(p,'utf8'));
const head=async()=> (await execute('git',['rev-parse','HEAD'],{cwd:checkout})).stdout.trim();
const status=async()=> (await execute('git',['status','--porcelain'],{cwd:checkout})).stdout;
const approvedRevision='4a1f773dcf377ebca5e46d83b81204707a56b59d';
const originalRenderRevision='be428ab6dbe6723f8b3cc25a287c18a744a9c318';
assert.equal(await head(),approvedRevision);assert.equal(await status(),'');
const plan=await json(path.join(checkout,base,'fixtures/DETAIL_ADAPTER_PLAN.json'));
const approved=await json(path.join(checkout,base,'evidence/proof/REPORT.json'));
const inventory=await json(path.join(checkout,base,'manifests/HASH_MANIFEST.json'));
assert.equal(approved.status,'PASS');assert.equal(approved.frames.length,240);
assert.equal(approved.checkpoints.length,6);
assert.equal(approved.video.sha256,'5ff055643ded594198f3dc5e313d9acadb6b636d4f621294ad69456d4b6449fe');
await mkdir(out,{recursive:false});
const record={schema:1,status:'STARTED',approvedSourceRevision:approvedRevision,originalRenderSourceRevision:originalRenderRevision,checkout,
 command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()},startedAtUtc:new Date().toISOString(),
 cleanCheckoutBefore:true,remoteCheckoutReceipt:'CLEAN_CHECKOUT_SETUP.json',sharedSystemToolchain:true,
 noLocalSourceOrAssetCopies:true,requiredInputs:[],frames:[],checkpoints:[],originalPublicProofModified:false};
let session,encoder,encoderExit,encoderStopped=null,encoderError='';
try{
 // Bind every actual runtime/source/asset/fixture/dependency input to the approved inventory.
 for(const expected of inventory.required_files){
  const file=path.resolve(checkout,expected.path);assert.ok(file.startsWith(checkout+path.sep));
  assert.equal(await realpath(file),file,'SYMLINK_REQUIRED_INPUT');
  const bytes=await readFile(file);assert.equal(bytes.length,expected.bytes,expected.path);
  assert.equal(sha(bytes),expected.sha256,expected.path);record.requiredInputs.push(expected);
 }
 for(const filename of ['HASH_MANIFEST.json','SHA256SUMS']){
  const relative=base+'/manifests/'+filename,body=await readFile(path.join(checkout,relative));
  record.requiredInputs.push({path:relative,sha256:sha(body),bytes:body.length});
 }
 assert.equal(record.requiredInputs.length,415);
 const runtime=await import(pathToFileURL(path.join(checkout,base,'polish_runtime.mjs')).href);
 assert.equal(runtime.repo,checkout);
 session=await runtime.openPolishRuntime();
 assert.equal(approved.sourceCommit,originalRenderRevision);
 assert.equal(session.detailPlan.totalFrames,240);
 const filename=approved.video.file,video=path.join(out,filename);
 const encodeArgs=approved.encodeCommand.slice(1,-1).concat(video);
 record.encodeCommand=['ffmpeg',...encodeArgs];encoder=spawn('ffmpeg',encodeArgs,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 // Resolve errors immediately so an early encoder exit cannot leave a drain wait hanging.
 encoderExit=new Promise(resolve=>{
  const stop=result=>{encoderStopped??=result;resolve(encoderStopped);};
  encoder.once('error',error=>stop({error:error.message}));
  encoder.once('exit',code=>stop({code}));
  encoder.stdin.once('error',error=>{encoderError+=' '+error.message;stop({error:error.message});});
 });
 const checkpointByFrame=new Map(approved.checkpoints.map(c=>[c.frame,c]));
 assert.equal(checkpointByFrame.size,6);
 for(let frame=0;frame<plan.totalFrames;frame++){
  const row=await session.page.evaluate(frame=>window.flowProof.capture(frame,{protect:true,png:true}),frame);
  const png=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  const golden=approved.frames[frame],diagnostic=row.diagnostic,flow=diagnostic.flow;
  assert.equal(row.raw_rgba_sha256,golden.raw_rgba_sha256,'RAW_RGBA_FRAME_'+frame);
  assert.equal(sha(png),golden.png_sha256,'NATIVE_PNG_FRAME_'+frame);
  assert.deepEqual(diagnostic.camera.flatBounds,golden.cameraBounds);
  assert.equal(diagnostic.state,golden.state);assert.equal(diagnostic.camera.cameraLocked,golden.cameraLocked);
  assert.deepEqual(flow.controls,golden.flow.controls);assert.deepEqual(flow.primitive,golden.flow.primitive);
  assert.deepEqual(flow.visualControls,golden.flow.visualControls);assert.deepEqual(flow.visualProfile,golden.flow.visualProfile);
  assert.deepEqual(flow.style,golden.flow.style);assert.equal(flow.enabled,golden.flow.enabled);
  assert.equal(diagnostic.glError,0);assert.equal(flow.protection.protectedChangedPixels,0);
  assert.equal(flow.protection.markerChangedPixels,0);assert.equal(flow.protection.outsideRoiChangedPixels,0);
  if(frame>=plan.detailLockFrame)assert.equal(flow.graphics.nativeStateRestored,true);
  assert.equal(encoderStopped,null,'ENCODER_STOPPED_EARLY '+JSON.stringify(encoderStopped));
  if(!encoder.stdin.write(png)){
   const drained=once(encoder.stdin,'drain').then(()=>({drained:true}),error=>({error:error.message}));
   const result=await Promise.race([drained,encoderExit]);
   assert.equal(result.drained,true,'ENCODER_BACKPRESSURE_FAILED '+JSON.stringify(result));
  }
  const checkpoint=checkpointByFrame.get(frame);
  if(checkpoint){
   const original=await readFile(path.join(checkout,base,'public-review',checkpoint.file));
   assert.deepEqual(png,original);await writeFile(path.join(out,checkpoint.file),png,{flag:'wx'});
   record.checkpoints.push({...checkpoint,bitExact:true});
  }
  record.frames.push({frame,state:diagnostic.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:sha(png),
   rawBitExact:true,pngBitExact:true,cameraTimelineEventIdentical:true,cameraTimelineFlowIdentical:true});
  if(frame%15===0||frame===239)console.log(JSON.stringify({phase:'CLEAN_REPRODUCTION',frame,total:240}));
 }
 assert.equal(record.frames.length,240);assert.equal(record.checkpoints.length,6);
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'ENCODER_FAILED '+encoderError);
 const original=await readFile(path.join(checkout,base,'public-review',filename)),reproduced=await readFile(video);
 assert.equal(sha(original),approved.video.sha256);
 const mp4Exact=sha(reproduced)===approved.video.sha256;
 const {stdout:probe}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video]);
 record.ffprobe=JSON.parse(probe);const stream=record.ffprobe.streams[0];assert.equal(record.ffprobe.streams.length,1);
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(stream.codec_name,'h264');
 assert.equal(Number(stream.nb_read_frames),240);assert.equal(Number(stream.duration),8);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 let decodedEquality='IMPLIED_BY_IDENTICAL_MP4_BYTES';
 if(!mp4Exact){
  const hashes=async f=>(await execute('ffmpeg',['-v','error','-threads','2','-i',f,'-map','0:v:0','-pix_fmt','rgb24','-f','framehash','-hash','sha256','-'],{maxBuffer:1048576})).stdout.split('\n').filter(s=>s&&!s.startsWith('#')).map(s=>s.split(',').map(v=>v.trim()));
  const [a,b]=await Promise.all([hashes(path.join(checkout,base,'public-review',filename)),hashes(video)]);
  assert.equal(a.length,240);assert.deepEqual(b,a,'DECODED_VIDEO_PIXELS_DIFFER');decodedEquality='240_OF_240_FRAME_HASHES_EQUAL';
 }
 assert.equal(session.errors.length,0);assert.equal(await status(),'');assert.equal(await head(),approvedRevision);
 record.status='PASS';record.result=mp4Exact?'BIT_EXACT':'DECODED_PIXEL_EQUALITY';record.cleanCheckoutAfter=true;
 record.rawFramesBitExact=record.frames.filter(f=>f.rawBitExact).length;
 record.nativePngFramesBitExact=record.frames.filter(f=>f.pngBitExact).length;
 record.checkpointPngsBitExact=record.checkpoints.filter(c=>c.bitExact).length;
 record.video={file:filename,sha256:sha(reproduced),bytes:reproduced.length,approvedSha256:approved.video.sha256,bitExact:mp4Exact,decodedEquality};
 record.actualRuntimeOrigin=checkout;record.requiredTempOnlyFiles=[];
}catch(error){record.status='FAIL';record.error=error.message;throw error;}
finally{
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
 try{await session?.close();}catch(error){record.status='FAIL';record.cleanupError=error.message;throw error;}
 finally{record.completedAtUtc=new Date().toISOString();await writeFile(path.join(out,'CLEAN_REPRODUCTION.json'),JSON.stringify(record,null,2)+'\n',{flag:'wx'});}
}
console.log(JSON.stringify({status:record.status,result:record.result,rawFrames:record.rawFramesBitExact,pngs:record.checkpointPngsBitExact,video:record.video}));
