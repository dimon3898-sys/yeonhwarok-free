/** Data-only presentation composition over unchanged V5/Flow/Area owners. */
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame} from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {evaluateMinimumContextCameraFrame} from '../../web/map_infographic_v1/camera_director_v5.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';
import {compileFlowRoute,evaluateFlowFrame,sampleFlowRoute} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {evaluateGeographicLineReveal} from '../../web/map_infographic_v1/event_line_v1.mjs';
import {compileAreaPlan} from '../../web/map_infographic_v1/area_core_v3.mjs';

export const PRESENTATION_VERSION='WORLD_ENGINE_PRESENTATION_PLAN_V2';
const copy=v=>structuredClone(v),ok=(v,c)=>{if(!v)throw Error(c);};
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const point=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90;
const unit=x=>Number.isFinite(x)&&x>=0&&x<=1;
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],span=b=>[b[2]-b[0],b[3]-b[1]];
const contains=(p,b,pad=0)=>p[0]>=b[0]+pad&&p[0]<=b[2]-pad&&p[1]>=b[1]+pad&&p[1]<=b[3]-pad;
function keys(x,allowed,code){ok(object(x),code+'_OBJECT_REQUIRED');ok(Object.keys(x).every(k=>allowed.includes(k)),code+'_UNKNOWN_FIELD');}
function frame(f,n,end=false){return Number.isSafeInteger(f)&&f>=0&&f<(end?n+1:n);}
export function projectBounds(bounds,point){return[(point[0]-bounds[0])/(bounds[2]-bounds[0])*1080,(bounds[3]-point[1])/(bounds[3]-bounds[1])*1920];}
export function unprojectBounds(bounds,pixel){return[bounds[0]+pixel[0]/1080*(bounds[2]-bounds[0]),bounds[3]-pixel[1]/1920*(bounds[3]-bounds[1])];}

