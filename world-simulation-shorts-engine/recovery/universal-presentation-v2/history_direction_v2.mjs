/** Opt-in territory-scale direction; all decisions are geometric display choices. */
import {analyzeTerritoryChanges,boundsOf,screenFraction,multi,areaKm2,geometry} from './territory_delta_v2.mjs';
import {fitGeographicPose,geographicCameraFrame,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {historicalTimeLabel} from '../../web/map_infographic_v1/historical_time_v1.mjs';
export const HISTORY_DIRECTION_V2='HISTORICAL_STATES_V2';
export const DEFAULT_DIRECTOR_CONFIG=Object.freeze({smallChangeRatio:.015,minimumStateSeconds:.4,finalHoldFraction:.18,maximumFocusZoomRatio:2.1,effectSeconds:.45,effectGain:.8});
const check=(v,c)=>{if(!v)throw Error('HISTORY_V2_'+c);};
const smooth=t=>t*t*t*(10+t*(-15+6*t));
const union=(a,b)=>[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[2],b[2]),Math.max(a[3],b[3])];
export function directorConfig(given={}){
 check(given&&typeof given==='object'&&!Array.isArray(given)&&Object.keys(given).every(k=>k in DEFAULT_DIRECTOR_CONFIG),'CONFIG_FIELDS');
 const c={...DEFAULT_DIRECTOR_CONFIG,...given},limits={smallChangeRatio:[0,.1],minimumStateSeconds:[.3,2],finalHoldFraction:[.12,.3],maximumFocusZoomRatio:[1,3],effectSeconds:[.15,1],effectGain:[0,1]};
 for(const [k,[lo,hi]] of Object.entries(limits))check(Number.isFinite(c[k])&&c[k]>=lo&&c[k]<=hi,'CONFIG_RANGE_'+k);return c;
}
/** Use the existing variable Scene state/beat contract. No history dates change. */
export function retimeHistoryScene(scene,analysis,config={}){
 const c=directorConfig(config),s=structuredClone(scene),n=s.timing.total_frames,fps=s.timing.fps,count=s.time_steps.length;
 check(n>=60&&n<=600&&fps===30&&s.timing.event_start_frame===0&&!s.causal_tracks?.length&&!s.routes?.length&&!s.front_lines?.length,'TERRITORY_ONLY_TIMING_REQUIRED');
 const hold=Math.max(18,Math.round(n*c.finalHoldFraction)),action=n-hold,min=Math.ceil(c.minimumStateSeconds*fps);
 const durations=Array(count).fill(min);durations[0]=Math.max(min,Math.round(.6*fps));
 let remaining=action-durations.reduce((a,b)=>a+b,0);check(remaining>=0,'READABILITY_BUDGET_REQUIRED');
 const maximum=Math.max(1,...analysis.changes.map(x=>x.changedKm2));
 // Larger absolute/relative change and separated regions need reading time.
 // The weight is explicitly not an assessment of historical importance.
 const weights=[.7,...analysis.changes.map(x=>.2+Math.sqrt(x.changedKm2/maximum)+.45*Math.sqrt(x.ratio)+.08*Math.min(4,x.parts))];
 const total=weights.reduce((a,b)=>a+b,0),shares=weights.map(w=>remaining*w/total),whole=shares.map(Math.floor);
 let remainder=remaining-whole.reduce((a,b)=>a+b,0);
 const order=shares.map((v,i)=>({i,f:v-whole[i]})).sort((a,b)=>b.f-a.f||a.i-b.i);
 for(let j=0;j<remainder;j++)whole[order[j].i]++;
 for(let i=0;i<count;i++)durations[i]+=whole[i];
 let cursor=0;
 s.beats=s.time_steps.map((step,i)=>{step.start_frame=cursor;step.transition_frames=durations[i];cursor+=durations[i];return{id:'BEAT_'+String(i+1).padStart(2,'0'),type:i?'STATE_CHANGE':'EVENT_ACTION',start_frame:step.start_frame,end_frame:cursor,duration_frames:durations[i],state_id:step.id,geometry_refs:[...s.camera_intent.target_geometry_refs]};});
 s.beats.push({id:'BEAT_'+String(count+1).padStart(2,'0'),type:'HOLD',start_frame:action,end_frame:n,duration_frames:hold,camera_intent:'LOCK',geometry_refs:[...s.camera_intent.target_geometry_refs]});
 s.timing={...s.timing,initial_reveal_frames:durations[0],state_transition_frames:durations[1],final_hold_frames:hold,action_frames:action};
 return{scene:s,audit:{durations,holdFrames:hold,weights,method:'MINIMUM_READING_BUDGET_PLUS_LARGEST_REMAINDER',authoritativeDurations:'time_steps[].transition_frames',historicalImportanceInferred:false,sourceDatesChanged:false}};
}
function bestPose(bounds,levels,{scaleCap=Infinity}={}){
 const candidates=[];
 // Tiny territories still need source-resolvable geographic context.
 const original=bounds,cx=(bounds[0]+bounds[2])/2;
 if(bounds[2]-bounds[0]<18)bounds=[cx-9,bounds[1],cx+9,bounds[3]];
 for(const spacing of [...new Set(levels.map(l=>Math.max(...l.pixelSpacing)))]){
  let fitted;try{fitted=fitGeographicPose(bounds,{margin:94,pixelSpacing:spacing});}catch{continue;}
  // A lower zoom may be needed for source coverage. Recenter in Mercator,
  // then verify the real raster gutter and density at every candidate.
  for(let j=0;j<60;j++){
   const scale=Math.min(scaleCap,fitted.scale)*Math.pow(.98,j),half=960/scale;
   const limit=mercatorY(Math.min(84,Math.acos(Math.min(.999,scale*spacing))*180/Math.PI-.75));if(limit<=half)continue;
   const cy=Math.max(-limit+half,Math.min(limit-half,(mercatorY(bounds[1])+mercatorY(bounds[3]))/2));
   const pose={center:[(bounds[0]+bounds[2])/2,inverseMercatorY(cy)],scale,rollDegrees:0};
   try{selectGeographicTerrain(levels,pose,{maximumTextureSize:8192});candidates.push(pose);break;}catch{}
  }
 }
 check(candidates.length,'SOURCE_FIT_REQUIRED_'+JSON.stringify(bounds));return candidates.sort((a,b)=>b.scale-a.scale)[0];
}
function focusBounds(change,state,config){
 if(change.ratio<config.smallChangeRatio||!change.bounds)return boundsOf(state);
 // Keep all substantial disconnected regions; tiny overlay slivers remain in the source and effects, but do not dictate the camera.
 const components=multi(change.changed).map(p=>({geometry:geometry([p]),area:areaKm2(geometry([p]))}));
 const substantial=components.filter(x=>x.area>=change.changedKm2*.01);
 const b=(substantial.length?substantial.map(x=>boundsOf(x.geometry)).reduce(union):change.bounds),all=boundsOf(state),cx=(b[0]+b[2])/2,cy=(mercatorY(b[1])+mercatorY(b[3]))/2;
 const w=Math.max(b[2]-b[0],(all[2]-all[0])/config.maximumFocusZoomRatio,18),h=Math.max(mercatorY(b[3])-mercatorY(b[1]),12);
 return[cx-w*.55,inverseMercatorY(cy-h*.55),cx+w*.55,inverseMercatorY(cy+h*.55)];
}
export function deriveHistoryPresentationV2({scene,admission,analysis=analyzeTerritoryChanges(scene),timingAudit,config={}}){
 const c=directorConfig(config),levels=admission.regionEvidence?.sourceLevels,n=scene.timing.total_frames,action=n-scene.timing.final_hold_frames;
 check(levels?.length,'QUALIFIED_TERRAIN_REQUIRED');
 const stateBoxes=analysis.states.map(boundsOf),overview=bestPose(stateBoxes.at(-1),levels),keys=[{frame:0,role:'INTRO',pose:bestPose(stateBoxes[0],levels)}];
 keys.push({frame:scene.time_steps[0].transition_frames-1,role:'INTRO_HOLD',pose:structuredClone(keys[0].pose)});
 const climax=analysis.changes.reduce((a,b)=>b.changedKm2>a.changedKm2?b:a).toStateId;
 for(let i=1;i<scene.time_steps.length;i++){
  const step=scene.time_steps[i],change=analysis.changes[i-1],last=i===scene.time_steps.length-1;
  const target=last?stateBoxes[i]:focusBounds(change,analysis.states[i],c);
  keys.push({frame:last?action-1:step.start_frame+Math.floor((step.transition_frames-1)*.75),role:last?'RESULT':step.id===climax?'CLIMAX':'DEVELOPMENT',stateId:step.id,pose:bestPose(target,levels,{scaleCap:last?Infinity:(936/(stateBoxes[i][2]-stateBoxes[i][0]))*c.maximumFocusZoomRatio})});
 }
 const frames=Array.from({length:n},(_,f)=>{
  const j=keys.findIndex(k=>k.frame>=f);if(j>=0&&keys[j].frame===f)return structuredClone(keys[j].pose);if(j===0)return structuredClone(keys[0].pose);if(j<0)return structuredClone(keys.at(-1).pose);
  const a=keys[j-1],b=keys[j],t=smooth((f-a.frame)/(b.frame-a.frame)),mix=(a,b)=>a+(b-a)*t;
  return{center:[mix(a.pose.center[0],b.pose.center[0]),inverseMercatorY(mix(mercatorY(a.pose.center[1]),mercatorY(b.pose.center[1])))],scale:Math.exp(mix(Math.log(a.pose.scale),Math.log(b.pose.scale))),rollDegrees:0};
 });
 // Source quality is an admission gate, never a reason to warp coordinates.
 const sourceAdmissions=frames.map(p=>selectGeographicTerrain(levels,p,{maximumTextureSize:8192}));
 for(const [index,f]of [[0,0],[analysis.states.length-1,n-1]]){
  const view=geographicCameraFrame(frames[f]);for(const p of multi(analysis.states[index]).flat(2)){const q=view.project(p);check(q[0]>=64&&q[0]<=1016&&q[1]>=64&&q[1]<=1856,'ENDPOINT_TERRITORY_CLIPPED');}
 }
 const maximum=Math.max(1,...analysis.changes.map(x=>x.changedKm2));
 const changes=analysis.changes.map((d,i)=>{
  const step=scene.time_steps[i+1],end=step.start_frame+Math.min(step.transition_frames,Math.max(3,Math.round(c.effectSeconds*30)));
  return{fromStateId:d.fromStateId,toStateId:d.toStateId,startFrame:step.start_frame,endFrame:end,strength:d.ratio<c.smallChangeRatio?0:c.effectGain*(.35+.65*Math.sqrt(d.changedKm2/maximum)),added:d.added,removed:d.removed};
 });
 const starts=scene.time_steps.map((s,i)=>i===0?0:s.start_frame+Math.ceil((s.transition_frames-1)/2));
 const labels=[{id:'HISTORY_TITLE',role:'TITLE',text:scene.subject.label,startFrame:0,endFrame:n,revealFrames:1,exitFrames:1,priority:100},
 ...scene.time_steps.map((s,i)=>({id:'HISTORY_YEAR_'+i,role:'TIMELINE',stateId:s.id,text:historicalTimeLabel(s.date),startFrame:starts[i],endFrame:starts[i+1]??n,revealFrames:1,exitFrames:1,priority:100}))];
 if(scene.source_notes.some(s=>s.uncertainty))labels.push({id:'HISTORY_DISCLOSURE',role:'DISCLOSURE',text:'역사 경계 재구성',startFrame:0,endFrame:n,revealFrames:1,exitFrames:1,priority:90});
 const presentation={camera:{mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames},initialStateVisibility:'PRESERVE_PROVIDED',territoryColors:Object.fromEntries(scene.time_steps.map(s=>[s.id,[1,.62,.12,.42]])),mapStyle:{preset:'REFERENCE_FOCUS_V2',revealFrames:1,countryFill:false,nativeBoundaries:false},labels:{enabled:true,items:labels},highlights:[],territoryChanges:{profile:HISTORY_DIRECTION_V2,config:c,items:changes}};
 return{presentation,audit:{profile:HISTORY_DIRECTION_V2,config:c,cameraKeys:keys,timing:timingAudit,sourceLevelIndices:[...new Set(sourceAdmissions.map(a=>a.index))],historicalGeometryChanged:false,newRenderer:false,historicalImportanceInferred:false,areaMethod:analysis.areaMethod,
 changes:analysis.changes.map((d,i)=>{const {added,removed,changed,...stats}=d;const f=keys[i+2].frame;return{...stats,measureFrame:f,changedScreenFraction:screenFraction(changed,frames[f]),newScreenFraction:screenFraction(added,frames[f]),removedScreenFraction:screenFraction(removed,frames[f]),effectStrength:changes[i].strength};}),
 limitations:['Area is a spherical estimate from source reconstruction, not surveyed area.','A centroid is a framing statistic; no event or army location is inferred.','Six seconds cannot make every supplied period a long reading hold.','Whole final territory in a portrait Mercator frame may require ocean context.'],omitted:['UNSOURCED_ROUTES','BATTLES','PROPAGATION_WAVES'],manualPresentationFields:[]}};
}
