/**
 * Reference motion director. Pure geographic camera ownership only: no pixel,
 * material, layout, reveal, story or asset mutation belongs in this module.
 */
import {geometryBounds, fitGeographicExtent} from './scale_contract.mjs';

export const CAMERA_DIRECTOR_V4_VERSION = 'CAMERA_DIRECTOR_V4';
export const CAMERA_INTENT_V4_VERSION = 'GEOGRAPHIC_CAMERA_INTENT_V4';
export const CAMERA_DIRECTOR_V4_PROFILE = Object.freeze({
 version:'REFERENCE_GEOGRAPHIC_MOTION_PROFILE_V4', fps:30,
 recognitionSeconds:1.05, relationSeconds:.8, settleSeconds:.6, lockSeconds:.2,
 titleEntrySeconds:.7, minimumTitlePerceptionSeconds:2.6, nextSeconds:.2,
 primaryPerceptionSeconds:.7, locationPerceptionSeconds:1.2,
 readingGraphemesPerSecond:7, expansionBaseSeconds:.65,
 expansionSecondsPerLogSpan:.72, approachBaseSeconds:2.9,
 approachSecondsPerLogSpan:1.35, approachSecondsPerNormalizedPan:1.05,
 accelerationFraction:.22, guidedFraction:.30, decelerationFraction:.26,
 minimumFineApproachSeconds:.4, maximumProgressBias:.28,
 projection:'REGIONAL_EQUIRECTANGULAR', holdDrift:false,
});
export const CAMERA_DIRECTOR_V4_STATES = Object.freeze([
 'PRIMARY_RECOGNITION','CONTEXT_EXPANSION','RELATION_HOLD','EVENT_APPROACH',
 'GUIDED_REVEAL','DECELERATE','EVENT_FRAMING','SETTLE','LOCK','EVENT_TITLE',
 'PERCEPTION_HOLD','NEXT',
]);
const copy=v=>structuredClone(v), clamp=x=>Math.max(0,Math.min(1,x));
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const pointOK=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90;
const extentOK=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]<b[2]&&b[1]<b[3]&&b[0]>=-180&&b[2]<=180&&b[1]>=-90&&b[3]<=90;
const center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2], size=b=>[b[2]-b[0],b[3]-b[1]];
const box=(c,s)=>[c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2];
const union=bs=>[Math.min(...bs.map(b=>b[0])),Math.min(...bs.map(b=>b[1])),Math.max(...bs.map(b=>b[2])),Math.max(...bs.map(b=>b[3]))];
const contains=(a,b)=>a[0]<=b[0]+1e-9&&a[1]<=b[1]+1e-9&&a[2]+1e-9>=b[2]&&a[3]+1e-9>=b[3];
const freeze=v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
const q=t=>{t=clamp(t);return t*t*t*(10+t*(-15+6*t));};
const dq=t=>t<=0||t>=1?0:30*t*t*(1-t)*(1-t);
const ddq=t=>t<=0||t>=1?0:60*t*(1-t)*(1-2*t);
const zero=()=>({longitudeDegreesPerSecond:0,latitudeDegreesPerSecond:0,logWidthPerSecond:0,logHeightPerSecond:0});
function geographicRecords(value){
 if(!value)return[];
 if(Array.isArray(value))return value.flatMap(geographicRecords);
 if(value.type==='FeatureCollection')return value.features.flatMap(geographicRecords);
 if(value.type==='GeometryCollection')return value.geometries.flatMap(geographicRecords);
 return[value];
}
function geographicBounds(value){return geographicRecords(value).map(geometryBounds);}
function textCount(text){return [...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text??'')].length;}
function safeContract(output,safe){
 if(!Array.isArray(output)||output.length!==2||output.some(x=>!Number.isFinite(x)||x<=0))throw Error('CAMERA_CANONICAL_OUTPUT_REQUIRED');
 if(!Array.isArray(safe)||safe.length!==4||safe.some(x=>!Number.isFinite(x))||safe[0]<0||safe[1]<0||safe[2]>output[0]||safe[3]>output[1]||safe[0]>=safe[2]||safe[1]>=safe[3])throw Error('CAMERA_SAFE_AREA_REQUIRED');
 return{canonicalOutput:[...output],safeArea:[...safe],padding:Math.max(output[0]/(safe[2]-safe[0]),output[1]/(safe[3]-safe[1]))};
}
function fit(bounds,display){
 return fitGeographicExtent(bounds,{output:display.canonicalOutput,padding:display.padding});
}
function noCloser(bounds,limit){const a=size(bounds),b=size(limit);return box(center(bounds),[Math.max(a[0],b[0]),Math.max(a[1],b[1])]);}
function profileFrom(overrides={}){
 for(const key of Object.keys(overrides))if(!(key in CAMERA_DIRECTOR_V4_PROFILE))throw Error(`CAMERA_PROFILE_UNKNOWN_FIELD: ${key}`);
 const profile={...CAMERA_DIRECTOR_V4_PROFILE,...overrides};
 for(const [key,value]of Object.entries(profile))if(typeof CAMERA_DIRECTOR_V4_PROFILE[key]==='number'&&(!Number.isFinite(value)||value<=0))throw Error(`CAMERA_PROFILE_POSITIVE_REQUIRED: ${key}`);
 if(!Number.isInteger(profile.fps)||profile.maximumProgressBias>=.5||profile.accelerationFraction+profile.guidedFraction+profile.decelerationFraction>=1)throw Error('CAMERA_PROFILE_MOTION_PHASE_CONTRACT');
 if(profile.projection!==CAMERA_DIRECTOR_V4_PROFILE.projection||profile.holdDrift!==false)throw Error('CAMERA_PROJECTION_AND_FIXED_HOLD_PROTECTED');
 return profile;
}

