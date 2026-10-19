/** Explicit free SOFTWARE_VALIDATION harness. No production admission, NVIDIA
 * launcher, Studio job, claim, Dropbox mutation, or synthetic map substitution.
 * The preserved serve_long software bootstrap and actual bounded native/ASTRA/
 * Area/V5 consumers draw the supplied frozen 80-second document at global time.
 */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,mkdir,rm,open,lstat} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {tmpdir,userInfo} from 'node:os';
import * as native from '../universal-auto-video-v2/long_runtime.mjs';
import * as production from '../universal-production-v3/long_runtime.mjs';
import * as fronts from '../verified-front-data-v4-recovery/front_runtime.mjs';
import {extendCompletionServerPlan} from '../universal-integration-completion-v2/runtime_binding.mjs';
import {assertCompletionFrame} from '../universal-integration-completion-v2/capture_runtime.mjs';
import {capturePreviewWithRuntime} from './preview_capture.mjs';
const execute=promisify(execFile),HERE=path.dirname(fileURLToPath(import.meta.url));
const {sha,engine,repo,boundedSource}=native,RECOVERY=path.dirname(HERE);
const json=async file=>JSON.parse(await boundedSource(file));
const iso=()=>new Date().toISOString();
function softwarePlaywright(){
 const locations=[path.join(repo,'cinematic-world-map/package.json'),
  '/opt/codex/runtimes/codex-primary-runtime/dependencies/node/package.json'];
 for(const location of locations){try{const require=createRequire(location),module=require('playwright');
  assert.equal(require('playwright/package.json').version,'1.62.1','SOFTWARE_PINNED_PLAYWRIGHT_REQUIRED');return module;
 }catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;}}
 throw Error('SOFTWARE_PLAYWRIGHT_DEPENDENCY_UNAVAILABLE');
}
export function assertSoftwareRuntimeInfo(info){
 assert.equal(info?.testOnly,true,'SOFTWARE_EXPLICIT_TEST_PROVENANCE_REQUIRED');
 assert.equal(info.productionEligible,false,'SOFTWARE_PRODUCTION_INELIGIBLE_REQUIRED');
 assert.equal(info.gpuRenderingVerified,false,'SOFTWARE_MUST_NOT_CLAIM_NVIDIA_REQUIRED');
 assert.match(info.backend,/SwiftShader/i);
 assert.ok(!/\bNVIDIA\b/i.test(info.backend),'SOFTWARE_ONLY_BACKEND_REQUIRED');return true;
}
export async function assertActualSoftwareFrame(captured,frame,plan){
 assert.equal(captured?.diagnostic?.frame,frame,'SOFTWARE_GLOBAL_FRAME_REQUIRED');
 const diagnostic=captured.diagnostic,astra=diagnostic.terrain?.astra;
 assert.equal(astra?.actualMaterialFactorySelected,true,'SOFTWARE_ACTUAL_ASTRA_FACTORY_REQUIRED');
 assert.equal(astra.testOnly,true,'SOFTWARE_ASTRA_TEST_ONLY_REQUIRED');
 assert.equal(astra.gpuUploadExecuted,true,'SOFTWARE_ACTUAL_UPLOAD_REQUIRED');
 assert.equal(diagnostic.sourceIntegrity?.sourceBeforeAreaAndFront,true,'SOFTWARE_SOURCE_COMPOSITION_ORDER_REQUIRED');
 assert.equal(diagnostic.sourceIntegrity?.fictional65422SceneUsed,false,'SOFTWARE_ACTUAL_FROZEN_80S_REQUIRED');
 assert.equal(diagnostic.glError,0,'SOFTWARE_GL_ERROR');
 if(plan.overnightRequest){
  const authority=await import('./capture_runtime.mjs');await authority.assertOvernightFrame(captured,plan);
 }else await assertCompletionFrame(captured,plan);
 return captured;
}
async function manifest(directory,name){
 const file=path.join(directory,name),raw=await boundedSource(file,64*1024*1024),object=JSON.parse(raw),records=[];
 for(const [name,expected]of Object.entries({...object.files,...object.testFiles})){
  assert.ok(!path.isAbsolute(name)&&name.split('/').every(p=>p&&p!=='.'&&p!=='..')&&!/[\\\0]/.test(name));
  const file=path.join(directory,name),bytes=await boundedSource(file,128*1024*1024);
  assert.equal(sha(bytes),expected,'SOFTWARE_PRESERVED_SOURCE_SHA_MISMATCH_'+name);
  records.push({name,file,bytes:bytes.length,sha256:expected});
 }
 return{object,records,sha256:sha(raw),file};
}
/** Pure source assembly only: production openLongRuntime/readAdmission is never
 * called. Every source selected below is byte-checked against its old manifest.
 */
