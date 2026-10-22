/** Loopback-only actual engine capture, invoked by a detached Studio worker.
 * No paid provider, user-supplied filesystem route or production GPU fallback. */
import {readFile,writeFile,mkdir,lstat,realpath} from 'node:fs/promises';
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
import {compileMinimumContextPlan,evaluateMinimumContextCameraFrame} from '../../web/map_infographic_v1/camera_director_v5.mjs';
import {compileScalePlan} from '../../web/map_infographic_v1/scale_contract.mjs';

export const HERE=path.dirname(fileURLToPath(import.meta.url)),ENGINE=path.resolve(HERE,'../..'),REPO=path.dirname(ENGINE);
export const SOURCE_REGIONS=Object.freeze(['namibia_desert_coast','europe_germany','south_america_chile','korean_peninsula','nepal_himalaya']);
const ZIP=path.join(ENGINE,'recovery/g2-final-recovery-v1/fixtures/GENERIC_REGION_INPUTS.zip');
const ZIP_SHA='29806402e97db3a97cb4f3b95d6851d9bca62810ccbfb29199592ad49b9dd22b';
const execute=promisify(execFile),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),copy=x=>structuredClone(x);
const check=(ok,code)=>{if(!ok)throw Error(code);};
const within=(p,r)=>p===r||p.startsWith(r+path.sep);
const hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const writeJSON=(file,value)=>writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx',mode:0o600});
async function actualFile(file,root){const real=await realpath(file);check(real===path.resolve(file)&&within(real,root),'UDP_SAFE_SOURCE_PATH_REQUIRED');return readFile(real);}

/** Server chooses a registered GIS/style seed; the topic's original scene is
 * validated separately and is never replaced by the seed's authored fields. */
