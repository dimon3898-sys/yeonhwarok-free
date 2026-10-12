#!/usr/bin/env node
// Executes the thin adapter only when explicitly invoked. No golden image input.
import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {lstat,readFile,realpath,mkdir,writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {spawn,execFile} from 'node:child_process';
import {createInterface} from 'node:readline';
import {promisify} from 'node:util';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const runtime=path.dirname(fileURLToPath(import.meta.url));
const engine=path.resolve(runtime,'../../..'),repo=path.dirname(engine);
const EXPECTED_STATIC_SHA='fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673';
const EXPECTED_STATIC_RGBA_SHA='cee0e480f1a0941f13d7bbe675952abe5a3bef53dd0bcc44c001f856982e7376';
const THREE_SHA='ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb';
const BROWSER_ARGS=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage'];
const execute=promisify(execFile);
const PYTHON='/usr/bin/python3';
const defaults={
  'mode':'static','regional-plan':'recovery/v4/equivalent-plans/REGIONAL-plan.json',
  'continent-plan':'recovery/v4/equivalent-plans/CONTINENT-plan.json',
  'scene':'recovery/v4/equivalent-plans/scene.json',
  'camera-plan':'recovery/v4/V4-state-records/camera-plan.json',
  'input-manifest':'recovery/v4/V4-state-records/input-manifest.json',
  'golden':'recovery/v4/approved-proof/07_FINAL_HOLD.png',
  'chromium':'/usr/bin/chromium','timeout-ms':'240000'
};
function options(){
  const result={...defaults},allowed=new Set([...Object.keys(defaults),'output-dir','frames','static-receipt','help']);
  for(let i=2;i<process.argv.length;i++){
    const name=process.argv[i].replace(/^--/,'');
    if(!process.argv[i].startsWith('--')||!allowed.has(name))throw Error('UNKNOWN_OPTION');
    if(name==='help'){result.help=true;continue;}
    if(!process.argv[i+1]||process.argv[i+1].startsWith('--'))throw Error('OPTION_VALUE_REQUIRED');
    result[name]=process.argv[++i];
  }
  if(!['static','checkpoints','frames'].includes(result.mode))throw Error('INVALID_MODE');
  if(!result.help&&!result['output-dir'])throw Error('OUTPUT_DIR_REQUIRED');
  if(!/^\d+$/.test(result['timeout-ms'])||Number(result['timeout-ms'])<1000)throw Error('INVALID_TIMEOUT');
  return result;
}
function inputPath(value){return path.isAbsolute(value)?path.resolve(value):path.resolve(engine,value);}
async function safeFile(file){
  const absolute=path.resolve(file),relative=path.relative(repo,absolute);
  if(relative.startsWith('..'+path.sep)||relative==='..'||path.isAbsolute(relative))throw Error('INPUT_OUTSIDE_REPOSITORY');
  if((await realpath(absolute))!==absolute||!(await lstat(absolute)).isFile())throw Error('INPUT_NOT_REGULAR_OR_SYMLINK');
  return absolute;
}
async function fileRecord(file){
  file=await safeFile(file);
  const hash=createHash('sha256');let bytes=0;
  for await(const chunk of createReadStream(file)){hash.update(chunk);bytes+=chunk.length;}
  return {path:path.relative(repo,file).split(path.sep).join('/'),sha256:hash.digest('hex'),bytes};
}
function assetPath(url){
  if(url==='/height.f32')return path.join(engine,'web/dem/glo30/height.f32');
  if(url==='/three.js')return path.join(engine,'web/vendor/three/0.170.0/three.module.js');
  const mounts={'/camera-v4-assets/':'web/camera-v4-assets/','/static/':'web/'};
  for(const [prefix,target]of Object.entries(mounts))if(url.startsWith(prefix))return path.join(engine,target,url.slice(prefix.length));
  if(url.startsWith('/v3/assets/'))return path.join(repo,'cinematic-world-map/assets',url.slice('/v3/assets/'.length));
  throw Error('UNSUPPORTED_RUNTIME_ASSET_ROUTE');
}
async function preflight(opts){
  const records={},inputs={};
  for(const name of ['regional-plan','continent-plan','input-manifest',...(opts.mode==='static'?[]:['scene','camera-plan'])]){
    const file=await safeFile(inputPath(opts[name]));
    inputs[name]=JSON.parse(await readFile(file,'utf8'));const record=await fileRecord(file);records[record.path]=record;
  }
  const metadata=inputs['input-manifest'],regional=inputs['regional-plan'];
  for(const descriptor of [...Object.values(regional.assets),metadata.heightSource,metadata.contextTerrain]){
    if(!descriptor||typeof descriptor.url!=='string'||!/^[a-f0-9]{64}$/.test(descriptor.sha256))throw Error('ASSET_DESCRIPTOR_INCOMPLETE');
    const record=await fileRecord(assetPath(descriptor.url));
    if(record.sha256!==descriptor.sha256)throw Error('RUNTIME_ASSET_SHA_MISMATCH');
    const expectedSize=descriptor.bytes??descriptor.byteLength;
    if(expectedSize!==undefined&&record.bytes!==expectedSize)throw Error('RUNTIME_ASSET_SIZE_MISMATCH');
    records[record.path]=record;
  }
  const three=await fileRecord(assetPath('/three.js'));
  if(three.sha256!==THREE_SHA)throw Error('PINNED_THREE_SHA_MISMATCH');records[three.path]=three;
  const importManifestFile=path.join(runtime,'IMPORT_MANIFEST.json');
  const importManifest=JSON.parse(await readFile(await safeFile(importManifestFile),'utf8'));
  for(const item of importManifest.modules){
    const file=path.resolve(repo,typeof item==='string'?item:item.path);
    const record=await fileRecord(file);
    if(typeof item==='object'&&((item.sha256&&record.sha256!==item.sha256)||(item.bytes!==undefined&&record.bytes!==item.bytes)))
      throw Error('IMPORT_MODULE_INVENTORY_MISMATCH');
    records[record.path]=record;
  }
  for(const file of ['index.html','harness.mjs','serve.py','render.mjs','DEPENDENCY_MANIFEST.json','IMPORT_MANIFEST.json']){
    const record=await fileRecord(path.join(runtime,file));records[record.path]=record;
  }
  for(const file of ['package.json','package-lock.json']){
    const record=await fileRecord(path.join(repo,'cinematic-world-map',file));records[record.path]=record;
  }
  const golden=await fileRecord(inputPath(opts.golden));
  if(golden.sha256!==EXPECTED_STATIC_SHA)throw Error('APPROVED_GOLDEN_SHA_MISMATCH');records[golden.path]=golden;
  const comparator=await fileRecord(path.join(repo,'tools/compare_v4_png.py'));records[comparator.path]=comparator;
  const {stdout:commit}=await execute('git',['rev-parse','HEAD'],{cwd:repo});
  const {stdout:status}=await execute('git',['status','--porcelain','--untracked-files=normal'],{cwd:repo});
  return {records,source_commit:commit.trim(),working_tree_clean:status.trim()===''};
}
async function compareStatic(opts,actual,actualSha){
  const argv=['-B',path.join(repo,'tools/compare_v4_png.py'),inputPath(opts.golden),actual];
  let stdout;
  try{({stdout}=await execute(PYTHON,argv,{cwd:repo,timeout:30000,maxBuffer:1024*1024}));}
  catch(error){if(error.code!==1||!error.stdout)throw error;stdout=error.stdout;}
  const report=JSON.parse(stdout);
  if(report.expected_sha256!==EXPECTED_STATIC_SHA||report.expected_rgba_sha256!==EXPECTED_STATIC_RGBA_SHA
    ||report.actual_sha256!==actualSha||JSON.stringify(report.expected_dimensions)!=='[1080,1920]'
    ||JSON.stringify(report.actual_dimensions)!=='[1080,1920]')throw Error('COMPARISON_PROVENANCE_MISMATCH');
  const passed=['BIT_EXACT','PIXEL_EXACT'].includes(report.classification)
    &&report.changed_pixels===0&&report.max_channel_difference===0&&report.actual_rgba_sha256===EXPECTED_STATIC_RGBA_SHA;
  return {report,passed,command:{argv:[PYTHON,...argv],cwd:repo}};
}
async function checkedStaticReceipt(opts,inventory){
  if(opts.mode==='static')return;
  if(!opts['static-receipt'])throw Error('VERIFIED_STATIC_RECEIPT_REQUIRED_BEFORE_V4');
  const receiptPath=path.resolve(opts['static-receipt']);
  if(path.basename(receiptPath)!=='runtime-diagnostic.json'||await realpath(receiptPath)!==receiptPath)
    throw Error('REGULAR_STATIC_DIAGNOSTIC_REQUIRED');
  const receipt=JSON.parse(await readFile(receiptPath,'utf8'));
  const v4Only=new Set(['scene','camera-plan'].map(name=>path.relative(repo,inputPath(opts[name])).split(path.sep).join('/')));
  const sharedFiles=Object.keys(inventory.records).filter(file=>!v4Only.has(file));
  if(receipt.kind!=='v4_runtime_diagnostic'||receipt.mode!=='static'||receipt.status!=='RENDERED'
    ||receipt.source_commit!==inventory.source_commit||!receipt.required_inputs
    ||Object.keys(receipt.required_inputs).length!==sharedFiles.length||sharedFiles.some(file=>!receipt.required_inputs[file])
    ||Object.entries(receipt.required_inputs).some(([file,record])=>JSON.stringify(record)!==JSON.stringify(inventory.records[file])))
    throw Error('STATIC_RECEIPT_INPUTS_MISMATCH');
  const output=receipt.outputs?.[0];
  if(!output||!/^[a-f0-9]{64}$/.test(output.sha256))throw Error('STATIC_OUTPUT_RECEIPT_REQUIRED');
  const outputPath=path.resolve(output.path);
  if(outputPath!==path.join(path.dirname(receiptPath),'static-final-hold.png')||await realpath(outputPath)!==outputPath)
    throw Error('REGULAR_STATIC_RECEIPT_OUTPUT_REQUIRED');
  const bytes=await readFile(outputPath);
  if(createHash('sha256').update(bytes).digest('hex')!==output.sha256)throw Error('STATIC_RECEIPT_OUTPUT_MISMATCH');
  if(!(await compareStatic(opts,outputPath,output.sha256)).passed)throw Error('STATIC_FINAL_HOLD_PIXEL_MISMATCH');
}
async function startServer(opts){
  const argv=['-B',path.join(runtime,'serve.py'),'--phase',opts.mode==='static'?'static':'v4'];
  for(const name of ['regional-plan','continent-plan','scene','camera-plan','input-manifest'])argv.push('--'+name,opts[name]);
  const child=spawn(PYTHON,argv,{cwd:repo,stdio:['ignore','pipe','pipe']});
  let stderr='';child.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-4096);});
  const ready=await new Promise((resolve,reject)=>{
    const lines=createInterface({input:child.stdout});
    const timer=setTimeout(()=>{child.kill('SIGTERM');reject(Error('SERVER_START_TIMEOUT'));},10000);
    child.once('error',reject);
    child.once('exit',code=>{clearTimeout(timer);reject(Error('SERVER_EXIT_'+code));});
    lines.once('line',line=>{clearTimeout(timer);lines.close();try{const data=JSON.parse(line);if(data.event!=='READY')throw Error('SERVER_NOT_READY');resolve(data);}catch(error){child.kill('SIGTERM');reject(error);}});
  });
  return {child,url:ready.url,config:ready.config,stderr:()=>stderr};
}
async function main(){
  const opts=options();
  if(opts.help){console.log('node render.mjs --output-dir NEW_PRIVATE_DIRECTORY [--mode static|checkpoints|frames] [--frames 0,330,374] [--static-receipt FILE] [--regional-plan FILE --continent-plan FILE --scene FILE --golden FILE]');return;}
  const inventory=await preflight(opts);await checkedStaticReceipt(opts,inventory);
  const require=createRequire(path.join(repo,'cinematic-world-map/package.json'));
  if(require('playwright/package.json').version!=='1.62.1')throw Error('PINNED_PLAYWRIGHT_VERSION_REQUIRED');
  const {chromium}=require('playwright');
  const outputDir=path.resolve(opts['output-dir']);
  if(outputDir===repo||outputDir.startsWith(repo+path.sep))throw Error('OUTPUT_MUST_BE_SEPARATE_FROM_DEVELOPMENT_SOURCE');
  if(await realpath(path.dirname(outputDir))!==path.dirname(outputDir))throw Error('OUTPUT_PARENT_SYMLINK_FORBIDDEN');
  await mkdir(outputDir); // Existing output directories are never overwritten.
  const diagnostic={schema:1,kind:'v4_runtime_diagnostic',mode:opts.mode,status:'STARTED',
    started_at_utc:new Date().toISOString(),source_commit:inventory.source_commit,required_inputs:inventory.records,
    working_tree_clean:inventory.working_tree_clean,clean_environment_verified:false,
    command:{argv:[process.execPath,...process.argv.slice(1)],cwd:process.cwd()},
    node:process.version,playwright:'1.62.1',chromium_executable:opts.chromium,browser_args:BROWSER_ARGS,
    viewport:[1080,1920],device_scale_factor:1,outputs:[],errors:[]};
  let browser,server;
  try{
    server=await startServer(opts);diagnostic.serving=server.config;
    browser=await chromium.launch({executablePath:opts.chromium,headless:true,args:BROWSER_ARGS});
    diagnostic.chromium=browser.version();
    if(!diagnostic.chromium.startsWith('154.'))throw Error('CHROMIUM_154_REQUIRED');
    const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
    const runtimeErrors=[];
    await page.route('**/*',route=>{
      const url=new URL(route.request().url());
      return url.origin===server.url?route.continue():route.abort('blockedbyclient');
    });
    page.on('pageerror',error=>runtimeErrors.push(String(error.message).slice(0,1024)));
    page.on('response',response=>{if(response.status()>=400)runtimeErrors.push('HTTP_'+response.status()+' '+new URL(response.url()).pathname);});
    await page.goto(server.url,{waitUntil:'load',timeout:Number(opts['timeout-ms'])});
    await page.waitForFunction(()=>['READY_STATIC','ERROR'].includes(window.v4Runtime?.state),null,{timeout:Number(opts['timeout-ms'])});
    const startupError=await page.evaluate(()=>window.v4Runtime.error);
    if(startupError||runtimeErrors.length)throw Error(startupError||'RUNTIME_HTTP_OR_PAGE_ERROR');
    let frames=[null];
    if(opts.mode!=='static'){
      await page.evaluate(()=>window.v4Runtime.initV4());
      if(opts['frames'])frames=opts.frames.split(',').map(Number);
      else if(opts.mode==='frames')frames=Array.from({length:375},(_,i)=>i);
      else frames=await page.evaluate(()=>Object.values(window.v4Runtime.checkpoints));
      frames=[...new Set(frames)].sort((a,b)=>a-b);
      if(!frames.length||frames.some(frame=>!Number.isInteger(frame)||frame<0||frame>374))throw Error('INVALID_INTEGER_FRAMES');
    }
    for(const frame of frames){
      const captured=await page.evaluate(frame=>frame===null?window.v4Runtime.captureStatic():window.v4Runtime.captureFrame(frame),frame);
      if(runtimeErrors.length)throw Error('RUNTIME_HTTP_OR_PAGE_ERROR');
      if(!captured.png.startsWith('data:image/png;base64,'))throw Error('CANVAS_PNG_REQUIRED');
      const bytes=Buffer.from(captured.png.slice('data:image/png;base64,'.length),'base64');
      if(bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||bytes.readUInt32BE(16)!==1080||bytes.readUInt32BE(20)!==1920)throw Error('CANONICAL_PNG_REQUIRED');
      const filename=frame===null?'static-final-hold.png':`frame-${String(frame).padStart(3,'0')}.png`;
      const output=path.join(outputDir,filename);await writeFile(output,bytes,{flag:'wx'});
      const {png,...evidence}=captured;
      await writeFile(path.join(outputDir,filename.replace('.png','.diagnostic.json')),JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
      const sha256=createHash('sha256').update(bytes).digest('hex');
      diagnostic.outputs.push({path:output,sha256,bytes:bytes.length,frame,raw_rgba_sha256:evidence.raw_rgba_sha256});
      console.log(JSON.stringify({event:'FRAME_WRITTEN',frame,path:output,sha256}));
    }
    const finalInventory=await preflight(opts);
    if(finalInventory.source_commit!==inventory.source_commit||JSON.stringify(finalInventory.records)!==JSON.stringify(inventory.records))throw Error('INPUT_OR_SOURCE_CHANGED_DURING_RENDER');
    diagnostic.status='RENDERED';diagnostic.command.exit_code=0;
    diagnostic.static_final_hold_expected_sha256=EXPECTED_STATIC_SHA;
    diagnostic.static_final_hold_hash_match=opts.mode==='static'?diagnostic.outputs[0].sha256===EXPECTED_STATIC_SHA:null;
    if(opts.mode==='static'){
      const comparison=await compareStatic(opts,diagnostic.outputs[0].path,diagnostic.outputs[0].sha256);
      const reportPath=path.join(outputDir,'static-final-hold.comparison.json');
      await writeFile(reportPath,JSON.stringify(comparison.report,null,2)+'\n',{flag:'wx'});
      diagnostic.static_comparison={path:reportPath,...comparison};
      diagnostic.static_final_hold_pixel_match=comparison.passed;
      if(!comparison.passed)throw Error('STATIC_FINAL_HOLD_PIXEL_MISMATCH');
    }
    await page.evaluate(()=>window.v4Runtime.dispose());
  }catch(error){
    diagnostic.status='ERROR';diagnostic.errors.push(String(error.message).slice(0,2048));diagnostic.command.exit_code=1;throw error;
  }finally{
    if(browser)await browser.close().catch(()=>{});
    if(server){server.child.kill('SIGTERM');diagnostic.server_stderr=server.stderr();}
    diagnostic.completed_at_utc=new Date().toISOString();
    await writeFile(path.join(outputDir,'runtime-diagnostic.json'),JSON.stringify(diagnostic,null,2)+'\n',{flag:'wx'});
  }
}
main().catch(error=>{console.error(JSON.stringify({status:'ERROR',reason:String(error.message).slice(0,2048)}));process.exitCode=1;});