export async function loadSoftwarePreviewPlan({planFile,expectedPlanSha256,sceneId,activationFile,expectedActivationSha256,
 submissionFile=path.join(RECOVERY,'universal-integration-completion-v2/fixtures/VALIDATED_80S_SUBMISSION.json')}={}){
 const inherited=await native.loadLongRuntimePlan({planFile,expectedPlanSha256,sceneId,activationFile,expectedActivationSha256}),
  pm=await manifest(path.join(RECOVERY,'universal-production-v3'),'PRODUCTION_FILES.json');
 const browserRecords=Object.entries(production.BROWSER_BINDINGS).map(([url,name])=>{
  const record=pm.records.find(row=>row.name===name);assert.ok(record);return{url,path:record.file,bytes:record.bytes,sha256:record.sha256};});
 const p=production.extendProductionServerPlan(inherited,{manifestSha256:pm.sha256,browserRecords,sourceRecords:pm.records}),
  fm=await manifest(path.join(RECOVERY,'verified-front-data-v4-recovery'),'FRONT_FILES.json'),
  profile=await json(path.join(RECOVERY,'verified-front-data-v4-recovery/FRONT_PROFILE.json')),
  profileRecord=fm.records.find(row=>row.name==='FRONT_PROFILE.json');
 fronts.validateFrontManifest(fm.object);
 const f=fronts.extendFrontServerPlan(p,{profile,profileRecord,manifestSha256:fm.sha256,records:fm.records});
 f.frontExecutionBinding=fronts.validateFrontPlanBinding(f.document,f.frontIntegrity,{testOnlySoftwareProbe:true});
 const previous=await manifest(path.join(RECOVERY,'universal-integration-v1'),'INTEGRATION_FILES.json'),
  own=await manifest(path.join(RECOVERY,'universal-integration-completion-v2'),'COMPLETION_FILES.json'),
  submission=await json(submissionFile),sourceCatalog=await json(path.join(RECOVERY,'universal-integration-completion-v2/SOURCE_DATA_CATALOG.json'));
 assert.equal(own.object.previousManifestSHA256,previous.sha256,'SOFTWARE_COMPLETION_PARENT_MANIFEST_REQUIRED');
 assert.deepEqual(submission.videoPlan,f.document,'SOFTWARE_FROZEN_80S_SCENE_REQUIRED');
 const completed=extendCompletionServerPlan(f,{visualProfile:submission.integration.visualProfile,completion:submission.completionV2,
  previousRecords:previous.records,previousManifestSha256:previous.sha256,records:own.records,manifestSha256:own.sha256,
  sourceCatalog,plan:f.document,frontProfile:f.frontProfile});
 const checked=[...pm.records,...fm.records,...previous.records,...own.records],parentCheck=inherited.assertSourceUnchanged;
 completed.assertSourceUnchanged=async()=>{await parentCheck();for(const row of checked)
  assert.equal(sha(await boundedSource(row.file,128*1024*1024)),row.sha256,'SOFTWARE_SOURCE_CHANGED_AFTER_BOOT');return true;};
 completed.serverConfig.runtimeConfig.testOnlySoftwareProbe=true;
 completed.softwareValidation={schema:'WORLD_ENGINE_FREE_SOFTWARE_VALIDATION_V3',testOnly:true,
  nvidiaHardwareVerified:false,productionRenderAllowed:false,original80sDocumentUnchanged:true,
  parentSourceManifestSHA256:own.sha256,originalSceneSHA256:expectedPlanSha256};
 return completed;
}
export async function loadOvernightSoftwarePlan(options){
 const inherited=await loadSoftwarePreviewPlan(options),authority=await import('./capture_runtime.mjs');
 return authority.extendLoadedOvernightPlan(inherited,options);
}
async function loopback(config,temporary){
 const file=path.join(temporary,'HTTP_CONFIG.json'),raw=Buffer.from(JSON.stringify(config));
 await writeFile(file,raw,{mode:0o600,flag:'wx'});
 const server=spawn('/usr/bin/python3',['-B',path.join(RECOVERY,'universal-auto-video-v2/serve_long.py'),
  '--config',file,'--expected-config-sha256',sha(raw)],{cwd:repo,stdio:['ignore','pipe','pipe']});let stderr='';
 server.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-4096);});
 const origin=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:server.stdout}),timer=setTimeout(()=>reject(Error('SOFTWARE_SERVER_TIMEOUT')),10000);
  lines.once('line',line=>{clearTimeout(timer);lines.close();try{const row=JSON.parse(line),url=new URL(row.url);
   assert.equal(row.event,'READY');assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');resolve(url.origin);
  }catch(error){reject(error);}});
  server.once('error',reject);server.once('exit',code=>{clearTimeout(timer);reject(Error('SOFTWARE_SERVER_EXIT_'+code+' '+stderr));});
 }).catch(error=>{server.kill();throw error;});return{server,origin};
}
export async function openSoftwarePreviewRuntime(options){
 const {loadPlan=loadSoftwarePreviewPlan,...sourceOptions}=options;
 const plan=await loadPlan(sourceOptions),temporary=await mkdtemp(path.join(tmpdir(),'worldengine-free-preview-http-'));
 let browser,server;
 try{
  const ready=await loopback(plan.serverConfig,temporary);server=ready.server;const {origin}=ready;
  browser=await softwarePlaywright().chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
   env:{...process.env,HOME:userInfo().homedir,XDG_CONFIG_HOME:path.join(temporary,'chromium-config'),XDG_CACHE_HOME:path.join(temporary,'chromium-cache')},
   ignoreDefaultArgs:['--disable-dev-shm-usage'],args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
    '--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)errors.push('HTTP_'+r.status()+' '+new URL(r.url()).pathname);});
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort('blockedbyclient'));
  await page.goto(origin+'/',{waitUntil:'load',timeout:240000});
  await page.waitForFunction(()=>Object.hasOwn(window,'longVideoBoot'),null,{timeout:240000});
  const info=await page.evaluate(()=>window.longVideoBoot);
  assertSoftwareRuntimeInfo(info);
  assert.deepEqual(errors,[],'SOFTWARE_BOOT_ERRORS');await plan.assertSourceUnchanged();
  const checkedPage=new Proxy(page,{get(target,key){
   if(key==='evaluate')return async(...args)=>{const captured=await target.evaluate(...args);
    return captured?.diagnostic?assertActualSoftwareFrame(captured,captured.diagnostic.frame,plan):captured;};
   const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});
  let closed=false;return{...plan,plan,page:checkedPage,errors,info,async close(){if(closed)return;closed=true;
   await page.evaluate(()=>window.longVideoProof?.dispose()).catch(()=>{});await browser.close();server.kill();
   await rm(temporary,{recursive:true,force:true});await plan.assertSourceUnchanged();}};
 }catch(error){await browser?.close().catch(()=>{});server?.kill();await rm(temporary,{recursive:true,force:true});throw error;}
}
export async function runFreePreview({outputRoot,requestFile,loadPlan,...options}){
 assert.equal(typeof loadPlan,'function','SOFTWARE_OVERNIGHT_SOURCE_AUTHORITY_REQUIRED');
 assert.ok(requestFile,'SOFTWARE_SOURCE_BOUND_PREVIEW_REQUEST_REQUIRED');
 const report=await capturePreviewWithRuntime({...options,outputRoot,requestFile,softwareProbe:true,
  loadSceneRuntime:async({sceneId})=>openSoftwarePreviewRuntime({...options,sceneId,loadPlan}),
  progress:value=>console.error(JSON.stringify({event:'SOFTWARE_FRAME',...value}))});
 assert.equal(report.status,'SOFTWARE_PREVIEW_TECHNICAL_PASS');assert.equal(report.hardwareVerified,false);
 assert.equal(report.completedFrames,150);assert.equal(report.fullDecodeVerified,true);
 const result={schema:'WORLD_ENGINE_FREE_PREVIEW_RESULT_V3',status:'PASS_SOFTWARE_ONLY',range:report.range,
  completedAt:iso(),softwareValidation:true,nvidiaHardwareVerified:false,gpuExecuted:false,
  actualWebGLDraw:true,actualReadPixels:true,actualMP4Decoded:true,original80sDocumentUnchanged:true,
  visualQualityApproved:false,full80SecondsRendered:false,productionRenderAllowed:false,
  video:report.video,checkpoints:report.checkpoints,totalWallMs:report.totalWallMs,
  sourceManifest:report.bindings.sourceManifestSHA256,sourceCommit:report.bindings.sourceCommit};
 await writeFile(path.join(outputRoot,'FREE_RENDER_RESULT.json'),JSON.stringify(result,null,2)+'\n',{mode:0o600,flag:'wx'});
 return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const options={},args=process.argv.slice(2),mapping={'--request-file':'requestFile','--overnight-request-file':'overnightRequestFile','--output-root':'outputRoot','--plan-file':'planFile','--plan-sha256':'expectedPlanSha256',
   '--activation-file':'activationFile','--activation-sha256':'expectedActivationSha256','--scene-id':'sceneId','--submission-file':'submissionFile'};
  while(args.length){const key=args.shift();assert.ok(mapping[key]&&args.length&&!Object.hasOwn(options,mapping[key]));options[mapping[key]]=args.shift();}
  const report=await runFreePreview({...options,loadPlan:loadOvernightSoftwarePlan});console.log(JSON.stringify({status:report.status,video:report.video,range:report.range,nvidiaHardwareVerified:false}));
 }catch(error){console.error(JSON.stringify({status:'GPU_PENDING',errorCode:String(error.message).slice(0,1200),stack:String(error.stack).slice(0,4500),nvidiaHardwareVerified:false}));process.exitCode=2;}
}
