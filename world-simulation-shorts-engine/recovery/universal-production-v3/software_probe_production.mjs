/** Real Chromium/SwiftShader probe of the production adapter, never NVIDIA or
 * a sample video. Parent preparation, safe HTTP and pixel measurements are
 * reused; only this new fixture/adapter and its actual cut are exercised. */
import assert from 'node:assert/strict';
import {access,mkdtemp,readFile,writeFile,mkdir,rm,lstat} from 'node:fs/promises';
import {constants} from 'node:fs';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
import {sha,repo,engine} from '../universal-auto-video-v2/long_runtime.mjs';
import {assertActualAdjacentScenePair,measureNativeBoundaryPixels,measureEventGeometryBounds} from '../universal-auto-video-v2/software_probe_long.mjs';
import {evaluateProductionGeometryClock} from './production_visual_profile.mjs';

const execute=promisify(execFile),root=path.dirname(fileURLToPath(import.meta.url)),parent=path.join(root,'../universal-auto-video-v2');
export const SCHEMA='WORLD_ENGINE_PRODUCTION_V3_ACTUAL_SOFTWARE_PROBE_V1';
const hash=value=>sha(Buffer.from(JSON.stringify(value))),hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const geometryHash=geometry=>hash({type:geometry.type,coordinates:geometry.coordinates});

/** A work-range cut must be inside one supplied transition, not at its start
 * or merely near a legacy timeline. Scene/chapter counts are independent. */
export function selectProductionTemporalFrames(document){
 assert.ok(document?.productionV3?.runtimeProfile==='UNIVERSAL_PRODUCTION_V3'&&document.totalFrames>=5,
  'PRODUCTION_ACTUAL_PROFILE_REQUIRED');
 const schedule=document.productionV3.geometrySchedule;
 assert.ok(Array.isArray(schedule)&&Array.isArray(document.scenes)&&document.scenes.length>1,'PRODUCTION_ACTUAL_SCHEDULE_REQUIRED');
 const candidates=document.scenes.slice(1).map(scene=>scene.startFrame).filter(cut=>schedule.some(row=>
  row.mode==='TRANSITION_SUPPLIED_SNAPSHOTS'&&cut-1>row.startFrame&&cut<row.endFrame-1&&row.sourceStartFrame!==row.sourceEndFrame))
  .sort((a,b)=>Math.abs(a-document.totalFrames/2)-Math.abs(b-document.totalFrames/2)||a-b);
 assert.ok(candidates.length,'PRODUCTION_REAL_WORK_CUT_INSIDE_SOURCE_TRANSITION_REQUIRED');
 const cut=candidates[0],witness=assertActualAdjacentScenePair(document,cut-1,cut),transition=schedule.find(row=>cut>=row.startFrame&&cut<row.endFrame),
  usedStates=new Set([transition.fromStateId,transition.toStateId]),diverse=schedule.find(row=>row.startFrame>cut
   &&row.mode==='TRANSITION_SUPPLIED_SNAPSHOTS'&&!usedStates.has(row.toStateId));
 assert.ok(diverse,'PRODUCTION_DISTINCT_LATER_SUPPLIED_STATE_REQUIRED');
 const abFrame=diverse.endFrame-1,frames=[0,witness.beforeFrame,witness.afterFrame,abFrame,document.totalFrames-1];
 assert.equal(new Set(frames).size,5,'PRODUCTION_FIVE_DISTINCT_TEMPORAL_FRAMES_REQUIRED');
 const left=evaluateProductionGeometryClock(document,witness.beforeFrame),right=evaluateProductionGeometryClock(document,witness.afterFrame);
 assert.equal(left.scheduleId,right.scheduleId);assert.notEqual(left.sourceGeometryFrame,right.sourceGeometryFrame,
  'PRODUCTION_ACTUAL_SOURCE_CLOCK_MUST_ADVANCE_AT_CUT');
 return {frames,abFrame,witness:{...witness,geometryScheduleId:transition.scheduleId,
  sourceBeforeFrame:left.sourceGeometryFrame,sourceAfterFrame:right.sourceGeometryFrame,sourceTransitionRange:[transition.startFrame,transition.endFrame]}};
}

