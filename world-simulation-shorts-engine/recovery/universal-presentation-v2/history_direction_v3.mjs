/** Reference-informed timing for supplied territory snapshots. No country/date branches. */
import {analyzeTerritoryChanges,boundsOf,multi,screenFraction} from './territory_delta_v2.mjs';
import {deriveHistoryPresentationV2} from './history_direction_v2.mjs';
import {geographicCameraFrame,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {historicalTimeLabel} from '../../web/map_infographic_v1/historical_time_v1.mjs';
export const HISTORY_DIRECTION_V3='HISTORICAL_STATES_V3';
export const REFERENCE_RHYTHM_V3=Object.freeze({fps:30,cameraMoveFrames:108,regionBlendFrames:25,readingHoldFrames:47,referenceSHA256:'853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc',evidence:'production/auto-director-v3-20261114/reference/TIMING_ANALYSIS.json'});
const check=(v,c)=>{if(!v)throw Error('HISTORY_V3_'+c);},copy=structuredClone,smooth=t=>t*t*t*(10+t*(-15+6*t));
export function retimeHistorySceneV3(input){
 const s=copy(input),n=s.timing.total_frames,r=REFERENCE_RHYTHM_V3,cycle=r.cameraMoveFrames+r.regionBlendFrames+r.readingHoldFrames;
 check(s.event_type==='WAR'&&s.timing.fps===30&&n>=cycle&&n<=600&&s.timing.event_start_frame===0&&!s.routes?.length&&!s.front_lines?.length&&!s.causal_tracks?.length,'TERRITORY_ONLY_6_TO_20_SECONDS');
 const all=copy(s.time_steps),events=Math.min(all.length-1,Math.floor(n/cycle));check(events>=1,'ADJACENT_STATES_REQUIRED');
 // A short sample is an explicitly disclosed chronological excerpt, not a fake accelerated full history.
 s.time_steps=all.slice(0,events+1);const ids=new Set(s.time_steps.flatMap(x=>x.area_ids));s.areas=s.areas.filter(x=>ids.has(x.id));
 s.camera_intent.target_geometry_refs=[...new Set(s.areas.map(x=>x.geometry_ref))];
 const extra=n-events*cycle,quiet=Array.from({length:events},(_,i)=>r.readingHoldFrames+Math.floor(extra/events)+(i<extra%events?1:0));
 const choreography=[];let cursor=0;
 for(let i=0;i<events;i++){
  const moveStart=cursor,moveEnd=cursor+r.cameraMoveFrames,blendStart=moveEnd,blendEnd=blendStart+r.regionBlendFrames,readEnd=blendEnd+quiet[i];
  choreography.push({fromStateId:s.time_steps[i].id,toStateId:s.time_steps[i+1].id,moveStart,moveEnd,blendStart,blendEnd,readEnd});cursor=readEnd;
 }
 check(cursor===n,'EXACT_BUDGET');
 s.time_steps.forEach((step,i)=>{step.start_frame=i?choreography[i-1].blendStart:0;step.transition_frames=i===events?r.regionBlendFrames:(i?choreography[i].blendStart-step.start_frame:r.cameraMoveFrames);});
 const hold=quiet.at(-1),action=n-hold;
 s.beats=s.time_steps.map((step,i)=>({id:'BEAT_'+String(i+1).padStart(2,'0'),type:i?'STATE_CHANGE':'EVENT_ACTION',start_frame:step.start_frame,end_frame:step.start_frame+step.transition_frames,duration_frames:step.transition_frames,state_id:step.id,geometry_refs:[...s.camera_intent.target_geometry_refs]}));
 s.beats.push({id:'BEAT_'+String(events+2).padStart(2,'0'),type:'HOLD',start_frame:action,end_frame:n,duration_frames:hold,camera_intent:'LOCK',geometry_refs:[...s.camera_intent.target_geometry_refs]});
 s.timing={...s.timing,initial_reveal_frames:r.cameraMoveFrames,state_transition_frames:s.time_steps[1].transition_frames,final_hold_frames:hold,action_frames:action};
 return{scene:s,audit:{profile:HISTORY_DIRECTION_V3,reference:copy(r),selection:'CHRONOLOGICAL_ADJACENT_PREFIX_EXCERPT',sourceStateCount:all.length,selectedStateIds:s.time_steps.map(x=>x.id),omittedStates:all.slice(events+1).map(x=>({id:x.id,date:copy(x.date)})),selectedPeriods:s.time_steps.map(x=>copy(x.date)),sourceDatesChanged:false,sourceGeometryChanged:false,historicalImportanceInferred:false,choreography,holdFrames:hold,cameraAndTerritoryMotionOverlapFrames:0,policyValuesAre:'reference-annotated durations; sequential choreography and exact lock are design adaptations'}};
}
function cameraPath(a,b,count){
 return Array.from({length:count},(_,f)=>{if(f===0)return copy(a);if(f===count-1)return copy(b);const t=smooth(f/(count-1)),mix=(x,y)=>x+(y-x)*t;return{center:[mix(a.center[0],b.center[0]),inverseMercatorY(mix(mercatorY(a.center[1]),mercatorY(b.center[1])))],scale:Math.exp(mix(Math.log(a.scale),Math.log(b.scale))),rollDegrees:mix(a.rollDegrees,b.rollDegrees)};});
}
export function deriveHistoryPresentationV3({scene,admission,timingAudit}){
 check(timingAudit?.profile===HISTORY_DIRECTION_V3,'TIMING_AUDIT_REQUIRED');
 const analysis=analyzeTerritoryChanges(scene),levels=admission.regionEvidence?.sourceLevels;check(levels?.length,'QUALIFIED_TERRAIN_REQUIRED');
 // Reuse V2's source-aware fits, original projection and Area/label presentation.
 const reused=deriveHistoryPresentationV2({scene,admission,analysis,timingAudit});
 const p=copy(reused.presentation),n=scene.timing.total_frames,frames=Array(n),keys=[];let current=copy(reused.audit.cameraKeys[0].pose);
 // Start in geographic context then gently approach. Source qualification bounds zoom, never raster enlargement.
 const context=copy(current);context.scale*=.78;
 try{selectGeographicTerrain(levels,context,{maximumTextureSize:8192});current=context;}catch{/* exact qualified V2 pose remains authoritative */}
 for(const [i,c]of timingAudit.choreography.entries()){
  // Last key is a full result overview; intermediate keys follow the actual difference region.
  const target=copy(reused.audit.cameraKeys[i+2].pose),movement=cameraPath(current,target,c.moveEnd-c.moveStart);
  for(let f=c.moveStart;f<c.moveEnd;f++)frames[f]=movement[f-c.moveStart];
  for(let f=c.moveEnd;f<c.readEnd;f++)frames[f]=copy(target);
  keys.push({frame:c.moveStart,role:'CONTEXT',pose:copy(current)},{frame:c.moveEnd-1,role:i===timingAudit.choreography.length-1?'RESULT':'CHANGE_FOCUS',stateId:c.toStateId,pose:copy(target)});current=target;
 }
 const sourceAdmissions=frames.map(x=>selectGeographicTerrain(levels,x,{maximumTextureSize:8192}));
 const lastView=geographicCameraFrame(frames.at(-1));for(const pt of multi(analysis.states.at(-1)).flat(2)){const q=lastView.project(pt);check(q[0]>=64&&q[0]<=1016&&q[1]>=64&&q[1]<=1856,'RESULT_CLIPPED');}
 const effects=analysis.changes.map((d,i)=>{
  const c=timingAudit.choreography[i],fraction=screenFraction(d.changed,frames[c.blendStart]);
  return{fromStateId:d.fromStateId,toStateId:d.toStateId,startFrame:c.blendStart,endFrame:c.blendEnd,strength:d.ratio<.015||fraction<.001?0:Math.min(.9,.42+.65*Math.sqrt(fraction)),added:d.added,removed:d.removed};
 });
 p.camera={mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames};
 p.territoryChanges={profile:HISTORY_DIRECTION_V3,config:{...REFERENCE_RHYTHM_V3},items:effects};
 p.territoryColors=Object.fromEntries(scene.time_steps.map(s=>[s.id,[1,.78,.08,.56]]));
 const starts=scene.time_steps.map((s,i)=>i?timingAudit.choreography[i-1].blendStart+Math.ceil((REFERENCE_RHYTHM_V3.regionBlendFrames-1)/2):0);
 p.labels.items=p.labels.items.filter(x=>x.role!=='TIMELINE');
 p.labels.items.push(...scene.time_steps.map((s,i)=>({id:'HISTORY_YEAR_'+i,role:'TIMELINE',stateId:s.id,text:historicalTimeLabel(s.date),startFrame:starts[i],endFrame:starts[i+1]??n,revealFrames:1,exitFrames:1,priority:100})));
 const disclosure=p.labels.items.find(x=>x.role==='DISCLOSURE');if(disclosure&&timingAudit.omittedStates.length)disclosure.text='역사 경계 재구성 / 일부 시기';
 return{presentation:p,audit:{profile:HISTORY_DIRECTION_V3,timing:timingAudit,cameraKeys:keys,reference:copy(REFERENCE_RHYTHM_V3),sourceLevelIndices:[...new Set(sourceAdmissions.map(a=>a.index))],sourceGeometryChanged:false,newRenderer:false,oldPassReruns:0,changes:analysis.changes.map((d,i)=>({fromStateId:d.fromStateId,toStateId:d.toStateId,changedKm2:d.changedKm2,ratio:d.ratio,changedScreenFraction:screenFraction(d.changed,frames[effects[i].startFrame]),effectStrength:effects[i].strength})),omitted:['UNSOURCED_ROUTES','BATTLES','PROPAGATION_WAVES'],limitations:['Short clips explicitly display a chronological excerpt.','Source-native density can constrain northward centering and geographic detail.','Reference rhythm does not by itself establish visual parity.'],manualPresentationFields:[]}};
}
