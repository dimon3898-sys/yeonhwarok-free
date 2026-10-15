/** New visual-profile runtime: reuse original ASTRA closure, browser boot and hardware admission. */
import assert from 'node:assert/strict';
import {readFile,lstat,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadAstraRuntimePlan as loadParentPlan,engine,repo,sha,readAdmission,assertHardwareBackend}
 from '../astra-gpu-activation-v1/astra_runtime.mjs';
import {qualityProfile,selectQualityCamera} from './quality_profiles.mjs';
export {engine,repo,sha,readAdmission,assertHardwareBackend};
export {assertQualityDiagnostic,movieName,json} from '../astra-gpu-activation-v1/astra_runtime.mjs';
export const root=path.dirname(fileURLToPath(import.meta.url));
const closure=['quality_runtime.mjs','quality_adapter.mjs','quality_profiles.mjs','serve_quality.py',
 'quality_material.mjs','quality_material_core.mjs','distance_support.mjs','support_gpu.mjs',
 'quality_territory.mjs','territory_style_core.mjs','QUALITY_FILES.json'];
const bytes=async file=>{const stat=await lstat(file);assert.ok(stat.isFile()&&!stat.isSymbolicLink()&&stat.size<=4*1024*1024,'QUALITY_REGULAR_BOUND_SOURCE_REQUIRED');return readFile(file);};

/** CPU-only. A..F are inspection variants; only F can enter production GPU capture. */
export async function loadQualityRuntimePlan(options={}){
 const parent=await loadParentPlan(options),profile=qualityProfile(parent.profile.quality?.profile),
  config=structuredClone(parent.serverConfig),scene=parent.scenePlan,
  baseCamera=JSON.parse(await readFile(path.join(engine,parent.fixture.nativeFiles.cameraPlan))),
  regional=JSON.parse(await readFile(path.join(engine,parent.fixture.nativeFiles.regionalPlan))),
  camera=selectQualityCamera({scenePlan:scene,baseCameraPlan:baseCamera,currentNativeFrame:parent.fixture.currentNativeFrame,
   safeArea:regional.layout.safe,inheritedNativeBounds:config.runtimeConfig.bootstrap.admittedNativeFraming.bounds}),
  derivedScene=profile.camera?camera.scenePlan:structuredClone(scene),
  cameraSceneSha256=sha(Buffer.from(JSON.stringify(derivedScene))),
  profileSha256=sha(Buffer.from(JSON.stringify({profile,scene:cameraSceneSha256}))),
  quality={...profile,profileSha256,cameraSceneSha256,cameraChanged:profile.camera&&camera.changed,
   cameraAudit:camera,qualityApproved:false,scope:'EXPLICIT_NEW_SCENE_VISUAL_EXTENSION_ORIGINAL_SOURCES_UNCHANGED',
   compositionOrder:['NATIVE_CAMERA_GIS_COVERAGE','UNCHANGED_BASE_MATERIAL','SOURCE_SUPPORTED_ASTRA',
    'TERRITORY_OWNERSHIP','ACTUAL_TERRAIN_LIGHTING_AND_REAL_FRONTIER','COHERENT_PRESENTATION','ORIGINAL_NATIONAL_UNITS']};
 config.runtimeConfig.bootstrap.scenePlan=derivedScene;config.runtimeConfig.quality=quality;
 const sourceBindings=[...parent.sourceBindings],extra=[];
 for(const name of closure){const file=path.join(root,name),raw=await bytes(file),record={
  path:path.relative(engine,file).replaceAll(path.sep,'/'),bytes:raw.length,sha256:sha(raw)};
  sourceBindings.push(record);extra.push({file,...record});
  if(name.endsWith('.mjs'))config.bindings.push({url:'/quality/'+name,path:file,bytes:raw.length,sha256:record.sha256});
 }
 // A pinned test tool may be served for explicit software probes. It is never
 // imported by either production bootstrap or the rendering/capture engines.
 const manifest=JSON.parse(await bytes(path.join(root,'QUALITY_FILES.json'))),tool='support_ab_probe.mjs',
  expectedToolSha=manifest.testFiles?.[tool];
 assert.match(expectedToolSha??'',/^[a-f0-9]{64}$/,'QUALITY_PINNED_TEST_TOOL_REQUIRED');
 const toolFile=path.join(root,tool),toolBytes=await bytes(toolFile),toolRecord={
  path:path.relative(engine,toolFile).replaceAll(path.sep,'/'),bytes:toolBytes.length,sha256:sha(toolBytes)};
 assert.equal(toolRecord.sha256,expectedToolSha,'QUALITY_TEST_TOOL_HASH_MISMATCH');
 sourceBindings.push(toolRecord);extra.push({file:toolFile,...toolRecord});
 config.bindings.push({url:'/quality/'+tool,path:toolFile,bytes:toolBytes.length,sha256:toolRecord.sha256});
 const sourceSignature=sha(Buffer.from(JSON.stringify({parent:parent.sourceSignature,profileSha256,
  cameraSceneSha256,sourceBindings}))),assertSourceUnchanged=async()=>{
   await parent.assertSourceUnchanged();for(const record of extra)
    assert.equal(sha(await bytes(record.file)),record.sha256,'QUALITY_BOUND_SOURCE_CHANGED '+record.path);return true;};
 return {...parent,scenePlan:derivedScene,sourceBindings,sourceSignature,assertSourceUnchanged,serverConfig:config,quality,
  originalScenePlan:scene,profileId:parent.profile.profileId,camera};
}
export const loadAstraRuntimePlan=loadQualityRuntimePlan;

