/** Independent reference expression lane over the unchanged Quality F plan. */
import assert from 'node:assert/strict';
import {readFile,lstat,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadQualityRuntimePlan,engine,repo,sha,readAdmission,assertHardwareBackend}
 from '../visual-quality-upgrade-v1/quality_runtime.mjs';
import {referenceV2Profile,REFERENCE_PROFILE_FAMILY} from './ref2_profiles.mjs';
import {selectReferenceUnitScale} from './unit-size-profile.mjs';
import {selectReferenceCamera} from './camera-profile.mjs';
export {engine,repo,sha,readAdmission,assertHardwareBackend};
export {assertQualityDiagnostic,movieName,json} from '../astra-gpu-activation-v1/astra_runtime.mjs';
export const root=path.dirname(fileURLToPath(import.meta.url));
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value),
 canonicalName=value=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/.test(value)&&!value.includes('..');
async function sourceBytes(file){
 assert.ok(path.isAbsolute(file)&&path.resolve(file)===file,'REFERENCE_CANONICAL_SOURCE_REQUIRED');
 let current=path.parse(file).root;
 for(const part of file.slice(current.length).split(path.sep)){
  current=path.join(current,part);assert.ok(!(await lstat(current)).isSymbolicLink(),'REFERENCE_SOURCE_SYMLINK_FORBIDDEN');
 }
 const attributes=await lstat(file);assert.ok(attributes.isFile()&&attributes.size<=8*1024*1024,'REFERENCE_BOUNDED_REGULAR_SOURCE_REQUIRED');
 const raw=await readFile(file),after=await lstat(file);
 assert.ok(raw.length===attributes.size&&after.ino===attributes.ino&&after.dev===attributes.dev
  &&after.mtimeMs===attributes.mtimeMs&&after.size===attributes.size,'REFERENCE_SOURCE_CHANGED_WHILE_READING');return raw;
}

export function validateReferenceRuntimeManifest(manifest){
 assert.equal(manifest?.schema,'WORLD_ENGINE_REFERENCE_VISUAL_FILES_V2');assert.equal(manifest.family,REFERENCE_PROFILE_FAMILY);
 assert.equal(manifest.profileId,REFERENCE_PROFILE_FAMILY,'REFERENCE_MANIFEST_PROFILE_FAMILY_REQUIRED');
 assert.ok(manifest.files&&typeof manifest.files==='object'&&!Array.isArray(manifest.files),'REFERENCE_RUNTIME_MANIFEST_REQUIRED');
 assert.ok(Object.keys(manifest.files).length>0&&Object.keys(manifest.files).length<=128,'REFERENCE_RUNTIME_CLOSURE_LIMIT');
 const tools=manifest.testFiles??{};assert.ok(tools&&typeof tools==='object'&&!Array.isArray(tools)
  &&Object.keys(tools).length<=16,'REFERENCE_TEST_CLOSURE_LIMIT');
 for(const [name,expected]of [...Object.entries(manifest.files),...Object.entries(tools)])
  assert.ok(canonicalName(name)&&hex(expected),'REFERENCE_FLAT_SOURCE_SHA_REQUIRED');
 for(const name of Object.keys(tools))assert.ok(!Object.hasOwn(manifest.files,name),'REFERENCE_TEST_RUNTIME_OVERLAP_FORBIDDEN');
 for(const name of ['ref2_runtime.mjs','ref2_adapter.mjs','serve_ref2.py','ref2_profiles.mjs','gain_territory.mjs','gain_style_core.mjs',
  'reference_source_material.mjs','source_grade_core.mjs','source_grade_pass.mjs','native_domain_coverage.mjs',
  'frontier_ref2.mjs','frontier_profile_core.mjs','coverage_outer_glow.mjs','unit-size-profile.mjs','camera-profile.mjs'])
  assert.ok(Object.hasOwn(manifest.files,name),'REFERENCE_SELECTED_RUNTIME_CLOSURE_REQUIRED '+name);
 return manifest;
}

/** Pure assembly keeps E and F camera keys identical by validating their one
 * candidate against the enlarged units before either variant is assembled. */
