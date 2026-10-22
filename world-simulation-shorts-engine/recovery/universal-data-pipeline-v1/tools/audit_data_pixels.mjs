/** Read-only independent data/clock/engine evidence audit. No render or GPU. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {analyzePrompt,canonicalJSON} from '../prompt_pipeline.mjs';
import {compileExistingEnginePlan} from '../../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {evaluateMinimumContextCameraFrame} from '../../../web/map_infographic_v1/camera_director_v5.mjs';
import {evaluateAreaFrame} from '../../../web/map_infographic_v1/area_core_v3.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '../../../web/map_infographic_v1/flow_core_v2.mjs';
const own=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const hash=b=>createHash('sha256').update(b).digest('hex'),json=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const check=(ok,code)=>{if(!ok)throw Error(code);};
const plain=x=>JSON.parse(JSON.stringify(x));
function same(a,b,where='value',eps=1e-7){
 if(typeof a==='number'&&typeof b==='number'){check(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=eps,`NUMERIC_MISMATCH:${where}:${a}:${b}`);return;}
 if(Array.isArray(a)&&Array.isArray(b)){check(a.length===b.length,'ARRAY_LENGTH:'+where);a.forEach((v,i)=>same(v,b[i],where+'['+i+']',eps));return;}
 if(a&&b&&typeof a==='object'&&typeof b==='object'){const ka=Object.keys(a).sort(),kb=Object.keys(b).sort();check(JSON.stringify(ka)===JSON.stringify(kb),'OBJECT_KEYS:'+where);ka.forEach(k=>same(a[k],b[k],where+'.'+k,eps));return;}
 check(a===b,'VALUE_MISMATCH:'+where);
}
const args={};for(const a of process.argv.slice(2)){const m=/^--(private-root|public-root|output-root)=(.+)$/.exec(a);check(m&&!args[m[1]],'AUDIT_ARGUMENT');args[m[1]]=m[2];}
const publicRoot=args['public-root']??path.join(own,'public-review'),output=args['output-root']??path.join(own,'reports');
const specs=[{case:1,prefix:'AVIATION_DEMO',example:'AVIATION_GERMANY.json'},{case:2,prefix:'FICTIONAL_AREA_DEMO',example:'FICTIONAL_NAMIBIA.json'},{case:3,prefix:'TRADE_DEMO',example:'TRADE_CHILE.json'}];
const report={schema:'WORLD_ENGINE_DATA_TO_PIXEL_AUDIT_V1',status:'IN_PROGRESS',scope:'INDEPENDENT_EXISTING_ENGINE_REEVALUATION_AND_ALL_FRAME_EVIDENCE',cases:[],paidExecuted:false,nvidiaVerified:false,visualQualityApproved:false,readOnly:true};
for(const spec of specs){
 const caseReport={prefix:spec.prefix,originalPrompt:'examples/'+spec.example,status:'IN_PROGRESS',failures:[]};report.cases.push(caseReport);
 try{
  const exports=path.join(args['private-root'],'case-'+spec.case,'exports'),jobs=(await fs.readdir(exports)).filter(n=>/^studio-[a-f0-9]+$/.test(n));check(jobs.length===1,'ONE_REAL_STUDIO_JOB_REQUIRED');
  const actualRoot=path.join(exports,jobs[0]),sceneRaw=await fs.readFile(path.join(actualRoot,'SCENE.json')),scene=JSON.parse(sceneRaw),runtime=await json(path.join(actualRoot,'RUNTIME.json'));
  const publicEvidence=path.join(publicRoot,spec.prefix+'_FRAME_EVIDENCE.json'),publicReceipt=path.join(publicRoot,spec.prefix+'_CAPTURE_RECEIPT.json');
  const evidenceRaw=await fs.readFile(publicEvidence),receiptRaw=await fs.readFile(publicReceipt),evidence=JSON.parse(evidenceRaw),receipt=JSON.parse(receiptRaw);
  const original=await fs.readFile(path.join(own,'examples',spec.example),'utf8'),analyzed=analyzePrompt(original);check(analyzed.status==='PASS','ORIGINAL_PROMPT_PASS_REQUIRED');
  const request=analyzed.renderRequests[0];same(scene,request.scene,'actual_scene_vs_original_prompt_compilation');same(runtime.scene,scene,'runtime_scene');same(receipt.inputTrace,request.inputTrace,'capture_input_trace');
  check(hash(sceneRaw)===receipt.sceneSHA256,'EXACT_SCENE_WIRE_SHA');check(receipt.frameEvidence.sha256===hash(evidenceRaw),'FRAME_EVIDENCE_SHA');
  check(receipt.status==='TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED'&&receipt.renderedFrames===90&&receipt.totalFrames===90&&evidence.frames.length===90,'ACTUAL_90_FRAME_RECEIPT');
  check(receipt.softwareOnly===true&&receipt.nvidiaVerified===false&&receipt.paidExecuted===false&&receipt.visualQualityApproved===false,'FREE_SOFTWARE_SCOPE');
  check(receipt.runtime.backend.includes('SwiftShader'),'ACTUAL_SWIFTSHADER_BACKEND');
  const plan=compileExistingEnginePlan(scene),cameraFrame=runtime.cameraPlan.totalFrames-1,camera=evaluateMinimumContextCameraFrame(runtime.cameraPlan,cameraFrame),b=camera.camera.flatBounds;
  const project=p=>[(p[0]-b[0])/(b[2]-b[0])*1080,(b[3]-p[1])/(b[3]-b[1])*1920],safe=runtime.nativePlan.layout.safe;
  const inSafe=p=>p[0]>=safe[0]&&p[0]<=safe[2]&&p[1]>=safe[1]&&p[1]<=safe[3];
  check(camera.cameraLocked&&camera.settle.locked&&!camera.admission.localUsed,'ACTUAL_LOCKED_CAMERA');
  same(runtime.cameraPlan.intent.anchor,scene.camera_intent.anchor,'actual_camera_anchor');
  same(runtime.cameraPlan.intent.eventGeometry,scene.geometries.filter(g=>scene.camera_intent.target_geometry_refs.includes(g.id)).map(g=>g.geometry),'camera_target_geometry');
  const material=runtime.sourceStyle.terrainAsset,gutter=Math.min((b[0]-material.bounds[0])/material.pixelSpacing[0],(b[1]-material.bounds[1])/material.pixelSpacing[1],(material.bounds[2]-b[2])/material.pixelSpacing[0],(material.bounds[3]-b[3])/material.pixelSpacing[1]);check(gutter>=1-1e-9,'SOURCE_VIEWPORT_SUPPORT');
  const rawSHAs=new Set(),baseSHAs=new Set(),states=new Set(),routeFractions=[],objectFractions=[],changed=[],positiveFrames=[];let flowDraws=0,objectDraws=0,areaDraws=0,routePositionChanges=0,lastPosition=null;
  for(let frame=0;frame<90;frame++){
   const row=evidence.frames[frame],d=row.diagnostic;check(row.frame===frame&&d.frame===frame,'FRAME_CLOCK_'+frame);same(d.timeSeconds,frame/30,'time');check(d.localEventFrame===frame-plan.globalEventStartFrame,'EVENT_CLOCK');
   check(/^[a-f0-9]{64}$/.test(row.rawSHA256)&&/^[a-f0-9]{64}$/.test(row.baseRawSHA256),'RAW_FRAME_SHA');rawSHAs.add(row.rawSHA256);baseSHAs.add(row.baseRawSHA256);
   check(row.nonBlackPixels>1080*1920*.2&&d.glError===0,'NONBLACK_GL');check(d.backend.includes('SwiftShader')&&d.nvidiaVerified===false&&d.qualityApproved===false,'FRAME_SOFTWARE_SCOPE');
   check(d.sourceGeometryBinding===JSON.stringify(scene.geometries),'SOURCE_GEOMETRY_BINDING');same(d.inputTrace,request.inputTrace,'per_frame_trace');
   check(d.camera.sourceFrame===cameraFrame,'CAMERA_SOURCE_FRAME');same(d.camera.state,camera,'actual_camera_state');same(d.camera.actualFactory.bounds,b,'factory_camera_bounds');check(d.camera.motionClaimed===false,'LOCKED_PROFILE_CLAIM');
   same(d.suppliedCameraAnchor.geographic,scene.camera_intent.anchor,'source_anchor');same(d.suppliedCameraAnchor.projected,project(scene.camera_intent.anchor),'actual_projected_anchor');check(d.suppliedCameraAnchor.inSafe===inSafe(project(scene.camera_intent.anchor)),'ANCHOR_SAFE_FLAG');
   check(d.suppliedLocations.length===scene.locations.length,'LOCATION_COUNT');
   for(const [i,location]of scene.locations.entries()){const actual=d.suppliedLocations[i];check(actual.id===location.id,'LOCATION_ID');same(actual.anchor,location.anchor,'LOCATION_SOURCE');same(actual.projected,project(location.anchor),'LOCATION_PROJECTED');check(actual.inSafe===inSafe(project(location.anchor)),'LOCATION_SAFE');}
   check(d.layout.valid&&d.layout.visibleNativeLabels===false,'LAYOUT_ADMISSION');check(d.material.fullViewportCovered&&d.material.demEnabled===false&&d.material.defaultCountryTintEnabled===false,'MATERIAL_SCOPE');same(d.material.minimumSourceGutterPixels,gutter,'MATERIAL_GUTTER');same(d.material.bounds,material.bounds,'MATERIAL_SOURCE_BOUNDS');check(d.material.terrainSHA256===material.sha256,'MATERIAL_SHA');
   check(d.markers.length===(scene.markers??[]).length,'SUPPLIED_MARKERS_ONLY');
   check(d.features.length===plan.plans.length,'ENGINE_PLAN_COUNT');
   for(const binding of plan.plans){
    const feature=d.features.find(f=>f.id===binding.id&&f.engine===binding.engine);check(feature,'ENGINE_BINDING_'+binding.id);const local=d.localEventFrame;
    if(binding.engine==='EXISTING_FLOW_V2'){
     const primitive=compileFlowRoute(binding.plan.intent,{project}),expected=evaluateFlowFrame(binding.plan,binding.plan.startFrame+local,{primitive,eventContext:{cameraState:camera,project,safeArea:safe,scalePlan:runtime.nativePlan,heightSource:null,protectedBoxes:d.markers.map(m=>m.box)}});
     check(feature.state===expected.state,'FLOW_STATE');same(feature.geometry,binding.plan.intent.route_geometry,'FLOW_GEOGRAPHIC_ROUTE');same(feature.projectedRoute,primitive.screenCoordinates,'FLOW_PROJECTED_ROUTE');
     for(const k of ['routeFraction','objectFraction','objectPosition','heading','departurePulse','arrivalPulse'])same(feature[k],expected[k],'FLOW_'+k);
     routeFractions.push(feature.routeFraction);objectFractions.push(feature.objectFraction);
     if(feature.routeFraction>0){check(feature.draw.route.drawn,'FLOW_ROUTE_DRAW');flowDraws++;check(d.featureChangedPixels>0,'FLOW_ACTUAL_CHANGED_PIXELS');}
     if(expected.objectVisible){check(feature.draw.object?.drawn,'FLOW_OBJECT_DRAW');same(feature.draw.object.position,expected.objectPosition,'GPU_OBJECT_POSITION');same(feature.draw.object.graphicDimensions,[binding.plan.intent.object_graphic.width_px,binding.plan.intent.object_graphic.height_px],'GPU_SUPPLIED_GRAPHIC_DIMENSIONS');objectDraws++;}
     if(lastPosition&&JSON.stringify(lastPosition)!==JSON.stringify(feature.objectPosition))routePositionChanges++;lastPosition=feature.objectPosition;
    }else if(binding.engine==='EXISTING_AREA_V3'){
     const expected=evaluateAreaFrame(binding.plan,binding.plan.startFrame+local,{project});check(feature.stateId===expected.stateId&&feature.state===expected.state,'AREA_STATE');states.add(feature.stateId);same(feature.activeFeatures,expected.activeFeatures,'AREA_ACTIVE_FEATURES');
     same(feature.sourceAreas,plain(expected.areas.map(a=>({id:a.id,stateId:a.state_id,geometry:a.geometry,alpha:a.alpha,coverage:a.coverage}))),'AREA_SOURCE_GEOMETRY_ALPHA_COVERAGE');
     same(feature.sourceFronts,plain(expected.fronts.map(f=>({id:f.id,geometry:f.geometry,alpha:f.alpha,revealFraction:f.revealFraction}))),'AREA_SOURCE_FRONT_TIMELINE');
     if(feature.draw.areas?.some(a=>a.drawn))areaDraws++;
    }else throw Error('UNSUPPORTED_ENGINE_WAS_RENDERED');
   }
   check(Number.isSafeInteger(d.featureChangedPixels)&&d.featureChangedPixels>=0,'MEASURED_FEATURE_PIXELS');changed.push(d.featureChangedPixels);if(d.featureChangedPixels>0)positiveFrames.push(frame);
  }
  check(baseSHAs.size===1,'FIXED_CAMERA_BASEMAP_STABILITY');check(rawSHAs.size>1,'INPUT_FEATURE_ANIMATION_PIXELS');check(positiveFrames.length>0,'NO_ACTUAL_FEATURE_PIXELS');
  if(scene.event_type==='TRANSPORT')check(flowDraws>0&&objectDraws>0&&routePositionChanges>0&&Math.min(...objectFractions)===0&&Math.max(...objectFractions)===1,'FLOW_TRAVEL_NOT_ACTUALLY_ANIMATED');
  if(scene.event_type==='WAR')check(states.size>=2&&areaDraws>0,'AREA_SUPPLIED_STATE_CHANGE_MISSING');
  Object.assign(caseReport,{status:'DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED',actualStudioJobId:jobs[0],family:scene.event_type,inputSHA256:analyzed.inputSHA256,sceneWireSHA256:hash(sceneRaw),sceneSemanticSHA256:hash(Buffer.from(canonicalJSON(scene))),
   publicFrameEvidence:path.basename(publicEvidence),frameEvidenceSHA256:hash(evidenceRaw),receiptSHA256:hash(receiptRaw),allFrames:90,frameClock:'EXACT_0_TO_89_30FPS',allSourceBindingsMatch:true,allInputTracesMatch:true,
   independentlyReevaluatedEngineFrames:true,actualFlowRouteDrawFrames:flowDraws,actualMovingObjectDrawFrames:objectDraws,objectPositionChanges:routePositionChanges,actualAreaDrawFrames:areaDraws,suppliedAreaStateIds:[...states],
   routeFractionRange:routeFractions.length?[Math.min(...routeFractions),Math.max(...routeFractions)]:null,objectFractionRange:objectFractions.length?[Math.min(...objectFractions),Math.max(...objectFractions)]:null,
   featureChangedPixels:{minimum:Math.min(...changed),maximum:Math.max(...changed),positiveFrames:positiveFrames.length,firstPositiveFrame:positiveFrames[0],lastPositiveFrame:positiveFrames.at(-1)},
   uniqueFinalRawFrames:rawSHAs.size,uniqueBaseRawFrames:baseSHAs.size,sourceTerrainSHA256:material.sha256,minimumSourceGutterPixels:gutter,sourceRegionId:receipt.sourceRegionId,
   projectedInputLocations:scene.locations.map(l=>({id:l.id,geographic:l.anchor,expectedProjected:project(l.anchor),inSafe:inSafe(project(l.anchor))})),
   noIgnoredRequests:{visibleTextRequested:false,onlyOriginalSuppliedMarkers:true,markerLabelsAndObjectProfileIdentifiers:'EXPLICIT_SEMANTIC_METADATA_ONLY',cameraProfile:'EXPLICIT_REGISTERED_REGIONAL_LOCKED',customCameraMotionClaimed:false,physicalSpeedClaimed:false,defaultCountryControlTint:false,sourceFramesFromFixedDemoUsed:false}});
 }catch(error){caseReport.status='FAIL';caseReport.failures.push(String(error.message));}
}
report.status=report.cases.every(c=>c.status==='DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED')?'DATA_TO_PIXEL_TECHNICAL_PASS_QUALITY_REVIEW_REQUIRED':'FAIL';report.totalFramesAudited=report.cases.reduce((n,c)=>n+(c.allFrames??0),0);
await fs.mkdir(output,{recursive:true});await fs.writeFile(path.join(output,'DATA_TO_PIXEL_AUDIT.json'),JSON.stringify(report,null,2)+'\n');
const lines=['# Scene to actual pixel audit','',`Status: **${report.status}**. This is a technical source/clock/engine audit, not user video-quality approval.`,
 '', 'The audit reads the exact Scene wire used by each real detached Studio worker, recompiles the original supplied prompt independently, re-evaluates existing Camera V5/Area V3/Flow V2 controls for every frame, and compares all persisted frame diagnostics. It independently checks geographic-to-screen coordinates using the native flat viewport formula. It does not render, alter source files, fabricate missing frames, or use a GPU.',
 '', '| Real Studio subject | Frames checked | Actual feature draws | Input-to-pixel result |','|---|---:|---|---|'];
for(const c of report.cases)lines.push(`| ${c.prefix} | ${c.allFrames??0} | Flow ${c.actualFlowRouteDrawFrames??0}; object ${c.actualMovingObjectDrawFrames??0}; Area ${c.actualAreaDrawFrames??0} | ${c.status} |`);
lines.push('','Every successful case preserves exact source geometry, semantic input trace, original event clock, real admitted locked camera, source-native terrain coverage and actual layout admission. Measured pre/post feature readPixels differences are distinct from nonblack base-map pixels. The paired changed-input proof separately establishes that changing an input route changes actual pixels while leaving the map and camera unchanged.',
 '', 'Scene semantic SHA and exact-wire SHA are recorded separately. The unchanged strict Planner validator requires canonical geometry member ordering; the new Studio wire-string persistence bridge preserves it across Python sorted-key cache storage. No original validation is weakened.',
 '', 'Limitations: registered regional views are locked; arbitrary pan/zoom, physical travel speed, visible arbitrary labels/text, automatic named object artwork, worldwide source coverage, historical ownership reconstruction, and LINE_METRIC/DISASTER pixel profiles are not claimed. Supplied locality/marker labels and object-profile identifiers are explicitly semantic metadata. These three demos are illustrative general/fictional inputs; they are not observed airline, shipping, or historical military movements.',
 '', 'The legacy diagnostic `nativeDraw` is a frame ordinal in the current consumer; this audit uses capture-receipt measured draw counts and complete frame rows instead of interpreting a random-access frame ordinal as a measured count.',
 '', 'NVIDIA hardware validation, final visual quality, external Dropbox delivery, G3, paid rendering and FINAL promotion remain outside this result.');
if(report.status==='FAIL')for(const c of report.cases)for(const f of c.failures)lines.push('',`${c.prefix}: ${f}`);
await fs.writeFile(path.join(own,'SCENE_TRACE_REPORT.md'),lines.join('\n')+'\n');
process.stdout.write(JSON.stringify({status:report.status,totalFramesAudited:report.totalFramesAudited,cases:report.cases.map(c=>({prefix:c.prefix,status:c.status,failures:c.failures}))})+'\n');if(report.status==='FAIL')process.exitCode=1;
