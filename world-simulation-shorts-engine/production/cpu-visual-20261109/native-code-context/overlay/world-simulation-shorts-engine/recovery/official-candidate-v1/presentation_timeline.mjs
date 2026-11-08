import {writeFile} from 'node:fs/promises';
import {readPinnedServerFile} from './candidate_asset_snapshot.mjs';
/** Official 300-frame source preparation, never candidate-material admission. */
import {createHash} from 'node:crypto';
import path from 'node:path';
import {sealSceneChunks,verifySceneChunk} from './sealed_scene_chunks.mjs';
import {prepareRuntimeRequest,verifyPreparedRuntimeRequest,createPrivateTimelineRoot} from './capture_presentation.mjs';
import {canonicalJSON} from './region_source.mjs';
const hash=x=>createHash('sha256').update(x).digest('hex');
const check=(v,c)=>{if(!v)throw Error(c)};
export function continuityFor(plan,chunk){return {schema:'WORLD_ENGINE_SCENE_CONTINUITY_CONTEXT_V1',plan,chunk,expectedOriginalSHA256:plan.originalSHA256};}
export async function prepareTimelineRequest({request,cacheRoot}={}){
 // Input snapshot precedes first await; caller cannot mutate admission identity.
 const plan=sealSceneChunks(structuredClone(request));
 check(plan.original.totalFrames===300&&plan.original.durationSeconds===10,'UP2_TIMELINE_300_ONLY');
 check(path.isAbsolute(cacheRoot),'UP2_TIMELINE_ABSOLUTE_CACHE_REQUIRED');
 // Existing per-chunk preparation checks every ancestor, ownership and private
 // target. This parent is exclusive; no existing cache is overwritten.
 await createPrivateTimelineRoot(cacheRoot);
 const chunks=[];
 for(const chunk of plan.chunks){
  const prepared=await prepareRuntimeRequest({request:chunk.request,cacheRoot:path.join(cacheRoot,`chunk-${chunk.globalRange[0]}`),continuity:continuityFor(plan,chunk)});
  const verified=await verifyPreparedRuntimeRequest(prepared,continuityFor(plan,chunk));
  check(verified.status==='PASS','UP2_TIMELINE_CHUNK_SOURCE_INVALID');
  chunks.push({chunk,prepared});
 }
 const qualification={schema:'WORLD_ENGINE_PRESENTATION_TIMELINE_SOURCES_V1',totalFrames:300,originalSHA256:plan.originalSHA256,
  chunks:chunks.map(({chunk,prepared},index)=>({index,globalRange:chunk.globalRange,requestSHA256:chunk.requestSHA256,
   sourceQualification:prepared.sourceQualification,sourceQualificationWireJSON:prepared.sourceQualificationWireJSON,sourceQualificationSHA256:prepared.sourceQualificationSHA256}))};
 const wire=canonicalJSON(qualification);
 return {schema:'WORLD_ENGINE_PREPARED_PRESENTATION_TIMELINE_V1',totalFrames:300,plan,chunks,sourceQualification:qualification,
  sourceQualificationWireJSON:wire,sourceQualificationSHA256:hash(wire),sourceBindings:chunks.flatMap(c=>c.prepared.sourceBindings),candidateSourceAdmitted:false};
}
export async function verifyPreparedTimeline(value){
 const prepared=structuredClone(value),q=prepared.sourceQualification;
 check(prepared.schema==='WORLD_ENGINE_PREPARED_PRESENTATION_TIMELINE_V1'&&q?.schema==='WORLD_ENGINE_PRESENTATION_TIMELINE_SOURCES_V1','UP2_TIMELINE_SCHEMA');
 check(prepared.totalFrames===300&&prepared.plan.original.totalFrames===300&&q.totalFrames===300,'UP2_TIMELINE_TOTAL');
 const rebuilt=sealSceneChunks(prepared.plan.original);
 check(canonicalJSON(rebuilt)===canonicalJSON(prepared.plan),'UP2_TIMELINE_PLAN_CHANGED');
 check(prepared.chunks.length===rebuilt.chunks.length&&q.chunks.length===rebuilt.chunks.length,'UP2_TIMELINE_CHUNK_COUNT');
 for(let i=0;i<rebuilt.chunks.length;i++){
  const {chunk,prepared:p}=prepared.chunks[i];verifySceneChunk(rebuilt,chunk,rebuilt.originalSHA256);
  check(canonicalJSON(chunk)===canonicalJSON(rebuilt.chunks[i]),'UP2_TIMELINE_CHUNK_ORDER');
  check((await verifyPreparedRuntimeRequest(p,continuityFor(rebuilt,chunk))).status==='PASS','UP2_TIMELINE_SOURCE_CHANGED');
  const expected={index:i,globalRange:chunk.globalRange,requestSHA256:chunk.requestSHA256,sourceQualification:p.sourceQualification,sourceQualificationWireJSON:p.sourceQualificationWireJSON,sourceQualificationSHA256:p.sourceQualificationSHA256};
  check(canonicalJSON(expected)===canonicalJSON(q.chunks[i]),'UP2_TIMELINE_CHUNK_QUALIFICATION');
 }
 check(q.originalSHA256===rebuilt.originalSHA256&&canonicalJSON(q)===prepared.sourceQualificationWireJSON&&hash(prepared.sourceQualificationWireJSON)===prepared.sourceQualificationSHA256,'UP2_TIMELINE_SEAL');
 check(canonicalJSON(prepared.sourceBindings)===canonicalJSON(prepared.chunks.flatMap(c=>c.prepared.sourceBindings)),'UP2_TIMELINE_SOURCE_BINDINGS');
 return {status:'PASS',sourceQualificationSHA256:prepared.sourceQualificationSHA256,verifiedChunks:prepared.chunks.length,candidateSourceAdmitted:false};
}

