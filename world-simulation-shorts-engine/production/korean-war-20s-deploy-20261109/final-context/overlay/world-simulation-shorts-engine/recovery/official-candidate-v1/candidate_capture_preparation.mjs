/** CPU-only explicit candidate lane. Registry is server-owned; default is disabled. */
import {createHash} from 'node:crypto';
import {verifyServerRoot,captureAssetSnapshot} from './candidate_asset_snapshot.mjs';
export const CANDIDATE_REQUEST_SCHEMA='WORLD_ENGINE_PRESENTATION_CANDIDATE_PREPARATION_REQUEST_V1';
export const isCandidatePreparationRequest=request=>request?.schema===CANDIDATE_REQUEST_SCHEMA;
const check=(v,code)=>{if(!v)throw Error(code);};
const deepFreeze=value=>{if(value&&typeof value==='object'){for(const child of Object.values(value))deepFreeze(child);Object.freeze(value);}return value;};
export async function prepareRegisteredCandidateRequest({request,registry,expectedSourceQualificationSHA256}={}){
 const input=Object.freeze({schema:request?.schema,registrationId:request?.registrationId,segment:request?.segment});
 check(isCandidatePreparationRequest(input)&&Object.keys(request).sort().join(',')==='registrationId,schema,segment'&&typeof input.registrationId==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(input.registrationId)&&Number.isInteger(input.segment)&&input.segment>=1&&input.segment<=4,'UP2_CANDIDATE_EXPLICIT_REQUEST_REQUIRED');
 check(registry instanceof Map&&registry.has(input.registrationId),'UP2_CANDIDATE_SERVER_REGISTRATION_REQUIRED');
 if(expectedSourceQualificationSHA256!==undefined)check(typeof expectedSourceQualificationSHA256==='string'&&/^[a-f0-9]{64}$/.test(expectedSourceQualificationSHA256),'UP2_CANDIDATE_EXPECTED_QUALIFICATION_INVALID');
 // Clone/freeze before the first await; never consult caller objects again.
 const registrySnapshot=deepFreeze(Object.fromEntries([...registry].map(([id,value])=>[id,structuredClone(value)])));
 const registration=registrySnapshot[input.registrationId];
 await verifyServerRoot(registration.partial.root);await verifyServerRoot(registration.png.root);
 // Fixed module path, never caller-provided. Loaded only for this explicit lane.
 const {preparePartialPngRoute,PNG_ROUTE_MODE}=await import('../../production/reference-reproduction-v18/source-candidate-contract/partial_png_route_adapter.mjs');
 const prepared=await preparePartialPngRoute(registration,{mode:PNG_ROUTE_MODE,segment:input.segment});
 check(prepared.status==='CPU_PREPARATION_ONLY'&&['productionAdmitted','renderAllowed','imageBuildAllowed','browserUploadQualified','materialQualified','lodQualified'].every(k=>prepared[k]===false),'UP2_CANDIDATE_ADMISSION_STATE_INVALID');
 const snapshot=await captureAssetSnapshot([{root:prepared.serverImageRoot,assets:prepared.serverImages}]);
 // Do not misrepresent late on-disk module hashes as executing code identity.
 delete prepared.identity;delete prepared.pngIdentity;delete prepared.cacheIdentity;
 delete prepared.serverAssetRoot;delete prepared.serverImageRoot;
 for(const a of [...Object.values(prepared.serverAssets),...Object.values(prepared.serverImages)])delete a.localFile;
 const identity={schema:CANDIDATE_REQUEST_SCHEMA,registrationId:input.registrationId,segment:input.segment,partialGenerationIndexSha256:registration.partial.generationIndexSha256,pngGenerationIndexSha256:registration.png.generationIndexSha256,originalGenerationIndexSha256:registration.partial.originalGenerationIndexSha256};
 const qualificationHash=createHash('sha256').update(JSON.stringify(identity)).digest('hex');
 if(expectedSourceQualificationSHA256!==undefined)check(expectedSourceQualificationSHA256===qualificationHash,'UP2_CANDIDATE_EXPECTED_QUALIFICATION_MISMATCH');
 const result={schema:'WORLD_ENGINE_REGISTERED_CANDIDATE_PREPARATION_V1',status:'CPU_PREPARATION_ONLY_NOT_CAPTURE',sourceQualificationSHA256:qualificationHash,dataIdentity:identity,cacheReuseAllowed:false,executingCodeIdentity:{status:'UNVERIFIED',reason:'Loaded modules are not attested by later on-disk hashes; no executable-cache admission.'},assetSnapshotBacking:'PROCESS_MEMORY_ONLY_PNG_BYTES',rawAssets:'VALIDATION_METADATA_ONLY_NOT_SERVABLE',snapshotBytes:snapshot.byteCount,prepared,productionAdmitted:false,renderAllowed:false,imageBuildAllowed:false,actualDrawPerformed:false};
 Object.defineProperty(result,'assetSnapshot',{value:snapshot,enumerable:false,writable:false});return result;
}
