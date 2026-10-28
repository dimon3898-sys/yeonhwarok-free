/** Loopback-only software capture of the exact Studio presentation request. */
import {readFile,writeFile,mkdir,lstat,realpath,readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {once} from 'node:events';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {resolveRegionPlan,prepareRegionTerrain,verifyRegionQualification,canonicalJSON} from './region_source_vulkan.generated.mjs';
import {compilePresentationCameraPlan,assertPresentationBoundaryContinuity} from '../universal-presentation-v2/presentation_plan.mjs';
import {buildVulkanLaunchOptions} from './backend/profile_contract.mjs';
import {createFreshPrivateDirectory as newPrivateRoot} from './backend/private_workspace.mjs';
import {createRecorder,attachPageDiagnostics,evaluateDiagnosed,classifyException,preserveCleanup,atomicPrivateJSON} from './backend/capture_operation_diagnostics.mjs';

export const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE);
const execute=promisify(execFile),hash=x=>createHash('sha256').update(x).digest('hex'),copy=x=>structuredClone(x),check=(v,c)=>{if(!v)throw Error(c);};
const within=(p,r)=>p===r||p.startsWith(r+path.sep),hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const writeJSON=(file,value)=>writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
async function safeFile(file,roots){const real=await realpath(file);check(real===path.resolve(file)&&roots.some(root=>within(real,root)),'UP2_SAFE_SOURCE_PATH_REQUIRED');return readFile(real);}
// New profile only: explicit qualified POSIX root, never inferred /workspace.