/** Unknown/unconsumed controls fail rather than being accepted as metadata. */
export function validatePresentation(input,{scene,region}={}){
 keys(input,['camera','territoryColors','highlights','transitions','initialStateVisibility'],'PRESENTATION');
 ok(scene?.timing?.fps===30&&Number.isSafeInteger(scene.timing.total_frames),'PRESENTATION_SCENE_TIMING_REQUIRED');
 const n=scene.timing.total_frames,result=copy(input);
 result.initialStateVisibility=input.initialStateVisibility??'REVEAL';
 ok(['REVEAL','PRESERVE_PROVIDED'].includes(result.initialStateVisibility),'PRESENTATION_INITIAL_VISIBILITY_UNSUPPORTED');
 if(result.initialStateVisibility==='PRESERVE_PROVIDED')ok(scene.event_type==='WAR'&&scene.timing.event_start_frame===0,'PRESENTATION_ALREADY_VISIBLE_AREA_WITHOUT_EVENT_PREFIX_REQUIRED');
 keys(input.camera,['mode','keyframes','routeId','zoom','followStrength'],'PRESENTATION_CAMERA');
 ok(['KEYFRAMES','ROUTE_FOLLOW'].includes(input.camera.mode),'PRESENTATION_CAMERA_MODE_UNSUPPORTED');
 if(input.camera.mode==='KEYFRAMES'){
  ok(input.camera.routeId===undefined&&input.camera.zoom===undefined&&input.camera.followStrength===undefined,'PRESENTATION_KEYFRAME_FIELD_CONFLICT');
  const rows=input.camera.keyframes;ok(Array.isArray(rows)&&rows.length>=2&&rows.length<=32,'PRESENTATION_KEYFRAMES_REQUIRED');
  for(const [i,k]of rows.entries()){
   keys(k,['frame','center','zoom'],'PRESENTATION_KEYFRAME');
   ok(frame(k.frame,n)&&point(k.center)&&Number.isFinite(k.zoom)&&k.zoom>0&&k.zoom<=1,'PRESENTATION_KEYFRAME_RANGE_INVALID');
   ok(!i||k.frame>rows[i-1].frame,'PRESENTATION_KEYFRAME_ORDER_INVALID');
  }
  ok(rows[0].frame===0&&rows.at(-1).frame===n-1,'PRESENTATION_COMPLETE_KEYFRAME_RANGE_REQUIRED');
  ok(rows.every(k=>k.zoom<=rows.at(-1).zoom),'PRESENTATION_FINAL_ENDPOINT_CLOSEST_REQUIRED');
 }else{
  ok(input.camera.keyframes===undefined,'PRESENTATION_FOLLOW_KEYFRAME_CONFLICT');
  ok(typeof input.camera.routeId==='string'&&scene.routes?.some(r=>r.id===input.camera.routeId),'PRESENTATION_FOLLOW_SUPPLIED_ROUTE_REQUIRED');
  const zoom=input.camera.zoom??.75,strength=input.camera.followStrength??.2;
  ok(Number.isFinite(zoom)&&zoom>0&&zoom<=1&&Number.isFinite(strength)&&strength>0&&strength<=1,'PRESENTATION_FOLLOW_RANGE_INVALID');
  result.camera.zoom=zoom;result.camera.followStrength=strength;
 }
 if(input.territoryColors!==undefined){
  ok(object(input.territoryColors)&&Object.keys(input.territoryColors).length<=8,'PRESENTATION_TERRITORY_PALETTE_INVALID');
  const states=new Set(scene.time_steps?.map(x=>x.id)??[]);
  for(const [id,rgba]of Object.entries(input.territoryColors))ok(states.has(id)&&Array.isArray(rgba)&&rgba.length===4&&rgba.every(unit)&&rgba[3]>=.08&&rgba[3]<=.6,'PRESENTATION_STATE_COLOR_BINDING_INVALID');
 }
 const highlights=input.highlights??[];ok(Array.isArray(highlights)&&highlights.length<=16,'PRESENTATION_HIGHLIGHT_CAPACITY');
 const seen=new Set();
 for(const h of highlights){
  keys(h,['id','locationId','startFrame','endFrame'],'PRESENTATION_HIGHLIGHT');
  ok(typeof h.id==='string'&&/^[A-Za-z0-9_.:-]+$/.test(h.id)&&!seen.has(h.id),'PRESENTATION_HIGHLIGHT_ID_INVALID');seen.add(h.id);
  ok(scene.locations?.some(l=>l.id===h.locationId),'PRESENTATION_HIGHLIGHT_LOCATION_REQUIRED');
  ok(frame(h.startFrame,n)&&frame(h.endFrame,n,true)&&h.endFrame-h.startFrame>=2,'PRESENTATION_HIGHLIGHT_TIMING_INVALID');
 }
 result.highlights=copy(highlights);
 const cuts=input.transitions??[];ok(Array.isArray(cuts),'PRESENTATION_TRANSITION_ARRAY_REQUIRED');
 for(const t of cuts){keys(t,['type','frame'],'PRESENTATION_TRANSITION');ok(t.type==='CUT'&&Number.isSafeInteger(t.frame)&&t.frame>=0,'PRESENTATION_CUT_REQUIRED');}
 result.transitions=copy(cuts);return result;
}

export function boundsFromKeyframe(key,closest){
 const s=span(closest).map(v=>v/key.zoom);return[key.center[0]-s[0]/2,key.center[1]-s[1]/2,key.center[0]+s[0]/2,key.center[1]+s[1]/2];
}

