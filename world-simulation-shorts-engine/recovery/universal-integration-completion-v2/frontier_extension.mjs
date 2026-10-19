/** Presentation adapter over the original supplied-line Area V3 consumer.
 * No shader, geometry interpolation, occupation classifier, or terrain sampler
 * is authored here. Motion is compiled from exact supplied frame geometries.
 */
export const FRONTIER_PROFILE='AUTHORED_FRONT_MOTION_V2';
export const FRONTIER_MOTION_SCHEMA='WORLD_ENGINE_SUPPLIED_FRONT_MOTION_V2';
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v),
 fail=code=>{throw Error(code);},clone=v=>structuredClone(v),
 id=v=>typeof v==='string'&&/^[A-Za-z0-9_.:-]{1,160}$/.test(v),
 clamp=v=>Math.max(0,Math.min(1,v));
export function normalizeFrontierProfile(value={}){
 if(!object(value)||Object.keys(value).some(k=>!['profile','enabled','motionResponse','settledStrength','settleFrames'].includes(k)))
  fail('COMPLETION_FRONTIER_PROFILE_FIELDS');
 const p={profile:FRONTIER_PROFILE,enabled:true,motionResponse:true,settledStrength:.2,settleFrames:18,...clone(value)};
 if(p.profile!==FRONTIER_PROFILE||typeof p.enabled!=='boolean'||typeof p.motionResponse!=='boolean'
  ||typeof p.settledStrength!=='number'||!Number.isFinite(p.settledStrength)||p.settledStrength<0||p.settledStrength>1
  ||!Number.isSafeInteger(p.settleFrames)||p.settleFrames<1||p.settleFrames>120)fail('COMPLETION_FRONTIER_PROFILE_INVALID');
 return Object.freeze(p);
}
function geometry(front){
 const points=front?.geometry?.coordinates;
 if(!id(front?.id)||front?.geometry?.type!=='LineString'||!Array.isArray(points)||points.length<2||points.length>8192
  ||points.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)||p[0]<-180||p[0]>180||p[1]<-90||p[1]>90))
  fail('COMPLETION_FRONTIER_SUPPLIED_GEOMETRY_REQUIRED');
 return points;
}
/** Dense observations are required: missing frames are never assumed held or
 * interpolated. Run compression preserves only exact supplied coordinates. */
export function compileSuppliedFrontMotion({observations,totalFrames,profile={}}={}){
 const p=normalizeFrontierProfile(profile);
 if(!Number.isSafeInteger(totalFrames)||totalFrames<1||totalFrames>24000||!Array.isArray(observations)||observations.length!==totalFrames)
  fail('COMPLETION_FRONTIER_DENSE_SOURCE_FRAMES_REQUIRED');
 const fronts=Object.create(null),previous=new Map();
 for(let frame=0;frame<totalFrames;frame++){
  const observation=observations[frame];
  if(observation?.frame!==frame||!Array.isArray(observation.fronts)||observation.fronts.length>128)
   fail('COMPLETION_FRONTIER_EXACT_FRAME_REQUIRED');
  const seen=new Set();
  for(const front of observation.fronts){
   const points=geometry(front);if(seen.has(front.id))fail('COMPLETION_FRONTIER_DUPLICATE_ID');seen.add(front.id);
   const text=JSON.stringify(points),last=previous.get(front.id),row=fronts[front.id]??={changeFrames:[],incomparableFrames:[],geometryRuns:[]};
   if(last&&last.frame===frame-1&&last.text!==text){
    if(last.points.length===points.length)row.changeFrames.push(frame);
    else row.incomparableFrames.push(frame);
   }
   const run=row.geometryRuns.at(-1);
   if(last?.frame===frame-1&&last.text===text)run.endFrame=frame+1;
   else row.geometryRuns.push({startFrame:frame,endFrame:frame+1,coordinates:clone(points)});
   previous.set(front.id,{frame,text,points});
  }
 }
 const result={schema:FRONTIER_MOTION_SCHEMA,totalFrames,profile:clone(p),fronts,
  geometrySource:'EXACT_SUPPLIED_FRAME_GEOMETRY',interpolation:'NONE',cameraMotionExcluded:true,
  inventedOccupation:false,rendererOutputVerified:false};
 if(JSON.stringify(result).length>16*1024*1024)fail('COMPLETION_FRONTIER_MOTION_PLAN_BUDGET');
 return result;
}
/** Stateless evaluation gives identical output at scene boundaries and seeks. */
export function evaluateSuppliedFrontMotion(plan,frame,front){
 if(plan?.schema!==FRONTIER_MOTION_SCHEMA||!Number.isSafeInteger(frame)||frame<0||frame>=plan.totalFrames)
  fail('COMPLETION_FRONTIER_MOTION_FRAME_INVALID');
 const p=normalizeFrontierProfile(plan.profile),points=geometry(front),row=plan.fronts?.[front.id];
 const run=row?.geometryRuns?.find(r=>frame>=r.startFrame&&frame<r.endFrame);
 if(!run||JSON.stringify(run.coordinates)!==JSON.stringify(points))fail('COMPLETION_FRONTIER_GEOMETRY_BINDING_MISMATCH');
 const changes=row.changeFrames.filter(f=>f<=frame),last=changes.at(-1),incomparable=row.incomparableFrames.filter(f=>f<=frame).at(-1);
 const measured=last!==undefined&&(incomparable===undefined||last>incomparable),elapsed=measured?frame-last:null,
  t=elapsed===null?0:clamp(elapsed/p.settleFrames),ease=t*t*(3-2*t),
  strength=!p.enabled||!p.motionResponse||!measured?1:p.settledStrength+(1-p.settledStrength)*(1-ease);
 return{frame,frontId:front.id,strength,geographicGeometryChangedThisFrame:last===frame,
  measuredComparableChange:measured,lastComparableChangeFrame:last??null,
  sourceTopologyChanged:incomparable!==undefined&&!measured,elapsedFramesSinceChange:elapsed,
  deterministicGlobalClock:true,projectionMotionExcluded:true,syntheticPulse:false,
  sourceGeometryModified:false,gpuVerified:false};
}
/** The supplied original factory remains the only GPU draw owner. The adapter
 * scales existing front alpha, leaving polygons, masks, line primitives and
 * source coordinates byte-semantically unchanged. */
