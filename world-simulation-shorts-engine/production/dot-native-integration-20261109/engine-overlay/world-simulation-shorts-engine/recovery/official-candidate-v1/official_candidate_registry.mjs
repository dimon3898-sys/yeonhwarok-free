/** Server configuration only. No request/CLI path, URL or Boolean is consulted. */
import path from 'node:path';import {lstat} from 'node:fs/promises';
import {readPinnedServerFile} from './candidate_asset_snapshot.mjs';
const check=(v,c)=>{if(!v)throw Error(c)};
export async function selectOfficialCandidateRegistration({originalSHA256,chunkRequestSHA256,nativeSourceQualificationSHA256}={}){
 // Snapshot server configuration before the first await.
 const file=process.env.WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE,pin=process.env.WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256;
 if(file===undefined&&pin===undefined)return undefined;
 check(typeof file==='string'&&path.isAbsolute(file)&&/^[a-f0-9]{64}$/.test(pin??''),'UP2_OFFICIAL_SERVER_CONFIG');
 const stat=await lstat(file);check(stat.size>0&&stat.size<=24*1024**2,'UP2_OFFICIAL_SERVER_REGISTRY_CAP');
 const raw=await readPinnedServerFile(path.dirname(file),path.basename(file),{sha256:pin,bytes:stat.size}),data=JSON.parse(raw);
 check(data.schema==='WORLD_ENGINE_OFFICIAL_SERVER_REGISTRY_V1'&&data.productionAdmitted===false&&data.mode==='CPU_QUALIFIED_GPU_PENDING','UP2_OFFICIAL_SERVER_REGISTRY_SCHEMA');
 const matches=data.registrations.filter(row=>row.record.originalSemanticSHA256===originalSHA256&&row.record.chunkRequestSHA256===chunkRequestSHA256);
 check(matches.length===1,'UP2_OFFICIAL_CHUNK_NOT_REGISTERED');const selected=matches[0];
 check(selected.record.nativeSourceQualificationSHA256===nativeSourceQualificationSHA256,'UP2_OFFICIAL_SOURCE_QUALIFICATION_MISMATCH');
 return {registrationId:selected.id,registry:new Map([[selected.id,selected.record]]),assetRegistry:new Map(data.assetRegistryEntries),registrySHA256:pin};
}
