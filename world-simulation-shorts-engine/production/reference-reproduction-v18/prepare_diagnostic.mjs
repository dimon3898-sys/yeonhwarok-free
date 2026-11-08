/** Re-materialize the already compiled request for this CPU diagnostic filesystem. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const [root,ready,privateRoot,out]=process.argv.slice(2);
const {prepareNvidiaRuntimeRequest}=await import(pathToFileURL(path.join(root,'world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs')));
const receipts=[];
for(const part of [1,2]){
 const request=JSON.parse(await fs.readFile(path.join(ready,`COMPILED_REQUEST_0${part}.json`),'utf8'));
 const value=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateRoot,'sources-'+part),privateWorkspaceRoot:privateRoot,publicExportRoot:out});
 assert(value.totalFrames===300);
 await fs.writeFile(path.join(privateRoot,`PREPARED_${part}.json`),JSON.stringify(value),{flag:'wx',mode:0o600});
 receipts.push({part,sourceQualificationSHA256:value.sourceQualificationSHA256,sceneIds:value.segments.map(s=>s.sceneId),scope:'Filesystem materialization for new sparse diagnostic only; compiler PASS reused'});
}
await fs.writeFile(path.join(out,'DIAGNOSTIC_PREPARATION.json'),JSON.stringify({status:'PASS',receipts,gpuStarts:0,oldPASSReruns:0},null,2)+'\n',{flag:'wx'});
