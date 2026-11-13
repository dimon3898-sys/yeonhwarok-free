import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {analyzePrompt,canonicalJSON} from '../../recovery/universal-data-pipeline-v1/prompt_pipeline.mjs';
const base=new URL('./',import.meta.url),input=JSON.parse(fs.readFileSync(new URL('MONGOL_EMPIRE_SCENE_INPUT.json',base))).data;
const checks=[],codes=x=>analyzePrompt(x).issues.map(x=>x.code),copy=structuredClone;
function check(name,fn){fn();checks.push(name);}
check('reviewed reconstructed periods pass data gate; source rendering remains separate',()=>assert.deepEqual([...new Set(codes(input))],['SOURCE_REGION_NOT_AVAILABLE']));
check('old source id cannot admit moved boundary',()=>{const x=copy(input);x.scenes[0].facts.geometries[0].geometry.coordinates[0][0][0][0]+=.01;assert.ok(codes(x).includes('EVIDENCE_DATASET_NOT_REVIEWED'));});
check('year cannot be silently replaced by invented day',()=>{const x=copy(input);x.scenes[0].facts.stages[0].date='1206-01-01';assert.ok(codes(x).includes('EVIDENCE_DATASET_NOT_REVIEWED'));});
check('source hash and uncertainty cannot be removed',()=>{for(const field of ['original_sha256','uncertainty']){const x=copy(input);delete x.scenes[0].facts.source_notes[0][field];assert.ok(codes(x).some(c=>c==='EVIDENCE_SOURCE_MISMATCH'||c==='EVIDENCE_DATASET_NOT_REVIEWED'));}});
check('protected record cannot be overwritten by caller registry',()=>{const x=copy(input);x.scenes[0].facts.source_notes[0].uncertainty='exact';const r=JSON.parse(fs.readFileSync(new URL('HISTORICAL_EVIDENCE_REGISTRY.json',base))).records[0];r.canonicalFactsSHA256=createHash('sha256').update(canonicalJSON(x.scenes[0].facts)).digest('hex');assert.ok(analyzePrompt(x,{evidenceRegistry:[r]}).issues.some(i=>i.code==='EVIDENCE_DATASET_NOT_REVIEWED'));});
check('new generic reconstruction claim cannot bind later polygon to early period',()=>{const x=copy(input),r=JSON.parse(fs.readFileSync(new URL('HISTORICAL_EVIDENCE_REGISTRY.json',base))).records[0];r.id='TEST_REVIEWED_OTHER';x.scenes[0].historicalEvidence[0].recordId=r.id;x.scenes[0].facts.stages[0].area_refs=[x.scenes[0].facts.geometries.at(-1).id];r.canonicalFactsSHA256=createHash('sha256').update(canonicalJSON(x.scenes[0].facts)).digest('hex');assert.ok(analyzePrompt(x,{evidenceRegistry:[r]}).issues.some(i=>i.code==='RECONSTRUCTION_VALIDITY_OR_DISCLOSURE_MISMATCH'));});
console.log(JSON.stringify({status:'PASS',scope:'source/geometry/period/uncertainty admission only',checks},null,2));