export function deriveReferenceScene({baseScene,cameraInput,normalized}={}){
 const unitCandidate=selectReferenceUnitScale({...cameraInput,scenePlan:baseScene,profile:{...normalized.units,enabled:true}}),
  cameraCandidate=selectReferenceCamera({...cameraInput,scenePlan:unitCandidate.scenePlan,profile:{...normalized.camera,enabled:true}}),
  actualScene=structuredClone(baseScene);
 if(normalized.units.enabled)actualScene.combatProfile.units=structuredClone(unitCandidate.scenePlan.combatProfile.units);
 if(normalized.camera.enabled)actualScene.cameraKeyframes=structuredClone(cameraCandidate.scenePlan.cameraKeyframes);
 return {unitCandidate,cameraCandidate,actualScene};
}

export function assertReferenceProductionPlan(plan){
 assert.equal(plan.referenceV2.variant,'F','REFERENCE_ONLY_INTEGRATED_F_CAN_ENTER_PRODUCTION');
 assert.equal(plan.profile.profileId,'REFERENCE_VISUAL_MASTER_V2_F','REFERENCE_EXACT_PRODUCTION_PROFILE_REQUIRED');
 assert.equal(plan.serverConfig.runtimeConfig.testOnlySoftwareProbe,false,'REFERENCE_SOFTWARE_PROBE_FORBIDDEN_IN_PRODUCTION');
 assert.equal(plan.referenceV2.testOnly,false,'REFERENCE_TEST_PLAN_FORBIDDEN_IN_PRODUCTION');return plan;
}

/** CPU-only source/profile construction. Original F is derived only by the
 * inherited plan once; the new camera selector never invokes that planner. */
