/** Actual SwiftShader GLSL compile/draw A/B test. NEVER physical GPU admission or public proof. */
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadAstraRuntimePlan,sha,repo} from './astra_runtime.mjs';
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
const root=await mkdtemp(path.join(tmpdir(),'astra-software-probe-'));
let browser,server;
try{
 const prepared=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'prepare_activation.py'),
  '--prepare-activation','--private-root',root],{maxBuffer:1024*1024,timeout:120000})).stdout);
 assert.equal(prepared.profileId,'ASTRA_SOURCE_MATERIAL_V1');
 const plan=await loadAstraRuntimePlan({activationFile:prepared.activationFile,expectedActivationSha256:prepared.activationSha256});
 const chromium=require('playwright').chromium;
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
  ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
   '--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
 async function view(materialProfile,frames){
  const config=structuredClone(plan.serverConfig);
  config.runtimeConfig.testOnlySoftwareProbe=true;
  config.runtimeConfig.astra.materialProfile=materialProfile;
  const filename=path.join(root,'CONFIG_'+Date.now()+'_'+Math.random().toString(16).slice(2)+'.json'),bytes=Buffer.from(JSON.stringify(config));
  await writeFile(filename,bytes,{flag:'wx',mode:0o600});
  server=spawn('/usr/bin/python3',['-B',path.join(here,'serve_astra.py'),'--config',filename,'--expected-config-sha256',sha(bytes)],
   {cwd:repo,stdio:['ignore','pipe','pipe']});
  let stderr='';server.stderr.on('data',b=>{stderr=(stderr+b).slice(-4096);});
  const origin=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>reject(Error('SOFTWARE_SERVER_TIMEOUT')),10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{
    const item=JSON.parse(line);assert.equal(item.event,'READY');const address=new URL(item.url);
    assert.equal(address.hostname,'127.0.0.1');resolve(address.origin);
   }catch(error){reject(error);}});
   server.once('error',reject);server.once('exit',code=>{clearTimeout(timer);reject(Error('SOFTWARE_SERVER_EXIT_'+code+' '+stderr));});
  });
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
  await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort('blockedbyclient'));
  try{
   await page.goto(origin+'/',{waitUntil:'load',timeout:180000});
   await page.waitForFunction(()=>Object.hasOwn(window,'astraBoot'),null,{timeout:180000});
   const info=await page.evaluate(()=>window.astraBoot);
   assert.equal(info.testOnly,true);assert.equal(info.productionEligible,false);
   assert.equal(info.gpuRenderingVerified,false);assert.match(info.backend,/SwiftShader/i);
   assert.equal(info.astra.actualMaterialFactorySelected,true);assert.equal(info.cameraMotion.status,'PASS');
   const rows=[];
   for(const frame of frames){
    const row=await page.evaluate(async frame=>window.referenceProof.capture(frame,{png:false}),frame);
    const d=row.diagnostic,a=d.terrain.astra;
    assert.equal(d.gpu.glError,0);assert.equal(d.frame,frame);assert.equal(d.protection.sourceUnchanged,true);
    assert.equal(d.territory.geometryUnchanged,true);assert.equal(d.frontierLight.realControlBoundaryDerived,true);
    assert.equal(d.units.noText,true);assert.equal(d.units.nationalFlags,true);
    assert.equal(a.actualMaterialFactorySelected,true);assert.equal(a.testOnly,true);
    assert.equal(a.sourceMaterialBeforeTerritory,true);assert.equal(a.combinedOutputTexture,true);
    assert.equal(a.actualNativeCoverage,true);assert.equal(a.drawPasses,3);
    assert.deepEqual([...a.selectedSourceRoles].sort(),['bathymetry','surfaceTexture','terrain']);
    assert.match(row.raw_rgba_sha256,/^[0-9a-f]{64}$/);
    rows.push({frame,rawRGBA_SHA256:row.raw_rgba_sha256,drawPasses:a.drawPasses,glError:d.gpu.glError,
     actualNativeCoverage:a.actualNativeCoverage,combinedOutputTexture:a.combinedOutputTexture,
     cameraBounds:d.camera.bounds,sourceGeometrySha256:d.protection.sourceGeometrySha256});
   }
   assert.deepEqual(errors,[]);return {backend:info.backend,rows};
  }finally{
   await page.evaluate(()=>window.referenceProof?.dispose()).catch(()=>{});await page.close();
   server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));server=null;
  }
 }
 const on=await view({},[0,75,149]),off=await view({surfaceMix:0,reliefStrength:0,depthMix:0},[0]);
 assert.notEqual(on.rows[0].rawRGBA_SHA256,off.rows[0].rawRGBA_SHA256,'ASTRA_MATERIAL_MUST_CHANGE_ACTUAL_SOFTWARE_FRAME');
 assert.deepEqual(on.rows[0].cameraBounds,off.rows[0].cameraBounds);
 assert.equal(on.rows[0].sourceGeometrySha256,off.rows[0].sourceGeometrySha256);
 await plan.assertSourceUnchanged();
 console.log(JSON.stringify({schema:'ASTRA_ACTUAL_SOFTWARE_RENDER_PROBE_V1',status:'PASS',testOnly:true,
  gpuRenderingVerified:false,gpuExecuted:false,softwareWebGLDrawExecuted:true,physicalNvidiaExecuted:false,
  actualMaterialFactorySelected:true,actualShaderCompile:true,partialSourceCoverage:true,
  softwareBackend:on.backend,frames:on.rows,zeroMixReference:off.rows[0],actualSoftwareABPixelsDiffer:true,
  cameraAndGeometryEqual:true,originalSourcesUnchanged:true,profileId:prepared.profileId,
  artifactBytes:prepared.artifactBytes,activationSha256:prepared.activationSha256,
  bundleManifestSha256:prepared.bundleManifestSha256,videoQualityApproved:false,
  publicProofGenerated:false,productionRenderAllowed:false}));
}catch(error){
 console.error('ASTRA_SOFTWARE_PROBE_ERROR',String(error.stack??error.message).slice(0,12000));
 console.log(JSON.stringify({schema:'ASTRA_ACTUAL_SOFTWARE_RENDER_PROBE_V1',status:'FAIL',testOnly:true,
  gpuRenderingVerified:false,gpuExecuted:false,errorType:error.name,productionRenderAllowed:false}));
 process.exitCode=1;
}finally{
 await browser?.close().catch(()=>{});if(server)server.kill();await rm(root,{recursive:true,force:true});
}
