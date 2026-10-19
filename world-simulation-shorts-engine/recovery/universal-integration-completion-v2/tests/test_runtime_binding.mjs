import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {suppliedFrontObservations} from '../source_observations.mjs';
import {extendCompletionServerPlan,COMPLETION_BROWSER_BINDINGS} from '../runtime_binding.mjs';
import {resolveCapture} from '../long_capture.mjs';
import {selectCompletionParentInputs} from '../capture_runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),parent=path.join(root,'../universal-integration-v1'),
 hash=v=>createHash('sha256').update(v).digest('hex'),
 read=name=>JSON.parse(readFileSync(path.join(root,'../verified-front-data-v4-recovery',name))),
 plan=read('VIDEO_PLAN_80S.json'),front=read('FRONT_PROFILE.json'),
 completion={schema:'WORLD_ENGINE_UNIVERSAL_COMPLETION_V2',profile:'VISUAL_UNIFIED_COMPLETION_V2',
  dataPolicy:'QUALIFIED_SOURCE_ONLY',camera:{mode:'V5_EVENT_TRACKING',settleFrames:18,holdFrames:24},
  frontier:{profile:'AUTHORED_FRONT_MOTION_V2',enabled:true,motionResponse:true,settledStrength:.2,settleFrames:18},
  eventFlow:{schema:'WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1',events:[],flows:[],areas:[]}},
 catalog={trustedSources:[]},hex='a'.repeat(64),
 records=directory=>readdirSync(directory).filter(name=>/\.(mjs|py|json)$/.test(name)).map(name=>{
  const file=path.join(directory,name),bytes=readFileSync(file);return{name,file,bytes:bytes.length,sha256:hash(bytes)};}),
 inherited={sourceSignature:hex,sourceBindings:[],serverConfig:{runtimeConfig:{frontV4:{runtimeProfile:'VERIFIED_ARCHIVAL_FRONT_V4'}},
  bindings:['/production-v3/production_area_pass.mjs','/production-v3/production_native_camera.mjs','/universal/long_adapter.mjs']
   .map(url=>({url,path:'/preserved/'+path.basename(url),bytes:1,sha256:hex}))}};
function bind(){return extendCompletionServerPlan(inherited,{visualProfile:{},completion,previousRecords:records(parent),
 previousManifestSha256:hex,records:records(root),manifestSha256:hex,sourceCatalog:catalog,plan,frontProfile:front});}
test('exact real 2400-frame source evaluator produces supplied geometry only',()=>{
 const before=JSON.stringify({plan,front}),observations=suppliedFrontObservations(plan,front);
 assert.equal(observations.length,2400);assert.equal(observations[0].fronts.length,0);
 assert.ok(observations.slice(1550).every(row=>row.fronts.every(f=>f.id.includes('-part-'))));
 assert.equal(JSON.stringify({plan,front}),before);
});
test('all new browser aliases reach real files while prior owners remain reachable',()=>{
 const result=bind(),map=new Map(result.serverConfig.bindings.map(row=>[row.url,row]));
 for(const[url,name]of Object.entries(COMPLETION_BROWSER_BINDINGS))assert.equal(map.get(url).path,path.join(root,name));
 assert.ok(map.has('/completion-v2/parent_adapter.mjs'));assert.ok(map.has('/completion-v2/parent_camera.mjs'));
 assert.ok(result.serverConfig.runtimeConfig.completionFrontierMotion.fronts);
 assert.equal(inherited.serverConfig.runtimeConfig.completionV2,undefined);
});
test('source profile is bound and changes capture signature without editing parent',()=>{
 const a=bind(),b=bind();assert.equal(a.sourceSignature,b.sourceSignature);
 assert.equal(a.completionV2.camera.mode,'V5_EVENT_TRACKING');assert.equal(a.sourceSelectionCPUOnly,true);
 assert.equal(a.completionIntegrity.actualGPUOutputVerified,false);
});
test('unknown source or completion profile cannot silently fall back',()=>{
 assert.throws(()=>extendCompletionServerPlan(inherited,{completion:{schema:'WRONG'},manifestSha256:hex}));
 assert.throws(()=>extendCompletionServerPlan(inherited,{completion,manifestSha256:hex,records:[],previousRecords:records(parent),previousManifestSha256:hex}));
});
test('Node encoder import substitution is restricted to exact preserved entry',()=>{
 let called=false;
 const next=()=>{called=true;return{url:'unchanged'};};
 assert.deepEqual(resolveCapture('./unrelated.mjs',{parentURL:'x'},next),{url:'unchanged'});assert.ok(called);
 const source=readFileSync(path.join(root,'long_capture.mjs'),'utf8');
 assert.ok(source.includes("process.version,'v24.19.0'"));
 assert.ok(source.includes("specifier==='./long_runtime.mjs'"));
});
test('real frozen loader document property reaches the completion source evaluator',()=>{
 const raw=readFileSync(path.join(root,'../universal-auto-video-v2/long_runtime.mjs'),'utf8');
 assert.ok(raw.includes('document,scene')); // preserved owner exports document, not plan
 const inherited={document:plan,frontProfile:front},selected=selectCompletionParentInputs(inherited);
 assert.equal(selected.plan,plan);assert.equal(selected.frontProfile,front);
 assert.equal(suppliedFrontObservations(selected.plan,selected.frontProfile).length,2400);
 assert.throws(()=>selectCompletionParentInputs({plan,frontProfile:front}),/ACTUAL_PARENT_DOCUMENT/);
});
