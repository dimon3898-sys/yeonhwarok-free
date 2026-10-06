/** Component-local rhythm over the approved v004 Production renderer.
 * Only interpolation phases change. The scene, shader, event, action, label,
 * entity lifetime, anticipation and geographic handoff clocks stay at real t.
 */
import {SceneProductionFlatRenderer,productionCameraIntervals,productionFlatCameraValues} from './production_visual_adapter.js';

export const RHYTHM_VISUAL_VERSION='v1';
const clamp01=value=>Math.max(0,Math.min(1,value));

/** Shared with Python: smoothstep speed integral is a*u+(b-a)*(u^3-.5*u^4).
 * Its segment area is width*(a+b)/2. Normalization preserves exact endpoints.
 * Adjacent zero-speed knots create a component pause, never a frozen video.
 */
export function compileRhythmRamp(knots){
 if(!Array.isArray(knots)||knots.length<2||knots.length>16)throw Error('RHYTHM_RAMP_REQUIRES_2_TO_16_KNOTS');
 const values=knots.map(knot=>({phase:knot?.phase,speed:knot?.speed}));
 if(values.some(value=>!Number.isFinite(value.phase)||!Number.isFinite(value.speed)||value.phase<0||value.phase>1||value.speed<0||value.speed>4))throw Error('RHYTHM_RAMP_INVALID_KNOT');
 if(values[0].phase!==0||values.at(-1).phase!==1)throw Error('RHYTHM_RAMP_REQUIRES_EXACT_ENDPOINTS');
 const segments=[];let area=0;
 for(let index=1;index<values.length;index++){
  const a=values[index-1],b=values[index],width=b.phase-a.phase;
  if(!(width>0))throw Error('RHYTHM_RAMP_KNOTS_MUST_INCREASE');
  const segmentArea=width*(a.speed+b.speed)/2;
  segments.push({start:a.phase,end:b.phase,width,a:a.speed,b:b.speed,precedingArea:area,area:segmentArea});area+=segmentArea;
 }
 if(!(area>0))throw Error('RHYTHM_RAMP_ZERO_INTEGRATED_SPEED');
 return {knots:values,segments,area};
}

function rampAtPhase(input,ramp){
 const p=clamp01(input);
 if(p===0)return {phase:0,normalizedSpeed:ramp.knots[0].speed/ramp.area};
 if(p===1)return {phase:1,normalizedSpeed:ramp.knots.at(-1).speed/ramp.area};
 const segment=ramp.segments.find(value=>p<=value.end),u=clamp01((p-segment.start)/segment.width);
 const integral=segment.width*(segment.a*u+(segment.b-segment.a)*(u**3-.5*u**4));
 const speed=segment.a+(segment.b-segment.a)*(u*u*(3-2*u));
 return {phase:clamp01((segment.precedingArea+integral)/ramp.area),normalizedSpeed:speed/ramp.area};
}

export function rhythmRampPhase(t,start,end,knots){
 if(!Number.isFinite(t)||!Number.isFinite(start)||!Number.isFinite(end)||!(end>start))throw Error('RHYTHM_RAMP_INVALID_CLOCK');
 return rampAtPhase((t-start)/(end-start),compileRhythmRamp(knots)).phase;
}

function componentClock(t,start,end,ramp){
 if(!Number.isFinite(t)||!Number.isFinite(start)||!Number.isFinite(end)||!(end>start))throw Error('RHYTHM_RAMP_INVALID_CLOCK');
 const inputPhase=clamp01((t-start)/(end-start)),value=ramp?rampAtPhase(inputPhase,ramp):{phase:inputPhase,normalizedSpeed:1};
 return {realTime:t,startTime:start,endTime:end,inputPhase,phase:value.phase,
  componentTime:start+(end-start)*value.phase,normalizedSpeed:value.normalizedSpeed,
  active:t>=start&&t<=end,paused:Boolean(ramp&&value.normalizedSpeed<1e-12&&t>start&&t<end)};
}

/** Reuse native interpolation, then native tracking/anticipation/handoff at t.
 * The fixed-pose second rig prevents those real-clock mechanisms being warped.
 */
