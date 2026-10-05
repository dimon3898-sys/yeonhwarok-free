/** Shared geographic rig and draw eligibility for the optional premium map.
 * Numeric certification forecasts draw eligibility; only browser frame audits
 * and decoded output establish that these primitives were actually rendered.
 * World XY units are projected degrees, Z is cartographic display clearance.
 */
import * as THREE from 'three';

export const FLAT_CAMERA_PRESETS = Object.freeze([
 'FLAT_ESTABLISH','FLAT_COUNTRY_FOCUS','FLAT_REGION_FOCUS','FLAT_ROUTE_FOLLOW',
 'FLAT_ENTITY_FOLLOW','FLAT_MULTI_COUNTRY','FLAT_PULLBACK','FLAT_NEXT_EVENT_PREVIEW',
]);
export const FLAT_EVENT_KINDS = new Set([
 'hook_reveal','city_reveal','country_reveal','region_reveal','route_start',
 'entity_departure','arrival','new_variable','route_blocked','route_reroute',
 'alternate_route_reveal','network_expand','network_expansion','comparison_reveal',
 'milestone_reveal','milestone','destination_preview','destination_hint','response',
 'counter_response','escalation','peak_reveal','peak_moment','final_reveal','route_choice',
 'distance_reveal','connection_reveal','consequence_reveal','consequence','timeline_reveal',
 'city_focus','destination_pulse','country_highlight','region_highlight','area_highlight',
 'pulse','radar','warning','impact','shockwave','route_block',
]);
export const flatClamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)));
export const flatSmooth=v=>{v=flatClamp(v);return v*v*(3-2*v);};
export const flatNumber=(v,f=0)=>Number.isFinite(Number(v))?Number(v):f;
export const flatEase=(value,kind='ease_in_out')=>{
 const p=flatClamp(value);if(kind==='linear')return p;if(kind==='ease_in')return p*p;
 if(kind==='ease_out')return 1-(1-p)*(1-p);if(kind==='ease_in_out'||kind==='smoothstep')return flatSmooth(p);
 throw Error('UNSUPPORTED_ENTITY_SPEED_EASING '+kind);
};
export const flatCameraEase=(value,kind='smootherstep')=>{
 const p=flatClamp(value);if(kind==='smootherstep')return p*p*p*(p*(p*6-15)+10);
 if(kind==='quintic_out')return 1-(1-p)**5;
 return flatEase(p,kind==='smoothstep'?'ease_in_out':kind);
};
export const flatCoordinate=value=>{
 const c=value?.coordinates||value;
 const lon=Array.isArray(c)?Number(c[0]):Number(c?.lon??c?.longitude);
 const lat=Array.isArray(c)?Number(c[1]):Number(c?.lat??c?.latitude);
 if(!Number.isFinite(lon)||!Number.isFinite(lat)||lat < -90||lat>90||lon < -180||lon>180)
  throw Error('FLAT_MAP_REQUIRES_VERIFIED_COORDINATES');
 return {lon,lat};
};
const radians=Math.PI/180;
const sphere=c=>new THREE.Vector3(Math.cos(c.lat*radians)*Math.cos(c.lon*radians),Math.sin(c.lat*radians),Math.cos(c.lat*radians)*Math.sin(c.lon*radians));
const sphericalLerp=(a,b,p)=>{
 const angle=Math.acos(flatClamp(a.dot(b),-1,1));
 if(angle<1e-8)return a.clone();
 if(Math.PI-angle<1e-5)throw Error('ANTIPODAL_ROUTE_REQUIRES_VERIFIED_INTERMEDIATE_WAYPOINT');
 return a.clone().multiplyScalar(Math.sin((1-p)*angle)/Math.sin(angle)).addScaledVector(b,Math.sin(p*angle)/Math.sin(angle)).normalize();
};
export const flatWindow=(t,start,end,fade=.24,hold=false)=>{
 if(t<start||t>end)return 0;
 const a=flatSmooth((t-start)/Math.min(fade,Math.max(.01,(end-start)/3)));
 return a*(hold?1:1-flatSmooth((t-end+fade)/fade));
};

