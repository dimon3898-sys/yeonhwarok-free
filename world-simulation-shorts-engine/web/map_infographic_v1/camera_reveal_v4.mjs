/** Guided information plan consumes a completed immutable CameraPlan. */
import {evaluateReferenceCameraFrame} from './camera_director_v4.mjs';
import {evaluateMovingLayout,validateVisibleMovingLayout} from './moving_layout_v4.mjs';
export const GUIDED_REVEAL_V4_VERSION='GUIDED_INFORMATION_REVEAL_V4';
export const GUIDED_REVEAL_V4_PROFILE=Object.freeze({version:'READABILITY_CONDITIONS_V4',stableEligibilitySeconds:.12,
 countryMaxViewportSpeed:.20,markerMaxViewportSpeed:.30,locationMaxViewportSpeed:.22,titleMaxViewportSpeed:.005,
 markerMinimumFramingRatio:.60,minimumPrimaryPerceptionSeconds:.70,markerLeadSeconds:.25,
 minimumLocationPerceptionSeconds:1.20,minimumTitlePerceptionSeconds:2.60});
const copy=v=>structuredClone(v),freeze=v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
const fingerprint=v=>{const text=JSON.stringify(v);let hash=2166136261;for(let i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619);}return(hash>>>0).toString(16).padStart(8,'0');};
const movingStates=new Set(['EVENT_APPROACH','GUIDED_REVEAL','DECELERATE','EVENT_FRAMING']);
function profileFrom(overrides){
 for(const key of Object.keys(overrides))if(!(key in GUIDED_REVEAL_V4_PROFILE))throw Error('GUIDED_REVEAL_UNKNOWN_PROFILE_FIELD: '+key);
 const result={...GUIDED_REVEAL_V4_PROFILE,...overrides};
 for(const [key,value]of Object.entries(result))if(typeof GUIDED_REVEAL_V4_PROFILE[key]==='number'&&(!Number.isFinite(value)||value<=0))throw Error('GUIDED_REVEAL_POSITIVE_PROFILE_REQUIRED: '+key);
 if(result.markerMinimumFramingRatio>1)throw Error('GUIDED_REVEAL_FRAMING_RATIO_REQUIRED');
 return result;
}

