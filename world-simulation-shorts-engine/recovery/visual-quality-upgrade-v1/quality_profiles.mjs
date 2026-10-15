/** Bounded visual variants and data-driven camera candidates. No place or event inference. */
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame,assessReferenceCameraMotion}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,geoToPresentationScreen}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {evaluateNationalUnitBadgeLayout} from '../../web/map_infographic_v1/national_unit_badge_v1.mjs';

const clone=value=>structuredClone(value),span=b=>[b[2]-b[0],b[3]-b[1]],
 center=b=>[(b[0]+b[2])/2,(b[1]+b[3])/2],inside=(a,b)=>a[0]<=b[0]+1e-8&&a[1]<=b[1]+1e-8&&a[2]>=b[2]-1e-8&&a[3]>=b[3]-1e-8,
 smooth=t=>t*t*(3-2*t),mean=points=>points.reduce((out,p)=>[out[0]+p[0]/points.length,out[1]+p[1]/points.length],[0,0]);

export function qualityProfile(letter){
 if(!['A','B','C','D','E','F'].includes(letter))throw Error('QUALITY_EXPLICIT_PROFILE_A_TO_F_REQUIRED');
 return Object.freeze({profile:letter,boundary:letter==='B'||letter==='F',
  territory:letter==='C'||letter==='F',frontierAudit:letter==='D'||letter==='F',
  camera:letter==='E'||letter==='F',screenFeatherPixels:32,
  territoryProfile:Object.freeze({minimumAlpha:.72,maximumAlpha:.82,opacityGain:1.1}),
  frontierChanged:false,frontierReason:'EXISTING_PROFILE_AT_APPROVED_CENTER_ALPHA_WIDTH_AND_HALO_LIMITS_NO_CONFIRMED_SYNCHRONIZATION_DEFECT'});
}

function plans(scene,baseCameraPlan,currentNativeFrame){
 const totalFrames=scene.controlIntent.total_frames,fps=scene.controlIntent.fps;
 return {track:compileReferenceCameraTrack({baseCameraPlan,currentNativeFrame,keyframes:scene.cameraKeyframes,totalFrames,fps}),
  presentation:compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
   totalFrames,fps,overscan:scene.presentationProfile.overscan,width:1080,height:1920})};
}
function cameraSample(track,presentation,frame){
 const camera=evaluateReferenceCameraTrackFrame(track,frame),state=evaluateReferencePresentationFrame(presentation,frame),
  expanded=expandNativeBounds({bounds:camera.flatBounds,referenceStartBounds:track.startBounds,
   rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true});
 return {camera,state,expanded};
}
function frontSamples(scene){
 const territory=compileTerritoryControlPlan(scene.controlIntent);
 return Array.from({length:territory.totalFrames},(_,frame)=>{
  const controls=evaluateTerritoryControlFrame(territory,territory.startFrame+frame);
  return controls.longitudinalKnots.map((x,i)=>[x,controls.boundaryLatitudes[i]])
   .filter(point=>classifyControlPoint(controls,point).inDomain);
 });
}
function assess(scene,baseCameraPlan,currentNativeFrame,safeArea,fronts){
 const {track,presentation}=plans(scene,baseCameraPlan,currentNativeFrame),samples=[],points=[],
  motion=assessReferenceCameraMotion(track);let focusError=0,frontWidth=0,frontFrames=0,
  minimumFrontMargin=Infinity,safeAreaViolations=0,criticalCollisions=0;
 for(let frame=0;frame<track.totalFrames;frame++){
  const sample=cameraSample(track,presentation,frame),project=point=>geoToPresentationScreen(point,sample.expanded,sample.state);
  samples.push(sample);
  const front=fronts[frame].map(project);
  if(front.length){
   const focal=mean(front),target=[(safeArea[0]+safeArea[2])/2,(safeArea[1]+safeArea[3])/2];
   focusError+=Math.hypot(focal[0]-target[0],focal[1]-target[1])**2;
   frontWidth+=Math.max(...front.map(p=>p[0]))-Math.min(...front.map(p=>p[0]));frontFrames++;
   minimumFrontMargin=Math.min(minimumFrontMargin,...front.flatMap(p=>[p[0],1080-p[0],p[1],1920-p[1]]));
  }
  const units=evaluateNationalUnitBadgeLayout(scene.combatProfile.units,frame,{project,protectedGraphics:[],safeArea});
  safeAreaViolations+=units.safeAreaViolations.length;criticalCollisions+=units.criticalCollisions.length;
  if(scene.cameraKeyframes.some(k=>k.frame===frame))points.push({frame,activeLandFrontSamples:front.length,
   frontScreenMean:front.length?mean(front):null,referenceCenter:sample.camera.center,
   referenceExtent:sample.camera.extent,nativeExpandedBounds:sample.expanded});
 }
 return {track,presentation,samples,motion,summary:{frontFocusRmsPixels:Math.sqrt(focusError/Math.max(1,frontFrames)),
  meanFrontWidthPixels:frontWidth/Math.max(1,frontFrames),minimumFrontMarginPixels:minimumFrontMargin,
  safeAreaViolations,criticalCollisions,points,motion}};
}