/** Bound disk receipt avoids sending multi-megabyte prepared plans over stdin. */
export function summarizePreparedTimeline(prepared,record){
 return {schema:'WORLD_ENGINE_PREPARED_TIMELINE_RECORD_V1',totalFrames:prepared.totalFrames,plan:prepared.plan,
  sourceQualification:prepared.sourceQualification,sourceQualificationWireJSON:prepared.sourceQualificationWireJSON,
  sourceQualificationSHA256:prepared.sourceQualificationSHA256,sourceBindings:prepared.sourceBindings,record,
  sourceCredits:prepared.chunks.flatMap(c=>c.prepared.segments.map(row=>({sourceId:row.regionEvidence?.sourceId,
   attribution:row.regionEvidence?.attribution,license:row.regionEvidence?.license,sourceURL:row.sourceStyle?.sourceOriginal?.url}))),candidateSourceAdmitted:false};
}
export async function prepareTimelineRecord(args){
 const prepared=await prepareTimelineRequest(args),raw=Buffer.from(JSON.stringify(prepared));
 check(raw.length<=24*1024**2,'UP2_TIMELINE_PREPARED_RECORD_LIMIT');
 const name='PREPARED_TIMELINE.json';await writeFile(path.join(args.cacheRoot,name),raw,{flag:'wx',mode:0o600});
 return summarizePreparedTimeline(prepared,{name,bytes:raw.length,sha256:hash(raw)});
}
export async function verifyTimelineRecord({summary,cacheRoot}){
 summary=structuredClone(summary);
 check(summary?.schema==='WORLD_ENGINE_PREPARED_TIMELINE_RECORD_V1'&&summary.record?.name==='PREPARED_TIMELINE.json'
  &&summary.record.bytes<=24*1024**2,'UP2_TIMELINE_RECORD_SCHEMA');
 const raw=await readPinnedServerFile(cacheRoot,summary.record.name,summary.record),prepared=JSON.parse(raw);
 check(canonicalJSON(summarizePreparedTimeline(prepared,summary.record))===canonicalJSON(summary),'UP2_TIMELINE_RECORD_SUMMARY_CHANGED');
 return verifyPreparedTimeline(prepared);
}

/** Preserve Planner's native object order in an opaque wire string across Python persistence. */
export function buildTimelineCaptureWires({runtimeRequestWireJSON,plan,candidateActivation,candidateActivationSHA256}={}){
 check(typeof runtimeRequestWireJSON==='string','UP2_TIMELINE_NATIVE_WIRE_REQUIRED');
 const rebuilt=sealSceneChunks(JSON.parse(runtimeRequestWireJSON));
 check(rebuilt.original.totalFrames===300&&canonicalJSON(rebuilt)===canonicalJSON(plan),'UP2_TIMELINE_NATIVE_WIRE_PLAN_MISMATCH');
 if(candidateActivation!==undefined){
  check(hash(canonicalJSON(candidateActivation))===candidateActivationSHA256
   &&candidateActivation.originalSemanticSHA256===rebuilt.originalSHA256,'UP2_TIMELINE_WIRE_ACTIVATION_PIN');
 }else check(candidateActivationSHA256===undefined,'UP2_TIMELINE_WIRE_ORPHAN_ACTIVATION_PIN');
 return rebuilt.chunks.map(chunk=>{
  verifySceneChunk(rebuilt,chunk,rebuilt.originalSHA256);
  const envelope={schema:'WORLD_ENGINE_OFFICIAL_SCENE_CHUNK_CAPTURE_V1',plan:rebuilt,chunk};
  if(candidateActivation!==undefined)Object.assign(envelope,{candidateActivation,candidateActivationSHA256});
  const wireJSON=JSON.stringify(envelope);
  return {chunkRequestSHA256:chunk.requestSHA256,wireJSON,wireSHA256:hash(wireJSON)};
 });
}
