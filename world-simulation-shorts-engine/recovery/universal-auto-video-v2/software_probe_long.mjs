/** Actual SwiftShader tests of the same Area/ASTRA runtime. This does not use
 * production GPU admission, create a sample MP4 or certify NVIDIA/video quality. */
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,rm,lstat} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
import {loadLongRuntimePlan,sha,repo,engine} from './long_runtime.mjs';
const execute=promisify(execFile),root=path.dirname(fileURLToPath(import.meta.url));
export const temporalFrames=Object.freeze([0,299,300,1200,2399]);
/** Runs inside the real browser: compare only the original finite native
 * boundary support, excluding its own measured graphics. A 32px spatial index
 * avoids testing millions of pixels against every geography segment. */
export async function measureNativeBoundaryPixels({frame}){
 const proof=window.longVideoProof;
 if(!proof?.testOnlyNative)throw Error('UNIVERSAL_EXPLICIT_TEST_NATIVE_API_REQUIRED');
 await proof.capture(frame,{png:false});const finalPixels=proof.pipeline.readPixels().slice();
 proof.testOnlyNative.drawFrame(frame);const original=proof.testOnlyNative.readPixels(),
  segments=proof.testOnlyNative.boundarySegments,protectedGraphics=proof.testOnlyNative.protectedGraphics;
 if(original.length!==1080*1920*4||finalPixels.length!==original.length)throw Error('UNIVERSAL_BOUNDARY_PIXEL_DIMENSIONS');
 const tiles=new Map(),tileSize=32,columns=Math.ceil(1080/tileSize),rows=Math.ceil(1920/tileSize);
 const segmentDistance=(x,y,edge)=>{const dx=edge.b[0]-edge.a[0],dy=edge.b[1]-edge.a[1],length=dx*dx+dy*dy,
  t=length?Math.max(0,Math.min(1,((x-edge.a[0])*dx+(y-edge.a[1])*dy)/length)):0;
  return Math.hypot(x-edge.a[0]-t*dx,y-edge.a[1]-t*dy);};
 for(const edge of segments){
  if(!Number.isFinite(edge.radiusPx)||edge.radiusPx<=0)throw Error('UNIVERSAL_ACTUAL_BOUNDARY_SUPPORT_REQUIRED');
  const left=Math.max(0,Math.floor((Math.min(edge.a[0],edge.b[0])-edge.radiusPx)/tileSize)),
   right=Math.min(columns-1,Math.floor((Math.max(edge.a[0],edge.b[0])+edge.radiusPx)/tileSize)),
   top=Math.max(0,Math.floor((Math.min(edge.a[1],edge.b[1])-edge.radiusPx)/tileSize)),
   bottom=Math.min(rows-1,Math.floor((Math.max(edge.a[1],edge.b[1])+edge.radiusPx)/tileSize));
  for(let y=top;y<=bottom;y++)for(let x=left;x<=right;x++){
   const key=y*columns+x;if(!tiles.has(key))tiles.set(key,[]);tiles.get(key).push(edge);
  }
 }
 let boundaryPixels=0,changedBoundaryPixels=0,changedOutsideBoundary=0,excludedGraphicPixels=0;
 const inside=(x,y,box)=>x>=box[0]&&x<=box[2]&&y>=box[1]&&y<=box[3];
 for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
  if(protectedGraphics.some(item=>inside(x+.5,y+.5,item.box))){excludedGraphicPixels++;continue;}
  const index=((1919-y)*1080+x)*4,changed=original[index]!==finalPixels[index]||original[index+1]!==finalPixels[index+1]
   ||original[index+2]!==finalPixels[index+2],edges=tiles.get(Math.floor(y/tileSize)*columns+Math.floor(x/tileSize))??[],
   onBoundary=edges.some(edge=>segmentDistance(x+.5,y+.5,edge)<=edge.radiusPx);
  if(onBoundary){boundaryPixels++;if(changed)changedBoundaryPixels++;}
  else if(changed)changedOutsideBoundary++;
 }
 if(boundaryPixels<1||changedBoundaryPixels!==0||changedOutsideBoundary<1)
  throw Error('UNIVERSAL_ACTUAL_NATIVE_BOUNDARY_PROTECTION_FAILED '+JSON.stringify({boundaryPixels,changedBoundaryPixels,changedOutsideBoundary}));
 return {status:'PASS',actualReadPixelsCompared:true,frame,boundaryPixels,changedBoundaryPixels,
  changedOutsideBoundary,excludedGraphicPixels,nativeSegmentCount:segments.length,
  support:'ACTUAL_NATIVE_RADIUS_PIXEL_CENTERS',spatialIndexTilePixels:tileSize,testOnly:true,
  sourceInteriorChanged:true,sourceOnlyInteriorClaimed:frame===0,physicalNvidiaExecuted:false};
}
async function start(config,file){
 const bytes=Buffer.from(JSON.stringify(config));await writeFile(file,bytes,{flag:'wx',mode:0o600});
 const server=spawn('/usr/bin/python3',['-B',path.join(root,'serve_long.py'),'--config',file,'--expected-config-sha256',sha(bytes)],
  {cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';server.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-2048);});
 const origin=await new Promise((resolve,reject)=>{const lines=createInterface({input:server.stdout}),
  timer=setTimeout(()=>{lines.close();reject(Error('UNIVERSAL_SW_SERVER_TIMEOUT'));},10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const row=JSON.parse(line),url=new URL(row.url);
   assert.ok(row.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1');resolve(url.origin);
  }catch(error){reject(error);}});
  for(const event of ['error','exit'])server.once(event,()=>{clearTimeout(timer);lines.close();reject(Error('UNIVERSAL_SW_SERVER_FAILED '+stderr));});
 });return {server,origin};
}
function configFor(base,scene){
 const config=structuredClone(base);config.runtimeConfig.testOnlySoftwareProbe=true;
 Object.assign(config.runtimeConfig.universalVideo,{scene,sceneRangeSha256:sha(Buffer.from(JSON.stringify(scene))),testOnly:true});return config;
}
export async function runLongSoftwareProbe({planFile=path.join(root,'fixtures/PLAN_80S.json')}={}){
 const temporary=await mkdtemp(path.join(tmpdir(),'world-engine-universal-software-')),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json')),rows=[],files=[],boundaryProof=[];
 let browser,activeServer,page,report;
 try{
  const raw=await readFile(planFile),document=JSON.parse(raw),privateJob=path.join(temporary,'job');
  await mkdir(privateJob,{mode:0o700});
  const preparationCode="import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from prepare_video import prepare_job_inputs;p=json.load(open(sys.argv[2]));first=prepare_job_inputs(p,Path(sys.argv[3]));second=prepare_job_inputs(p,Path(sys.argv[3]));assert second['cacheHit'] is True and first['activationSha256']==second['activationSha256'];print(json.dumps({**first,'inputCacheReuseVerified':True}))";
  const prepared=JSON.parse((await execute('/usr/bin/python3',['-B','-c',preparationCode,root,planFile,privateJob],
   {timeout:180000,maxBuffer:1024*1024})).stdout);
  assert.equal(prepared.gpuExecuted,false);assert.equal(prepared.inputCacheReuseVerified,true);
  const plan=await loadLongRuntimePlan({planFile,
   expectedPlanSha256:sha(raw),sceneId:document.scenes[0].sceneId,activationFile:prepared.activationFile,
   expectedActivationSha256:prepared.activationSha256});
  assert.equal(document.totalFrames,2400);assert.equal(document.fps,30);
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
    '--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  const output=process.env.WORLD_ENGINE_UNIVERSAL_EVIDENCE_DIR;
  if(output){assert.ok(path.isAbsolute(output)&&path.resolve(output)===output);await mkdir(output,{recursive:true,mode:0o700});
   assert.ok(!(await lstat(output)).isSymbolicLink(),'UNIVERSAL_TEST_EVIDENCE_SYMLINK_REFUSED');}
  let invocation=0;
  const open=async config=>{
   const opened=await start(config,path.join(temporary,'HTTP_'+invocation+++'.json'));activeServer=opened.server;
   page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});const errors=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
   await page.route('**/*',route=>new URL(route.request().url()).origin===opened.origin?route.continue():route.abort('blockedbyclient'));
   await page.goto(opened.origin+'/',{waitUntil:'load',timeout:240000});
   await page.waitForFunction(()=>Object.hasOwn(window,'longVideoBoot'),null,{timeout:240000});
   const info=await page.evaluate(()=>window.longVideoBoot);assert.equal(info.testOnly,true);assert.match(info.backend,/SwiftShader/i);
   assert.equal(info.productionEligible,false);assert.equal(info.universalVideo.planSha256,plan.planSha256);
   return {info,errors};
  };
  const close=async()=>{if(page){await page.evaluate(()=>window.longVideoProof?.dispose());await page.close();page=null;}
   activeServer?.kill();activeServer=null;};
  for(const frame of temporalFrames){
   const scene=document.scenes.find(item=>frame>=item.startFrame&&frame<item.endFrame);assert.ok(scene);
   const config=configFor(plan.serverConfig,scene),{info,errors}=await open(config);
   try{
    const captured=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:true}),frame),d=captured.diagnostic;
    assert.equal(d.frame,frame);assert.equal(d.universalVideo.globalFrame,frame);assert.equal(d.universalVideo.testOnly,true);
    assert.equal(d.universalVideo.legacySceneSha256,plan.legacySceneSha256);assert.equal(d.glError,0);
    assert.equal(d.sourceIntegrity.fictional65422SceneUsed,false);assert.equal(d.sourceIntegrity.actualAstraSelected,true);
    assert.equal(d.sourceIntegrity.sourceBeforeAreaAndFront,true);assert.equal(d.coverageCache.entryLimit,1);
    assert.equal(info.evidence.source.astra.actualMaterialFactorySelected,true);
    assert.equal(d.terrain.astra.gpuUploadExecuted,true);assert.equal(d.terrain.astra.testOnly,true);
    assert.equal(d.terrain.sourceGrade.gradeDraws,1);
    const bytes=Buffer.from(captured.png.split(',')[1],'base64');assert.equal(sha(bytes),captured.png_sha256);
    assert.equal(bytes.readUInt32BE(16),1080);assert.equal(bytes.readUInt32BE(20),1920);
    const filename='FRAME_'+String(frame).padStart(6,'0')+'.png';
    if(output)await writeFile(path.join(output,filename),bytes,{flag:'wx',mode:0o644});
    files.push({file:filename,sha256:captured.png_sha256,bytes:bytes.length});
    rows.push({frame,sceneId:scene.sceneId,rawRgbaSha256:captured.raw_rgba_sha256,pngSha256:captured.png_sha256,
     stateId:d.area.controls?.stateId??null,globalFrame:d.universalVideo.globalFrame,
     cameraNativeFrame:d.camera.nativeFrame,cameraClamped:d.camera.frameClamped,
     actualAstra:d.terrain.astra,sourceGrade:d.terrain.sourceGrade,coverageCache:d.coverageCache,timings:d.timings});
    if(frame===0||frame===1200)boundaryProof.push(await page.evaluate(measureNativeBoundaryPixels,{frame}));
    assert.deepEqual(errors,[],'UNIVERSAL_SW_PAGE_ERRORS');
   }finally{await close();}
  }
  const fullScene={...document.scenes[0],sceneId:'TEST_ONLY_UNSEGMENTED_GLOBAL_CLOCK',startFrame:0,endFrame:document.totalFrames,
   globalFrameOffset:0},fullConfig=configFor(plan.serverConfig,fullScene),{errors}=await open(fullConfig),continuity=[];
  try{for(const frame of [299,300]){
   const actual=await page.evaluate(frame=>window.longVideoProof.capture(frame,{png:false}),frame),segmented=rows.find(row=>row.frame===frame);
   assert.equal(actual.raw_rgba_sha256,segmented.rawRgbaSha256,'UNIVERSAL_SEGMENT_RESET_CHANGED_PIXELS');
   continuity.push({globalFrame:frame,segmentedRawRgbaSha256:segmented.rawRgbaSha256,
    fullTimelineRawRgbaSha256:actual.raw_rgba_sha256,bitExact:true});
  }assert.deepEqual(errors,[]);}finally{await close();}
  await plan.assertSourceUnchanged();
  if(output)await writeFile(path.join(output,'SHA256SUMS'),files.map(row=>row.sha256+'  '+row.file).join('\n')+'\n',{flag:'wx',mode:0o644});
  report={schema:'WORLD_ENGINE_UNIVERSAL_ACTUAL_SOFTWARE_PROBE_V2',status:'PASS',testOnly:true,actualDrawReadPixels:true,
   actualShaderCompile:true,softwareWebGLDrawExecuted:true,actualHistoricalSceneSelected:true,originalSourcesUnchanged:true,
   nvidiaHardwareVerified:false,physicalNvidiaExecuted:false,gpuRenderingVerified:false,full80SecondVideoRendered:false,
   all5TemporalFrames:true,boundaryContinuityBitExact:true,rangeBoundaryContinuityVerified:true,
   browserVersion:browser.version(),nodeVersion:process.version,playwrightVersion:require('playwright/package.json').version,
   frames:[...temporalFrames],rows,files,continuity,nativeBoundaryProtection:{status:'PASS',actualReadPixelsCompared:true,cases:boundaryProof},
   productionCpuPreparationSelected:true,inputCacheReuseVerified:prepared.inputCacheReuseVerified,
   sourceGeometryMeaning:'PRESERVED_SCHEMATIC_HISTORICAL_STATES_NOT_ARCHIVAL_DAILY_CONTROL',
   shaderBackend:'SWIFTSHADER_ONLY',sampleMp4Generated:false,gpuVideoQualityApproved:false,
   planSha256:plan.planSha256,legacySceneSha256:plan.legacySceneSha256,sourceSignature:plan.sourceSignature};
  return report;
 }finally{
  try{if(page){await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await page.close();}}catch{}
  activeServer?.kill();await browser?.close();await rm(temporary,{recursive:true,force:true});
 }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{console.log(JSON.stringify(await runLongSoftwareProbe()));}
 catch(error){console.error(JSON.stringify({schema:'WORLD_ENGINE_UNIVERSAL_ACTUAL_SOFTWARE_PROBE_V2',status:'FAIL',testOnly:true,
  errorCode:error?.message??'UNIVERSAL_SOFTWARE_TEST_FAILED',nvidiaHardwareVerified:false,physicalNvidiaExecuted:false,gpuRenderingVerified:false,full80SecondVideoRendered:false}));process.exitCode=2;}
}
