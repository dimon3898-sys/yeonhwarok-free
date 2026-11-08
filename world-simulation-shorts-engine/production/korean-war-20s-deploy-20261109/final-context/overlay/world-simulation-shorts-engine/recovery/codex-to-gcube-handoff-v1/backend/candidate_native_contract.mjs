/** Pure plan transport checks; no authority issuance, process start or rendering. */
import {createHash} from 'node:crypto';
import {sealSceneChunks,verifySceneChunk} from '../../official-candidate-v1/sealed_scene_chunks.mjs';
const hash=x=>createHash('sha256').update(x).digest('hex');
export const canonical=v=>JSON.stringify(v,(_k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
const check=(v,c)=>{if(!v)throw Error(c)};
export function validateNativeCandidateBinding(plan){
 const input=structuredClone(plan),binding=input.nativeCandidate;
 if(binding===undefined){check(input.nativeCandidateSHA256===undefined,'HANDOFF_CANDIDATE_ORPHAN_PIN');return null;}
 check(input.totalFrames===300&&input.durationSeconds===10&&binding.schema==='WORLD_ENGINE_NATIVE_CANDIDATE_BINDING_V1','HANDOFF_CANDIDATE_SCOPE');
 check(Object.keys(binding).sort().join(',')==='activation,activationSHA256,chunkCaptureWires,schema','HANDOFF_CANDIDATE_BINDING_FIELDS');
 check(hash(canonical(binding))===input.nativeCandidateSHA256,'HANDOFF_CANDIDATE_BINDING_PIN');
 check(typeof input.runtimeWireJSON==='string'&&hash(input.runtimeWireJSON)===input.runtimeWireSHA256&&canonical(JSON.parse(input.runtimeWireJSON))===canonical(input.runtime),'HANDOFF_CANDIDATE_RUNTIME_PIN');
 const chunks=sealSceneChunks(JSON.parse(input.runtimeWireJSON)),a=binding.activation,q=input.sourceQualification;
 check(a?.schema==='WORLD_ENGINE_OFFICIAL_CANDIDATE_ACTIVATION_V1'&&a.mode==='CPU_QUALIFIED_GPU_PENDING'&&a.productionAdmitted===false&&hash(canonical(a))===binding.activationSHA256,'HANDOFF_CANDIDATE_ACTIVATION_PIN');
 check(a.originalSemanticSHA256===chunks.originalSHA256&&a.aggregateQualificationSHA256===input.sourceQualificationSHA256,'HANDOFF_CANDIDATE_AGGREGATE_PIN');
 check(q?.schema==='WORLD_ENGINE_PRESENTATION_TIMELINE_SOURCES_V1'&&q.totalFrames===300&&q.originalSHA256===chunks.originalSHA256,'HANDOFF_CANDIDATE_QUALIFICATION');
 check(typeof input.sourceQualificationWireJSON==='string'&&hash(input.sourceQualificationWireJSON)===input.sourceQualificationSHA256&&canonical(JSON.parse(input.sourceQualificationWireJSON))===canonical(q),'HANDOFF_CANDIDATE_QUALIFICATION_WIRE');
 check(Array.isArray(binding.chunkCaptureWires)&&Array.isArray(q.chunks)&&Array.isArray(a.chunks),'HANDOFF_CANDIDATE_CHUNK_ARRAYS');
 check(binding.chunkCaptureWires.length===chunks.chunks.length&&q.chunks.length===chunks.chunks.length&&a.chunks.length===chunks.chunks.length,'HANDOFF_CANDIDATE_CHUNK_COUNT');
 const rows=chunks.chunks.map((chunk,index)=>{
  verifySceneChunk(chunks,chunk,chunks.originalSHA256);
  check(chunk.request.segments.length===1,'HANDOFF_CANDIDATE_ONE_SCENE_PER_CHUNK');
  const wire=binding.chunkCaptureWires[index];check(typeof wire.wireJSON==='string'&&hash(wire.wireJSON)===wire.wireSHA256&&wire.chunkRequestSHA256===chunk.requestSHA256,'HANDOFF_CANDIDATE_CHUNK_WIRE');
  const envelope=JSON.parse(wire.wireJSON);
  check(envelope.schema==='WORLD_ENGINE_OFFICIAL_SCENE_CHUNK_CAPTURE_V1'&&canonical(envelope.plan)===canonical(chunks)&&canonical(envelope.chunk)===canonical(chunk),'HANDOFF_CANDIDATE_CHUNK_PLAN');
  check(canonical(envelope.candidateActivation)===canonical(a)&&envelope.candidateActivationSHA256===binding.activationSHA256,'HANDOFF_CANDIDATE_CHUNK_ACTIVATION');
  const qualification=q.chunks[index],selected=a.chunks[index];
  check(qualification.index===index&&canonical(qualification.globalRange)===canonical(chunk.globalRange)&&qualification.requestSHA256===chunk.requestSHA256&&selected.chunkRequestSHA256===chunk.requestSHA256&&selected.nativeSourceQualificationSHA256===qualification.sourceQualificationSHA256,'HANDOFF_CANDIDATE_CHUNK_ORDER');
  return{chunk,qualification,activation:a,activationSHA256:binding.activationSHA256};
 });
 return{plan:chunks,rows,bindingSHA256:input.nativeCandidateSHA256};
}
