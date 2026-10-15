/** Actual full-resolution SwiftShader A/B pictures. CPU software evidence only. */
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm,mkdir,lstat} from 'node:fs/promises';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
import {loadQualityRuntimePlan,sha,repo,engine} from './quality_runtime.mjs';
import {assertQualityDiagnostic} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
import {supportMaskForRole} from './distance_support.mjs';
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
const baselineSoftware={provenance:'astra-gpu-activation-v1/runs/38810579567-1/build.json/actualImageSoftwareProbe/report',
 backend:'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)',
 frames:{0:'4c14fb68d01ac946ef6c8c285d4436993f14581333e4cafff1f956841affd791',
 75:'f3e51f3b835ff48a6fc52ebed768c4d2a5943b20251a03bfe5673d603d9ad4ab',
 149:'f8603e5d186144f062874b1782cd26fa4c52caf325c1a6d3da303892a11f3c91'}};
export const evidenceNames=['A_075.png','B_075.png','C_075.png','D_075.png','E_075.png','F_000.png','F_075.png','F_149.png'];

/** Native-grid support edges only; no source values, masks or coordinates change. */
export async function sourceEdgeSamples(manifestFile){
 const manifest=JSON.parse(await readFile(manifestFile)),root=path.dirname(manifestFile),samples=[];
 for(const [role,source] of Object.entries(manifest.sources))for(const part of source.parts){
  const [w,h]=part.dimensions,[west,south,east,north]=part.bbox,t=part.transform;
  const valid=new Uint8Array(await readFile(path.join(root,part.valid.file)));
  const raw=await readFile(path.join(root,part.values.file)),buffer=raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),
   values=role==='terrain'?new Float32Array(buffer):role==='bathymetry'?new Int16Array(buffer):new Uint8Array(buffer),
   support=supportMaskForRole(role,w,h,valid,values,{transform:t});
  const supported=i=>support[i]===1;
  const sample=(geo,inside,kind)=>samples.push({role,geo,inside,kind});
  for(let n=0;n<16;n++){
   const u=(n+.5)/16,x=west+(east-west)*u,y=south+(north-south)*u;
   sample([west,y],[west+Math.abs(t[1])*.5,y],'RECTANGLE');sample([east,y],[east-Math.abs(t[1])*.5,y],'RECTANGLE');
   sample([x,south],[x,south+Math.abs(t[5])*.5],'RECTANGLE');sample([x,north],[x,north-Math.abs(t[5])*.5],'RECTANGLE');
  }
  const transitions=[];let transitionCount=0;
  const offer=value=>{transitionCount++;if(transitions.length<128)transitions.push(value);
   else{const index=((Math.imul(transitionCount,2654435761)>>>0)%transitionCount);if(index<128)transitions[index]=value;}};
  for(let j=0;j<h;j++)for(let i=0;i<w-1;i++)if(supported(j*w+i)!==supported(j*w+i+1)){
   const geo=[t[0]+(i+1)*t[1],t[3]+(j+.5)*t[5]],sign=supported(j*w+i)?-1:1;
   offer({role,geo,inside:[geo[0]+sign*t[1]*.5,geo[1]],kind:'VALIDITY_OR_SIGN'});
  }
  for(let j=0;j<h-1;j++)for(let i=0;i<w;i++)if(supported(j*w+i)!==supported((j+1)*w+i)){
   const geo=[t[0]+(i+.5)*t[1],t[3]+(j+1)*t[5]],sign=supported(j*w+i)?-1:1;
   offer({role,geo,inside:[geo[0],geo[1]+sign*t[5]*.5],kind:'VALIDITY_OR_SIGN'});
  }
  samples.push(...transitions);
 }
 return samples;
}