export async function loadReferenceRuntimePlan(options={}){
 const base=await loadQualityRuntimePlan(options);
 assert.equal(base.profile.quality?.profile,'F','REFERENCE_BASE_QUALITY_F_REQUIRED');
 const requested=base.profile.referenceV2??{},normalized=referenceV2Profile(requested.variant??'A',requested.parameters??{}),
  baseScene=base.scenePlan,baseSceneSha256=sha(Buffer.from(JSON.stringify(baseScene))),
  cameraInput={baseCameraPlan:JSON.parse(await readFile(path.join(engine,base.fixture.nativeFiles.cameraPlan))),
   currentNativeFrame:base.fixture.currentNativeFrame,
   safeArea:JSON.parse(await readFile(path.join(engine,base.fixture.nativeFiles.regionalPlan))).layout.safe,
   inheritedNativeBounds:base.serverConfig.runtimeConfig.bootstrap.admittedNativeFraming.bounds},
  {unitCandidate,cameraCandidate,actualScene}=deriveReferenceScene({baseScene,cameraInput,normalized});
 const actualSceneSha256=sha(Buffer.from(JSON.stringify(actualScene))),
  cameraKeyframeSha256=sha(Buffer.from(JSON.stringify(actualScene.cameraKeyframes))),
  candidateCameraSceneSha256=sha(Buffer.from(JSON.stringify(cameraCandidate.scenePlan))),
  candidateCameraKeyframeSha256=sha(Buffer.from(JSON.stringify(cameraCandidate.scenePlan.cameraKeyframes))),
  profileSha256=sha(Buffer.from(JSON.stringify({normalized,baseSceneSha256,actualSceneSha256,candidateCameraSceneSha256}))),
  referenceV2={...normalized,family:REFERENCE_PROFILE_FAMILY,profileSha256,baseSceneSha256,actualSceneSha256,
   cameraSceneSha256:actualSceneSha256,cameraKeyframeSha256,candidateCameraSceneSha256,candidateCameraKeyframeSha256,
   cameraChanged:normalized.camera.enabled&&cameraCandidate.changed,unitSizeChanged:normalized.units.enabled&&unitCandidate.changed,
   cameraAudit:{candidate:cameraCandidate.audit,actualApplied:normalized.camera.enabled,
    interpretation:normalized.camera.enabled?'ACTUAL_CANDIDATE_CAMERA':'BASELINE_F_CAMERA_CANDIDATE_NOT_APPLIED'},
   unitAudit:{candidate:unitCandidate.audit,actualApplied:normalized.units.enabled,
    actualScale:normalized.units.enabled?unitCandidate.audit.selectedScale:1,cameraSafetyScale:unitCandidate.audit.selectedScale},
   actualSceneBinding:'NEW_SCENE_CAMERA_AND_OPTIONAL_STATIC_UNIT_SIZE_ONLY',testOnly:false,gpuVisualQualityVerified:false};
 const config=structuredClone(base.serverConfig),baseQualityMetadata=structuredClone(config.runtimeConfig.quality);
 config.runtimeConfig.bootstrap.scenePlan=actualScene;config.runtimeConfig.referenceV2=referenceV2;
 config.runtimeConfig.quality={...baseQualityMetadata,profileSha256,cameraSceneSha256:actualSceneSha256,
  cameraChanged:referenceV2.cameraChanged,frontierChanged:normalized.frontier.enabled,
  screenFeatherPixels:normalized.source.enabled?normalized.source.screenFeatherPixels:baseQualityMetadata.screenFeatherPixels,
  cameraAudit:referenceV2.cameraAudit,baseCameraAudit:baseQualityMetadata.cameraAudit,
  baselineQualityProfile:'F',newReferenceOverrides:true,compositionOrder:normalized.compositionOrder};
 const manifestFile=path.join(root,'REFERENCE_FILES.json'),manifestBytes=await sourceBytes(manifestFile),
  manifest=JSON.parse(manifestBytes),manifestSha256=sha(manifestBytes);
 validateReferenceRuntimeManifest(manifest);
 const sourceBindings=[...base.sourceBindings],records=[];
 async function bind(name,expectedSha=null,testTool=false){
  assert.ok(canonicalName(name),'REFERENCE_FLAT_SOURCE_NAME_REQUIRED');const file=path.join(root,name),raw=await sourceBytes(file);
  if(expectedSha!==null){assert.ok(hex(expectedSha),'REFERENCE_SOURCE_SHA_REQUIRED');assert.equal(sha(raw),expectedSha,'REFERENCE_SOURCE_HASH_MISMATCH '+name);}
  const record={path:path.relative(engine,file).replaceAll(path.sep,'/'),bytes:raw.length,sha256:sha(raw),testTool};
  sourceBindings.push(record);records.push({file,...record});
  if(name.endsWith('.mjs'))config.bindings.push({url:'/reference/'+name,path:file,bytes:raw.length,sha256:record.sha256});
 }
 await bind('REFERENCE_FILES.json',manifestSha256);
 for(const [name,expected]of Object.entries(manifest.files))await bind(name,expected);
 for(const [name,expected]of Object.entries(manifest.testFiles??{})){
  assert.ok(!Object.hasOwn(manifest.files,name),'REFERENCE_TEST_RUNTIME_OVERLAP_FORBIDDEN');await bind(name,expected,true);
 }
 const sourceSignature=sha(Buffer.from(JSON.stringify({parent:base.sourceSignature,profileSha256,manifestSha256,
  actualSceneSha256,cameraKeyframeSha256,sourceBindings}))),assertSourceUnchanged=async()=>{
   await base.assertSourceUnchanged();for(const record of records)
    assert.equal(sha(await sourceBytes(record.file)),record.sha256,'REFERENCE_BOUND_SOURCE_CHANGED '+record.path);return true;};
 return {...base,scenePlan:actualScene,originalScenePlan:baseScene,sourceBindings,sourceSignature,assertSourceUnchanged,
  serverConfig:config,referenceV2,profileId:base.profile.profileId,manifestSha256,
  actualSceneSha256,cameraKeyframeSha256,baseQualityMetadata};
}
export const loadAstraRuntimePlan=loadReferenceRuntimePlan;
export const loadRef2RuntimePlan=loadReferenceRuntimePlan;

