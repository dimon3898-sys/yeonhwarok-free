/** One private frame identity for every owner consumer; no copied/faked fields.
 * Current qualified history has no full ownership source. No scalar simulation,
 * complementary area fill, or interpolated historical movement is generated.
 */
const knownStates=new WeakSet(),clone=x=>structuredClone(x),hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const fail=code=>{throw Error(code);};
function freeze(x){if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;}
function json(raw){const text=typeof raw==='string'?raw:new TextDecoder().decode(raw);return JSON.parse(text);}
async function sha(raw){const bytes=typeof raw==='string'?new TextEncoder().encode(raw):raw;
 return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
function partition(rows,total){let end=0;if(!Array.isArray(rows)||!rows.length)fail('CONTROL_SOURCE_PARTITION_REQUIRED');
 for(const row of rows){if(!Number.isSafeInteger(row.startFrame)||row.startFrame!==end||!Number.isSafeInteger(row.endFrame)
  ||row.endFrame<=end||row.endFrame>total)fail('CONTROL_SOURCE_PARTITION_REQUIRED');end=row.endFrame;}
 if(end!==total)fail('CONTROL_EXACT_GLOBAL_CLOCK_REQUIRED');}
export async function createQualifiedControlBridge({timelineBytes,profileBytes,catalogBytes,
 expectedTimelineSHA256,expectedProfileSHA256,expectedCatalogSHA256,sourcePlanSHA256,purpose}={}){
 if(purpose!=='QUALIFIED_SOURCE_REVIEW')fail('CONTROL_SOURCE_REVIEW_ONLY');
 for(const[raw,expected]of [[timelineBytes,expectedTimelineSHA256],[profileBytes,expectedProfileSHA256],[catalogBytes,expectedCatalogSHA256]]){
  if(!hex(expected)||await sha(raw)!==expected)fail('CONTROL_ACTUAL_SOURCE_SHA_MISMATCH');}
 const t=json(timelineBytes),p=json(profileBytes),c=json(catalogBytes);
 if(t.schema!=='WORLD_ENGINE_QUALIFIED_CONTROL_TIMELINE_V2'||t.version!==2||p.schema!=='WORLD_ENGINE_QUALIFIED_EVENT_PROFILE_V2'
  ||c.schema!=='WORLD_ENGINE_HISTORY_SOURCE_CATALOG_V2'||!hex(sourcePlanSHA256)
  ||[t,p,c].some(x=>x.sourcePlanSHA256!==sourcePlanSHA256)
  ||t.eventProfileSHA256!==expectedProfileSHA256||t.sourceCatalogSHA256!==expectedCatalogSHA256)
  fail('CONTROL_QUALIFIED_SOURCE_BINDING_REQUIRED');
 if(t.productionReady!==false||t.ownerFields?.length!==0||t.transitions?.length!==0
  ||p.fullControlStates?.length!==0||p.controlTransitions?.length!==0)fail('CONTROL_FULL_OWNER_SOURCE_ADAPTER_REQUIRED');
 if(!Number.isSafeInteger(t.totalFrames)||t.totalFrames<2||!Number.isSafeInteger(t.fps)||t.fps<1
  ||p.totalFrames!==t.totalFrames||p.fps!==t.fps)fail('CONTROL_EXACT_GLOBAL_CLOCK_REQUIRED');
 if(t.noUnknownComplement!==true||t.noPartialFrontClosure!==true||t.noPreviousStateFallback!==true)
  fail('CONTROL_NO_INFERRED_OWNER_POLICY_REQUIRED');
 partition(t.states,t.totalFrames);partition(t.sourceObservations,t.totalFrames);
 partition(p.chapters,t.totalFrames);partition(p.sourceSchedule,t.totalFrames);
 if(t.states.length!==p.chapters.length||t.sourceObservations.length!==p.sourceSchedule.length)fail('CONTROL_SOURCE_SHAPE_CHANGED');
 for(let i=0;i<t.states.length;i++){
  const state=t.states[i],chapter=p.chapters[i];
  for(const key of ['chapterId','eventId','startFrame','endFrame','controlStartState','controlEndState'])
   if(state[key]!==chapter[key])fail('CONTROL_SOURCE_CHAPTER_CHANGED');
  if(state.truthKind!=='unknown'||state.controlStartState!==null||state.controlEndState!==null
   ||state.ownerMasks?.length!==0||state.sharedFront!==null||state.asOfDate!==null
   ||state.unknownMask!==null||state.contestedMask!==null||state.interpolationProgress!==null)
   fail('CONTROL_UNKNOWN_OWNER_MUST_REMAIN_NULL');
 }
 for(let i=0;i<t.sourceObservations.length;i++){
  const row=t.sourceObservations[i],original=p.sourceSchedule[i];
  for(const key of ['startFrame','endFrame','chapterId','stateId','kind','truthKind','sourceDate','sourceIds','visibleQualifier'])
   if(JSON.stringify(row[key])!==JSON.stringify(original[key]))fail('CONTROL_SOURCE_OBSERVATION_CHANGED');
  if(!Array.isArray(row.sourceIds)||row.sourceIds.some(id=>!Object.hasOwn(c.sources,id)))fail('CONTROL_SOURCE_REFERENCE_UNAVAILABLE');
  if(row.truthKind==='unknown'&&(row.stateId!==null||row.sourceIds.length||row.sourceDate!==null))fail('CONTROL_UNKNOWN_CANNOT_REUSE_PREVIOUS_STATE');
 }
 let disposed=false,last=null;
 function evaluateControlState(globalFrame){
  if(disposed)fail('CONTROL_BRIDGE_DISPOSED');
  if(!Number.isSafeInteger(globalFrame)||globalFrame<0||globalFrame>=t.totalFrames)fail('CONTROL_GLOBAL_FRAME_OUT_OF_RANGE');
  if(last?.globalFrame===globalFrame)return last;
  const chapter=t.states.find(x=>globalFrame>=x.startFrame&&globalFrame<x.endFrame),
   observation=t.sourceObservations.find(x=>globalFrame>=x.startFrame&&globalFrame<x.endFrame);
  const state=freeze({schema:'WORLD_ENGINE_QUALIFIED_CONTROL_FRAME_V2',globalFrame,frame:globalFrame,
   chapterId:chapter.chapterId,eventId:chapter.eventId,stateId:null,truthKind:'unknown',sourceIds:[],asOfDate:null,
   ownerMasks:[],unknownMask:null,unknownMaskStatus:'GEOMETRY_UNAVAILABLE',contestedMask:null,sharedFront:null,
   interpolationProgress:null,sourceHashes:{sourcePlanSHA256,eventProfileSHA256:expectedProfileSHA256,
    sourceCatalogSHA256:expectedCatalogSHA256,timelineSHA256:expectedTimelineSHA256},
   qualifiedSourceObservation:clone(observation),ownerFieldAvailable:false,synthetic:false,
   renderAllowed:false,noUnknownComplement:true,noPreviousStateFallback:true});
  knownStates.add(state);last=state;return state;
 }
 return Object.freeze({evaluateControlState,dispose(){disposed=true;last=null;},
  evidence:freeze({schema:'WORLD_ENGINE_QUALIFIED_CONTROL_BRIDGE_V2',timelineSHA256:expectedTimelineSHA256,
   productionReady:false,scalarControlCompiled:false,historicalMorphDrawn:false,
   actualExistingScalarSource:'web/map_infographic_v1/territory_control_adapter_v1.mjs',
   scalarAvailability:'ORIGINAL_SCALAR_AVAILABLE_BUT_INPUT_BLOCKED',boundedFrameCacheEntries:1})});
}
/** Explicitly verifies an absent owner draw too: zero is never an executed morph. */
export function assertControlConsumerIdentity({state,area,front,terrain}={}){
 if(!knownStates.has(state)||state.synthetic!==false)fail('CONTROL_ACTUAL_EVALUATED_FRAME_REQUIRED');
 for(const consumer of [area,front,terrain]){
  if(!consumer||consumer.field!==state||consumer.globalFrame!==state.globalFrame)fail('CONTROL_CONSUMERS_MUST_SHARE_EXACT_FRAME_IDENTITY');
  if(consumer.ownerDrawCount!==0)fail('CONTROL_DRAW_BLOCKED_WITHOUT_OWNER_FIELD');
 }
 return freeze({globalFrame:state.globalFrame,sameFieldIdentity:true,status:'NO_FULL_OWNER_DRAW_SOURCE_BLOCKED',
  ownerDrawCount:0,frontMorphDrawCount:0,terrainLightingConnected:false,historicalMorphVerified:false});
}
