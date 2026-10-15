/** ASTRA capture orchestration. Camera, frame engine, encoder and storage APIs are inherited. */
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile, open, rename, unlink, stat, readdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {processIdentity, isActiveCapture, originalEncodingArgs} from '../rtx-gpu-package-v1/hardware_render.mjs';
import {readAdmission, assertQualityDiagnostic, packageRoot, repo, movieName, json, sha} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
import {loadAstraRuntimePlan, openAstraRuntime} from './astra_runtime.mjs';

const execute = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));
const exists = file => stat(file).then(() => true, () => false);
const atomic = async (file, data) => {
 const pending = file + '.writing';
 await writeFile(pending, JSON.stringify(data) + '\n', {flag:'wx', mode:0o600});
 await rename(pending, file);
};
const codeOf = error => /^[A-Z][A-Z0-9_]{1,95}$/.test(error?.message ?? '') ? error.message : 'ASTRA_CAPTURE_FAILED';

export function captureSignature({plan, admission, stagingReceiptSha256, extensionManifestSha256}) {
 for (const value of [plan.sourceSignature, plan.activationSha256, plan.bundleManifestSha256,
  stagingReceiptSha256, extensionManifestSha256]) assert.match(value, /^[0-9a-f]{64}$/);
 return sha(Buffer.from(JSON.stringify({schema:'ASTRA_CAPTURE_SIGNATURE_V1',
  profileId:plan.profileId ?? plan.profile?.profileId, runtimeSourceSignature:plan.sourceSignature,
  activationSha256:plan.activationSha256, bundleManifestSha256:plan.bundleManifestSha256,
  extensionManifestSha256, stagingReceiptSha256, hardwareProfileFingerprint:admission.probe.profile_fingerprint,
  browser:admission.probe.browser_version, model:admission.allocation.model, driver:admission.allocation.driver_version})));
}

export function assertAstraFrame(captured, frame) {
 assertQualityDiagnostic(captured.diagnostic, {frame});
 const astra = captured.diagnostic.terrain?.astra;
 assert.ok(astra && astra.actualMaterialFactorySelected === true, 'ASTRA_MATERIAL_NOT_SELECTED');
 assert.equal(astra.selected,true);assert.ok(Number.isSafeInteger(astra.drawPasses)&&astra.drawPasses>0);
 assert.equal(astra.sourceMaterialBeforeTerritory, true, 'ASTRA_COMPOSITION_ORDER_UNVERIFIED');
 assert.equal(astra.combinedOutputTexture, true);assert.equal(astra.actualNativeCoverage, true);
 assert.equal(astra.gpuUploadExecuted, true);assert.equal(astra.testOnly, false);
 assert.deepEqual([...astra.selectedSourceRoles].sort(),['bathymetry','surfaceTexture','terrain']);
 assert.match(captured.raw_rgba_sha256, /^[0-9a-f]{64}$/);
}

async function verifySources() {
 const staged = JSON.parse((await execute('/usr/bin/python3', ['-B',path.join(packageRoot,'stage_package.py'),
  'verify-context','--package-root',path.dirname(repo)], {maxBuffer:1024*1024})).stdout);
 assert.equal(staged.status,'PASS','ORIGINAL_SOURCE_CONTRACT_INVALID');
 const extension = JSON.parse((await execute('/usr/bin/python3', ['-B',path.join(here,'prepare_activation.py'),
  '--verify-extension'], {maxBuffer:1024*1024})).stdout);
 assert.equal(extension.status,'PASS','ASTRA_EXTENSION_CONTRACT_INVALID');
 assert.match(extension.manifestSha256,/^[0-9a-f]{64}$/);
 return {staged, extension};
}

