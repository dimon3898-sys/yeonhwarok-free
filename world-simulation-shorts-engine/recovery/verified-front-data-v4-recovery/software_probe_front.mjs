/** Actual loopback Chromium/SwiftShader draw/readPixels of the new archival source path.
 * No hardware admission, video render or historical daily interpolation is claimed. */
import assert from 'node:assert/strict';
import {access,mkdtemp,readFile,writeFile,mkdir,rm,lstat} from 'node:fs/promises';
import {constants} from 'node:fs';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
import {sha,repo,loadLongRuntimePlan,assertFrontCapturedFrame} from './front_runtime.mjs';
import {selectFrontSnapshot,sourceLineChunks} from './front_visual.mjs';
import {compareActualPixels} from '../universal-production-v3/software_probe_production.mjs';
import {measureEventGeometryBounds,measureNativeBoundaryPixels} from '../universal-auto-video-v2/software_probe_long.mjs';
export const SCHEMA='WORLD_ENGINE_ARCHIVAL_FRONT_V4_SOFTWARE_PROBE_V1';
const root=path.dirname(fileURLToPath(import.meta.url)),parent=path.join(root,'../universal-auto-video-v2'),execute=promisify(execFile),
 hash=value=>sha(Buffer.from(JSON.stringify(value))),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
export function selectFrontProbeFrames(document,profile){
 const active=profile.schedule.map(row=>Math.floor((row.startFrame+row.endFrame-1)/2)),
  cut=document.scenes.slice(1).map(row=>row.startFrame).find(frame=>selectFrontSnapshot(profile,frame-1).sourceActiveFrame
   &&selectFrontSnapshot(profile,frame).sourceActiveFrame),frames=[0,...active,...(cut?[cut-1,cut]:[]),document.totalFrames-1];
 const unique=[...new Set(frames)];assert.ok(unique.length>=3&&unique.length<=12,'FRONT_V4_BOUNDED_ACTUAL_SAMPLE_FRAMES_REQUIRED');
 assert.ok(unique.some(frame=>selectFrontSnapshot(profile,frame).sourceActiveFrame),'FRONT_V4_ACTUAL_SOURCE_FRAME_REQUIRED');
 return{frames:unique,abFrame:active[0],cut:cut??null};
}
export function softwareConfigFor(base,scene,variant='AFTER'){
 assert.ok(['AFTER','SUPPRESS_ARCHIVAL_FRONT'].includes(variant));const config=structuredClone(base);
 config.runtimeConfig.testOnlySoftwareProbe=true;config.runtimeConfig.productionV3ProbeVariant='AFTER';
 if(config.runtimeConfig.frontV4)config.runtimeConfig.frontV4ProbeVariant=variant;
 Object.assign(config.runtimeConfig.universalVideo,{scene,sceneRangeSha256:hash(scene),testOnly:true});return config;
}
async function temporaryRoot(){
 for(const base of ['/var/lib/world-engine-private/engine',repo,tmpdir()])try{
  await access(base,constants.W_OK);return await mkdtemp(path.join(base,'.world-front-software-'));
 }catch{}throw Error('FRONT_V4_PRIVATE_SOFTWARE_ROOT_REQUIRED');
}
async function start(config,file){
 const raw=Buffer.from(JSON.stringify(config));await writeFile(file,raw,{flag:'wx',mode:0o600});
 const server=spawn('/usr/bin/python3',['-B',path.join(parent,'serve_long.py'),'--config',file,'--expected-config-sha256',sha(raw)],
  {cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';server.stderr.on('data',bytes=>{stderr=(stderr+bytes).slice(-2048);});
 try{
  const origin=await new Promise((resolve,reject)=>{const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('FRONT_V4_SOFTWARE_LOOPBACK_TIMEOUT'));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{const row=JSON.parse(line),url=new URL(row.url);
    assert.equal(row.event,'READY');assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');resolve(url.origin);
   }catch(error){reject(error);}});for(const event of ['exit','error'])server.once(event,()=>{clearTimeout(timer);lines.close();reject(Error('FRONT_V4_SOFTWARE_LOOPBACK_FAILED '+stderr));});
  });return{server,origin};
 }catch(error){server.kill();throw error;}
}
async function rawPixels(page){return Buffer.from(await page.evaluate(()=>{
 const bytes=window.longVideoProof.pipeline.readPixels(),parts=[];for(let i=0;i<bytes.length;i+=16384)
  parts.push(String.fromCharCode(...bytes.subarray(i,i+16384)));return btoa(parts.join(''));
}),'base64');}
function witness(d){return{cameraSha256:hash(d.camera.camera),geometrySha256:hash(d.area.controls),
 dateSha256:hash(d.area.date)};}
