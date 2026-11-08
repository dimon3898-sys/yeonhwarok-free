// Synthetic sequencing tests only. No browser, WebGL context, renderer or GPU.
import assert from 'node:assert/strict';
import {runThreeNativeDraws} from './native_guard_candidate.mjs';
const pixels=new Uint8Array(1080*1920*4).fill(1);
function fixture(){
 const events=[];let ready=false;
 const gl={getExtension:()=>({UNMASKED_RENDERER_WEBGL:1}),getParameter:()=> 'NVIDIA synthetic fixture Vulkan',getError:()=>0};
 const canvas={width:1080,height:1920,getContext:()=>{events.push('context');return gl;}};
 const runtime={
  async prepareFrame(frame){assert.equal(frame,0);events.push('prepare-start');await Promise.resolve();ready=true;events.push('prepare-finish');},
  drawFrame(frame){assert(ready);events.push('draw');return{glError:0,backend:'NVIDIA synthetic fixture Vulkan'};},
  readPixels(){events.push('read');return pixels;},
  recordNativeStability(){events.push('record');}
 };
 return {events,canvas,runtime,legacyReady(){ready=true;}};
}
const results=[];
{
 const f=fixture();await runThreeNativeDraws(f);
 assert.deepEqual(f.events,['prepare-start','prepare-finish','context','draw','read','draw','read','draw','read','record']);
 results.push({name:'await_preparation_before_native_proof',status:'PASS'});
}
{
 const f=fixture();f.runtime.prepareFrame=async()=>{f.events.push('failed-prepare');throw Error('synthetic preparation failure');};
 await assert.rejects(runThreeNativeDraws(f),/synthetic preparation failure/);
 assert.deepEqual(f.events,['failed-prepare']);
 results.push({name:'preparation_failure_prevents_context_and_draw',status:'PASS'});
}
{
 const f=fixture();delete f.runtime.prepareFrame;f.legacyReady();await runThreeNativeDraws(f);
 assert.deepEqual(f.events,['context','draw','read','draw','read','draw','read','record']);
 results.push({name:'optional_hook_preserves_unconfigured_call_order',status:'PASS'});
}
console.log(JSON.stringify({status:'PASS_SYNTHETIC_SEQUENCING_ONLY',tests:results,gpuExecuted:false,browserStarted:false}));