/** No alternate runtime or encoder injection is exposed by this production entrypoint. */
export async function captureAstra({admissionFile, outputRoot,
 activationFile=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_FILE,
 activationSha256=process.env.WORLD_ENGINE_ASTRA_ACTIVATION_SHA256}={}) {
 assert.ok(typeof outputRoot==='string' && path.isAbsolute(outputRoot),'PERSISTENT_ABSOLUTE_OUTPUT_REQUIRED');
 const admission=await readAdmission(admissionFile), before=await verifySources();
 assert.equal(before.staged.sourceContractSha256,admission.sourceVerification.sourceContractSha256);
 const plan=await loadAstraRuntimePlan({activationFile,expectedActivationSha256:activationSha256});
 assert.equal(plan.fixture.totalFrames,150); assert.equal(plan.fixture.fps,30);
 const stagingReceiptSha256=sha(await readFile(path.join(path.dirname(repo),'STAGING_RECEIPT.json')));
 const signature=captureSignature({plan,admission,stagingReceiptSha256,
  extensionManifestSha256:before.extension.manifestSha256});
 const runRoot=path.join(outputRoot,'captures',signature), framesDir=path.join(runRoot,'frames'),
  publicDir=path.join(runRoot,'public-review'), lockPath=path.join(runRoot,'ACTIVE_CAPTURE_LOCK.json');
 assert.ok(!path.resolve(runRoot).startsWith(path.resolve(repo)+path.sep),'SOURCE_TREE_OUTPUT_FORBIDDEN');
 await mkdir(runRoot,{recursive:true,mode:0o700});
 if(await exists(lockPath)) {
  if(await isActiveCapture(await json(lockPath))) throw Error('GPU_CAPTURE_ALREADY_RUNNING');
  throw Error('ASTRA_PREVIOUS_CAPTURE_REQUIRES_REVIEW');
 }
 if((await readdir(runRoot)).length) throw Error('ASTRA_PREVIOUS_CAPTURE_REQUIRES_REVIEW');
 for(const dir of [framesDir,publicDir]) await mkdir(dir,{mode:0o700});
 const identity=await processIdentity(), lock=await open(lockPath,'wx',0o600);
 await lock.writeFile(JSON.stringify({...identity,signature})+'\n'); await lock.close();
 const checkpoints=new Map(), names=new Set();
 for(const item of plan.fixture.checkpoints) {
  assert.ok(Number.isSafeInteger(item.frame)&&item.frame>=0&&item.frame<150);
  assert.match(item.name,/^[A-Z0-9_]+\.png$/i);assert.ok(!names.has(item.name));names.add(item.name);
  checkpoints.set(item.frame,[...(checkpoints.get(item.frame)??[]),item.name]);
 }
 assert.equal(names.size,5,'EXACT_FIVE_CHECKPOINTS_REQUIRED');
 const report={schema:'RTX_GPU_HARDWARE_CAPTURE_V1',status:'IN_PROGRESS',signature,sourceVerification:before.staged,
  astraProfileId:plan.profileId??plan.profile?.profileId,activationSha256:plan.activationSha256,
  bundleManifestSha256:plan.bundleManifestSha256,extensionManifestSha256:before.extension.manifestSha256,
  runtimeSourceSignature:plan.sourceSignature,stagingReceiptSha256,hardware:admission.probe,
  output:[1080,1920],totalFrames:150,fps:30,durationSeconds:5,audio:false,frames:[],checkpoints:[],
  reusedFrames:0,qualityParityClaimed:false,userVideoApproved:false,finalPromotion:false,
  visualQualityVerified:false,requiredTempOnlyFiles:0,startedAt:new Date().toISOString()};
 let session,pendingCleanup,failure;
 const interrupted=()=>{const close=session?()=>session.close():pendingCleanup;
  Promise.resolve().then(()=>close?.()).finally(()=>process.exit(143));};
 process.once('SIGTERM',interrupted);
 try {
  session=await openAstraRuntime({mode:'VISUAL_REFERENCE_STUDY',admissionFile,activationFile,
   expectedActivationSha256:activationSha256,onPendingCleanup:cleanup=>{pendingCleanup=cleanup;}});
  assert.equal(session.info.productionEligible,true);assert.equal(session.info.cameraMotion.status,'PASS');
  assert.equal(session.info.cameraMotion.fakeLockCount,0);
  assert.equal(session.info.astra.actualMaterialFactorySelected,true,'ASTRA_RUNTIME_NOT_SELECTED');
  assert.equal(session.info.astra.activationSha256,plan.activationSha256);
  assert.equal(session.info.astra.bundleManifestSha256,plan.bundleManifestSha256);report.runtime=session.info;
  for(let frame=0;frame<150;frame++) {
   const captured=await session.page.evaluate(async frame=>window.referenceProof.capture(frame,{png:true}),frame);
   assertAstraFrame(captured,frame);
   assert.ok(typeof captured.png==='string'&&captured.png.startsWith('data:image/png;base64,'),'PNG_CAPTURE_REQUIRED');
   const bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
   await writeFile(path.join(framesDir,String(frame).padStart(3,'0')+'.png'),bytes,{flag:'wx',mode:0o600});
   const row={signature,frame,raw_rgba_sha256:captured.raw_rgba_sha256,png_sha256:captured.png_sha256,
    diagnostic:captured.diagnostic};report.frames.push(row);
   for(const file of checkpoints.get(frame)??[]) {
    await writeFile(path.join(publicDir,file),bytes,{flag:'wx',mode:0o600});
    report.checkpoints.push({file,frame,sha256:sha(bytes),bytes:bytes.length});
   }
   if(frame%30===0||frame===149) {
    await atomic(path.join(runRoot,'CAPTURE_STATUS.json'),{signature,lastFrame:frame,status:'IN_PROGRESS',profile:'ASTRA'});
    console.log(JSON.stringify({phase:'RTX_NATIVE_CAPTURE',profile:'ASTRA',frame,total:150,reused:0}));
   }
  }
  assert.equal(session.errors.length,0,'ASTRA_BROWSER_RUNTIME_ERROR');await session.close();session=null;
  const verified=await verifySources();assert.deepEqual(verified,before,'SOURCE_CHANGED_DURING_CAPTURE');
  const partial=path.join(runRoot,'ASTRA_HARDWARE_ENCODING.mp4'),video=path.join(publicDir,movieName);
  const command=originalEncodingArgs(framesDir,partial);
  await execute('ffmpeg',command,{maxBuffer:8*1024*1024});
  const encoded=await readFile(partial);
  await atomic(path.join(runRoot,'ENCODING_RECEIPT.json'),{signature,sha256:sha(encoded),bytes:encoded.length,
   command:['ffmpeg',...command]});await rename(partial,video);
  report.ffprobe=JSON.parse((await execute('ffprobe',['-v','error','-show_streams','-show_format','-of','json',video])).stdout);
  assert.equal(report.ffprobe.streams.length,1);const stream=report.ffprobe.streams[0];
  assert.equal(stream.codec_name,'h264');assert.equal(stream.width,1080);assert.equal(stream.height,1920);
  assert.equal(stream.avg_frame_rate,'30/1');assert.equal(Number(stream.nb_frames),150);assert.equal(Number(stream.duration),5);
  report.video={file:movieName,sha256:sha(encoded),bytes:encoded.length};
  const sums=[report.video,...report.checkpoints].sort((a,b)=>a.file.localeCompare(b.file));
  await writeFile(path.join(publicDir,'SHA256SUMS'),sums.map(item=>item.sha256+'  '+item.file).join('\n')+'\n',
   {flag:'wx',mode:0o600});
  assert.deepEqual((await readdir(publicDir)).sort(),[movieName,'SHA256SUMS',...names].sort(),'PUBLIC_ALLOWLIST_REQUIRED');
  assert.deepEqual(await verifySources(),before,'SOURCE_CHANGED_DURING_ENCODING');
  report.astraApplied=true;report.status='CAPTURE_TECHNICAL_PASS';report.publicDirectory=publicDir;report.next='USER_VIDEO_REVIEW_REQUIRED';
 } catch(error) { failure=error;report.status='BLOCKED';report.error=codeOf(error); }
 finally {
  try{await session?.close();}catch(error){failure??=error;report.status='BLOCKED';report.error??=codeOf(error);}
  report.completedAt=new Date().toISOString();
  try{await atomic(path.join(runRoot,'REPORT.json'),report);await atomic(path.join(runRoot,'CAPTURE_STATUS.json'),
   {signature,status:report.status,lastFrame:report.frames.length-1,profile:'ASTRA'});}finally{await unlink(lockPath);}
  process.removeListener('SIGTERM',interrupted);
 }
 if(failure)throw failure;
 console.log(JSON.stringify({status:report.status,video:report.video,publicDirectory:publicDir,
  astraMaterialSelected:true,visualQualityVerified:false}));return report;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 try {
  const args=process.argv.slice(2),options={};
  while(args.length){const key=args.shift();assert.ok(['--admission-file','--output-root'].includes(key)&&args.length,
   'EXPLICIT_RENDER_ARGUMENTS_REQUIRED');assert.ok(!Object.hasOwn(options,key),'DUPLICATE_RENDER_ARGUMENT');options[key]=args.shift();}
  await captureAstra({admissionFile:options['--admission-file'],outputRoot:options['--output-root']});
 }catch(error){console.error(JSON.stringify({schema:'ASTRA_CAPTURE_FAILURE_V1',status:'BLOCKED',errorCode:codeOf(error),
  gpuRenderingVerified:false,visualQualityVerified:false}));process.exitCode=2;}
}
