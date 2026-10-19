/** Read-only geographic/state oracle over actual private renderer diagnostics.
 * Existing Area/clock/front compilers are the authority. No rendering, new
 * history, geometry interpolation or change to the source Scene occurs here.
 * Public evidence contains hashes, alpha/coverage/state IDs and counts only.
 */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),ENGINE=path.resolve(ROOT,'../..');
const argument=process.argv.slice(2).find(x=>x.startsWith('--prepared='));
assert.ok(argument,'SOURCE_ORACLE_PREPARED_RECEIPT_REQUIRED');
const json=async file=>JSON.parse(await readFile(file,'utf8')),
 sha=bytes=>createHash('sha256').update(bytes).digest('hex'),
 canonical=value=>JSON.stringify(value,(_key,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v),
 hash=value=>sha(canonical(value)),clone=structuredClone;
const prepared=await json(argument.slice('--prepared='.length)),planBytes=await readFile(prepared.options.planFile),plan=JSON.parse(planBytes),
 reportFile=path.join(ROOT,'proof/FRAME_RENDER_REPORT.json'),reportBytes=await readFile(reportFile),report=JSON.parse(reportBytes),
 fullFile=path.join(ROOT,'.private/FULL_FRAME_DIAGNOSTICS.json'),fullBytes=await readFile(fullFile),full=JSON.parse(fullBytes);
assert.equal(report.status,'FRAME_RENDER_PASS');assert.equal(sha(planBytes),report.sourcePlanSHA256);
assert.equal(sha(planBytes),prepared.options.expectedPlanSha256);assert.equal(full.length,25);
const sourceBefore=hash(plan),hook=registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('/modules/'))return{url:new URL('file://'+path.join(ENGINE,'web/map_infographic_v1',specifier.slice(9))).href,shortCircuit:true};
 return next(specifier,context);}});
let long,area,visual,frontVisual,normalize;
try{
 long=await import('../../universal-auto-video-v2/long_area_timeline.mjs');
 area=await import('../../../web/map_infographic_v1/area_core_v3.mjs');
 visual=await import('../../universal-production-v3/production_visual_profile.mjs');
 frontVisual=await import('../../verified-front-data-v4-recovery/front_visual.mjs');
 ({normalizePlannerGeometryKeys:normalize}=await import('../../universal-auto-video-v2/planner_geometry_serialization.mjs'));
}finally{hook.deregister();}
const raw=normalize(plan.legacyScenePlan),request=long.compileLongAreaRequest(raw),frontBytes=await readFile(path.join(ENGINE,'recovery/verified-front-data-v4-recovery/FRONT_PROFILE.json')),
 frontProfile=frontVisual.normalizeFrontProfile(JSON.parse(frontBytes),{totalFrames:plan.totalFrames,eventChapters:plan.productionV3.eventChapters}),archival=new Map();
