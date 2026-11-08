import assert from 'node:assert/strict';import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';import {pathToFileURL} from 'node:url';
const {validateNativeCandidateBinding}=await import(pathToFileURL(path.resolve(process.argv[2],'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/candidate_native_contract.mjs')));
const plan=JSON.parse(await readFile(path.resolve(process.argv[3]))).videoPlan;
const cases=[
 ['ORPHAN_PIN',p=>{delete p.nativeCandidate},'HANDOFF_CANDIDATE_ORPHAN_PIN'],
 ['SHORTER_FRAME_BUDGET',p=>{p.totalFrames=180},'HANDOFF_CANDIDATE_SCOPE'],
 ['UNKNOWN_BINDING_FIELD',p=>{p.nativeCandidate.untrusted=true},'HANDOFF_CANDIDATE_BINDING_FIELDS'],
 ['ACTIVATION_MUTATION',p=>{p.nativeCandidate.activation.registrySHA256='0'.repeat(64)},'HANDOFF_CANDIDATE_BINDING_PIN'],
 ['CHUNK_WIRE_MUTATION',p=>{p.nativeCandidate.chunkCaptureWires[0].wireJSON+=' '},'HANDOFF_CANDIDATE_BINDING_PIN'],
 ['RUNTIME_WIRE_MUTATION',p=>{p.runtimeWireJSON+=' '},'HANDOFF_CANDIDATE_RUNTIME_PIN'],
 ['RUNTIME_OBJECT_MUTATION',p=>{p.runtime.totalFrames=299},'HANDOFF_CANDIDATE_RUNTIME_PIN']
];
const checks=[];
for(const [name,change,code]of cases){const p=structuredClone(plan);change(p);assert.throws(()=>validateNativeCandidateBinding(p),new RegExp('^Error: '+code+'$'));checks.push(name);}
assert.equal(validateNativeCandidateBinding({totalFrames:180}),null);checks.push('LEGACY_NO_CANDIDATE_DELEGATES');
const result={schema:'WORLD_ENGINE_NATIVE_BINDING_TEST_V1',status:'PASS',newChecks:checks.length,checks,source:'FIRST_ACTUAL_CONTROLLER_NORMALIZATION',rendererExecuted:false,gpuExecuted:false};
await writeFile(path.resolve(process.argv[4],'NATIVE_BINDING_RESULT.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
