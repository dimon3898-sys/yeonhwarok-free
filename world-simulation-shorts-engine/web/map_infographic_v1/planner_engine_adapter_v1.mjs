/** Scene data selects existing engines. No story interpretation, camera math or new renderer. */
import {compileAreaIntent,compileAreaPlan} from './area_core_v3.mjs';
import {compileFlowIntent,compileFlowPlan} from './flow_core_v2.mjs';
import {compileEventIntent} from './event_contract_v1.mjs';
import {compileEventPlan} from './event_timeline_v1.mjs';
import {compileWaveVisualPlan} from './wave_visual_v3.mjs';
import {validateScenePlan,PlannerDataRequiredError} from './planner_scene_v1.mjs';

export const PLANNER_ENGINE_ADAPTER_V1_VERSION='PLANNER_ENGINE_ADAPTER_V1';
const copy=value=>structuredClone(value);
const unique=value=>[...new Set(value)];

function sourceFor(scene,id){
 const source=scene.source_notes.find(row=>row.id===id);
 if(!source)throw Error('PLANNER_ENGINE_SOURCE_REFERENCE_REQUIRED_'+id);
 return {source_type:source.source_type,source_reference:source.source_reference,
  verification_status:source.verification_status};
}
function geometryFor(scene,id){
 const record=scene.geometries.find(row=>row.id===id);
 if(!record)throw Error('PLANNER_ENGINE_GEOMETRY_REFERENCE_REQUIRED_'+id);
 return copy(record.geometry);
}
function recordFor(scene,row){
 return {id:row.id,geometry:geometryFor(scene,row.geometry_ref),source:sourceFor(scene,row.source_id),
  role:row.role,style_role:row.style_role??'PRIMARY'};
}

/** Translate supplied states and beat frames to the frozen Area V3 contract. */
export function compileSceneEngineRequest(scene){
 validateScenePlan(scene);
 if(!scene||!Array.isArray(scene.geometries)||!Array.isArray(scene.source_notes)||!scene.timing
  ||!scene.camera_intent||!Array.isArray(scene.time_steps)||!scene.time_steps.length)
  throw Error('PLANNER_EXISTING_AREA_SCENE_CONTRACT_REQUIRED');
 const origin=copy(scene.camera_intent.anchor),eventStart=scene.timing.event_start_frame;
 const totalFrames=scene.timing.total_frames-eventStart;
 if(!Number.isSafeInteger(eventStart)||!Number.isSafeInteger(totalFrames)||totalFrames<=0)
  throw Error('PLANNER_ENGINE_EXPLICIT_EVENT_TIMING_REQUIRED');
 const areas=scene.areas??[],fronts=scene.front_lines??[];
 const states=scene.time_steps.map(step=>({state_id:step.id,time_label:step.date,
  areas:step.area_ids.map(id=>{const row=areas.find(value=>value.id===id);if(!row)throw Error('PLANNER_AREA_ID_REQUIRED');return recordFor(scene,row);}),
  fronts:step.front_line_ids.map(id=>{const row=fronts.find(value=>value.id===id);if(!row)throw Error('PLANNER_FRONT_ID_REQUIRED');return recordFor(scene,row);})}));
 const sourceId=areas[0]?.source_id??fronts[0]?.source_id;
 const intent=compileAreaIntent({data_mode:scene.metadata.data_mode,origin,source:sourceFor(scene,sourceId),
  semantic_mode:scene.metadata.semantic_mode,states});
 const operations=[];
 const revealFrames=Math.min(scene.timing.initial_reveal_frames??36,scene.time_steps[0].transition_frames);
 for(const id of unique(areas.map(row=>row.id)))operations.push({type:'AREA_REVEAL',target_id:id,start_frame:0,duration_frames:revealFrames});
 for(const id of unique(fronts.map(row=>row.id)))operations.push({type:'FRONT_LINE',target_id:id,start_frame:0,duration_frames:revealFrames});
 for(let index=1;index<scene.time_steps.length;index++){
  const step=scene.time_steps[index],start=step.start_frame-eventStart;
  operations.push({type:'STATE_TRANSITION',state_ids:[scene.time_steps[index-1].id,step.id],
   start_frame:start,duration_frames:step.transition_frames});
 }
 const holdFrames=scene.timing.final_hold_frames??36;
 operations.push({type:'AREA_HOLD',start_frame:totalFrames-holdFrames,duration_frames:holdFrames});
 const areaPlan=compileAreaPlan(intent,{fps:scene.timing.fps,total_frames:totalFrames,operations});
 const annotations=scene.time_steps.map(step=>({id:step.id,display_value:step.date.replaceAll('-','.'),
  unit:step.label,source:sourceFor(scene,sourceId),anchor:copy(origin)}));
 return {version:PLANNER_ENGINE_ADAPTER_V1_VERSION,areaPlan,annotations,
  timing:{fps:scene.timing.fps,totalFrames:scene.timing.total_frames,eventStartFrame:eventStart},
  cameraRequest:{owner:scene.camera_intent.owner,anchor:copy(origin),
   targetGeometries:scene.camera_intent.target_geometry_refs.map(id=>geometryFor(scene,id)),
   contextGeometries:(scene.camera_intent.minimum_context_geometry_refs??[]).map(id=>geometryFor(scene,id)),
   detailPolicy:scene.camera_intent.detail_policy,scale:scene.scale_intent.preferred,
   nativeContext:copy(scene.camera_intent.native_context??{})},
  ownership:{area:'UNCHANGED_AREA_CORE_V3',timeline:'UNCHANGED_AREA_STATE_TIMELINE_V3',
   line:'UNCHANGED_V1_ARC_LENGTH',camera:'UNCHANGED_CAMERA_DIRECTOR_V5',projection:'UNCHANGED_NATIVE_FACTORY',
   annotation:'UNCHANGED_AREA_ANNOTATION_V3',renderer:'UNCHANGED_AREA_GPU_ADAPTER_V3',
   naturalLanguageInterpretation:false,physicalSimulation:false},
  sourceGeometryBinding:JSON.stringify(scene.geometries)};
}

