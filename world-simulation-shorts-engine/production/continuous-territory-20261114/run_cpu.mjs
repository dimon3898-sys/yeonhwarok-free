import fs from 'node:fs/promises';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),mode=process.argv[2],attempt=process.argv[3],read=async n=>JSON.parse(await fs.readFile(new URL(n,base))),hash=b=>createHash('sha256').update(b).digest('hex');
assert.ok(['probe','final'].includes(mode));assert.match(attempt,/^a[1-9][0-9]*$/);
for(const n of ['MODEL_TESTS','GEOMETRY_TESTS','FRAME_GEOMETRY_GATE','STATIC_CHECKS'])assert.equal((await read('evidence/'+n+'.json')).status,'PASS');
const raw=await fs.readFile(new URL('RUNTIME_REQUEST.json',base)),r=JSON.parse(raw),model=await read('evidence/MODEL_TESTS.json');assert.equal(model.runtimeSHA256,hash(raw));
const event=r.segments[0].presentation.territoryChanges.items[0];
if(mode==='final'){const gate=await read('PROBE_VISUAL_REVIEW.json');assert.equal(gate.status,'PASS_FOR_NEW_FULL_CPU_CAPTURE');assert.equal(gate.runtimeSHA256,hash(raw));assert.equal(gate.consecutiveFrames,30);assert.equal(gate.actualBoundaryMotionVerified,true);}
const consecutive=Array.from({length:30},(_,i)=>event.startFrame+30+i),probeFrames=[...new Set([0,event.startFrame,...consecutive,Math.floor((event.startFrame+event.endFrame)/2),event.endFrame-1,179])].sort((a,b)=>a-b);
const outputRoot='/workspace/continuous-'+mode+'-'+attempt;
try{const receipt=await capturePresentation({packageFile:new URL('RUNTIME_REQUEST.json',base).pathname,outputRoot,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:mode==='probe'?probeFrames:null});console.log(JSON.stringify({status:receipt.status,video:receipt.video,backend:receipt.runtime.backend,probeFrames:mode==='probe'?probeFrames:null}));}
catch(error){await fs.mkdir(outputRoot,{recursive:true});await fs.writeFile(outputRoot+'/TASK_FAILURE.json',JSON.stringify({status:'BLOCKED',error:error.message,stack:error.stack,firstIncomplete:mode==='probe'?'CONTINUOUS_30_ACTUAL_FRAMES':'NEW_FINAL_CAPTURE',gpuStarts:0},null,2)+'\n');throw error;}
