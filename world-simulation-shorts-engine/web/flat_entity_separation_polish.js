/** Optional v1 cartographic separation over the frozen v004 renderer.
 * This moves display proxies only. Verified geographic anchors, route heads,
 * route progress, scene timing and the underlying renderer are unchanged.
 */
import * as THREE from 'three';
import {SceneFlatPolishRenderer} from './flat_polish_renderer.js';
import {flatNumber,flatSmooth,flatClamp} from './flat_semantics.js';

export const FLAT_ENTITY_SEPARATION_VERSION='v1';
export const FLAT_ENTITY_SEPARATION_POLICY=Object.freeze({
 gapPixelsAt375:12,stoppedGapPixelsAt375:3,approachPixels1080:90,
 stoppedApproachPixels1080:85,iterations:6,departureReservationLeadSeconds:.60,
 positionScope:'cartographic_display_proxy_only',minimumAircraftSizeUnchanged:true,
});

/** Conservative bounds from the actual posed 3D mesh, through the current
 * registered projection. No icon-size constant substitutes for these bounds.
 */
export function projectedAircraftFootprint(model,project){
 model.updateMatrixWorld(true);
 const box=new THREE.Box3().setFromObject(model),points=[];
 for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
  const p=project(new THREE.Vector3(x,y,z));
  if(Number.isFinite(p.x)&&Number.isFinite(p.y))points.push(p);
 }
 if(!points.length)return null;
 const left=Math.min(...points.map(p=>p.x)),right=Math.max(...points.map(p=>p.x));
 const top=Math.min(...points.map(p=>p.y)),bottom=Math.max(...points.map(p=>p.y));
 const center=project(model.position);
 return {x:left,y:top,width:right-left,height:bottom-top,
  cx:(left+right)/2,cy:(top+bottom)/2,center:{x:center.x,y:center.y},
  source:'actual_posed_3d_mesh_projected_box_corners'};
}

/** A deterministic lane normal, derived once from verified route geometry.
 * The nearly horizontal lane preserves the reserved labels above/below cities.
 * Source longitudes choose priority, rather than fluctuating current positions.
 */
export function aircraftSeparationLane(a,b,scene,core){
 const routeOf=item=>(scene.routes||[]).find(route=>(route.route_id||route.id)===item.spec.route_id);
 const routes=[routeOf(a),routeOf(b)],directions=[];
 for(const route of routes){
  if(!route?.points||route.points.length<2)continue;
  const end=core.projection.point(route.points.at(-1)),before=core.projection.point(route.points.at(-2));
  const dx=end.x-before.x,dy=-(end.y-before.y),length=Math.hypot(dx,dy);
  if(length>1e-6)directions.push({x:dx/length,y:dy/length});
 }
 const direction=directions.reduce((v,d)=>({x:v.x+d.x,y:v.y+d.y}),{x:0,y:0});
 let axis={x:-direction.y,y:direction.x};
 if(Math.abs(axis.x)<1e-5)axis={x:1,y:0};
 if(axis.x<0){axis.x*=-1;axis.y*=-1;}
 axis.y=flatClamp(axis.y,-Math.abs(axis.x)*.28,Math.abs(axis.x)*.28);
 const length=Math.hypot(axis.x,axis.y)||1;axis={x:axis.x/length,y:axis.y/length};
 const sourceLon=route=>flatNumber(route?.points?.[0]?.lon);
 const lonDifference=sourceLon(routes[1])-sourceLon(routes[0]);
 const sign=a.spec.action==='stop'?-1:b.spec.action==='stop'?1:
  Math.abs(lonDifference)>1e-5?Math.sign(lonDifference):String(b.spec.id).localeCompare(String(a.spec.id))>=0?1:-1;
 return {x:axis.x*sign,y:axis.y*sign,source:'verified_route_arrival_tangent_and_origin_order'};
}

/** Invert the actual projection locally while keeping the map altitude fixed.
 * Re-evaluation makes this work throughout the tangent-plane -> sphere morph.
 */