export class FlatProjection {
 constructor(center,kind='LOCAL_MERCATOR'){
  this.center=flatCoordinate(center);this.kind=kind;
  if(!['LOCAL_MERCATOR','LOCAL_EQUIRECTANGULAR'].includes(kind))throw Error('UNSUPPORTED_FLAT_PROJECTION '+kind);
 }
 unwrap(lon){return this.center.lon+((lon-this.center.lon+540)%360)-180;}
 point(value,z=0){const c=flatCoordinate(value);return new THREE.Vector3(this.unwrap(c.lon),this.y(c.lat),z);}
 y(lat){return this.kind==='LOCAL_EQUIRECTANGULAR'?lat:Math.log(Math.tan(Math.PI/4+flatClamp(lat,-80,80)*radians/2))/radians;}
 latitude(y){return this.kind==='LOCAL_EQUIRECTANGULAR'?y:(2*Math.atan(Math.exp(y*radians))-Math.PI/2)/radians;}
 inverse(point){return {lon:((point.x+540)%360)-180,lat:this.latitude(point.y)};}
}

export class FlatRoute {
 constructor(spec,projection,duration){
  this.spec=spec;this.id=spec.route_id||spec.id;this.projection=projection;
  this.coordinates=(spec.points||spec.waypoints||[]).map(flatCoordinate);
  if(this.coordinates.length<2)throw Error('Route requires two verified waypoints: '+this.id);
  this.vectors=this.coordinates.map(sphere);this.lengths=[0];
  for(let i=1;i<this.vectors.length;i++)this.lengths.push(this.lengths.at(-1)+Math.acos(flatClamp(this.vectors[i-1].dot(this.vectors[i]),-1,1)));
  this.total=this.lengths.at(-1);if(this.total<1e-7)throw Error('Route endpoints coincide: '+this.id);
  this.start=flatNumber(spec.start_time);this.end=flatNumber(spec.end_time,duration);
  this.faint=Boolean(spec.faint);this.displayAltitude=.028;
 }
 progress(t,easing=this.spec.speed_easing||'ease_in_out'){const p=flatEase((t-this.start)/Math.max(.001,this.end-this.start),easing);return flatNumber(this.spec.progress_start)+(flatNumber(this.spec.progress_end,1)-flatNumber(this.spec.progress_start))*p;}
 coordinate(p){
  const d=flatClamp(p)*this.total;let i=1;while(i<this.lengths.length-1&&this.lengths[i]<d)i++;
  const delta=this.lengths[i]-this.lengths[i-1],e=delta>1e-8?(d-this.lengths[i-1])/delta:0;
  const n=sphericalLerp(this.vectors[i-1],this.vectors[i],e);
  return {lon:Math.atan2(n.z,n.x)/radians,lat:Math.asin(flatClamp(n.y,-1,1))/radians};
 }
 point(p,z=this.displayAltitude){return this.projection.point(this.coordinate(p),z);}
 tangent(p){return this.point(flatClamp(p+.0001)).sub(this.point(flatClamp(p-.0001))).normalize();}
 shown(t){return t>=this.start||flatNumber(this.spec.progress_start)>0;}
}

