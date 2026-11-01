import assert from 'node:assert/strict';
import vm from 'node:vm';
import * as fs from 'node:fs/promises';
import {writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {EventEmitter, once} from 'node:events';
import {promisify} from 'node:util';
import os from 'node:os';

// No browser, WebGL, GPU, network listener, renderer, or encoder is launched.
// This executes the real adapter orchestration with deterministic test doubles.
const HERE=path.dirname(fileURLToPath(import.meta.url));
const current=await fs.readFile(path.join(HERE,'../../codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs'),'utf8');
const baseline=await fs.readFile(path.join(HERE,'capture_adapter_before.mjs.fixture'),'utf8');
const sha=x=>createHash('sha256').update(x).digest('hex');
const bounds={west:0,east:1,south:0,north:1};
const scene={timing:{total_frames:300,fps:30},metadata:{output:{width:1080,height:1920}},event_type:'WAR',scale_intent:{preferred:'REGIONAL'}};
const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:'a'.repeat(64),transitions:[],segments:[{startFrame:0,endFrame:300,scene,region:{},presentation:{}}]};
const prepared={sourceStyle:{styleId:'test',license:'TEST',sourceOriginal:{url:'https://example.invalid/test'},terrainAsset:{file:'/unused/test.png',url:'/terrain.png',sourceOriginalSHA256:'b'.repeat(64),sha256:'c'.repeat(64),bounds,dimensions:{width:1080,height:1920}}},regionEvidence:{sourceId:'test',sourceDimensions:{width:1080,height:1920},attribution:'TEST'},terrainTreatment:'test',nativePlan:{framing:{bounds},assets:{}},sourceBindings:[]};

async function run(source,{failEvaluate=null,failEncoder=false}={}){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'capture-diagnostic-focus-'));
 const output=path.join(root,'output'),input=path.join(root,'input.json'),bytes=JSON.stringify(request);
 await fs.writeFile(input,bytes,{mode:0o600});
 const original=Object.assign(new TypeError('page.evaluate: TypeError: Cannot read properties of undefined (reading \'private-token\')'),{testMarker:'same-object'});
 const calls={evaluate:0,encoderWrites:0,browserLaunches:0,close:0,serverClose:0,spawn:0},credit={};
 const page={on(){},async route(){},async goto(){},async evaluate(_callback,arg){
  calls.evaluate++;
  if(calls.evaluate===failEvaluate)throw original;
  if(calls.evaluate===1)return undefined;
  if(calls.evaluate===2)return{proof:{status:'PASS'},evidence:{backend:'TEST_DOUBLE'}};
  return{segmentIndex:0,localFrame:arg,diagnostic:{glError:0},initialized:null,rawSHA256:'d'.repeat(64),baseRawSHA256:'e'.repeat(64),nonBlackPixels:1080*1920,png:Buffer.from('TEST-DOUBLE-NOT-PNG').toString('base64')};
 }};
 const chromium={async launch(){calls.browserLaunches++;return{version:()=> 'TEST',async newPage(){return page;},async close(){calls.close++;}};}};
 const requireStub=name=>name==='playwright'?{chromium}:name==='playwright/package.json'?{version:'TEST'}:assert.fail(name);
 const imports={
  'node:fs/promises':fs,
  'node:path':{default:path},
  'node:url':{fileURLToPath},
  'node:crypto':{createHash},
  'node:module':{createRequire:()=>requireStub},
  'node:http':{createServer:()=>({once(){},listen(_port,_host,callback){callback();},address(){return{port:12345};},close(callback){calls.serverClose++;callback();}})},
  'node:child_process':{
   spawn(_program,args){calls.spawn++;const encoder=new EventEmitter();encoder.exitCode=null;encoder.stderr=new EventEmitter();encoder.stdin=new EventEmitter();encoder.stdin.write=()=>{if(failEncoder)throw original;calls.encoderWrites++;return true;};
    encoder.stdin.end=()=>{const file=args.at(-1);writeFileSync(file,'TEST-DOUBLE-NOT-MP4');credit.value=args.find(x=>x.startsWith('comment=')).slice(8);queueMicrotask(()=>{encoder.exitCode=0;encoder.emit('exit',0);});};
    encoder.kill=()=>{encoder.exitCode=-15;encoder.emit('exit',null,'SIGTERM');};return encoder;},
   execFile(program,_args,_options,callback){callback(null,program==='ffprobe'?JSON.stringify({streams:[{codec_type:'video',codec_name:'h264',width:1080,height:1920,r_frame_rate:'30/1',nb_read_frames:'300'}],format:{duration:'10',tags:{comment:credit.value,copyright:credit.value}}}):'', '');}
  },
  'node:util':{promisify},
  'node:events':{once},
  '../../web/map_infographic_v1/planner_scene_v1.mjs':{validateScenePlan:()=>true},
  '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs':{compileExistingEnginePlan:()=>({sourceGeometryBinding:{test:true}})},
  './region_source_vulkan.generated.mjs':{resolveRegionPlan:async()=>({baseCameraPlan:{test:true},nativePlan:prepared.nativePlan}),prepareRegionTerrain:async()=>structuredClone(prepared),verifyRegionQualification:async()=>({status:'PASS'}),canonicalJSON:JSON.stringify},
  '../universal-presentation-v2/presentation_plan.mjs':{compilePresentationCameraPlan:()=>({closestBounds:bounds,coverageBounds:bounds}),assertPresentationBoundaryContinuity:()=>true},
  './backend/profile_contract.mjs':{buildVulkanLaunchOptions:()=>({evidence:{test:true},options:{test:true}})},
  './backend/private_workspace.mjs':{createFreshPrivateDirectory:async p=>fs.mkdir(p,{recursive:true,mode:0o700})}
 };
 const fakeExec=imports['node:child_process'].execFile;
 fakeExec[promisify.custom]=(program,args,options)=>new Promise((resolve,reject)=>fakeExec(program,args,options,(error,stdout,stderr)=>error?reject(error):resolve({stdout,stderr})));
 const context=vm.createContext({Buffer,URL,structuredClone,performance,console,process:{env:{},getuid:process.getuid.bind(process),version:process.version,stdout:{write(){}}}});
 const module=new vm.SourceTextModule(source,{context,identifier:path.join(root,'adapter.mjs'),initializeImportMeta(meta){meta.url=new URL('file://'+path.join(root,'engine/recovery/capture/adapter.mjs')).href;}});
 await module.link(async name=>{const exported=imports[name];assert.ok(exported,`Unexpected import ${name}`);return new vm.SyntheticModule(Object.keys(exported),function(){for(const[k,v]of Object.entries(exported))this.setExport(k,v);},{context});});
 await module.evaluate();
 let thrown;
 try{await module.namespace.captureVulkanDerived({packageFile:input,outputRoot:output,expectedSHA256:sha(bytes),depsRoot:root,executionDeadline:Date.now()+60000,privateWorkspaceRoot:root,publicExportRoot:path.join(root,'public')});}catch(error){thrown=error;}
 const receipt=JSON.parse(await fs.readFile(path.join(output,'CAPTURE_RECEIPT.json'),'utf8'));
 await fs.rm(root,{recursive:true,force:true});
 return{thrown,original,receipt,calls};
}

