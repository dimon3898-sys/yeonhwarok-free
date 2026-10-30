/** Explicit moving-projection composition; unchanged engines own every pixel. */
import * as THREE from '/three.js';
import {createMapInfographicRenderer} from '../../web/map_infographic_v1/renderer.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {evaluateAreaFrame} from '../../web/map_infographic_v1/area_core_v3.mjs';
import {createAreaOverlayPass} from '../../web/map_infographic_v1/area_overlay_pass_v3.mjs';
import {selectAreaStyle} from '../../web/map_infographic_v1/area_style_v3.mjs';
import {compileFlowRoute,evaluateFlowFrame} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {createFlowGraphicPass} from '../../web/map_infographic_v1/flow_graphic_pass_v2.mjs';
import {selectEventLineStyle} from '../../web/map_infographic_v1/event_style_v1.mjs';
import {createMovingGraphicPass} from '../../web/map_infographic_v1/graphic_motion_pass_v4.mjs';
import {auditRuntimeLayout} from '../../web/map_infographic_v1/graphic_layout.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame} from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {evaluatePresentationCameraFrame,projectBounds,reprojectFlowPresentation,assertMovingProjectionAdmission,compilePresentationEnginePlan} from '../universal-presentation-v2/presentation_plan.mjs';
import {assertNvidiaVulkanContext,validateNativeStability} from './backend/native_guard.mjs';
import {createPresentationLabelPass} from '../universal-presentation-v2/presentation_label_layer.mjs';

export const PRESENTATION_RUNTIME_SCHEMA='WORLD_ENGINE_NVIDIA_PRESENTATION_RUNTIME_V1';
const copy=x=>structuredClone(x),assert=(v,c)=>{if(!v)throw Error(c);};
const inside=(p,b)=>p[0]>=b[0]&&p[0]<=b[2]&&p[1]>=b[1]&&p[1]<=b[3];
const finiteBox=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3];
const flatPoints=g=>g.type==='Polygon'?g.coordinates.flat():g.type==='MultiPolygon'?g.coordinates.flat(2):g.coordinates;

/** Source data, camera track and regional coverage were qualified before claim.
 * Actual current-projection admission is nevertheless repeated at every draw. */