export function projectedScreenOffsetDelta(position,offset,project){
 const original=position.clone(),target=project(original),point=original.clone();
 const wanted={x:target.x+offset.x,y:target.y+offset.y};
 for(let i=0;i<7;i++){
  const here=project(point),error={x:wanted.x-here.x,y:wanted.y-here.y};
  if(Math.hypot(error.x,error.y)<.025)break;
  const step=.002,px=project(point.clone().add(new THREE.Vector3(step,0,0))),py=project(point.clone().add(new THREE.Vector3(0,step,0)));
  const ax=(px.x-here.x)/step,ay=(px.y-here.y)/step,bx=(py.x-here.x)/step,by=(py.y-here.y)/step;
  const determinant=ax*by-ay*bx;
  if(!Number.isFinite(determinant)||Math.abs(determinant)<1e-8)throw Error('ENTITY_SEPARATION_PROJECTION_SINGULAR');
  const dx=(error.x*by-error.y*bx)/determinant,dy=(ax*error.y-ay*error.x)/determinant;
  if(!Number.isFinite(dx)||!Number.isFinite(dy))throw Error('ENTITY_SEPARATION_NONFINITE_OFFSET');
  point.x+=flatClamp(dx,-4,4);point.y+=flatClamp(dy,-4,4);
 }
 const actual=project(point),delta=point.sub(original);
 return {delta,residualPixels:Math.hypot(actual.x-wanted.x,actual.y-wanted.y)};
}

const support=(box,axis)=>(Math.abs(axis.x)*box.width+Math.abs(axis.y)*box.height)/2;
// An upper C1 approximation of max(0,x) avoids a velocity corner when a pair
// enters/leaves its separation lane, while never reducing the required gap.
const smoothPositive=(x,width)=>x<=-width?0:x>=width?x:(x+width)*(x+width)/(4*width);
const translationLimit=(box,direction,amount,w,h)=>{
 let limit=amount;
 for(const [coordinate,size,d,min,max] of [[box.x,box.width,direction.x,w*.055,w*.945],[box.y,box.height,direction.y,h*.08,h*.82]]){
  if(d>1e-8)limit=Math.min(limit,Math.max(0,(max-coordinate-size)/d));
  if(d< -1e-8)limit=Math.min(limit,Math.max(0,(coordinate-min)/-d));
 }
 return Math.max(0,limit);
};

/** Absolute, order-independent across calls. The inherited update resets all
 * model poses before every call; no previous-frame offset is retained.
 */
