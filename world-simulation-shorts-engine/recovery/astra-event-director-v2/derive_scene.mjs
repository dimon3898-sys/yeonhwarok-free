/** Generic derived-scene compiler. Existing historical geometry is never rewritten. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {normalizeFrontProfile} from '../verified-front-data-v4-recovery/front_visual.mjs';
import {evaluateProductionGeometryClock} from '../universal-production-v3/production_visual_profile.mjs';
const clone=v=>structuredClone(v),sha=v=>createHash('sha256').update(v).digest('hex');
export const sceneBytes=v=>Buffer.from(JSON.stringify(v,null,2)+'\n');
const hash=v=>sha(Buffer.from(JSON.stringify(v)));
const rgb=value=>{assert.match(value,/^#[a-fA-F0-9]{6}$/);return[1,3,5].map(i=>parseInt(value.slice(i,i+2),16)/255);};

export function compileDerivedScene({sourceBytes,profileBytes,catalogBytes,frontProfileBytes}){
 const sourceSHA=sha(sourceBytes),profile=JSON.parse(profileBytes),catalog=JSON.parse(catalogBytes),
  original=JSON.parse(sourceBytes),originalFront=JSON.parse(frontProfileBytes),derived=clone(original);
 assert.equal(profile.schema,'WORLD_ENGINE_QUALIFIED_EVENT_PROFILE_V2');
 assert.equal(sourceSHA,profile.sourcePlanSHA256,'SOURCE_HASH_MISMATCH');
 assert.equal(catalog.sourcePlanSHA256,sourceSHA);
 assert.equal(sha(frontProfileBytes),catalog.originalFrontProfileSHA256);
 assert.equal(profile.totalFrames,original.totalFrames);assert.equal(profile.fps,original.fps);
 const beforeLegacy=hash(original.legacyScenePlan),payloads=original.scenes.map(x=>hash(x.renderProfile.nativePayload));
 assert.deepEqual(profile.chapters.map(x=>[x.chapterId,x.eventId,x.startFrame,x.endFrame]),
  original.productionV3.eventChapters.map(x=>[x.chapterId,x.eventId,x.startFrame,x.endFrame]));
 derived.productionV3.eventChapters=original.productionV3.eventChapters.map(parent=>{
  const item=profile.chapters.find(x=>x.chapterId===parent.chapterId),rows=profile.sourceSchedule.filter(x=>x.chapterId===parent.chapterId);
  return{...clone(parent),title:item.title,displayLabel:item.displayLabel,
   semanticTopic:item.semanticTopic,sourceIds:clone(item.sourceIds),
   geometryStateIds:rows.filter(x=>x.stateId).map(x=>x.stateId),
   geometryStatus:item.fullControlStatus,controlStartState:item.controlStartState,controlEndState:item.controlEndState,
   cameraIntent:{...clone(parent.cameraIntent),sourceGeometryRefs:[],contextLocationRefs:clone(item.locationRefs),
    visibleContextPolicy:'CURRENT_SOURCE_AND_EXPLICIT_GEOGRAPHIC_CONTEXT_ONLY',
    locationRole:'GEOGRAPHIC_CONTEXT_ONLY_NOT_HISTORICAL_TROOP_POSITION'},
   eventTimeWindow:{...clone(parent.eventTimeWindow),displayLabel:item.displayLabel,
    correctionSource:'MASTER_OFFICIAL_CHRONOLOGY_REVIEW',originalWindowPreservedInSourcePlan:true},
   historicalUnitPositionsVerified:false,newUnitPositions:[]};
 });
 const areaSchedule=profile.sourceSchedule.map((row,index)=>{
  assert.ok(['UNKNOWN','SCHEMATIC_HELD_CORE','OBSERVED_PARTIAL_FRONT'].includes(row.kind),
   'UNSUPPORTED_SOURCE_STATE_KIND');
  if(row.kind==='UNKNOWN')assert.equal(row.stateId,null,'UNKNOWN_CANNOT_REUSE_PREVIOUS_STATE');
  const supplied=row.kind==='SCHEMATIC_HELD_CORE';
  return{scheduleId:'qualified-source-'+String(index).padStart(3,'0'),chapterId:row.chapterId,
   startFrame:row.startFrame,endFrame:row.endFrame,
   mode:supplied?'HOLD_SUPPLIED_SNAPSHOT':'ARRIVAL_NO_EVENT',
   sourceStartFrame:supplied?row.sourceFrame:null,sourceEndFrame:supplied?row.sourceFrame:null,
   sourceStateId:supplied?row.stateId:null,fromStateId:supplied?row.stateId:null,toStateId:supplied?row.stateId:null,
   snapshotDate:row.sourceDate,snapshotLabel:supplied?'전선: '+row.visibleQualifier:row.visibleQualifier,
   eventDateMatchesSnapshot:false,geometryStatus:row.kind,
   sourceClock:'EXPLICIT_QUALIFIED_SOURCE_V2_NO_PREVIOUS_STATE_FALLBACK',
   truthKind:row.truthKind,fullControlAvailable:false,measuredMilitaryControl:false,newGeometryCreated:false};
 });
 derived.productionV3.geometrySchedule=areaSchedule;
 const ownerId=profile.presentation?.heldCoreColorFactionId;
 assert.equal(typeof ownerId,'string','EXPLICIT_HELD_CORE_COLOR_FACTION_REQUIRED');
 assert.ok(Object.hasOwn(profile.factions,ownerId),'HELD_CORE_COLOR_FACTION_UNKNOWN');
 const color=rgb(profile.factions[ownerId].color);
 derived.productionV3.visualBindings.areaStyles=derived.productionV3.visualBindings.areaStyles.map(x=>({...x,color:[...color]}));
 derived.productionV3.directorRevision={schema:'WORLD_ENGINE_QUALIFIED_DERIVED_SCENE_V2',sourcePlanSHA256:sourceSHA,
  eventProfileSHA256:sha(profileBytes),sourceCatalogSHA256:sha(catalogBytes),
  explicitSourceMappingChanged:true,originalLegacyGeometryUnchanged:true,
  unknownControlNeverFilled:true,sourceDateRegressionFixed:true,fullHistoricalControlReady:false};
 const front={...clone(originalFront),schedule:profile.sourceSchedule.filter(x=>x.kind==='OBSERVED_PARTIAL_FRONT').map(row=>{
  const originalRow=originalFront.schedule.find(x=>x.frontId===row.stateId);
  assert.ok(originalRow,'ORIGINAL_SOURCE_FRONT_REQUIRED');
  return{...clone(originalRow),chapterId:row.chapterId,startFrame:row.startFrame,endFrame:row.endFrame,
   eventDate:row.sourceDate,sourceLabel:originalRow.sourceLabel,
   datePolicy:'AS_OF_SOURCE_DATE_DISTINCT_FROM_NARRATIVE_EVENT_DATE'};
 })};
 const normalized=normalizeFrontProfile(front,{totalFrames:derived.totalFrames,eventChapters:derived.productionV3.eventChapters});
 let previousDate='';
 for(let frame=0;frame<derived.totalFrames;frame++){
  const row=profile.sourceSchedule.find(x=>frame>=x.startFrame&&frame<x.endFrame);
  assert.ok(row,'SOURCE_TIMELINE_GAP');
  const clock=evaluateProductionGeometryClock(derived,frame);
  assert.equal(clock.eventEnabled,row.kind==='SCHEMATIC_HELD_CORE');
  if(row.sourceDate){assert.ok(row.sourceDate>=previousDate,'SOURCE_DATE_REGRESSION');previousDate=row.sourceDate;}
  if(row.kind==='UNKNOWN')assert.equal(clock.sourceGeometryFrame,null,'UNKNOWN_STATE_MUST_NOT_REUSE_PREVIOUS_GEOMETRY');
 }
 assert.equal(hash(derived.legacyScenePlan),beforeLegacy,'ORIGINAL_LEGACY_SCENE_MUTATED');
 assert.deepEqual(derived.scenes.map(x=>hash(x.renderProfile.nativePayload)),payloads,'ORIGINAL_NATIVE_PAYLOAD_MUTATED');
 assert.deepEqual(normalized.fronts,originalFront.fronts,'ORIGINAL_ARCHIVAL_FRONT_GEOMETRY_MUTATED');
 const bytes=sceneBytes(derived),derivedFrontBytes=sceneBytes(front),receipt={
  schema:'WORLD_ENGINE_ASTRA_DERIVATION_RECEIPT_V2',status:'PASS_DERIVED_MAPPING_ONLY',
  sourcePlanSHA256:sourceSHA,derivedSceneSHA256:sha(bytes),eventProfileSHA256:sha(profileBytes),
  sourceCatalogSHA256:sha(catalogBytes),derivedFrontProfileSHA256:sha(derivedFrontBytes),
  compilerSHA256:null,legacySceneSHA256:beforeLegacy,originalLegacySceneUnchanged:true,
  originalNativePayloadsUnchanged:true,originalArchivalGeometriesUnchanged:true,
  totalFrames:derived.totalFrames,fps:derived.fps,chapterCount:profile.chapters.length,
  mappingFramesVerified:derived.totalFrames,fullControlGeometryAvailable:false,
  originalSourcePlanOverwritten:false,productionEligible:false,visualQualityApproved:false};
 return{document:derived,frontProfile:front,bytes,frontBytes:derivedFrontBytes,receipt};
}