/** Exact source coordinates/identities; the renderer may crossfade the supplied
 * polygons but this proof cannot invent their complementary ownership. */
export function assertSuppliedGeometry(document,controls){
 if(!controls)return{active:false,areas:[],fronts:[]};
 const legacy=document.legacyScenePlan,geometry=new Map(legacy.geometries.map(row=>[row.id,row.geometry])),
  bindings=new Map(document.productionV3.visualBindings.areaStyles.map(row=>[row.areaId,row]));
 const check=(item,kind)=>{
  const record=(kind==='AREA'?legacy.areas:legacy.front_lines).find(row=>row.id===item.id);
  assert.ok(record,'PRODUCTION_UNKNOWN_ACTUAL_GEOMETRY_ID');
  assert.equal(geometryHash(item.geometry),geometryHash(geometry.get(record.geometry_ref)),'PRODUCTION_ACTUAL_GEOMETRY_CHANGED');
  if(kind==='AREA')assert.ok(bindings.has(item.id),'PRODUCTION_AREA_WITHOUT_EXPLICIT_FACTION');
  return{id:item.id,kind,geometryRef:record.geometry_ref,geometrySha256:geometryHash(item.geometry),alpha:item.alpha,
   ...(kind==='AREA'?{factionId:bindings.get(item.id).factionId}:{} )};
 };
 return{active:true,areas:controls.areas.map(row=>check(row,'AREA')),fronts:controls.fronts.map(row=>check(row,'FRONT')),
  exactSuppliedCoordinates:true,noEnemyComplementCreated:true};
}

export function frameWitness(diagnostic){
 assert.ok(diagnostic?.productionV3&&diagnostic.camera?.camera,'PRODUCTION_ACTUAL_FRAME_WITNESS_REQUIRED');
 return {cameraSha256:hash(diagnostic.camera.camera),geometrySha256:hash(diagnostic.area.controls),
  dateSha256:hash({chapter:diagnostic.productionV3.chapter,clock:diagnostic.productionV3.geometryClock,date:diagnostic.area.date}),
  camera:diagnostic.camera.camera};
}

export function compareActualPixels(before,after,{safeArea,protectedGraphics=[]}={}){
 assert.ok(before instanceof Uint8Array&&after instanceof Uint8Array&&before.length===1080*1920*4&&after.length===before.length,
  'PRODUCTION_FULL_RGBA_READBACK_REQUIRED');
 assert.ok(Array.isArray(safeArea)&&safeArea.length===4&&safeArea.every(Number.isFinite),'PRODUCTION_MEASURED_SAFE_AREA_REQUIRED');
 const inside=(x,y,b)=>x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3];
 let changedPixelCount=0,protectedGraphicChangedPixelCount=0,outsideSafeAreaChangedPixelCount=0,sumAbsoluteRGBChange=0;
 for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
  const i=((1919-y)*1080+x)*4;
  if(before[i]===after[i]&&before[i+1]===after[i+1]&&before[i+2]===after[i+2]&&before[i+3]===after[i+3])continue;
  changedPixelCount++;sumAbsoluteRGBChange+=Math.abs(before[i]-after[i])+Math.abs(before[i+1]-after[i+1])+Math.abs(before[i+2]-after[i+2]);
  if(protectedGraphics.some(row=>inside(x+.5,y+.5,row.box??row)))protectedGraphicChangedPixelCount++;
  if(!inside(x+.5,y+.5,safeArea))outsideSafeAreaChangedPixelCount++;
 }
 assert.ok(changedPixelCount>0,'PRODUCTION_STYLE_AB_MUST_CHANGE_ACTUAL_PIXELS');
 assert.equal(protectedGraphicChangedPixelCount,0,'PRODUCTION_STYLE_CHANGED_PROTECTED_GRAPHIC_PIXELS');
 assert.equal(outsideSafeAreaChangedPixelCount,0,'PRODUCTION_STYLE_CHANGED_OUTSIDE_SAFE_AREA');
 return{changedPixelCount,protectedGraphicChangedPixelCount,outsideSafeAreaChangedPixelCount,
  meanAbsoluteRGBChangeOnChangedPixels:sumAbsoluteRGBChange/(changedPixelCount*3)};
}

