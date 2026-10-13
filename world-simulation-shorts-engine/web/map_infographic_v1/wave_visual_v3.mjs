/** Event-owned, illustrative open wave fronts over supplied coast geometry.
 * Existing Area/Front/Timeline/Projection engines remain unchanged. This is a
 * deterministic presentation profile, never a wave speed or inundation solver.
 */
import {freezeEventData,validateEventAnchor} from './event_contract_v1.mjs';
import {compileAreaLinePrimitive} from './area_core_v3.mjs';
import {evaluateGeographicLineReveal} from './event_line_v1.mjs';

export const WAVE_VISUAL_PLAN_V3_VERSION='WAVE_VISUAL_PLAN_V3';
export const WAVE_VISUAL_FRAME_V3_VERSION='WAVE_VISUAL_FRAME_V3';
const clamp=value=>Math.max(0,Math.min(1,value));
const smooth=value=>{const t=clamp(value);return t*t*(3-2*t);};
const copy=value=>structuredClone(value);
const quantize=point=>point.map(value=>Number(value.toFixed(9)));
const canonicalNumber=value=>Number(value.toFixed(9));
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function integer(value,name,min=0){if(!Number.isSafeInteger(value)||value<min)throw Error('WAVE_'+name+'_INTEGER_REQUIRED');return value;}
function number(value,name,min,max){if(!Number.isFinite(value)||value<min||value>max)throw Error('WAVE_'+name+'_RANGE_REQUIRED');return value;}
function text(value,name){if(typeof value!=='string'||!value.trim())throw Error('WAVE_'+name+'_TEXT_REQUIRED');return value;}
function localFunctions(origin){
 const cos=Math.cos(origin[1]*Math.PI/180);
 if(cos<.05)throw Error('WAVE_NON_POLAR_PRESENTATION_REQUIRED');
 return {toLocal:point=>[(point[0]-origin[0])*cos,point[1]-origin[1]],
  toGeographic:point=>quantize([origin[0]+point[0]/cos,origin[1]+point[1]])};
}
function pointAt(primitive,fraction){return fraction===0?[...primitive.screenCoordinates[0]]:
 [...evaluateGeographicLineReveal(primitive,fraction).path.at(-1)];}
function lineGeometry(points){return {type:'LineString',coordinates:points};}
function lineItem(plan,id,geometry,alpha,project,extra={}){
 const linePrimitive=compileAreaLinePrimitive({geometry,source:plan.source,data_mode:plan.data_mode,
  direction:'FORWARD',style_role:'PRIMARY'},{project});
 return {id,geometry,linePrimitive,lineReveal:evaluateGeographicLineReveal(linePrimitive,1),
  revealFraction:1,alpha:clamp(alpha),role:'VISUAL_WAVE_FRONT',style_role:'PRIMARY',...extra};
}
/** Every highlighted interval retains exact native vertices, plus cut points on
 * their original segments. No source coastline is simplified or replaced. */
