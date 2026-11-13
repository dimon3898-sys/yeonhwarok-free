import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),mode=process.argv[2],attempt=process.argv[3];
assert.ok(['probe','final'].includes(mode));assert.match(attempt,/^a[1-9][0-9]*$/);
const read=async n=>JSON.parse(await fs.readFile(new URL(n,base))),hash=b=>createHash('sha256').update(b).digest('hex');
for(const name of ['DELTA_TESTS','SCHEMA_DELTA','STATIC_CHECKS'])assert.equal((await read('evidence/'+name+'.json')).status,'PASS');
const compiled=await read('evidence/COMPILE_RESULT.json');assert.equal(compiled.status,'PASS');
const raw=await fs.readFile(new URL('RUNTIME_REQUEST.json',base)),request=JSON.parse(raw);
assert.equal(request.sourceInputSHA256,compiled.inputSHA256);assert.deepEqual(request.segments,compiled.renderRequests);
assert.equal(request.segments[0].automaticDirection.profile,'HISTORICAL_STATES_V2');
if(mode==='final'){const gate=await read('PROBE_VISUAL_REVIEW.json');assert.equal(gate.status,'PASS_FOR_FULL_CPU_CAPTURE');assert.equal(gate.runtimeSHA256,hash(raw));}
const keys=request.segments[0].automaticDirection.cameraKeys.map(k=>k.frame),items=request.segments[0].presentation.territoryChanges.items;
const probeFrames=[...new Set([0,20,...keys,...items.map(e=>Math.floor((e.startFrame+e.endFrame-1)/2)),147,179])].sort((a,b)=>a-b);
const outputRoot='/workspace/director-v2-'+mode+'-'+attempt;
try{const receipt=await capturePresentation({packageFile:new URL('RUNTIME_REQUEST.json',base).pathname,outputRoot,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:mode==='probe'?probeFrames:null});console.log(JSON.stringify({status:receipt.status,video:receipt.video,backend:receipt.runtime.backend,probeFrames:mode==='probe'?probeFrames:null}));}
catch(error){await fs.mkdir(outputRoot,{recursive:true});await fs.writeFile(outputRoot+'/TASK_FAILURE.json',JSON.stringify({status:'BLOCKED',error:error.message,stack:error.stack,firstIncomplete:mode==='probe'?'V2_REPRESENTATIVE_CAPTURE':'V2_FINAL_CAPTURE',gpuStarts:0},null,2)+'\n');throw error;}