/** Scene/data contract: verified geometry and text are consumed, never invented. */
export function compileCameraIntent(scene={}){
 if(typeof scene.primary_region_id!=='string'||!scene.primary_region_id)throw Error('CAMERA_PRIMARY_REGION_ID_REQUIRED');
 if(!scene.primary_geometry)throw Error('CAMERA_PRIMARY_GEOMETRY_REQUIRED');
 const primaryBounds=union(geographicBounds(scene.primary_geometry));
 if(!extentOK(primaryBounds))throw Error('CAMERA_PRIMARY_REGION_AREA_REQUIRED');
 if(!pointOK(scene.event_anchor))throw Error('CAMERA_EVENT_GEOGRAPHIC_ANCHOR_REQUIRED');
 if(!extentOK(scene.approved_final_extent))throw Error('CAMERA_APPROVED_FINAL_EXTENT_REQUIRED');
 const display=safeContract(scene.canonical_output??[1080,1920],scene.safe_area??[48,72,1032,1848]);
 const admissionSource=scene.scale_admission?.localDetail??scene.scale_admission??{};
 const admission=admissionSource.admission??admissionSource;
 const safeClosest=admissionSource.safeClosest??scene.scale_admission?.safeClosest;
 const status=admission.status??'LOCAL_NOT_ADMITTED';
 const requested=scene.desired_detail_level??'REGIONAL';
 if(!['CONTINENT','REGIONAL','LOCAL'].includes(requested))throw Error('CAMERA_SUPPORTED_DETAIL_LEVEL_REQUIRED');
 let finalBounds=[...scene.approved_final_extent],effective='REGIONAL';
 if(requested==='LOCAL'&&status==='LOCAL_ADMITTED'){
  const admitted=scene.admitted_local_extent??admission.admittedExtent??admission.requestedExtent;
  if(!extentOK(admitted)||admission.renderLocal===false)throw Error('CAMERA_ADMITTED_LOCAL_EXTENT_REQUIRED');
  finalBounds=[...admitted];effective='LOCAL';
 }else if(safeClosest?.bounds&&!eq(safeClosest.bounds,scene.approved_final_extent)){
  throw Error('CAMERA_APPROVED_STOP_AND_SAFE_CLOSEST_MISMATCH');
 }
 const eventBounds=geographicBounds(scene.event_geometry);
 const anchorBounds=[scene.event_anchor[0],scene.event_anchor[1],scene.event_anchor[0],scene.event_anchor[1]];
 const relations=geographicBounds(scene.context_geometry);
 if(scene.context_extent!==undefined){if(!extentOK(scene.context_extent))throw Error('CAMERA_CONTEXT_EXTENT_REQUIRED');relations.push([...scene.context_extent]);}
 if(scene.start_extent!==undefined&&!extentOK(scene.start_extent))throw Error('CAMERA_START_EXTENT_REQUIRED');
 const relationBounds=union([primaryBounds,anchorBounds,...eventBounds,...relations]);
 const primaryFit=fit(primaryBounds,display);
 const start=noCloser(scene.start_extent?[...scene.start_extent]:primaryFit,finalBounds);
 // Context is unnecessary if all required space is already readable in the safe
 // rectangle, regardless of the presence or absence of sea or relation records.
 const contextFit=fit(relationBounds,display);
 const safeViewport=b=>{
  const s=size(b),[w,h]=display.canonicalOutput,a=display.safeArea;
  return[b[0]+a[0]/w*s[0],b[3]-a[3]/h*s[1],b[0]+a[2]/w*s[0],b[3]-a[1]/h*s[1]];
 };
 const needsContext=!contains(safeViewport(start),relationBounds);
 // A context move never narrows either dimension of the recognition view.
 const context=needsContext?noCloser(contextFit,start):[...start];
 if(!extentOK(start)||!extentOK(context)||!extentOK(finalBounds))throw Error('CAMERA_GEOGRAPHIC_EXTENT_OUT_OF_RANGE');
 if(!contains(finalBounds,anchorBounds))throw Error('CAMERA_EVENT_ANCHOR_OUTSIDE_APPROVED_FINAL');
 return freeze({version:CAMERA_INTENT_V4_VERSION,primaryRegionId:scene.primary_region_id,
  primaryGeometry:copy(scene.primary_geometry),primaryBounds,anchor:[...scene.event_anchor],
  eventGeometry:copy(scene.event_geometry??null),contextGeometry:copy(scene.context_geometry??null),
  texts:{eventTitle:scene.event_title??'',locationLabel:scene.location_label??'',primaryLabel:scene.primary_label??''},
  display,requestedScale:requested,effectiveScale:effective,approvedFinalExtent:[...scene.approved_final_extent],
  finalExtent:finalBounds,startExtent:start,contextExtent:context,
  context:{required:needsContext,requiredGeometryBounds:relationBounds,
   basis:'Actual region, event and relation geometry fitted to canonical safe area',
   condition:'Required geometry is not contained by starting safe viewport'},
  admission:{status,requestedScale:requested,effectiveScale:effective,localUsed:effective==='LOCAL',
   localRejected:requested==='LOCAL'&&effective!=='LOCAL',
   localPermitted:status==='LOCAL_ADMITTED',regionalStopBounds:[...scene.approved_final_extent],
   stopBounds:[...finalBounds],safeClosestStatus:safeClosest?.status??'APPROVED_FIXED_STOP',
   diagnosticCategory:'DATA_ADMISSION'},
 });
}