/** Serialized by Playwright; all metrics come from the actual readPixels array. */
export async function captureSoftwareFrame({frame,samples,width=1080,height=1920,png=true}){
 const row=await window.referenceProof.capture(frame,{png}),pipeline=window.referenceProof.pipeline,
  pixels=pipeline.readPixels();
 if(pixels.length!==width*height*4)throw Error('QUALITY_SOFTWARE_PIXEL_LENGTH');
 let sum=0,square=0,saturation=0,brightWarm=0,dark=0,count=0;
 const lum=(r,g,b)=>(.2126*r+.7152*g+.0722*b)/255;
 for(let i=0;i<pixels.length;i+=16){
  const r=pixels[i],g=pixels[i+1],b=pixels[i+2],value=lum(r,g,b),hi=Math.max(r,g,b),lo=Math.min(r,g,b);
  sum+=value;square+=value*value;saturation+=hi?(hi-lo)/hi:0;
  if(r>=190&&g>=130&&b<=150)brightWarm++;if(value<.08)dark++;count++;
 }
 const pixel=(x,y)=>{x=Math.round(x);y=Math.round(y);if(x<0||x>=width||y<0||y>=height)return null;
  const i=((height-1-y)*width+x)*4;return [pixels[i],pixels[i+1],pixels[i+2]];};
 const edges={};
 for(const sample of samples){
  const p=pipeline.project(sample.geo),q=pipeline.project(sample.inside);
  if(!Array.isArray(p)||!Array.isArray(q)||!p.every(Number.isFinite)||!q.every(Number.isFinite))continue;
  const dx=q[0]-p[0],dy=q[1]-p[1],distance=Math.hypot(dx,dy);if(distance<1e-6)continue;
  const nx=dx/distance,ny=dy/distance,key=sample.role+':'+sample.kind;
  for(const radius of [1,2,4]){
   const a=pixel(p[0]+nx*radius,p[1]+ny*radius),b=pixel(p[0]-nx*radius,p[1]-ny*radius);if(!a||!b)continue;
   const name=key+':'+radius,entry=edges[name]??={samples:0,rgbJumpSum:0,luminanceJumpSum:0};
   entry.samples++;entry.rgbJumpSum+=Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2])/(255*Math.sqrt(3));
   entry.luminanceJumpSum+=Math.abs(lum(...a)-lum(...b));
  }
 }
 for(const [key,item]of Object.entries(edges))edges[key]={samples:item.samples,
  meanRGBJump:item.rgbJumpSum/item.samples,meanLuminanceJump:item.luminanceJumpSum/item.samples};
 return {...row,actualReadPixelsExecuted:true,metrics:{sampleCount:count,luminanceMean:sum/count,
  luminanceStdDev:Math.sqrt(Math.max(0,square/count-(sum/count)**2)),saturationMean:saturation/count,
  brightWarmFraction:brightWarm/count,darkFraction:dark/count,sourceEdgeJumps:edges}};
}

