/** Server-only activation seal. Authored requests cannot supply this contract. */
import {createHash} from 'node:crypto';
import {selectOfficialCandidateRegistration} from './official_candidate_registry.mjs';
import {candidateSourceCredits} from './candidate_source_credits.mjs';
export const canonical=value=>JSON.stringify(value,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
export const activationHash=value=>createHash('sha256').update(canonical(value)).digest('hex');
const check=(v,c)=>{if(!v)throw Error(c)};
export async function sealOfficialCandidateActivation({originalSemanticSHA256,aggregateQualificationSHA256,chunks}={}){
 const input=structuredClone({originalSemanticSHA256,aggregateQualificationSHA256,chunks}),rows=[];let registrySHA256;
 for(const c of input.chunks){const selected=await selectOfficialCandidateRegistration({originalSHA256:input.originalSemanticSHA256,chunkRequestSHA256:c.requestSHA256,nativeSourceQualificationSHA256:c.sourceQualificationSHA256});
  if(selected===undefined){check(rows.length===0,'UP2_CANDIDATE_CONFIG_CHANGED_DURING_SEAL');return undefined;}
  check(registrySHA256===undefined||registrySHA256===selected.registrySHA256,'UP2_CANDIDATE_CONFIG_CHANGED_DURING_SEAL');registrySHA256=selected.registrySHA256;
  const r=selected.registry.get(selected.registrationId);check(r.aggregateQualificationSHA256===input.aggregateQualificationSHA256,'UP2_CANDIDATE_AGGREGATE_SEAL');
  const credits=candidateSourceCredits();rows.push({chunkRequestSHA256:c.requestSHA256,registrationId:selected.registrationId,sceneKey:r.sceneKey,nativeSourceQualificationSHA256:c.sourceQualificationSHA256,materialPolicy:r.materialPolicy,lightingPolicy:r.lightingPolicy,shaderSha256:r.shaderSha256,credits,creditsSHA256:activationHash(credits)});
 }
 check(rows.length>0,'UP2_CANDIDATE_EMPTY_SEAL');return {schema:'WORLD_ENGINE_OFFICIAL_CANDIDATE_ACTIVATION_V1',mode:'CPU_QUALIFIED_GPU_PENDING',productionAdmitted:false,registrySHA256,originalSemanticSHA256:input.originalSemanticSHA256,aggregateQualificationSHA256:input.aggregateQualificationSHA256,chunks:rows};
}
export async function selectSealedOfficialCandidate({activation,expectedActivationSHA256,originalSHA256,chunkRequestSHA256,nativeSourceQualificationSHA256}={}){
 // An already submitted legacy job stays legacy regardless of later configuration.
 if(activation===undefined){check(expectedActivationSHA256===undefined,'UP2_CANDIDATE_UNSEALED_HASH');return undefined;}
 const a=structuredClone(activation);check(a.schema==='WORLD_ENGINE_OFFICIAL_CANDIDATE_ACTIVATION_V1'&&a.mode==='CPU_QUALIFIED_GPU_PENDING'&&a.productionAdmitted===false&&activationHash(a)===expectedActivationSHA256&&a.originalSemanticSHA256===originalSHA256,'UP2_CANDIDATE_ACTIVATION_SEAL');
 const rows=a.chunks.filter(c=>c.chunkRequestSHA256===chunkRequestSHA256);check(rows.length===1,'UP2_CANDIDATE_ACTIVATION_CHUNK');const c=rows[0];
 check(c.nativeSourceQualificationSHA256===nativeSourceQualificationSHA256&&activationHash(c.credits)===c.creditsSHA256&&canonical(c.credits)===canonical(candidateSourceCredits()),'UP2_CANDIDATE_CREDITS_SEAL');
 const selected=await selectOfficialCandidateRegistration({originalSHA256,chunkRequestSHA256,nativeSourceQualificationSHA256});check(selected&&selected.registrySHA256===a.registrySHA256&&selected.registrationId===c.registrationId,'UP2_CANDIDATE_REGISTRY_CHANGED');const r=selected.registry.get(selected.registrationId);
 check(r.aggregateQualificationSHA256===a.aggregateQualificationSHA256&&['sceneKey','materialPolicy','lightingPolicy','shaderSha256'].every(k=>r[k]===c[k]),'UP2_CANDIDATE_RECORD_CHANGED');
 return {...selected,sealedActivationSHA256:expectedActivationSHA256,sealedActivation:a,sealedChunk:c};
}
export function candidateReceiptFields(selected){if(!selected)return{};const c=selected.sealedChunk;return {candidateActivationSHA256:selected.sealedActivationSHA256,candidateRegistrySHA256:selected.registrySHA256,candidateRegistrationId:selected.registrationId,candidateSceneKey:c.sceneKey,candidateCredits:structuredClone(c.credits),candidateCreditsSHA256:c.creditsSHA256};}
export const candidateCreditText=credits=>credits.map(c=>`${c.attribution}; license=${c.license}; source=${c.sourceURL}; modifications=${c.transformations}; evidence=${c.evidenceSHA256}`).join(' | ');
