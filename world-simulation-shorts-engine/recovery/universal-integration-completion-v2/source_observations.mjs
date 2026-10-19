/** CPU-only evaluation of the exact preserved scene clock and original Area math. */
import {registerHooks} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {evaluateProductionGeometryClock} from '../universal-production-v3/production_visual_profile.mjs';
import {normalizeFrontProfile,selectFrontSnapshot,sourceLineChunks} from '../verified-front-data-v4-recovery/front_visual.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),web=path.resolve(root,'../../web/map_infographic_v1');
const hook=registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('/modules/'))return{url:new URL('file://'+path.join(web,specifier.slice(9))).href,shortCircuit:true};
 return next(specifier,context);
}});
let long,serialization;
try{[long,serialization]=await Promise.all([import('../universal-auto-video-v2/long_area_timeline.mjs'),
 import('../universal-auto-video-v2/planner_geometry_serialization.mjs')]);}finally{hook.deregister();}
export function suppliedFrontObservations(plan,frontProfile){
 const request=long.compileLongAreaRequest(serialization.normalizePlannerGeometryKeys(plan.legacyScenePlan)),
  profile=normalizeFrontProfile(frontProfile,{totalFrames:plan.totalFrames,eventChapters:plan.productionV3.eventChapters}),
  result=[];
 for(let frame=0;frame<plan.totalFrames;frame++){
  const selected=selectFrontSnapshot(profile,frame),clock=evaluateProductionGeometryClock(plan,frame);
  let fronts=[];
  if(selected.sourceActiveFrame){
   const front=profile.fronts.find(row=>row.frontId===selected.frontId);
   fronts=sourceLineChunks(front.geometry).map((chunk,index)=>({id:front.frontId+'-part-'+index,geometry:chunk.geometry}));
  }else if(clock.eventEnabled){
   fronts=long.evaluateLongAreaFrame(request.timelinePlan,clock.sourceGeometryFrame,{project:point=>point})
    .fronts.map(row=>({id:row.id,geometry:row.geometry}));
  }
  result.push({frame,fronts});
 }
 return result;
}
