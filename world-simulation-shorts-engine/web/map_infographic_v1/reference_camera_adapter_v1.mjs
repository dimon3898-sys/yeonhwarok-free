/** External reference framing track. V5 and native projection remain read-only owners. */
import {evaluateMinimumContextCameraFrame} from './camera_director_v5.mjs';
import {freezeEventData} from './event_contract_v1.mjs';

export const REFERENCE_CAMERA_ADAPTER_V1_VERSION='REFERENCE_CAMERA_ADAPTER_V1';
const known=new WeakSet(),copy=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],spans=b=>[b[2]-b[0],b[3]-b[1]];
const pose=b=>[...center(b),...spans(b).map(Math.log)];
function integer(value,label,minimum=0){
 if(!Number.isSafeInteger(value)||value<minimum)throw Error(`REFERENCE_CAMERA_${label}_INTEGER_REQUIRED`);
 return value;
}
function bounds(value,label){
 if(!Array.isArray(value)||value.length!==4||!value.every(Number.isFinite)
  ||value[0]>=value[2]||value[1]>=value[3]||value[0]<-180||value[2]>180||value[1]<-90||value[3]>90)
  throw Error(`REFERENCE_CAMERA_${label}_GEOGRAPHIC_BOUNDS_REQUIRED`);
 return [...value];
}

// Shape-preserving shared slopes: a reference excerpt can begin and end while
// the camera is moving. No arrival/settle/lock state is manufactured here.
function tangent(values,times,index,axis){
 const last=values.length-1;
 if(index===0)return(values[1][axis]-values[0][axis])/(times[1]-times[0]);
 if(index===last)return(values[last][axis]-values[last-1][axis])/(times[last]-times[last-1]);
 const before=times[index]-times[index-1],after=times[index+1]-times[index];
 const left=(values[index][axis]-values[index-1][axis])/before;
 const right=(values[index+1][axis]-values[index][axis])/after;
 if(left===0||right===0||Math.sign(left)!==Math.sign(right))return 0;
 const a=2*after+before,b=after+2*before;
 return(a+b)/(a/left+b/right);
}
function compileSegments(keyframes,fps){
 const values=keyframes.map(k=>pose(k.bounds)),times=keyframes.map(k=>k.frame/fps);
 const slopes=values.map((_,i)=>values[0].map((__,axis)=>tangent(values,times,i,axis)));
 return keyframes.slice(1).map((key,index)=>{
  const duration=times[index+1]-times[index];
  return{startFrame:keyframes[index].frame,endFrame:key.frame,startSeconds:times[index],
   durationSeconds:duration,from:[...values[index]],to:[...values[index+1]],
   startVelocity:[...slopes[index]],endVelocity:[...slopes[index+1]],
   coefficients:values[index].map((a,axis)=>{
    const delta=values[index+1][axis]-a,v0=slopes[index][axis]*duration,v1=slopes[index+1][axis]*duration;
    return[a,v0,3*delta-2*v0-v1,-2*delta+v0+v1];
   })};
 });
}
function at(segment,seconds){
 const u=Math.max(0,Math.min(1,(seconds-segment.startSeconds)/segment.durationSeconds));
 const values=[],velocity=[],acceleration=[];
 for(const [a,b,c,d]of segment.coefficients){
  values.push(a+u*(b+u*(c+u*d)));
  velocity.push((b+u*(2*c+u*3*d))/segment.durationSeconds);
  acceleration.push((2*c+u*6*d)/(segment.durationSeconds*segment.durationSeconds));
 }
 if(u===0)return{values:[...segment.from],velocity:[...segment.startVelocity],acceleration};
 if(u===1)return{values:[...segment.to],velocity:[...segment.endVelocity],acceleration};
 return{values,velocity,acceleration};
}

