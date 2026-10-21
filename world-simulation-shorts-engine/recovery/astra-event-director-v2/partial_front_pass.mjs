/** Actual source-only extension over original Area V3. No ownership inference.
 * This lane does not coerce a pre-UN ROK front into legacy OBSERVED_UN_FRONT.
 * Root compiler must first bind the exact source GeoJSON bytes and review proof.
 */
import {compileAreaIntent,compileAreaPlan,evaluateAreaFrame} from '/modules/area_core_v3.mjs';
import {createProductionAreaPass} from '/production-v3/production_area_pass.mjs';
import {sourceLineChunks} from '/front-v4/front_visual.mjs';
const clone=x=>structuredClone(x),hex=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x),
 fail=code=>{throw Error(code);};
export function compileQualifiedPartialFronts({profile,fronts,origin}={}){
 if(profile?.schema!=='WORLD_ENGINE_QUALIFIED_EVENT_PROFILE_V2'||!Number.isSafeInteger(profile.totalFrames)
  ||!Number.isSafeInteger(profile.fps)||!Array.isArray(profile.sourceSchedule)
  ||!Array.isArray(fronts)||fronts.length>64)fail('DIRECTOR_PARTIAL_SOURCE_PROFILE_REQUIRED');
 const ids=new Set(),compiled=[];
 for(const front of fronts){
  const source=front?.source;
  if(typeof front?.frontId!=='string'||!front.frontId||ids.has(front.frontId)
   ||front.runtimeAdmission!=='QUALIFIED_SOURCE_REVIEW_ONLY'||front.fullControlPolygon!==false
   ||front.renderConsumer!=='DIRECTOR_ADDITIONAL_PARTIAL_FRONT'||!hex(front.geoJsonSha256)
   ||typeof front.sourceFile!=='string'||!front.sourceFile||front.sourceFile.startsWith('/')
   ||front.sourceFile.split('/').some(x=>!x||x==='.'||x==='..')||/[\\\0]/.test(front.sourceFile)
   ||typeof source?.reference!=='string'||!source.reference.trim()
   ||!hex(source.documentSha256)||!hex(source.rasterSha256)
   ||source.cartographicAccuracy!=='UNKNOWN_NOT_CERTIFIED'
   ||typeof front.sourceLabel!=='string'||!front.sourceLabel.trim()
   ||typeof front.mapDate!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(front.mapDate))
   fail('DIRECTOR_QUALIFIED_PARTIAL_FRONT_PROOF_REQUIRED');
  const rows=profile.sourceSchedule.filter(x=>x.stateId===front.frontId);
  if(!rows.length||rows.some(row=>row.truthKind!=='observed'||row.sourceDate!==front.mapDate
    ||!row.sourceIds.includes(front.frontId)))fail('DIRECTOR_PARTIAL_ACTUAL_SOURCE_SCHEDULE_REQUIRED');
  const sourceRecord={source_type:'OFFICIAL_ARCHIVAL_MAP_APPROXIMATE_DIGITIZATION',
   source_reference:source.reference,verification_status:'VERIFIED'},
   chunks=sourceLineChunks(front.geometry),lines=chunks.map((chunk,index)=>({id:front.frontId+'-part-'+index,
    geometry:chunk.geometry,source:sourceRecord,role:'FRONT_LINE',style_role:'PRIMARY'})),
   intent=compileAreaIntent({data_mode:'PRODUCTION',semantic_mode:'SUPPLIED_OBSERVED_STATES',origin,
    source:sourceRecord,fronts:lines}),
   plan=compileAreaPlan(intent,{fps:profile.fps,total_frames:1,
    operations:[{type:'AREA_HOLD',start_frame:0,duration_frames:1}]});
  ids.add(front.frontId);compiled.push({front:clone(front),plan,sourceRecord,
   sourceGeometryBinding:JSON.stringify(front.geometry),sourceChunks:clone(chunks)});
 }
 return{profile:clone(profile),fronts:compiled};
}
export function createQualifiedPartialFrontPass({canvas,profile,fronts,origin,productionVisualProfile}={}){
 const compiled=compileQualifiedPartialFronts({profile,fronts,origin}),
  pass=compiled.fronts.length?createProductionAreaPass({canvas,profile:productionVisualProfile,bindings:[],probeVariant:'AFTER'}):null;
 let disposed=false;
 return{draw({stateId,globalFrame,project,safeArea,protectedGraphics=[],boundarySegments=[]}={}){
  if(disposed)fail('DIRECTOR_PARTIAL_FRONT_PASS_DISPOSED');
  if(!Number.isSafeInteger(globalFrame)||globalFrame<0||globalFrame>=compiled.profile.totalFrames)
   fail('DIRECTOR_PARTIAL_GLOBAL_FRAME_REQUIRED');
  const row=compiled.profile.sourceSchedule.find(x=>globalFrame>=x.startFrame&&globalFrame<x.endFrame);
  if(!row)fail('DIRECTOR_PARTIAL_SOURCE_SCHEDULE_REQUIRED');
  const selected=compiled.fronts.find(x=>x.front.frontId===stateId);
  if(!selected){
   if(compiled.fronts.some(x=>x.front.frontId===row.stateId))fail('DIRECTOR_PARTIAL_ACTIVE_STATE_OMITTED');
   return null;
  }
  if(row.stateId!==stateId||row.truthKind!=='observed'||row.sourceDate!==selected.front.mapDate)
   fail('DIRECTOR_PARTIAL_FRAME_SOURCE_MISMATCH');
  if(typeof project!=='function'||!Array.isArray(protectedGraphics)||!Array.isArray(boundarySegments))
   fail('DIRECTOR_PARTIAL_NATIVE_FRAME_CONTEXT_REQUIRED');
  const base=evaluateAreaFrame(selected.plan,0,{project}),controls={...clone(base),frame:globalFrame,
   localFrame:globalFrame,timeSeconds:globalFrame/compiled.profile.fps,state:'QUALIFIED_PARTIAL_FRONT_HOLD',
   stateId,areas:[],observedSnapshotOnly:true,coordinatesInterpolated:false},
   graphics=pass.draw({controls,project,safeArea,protectedGraphics,boundarySegments:[]});
  if(controls.areas.length||!controls.fronts.length||graphics.areas?.length)
   fail('DIRECTOR_PARTIAL_FRONT_CANNOT_FILL_OWNERSHIP');
  return{controls,graphics,globalFrame,stateId,sourceQualifier:selected.front.sourceLabel,
   sourceDate:selected.front.mapDate,source:clone(selected.front.source),sourceFile:selected.front.sourceFile,
   geoJsonSha256:selected.front.geoJsonSha256,sourceGeometryBinding:selected.sourceGeometryBinding,
   sourceChunkCount:selected.sourceChunks.length,sourceGeoJsonVerifiedBy:'ROOT_CANONICAL_COMPILER_BYTE_HASH',
   sourceFrontDrawRequested:true,sourceAreaDrawCount:0,fullControlGeometryDrawn:false,
   coordinatesInterpolated:false,noGapBridging:true,unknownComplementInferred:false,
   sourceSide:sourceSide(selected.front.source),
   boundaryPolicy:'QUALIFIED_SOURCE_FRONT_ABOVE_STATIC_BOUNDARY',nativeBoundaryRestoreUnchanged:true,
   protectedGraphicMasksRetained:true,originalAreaEngineReused:true,originalShadersChanged:false,
   nvidiaHardwareVerified:false,visualQualityApproved:false};
 },evidence:{schema:'WORLD_ENGINE_QUALIFIED_PARTIAL_FRONT_PASS_V2',sourceCount:compiled.fronts.length,
  originalAreaEngineReused:true,originalProductionFrontStyleReused:true,originalShadersChanged:false,
  fullControlGeometryAvailable:false,legacyUNClassificationNotFabricated:true},
 dispose(){if(disposed)return;disposed=true;pass?.dispose();}};
}
function sourceSide(source){return typeof source.side==='string'?source.side:
 typeof source.classification==='string'?source.classification:'SOURCE_LABEL_ONLY';}