const project=p=>p;
function fields(record,keys){return Object.fromEntries(keys.filter(k=>record[k]!==undefined).map(k=>[k,clone(record[k])]));}
function stateWitness(controls){
 if(controls===null)return null;
 return {stateId:controls.stateId,stateProgress:controls.stateProgress,hold:controls.hold,activeFeatures:controls.activeFeatures,
  areas:controls.areas.map(row=>fields(row,['id','geometry','sourceGeometry','source','role','style_role','state_id','alpha','coverage','coverageMode','coverageOrigin','transform','motion'])),
  fronts:controls.fronts.map(row=>fields(row,['id','geometry','source','direction','style_role','role','state_id','alpha','revealFraction']))};
}
for(const front of frontProfile.fronts){
 const source={source_type:'OFFICIAL_ARCHIVAL_MAP_APPROXIMATE_DIGITIZATION',source_reference:front.source.reference,verification_status:'VERIFIED'},
 fronts=frontVisual.sourceLineChunks(front.geometry).map((chunk,index)=>({id:front.frontId+'-part-'+index,geometry:chunk.geometry,source,role:'FRONT_LINE',style_role:'PRIMARY'})),
 intent=area.compileAreaIntent({data_mode:'PRODUCTION',semantic_mode:'SUPPLIED_OBSERVED_STATES',origin:request.origin,source,fronts});
 archival.set(front.frontId,area.compileAreaPlan(intent,{fps:plan.fps,total_frames:1,operations:[{type:'AREA_HOLD',start_frame:0,duration_frames:1}]}));
}
const rows=[];
for(const capture of full){
 const frame=capture.globalFrame,d=capture.diagnostic,clock=visual.evaluateProductionGeometryClock(plan,frame),selection=frontVisual.selectFrontSnapshot(frontProfile,frame);
 assert.equal(d.frame,frame);assert.deepEqual(d.productionV3.geometryClock,clock,'SOURCE_ORACLE_CLOCK_MISMATCH_'+frame);
 assert.deepEqual(d.frontV4.selection,selection,'SOURCE_ORACLE_SELECTION_MISMATCH_'+frame);
 let expected=null,role='NO_EVENT_GEOMETRY';
 if(selection.sourceActiveFrame){
  role='ARCHIVAL_PARTIAL_FRONT';const front=frontProfile.fronts.find(row=>row.frontId===selection.frontId);
  expected=area.evaluateAreaFrame(archival.get(selection.frontId),0,{project});
  expected={...expected,stateId:selection.frontId};
  assert.equal(d.frontV4.sourceGeometrySha256,sha(JSON.stringify(front.geometry)),'SOURCE_ORACLE_ARCHIVAL_GEOMETRY_SHA_'+frame);
 }else if(clock.eventEnabled){
  role='SCHEMATIC_SUPPLIED_SOURCE_CLOCK';expected=long.evaluateLongAreaFrame(request.timelinePlan,clock.sourceGeometryFrame,{project});
 }
 const actualWitness=stateWitness(d.area.controls),expectedWitness=stateWitness(expected),actualSHA=hash(actualWitness),expectedSHA=hash(expectedWitness);
 assert.deepEqual(actualWitness,expectedWitness,'SOURCE_ORACLE_GEOMETRY_STATE_ALPHA_MISMATCH_'+frame);
 rows.push({globalFrame:frame,role,exactExistingGeometryClockMatch:true,exactExistingFrontSelectionMatch:true,
  sourceGeometryFrame:clock.sourceGeometryFrame,sourceClockMode:clock.mode,
  fromStateId:clock.fromStateId,toStateId:clock.toStateId,targetMetadataStateId:clock.sourceStateId,
  actualChosenStateId:actualWitness?.stateId??null,stateProgress:actualWitness?.stateProgress??null,
  actualAreaStates:actualWitness?.areas.map(x=>({id:x.id,stateId:x.state_id,alpha:x.alpha,coverage:x.coverage}))??[],
  actualFrontStates:actualWitness?.fronts.map(x=>({id:x.id,stateId:x.state_id,alpha:x.alpha,revealFraction:x.revealFraction}))??[],
  actualGeographicStateWitnessSHA256:actualSHA,expectedGeographicStateWitnessSHA256:expectedSHA,
  exactSuppliedGeographicGeometryAlphaAndStateMatch:actualSHA===expectedSHA,
  targetStateMetadataIsNotCurrentCrossfadeState:role==='SCHEMATIC_SUPPLIED_SOURCE_CLOCK'&&clock.mode==='TRANSITION_SUPPLIED_SNAPSHOTS'&&clock.sourceStateId!==actualWitness?.stateId,
  noHistoricalInterpolationInvented:true,actualNvidiaVerified:false});
}
assert.equal(hash(plan),sourceBefore);assert.equal(sha(await readFile(prepared.options.planFile)),sha(planBytes));
const output={schema:'WORLD_ENGINE_STORY_DIRECTOR_EXISTING_SOURCE_CONSUMER_ORACLE_V1',status:'PASS',
 scope:'EXACT_EXISTING_CPU_GEOGRAPHIC_STATE_VS_ACTUAL_SOFTWARE_RENDER_DIAGNOSTIC',
 frameRenderReportSHA256:sha(reportBytes),fullDiagnosticSHA256:sha(fullBytes),sourcePlanSHA256:sha(planBytes),frontProfileSHA256:sha(frontBytes),
 actualFrameCount:rows.length,allActualSourceConsumersMatchExistingEvaluators:true,
 expectedFunctions:['evaluateProductionGeometryClock','selectFrontSnapshot','evaluateLongAreaFrame','compileAreaIntent','compileAreaPlan','evaluateAreaFrame'],
 originalSceneChanged:false,newCoordinates:false,actualNvidiaVerified:false,visualQualityApproved:false,
 caution:'A transition target metadata state may differ from the actual chosen from-state at its first source frame. This is checked against the original existing evaluator, not relabelled as an actual daily front.',rows};
await writeFile(path.join(ROOT,'proof/SOURCE_CONSUMER_ORACLE.json'),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({status:output.status,frames:rows.length,firstTransitionTargetMetadataDifference:rows.filter(row=>row.targetStateMetadataIsNotCurrentCrossfadeState).map(row=>row.globalFrame),noCoordinatesPublished:true}));
