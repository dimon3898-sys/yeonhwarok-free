/** Only new multipart static-context scope; does not rerun the prior A2 suite. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {analyzePrompt,canonicalJSON} from '../../recovery/universal-data-pipeline-v1/prompt_pipeline.mjs';
import {reviewedContextRecords} from '../../recovery/universal-data-pipeline-v1/reviewed_context_registry.mjs';
const sha=x=>createHash('sha256').update(canonicalJSON(x)).digest('hex');
const original=JSON.parse(fs.readFileSync(new URL('./KOREAN_WAR_20S_PART_01.json',import.meta.url))).data;
const input=()=>({...structuredClone(original),renderSettings:{sourceRegionId:'korean_peninsula'}});
const checks=[],record=(name,value)=>{assert(value,name);checks.push(name);};
record('two_complete_polygon_groups_admitted',analyzePrompt(input()).status==='PASS');
function alternate(mutate){const value=input(),records=reviewedContextRecords();for(const r of records)r.id='DETAIL_TEST_'+r.id;
 for(const scene of value.scenes){for(const b of scene.historicalEvidence)b.recordId='DETAIL_TEST_'+b.recordId;mutate(scene.facts);
  for(const r of records.filter(r=>scene.historicalEvidence.some(b=>b.recordId===r.id))){r.canonicalFactsSHA256=sha(scene.facts);r.geometrySHA256ById=Object.fromEntries(scene.facts.geometries.filter(g=>g.source_id===r.sourceId).map(g=>[g.id,sha(g.geometry)]));}}
 return analyzePrompt(value,{evidenceRegistry:records});}
record('dropping_island_group_at_later_stage_rejected',alternate(f=>{f.stages[1].area_refs=f.stages[1].area_refs.slice(0,1);}).issues.some(x=>x.code==='EVIDENCE_SCOPE_INSUFFICIENT'));
record('multipart_context_cannot_claim_historical_control',alternate(f=>{f.semantic_mode='HISTORICAL_RECONSTRUCTION';}).issues.some(x=>x.code==='EVIDENCE_SCOPE_INSUFFICIENT'));
const changed=input();changed.scenes[0].facts.geometries[0].geometry.coordinates[0][0][0][0]+=.001;
const spoof=reviewedContextRecords();for(const r of spoof)r.canonicalFactsSHA256=sha(changed.scenes[0].facts);
record('new_reserved_review_ids_cannot_be_replaced',analyzePrompt(changed,{evidenceRegistry:spoof}).issues.some(x=>x.code==='EVIDENCE_DATASET_NOT_REVIEWED'));
const result={status:'PASS_NEW_MULTIPART_CONTEXT_SCOPE',checks,checkCount:checks.length,oldPassSuitesRerun:0,gpuExecuted:false};
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result));
