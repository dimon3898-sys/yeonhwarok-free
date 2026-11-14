/** Generic authored historical windows over existing render/display functions. */
import {canonicalJSON} from '../universal-data-pipeline-v1/prompt_pipeline.mjs';
import {compileReviewedHistoryDisplay} from './history_authored_v1.mjs';
import {loadExternalHistoryDataset,dataHash} from './external_history_data.mjs';
import {WINDOW_RUNTIME_PROFILE,validateTimelineWindow} from './timeline_window.mjs';
export const HISTORY_INPUT_V2='WORLD_ENGINE_AUTHORED_HISTORY_INPUT_V2';
export const HISTORY_ADMISSION_V2='WORLD_ENGINE_AUTHORED_HISTORY_ADMISSION_V2';
export const HISTORY_EXECUTION_PROFILE_V2='GCUBE_NVIDIA_HISTORICAL_V2';
const check=(v,c)=>{if(!v)throw Error('UP2_HISTORY_V2_'+c);};
const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&Object.keys(v).every(k=>keys.includes(k));
export async function compileHistoryInputV2(input,operator={}){
 check(exact(input,['schema','simulationType','source','output','timeline','presentation']),'INPUT_FIELDS');
 check(input.schema===HISTORY_INPUT_V2&&input.simulationType==='HISTORICAL','EXPLICIT_PROFILE');
 const o=input.output;
 check(exact(o,['width','height','fps','totalFrames','durationSeconds','codec','audio'])&&o.width===1080&&o.height===1920&&o.fps===30&&o.codec==='h264'&&o.audio===false&&[6,10,20].includes(o.durationSeconds)&&o.totalFrames===o.durationSeconds*30,'OUTPUT_CONTRACT');
 const timeline=input.timeline;
 check(exact(timeline,['totalFrames','timing','window'])&&Number.isSafeInteger(timeline.totalFrames)&&timeline.totalFrames>=2&&timeline.totalFrames<=600,'TIMELINE_FIELDS');
 check(exact(timeline.window,['startFrame','endFrame']),'WINDOW_REQUIRED');
 validateTimelineWindow(timeline.window,timeline.totalFrames,o.totalFrames);
 const t=timeline.timing,n=timeline.totalFrames;
 check(exact(t,['territoryStartFrame','territoryEndFrame','finalHoldFrames'])&&Object.values(t).every(Number.isSafeInteger)&&t.territoryStartFrame>=2&&t.finalHoldFrames>=2&&t.territoryEndFrame>t.territoryStartFrame&&t.territoryEndFrame<=n-t.finalHoldFrames,'TIMING_RANGE');
 check(exact(input.presentation,['camera','mapStyle','territoryColors','labels']),'PRESENTATION_FIELDS');
 // Offset playback cannot silently reset stateful geographic label placement.
 if(timeline.window.startFrame>0)check(input.presentation.mapStyle?.physicalContext!=='NATURAL_EARTH_V1'&&(!input.presentation.labels?.enabled||input.presentation.labels.items.every(x=>['TITLE','TIMELINE','DISCLOSURE'].includes(x.screenPlacement))),'STATEFUL_LABEL_WINDOW_NOT_ADMITTED');
 const source=await loadExternalHistoryDataset(input.source,operator),inputSHA256=dataHash(input);
 const sourceSegment=compileReviewedHistoryDisplay(source,{timing:t,presentation:input.presentation,totalFrames:n,inputTrace:[{origin:'EXPLICIT_AUTHORED_HISTORY_DISPLAY_V2',source:structuredClone(input.source),sourceEvidence:source.sourceEvidence,sourceDatesChanged:false,sourceGeometryChanged:false,interpolationRegenerated:false,authoredInputSHA256:inputSHA256}]});
 const segment={...sourceSegment,endFrame:o.totalFrames,timelineWindow:structuredClone(timeline.window)};
 const historicalAdmission={schema:HISTORY_ADMISSION_V2,status:'PASS',scope:WINDOW_RUNTIME_PROFILE,simulationType:'HISTORICAL',source:structuredClone(input.source),sourceEvidence:source.sourceEvidence,timeline:structuredClone(timeline),authoredInputSHA256:inputSHA256,runtimeSegmentSHA256:dataHash(segment),paidExecutionAllowed:false};
 return {schema:'WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2',compilerVersion:'AUTHORED_HISTORY_V2',status:'PASS',issues:[],clarifications:[],simulationType:'HISTORICAL',historicalRenderAllowed:true,paidExecutionAllowed:false,inputSHA256,totalFrames:o.totalFrames,durationSeconds:o.durationSeconds,renderRequests:[segment],renderableSceneIds:[segment.sceneId],blockedSceneIds:[],transitionPlan:[],sceneResults:[{sceneId:segment.sceneId,status:'PASS',issues:[]}],historicalAdmission,inputTrace:structuredClone(segment.inputTrace)};
}
export async function verifyHistoryInputV2Runtime(runtime,operator={}){
 check(runtime?.profile===WINDOW_RUNTIME_PROFILE&&runtime.simulationType==='HISTORICAL'&&runtime.segments?.length===1&&runtime.transitions?.length===0,'RUNTIME_PROFILE');
 const a=runtime.historicalAdmission,s=runtime.segments[0];
 check(a?.schema===HISTORY_ADMISSION_V2&&a.status==='PASS'&&a.scope===WINDOW_RUNTIME_PROFILE&&a.paidExecutionAllowed===false,'ADMISSION_REQUIRED');
 const input={schema:HISTORY_INPUT_V2,simulationType:'HISTORICAL',source:a.source,output:{width:1080,height:1920,fps:30,totalFrames:runtime.totalFrames,durationSeconds:runtime.durationSeconds,codec:'h264',audio:false},timeline:a.timeline,presentation:Object.fromEntries(['camera','mapStyle','territoryColors','labels'].map(k=>[k,s.presentation[k]]))};
 const compiled=await compileHistoryInputV2(input,operator);
 check(runtime.sourceInputSHA256===compiled.inputSHA256&&canonicalJSON(a)===canonicalJSON(compiled.historicalAdmission)&&canonicalJSON(s)===canonicalJSON(compiled.renderRequests[0]),'RUNTIME_SOURCE_OR_DISPLAY_CHANGED');
 return {status:'PASS',profile:WINDOW_RUNTIME_PROFILE,sourceEvidence:a.sourceEvidence};
}
