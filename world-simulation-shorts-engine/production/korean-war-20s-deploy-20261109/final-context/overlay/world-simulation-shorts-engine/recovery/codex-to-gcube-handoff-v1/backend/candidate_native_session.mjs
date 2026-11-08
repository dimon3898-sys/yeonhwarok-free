/** Existing official issuer/session used by the normal NVIDIA controller/worker. */
import path from 'node:path';
import {readFile,lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {readPinnedServerFile} from '../../official-candidate-v1/candidate_asset_snapshot.mjs';
import {sealSceneChunks} from '../../official-candidate-v1/sealed_scene_chunks.mjs';
import {prepareOfficialCandidateSession} from '../../official-candidate-v1/official_candidate_session.mjs';
import {selectSealedOfficialCandidate} from '../../official-candidate-v1/official_candidate_activation.mjs';
import {validateNativeCandidateBinding,canonical} from './candidate_native_contract.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex'),check=(v,c)=>{if(!v)throw Error(c)};
export async function nativeResourcePins(){return[
 {url:'/recovery/universal-presentation-v2/presentation_runtime.mjs',sha256:hash(await readFile(new URL('../../official-candidate-v1/presentation_runtime_nvidia.generated.mjs',import.meta.url)))},
 {url:'/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs',sha256:hash(await readFile(new URL('./native_guard_candidate.mjs',import.meta.url)))}
 ];}
async function assertNativeResources(record){
 for(const expected of await nativeResourcePins()){
  const rows=record.resources.filter(r=>r.url===expected.url);check(rows.length===1&&rows[0].kind==='module'&&rows[0].pin.sha256===expected.sha256,'HANDOFF_CANDIDATE_NATIVE_RESOURCE_PIN');
 }
}
async function configuredRegistry(){
 const file=process.env.WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE,pin=process.env.WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256;
 check(typeof file==='string'&&path.isAbsolute(file)&&/^[a-f0-9]{64}$/.test(pin??''),'HANDOFF_CANDIDATE_SERVER_CONFIG');
 const stat=await lstat(file);check(stat.size<=24*1024**2,'HANDOFF_CANDIDATE_REGISTRY_CAP');
 const raw=await readPinnedServerFile(path.dirname(file),path.basename(file),{bytes:stat.size,sha256:pin}),data=JSON.parse(raw);
 check(data.schema==='WORLD_ENGINE_OFFICIAL_SERVER_REGISTRY_V1'&&data.mode==='CPU_QUALIFIED_GPU_PENDING'&&data.productionAdmitted===false,'HANDOFF_CANDIDATE_REGISTRY_SCHEMA');
 return{data,pin};
}
export async function prepareNativeCandidateAdmission({request}={}){
 const plan=sealSceneChunks(structuredClone(request));check(plan.original.totalFrames===300&&plan.original.durationSeconds===10,'HANDOFF_CANDIDATE_300_ONLY');
 const{data}=await configuredRegistry();let qualification,wire,qualificationSHA;const credits=[];
 for(const chunk of plan.chunks){
  const rows=data.registrations.filter(r=>r.record.originalSemanticSHA256===plan.originalSHA256&&r.record.chunkRequestSHA256===chunk.requestSHA256);
  check(rows.length===1,'HANDOFF_CANDIDATE_SCENE_NOT_REGISTERED');const row=rows[0],r=row.record;
  check(canonical(r.proof.continuity.plan)===canonical(plan)&&canonical(r.proof.continuity.chunk)===canonical(chunk),'HANDOFF_CANDIDATE_COMPILED_PLAN_CHANGED');
  await assertNativeResources(r);
  const session=await prepareOfficialCandidateSession({registrationId:row.id,registry:new Map([[row.id,r]]),assetRegistry:new Map(data.assetRegistryEntries)});
  try{
   const q=r.proof.aggregateQualification,w=r.proof.aggregateQualificationWireJSON;
   check(qualificationSHA===undefined||qualificationSHA===r.aggregateQualificationSHA256,'HANDOFF_CANDIDATE_AGGREGATE_CHANGED');
   qualification=q;wire=w;qualificationSHA=r.aggregateQualificationSHA256;
   for(const s of session.payload.segments)credits.push({sourceId:s.regionEvidence?.sourceId,attribution:s.regionEvidence?.attribution,license:s.regionEvidence?.license,sourceURL:s.sourceStyle?.sourceOriginal?.url});
  }finally{session.close();}
 }
 check(hash(wire)===qualificationSHA&&canonical(JSON.parse(wire))===canonical(qualification),'HANDOFF_CANDIDATE_QUALIFICATION_PIN');
 return{status:'PASS',sourceQualification:qualification,sourceQualificationWireJSON:wire,sourceQualificationSHA256:qualificationSHA,preparedBeforeClaim:true,actualDrawPerformed:false,candidateSourceAdmitted:false,chunkPlan:plan,sourceCredits:credits};
}
export async function createNativeCandidateSessions(plan){
 const binding=validateNativeCandidateBinding(plan);if(binding===null)return null;
 const{data,pin}=await configuredRegistry();
 check(pin===plan.nativeCandidate.activation.registrySHA256,'HANDOFF_CANDIDATE_REGISTRY_CHANGED');
 const segments=binding.rows.map(row=>{
  const matches=data.registrations.filter(r=>r.record.originalSemanticSHA256===binding.plan.originalSHA256&&r.record.chunkRequestSHA256===row.chunk.requestSHA256);
  check(matches.length===1,'HANDOFF_CANDIDATE_SCENE_NOT_REGISTERED');const record=matches[0].record;
  check(record.payload.segments.length===1,'HANDOFF_CANDIDATE_ONE_SCENE_PER_CHUNK');
  return{...structuredClone(record.payload.segments[0]),startFrame:row.chunk.globalRange[0],endFrame:row.chunk.globalRange[1]};
 });
 const payload={schema:'WORLD_ENGINE_PREPARED_PRESENTATION_V2',durationSeconds:10,totalFrames:300,segments,
  transitions:structuredClone(plan.runtime.transitions),sourceQualification:structuredClone(plan.sourceQualification),
  sourceQualificationSHA256:plan.sourceQualificationSHA256,sourceQualificationWireJSON:plan.sourceQualificationWireJSON};
 let current=null,activeIndex=-1,closed=false;
 async function open(index){
  check(!closed&&Number.isSafeInteger(index)&&index===activeIndex+1&&index<binding.rows.length,'HANDOFF_CANDIDATE_SESSION_ORDER');
  current?.close();current=null;const row=binding.rows[index];
  const selected=await selectSealedOfficialCandidate({activation:row.activation,expectedActivationSHA256:row.activationSHA256,originalSHA256:binding.plan.originalSHA256,chunkRequestSHA256:row.chunk.requestSHA256,nativeSourceQualificationSHA256:row.qualification.sourceQualificationSHA256});
  check(selected,'HANDOFF_CANDIDATE_SEALED_SELECTION_REQUIRED');await assertNativeResources(selected.registry.get(selected.registrationId));
  current=await prepareOfficialCandidateSession(selected);activeIndex=index;
  return{session:current,index,offset:row.chunk.globalRange[0],end:row.chunk.globalRange[1]};
 }
 return Object.freeze({payload,rows:binding.rows.map(r=>({globalRange:r.chunk.globalRange})),bindingSHA256:binding.bindingSHA256,activation:plan.nativeCandidate.activation,open,close(){if(closed)return;closed=true;current?.close();current=null;}});
}
