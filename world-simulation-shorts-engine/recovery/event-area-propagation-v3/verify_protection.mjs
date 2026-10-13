/** One focused native-extension OFF comparison, not the user-approval Permanent Gate. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {openAreaRuntime,root,repo,json} from './area_runtime.mjs';
const execute=promisify(execFile),parent='fbc3be89d94040271c7f54a051162913ad134bac';
assert.equal((await json(path.join(root,'evidence/proof/REPORT.json'))).status,'PASS');
const original=(await execute('git',['ls-tree','-r','--name-only',parent],{cwd:repo,maxBuffer:16*1024*1024})).stdout.trim().split('\n');
const originalSet=new Set(original);
const changed=(await execute('git',['diff','--name-only',parent],{cwd:repo})).stdout.trim().split('\n').filter(p=>originalSet.has(p));
assert.deepEqual(changed,[],'FROZEN_PARENT_FILES_CHANGED');
const beforeManifest=await execute('git',['show',parent+':world-simulation-shorts-engine/recovery/event-flow-v2-final/FINAL_MANIFEST.json'],{cwd:repo});
assert.equal(beforeManifest.stdout,await readFile(path.join(repo,'world-simulation-shorts-engine/recovery/event-flow-v2-final/FINAL_MANIFEST.json'),'utf8'));
const session=await openAreaRuntime({fixtureFile:path.join(root,'fixtures/synthetic-a.json')});
let receipt;
try{
 receipt=await session.page.evaluate(async()=>{
  window.areaProof.dispose();
  const {createAreaNativeBridge}=await import('/modules/area_native_bridge_v3.mjs');
  const {createV5CameraGpuPipeline}=await import('/modules/camera_gpu_pipeline_v5.mjs');
  const load=async p=>(await fetch(p)).json();
  const [REGIONAL,CONTINENT,scene,cameraPlan,input]=await Promise.all([load('/inputs/regional.json'),load('/inputs/continent.json'),load('/inputs/scene.json'),load('/inputs/camera-plan.json'),load('/inputs/input-manifest.json')]);
  const canvases=[0,1].map(()=>{const c=document.createElement('canvas');c.width=1080;c.height=1920;document.body.appendChild(c);return c;});
  const options={plans:{REGIONAL,CONTINENT},scene,cameraPlan,heightSource:input.heightSource,contextTerrain:input.contextTerrain};
  const bridge=await createAreaNativeBridge({...options,canvas:canvases[0]});
  const baseline=await createV5CameraGpuPipeline({...options,canvas:canvases[1]});
  const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
  const frames=[];
  try{
   for(const frame of [0,120,249]){
    bridge.drawNative(frame);baseline.drawFrame(frame);
    const a=bridge.readPixels(),b=baseline.readPixels();let changedPixels=0;
    const av=new Uint32Array(a.buffer,a.byteOffset,a.byteLength/4),bv=new Uint32Array(b.buffer,b.byteOffset,b.byteLength/4);
    for(let i=0;i<av.length;i++)if(av[i]!==bv[i])changedPixels++;
    frames.push({frame,changedPixels,bridgeRgbaSha256:await digest(a),frozenV5RgbaSha256:await digest(b)});
   }
  }finally{bridge.dispose();baseline.dispose();}
  return{frames,status:frames.every(row=>row.changedPixels===0)?'PASS':'FAIL',scope:'SAMPLED_ACTUAL_FROZEN_V5_NATIVE_PIPELINE_NOT_FULL_250_FRAME_GATE'};
 });
 assert.equal(receipt.status,'PASS');assert.equal(session.errors.length,0);
}finally{await session.close();}
const sourceFiles=(await execute('git',['ls-files','world-simulation-shorts-engine/web/map_infographic_v1/area_*.mjs'],{cwd:repo})).stdout.trim().split('\n');
const forbidden=[];
for(const file of sourceFiles){const source=await readFile(path.join(repo,file),'utf8');if(/suez|egypt|tohoku|tsunami|COUNTRY_JPN|142\.373|193\.30/iu.test(source))forbidden.push(file);}
assert.deepEqual(forbidden,[],'EVENT_SPECIFIC_ENGINE_BRANCH');
const proof=await json(path.join(root,'evidence/proof/REPORT.json'));
assert.equal(proof.frames.length,proof.totalFrames);
const timelineStates=proof.frames.filter(row=>row.area.controls).map(row=>row.area.controls.stateId);
assert.equal(timelineStates.at(-1),'HOLD');
for(const row of proof.frames){assert.equal(row.glError,0);if(row.area.enabled)assert.equal(row.cameraLocked,true);}
const report={schema:1,status:'PASS',protectedParentCommit:parent,protectedTrackedFiles:original.length,changedOriginalPaths:[],
 camera:'SOURCE_UNCHANGED_AND_NATIVE_OFF_SAMPLE_BIT_EXACT',eventV1:'SOURCE_UNCHANGED',flowV2:'SOURCE_UNCHANGED',layout:'SOURCE_UNCHANGED',
 marker:'SOURCE_DESIGN_UNCHANGED_AND_ALL_PROOF_PIXEL_PROTECTION_PASS',geometry:'SUPPLIED_GEOMETRY_IMMUTABLE',
 nativeOff:receipt,eventOnFrames:proof.protection.eventOnFrames,allFramePixelProtection:proof.protection,
 geographicHardcodeFiles:forbidden,permanentGateExecuted:false};
await writeFile(path.join(root,'evidence/PROTECTION.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:report.status,parentFiles:original.length,nativeOff:receipt.status,samples:receipt.frames.map(row=>row.frame)}));