/** Portable bindings for every V1 planning family. GPU proof is deliberately an Area scene. */
export function compileExistingEnginePlan(scene){
 validateScenePlan(scene);
 const mode=scene.metadata.data_mode,eventFrames=scene.timing.total_frames-scene.timing.event_start_frame,
  actionFrames=scene.timing.action_frames,holdFrames=scene.timing.final_hold_frames,plans=[];
 const routes=scene.routes??[];
 for(const route of routes){
  const object=scene.moving_objects.find(row=>row.route_id===route.id),geometry=geometryFor(scene,route.geometry_ref);
  if(!object?.graphic)throw new PlannerDataRequiredError('supplied moving-object graphic for existing Flow renderer');
  const points=geometry.coordinates,reverse=route.direction==='REVERSE';
  const flow=compileFlowIntent({data_mode:mode,route_geometry:geometry,route_source:sourceFor(scene,route.source_id),
   direction:route.direction,start_anchor:copy(reverse?points.at(-1):points[0]),end_anchor:copy(reverse?points[0]:points.at(-1)),
   object_role:object.role,object_graphic:copy(object.graphic)});
  const available=scene.event_type==='TRANSPORT'?actionFrames:eventFrames-holdFrames;
  const objectStart=Math.max(3,Math.round(available*.12)),arrivalPulse=Math.max(8,Math.round(available*.12));
  const timing={fps:scene.timing.fps,start_frame:0,reveal_frames:Math.max(2,Math.round(available*.32)),
   direction_start_frame:Math.max(1,Math.floor(objectStart/2)),object_start_frame:objectStart,
   travel_frames:available-objectStart-arrivalPulse,departure_pulse_frames:Math.min(12,available-objectStart-arrivalPulse),
   arrival_pulse_frames:arrivalPulse,hold_frames:holdFrames};
  plans.push({id:route.id,engine:'EXISTING_FLOW_V2',plan:compileFlowPlan(flow,timing),objectProfile:object.profile});
 }
 if(scene.event_type==='WAR')plans.push({id:'AREA_STATE_TIMELINE',engine:'EXISTING_AREA_V3',plan:compileSceneEngineRequest(scene).areaPlan});
 if(scene.event_type==='LINE_METRIC'){
  const lines=scene.geographic_lines,metrics=scene.metrics;
  for(let index=0;index<Math.max(lines.length,metrics.length);index++){
   const line=lines[index],metric=metrics[index],geometry=line?geometryFor(scene,line.geometry_ref):null;
   const geometrySource=line?scene.geometries.find(row=>row.id===line.geometry_ref).source_id:null;
   const intent=compileEventIntent({data_mode:mode,
    line:line?{geometry,source:sourceFor(scene,geometrySource),direction:line.direction,style_role:line.style_role}:null,
    metric:metric?{display_value:metric.display_value,unit:metric.unit,anchor:copy(metric.anchor),source:sourceFor(scene,metric.source_id)}:null});
   const reveal=line?Math.max(2,Math.round(actionFrames*.55)):0,lineHold=line?Math.round(actionFrames*.12):0;
   const metricReveal=metric?Math.max(2,actionFrames-1-reveal-lineHold):2;
   const profile={ready_frames:1,line_reveal_frames:Math.max(2,reveal),line_hold_frames:lineHold,
    metric_reveal_frames:metricReveal,information_hold_frames:holdFrames+(metric?0:actionFrames-1-reveal-lineHold)};
   plans.push({id:line?.id??metric.id,engine:'EXISTING_EVENT_V1',plan:compileEventPlan(intent,{fps:scene.timing.fps,profile})});
  }
 }
 if(scene.event_type==='DISASTER'){
  const impacts=scene.impact_zones.map(row=>{const geo=scene.geometries.find(value=>value.id===row.geometry_ref);
   return {id:row.id,geometry:copy(geo.geometry),source:sourceFor(scene,geo.source_id),role:'IMPACT_ZONE',style_role:'IMPACT'};});
  const radial=[],waves=[];
  for(const item of scene.propagations){
   if(item.radius_end_degrees!==undefined)radial.push({...copy(item),source:sourceFor(scene,item.source_id)});
   else{
    const coastGeometry=geometryFor(scene,item.geometry_ref);
    if(coastGeometry.coordinates.length<3)throw new PlannerDataRequiredError('open target coast needs at least three supplied vertices');
    const stagger=Math.max(8,Math.round(actionFrames*.12)),fade=24,start=0;
    const plan=compileWaveVisualPlan({origin:item.origin,coastGeometry,source:sourceFor(scene,item.source_id),data_mode:mode,
     fps:scene.timing.fps,total_frames:eventFrames,start_frame:start,travel_frames:Math.max(30,actionFrames-2*stagger-fade),
     stagger_frames:stagger,wave_count:3,fade_frames:fade,contact_frames:20,pulse_frames:24});
    waves.push({id:item.id,engine:'EXISTING_IRREGULAR_WAVE_VISUAL_V3',plan});
   }
  }
  const sourceId=scene.propagations[0].source_id;
  const intent=compileAreaIntent({data_mode:mode,origin:scene.camera_intent.anchor,source:sourceFor(scene,sourceId),
   semantic_mode:scene.metadata.semantic_mode,propagations:radial,impacts});
  const operations=radial.map(row=>({type:'PROPAGATION_WAVE',target_id:row.id,start_frame:0,duration_frames:actionFrames}));
  for(const row of impacts)operations.push({type:'IMPACT_ZONE',target_id:row.id,
   start_frame:Math.max(0,actionFrames-30),duration_frames:30});
  operations.push({type:'AREA_HOLD',start_frame:actionFrames,duration_frames:holdFrames});
  plans.push({id:'PROPAGATION_IMPACT_TIMELINE',engine:'EXISTING_AREA_V3',
   plan:compileAreaPlan(intent,{fps:scene.timing.fps,total_frames:eventFrames,operations})},...waves);
 }
 if(!plans.length)throw Error('PLANNER_EXISTING_ENGINE_BINDING_REQUIRED');
 return {version:PLANNER_ENGINE_ADAPTER_V1_VERSION,family:scene.event_type,plans,
  globalEventStartFrame:scene.timing.event_start_frame,totalFrames:scene.timing.total_frames,
  projectionOwner:'EXISTING_NATIVE_FACTORY',cameraOwner:'UNCHANGED_CAMERA_DIRECTOR_V5',
  rendererScope:'ACTUAL_PROOF_AREA_V3_NATIVE_GPU_OTHER_PLANS_USE_EXISTING_ENGINE_CONTRACTS',
  sourceGeometryBinding:JSON.stringify(scene.geometries),newEngine:false,newRenderer:false,physicalSimulation:false};
}