export async function buildRuntimePayload({scene,sourceRegionId,inputTrace=null}={}){
 validateScenePlan(scene);check(SOURCE_REGIONS.includes(sourceRegionId),'UDP_SOURCE_REGION_UNSUPPORTED');
 check(['WAR','TRANSPORT'].includes(scene.event_type),'UDP_RENDER_FAMILY_UNSUPPORTED');
 check(scene.scale_intent.preferred==='REGIONAL','UDP_PIXEL_SCALE_UNSUPPORTED');
 check(!(scene.text?.length),'UDP_VISIBLE_TEXT_UNSUPPORTED');
 check(!(scene.causal_tracks?.length),'UDP_CAUSAL_TRACK_PIXEL_ADAPTER_UNSUPPORTED');
 check(!(scene.camera_intent.native_context?.secondary_country_ids?.length),'UDP_NATIVE_CONTEXT_ROLE_UNSUPPORTED');
 check(scene.timing.fps===30&&scene.timing.total_frames>=2&&scene.timing.total_frames<=240&&scene.metadata.output.width===1080&&scene.metadata.output.height===1920,'UDP_FREE_CAPTURE_SCOPE_REQUIRED');
 const enginePlan=compileExistingEnginePlan(scene);
 const raw=await actualFile(ZIP,REPO);check(hash(raw)===ZIP_SHA,'UDP_SEED_ARCHIVE_SHA_MISMATCH');
 const unpack="import zipfile,json,sys; z=zipfile.ZipFile(sys.argv[1]); sys.stdout.write(z.read(sys.argv[2]).decode())";
 const {stdout}=await execute('python',['-B','-c',unpack,ZIP,sourceRegionId+'/RECOVERY_RUNTIME.json'],{maxBuffer:32*1024**2,timeout:30000});
 const seed=JSON.parse(stdout),nativePlan=copy(seed.nativePlan),originalSourceGeometry=JSON.stringify(nativePlan.geometries);
 const anchor=copy(scene.camera_intent.anchor),primaryId=scene.camera_intent.native_context?.primary_country_id??nativePlan.primary;
 const primary=nativePlan.geometries.find(item=>item.id===primaryId);check(primary,'UDP_PRIMARY_GIS_MISSING');
 const contextLocations=(scene.camera_intent.native_context?.context_location_ids??[]).map(id=>{
  const location=scene.locations.find(item=>item.id===id);check(location,'UDP_CONTEXT_LOCATION_MISSING');return{type:'Point',coordinates:copy(location.anchor)};
 });
 nativePlan.primary=primaryId;nativePlan.secondary=[];nativePlan.anchor={geometry_type:'Point',crs:'EPSG:4326',coordinates:anchor};
 nativePlan.layout.locationPlacement={schema:'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1',mode:'BOUNDED_GAP_SEARCH',maxGap:216,step:16};
 nativePlan.layout.countryLabels=[];
 nativePlan.scale.information.location=true;
 const compiledNative=compileScalePlan(nativePlan,'REGIONAL',{allCountries:nativePlan.geometries});
 check(JSON.stringify(compiledNative.geometries)===originalSourceGeometry,'UDP_SOURCE_GIS_MUTATION');
 const cameraScene={primary_region_id:primaryId,primary_geometry:copy(primary),event_anchor:anchor,
  approved_final_extent:copy(compiledNative.framing.bounds),start_extent:copy(seed.cameraPlan.intent.startExtent),
  desired_detail_level:'REGIONAL',scale_admission:{status:'LOCAL_NOT_ADMITTED'},canonical_output:[1080,1920],safe_area:copy(compiledNative.layout.safe),
  event_geometry:scene.geometries.filter(g=>scene.camera_intent.target_geometry_refs.includes(g.id)).map(g=>copy(g.geometry)),
  context_geometry:[...scene.geometries.filter(g=>(scene.camera_intent.minimum_context_geometry_refs??[]).includes(g.id)).map(g=>copy(g.geometry)),...contextLocations],event_title:'',location_label:'',primary_label:''};
 const cameraPlan=compileMinimumContextPlan({scene:cameraScene,profile:copy(seed.cameraPlan.profile),seed:0});
 const camera=evaluateMinimumContextCameraFrame(cameraPlan,cameraPlan.totalFrames-1);check(camera.cameraLocked&&camera.settle.locked,'UDP_CAMERA_NOT_LOCKED');
 const bindings=[];
 for(const [role,asset] of Object.entries(compiledNative.assets)){
  const candidate=asset.file.startsWith('world-simulation-shorts-engine/')?path.join(REPO,asset.file):path.resolve(ENGINE,asset.file);
  const bytes=await actualFile(candidate,REPO);check(hash(bytes)===asset.sha256,'UDP_SOURCE_ASSET_SHA_MISMATCH_'+role);
  bindings.push({role,path:path.relative(REPO,candidate),sha256:hash(bytes),bytes:bytes.length});
 }
 const a=seed.sourceStyle.terrainAsset,b=camera.camera.flatBounds;
 const gutter=Math.min((b[0]-a.bounds[0])/a.pixelSpacing[0],(b[1]-a.bounds[1])/a.pixelSpacing[1],(a.bounds[2]-b[2])/a.pixelSpacing[0],(a.bounds[3]-b[3])/a.pixelSpacing[1]);
 check(gutter>=1-1e-9,'UDP_SOURCE_VIEWPORT_OUTSIDE_NATIVE_STYLE');
 return{scene:copy(scene),nativePlan:compiledNative,cameraPlan,sourceStyle:copy(seed.sourceStyle),inputTrace:copy(inputTrace),
  serverBindings:{seedArchiveSHA256:ZIP_SHA,seedMember:sourceRegionId+'/RECOVERY_RUNTIME.json',seedMemberSHA256:hash(Buffer.from(stdout)),assets:bindings,
   inputGeometryBinding:enginePlan.sourceGeometryBinding,sourceRegionId,minimumSourceGutterPixels:gutter,profile:'EXPLICIT_REGION_PROFILE_LOCKED',syntheticSeedFieldsUsed:false}};
}

