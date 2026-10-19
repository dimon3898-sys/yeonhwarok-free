#!/usr/bin/env node
/** CPU source/camera trace only. No browser, Canvas, WebGL, encoder or GPU command is used. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {suppliedFrontObservations} from '../source_observations.mjs';
import {compileSuppliedFrontMotion,evaluateSuppliedFrontMotion} from '../frontier_extension.mjs';
import {integrationFrameSelections} from '../../universal-integration-v1/runtime_binding.mjs';

const root=fileURLToPath(new URL('../',import.meta.url)),engine=fileURLToPath(new URL('../../../',import.meta.url)),
 repo=path.dirname(engine),web=new URL('../../../web/map_infographic_v1/',import.meta.url),
 production=new URL('../../universal-production-v3/',import.meta.url),
 sha=raw=>createHash('sha256').update(raw).digest('hex'),hash=value=>sha(Buffer.from(JSON.stringify(value))),
 json=async file=>JSON.parse(await readFile(file)),relative=file=>path.relative(repo,file).replaceAll(path.sep,'/'),
 count=(table,key)=>{table[key]=(table[key]??0)+1;},bool=value=>value?'true':'false',
 csvCell=value=>{const text=String(value??'');return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};

export async function buildFrameTrace(){
 const hook=registerHooks({resolve(specifier,context,next){
  if(specifier.startsWith('/modules/'))return{url:new URL(specifier.slice(9),web).href,shortCircuit:true};
  if(specifier.startsWith('/production-v3/'))return{url:new URL(specifier.slice(15),production).href,shortCircuit:true};
  return next(specifier,context);
 }});let camera,v5,productionCamera;
 try{camera=await import('../camera_extension.mjs');v5=await import(new URL('camera_director_v5.mjs',web));
  productionCamera=await import(new URL('production_camera.mjs',production));}finally{hook.deregister();}
 const inputFile=path.join(root,'fixtures/VALIDATED_80S_SUBMISSION.json'),inputRaw=await readFile(inputFile),
  submission=JSON.parse(inputRaw),plan=submission.videoPlan,planBefore=JSON.stringify(plan),
  frontFile=path.join(root,'../verified-front-data-v4-recovery/FRONT_PROFILE.json'),
  frontRaw=await readFile(frontFile),frontProfile=JSON.parse(frontRaw),payloadFile=path.join(root,'../universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json'),
  payloadRaw=await readFile(payloadFile),payload=JSON.parse(payloadRaw),nativeInputs={},sourceFiles=[];
 const bindFile=async file=>{const raw=await readFile(file),record={path:relative(file),sha256:sha(raw),bytes:raw.length};sourceFiles.push(record);return record;};
 await bindFile(inputFile);await bindFile(frontFile);await bindFile(payloadFile);
 for(const [name,reference]of Object.entries(payload.nativeFiles)){
  const file=path.join(engine,reference.path),record=await bindFile(file);assert.equal(record.sha256,reference.sha256,'TRACE_NATIVE_SOURCE_SHA_MISMATCH');
  nativeInputs[name]=await json(file);
 }
 assert.equal(plan.totalFrames,2400);assert.equal(plan.fps,30);assert.equal(plan.durationSeconds,80);
 assert.equal(plan.productionV3.eventChapters.length,12);
 for(const file of ['camera_extension.mjs','production_camera_bridge.mjs','source_observations.mjs','frontier_extension.mjs',
  'tools/build_frame_trace.mjs'])await bindFile(path.join(root,file));
 for(const file of ['camera_director_v5.mjs','camera_director_v4.mjs','camera_detail_approach_adapter_v1.mjs','area_core_v3.mjs'])
  await bindFile(fileURLToPath(new URL(file,web)));
 for(const file of ['production_camera.mjs','production_visual_profile.mjs'])await bindFile(fileURLToPath(new URL(file,production)));
 const sourceRows=[...integrationFrameSelections({plan,frontProfile})],observations=suppliedFrontObservations(plan,frontProfile),
  motion=compileSuppliedFrontMotion({observations,totalFrames:2400,profile:submission.completionV2.frontier}),
  r=nativeInputs.regionalPlan,c=nativeInputs.continentPlan,nativePlan=nativeInputs.cameraPlan,
  eventStart=plan.legacyScenePlan.timing.event_start_frame,chapters=plan.productionV3.eventChapters,
  allGeometry=chapters.flatMap(chapter=>camera.completionChapterGeometries(plan,chapter));
 let nativeLayoutSpyCalls=0,nativeDrawSpyCalls=0;
 const native={cameraPlan:nativePlan,layoutContract:{CPU_NATIVE_LAYOUT_SPY_ONLY:true},project:p=>p,
  evidence:{frozenMaterialParameters:{}},
  drawNative:frame=>({...v5.evaluateMinimumContextCameraFrame(nativePlan,Math.min(frame,nativePlan.totalFrames-1)),
   reveal:{country:1,marker:1,location:1,title:1}}),
  factory:{evidence:{cameraFrame:{}},updateCamera(bounds){this.evidence.cameraFrame={flatBounds:[...bounds]};},
   setScaleVisual(){},setTerrainLod(){},renderFrame(){nativeDrawSpyCalls++;return{glError:0};}}},
  operations={geographicScaleVisualTokens:()=>({markerSize:40}),geographicTerrainLod:()=>({weight:1}),
   evaluateMovingLayout:()=>{nativeLayoutSpyCalls++;return{items:[]};},validateVisibleMovingLayout:()=>({valid:true}),
   nativeGraphicReservations:()=>[],nativeBoundarySupport:()=>[]},
  owner=camera.createCompletionNativeCamera({native,plans:{REGIONAL:r,CONTINENT:c},plan,
   request:{origin:plan.legacyScenePlan.camera_intent.anchor,timing:{eventStartFrame:eventStart}},
   profile:submission.integration.visualProfile,cameraStartFrame:payload.cameraStartFrame},
   {camera:submission.completionV2.camera,operations,originalFactory:()=>{throw Error('TRACE_OLD_CAMERA_PATH_FORBIDDEN');}}),
  fields=['frame','timeSeconds','chapterId','eventId','eventDate','sourceMode','sourceClockMode','sourceGeometryFrame',
   'sourceStateId','archivalFrontId','areaPolicy','frontCount','frontGeometrySHA256','frontCoordinateSetChangedFromPrevious',
   'sameIdentityComparableCoordinateChanged','sameIdentityTopologyChanged','frontierStrengthMin','frontierStrengthMax',
   'cameraKind','cameraState','cameraLocked','cameraWest','cameraSouth','cameraEast','cameraNorth','cameraV5TurnSelected',
   'allSuppliedSourceSafe','parentMinimumExtentPass','nativeLayoutEvidence','nativeDrawEvidence','renderedFrame','gpuOutputVerified'],
  csv=[fields.join(',')],sourceCounts={},cameraCounts={},clockCounts={},perChapter=new Map(chapters.map(chapter=>[chapter.chapterId,{
   chapterId:chapter.chapterId,eventId:chapter.eventId,title:chapter.title,date:chapter.displayLabel,
   startFrame:chapter.startFrame,endFrame:chapter.endFrame,frames:0,sourceModes:{},areaPolicies:{},sourceClockModes:{},
   cameraKinds:{},cameraStates:{},frontPresentFrames:0,frontCoordinateSetChangeFrames:0,sameIdentityComparableChangeFrames:0,
   sameIdentityTopologyChangeFrames:0,sourceSafeFrames:0,minimumExtentPassFrames:0,nativeLayoutProof:'CPU_SPY_NOT_ACTUAL_FONT_LAYOUT',
   sourceChronologyStatus:chapter.eventTimeWindow.status,exactEventDateFrontClaimed:false,
   sfxCues:submission.sfx.cues.filter(cue=>cue.frame>=chapter.startFrame&&cue.frame<chapter.endFrame).map(cue=>({...cue})),
   newHistoricalUnits:0,newHistoricalRoutes:0,actualRendererOutputVerified:false}]));
 let previousBounds=null,previousFrontHash=null,previousFrontPresent=false,coordinateSetChangeFrames=0,
  comparableChangeFrames=0,topologyChangeFrames=0,frontPresentFrames=0,frontAbsenceAppearanceTransitions=0;
 const boundaryChecks=[];
 for(let frame=0;frame<2400;frame++){
  const source=sourceRows[frame],chapter=chapters.find(row=>frame>=row.startFrame&&frame<row.endFrame),summary=perChapter.get(chapter.chapterId),
   actual=owner.drawNative(frame),bounds=actual.camera.flatBounds,completion=actual.productionCamera.completionV2,
   kind=completion.kind,state=actual.productionCamera.completionV2.state??actual.state,
   selected=source.selection,observed=observations[frame],frontPresent=observed.fronts.length>0,
   frontHash=hash(observed.fronts.map(front=>front.geometry)),frontMotion=observed.fronts.map(front=>evaluateSuppliedFrontMotion(motion,frame,front)),
   comparable=frontMotion.some(item=>item.geographicGeometryChangedThisFrame),
   topology=observed.fronts.some(front=>motion.fronts[front.id].incomparableFrames.includes(frame)),
   coordinateChange=frontPresent&&previousFrontPresent&&frontHash!==previousFrontHash,
   minimumPass=bounds[2]-bounds[0]>=r.framing.bounds[2]-r.framing.bounds[0]-1e-8
    &&bounds[3]-bounds[1]>=r.framing.bounds[3]-r.framing.bounds[1]-1e-8,
   sourceSafe=frame<eventStart?null:productionCamera.geometryScreenSafety({geometries:allGeometry,bounds,safeArea:r.layout.safe}).wholeSuppliedGeometrySafe,
   sourceMode=selected.sourceActiveFrame?'ARCHIVAL_FRONT_ONLY':source.geometryClock.eventEnabled?'QUALIFIED_SCHEMATIC':'NO_EVENT';
  assert.ok(bounds.every(Number.isFinite)&&minimumPass);if(frame>=eventStart)assert.equal(sourceSafe,true,'TRACE_SOURCE_OUTSIDE_SAFE_AREA');
  if(frame===chapter.startFrame&&frame>0){const noJump=previousBounds.every((value,index)=>Math.abs(value-bounds[index])<1e-8);
   assert.equal(noJump,true,'TRACE_CAMERA_CHAPTER_DISCONTINUITY');boundaryChecks.push({frame,chapterId:chapter.chapterId,poseContinuous:true});}
  count(sourceCounts,source.areaPolicy);count(cameraCounts,kind);count(clockCounts,source.geometryClock.mode);
  summary.frames++;count(summary.sourceModes,sourceMode);count(summary.areaPolicies,source.areaPolicy);
  count(summary.sourceClockModes,source.geometryClock.mode);count(summary.cameraKinds,kind);count(summary.cameraStates,state);
  summary.frontPresentFrames+=Number(frontPresent);summary.frontCoordinateSetChangeFrames+=Number(coordinateChange);
  summary.sameIdentityComparableChangeFrames+=Number(comparable);summary.sameIdentityTopologyChangeFrames+=Number(topology);
  summary.sourceSafeFrames+=Number(sourceSafe===true);summary.minimumExtentPassFrames+=Number(minimumPass);
  coordinateSetChangeFrames+=Number(coordinateChange);comparableChangeFrames+=Number(comparable);topologyChangeFrames+=Number(topology);
  frontPresentFrames+=Number(frontPresent);if(frame&&frontPresent!==previousFrontPresent)frontAbsenceAppearanceTransitions++;
  const strengths=frontMotion.map(item=>item.strength),row={frame,timeSeconds:(frame/30).toFixed(6),chapterId:chapter.chapterId,eventId:chapter.eventId,
   eventDate:chapter.displayLabel,sourceMode,sourceClockMode:source.geometryClock.mode,sourceGeometryFrame:source.geometryClock.sourceGeometryFrame,
   sourceStateId:source.geometryClock.sourceStateId,archivalFrontId:selected.frontId,areaPolicy:source.areaPolicy,
   frontCount:observed.fronts.length,frontGeometrySHA256:frontHash,frontCoordinateSetChangedFromPrevious:bool(coordinateChange),
   sameIdentityComparableCoordinateChanged:bool(comparable),sameIdentityTopologyChanged:bool(topology),
   frontierStrengthMin:strengths.length?Math.min(...strengths):'',frontierStrengthMax:strengths.length?Math.max(...strengths):'',
   cameraKind:kind,cameraState:state,cameraLocked:bool(actual.cameraLocked),cameraWest:bounds[0],cameraSouth:bounds[1],cameraEast:bounds[2],cameraNorth:bounds[3],
   cameraV5TurnSelected:bool(completion.actualV5Turn===true),allSuppliedSourceSafe:sourceSafe===null?'NOT_REQUIRED_INITIAL_NO_EVENT':bool(sourceSafe),
   parentMinimumExtentPass:bool(minimumPass),nativeLayoutEvidence:'CPU_SPY_NOT_ACTUAL_FONT_LAYOUT',nativeDrawEvidence:'CPU_API_SPY_NO_WEBGL',
   renderedFrame:false,gpuOutputVerified:false};
  csv.push(fields.map(key=>csvCell(row[key])).join(','));previousBounds=bounds;previousFrontHash=frontHash;previousFrontPresent=frontPresent;
 }
 assert.equal(sourceRows.length,2400);assert.equal([...perChapter.values()].reduce((sum,row)=>sum+row.frames,0),2400);
 assert.equal(JSON.stringify(plan),planBefore,'TRACE_SOURCE_PLAN_MUTATED');
 for(const record of sourceFiles)assert.equal(sha(await readFile(path.join(repo,record.path))),record.sha256,'TRACE_SOURCE_CHANGED_DURING_CPU_RUN');
 for(const summary of perChapter.values()){
  const entry=owner.completionFocusPlan.entries.find(row=>row.chapterId===summary.chapterId);
  summary.cameraPlan=entry.kind==='V5_EVENT_TRACKING'?{kind:entry.kind,activeFrames:entry.activeFrames,settleFrames:entry.settleFrames,
   minimumHoldFrames:entry.minimumHoldFrames,actualHoldFrames:entry.actualHoldFrames,actualV5ContextTurn:entry.actualV5Turn,
   explicitContextGeometryCount:entry.explicitContextGeometryCount}:{kind:entry.kind};
  summary.features={camera:{featureIds:['CAMERA.CONSERVATIVE_CHAPTER_FOCUS','CAMERA.GUIDED_LAYOUT_SCALE','CAMERA.MINIMUM_CONTEXT','CAMERA.NATURAL_TURNAROUND'],
   actualMath:'PRESERVED_V5',nativeConsumers:'CPU_SPIES',actualOutputVerified:false},
   suppliedArea:{featureId:'TERRITORY.SUPPLIED_AREA_COLOR',selectedFrames:summary.areaPolicies.PRESERVED_QUALIFIED_SCHEMATIC_AREAS??0,
    exactBilateralOccupationClaimed:false},
   partialArchivalFront:{featureId:'TERRITORY.ARCHIVAL_FRONT_ONLY',selectedFrames:summary.areaPolicies.NO_INFERRED_OCCUPATION_FILL??0,
    inferredFill:false,exactDailyMovementClaimed:false},
   frontStyle:{featureId:'FRONTIER.PRODUCTION_FRONT_STYLE',sourcePresentFrames:summary.frontPresentFrames,
    sourceComparableMotionFrames:summary.sameIdentityComparableChangeFrames,shaderExecuted:false},
   astra:{state:'PRESERVED_SOURCE_BOUND_OWNER',actualUploadOrMaterialDrawExecuted:false},
   newEventFlowArea:{events:0,flows:0,areas:0,reason:'CURRENT_TRUSTED_PRODUCTION_EXTENSION_LISTS_ARE_EMPTY'},
   nationalMilitaryMarkers:{state:'BLOCKED',reason:'NO_VERIFIED_HISTORICAL_ACTOR_POSITIONS_OR_ROUTES'},
   sfx:{featureId:'STUDIO.SFX_AUTHORED_CUES',eventBoundCueCount:summary.sfxCues.length,audioRendered:false}};
 }
 const csvRaw=csv.join('\n')+'\n',outputFile=path.join(root,'reports/FRAME_SELECTION_TRACE_2400.csv');
 await writeFile(outputFile,csvRaw);
 const result={schema:'WORLD_ENGINE_COMPLETION_CHAPTER_FEATURE_COVERAGE_V2',status:'CPU_SOURCE_CAMERA_TRACE_COMPLETE',
  evidenceScope:'ACTUAL_PRESERVED_SOURCE_SELECTION_AND_V5_MATH_WITH_EXPLICIT_NATIVE_LAYOUT_DRAW_SPIES',
  durationSeconds:80,fps:30,totalFrames:2400,chapterCount:12,sourceCounts,cameraCounts,sourceClockCounts:clockCounts,
  sourceFiles,sourceSubmissionSHA256:sha(inputRaw),videoPlanCanonicalSHA256:hash(plan),frontProfileSHA256:sha(frontRaw),
  csv:{file:'FRAME_SELECTION_TRACE_2400.csv',sha256:sha(csvRaw),rows:2400},
  frontGeometry:{frontPresentFrames,coordinateSetChangeFrames,sameIdentityComparableChangeFrames:comparableChangeFrames,
   sameIdentityTopologyChangeFrames:topologyChangeFrames,frontAbsenceAppearanceTransitions,
   motionInterpretation:'Only same-identity comparable coordinate changes drive the supplied-front motion response. Snapshot/ID switches, camera movement and line appearance are not measured frontier travel.',
   recordedComparableFrontEvents:Object.values(motion.fronts).reduce((sum,row)=>sum+row.changeFrames.length,0),
   recordedTopologyChangeEvents:Object.values(motion.fronts).reduce((sum,row)=>sum+row.incomparableFrames.length,0)},
  nativeLayoutSpyCalls,nativeDrawSpyCalls,boundaryChecks,chapters:[...perChapter.values()],
  guards:{sourceGeometryChanged:false,opponentComplementInvented:false,historicalUnitPositionsInvented:false,
   actualNativeFontLayoutVerified:false,gpuExecuted:false,swiftShaderExecuted:false,renderedFrames:0,videoCreated:false,
   visualQualityApproved:false,full80sRenderAuthorized:false,appliedOutputFeatures:0}};
 await writeFile(path.join(root,'reports/CHAPTER_FEATURE_COVERAGE.json'),JSON.stringify(result,null,2)+'\n');
 const md=['# 2,400-frame source/camera CPU trace','',
  '**No video frames were rendered. Native layout and draw calls are explicitly labeled CPU spies.**','',
  `Source selection: ${JSON.stringify(sourceCounts)}.`,
  `Front present: ${frontPresentFrames} frames; coordinate-set switches: ${coordinateSetChangeFrames}; same-identity comparable motion frames: ${comparableChangeFrames}; topology-change frames: ${topologyChangeFrames}.`,
  'Snapshot switches, camera pans and line reveal are not continuous observed historical frontier movement. The full supplied source still consists of qualified schematic states and held partial archival fronts.','',
  '| Chapter | Frames | Qualified schematic | Partial archival / no inferred fill | V5 active / hold | Context turn |',
  '|---|---:|---:|---:|---|---|',
  ...result.chapters.map(row=>`| ${row.chapterId} | ${row.frames} | ${row.areaPolicies.PRESERVED_QUALIFIED_SCHEMATIC_AREAS??0} | ${row.areaPolicies.NO_INFERRED_OCCUPATION_FILL??0} | ${row.cameraPlan.activeFrames??'Preserve'} / ${row.cameraPlan.actualHoldFrames??'—'} | ${row.cameraPlan.actualV5ContextTurn??false} |`),'',
  `CSV SHA-256: \`${result.csv.sha256}\`. Source-file SHA values and per-chapter feature evidence are in CHAPTER_FEATURE_COVERAGE.json.`,
  'The camera uses actual preserved V5 math and original safe-area math on all 2,400 source states. Every chapter boundary is continuous. Actual native font layout, GPU materials, pixels, SFX mixing and visual rhythm require the separately approved hardware preview.',''];
 await writeFile(path.join(root,'reports/FRAME_TRACE_README.md'),md.join('\n'));
 return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const result=await buildFrameTrace();console.log(JSON.stringify({status:result.status,frames:result.totalFrames,chapters:result.chapterCount,
  sourceCounts:result.sourceCounts,frontGeometry:result.frontGeometry,csv:result.csv,nativeLayoutSpyCalls:result.nativeLayoutSpyCalls,
  nativeDrawSpyCalls:result.nativeDrawSpyCalls,renderedFrames:0,gpuExecuted:false}));
}
