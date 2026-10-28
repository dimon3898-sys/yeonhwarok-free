/** Real Chromium page.evaluate transport; synthetic failures, NO GPU/render. */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile,mkdtemp,chmod,readdir} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {once} from 'node:events';
import {createRecorder,attachPageDiagnostics,evaluateDiagnosed,preserveCleanup,classifyException} from '../../codex-to-gcube-handoff-v1/backend/capture_operation_diagnostics.mjs';
const require=createRequire(import.meta.url),{chromium}=require(path.join(process.env.WORLD_ENGINE_TEST_PLAYWRIGHT_ROOT,'node_modules/playwright-core'));
const execute=promisify(execFile),here=path.dirname(fileURLToPath(import.meta.url));
const output=path.resolve(process.env.WORLD_ENGINE_TEST_OUTPUT||'g1-evidence');await mkdir(output,{recursive:true});
const privateRoot=await mkdtemp(path.join(os.tmpdir(),'we-g1-browser-'));await chmod(privateRoot,0o700);
const guard=await readFile(path.join(here,'../../codex-to-gcube-handoff-v1/backend/native_guard.mjs'));
const server=createServer((req,res)=>{
 if(req.url==='/native_guard.mjs'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(guard);}
 else if(req.url==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>CPU diagnostic fixture</title>');}
 else{res.writeHead(404);res.end();}
});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port,results=[];
let browser;
async function exported(job,label,noReceipt=false){
 const dest=path.join(output,label);await execute('python3',[path.join(here,'export_fixture.py'),job,dest,...(noReceipt?['--no-receipt']:[])]);
 const raw=await readFile(path.join(dest,'CAPTURE_DIAGNOSTIC.json')),sum=await readFile(path.join(dest,'SHA256SUMS'),'utf8');
 assert(!raw.includes(Buffer.from('SYNTHETIC_SECRET_NOT_FOR_EXPORT')));assert(!raw.includes(Buffer.from('https://secret.invalid')));
 const sha=createHash('sha256').update(raw).digest('hex');assert(sum.startsWith(sha));return{value:JSON.parse(raw),sha};
}
async function fixture(label){const job=path.join(privateRoot,'studio-'+createHash('sha256').update(label).digest('hex').slice(0,32));
 const capture=path.join(job,'capture');await mkdir(capture,{recursive:true,mode:0o700});
 const recorder=createRecorder({outputRoot:capture,runId:path.basename(job)});const page=await browser.newPage();await page.goto(origin);await attachPageDiagnostics(page,recorder);
 return{job,recorder,page};}
try{
 browser=await chromium.launch({executablePath:process.env.WORLD_ENGINE_TEST_CHROMIUM,headless:true,args:['--no-sandbox','--disable-gpu']});
 const cases=[
  ['known_native','DRAW','Error','GCUBE_NATIVE_DRAW_FAILED','DOMAIN_ERROR'],
  ['native_guard_code','PROOF_VALIDATION','Error','GCUBE_NATIVE_STABILITY_PROOF_REQUIRED','DOMAIN_ERROR'],
  ['unknown_type','RUNTIME_CREATE','TypeError','UNCLASSIFIED_EXCEPTION','UNCLASSIFIED_EXCEPTION'],
  ['secret_message','DRAW','Error','UNCLASSIFIED_EXCEPTION','UNCLASSIFIED_EXCEPTION'],
  ['module_import','NATIVE_GUARD_IMPORT','TypeError','UNCLASSIFIED_EXCEPTION','MODULE_IMPORT_FAILURE'],
  ['asset_http','MAP_TEXTURE_PREPARATION','Error','CAPTURE_ASSET_HTTP_FAILED','ASSET_HTTP_FAILURE'],
  ['context_failure','WEBGL_CONTEXT','Error','GCUBE_NATIVE_CONTEXT_REQUIRED','DOMAIN_ERROR'],
  ['readback','READBACK','Error','GCUBE_NATIVE_READBACK_INVALID','DOMAIN_ERROR'],
  ['cleanup_failure','DRAW','Error','GCUBE_NATIVE_DRAW_FAILED','DOMAIN_ERROR'],
  ['real_guard_readback','READBACK','TypeError','UNCLASSIFIED_EXCEPTION','UNCLASSIFIED_EXCEPTION'],
 ];
 for(const[label,operation,type,wanted,kind]of cases){
  const{job,recorder,page}=await fixture(label);
  let caught;try{await evaluateDiagnosed(page,async spec=>window.__worldEngineDiagnostics.capture(async()=>{
   const d=window.__worldEngineDiagnostics;await d.run('INPUT_CANVAS',()=>true);
   const {label,operation}=spec;
   if(label==='real_guard_readback'){
    const{runThreeNativeDraws}=await d.run('NATIVE_GUARD_IMPORT',()=>import('/native_guard.mjs'));
    // CPU mock only, executes unchanged hardware guards; not hardware proof.
    const gl={getExtension:()=>({UNMASKED_RENDERER_WEBGL:1}),getParameter:()=> 'NVIDIA Vulkan CPU_TEST_MOCK',getError:()=>0};
    const runtime={drawFrame:()=>({backend:'NVIDIA Vulkan CPU_TEST_MOCK',glError:0}),readPixels:()=>{throw TypeError('SYNTHETIC_SECRET_NOT_FOR_EXPORT');},recordNativeStability:()=>{}};
    return d.run('NATIVE_CONTEXT_PROOF',()=>runThreeNativeDraws({runtime,canvas:{width:1080,height:1920,getContext:()=>gl},diagnostics:d}));
   }
   try{return await d.run(operation,async()=>{
    if(label==='module_import')return import('/missing-module.mjs');
    if(label==='asset_http'){const r=await fetch('/missing-asset');if(!r.ok)throw Error('CAPTURE_ASSET_HTTP_FAILED');}
    if(label==='unknown_type')throw TypeError('https://secret.invalid/?token=SYNTHETIC_SECRET_NOT_FOR_EXPORT');
    if(label==='secret_message')throw Error('GCUBE_NATIVE_DRAW_FAILED Authorization=SYNTHETIC_SECRET_NOT_FOR_EXPORT');
    throw Error(spec.code);
   },{frame:0});}finally{if(label==='cleanup_failure')await d.cleanup(()=>{throw Error('SYNTHETIC_SECRET_NOT_FOR_EXPORT');});}
  }),{label,operation,code:wanted},{recorder,timeoutMs:10000});}catch(error){caught=error;}
  assert(caught,label);assert.equal(caught.message,wanted,label);await page.close();
  const safe=await exported(job,label),inner=safe.value.capture.operations.firstFailure;
  assert.equal(inner.errorCode,wanted,label);assert.equal(inner.operationId,operation,label);assert.equal(inner.exceptionType,type,label);assert.equal(inner.failureKind,kind,label);
  assert.equal(safe.value.capture.nvidiaVerified,false);assert.equal(safe.value.capture.operations.nativeProofCompleted,false);
  if(label==='cleanup_failure')assert.equal(safe.value.capture.operations.cleanupFailure.errorCode,'UNCLASSIFIED_EXCEPTION');
  results.push({case:label,status:'PASS',scope:'CPU_ONLY_SYNTHETIC_BROWSER',errorCode:inner.errorCode,operationId:inner.operationId,sha256:safe.sha});
 }
 for(const[label,expected]of [['timeout','CAPTURE_PAGE_TIMEOUT'],['closed','CAPTURE_PAGE_CLOSED'],['crash','CAPTURE_PAGE_CRASH']]){
  const{job,recorder,page}=await fixture(label);let startedResolve;const started=new Promise(resolve=>{startedResolve=resolve;});
  await page.exposeFunction('__fixtureStarted',()=>startedResolve());
  const evaluation=evaluateDiagnosed(page,async()=>window.__worldEngineDiagnostics.capture(async()=>{
   const d=window.__worldEngineDiagnostics;await d.run('INPUT_CANVAS',()=>true);
   return d.run('DRAW',async()=>{await window.__fixtureStarted();return new Promise(()=>{});});
  }),undefined,{recorder,timeoutMs:label==='timeout'?500:10000}).then(()=>null,error=>error);
  await started;if(label==='closed')await page.close();if(label==='crash'){const cdp=await page.context().newCDPSession(page);cdp.send('Page.crash').catch(()=>{});}
  const error=await evaluation;assert.equal(error?.message,expected,label);await page.close().catch(()=>{});
  const safe=await exported(job,label,true);assert.equal(safe.value.capture.operations.lastCompletedOperation,'INPUT_CANVAS');
  assert.equal(safe.value.capture.code,expected);assert(safe.value.missingEvidence.capture);
  results.push({case:label,status:'PASS',scope:'CPU_ONLY_REAL_BROWSER_TRANSPORT',errorCode:expected,sha256:safe.sha});
 }
 const job=path.join(privateRoot,'studio-'+'9'.repeat(32));await mkdir(path.join(job,'capture'),{recursive:true,mode:0o700});
 const helper=new URL('../../codex-to-gcube-handoff-v1/backend/capture_operation_diagnostics.mjs',import.meta.url).href;
 const child=spawn(process.execPath,['--input-type=module','-e',`import {createRecorder} from ${JSON.stringify(helper)};const r=createRecorder({outputRoot:process.argv[1]});await r.event({phase:'END',operationId:'DRAW'});await r.event({phase:'START',operationId:'READBACK'});process.stdout.write('CHECKPOINT_READY\\n');setInterval(()=>{},1000);`,path.join(job,'capture')],{stdio:['ignore','pipe','pipe']});
 await once(child.stdout,'data');child.kill('SIGTERM');await once(child,'exit');const safe=await exported(job,'process_termination',true);
 assert.equal(safe.value.capture.operations.lastCompletedOperation,'DRAW');assert.equal(safe.value.capture.operations.operationId,'READBACK');
 results.push({case:'process_termination',status:'PASS',scope:'CPU_ONLY_PROCESS',sha256:safe.sha});
 const report={schema:'WORLD_ENGINE_G1_TEST_RESULTS_V1',scope:'CPU_ONLY',gpuExecuted:false,gpuRootCause:'UNKNOWN',
  sourceCommit:process.env.GITHUB_SHA??null,runId:process.env.GITHUB_RUN_ID??null,chromium:browser.version(),
  cases:results,status:'G1_BROWSER_CONTRACT_PASS',productionImageTested:false};
 await writeFile(path.join(output,'TEST_RESULTS.json'),JSON.stringify(report,null,2)+'\n');
 const files=[];async function walk(dir){for(const entry of await readdir(dir,{withFileTypes:true})){const f=path.join(dir,entry.name);if(entry.isDirectory())await walk(f);else if(entry.name!=='SHA256SUMS')files.push(f);}}await walk(output);
 const rows=[];for(const f of files.sort()){const bytes=await readFile(f);assert(!bytes.includes(Buffer.from('SYNTHETIC_SECRET_NOT_FOR_EXPORT')));rows.push(createHash('sha256').update(bytes).digest('hex')+'  '+path.relative(output,f));}
 await writeFile(path.join(output,'SHA256SUMS'),rows.join('\n')+'\n');console.log(JSON.stringify(report));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
