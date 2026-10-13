/** Actual native projection selects safe schematic local cues, without changing source geography. */
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
import {openNightRuntime,root,engine,json,sha} from './night_runtime.mjs';
import {candidateDataVariants,buildNightFacts,compileNightScene} from './build_fixture.mjs';
import {compileCausalEnginePlan} from '../../web/map_infographic_v1/planner_causal_adapter_v1.mjs';

const variants=await candidateDataVariants(),groups=variants.groups;
assert.equal(groups.length,3);
const seedFacts=await buildNightFacts({routes:groups.map(group=>group.rawCandidates[0])});
const seedScene=await compileNightScene({facts:seedFacts}),seedPlan=compileCausalEnginePlan(seedScene);
let session;
try{
 session=await openNightRuntime({selectionOnly:true});
 const results=await session.page.evaluate(async({groups,entries})=>{
  const {compileFlowIntent,compileFlowPlan}=await import('/modules/flow_core_v2.mjs');
  const {preflightPlannerCausalFlowTrack}=await import('/modules/planner_causal_gpu_adapter_v1.mjs');
  const {native,frame,safeArea,plans}=window.nightSelection;
  return groups.map(group=>{
   const template=entries.find(entry=>entry.id===group.trackId);if(!template)throw Error('NIGHT_CANDIDATE_TRACK_TEMPLATE_REQUIRED');
   const accepted=[],rejections={};
   for(const candidate of group.rawCandidates){
    try{
     const geometry=candidate.routeGeometry,coordinates=geometry.coordinates;
     const intent=compileFlowIntent({...template.plan.intent,route_geometry:geometry,start_anchor:coordinates[0],end_anchor:coordinates.at(-1)});
     const plan=compileFlowPlan(intent,template.plan.timing);
     const result=preflightPlannerCausalFlowTrack({id:group.trackId,plan,project:native.project,safeArea,
      protectedGraphics:frame.protectedGraphics,boundarySegments:frame.boundarySegments,
      theme:plans.REGIONAL.theme,primaryMaterialColor:plans.REGIONAL.theme.primary,visualProfile:template.visualProfile});
     if(result.totalLengthPixels<80||result.totalLengthPixels>240){rejections.PERCEPTION_WINDOW=(rejections.PERCEPTION_WINDOW??0)+1;continue;}
     const score=Math.abs(result.totalLengthPixels-180)+Math.max(0,12-result.minimumClearancePixels)*2;
     accepted.push({candidate,score,projectedLengthPixels:result.totalLengthPixels,
      minimumBoundaryClearancePixels:result.minimumClearancePixels,supportPixels:result.supportPixels,
      nativeTextAndPanelCollisionCheck:result.nativeTextAndPanelCollisionCheck});
    }catch(error){rejections[error.message]=(rejections[error.message]??0)+1;}
   }
   accepted.sort((a,b)=>a.score-b.score);
   if(!accepted.length)throw Object.assign(Error('NIGHT_SAFE_LOCAL_CUE_UNAVAILABLE_'+group.trackId),{rejections});
   return{trackId:group.trackId,tested:group.rawCandidates.length,accepted:accepted.length,rejections,selected:accepted[0]};
  });
 },{groups,entries:seedPlan.flowTracks});
 assert.equal(session.errors.length,0);
 const selected=results.map(result=>result.selected.candidate),facts=await buildNightFacts({routes:selected});
 const scene=await compileNightScene({facts}),plan=compileCausalEnginePlan(scene);
 assert.equal(scene.timing.total_frames,420);assert.equal(plan.flowTracks.length,3);
 const old=await json(path.join(engine,'recovery/planner-scene-json-v1/fixtures/RUNTIME_FIXTURE.json'));
 const fixture={version:'NIGHT_CAUSAL_VISUAL_FIXTURE_V1',scenePlanPath:'recovery/planner-night-run-v1/fixtures/SCENE_PLAN.json',
  sourceGeometryBinding:plan.sourceGeometryBinding,nativeFiles:old.nativeFiles,
  presentation:{...old.presentation,cameraStartFrame:old.presentation.cameraStartFrame+old.presentation.eventStartFrame,
   eventStartFrame:0,totalFrames:420,annotations:plan.annotations,
   videoFilename:'KOREAN_WAR_PLANNER_SCENE_JSON_V1_CAUSAL_VISUAL_14S.mp4',checkpoints:[
    {frame:30,name:'01_IMMEDIATE_ACTION.png'},{frame:74,name:'02_FRONT_CONTACT.png'},
    {frame:115,name:'03_CONTROL_CHANGE.png'},{frame:158,name:'04_NORTH_ADVANCE.png'},
    {frame:245,name:'05_DEFENSIVE_WITHDRAWAL.png'},{frame:342,name:'06_SETTLEMENT.png'},
    {frame:419,name:'07_FINAL_HOLD.png'},{frame:158,name:'PREVIEW.png'}]}};
 const folder=path.join(root,'fixtures');await mkdir(folder,{recursive:true});await mkdir(path.join(root,'evidence'),{recursive:true});
 for(const [name,value] of Object.entries({'FACT_DATA.json':facts,'SCENE_PLAN.json':scene,'CAUSAL_PLAN.json':plan,'RUNTIME_FIXTURE.json':fixture})){
  const file=path.join(folder,name),body=JSON.stringify(value,null,2)+'\n';
  try{assert.equal(await readFile(file,'utf8'),body,'NIGHT_FIXTURE_ALREADY_SAVED_DIFFERENT_BYTES');}
  catch(error){if(error.code!=='ENOENT')throw error;await writeFile(file,body,{flag:'wx'});}
 }
 const report={schema:1,status:'PASS',scope:'ACTUAL_NATIVE_PROJECTION_LOCAL_CUE_SELECTION',
  native:session.info,profile:'COMMON_DIRECTIONAL_ACTOR',landScreening:'UNCHANGED_EXISTING_MAINLAND_GEOMETRY',
  routeSemantics:'SCHEMATIC_LOCAL_PHASE_DIRECTION_NOT_HISTORICAL_UNIT_ROUTE',representsHistoricalUnit:false,
  targetCoverage:'EXISTING_WHOLE_PENINSULA_CURRENT_VIEW',results,sceneSha256:sha(await readFile(path.join(folder,'SCENE_PLAN.json'))),
  geometryOriginal:'FIVE_EXISTING_STATE_GEOMETRIES_UNCHANGED',finalSettlementContact:'NONE',requiredTempOnlyFiles:0};
 await writeFile(path.join(root,'evidence/ROUTE_SELECTION.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({status:'PASS',routes:results.map(result=>({id:result.trackId,
  length:result.selected.projectedLengthPixels,clearance:result.selected.minimumBoundaryClearancePixels})),sceneSha256:report.sceneSha256}));
}finally{await session?.close();}