let count=0;
for(const[call,stage,frame]of [[1,'PAGE_EVALUATE_RUNTIME_IMPORT',null],[2,'PAGE_EVALUATE_FIRST_NATIVE_DRAW',null],[3,'PAGE_EVALUATE_FRAME_CAPTURE',0]]){
 const result=await run(current,{failEvaluate:call});
 assert.equal(result.thrown,result.original,'diagnostics must rethrow the identical exception');
 assert.equal(result.receipt.failure.code,result.original.message);
 assert.equal(result.receipt.failure.diagnosticStage,stage);
 assert.equal(result.receipt.failure.frameIndex,frame);
 assert.equal(result.receipt.renderedFrames,0);
 assert.equal(result.calls.evaluate,call);
 assert.equal(result.calls.close,1);
 console.log(`PASS ${++count}: ${stage} preserves first error and cleanup`);
}
{
 const result=await run(current,{failEncoder:true});
 assert.equal(result.thrown,result.original);
 assert.equal(result.receipt.failure.diagnosticStage,null);
 assert.equal(result.receipt.failure.frameIndex,null);
 assert.equal(result.calls.evaluate,3);
 console.log(`PASS ${++count}: successful evaluate does not taint subsequent encoder failure stage`);
}
{
 const before=await run(baseline),after=await run(current);
 assert.equal(before.thrown,undefined);assert.equal(after.thrown,undefined);
 assert.deepEqual(after.calls,before.calls);
 assert.equal(after.calls.evaluate,302);
 assert.equal(after.calls.encoderWrites,300);
 const stable=r=>{const x=structuredClone(r);delete x.startedAt;delete x.finishedAt;delete x.elapsedSeconds;return x;};
 assert.deepEqual(stable(after.receipt),stable(before.receipt));
 console.log(`PASS ${++count}: unchanged success receipt and call order versus pinned baseline (synthetic only)`);
}
console.log(JSON.stringify({status:'PASS',tests:count,gpuStarts:0,realFramesRendered:0,browserStarts:0,networkListeners:0}));