function assertRow(row,frame,profile){
 assertQualityDiagnostic(row.diagnostic,{frame});
 const astra=row.diagnostic.terrain.astra;
 assert.equal(astra.testOnly,true);assert.equal(astra.actualMaterialFactorySelected,true);
 assert.equal(astra.sourceMaterialBeforeTerritory,true);assert.equal(astra.actualNativeCoverage,true);
 assert.equal(astra.gpuUploadExecuted,true);assert.equal(row.actualReadPixelsExecuted,true);
 assert.equal(row.diagnostic.qualityActivation.profile,profile);
 assert.match(row.raw_rgba_sha256,/^[a-f0-9]{64}$/);
}
async function startServer(config,filename){
 const bytes=Buffer.from(JSON.stringify(config));await writeFile(filename,bytes,{flag:'wx',mode:0o600});
 const server=spawn('/usr/bin/python3',['-B',path.join(here,'serve_quality.py'),'--config',filename,
  '--expected-config-sha256',sha(bytes)],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let stderr='';server.stderr.on('data',data=>{stderr=(stderr+data).slice(-4096);});
 const origin=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('QUALITY_SOFTWARE_SERVER_TIMEOUT'));},10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const item=JSON.parse(line),url=new URL(item.url);
   assert.equal(item.event,'READY');assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');resolve(url.origin);
  }catch(error){reject(error);}});
  server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
  server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('QUALITY_SOFTWARE_SERVER_EXIT_'+code+' '+stderr));});
 });return {server,origin};
}
export async function runSoftwareProbe(){
 const root=await mkdtemp(path.join(tmpdir(),'quality-software-probe-')),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 let browser,activeServer,supportProbe;const cases={},files=[];
 try{
  const prepared=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'prepare_quality.py'),
   '--prepare-activation','--private-root',root,'--profile','F'],{timeout:120000,maxBuffer:1024*1024})).stdout);
  assert.equal(prepared.profileId,'VISUAL_QUALITY_UPGRADE_V1_F');
  const saved=JSON.parse(await readFile(prepared.activationFile)),manifestFile=path.isAbsolute(saved.bundleManifestFile)?
   saved.bundleManifestFile:path.join(engine,saved.bundleManifestFile),samples=await sourceEdgeSamples(manifestFile);
  assert.ok(samples.length>0,'QUALITY_SOURCE_SUPPORT_SAMPLES_REQUIRED');
  const output=process.env.WORLD_ENGINE_QUALITY_EVIDENCE_DIR;
  if(output){assert.ok(path.isAbsolute(output)&&path.resolve(output)===output,'QUALITY_EVIDENCE_PATH_REQUIRED');
   await mkdir(output,{recursive:true,mode:0o700});assert.ok((await lstat(output)).isDirectory()&&!(await lstat(output)).isSymbolicLink());}
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(root,'chromium-config'),
    XDG_CACHE_HOME:path.join(root,'chromium-cache')},ignoreDefaultArgs:['--disable-dev-shm-usage'],
   args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  let totalBytes=0;
  for(const profile of ['A','B','C','D','E','F']){
   const activation={...saved,profileId:'VISUAL_QUALITY_UPGRADE_V1_'+profile,quality:{...saved.quality,profile}},
    bytes=Buffer.from(JSON.stringify(activation)+'\n'),file=path.join(root,'ACTIVATION_'+profile+'.json');
   await writeFile(file,bytes,{flag:'wx',mode:0o600});
   const plan=await loadQualityRuntimePlan({activationFile:file,expectedActivationSha256:sha(bytes)}),config=structuredClone(plan.serverConfig);
   config.runtimeConfig.testOnlySoftwareProbe=true;
   const {server,origin}=await startServer(config,path.join(root,'CONFIG_'+profile+'.json'));activeServer=server;
   const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
   await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort('blockedbyclient'));
   try{
    await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
    await page.waitForFunction(()=>Object.hasOwn(window,'astraBoot'),null,{timeout:240000});
    const info=await page.evaluate(()=>window.astraBoot);
    assert.equal(info.testOnly,true);assert.equal(info.productionEligible,false);assert.equal(info.gpuRenderingVerified,false);
    assert.match(info.backend,/SwiftShader/i);assert.equal(info.quality.profile,profile);assert.equal(info.cameraMotion.status,'PASS');
    if(profile==='F'){
     supportProbe=await page.evaluate(async()=>{const tool=await import('/quality/support_ab_probe.mjs');return tool.runSupportABProbe();});
     assert.equal(supportProbe.testOnly,true);assert.equal(supportProbe.nvidiaHardwareVerified,false);
     assert.equal(supportProbe.actualReadPixelsExecuted,true);
     assert.deepEqual(supportProbe.roles.map(item=>item.role).sort(),['bathymetry','surfaceTexture','terrain']);
     for(const role of supportProbe.roles)assert.ok(role.oldRGBJump>role.newRGBJump,'QUALITY_ROLE_BOUNDARY_AB_REQUIRED_'+role.role);
    }
    const rows=[];
    for(const frame of ['A','F'].includes(profile)?[0,75,149]:[75]){
     const savePng=profile==='F'||frame===75;
     const row=await page.evaluate(captureSoftwareFrame,{frame,samples,png:savePng});assertRow(row,frame,profile);
     if(savePng){
      const name=profile+'_'+String(frame).padStart(3,'0')+'.png';assert.ok(evidenceNames.includes(name));
      const png=Buffer.from(row.png.split(',')[1],'base64');assert.equal(sha(png),row.png_sha256);
      assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1920);
      assert.ok(png.length<=12*1024*1024,'QUALITY_PNG_BYTE_LIMIT');totalBytes+=png.length;
      assert.ok(totalBytes<=48*1024*1024,'QUALITY_TOTAL_PNG_BYTE_LIMIT');
      if(output)await writeFile(path.join(output,name),png,{flag:'wx',mode:0o644});
      files.push({file:name,sha256:sha(png),bytes:png.length,width:1080,height:1920,scope:'CPU_SW_NOT_NVIDIA'});
     }
     rows.push({frame,rawRGBA_SHA256:row.raw_rgba_sha256,pngSha256:row.png_sha256,metrics:row.metrics,
      camera:{bounds:row.diagnostic.camera.bounds,nativeExpandedBounds:row.diagnostic.camera.nativeExpandedBounds,
       rollDegrees:row.diagnostic.camera.rollDegrees,overscan:row.diagnostic.camera.overscan},
      sourceGeometrySha256:row.diagnostic.protection.sourceGeometrySha256,
      quality:row.diagnostic.qualityActivation,glError:row.diagnostic.gpu.glError});
    }
    assert.deepEqual(errors,[]);await plan.assertSourceUnchanged();
    cases[profile]={profile,backend:info.backend,quality:info.quality,rows};
   }finally{
    await page.evaluate(()=>window.referenceProof?.dispose()).catch(()=>{});await page.close();
    server.kill();await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));activeServer=null;
   }
  }
  const mid=profile=>cases[profile].rows.find(row=>row.frame===75),a=mid('A');
  for(const profile of ['B','C','D']){assert.deepEqual(mid(profile).camera,a.camera);assert.equal(mid(profile).sourceGeometrySha256,a.sourceGeometrySha256);}
  assert.deepEqual(mid('E').camera,mid('F').camera);
  const cameraChanged=cases.E.quality.cameraChanged===true;
  if(cameraChanged)assert.notDeepEqual(mid('E').camera,a.camera);else assert.deepEqual(mid('E').camera,a.camera);
  assert.equal(cases.A.backend,baselineSoftware.backend,'PINNED_SOFTWARE_BACKEND_CHANGED');
  for(const row of cases.A.rows)assert.equal(row.rawRGBA_SHA256,baselineSoftware.frames[row.frame],
   'PARENT_A_SOFTWARE_PIXEL_REGRESSION_FRAME_'+row.frame);
  assert.equal(mid('D').rawRGBA_SHA256,a.rawRGBA_SHA256,'AUDITED_UNCHANGED_FRONTIER_MUST_REMAIN_IDENTICAL');
  assert.notEqual(mid('B').rawRGBA_SHA256,a.rawRGBA_SHA256,'QUALITY_BOUNDARY_AB_PIXELS_MUST_DIFFER');
  assert.notEqual(mid('C').rawRGBA_SHA256,a.rawRGBA_SHA256,'QUALITY_TERRITORY_AB_PIXELS_MUST_DIFFER');
  assert.notEqual(mid('F').rawRGBA_SHA256,mid('E').rawRGBA_SHA256,'QUALITY_INTEGRATED_MATCHED_CAMERA_AB_MUST_DIFFER');
  for(const item of Object.values(cases))for(const row of item.rows)assert.equal(row.sourceGeometrySha256,a.sourceGeometrySha256);
  const edgeComparison=Object.fromEntries(Object.entries(a.metrics.sourceEdgeJumps).map(([key,before])=>[key,
   {before,after:mid('B').metrics.sourceEdgeJumps[key]??null,
    rgbDelta:mid('B').metrics.sourceEdgeJumps[key]?mid('B').metrics.sourceEdgeJumps[key].meanRGBJump-before.meanRGBJump:null}]));
  const report={schema:'QUALITY_ACTUAL_SOFTWARE_PROBE_V1',status:'PASS',testOnly:true,physicalNvidiaExecuted:false,
   gpuRenderingVerified:false,gpuExecuted:false,actualShaderCompile:true,softwareWebGLDrawExecuted:true,
   actualQualityABPixelsDiffer:true,cameraAndGeometryEqual:true,cameraOnlyComparisonSeparate:true,
   candidateCameraMatchedEF:true,cameraChanged,parentSoftwareBaselineBitExact:true,
   parentSoftwareBaselineProvenance:baselineSoftware.provenance,frontierDMatchesA:true,
   originalSourcesUnchanged:true,sourceSupportSamples:samples.length,
   sourceEdgeComparison:edgeComparison,perRoleSupportProbe:supportProbe,actualPerRoleBoundaryAB:true,
   cases,files,totalPngBytes:totalBytes,
   qualityApproved:false,videoQualityApproved:false,publicProofGenerated:false,productionRenderAllowed:false};
  console.log(JSON.stringify(report));return report;
 }catch(error){console.error('QUALITY_SOFTWARE_PROBE_ERROR',String(error.stack??error.message).slice(0,12000));
  console.log(JSON.stringify({schema:'QUALITY_ACTUAL_SOFTWARE_PROBE_V1',status:'FAIL',testOnly:true,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,gpuExecuted:false,errorType:error.name,
   productionRenderAllowed:false}));process.exitCode=1;return null;
 }finally{await browser?.close().catch(()=>{});activeServer?.kill();await rm(root,{recursive:true,force:true});}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 assert.equal(process.argv.length,2,'QUALITY_PROBE_NO_ARGUMENTS');await runSoftwareProbe();
}