/** Camera core and event timing remain frozen. Only a new scene-owned framing candidate is emitted. */
export function selectQualityCamera({scenePlan,baseCameraPlan,currentNativeFrame,safeArea,inheritedNativeBounds}={}){
 const scene=clone(scenePlan),before=JSON.stringify(scenePlan),fronts=frontSamples(scene),
  baseline=assess(scene,baseCameraPlan,currentNativeFrame,safeArea,fronts),
  envelope=[Math.min(...baseline.samples.map(s=>s.expanded[0])),Math.min(...baseline.samples.map(s=>s.expanded[1])),
   Math.max(...baseline.samples.map(s=>s.expanded[2])),Math.max(...baseline.samples.map(s=>s.expanded[3]))],
  floor=span(inheritedNativeBounds),target=[(safeArea[0]+safeArea[2])/2,(safeArea[1]+safeArea[3])/2],candidates=[];
 for(const [zoom,centering] of [[1.04,.25],[1.08,.4],[1.12,.55]]){
  const candidate=clone(scene);
  candidate.cameraKeyframes=scene.cameraKeyframes.map(key=>{
   if(key.frame===0)return clone(key);
   const progress=smooth(key.frame/(scene.controlIntent.total_frames-1)),size=span(key.bounds).map(v=>v/(1+(zoom-1)*progress)),
    c=center(key.bounds),bounds=[c[0]-size[0]/2,c[1]-size[1]/2,c[0]+size[0]/2,c[1]+size[1]/2],
    state=evaluateReferencePresentationFrame(baseline.presentation,key.frame),expanded=expandNativeBounds({bounds,
     referenceStartBounds:baseline.track.startBounds,rollDegrees:state.rollDegrees,overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true}),
    points=fronts[key.frame].map(p=>geoToPresentationScreen(p,expanded,state)),focal=points.length?mean(points):target;
   const shift=[(focal[0]-target[0])/1080*size[0]*centering*progress,
    (target[1]-focal[1])/1920*size[1]*centering*progress];
   return {...key,bounds:[bounds[0]+shift[0],bounds[1]+shift[1],bounds[2]+shift[0],bounds[3]+shift[1]]};
  });
  const result=assess(candidate,baseCameraPlan,currentNativeFrame,safeArea,fronts),summary=result.summary,
   nativeFloorRespected=result.samples.every(s=>span(s.expanded).every((v,i)=>v>=floor[i]-1e-9)),
   originalNativeEnvelopeRespected=result.samples.every(s=>inside(envelope,s.expanded)),
   continuity=summary.motion.maximumCenterStepPixels<=Math.max(1080*.008,baseline.motion.maximumCenterStepPixels*1.5),
   admitted=nativeFloorRespected&&originalNativeEnvelopeRespected&&continuity&&summary.safeAreaViolations===0
    &&summary.criticalCollisions===0&&summary.minimumFrontMarginPixels>=Math.min(48,baseline.summary.minimumFrontMarginPixels)
    &&summary.frontFocusRmsPixels<baseline.summary.frontFocusRmsPixels*.95
    &&summary.meanFrontWidthPixels>baseline.summary.meanFrontWidthPixels*1.02;
  candidates.push({zoom,centering,admitted,nativeFloorRespected,originalNativeEnvelopeRespected,continuity,summary,
   cameraKeyframes:candidate.cameraKeyframes});
 }
 const selected=candidates.find(candidate=>candidate.admitted);
 if(selected)scene.cameraKeyframes=clone(selected.cameraKeyframes);
 if(JSON.stringify(scenePlan)!==before)throw Error('QUALITY_PROTECTED_SCENE_MUTATED');
 return {scenePlan:scene,changed:Boolean(selected),decision:selected?'BOUNDED_FRONT_FOLLOW_DETAIL_SELECTED':'USE_PROTECTED_CAMERA_NO_SAFE_IMPROVEMENT',
  selected:selected?{zoom:selected.zoom,centering:selected.centering,summary:selected.summary}:null,
  baseline:baseline.summary,candidates,originalNativeEnvelope:envelope,inheritedNativeFloor:clone(inheritedNativeBounds),
  actualGpuVisualQualityVerified:false,cameraV5SourceChanged:false,eventTimingChanged:false,unitGeometryChanged:false};
}
