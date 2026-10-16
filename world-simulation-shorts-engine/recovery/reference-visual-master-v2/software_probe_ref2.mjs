/** Actual software WebGL2 reference-expression comparisons; never NVIDIA or video-quality admission. */
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,lstat,rm,open} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir,userInfo} from 'node:os';
import path from 'node:path';
import {loadReferenceRuntimePlan,sha,repo,engine} from './ref2_runtime.mjs';
import {captureSoftwareFrame,sourceEdgeSamples} from '../visual-quality-upgrade-v1/software_probe.mjs';
import {assertQualityDiagnostic} from '../rtx-gpu-package-v1/hardware_runtime.mjs';
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
export const evidenceNames=['A_075.png','B_075.png','C_075.png','D_075.png','E_075.png',
 'F_000.png','F_038.png','F_075.png','F_112.png','F_149.png'];

/** Browser-serialized unit-only ablation. Bounds locate pixels; dimensions are
 * measured from the actual on/off RGB difference, not copied from those bounds. */
export async function measureUnitPixels({frame,width=1080,height=1920}){
 const pipeline=window.referenceProof.pipeline,before=pipeline.readPixels().slice(),
  full=structuredClone(pipeline.diagnostic),units=full.units.units;
 const without=await window.referenceProof.capture(frame,{png:false,combatEnabled:false}),after=pipeline.readPixels();
 if(JSON.stringify(full.camera)!==JSON.stringify(without.diagnostic.camera))throw Error('REFERENCE_UNIT_ABLATION_CAMERA_CHANGED');
 if(full.frame!==frame||without.diagnostic.frame!==frame||before.length!==width*height*4||after.length!==before.length)
  throw Error('REFERENCE_UNIT_ABLATION_FRAME_MISMATCH');
 const overlap=(a,b)=>a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1];
 if(units.some((unit,i)=>units.slice(i+1).some(other=>overlap(unit.bounds,other.bounds))))
  return {status:'SKIP',reason:'AMBIGUOUS_PROJECTED_UNIT_RECT_OVERLAP',testOnly:true,actualReadPixelsCompared:true,
   physicalNvidiaExecuted:false,renderedPixelWidthClaimed:false};
 const boxes=units.map(unit=>({id:unit.id,profileId:unit.profile_id,sizePx:unit.size_px,box:unit.bounds,
  minX:Infinity,minY:Infinity,maxX:-Infinity,maxY:-Infinity,pixels:0}));
 let outsideChanged=0;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const index=((height-1-y)*width+x)*4;
  if(Math.max(Math.abs(before[index]-after[index]),Math.abs(before[index+1]-after[index+1]),
    Math.abs(before[index+2]-after[index+2]))<=2)continue;
  const unit=boxes.find(item=>x+.5>=item.box[0]&&x+.5<=item.box[2]&&y+.5>=item.box[1]&&y+.5<=item.box[3]);
  if(!unit){outsideChanged++;continue;}unit.pixels++;unit.minX=Math.min(unit.minX,x);unit.minY=Math.min(unit.minY,y);
  unit.maxX=Math.max(unit.maxX,x);unit.maxY=Math.max(unit.maxY,y);
 }
 if(outsideChanged)throw Error('REFERENCE_UNIT_ABLATION_CHANGED_OUTSIDE_UNITS');
 if(boxes.some(unit=>unit.pixels===0))throw Error('REFERENCE_UNIT_ABLATION_VISIBLE_PIXELS_REQUIRED');
 return {status:'PASS',testOnly:true,actualReadPixelsCompared:true,physicalNvidiaExecuted:false,
  renderedPixelWidthClaimed:true,thresholdPerChannel:2,changedPixelsOutsideUnitBounds:outsideChanged,
  units:boxes.map(unit=>({id:unit.id,profileId:unit.profileId,nominalSizePx:unit.sizePx,changedPixelCount:unit.pixels,
   measuredRGBDifferenceBounds:[unit.minX,unit.minY,unit.maxX+1,unit.maxY+1],
   actualVisibleDifferenceWidth:unit.maxX-unit.minX+1,actualVisibleDifferenceHeight:unit.maxY-unit.minY+1})),
  artworkRedesigned:false,anchorsMoved:false,mobileReadabilityApproved:false};
}
async function start(config,filename){
 const bytes=Buffer.from(JSON.stringify(config));await writeFile(filename,bytes,{flag:'wx',mode:0o600});
 const server=spawn('/usr/bin/python3',['-B',path.join(here,'serve_ref2.py'),'--config',filename,
  '--expected-config-sha256',sha(bytes)],{cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';
 server.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-4096);});
 const origin=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('REFERENCE_SW_SERVER_TIMEOUT'));},10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const item=JSON.parse(line),url=new URL(item.url);
   assert.equal(item.event,'READY');assert.equal(url.hostname,'127.0.0.1');assert.equal(url.protocol,'http:');resolve(url.origin);
  }catch(error){reject(error);}});
  server.once('error',error=>{clearTimeout(timer);lines.close();reject(error);});
  server.once('exit',code=>{clearTimeout(timer);lines.close();reject(Error('REFERENCE_SW_SERVER_EXIT_'+code+' '+stderr));});
 });return {server,origin};
}
function assertRow(row,frame,variant){
 assertQualityDiagnostic(row.diagnostic,{frame});const a=row.diagnostic.terrain.astra;
 assert.equal(a.testOnly,true);assert.equal(a.actualMaterialFactorySelected,true);assert.equal(a.actualNativeCoverage,true);
 assert.equal(a.sourceMaterialBeforeTerritory,true);assert.equal(a.gpuUploadExecuted,true);
 assert.equal(row.diagnostic.referenceV2.variant,variant);assert.equal(row.diagnostic.referenceV2.testOnly,true);
 assert.equal(row.actualReadPixelsExecuted,true);assert.match(row.raw_rgba_sha256,/^[a-f0-9]{64}$/);
 if(['B','F'].includes(variant))assert.equal(row.diagnostic.territory.graphics.gainTerritory.actualFactorySelected,true);
 if(['C','F'].includes(variant)){assert.equal(row.diagnostic.terrain.sourceGrade.gradeDraws,1);
  assert.equal(row.diagnostic.terrain.sourceGrade.sourceMaterialBeforeTerritory,true);}
 if(['D','F'].includes(variant))assert.equal(row.diagnostic.frontierLight.outerDomainGold.version,'REFERENCE_NATIVE_DOMAIN_OUTER_GOLD_V2');
}
export async function runReferenceSoftwareProbe(){
 const temporary=await mkdtemp(path.join(tmpdir(),'reference-v2-software-')),
  require=createRequire(path.join(repo,'cinematic-world-map/package.json')),
  baseline=JSON.parse(await readFile(path.join(here,'PROTECTED_BASELINE.json'))),cases={},files=[];
 let browser,activeServer,totalPngBytes=0,tools;
 try{
  const prepared=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'prepare_ref2.py'),
   '--prepare-activation','--private-root',temporary,'--variant','F'],{timeout:120000,maxBuffer:1024*1024})).stdout);
  assert.equal(prepared.profileId,'REFERENCE_VISUAL_MASTER_V2_F');
  const saved=JSON.parse(await readFile(prepared.activationFile)),manifest=path.isAbsolute(saved.bundleManifestFile)?
   saved.bundleManifestFile:path.join(engine,saved.bundleManifestFile),samples=await sourceEdgeSamples(manifest),
   output=process.env.WORLD_ENGINE_REFERENCE_EVIDENCE_DIR;
  if(output){assert.ok(path.isAbsolute(output)&&path.resolve(output)===output,'REFERENCE_EVIDENCE_PATH_REQUIRED');
   await mkdir(output,{recursive:true,mode:0o700});const entry=await lstat(output);assert.ok(entry.isDirectory()&&!entry.isSymbolicLink());}
  browser=await require('playwright').chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),
    XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},ignoreDefaultArgs:['--disable-dev-shm-usage'],
   args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  for(const variant of ['A','B','C','D','E','F']){
   const activation={...saved,profileId:'REFERENCE_VISUAL_MASTER_V2_'+variant,
    referenceV2:{...saved.referenceV2,variant}},raw=Buffer.from(JSON.stringify(activation)+'\n'),
    file=path.join(temporary,'REFERENCE_'+variant+'.json');await writeFile(file,raw,{flag:'wx',mode:0o600});
   const plan=await loadReferenceRuntimePlan({activationFile:file,expectedActivationSha256:sha(raw)}),config=structuredClone(plan.serverConfig);
   config.runtimeConfig.testOnlySoftwareProbe=true;
   let fixture;
   if(variant==='F'){
    fixture=JSON.parse((await execute('/usr/bin/python3',['-B',path.join(here,'build_source_probe.py'),
     '--output',path.join(config.bundleRoot,'reference-source-probe')],{timeout:120000,maxBuffer:1024*1024})).stdout);
    for(const record of fixture.bindings)config.bindings.push({url:'/reference-source-probe/'+record.name,
     path:path.join(fixture.directory,record.name),sha256:record.sha256,bytes:record.bytes});
   }
   const {server,origin}=await start(config,path.join(temporary,'HTTP_'+variant+'.json'));activeServer=server;
   const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
   page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.status()>=400)
    errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
   await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
   try{
    await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
    await page.waitForFunction(()=>Object.hasOwn(window,'referenceV2Boot'),null,{timeout:240000});
    const info=await page.evaluate(()=>window.referenceV2Boot);
    assert.equal(info.testOnly,true);assert.equal(info.productionEligible,false);assert.equal(info.gpuRenderingVerified,false);
    assert.match(info.backend,/SwiftShader/i);assert.equal(info.referenceV2.variant,variant);assert.equal(info.referenceV2.testOnly,true);
    assert.equal(info.cameraMotion.status,'PASS');const rows=[];let unitPixels;
    for(const frame of variant==='F'?[0,38,75,112,149]:variant==='A'?[0,75,149]:[75]){
     const save=variant==='F'||frame===75,row=await page.evaluate(captureSoftwareFrame,{frame,samples,png:save});assertRow(row,frame,variant);
     if(save){
      const name=variant+'_'+String(frame).padStart(3,'0')+'.png';assert.ok(evidenceNames.includes(name));
      const png=Buffer.from(row.png.split(',')[1],'base64');assert.equal(sha(png),row.png_sha256);
      assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1920);
      assert.ok(png.length<=12*1024*1024);totalPngBytes+=png.length;assert.ok(totalPngBytes<=60*1024*1024);
      if(output){const fd=await open(path.join(output,name),'wx',0o644);
       try{await fd.writeFile(png);await fd.chmod(0o644);}finally{await fd.close();}}
      files.push({file:name,sha256:sha(png),bytes:png.length,width:1080,height:1920,scope:'CPU_SW_NOT_NVIDIA'});
     }
     rows.push({frame,rawRGBA_SHA256:row.raw_rgba_sha256,pngSha256:row.png_sha256,metrics:row.metrics,
      camera:{bounds:row.diagnostic.camera.bounds,nativeExpandedBounds:row.diagnostic.camera.nativeExpandedBounds,
       rollDegrees:row.diagnostic.camera.rollDegrees,overscan:row.diagnostic.camera.overscan},
      sourceGeometrySha256:row.diagnostic.protection.sourceGeometrySha256,
      referenceV2:row.diagnostic.referenceV2,glError:row.diagnostic.gpu.glError});
     if(frame===75&&['A','D'].includes(variant))unitPixels=await page.evaluate(measureUnitPixels,{frame});
    }
    if(variant==='F'){
     const sourceOptions={manifestURL:'/reference-source-probe/UPLOAD_BUNDLE.json',expectedManifestSha256:fixture.manifestSHA256,
      fixtureURL:'/reference-source-probe/SOURCE_PROBE.json',expectedFixtureSha256:fixture.fixtureSHA256};
     tools=await page.evaluate(async options=>{
      const gain=await(await import('/reference/gain_ab_probe.mjs')).runGainABProbe(),
       source=await(await import('/reference/source_grade_ab_probe.mjs')).runSourceGradeABProbe(options),
       outer=await(await import('/reference/outer_glow_ab_probe.mjs')).runOuterGlowABProbe();return {gain,source,outer};
     },sourceOptions);
     assert.equal(tools.gain.status,'PASS');assert.equal(tools.gain.productionGainFactorySelected,true);
     assert.equal(tools.source.actualReadPixelsExecuted,true);assert.equal(tools.source.rawValuesMaskCoordinatesUnchanged,true);
     for(const item of Object.values(tools.source.cases))assert.equal(item.result,'PASS');
     assert.equal(tools.outer.status,'PASS');assert.equal(tools.outer.actualReadPixelsCompared,true);
     for(const value of Object.values(tools)){assert.equal(value.testOnly,true);assert.ok(value.videoQualityApproved===false||value.visualQualityApproved===false);
      assert.ok(value.physicalNvidiaExecuted===false||value.nvidiaHardwareVerified===false);}
    }
    assert.deepEqual(errors,[]);await plan.assertSourceUnchanged();
    cases[variant]={variant,backend:info.backend,referenceV2:info.referenceV2,rows,unitPixels};
   }finally{
    await page.evaluate(()=>window.referenceProof?.dispose()).catch(()=>{});await page.close();server.kill();
    await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));activeServer=null;
   }
  }
  const mid=variant=>cases[variant].rows.find(row=>row.frame===75),a=mid('A');
  for(const row of cases.A.rows)assert.equal(row.rawRGBA_SHA256,baseline.softwareRegression.frames[String(row.frame)],
   'REFERENCE_PROTECTED_F_SOFTWARE_PIXEL_REGRESSION_'+row.frame);
  for(const variant of ['B','C','D']){assert.deepEqual(mid(variant).camera,a.camera);
   assert.equal(cases[variant].referenceV2.cameraKeyframeSha256,cases.A.referenceV2.cameraKeyframeSha256);}
  assert.deepEqual(mid('E').camera,mid('F').camera);
  assert.equal(cases.E.referenceV2.cameraKeyframeSha256,cases.F.referenceV2.cameraKeyframeSha256);
  assert.notDeepEqual(mid('E').camera,a.camera);
  for(const variant of ['B','C','D'])assert.notEqual(mid(variant).rawRGBA_SHA256,a.rawRGBA_SHA256,'REFERENCE_VARIANT_PIXELS_MUST_DIFFER_'+variant);
  assert.notEqual(mid('F').rawRGBA_SHA256,mid('E').rawRGBA_SHA256,'REFERENCE_INTEGRATED_MATCHED_CAMERA_PIXELS_MUST_DIFFER');
  for(const value of Object.values(cases))for(const row of value.rows)assert.equal(row.sourceGeometrySha256,a.sourceGeometrySha256);
  assert.deepEqual(files.map(item=>item.file).sort(),[...evidenceNames].sort());
  const sourceEdgeComparison=Object.fromEntries(Object.entries(a.metrics.sourceEdgeJumps).map(([key,before])=>[key,
   {before,after:mid('C').metrics.sourceEdgeJumps[key]??null}]));
  const result={schema:'REFERENCE_V2_ACTUAL_SOFTWARE_PROBE_V1',status:'PASS',testOnly:true,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,gpuExecuted:false,actualShaderCompile:true,
   softwareWebGLDrawExecuted:true,actualReferenceABPixelsDiffer:true,parentSoftwareBaselineBitExact:true,
   cameraAndGeometryEqual:true,cameraComparisonScope:'A_B_C_D_SHARE_OLD_F_AND_E_F_SHARE_CANDIDATE',oldFCameraMatchedABCD:true,candidateCameraMatchedEF:true,originalSourcesUnchanged:true,
   parentBaselineProvenance:baseline.softwareRegression.provenance,sourceEdgeComparison,cases,tools,files,totalPngBytes,
   mainFramesRendered:12,additionalUnitAblationDraws:2,actualNvidiaVideoGenerated:false,
   qualityApproved:false,videoQualityApproved:false,productionRenderAllowed:false};
  console.log(JSON.stringify(result));return result;
 }catch(error){console.error('REFERENCE_SOFTWARE_PROBE_ERROR',String(error.stack??error.message).slice(0,12000));
  console.log(JSON.stringify({schema:'REFERENCE_V2_ACTUAL_SOFTWARE_PROBE_V1',status:'FAIL',testOnly:true,
   physicalNvidiaExecuted:false,gpuRenderingVerified:false,gpuExecuted:false,errorType:error.name,productionRenderAllowed:false}));
  process.exitCode=1;return null;
 }finally{await browser?.close().catch(()=>{});activeServer?.kill();await rm(temporary,{recursive:true,force:true});}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 assert.equal(process.argv.length,2,'REFERENCE_PROBE_NO_ARGUMENTS');await runReferenceSoftwareProbe();
}