function travelMetrics(from,to){
 const a=center(from),b=center(to),s0=size(from),s1=size(to);
 const pan=Math.hypot((b[0]-a[0])/Math.max(s0[0],s1[0]),(b[1]-a[1])/Math.max(s0[1],s1[1]));
 const zoom=Math.hypot(Math.log(s1[0]/s0[0]),Math.log(s1[1]/s0[1]))/Math.SQRT2;
 const sum=pan+zoom;
 return{normalizedPan:pan,logSpan:zoom,panWeight:sum?pan/sum:0,zoomWeight:sum?zoom/sum:0,
  geographicCenterDelta:[b[0]-a[0],b[1]-a[1]],logSpanDelta:s0.map((v,i)=>Math.log(s1[i]/v))};
}

/** Compile CameraPlan before RevealPlan. Perception budgets slow motion once. */
export function compileReferenceCameraPlan({scene,intent=null,profile:overrides={},seed=0}={}){
 if(!Number.isInteger(seed))throw Error('CAMERA_INTEGER_SEED_REQUIRED');
 const request=intent??compileCameraIntent(scene);
 if(request.version!==CAMERA_INTENT_V4_VERSION)throw Error('CAMERA_INTENT_VERSION_REQUIRED');
 const profile=profileFrom(overrides),fps=profile.fps,frames=s=>Math.max(1,Math.round(s*fps));
 const timeline=[],add=(state,count,details={})=>{
  const startFrame=timeline.length?timeline.at(-1).endFrame:0;
  const entry={state,key:state,startFrame,endFrame:startFrame+count,durationFrames:count,
   startSeconds:startFrame/fps,endSeconds:(startFrame+count)/fps,...details};timeline.push(entry);return entry;
 };
 const recognition=add('PRIMARY_RECOGNITION',frames(profile.recognitionSeconds),{motion:'FIXED',scale:'REGIONAL_CONTEXT'});
 const trajectories=[];
 const expansionMetric=travelMetrics(request.startExtent,request.contextExtent);
 let expansion=null;
 if(request.context.required){
  const duration=profile.expansionBaseSeconds+expansionMetric.logSpan*profile.expansionSecondsPerLogSpan+expansionMetric.normalizedPan*profile.approachSecondsPerNormalizedPan;
  expansion=add('CONTEXT_EXPANSION',Math.max(8,frames(duration)),{motion:'PAN_AND_LOG_EXTENT',scale:'CONTEXT'});
  trajectories.push({kind:'CONTEXT_EXPANSION',startFrame:expansion.startFrame,endFrame:expansion.endFrame,
   from:[...request.startExtent],to:[...request.contextExtent],metrics:expansionMetric,panBias:0,zoomBias:0});
 }
 const relation=add('RELATION_HOLD',frames(profile.relationSeconds),{motion:'FIXED',scale:'CONTEXT'});
 const approachMetric=travelMetrics(request.contextExtent,request.finalExtent);
 const primarySeconds=request.texts.primaryLabel?Math.max(profile.primaryPerceptionSeconds,textCount(request.texts.primaryLabel)/profile.readingGraphemesPerSecond):0;
 const locationSeconds=request.texts.locationLabel?Math.max(profile.locationPerceptionSeconds,textCount(request.texts.locationLabel)/profile.readingGraphemesPerSecond):profile.locationPerceptionSeconds;
 const geometricSeconds=profile.approachBaseSeconds+approachMetric.logSpan*profile.approachSecondsPerLogSpan+approachMetric.normalizedPan*profile.approachSecondsPerNormalizedPan;
 const approachSeconds=Math.max(geometricSeconds,primarySeconds+locationSeconds+profile.minimumFineApproachSeconds);
 const approachFrames=Math.max(12,frames(approachSeconds));
 const accelerateCount=Math.max(2,Math.round(approachFrames*profile.accelerationFraction));
 const guidedCount=Math.max(2,Math.round(approachFrames*profile.guidedFraction));
 const decelerateCount=Math.max(2,Math.round(approachFrames*profile.decelerationFraction));
 const fineCount=approachFrames-accelerateCount-guidedCount-decelerateCount;
 if(fineCount<2)throw Error('CAMERA_FINE_APPROACH_PHASE_REQUIRED');
 const approach=add('EVENT_APPROACH',accelerateCount,{motion:'ACCELERATE',scale:'CONTEXT_TO_EVENT'});
 const guided=add('GUIDED_REVEAL',guidedCount,{motion:'TRAVEL_WITH_READABILITY_BUDGET',scale:'CONTEXT_TO_EVENT'});
 const decelerate=add('DECELERATE',decelerateCount,{motion:'GUIDED_DECELERATION',scale:'CONTEXT_TO_EVENT'});
 const framing=add('EVENT_FRAMING',fineCount,{motion:'FINE_APPROACH',scale:request.effectiveScale});
 // Bias comes from normalized spatial travel, never topic, label or fixture time.
 const bias=profile.maximumProgressBias*(approachMetric.panWeight+Math.min(1,approachMetric.normalizedPan))*.5;
 const trajectory={kind:'EVENT_APPROACH',startFrame:approach.startFrame,endFrame:framing.endFrame,
  from:[...request.contextExtent],to:[...request.finalExtent],metrics:approachMetric,
  panBias:bias,zoomBias:-bias};trajectories.push(trajectory);
 const settle=add('SETTLE',frames(profile.settleSeconds),{motion:'FIXED',scale:request.effectiveScale});
 const lock=add('LOCK',frames(profile.lockSeconds),{motion:'FIXED',scale:request.effectiveScale});
 const title=add('EVENT_TITLE',request.texts.eventTitle?frames(profile.titleEntrySeconds):1,{motion:'FIXED',scale:request.effectiveScale});
 const titlePerception=request.texts.eventTitle?Math.max(profile.minimumTitlePerceptionSeconds,textCount(request.texts.eventTitle)/profile.readingGraphemesPerSecond):profile.locationPerceptionSeconds;
 const hold=add('PERCEPTION_HOLD',frames(titlePerception),{motion:'FIXED',scale:request.effectiveScale});
 const next=add('NEXT',frames(profile.nextSeconds),{motion:'FIXED',scale:request.effectiveScale});
 return freeze({version:CAMERA_DIRECTOR_V4_VERSION,kind:'GEOGRAPHIC_CAMERA_PLAN_ONLY',fps,seed,
  canonicalOutput:[...request.display.canonicalOutput],profile,intent:request,totalFrames:next.endFrame,
  durationSeconds:next.endFrame/fps,anchor:[...request.anchor],target:{intent:'EVENT_LOCATION',geometryIds:[request.primaryRegionId],effectiveScale:request.effectiveScale},
  timeline,trajectories,context:{...copy(request.context),startExtent:[...request.startExtent],framedExtent:[...request.contextExtent],
   expansionStartFrame:expansion?.startFrame??null,expansionEndFrame:expansion?.endFrame??null,relationStartFrame:relation.startFrame,relationEndFrame:relation.endFrame},
  motion:{startFrame:approach.startFrame,endFrame:framing.endFrame,arrivalFrame:framing.endFrame-1,
   startBounds:[...request.contextExtent],endBounds:[...request.finalExtent],singleTrajectory:true,
   interpolation:'GEOGRAPHIC_CENTER_AND_LOG_EXTENT_WITH_DATA_DERIVED_C2_PAN_ZOOM_PROGRESS',
   phaseCurveResets:false,noCloserThanApprovedStop:true,panWeight:approachMetric.panWeight,
   zoomWeight:approachMetric.zoomWeight,progressBias:bias,metrics:approachMetric},
  perception:{primarySeconds,locationSeconds,titleSeconds:titlePerception,
   ownership:'Camera compiler reserves readability budgets; RevealPlan reads immutable motion',
   guidedStartFrame:guided.startFrame,guidedEndFrame:decelerate.endFrame},
  projection:{name:profile.projection,policy:'ONE_CONTINUOUS_GEOGRAPHIC_MAP_SPACE',changeCount:0},
  admission:copy(request.admission),primaryMaterial:{factor:1,animated:false,policy:'ALWAYS_ON_FROM_FRAME_0'},
  hold:{startFrame:hold.startFrame,endFrame:hold.endFrame,drift:false},
  checkpoints:{PRIMARY_START:recognition.startFrame,CONTEXT:relation.startFrame+Math.floor(relation.durationFrames/2),
   EVENT_APPROACH:guided.startFrame,REGIONAL_LOCK:lock.endFrame-1,
   EVENT_TITLE:title.endFrame-1,FINAL_HOLD:hold.startFrame+Math.floor(hold.durationFrames/2)},
  protections:{visualSource:'UNCHANGED',gis:'UNCHANGED',scale:'UNCHANGED',localAdmission:'UNCHANGED',
   finalFraming:'EXACT_APPROVED_INPUT',cameraAndRevealOwnership:'SEPARATE',seedUse:'DETERMINISTIC_NO_JITTER'},
 });
}