async function temporaryRoot(){
 for(const base of ['/var/lib/world-engine-private/engine',repo,tmpdir()]){
  try{await access(base,constants.W_OK);return await mkdtemp(path.join(base,'.world-production-software-'));}catch{}
 }
 throw Error('PRODUCTION_WRITABLE_PRIVATE_TEST_ROOT_REQUIRED');
}
async function start(config,file){
 const bytes=Buffer.from(JSON.stringify(config));await writeFile(file,bytes,{flag:'wx',mode:0o600});
 const server=spawn('/usr/bin/python3',['-B',path.join(parent,'serve_long.py'),'--config',file,'--expected-config-sha256',sha(bytes)],
  {cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';server.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-2048);});
 let origin;
 try{origin=await new Promise((resolve,reject)=>{const lines=createInterface({input:server.stdout}),
  timer=setTimeout(()=>{lines.close();reject(Error('PRODUCTION_SW_SERVER_TIMEOUT'));},10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const row=JSON.parse(line),url=new URL(row.url);
   assert.ok(row.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1');resolve(url.origin);
  }catch(error){reject(error);}});
  for(const event of ['error','exit'])server.once(event,()=>{clearTimeout(timer);lines.close();reject(Error('PRODUCTION_SW_SERVER_FAILED '+stderr));});
 });}catch(error){server.kill();throw error;}
 return{server,origin};
}
export function configFor(base,scene,variant='AFTER'){
 assert.ok(['BEFORE','AFTER'].includes(variant),'PRODUCTION_SUPPORTED_AB_VARIANT_REQUIRED');
 const config=structuredClone(base);config.runtimeConfig.testOnlySoftwareProbe=true;config.runtimeConfig.productionV3ProbeVariant=variant;
 Object.assign(config.runtimeConfig.universalVideo,{scene,sceneRangeSha256:hash(scene),testOnly:true});return config;
}
async function rawPixels(page){
 return Buffer.from(await page.evaluate(()=>{
  const pixels=window.longVideoProof.pipeline.readPixels();let chunks=[];
  for(let i=0;i<pixels.length;i+=16384)chunks.push(String.fromCharCode(...pixels.subarray(i,i+16384)));
  return btoa(chunks.join(''));
 }),'base64');
}

export async function runProductionSoftwareProbe({planFile=path.join(root,'fixtures/PLAN_80S.json')}={}){
 const {loadLongRuntimePlan}=await import('./long_runtime.mjs'),temporary=await temporaryRoot(),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json')),rows=[],files=[],boundaryProof=[];
 let browser,activeServer,page,report,invocation=0;
 try{
  const raw=await readFile(planFile),document=JSON.parse(raw),temporal=selectProductionTemporalFrames(document),privateJob=path.join(temporary,'job');
  assert.equal(document.totalFrames,2400);assert.equal(document.fps,30);assert.equal(document.productionV3.eventChapters.length,12);
  await mkdir(privateJob,{mode:0o700});
  const preparationCode="import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from prepare_video import prepare_job_inputs;p=json.load(open(sys.argv[2]));first=prepare_job_inputs(p,Path(sys.argv[3]));second=prepare_job_inputs(p,Path(sys.argv[3]));assert second['cacheHit'] is True and first['activationSha256']==second['activationSha256'];print(json.dumps({**first,'inputCacheReuseVerified':True}))";
  const prepared=JSON.parse((await execute('/usr/bin/python3',['-B','-c',preparationCode,parent,planFile,privateJob],
   {timeout:180000,maxBuffer:1024*1024})).stdout);
  assert.equal(prepared.gpuExecuted,false);assert.equal(prepared.inputCacheReuseVerified,true);
  const plan=await loadLongRuntimePlan({planFile,expectedPlanSha256:sha(raw),sceneId:document.scenes[0].sceneId,
   activationFile:prepared.activationFile,expectedActivationSha256:prepared.activationSha256});
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
    '--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  const output=process.env.WORLD_ENGINE_PRODUCTION_EVIDENCE_DIR;
  if(output){assert.ok(path.isAbsolute(output)&&path.resolve(output)===output);await mkdir(output,{recursive:true,mode:0o700});
   assert.ok(!(await lstat(output)).isSymbolicLink(),'PRODUCTION_TEST_EVIDENCE_SYMLINK_REFUSED');}
  const store=async(file,captured)=>{
   const bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
   assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
   if(output)await writeFile(path.join(output,file),bytes,{flag:'wx',mode:0o644});
   files.push({file,sha256:captured.png_sha256,bytes:bytes.length,width:1080,height:1920,scope:'CPU_SW_NOT_NVIDIA'});
  };
  const open=async config=>{
   const opened=await start(config,path.join(temporary,'HTTP_'+invocation+++'.json'));activeServer=opened.server;
   page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});const errors=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
   await page.route('**/*',route=>new URL(route.request().url()).origin===opened.origin?route.continue():route.abort('blockedbyclient'));
   await page.goto(opened.origin+'/',{waitUntil:'load',timeout:240000});
   await page.waitForFunction(()=>Object.hasOwn(window,'longVideoBoot'),null,{timeout:240000});
   const info=await page.evaluate(()=>window.longVideoBoot);assert.equal(info.testOnly,true);assert.match(info.backend,/SwiftShader/i);
   assert.equal(info.productionEligible,false);assert.equal(info.universalVideo.planSha256,plan.planSha256);
   assert.equal(info.productionV3.runtimeProfile,'UNIVERSAL_PRODUCTION_V3');assert.equal(info.productionV3.probeVariant,config.runtimeConfig.productionV3ProbeVariant);
   return{info,errors};
  };
  const close=async()=>{if(page){await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await page.close();page=null;}
   activeServer?.kill();activeServer=null;};
  const inspect=async(frame,captured,scene,config,info)=>{
   const d=captured.diagnostic,clock=evaluateProductionGeometryClock(document,frame),production=d.productionV3;
   assert.equal(d.frame,frame);assert.equal(d.universalVideo.globalFrame,frame);assert.equal(d.universalVideo.testOnly,true);
   assert.equal(d.universalVideo.legacySceneSha256,plan.legacySceneSha256);assert.equal(d.glError,0);
   assert.equal(d.universalVideo.sceneRangeSha256,config.runtimeConfig.universalVideo.sceneRangeSha256);
   assert.deepEqual(production.geometryClock,clock);assert.equal(production.noInferredEnemyComplement,true);
   assert.equal(production.noInferredHistoricalUnits,true);assert.equal(production.originalNativeMarkerStyleAndAnchor,true);
   assert.equal(production.originalProjectionUsed,true);assert.equal(d.sourceIntegrity.fictional65422SceneUsed,false);
   assert.equal(d.sourceIntegrity.actualAstraSelected,true);assert.equal(d.sourceIntegrity.sourceBeforeAreaAndFront,true);
   assert.equal(d.coverageCache.entryLimit,1);assert.equal(info.evidence.source.astra.actualMaterialFactorySelected,true);
   assert.equal(d.terrain.astra.gpuUploadExecuted,true);assert.equal(d.terrain.astra.testOnly,true);assert.equal(d.terrain.sourceGrade.gradeDraws,1);
   assert.deepEqual(production.layerOrder,['NATIVE_GIS_COVERAGE','ASTRA_SUPPORTED_SOURCE','ACTUAL_SUPPLIED_AREA_OWNERSHIP',
    'ACTUAL_SUPPLIED_FRONT_WHITE_GOLD','CHAPTER_AND_SNAPSHOT_DATE','ORIGINAL_NATIVE_MARKERS_LABELS']);
   const chapter=document.productionV3.eventChapters.find(row=>frame>=row.startFrame&&frame<row.endFrame);
   assert.deepEqual(production.chapter,chapter);
   if(clock.eventEnabled&&clock.sourceGeometryFrame>document.legacyScenePlan.timing.event_start_frame+document.legacyScenePlan.timing.initial_reveal_frames){
    assert.ok(d.area.graphics.areas.some(row=>row.drawn),'PRODUCTION_ACTUAL_AREA_DRAW_REQUIRED');
    assert.ok(d.area.graphics.fronts.some(row=>row.drawn),'PRODUCTION_ACTUAL_FRONT_DRAW_REQUIRED');
    assert.equal(d.area.controls.frame,clock.sourceGeometryFrame,'PRODUCTION_ACTUAL_SOURCE_FRAME_MISMATCH');
   }
   const suppliedGeometry=assertSuppliedGeometry(document,d.area.controls),geometryBounds=await page.evaluate(measureEventGeometryBounds);
   if(geometryBounds.active){
    assert.equal(geometryBounds.wholeEventGeometryInViewport,true,'PRODUCTION_ACTUAL_SUPPLIED_GEOMETRY_CROPPED');
    assert.equal(geometryBounds.wholeEventGeometryInSafeArea,true,'PRODUCTION_ACTUAL_SUPPLIED_GEOMETRY_OUTSIDE_SAFE_AREA');
   }
   return{d,clock,row:{frame,globalFrame:frame,sceneId:scene.sceneId,sceneRange:[scene.startFrame,scene.endFrame],
    sceneRangeSha256:config.runtimeConfig.universalVideo.sceneRangeSha256,chapterId:chapter.chapterId,
    geometryScheduleId:clock.scheduleId,sourceGeometryFrame:clock.sourceGeometryFrame,stateId:d.area.controls?.stateId??null,
    rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256,geometryBounds,suppliedGeometry,
    actualAstra:d.terrain.astra,sourceGrade:d.terrain.sourceGrade,productionV3:production,timings:d.timings}};
  };
  let afterAB,afterPixels,afterDiagnostic;
  for(const frame of temporal.frames){
   const scene=document.scenes.find(row=>frame>=row.startFrame&&frame<row.endFrame),config=configFor(plan.serverConfig,scene),{info,errors}=await open(config);
   try{
    const captured=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),frame),checked=await inspect(frame,captured,scene,config,info);
    await store('FRAME_'+String(frame).padStart(6,'0')+'.png',captured);rows.push(checked.row);
    if(frame===0)boundaryProof.push(await page.evaluate(measureNativeBoundaryPixels,{frame}));
    if(frame===temporal.abFrame){afterPixels=await rawPixels(page);assert.equal(sha(afterPixels),captured.raw_rgba_sha256);
     afterAB={...frameWitness(checked.d),rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256};afterDiagnostic=checked.d;await store('AB_AFTER.png',captured);}
    assert.deepEqual(errors,[],'PRODUCTION_SW_PAGE_ERRORS');
   }finally{await close();}
  }
  assert.ok(new Set(rows.filter(row=>row.stateId!==null).map(row=>row.stateId)).size>=2,'PRODUCTION_MULTIPLE_ACTUAL_STATES_REQUIRED');
  assert.ok(new Set(rows.map(row=>row.rawRgbaSha256)).size>=2,'PRODUCTION_NON_CONSTANT_RENDER_REQUIRED');
  const abScene=document.scenes.find(row=>temporal.abFrame>=row.startFrame&&temporal.abFrame<row.endFrame),abConfig=configFor(plan.serverConfig,abScene,'BEFORE'),
   beforeBoot=await open(abConfig);let abComparison;
  try{
   const captured=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),temporal.abFrame),checked=await inspect(temporal.abFrame,captured,abScene,abConfig,beforeBoot.info),
    beforePixels=await rawPixels(page),before={...frameWitness(checked.d),rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256};
   assert.equal(sha(beforePixels),captured.raw_rgba_sha256);assert.equal(before.cameraSha256,afterAB.cameraSha256);
   assert.equal(before.geometrySha256,afterAB.geometrySha256);assert.equal(before.dateSha256,afterAB.dateSha256);
   assert.notEqual(before.rawRgbaSha256,afterAB.rawRgbaSha256);await store('AB_BEFORE.png',captured);
   const pixels=compareActualPixels(beforePixels,afterPixels,{safeArea:afterDiagnostic.camera.safeArea,
    protectedGraphics:afterDiagnostic.camera.protectedGraphics});
   abComparison={status:'PASS',frame:temporal.abFrame,sceneId:abScene.sceneId,sceneRangeSha256:abConfig.runtimeConfig.universalVideo.sceneRangeSha256,
    sameFrame:true,sameGeometryClock:true,sameCamera:true,sameChapterDate:true,comparisonScope:'SAME_FRAME_CAMERA_GEOMETRY_DATE',...pixels,before,after:afterAB};
   assert.deepEqual(beforeBoot.errors,[],'PRODUCTION_AB_SW_PAGE_ERRORS');
  }finally{await close();}
  const fullScene={...document.scenes[0],sceneId:'TEST_ONLY_UNSEGMENTED_GLOBAL_CLOCK',startFrame:0,endFrame:document.totalFrames,globalFrameOffset:0},
   fullConfig=configFor(plan.serverConfig,fullScene),fullBoot=await open(fullConfig),continuity=[];
  try{
   const actualPair=assertActualAdjacentScenePair(document,temporal.witness.beforeFrame,temporal.witness.afterFrame);
   for(const frame of [actualPair.beforeFrame,actualPair.afterFrame]){
    const actual=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:false}),frame),segmented=rows.find(row=>row.frame===frame);
    assert.equal(actual.raw_rgba_sha256,segmented.rawRgbaSha256,'PRODUCTION_REAL_SCENE_CUT_CHANGED_PIXELS');
    assert.deepEqual(actual.diagnostic.productionV3.geometryClock,evaluateProductionGeometryClock(document,frame));
    continuity.push({globalFrame:frame,sceneId:segmented.sceneId,productionSceneRange:segmented.sceneRange,
     productionSceneRangeSha256:segmented.sceneRangeSha256,segmentedRawRgbaSha256:segmented.rawRgbaSha256,
     fullTimelineRawRgbaSha256:actual.raw_rgba_sha256,bitExact:true});
   }assert.deepEqual(fullBoot.errors,[],'PRODUCTION_UNSEGMENTED_PAGE_ERRORS');
  }finally{await close();}
  await plan.assertSourceUnchanged();
  if(output)await writeFile(path.join(output,'SHA256SUMS'),files.map(row=>row.sha256+'  '+row.file).join('\n')+'\n',{flag:'wx',mode:0o644});
  report={schema:SCHEMA,status:'PASS',testOnly:true,actualDrawReadPixels:true,actualShaderCompile:true,softwareWebGLDrawExecuted:true,
   actualHistoricalSceneSelected:true,twelveChapterPlanSelected:true,originalSourcesUnchanged:true,nvidiaHardwareVerified:false,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,full80SecondVideoRendered:false,all5TemporalFrames:true,
   boundaryContinuityBitExact:true,rangeBoundaryContinuityVerified:true,actualAstraUpload:true,sourceGradeSelected:true,sourceOrderVerified:true,
   ABComparisonVerified:true,abComparison,browserVersion:browser.version(),nodeVersion:process.version,playwrightVersion:require('playwright/package.json').version,
   frames:[...temporal.frames],actualBoundaryPair:temporal.witness,rows,files,continuity,
   nativeBoundaryProtection:{status:'PASS',actualReadPixelsCompared:true,cases:boundaryProof},
   productionCpuPreparationSelected:true,inputCacheReuseVerified:prepared.inputCacheReuseVerified,
   projectedEventGeometryMeasured:true,wholeEventGeometryInViewport:true,wholeEventGeometryInSafeArea:true,
   sourceGeometryMeaning:'PRESERVED_SUPPLIED_SCHEMATIC_SNAPSHOTS_NOT_ARCHIVAL_DAILY_CONTROL',
   shaderBackend:'SWIFTSHADER_ONLY',sampleMp4Generated:false,gpuVideoQualityApproved:false,
   planSha256:plan.planSha256,legacySceneSha256:plan.legacySceneSha256,sourceSignature:plan.sourceSignature,
   productionIntegrity:plan.productionIntegrity};
  return report;
 }finally{
  try{if(page){await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await page.close();}}catch{}
  activeServer?.kill();await browser?.close();await rm(temporary,{recursive:true,force:true});
 }
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{console.log(JSON.stringify(await runProductionSoftwareProbe()));}
 catch(error){console.error(JSON.stringify({schema:SCHEMA,status:'FAIL',testOnly:true,errorCode:error?.message??'PRODUCTION_SOFTWARE_TEST_FAILED',
  nvidiaHardwareVerified:false,physicalNvidiaExecuted:false,gpuRenderingVerified:false,full80SecondVideoRendered:false}));process.exitCode=2;}
}
