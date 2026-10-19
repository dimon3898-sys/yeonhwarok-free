/** CPU selection trace only. No browser, canvas, GPU, or video frame is created. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {integrationFrameSelections} from './runtime_binding.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
export async function traceStoredPlan(){
 const planFile=path.join(root,'../verified-front-data-v4-recovery/VIDEO_PLAN_80S.json'),
  frontFile=path.join(root,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'),
  planBytes=await readFile(planFile),frontBytes=await readFile(frontFile),
  plan=JSON.parse(planBytes),frontProfile=JSON.parse(frontBytes),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
 let count=0;const counts={};let lines='';
 for(const row of integrationFrameSelections({plan,frontProfile})){
  count++;counts[row.areaPolicy]=(counts[row.areaPolicy]??0)+1;
  lines+=JSON.stringify({...row,evidenceScope:'ACTUAL_CPU_GEOMETRY_AND_ARCHIVAL_SELECTION_ONLY',
   selectedRendererChain:['front_adapter.bootLongRuntime','reference_source_material','production_area_bridge','production_camera_bridge','native protected graphics'],
   browserFactoriesExecuted:false,drawReadPixelsExecuted:false})+'\n';
 }
 if(count!==plan.totalFrames)throw Error('INTEGRATION_TRACE_FRAME_GAP');
 await writeFile(path.join(root,'reports/FRAME_SELECTION_TRACE_2400.ndjson'),lines);
 const summary={schema:'WORLD_ENGINE_INTEGRATION_CPU_SELECTION_TRACE_V1',frames:count,counts,
  planSHA256:sha(planBytes),frontProfileSHA256:sha(frontBytes),traceSHA256:sha(lines),
  codeInvoked:['integrationFrameSelections','evaluateProductionGeometryClock','normalizeFrontProfile','selectFrontSnapshot'],
  browserFactoryInvocation:'NOT_EXECUTED','gpuRenderingVerified':false,'mp4Created':false,'appliedOutputFeatures':0};
 await writeFile(path.join(root,'reports/FRAME_SELECTION_TRACE_SUMMARY.json'),JSON.stringify(summary,null,2)+'\n');return summary;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(await traceStoredPlan()));
