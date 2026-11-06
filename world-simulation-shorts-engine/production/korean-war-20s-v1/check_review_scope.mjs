import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {analyzePrompt,canonicalJSON} from '../../recovery/universal-data-pipeline-v1/prompt_pipeline.mjs';
import {reviewedContextRecords} from '../../recovery/universal-data-pipeline-v1/reviewed_context_registry.mjs';
const sha=x=>createHash('sha256').update(canonicalJSON(x)).digest('hex');
const checks=[],record=(name,ok)=>{assert(ok,name);checks.push(name);};
const input=i=>{const v=JSON.parse(fs.readFileSync(new URL(`./KOREAN_WAR_20S_PART_0${i}.json`,import.meta.url))).data;v.renderSettings={sourceRegionId:'korean_peninsula'};return v;};
for(const i of [1,2]){const r=analyzePrompt(input(i));record(`new_input_${i}_reviewed_data_admission`,r.status==='PASS');}
const bad=input(1);bad.scenes[0].facts.locations[0].anchor[0]+=.001;
record('unreviewed_coordinate_change_rejected',analyzePrompt(bad).issues.some(x=>x.code==='EVIDENCE_DATASET_NOT_REVIEWED'));
const noBinding=input(1);delete noBinding.scenes[0].historicalEvidence;
record('caller_verified_flag_insufficient',analyzePrompt(noBinding).issues.some(x=>x.code==='REVIEWED_EVIDENCE_REQUIRED'));
const spoof=reviewedContextRecords();spoof.forEach(r=>r.canonicalFactsSHA256=sha(bad.scenes[0].facts));
record('caller_cannot_replace_builtin_review',analyzePrompt(bad,{evidenceRegistry:spoof}).issues.some(x=>x.code==='EVIDENCE_DATASET_NOT_REVIEWED'));
// Simulate a mistaken additional server registration with exact hashes, so the
// following check exercises scope enforcement instead of merely hash rejection.
function alternate(input,mutate){const records=reviewedContextRecords();for(const r of records)r.id='TEST_'+r.id;for(const s of input.scenes){for(const b of s.historicalEvidence)b.recordId='TEST_'+b.recordId;mutate(s.facts);for(const r of records.filter(r=>s.historicalEvidence.some(b=>b.recordId===r.id))){r.canonicalFactsSHA256=sha(s.facts);r.geometrySHA256ById=Object.fromEntries(s.facts.geometries.filter(g=>g.source_id===r.sourceId).map(g=>[g.id,sha(g.geometry)]));}}return analyzePrompt(input,{evidenceRegistry:records});}
const dynamic=alternate(input(1),f=>{f.geometries.push({...structuredClone(f.geometries[0]),id:'CHANGED_AREA'});f.stages[1].area_refs=['CHANGED_AREA'];});
record('context_scope_cannot_admit_territory_change',dynamic.issues.some(x=>x.code==='EVIDENCE_SCOPE_INSUFFICIENT'));
const control=alternate(input(1),f=>{f.semantic_mode='HISTORICAL_RECONSTRUCTION';});
record('context_scope_cannot_admit_ownership_semantics',control.issues.some(x=>x.code==='EVIDENCE_SCOPE_INSUFFICIENT'));
const result={status:'PASS_NEW_REVIEW_SCOPE_ONLY',checkCount:checks.length,checks,oldPassSuitesRerun:0,gpuExecutions:0};
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result));