export class FlatCameraRig {
 constructor(camera,scene,projection,routes){
  this.camera=camera;this.scene=scene;this.projection=projection;this.routes=routes;this.duration=scene.duration;
  const config=scene.flat_map||{},center=projection.center;
  const fallback={...center,span_degrees:flatNumber(config.span_degrees,24),tilt:flatNumber(config.tilt,.07),rotation:0,bank:0};
  this.start={...fallback,...(scene.camera_start||{}),...(config.camera_start||{})};
  this.end={...this.start,...(scene.camera_end||{}),...(config.camera_end||{})};
  if(config.camera_end?.span_degrees===undefined&&scene.camera_end?.span_degrees===undefined){
   if(scene.camera_preset==='FLAT_PULLBACK')this.end.span_degrees=this.start.span_degrees*1.28;
   else if(['FLAT_COUNTRY_FOCUS','FLAT_REGION_FOCUS'].includes(scene.camera_preset))this.end.span_degrees=this.start.span_degrees*.84;
   else if(scene.camera_preset==='FLAT_ESTABLISH')this.end.span_degrees=this.start.span_degrees*.95;
  }
  for(const pose of [this.start,this.end]){
   flatCoordinate(pose);pose.span_degrees=flatNumber(pose.span_degrees,fallback.span_degrees);
   if(!(pose.span_degrees>=.25&&pose.span_degrees<=220))throw Error('Flat camera span must be .25–220 degrees');
   pose.tilt=flatClamp(flatNumber(pose.tilt,fallback.tilt),0,.16);
   pose.rotation=flatClamp(flatNumber(pose.rotation??pose.yaw),-.12,.12);
   pose.bank=flatClamp(flatNumber(pose.bank),-.035,.035);
  }
  if(!FLAT_CAMERA_PRESETS.includes(scene.camera_preset))throw Error('Unknown flat camera preset '+scene.camera_preset);
 }
 values(t){
  const p=flatClamp(t/this.duration),speed=flatClamp(flatNumber(this.scene.camera_speed,1),.6,2.5);
  const e=flatCameraEase(Math.pow(p,1/speed),this.scene.camera_easing||this.scene.flat_map?.camera_easing||'smootherstep');
  const a=this.projection.point(this.start),b=this.projection.point(this.end),center=a.lerp(b,e);
  let span=this.start.span_degrees+(this.end.span_degrees-this.start.span_degrees)*e;
  const envelope=p<=0||p>=1?0:Math.sin(Math.PI*p)**2;
  const primary=this.routes.find(r=>!r.faint&&t>=r.start&&t<=r.end)||this.routes.find(r=>!r.faint);
  if(['FLAT_ROUTE_FOLLOW','FLAT_ENTITY_FOLLOW'].includes(this.scene.camera_preset)&&primary)
   center.lerp(primary.point(primary.progress(t),0),flatNumber(this.scene.flat_map?.tracking,.38)*envelope);
  const preview=this.scene.flat_map?.next_event;
  let previewWeight=0;
  if(preview&&this.scene.camera_preset==='FLAT_NEXT_EVENT_PREVIEW'){
   const at=flatNumber(preview.event_time),lead=Math.max(.12,flatNumber(preview.lead_time,.7));
   previewWeight=flatSmooth((t-at+lead)/lead)*flatNumber(preview.strength,.40)*envelope;
   center.lerp(this.projection.point(preview.coordinates),previewWeight);
  }
  let tilt=this.start.tilt+(this.end.tilt-this.start.tilt)*e;
  const transitionDuration=Math.max(.15,Math.min(1.5,flatNumber(this.scene.map_transition?.duration??this.scene.flat_map?.transition_duration,.42)));
  let handoff=0;
  if(['FLAT_TO_EARTH','EARTH_TO_FLAT'].includes(this.scene.transition_out))handoff=flatSmooth((t-this.duration+transitionDuration)/transitionDuration);
  if(this.scene.transition_in==='EARTH_TO_FLAT')handoff=Math.max(handoff,1-flatSmooth(t/transitionDuration));
  span*=1+.28*handoff;tilt+=(.15-tilt)*handoff;
  return {p,e,center,span,previewWeight,projectionHandoff:handoff,tilt,rotation:this.start.rotation+(this.end.rotation-this.start.rotation)*e,bank:this.start.bank+(this.end.bank-this.start.bank)*e};
 }
 update(t){
  const v=this.values(t),aspect=this.camera.aspect||9/16,height=v.span/aspect;
  this.camera.left=-v.span/2;this.camera.right=v.span/2;this.camera.top=height/2;this.camera.bottom=-height/2;
  this.camera.position.copy(v.center).add(new THREE.Vector3(Math.sin(v.rotation)*v.span*.12,-height*v.tilt,height*.90));
  this.camera.up.set(Math.sin(v.bank),Math.cos(v.bank),0);this.camera.lookAt(v.center);
  this.camera.updateProjectionMatrix();this.camera.updateMatrixWorld(true);this.current=v;return v;
 }
}

