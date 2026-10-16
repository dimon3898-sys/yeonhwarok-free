/** External Scene clock over immutable Area V3 static-state outputs.
 * The preserved Area compiler caps each plan at1200frames. This adapter never
 * raises that cap, forges an Area plan, quantizes time or changes coordinates.
 * It reuses original one-frame validated state plans and original line-reveal
 * evaluation, applying the same Area quintic state/reveal weights at the full
 * supplied global Scene clock. Geometry/rendering remain existing owners. */
import {compileAreaIntent,compileAreaPlan,evaluateAreaFrame} from '/modules/area_core_v3.mjs';
import {validateScenePlan} from '/modules/planner_scene_v1.mjs';
import {evaluateGeographicLineReveal} from '/modules/event_line_v1.mjs';

export const LONG_AREA_TIMELINE_VERSION='UNIVERSAL_LONG_AREA_TIMELINE_V1';
const clone=value=>structuredClone(value),clamp=value=>Math.max(0,Math.min(1,value)),projectionCaches=new WeakMap();
// Exact expression used by preserved Area V3 operationProgress/stateAt. This
// external timing extension changes no original easing or shader source.
const quintic=value=>value ** 3*(value*(value*6-15)+10);
const progress=(frame,start,duration)=>quintic(clamp((frame-start)/Math.max(1,duration-1)));
const sourceFor=(scene,id)=>{
 const row=scene.source_notes.find(item=>item.id===id);if(!row)throw Error('UNIVERSAL_LONG_AREA_SOURCE_REQUIRED');
 return {source_type:row.source_type,source_reference:row.source_reference,verification_status:row.verification_status};
};
const geometryFor=(scene,id)=>{
 const row=scene.geometries.find(item=>item.id===id);if(!row)throw Error('UNIVERSAL_LONG_AREA_GEOMETRY_REFERENCE_REQUIRED');
 return clone(row.geometry);
};
const renderRecord=(scene,row)=>({id:row.id,geometry:geometryFor(scene,row.geometry_ref),source:sourceFor(scene,row.source_id),
 role:row.role,style_role:row.style_role??'PRIMARY'});
