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
import {verifyRegionQualification} from '../../recovery/codex-to-gcube-handoff-v1/region_source_vulkan.generated.mjs';
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
  for(const segment of value.segments){
   assert.equal(segment.regionEvidence.sourceId,'NASA_BMNG_KOREA_500M_NE10M_V2');
   assert.equal(segment.regionEvidence.geometryOriginalSHA256,'239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255');
   assert.equal(segment.regionEvidence.resampling,false);
   for(const code of ['COUNTRY_KOR','COUNTRY_PRK'])assert.equal(segment.nativePlan.geometries.find(g=>g.id===code).scale.denominator,10000000);
  }
  await save(`PREPARED_${clip}.json`,value);values.push(value);checks.push(`clip_${clip}_new_source_analysis_admission_hashes_and_native_geometry`);
 }
 const last=values[0].segments.at(-1),first=values[1].segments[0];
 assert.deepEqual(last.presentationPlan.cpuFrameBounds.at(-1),first.presentationPlan.cpuFrameBounds[0]);checks.push('new_source_seam_camera_exact');
 const visible=(s,f)=>s.presentation.labels.items.filter(x=>f>=x.startFrame&&f<x.endFrame).map(x=>({id:x.id,text:x.text,role:x.role,anchor:x.anchor,pin:x.pin}));
 assert.deepEqual(visible(last,149),visible(first,0));
 const boundary={cameraBounds:last.presentationPlan.cpuFrameBounds.at(-1),labels:visible(last,149),geographicContext:'unchanged modern land; no ownership claim',nativeBoundaries:false};
 await save('COMPOSE_PLAN.json',{schema:'WORLD_ENGINE_NEUTRAL_VIDEO_PLAN_V1',durationSeconds:20,fps:30,resolution:{width:1080,height:1920},scenes:[{sceneId:'clip-01',startFrame:0,endFrame:300,boundaryEnd:boundary},{sceneId:'clip-02',startFrame:300,endFrame:600,boundaryStart:boundary}]});
 // Negative test is specific to the new override binding, not an old suite.
 const tampered=structuredClone(first);tampered.nativePlan.geometries.find(g=>g.id==='COUNTRY_KOR').coordinates[0][0][0][0]+=.001;
 const rejection=await verifyRegionQualification({prepared:tampered,privateWorkspaceRoot:privateRoot,publicExportRoot:output});
 assert.equal(rejection.status,'INVALID');assert.equal(rejection.issues[0].code,'REGION_NATIVE_GEOMETRY_BINDING_MISMATCH');checks.push('tampered_native_geometry_rejected');
 await save('CHECK_RESULT.json',{status:'PASS_NEW_DETAIL_SOURCE_PREPARATION',checks,checkCount:checks.length,oldPassSuitesRerun:0,framesRendered:0,priorPass:'A2 source-review gate behavior; A4 timing/layout inputs; A7 19 actual V1 frames. Valid for V1 only.',qualityPass:false,gpuExecuted:false});
 console.log('KW20_DETAIL_SOURCE_PREPARED');
}catch(error){await save('CHECK_FAILED.json',{status:'FAIL',checks,error:String(error.stack??error)});throw error;}
