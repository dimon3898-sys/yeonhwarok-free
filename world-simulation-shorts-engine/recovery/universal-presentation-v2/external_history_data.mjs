/** Operator-approved external data; input cannot choose files, URLs or modules. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {canonicalJSON,analyzePrompt} from '../universal-data-pipeline-v1/prompt_pipeline.mjs';
const REPO=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const check=(value,code)=>{if(!value)throw Error('UP2_DATA_'+code);};
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&Object.keys(v).every(k=>keys.includes(k));
const hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const id=v=>typeof v==='string'&&/^[A-Z][A-Z0-9_]{0,95}$/.test(v);
export const dataHash=v=>createHash('sha256').update(typeof v==='string'||Buffer.isBuffer(v)?v:canonicalJSON(v)).digest('hex');
const jsonSafe=(v,depth=0)=>{
 check(depth<=64,'JSON_DEPTH');
 if(v===null||typeof v==='boolean'||typeof v==='string')return;
 if(typeof v==='number'){check(Number.isFinite(v),'FINITE_JSON');return;}
 check(typeof v==='object','FINITE_JSON');
 for(const [k,x]of Object.entries(v)){check(!['__proto__','prototype','constructor'].includes(k),'JSON_KEY');jsonSafe(x,depth+1);}
};
async function readPinned(file,expected,maximum){
 check(hex(expected),'HASH_REQUIRED');
 let handle;
 try{
  check(await fs.realpath(file)===file,'PATH_ALIAS');
  handle=await fs.open(file,constants.O_RDONLY|constants.O_NOFOLLOW);
  const stat=await handle.stat();check(stat.isFile()&&[0,process.getuid()].includes(stat.uid)&&!(stat.mode&0o022)&&stat.size>0&&stat.size<=maximum,'FILE_POLICY');
  const raw=await handle.readFile();const after=await handle.stat();
  check(raw.length===stat.size&&after.size===stat.size&&after.mtimeMs===stat.mtimeMs&&after.ctimeMs===stat.ctimeMs,'FILE_CHANGED');
  check(dataHash(raw)===expected,'HASH_MISMATCH');
  const value=JSON.parse(raw);jsonSafe(value);return value;
 }catch(e){if(String(e.message).startsWith('UP2_DATA_'))throw e;throw Error('UP2_DATA_FILE_UNAVAILABLE_OR_INVALID');}
 finally{await handle?.close();}
}
async function safeRoot(root){
 check(typeof root==='string'&&path.isAbsolute(root)&&path.resolve(root)===root&&root!==REPO&&!root.startsWith(REPO+path.sep),'ROOT_POLICY');
 try{
  for(let p=root;p!==path.dirname(p);p=path.dirname(p)){
   const stat=await fs.lstat(p);check(stat.isDirectory()&&!stat.isSymbolicLink()&&!(stat.mode&0o022)&&[0,process.getuid()].includes(stat.uid),'ROOT_PERMISSIONS');
  }
 }catch(e){if(String(e.message).startsWith('UP2_DATA_'))throw e;throw Error('UP2_DATA_ROOT_UNAVAILABLE');}
 return root;
}
export async function loadExternalHistoryDataset(reference,{dataRoot=process.env.WORLD_ENGINE_DATA_ROOT,catalogSHA256=process.env.WORLD_ENGINE_DATA_CATALOG_SHA256}={}){
 check(exact(reference,['id','version','sha256'])&&id(reference.id)&&typeof reference.version==='string'&&/^[0-9]+\.[0-9]+\.[0-9]+$/.test(reference.version)&&hex(reference.sha256),'REFERENCE');
 check(hex(catalogSHA256),'OPERATOR_CATALOG_PIN_REQUIRED');
 const root=await safeRoot(dataRoot),catalog=await readPinned(path.join(root,'catalog.json'),catalogSHA256,1024*1024);
 check(exact(catalog,['schema','version','records'])&&catalog.schema==='WORLD_ENGINE_REVIEWED_DATA_CATALOG_V1'&&catalog.version===1&&Array.isArray(catalog.records)&&catalog.records.length>0&&catalog.records.length<=1024,'CATALOG_SCHEMA');
 const matches=catalog.records.filter(r=>r.id===reference.id&&r.version===reference.version);
 check(matches.length===1,'UNREGISTERED_OR_DUPLICATE');const row=matches[0];
 check(exact(row,['id','version','sha256','bytes','reviewStatus','sourceInputSHA256','sourceRuntimeSHA256','evidenceRegistrySHA256'])&&row.sha256===reference.sha256&&row.reviewStatus==='SOURCE_BOUND_DISPLAY_INTERPOLATION_ONLY'&&Number.isSafeInteger(row.bytes)&&row.bytes>0&&row.bytes<=24*1024**2,'CATALOG_RECORD');
 const data=await readPinned(path.join(root,reference.sha256+'.json'),row.sha256,row.bytes);
 check(exact(data,['schema','id','version','sourceInput','sourceRuntime','evidenceRegistry'])&&data.schema==='WORLD_ENGINE_REVIEWED_HISTORY_DATASET_V1'&&data.id===row.id&&data.version===row.version,'PACKAGE_SCHEMA');
 for(const [key,pin]of [['sourceInput','sourceInputSHA256'],['sourceRuntime','sourceRuntimeSHA256'],['evidenceRegistry','evidenceRegistrySHA256']])check(hex(row[pin])&&dataHash(data[key])===row[pin],'COMPONENT_HASH');
 const original=data.sourceInput,runtime=data.sourceRuntime;
 check(original?.data?.simulationType==='HISTORICAL'&&runtime?.segments?.length===1,'HISTORICAL_SOURCE');
 // Registry is operator-pinned package data, never an approval supplied in the input JSON.
 const audit=analyzePrompt(original.data,{evidenceRegistry:data.evidenceRegistry});
 check(audit.issues.filter(x=>x.code!=='SOURCE_REGION_NOT_AVAILABLE').length===0&&audit.sceneResults.length===1&&audit.sceneResults[0].issues.every(x=>x.code==='SOURCE_REGION_NOT_AVAILABLE'),'EVIDENCE_REJECTED');
 const segment=runtime.segments[0],scene=segment.scene,effect=segment.presentation?.territoryChanges?.items?.[0],facts=original.data.scenes[0].facts;
 check(scene.event_type==='WAR'&&scene.time_steps.length===2&&segment.presentation.territoryChanges.profile==='HISTORICAL_CONTINUOUS_V1'&&segment.presentation.territoryChanges.items.length===1,'CONTINUOUS_SOURCE');
 check(canonicalJSON(scene.geometries)===canonicalJSON(facts.geometries)&&canonicalJSON(scene.source_notes)===canonicalJSON(facts.source_notes),'SOURCE_FACTS');
 for(const step of scene.time_steps){const fact=facts.stages.find(x=>x.id===step.id);check(fact&&canonicalJSON(fact.date)===canonicalJSON(step.date),'SOURCE_PERIOD');}
 check(typeof segment.regionEvidence?.sourceId==='string','PINNED_MAP_SOURCE');
 return {segment,original,sourceEvidence:{owner:'OPERATOR_PINNED_EXTERNAL_DATA_AND_EXISTING_HISTORICAL_FACTS_GATE',catalogSHA256,datasetSHA256:row.sha256,sourceInputSHA256:row.sourceInputSHA256,sourceRuntimeSHA256:row.sourceRuntimeSHA256,evidenceRegistrySHA256:row.evidenceRegistrySHA256,canonicalFactsSHA256:dataHash(facts),continuousSHA256:dataHash(effect.continuous)}};
}
