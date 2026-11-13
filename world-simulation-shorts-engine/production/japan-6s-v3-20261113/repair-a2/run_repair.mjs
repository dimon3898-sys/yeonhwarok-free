import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {capturePresentation} from '../../../recovery/universal-presentation-v2/capture_presentation.mjs';
const p=new URL('./',import.meta.url),mode=process.argv[2];assert.ok(['probe','final'].includes(mode));
const hash=b=>createHash('sha256').update(b).digest('hex');
const tests=JSON.parse(await fs.readFile(new URL('REPAIR_TEST_RESOLUTION.json',p)));assert.equal(tests.status,'PASS');
const compiled=JSON.parse(await fs.readFile(new URL('COMPILE_RESULT.json',p)));assert.equal(compiled.status,'PASS');
const request=await fs.readFile(new URL('RUNTIME_REQUEST.json',p));assert.equal(hash(request),'a359d05550c562cd4bd6ce7feb632a0f07c34beda0d03112eec88819f1b34166');
if(mode==='final'){const gate=JSON.parse(await fs.readFile(new URL('PROBE_VISUAL_REVIEW.json',p)));assert.equal(gate.status,'PASS_FOR_FULL_CPU_CAPTURE');assert.equal(gate.runtimeSHA256,hash(request));}
const receipt=await capturePresentation({packageFile:new URL('RUNTIME_REQUEST.json',p).pathname,outputRoot:'/workspace/japan6s-v3-effects-'+mode+'-a2',expectedSHA256:hash(request),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:mode==='probe'?[9,15,60,90,96,120,135,143,149,150,179]:null});
console.log(JSON.stringify({status:receipt.status,video:receipt.video,backend:receipt.runtime.backend}));