export function validateRuntimeRequest(request){
 check(request?.schema==='WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2','UP2_RUNTIME_REQUEST_SCHEMA');
 check(Number.isSafeInteger(request.totalFrames)&&request.totalFrames>=2&&request.totalFrames<=240,'UP2_RUNTIME_TOTAL_FRAMES');
 check(hex(request.sourceInputSHA256),'UP2_SOURCE_INPUT_HASH_REQUIRED');check(Array.isArray(request.segments)&&request.segments.length>=1&&request.segments.length<=16,'UP2_RUNTIME_SEGMENTS');
 let cursor=0;for(const[index,segment]of request.segments.entries()){check(segment.startFrame===cursor&&Number.isSafeInteger(segment.endFrame)&&segment.endFrame>cursor,'UP2_SEGMENT_FRAME_GAP_OR_OVERLAP');
  validateScenePlan(segment.scene);check(segment.scene.timing.total_frames===segment.endFrame-segment.startFrame&&segment.scene.timing.fps===30&&segment.scene.metadata.output.width===1080&&segment.scene.metadata.output.height===1920,'UP2_SEGMENT_SCENE_TIMING');
  check(['WAR','TRANSPORT'].includes(segment.scene.event_type)&&segment.scene.scale_intent.preferred==='REGIONAL','UP2_RENDER_FAMILY_OR_SCALE_UNSUPPORTED');
  check(!segment.scene.text?.length&&!segment.scene.causal_tracks?.length,'UP2_UNCONNECTED_VISIBLE_TEXT_OR_CAUSAL_TRACK_UNSUPPORTED');compileExistingEnginePlan(segment.scene);cursor=segment.endFrame;
  if(segment.presentation?.initialStateVisibility==='PRESERVE_PROVIDED')assertPresentationBoundaryContinuity(request.segments[index-1],segment);
 }
 check(cursor===request.totalFrames,'UP2_TOTAL_FRAME_SUM');
 const expected=request.segments.slice(1).map(s=>({type:'CUT',frame:s.startFrame}));check(canonicalJSON(request.transitions??[])===canonicalJSON(expected),'UP2_EXACT_SCENE_CUTS_REQUIRED');return true;
}
function sourceRowsFor(segments){return segments.map((s,index)=>{const source=s.sourceStyle.terrainAsset;return{segmentIndex:index,startFrame:s.startFrame,endFrame:s.endFrame,sourceId:s.regionEvidence.sourceId,sourceOriginalSHA256:source.sourceOriginalSHA256,styleId:s.sourceStyle.styleId,terrainSHA256:source.sha256,bounds:copy(source.bounds),cameraEnvelope:copy(s.presentationPlan.coverageBounds),terrainTreatment:s.terrainTreatment,nativeResolution:copy(s.regionEvidence.sourceDimensions),outputResolution:copy(source.dimensions),sourceGeometryBinding:compileExistingEnginePlan(s.scene).sourceGeometryBinding,sceneSHA256:hash(canonicalJSON(s.scene)),presentationSHA256:hash(canonicalJSON(s.presentation))};});}
export async function verifyPreparedRuntimeRequest(prepared,{privateWorkspaceRoot,publicExportRoot}={}){
 try{
  check(prepared?.schema==='WORLD_ENGINE_PREPARED_PRESENTATION_V2','UP2_PREPARED_SCHEMA_REQUIRED');validateRuntimeRequest({...prepared,schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2'});
  for(const segment of prepared.segments){const verification=await verifyRegionQualification({prepared:segment,privateWorkspaceRoot,publicExportRoot});check(verification.status==='PASS','UP2_CACHED_REGION_VERIFICATION_FAILED');
   const regionPlan=await resolveRegionPlan({scene:segment.scene,region:segment.region});check(canonicalJSON(regionPlan.baseCameraPlan)===canonicalJSON(segment.baseCameraPlan),'UP2_CACHED_BASE_CAMERA_CHANGED');
   const camera=compilePresentationCameraPlan({scene:segment.scene,region:segment.region,nativePlan:regionPlan.nativePlan,baseCameraPlan:regionPlan.baseCameraPlan,presentation:segment.presentation});check(canonicalJSON(camera)===canonicalJSON(segment.presentationPlan),'UP2_CACHED_PRESENTATION_CAMERA_CHANGED');
  }
  const qualification={schema:'WORLD_ENGINE_PRESENTATION_SOURCES_V2',segments:sourceRowsFor(prepared.segments),totalFrames:prepared.totalFrames},wire=canonicalJSON(qualification);
  check(wire===prepared.sourceQualificationWireJSON&&canonicalJSON(qualification)===canonicalJSON(prepared.sourceQualification)&&hash(wire)===prepared.sourceQualificationSHA256,'UP2_CACHED_SOURCE_QUALIFICATION_CHANGED');
  return{status:'PASS',sourceQualificationSHA256:hash(wire),verifiedSegments:prepared.segments.length};
 }catch(error){return{status:'INVALID',code:String(error.message)};}
}
export async function prepareRuntimeRequest({request,cacheRoot,privateWorkspaceRoot,publicExportRoot}={}){
 validateRuntimeRequest(request);await newPrivateRoot(cacheRoot,{privateWorkspaceRoot,publicExportRoot});const segments=[],sourceBindings=[],sourceRows=[];
 for(const [index,item]of request.segments.entries()){
  const regionPlan=await resolveRegionPlan({scene:item.scene,region:item.region});
  check(regionPlan.baseCameraPlan,'UP2_REGION_BASE_CAMERA_REQUIRED');
  const presentationPlan=compilePresentationCameraPlan({scene:item.scene,region:item.region,nativePlan:regionPlan.nativePlan,baseCameraPlan:regionPlan.baseCameraPlan,presentation:item.presentation});
  const prepared=await prepareRegionTerrain({regionPlan,bounds:presentationPlan.coverageBounds,outputRoot:path.join(cacheRoot,'segment-'+String(index).padStart(3,'0')),privateWorkspaceRoot,publicExportRoot});
  const qualification=await verifyRegionQualification({prepared,privateWorkspaceRoot,publicExportRoot});check(qualification.status==='PASS','UP2_PREPARED_REGION_VERIFICATION_FAILED');
  check(canonicalJSON(prepared.nativePlan.framing.bounds)===canonicalJSON(presentationPlan.closestBounds),'UP2_CLOSEST_APPROVED_EXTENT_CHANGED');
  const source=prepared.sourceStyle.terrainAsset;
  const assets=[];for(const[role,asset]of Object.entries(prepared.nativePlan.assets)){
   const candidate=path.isAbsolute(asset.file)?asset.file:asset.file.startsWith('world-simulation-shorts-engine/')?path.join(REPO,asset.file):path.resolve(ENGINE,asset.file);
   const bytes=await safeFile(candidate,[REPO,cacheRoot]);check(hash(bytes)===asset.sha256,'UP2_ASSET_SHA_MISMATCH_'+role);assets.push({role,path:candidate,sha256:hash(bytes),bytes:bytes.length});
  }
  sourceBindings.push(...prepared.sourceBindings,...assets);
  segments.push({...copy(item),...prepared,baseCameraPlan:regionPlan.baseCameraPlan,presentationPlan,serverBindings:{assets,sourceGeometryBinding:compileExistingEnginePlan(item.scene).sourceGeometryBinding}});
  sourceRows.push({segmentIndex:index,startFrame:item.startFrame,endFrame:item.endFrame,sourceId:prepared.regionEvidence.sourceId,sourceOriginalSHA256:source.sourceOriginalSHA256,styleId:prepared.sourceStyle.styleId,terrainSHA256:source.sha256,bounds:copy(source.bounds),cameraEnvelope:copy(presentationPlan.coverageBounds),terrainTreatment:prepared.terrainTreatment,nativeResolution:copy(prepared.regionEvidence.sourceDimensions),outputResolution:copy(source.dimensions),sourceGeometryBinding:compileExistingEnginePlan(item.scene).sourceGeometryBinding});
 }
 const sourceQualification={schema:'WORLD_ENGINE_PRESENTATION_SOURCES_V2',segments:sourceRowsFor(segments),totalFrames:request.totalFrames},sourceQualificationWireJSON=canonicalJSON(sourceQualification);
 return{schema:'WORLD_ENGINE_PREPARED_PRESENTATION_V2',totalFrames:request.totalFrames,transitions:copy(request.transitions),sourceInputSHA256:request.sourceInputSHA256,inputTrace:copy(request.inputTrace??null),segments,sourceBindings,sourceQualification,sourceQualificationWireJSON,sourceQualificationSHA256:hash(sourceQualificationWireJSON)};
}
async function makeLoopback(payload,cacheRoot){
 const trace=[],aliases=new Map([['/three.js',path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js')],['/web/map_infographic_v1/graphic_layout.mjs',path.join(ENGINE,'recovery/g2-final-recovery-v1/layout_extension.mjs')],['/web/map_infographic_v1/graphic_layout_legacy.mjs',path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs')]]);
 for(const segment of payload.segments)aliases.set(segment.sourceStyle.terrainAsset.url,segment.sourceStyle.terrainAsset.file);
 const server=createServer(async(req,res)=>{let target='';try{
  const url=new URL(req.url,'http://localhost');target=decodeURIComponent(url.pathname);check(['GET','HEAD'].includes(req.method)&&!url.search&&!target.includes('..')&&!target.includes('\\'),'UP2_HTTP_READ_ONLY');let raw,type='application/octet-stream';
  if(target==='/'){raw=Buffer.from('<!doctype html><meta charset="utf-8"><body style="margin:0"><canvas id="map" width="1080" height="1920"></canvas>');type='text/html';}
  else if(target==='/runtime.json'){raw=Buffer.from(JSON.stringify(payload));type='application/json';}
  else{const mounts=[['/web/',path.join(ENGINE,'web')],['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/recovery/universal-presentation-v2/',path.join(ENGINE,'recovery/universal-presentation-v2')],['/recovery/codex-to-gcube-handoff-v1/',HERE],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]],mount=mounts.find(([p])=>target.startsWith(p)),file=aliases.get(target)??(mount?path.join(mount[1],target.slice(mount[0].length)):null);check(file,'UP2_HTTP_NOT_FOUND');raw=await safeFile(file,[REPO,cacheRoot]);type=/\.(mjs|js)$/.test(target)?'text/javascript':/\.png$/.test(target)?'image/png':/\.jpg$/.test(target)?'image/jpeg':/\.otf$/.test(target)?'font/otf':type;}
  trace.push({path:target,status:200,sha256:hash(raw),bytes:raw.length});res.writeHead(200,{'content-type':type,'cache-control':'no-store','content-length':raw.length});res.end(req.method==='HEAD'?undefined:raw);
 }catch(error){trace.push({path:target,status:404,code:error.message});res.writeHead(404);res.end();}});
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});return{server,trace,origin:'http://127.0.0.1:'+server.address().port};
}
export async function captureVulkanDerived({packageFile,outputRoot,expectedSHA256,expectedSourceQualificationSHA256,depsRoot=process.env.WORLD_ENGINE_NODE_DEPS,probeFrames=null,prepareOnly=false,rootTestOnly=false,executionDeadline,privateWorkspaceRoot,publicExportRoot}={}){
 check(!prepareOnly&&probeFrames===null&&Number.isFinite(executionDeadline),'GCUBE_FULL_CAPTURE_AUTHORITY_REQUIRED');
 check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');
 check(hex(expectedSHA256),'UP2_EXPECTED_PACKAGE_SHA_REQUIRED');const raw=await readFile(packageFile);check(hash(raw)===expectedSHA256,'UP2_PACKAGE_SHA_MISMATCH');const request=JSON.parse(raw);check(request.totalFrames===180,'GCUBE_EXACT_180_FRAMES_REQUIRED');
 await newPrivateRoot(outputRoot,{privateWorkspaceRoot,publicExportRoot});const payload=await prepareRuntimeRequest({request,cacheRoot:path.join(outputRoot,'sources'),privateWorkspaceRoot,publicExportRoot});
 if(expectedSourceQualificationSHA256!==undefined)check(hex(expectedSourceQualificationSHA256)&&payload.sourceQualificationSHA256===expectedSourceQualificationSHA256,'UP2_PRECLAIM_SOURCE_QUALIFICATION_CHANGED');
 await writeFile(path.join(outputRoot,'REQUEST.json'),raw,{flag:'wx',mode:0o600});await writeJSON(path.join(outputRoot,'RUNTIME.json'),payload);
 if(prepareOnly){const result={schema:'WORLD_ENGINE_PRESENTATION_PREPARATION_V2',status:'CPU_PREPARATION_PASS_NOT_DRAW',packageSHA256:expectedSHA256,sourceQualification:payload.sourceQualification,sourceQualificationWireJSON:payload.sourceQualificationWireJSON,sourceQualificationSHA256:payload.sourceQualificationSHA256,softwareOnly:true,nvidiaVerified:false};await writeJSON(path.join(outputRoot,'PREPARATION_RECEIPT.json'),result);return result;}
 const receipt={schema:'WORLD_ENGINE_NVIDIA_SIX_SECOND_CAPTURE_V1',status:'RUNNING',packageSHA256:expectedSHA256,sourceInputSHA256:request.sourceInputSHA256,sourceQualificationSHA256:payload.sourceQualificationSHA256,totalFrames:request.totalFrames,renderedFrames:0,softwareOnly:false,nvidiaVerified:false,visualQualityApproved:false,paidExecutionAttempted:false,providerBillingStopControlled:false,startedAt:new Date().toISOString(),transitions:copy(request.transitions),inputTrace:copy(request.inputTrace??null),sourceCredits:payload.segments.map((s,index)=>({segmentIndex:index,sourceId:s.regionEvidence.sourceId,license:s.sourceStyle.license,attribution:s.regionEvidence.attribution,sourceURL:s.sourceStyle.sourceOriginal.url,sourceOriginalSHA256:s.sourceStyle.terrainAsset.sourceOriginalSHA256,terrainSHA256:s.sourceStyle.terrainAsset.sha256}))};
 const recorder=createRecorder({outputRoot,runId:path.basename(path.dirname(outputRoot)),imageDigest:process.env.WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST,sceneSHA256:request.segments.length===1?hash(canonicalJSON(request.segments[0].scene)):null});
 let primaryError=null;
 let browser,encoder,encoderExit,service;let diagnosticStage='BEFORE_PAGE_EVALUATION';const evidence=[],errors=[],runtimeEvidence=[],started=performance.now();
 try{
  check(typeof depsRoot==='string'&&path.isAbsolute(depsRoot),'UP2_PRIVATE_PLAYWRIGHT_REQUIRED');const require=createRequire(path.join(depsRoot,'package.json')),{chromium}=require('playwright');receipt.dependencies={node:process.version,playwright:require('playwright/package.json').version};
  for(const prepared of payload.segments){const qualification=await verifyRegionQualification({prepared,privateWorkspaceRoot,publicExportRoot});check(qualification.status==='PASS','UP2_REGION_CHANGED_BEFORE_DRAW');}
  service=await makeLoopback(payload,outputRoot);check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');const launchProfile=buildVulkanLaunchOptions({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']},{uid:process.getuid(),rootTestOptIn:rootTestOnly});receipt.browserProfile=launchProfile.evidence;receipt.paidExecutionAttempted=true;browser=await chromium.launch(launchProfile.options);receipt.dependencies.chromium=browser.version();
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});page.on('pageerror',error=>errors.push(error.message));await page.route('**/*',route=>new URL(route.request().url()).origin===service.origin?route.continue():route.abort('blockedbyclient'));await page.goto(service.origin,{waitUntil:'load'});
  await attachPageDiagnostics(page,recorder);
  diagnosticStage='PAGE_EVALUATE_RUNTIME_IMPORT';await evaluateDiagnosed(page,async()=>window.__worldEngineDiagnostics.capture(async()=>{
   const d=window.__worldEngineDiagnostics;window.payload=await d.run('INPUT_CANVAS',async()=>{const response=await fetch('/runtime.json');if(!response.ok)throw Error('CAPTURE_ASSET_HTTP_FAILED');return response.json();});
   window.createRuntime=await d.run('RUNTIME_IMPORT',async()=>(await import('/recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs')).createNvidiaPresentationRuntime);window.currentSegment=-1;
  }),undefined,{recorder,timeoutMs:executionDeadline-Date.now()});
  diagnosticStage='PAGE_EVALUATE_FIRST_NATIVE_DRAW';const firstNativeProof=await evaluateDiagnosed(page,async()=>window.__worldEngineDiagnostics.capture(async()=>{
   const d=window.__worldEngineDiagnostics;
   const first=window.payload.segments[0];
   const canvas=await d.run('INPUT_CANVAS',()=>{if(first.startFrame!==0)throw Error('GCUBE_INITIAL_SEGMENT_REQUIRED');const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);return canvas;});
   window.runtime=await d.run('RUNTIME_CREATE',()=>window.createRuntime({canvas,...first,diagnostics:d}));window.currentSegment=0;
   const{runThreeNativeDraws}=await d.run('NATIVE_GUARD_IMPORT',()=>import('/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs'));
   const proof=await d.run('NATIVE_CONTEXT_PROOF',()=>runThreeNativeDraws({runtime:window.runtime,canvas,diagnostics:d}));return{proof,evidence:window.runtime.evidence};
  }),undefined,{recorder,timeoutMs:executionDeadline-Date.now()});
  receipt.nativeStability=[{segmentIndex:0,...firstNativeProof.proof}];receipt.nvidiaVerified=true;receipt.actualGpuDrawVerified=true;await recorder.proofCompleted();
  runtimeEvidence.push({segmentIndex:0,...firstNativeProof.evidence,nativeStability:firstNativeProof.proof});
  const frames=probeFrames??Array.from({length:request.totalFrames},(_,i)=>i),checkpoints=new Set([0,Math.floor(request.totalFrames/2),request.totalFrames-1,...request.transitions.flatMap(t=>[t.frame-1,t.frame])]);check(frames.length&&frames.every(f=>Number.isSafeInteger(f)&&f>=0&&f<request.totalFrames),'UP2_PROBE_FRAMES_INVALID');let ffmpegStderr='';
  if(!probeFrames){
   const creditText=[...new Set(receipt.sourceCredits.map(c=>`${c.attribution}; license=${typeof c.license==='string'?c.license:JSON.stringify(c.license)}; source=${c.sourceURL}`))].join(' | ')+' | Modifications: native-pixel crop, geographic map rendering and supplied event graphics.';
   receipt.embeddedSourceCredits={format:'MP4_COMMENT_AND_COPYRIGHT',text:creditText};
   await recorder.event({phase:'START',operationId:'ENCODER'});
   encoder=spawn('ffmpeg',['-hide_banner','-loglevel','error','-n','-f','image2pipe','-framerate','30','-vcodec','png','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-r','30','-metadata','comment='+creditText,'-metadata','copyright='+creditText,'-movflags','+faststart',path.join(outputRoot,'VIDEO.mp4')],{stdio:['pipe','ignore','pipe']});encoder.stderr.on('data',chunk=>{ffmpegStderr=(ffmpegStderr+chunk).slice(-8192);});encoderExit=once(encoder,'exit');encoder.stdin.on('error',()=>{});await recorder.event({phase:'END',operationId:'ENCODER'});
  }
  for(const frame of frames){check(Date.now()<executionDeadline,'GCUBE_REVIEW_DEADLINE_EXCEEDED');diagnosticStage='PAGE_EVALUATE_FRAME_CAPTURE';const capture=await evaluateDiagnosed(page,async frame=>window.__worldEngineDiagnostics.capture(async()=>{
   const d=window.__worldEngineDiagnostics;
   const index=window.payload.segments.findIndex(s=>frame>=s.startFrame&&frame<s.endFrame),segment=window.payload.segments[index];let initialized=null;
   if(window.currentSegment!==index){window.runtime?.dispose();const canvas=await d.run('INPUT_CANVAS',()=>{const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;document.body.replaceChildren(canvas);return canvas;},{frame});window.runtime=await d.run('RUNTIME_CREATE',()=>window.createRuntime({canvas,...segment,diagnostics:d}),{frame});window.currentSegment=index;const{runThreeNativeDraws}=await d.run('NATIVE_GUARD_IMPORT',()=>import('/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs'),{frame});const proof=await d.run('NATIVE_CONTEXT_PROOF',()=>runThreeNativeDraws({runtime:window.runtime,canvas,diagnostics:d}),{frame});initialized={...window.runtime.evidence,nativeStability:proof};}
   const diagnostic=await d.run('DRAW',()=>window.runtime.drawFrame(frame-segment.startFrame),{frame}),pixels=await d.run('READBACK',()=>window.runtime.readPixels(),{frame});let nonBlackPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlackPixels++;
   const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');return{segmentIndex:index,localFrame:frame-segment.startFrame,diagnostic,initialized,rawSHA256:await digest(pixels),baseRawSHA256:await digest(window.runtime.readBasePixels()),nonBlackPixels,png:await d.run('PNG',()=>window.runtime.png().split(',')[1],{frame})};
  }),frame,{recorder,timeoutMs:executionDeadline-Date.now()});
   check(capture.nonBlackPixels>1080*1920*.2,'UP2_BLACK_FRAME');check(capture.diagnostic.glError===0,'UP2_FRAME_GL_ERROR');if(capture.initialized){runtimeEvidence.push({segmentIndex:capture.segmentIndex,...capture.initialized});receipt.nativeStability.push({segmentIndex:capture.segmentIndex,...capture.initialized.nativeStability});}
   const png=Buffer.from(capture.png,'base64');evidence.push({frame,segmentIndex:capture.segmentIndex,localFrame:capture.localFrame,rawSHA256:capture.rawSHA256,baseRawSHA256:capture.baseRawSHA256,pngSHA256:hash(png),nonBlackPixels:capture.nonBlackPixels,diagnostic:capture.diagnostic});
   if(probeFrames||checkpoints.has(frame))await writeFile(path.join(outputRoot,`FRAME_${String(frame).padStart(3,'0')}.png`),png,{flag:'wx',mode:0o600});if(encoder){await recorder.event({phase:'START',operationId:'ENCODER'});check(encoder.exitCode===null,'UP2_ENCODER_EARLY_EXIT');if(!encoder.stdin.write(png))await Promise.race([once(encoder.stdin,'drain'),encoderExit.then(()=>{throw Error('UP2_ENCODER_CLOSED');})]);await recorder.event({phase:'END',operationId:'ENCODER'});}
   receipt.renderedFrames++;await recorder.completeFrame(receipt.renderedFrames);process.stdout.write(JSON.stringify({stage:'ACTUAL_FRAME_DRAW',frame,renderedFrames:receipt.renderedFrames,totalFrames:request.totalFrames})+'\n');
  }
  if(encoder){await recorder.event({phase:'START',operationId:'ENCODER'});encoder.stdin.end();const[code]=await encoderExit;check(code===0,'UP2_ENCODER_FAILED_'+ffmpegStderr);encoder=null;const video=path.join(outputRoot,'VIDEO.mp4'),probe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video],{timeout:120000,maxBuffer:2*1024**2})).stdout),stream=probe.streams.find(s=>s.codec_type==='video');
   check(probe.streams.filter(s=>s.codec_type==='video').length===1&&!probe.streams.some(s=>s.codec_type==='audio'),'GCUBE_SILENT_SINGLE_VIDEO_STREAM_REQUIRED');
   check(stream?.codec_name==='h264'&&stream.width===1080&&stream.height===1920&&stream.r_frame_rate==='30/1'&&Number(stream.nb_read_frames)===request.totalFrames,'UP2_VIDEO_CONTRACT_FAILED');check(Math.abs(Number(probe.format.duration)-request.totalFrames/30)<1/30,'UP2_VIDEO_DURATION_MISMATCH');check(probe.format.tags?.comment===receipt.embeddedSourceCredits.text&&probe.format.tags?.copyright===receipt.embeddedSourceCredits.text,'UP2_EMBEDDED_SOURCE_CREDITS_MISSING');await execute('ffmpeg',['-v','error','-i',video,'-f','null','-'],{timeout:120000,maxBuffer:2*1024**2});const bytes=await readFile(video);receipt.video={file:'VIDEO.mp4',sha256:hash(bytes),bytes:bytes.length,frames:Number(stream.nb_read_frames),width:stream.width,height:stream.height,fps:30,codec:'h264',durationSeconds:Number(probe.format.duration),fullDecode:'PASS',audio:false,sourceCreditsEmbedded:true};receipt.status='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED';await recorder.event({phase:'END',operationId:'ENCODER'});
  }else receipt.status='ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO';check(errors.length===0,'UP2_BROWSER_ERROR');receipt.runtime={backend:runtimeEvidence[0]?.backend,segments:runtimeEvidence};
 }catch(error){primaryError=error;receipt.status='FAILED';await recorder.fail(error.captureFailure??classifyException(error,recorder.snapshot().operationId??'INPUT_CANVAS'));receipt.failure={code:recorder.snapshot().firstFailure.errorCode,diagnosticStage};}
 finally{await preserveCleanup(recorder,[()=>encoder?.kill('SIGTERM'),()=>browser?.close(),()=>service?new Promise((resolve,reject)=>service.server.close(error=>error?reject(error):resolve())):undefined]);receipt.elapsedSeconds=(performance.now()-started)/1000;receipt.finishedAt=new Date().toISOString();receipt.browserErrors=errors;receipt.captureOperations=recorder.snapshot();
  try{
  await recorder.event({phase:'START',operationId:'EXPORT'});
  await writeJSON(path.join(outputRoot,'FRAME_EVIDENCE.json'),{schema:'WORLD_ENGINE_NVIDIA_PRESENTATION_FRAMES_V1',frames:evidence});await writeJSON(path.join(outputRoot,'HTTP_ASSET_BINDINGS.json'),service?.trace??[]);receipt.frameEvidence={file:'FRAME_EVIDENCE.json',sha256:hash(await readFile(path.join(outputRoot,'FRAME_EVIDENCE.json')))};await atomicPrivateJSON(path.join(outputRoot,'CAPTURE_RECEIPT.json'),receipt,{maximum:24*1024**2});
  await recorder.event({phase:'END',operationId:'EXPORT'});
  const names=(await readdir(outputRoot)).filter(n=>n!=='SHA256SUMS').sort(),lines=[];for(const name of names){const file=path.join(outputRoot,name);if((await lstat(file)).isFile())lines.push(hash(await readFile(file))+'  '+name);}await writeFile(path.join(outputRoot,'SHA256SUMS'),lines.join('\n')+'\n',{flag:'wx',mode:0o600});
  }catch(error){await recorder.fail(classifyException(error,'EXPORT'),{cleanup:Boolean(primaryError)});if(!primaryError)primaryError=error;}
  if(!primaryError&&recorder.snapshot().cleanupFailure)primaryError=Error(recorder.snapshot().cleanupFailure.errorCode);
 }
 if(primaryError)throw primaryError;
 return receipt;
}
// Library-only derived adapter; the gated capture_nvidia.mjs entry owns execution.
