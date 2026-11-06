import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {analyzePresentationPrompt} from '../../recovery/universal-presentation-v2/presentation_prompt.mjs';
import {validatePresentation,presentationNativeMapOptions,presentationBoundarySegments} from '../../recovery/universal-presentation-v2/presentation_plan.mjs';
import {prepareNvidiaRuntimeRequest,verifyNvidiaPreparedRuntimeRequest} from '../../recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),[output,privateRoot]=process.argv.slice(2);
assert(path.isAbsolute(output)&&path.isAbsolute(privateRoot));await mkdir(output,{mode:0o700});
const hash=b=>createHash('sha256').update(b).digest('hex'),write=(name,x)=>writeFile(path.join(output,name),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const prepared=[],checks=[],record=(name,ok)=>{assert(ok,name);checks.push(name);};
try{
 for(let clip=1;clip<=2;clip++){
  const name=`KOREAN_WAR_20S_PART_${String(clip).padStart(2,'0')}.json`,raw=await readFile(path.join(here,name)),input=JSON.parse(raw);
  const analysis=await analyzePresentationPrompt(input,{allowTenSecondStudioSample:true});await write(`ANALYSIS_${clip}.json`,analysis);
  assert.equal(analysis.status,'PASS',JSON.stringify(analysis.issues));assert.equal(analysis.totalFrames,300);assert.equal(analysis.renderRequests.length,2);
  const request={schema:'WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2',durationSeconds:10,totalFrames:300,sourceInputSHA256:analysis.inputSHA256,transitions:analysis.transitionPlan,segments:analysis.renderRequests.map(r=>({sceneId:r.sceneId,startFrame:r.startFrame,endFrame:r.endFrame,scene:r.scene,region:r.region,presentation:r.presentation,inputTrace:r.inputTrace}))};
  const value=await prepareNvidiaRuntimeRequest({request,cacheRoot:path.join(privateRoot,'sources-'+clip),privateWorkspaceRoot:privateRoot,publicExportRoot:output});
  const verified=await verifyNvidiaPreparedRuntimeRequest({prepared:value,privateWorkspaceRoot:privateRoot,publicExportRoot:output});
  await write(`PREPARED_${clip}.json`,value);prepared.push(value);
  record(`clip_${clip}_existing_native_prepare_verify`,!!verified);
  record(`clip_${clip}_all_300_camera_frames`,value.segments.reduce((sum,s)=>sum+s.presentationPlan.cpuFrameBounds.length,0)===300);
  record(`clip_${clip}_same_internal_boundary`,JSON.stringify(value.segments[0].presentationPlan.cpuFrameBounds.at(-1))===JSON.stringify(value.segments[1].presentationPlan.cpuFrameBounds[0]));
  for(const s of value.segments){
   record(`no_modern_boundaries_${s.scene.id}`,presentationNativeMapOptions(s.presentation,0).boundaries===false&&presentationBoundarySegments({presentation:s.presentation}) .length===0);
   assert.throws(()=>validatePresentation({...s.presentation,mapStyle:{...s.presentation.mapStyle,nativeBoundaries:'false'}},{scene:s.scene}),/NATIVE_BOUNDARIES_BOOLEAN/);
   const oldStyle={preset:'REFERENCE_FOCUS_V2',revealFrames:1,countryFill:false};
   assert.equal(presentationNativeMapOptions({mapStyle:oldStyle},0).boundaries,true);
   record(`invalid_boundary_option_rejected_${s.scene.id}`,true);
  }
  await write(`INPUT_RECEIPT_${clip}.json`,{input:name,sha256:hash(raw),bytes:raw.length,frames:300,preparedVerified:verified,gpuExecuted:false});
 }
 const left=prepared[0].segments.at(-1),right=prepared[1].segments[0],lb=left.presentationPlan.cpuFrameBounds.at(-1),rb=right.presentationPlan.cpuFrameBounds[0];
 record('10s_boundary_camera_exact',JSON.stringify(lb)===JSON.stringify(rb));
 const visible=(s,f)=>s.presentation.labels.items.filter(x=>f>=x.startFrame&&f<x.endFrame).map(x=>({id:x.id,text:x.text,role:x.role,anchor:x.anchor,pin:x.pin}));
 record('10s_boundary_active_labels_exact',JSON.stringify(visible(left,149))===JSON.stringify(visible(right,0)));
 record('same_source_terrain',left.sourceStyle.terrainAsset.sourceOriginalSHA256===right.sourceStyle.terrainAsset.sourceOriginalSHA256);
 const boundary={cameraBounds:lb,labels:visible(left,149),geographicContext:'unchanged land context; no ownership claim',nativeBoundaries:false};
 await write('COMPOSE_PLAN.json',{schema:'WORLD_ENGINE_NEUTRAL_VIDEO_PLAN_V1',durationSeconds:20,fps:30,resolution:{width:1080,height:1920},scenes:[{sceneId:'clip-01',startFrame:0,endFrame:300,boundaryEnd:boundary},{sceneId:'clip-02',startFrame:300,endFrame:600,boundaryStart:boundary}]});
 await write('CHECK_RESULT.json',{status:'PASS_NEW_INPUT_PREPARATION_ONLY',checks,checkCount:checks.length,framesPrepared:600,oldPassSuitesRerun:0,paidGpuExecutions:0,actualVideoQuality:'UNREVIEWED',sourceScope:'Regional modern land context and official event chronology; no historical control polygon or measured troop route.'});
 console.log('KW20_NATIVE_INPUTS_PREPARED');
}catch(error){await write('CHECK_FAILED.json',{status:'FAIL',completedChecks:checks,preparedClipCount:prepared.length,error:String(error.stack??error)});throw error;}