async function makeLoopback(payload){
 const terrainFile=path.join(REPO,payload.sourceStyle.terrainAsset.path),trace=[];
 const layoutRoot=path.join(ENGINE,'recovery/g2-final-recovery-v1');
 const aliases=new Map([['/generic_runtime.mjs',path.join(HERE,'generic_runtime.mjs')],['/three.js',path.join(ENGINE,'web/vendor/three/0.170.0/three.module.js')],
  ['/modules/graphic_layout.mjs',path.join(layoutRoot,'layout_extension.mjs')],['/modules/graphic_layout_legacy.mjs',path.join(ENGINE,'web/map_infographic_v1/graphic_layout.mjs')],
  [payload.sourceStyle.terrainAsset.url,terrainFile]]);
 const server=createServer(async(req,res)=>{
  let target='';
  try{
   const url=new URL(req.url,'http://localhost');target=decodeURIComponent(url.pathname);
   check(['GET','HEAD'].includes(req.method)&&!url.search&&!target.includes('..')&&!target.includes('\\'),'UDP_HTTP_READ_ONLY');
   let raw,type='application/octet-stream';
   if(target==='/'){raw=Buffer.from('<!doctype html><meta charset="utf-8"><canvas id="map" width="1080" height="1920"></canvas>');type='text/html';}
   else if(target==='/runtime.json'){raw=Buffer.from(JSON.stringify(payload));type='application/json';}
   else{
    const mounts=[['/modules/',path.join(ENGINE,'web/map_infographic_v1')],['/static/',path.join(ENGINE,'web')],['/v3/assets/',path.join(REPO,'cinematic-world-map/assets')]],mount=mounts.find(([prefix])=>target.startsWith(prefix));
    const file=aliases.get(target)??(mount?path.join(mount[1],target.slice(mount[0].length)):null);
    check(file,'UDP_HTTP_ROUTE_NOT_FOUND');raw=await actualFile(file,REPO);
    type=/\.(mjs|js)$/.test(target)?'text/javascript':/\.png$/.test(target)?'image/png':/\.jpg$/.test(target)?'image/jpeg':/\.otf$/.test(target)?'font/otf':type;
   }
   trace.push({path:target,status:200,sha256:hash(raw),bytes:raw.length});res.writeHead(200,{'content-type':type,'cache-control':'no-store','content-length':raw.length});res.end(req.method==='HEAD'?undefined:raw);
  }catch(error){trace.push({path:target,status:404});res.writeHead(404);res.end();}
 });
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 return{server,trace,origin:'http://127.0.0.1:'+server.address().port};
}