export function separateAircraftDisplayProxies(renderer,t,frame){
 const scale=renderer.w/1080,gap=FLAT_ENTITY_SEPARATION_POLICY.gapPixelsAt375*renderer.w/375;
 const approach=FLAT_ENTITY_SEPARATION_POLICY.approachPixels1080*scale;
 const project=point=>renderer.polishHooks?.projectDisplayPoint?.(renderer,point)||renderer.core.project(point);
 const active=renderer.entities.items.map((item,index)=>{
  const pose=frame.entities[index],start=flatNumber(item.spec.start_time,pose.route?.start||0);
  const reserve=flatSmooth((t-start+FLAT_ENTITY_SEPARATION_POLICY.departureReservationLeadSeconds)/FLAT_ENTITY_SEPARATION_POLICY.departureReservationLeadSeconds);
  if(item.spec.type!=='aircraft')return null;
  if(item.model.visible&&pose.alpha>.015)return {item,pose,reserve,futureReservation:false};
  if(t<=start+.20&&reserve>0){
   // A private, undrawn clone reserves the measured departure footprint. This
   // never turns an entity on early or changes a route/event timestamp.
   const model=item.model.clone(true),authored=flatNumber(item.spec.screen_size,74),minimum=index===0?88:82;
   if(!item.model.visible)model.scale.multiplyScalar(Math.max(1,minimum/authored));model.updateMatrixWorld(true);
   return {item:{...item,model,shadow:item.shadow.clone(),ghosts:[]},pose,reserve,futureReservation:true};
  }
  return null;
 }).filter(Boolean)
  .sort((a,b)=>String(a.item.spec.id).localeCompare(String(b.item.spec.id)));
 const originals=new Map(active.map(({item,pose})=>[item.spec.id,{position:item.model.position.clone(),screen:project(item.model.position),geographicAnchor:pose.position.toArray()}]));
 const pairs=[];
 for(let a=0;a<active.length;a++)for(let b=a+1;b<active.length;b++){
  const first=projectedAircraftFootprint(active[a].item.model,project),second=projectedAircraftFootprint(active[b].item.model,project);
  if(!first||!second)continue;
  const axis=aircraftSeparationLane(active[a].item,active[b].item,renderer.sceneSpec,renderer.core);
  const parkedPair=active[a].pose.mode==='stop'||active[b].pose.mode==='stop';
  const pairGap=parkedPair?
   FLAT_ENTITY_SEPARATION_POLICY.stoppedGapPixelsAt375*renderer.w/375:gap;
  const distance=Math.hypot(second.cx-first.cx,second.cy-first.cy),extent=support(first,axis)+support(second,axis);
  const proximityRange=parkedPair?FLAT_ENTITY_SEPARATION_POLICY.stoppedApproachPixels1080*scale:approach;
  const envelope=(1-flatSmooth((distance-extent-pairGap)/proximityRange))*Math.min(
   Math.max(flatSmooth(active[a].pose.alpha/.20),active[a].reserve),
   Math.max(flatSmooth(active[b].pose.alpha/.20),active[b].reserve));
  pairs.push({a:active[a],b:active[b],axis,envelope,gap:pairGap,smoothing:(parkedPair?85:70)*scale,
   originalSignedDistance:(second.cx-first.cx)*axis.x+(second.cy-first.cy)*axis.y});
 }
 const translate=(record,axis,amount)=>{
  if(amount<1e-5)return;
  const {delta}=projectedScreenOffsetDelta(record.item.model.position,{x:axis.x*amount,y:axis.y*amount},project);
  record.item.model.position.add(delta);record.item.shadow.position.add(delta);
  for(const ghost of record.item.ghosts)ghost.model.position.add(delta);
  record.item.model.updateMatrixWorld(true);
 };
 for(let iteration=0;iteration<FLAT_ENTITY_SEPARATION_POLICY.iterations;iteration++){
  for(const pair of pairs){
   if(pair.envelope<1e-5)continue;
   const a=projectedAircraftFootprint(pair.a.item.model,project),b=projectedAircraftFootprint(pair.b.item.model,project);
   if(!a||!b)continue;
   const extent=support(a,pair.axis)+support(b,pair.axis);
   const signedDistance=(b.cx-a.cx)*pair.axis.x+(b.cy-a.cy)*pair.axis.y;
   // A target computed against the original absolute pose is crucial: applying
   // the opacity envelope repeatedly would accelerate it over solver passes.
   const target=pair.originalSignedDistance+smoothPositive(extent+pair.gap-pair.originalSignedDistance,pair.smoothing)*pair.envelope;
   const needed=Math.max(0,target-signedDistance);
   if(needed<.01)continue;
   const negative={x:-pair.axis.x,y:-pair.axis.y},positive=pair.axis;
   const aYields=pair.a.pose.mode==='stop'||pair.b.futureReservation;
   const bYields=pair.b.pose.mode==='stop'||pair.a.futureReservation;
   const fraction=aYields&&!bYields?1:bYields&&!aYields?0:.5;
   let left=translationLimit(a,negative,needed*fraction,renderer.w,renderer.h),right=translationLimit(b,positive,needed-left,renderer.w,renderer.h);
   left=translationLimit(a,negative,needed-right,renderer.w,renderer.h);
   translate(pair.a,negative,left);translate(pair.b,positive,right);
  }
 }
 const records=[];
 for(const {item,pose,futureReservation} of active){
  if(futureReservation)continue;
  const original=originals.get(item.spec.id),display=project(item.model.position),offset={x:display.x-original.screen.x,y:display.y-original.screen.y};
  records.push({entity_id:item.spec.id,geographicAnchor:original.geographicAnchor,
   sourceProjectedPosition:original.position.toArray(),displayProjectedPosition:item.model.position.toArray(),
   additionalDisplayOffsetPixels:offset,finalFootprint:projectedAircraftFootprint(item.model,project),
   modelScaleUnchanged:true,route_id:pose.route?.id||item.spec.route_id,action:pose.mode});
 }
 const finalPairs=pairs.map(pair=>{
  const a=projectedAircraftFootprint(pair.a.item.model,project),b=projectedAircraftFootprint(pair.b.item.model,project);
  const gapAlongLane=(b.cx-a.cx)*pair.axis.x+(b.cy-a.cy)*pair.axis.y-support(a,pair.axis)-support(b,pair.axis);
  const intersects=a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
  return {entity_ids:[pair.a.item.spec.id,pair.b.item.spec.id],axis:pair.axis,
   gapAlongLanePixels:gapAlongLane,actualProjectedBoxesOverlap:intersects,
   minimumAlpha:Math.min(pair.a.pose.alpha,pair.b.pose.alpha),requiredGapPixels:pair.gap,
   upcomingDepartureReservation:pair.a.futureReservation||pair.b.futureReservation};
 });
 renderer.entitySeparationFrame={time:t,version:FLAT_ENTITY_SEPARATION_VERSION,records,pairs:finalPairs,
  scope:'display_proxy_only; verified coordinates and route heads remain unchanged',
  algorithm:'actual_projected_3d_bounds_fixed_arrival_lanes_local_projection_inverse',
  previousFrameStateUsed:false};
 return renderer.entitySeparationFrame;
}