function progression(t,bias,seconds){
 const warped=t+bias*t*(1-t),first=1+bias*(1-2*t),second=-2*bias;
 return{value:q(warped),velocity:dq(warped)*first/seconds,
  acceleration:(ddq(warped)*first*first+dq(warped)*second)/(seconds*seconds)};
}
function poseFromTrajectory(trajectory,frame,fps){
 const count=trajectory.endFrame-trajectory.startFrame-1,t=clamp((frame-trajectory.startFrame)/count),seconds=count/fps;
 const pan=progression(t,trajectory.panBias,seconds),zoom=progression(t,trajectory.zoomBias,seconds);
 const a=center(trajectory.from),b=center(trajectory.to),s0=size(trajectory.from),s1=size(trajectory.to);
 const delta=a.map((v,i)=>b[i]-v),logDelta=s0.map((v,i)=>Math.log(s1[i]/v));
 const c=a.map((v,i)=>v+delta[i]*pan.value),s=s0.map((v,i)=>Math.exp(Math.log(v)+logDelta[i]*zoom.value));
 const extent=t===0?[...trajectory.from]:t===1?[...trajectory.to]:box(c,s);
 return{bounds:extent,center:t===0?a:t===1?b:c,progress:t,panProgress:pan.value,zoomProgress:zoom.value,
  velocity:{longitudeDegreesPerSecond:delta[0]*pan.velocity,latitudeDegreesPerSecond:delta[1]*pan.velocity,
   logWidthPerSecond:logDelta[0]*zoom.velocity,logHeightPerSecond:logDelta[1]*zoom.velocity},
  acceleration:{longitudeDegreesPerSecondSquared:delta[0]*pan.acceleration,latitudeDegreesPerSecondSquared:delta[1]*pan.acceleration,
   logWidthPerSecondSquared:logDelta[0]*zoom.acceleration,logHeightPerSecondSquared:logDelta[1]*zoom.acceleration}};
}
function staticPose(bounds){return{bounds:[...bounds],center:center(bounds),progress:0,panProgress:0,zoomProgress:0,velocity:zero(),
 acceleration:{longitudeDegreesPerSecondSquared:0,latitudeDegreesPerSecondSquared:0,logWidthPerSecondSquared:0,logHeightPerSecondSquared:0}};}