/** A genuine fixed V5 frame is a model-time evaluation space, never the moving camera. */
export function compilePresentationCameraPlan({scene,region,nativePlan,baseCameraPlan,presentation}={}){
 const p=validatePresentation(presentation,{scene,region}),n=scene.timing.total_frames,
  base=copy(baseCameraPlan),analysisSourceFrame=base.totalFrames-1,
  analysisCamera=evaluateMinimumContextCameraFrame(base,analysisSourceFrame),closest=nativePlan.framing.bounds;
 ok(analysisCamera.cameraLocked&&analysisCamera.settle.locked,'PRESENTATION_GENUINE_MODEL_CAMERA_REQUIRED');
 const canonical=copy(scene),engine=compileExistingEnginePlan(scene),analysisBounds=analysisCamera.camera.flatBounds,
  analysisProject=point=>projectBounds(analysisBounds,point),safe=nativePlan.layout.safe;
 let keyframes=p.camera.keyframes;
 if(p.camera.mode==='ROUTE_FOLLOW'){
  const binding=engine.plans.find(x=>x.id===p.camera.routeId&&x.engine==='EXISTING_FLOW_V2');
  ok(binding,'PRESENTATION_FOLLOW_ENGINE_REQUIRED');
  const primitive=compileFlowRoute(binding.plan.intent,{project:analysisProject}),c=center(closest),selected=[0,n-1];
  for(const fraction of [.2,.4,.6,.8])selected.push(Math.round((n-1)*fraction));
  keyframes=[...new Set(selected)].sort((a,b)=>a-b).map(f=>{
   const local=Math.max(0,Math.min(binding.plan.totalFrames-1,f-engine.globalEventStartFrame));
   const model=evaluateFlowFrame(binding.plan,binding.plan.startFrame+local,{primitive,eventContext:{cameraState:analysisCamera,project:analysisProject,safeArea:safe,scalePlan:nativePlan,heightSource:null,protectedBoxes:[]}});
   const geographic=unprojectBounds(analysisBounds,model.objectPosition),strength=p.camera.followStrength;
   return{frame:f,center:c.map((v,i)=>v+(geographic[i]-v)*strength),zoom:p.camera.zoom};
  });
 }
 const boundsKeys=keyframes.map(k=>({frame:k.frame,bounds:boundsFromKeyframe(k,closest)}));
 const track=compileReferenceCameraTrack({baseCameraPlan:base,currentNativeFrame:analysisSourceFrame,keyframes:boundsKeys,totalFrames:n,fps:30});
 const samples=Array.from({length:n},(_,f)=>evaluateReferenceCameraTrackFrame(track,f));
 const coverageBounds=[Math.min(...samples.map(s=>s.flatBounds[0])),Math.min(...samples.map(s=>s.flatBounds[1])),Math.max(...samples.map(s=>s.flatBounds[2])),Math.max(...samples.map(s=>s.flatBounds[3]))];
 const aspect=span(samples[0].flatBounds)[0]/span(samples[0].flatBounds)[1];
 for(const sample of samples){
  ok(sample.cameraLocked===false&&sample.settle.locked===false,'PRESENTATION_FAKE_LOCK_REJECTED');
  ok(Math.abs(span(sample.flatBounds)[0]/span(sample.flatBounds)[1]-aspect)<1e-10,'PRESENTATION_NONUNIFORM_PROJECTION_UNSUPPORTED');
  ok(sample.camera.noCloserThanApprovedStop===true,'PRESENTATION_DETAIL_ADMISSION_EXCEEDED');
 }
 ok(same(scene,canonical),'PRESENTATION_SCENE_MUTATION');
 return{schema:PRESENTATION_VERSION,mode:p.camera.mode,track,cpuFrameBounds:samples.map(s=>copy(s.flatBounds)),analysisCamera,analysisSourceFrame,analysisBounds,
  keyframes:copy(keyframes),coverageBounds,closestBounds:copy(closest),sameAspect:true,
  modelTimingOwner:'UNCHANGED_FLOW_V2_AT_GENUINE_FIXED_V5_FRAME',movingCameraOwner:'UNCHANGED_REFERENCE_CAMERA_ADAPTER_V1',
  actualMovingCameraLockForged:false,sourceGeometryMutated:false,presentation:p};
}
export function evaluatePresentationCameraFrame(plan,frame){return evaluateReferenceCameraTrackFrame(plan.track,frame);}

/** The old public Area operations support already visible supplied states.
 * This changes opacity endpoints only, never event time or geographic input. */