/** Separate process orchestration only; original render/encoding engines are not copied. */
export async function openQualityRuntime({admissionFile=process.env.RTX_GPU_ADMISSION_FILE,onPendingCleanup=null,...options}={}){
 const plan=await loadQualityRuntimePlan(options);
 assert.equal(plan.quality.profile,'F','QUALITY_ONLY_INTEGRATED_F_CAN_ENTER_PRODUCTION');
 assert.equal(plan.profile.profileId,'VISUAL_QUALITY_UPGRADE_V1_F','QUALITY_EXACT_PRODUCTION_PROFILE_REQUIRED');
 const admission=await readAdmission(admissionFile),require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
 const temporary=await mkdtemp(path.join(tmpdir(),'world-engine-quality-http-')),
  configFile=path.join(temporary,'CONFIG.json'),raw=Buffer.from(JSON.stringify(plan.serverConfig));
 await writeFile(configFile,raw,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(root,'serve_quality.py'),'--config',configFile,
  '--expected-config-sha256',sha(raw)],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,browserStarting,aborted=false,closed=false,stderr='';
 const cleanup=async()=>{server.kill();await(browser??await browserStarting?.catch(()=>null))?.close().catch(()=>{});await rm(temporary,{recursive:true,force:true});};
 onPendingCleanup?.(async()=>{aborted=true;await cleanup();});
 server.stderr.on('data',value=>{stderr=(stderr+value).slice(-4096);});
 try{
  const origin=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('QUALITY_LOOPBACK_TIMEOUT '+stderr));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{const data=JSON.parse(line),url=new URL(data.url);
    assert.ok(data.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1','QUALITY_LOOPBACK_REQUIRED');resolve(url.origin);
   }catch(error){reject(error);}});
   for(const event of ['error','exit'])server.once(event,value=>{clearTimeout(timer);lines.close();reject(Error('QUALITY_SERVER_'+event+' '+String(value)+' '+stderr));});
  });
  if(aborted)throw Error('QUALITY_RUNTIME_ABORTED');
  browserStarting=require('playwright').chromium.launch({executablePath:path.join(engine,'deployment/gcube/chromium_wrapper.py'),
   headless:true,ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox']});
  browser=await browserStarting;if(aborted)throw Error('QUALITY_RUNTIME_ABORTED');
  assert.equal(browser.version(),admission.probe.browser_version,'SAME_ADMITTED_BROWSER_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>Object.hasOwn(window,'qualityBoot'),null,{timeout:240000});
  const info=await page.evaluate(()=>window.qualityBoot);assertHardwareBackend(info.backend,admission);
  assert.equal(info.testOnly,false);assert.equal(info.quality.profile,'F');assert.equal(info.quality.profileSha256,plan.quality.profileSha256);
  assert.equal(info.quality.cameraSceneSha256,plan.quality.cameraSceneSha256);
  assert.equal(info.astra.activationSha256,plan.activationSha256);assert.equal(info.astra.bundleManifestSha256,plan.bundleManifestSha256);
  for(const [flag,record] of Object.entries(plan.serverConfig.runtimeConfig.inputs))
   assert.equal(info.runtimeConfig.inputs[flag]?.sha256,record.sha256,'QUALITY_ACTUAL_INPUT_HASH_MISMATCH_'+flag);
  if(errors.length)throw Error(errors[0]);await plan.assertSourceUnchanged();
  return {...plan,page,errors,info,admission,async close(){if(closed)return;closed=true;let failure;
   try{if(!page.isClosed())await page.evaluate(()=>window.referenceProof?.dispose());}catch(error){failure=error;}
   try{await cleanup();}catch(error){failure??=error;}await plan.assertSourceUnchanged();if(failure)throw failure;}};
 }catch(error){await cleanup();throw error;}
}
export const openAstraRuntime=openQualityRuntime;