const INFO_KINDS=new Set(['new_variable','alternate_route_reveal','comparison_reveal','milestone_reveal','milestone','destination_hint','response','counter_response','escalation','peak_reveal','peak_moment','final_reveal','route_choice','distance_reveal','connection_reveal','consequence_reveal','consequence','timeline_reveal']);
const VFX_KINDS=new Set(['arrival','destination_pulse','city_focus','pulse','radar','warning','impact','shockwave','route_block','route_blocked','area_highlight','region_highlight']);
const physicalEventNames=new Set(['route_start','entity_departure','route_blocked','route_block','route_reroute','network_expand','network_expansion','arrival']);

export class FlatSceneCore {
 constructor(scene,plan,options={}){
  this.sceneSpec=scene;this.plan=plan;this.duration=flatNumber(scene.duration);this.w=options.width||2160;this.h=options.height||3840;
  if(!(this.duration>0))throw Error('Positive scene duration is required');
  this.projection=new FlatProjection(scene.flat_map?.center||scene.coordinates,scene.flat_map?.projection||'LOCAL_MERCATOR');
  this.camera=new THREE.OrthographicCamera(-12,12,21,-21,.01,2000);this.camera.aspect=this.w/this.h;
  this.routes=(scene.routes||[]).map(r=>new FlatRoute(r,this.projection,this.duration));
  this.cam=new FlatCameraRig(this.camera,scene,this.projection,this.routes);
  this.context=options.context;this.countries=options.countries?.features||options.countries||[];
  this.countryTargets=(scene.flat_map?.country_highlights||[]).map(h=>({...h,country:String(h.country||h.country_id||h.target_id).toUpperCase()}));
  this.entities=(scene.entities||[]).map(spec=>({...spec,type:spec.type==='ship'?'cargo_ship':spec.type,visibility_role:spec.visibility_role||'primary'}));
  for(const entity of this.entities)if(!['aircraft','cargo_ship','vehicle','location_marker','city','port','airport'].includes(entity.type))throw Error('UNSUPPORTED_FLAT_ENTITY '+entity.type);
  for(const entity of this.entities)if(entity.route_id&&!this.route(entity.route_id))throw Error('ENTITY_ROUTE_NOT_FOUND '+entity.route_id);
  for(const action of scene.entity_actions||[]){
   if(!['move','stop','reroute','split','merge','converge','diverge','follow','intercept'].includes(action.action))throw Error('UNSUPPORTED_FLAT_ENTITY_ACTION '+action.action);
   if(action.speed_easing)flatEase(.5,action.speed_easing);
  }
  for(const event of scene.visual_events||[])if(event.meaningful!==false&&!FLAT_EVENT_KINDS.has(String(event.kind).toLowerCase()))throw Error('UNSUPPORTED_FLAT_EVENT '+event.kind);
  this.cam.update(0);
 }
 route(id){return this.routes.find(r=>r.id===id);}
 project(point){const v=point.clone().project(this.camera);return {x:(v.x*.5+.5)*this.w,y:(.5-v.y*.5)*this.h,visible:v.z>=-1&&v.z<=1,occluded:false};}
 safe(point){const p=this.project(point);return p.visible&&p.x>=this.w*.06&&p.x<=this.w*.91&&p.y>=this.h*.08&&p.y<=this.h*.85;}
 entityPose(spec,t,depth=0){
  if(depth>8)throw Error('CYCLIC_ENTITY_ACTION');
  const actions=(this.sceneSpec.entity_actions||[]).filter(a=>a.entity_id===spec.id&&flatNumber(a.time,a.start_time||0)<=t).sort((a,b)=>flatNumber(a.time,a.start_time||0)-flatNumber(b.time,b.start_time||0));
  const action=actions.at(-1)||{};const mode=action.action||spec.action||'move';
  let route=this.route(action.route_id||spec.route_id),p=route?route.progress(t,action.speed_easing||spec.speed_easing||route.spec.speed_easing||'ease_in_out'):0;
  if((mode==='reroute'||mode==='split'||mode==='diverge')&&action.route_id&&!route)throw Error('ENTITY_ACTION_REQUIRES_VERIFIED_ROUTE '+action.route_id);
  if(mode==='stop'&&route)p=flatNumber(action.stop_progress??spec.stop_progress,route.progress(flatNumber(action.time,route.start)));
  if(['follow','merge','converge','intercept'].includes(mode)&&action.target_entity_id){
   const target=this.entities.find(e=>e.id===action.target_entity_id);if(!target)throw Error('ENTITY_ACTION_TARGET_MISSING');
   const pose=this.entityPose(target,t,depth+1),start=flatNumber(action.time),blend=flatSmooth((t-start)/Math.max(.2,flatNumber(action.duration,.8)));
   const from=route?route.point(p,.16):this.projection.point(spec.coordinates||this.sceneSpec.coordinates,.16);
   const ownStart=flatNumber(spec.start_time),ownEnd=flatNumber(spec.end_time,this.duration),alpha=flatWindow(t,ownStart,ownEnd,.20,Boolean(spec.persistent));
   return {...pose,spec,position:from.lerp(pose.position,blend),mode,action,route,alpha,visible:t>=ownStart&&t<=ownEnd&&alpha>.005};
  }
  p=flatClamp(p+flatNumber(action.phase_offset,spec.phase_offset||0));
  const position=route?route.point(p,.16):this.projection.point(spec.coordinates||this.sceneSpec.coordinates,.12);
  const tangent=route?route.tangent(p):new THREE.Vector3(0,1,0);
  const start=flatNumber(spec.start_time,route?.start||0),end=flatNumber(spec.end_time,this.duration);
  const beginsExisting=route&&flatNumber(route.spec.progress_start)>0&&start===0;
  const continues=spec.persistent||route&&flatNumber(route.spec.progress_end,1)<1;
  const alpha=(beginsExisting?1:flatSmooth((t-start)/.20))*(continues?1:1-flatSmooth((t-end+.20)/.20));
  return {spec,route,position,tangent,p,alpha,visible:t>=start&&t<=end&&alpha>.005,mode,action};
 }
 routeProgress(route,t){
  const poses=this.entities.map(e=>this.entityPose(e,t)).filter(p=>p.visible&&p.route?.id===route.id&&Number.isFinite(p.p));
  return poses.length?Math.max(...poses.map(p=>p.p)):route.progress(t);
 }
 visibleRoutes(t){return this.routes.filter(r=>r.shown(t)&&this.routeProgress(r,t)>.000001&&Array.from({length:25},(_,i)=>r.point(this.routeProgress(r,t)*i/24)).some(p=>this.safe(p)));}
 countryContains(feature,coordinate){
  const p=this.projection.point(coordinate),inside=ring=>{
   let result=false;const points=ring.map(v=>this.projection.point(v));
   for(let i=0,j=points.length-1;i<points.length;j=i++){
    const a=points[i],b=points[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)result=!result;
   }return result;
  };
  const polys=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
  return polys.some(poly=>inside(poly[0])&&!poly.slice(1).some(inside));
 }
 overlayLabels(t){
  const s=this.w/1080,c=this.context,labels=[],placed=[];
  const candidates=[...(this.sceneSpec.labels||[])];
  for(const event of this.sceneSpec.visual_events||[])
   if(['city_reveal','country_reveal','region_reveal','destination_preview'].includes(event.kind)&&event.coordinates&&event.text)
    candidates.push({text:event.text,event_id:event.id,kind:'world_label',coordinates:event.coordinates,start_time:event.time,end_time:Math.min(this.duration,event.time+flatNumber(event.duration,1.5)),size:48});
  const widthOf=(text,size)=>{if(c){c.font=`300 ${size}px 'Open Sans'`;return c.measureText(text).width;}return [...text].reduce((v,ch)=>v+(ch===' '? .27:.60)*size,0);};
  for(const label of candidates){
   if(!label.text||!label.coordinates)continue;
   const start=flatNumber(label.start_time),end=flatNumber(label.end_time,this.duration),opacity=flatWindow(t,start,end,.22,Boolean(label.persistent));
   if(opacity<.01)continue;const p=this.project(this.projection.point(label.coordinates));
   if(!p.visible||p.x<this.w*.04||p.x>this.w*.96||p.y<this.h*.08||p.y>this.h*.82)continue;
   const font=flatNumber(label.size,48)*s,text=String(label.text),spacing=1.8*s;
   const width=widthOf(text,font)+(text.length-1)*spacing;
   const x=flatClamp(p.x+flatNumber(label.offset_x,60)*s,this.w*.10+width/2,this.w*.85-width/2);
   let baseline=flatClamp(p.y+flatNumber(label.offset_y,-35)*s,this.h*.14+font,this.h*.77);
   const box={text,kind:label.kind||'world_label',event_id:label.event_id||null,x:x-width/2,y:baseline-font,width,height:font*1.25,font,spacing,opacity:opacity*flatNumber(label.opacity,1),color:label.color||'#e8eee9',anchor:p};
   let attempts=0;while(placed.some(b=>box.x<b.x+b.width+12*s&&box.x+box.width>b.x-12*s&&box.y<b.y+b.height+12*s&&box.y+box.height>b.y-12*s)&&attempts++<4){box.y+=font*1.45;}
   if(box.y+box.height>this.h*.80)continue;
   labels.push(box);placed.push(box);
  }
  const hook=this.sceneSpec.hook||this.plan.story?.hook||this.plan.story_plan?.hook;
  let event=null,text='',opacity=0;
  if(flatNumber(this.sceneSpec.start_time)===0&&t<2.35&&hook){text=hook;opacity=.9*(1-flatSmooth((t-1.95)/.40));}
  else{
   for(const e of this.sceneSpec.visual_events||[]){
    const start=flatNumber(e.time),end=Math.min(this.duration,start+Math.max(1.20,flatNumber(e.duration,1.5)));
    if(!INFO_KINDS.has(e.kind)||t<start||t>=end)continue;
    text=e.text||e.label||'';if(!text&&e.kind==='distance_reveal'){const r=this.route(e.target_id);text=r?`${Math.round(r.total*6371).toLocaleString('en-US')} KM`:'';}
    if(text){event=e;opacity=flatWindow(t,start,end,.20,this.sceneSpec.scene_type==='FINAL_OVERVIEW');break;}
   }
  }
  if(text&&opacity>.01){
   const korean=/[\u3131-\uD79D]/.test(text),font=(event?38:48)*s,fontFamily=korean?'Noto Cinema':'Open Sans';
   if(c)c.font=`${korean?400:300} ${font}px '${fontFamily}'`;
   const measure=str=>c?c.measureText(str).width:[...str].length*font*.65;
   const words=String(text).replace(/\s*·\s*/g,'\n').split(/(\n|[^\S\n]+)/),lines=[];let line='';
   for(const word of words){if(word==='\n'){if(line.trim())lines.push(line.trim());line='';}else if(measure(line+word)>this.w*.74&&line){lines.push(line.trim());line=word.trimStart();}else line+=word;}
   if(line.trim())lines.push(line.trim());if(lines.length>3)throw Error('FLAT_INFORMATION_EXCEEDS_SAFE_THREE_LINES');
   for(let i=0;i<lines.length;i++)labels.push({text:lines[i],x:this.w*.12,y:this.h*.118+i*font*1.4,width:measure(lines[i]),height:font*1.35,font,fontFamily,opacity,color:'#f2f0e7',kind:event?.kind||'hook_reveal',event_id:event?.id||null,information:true,spacing:0});
  }
  return labels;
 }
 semanticFrame(t){
  this.cam.update(t);const entities=this.entities.map(e=>this.entityPose(e,t)),labels=this.overlayLabels(t),active=this.visibleRoutes(t),events=[],vfx=[];
  for(const event of this.sceneSpec.visual_events||[]){
   const kind=String(event.kind).toLowerCase(),start=flatNumber(event.time),end=Math.min(this.duration,start+Math.max(.70,flatNumber(event.duration,1.35)));
   if(t<start||t>=end)continue;
   const age=(t-start)/(end-start),point=event.coordinates?this.projection.point(event.coordinates,.040):null;
   if(VFX_KINDS.has(kind)&&point){vfx.push({event,kind,point,age,duration:end-start,visible:this.safe(point),opacity:Math.sin(Math.PI*age)**.5});}
   if(event.meaningful===false)continue;let primitive=null,detail={};
   const label=labels.find(l=>l.event_id===event.id&&l.opacity>.1);
   if(label&&!physicalEventNames.has(kind)){primitive=label.information?'information':'world_label';detail={text:label.text,opacity:label.opacity,box:{x:label.x,y:label.y,width:label.width,height:label.height}};}
   if(kind==='route_start'||kind==='route_reroute'){
    const r=this.route(event.target_id),p=r?this.routeProgress(r,t):0;if(r&&r.shown(t)&&t<r.end&&p<1&&this.safe(r.point(p))){primitive='route_head';detail={route_id:r.id,progress:p,headPosition:r.point(p).toArray()};}
   }
   if(kind==='entity_departure'){
    const e=entities.find(e=>e.spec.id===event.target_id&&e.visible&&e.alpha>.1&&e.mode!=='stop'&&e.route&&this.safe(e.position)&&e.p>this.entityPose(e.spec,Math.max(0,t-1/30)).p+1e-8);
    if(e){primitive='3D_entity';detail={entity_id:e.spec.id,route_id:e.route.id,alpha:e.alpha,position:e.position.toArray()};}
   }
   if(['country_reveal','country_highlight'].includes(kind)&&event.coordinates){
    const h=this.countryTargets.find(h=>{
     const weight=flatWindow(t,flatNumber(h.start_time),flatNumber(h.end_time,this.duration),.32,Boolean(h.persistent))*flatNumber(h.opacity,.20);
     const feature=this.countries.find(f=>['ISO_A3','ISO_A3_EH','ADM0_A3','ISO_A2','ADMIN','NAME','NAME_EN'].some(k=>String(f.properties[k]).toUpperCase()===h.country));
     return weight>.01&&feature&&this.countryContains(feature,event.coordinates)&&this.safe(this.projection.point(event.coordinates));
    });
    if(h){primitive='country_highlight';detail={country_id:h.country,source_id:h.source_id,terrain_preserved:true,opacity:flatWindow(t,flatNumber(h.start_time),flatNumber(h.end_time,this.duration),.32,Boolean(h.persistent))*flatNumber(h.opacity,.20)};}
   }
   if(['network_expand','network_expansion','peak_reveal','final_reveal','connection_reveal'].includes(kind)&&active.length>=2&&(!['network_expand','network_expansion'].includes(kind)||active.some(r=>r.id===event.target_id&&t>=r.start&&t<r.end))){primitive='network';detail={route_ids:active.map(r=>r.id),progress:active.map(r=>this.routeProgress(r,t))};}
   const effect=vfx.find(v=>v.event.id===event.id&&v.visible&&v.opacity>.1);
   if(effect){primitive=['route_blocked','route_block'].includes(kind)?'route_barrier':['arrival','city_focus','destination_pulse','pulse'].includes(kind)?'geographic_pulse':'map_vfx';detail={coordinates:event.coordinates,age:effect.age,pulse_duration:effect.duration,opacity:effect.opacity,vfx_kind:kind};}
   if(primitive)events.push({event_id:event.id,kind,rendered_primitive:primitive,actual_time:t,scheduled_time:start,visible:true,...detail});
  }
  return {t,entities,labels,events,vfx,activeRoutes:active};
 }
 numericPreflight(fps=30){
  let previous=null,maxCameraAngle=0,finite=true;const records=[];
  for(let frame=0;frame<=Math.round(this.duration*fps);frame++){
   const t=Math.min(this.duration,frame/fps);this.cam.update(t);const q=this.camera.quaternion.clone();
   if(previous)maxCameraAngle=Math.max(maxCameraAngle,previous.angleTo(q)*180/Math.PI);previous=q;
   finite=finite&&this.camera.position.toArray().every(Number.isFinite);
   for(const r of this.routes)finite=finite&&r.point(r.progress(t)).toArray().every(Number.isFinite);
   for(const e of this.entities)finite=finite&&this.entityPose(e,t).position.toArray().every(Number.isFinite);
   records.push({time:t,camera:this.camera.position.toArray(),quaternion:q.toArray()});
  }
  this.cam.update(0);return {render_mode:'FLAT_MAP_PREMIUM',motionIntegrationTaps:1,finite,maxCameraAngleDegreesPerFrame:maxCameraAngle,cameraWithinEarth:false,entityWithinEarth:false,routeWithinEarth:false,minCameraRadius:null,minRouteRadius:null,minEntityRadius:null,entityVertexChecks:0,projection:this.projection.kind,scope:'Projected-map rig; spherical-inside flags are inapplicable, geographic coordinates and planar finite poses are checked.',records};
 }
}