export function compilePresentationEnginePlan({scene,presentation}={}){
 const engines=compileExistingEnginePlan(scene),mode=presentation?.initialStateVisibility??'REVEAL';
 ok(['REVEAL','PRESERVE_PROVIDED'].includes(mode),'PRESENTATION_INITIAL_VISIBILITY_UNSUPPORTED');
 if(mode==='REVEAL')return engines;
 ok(scene.event_type==='WAR'&&engines.globalEventStartFrame===0,'PRESENTATION_ALREADY_VISIBLE_AREA_WITHOUT_EVENT_PREFIX_REQUIRED');
 return{...engines,plans:engines.plans.map(binding=>{if(binding.engine!=='EXISTING_AREA_V3')return binding;const plan=binding.plan,operations=plan.operations.map(op=>['AREA_REVEAL','FRONT_LINE'].includes(op.type)?{...copy(op),from:1,to:1}:copy(op));
  return{...binding,plan:compileAreaPlan(plan.intent,{fps:plan.fps,start_frame:plan.startFrame,total_frames:plan.totalFrames,operations}),presentationOperationBinding:{owner:'UNCHANGED_COMPILE_AREA_PLAN_PUBLIC_OPERATIONS',initialStateVisibility:mode,revealEndpoints:[1,1],originalGlobalClockPreserved:true,sourceGeometryChanged:false}};})};
}

function boundarySignature(segment,last){
 const scene=segment.scene,state=last?scene.time_steps.at(-1):scene.time_steps[0];
 ok(state,'PRESENTATION_BOUNDARY_STATE_REQUIRED');
 const source=id=>{const s=scene.source_notes.find(x=>x.id===id);ok(s,'PRESENTATION_BOUNDARY_SOURCE_REQUIRED');return{source_type:s.source_type,source_reference:s.source_reference,verification_status:s.verification_status,license:s.license??null,crs:s.crs??null,originalSHA256:s.original_sha256??s.sha256??null};};
 const geometry=id=>scene.geometries.find(g=>g.id===id)?.geometry;
 const records=(ids,rows)=>ids.map(id=>{const row=rows.find(r=>r.id===id);ok(row,'PRESENTATION_BOUNDARY_GEOMETRY_REQUIRED');return{geometry:copy(geometry(row.geometry_ref)),role:row.role,source:source(row.source_id)};});
 const color=segment.presentation?.territoryColors?.[state.id];ok(color,'PRESENTATION_CONTINUITY_EXPLICIT_STATE_COLOR_REQUIRED');
 return{areas:records(state.area_ids,scene.areas),fronts:records(state.front_line_ids,scene.front_lines),color:copy(color)};
}
export function assertPresentationBoundaryContinuity(previous,next){
 if(next.presentation?.initialStateVisibility!=='PRESERVE_PROVIDED')return{status:'NOT_REQUESTED',continuityClaimed:false};
 ok(previous?.scene?.event_type==='WAR'&&next.scene.event_type==='WAR','PRESENTATION_CONTINUITY_PREVIOUS_AREA_REQUIRED');
 const before=boundarySignature(previous,true),after=boundarySignature(next,false);
 ok(same(before,after),'PRESENTATION_CUT_PROVIDED_STATE_DISCONTINUITY');
 ok(previous.scene.time_steps.at(-1).date<=next.scene.time_steps[0].date,'PRESENTATION_CUT_STATE_TIME_REVERSED');
 return{status:'SOURCE_STATE_CONTINUITY_CONFIRMED',geometryMatched:true,frontMatched:true,colorMatched:true,sourceMatched:true,eventClockOffsetFrames:0};
}