export async function createNvidiaPresentationRuntime({canvas,scene,nativePlan,baseCameraPlan,presentationPlan,sourceStyle,terrainTreatment,inputTrace=null,diagnostics=null}={}){
 const observe=(operation,task)=>diagnostics?diagnostics.run(operation,task,{sourceId:'PRESENTATION_RUNTIME'}):task();
 validateScenePlan(scene);
 assert(scene.timing.fps===30&&scene.timing.total_frames>=2&&scene.timing.total_frames<=240,'UP2_FREE_FRAME_SCOPE');
 assert(canvas?.width===1080&&canvas?.height===1920,'UP2_CANONICAL_CANVAS_REQUIRED');
 assert(['NE1_SOURCE_NATIVE_COVERAGE','GLOBAL_RGB_SOURCE_NATIVE_COVERAGE'].includes(sourceStyle?.styleId),'UP2_ACTUAL_NATIVE_SOURCE_REQUIRED');
 assert(sourceStyle.terrainAsset.sha256===nativePlan.assets.terrain.sha256&&terrainTreatment===sourceStyle.terrainTreatment,'UP2_SOURCE_BINDING_REQUIRED');
 assert(baseCameraPlan?.directorVersion==='CAMERA_DIRECTOR_V5'&&presentationPlan?.actualMovingCameraLockForged===false,'UP2_CAMERA_OWNER_REQUIRED');
 const original=JSON.stringify({scene,nativePlan,baseCameraPlan,presentationPlan,sourceStyle}),p=presentationPlan.presentation,engines=compilePresentationEnginePlan({scene,presentation:p}),safe=copy(nativePlan.layout.safe);
 const gl=await observe('WEBGL_CONTEXT',()=>{const gl=canvas.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});assert(gl,'UP2_WEBGL2_REQUIRED');return gl;});
 const{backend}=await observe('RENDERER_IDENTIFICATION',()=>assertNvidiaVulkanContext(gl));
 const renderer=new THREE.WebGLRenderer({canvas,context:gl,antialias:false});renderer.setPixelRatio(1);renderer.setSize(1080,1920,false);renderer.autoClear=false;
 renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 let labelPass=null;
 let factory,graphics,last,lastBasePixels,disposed=false,nativeStabilityProof=null;const passes=[];
 try{
  factory=await observe('MAP_TEXTURE_PREPARATION',()=>createMapInfographicRenderer({canvas,plan:nativePlan,layoutPlan:nativePlan,outputRenderer:renderer,terrainTreatment}));
  graphics=await observe('GRAPHICS_PREPARATION',()=>createMovingGraphicPass({renderer,factory,width:1080,height:1920}));
  if(p.labels?.enabled===true&&p.labels.items.length){labelPass=createPresentationLabelPass({renderer,THREE,width:1080,height:1920});passes.push(labelPass);}
  // Derived plans are created in their consuming JS realm. The frozen owner's
  // canonical check is retained; JSON is the transport for authored inputs,
  // not a promise that Node/Chromium Math.log coefficients are bit-identical.
  const transportedTrack=presentationPlan.track,browserTrack=compileReferenceCameraTrack({baseCameraPlan:transportedTrack.baseCameraPlan,currentNativeFrame:transportedTrack.currentNativeFrame,keyframes:transportedTrack.keyframes,totalFrames:transportedTrack.totalFrames,fps:transportedTrack.fps});
  function firstDifference(a,b,p='$'){if(typeof a!==typeof b)return{path:p,transported:a,browser:b};if(a===null||b===null||typeof a!=='object')return a===b?null:{path:p,transported:a,browser:b};for(const key of new Set([...Object.keys(a),...Object.keys(b)])){const found=firstDifference(a[key],b[key],p+'.'+key);if(found)return found;}return null;}
  const trackHydration={owner:'UNCHANGED_REFERENCE_CAMERA_ADAPTER_V1_COMPILED_IN_CONSUMER_REALM',authoredKeyframesPreserved:JSON.stringify(browserTrack.keyframes)===JSON.stringify(transportedTrack.keyframes),firstDerivedDifference:firstDifference(transportedTrack,browserTrack),transportedDerivedPlanPassedAsCanonical:false};
  assert(trackHydration.authoredKeyframesPreserved,'UP2_CAMERA_KEYFRAME_TRANSPORT_CHANGED');
  assert(presentationPlan.cpuFrameBounds?.length===scene.timing.total_frames,'UP2_CPU_CAMERA_SAMPLES_REQUIRED');
  trackHydration.maximumBrowserCPUFrameBoundDeltaDegrees=0;
  for(let f=0;f<scene.timing.total_frames;f++){const actual=evaluateReferenceCameraTrackFrame(browserTrack,f).flatBounds,cpu=presentationPlan.cpuFrameBounds[f];assert(Array.isArray(cpu)&&cpu.length===4&&cpu.every(Number.isFinite),'UP2_CPU_CAMERA_SAMPLE_INVALID');trackHydration.maximumBrowserCPUFrameBoundDeltaDegrees=Math.max(trackHydration.maximumBrowserCPUFrameBoundDeltaDegrees,...actual.map((v,i)=>Math.abs(v-cpu[i])));}
  assert(trackHydration.maximumBrowserCPUFrameBoundDeltaDegrees<=1e-9,'UP2_BROWSER_CAMERA_TRANSPORT_DRIFT');trackHydration.comparedFrameCount=scene.timing.total_frames;
  const activePresentationPlan={...presentationPlan,track:browserTrack};
  factory.updateCamera(presentationPlan.analysisBounds);factory.setTerrainLod(1);
  const analysisProject=point=>projectBounds(presentationPlan.analysisBounds,point);
  for(const location of scene.locations){const actual=factory.screen(location.anchor),model=analysisProject(location.anchor);assert(Math.hypot(actual[0]-model[0],actual[1]-model[1])<1e-6,'UP2_ANALYSIS_PROJECTION_MISMATCH');}
  const baseline=copy(graphics.baseline),nativeMarker=baseline.find(i=>i.kind==='MARKER');assert(nativeMarker,'UP2_ORIGINAL_MARKER_DESIGN_REQUIRED');
  const colorPasses=new Map(),defaultAreaStyle=selectAreaStyle({primaryMaterialColor:nativePlan.theme.primary});
  function areaPass(stateId){const key=stateId??'__DEFAULT__';if(!colorPasses.has(key)){
   const style=copy(defaultAreaStyle),color=p.territoryColors?.[stateId];if(color)style.AREA.fillColor=copy(color);
   const pass=createAreaOverlayPass({canvas,style});passes.push(pass);colorPasses.set(key,pass);
  }return colorPasses.get(key);}
  const bindings=engines.plans.map(binding=>{
   if(binding.engine==='EXISTING_AREA_V3')return binding;
   assert(binding.engine==='EXISTING_FLOW_V2','UP2_ENGINE_UNSUPPORTED');
   const style=selectEventLineStyle({role:'PRIMARY',theme:nativePlan.theme,primaryMaterialColor:nativePlan.theme.primary}),pass=createFlowGraphicPass({canvas,style});passes.push(pass);
   return{...binding,pass,style,analysisPrimitive:compileFlowRoute(binding.plan.intent,{project:analysisProject})};
  });
  const project=point=>factory.screen(point),source=sourceStyle.terrainAsset;
  function markersAt(frame){
   const rows=(scene.markers??[]).map(item=>({id:item.id,anchor:copy(item.anchor),kind:'MARKER',scale:1,source:'SUPPLIED_SCENE_MARKER'}));
   for(const h of p.highlights)if(frame>=h.startFrame&&frame<h.endFrame){const location=scene.locations.find(l=>l.id===h.locationId),progress=(frame-h.startFrame)/(h.endFrame-h.startFrame-1);
    rows.push({id:h.id,anchor:copy(location.anchor),kind:'MARKER',scale:1+.4*Math.sin(Math.PI*progress),source:'SUPPLIED_LOCATION_EVENT_NATIVE_MARKER_PULSE',locationId:h.locationId,progress});}
   for(const row of rows){row.position=project(row.anchor);row.size=nativeMarker.box[2]*row.scale;const r=row.size/2+2;row.box=[row.position[0]-r,row.position[1]-r,row.position[0]+r,row.position[1]+r];
    assert(finiteBox(row.box)&&inside(row.box.slice(0,2),safe)&&inside(row.box.slice(2),safe),'UP2_SUPPLIED_MARKER_FULL_ROI_OUTSIDE_SAFE');}
   assert(rows.length<=64,'UP2_MARKER_RESERVATION_CAPACITY');return rows;
  }
  function drawFrame(frame){
   assert(!disposed&&Number.isSafeInteger(frame)&&frame>=0&&frame<scene.timing.total_frames,'UP2_FRAME_RANGE');
   const camera=evaluatePresentationCameraFrame(activePresentationPlan,frame),bounds=camera.flatBounds;
   renderer.resetState();factory.updateCamera(bounds);
   const gutter=Math.min((bounds[0]-source.bounds[0])/source.pixelSpacing[0],(bounds[1]-source.bounds[1])/source.pixelSpacing[1],(source.bounds[2]-bounds[2])/source.pixelSpacing[0],(source.bounds[3]-bounds[3])/source.pixelSpacing[1]);
   assert(gutter>=1-1e-8,'UP2_CURRENT_SOURCE_COVERAGE_FAILED');
   for(const location of scene.locations){const expected=projectBounds(bounds,location.anchor),actual=project(location.anchor);assert(Math.hypot(actual[0]-expected[0],actual[1]-expected[1])<1e-6,'UP2_CURRENT_COORDINATE_MISMATCH');}
   const layoutAudit=auditRuntimeLayout({plan:nativePlan,screen:project});assert(layoutAudit.validation.valid,'UP2_CURRENT_LAYOUT_FAILED');
   const native=factory.renderFrame({mode:1,graphics:false,boundaries:false,glow:false,dem:false,primaryMaterial:0,reveal:{primary:0,marker:0,location:0,country:0,title:0,disclosure:0}});
   const basePixels=factory.readPixels();lastBasePixels=basePixels;const markerRows=markersAt(frame),features=[],localFrame=frame-engines.globalEventStartFrame;
   if(localFrame>=0)for(const binding of bindings){assert(localFrame<binding.plan.totalFrames,'UP2_ENGINE_FRAME_BINDING_REQUIRED');
    if(binding.engine==='EXISTING_AREA_V3'){
     const controls=evaluateAreaFrame(binding.plan,binding.plan.startFrame+localFrame,{project}),groups=[...new Set(controls.areas.map(a=>a.state_id??'__DEFAULT__'))];if(!groups.length)groups.push('__DEFAULT__');
     for(const area of controls.areas)if(area.alpha>0)assert(flatPoints(area.geometry).every(q=>inside(project(q),safe)),'UP2_AREA_SOURCE_FOOTPRINT_OUTSIDE_SAFE');
     const draws=groups.map((id,index)=>{const subset={...controls,areas:controls.areas.filter(a=>(a.state_id??'__DEFAULT__')===id),fronts:index===0?controls.fronts:[],impacts:index===0?controls.impacts:[],propagations:index===0?controls.propagations:[]};
      return{stateId:id,color:p.territoryColors?.[id]??defaultAreaStyle.AREA.fillColor,draw:areaPass(id).draw({controls:subset,project,safeArea:safe,protectedGraphics:markerRows,primaryMaterialColor:nativePlan.theme.primary,boundarySegments:[]})};});
     for(const item of controls.areas)if(item.alpha>0&&item.coverage>0)assert(draws.some(d=>d.draw.areas.some(a=>a.id===item.id&&a.drawn)),'UP2_AREA_NOT_DRAWN');
     features.push({id:binding.id,engine:binding.engine,state:controls.state,stateId:controls.stateId,activeFeatures:controls.activeFeatures,presentationOperationBinding:copy(binding.presentationOperationBinding??null),sourceAreas:controls.areas.map(a=>({id:a.id,stateId:a.state_id,geometry:copy(a.geometry),coverage:a.coverage,alpha:a.alpha})),sourceFronts:controls.fronts.map(f=>({id:f.id,geometry:copy(f.geometry),alpha:f.alpha,revealFraction:f.revealFraction})),draws});
    }else{
     const model=evaluateFlowFrame(binding.plan,binding.plan.startFrame+localFrame,{primitive:binding.analysisPrimitive,eventContext:{cameraState:presentationPlan.analysisCamera,project:analysisProject,safeArea:safe,scalePlan:nativePlan,heightSource:null,protectedBoxes:[]}}),primitive=compileFlowRoute(binding.plan.intent,{project}),controls=reprojectFlowPresentation({modelControls:model,primitive,flowIntent:binding.plan.intent});
     const admission=assertMovingProjectionAdmission({primitive,controls,camera,modelCamera:presentationPlan.analysisCamera,safeArea:safe,sourceBounds:source.bounds,project,sourceGeometry:binding.plan.intent.route_geometry,currentBounds:bounds,protectedGraphics:markerRows,flowIntent:binding.plan.intent});
     const draw=binding.pass.draw({primitive,controls,safeArea:safe,protectedGraphics:markerRows,flowIntent:binding.plan.intent});
     assert(!controls.objectVisible||draw.object?.drawn===true,'UP2_FLOW_OBJECT_NOT_DRAWN');assert(controls.routeFraction===0||draw.route?.drawn===true,'UP2_FLOW_ROUTE_NOT_DRAWN');
     features.push({id:binding.id,engine:binding.engine,state:controls.state,routeFraction:controls.routeFraction,objectFraction:controls.objectFraction,objectPosition:copy(controls.objectPosition),heading:controls.heading,departurePulse:controls.departurePulse,arrivalPulse:controls.arrivalPulse,routeReveal:controls.routeReveal,geometry:copy(binding.plan.intent.route_geometry),projectedRoute:copy(primitive.screenCoordinates),admission,modelEventReadinessScope:controls.eventControls.readinessScope,draw});
    }
   }
   const featurePixels=factory.readPixels();let featureChangedPixels=0;for(let i=0;i<featurePixels.length;i+=4)if(featurePixels[i]!==basePixels[i]||featurePixels[i+1]!==basePixels[i+1]||featurePixels[i+2]!==basePixels[i+2]||featurePixels[i+3]!==basePixels[i+3])featureChangedPixels++;
   if(features.some(f=>f.engine==='EXISTING_FLOW_V2'&&f.routeFraction>0)||features.some(f=>f.engine==='EXISTING_AREA_V3'&&f.sourceAreas.some(a=>a.alpha>0&&a.coverage>0)))assert(featureChangedPixels>0,'UP2_ACTUAL_FEATURE_PIXELS_MISSING');
   renderer.resetState();for(const marker of markerRows){const items=copy(baseline),item=items.find(i=>i.kind==='MARKER');item.box=[marker.position[0]-marker.size/2,marker.position[1]-marker.size/2,marker.size,marker.size];graphics.draw({items,reveal:{marker:1,location:0,country:0,title:0,disclosure:0}});}
   const labelDraw=labelPass?labelPass.draw({labels:p.labels,scene,frame,project,safeArea:safe,protectedBoxes:markerRows}):null;
   gl.finish();assert(gl.getError()===gl.NO_ERROR,'UP2_ACTUAL_DRAW_GL_ERROR');assert(JSON.stringify({scene,nativePlan,baseCameraPlan,presentationPlan,sourceStyle})===original,'UP2_SOURCE_MUTATION');
   last={schema:PRESENTATION_RUNTIME_SCHEMA,frame,timeSeconds:frame/30,localEventFrame:localFrame,backend,get nvidiaVerified(){return nativeStabilityProof!==null;},qualityApproved:false,
    camera:{owner:presentationPlan.movingCameraOwner,profile:presentationPlan.mode,state:camera,actualFactory:copy(factory.evidence.cameraFrame),center:camera.camera.center??[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2],bounds:copy(bounds),motionClaimed:true,actualCameraLocked:false,actualSettleLocked:false,trackHydration},
    fixedModelCamera:{sourceFrame:presentationPlan.analysisSourceFrame,state:presentationPlan.analysisCamera,scope:'UNCHANGED_FLOW_TIMING_ONLY_NEVER_CURRENT_MOVING_CAMERA'},
    layout:{valid:layoutAudit.validation.valid,visibleNativeLabels:false,locationRecovery:layoutAudit.validation.locationRecovery},
    material:{styleId:sourceStyle.styleId,terrainTreatment,terrainSHA256:source.sha256,sourceOriginalSHA256:source.sourceOriginalSHA256,bounds:copy(source.bounds),cameraBounds:copy(bounds),minimumSourceGutterPixels:gutter,fullViewportCovered:true,demEnabled:false,defaultCountryTintEnabled:false,classification:source.classification},
    suppliedLocations:scene.locations.map(l=>({id:l.id,anchor:copy(l.anchor),projected:project(l.anchor),inSafe:inside(project(l.anchor),safe)})),markers:copy(markerRows),features,featureChangedPixels,
    featurePixelComparison:'ACTUAL_NATIVE_MAP_READPIXELS_BEFORE_AND_AFTER_FEATURE_PASSES_BEFORE_MARKERS',inputTrace:copy(inputTrace),sourceGeometryBinding:engines.sourceGeometryBinding,nativeDraw:frame+1,glError:native.glError};
   if(labelDraw){last.layout.visiblePresentationLabels=labelDraw.visibleCount>0;last.presentationLabels=copy(labelDraw);}
   return last;
  }
  const truthfulFactoryEvidence=copy(factory.evidence);if(sourceStyle.styleId==='GLOBAL_RGB_SOURCE_NATIVE_COVERAGE')truthfulFactoryEvidence.sourceRelief='ACTUAL_GLOBAL_RGB_AND_EXISTING_NATIVE_RELIEF_PROXY_NO_DEM_OR_BAKED_HILLSHADE_CLAIM';
  return{drawFrame,readPixels:factory.readPixels,readBasePixels:()=>{assert(lastBasePixels,'UP2_FRAME_NOT_DRAWN');return lastBasePixels;},png:()=>canvas.toDataURL('image/png'),project,
   evidence:{schema:PRESENTATION_RUNTIME_SCHEMA,backend,softwareOnly:false,get nvidiaVerified(){return nativeStabilityProof!==null;},get actualGPUVerified(){return nativeStabilityProof!==null;},visualQualityApproved:false,existingEngines:engines.plans.map(b=>b.engine),nativeFactory:truthfulFactoryEvidence,materialSource:copy(sourceStyle),movingComposition:'NEW_EXPLICIT_PROJECTED_COMPOSITION_OLD_EVENT_ADMISSION_NOT_FORGED',modelCamera:copy(presentationPlan.analysisCamera),trackHydration,countrySpecificBranches:false,finishedFrameBlit:false},
   recordNativeStability(proof){validateNativeStability(proof,backend);nativeStabilityProof=copy(proof);},get diagnostic(){return last;},dispose(){if(disposed)return;passes.forEach(pass=>pass.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();disposed=true;}};
 }catch(error){if(diagnostics){await diagnostics.cleanup(()=>passes.forEach(pass=>pass.dispose()));await diagnostics.cleanup(()=>graphics?.dispose());await diagnostics.cleanup(()=>factory?.dispose());await diagnostics.cleanup(()=>renderer.dispose());}
  else{passes.forEach(pass=>pass.dispose());graphics?.dispose();factory?.dispose();renderer.dispose();}throw error;}
}
