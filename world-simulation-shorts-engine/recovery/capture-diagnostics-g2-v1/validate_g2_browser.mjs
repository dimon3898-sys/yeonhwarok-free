/** New-image installed-module integration only. No G1 suite, GPU, or renderer invocation. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {readFile,access,mkdir,stat} from 'node:fs/promises';
import {constants} from 'node:fs';
import {createServer} from 'node:http';
import path from 'node:path';
import os from 'node:os';

const [root, job, depsRoot] = process.argv.slice(2);
const ns = path.join(root, 'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1');
let browser, server, step='ARGUMENTS';
const proof = {schema:'WORLD_ENGINE_G2_IMAGE_BROWSER_PROBE_V1', status:'BLOCKED',
  scope:'INSTALLED_IMAGE_CPU_INTEGRATION', gpuExecuted:false, renderedFrames:0, gpuRootCause:'UNKNOWN'};
function launchSignals(error, home) {
  // Only closed booleans leave the browser failure. Never publish its raw log.
  const message=typeof error?.message==='string'?error.message:'';
  const denied=/permission denied|read-only file system|EACCES|EROFS/i.test(message);
  const xdg=[process.env.XDG_CONFIG_HOME,process.env.XDG_CACHE_HOME]
    .filter(value=>typeof value==='string' && path.isAbsolute(value));
  return {
    crashpadDatabaseRequired:/chrome_crashpad_handler:\s*--database is required|crashpad_handler[^\n]*--database[^\n]*required/i.test(message),
    homeWriteDenied:denied && typeof home==='string' && home.length>1 && message.includes(home),
    xdgWriteDenied:denied && xdg.some(value=>message.includes(value)),
    missingSharedLibrary:/error while loading shared libraries|Host system is missing dependencies/i.test(message),
    sandboxAdmission:/no usable sandbox|SUID sandbox|Running as root without --no-sandbox/i.test(message),
    executableMissing:/executable doesn.t exist|spawn .*ENOENT|Failed to launch.*executable/i.test(message),
    browserClosed:/Target page, context or browser has been closed|browser has been closed/i.test(message)
  };
}
async function homeReadiness(home) {
  const state={configured:typeof process.env.HOME==='string',absolute:path.isAbsolute(home),
    exists:false,directory:false,writableByAccessCheck:false};
  try {const info=await stat(home);state.exists=true;state.directory=info.isDirectory();} catch {}
  try {await access(home,constants.W_OK);state.writableByAccessCheck=true;} catch {}
  return state;
}
try {
  assert(path.isAbsolute(root) && path.isAbsolute(job) && path.isAbsolute(depsRoot));
  step='VARIANT_VERIFY';
  const {verifyGeneratedSources} = await import(pathToFileURL(path.join(ns, 'backend/capture_nvidia.mjs')).href);
  proof.generatedVariants = await verifyGeneratedSources();
  assert.equal(proof.generatedVariants.length, 3);
  proof.verifyGeneratedSources = 'PASS';
  step='CAPTURE_IMPORT';
  const capture = await import(pathToFileURL(path.join(ns, 'capture_vulkan.generated.mjs')).href);
  assert.equal(typeof capture.captureVulkanDerived, 'function');
  proof.installedCaptureImport = 'PASS';
  step='DIAGNOSTIC_IMPORT';
  const {createRecorder,attachPageDiagnostics,evaluateDiagnosed} =
    await import(pathToFileURL(path.join(ns,'backend/capture_operation_diagnostics.mjs')).href);
  proof.installedDiagnosticImport = 'PASS';
  step='PLAYWRIGHT_REQUIRE';
  const require = createRequire(path.join(depsRoot, 'package.json'));
  const {chromium} = require('playwright');
  proof.node = process.version;
  proof.playwright = require('playwright/package.json').version;
  proof.playwrightModulePath = require.resolve('playwright');
  proof.chromiumExecutable = '/usr/bin/chromium';
  step='LOOPBACK_SERVER';
  server = createServer((req,res)=>{
    if (req.url === '/') { res.writeHead(200, {'Content-Type':'text/html'}); res.end('<!doctype html><title>G2 installed image diagnostic transport</title>'); }
    else { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve=>server.listen(0, '127.0.0.1', resolve));
  step='CHROMIUM_LAUNCH';
  const home=os.homedir();
  proof.launchEnvironment={home:await homeReadiness(home),ephemeralTestEnvironmentApplied:false,
    productionEnvironmentChanged:false,launchAttempts:1};
  const launch={executablePath:proof.chromiumExecutable, headless:true,
    args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']};
  try {browser=await chromium.launch(launch);}
  catch(error) {
    const signals=launchSignals(error,home);
    proof.launchEnvironment.initialFailureSignals=signals;
    const eligible=(signals.crashpadDatabaseRequired||signals.homeWriteDenied||signals.xdgWriteDenied)
      && !signals.missingSharedLibrary && !signals.sandboxAdmission && !signals.executableMissing;
    proof.launchEnvironment.ephemeralEnvironmentRetryEligible=eligible;
    if(!eligible) throw error;
    // A single CPU-only correction is conditional on an observed home/crashpad
    // failure. This changes only the test browser child environment, never the
    // packaged capture launch profile, container environment, or production HOME.
    step='CHROMIUM_LAUNCH_EPHEMERAL_HOME';
    const childHome=path.join(job,'browser-home'),config=path.join(childHome,'config'),cache=path.join(childHome,'cache');
    await mkdir(childHome,{mode:0o700});
    await mkdir(config,{mode:0o700});
    await mkdir(cache,{mode:0o700});
    proof.launchEnvironment.ephemeralTestEnvironmentApplied=true;
    proof.launchEnvironment.launchAttempts=2;
    try {browser=await chromium.launch({...launch,env:{...process.env,
      HOME:childHome,XDG_CONFIG_HOME:config,XDG_CACHE_HOME:cache}});}
    catch(retryError) {proof.launchEnvironment.retryFailureSignals=launchSignals(retryError,childHome);throw retryError;}
  }
  proof.chromium = browser.version();
  step='PAGE_NAVIGATION';
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:'+server.address().port);
  step='DIAGNOSTIC_ATTACH';
  const recorder = createRecorder({outputRoot:path.join(job,'capture'), runId:path.basename(job)});
  await attachPageDiagnostics(page, recorder);
  step='DIAGNOSTIC_EVALUATE';
  let failure;
  try {
    await evaluateDiagnosed(page, async()=>window.__worldEngineDiagnostics.capture(async()=>{
      const d=window.__worldEngineDiagnostics;
      await d.run('INPUT_CANVAS', ()=>true);
      try { return await d.run('READBACK', ()=>{throw Error('GCUBE_NATIVE_READBACK_INVALID');}, {sourceId:'NATIVE_GUARD',frame:0}); }
      finally { await d.cleanup(()=>{throw Error('G2_PRIVATE_SENTINEL_NOT_FOR_EXPORT https://private.invalid/?owner=G2_PRIVATE_SENTINEL_NOT_FOR_EXPORT');}); }
    }), undefined, {recorder,timeoutMs:10000});
  } catch(error) { failure=error; }
  assert.equal(failure?.message, 'GCUBE_NATIVE_READBACK_INVALID');
  step='CHECKPOINT_READBACK';
  const checkpoint=JSON.parse(await readFile(path.join(job,'capture/CAPTURE_OPERATION_CHECKPOINT.json'),'utf8'));
  assert.equal(checkpoint.firstFailure.errorCode,'GCUBE_NATIVE_READBACK_INVALID');
  assert.equal(checkpoint.firstFailure.operationId,'READBACK');
  assert.equal(checkpoint.firstFailure.sourceId,'NATIVE_GUARD');
  assert.equal(checkpoint.cleanupFailure.errorCode,'UNCLASSIFIED_EXCEPTION');
  assert.equal(checkpoint.lastCompletedOperation,'INPUT_CANVAS');
  assert.equal(checkpoint.nativeProofCompleted,false);
  assert.equal(checkpoint.renderedFrames,0);
  proof.browserCheckpoint = {status:'PASS',errorCode:checkpoint.firstFailure.errorCode,
    operationId:checkpoint.firstFailure.operationId,lastCompletedOperation:checkpoint.lastCompletedOperation,
    cleanupErrorCode:checkpoint.cleanupFailure.errorCode};
  await page.close();
  proof.status='PASS';
} catch(error) {
  proof.failedStep=step;
  const exceptionNames=['Error','TypeError','RangeError','SyntaxError','ReferenceError','AssertionError','TimeoutError'];
  proof.exceptionType=exceptionNames.includes(error?.name)?error.name:'UNKNOWN';
  const publicCodes=['HANDOFF_VARIANT_MANIFEST_REQUIRED','HANDOFF_VARIANT_PATH_INVALID','HANDOFF_VARIANT_SHA_REQUIRED',
    'HANDOFF_EXACT_VARIANT_SET_REQUIRED','HANDOFF_VARIANT_REGULAR_FILE_REQUIRED','HANDOFF_CAPTURE_SOURCE_CHANGED',
    'CAPTURE_DIAGNOSTIC_SCHEMA_INVALID','CAPTURE_EVALUATION_TRANSPORT_FAILED','CAPTURE_PAGE_TIMEOUT',
    'CAPTURE_PAGE_CLOSED','CAPTURE_PAGE_CRASH','DIAGNOSTIC_STORAGE_PERMISSION','DIAGNOSTIC_STORAGE_NO_SPACE',
    'DIAGNOSTIC_STORAGE_TOO_LARGE','DIAGNOSTIC_STORAGE_IO'];
  proof.errorCode=publicCodes.includes(error?.message)?error.message:'G2_IMAGE_BROWSER_PROBE_FAILED';
  const systemCodes=['ENOENT','EACCES','EPERM','ENOSPC','EDQUOT','EADDRINUSE','ERR_MODULE_NOT_FOUND','MODULE_NOT_FOUND','ERR_ASSERTION'];
  proof.systemCode=systemCodes.includes(error?.code)?error.code:null;
  const message=typeof error?.message==='string'?error.message:'';
  proof.failureCategory=/error while loading shared libraries|Host system is missing dependencies/i.test(message)?'MISSING_SHARED_LIBRARY':
    /no usable sandbox|SUID sandbox|Running as root without --no-sandbox/i.test(message)?'SANDBOX_ADMISSION':
    /executable doesn.t exist|spawn .*ENOENT|Failed to launch.*executable/i.test(message)?'EXECUTABLE_MISSING':
    /Target page, context or browser has been closed|browser has been closed/i.test(message)?'BROWSER_CLOSED':
    error?.name==='AssertionError'?'INTEGRATION_ASSERTION':'UNCLASSIFIED';
  process.exitCode=1;
} finally {
  await browser?.close().catch(()=>{});
  if(server?.listening) await new Promise(resolve=>server.close(resolve));
}
console.log(JSON.stringify(proof));
