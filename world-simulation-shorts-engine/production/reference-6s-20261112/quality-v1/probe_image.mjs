// Executed inside the candidate image without GPU, network, or renderer startup.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root='/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/';
const e=root+'world-simulation-shorts-engine/';
const plan=JSON.parse(fs.readFileSync(0,'utf8'));
const verified=[];
for(const row of plan.files){
 const file=root+row.path,stat=fs.lstatSync(file),raw=fs.readFileSync(file);
 assert.ok(stat.isFile()&&!stat.isSymbolicLink()&&!(stat.mode&0o022));
 assert.equal(raw.length,row.bytes);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),row.sha256);
 verified.push(row.path);
}
const bindings=['boundaryTrace:p.mapStyle?.boundaryTrace',':visualPlan,project,frame:displayFrame','boundaryTrace:copy(factory.evidence.boundaryTrace??null)'];
for(const file of ['recovery/universal-presentation-v2/presentation_runtime.mjs','recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs']){
 const code=fs.readFileSync(e+file,'utf8');for(const binding of bindings)assert.ok(code.includes(binding),file+':'+binding);
}
const {verifyGeneratedSources}=await import(e+'recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs');
const variants=await verifyGeneratedSources();
const {compileBoundaryTrace,evaluateBoundaryTrace,boundaryTraceFraction}=await import(e+'web/map_infographic_v1/boundary_trace_v1.mjs');
const input=JSON.parse(fs.readFileSync(e+'production/reference-6s-20261112/quality-v1/REFERENCE_6S_QUALITY_INPUT.json'));
const spec=input.presentation.mapStyle.boundaryTrace;
const primitive=compileBoundaryTrace({id:'COUNTRY_PROBE',type:'Polygon',coordinates:[[[0,0],[2,0],[2,2],[0,2],[0,0]]]},x=>x,spec);
assert.equal(evaluateBoundaryTrace(primitive,0).length,0);
assert.equal(evaluateBoundaryTrace(primitive,.5)[0].closed,false);
assert.equal(evaluateBoundaryTrace(primitive,1)[0].closed,true);
assert.equal(boundaryTraceFraction(spec,179),1);
assert.deepEqual(input.presentation.camera.frames[149],input.presentation.camera.frames[179]);
console.log(JSON.stringify({status:'PASS_ACTUAL_IMAGE_QUALITY_BINDINGS',verified,variants,boundaryModuleExecuted:true,CPUAndNvidiaRoutesConnected:true,cameraCandidateSealed:true,oldPassReruns:0,GPUExecutions:0,actualNvidiaRenderVerified:false},null,2));