/** Time is evaluated by Flow V2. Only presentation projection is composed here. */
export function reprojectFlowPresentation({modelControls,primitive,flowIntent}={}){
 const look=modelControls.headingLookAheadPixels,object=sampleFlowRoute(primitive,modelControls.objectFraction,{lookAheadPixels:look}),
  directional=sampleFlowRoute(primitive,modelControls.directionalFraction,{lookAheadPixels:look});
 const out={...copy(modelControls),objectPosition:copy(object.position),heading:object.heading,objectHeading:object.heading,
  headingVector:copy(object.headingVector),directionalPosition:copy(directional.position),directionalHeading:directional.heading,
  routeReveal:evaluateGeographicLineReveal(primitive,modelControls.routeFraction),
  departurePulse:{...copy(modelControls.departurePulse),anchor:copy(primitive.screenCoordinates[0]),position:copy(primitive.screenCoordinates[0])},
  arrivalPulse:{...copy(modelControls.arrivalPulse),anchor:copy(primitive.screenCoordinates.at(-1)),position:copy(primitive.screenCoordinates.at(-1))},
  projectionComposition:'EXPLICIT_CURRENT_FACTORY_PROJECTION_OVER_UNCHANGED_MODEL_TIME',movingProjectionAdmissionRequired:true};
 out.pulse=out.arrivalPulse.active?out.arrivalPulse:out.departurePulse;
 // No current EVENT_READY result is manufactured. It remains explicitly the
 // earlier genuine fixed-frame timing/model result for audit only.
 out.eventControls={...copy(modelControls.eventControls),readinessScope:'MODEL_FIXED_V5_ONLY_NOT_CURRENT_MOVING_CAMERA'};
 return out;
}

export function assertMovingProjectionAdmission({primitive,controls,camera,modelCamera,safeArea,sourceBounds,project,sourceGeometry,currentBounds,protectedGraphics=[],flowIntent=null}={}){
 ok(camera.cameraLocked===false&&camera.settle.locked===false,'PRESENTATION_ACTUAL_MOVING_CAMERA_STATE_REQUIRED');
 ok(modelCamera.cameraLocked===true&&modelCamera.settle.locked===true,'PRESENTATION_MODEL_CAMERA_STATE_REQUIRED');
 ok(currentBounds.every((v,i)=>i<2?v>=sourceBounds[i]-1e-8:v<=sourceBounds[i]+1e-8),'PRESENTATION_SOURCE_COVERAGE_FAILED');
 const projected=sourceGeometry.coordinates.map(p=>project(p)),actual=primitive.direction==='REVERSE'?[...projected].reverse():projected;
 ok(same(actual,primitive.screenCoordinates),'PRESENTATION_CURRENT_PROJECTION_BINDING_FAILED');
 ok(primitive.screenCoordinates.every(p=>contains(p,safeArea,36)),'PRESENTATION_ROUTE_FULL_FOOTPRINT_OUTSIDE_SAFE');
 const objectPadding=flowIntent?Math.hypot(flowIntent.object_graphic.width_px,flowIntent.object_graphic.height_px)/2+2:58;
 if(controls.objectVisible)ok(contains(controls.objectPosition,safeArea,objectPadding),'PRESENTATION_OBJECT_FULL_ROI_OUTSIDE_SAFE');
 for(const pulse of [controls.departurePulse,controls.arrivalPulse])if(pulse.active)ok(contains(pulse.anchor,safeArea,pulse.radius+3),'PRESENTATION_PULSE_OUTSIDE_SAFE');
 for(const row of protectedGraphics)ok(Array.isArray(row.box)&&row.box.length===4&&row.box.every(Number.isFinite)&&row.box[0]<row.box[2]&&row.box[1]<row.box[3]&&contains(row.box.slice(0,2),safeArea)&&contains(row.box.slice(2),safeArea),'PRESENTATION_CURRENT_PROTECTED_RESERVATION_INVALID');
 return{status:'MOVING_PROJECTION_READY',oldEventAdmissionClaimed:false,actualCameraLocked:false,actualSettleLocked:false,
  genuineFixedModelCameraUsed:true,currentProjectionBound:true,uniformAspectOnly:true,routeFullFootprintSafe:true,sourceCoverage:true,
  protectedReservations:copy(protectedGraphics),reservationPolicy:'CURRENT_PROJECTION_NATIVE_RASTER_MASK_NO_MODEL_BOX_SUBSTITUTION'};
}
