/** Actual free software capture, explicitly separate from production GPU admission. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {runFreePreview,loadOvernightSoftwarePlan} from '../universal-overnight-v3/free_preview_runner.mjs';
import {extendObservedPlan} from './trace_binding.mjs';
export async function runObservedPreview(options){
 const report=await runFreePreview({...options,loadPlan:async source=>extendObservedPlan(await loadOvernightSoftwarePlan(source))});
 assert.equal(report.nvidiaHardwareVerified,false);
 const trace={schema:'WORLD_ENGINE_RECONCILIATION_SOFTWARE_CAPTURE_V1',
  status:'ACTUAL_SOFTWARE_CAPTURE_ONLY',result:report,sourceCheckoutCommit:options.sourceCheckoutCommit,
  candidateContainerExecuted:false,visualQualityApproved:false,newVisualDesignClaimed:false};
 await writeFile(path.join(options.outputRoot,'RECONCILIATION_CAPTURE.json'),JSON.stringify(trace,null,2)+'\n',{flag:'wx',mode:0o600});
 return trace;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  assert.equal(process.argv.length,5,'RECONCILIATION_OPTIONS_AND_OUTPUT_AND_COMMIT_REQUIRED');
  const supplied=JSON.parse(await readFile(process.argv[2])),sourceCheckoutCommit=process.argv[4];
  assert.match(sourceCheckoutCommit,/^[a-f0-9]{40}$/);
  const result=await runObservedPreview({...supplied.options,outputRoot:process.argv[3],sourceCheckoutCommit});
  console.log(JSON.stringify({status:result.status,video:result.result.video,sourceCheckoutCommit,
   nvidiaHardwareVerified:false,visualQualityApproved:false}));
 }catch(error){console.error(JSON.stringify({status:'BLOCKED',errorCode:error.message,stack:error.stack}));process.exitCode=2;}
}
