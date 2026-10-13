/** Optional scene orchestration; frozen Flow/Area/Camera engines keep their ownership. */
import {validateScenePlan} from './planner_scene_v1.mjs';
import {compileSceneEngineRequest} from './planner_engine_adapter_v1.mjs';
import {compileAreaPlan} from './area_core_v3.mjs';
import {compileFlowIntent,compileFlowPlan} from './flow_core_v2.mjs';
import {compileFlowVisualProfile} from './flow_visual_profile_v2.mjs';
import {freezeEventData} from './event_contract_v1.mjs';

export const PLANNER_CAUSAL_ADAPTER_V1_VERSION='PLANNER_CAUSAL_ADAPTER_V1';
const copy=value=>structuredClone(value);
function sourceFor(scene,id){
 const source=scene.source_notes.find(item=>item.id===id);
 if(!source)throw Error('PLANNER_CAUSAL_SOURCE_REQUIRED');
 return {source_type:source.source_type,source_reference:source.source_reference,
  verification_status:source.verification_status};
}

/** Reuses the stock state snapshots; only operation schedules are changed by supplied intent. */
export function compileCausalEnginePlan(scene){
 validateScenePlan(scene);
 const base=compileSceneEngineRequest(scene),tracks=scene.causal_tracks??[];
 const operations=base.areaPlan.operations.map(copy);
 for(const track of tracks){
  const index=operations.findIndex(item=>item.type==='STATE_TRANSITION'
   &&item.state_ids[0]===track.from_state_id&&item.state_ids[1]===track.to_state_id);
  if(index<0)throw Error('PLANNER_CAUSAL_EXISTING_STATE_OPERATION_REQUIRED');
  operations[index]={...operations[index],start_frame:track.control_start_frame-scene.timing.event_start_frame,
   duration_frames:track.control_end_frame-track.control_start_frame};
 }
 const areaPlan=tracks.length?compileAreaPlan(base.areaPlan.intent,{fps:base.areaPlan.fps,
  start_frame:base.areaPlan.startFrame,total_frames:base.areaPlan.totalFrames,operations}):base.areaPlan;
 const flowTracks=tracks.filter(track=>track.route_id!==undefined).map(track=>{
  const route=scene.routes.find(item=>item.id===track.route_id),object=scene.moving_objects.find(item=>item.id===track.object_id);
  const record=scene.geometries.find(item=>item.id===route.geometry_ref),geometry=copy(record.geometry);
  if(!object.graphic)throw Error('PLANNER_CAUSAL_SUPPLIED_ACTOR_GRAPHIC_REQUIRED');
  const reverse=route.direction==='REVERSE',points=geometry.coordinates;
  const intent=compileFlowIntent({data_mode:scene.metadata.data_mode,route_geometry:geometry,
   route_source:sourceFor(scene,route.source_id),direction:route.direction,
   start_anchor:copy(reverse?points.at(-1):points[0]),end_anchor:copy(reverse?points[0]:points.at(-1)),
   object_role:object.role,object_graphic:copy(object.graphic)});
  const available=track.contact_frame-track.motion_start_frame;
  const objectStart=Math.min(6,available-2),arrival=track.contact_kind==='NONE'?0:track.control_start_frame-track.contact_frame;
  if(objectStart<1||arrival===1)throw Error('PLANNER_CAUSAL_FLOW_PERCEPTION_WINDOW_REQUIRED');
  const holdFrames=track.end_frame-track.contact_frame-arrival;
  if(holdFrames<1)throw Error('PLANNER_CAUSAL_PHASE_HOLD_REQUIRED');
  const plan=compileFlowPlan(intent,{fps:scene.timing.fps,start_frame:track.motion_start_frame,
   reveal_frames:Math.max(2,Math.min(18,available-1)),direction_start_frame:Math.max(1,Math.floor(objectStart/2)),
   object_start_frame:objectStart,travel_frames:available-objectStart,
   departure_pulse_frames:Math.min(12,available-objectStart),arrival_pulse_frames:arrival,hold_frames:holdFrames});
  if(plan.arrivalFrame!==track.contact_frame||plan.endFrame!==track.end_frame)
   throw Error('PLANNER_CAUSAL_FLOW_CONTACT_CLOCK_BINDING_REQUIRED');
  return {id:track.id,track:copy(track),plan,fadeInFrames:6,fadeOutFrames:10,
   visualProfile:compileFlowVisualProfile({profileName:'COMMON_DIRECTIONAL_ACTOR',roleGroup:'GENERIC',objectScale:1,
    routeLeadPixels:36,directionalLeadBodyRatio:.6,arrivalRadiusScale:1.05,arrivalPeakProgress:.22})};
 });
 return freezeEventData({version:PLANNER_CAUSAL_ADAPTER_V1_VERSION,areaPlan,flowTracks,causalTracks:copy(tracks),
  annotations:copy(base.annotations),totalFrames:scene.timing.total_frames,fps:scene.timing.fps,
  eventStartFrame:scene.timing.event_start_frame,sourceGeometryBinding:JSON.stringify(scene.geometries),
  sourceStateGeometryBinding:JSON.stringify(base.areaPlan.intent.states),
  ownership:{camera:'UNCHANGED_CAMERA_DIRECTOR_V5',projection:'ACTUAL_EXISTING_NATIVE_FACTORY',
   area:'UNCHANGED_AREA_CORE_V3',flow:'UNCHANGED_FLOW_CORE_V2',route:'UNCHANGED_V1_ARC_LENGTH',
   graphic:'SUPPLIED_GENERIC_FIXTURE_VECTOR',contact:'EXISTING_SINGLE_ENDPOINT_PULSE',
   stateChange:'EXISTING_SNAPSHOT_CROSSFADE',physics:false,historicalUnitReconstruction:false,
   newWarEngine:false,newRenderer:false}});
}

export function evaluateCausalSchedule(plan,frame){
 if(plan?.version!==PLANNER_CAUSAL_ADAPTER_V1_VERSION||!Number.isSafeInteger(frame)||frame<0||frame>=plan.totalFrames)
  throw Error('PLANNER_CAUSAL_SCHEDULE_FRAME_REQUIRED');
 return plan.causalTracks.map(track=>({id:track.id,fromStateId:track.from_state_id,toStateId:track.to_state_id,
  actionKind:track.action_kind,contactKind:track.contact_kind,representsHistoricalUnit:false,
  phase:frame<track.motion_start_frame?'PENDING':frame<track.contact_frame?'ACTION'
   :frame<track.control_start_frame?'CONTACT':frame<track.control_end_frame?'CONTROL_CHANGE'
    :frame<track.end_frame?'AFTERMATH':'COMPLETE',
  active:frame>=track.motion_start_frame&&frame<track.end_frame,
  contactCueAllowed:track.contact_kind!=='NONE'&&frame>=track.contact_frame&&frame<track.control_start_frame}));
}
