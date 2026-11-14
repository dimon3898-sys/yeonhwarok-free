/** Previously uncovered runtime tampering cases, no renderer or source materialization. */
import fs from 'node:fs/promises';import assert from 'node:assert/strict';
import {compileAuthoredHistory,verifyAuthoredHistoryRuntime} from '../../recovery/universal-presentation-v2/history_authored_v1.mjs';
import {runtimeDurationContract} from '../../recovery/codex-to-gcube-handoff-v1/backend/profile_contract.mjs';
const base=new URL('./',import.meta.url), input=JSON.parse(await fs.readFile(new URL('FINAL_20S_INPUT.json',base))),c=await compileAuthoredHistory(input.prompt);
const runtime={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',totalFrames:600,durationSeconds:20,profile:'HISTORICAL_CONTINUOUS_600F_V1',simulationType:'HISTORICAL',historicalAdmission:c.historicalAdmission,sourceInputSHA256:c.inputSHA256,segments:c.renderRequests,transitions:[],inputTrace:c.inputTrace};
const checks=[];
for(const [name,edit,code] of [
 ['MISSING_PINNED_MAP',r=>delete r.segments[0].region.sourceId,'UP2_HISTORY_RUNTIME_SOURCE_OR_DISPLAY_CHANGED'],
 ['WRONG_INPUT_HASH',r=>r.sourceInputSHA256='0'.repeat(64),'UP2_HISTORY_RUNTIME_SOURCE_OR_DISPLAY_CHANGED'],
 ['WRONG_RUNTIME_PROFILE',r=>r.profile='GENERAL_600','UP2_HISTORY_RUNTIME_PROFILE'],
 ['RUNTIME_FRAME_OVERFLOW',r=>r.segments[0].endFrame=601,'UP2_HISTORY_RUNTIME_SOURCE_OR_DISPLAY_CHANGED'],
 ['MISSING_HISTORICAL_EVIDENCE',r=>delete r.historicalAdmission.sourceEvidence,'UP2_HISTORY_RUNTIME_SOURCE_OR_DISPLAY_CHANGED']
]){const r=structuredClone(runtime);edit(r);let actual;try{await verifyAuthoredHistoryRuntime(r);}catch(e){actual=e.message;}assert.equal(actual,code,name);checks.push({name,status:'PASS',errorCode:actual});}
for(const d of [6,10]){const r=structuredClone(runtime);r.durationSeconds=d;r.totalFrames=d*30;assert.throws(()=>runtimeDurationContract(r),/HANDOFF_LEGACY_PROFILE_FIELDS_CHANGED/);checks.push({name:'RUNTIME_DOWNCAST_'+d*30,status:'PASS',errorCode:'HANDOFF_LEGACY_PROFILE_FIELDS_CHANGED'});}
const report={status:'PASS',scope:'PREVIOUSLY_UNCOVERED_600_RUNTIME_REJECTIONS',checks,oldPassReruns:0,gpuStarts:0,renderersExecuted:0};await fs.writeFile(new URL('REMAINING_RUNTIME_CASES.json',base),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:'PASS',newRejections:checks.length}));