function intervalGeometry(primitive,from,to,toGeographic){
 const a=from*primitive.totalLengthPixels,b=to*primitive.totalLengthPixels;
 const points=[pointAt(primitive,from)];
 for(let index=1;index<primitive.screenCoordinates.length-1;index++){
  const distance=primitive.cumulativeLengthsPixels[index];
  if(distance>a&&distance<b)points.push([...primitive.screenCoordinates[index]]);
 }
 points.push(pointAt(primitive,to));
 return lineGeometry(points.map(toGeographic));
}
/** Source/time/profile are explicit fixture input; no subject or place branch. */
export function compileWaveVisualPlan(input){
 if(!input||typeof input!=='object')throw Error('WAVE_INPUT_REQUIRED');
 const origin=validateEventAnchor(input.origin,'WAVE_ORIGIN'),data_mode=input.data_mode??'PRODUCTION';
 const geometry=copy(input.coastGeometry),source=copy(input.source),local=localFunctions(origin);
 if(geometry?.type!=='LineString'||geometry.coordinates?.length<3)throw Error('WAVE_OPEN_COAST_LINE_REQUIRED');
 if(same(geometry.coordinates[0],geometry.coordinates.at(-1)))throw Error('WAVE_CLOSED_COAST_RING_FORBIDDEN');
 const coastPrimitive=compileAreaLinePrimitive({geometry,source,data_mode,direction:'FORWARD',style_role:'PRIMARY'},
  {project:point=>quantize(local.toLocal(point))});
 const fps=integer(input.fps??30,'FPS',1),totalFrames=integer(input.total_frames,'TOTAL_FRAMES',1),
  startFrame=integer(input.start_frame??0,'START_FRAME'),travelFrames=integer(input.travel_frames,'TRAVEL_FRAMES',30),
  staggerFrames=integer(input.stagger_frames??22,'STAGGER_FRAMES',8),waveCount=integer(input.wave_count??3,'WAVE_COUNT',2),
  fadeFrames=integer(input.fade_frames??28,'FADE_FRAMES',8),contactFrames=integer(input.contact_frames??20,'CONTACT_FRAMES',8),
  pulseFrames=integer(input.pulse_frames??24,'PULSE_FRAMES',8);
 if(waveCount>3)throw Error('WAVE_TWO_OR_THREE_MAJOR_FRONTS_REQUIRED');
 const profile=input.profile??{},sampleCount=integer(profile.sample_count??41,'SAMPLE_COUNT',9),
  contactCount=integer(profile.contact_count??9,'CONTACT_COUNT',3),birthFrames=integer(profile.birth_frames??12,'BIRTH_FRAMES',4);
 if(sampleCount>97||contactCount>24)throw Error('WAVE_VISUAL_CAPACITY_EXCEEDED');
 const curvature=number(profile.curvature_variation??.055,'CURVATURE_VARIATION',.01,.12),
  travelRatioFloor=number(profile.travel_ratio_floor??.35,'TRAVEL_RATIO_FLOOR',.2,.7),
  pulseStartPixels=number(profile.pulse_start_pixels??32,'PULSE_START_PIXELS',24,48),
  pulseEndPixels=number(profile.pulse_end_pixels??52,'PULSE_END_PIXELS',36,72);
 const sourceGeometryBinding=JSON.stringify({origin,geometry,source,data_mode});
 const sampled=Array.from({length:sampleCount},(_,index)=>quantize(pointAt(coastPrimitive,index/(sampleCount-1))));
 const distances=sampled.map(point=>canonicalNumber(Math.hypot(...point))),maximumDistance=Math.max(...distances);
 if(Math.min(...distances)<1e-5||maximumDistance>60)throw Error('WAVE_ORIGIN_AND_COAST_SEPARATION_REQUIRED');
 // Fixed profile variations are data-independent and deterministic; each wave
 // differs in span, shoreline correspondence and restrained normal curvature.
 const profiles=[{span:[0,1],bend:1,phase:.23,strength:.96},
  {span:[.045,.97],bend:-.82,phase:1.08,strength:.86},
  {span:[.01,.94],bend:.66,phase:1.87,strength:.78}];
 const waves=profiles.slice(0,waveCount).map((shape,index)=>{
  const start=startFrame+index*staggerFrames;
  const samples=Array.from({length:sampleCount},(_,sample)=>{
   const u=canonicalNumber(sample/(sampleCount-1)),fraction=canonicalNumber(shape.span[0]+u*(shape.span[1]-shape.span[0])),
    target=quantize(pointAt(coastPrimitive,fraction)),distance=canonicalNumber(Math.hypot(...target)),
    duration=canonicalNumber(travelFrames*(travelRatioFloor+(1-travelRatioFloor)*distance/maximumDistance));
   return {u,fraction,target,distance,duration,arrivalFrame:canonicalNumber(start+duration)};
  });
  // Only the new wave presentation is smoothed. Exact supplied coast vertices
  // remain in the plan and contact paths; interpolation tends back to their
  // actual positions as the front approaches shore.
  const displaySamples=samples.map((sample,index)=>{
   const weights=[1,2,3,2,1],mean=[0,0];
   for(let offset=-2;offset<=2;offset++){
    const target=samples[Math.max(0,Math.min(samples.length-1,index+offset))].target,weight=weights[offset+2]/9;
    mean[0]+=target[0]*weight;mean[1]+=target[1]*weight;
   }
   return {...sample,smoothedTarget:quantize(mean)};
  });
  return {id:'WAVE_'+(index+1),startFrame:start,...shape,samples:displaySamples};
 });
 const contacts=Array.from({length:contactCount},(_,index)=>{
  const from=canonicalNumber(index/contactCount),to=canonicalNumber((index+1)/contactCount),
   center=quantize(pointAt(coastPrimitive,(from+to)/2)),distance=canonicalNumber(Math.hypot(...center)),
   arrivalFrame=canonicalNumber(startFrame+travelFrames*(travelRatioFloor+(1-travelRatioFloor)*distance/maximumDistance));
  return {id:'COAST_CONTACT_'+(index+1),from,to,arrivalFrame,distance,
   geometry:intervalGeometry(coastPrimitive,from,to,local.toGeographic)};
 });
 const completeFrame=Math.ceil(Math.max(...waves.flatMap(wave=>wave.samples.map(sample=>sample.arrivalFrame)))+fadeFrames),
  firstContactFrame=Math.min(...contacts.map(contact=>contact.arrivalFrame));
 if(completeFrame>=totalFrames)throw Error('WAVE_REQUIRES_SHORT_POST_ARRIVAL_HOLD');
 const average=sampled.reduce((sum,point)=>[sum[0]+point[0]/sampled.length,sum[1]+point[1]/sampled.length],[0,0]),
  averageLength=Math.hypot(...average),heading=quantize(average.map(value=>value/averageLength));
 if(!heading.every(Number.isFinite))throw Error('WAVE_DIRECTION_FROM_ORIGIN_TO_COAST_REQUIRED');
 return freezeEventData({version:WAVE_VISUAL_PLAN_V3_VERSION,origin,coastGeometry:geometry,source,data_mode,
  fps,totalFrames,startFrame,travelFrames,staggerFrames,waveCount,fadeFrames,contactFrames,pulseFrames,
  sampleCount,contactCount,birthFrames,curvature,travelRatioFloor,pulseStartPixels,pulseEndPixels,waves,contacts,heading,
  completeFrame,firstContactFrame,sourceGeometryBinding,physicalSimulation:false,
  semanticMode:'ILLUSTRATIVE_FACT_BASED_VISUAL',motionSpace:'SUPPLIED_COAST_CORRESPONDENCE_NOT_PHYSICAL_SPEED',
  topology:'OPEN_FRONT_NO_CLOSED_PROPAGATION_RING',coastArrivalPolicy:'ONE_LOCAL_ACCENT_PER_SUPPLIED_INTERVAL'});
}
/** Saved plans are verified from their original supplied input and profile. */
export function assertWaveVisualPlan(plan){
 if(plan?.version!==WAVE_VISUAL_PLAN_V3_VERSION)throw Error('WAVE_PLAN_VERSION_REQUIRED');
 const canonical=compileWaveVisualPlan({origin:plan.origin,coastGeometry:plan.coastGeometry,source:plan.source,
  data_mode:plan.data_mode,fps:plan.fps,total_frames:plan.totalFrames,start_frame:plan.startFrame,
  travel_frames:plan.travelFrames,stagger_frames:plan.staggerFrames,wave_count:plan.waveCount,
  fade_frames:plan.fadeFrames,contact_frames:plan.contactFrames,pulse_frames:plan.pulseFrames,
  profile:{sample_count:plan.sampleCount,contact_count:plan.contactCount,birth_frames:plan.birthFrames,
   curvature_variation:plan.curvature,travel_ratio_floor:plan.travelRatioFloor,
   pulse_start_pixels:plan.pulseStartPixels,pulse_end_pixels:plan.pulseEndPixels}});
 if(!same(canonical,plan))throw Error('WAVE_PLAN_NON_CANONICAL');
 return canonical;
}
function waveAt(plan,wave,frame,project){
 const elapsed=frame-wave.startFrame;if(elapsed<=0)return {fronts:[],arrivals:[],visible:false};
 const local=localFunctions(plan.origin),birth=smooth(elapsed/plan.birthFrames),samples=wave.samples.map(sample=>{
  const progress=smooth(elapsed/sample.duration),shoreInfluence=progress**3,
   target=sample.smoothedTarget.map((value,axis)=>value*(1-shoreInfluence)+sample.target[axis]*shoreInfluence),
   normal=[-target[1]/sample.distance,target[0]/sample.distance],
   bend=plan.curvature*wave.bend*sample.distance*Math.sin(Math.PI*progress)
    *(Math.sin(sample.u*Math.PI*1.7+wave.phase)+.31*Math.sin(sample.u*Math.PI*3.4+wave.phase*.7)),
   point=[target[0]*progress+normal[0]*bend,target[1]*progress+normal[1]*bend],
   energy=1-smooth((elapsed-sample.duration)/plan.fadeFrames);
  return {...sample,geometryPoint:local.toGeographic(point),progress,alpha:birth*energy*wave.strength};
 });
 const maximumAlpha=Math.max(...samples.map(sample=>sample.alpha)),fronts=[];
 if(maximumAlpha<1e-7)return {fronts:[],arrivals:samples.filter(sample=>sample.progress===1).map(sample=>sample.arrivalFrame),visible:false};
 const entirelyUnabsorbed=samples.every(sample=>elapsed<=sample.duration);
 if(entirelyUnabsorbed){
  fronts.push(lineItem(plan,wave.id,lineGeometry(samples.map(sample=>sample.geometryPoint)),birth*wave.strength,project,
   {waveId:wave.id,phase:'TRAVEL',progress:samples.reduce((sum,sample)=>sum+sample.progress/samples.length,0)}));
 }else{
  // Section-by-section energy decay prevents a whole-country arrival flash.
  // Before absorption a single curve is used; only fading edges are separated.
  let points=[],alpha=null,part=0;
  const flush=()=>{if(points.length>1&&alpha>1e-7)fronts.push(lineItem(plan,wave.id+'_PART_'+part++,lineGeometry(points),alpha,project,
   {waveId:wave.id,phase:'COAST_ABSORPTION'}));points=[];alpha=null;};
  for(let index=1;index<samples.length;index++){
   const a=samples[index-1],b=samples[index],energy=(a.alpha+b.alpha)/2;
   if(energy<=1e-7){flush();continue;}
   if(alpha!==null&&Math.abs(energy-alpha)<1e-10)points.push(b.geometryPoint);
   else{flush();points=[a.geometryPoint,b.geometryPoint];alpha=energy;}
  }flush();
 }
 return {fronts,visible:fronts.length>0,arrivals:samples.filter(sample=>sample.progress===1).map(sample=>sample.arrivalFrame)};
}
function originPulseAt(plan,frame,project){
 const elapsed=frame-plan.startFrame,active=elapsed>0&&elapsed<plan.pulseFrames,
  progress=clamp(elapsed/(plan.pulseFrames-1)),amplitude=active?Math.sin(Math.PI*progress):0;
 if(!active||amplitude<=1e-7)return {active:false,progress,amplitude:0,front:null};
 const local=localFunctions(plan.origin),heading=plan.heading,normal=[-heading[1],heading[0]],originScreen=project(plan.origin),
  basisScreen=project(local.toGeographic(heading)),pixelsPerLocal=Math.hypot(basisScreen[0]-originScreen[0],basisScreen[1]-originScreen[1]),
  radius=(plan.pulseStartPixels+(plan.pulseEndPixels-plan.pulseStartPixels)*smooth(progress))/pixelsPerLocal;
 if(!Number.isFinite(radius)||radius<=0)throw Error('WAVE_PULSE_EXISTING_PROJECTION_REQUIRED');
 const coordinates=Array.from({length:17},(_,index)=>{
  const u=index/8-1,forward=radius*(.86-.41*u*u),side=radius*u;
  return local.toGeographic([heading[0]*forward+normal[0]*side,heading[1]*forward+normal[1]*side]);
 });
 const front=lineItem(plan,'ORIGIN_PULSE_OPEN_FRONT',lineGeometry(coordinates),amplitude*.86,project,
  {role:'ORIGIN_PULSE',singleOccurrence:true});
 return {active:true,progress,amplitude,front,origin:[...plan.origin],repeatCount:1};
}
/** Out-of-order evaluation produces the same result; source geometry is never mutated. */
export function evaluateWaveVisualFrame(plan,frame,{project}={}){
 if(plan?.version!==WAVE_VISUAL_PLAN_V3_VERSION)throw Error('WAVE_PLAN_VERSION_REQUIRED');
 integer(frame,'FRAME');if(frame>=plan.totalFrames)throw Error('WAVE_FRAME_OUT_OF_RANGE');
 if(typeof project!=='function')throw Error('WAVE_EXISTING_PROJECTION_REQUIRED');
 const states=plan.waves.map(wave=>waveAt(plan,wave,frame,project)),fronts=states.flatMap(state=>state.fronts),
  originPulse=originPulseAt(plan,frame,project),coastfrontHighlights=[];
 for(const contact of plan.contacts){
  const elapsed=frame-contact.arrivalFrame;
  if(elapsed<=0||elapsed>=plan.contactFrames)continue;
  const progress=elapsed/plan.contactFrames,alpha=Math.sin(Math.PI*progress)*.88;
  coastfrontHighlights.push(lineItem(plan,contact.id,copy(contact.geometry),alpha,project,
   {role:'COAST_CONTACT',arrivalFrame:contact.arrivalFrame,progress,singleOccurrence:true}));
 }
 const hold=frame>=plan.completeFrame,stateId=hold?'HOLD':frame>=plan.firstContactFrame?'COAST':'ORIGIN',
  allFronts=[...fronts,...(originPulse.front?[originPulse.front]:[])];
 return freezeEventData({version:WAVE_VISUAL_FRAME_V3_VERSION,frame,origin:[...plan.origin],stateId,
  timeLabel:null,timeLabelVisible:false,fronts,coastfrontHighlights,originPulse,hold,physicalSimulation:false,
  controls:{areas:[],impacts:[],fronts:allFronts,propagations:coastfrontHighlights},
  diagnostics:{majorFrontCount:states.filter(state=>state.visible).length,closedRingCount:0,
   coastContactCount:coastfrontHighlights.length,coastContactIds:coastfrontHighlights.map(item=>item.id),
   coastArrivalOrder:plan.contacts.map(contact=>({id:contact.id,frame:contact.arrivalFrame,distance:contact.distance}))
    .sort((a,b)=>a.frame-b.frame),singleOriginPulse:true,repeatBlink:false,
   geometrySourceBinding:plan.sourceGeometryBinding,sourceGeometryMutation:false,physicalSimulation:false,
   firstContactFrame:plan.firstContactFrame,completeFrame:plan.completeFrame,
   holdFrames:plan.totalFrames-plan.completeFrame,motion:'CONTINUOUS_COAST_REFERENCED_OPEN_FRONT_AND_LOCAL_ENERGY_FADE'}});
}
