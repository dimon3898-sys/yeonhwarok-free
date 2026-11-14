/** Explicit display intent over server-reviewed history and preserved geometry.
 * No renderer, geometry generation, source reclassification or GPU execution.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {analyzePrompt,canonicalJSON} from '../universal-data-pipeline-v1/prompt_pipeline.mjs';
import {reviewedHistoricalRegistrySHA256} from '../universal-data-pipeline-v1/reviewed_historical_registry.mjs';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {validatePresentation} from './presentation_plan.mjs';
export const AUTHORED_HISTORY_SCHEMA='WORLD_ENGINE_AUTHORED_HISTORY_INPUT_V1';
export const HISTORY_RUNTIME_PROFILE='HISTORICAL_CONTINUOUS_600F_V1';
export const HISTORY_ADMISSION_SCHEMA='WORLD_ENGINE_AUTHORED_HISTORY_ADMISSION_V1';
export const HISTORY_CATALOG_SHA256='53335eac8281bf37efb9226c6967e6151d04bacfc31fda36ace16bfaf353e788';
const HERE=path.dirname(fileURLToPath(import.meta.url)),REPO=path.resolve(HERE,'../../..');
const hash=x=>createHash('sha256').update(typeof x==='string'||Buffer.isBuffer(x)?x:canonicalJSON(x)).digest('hex');
const copy=structuredClone,check=(v,c)=>{if(!v)throw Error('UP2_HISTORY_'+c);};
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&Object.keys(v).every(k=>keys.includes(k));
async function pinnedSource(row){
 const file=path.resolve(REPO,row.path);check(file.startsWith(REPO+'/world-simulation-shorts-engine/')&&await fs.realpath(file)===file,'SOURCE_PATH');
 const raw=await fs.readFile(file);check(hash(raw)===row.sha256,'SOURCE_HASH');return JSON.parse(raw);
}
async function reviewedSource(source){
 check(exact(source,['id','runtimeSHA256','continuousSHA256','periods']),'SOURCE_FIELDS');
 const raw=await fs.readFile(path.join(HERE,'HISTORY_SOURCE_CATALOG.json'));check(hash(raw)===HISTORY_CATALOG_SHA256,'CATALOG_HASH');
 const catalog=JSON.parse(raw);check(catalog.schema==='WORLD_ENGINE_REVIEWED_CONTINUOUS_SOURCE_CATALOG_V1','CATALOG_SCHEMA');
 const record=catalog.records.find(x=>x.id===source.id);check(record&&record.reviewStatus==='SOURCE_BOUND_DISPLAY_INTERPOLATION_ONLY','SOURCE_NOT_REGISTERED');
 check(source.runtimeSHA256===record.runtime.sha256&&source.continuousSHA256===record.continuousSHA256&&canonicalJSON(source.periods)===canonicalJSON(record.periods),'SOURCE_REFERENCE_CHANGED');
 const original=await pinnedSource(record.sourceInput),runtime=await pinnedSource(record.runtime);
 check(original.data.simulationType==='HISTORICAL'&&runtime.segments.length===1,'HISTORICAL_SOURCE_REQUIRED');
 // Run the existing HISTORICAL evidence owner on unchanged canonical facts.
 // Its legacy texture selector is replaced by the actual NVIDIA source gate,
 // not by a caller assertion. No evidence/date/geometry errors are filtered.
 const audit=analyzePrompt(original.data),issues=audit.issues.filter(x=>x.code!=='SOURCE_REGION_NOT_AVAILABLE');
 check(issues.length===0&&audit.sceneResults.length===1&&audit.sceneResults[0].issues.every(x=>x.code==='SOURCE_REGION_NOT_AVAILABLE'),'SOURCE_EVIDENCE_REJECTED');
 const segment=runtime.segments[0],scene=segment.scene,item=segment.presentation.territoryChanges?.items?.[0];
 check(scene.event_type==='WAR'&&scene.time_steps.length===2&&segment.presentation.territoryChanges.profile==='HISTORICAL_CONTINUOUS_V1'&&hash(item.continuous)===record.continuousSHA256,'CONTINUOUS_SOURCE_BINDING');
 const facts=original.data.scenes[0].facts;
 check(canonicalJSON(scene.geometries)===canonicalJSON(facts.geometries)&&canonicalJSON(scene.source_notes)===canonicalJSON(facts.source_notes),'SOURCE_FACTS_CHANGED');
 for(const step of scene.time_steps){const fact=facts.stages.find(x=>x.id===step.id);check(fact&&canonicalJSON(fact.date)===canonicalJSON(step.date),'SOURCE_PERIOD_CHANGED');}
 return{record,segment,original,sourceEvidence:{owner:'UNCHANGED_HISTORICAL_CANONICAL_FACTS_GATE',registrySHA256:reviewedHistoricalRegistrySHA256,sourceInputSHA256:record.sourceInput.sha256,canonicalFactsSHA256:hash(facts),sourceRuntimeSHA256:record.runtime.sha256,continuousSHA256:record.continuousSHA256,catalogSHA256:HISTORY_CATALOG_SHA256}};
}
export async function compileAuthoredHistory(input){
 check(exact(input,['schema','simulationType','source','output','timing','presentation']),'INPUT_FIELDS');
 check(input.schema===AUTHORED_HISTORY_SCHEMA&&input.simulationType==='HISTORICAL','EXPLICIT_PROFILE_REQUIRED');
 check(canonicalJSON(input.output)===canonicalJSON({width:1080,height:1920,fps:30,totalFrames:600,durationSeconds:20,codec:'h264',audio:false}),'EXACT_600_OUTPUT_REQUIRED');
 check(exact(input.timing,['territoryStartFrame','territoryEndFrame','finalHoldFrames']),'TIMING_FIELDS');
 const t=input.timing,n=600;
 check(Object.values(t).every(Number.isSafeInteger)&&t.territoryStartFrame>=2&&t.finalHoldFrames>=30&&t.territoryEndFrame>t.territoryStartFrame&&t.territoryEndFrame<=n-t.finalHoldFrames,'TIMING_RANGE');
 check(exact(input.presentation,['camera','mapStyle','territoryColors','labels']),'PRESENTATION_FIELDS');
 const source=await reviewedSource(input.source),s=copy(source.segment),scene=s.scene,p=s.presentation;
 const effect=p.territoryChanges.items[0];check(t.territoryEndFrame-t.territoryStartFrame===effect.continuous.frames.length,'REUSED_GEOMETRY_TIME_BINDING');
 s.startFrame=0;s.endFrame=n;
 scene.timing={...scene.timing,total_frames:n,duration_seconds:20,initial_reveal_frames:t.territoryStartFrame,state_transition_frames:n-t.finalHoldFrames-t.territoryStartFrame,action_frames:n-t.finalHoldFrames,final_hold_frames:t.finalHoldFrames};
 scene.time_steps[0].transition_frames=t.territoryStartFrame;scene.time_steps[1].start_frame=t.territoryStartFrame;scene.time_steps[1].transition_frames=scene.timing.state_transition_frames;
 scene.beats=[['EVENT_ACTION',0,t.territoryStartFrame],['STATE_CHANGE',t.territoryStartFrame,n-t.finalHoldFrames],['HOLD',n-t.finalHoldFrames,n]].map(([type,a,b],i)=>({id:'BEAT_'+String(i+1).padStart(2,'0'),type,start_frame:a,end_frame:b,duration_frames:b-a,geometry_refs:copy(scene.camera_intent.target_geometry_refs),...(type==='HOLD'?{camera_intent:'LOCK'}:{})}));
 Object.assign(p,copy(input.presentation));effect.startFrame=t.territoryStartFrame;effect.endFrame=t.territoryEndFrame;
 p.territoryChanges.config.visualProfile='FRONTIER_LIGHT_V1';
 check(p.camera.mode==='GEOGRAPHIC_TRACK'&&p.mapStyle.nativeBoundaries===false,'GEOGRAPHIC_HISTORY_PRESENTATION_REQUIRED');
 validateScenePlan(scene);const presentation=validatePresentation(p,{scene,region:s.region});
 // The compiled packet carries only consumed fields, no stale automatic audit.
 const segment={sceneId:s.sceneId,startFrame:0,endFrame:n,scene,region:s.region,presentation,
  inputTrace:[{origin:'EXPLICIT_AUTHORED_HISTORY_DISPLAY_V1',source:copy(input.source),sourceEvidence:source.sourceEvidence,sourceDatesChanged:false,sourceGeometryChanged:false,interpolationRegenerated:false,authoredInputSHA256:hash(input)}]};
 compileExistingEnginePlan(scene);
 const admission={schema:HISTORY_ADMISSION_SCHEMA,status:'PASS',simulationType:'HISTORICAL',scope:HISTORY_RUNTIME_PROFILE,source:copy(input.source),sourceEvidence:source.sourceEvidence,authoredInputSHA256:hash(input),runtimeSegmentSHA256:hash(segment),paidExecutionAllowed:false};
 return{schema:'WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2',compilerVersion:'AUTHORED_HISTORY_V1',status:'PASS',issues:[],clarifications:[],simulationType:'HISTORICAL',historicalRenderAllowed:true,paidExecutionAllowed:false,
  inputSHA256:hash(input),totalFrames:600,durationSeconds:20,renderRequests:[segment],renderableSceneIds:[s.sceneId],blockedSceneIds:[],transitionPlan:[],sceneResults:[{sceneId:s.sceneId,status:'PASS',issues:[]}],historicalAdmission:admission,inputTrace:copy(segment.inputTrace)};
}
export async function verifyAuthoredHistoryRuntime(runtime){
 check(runtime?.totalFrames===600&&runtime.durationSeconds===20&&runtime.profile===HISTORY_RUNTIME_PROFILE&&runtime.simulationType==='HISTORICAL','RUNTIME_PROFILE');
 const a=runtime.historicalAdmission;check(a?.schema===HISTORY_ADMISSION_SCHEMA&&a.status==='PASS'&&a.scope===HISTORY_RUNTIME_PROFILE&&a.simulationType==='HISTORICAL'&&a.paidExecutionAllowed===false,'ADMISSION_REQUIRED');
 check(runtime.segments?.length===1&&runtime.transitions?.length===0,'CONTINUOUS_SINGLE_SEGMENT_REQUIRED');
 const s=runtime.segments[0],e=s.presentation?.territoryChanges?.items?.[0];
 check(e&&s.presentation.territoryChanges.items.length===1,'SINGLE_STATE_CHANGE_REQUIRED');
 const input={schema:AUTHORED_HISTORY_SCHEMA,simulationType:'HISTORICAL',source:a.source,output:{width:1080,height:1920,fps:30,totalFrames:600,durationSeconds:20,codec:'h264',audio:false},
  timing:{territoryStartFrame:e.startFrame,territoryEndFrame:e.endFrame,finalHoldFrames:s.scene.timing.final_hold_frames},
  presentation:Object.fromEntries(['camera','mapStyle','territoryColors','labels'].map(k=>[k,s.presentation[k]]))};
 const compiled=await compileAuthoredHistory(input);
 check(runtime.sourceInputSHA256===compiled.inputSHA256&&canonicalJSON(compiled.historicalAdmission)===canonicalJSON(a)&&canonicalJSON(compiled.renderRequests[0])===canonicalJSON(s),'RUNTIME_SOURCE_OR_DISPLAY_CHANGED');
 return{status:'PASS',profile:HISTORY_RUNTIME_PROFILE,sourceEvidence:a.sourceEvidence};
}