export async function captureGeneric({sceneFile,outputRoot,expectedSHA256,sourceRegionId,depsRoot=process.env.WORLD_ENGINE_NODE_DEPS,inputTrace=null,probeFrames=null}={}){
 check(hex(expectedSHA256),'UDP_EXPECTED_SCENE_SHA_REQUIRED');check(path.isAbsolute(outputRoot),'UDP_ABSOLUTE_NEW_OUTPUT_REQUIRED');
 const sceneRaw=await readFile(sceneFile);check(hash(sceneRaw)===expectedSHA256,'UDP_SCENE_SHA_MISMATCH');
 const scene=JSON.parse(sceneRaw),payload=await buildRuntimePayload({scene,sourceRegionId,inputTrace});
 await mkdir(outputRoot,{mode:0o700});check(!(await lstat(outputRoot)).isSymbolicLink(),'UDP_OUTPUT_SYMLINK_REJECTED');
 await writeFile(path.join(outputRoot,'SCENE.json'),sceneRaw,{flag:'wx',mode:0o600});await writeJSON(path.join(outputRoot,'RUNTIME.json'),payload);
 const receipt={schema:'WORLD_ENGINE_UNIVERSAL_DATA_CAPTURE_V1',status:'RUNNING',sceneSHA256:expectedSHA256,sourceRegionId,sourceGeometryBinding:payload.serverBindings.inputGeometryBinding,
  totalFrames:scene.timing.total_frames,renderedFrames:0,softwareOnly:true,nvidiaVerified:false,visualQualityApproved:false,paidExecuted:false,
  startedAt:new Date().toISOString(),serverBindings:payload.serverBindings,inputTrace};
 let browser,encoder,encoderExit,service;const evidence=[],errors=[];
 const started=performance.now();
 try{
  check(typeof depsRoot==='string'&&path.isAbsolute(depsRoot),'UDP_PRIVATE_PLAYWRIGHT_DEPS_REQUIRED');
  const require=createRequire(path.join(depsRoot,'package.json')),{chromium}=require('playwright');
  receipt.dependencies={node:process.version,playwright:require('playwright/package.json').version};
  service=await makeLoopback(payload);browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  receipt.dependencies.chromium=browser.version();
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===service.origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(service.origin,{waitUntil:'load'});
  receipt.runtime=await page.evaluate(async()=>{
   const payload=await(await fetch('/runtime.json')).json(),{createGenericRuntime}=await import('/generic_runtime.mjs');
   window.runtime=await createGenericRuntime({canvas:document.getElementById('map'),...payload});return window.runtime.evidence;
  });
  check(receipt.runtime.backend.includes('SwiftShader'),'UDP_ACTUAL_SOFTWARE_REQUIRED');
  const frames=probeFrames??Array.from({length:scene.timing.total_frames},(_,i)=>i),checkpoints=new Set([0,Math.floor(scene.timing.total_frames/2),scene.timing.total_frames-1]);
  check(frames.length>0&&frames.every(f=>Number.isSafeInteger(f)&&f>=0&&f<scene.timing.total_frames),'UDP_PROBE_FRAMES_INVALID');
  let ffmpegStderr='';
  if(!probeFrames){
   encoder=spawn('ffmpeg',['-hide_banner','-loglevel','error','-n','-f','image2pipe','-framerate','30','-vcodec','png','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',path.join(outputRoot,'VIDEO.mp4')],{stdio:['pipe','ignore','pipe']});
   encoder.stderr.on('data',chunk=>{ffmpegStderr=(ffmpegStderr+chunk).slice(-8192);});encoderExit=once(encoder,'exit');
   encoder.stdin.on('error',()=>{});
  }
  for(const frame of frames){
   const capture=await page.evaluate(async frame=>{
    const diagnostic=window.runtime.drawFrame(frame),pixels=window.runtime.readPixels();
    let nonBlackPixels=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]||pixels[i+1]||pixels[i+2])nonBlackPixels++;
    const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
    const rawSHA256=await digest(pixels),baseRawSHA256=await digest(window.runtime.readBasePixels());
    return{diagnostic,rawSHA256,baseRawSHA256,nonBlackPixels,png:window.runtime.png().split(',')[1]};
   },frame);
   check(capture.nonBlackPixels>1080*1920*.2,'UDP_BLACK_FRAME');
   check(capture.diagnostic.glError===0,'UDP_FRAME_GL_ERROR');
   const png=Buffer.from(capture.png,'base64');
   evidence.push({frame,rawSHA256:capture.rawSHA256,baseRawSHA256:capture.baseRawSHA256,pngSHA256:hash(png),nonBlackPixels:capture.nonBlackPixels,diagnostic:capture.diagnostic});
   if(probeFrames||checkpoints.has(frame))await writeFile(path.join(outputRoot,`FRAME_${String(frame).padStart(3,'0')}.png`),png,{flag:'wx',mode:0o600});
   if(encoder){check(encoder.exitCode===null,'UDP_ENCODER_EARLY_EXIT');if(!encoder.stdin.write(png))await Promise.race([
    once(encoder.stdin,'drain'),encoderExit.then(()=>{throw Error('UDP_ENCODER_CLOSED_DURING_FRAME_WRITE');})
   ]);}
   receipt.renderedFrames++;
   process.stdout.write(JSON.stringify({stage:'ACTUAL_FRAME_DRAW',frame,renderedFrames:receipt.renderedFrames,totalFrames:scene.timing.total_frames})+'\n');
  }
  if(encoder){encoder.stdin.end();const [code]=await encoderExit;check(code===0,'UDP_ENCODER_FAILED_'+ffmpegStderr);encoder=null;
   const video=path.join(outputRoot,'VIDEO.mp4'),probe=JSON.parse((await execute('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',video],{timeout:120000,maxBuffer:2*1024**2})).stdout);
   const stream=probe.streams.find(s=>s.codec_type==='video');check(stream?.codec_name==='h264'&&stream.width===1080&&stream.height===1920&&stream.r_frame_rate==='30/1'&&Number(stream.nb_read_frames)===scene.timing.total_frames,'UDP_FINAL_VIDEO_CONTRACT_FAILED');
   check(Math.abs(Number(probe.format.duration)-scene.timing.duration_seconds)<1/30,'UDP_VIDEO_DURATION_MISMATCH');
   await execute('ffmpeg',['-v','error','-i',video,'-f','null','-'],{timeout:120000,maxBuffer:2*1024**2});
   const bytes=await readFile(video);receipt.video={file:'VIDEO.mp4',sha256:hash(bytes),bytes:bytes.length,frames:Number(stream.nb_read_frames),width:stream.width,height:stream.height,fps:30,codec:'h264',durationSeconds:Number(probe.format.duration),fullDecode:'PASS',audio:false};
   receipt.status='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED';
  }else receipt.status='ACTUAL_DRAW_PROBE_PASS_NOT_STUDIO_VIDEO';
  check(errors.length===0,'UDP_BROWSER_ERROR');
 }catch(error){receipt.status='FAILED';receipt.failure={code:String(error.message).slice(0,4000)};throw error;}
 finally{
  encoder?.kill('SIGTERM');await browser?.close();if(service)await new Promise(resolve=>service.server.close(resolve));
  receipt.elapsedSeconds=(performance.now()-started)/1000;receipt.finishedAt=new Date().toISOString();receipt.browserErrors=errors;
  await writeJSON(path.join(outputRoot,'FRAME_EVIDENCE.json'),{schema:'WORLD_ENGINE_UNIVERSAL_DATA_FRAMES_V1',frames:evidence});
  await writeJSON(path.join(outputRoot,'HTTP_ASSET_BINDINGS.json'),service?.trace??[]);
  receipt.frameEvidence={file:'FRAME_EVIDENCE.json',sha256:hash(await readFile(path.join(outputRoot,'FRAME_EVIDENCE.json')))};
  await writeJSON(path.join(outputRoot,'CAPTURE_RECEIPT.json'),receipt);
  const {readdir}=await import('node:fs/promises'),names=(await readdir(outputRoot)).filter(n=>n!=='SHA256SUMS').sort();
  const lines=[];for(const name of names)lines.push(hash(await readFile(path.join(outputRoot,name)))+'  '+name);
  await writeFile(path.join(outputRoot,'SHA256SUMS'),lines.join('\n')+'\n',{flag:'wx',mode:0o600});
 }
 return receipt;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args={};for(const arg of process.argv.slice(2)){const m=/^--(scene|output-root|expected-sha256|source-region|deps-root|probe-frames|input-trace)=(.+)$/.exec(arg);check(m&&!args[m[1]],'UDP_CAPTURE_ARGUMENT_INVALID');args[m[1]]=m[2];}
 const inputTrace=args['input-trace']?JSON.parse(await readFile(args['input-trace'],'utf8')):null;
 try{const receipt=await captureGeneric({sceneFile:args.scene,outputRoot:args['output-root'],expectedSHA256:args['expected-sha256'],sourceRegionId:args['source-region'],depsRoot:args['deps-root']??process.env.WORLD_ENGINE_NODE_DEPS,inputTrace,probeFrames:args['probe-frames']?args['probe-frames'].split(',').map(Number):null});
  process.stdout.write(JSON.stringify({status:receipt.status,outputRoot:args['output-root'],video:receipt.video??null})+'\n');
 }catch(error){process.stderr.write(String(error.message)+'\n');process.exitCode=1;}
}
