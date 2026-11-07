/** New source-bound inputs only. Prior A2/A4/A7 suites and pixels are preserved. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {canonicalJSON} from '../../recovery/universal-data-pipeline-v1/prompt_pipeline.mjs';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {prepareNvidiaRuntimeRequest,verifyNvidiaPreparedRuntimeRequest} from '../../recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),[output,privateRoot]=process.argv.slice(2);
assert(path.isAbsolute(output)&&path.isAbsolute(privateRoot));await mkdir(output,{mode:0o700});
const save=(name,x)=>writeFile(path.join(output,name),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const values=[],checks=[];
try{
 for(const clip of [1,2]){
  const input=JSON.parse(await readFile(path.join(here,`KOREAN_WAR_20S_PART_0${clip}.json`)));
  let analysis;
  if(process.argv.includes('--reuse-analysis')){
   const encoded=await readFile(path.join(here,`evidence/local/ANALYSIS_${clip}.json.gz.base64`),'utf8');
   analysis=JSON.parse(gunzipSync(Buffer.from(encoded.trim(),'base64')));
   assert.equal(analysis.inputSHA256,createHash('sha256').update(canonicalJSON(input)).digest('hex'),'PRESERVED_ANALYSIS_INPUT_CHANGED');
  }else analysis=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true});
  await save(`ANALYSIS_${clip}.json`,analysis);
  assert.equal(analysis.status,'PASS',JSON.stringify(analysis.issues));assert.equal(analysis.totalFrames,300);
  const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:analysis.inputSHA256,transitions:analysis.transitionPlan,segments:analysis.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,scene:r.scene,region:r.region,presentation:r.presentation,inputTrace:r.inputTrace}))};
  const value=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateRoot,'detail-'+clip),privateWorkspaceRoot:privateRoot,publicExportRoot:output});
  const verified=await verifyNvidiaPreparedRuntimeRequest({prepared:value,privateWorkspaceRoot:privateRoot,publicExportRoot:output});assert.equal(verified.status,'PASS',JSON.stringify(verified));
  await save(`PREPARED_${clip}.json`,value);values.push(value);checks.push(`clip_${clip}_new_source_analysis_admission_hashes_and_native_geometry`);
 }
 // Reuse the sealed analysis, seam plan and prior source checks. Only private
 // runtime requests are rematerialized because their filesystem paths are new.
 await writeFile(path.join(output,'COMPOSE_PLAN.json'),await readFile(path.resolve(here,'../korean-war-20s-detail-v2/evidence/local/COMPOSE_PLAN.json')),{flag:'wx'});
 await save('REUSED_PREPARATION_RECEIPT.json',{status:'PREPARED_NEW_COLOR_INPUT_WITH_PRESERVED_SOURCE_GATES',sourceCommit:'ceee49fc512074e33179344663b02367c3e875d6',oldPassSuitesRerun:0,priorSourceChecks:4,priorStaticChecks:4,negativeTestRerun:false,newInputAnalysis:true,qualityPass:false});
 console.log('KW20_DETAIL_PRIVATE_REQUESTS_READY');
}catch(error){await save('CHECK_FAILED.json',{status:'FAIL',checks,error:String(error.stack??error)});throw error;}