/** The actual native projection is sampled; no geography is moved to make it fit. */
export async function measureSourceProjection(page,front,{safeArea,width=1080,height=1920,includeProjectedParts=false}={}){
 const parts=front.geometry.type==='LineString'?[front.geometry.coordinates]:front.geometry.coordinates,
  projected=await page.evaluate(parts=>parts.map(part=>part.map(point=>window.longVideoProof.pipeline.project([...point]))),parts);
 assert.ok(projected.flat().every(point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite)),
  'FRONT_V4_ACTUAL_NATIVE_PROJECTION_REQUIRED');
 const inside=(point,box)=>point[0]>=box[0]&&point[0]<=box[2]&&point[1]>=box[1]&&point[1]<=box[3],points=projected.flat(),
  bounds=[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))],
  projectedLengthPixels=projected.reduce((sum,part)=>sum+part.slice(1).reduce((n,p,i)=>n+Math.hypot(p[0]-part[i][0],p[1]-part[i][1]),0),0),
  allRetainedCoordinatesInSafeArea=points.every(point=>inside(point,safeArea)),
  allRetainedCoordinatesInViewport=points.every(point=>inside(point,[0,0,width,height]));
 assert.equal(allRetainedCoordinatesInSafeArea,true,'FRONT_V4_RETAINED_SOURCE_COORDINATES_CROPPED_BY_SAFE_AREA');
 assert.equal(allRetainedCoordinatesInViewport,true,'FRONT_V4_RETAINED_SOURCE_COORDINATES_CROPPED_BY_VIEWPORT');
 // A linear projected segment in a convex rectangle stays within the rectangle
 // when both endpoints do. This checks source edges rather than a generated hull.
 assert.ok(projectedLengthPixels>1,'FRONT_V4_SOURCE_PROJECTED_LENGTH_SUBPIXEL');
 return{bounds,projectedLengthPixels,retainedCoordinateCount:points.length,sourcePartCount:projected.length,
  projectedPositionsSha256:hash(projected),allRetainedCoordinatesInSafeArea,allRetainedCoordinatesInViewport,
  allRetainedSegmentsInSafeArea:true,allRetainedSegmentsInViewport:true,projectionOwner:'UNCHANGED_NATIVE_FACTORY',
  screenCoverage:{width:(bounds[2]-bounds[0])/width,height:(bounds[3]-bounds[1])/height},
  minimumCondition:'POSITIVE_RESOLVABLE_SOURCE_LENGTH_NOT_FINAL_MOBILE_QUALITY_APPROVAL',
  ...(includeProjectedParts?{projectedParts:projected}:{})};
}
/** Actual AFTER-minus-suppression pixels must belong to the retained source
 * contour, not an unrelated border/terrain change. This does not certify an
 * entire line's mobile readability or physical NVIDIA rendering. */
