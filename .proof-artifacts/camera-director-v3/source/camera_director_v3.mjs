/** V3 changes material visibility and information reveal only. V2 owns motion. */
import {evaluateContinuousCameraFrame,cameraEase} from './camera_director_v2.mjs';
export const PRIMARY_COLOR_CAMERA_VERSION='CAMERA_DIRECTOR_V3';
const freeze=value=>{if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};

export function compilePrimaryColorCameraPlan(baseCameraPlan){
 if(baseCameraPlan?.version!=='CAMERA_DIRECTOR_V2')throw Error('V3 requires the approved V2 camera plan');
 const base=structuredClone(baseCameraPlan),stages=base.reveal.stages;
 const length=role=>{const s=stages.find(s=>s.role===role);if(!s)throw Error('Missing V2 reveal stage '+role);return s.durationFrames;};
 let cursor=base.reveal.startFrame;
 const revealStages=[['marker',length('marker')],['location',length('location')],['country',length('primary')],['title',length('title')]].map(([role,durationFrames])=>{
  const stage={role,startFrame:cursor,endFrame:cursor+durationFrames,durationFrames};cursor+=durationFrames;return stage;
 });
 if(cursor!==base.reveal.endFrame)throw Error('V3 must preserve V2 reveal window and Hold timeline');
 const plan={...structuredClone(base),version:PRIMARY_COLOR_CAMERA_VERSION,baseCameraPlan:base,
  primaryMaterial:{policy:'ALWAYS_ON_FROM_FRAME_0',factor:1,animated:false},
  reveal:{...base.reveal,stages:revealStages,countryWithLocation:false,primaryMaterialStage:false,
   boundaryGlowTiming:'Exact V2 primary factor retained independently of country material'},
  checkpoints:{FRAME0:0,MID_ZOOM:base.checkpoints.APPROACH,REGIONAL_LOCK:base.checkpoints.REGIONAL_LOCK,
   MARKER_REVEAL:revealStages[0].endFrame-1,FINAL_HOLD:base.checkpoints.FINAL_HOLD}};
 return freeze(plan);
}

export function evaluatePrimaryColorCameraFrame(plan,frame){
 if(plan?.version!==PRIMARY_COLOR_CAMERA_VERSION)throw Error('Compiled V3 camera plan required');
 const state=evaluateContinuousCameraFrame(plan.baseCameraPlan,frame);
 const reveal={primary:state.reveal.primary,marker:0,location:0,country:0,title:0,disclosure:state.reveal.disclosure};
 for(const stage of plan.reveal.stages){
  const progress=Math.max(0,Math.min(1,(frame-stage.startFrame)/Math.max(1,stage.durationFrames-1)));
  reveal[stage.role]=cameraEase(progress);
 }
 return {...state,version:PRIMARY_COLOR_CAMERA_VERSION,reveal,primaryMaterial:1,
  primaryColorPolicy:'ALWAYS_ON_FROM_FRAME_0',primaryBoundaryFactor:state.reveal.primary};
}