/** No camera mutation/recompilation, timestamps, frame-specific geometry or content. */
export function compileGuidedRevealPlan({cameraPlan,scene,layoutContract,evaluateCamera=evaluateReferenceCameraFrame,profile:overrides={},visualTokensForFrame=null}={}){
 if(cameraPlan?.version!=='CAMERA_DIRECTOR_V4'||!Number.isInteger(cameraPlan.totalFrames)||cameraPlan.totalFrames<=0)throw Error('GUIDED_REVEAL_VALIDATED_CAMERA_PLAN_REQUIRED');
 if(typeof evaluateCamera!=='function'||!layoutContract)throw Error('GUIDED_REVEAL_CAMERA_AND_MEASURED_LAYOUT_REQUIRED');
 const before=fingerprint(cameraPlan),profile=profileFrom(overrides),fps=cameraPlan.fps,count=cameraPlan.totalFrames,frames=s=>Math.max(1,Math.ceil(s*fps));
 const presence={country:Boolean(scene?.primary_label),marker:true,location:Boolean(scene?.location_label),title:Boolean(scene?.event_title),
  disclosure:layoutContract.items.some(i=>i.role==='SCENARIO_DISCLOSURE')};
 const states=[],layouts=[],conditions=[];
 const finalWidth=layoutContract.finalBounds[2]-layoutContract.finalBounds[0];
 for(let frame=0;frame<count;frame++){
  const state=evaluateCamera(cameraPlan,frame),tokens=visualTokensForFrame?.(state)??{},layout=evaluateMovingLayout(layoutContract,state,{markerSize:tokens.markerSize??layoutContract.markerSize,boundaryTokens:tokens});
  const speed=(state.screenVelocity?.pixelsPerSecond??Infinity)/Math.min(...cameraPlan.canonicalOutput),eventSpeed=(state.screenVelocity?.event?.pixelsPerSecond??Infinity)/Math.min(...cameraPlan.canonicalOutput);
  const framingRatio=finalWidth/(state.camera.flatBounds[2]-state.camera.flatBounds[0]);
  states.push(state);layouts.push(layout);conditions.push({frame,state:state.state,viewportSpeed:speed,eventViewportSpeed:eventSpeed,framingRatio,
   country:presence.country&&state.projectedRegion?.visible&&layout.readiness.country&&speed<=profile.countryMaxViewportSpeed,
   marker:presence.marker&&movingStates.has(state.state)&&state.projectedAnchor?.inSafe&&layout.readiness.marker&&framingRatio>=profile.markerMinimumFramingRatio&&eventSpeed<=profile.markerMaxViewportSpeed,
   location:presence.location&&movingStates.has(state.state)&&layout.readiness.location&&eventSpeed<=profile.locationMaxViewportSpeed,
   title:presence.title&&['EVENT_TITLE','PERCEPTION_HOLD','NEXT'].includes(state.state)&&state.settle?.locked&&layout.readiness.title&&speed<=profile.titleMaxViewportSpeed,
   layoutReadiness:copy(layout.readiness)});
 }
 const safeSuffix={};
 for(const role of ['country','marker','location','title']){
  safeSuffix[role]=Array(count);let safe=true;
  for(let frame=count-1;frame>=0;frame--){safe=safe&&layouts[frame].readiness[role];safeSuffix[role][frame]=safe;}
 }
 const stableFrames=frames(profile.stableEligibilitySeconds),schedule={},failures=[];
 const find=(role,minimum)=>{
  if(!presence[role])return null;
  for(let frame=Math.max(0,minimum);frame<count;frame++){
   if(!safeSuffix[role][frame])continue;
   let stable=true;for(let next=frame;next<Math.min(count,frame+stableFrames);next++)stable=stable&&conditions[next][role];
   if(stable&&frame+stableFrames<=count)return frame;
  }
  failures.push({role,code:'NO_READABLE_SAFE_GUIDED_ENTRY'});return null;
 };
 schedule.country=find('country',0);
 schedule.marker=find('marker',schedule.country===null?0:schedule.country+frames(profile.minimumPrimaryPerceptionSeconds));
 schedule.location=find('location',schedule.marker===null?0:schedule.marker+frames(profile.markerLeadSeconds));
 schedule.title=find('title',cameraPlan.timeline.find(s=>s.state==='EVENT_TITLE')?.startFrame??count);
 const perception={country:{minimumFrames:frames(profile.minimumPrimaryPerceptionSeconds),startFrame:schedule.country},
  marker:{minimumFrames:frames(profile.markerLeadSeconds),startFrame:schedule.marker},
  location:{minimumFrames:frames(profile.minimumLocationPerceptionSeconds),startFrame:schedule.location},
  title:{minimumFrames:frames(profile.minimumTitlePerceptionSeconds),startFrame:schedule.title}};
 for(const [role,window]of Object.entries(perception)){
  window.availableFrames=window.startFrame===null?0:count-window.startFrame;window.minimumSeconds=window.minimumFrames/fps;
  if(presence[role]&&window.availableFrames<window.minimumFrames)failures.push({role,code:'PERCEPTION_WINDOW_UNDERRUN'});
 }
 if(presence.country&&schedule.country!==null&&schedule.marker!==null&&schedule.country>=schedule.marker)failures.push({role:'marker',code:'PRIMARY_LABEL_SEQUENCE'});
 if(presence.location&&schedule.location!==null&&schedule.marker!==null&&schedule.marker>=schedule.location)failures.push({role:'location',code:'MARKER_LOCATION_SEQUENCE'});
 const cameraUnchanged=before===fingerprint(cameraPlan);
 if(!cameraUnchanged)throw Error('GUIDED_REVEAL_MUST_NOT_CHANGE_CAMERA_PLAN');
 if(failures.length)throw Object.assign(Error('GUIDED_REVEAL_PLAN_INVALID: '+JSON.stringify(failures)),{code:'GUIDED_REVEAL_PLAN_INVALID',failures});
 return freeze({version:GUIDED_REVEAL_V4_VERSION,fps,totalFrames:count,profile,presence,schedule,perception,conditions,
  cameraBinding:{version:cameraPlan.version,fingerprint:before,unchanged:true},primaryMaterial:{factor:1,animated:false},
  policy:'Geometry, actual glyph bounds, geographic speed, scale and future-safe latched candidates; no timestamp-only reveal',
  candidatePolicy:layoutContract.candidatePolicy,failures:[]});
}

/** Random-access visibility latches are a compiled plan, never mutable frame state. */
export function evaluateGuidedRevealFrame(plan,cameraState,layout){
 if(plan?.version!==GUIDED_REVEAL_V4_VERSION)throw Error('GUIDED_REVEAL_COMPILED_PLAN_REQUIRED');
 const frame=cameraState?.frame;
 if(!Number.isInteger(frame)||frame<0||frame>=plan.totalFrames)throw Error('GUIDED_REVEAL_FRAME_OUT_OF_RANGE');
 const reveal={primary:1,marker:0,location:0,country:0,title:0,disclosure:plan.presence.disclosure?1:0};
 for(const role of ['country','marker','location','title'])reveal[role]=plan.schedule[role]!==null&&frame>=plan.schedule[role]?1:0;
 const validation=layout?validateVisibleMovingLayout(layout,reveal):null;
 if(validation&&!validation.valid)throw Object.assign(Error('GUIDED_REVEAL_VISIBLE_LAYOUT_INVALID: '+JSON.stringify(validation.failures)),{code:'GUIDED_REVEAL_VISIBLE_LAYOUT_INVALID',failures:validation.failures});
 return{version:GUIDED_REVEAL_V4_VERSION,frame,reveal,primaryMaterial:1,
  visibility:{primaryRegion:true,primaryLabel:!!reveal.country,marker:!!reveal.marker,locationLabel:!!reveal.location,eventTitle:!!reveal.title},
  readiness:copy(plan.conditions[frame]),layout,validation,perception:copy(plan.perception),cameraChanged:false};
}
