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
const base='world-simulation-shorts-engine/recovery/event-v1-v3-visual-detail';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=async p=>JSON.parse(await readFile(p,'utf8'));
const head=async()=> (await execute('git',['rev-parse','HEAD'],{cwd:checkout})).stdout.trim();
const status=async()=> (await execute('git',['status','--porcelain','--untracked-files=no'],{cwd:checkout})).stdout;
const approvedRevision='a7241a1e69d901fdd7ef5212ea5faf34d0ea6baf';
assert.equal(await head(),approvedRevision);assert.equal(await status(),'');
const plan=await json(path.join(checkout,base,'fixtures/DETAIL_ADAPTER_PLAN.json'));
const approved=await json(path.join(checkout,base,'evidence/proof/REPORT.json'));
const inventory=await json(path.join(checkout,base,'manifests/HASH_MANIFEST.json'));
assert.equal(approved.status,'PASS');assert.equal(approved.frames.length,210);
assert.equal(approved.video.sha256,'adea9790ee91834622cdee2cf96ef5715812ea2eb846a18a70984a81469f1049');
await mkdir(out,{recursive:false});
const record={schema:1,status:'STARTED',approvedSourceRevision:approvedRevision,checkout,
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
 const runtime=await import(pathToFileURL(path.join(checkout,base,'visual_runtime.mjs')).href);
 assert.equal(runtime.repo,checkout);
 const {evaluateCameraDetailApproachFrame}=await import(pathToFileURL(path.join(checkout,'world-simulation-shorts-engine/web/map_infographic_v1/camera_detail_approach_adapter_v1.mjs')).href);
 session=await runtime.openVisualRuntime();
 await session.page.evaluate(request=>window.visualDetail.initialize({targetFraming:request.targetFraming,
  mode:'VISUAL_DETAIL_ADMITTED',certificate:request.certificate}),plan.request);
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
 for(let frame=0;frame<plan.totalFrames;frame++){
  const schedule=evaluateCameraDetailApproachFrame(plan,frame);
  const row=await session.page.evaluate(s=>window.visualDetail.capture({frame:s.frame,bounds:s.flatBounds,cameraLocked:s.cameraLocked,
   eventFrame:s.eventFrame,eventEnabled:s.eventEnabled,protect:s.eventEnabled,png:true}),schedule);
  const png=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  const golden=approved.frames[frame],event=row.diagnostic.event;
  assert.equal(row.raw_rgba_sha256,golden.raw_rgba_sha256,'RAW_RGBA_FRAME_'+frame);
  assert.equal(sha(png),golden.png_sha256,'NATIVE_PNG_FRAME_'+frame);
  assert.deepEqual(row.diagnostic.gpu.actualCamera.bounds,golden.bounds);
  assert.equal(schedule.state,golden.state);assert.equal(schedule.cameraLocked,golden.cameraLocked);
  assert.equal(schedule.eventFrame,golden.eventFrame);assert.deepEqual(event.controls,golden.event.controls);
  assert.equal(row.diagnostic.gpu.glError,0);
  if(schedule.eventEnabled){assert.equal(row.protected_changed_pixels,0);assert.equal(row.marker_changed_pixels,0);assert.equal(row.outside_roi_changed_pixels,0);}
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
  record.frames.push({frame,state:schedule.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:sha(png),
   rawBitExact:true,pngBitExact:true,cameraTimelineEventIdentical:true});
  if(frame%15===0||frame===209)console.log(JSON.stringify({phase:'CLEAN_REPRODUCTION',frame,total:210}));
 }
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'ENCODER_FAILED '+encoderError);
 const original=await readFile(path.join(checkout,base,'public-review',filename)),reproduced=await readFile(video);
 assert.equal(sha(original),approved.video.sha256);
 const mp4Exact=sha(reproduced)===approved.video.sha256;
 const {stdout:probe}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video]);
 record.ffprobe=JSON.parse(probe);const stream=record.ffprobe.streams[0];assert.equal(record.ffprobe.streams.length,1);
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(Number(stream.nb_read_frames),210);assert.equal(Number(stream.duration),7);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 let decodedEquality='IMPLIED_BY_IDENTICAL_MP4_BYTES';
 if(!mp4Exact){
  const hashes=async f=>(await execute('ffmpeg',['-v','error','-threads','2','-i',f,'-map','0:v:0','-pix_fmt','rgb24','-f','framehash','-hash','sha256','-'],{maxBuffer:1048576})).stdout.split('\n').filter(s=>s&&!s.startsWith('#')).map(s=>s.split(',').map(v=>v.trim()));
  const [a,b]=await Promise.all([hashes(path.join(checkout,base,'public-review',filename)),hashes(video)]);
  assert.equal(a.length,210);assert.deepEqual(b,a,'DECODED_VIDEO_PIXELS_DIFFER');decodedEquality='210_OF_210_FRAME_HASHES_EQUAL';
 }
 assert.equal(session.errors.length,0);assert.equal(await status(),'');assert.equal(await head(),approvedRevision);
 record.status='PASS';record.result=mp4Exact?'BIT_EXACT':'DECODED_PIXEL_EQUALITY';record.cleanCheckoutAfter=true;
 record.rawFramesBitExact=210;record.nativePngFramesBitExact=210;record.checkpointPngsBitExact=7;
 record.video={file:filename,sha256:sha(reproduced),bytes:reproduced.length,approvedSha256:approved.video.sha256,bitExact:mp4Exact,decodedEquality};
 record.actualRuntimeOrigin=checkout;record.requiredTempOnlyFiles=[];
}catch(error){record.status='FAIL';record.error=error.message;throw error;}
finally{
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
 try{await session?.close();}catch(error){record.status='FAIL';record.cleanupError=error.message;throw error;}
 finally{record.completedAtUtc=new Date().toISOString();await writeFile(path.join(out,'CLEAN_REPRODUCTION.json'),JSON.stringify(record,null,2)+'\n',{flag:'wx'});}
}
console.log(JSON.stringify({status:record.status,result:record.result,rawFrames:record.rawFramesBitExact,pngs:record.checkpointPngsBitExact,video:record.video}));