export class SceneFlatEntitySeparationPolishRenderer extends SceneFlatPolishRenderer {
 constructor(scene,plan,options={}){
  if(scene.visual_polish?.entity_separation!==FLAT_ENTITY_SEPARATION_VERSION)throw Error('FLAT_ENTITY_SEPARATION_OPT_IN_V1_REQUIRED');
  super(scene,plan,options);this.entitySeparationFrame=null;
 }
 polishEntities(t,frame){
  const parked=this.entities.items.map((item,index)=>({item,index,pose:frame.entities[index]}))
   .filter(record=>record.item.spec.type==='aircraft'&&record.pose.mode==='stop'&&record.item.model.visible)
   .map(record=>({...record,modelPosition:record.item.model.position.clone(),modelScale:record.item.model.scale.clone(),
    shadowPosition:record.item.shadow.position.clone(),shadowScale:record.item.shadow.scale.clone(),
    ghosts:record.item.ghosts.map(ghost=>({ghost,position:ghost.model.position.clone(),scale:ghost.model.scale.clone()}))}));
  super.polishEntities(t,frame);
  // Use one absolute stopped-aircraft policy, rather than summing the frozen
  // adapter's short departure envelope with this slower footprint reservation.
  // The new policy retains the 88/82 px floors and does not shrink a model.
  for(const record of parked){
   const {item,index,pose}=record,gain=Math.max(1,(index===0?88:82)/flatNumber(item.spec.screen_size,74));
   item.model.position.copy(record.modelPosition);item.model.scale.copy(record.modelScale).multiplyScalar(gain);
   item.shadow.position.copy(record.shadowPosition);item.shadow.scale.copy(record.shadowScale);item.shadow.scale.x*=gain;item.shadow.scale.y*=gain;
   item.model.traverse(object=>{if(object.isMesh)for(const material of Array.isArray(object.material)?object.material:[object.material])material.opacity=pose.alpha;});
   item.model.userData.alpha=pose.alpha;
   for(const saved of record.ghosts){saved.ghost.model.position.copy(saved.position);saved.ghost.model.scale.copy(saved.scale).multiplyScalar(gain);}
   item.model.updateMatrixWorld(true);this.displayOffsets.delete(item.spec.id);
  }
  // The normal lifecycle applies this same absolute rig update again later.
  // Here it ensures the collision pass uses current curvature, never frame t-1.
  this.polishHooks?.beforeWorldRender?.(this,t,frame);
  separateAircraftDisplayProxies(this,t,frame);
 }
 drawOverlay(frame){
  const c=this.ctx,s=this.w/1080;
  for(const record of this.entitySeparationFrame?.records||[]){
   const length=Math.hypot(record.additionalDisplayOffsetPixels.x,record.additionalDisplayOffsetPixels.y);
   if(length<18*s)continue;
   const anchor=this.polishHooks?.projectDisplayPoint?.(this,new THREE.Vector3(...record.sourceProjectedPosition))||this.core.project(new THREE.Vector3(...record.sourceProjectedPosition));
   const center=record.finalFootprint.center;
   c.save();c.globalAlpha=.18;c.strokeStyle='#d2e6e5';c.lineWidth=1.15*s;c.setLineDash([3*s,4*s]);
   c.beginPath();c.moveTo(anchor.x,anchor.y);c.lineTo(center.x,center.y);c.stroke();c.restore();
  }
  super.drawOverlay(frame);
 }
 audit(t){
  const value=super.audit(t),layout=this.entitySeparationFrame;
  value.entitySeparation=layout;
  value.entities=value.entities.map(entity=>({...entity,
   additionalCartographicDisplaySeparation:layout?.records.find(record=>record.entity_id===entity.id)||null}));
  return value;
 }
}
