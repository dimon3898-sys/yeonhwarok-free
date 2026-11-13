/** Geometry-driven choreography in the existing formal presentation compiler. */
import {analyzeTerritoryChanges,boundsOf,screenFraction,multi,areaKm2,geometry} from './territory_delta_v2.mjs';
import {deriveHistoryPresentationV2} from './history_direction_v2.mjs';
import {REFERENCE_RHYTHM_V3} from './history_direction_v3.mjs';
import {compileContinuousTerritory} from './continuous_territory_compile.mjs';
import {CONTINUOUS_PROFILE,continuousTerritoryAt} from './continuous_territory_runtime.mjs';
import {geographicCameraFrame,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {historicalTimeLabel} from '../../web/map_infographic_v1/historical_time_v1.mjs';
export {CONTINUOUS_PROFILE};
const copy=structuredClone,check=(v,c)=>{if(!v)throw Error('CONTINUOUS_DIRECTOR_'+c);};
const ease=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
export function retimeContinuousHistory(input){
 const s=copy(input),n=s.timing.total_frames;
 check(s.event_type==='WAR'&&s.timing.fps===30&&n>=180&&n<=600&&!s.routes?.length&&!s.front_lines?.length&&!s.causal_tracks?.length,'SOURCE_SCOPE');
 const all=copy(s.time_steps),events=Math.min(all.length-1,Math.floor(n/180));check(events>0,'TWO_STATES_REQUIRED');
 s.time_steps=all.slice(0,events+1);const ids=new Set(s.time_steps.flatMap(x=>x.area_ids));s.areas=s.areas.filter(x=>ids.has(x.id));
 s.camera_intent.target_geometry_refs=[...new Set(s.areas.map(x=>x.geometry_ref))];
 const changes=analyzeTerritoryChanges(s).changes,choreography=[];let cursor=0;
 for(let i=0;i<events;i++){
  const budget=Math.floor(n/events)+(i<n%events?1:0),d=changes[i];
  // Reference reading interval is an anchor, not a fixed template. Additional
  // disconnected components get reading time, never invented historical order.
  const significantParts=d.changed.coordinates.filter(p=>areaKm2(geometry([p]))>=d.changedKm2*.01).length;
  const read=Math.min(Math.round(budget*.32),REFERENCE_RHYTHM_V3.readingHoldFrames+Math.min(10,Math.max(0,significantParts-1)));
  const intro=d.ratio<.005?Math.round(budget*.23):Math.round(22+10*Math.sqrt(d.ratio));
  const start=cursor+intro,end=cursor+budget-read;
  choreography.push({fromStateId:s.time_steps[i].id,toStateId:s.time_steps[i+1].id,
   cycleStart:cursor,startFrame:start,endFrame:end,readEnd:cursor+budget,
   cameraStart:cursor,cameraEnd:end-1,holdFrames:read,
   strategy:d.ratio<.005?'QUIET_RESULT':significantParts>3?'MULTI_REGION_CONTEXT':'BOUNDARY_FOLLOW',
   sourcePeriods:[copy(s.time_steps[i].date),copy(s.time_steps[i+1].date)]});cursor+=budget;
 }
 s.time_steps.forEach((step,i)=>{step.start_frame=i?choreography[i-1].startFrame:0;step.transition_frames=i===events?choreography.at(-1).endFrame-step.start_frame:(i?choreography[i].startFrame:choreography[0].startFrame)-step.start_frame;});
 const hold=choreography.at(-1).holdFrames,action=n-hold;
 s.beats=s.time_steps.map((step,i)=>({id:'BEAT_'+String(i+1).padStart(2,'0'),type:i?'STATE_CHANGE':'EVENT_ACTION',start_frame:step.start_frame,end_frame:step.start_frame+step.transition_frames,duration_frames:step.transition_frames,state_id:step.id,geometry_refs:[...s.camera_intent.target_geometry_refs]}));
 s.beats.push({id:'BEAT_'+String(events+2).padStart(2,'0'),type:'HOLD',start_frame:action,end_frame:n,duration_frames:hold,camera_intent:'LOCK',geometry_refs:[...s.camera_intent.target_geometry_refs]});
 s.timing={...s.timing,initial_reveal_frames:s.time_steps[0].transition_frames,state_transition_frames:s.time_steps[1].transition_frames,final_hold_frames:hold,action_frames:action};
 return{scene:s,audit:{profile:CONTINUOUS_PROFILE,choreography,holdFrames:hold,sourceStateCount:all.length,
  omittedStates:all.slice(events+1).map(x=>({id:x.id,date:x.date})),sourceDatesChanged:false,sourceGeometryChanged:false,
  historicalImportanceInferred:false,sourcePeriodDurationsAreNotPlaybackDurations:true,
  reference:copy(REFERENCE_RHYTHM_V3),referenceInterpretation:'Measured reading/camera rhythm reused; continuous territory speed is a new geometric display policy, not measured historical speed.'}};
}
function mixPose(a,b,t){t=ease(t);return{center:[a.center[0]+(b.center[0]-a.center[0])*t,inverseMercatorY(mercatorY(a.center[1])+(mercatorY(b.center[1])-mercatorY(a.center[1]))*t)],scale:Math.exp(Math.log(a.scale)+(Math.log(b.scale)-Math.log(a.scale))*t),rollDegrees:0};}
export function deriveContinuousHistory({scene,admission,timingAudit}){
 const a=analyzeTerritoryChanges(scene),reused=deriveHistoryPresentationV2({scene,admission,analysis:a,timingAudit}),p=copy(reused.presentation),levels=admission.regionEvidence.sourceLevels;
 const shapes=compileContinuousTerritory(a.changes.map((d,i)=>({previous:a.states[i],following:a.states[i+1],frames:timingAudit.choreography[i].endFrame-timingAudit.choreography[i].startFrame,bandWidth:.045})));
 const items=a.changes.map((d,i)=>{const c=timingAudit.choreography[i];return{fromStateId:d.fromStateId,toStateId:d.toStateId,startFrame:c.startFrame,endFrame:c.endFrame,strength:.65,added:d.added,removed:d.removed,continuous:shapes[i]};});
 p.territoryChanges={profile:CONTINUOUS_PROFILE,config:{semanticMode:'GEOMETRIC_VISUAL_INTERPOLATION_NOT_HISTORICAL_ROUTE'},items};
 const frames=Array(scene.timing.total_frames),keys=[];let current=copy(reused.audit.cameraKeys[0].pose);
 for(const [i,c] of timingAudit.choreography.entries()){
  const target=copy(reused.audit.cameraKeys[i+2].pose),context=copy(current);
  // Start closer than V3's half-scale panorama; source coverage is checked.
  if(i===0)for(const r of [.82,.88,.94,1]){const q=copy(context);q.scale*=r;try{selectGeographicTerrain(levels,q,{maximumTextureSize:8192});current=q;break;}catch{}}
  keys.push({frame:c.cycleStart,role:'CONTEXT',pose:copy(current)});
  for(let f=c.cycleStart;f<c.readEnd;f++){
   const ratio=(f-c.cameraStart)/Math.max(1,c.cameraEnd-c.cameraStart),pose=mixPose(current,target,ratio);
   // The moving frontier contributes a restrained framing offset. A source-
   // aware fit and safe viewport check prevent the whole territory disappearing.
   const state=continuousTerritoryAt(p.territoryChanges,f),front=boundsOf(state.boundaryBand);
   if(c.strategy==='BOUNDARY_FOLLOW'&&front&&f<c.endFrame){const envelope=Math.sin(Math.PI*Math.max(0,Math.min(1,ratio)))**2;
    pose.center[0]+=(.5*(front[0]+front[2])-pose.center[0])*.08*envelope;
    pose.center[1]=inverseMercatorY(mercatorY(pose.center[1])+(mercatorY((front[1]+front[3])/2)-mercatorY(pose.center[1]))*.06*envelope);
   }
   let admitted=null;
   for(const t of [1,.75,.5,.25,0]){const candidate=mixPose(target,pose,t),view=geographicCameraFrame(candidate),pts=multi(state.geometry).flat(2);
    if(!pts.every(pt=>{const q=view.project(pt);return q[0]>=72&&q[0]<=1008&&q[1]>=200&&q[1]<=1660;}))continue;
    try{selectGeographicTerrain(levels,candidate,{maximumTextureSize:8192});admitted=candidate;break;}catch{}
   }
   // Preserve the qualified V2 full-result fit if tighter top/bottom text
   // bands cannot be satisfied; labels are separately protected during draw.
   if(!admitted){admitted=target;selectGeographicTerrain(levels,admitted,{maximumTextureSize:8192});}
   frames[f]=copy(admitted);
  }
  keys.push({frame:c.endFrame-1,role:'RESULT',pose:copy(frames[c.endFrame-1])});current=copy(target);
 }
 p.camera={mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames};
 p.territoryColors=Object.fromEntries(scene.time_steps.map(s=>[s.id,[1,.78,.08,.48]]));
 const starts=scene.time_steps.map((s,i)=>i?items[i-1].startFrame+Math.ceil((items[i-1].endFrame-items[i-1].startFrame-1)/2):0);
 p.labels.items=p.labels.items.filter(x=>!['TIMELINE','DISCLOSURE'].includes(x.role));
 p.labels.items.push(...scene.time_steps.map((s,i)=>({id:'HISTORY_YEAR_'+i,role:'TIMELINE',stateId:s.id,text:historicalTimeLabel(s.date),startFrame:starts[i],endFrame:starts[i+1]??frames.length,revealFrames:1,exitFrames:1,priority:100})),
  {id:'HISTORY_DISCLOSURE',role:'DISCLOSURE',text:'중간 움직임: 시각적 보간 / 일부 시기',startFrame:0,endFrame:frames.length,revealFrames:1,exitFrames:1,priority:90});
 const overlap=frames.filter((x,f)=>f>0&&JSON.stringify(x)!==JSON.stringify(frames[f-1])&&items.some(e=>f>e.startFrame&&f<e.endFrame)).length;
 check(overlap>0||a.changes.every(x=>x.ratio<.005),'CAMERA_OVERLAP_REQUIRED');
 return{presentation:p,audit:{profile:CONTINUOUS_PROFILE,timing:timingAudit,cameraKeys:keys,cameraAndTerritoryMotionOverlapFrames:overlap,
  geometryAlgorithm:'SOURCE_CLIPPED_BOUNDARY_DISTANCE_WAVE',newRenderer:false,oldPassReruns:0,sourceGeometryChanged:false,
  changes:a.changes.map((d,i)=>({fromStateId:d.fromStateId,toStateId:d.toStateId,ratio:d.ratio,parts:d.parts,center:d.center,bounds:d.bounds,changedScreenFraction:screenFraction(d.changed,frames[items[i].startFrame]),detachedComponents:shapes[i].detachedAddedComponents,maximumDisplayTravel:shapes[i].maximumDisplayTravel})),
  limitations:['Reference close-map detail remains constrained by qualified source density.','Geometric waves are illustrative, never conquest routes.','Visual equivalence requires actual comparison and user approval.']}};
}