export function flatSceneEligibility(scene,plan,fps=30,options={}){
 const core=new FlatSceneCore(scene,plan,options),observed=new Map((scene.visual_events||[]).filter(e=>e.meaningful!==false).map(e=>[e.id,{event_id:e.id,scene_id:scene.scene_id,kind:e.kind,target_id:e.target_id,coordinates:e.coordinates||null,scheduled_local_time:e.time,eligible_frames:0,eligible_primitives:new Set(),first_eligible_local_time:null,projection_at_scheduled_time:null,renderer_supported:FLAT_EVENT_KINDS.has(e.kind)}]));
 let opening=false;
 for(let frame=0;frame<Math.round(scene.duration*fps);frame++){
  const t=frame/fps,f=core.semanticFrame(t);
  const uncovered=options.visibilityFilter?options.visibilityFilter(t):true;
  if(uncovered&&flatNumber(scene.start_time)+t<3&&f.labels.some(l=>l.kind==='hook_reveal'&&l.opacity>.1))opening=true;
  if(uncovered)for(const e of f.events){const result=observed.get(e.event_id);if(!result)continue;result.first_eligible_local_time??=t;result.first_primitive??=e.rendered_primitive;result.eligible_frames++;result.eligible_primitives.add(e.rendered_primitive);}
  for(const result of observed.values())if(result.projection_at_scheduled_time===null&&t>=result.scheduled_local_time&&result.coordinates){const p=core.project(core.projection.point(result.coordinates));result.projection_at_scheduled_time={x:p.x/core.w,y:p.y/core.h,earth_occluded:false,depth_visible:p.visible,inside_event_safe_area:core.safe(core.projection.point(result.coordinates))};}
 }
 return {events:[...observed.values()].map(e=>({...e,visible_seconds:e.eligible_frames/fps,eligible_primitives:[...e.eligible_primitives]})),opening_hook_eligible:opening,failures:[],numeric:core.numericPreflight(fps),scope:'Shared flat rig and exact primitive/layout eligibility forecast. No WebGL pixels or aesthetic completion claim.'};
}
