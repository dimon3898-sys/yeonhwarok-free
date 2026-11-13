/** Opt-in composition of existing Flow clocks/vector primitives. No country logic. */
import {compileFlowPlan,sampleFlowRoute} from '../../web/map_infographic_v1/flow_core_v2.mjs';
import {evaluateGeographicLineReveal} from '../../web/map_infographic_v1/event_line_v1.mjs';
const check=(v,c)=>{if(!v)throw Error(c);};
const copy=structuredClone;
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
function keys(v,allowed,code){check(object(v)&&Object.keys(v).every(k=>allowed.includes(k)),code);}
const unit=v=>Number.isFinite(v)&&v>=0&&v<=1;
const integer=(v,min,max)=>Number.isSafeInteger(v)&&v>=min&&v<=max;
export function validateFlowStyle(style){
 keys(style,['width','coreColor','glowColor','glowRadius','glowGain'],'PRESENTATION_FLOW_STYLE_FIELDS');
 check(Number.isFinite(style.width)&&style.width>=1&&style.width<=12&&Number.isFinite(style.glowRadius)&&style.glowRadius>0&&style.glowRadius<=12&&unit(style.glowGain),'PRESENTATION_FLOW_STYLE_RANGE');
 for(const k of ['coreColor','glowColor'])check(Array.isArray(style[k])&&style[k].length===4&&style[k].every(unit),'PRESENTATION_FLOW_STYLE_RGBA');
 check(style.coreColor[3]>0,'PRESENTATION_FLOW_VISIBLE_CORE_REQUIRED');
 return copy(style);
}
export function validateHighlightRing(ring,{startFrame,endFrame,totalFrames,holdFrames}){
 keys(ring,['frames','radiusPx','color'],'PRESENTATION_RING_FIELDS');
 check(integer(ring.frames,2,60)&&startFrame+ring.frames<=endFrame&&startFrame+ring.frames<=totalFrames-holdFrames,'PRESENTATION_RING_MUST_FINISH_BEFORE_HOLD');
 check(Number.isFinite(ring.radiusPx)&&ring.radiusPx>=12&&ring.radiusPx<=64,'PRESENTATION_RING_RADIUS');
 check(Array.isArray(ring.color)&&ring.color.length===4&&ring.color.every(unit)&&ring.color[3]>0,'PRESENTATION_RING_COLOR');
 return copy(ring);
}
export function validatePresentationFlows(items,{scene,engines}){
 check(Array.isArray(items)&&items.length>=1&&items.length<=8,'PRESENTATION_FLOW_CAPACITY');
 const ids=new Set();
 return items.map(item=>{
  keys(item,['routeId','timing','style','previewStyle','trail','reveal'],'PRESENTATION_FLOW_FIELDS');
  const binding=engines.plans.find(b=>b.id===item.routeId&&b.engine==='EXISTING_FLOW_V2');
  check(binding&&!ids.has(item.routeId),'PRESENTATION_FLOW_SUPPLIED_UNIQUE_ROUTE_REQUIRED');ids.add(item.routeId);
  const out=copy(item);
  if(item.timing!==undefined){
   const plan=compileFlowPlan(binding.plan.intent,item.timing);
   check(plan.fps===scene.timing.fps&&plan.startFrame===0&&plan.totalFrames===binding.plan.totalFrames&&plan.timing.hold_frames===scene.timing.final_hold_frames,'PRESENTATION_FLOW_ORIGINAL_CLOCK_REQUIRED');
  }
  for(const k of ['style','previewStyle'])if(item[k]!==undefined)out[k]=validateFlowStyle(item[k]);
  if(item.trail!==undefined){keys(item.trail,['echoes','spacingPixels','alpha'],'PRESENTATION_TRAIL_FIELDS');
   check(integer(item.trail.echoes,1,3)&&Number.isFinite(item.trail.spacingPixels)&&item.trail.spacingPixels>=8&&item.trail.spacingPixels<=32&&Number.isFinite(item.trail.alpha)&&item.trail.alpha>0&&item.trail.alpha<=.4,'PRESENTATION_TRAIL_RANGE');}
  if(item.reveal!==undefined){keys(item.reveal,['mode','leadPixels'],'PRESENTATION_FLOW_REVEAL_FIELDS');
   check(item.reveal.mode==='FOLLOW_OBJECT'&&Number.isFinite(item.reveal.leadPixels)&&item.reveal.leadPixels>=0&&item.reveal.leadPixels<=48,'PRESENTATION_FLOW_REVEAL_RANGE');}
  return out;
 });
}
export function bindPresentationFlows(engines,items){
 if(items===undefined)return engines;
 return {...engines,plans:engines.plans.map(binding=>{
  const options=items.find(item=>item.routeId===binding.id);if(!options)return binding;
  return {...binding,plan:options.timing?compileFlowPlan(binding.plan.intent,options.timing):binding.plan,presentationFlow:copy(options)};
 })};
}
export function composePresentationFlowControls(controls,primitive,options){
 if(!options?.reveal)return controls;
 const fraction=controls.localFrame===0?0:Math.min(1,controls.objectFraction+options.reveal.leadPixels/primitive.totalLengthPixels);
 const directionalFraction=Math.min(controls.directionalFraction,fraction);
 const directional=sampleFlowRoute(primitive,directionalFraction,{lookAheadPixels:controls.headingLookAheadPixels});
 check(fraction>=controls.objectFraction,'PRESENTATION_FLOW_OBJECT_BEHIND_REVEAL_REQUIRED');
 return {...controls,routeFraction:fraction,routeReveal:evaluateGeographicLineReveal(primitive,fraction),directionalFraction,directionalPosition:directional.position,directionalHeading:directional.heading,
  presentationReveal:{mode:options.reveal.mode,leadPixels:options.reveal.leadPixels,clockOwner:'UNCHANGED_FLOW_V2_OBJECT_CLOCK'}};
}
export function highlightRingAt(highlight,frame,position){
 const ring=highlight.ring;if(!ring||frame<highlight.startFrame||frame>=highlight.startFrame+ring.frames)return null;
 const progress=(frame-highlight.startFrame)/(ring.frames-1);
 return {active:true,anchor:[...position],position:[...position],radius:ring.radiusPx*(.3+.7*progress),alpha:progress===0||progress===1?0:Math.sin(Math.PI*progress),progress};
}
