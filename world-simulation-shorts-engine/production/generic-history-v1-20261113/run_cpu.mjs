import fs from 'node:fs/promises';import {createHash} from 'node:crypto';import assert from 'node:assert/strict';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),mode=process.argv[2];assert.ok(['probe','final'].includes(mode));
const hash=b=>createHash('sha256').update(b).digest('hex'),read=async n=>JSON.parse(await fs.readFile(new URL(n,base)));
for(const name of ['TIME','STATE','SOURCE','WIDE','TOPOLOGY','DIRECTION','FIRST_STATE'])assert.equal((await read('evidence/'+name+'_TESTS.json')).status,'PASS');
const compiled=await read('evidence/AUTOMATIC_COMPILE_RESULT.json');assert.equal(compiled.status,'PASS');
const raw=await fs.readFile(new URL('RUNTIME_REQUEST.json',base)),request=JSON.parse(raw);assert.equal(request.sourceInputSHA256,compiled.inputSHA256);
assert.deepEqual(request.segments,compiled.renderRequests);assert.equal(request.totalFrames,180);
if(mode==='final'){const gate=await read('PROBE_VISUAL_REVIEW.json');assert.equal(gate.status,'PASS_FOR_FULL_CPU_CAPTURE');assert.equal(gate.runtimeSHA256,hash(raw));}
const out='/workspace/history6s-'+mode+'-a5';
try{const receipt=await capturePresentation({packageFile:new URL('RUNTIME_REQUEST.json',base).pathname,outputRoot:out,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:mode==='probe'?[0,22,30,38,54,70,86,102,118,134,150,179]:null});console.log(JSON.stringify({status:receipt.status,video:receipt.video,backend:receipt.runtime.backend}));}
catch(error){await fs.mkdir(out,{recursive:true});await fs.writeFile(out+'/TASK_FAILURE.json',JSON.stringify({status:'BLOCKED',code:error.message,stack:error.stack,gpuStarts:0},null,2)+'\n');throw error;}