export function compileLongAreaRequest(scene){
 validateScenePlan(scene);
 if(scene.event_type!=='WAR'||!scene.areas?.length||!scene.front_lines?.length||scene.time_steps?.length<2)
  throw Error('UNIVERSAL_LONG_AREA_POLYGON_STATE_TIMELINE_REQUIRED');
 const initialRevealFrames=Math.min(scene.timing.initial_reveal_frames??36,scene.time_steps[0].transition_frames);
 if(!Number.isSafeInteger(initialRevealFrames)||initialRevealFrames<2)throw Error('UNIVERSAL_LONG_TWO_FRAME_INITIAL_REVEAL_REQUIRED');
 const source=sourceFor(scene,scene.areas[0].source_id),origin=clone(scene.camera_intent.anchor),
  states=scene.time_steps.map(step=>{
   const areas=step.area_ids.map(id=>{const row=scene.areas.find(item=>item.id===id);
    if(!row)throw Error('UNIVERSAL_LONG_AREA_STATE_AREA_REQUIRED');return renderRecord(scene,row);}),
    fronts=step.front_line_ids.map(id=>{const row=scene.front_lines.find(item=>item.id===id);
     if(!row)throw Error('UNIVERSAL_LONG_AREA_STATE_FRONT_REQUIRED');return renderRecord(scene,row);}),
    state={state_id:step.id,time_label:step.date,areas,fronts},
    intent=compileAreaIntent({data_mode:scene.metadata.data_mode,origin,source,
     semantic_mode:scene.metadata.semantic_mode,states:[state]}),
    staticPlan=compileAreaPlan(intent,{fps:scene.timing.fps,total_frames:1,
     operations:[{type:'AREA_HOLD',start_frame:0,duration_frames:1}]});
   return Object.freeze({stateId:step.id,date:step.date,globalStartFrame:step.start_frame,
    transitionFrames:step.transition_frames,staticPlan});
  }),timelinePlan=Object.freeze({version:LONG_AREA_TIMELINE_VERSION,totalFrames:scene.timing.total_frames,fps:scene.timing.fps,
   eventStartFrame:scene.timing.event_start_frame,finalHoldStartFrame:scene.timing.total_frames-scene.timing.final_hold_frames,
   initialRevealFrames,
   states:Object.freeze(states),sourceGeometryBinding:JSON.stringify(scene.geometries),
   dataMode:scene.metadata.data_mode,origin:Object.freeze(origin),semanticMode:scene.metadata.semantic_mode,
   ownership:Object.freeze({clock:'EXPLICIT_LONG_SCENE_GLOBAL_FRAME_EXTENSION',geometry:'UNCHANGED_AREA_V3_VALIDATED_STATIC_STATES',
    projection:'UNCHANGED_NATIVE_FACTORY',line:'UNCHANGED_V1_REVEAL_EVALUATOR',renderer:'UNCHANGED_AREA_V3_GPU_OVERLAY',
    existingAreaFrameCapChanged:false,forgedAreaPlan:false,timeQuantization:false,newCoordinates:false})});
 return {version:LONG_AREA_TIMELINE_VERSION,timelinePlan,dataMode:scene.metadata.data_mode,origin,
  timing:{fps:scene.timing.fps,totalFrames:scene.timing.total_frames,eventStartFrame:scene.timing.event_start_frame},
  annotations:scene.time_steps.map(step=>({id:step.id,display_value:step.date.replaceAll('-','.'),unit:step.label,
   source,anchor:clone(origin)})),sourceGeometryBinding:JSON.stringify(scene.geometries)};
}
export function evaluateLongAreaFrame(plan,globalFrame,{project,projectionKey}={}){
 if(plan?.version!==LONG_AREA_TIMELINE_VERSION||!Number.isSafeInteger(globalFrame)
  ||globalFrame<plan.eventStartFrame||globalFrame>=plan.totalFrames)
  throw Error('UNIVERSAL_LONG_AREA_GLOBAL_FRAME_REQUIRED');
 let index=0;for(let i=1;i<plan.states.length;i++)if(globalFrame>=plan.states[i].globalStartFrame)index=i;else break;
 let cache=null;
 if(projectionKey!==undefined){
  if(typeof project!=='function'||typeof projectionKey!=='string'||!projectionKey||projectionKey.length>512)
   throw Error('UNIVERSAL_LONG_ACTUAL_PROJECTION_KEY_REQUIRED');
  cache=projectionCaches.get(plan);
  if(!cache||cache.project!==project||cache.projectionKey!==projectionKey){cache={project,projectionKey,states:new Map()};projectionCaches.set(plan,cache);}
 }
 const target=plan.states[index],stateProgress=index===0?0:progress(globalFrame,target.globalStartFrame,target.transitionFrames),
  weights=index===0?[{entry:target,alpha:1}]:[{entry:plan.states[index-1],alpha:1-stateProgress},{entry:target,alpha:stateProgress}],
  reveal=progress(globalFrame,plan.eventStartFrame,plan.initialRevealFrames),areas=[],fronts=[];
 let prototype;
 for(const {entry,alpha}of weights){
  if(alpha<=0)continue;let base=cache?.states.get(entry.stateId);
  if(!base){base=evaluateAreaFrame(entry.staticPlan,0,{project});cache?.states.set(entry.stateId,base);}prototype??=base;
  for(const item of base.areas)areas.push({...item,alpha:item.alpha*alpha*reveal});
  for(const item of base.fronts)fronts.push({...item,alpha:item.alpha*alpha,revealFraction:reveal,
   lineReveal:item.linePrimitive?evaluateGeographicLineReveal(item.linePrimitive,reveal):null});
 }
 const chosen=index===0||stateProgress>=.5?target:plan.states[index-1],hold=globalFrame>=plan.finalHoldStartFrame;
 return {...prototype,version:'UNIVERSAL_LONG_AREA_FRAME_V1',reusedStaticControlVersion:prototype.version,
  frame:globalFrame,localFrame:globalFrame-plan.eventStartFrame,timeSeconds:globalFrame/plan.fps,
  state:hold?'AREA_HOLD':index===0?'AREA_REVEAL+FRONT_LINE':'STATE_TRANSITION',stateFrame:globalFrame-target.globalStartFrame,
  stateProgress:index===0?reveal:stateProgress,stateId:chosen.stateId,timeLabel:chosen.date,
  areas,fronts,hold,activeFeatures:hold?['AREA_HOLD']:index===0?['AREA_REVEAL','FRONT_LINE']:['STATE_TRANSITION'],
  geometryBinding:plan.sourceGeometryBinding,longTimelineOwner:plan.ownership,
  originalAreaFrameCapPreserved:true,globalClockContinuous:true,
  projectionCache:{enabled:cache!==null,projectionKey:projectionKey??null,projectionHistoryLimit:1,staticStatesCached:cache?.states.size??0}};
}
