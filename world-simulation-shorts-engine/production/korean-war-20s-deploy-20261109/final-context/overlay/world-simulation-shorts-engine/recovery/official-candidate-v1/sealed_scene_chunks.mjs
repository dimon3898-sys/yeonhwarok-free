import {createHash} from 'node:crypto';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {canonicalJSON} from './region_source.mjs';
import {assertPresentationBoundaryContinuity} from './presentation_plan.mjs';
const check=(v,c)=>{if(!v)throw Error(c)},hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const hash=x=>createHash('sha256').update(canonicalJSON(x)).digest('hex');
function validateCore(request, maximum=240, predecessor=null){
 check(request?.schema==='WORLD_ENGINE_PRESENTATION_RUNTIME_REQUEST_V2','UP2_RUNTIME_REQUEST_SCHEMA');
 check(Number.isSafeInteger(request.totalFrames)&&request.totalFrames>=2&&request.totalFrames<=maximum,'UP2_RUNTIME_TOTAL_FRAMES');
 check(hex(request.sourceInputSHA256),'UP2_SOURCE_INPUT_HASH_REQUIRED');check(Array.isArray(request.segments)&&request.segments.length>=1&&request.segments.length<=16,'UP2_RUNTIME_SEGMENTS');
 let cursor=0;for(const[index,segment]of request.segments.entries()){check(segment.startFrame===cursor&&Number.isSafeInteger(segment.endFrame)&&segment.endFrame>cursor,'UP2_SEGMENT_FRAME_GAP_OR_OVERLAP');
  validateScenePlan(segment.scene);check(segment.scene.timing.total_frames===segment.endFrame-segment.startFrame&&segment.scene.timing.fps===30&&segment.scene.metadata.output.width===1080&&segment.scene.metadata.output.height===1920,'UP2_SEGMENT_SCENE_TIMING');
  check(['WAR','TRANSPORT'].includes(segment.scene.event_type)&&segment.scene.scale_intent.preferred==='REGIONAL','UP2_RENDER_FAMILY_OR_SCALE_UNSUPPORTED');
  check(!segment.scene.text?.length&&!segment.scene.causal_tracks?.length,'UP2_UNCONNECTED_VISIBLE_TEXT_OR_CAUSAL_TRACK_UNSUPPORTED');compileExistingEnginePlan(segment.scene);cursor=segment.endFrame;
  if(segment.presentation?.initialStateVisibility==='PRESERVE_PROVIDED')assertPresentationBoundaryContinuity((index===0?predecessor:request.segments[index-1]),segment);
 }
 check(cursor===request.totalFrames,'UP2_TOTAL_FRAME_SUM');
 const expected=request.segments.slice(1).map(s=>({type:'CUT',frame:s.startFrame}));check(canonicalJSON(request.transitions??[])===canonicalJSON(expected),'UP2_EXACT_SCENE_CUTS_REQUIRED');return true;
}
export function validateOriginalTimeline(original){
 check(original?.totalFrames<=240||(original?.totalFrames===300&&original?.durationSeconds===10),'UP2_CHUNK_TIMELINE_SCOPE');
 // Full original checks, including all authored inter-scene state continuity.
 validateCore(original,original.totalFrames===300?300:240);return true;
}
export function sealSceneChunks(input){
 const original=structuredClone(input);validateOriginalTimeline(original);
 const originalSHA256=hash(original),chunks=[];let group=[],size=0;
 const finish=()=>{if(!group.length)return;const start=group[0],end=group.at(-1)+1;
  const first=original.segments[start].startFrame,last=original.segments[end-1].endFrame;
  const request=structuredClone(original);delete request.durationSeconds;
  request.segments=request.segments.slice(start,end);for(const row of request.segments){row.startFrame-=first;row.endFrame-=first;}
  request.totalFrames=last-first;request.transitions=request.segments.slice(1).map(s=>({type:'CUT',frame:s.startFrame}));
  validateCore(request,240,start?original.segments[start-1]:null);
  chunks.push({schema:'WORLD_ENGINE_SEALED_SCENE_CHUNK_V1',originalSHA256,segmentRange:[start,end],globalRange:[first,last],requestSHA256:hash(request),request});group=[];size=0;
 };
 for(const[i,row]of original.segments.entries()){const n=row.endFrame-row.startFrame;check(n<=240,'UP2_CHUNK_COMPLETE_SCENE_REQUIRED');if(size+n>240)finish();group.push(i);size+=n;}finish();
 return {schema:'WORLD_ENGINE_SEALED_TIMELINE_V1',original,originalSHA256,chunks,productionAdmitted:false};
}
export function verifySceneChunk(envelope,chunk,expectedOriginalSHA256){
 check(hex(expectedOriginalSHA256)&&hash(envelope.original)===expectedOriginalSHA256&&envelope.originalSHA256===expectedOriginalSHA256,'UP2_CHUNK_ORIGINAL_PIN');
 const rebuilt=sealSceneChunks(envelope.original);
 check(rebuilt.chunks.some(c=>canonicalJSON(c)===canonicalJSON(chunk)),'UP2_CHUNK_IDENTITY');
 return {status:'CPU_CONTINUITY_VERIFIED',globalRange:chunk.globalRange,requestSHA256:chunk.requestSHA256,sourceAdmission:false};
}

export function validateSealedPreparedRequest(request, continuity){
 check(continuity?.schema==='WORLD_ENGINE_SCENE_CONTINUITY_CONTEXT_V1','UP2_CHUNK_CONTEXT_SCHEMA');
 const {plan,chunk,expectedOriginalSHA256}=continuity;
 verifySceneChunk(plan,chunk,expectedOriginalSHA256);
 // Prepared records add verified source fields; authored request fields must
 // remain byte-semantic identical. Do not let prepared additions replace them.
 for(const [key,value] of Object.entries(chunk.request)){
  if(key==='segments')continue;
  if(key==='schema')continue;
  check(canonicalJSON(request[key])===canonicalJSON(value),'UP2_CHUNK_AUTHORED_REQUEST_CHANGED');
 }
 check(request.segments.length===chunk.request.segments.length,'UP2_CHUNK_SEGMENT_COUNT');
 for(let i=0;i<request.segments.length;i++)for(const[key,value]of Object.entries(chunk.request.segments[i]))
  check(canonicalJSON(request.segments[i][key])===canonicalJSON(value),'UP2_CHUNK_AUTHORED_SCENE_CHANGED');
 const first=chunk.segmentRange[0];validateCore(request,240,first?plan.original.segments[first-1]:null);
 return true;
}