/** Fixture owns measured framing keyframes; this module contains no subject inference. */
export function compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes,
 totalFrames,fps=baseCameraPlan?.fps}={}){
 integer(totalFrames,'TOTAL_FRAMES',2);integer(fps,'FPS',1);integer(currentNativeFrame,'BASE_FRAME');
 if(baseCameraPlan?.directorVersion!=='CAMERA_DIRECTOR_V5'||baseCameraPlan?.fps!==fps
  ||!Number.isSafeInteger(baseCameraPlan.totalFrames)||currentNativeFrame>=baseCameraPlan.totalFrames)
  throw Error('REFERENCE_CAMERA_ACTUAL_V5_INPUT_REQUIRED');
 const original=copy(baseCameraPlan),baseCameraState=copy(evaluateMinimumContextCameraFrame(original,currentNativeFrame));
 if(!Array.isArray(keyframes)||keyframes.length<2)throw Error('REFERENCE_CAMERA_KEYFRAMES_REQUIRED');
 const keys=keyframes.map((key,index)=>({frame:integer(key?.frame,`KEY_${index}_FRAME`),
  bounds:bounds(key?.bounds,`KEY_${index}`)}));
 if(keys[0].frame!==0||keys.at(-1).frame!==totalFrames-1
  ||keys.some((key,index)=>index>0&&key.frame<=keys[index-1].frame))
  throw Error('REFERENCE_CAMERA_ORDERED_COMPLETE_INTEGER_KEYFRAMES_REQUIRED');
 const targetBounds=[...keys.at(-1).bounds],minimum=spans(targetBounds);
 if(keys.some(key=>spans(key.bounds).some((span,axis)=>span<minimum[axis]-1e-10)))
  throw Error('REFERENCE_CAMERA_FINAL_ENDPOINT_MUST_BE_CLOSEST');
 const plan={version:REFERENCE_CAMERA_ADAPTER_V1_VERSION,profile:'VISUAL_REFERENCE_STUDY',
  fps,totalFrames,durationSeconds:totalFrames/fps,keyframes:keys,segments:compileSegments(keys,fps),
  baseCameraPlan:original,currentNativeFrame,baseCameraState,
  startBounds:[...keys[0].bounds],targetBounds,targetFraming:{bounds:[...targetBounds]},
  interpolation:'SHARED_MONOTONE_CUBIC_CENTER_LOG_EXTENT_C1',
  admission:{survey:copy(baseCameraState.admission),visual:'STATIC_NATIVE_PROBE_REQUIRED',
   admitted:false,surveyModified:false},
  ownership:{camera:'EXTERNAL_REFERENCE_FRAMING_ADAPTER',v5:'READ_ONLY_FINAL_BASELINE',
   projection:'UNCHANGED_NATIVE_FACTORY_SCREEN',renderer:'UNCHANGED_NATIVE_FACTORY',
   eventOwnsCamera:false,wholeCountryFitRequired:false,arrivalReadinessForged:false,
   referenceExcerptMayStartMidMotion:true}};
 freezeEventData(plan);known.add(plan);
 for(let frame=0;frame<totalFrames;frame++)bounds(evaluateReferenceCameraTrackFrame(plan,frame).flatBounds,'INTERPOLATED');
 return plan;
}
export function assertReferenceCameraTrackPlan(plan){
 if(known.has(plan))return plan;
 if(plan?.version!==REFERENCE_CAMERA_ADAPTER_V1_VERSION)throw Error('REFERENCE_CAMERA_PLAN_VERSION_REQUIRED');
 const canonical=compileReferenceCameraTrack({baseCameraPlan:plan.baseCameraPlan,currentNativeFrame:plan.currentNativeFrame,
  keyframes:plan.keyframes,totalFrames:plan.totalFrames,fps:plan.fps});
 if(!same(canonical,plan))throw Error('REFERENCE_CAMERA_NON_CANONICAL_PLAN');
 return canonical;
}

