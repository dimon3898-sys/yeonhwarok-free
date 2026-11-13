/** Opt-in common policy connecting existing Area, Mercator, glyph and map passes.
 * No country names, dates, routes, authored camera poses, renderer or world simulation. */
import {fitGeographicPose,geographicCameraFrame,mercatorY,inverseMercatorY,selectGeographicTerrain} from '../../web/map_infographic_v1/geographic_camera_v1.mjs';
import {historicalTimeLabel} from '../../web/map_infographic_v1/historical_time_v1.mjs';
export const HISTORY_DIRECTION_PROFILE='HISTORICAL_STATES_V1';
const check=(v,c)=>{if(!v)throw Error('HISTORY_DIRECTION_'+c);};
const union=(a,b)=>[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[2],b[2]),Math.max(a[3],b[3])];
export function geometryBounds(geometry){
 const points=[];const visit=x=>{if(Array.isArray(x)&&x.length===2&&x.every(Number.isFinite))points.push(x);else if(Array.isArray(x))x.forEach(visit);};visit(geometry.coordinates);
 check(points.length,'GEOMETRY_REQUIRED');return[Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];
}
export function historyRegion(data){
 check(data?.scenes?.length===1,'ONE_CONTINUOUS_SCENE_REQUIRED');const facts=data.scenes[0].facts;
 check(facts?.subject?.event_family==='WAR'&&facts.stages?.length>=2,'SUPPLIED_STATES_REQUIRED');
 const ids=new Set(facts.stages.flatMap(s=>s.area_refs??[]));check(ids.size,'SUPPLIED_TERRITORY_REQUIRED');
 const boxes=facts.geometries.filter(g=>ids.has(g.id)).map(g=>geometryBounds(g.geometry)),bbox=boxes.reduce(union);
 return{sourceId:'AUTO',crs:'EPSG:4326',projection:'GEOGRAPHIC_MERCATOR_V1',center:[(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2],bbox};
}
export function deriveHistoryPresentation({scene,admission}){
 check(scene.event_type==='WAR'&&scene.time_steps.length>=2,'AREA_STATES_REQUIRED');
 check(!scene.routes?.length,'WIDE_ROUTE_CONSUMER_NOT_CONNECTED');
 const n=scene.timing.total_frames,hold=scene.timing.final_hold_frames,levels=admission.regionEvidence?.sourceLevels;
 check(levels?.length,'QUALIFIED_TERRAIN_LEVELS_REQUIRED');
 // A single adequate overview avoids style/density discontinuities in a wide tour.
 const spacing=Math.max(...levels.map(l=>Math.max(...l.pixelSpacing)));
 const byId=new Map(scene.areas.map(a=>[a.id,scene.geometries.find(g=>g.id===a.geometry_ref).geometry]));
 const boxes=scene.time_steps.map(s=>{check(s.area_ids.length,'TERRITORY_STATE_REQUIRED');return s.area_ids.map(id=>geometryBounds(byId.get(id))).reduce(union);});
 let envelope=boxes[0];const keys=boxes.map((b,i)=>{envelope=union(envelope,b);return{frame:i===0?0:scene.time_steps[i].start_frame,pose:fitGeographicPose(envelope,{pixelSpacing:spacing})};});
 const frames=Array.from({length:n},(_,f)=>{
  const k=keys.findIndex(k=>k.frame>=f);if(k===0)return structuredClone(keys[0].pose);if(k<0)return structuredClone(keys.at(-1).pose);
  const a=keys[k-1],b=keys[k],u=(f-a.frame)/(b.frame-a.frame),t=u*u*u*(10+u*(-15+u*6)),mix=(a,b)=>a+(b-a)*t;
  const width=mix(1080/a.pose.scale,1080/b.pose.scale),scale=1080/width,half=960/scale;
  const limit=mercatorY(Math.min(84,Math.acos(scale*spacing)*180/Math.PI-.75));
  const cy=Math.max(-limit+half,Math.min(limit-half,mix(mercatorY(a.pose.center[1]),mercatorY(b.pose.center[1]))));
  return{center:[mix(a.pose.center[0],b.pose.center[0]),inverseMercatorY(cy)],scale,rollDegrees:0};
 });
 const sourceAdmissions=frames.map(p=>selectGeographicTerrain(levels,p,{maximumTextureSize:8192}));
 // Validate every visible source state, including both ends of each cross-fade.
 for(let f=0;f<n;f++){
  const current=scene.time_steps.findLastIndex(s=>s.start_frame<=f),active=current>0&&f<scene.time_steps[current].start_frame+scene.time_steps[current].transition_frames?[current-1,current]:[Math.max(0,current)];
  const view=geographicCameraFrame(frames[f]);for(const i of active)for(const id of scene.time_steps[i].area_ids){
   const g=byId.get(id),visit=x=>{if(Array.isArray(x)&&x.length===2&&x.every(Number.isFinite)){const q=view.project(x);check(q[0]>=64&&q[0]<=1016&&q[1]>=64&&q[1]<=1856,'VISIBLE_GEOMETRY_CLIPPED');}else if(Array.isArray(x))x.forEach(visit);};visit(g.coordinates);
  }
 }
 const starts=scene.time_steps.map((s,i)=>i===0?0:s.start_frame+Math.ceil((s.transition_frames-1)/2));
 const labels=[{id:'HISTORY_TITLE',role:'TITLE',text:scene.subject.label,startFrame:0,endFrame:n,revealFrames:8,exitFrames:1,priority:100},
  ...scene.time_steps.map((s,i)=>({id:'HISTORY_YEAR_'+i,role:'TIMELINE',stateId:s.id,text:historicalTimeLabel(s.date),startFrame:starts[i],endFrame:starts[i+1]??n,revealFrames:1,exitFrames:1,priority:100}))];
 if(scene.source_notes.some(s=>s.uncertainty))labels.push({id:'HISTORY_DISCLOSURE',role:'DISCLOSURE',text:'역사 경계 재구성',startFrame:0,endFrame:n,revealFrames:8,exitFrames:1,priority:90});
 check(labels.length<=16,'LABEL_CAPACITY');
 const territoryColors=Object.fromEntries(scene.time_steps.map(s=>[s.id,[1,.62,.12,.42]]));
 check(scene.time_steps.length<=8,'STATE_COLOR_CAPACITY');
 const presentation={camera:{mode:'GEOGRAPHIC_TRACK',projection:'GEOGRAPHIC_MERCATOR_V1',frames},initialStateVisibility:'PRESERVE_PROVIDED',
  territoryColors,mapStyle:{preset:'REFERENCE_FOCUS_V2',revealFrames:1,countryFill:false,nativeBoundaries:false},labels:{enabled:true,items:labels},highlights:[]};
 return{presentation,audit:{profile:HISTORY_DIRECTION_PROFILE,newCommonConnection:true,newRenderer:false,manualPresentationFields:[],
  cameraRule:'Source geometry envelopes, existing Mercator projection, source density limits, quintic interpolation; first-to-last states, fixed final hold.',
  cameraKeys:keys,checkedVisibleGeometryFrames:n,sourceLevelIndices:[...new Set(sourceAdmissions.map(a=>a.index))],
  decisions:[{item:'cameraStart',status:'AUTO',basis:'first supplied extent'},{item:'cameraMotion',status:'AUTO',basis:'dated cumulative framing bounds; displayed territories never accumulated'},
   {item:'territoryStates',status:'AUTO',basis:'existing Area state cross-fades; exact input polygons'},
   {item:'militaryRoutes',status:'OMITTED_NO_SOURCE_DATA',basis:'no campaign route invented'},
   {item:'importantEvents',status:'OMITTED_NO_SOURCE_DATA',basis:'no source event points or conquest dates'},
   {item:'visualEffects',status:'AUTO_EXISTING_AREA_STYLE',basis:'existing outline/glow; propagation waves omitted without propagation facts'},
   {item:'yearAndRegionLabels',status:'AUTO',basis:'source state periods, supplied subject label and reconstruction disclosure'},
   {item:'finalFraming',status:'AUTO',basis:'whole supplied territory sequence fits, '+hold+' frame stable hold'}],
  historicalGeometryChanged:false,intermediateOpacityIsHistoricalClaim:false}};
}
