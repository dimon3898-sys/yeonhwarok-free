/** Final verification only: render unchanged approved source from an actual remote checkout. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {once} from 'node:events';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';

const execute=promisify(execFile),argv=process.argv.slice(2);
assert.equal(argv.length,4);assert.equal(argv[0],'--checkout');assert.equal(argv[2],'--output-dir');
const checkout=await realpath(argv[1]),out=path.resolve(argv[3]);
const finalRoot=path.dirname(fileURLToPath(import.meta.url));
assert.ok(!out.startsWith(checkout+path.sep),'Verification outputs cannot overwrite approved checkout files');
const base='world-simulation-shorts-engine/recovery/event-tsunami-wave-polish-v3';
const approvedRevision='a6ef67fa16143dc2bd53b334d583c05cf1476bed';
const originalRenderRevision='1e52b58deaf0fa1a48d6966c0d0e19f55e8b8cd0';
const mediaRevision='263a5250671a36297892ebe4b11380fdfb927a9b';
const approvedSha='d41891620cf08aa953eed78e5b0d443b51843b173912fa1f887fb7e163d9ead7';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const shaFile=async filename=>{const hash=createHash('sha256');for await(const chunk of createReadStream(filename))hash.update(chunk);return hash.digest('hex');};
const json=async p=>JSON.parse(await readFile(p,'utf8'));
const git=async args=>(await execute('git',args,{cwd:checkout,maxBuffer:16*1024*1024})).stdout.trim();
assert.equal(await git(['rev-parse','HEAD']),approvedRevision);assert.equal(await git(['status','--porcelain']),'');
const setup=await json(path.join(finalRoot,'evidence/CLEAN_CHECKOUT_SETUP.json'));
assert.equal(setup.status,'PASS');assert.equal(setup.revision,approvedRevision);assert.equal(setup.checkout,checkout);
const approved=await json(path.join(checkout,base,'evidence/proof/REPORT.json'));
const inventory=await json(path.join(checkout,base,'manifests/HASH_MANIFEST.json'));
assert.equal(approved.status,'PASS');assert.equal(approved.sourceCommit,originalRenderRevision);
assert.equal(approved.frames.length,240);assert.equal(approved.checkpoints.length,8);assert.equal(approved.video.sha256,approvedSha);
await mkdir(out,{recursive:false});
const record={schema:1,status:'STARTED',approvedSourceRevision:approvedRevision,originalRenderSourceRevision:originalRenderRevision,
 approvedMediaRevision:mediaRevision,checkout,command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()},
 startedAtUtc:new Date().toISOString(),cleanCheckoutBefore:true,remoteCheckoutReceipt:'CLEAN_CHECKOUT_SETUP.json',
 sharedSystemToolchain:true,noLocalSourceOrAssetCopies:true,sourceBindings:[],requiredInputs:[],frames:[],checkpoints:[],
 originalPublicProofModified:false};
let session,encoder,encoderExit,encoderStopped=null,encoderError='';
try{
 // All inherited and active inputs come from canonical remote Git/Git LFS, with pinned hashes.
 for(const expected of inventory.required_files){
  const file=path.resolve(checkout,expected.path);assert.ok(file.startsWith(checkout+path.sep));
  assert.equal(await realpath(file),file,'SYMLINK_REQUIRED_INPUT');
  assert.equal(await shaFile(file),expected.sha256,expected.path);record.requiredInputs.push(expected);
 }
 for(const filename of ['HASH_MANIFEST.json','SHA256SUMS']){
  const relative=base+'/manifests/'+filename,body=await readFile(path.join(checkout,relative));
  record.requiredInputs.push({path:relative,sha256:sha(body),bytes:body.length});
 }
 // Bind actual executable/fixture input blobs to the exact prerender source and media commits.
 const sourcePaths=[base+'/wave_runtime.mjs',base+'/render_proof.mjs',base+'/fixtures/REAL_FIXTURE.json',
  'world-simulation-shorts-engine/web/map_infographic_v1/wave_visual_v3.mjs',
  'world-simulation-shorts-engine/web/map_infographic_v1/wave_gpu_adapter_v3.mjs'];
 for(const sourcePath of sourcePaths){
  const current=await git(['rev-parse',approvedRevision+':'+sourcePath]);
  const original=await git(['rev-parse',originalRenderRevision+':'+sourcePath]);
  const media=await git(['rev-parse',mediaRevision+':'+sourcePath]);
  assert.equal(current,original,'ORIGINAL_RENDER_SOURCE_CHANGED');assert.equal(current,media,'MEDIA_SOURCE_CHANGED');
  record.sourceBindings.push({path:sourcePath,gitBlob:current,originalRenderSourceIdentical:true,approvedMediaSourceIdentical:true});
 }
 const runtime=await import(pathToFileURL(path.join(checkout,base,'wave_runtime.mjs')).href);
 assert.equal(runtime.repo,checkout);session=await runtime.openWaveRuntime();
 assert.equal(session.presentation.totalFrames,240);record.runtimeInfo=session.info;
 const filename=approved.video.file,video=path.join(out,filename);
 const encodeArgs=approved.encodeCommand.slice(1,-1).concat(video);
 record.encodeCommand=['ffmpeg',...encodeArgs];encoder=spawn('ffmpeg',encodeArgs,{stdio:['pipe','ignore','pipe']});
 encoder.stderr.on('data',v=>{encoderError=(encoderError+v).slice(-4096);});
 encoderExit=new Promise(resolve=>{const stop=result=>{encoderStopped??=result;resolve(encoderStopped);};
  encoder.once('error',error=>stop({error:error.message}));encoder.once('exit',code=>stop({code}));
  encoder.stdin.once('error',error=>{encoderError+=' '+error.message;stop({error:error.message});});});
 const checkpoints=new Map(approved.checkpoints.map(row=>[row.frame,row]));
 for(let frame=0;frame<240;frame++){
  const row=await session.page.evaluate(frame=>window.waveProof.capture(frame,{protect:true,png:true}),frame);
  const png=Buffer.from(row.png.split(',')[1],'base64');delete row.png;
  const golden=approved.frames[frame],diagnostic=row.diagnostic,wave=diagnostic.wave;
  assert.equal(row.raw_rgba_sha256,golden.raw_rgba_sha256,'RAW_RGBA_FRAME_'+frame);
  assert.equal(sha(png),golden.png_sha256,'NATIVE_PNG_FRAME_'+frame);
  assert.deepEqual(diagnostic.camera.camera.flatBounds,golden.cameraBounds);
  assert.equal(diagnostic.state,golden.state);assert.equal(diagnostic.camera.cameraLocked,golden.cameraLocked);
  assert.equal(diagnostic.camera.nativeFrame,golden.cameraNativeFrame);
  assert.equal(wave.enabled,golden.wave.enabled);assert.equal(wave.geometryUnchanged,true);
  assert.equal(wave.closedPropagationRing,false);assert.deepEqual(wave.diagnostics,golden.wave.diagnostics);
  assert.deepEqual(wave.controls?{physicalSimulation:wave.controls.physicalSimulation,
   propagations:wave.controls.propagations.map(item=>({id:item.id,geometry:item.geometry,alpha:item.alpha}))}:null,golden.wave.controls);
  assert.equal(diagnostic.glError,0);
  for(const key of ['protectedChangedPixels','markerChangedPixels','outsideRoiChangedPixels','safeAreaChangedPixels'])assert.equal(wave.protection[key],0);
  assert.equal(encoderStopped,null,'ENCODER_STOPPED_EARLY '+JSON.stringify(encoderStopped));
  if(!encoder.stdin.write(png)){
   const drained=once(encoder.stdin,'drain').then(()=>({drained:true}),error=>({error:error.message}));
   const result=await Promise.race([drained,encoderExit]);assert.equal(result.drained,true,'ENCODER_BACKPRESSURE_FAILED '+JSON.stringify(result));
  }
  const checkpoint=checkpoints.get(frame);
  if(checkpoint){
   const original=await readFile(path.join(checkout,base,'public-review',checkpoint.file));
   assert.deepEqual(png,original);await writeFile(path.join(out,checkpoint.file),png,{flag:'wx'});
   record.checkpoints.push({...checkpoint,bitExact:true});
  }
  record.frames.push({frame,state:diagnostic.state,raw_rgba_sha256:row.raw_rgba_sha256,png_sha256:sha(png),
   rawBitExact:true,pngBitExact:true,cameraTimelineEventIdentical:true,waveControlsIdentical:true});
  if(frame%15===0||frame===239)console.log(JSON.stringify({phase:'CLEAN_REPRODUCTION',frame,total:240}));
 }
 encoder.stdin.end();assert.equal((await encoderExit).code,0,'ENCODER_FAILED '+encoderError);
 const originalVideo=path.join(checkout,base,'public-review',filename);
 assert.equal(await shaFile(originalVideo),approvedSha);
 const reproduced=await readFile(video),mp4Exact=sha(reproduced)===approvedSha;
 const {stdout:probe}=await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video]);
 record.ffprobe=JSON.parse(probe);const stream=record.ffprobe.streams[0];assert.equal(record.ffprobe.streams.length,1);
 assert.equal(stream.width,1080);assert.equal(stream.height,1920);assert.equal(stream.avg_frame_rate,'30/1');
 assert.equal(stream.codec_name,'h264');assert.equal(Number(stream.nb_read_frames),240);assert.equal(Number(stream.duration),8);
 await execute('ffmpeg',['-v','error','-xerror','-threads','2','-i',video,'-map','0:v:0','-f','null','-']);
 let decodedEquality='IMPLIED_BY_IDENTICAL_MP4_BYTES';
 if(!mp4Exact){
  const hashes=async file=>(await execute('ffmpeg',['-v','error','-threads','2','-i',file,'-map','0:v:0','-pix_fmt','rgb24',
   '-f','framehash','-hash','sha256','-'],{maxBuffer:1048576})).stdout.split('\n').filter(s=>s&&!s.startsWith('#')).map(s=>s.split(',').map(v=>v.trim()));
  const [a,b]=await Promise.all([hashes(originalVideo),hashes(video)]);
  assert.equal(a.length,240);assert.deepEqual(b,a,'DECODED_VIDEO_PIXELS_DIFFER');decodedEquality='240_OF_240_FRAME_HASHES_EQUAL';
 }
 assert.equal(session.errors.length,0);assert.equal(await git(['status','--porcelain']),'');assert.equal(await git(['rev-parse','HEAD']),approvedRevision);
 record.status='PASS';record.result=mp4Exact?'BIT_EXACT':'DECODED_PIXEL_EQUALITY';record.cleanCheckoutAfter=true;
 record.rawFramesBitExact=240;record.nativePngFramesBitExact=240;record.checkpointPngsBitExact=8;
 record.video={file:filename,sha256:sha(reproduced),bytes:reproduced.length,approvedSha256:approvedSha,bitExact:mp4Exact,decodedEquality};
 record.actualRuntimeOrigin=checkout;record.requiredTempOnlyFiles=[];
}catch(error){record.status='FAIL';record.error=error.message;throw error;}
finally{
 if(encoder&&encoder.exitCode===null)encoder.kill('SIGTERM');
 try{await session?.close();}catch(error){record.status='FAIL';record.cleanupError=error.message;throw error;}
 finally{record.completedAtUtc=new Date().toISOString();
  await writeFile(path.join(out,'CLEAN_REPRODUCTION.json'),JSON.stringify(record,null,2)+'\n',{flag:'wx'});
  await writeFile(path.join(finalRoot,'evidence/CLEAN_REPRODUCTION.json'),JSON.stringify(record,null,2)+'\n');}
}
console.log(JSON.stringify({status:record.status,result:record.result,rawFrames:record.rawFramesBitExact,pngs:record.checkpointPngsBitExact,video:record.video}));