/** Pure random-access framing; callers draw through the existing external native adapter. */
export function evaluateReferenceCameraTrackFrame(plan,frame){
 const p=assertReferenceCameraTrackPlan(plan);integer(frame,'FRAME');
 if(frame>=p.totalFrames)throw Error('REFERENCE_CAMERA_FRAME_OUT_OF_RANGE');
 const segment=p.segments.find(item=>frame<=item.endFrame)??p.segments.at(-1),
  sample=at(segment,frame/p.fps),c=sample.values.slice(0,2),s=sample.values.slice(2).map(Math.exp),
  exact=p.keyframes.find(key=>key.frame===frame),flatBounds=exact?[...exact.bounds]:
   [c[0]-s[0]/2,c[1]-s[1]/2,c[0]+s[0]/2,c[1]+s[1]/2],
  original=spans(p.baseCameraState.camera.flatBounds),actual=spans(flatBounds);
 return freezeEventData({version:REFERENCE_CAMERA_ADAPTER_V1_VERSION,frame,timeSeconds:frame/p.fps,
  state:'REFERENCE_CAMERA_TRACKING',flatBounds,center:center(flatBounds),extent:spans(flatBounds),
  camera:{flatBounds:[...flatBounds],noCloserThanApprovedStop:actual.every((span,i)=>span>=original[i]-1e-9)},
  cameraLocked:false,settle:{phase:'REFERENCE_CAMERA_TRACKING',settled:false,locked:false},
  velocity:{longitudeDegreesPerSecond:sample.velocity[0],latitudeDegreesPerSecond:sample.velocity[1],
   logWidthPerSecond:sample.velocity[2],logHeightPerSecond:sample.velocity[3]},
  acceleration:{longitudeDegreesPerSecondSquared:sample.acceleration[0],latitudeDegreesPerSecondSquared:sample.acceleration[1],
   logWidthPerSecondSquared:sample.acceleration[2],logHeightPerSecondSquared:sample.acceleration[3]},
  admission:copy(p.baseCameraState.admission),surveyAdmissionPreserved:true,
  visualAdmission:'STATIC_NATIVE_PROBE_REQUIRED',productionEligible:false,
  motionOwner:p.ownership.camera,eventCameraOwnership:false,sourceV5Unchanged:true});
}
export function assessReferenceCameraMotion(plan){
 const p=assertReferenceCameraTrackPlan(plan),samples=Array.from({length:p.totalFrames},(_,f)=>evaluateReferenceCameraTrackFrame(p,f));
 let maximumNormalizedCornerStep=0,maximumLogSpanStep=0,maximumCenterStepPixels=0;
 const output=p.baseCameraPlan.canonicalOutput;
 for(let frame=1;frame<samples.length;frame++){
  const a=samples[frame-1],b=samples[frame],size=spans(a.flatBounds);
  maximumNormalizedCornerStep=Math.max(maximumNormalizedCornerStep,...b.flatBounds.map((v,i)=>Math.abs(v-a.flatBounds[i])/size[i%2]));
  maximumLogSpanStep=Math.max(maximumLogSpanStep,...b.extent.map((v,i)=>Math.abs(Math.log(v/a.extent[i]))));
  maximumCenterStepPixels=Math.max(maximumCenterStepPixels,Math.hypot(...b.center.map((v,i)=>(v-a.center[i])/size[i]*output[i])));
 }
 return freezeEventData({status:'PASS',framesChecked:p.totalFrames,deterministicRandomAccess:true,
  positionContinuous:true,velocityContinuous:true,accelerationContinuity:'NOT_CLAIMED_C1_TRACK',
  sourceV5Unchanged:true,surveyAdmissionModified:false,fakeLockCount:0,
  exactKeyframes:p.keyframes.every(key=>same(samples[key.frame].flatBounds,key.bounds)),
  maximumNormalizedCornerStep,maximumLogSpanStep,maximumCenterStepPixels,
  visualQuality:'REQUIRES_ACTUAL_NATIVE_VIDEO_REVIEW',qualityParityClaimed:false});
}