export function bindFrontierProductionFactory(originalFactory,{profile={},readFrameContext=null,motionPlan=null}={}){
 const p=normalizeFrontierProfile(profile);
 if(typeof originalFactory!=='function'||readFrameContext!==null&&typeof readFrameContext!=='function')
  fail('COMPLETION_FRONTIER_FACTORY_REQUIRED');
 if(motionPlan!==null&&(motionPlan.schema!==FRONTIER_MOTION_SCHEMA||JSON.stringify(normalizeFrontierProfile(motionPlan.profile))!==JSON.stringify(p)))
  fail('COMPLETION_FRONTIER_MOTION_PROFILE_MISMATCH');
 return options=>{
  const owner=originalFactory(options);
  if(!object(owner)||typeof owner.draw!=='function')fail('COMPLETION_FRONTIER_DRAW_OWNER_REQUIRED');
  if(!p.enabled)return owner;
  const metadata={profile:clone(p),existingAreaFactoryCalled:true,originalShaderCopied:false,
   actualConsumer:'AREA_OVERLAY_PASS_V3.drawLine -> contour',geometryPolicy:'EXACT_SUPPLIED_FRONT_ONLY',
   motionConnected:!p.motionResponse||motionPlan!==null,
   motionBlocker:p.motionResponse&&motionPlan===null?'COMPLETION_FRONTIER_MOTION_SOURCE_NOT_CONNECTED':null,
   terrainLightingConnected:false,terrainLightingBlocker:'SCALAR_TERRITORY_AND_CURRENT_TERRAIN_TEXTURE_CONTRACT_REQUIRED',
   gpuVerified:false,visualOutputVerified:false};
  return{...owner,evidence:{...clone(owner.evidence??{}),completionFrontier:clone(metadata)},draw(input){
   if(!object(input?.controls)||!Array.isArray(input.controls.fronts))fail('COMPLETION_FRONTIER_CONTROLS_REQUIRED');
   const context=readFrameContext?.(options.canvas),frame=context?.frame??input.controls.frame,
    motion=[];
   const fronts=input.controls.fronts.map(front=>{
    geometry(front);
    if(!p.motionResponse||motionPlan===null)return front;
    const state=evaluateSuppliedFrontMotion(motionPlan,frame,front);motion.push(state);
    if(typeof front.alpha!=='number'||!Number.isFinite(front.alpha)||front.alpha<0||front.alpha>1)
     fail('COMPLETION_FRONTIER_ALPHA_REQUIRED');
    return{...front,alpha:front.alpha*state.strength};
   });
   const result=owner.draw({...input,controls:{...input.controls,fronts}});
   return{...result,completionFrontier:{...clone(metadata),frame:Number.isSafeInteger(frame)?frame:null,motion,
    boundaryAndReservationMasksForwarded:true,actualSuppliedGeometryRetained:true}};
  }};
 };
}