export function rhythmFlatCameraValues(rig,t,state){
 if(!state.camera&&!state.zoom)return productionFlatCameraValues(rig,t);
 const intervals=productionCameraIntervals(rig.scene,2.5);
 const cameraClock=componentClock(t,0,intervals.travel,state.camera),zoomClock=componentClock(t,0,intervals.zoom,state.zoom);
 const interpolationRig={...rig,routes:[],scene:{...rig.scene,
  flat_map:{...(rig.scene.flat_map||{}),tracking:0,next_event:null},transition_in:'camera_continuity',transition_out:'camera_continuity'}};
 const pan=productionFlatCameraValues(interpolationRig,state.camera?cameraClock.componentTime:t);
 const zoom=productionFlatCameraValues(interpolationRig,state.zoom?zoomClock.componentTime:t);
 const coordinate=rig.projection.inverse(pan.center),pose={...coordinate,span_degrees:zoom.span,
  tilt:pan.tilt,rotation:pan.rotation,bank:pan.bank};
 const value=productionFlatCameraValues({...rig,start:pose,end:pose},t);
 return {...value,e:pan.e,zoomEasing:zoom.zoomEasing,sourceTime:t,globalTimewarp:false,
  rhythmCameraClock:cameraClock,rhythmZoomClock:zoomClock};
}

/** Same installation in native rendering and the canvas-free semantic gate. */
export function installRhythmOnFlatCore(core){
 const spec=core.sceneSpec.rhythm_visual;
 if(!spec)return null;
 if(spec.version!==RHYTHM_VISUAL_VERSION)throw Error('RHYTHM_VISUAL_V1_REQUIRED');
 if(core.rhythmVisualState)return core.rhythmVisualState;
 const state={version:RHYTHM_VISUAL_VERSION,camera:spec.camera?compileRhythmRamp(spec.camera.knots):null,
  zoom:spec.zoom?compileRhythmRamp(spec.zoom.knots):null,routes:new Map()};
 for(const target of spec.routes||[]){
  if(state.routes.has(target.route_id))throw Error('RHYTHM_ROUTE_DUPLICATE '+target.route_id);
  const route=core.route(target.route_id);
  if(!route)throw Error('RHYTHM_ROUTE_NOT_FOUND '+target.route_id);
  if(!(route.end>route.start))throw Error('RHYTHM_ROUTE_INVALID_WINDOW '+route.id);
  if(Number(route.spec.progress_start||0)===Number(route.spec.progress_end??1))throw Error('RHYTHM_HELD_ROUTE_MUST_REMAIN_UNCHANGED '+route.id);
  state.routes.set(route.id,{route,ramp:compileRhythmRamp(target.knots),originalProgress:route.progress.bind(route)});
 }
 // Validation completes before any route/camera method changes.
 for(const {route,ramp,originalProgress} of state.routes.values())route.progress=(time,easing)=>{
  const clock=componentClock(time,route.start,route.end,ramp);
  return originalProgress(clock.componentTime,easing);
 };
 core.cam.values=time=>rhythmFlatCameraValues(core.cam,time,state);
 core.rhythmVisualState=state;return state;
}

export function rhythmComponentAudit(core,t){
 const state=core.rhythmVisualState;if(!state)return null;
 const intervals=productionCameraIntervals(core.cam.scene,2.5);
 return {version:state.version,sourceSceneTime:t,globalTimewarp:false,
  camera:state.camera?{...componentClock(t,0,intervals.travel,state.camera),actualEasedPhase:core.cam.current?.e??null}:null,
  zoom:state.zoom?{...componentClock(t,0,intervals.zoom,state.zoom),actualEasedPhase:core.cam.current?.zoomEasing??null}:null,
  routes:[...state.routes.values()].map(({route,ramp})=>({...componentClock(t,route.start,route.end,ramp),
   route_id:route.id,actualEasedProgress:route.progress(t),actualEntityDrivenProgress:core.routeProgress(route,t)})),
  authoredComponentCount:Number(Boolean(state.camera))+Number(Boolean(state.zoom))+state.routes.size,
  realClockConsumers:['shaders','visual_events','entity_actions','spawn','entity_visibility','labels','country_highlights','focus','next_event','geographic_handoff'],
  approvedGraphicsChanged:false};
}

export class SceneRhythmFlatRenderer extends SceneProductionFlatRenderer {
 constructor(scene,plan){
  if(scene.rhythm_visual?.version!==RHYTHM_VISUAL_VERSION)throw Error('RHYTHM_VISUAL_V1_REQUIRED');
  super(scene,plan);
 }
 async init(){await super.init();installRhythmOnFlatCore(this.core);this.frame(0);return this;}
 audit(t){const value=super.audit(t);value.rhythmVisual=rhythmComponentAudit(this.core,t);return value;}
}