function projected(point,pose,output){const s=size(pose.bounds);return[(point[0]-pose.bounds[0])/s[0]*output[0],(pose.bounds[3]-point[1])/s[1]*output[1]];}
function pointSpeed(point,pose,output){
 const s=size(pose.bounds),c=pose.center,v=pose.velocity;
 const x=output[0]/s[0]*(-v.longitudeDegreesPerSecond-(point[0]-c[0])*v.logWidthPerSecond);
 const y=output[1]/s[1]*(v.latitudeDegreesPerSecond+(point[1]-c[1])*v.logHeightPerSecond);
 return{xPixelsPerSecond:x,yPixelsPerSecond:y,pixelsPerSecond:Math.hypot(x,y)};
}

/** Random-access integer frame evaluation: no stateful integration or clock. */
export function evaluateReferenceCameraFrame(plan,frame){
 if(plan?.version!==CAMERA_DIRECTOR_V4_VERSION)throw Error('CAMERA_REFERENCE_PLAN_VERSION_REQUIRED');
 if(!Number.isInteger(frame)||frame<0||frame>=plan.totalFrames)throw Error('CAMERA_REFERENCE_FRAME_OUT_OF_RANGE');
 const segment=plan.timeline.find(s=>frame>=s.startFrame&&frame<s.endFrame);
 const active=plan.trajectories.find(t=>frame>=t.startFrame&&frame<t.endFrame);
 let pose;
 if(active)pose=poseFromTrajectory(active,frame,plan.fps);
 else if(frame<plan.motion.startFrame)pose=staticPose(frame<(plan.context.expansionStartFrame??0)?plan.intent.startExtent:plan.intent.contextExtent);
 else pose=staticPose(plan.intent.finalExtent);
 // Recognition before an expansion starts is exactly the starting extent.
 if(segment.state==='PRIMARY_RECOGNITION')pose=staticPose(plan.intent.startExtent);
 const final=frame>=plan.motion.endFrame,lock=plan.timeline.find(s=>s.state==='LOCK');
 const from=size(plan.intent.contextExtent),to=size(plan.intent.finalExtent),current=size(pose.bounds);
 const denominator=Math.log(from[0]/to[0]);
 const sizeProgress=denominator>1e-9?clamp(Math.log(from[0]/current[0])/denominator):1;
 const bounds=plan.intent.primaryBounds,pa=projected([bounds[0],bounds[3]],pose,plan.canonicalOutput),pb=projected([bounds[2],bounds[1]],pose,plan.canonicalOutput);
 const primaryBox=[pa[0],pa[1],pb[0],pb[1]],anchor=projected(plan.anchor,pose,plan.canonicalOutput),safe=plan.intent.display.safeArea;
 const anchorInSafe=anchor[0]>=safe[0]&&anchor[0]<=safe[2]&&anchor[1]>=safe[1]&&anchor[1]<=safe[3];
 const primarySpeed=pointSpeed(center(bounds),pose,plan.canonicalOutput),eventSpeed=pointSpeed(plan.anchor,pose,plan.canonicalOutput);
 const metric=active?.metrics??(final?plan.motion.metrics:travelMetrics(plan.intent.startExtent,plan.intent.contextExtent));
 return{version:CAMERA_DIRECTOR_V4_VERSION,frame,timeSeconds:frame/plan.fps,state:segment.state,stateKey:segment.key,
  stateFrame:frame-segment.startFrame,stateProgress:(frame-segment.startFrame)/Math.max(1,segment.durationFrames-1),
  scale:final?plan.intent.effectiveScale:'CONTINENT',projection:plan.projection.name,target:'EVENT_LOCATION',
  targetGeometryIds:[plan.intent.primaryRegionId],center:[...pose.center],extent:[...pose.bounds],
  geographicCenter:[...pose.center],geographicExtent:[...pose.bounds],velocity:pose.velocity,acceleration:pose.acceleration,
  easingProgress:sizeProgress,motionProgress:pose.progress,panProgress:pose.panProgress,zoomProgress:pose.zoomProgress,
  panWeight:metric.panWeight,zoomWeight:metric.zoomWeight,
  screenVelocity:{primary:primarySpeed,event:eventSpeed,pixelsPerSecond:Math.max(primarySpeed.pixelsPerSecond,eventSpeed.pixelsPerSecond)},
  projectedRegion:{box:primaryBox,width:pb[0]-pa[0],height:pb[1]-pa[1],area:(pb[0]-pa[0])*(pb[1]-pa[1]),
   visible:primaryBox[0]<plan.canonicalOutput[0]&&primaryBox[2]>0&&primaryBox[1]<plan.canonicalOutput[1]&&primaryBox[3]>0,
   fitsSafe:primaryBox[0]>=safe[0]&&primaryBox[1]>=safe[1]&&primaryBox[2]<=safe[2]&&primaryBox[3]<=safe[3]},
  projectedAnchor:{position:anchor,inFrame:anchor[0]>=0&&anchor[0]<=plan.canonicalOutput[0]&&anchor[1]>=0&&anchor[1]<=plan.canonicalOutput[1],inSafe:anchorInSafe},
  settle:{phase:segment.state,settled:frame>=lock.startFrame,locked:frame>=lock.startFrame},
  camera:{flatBounds:[...pose.bounds],noCloserThanApprovedStop:true},cameraLocked:final,
  primaryMaterial:1,admission:copy(plan.admission),geographicAnchor:[...plan.anchor],
  layoutLocked:final,transition:{active:false,method:'NONE',mix:0},
 };
}