/** Process orchestration is separate; GPU admission and every rendering core remain original. */
export async function openReferenceRuntime({admissionFile=process.env.RTX_GPU_ADMISSION_FILE,onPendingCleanup=null,...options}={}){
 const plan=await loadReferenceRuntimePlan(options);
 assertReferenceProductionPlan(plan);
 const admission=await readAdmission(admissionFile),require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
 assert.equal(process.version,'v24.19.0');assert.equal(require('playwright/package.json').version,'1.62.1');
 const temporary=await mkdtemp(path.join(tmpdir(),'world-engine-reference-http-')),
  configFile=path.join(temporary,'CONFIG.json'),raw=Buffer.from(JSON.stringify(plan.serverConfig));
 await writeFile(configFile,raw,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(root,'serve_ref2.py'),'--config',configFile,
  '--expected-config-sha256',sha(raw)],{cwd:repo,stdio:['ignore','pipe','pipe']});
 let browser,browserStarting,aborted=false,closed=false,stderr='';
 const cleanup=async()=>{server.kill();await(browser??await browserStarting?.catch(()=>null))?.close().catch(()=>{});await rm(temporary,{recursive:true,force:true});};
 onPendingCleanup?.(async()=>{aborted=true;await cleanup();});
 server.stderr.on('data',value=>{stderr=(stderr+value).slice(-4096);});
 try{
  const origin=await new Promise((resolve,reject)=>{
   const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>{lines.close();reject(Error('REFERENCE_LOOPBACK_TIMEOUT '+stderr));},10000);
   lines.once('line',line=>{clearTimeout(timer);lines.close();try{const data=JSON.parse(line),url=new URL(data.url);
    assert.ok(data.event==='READY'&&url.protocol==='http:'&&url.hostname==='127.0.0.1','REFERENCE_LOOPBACK_REQUIRED');resolve(url.origin);
   }catch(error){reject(error);}});
   for(const event of ['error','exit'])server.once(event,value=>{clearTimeout(timer);lines.close();reject(Error('REFERENCE_SERVER_'+event+' '+String(value)+' '+stderr));});
  });
  if(aborted)throw Error('REFERENCE_RUNTIME_ABORTED');
  browserStarting=require('playwright').chromium.launch({executablePath:path.join(engine,'deployment/gcube/chromium_wrapper.py'),
   headless:true,ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox']});
  browser=await browserStarting;if(aborted)throw Error('REFERENCE_RUNTIME_ABORTED');
  assert.equal(browser.version(),admission.probe.browser_version,'SAME_ADMITTED_BROWSER_REQUIRED');
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)errors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>Object.hasOwn(window,'referenceV2Boot'),null,{timeout:240000});
  const info=await page.evaluate(()=>window.referenceV2Boot);assertHardwareBackend(info.backend,admission);
  assert.equal(info.testOnly,false);assert.equal(info.referenceV2.testOnly,false);assert.equal(info.referenceV2.variant,'F');
  assert.equal(info.referenceV2.profileSha256,plan.referenceV2.profileSha256);
  assert.equal(info.referenceV2.actualSceneSha256,plan.actualSceneSha256);
  assert.equal(info.referenceV2.cameraKeyframeSha256,plan.cameraKeyframeSha256);
  assert.equal(info.cameraKeyframeBinding,JSON.stringify(plan.scenePlan.cameraKeyframes),'REFERENCE_ACTUAL_CAMERA_KEYS_REQUIRED');
  assert.equal(info.astra.activationSha256,plan.activationSha256);assert.equal(info.astra.bundleManifestSha256,plan.bundleManifestSha256);
  for(const [flag,record] of Object.entries(plan.serverConfig.runtimeConfig.inputs))
   assert.equal(info.runtimeConfig.inputs[flag]?.sha256,record.sha256,'REFERENCE_ACTUAL_INPUT_HASH_MISMATCH_'+flag);
  if(errors.length)throw Error(errors[0]);await plan.assertSourceUnchanged();
  return {...plan,page,errors,info,admission,async close(){if(closed)return;closed=true;let failure;
   try{if(!page.isClosed())await page.evaluate(()=>window.referenceProof?.dispose());}catch(error){failure=error;}
   try{await cleanup();}catch(error){failure??=error;}await plan.assertSourceUnchanged();if(failure)throw failure;}};
 }catch(error){await cleanup();throw error;}
}
export const openAstraRuntime=openReferenceRuntime;
export const openRef2Runtime=openReferenceRuntime;