export function compareSourceFrontPixels(before,after,{safeArea,protectedGraphics=[],projectedParts,
 frontCoreWidthPixels,frontGlowRadiusPixels}={}){
 assert.ok(Array.isArray(projectedParts)&&projectedParts.length>0&&projectedParts.length<=64
  &&projectedParts.every(part=>Array.isArray(part)&&part.length>=2&&part.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite))),
  'FRONT_V4_ACTUAL_SOURCE_PROJECTED_PARTS_REQUIRED');
 assert.ok(Number.isFinite(frontCoreWidthPixels)&&frontCoreWidthPixels>0&&Number.isFinite(frontGlowRadiusPixels)&&frontGlowRadiusPixels>=0,
  'FRONT_V4_ACTUAL_SOURCE_STYLE_SUPPORT_REQUIRED');
 const sourceSupportRadiusPixels=frontCoreWidthPixels/2+frontGlowRadiusPixels+.5,
  coreSupportRadiusPixels=frontCoreWidthPixels/2+.5;
 assert.ok(sourceSupportRadiusPixels<=12.9+1e-9,'FRONT_V4_APPROVED_SOURCE_STYLE_SUPPORT_EXCEEDED');
 const compared=compareActualPixels(before,after,{safeArea,protectedGraphics}),segments=projectedParts.flatMap(part=>part.slice(1).map((b,i)=>({a:part[i],b})));
 assert.ok(segments.length>0&&segments.length<=8192,'FRONT_V4_BOUNDED_ACTUAL_SOURCE_SEGMENTS_REQUIRED');
 const distance=(x,y,{a,b})=>{const dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy,
  t=length?Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/length)):0;return Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy);};
 let outsideSourceCorridorChangedPixelCount=0,sourceCoreChangedPixelCount=0,maximumChangedPixelDistanceFromSource=0;
 for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
  const i=((1919-y)*1080+x)*4;
  if(before[i]===after[i]&&before[i+1]===after[i+1]&&before[i+2]===after[i+2]&&before[i+3]===after[i+3])continue;
  const d=Math.min(...segments.map(segment=>distance(x+.5,y+.5,segment)));
  if(d>sourceSupportRadiusPixels+1e-6)outsideSourceCorridorChangedPixelCount++;
  if(d<=coreSupportRadiusPixels)sourceCoreChangedPixelCount++;
  maximumChangedPixelDistanceFromSource=Math.max(maximumChangedPixelDistanceFromSource,d);
 }
 assert.equal(outsideSourceCorridorChangedPixelCount,0,'FRONT_V4_PIXELS_CHANGED_OUTSIDE_ACTUAL_SOURCE_CORRIDOR');
 assert.ok(sourceCoreChangedPixelCount>0,'FRONT_V4_SOURCE_WHITE_CORE_NOT_VISIBLE');
 return{...compared,outsideSourceCorridorChangedPixelCount,sourceCoreChangedPixelCount,sourceSupportRadiusPixels,coreSupportRadiusPixels,
  maximumChangedPixelDistanceFromSource,sourceSegmentCount:segments.length,sourceProjectedPositionsSha256:hash(projectedParts),
  boundaryPixelChangePolicy:'ONLY_WITHIN_ACTUAL_SOURCE_FRONT_SUPPORT',allNativeMarkerAndTextReservationsPreserved:true};
}
export async function runFrontSoftwareProbe({planFile=path.join(root,'../universal-production-v3/fixtures/PLAN_80S.json'),
 frontProfileFile=path.join(root,'FRONT_PROFILE.json'),frontManifestFile=path.join(root,'FRONT_FILES.json')}={}){
 const temporary=await temporaryRoot(),require=createRequire(path.join(repo,'cinematic-world-map/package.json')),rows=[],files=[],evidenceDir=process.env.WORLD_ENGINE_FRONT_EVIDENCE_DIR;
 let browser,page,activeServer,invocation=0;
 try{
  const planRaw=await readFile(planFile),document=JSON.parse(planRaw),profileRaw=await readFile(frontProfileFile),manifestRaw=await readFile(frontManifestFile),
   privateJob=path.join(temporary,'job');assert.equal(document.totalFrames,2400);assert.equal(document.fps,30);assert.equal(document.productionV3.eventChapters.length,12);
  await mkdir(privateJob,{mode:0o700});
  const prepare="import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from prepare_video import prepare_job_inputs;p=json.load(open(sys.argv[2]));a=prepare_job_inputs(p,Path(sys.argv[3]));b=prepare_job_inputs(p,Path(sys.argv[3]));assert b['cacheHit'] is True and a['activationSha256']==b['activationSha256'];print(json.dumps({**a,'inputCacheReuseVerified':True}))",
   prepared=JSON.parse((await execute('/usr/bin/python3',['-B','-c',prepare,parent,planFile,privateJob],{timeout:180000,maxBuffer:1024*1024})).stdout);
  assert.equal(prepared.gpuExecuted,false);assert.equal(prepared.inputCacheReuseVerified,true);
  const plan=await loadLongRuntimePlan({planFile,expectedPlanSha256:sha(planRaw),sceneId:document.scenes[0].sceneId,
   activationFile:prepared.activationFile,expectedActivationSha256:prepared.activationSha256,
   frontProfileFile,expectedFrontProfileSha256:sha(profileRaw),frontManifestFile,expectedFrontManifestSha256:sha(manifestRaw),testOnlySoftwareProbe:true}),
   temporal=selectFrontProbeFrames(document,plan.frontProfile);
  if(evidenceDir){assert.ok(path.isAbsolute(evidenceDir)&&path.resolve(evidenceDir)===evidenceDir);
   await mkdir(evidenceDir,{recursive:true,mode:0o700});assert.ok(!(await lstat(evidenceDir)).isSymbolicLink(),'FRONT_V4_EVIDENCE_SYMLINK_REFUSED');}
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  const store=async(file,captured)=>{const bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);if(evidenceDir)await writeFile(path.join(evidenceDir,file),bytes,{flag:'wx',mode:0o644});
   files.push({file,sha256:sha(bytes),bytes:bytes.length,width:1080,height:1920,scope:'CPU_SW_NOT_NVIDIA'});};
  const open=async config=>{const server=await start(config,path.join(temporary,'HTTP_'+invocation+++'.json'));activeServer=server.server;
   page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});const errors=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
   await page.route('**/*',route=>new URL(route.request().url()).origin===server.origin?route.continue():route.abort('blockedbyclient'));
   await page.goto(server.origin+'/',{waitUntil:'load',timeout:240000});await page.waitForFunction(()=>Object.hasOwn(window,'longVideoBoot'),null,{timeout:240000});
   const info=await page.evaluate(()=>window.longVideoBoot);assert.equal(info.testOnly,true);assert.match(info.backend,/SwiftShader/i);assert.equal(info.productionEligible,false);
   return{info,errors};};
  const close=async()=>{if(page){await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await page.close();page=null;}activeServer?.kill();activeServer=null;};
  const afterWitnesses=new Map(),representativeSourceIds=new Set(),boundaryProof=[];
  let afterReadbackBufferHighWaterMark=0;
  for(const frame of temporal.frames){
   const scene=document.scenes.find(row=>frame>=row.startFrame&&frame<row.endFrame),config=softwareConfigFor(plan.serverConfig,scene),opened=await open(config);
   try{
    const captured=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),frame),d=captured.diagnostic,
     selected=selectFrontSnapshot(plan.frontProfile,frame),selectedPlan={...plan,scene};
    await assertFrontCapturedFrame(captured,selectedPlan);assert.equal(d.glError,0);assert.equal(d.universalVideo.testOnly,true);
    assert.equal(d.universalVideo.planSha256,plan.planSha256);assert.equal(d.universalVideo.legacySceneSha256,plan.legacySceneSha256);
    assert.equal(d.universalVideo.sceneRangeSha256,config.runtimeConfig.universalVideo.sceneRangeSha256);
    assert.equal(d.terrain.astra.gpuUploadExecuted,true);assert.equal(d.terrain.astra.testOnly,true);
    assert.equal(d.terrain.astra.actualMaterialFactorySelected,true);assert.equal(d.sourceIntegrity.sourceBeforeAreaAndFront,true);
    assert.equal(d.coverageCache.entryLimit,1);assert.equal(d.sourceIntegrity.fictional65422SceneUsed,false);
    const bounds=await page.evaluate(measureEventGeometryBounds);
    if(bounds.active){assert.equal(bounds.wholeEventGeometryInViewport,true,'FRONT_V4_SOURCE_GEOMETRY_CROPPED');assert.equal(bounds.wholeEventGeometryInSafeArea,true,'FRONT_V4_SOURCE_OUTSIDE_SAFE_AREA');}
    const file='FRAME_'+String(frame).padStart(6,'0')+'.png';await store(file,captured);
    const row={frame,sceneId:scene.sceneId,sceneRange:[scene.startFrame,scene.endFrame],rawRgbaSha256:captured.raw_rgba_sha256,
     pngSha256:captured.png_sha256,pngFile:file,sourceActiveFrame:selected.sourceActiveFrame,selection:selected,
     geometryBounds:bounds,actualAstra:d.terrain.astra,timings:d.timings,...witness(d)};
    if(selected.sourceActiveFrame){
     const front=plan.frontProfile.fronts.find(row=>row.frontId===selected.frontId),chunks=sourceLineChunks(front.geometry);
     assert.ok(d.area.graphics.fronts.some(row=>row.drawn),'FRONT_V4_SOURCE_FRONT_ACTUAL_DRAW_REQUIRED');
     assert.equal(d.area.graphics.areas.length,0);Object.assign(row,{frontId:front.frontId,sourceFile:front.sourceFile,
      sourceGeoJsonSha256:front.geoJsonSha256,sourceMapDate:front.mapDate,sourceGeometrySha256:hash(front.geometry),
      sourceCoordinateCount:chunks.reduce((sum,chunk)=>sum+chunk.geometry.coordinates.length,0),
      sourcePartCount:front.geometry.type==='LineString'?1:front.geometry.coordinates.length,exactPartialSourceCoordinates:true,
      sourceObservedFrontNotExactOccupation:true,sourceDateGlyph:d.area.date.geometry.text,
      unverifiedSchematicAreaSuppressed:true,registrationResidualMeters:front.source.registrationResidualMeters,
      originalCartographicAccuracy:'UNKNOWN_NOT_CERTIFIED'});
     const {projectedParts,...projection}=await measureSourceProjection(page,front,{safeArea:d.camera.safeArea,includeProjectedParts:true});
     row.sourceProjection=projection;row.sourceBoundaryPolicy=structuredClone(d.frontV4.boundaryPolicy);
     assert.equal(row.sourceBoundaryPolicy.policy,'ARCHIVAL_SOURCE_FRONT_ABOVE_STATIC_COUNTRY_BOUNDARY');
     if(!representativeSourceIds.has(front.frontId)||frame===document.totalFrames-1){
      representativeSourceIds.add(front.frontId);const pixels=await rawPixels(page);assert.equal(sha(pixels),captured.raw_rgba_sha256);
      afterWitnesses.set(frame,{pixels,diagnostic:d,projectedParts,...witness(d),rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256,
       frontId:front.frontId,sourceFile:front.sourceFile,sourceMapDate:front.mapDate,sourceGeoJsonSha256:front.geoJsonSha256});
      afterReadbackBufferHighWaterMark=Math.max(afterReadbackBufferHighWaterMark,afterWitnesses.size);
      assert.ok(afterWitnesses.size<=11,'FRONT_V4_BOUNDED_SOURCE_READBACK_BUFFERS_REQUIRED');
     }
    }
    rows.push(row);if(frame===0)boundaryProof.push(await page.evaluate(measureNativeBoundaryPixels,{frame}));
    if(frame===temporal.abFrame)await store('AB_AFTER.png',captured);
    assert.deepEqual(opened.errors,[],'FRONT_V4_SOFTWARE_BROWSER_ERRORS');
   }finally{await close();}
  }
  let abComparison;const sourceVisibility=[];
  for(const [frame,afterWitness]of afterWitnesses){
   const abScene=document.scenes.find(row=>frame>=row.startFrame&&frame<row.endFrame),beforeConfig=softwareConfigFor(plan.serverConfig,abScene,'SUPPRESS_ARCHIVAL_FRONT'),
    beforeBoot=await open(beforeConfig);
   try{
    const captured=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),frame),d=captured.diagnostic,
     pixels=await rawPixels(page),before={...witness(d),rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256},
     after={cameraSha256:afterWitness.cameraSha256,geometrySha256:afterWitness.geometrySha256,dateSha256:afterWitness.dateSha256,
      rawRgbaSha256:afterWitness.rawRgbaSha256,pngSha256:afterWitness.pngSha256},afterDiagnostic=afterWitness.diagnostic;
    assert.equal(d.frontV4.softwareProbeVariant,'SUPPRESS_ARCHIVAL_FRONT');assert.equal(sha(pixels),captured.raw_rgba_sha256);
    assert.equal(before.cameraSha256,after.cameraSha256);assert.equal(before.geometrySha256,after.geometrySha256);assert.equal(before.dateSha256,after.dateSha256);
    assert.deepEqual(d.frontV4.boundaryPolicy,afterDiagnostic.frontV4.boundaryPolicy);
    if(frame===temporal.abFrame)await store('AB_BEFORE.png',captured);
    const protectedGraphics=[...afterDiagnostic.camera.protectedGraphics,afterDiagnostic.area.date.event.reservation,afterDiagnostic.area.date.geometry.reservation],
     style=afterDiagnostic.area.graphics.productionVisual,compared=compareSourceFrontPixels(pixels,afterWitness.pixels,{safeArea:afterDiagnostic.camera.safeArea,
      protectedGraphics,projectedParts:afterWitness.projectedParts,frontCoreWidthPixels:style.frontCoreWidthPixels,frontGlowRadiusPixels:style.frontGlowRadiusPixels});
    const result={status:'PASS',frame,frontId:afterWitness.frontId,sourceFile:afterWitness.sourceFile,sourceMapDate:afterWitness.sourceMapDate,
     sourceGeoJsonSha256:afterWitness.sourceGeoJsonSha256,sameFrame:true,sameCamera:true,sameSourceGeometry:true,sameSourceDateGlyph:true,
     comparisonScope:'TEST_ONLY_FRONT_DRAW_SUPPRESSION_VS_ACTUAL_ARCHIVAL_FRONT_DRAW',...compared,before,after};
    sourceVisibility.push(result);rows.find(row=>row.frame===frame).sourceVisibility=result;
    if(frame===temporal.abFrame)abComparison=result;
    assert.deepEqual(beforeBoot.errors,[],'FRONT_V4_AB_BROWSER_ERRORS');
   }finally{await close();afterWitnesses.delete(frame);}
  }
  assert.equal(new Set(sourceVisibility.map(row=>row.frontId)).size,plan.frontProfile.fronts.length,'FRONT_V4_EVERY_SOURCE_FRONT_VISIBILITY_REQUIRED');
  assert.ok(sourceVisibility.some(row=>row.frame===document.totalFrames-1),'FRONT_V4_FINAL_FRAME_SOURCE_VISIBILITY_REQUIRED');
  assert.ok(abComparison,'FRONT_V4_PRIMARY_AB_REQUIRED');assert.ok(files.length<=14,'FRONT_V4_BOUNDED_PERSISTED_PNGS_REQUIRED');
  // Fallback is compared against the original V3 compositor, not a mocked renderer.
  const fallbackScene=document.scenes[0],legacyConfig=softwareConfigFor(plan.preservedProductionServerConfig,fallbackScene),legacyBoot=await open(legacyConfig);let preservedFallback;
  const originalCameraComparisons=[];
  try{
   const old=await page.evaluate(()=>window.longVideoProof.capture(0,{png:false})),actual=rows.find(row=>row.frame===0);
   assert.equal(old.raw_rgba_sha256,actual.rawRgbaSha256,'FRONT_V4_INACTIVE_PATH_CHANGED_V3_PIXELS');
   for(const sourceRow of rows.filter(row=>row.sourceActiveFrame)){
    const originalCamera=await page.evaluate(frame=>window.longVideoProof.testOnlyNative.drawFrame(frame).camera,sourceRow.frame),
     originalCameraSha256=hash(originalCamera);
    assert.equal(originalCameraSha256,sourceRow.cameraSha256,'FRONT_V4_ARCHIVAL_SOURCE_CHANGED_ORIGINAL_V3_CAMERA');
    const comparison={frame:sourceRow.frame,originalV3CameraSha256:originalCameraSha256,archivalCameraSha256:sourceRow.cameraSha256,identical:true};
    sourceRow.originalV3CameraComparison=comparison;originalCameraComparisons.push(comparison);
   }
   assert.deepEqual(legacyBoot.errors,[]);preservedFallback={status:'PASS',frame:0,rawRgbaSha256:old.raw_rgba_sha256,bitExact:true,originalV3CompositorUsed:true};
  }finally{await close();}
  const continuity=[];
  if(temporal.cut!==null){
   const fullScene={...document.scenes[0],sceneId:'TEST_ONLY_UNSEGMENTED_GLOBAL_CLOCK',startFrame:0,endFrame:document.totalFrames,globalFrameOffset:0},
    fullConfig=softwareConfigFor(plan.serverConfig,fullScene),fullBoot=await open(fullConfig);
   try{for(const frame of [temporal.cut-1,temporal.cut]){
    const capture=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:false}),frame),segmented=rows.find(row=>row.frame===frame);
    assert.equal(capture.raw_rgba_sha256,segmented.rawRgbaSha256,'FRONT_V4_SCENE_CUT_CHANGED_SOURCE_PIXELS');
    continuity.push({frame,segmentedRawRgbaSha256:segmented.rawRgbaSha256,fullTimelineRawRgbaSha256:capture.raw_rgba_sha256,bitExact:true});
   }assert.deepEqual(fullBoot.errors,[]);}finally{await close();}
  }
  await plan.assertSourceUnchanged();if(evidenceDir)await writeFile(path.join(evidenceDir,'SHA256SUMS'),files.map(row=>row.sha256+'  '+row.file).join('\n')+'\n',{flag:'wx',mode:0o644});
  return{schema:SCHEMA,status:'PASS',testOnly:true,actualDrawReadPixels:true,actualShaderCompile:true,softwareWebGLDrawExecuted:true,
   sourceActiveFrame:true,actualHistoricalSourceSelected:true,originalSourcesUnchanged:true,actualAstraUpload:true,sourceOrderVerified:true,
   fullPlan2400Frames:true,twelveChapterPlanSelected:true,nvidiaHardwareVerified:false,physicalNvidiaExecuted:false,gpuRenderingVerified:false,
   full80SecondVideoRendered:false,gpuVideoQualityApproved:false,frontProfileSha256:sha(profileRaw),frontManifestSha256:sha(manifestRaw),
   planSha256:plan.planSha256,sourceSignature:plan.sourceSignature,frontIntegrity:plan.frontIntegrity,
   frames:temporal.frames,rows,files,abComparison,
   sourceVisibility:{status:'PASS',policy:'ARCHIVAL_SOURCE_FRONT_ABOVE_STATIC_COUNTRY_BOUNDARY',cases:sourceVisibility},
   preservedFallback,continuity,actualBoundaryPair:temporal.cut,originalCameraComparisons,
   allSourceFrontsVisibleInMeasuredSamples:true,finalFrameSourceVisible:true,
   readbackMemory:{retainedAfterBufferHighWaterMark:afterReadbackBufferHighWaterMark,transientBeforeComparisonBuffers:1,
    maximumSimultaneousReadbackBuffers:afterReadbackBufferHighWaterMark+1,bytesPerBuffer:1080*1920*4,
    all2400FramesRetained:false,otherBeforePngsPersisted:false},
   nativeBoundaryProtection:{status:'PASS',scope:'SOURCE_INACTIVE_FRAME_0_ONLY',actualReadPixelsCompared:true,cases:boundaryProof,
    sourceActivePolicy:'ARCHIVAL_SOURCE_FRONT_ABOVE_STATIC_COUNTRY_BOUNDARY',allSourceActiveBoundaryPixelsUnchangedClaimed:false},
   shaderBackend:'SWIFTSHADER_ONLY',browserVersion:browser.version(),nodeVersion:process.version,
   playwrightVersion:require('playwright/package.json').version,inputCacheReuseVerified:true,
   historicalMeaning:'SOURCE_REVIEWED_DATED_PARTIAL_UN_FRONTS_APPROXIMATELY_REGISTERED_NOT_EXACT_OCCUPATION_OR_MDL',
   noInferredEnemyComplement:true,noInventedHistoricalMovement:true,sampleMp4Generated:false};
 }finally{
  try{if(page){await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await page.close();}}catch{}
  activeServer?.kill();await browser?.close();await rm(temporary,{recursive:true,force:true});
 }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{console.log(JSON.stringify(await runFrontSoftwareProbe()));}
 catch(error){console.error(JSON.stringify({schema:SCHEMA,status:'FAIL',testOnly:true,errorCode:error?.message??'FRONT_V4_SOFTWARE_PROBE_FAILED',
  nvidiaHardwareVerified:false,physicalNvidiaExecuted:false,gpuRenderingVerified:false,full80SecondVideoRendered:false}));process.exitCode=2;}
}
