/** Materialize the second clip from its already-passed A5 analysis; do not rerun the prior suites. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {prepareNvidiaRuntimeRequest,verifyNvidiaPreparedRuntimeRequest} from '../../recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
const [previous,output,privateRoot]=process.argv.slice(2);
const analysis=JSON.parse(await readFile(path.join(previous,'check/ANALYSIS_2.json')));
const check=JSON.parse(await readFile(path.join(previous,'check/CHECK_RESULT.json')));
assert.equal(check.status,'PASS_NEW_INPUT_PREPARATION_ONLY');assert.equal(analysis.status,'PASS');
const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:analysis.inputSHA256,transitions:analysis.transitionPlan,segments:analysis.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,scene:r.scene,region:r.region,presentation:r.presentation,inputTrace:r.inputTrace}))};
await mkdir(output,{mode:0o700});
const value=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateRoot,'sources-2'),privateWorkspaceRoot:privateRoot,publicExportRoot:output});
await verifyNvidiaPreparedRuntimeRequest({prepared:value,privateWorkspaceRoot:privateRoot,publicExportRoot:output});
await writeFile(path.join(output,'PREPARED_2.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
await writeFile(path.join(output,'REUSED_CHECKS.json'),JSON.stringify({sourceRun:42209920397,analysis:'ANALYSIS_2.json',reusedInputChecks:check.checkCount,oldPassSuitesRerun:0,reason:'Re-materialize ephemeral source assets only; same sealed runtime and input. Only previously undrawn clip-02 key frames execute.'},null,2)+'\n');
