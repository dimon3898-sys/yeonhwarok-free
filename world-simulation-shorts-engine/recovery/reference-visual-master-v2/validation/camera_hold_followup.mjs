/** TEST-ONLY mounted follow-up for an immutable published image. No image,
 * production source, manifest, renderer, or original proof is changed. */
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,open,mkdir,lstat,rm} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
const execute=promisify(execFile);
export const IMAGE_ROOT='/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/reference-visual-master-v2';
export const IMMUTABLE_IMAGE='ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5';
export const evidenceNames=['A_100.png','E_100.png'];
const comparableUnit=unit=>({id:unit.id,profile_id:unit.profile_id,anchor:unit.anchor,
 size_px:unit.size_px,rotation_degrees:unit.rotation_degrees});
const spatial=row=>({bounds:row.diagnostic.camera.bounds,nativeExpandedBounds:row.diagnostic.camera.nativeExpandedBounds,
 rollDegrees:row.diagnostic.camera.rollDegrees,overscan:row.diagnostic.camera.overscan});
function projectionDifference(one,two){
 assert.equal(one.length,two.length);assert.ok(one.length>0);
 const visible=point=>Array.isArray(point)&&point.length===2&&point.every(Number.isFinite)
  &&point[0]>=0&&point[0]<1080&&point[1]>=0&&point[1]<1920;
 const distances=one.map((point,index)=>visible(point)&&visible(two[index])?
  Math.hypot(point[0]-two[index][0],point[1]-two[index][1]):null).filter(value=>value!==null);
 assert.ok(distances.length>=4,'FOLLOWUP_VISIBLE_REFERENCE_POINTS_REQUIRED');
 return {sampleCount:distances.length,discardedOffscreenPoints:one.length-distances.length,maximumPixels:Math.max(...distances),
  rmsPixels:Math.sqrt(distances.reduce((sum,value)=>sum+value*value,0)/distances.length)};
}
function maxNumericDifference(one,two){
 const a=JSON.stringify(one),b=JSON.stringify(two);if(a===b)return 0;
 const numbers=value=>Array.isArray(value)?value.flatMap(numbers):typeof value==='number'?[value]:
  value&&typeof value==='object'?Object.values(value).flatMap(numbers):[];
 const first=numbers(one),second=numbers(two);assert.equal(first.length,second.length);
 return Math.max(...first.map((value,index)=>Math.abs(value-second[index])));
}
export function validateFollowupRows(cases){
 const a=cases.A.find(row=>row.frame===100),e=cases.E.find(row=>row.frame===100);
 assert.ok(a&&e);assert.notEqual(a.raw_rgba_sha256,e.raw_rgba_sha256,'FOLLOWUP_SELECTED_CAMERA_MUST_CHANGE_ACTUAL_PIXELS');
 assert.deepEqual(a.diagnostic.territory.controls,e.diagnostic.territory.controls,'FOLLOWUP_EVENT_MUST_MATCH_AT_FRAME_100');
 assert.deepEqual(a.diagnostic.units.units.map(comparableUnit),e.diagnostic.units.units.map(comparableUnit),
  'FOLLOWUP_WORLD_UNITS_AND_SIZES_MUST_MATCH');
 assert.equal(a.diagnostic.protection.sourceGeometrySha256,e.diagnostic.protection.sourceGeometrySha256);
 const delta=projectionDifference(a.projectedReferencePoints,e.projectedReferencePoints);
 assert.ok(delta.rmsPixels>1,'FOLLOWUP_CAMERA_DIFFERENCE_MUST_EXCEED_ONE_PIXEL');
 assert.ok(maxNumericDifference(spatial(a),spatial(e))>1e-9,'FOLLOWUP_CAMERA_BOUNDS_MUST_MEANINGFULLY_DIFFER');
 assert.deepEqual(cases.E.map(row=>row.frame),[99,100,101]);
 const holdDeltas=cases.E.map(row=>projectionDifference(e.projectedReferencePoints,row.projectedReferencePoints));
 for(const row of cases.E){
  assert.ok(maxNumericDifference(spatial(e),spatial(row))<1e-9,'FOLLOWUP_HOLD_SPATIAL_CAMERA_MUST_MATCH');
  assert.equal(row.diagnostic.territory.controls.frame-row.eventStartFrame,row.frame,'FOLLOWUP_EVENT_INDEX_MUST_ADVANCE');
 }
 assert.ok(holdDeltas.every(item=>item.maximumPixels<.00001),'FOLLOWUP_ACTUAL_PROJECTION_HOLD_REQUIRED');
 for(let i=1;i<cases.E.length;i++){
  assert.notDeepEqual(cases.E[i-1].diagnostic.territory.controls.boundaryLatitudes,
   cases.E[i].diagnostic.territory.controls.boundaryLatitudes,'FOLLOWUP_EVENT_BOUNDARY_MUST_KEEP_ADVANCING');
  assert.notEqual(cases.E[i-1].raw_rgba_sha256,cases.E[i].raw_rgba_sha256,'FOLLOWUP_EVENT_FRAMES_MUST_NOT_FREEZE');
 }
 return {actualCameraDeltaPixels:delta.rmsPixels,projectionDelta:delta,holdLocked:true,
  holdProjectionDeltas:holdDeltas,eventAdvances:true,pixelsDiffer:true};
}
async function serve(config,file,sha,repo){
 const bytes=Buffer.from(JSON.stringify(config));await writeFile(file,bytes,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(IMAGE_ROOT,'serve_ref2.py'),'--config',file,
  '--expected-config-sha256',sha(bytes)],{cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';
 server.stderr.on('data',data=>{stderr=(stderr+data).slice(-4096);});
 const origin=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('FOLLOWUP_SERVER_TIMEOUT'));},10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const item=JSON.parse(line),url=new URL(item.url);
   assert.equal(item.event,'READY');assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');resolve(url.origin);
  }catch(error){reject(error);}});
  server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
  server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('FOLLOWUP_SERVER_EXIT_'+code+' '+stderr));});
 });return {server,origin};
}
export async function runCameraHoldFollowup(){
 const {loadReferenceRuntimePlan,sha,repo}=await import(pathToFileURL(path.join(IMAGE_ROOT,'ref2_runtime.mjs')).href),
  {assertQualityDiagnostic}=await import(pathToFileURL(path.join(IMAGE_ROOT,'../rtx-gpu-package-v1/hardware_runtime.mjs')).href),
  temporary=await mkdtemp(path.join(tmpdir(),'reference-camera-followup-')),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 let browser,activeServer;const cases={},files=[],bindings={};
 try{
  const verification=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(IMAGE_ROOT,'prepare_ref2.py'),
   '--verify-extension'],{timeout:120000,maxBuffer:1024*1024})).stdout);assert.equal(verification.status,'PASS');
  const prepared=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(IMAGE_ROOT,'prepare_ref2.py'),
   '--prepare-activation','--private-root',temporary,'--variant','F'],{timeout:120000,maxBuffer:1024*1024})).stdout),
   original=JSON.parse(await readFile(prepared.activationFile)),output=process.env.WORLD_ENGINE_REFERENCE_FOLLOWUP_DIR??'/workspace/reference-followup';
  assert.ok(path.isAbsolute(output)&&path.resolve(output)===output,'FOLLOWUP_OUTPUT_PATH_REQUIRED');
  await mkdir(output,{mode:0o700,recursive:true});const directory=await lstat(output);
  assert.ok(directory.isDirectory()&&!directory.isSymbolicLink(),'FOLLOWUP_REGULAR_OUTPUT_DIRECTORY_REQUIRED');
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),
    XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},ignoreDefaultArgs:['--disable-dev-shm-usage'],
   args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  let referencePoints;
  for(const variant of ['A','E']){
   const activation={...original,profileId:'REFERENCE_VISUAL_MASTER_V2_'+variant,
    referenceV2:{...original.referenceV2,variant}},bytes=Buffer.from(JSON.stringify(activation)+'\n'),
    activationFile=path.join(temporary,'ACTIVATION_'+variant+'.json');await writeFile(activationFile,bytes,{mode:0o600,flag:'wx'});
   const plan=await loadReferenceRuntimePlan({activationFile,expectedActivationSha256:sha(bytes)}),config=structuredClone(plan.serverConfig);
   config.runtimeConfig.testOnlySoftwareProbe=true;
   const scene=structuredClone(plan.scenePlan);delete scene.cameraKeyframes;
   bindings[variant]={nonCameraSceneSha256:sha(Buffer.from(JSON.stringify(scene))),
    bundleManifestSha256:plan.bundleManifestSha256,sourceSignature:plan.sourceSignature,
    baseSceneSha256:plan.referenceV2.baseSceneSha256,cameraKeyframeSha256:plan.referenceV2.cameraKeyframeSha256};
   if(!referencePoints){const intent=plan.scenePlan.controlIntent;
    referencePoints=[...plan.scenePlan.combatProfile.units.map(unit=>unit.anchor_frames[100]),
     ...intent.longitudinal_knots.filter((_,index)=>index%8===0).map(longitude=>[longitude,
      plan.scenePlan.combatProfile.units[0].anchor_frames[100][1]])];
    assert.ok(referencePoints.length>=8);}
   const {server,origin}=await serve(config,path.join(temporary,'HTTP_'+variant+'.json'),sha,repo);activeServer=server;
   const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.status()>=400)
    errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
   await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
   try{
    await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
    await page.waitForFunction(()=>Object.hasOwn(window,'referenceV2Boot'),null,{timeout:240000});
    const info=await page.evaluate(()=>window.referenceV2Boot);
    assert.equal(info.testOnly,true);assert.equal(info.productionEligible,false);assert.equal(info.gpuRenderingVerified,false);
    assert.match(info.backend,/SwiftShader/i);assert.equal(info.referenceV2.variant,variant);
    const rows=[];
    for(const frame of variant==='A'?[100]:[99,100,101]){
     const row=await page.evaluate(async({frame,points})=>{
      const row=await window.referenceProof.capture(frame,{png:frame===100}),pipeline=window.referenceProof.pipeline,
       gl=document.querySelector('canvas').getContext('webgl2'),actual=pipeline.readPixels();
      if(!actual||actual.length!==1080*1920*4)throw Error('FOLLOWUP_ACTUAL_READPIXELS_REQUIRED');
      return {...row,projectedReferencePoints:points.map(point=>pipeline.project(point)),actualReadPixelsExecuted:true,
       actualWebGL2Version:gl.getParameter(gl.VERSION),glErrorAfterRead:gl.getError()};
     },{frame,points:referencePoints});
     assertQualityDiagnostic(row.diagnostic,{frame});assert.equal(row.actualReadPixelsExecuted,true);
     assert.match(row.actualWebGL2Version,/WebGL\s*2/i);assert.equal(row.glErrorAfterRead,0);
     assert.equal(row.diagnostic.referenceV2.testOnly,true);assert.equal(row.diagnostic.referenceV2.variant,variant);
     assert.match(row.raw_rgba_sha256,/^[a-f0-9]{64}$/);
     if(frame===100){const png=Buffer.from(row.png.split(',')[1],'base64'),name=variant+'_100.png';
      assert.equal(sha(png),row.png_sha256);assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1920);
      assert.ok(png.length<=12*1024*1024);const fd=await open(path.join(output,name),'wx',0o644);
      try{await fd.writeFile(png);await fd.chmod(0o644);}finally{await fd.close();}
      files.push({file:name,sha256:sha(png),bytes:png.length,width:1080,height:1920,scope:'CPU_SW_NOT_NVIDIA'});}
     rows.push({frame,raw_rgba_sha256:row.raw_rgba_sha256,pngSha256:row.png_sha256,
      projectedReferencePoints:row.projectedReferencePoints,diagnostic:row.diagnostic,
      eventStartFrame:plan.scenePlan.controlIntent.start_frame,backend:info.backend,
      actualWebGL2Version:row.actualWebGL2Version,actualReadPixelsExecuted:true});
    }
    assert.deepEqual(errors,[]);await plan.assertSourceUnchanged();cases[variant]=rows;
   }finally{await page.evaluate(()=>window.referenceProof?.dispose()).catch(()=>{});await page.close();server.kill();
    await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));activeServer=null;}
  }
  assert.equal(bindings.A.nonCameraSceneSha256,bindings.E.nonCameraSceneSha256);
  assert.equal(bindings.A.bundleManifestSha256,bindings.E.bundleManifestSha256);
  assert.equal(bindings.A.baseSceneSha256,bindings.E.baseSceneSha256);
  assert.notEqual(bindings.A.cameraKeyframeSha256,bindings.E.cameraKeyframeSha256);
  const proof=validateFollowupRows(cases);
  const summary={schema:'REFERENCE_CAMERA_HOLD_FOLLOWUP_SW_V1',status:'PASS',testOnly:true,
   immutableImage:IMMUTABLE_IMAGE,followupScriptSha256:sha(await readFile(fileURLToPath(import.meta.url))),
   sourceVerification:verification,actualShaderCompile:true,actualWebGL2DrawExecuted:true,
   actualReadPixelsExecuted:true,softwareWebGLDrawExecuted:true,physicalNvidiaExecuted:false,gpuRenderingVerified:false,
   actualNvidiaVideoGenerated:false,imageBuilt:false,productionSourcesModified:false,
   materialAndSourceAndEventAndWorldUnitsEqual:true,selectedComparisonFrame:100,...proof,bindings,files,
   cases:Object.fromEntries(Object.entries(cases).map(([variant,rows])=>[variant,rows.map(row=>({frame:row.frame,
    rawRGBA_SHA256:row.raw_rgba_sha256,pngSha256:row.pngSha256,spatialCamera:spatial(row),
    projectedReferencePoints:row.projectedReferencePoints,eventFrame:row.diagnostic.territory.controls.frame,
    movingBoundaryLatitudes:row.diagnostic.territory.controls.boundaryLatitudes,backend:row.backend,
    actualWebGL2Version:row.actualWebGL2Version,actualReadPixelsExecuted:true}))])),
   comparisonScope:'TARGETED_CAMERA_HOLD_FRAMES_ONLY_NOT_FULL_NVIDIA_VIDEO_OR_VISUAL_APPROVAL',
   videoQualityApproved:false,productionRenderAllowed:false};console.log(JSON.stringify(summary));return summary;
 }catch(error){console.error('REFERENCE_CAMERA_FOLLOWUP_ERROR',String(error.stack??error.message).slice(0,12000));
  console.log(JSON.stringify({schema:'REFERENCE_CAMERA_HOLD_FOLLOWUP_SW_V1',status:'FAIL',testOnly:true,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,errorType:error.name,productionRenderAllowed:false}));
  process.exitCode=1;return null;
 }finally{await browser?.close().catch(()=>{});activeServer?.kill();await rm(temporary,{recursive:true,force:true});}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 assert.equal(process.argv.length,2,'FOLLOWUP_NO_ARGUMENTS');await runCameraHoldFollowup();
}
