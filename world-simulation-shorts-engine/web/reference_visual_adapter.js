/** REFERENCE_MASTER v013: exact lock after reference-authored travel. Legacy v012 unchanged. */
import * as THREE from 'three';
import {SceneProductionEarthRenderer,SceneProductionFlatRenderer} from './production_visual_adapter.js';
import {SceneReadableEarthRenderer} from './readability_visual_adapter.js';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
function ramp(v){
 const p=clamp(v),a=.20,area=1-a;
 if(p<a)return (p/2-a*Math.sin(Math.PI*p/a)/(2*Math.PI))/area;
 if(p>1-a){const q=1-p;return 1-(q/2-a*Math.sin(Math.PI*q/a)/(2*Math.PI))/area;}
 return (p-a/2)/area;
}
const sphere=(lon,lat)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180));
export function directionPhase(t,scene){
 const p=scene.direction;if(!p||!(p.move_end>p.initial_hold))throw Error('DIRECTION_CAMERA_WINDOW_INVALID');
 // Smootherstep gives acceleration, deceleration, then an exact stationary end.
 const u=clamp((t-p.initial_hold)/(p.move_end-p.initial_hold));return ramp(u);
}
export function installDirectionCamera(cam){
 const s=cam.scene;if(!s.direction)return;
 cam.values=t=>{
  const p=directionPhase(t,s),a=sphere(cam.start.lon,cam.start.lat),b=sphere(cam.end.lon,cam.end.lat);
  const theta=a.angleTo(b),hasPan=theta>.03,zoomDelta=Math.abs(cam.end.height-cam.start.height)>.05;
  // A strong geographical pan and zoom occupy separate intervals.
  const u=clamp((t-s.direction.initial_hold)/(s.direction.move_end-s.direction.initial_hold));
  const pan=hasPan&&zoomDelta?ramp(u/.68):p,zoom=hasPan&&zoomDelta?ramp((u-.68)/.32):p;
  const n=a.clone().applyQuaternion(new THREE.Quaternion().identity().slerp(new THREE.Quaternion().setFromUnitVectors(a,b),pan));
  // The frozen rig uses p for independent orbit/follow oscillations. Disable
  // that auxiliary envelope here; e still carries the actual directed pose.
  const value={lon:Math.atan2(-n.z,n.x)*180/Math.PI,lat:Math.asin(clamp(n.y,-1,1))*180/Math.PI,p:0,e:pan};
  for(const key of ['height','tilt','yaw','bank','fov'])value[key]=cam.start[key]+(cam.end[key]-cam.start[key])*(key==='height'?zoom:p);
  return value;
 };
 // Independent follow oscillation must not restart motion inside the read gate.
 // Physical ship/aircraft progress remains on the authored scene clock.
 cam.scene={...s,camera_tracking:0,camera_target_tracking:0};
 const update=cam.update.bind(cam);
 cam.update=t=>{
  const value=update(t),n=sphere(value.lon,value.lat),start=sphere(cam.start.lon,cam.start.lat);
  const transport=new THREE.Quaternion().setFromUnitVectors(start,n);
  const north=new THREE.Vector3(...s.direction.camera_up_start).applyQuaternion(transport).normalize().applyAxisAngle(n,(s.direction.camera_roll_correction||0)*directionPhase(t,s));
  const east=new THREE.Vector3().crossVectors(north,n).normalize();
  // A geographic north reference has no radial-up threshold switch while
  // looking toward the surface. It prevents the frozen rig's roll reversal.
  cam.camera.position.copy(n.clone().multiplyScalar(1+value.height)).addScaledVector(north,-value.tilt*value.height).addScaledVector(east,value.yaw*value.height);
  cam.camera.up.copy(north);cam.camera.lookAt(n.multiplyScalar(.99));
  cam.camera.updateMatrixWorld();return value;
 };
}
export function installDirectionFlat(core){
 if(!core.sceneSpec.direction)return;
 const cam=core.cam;
 cam.values=t=>{
  const e=directionPhase(t,core.sceneSpec),a=cam.projection.point(cam.start),b=cam.projection.point(cam.end);
  const pan=a.distanceTo(b)>1,zoom=Math.abs(cam.end.span_degrees-cam.start.span_degrees)>1;
  const pe=pan&&zoom?smooth(e/.68):e,ze=pan&&zoom?smooth((e-.68)/.32):e;
  const center=a.lerp(b,pe);
  let span=cam.start.span_degrees+(cam.end.span_degrees-cam.start.span_degrees)*ze;
  let tilt=cam.start.tilt+(cam.end.tilt-cam.start.tilt)*e;
  const scene=core.sceneSpec,duration=Math.max(.15,Math.min(1.5,Number(scene.map_transition?.duration??scene.flat_map?.transition_duration??.42)));
  let handoff=0;
  // Outgoing projection opacity stays on the frozen handoff clock;
  // geometry remains locked while the information is read.
  // Incoming travel may accommodate the registered projection change.
  if(scene.transition_in==='EARTH_TO_FLAT')handoff=Math.max(handoff,1-smooth(t/duration));
  // Keep the approved projection handoff on its real clock; only travel uses
  // the new read gate. No change to the registered projection or terrain.
  span*=1+.28*handoff;tilt+=(.15-tilt)*handoff;
  return {p:e,e,center,span,projectionHandoff:handoff,
   tilt,rotation:cam.start.rotation+(cam.end.rotation-cam.start.rotation)*e,
   bank:cam.start.bank+(cam.end.bank-cam.start.bank)*e,previewWeight:0};
 };
}
export function directionLabelScene(scene){
 const result=JSON.parse(JSON.stringify(scene));if(!result.direction)return result;
 const current=result.coordinates?.location_id;
 // Keep one current location. Earlier destinations retain factual metadata in
 // Scene JSON, while their redundant screen labels are not all emphasized.
 const primaryText=(result.text_events||[]).find(t=>t.event_id===result.direction.primary_event_id);
 result.labels=(result.labels||[]).filter(label=>label.event_id||(label.coordinates?.location_id===current&&label.text!==primaryText?.text));
 for(const label of result.labels){
  const location=['city','country','location'].includes(label.role);
  label.color='#f4f3ec';label.size=location?42:50;label.opacity=location?.55:.98;
  if(!location&&!label.event_id&&label.kind!=='hook_reveal')label.start_time=Math.max(label.start_time||0,result.direction.move_end);
 }
 return result;
}
export function directionLabelsAt(scene,t){
 const source=scene.labels||[],active=source.filter(l=>t>=Number(l.start_time||0)&&t<=Number(l.end_time??scene.duration));
 const rank=l=>l.event_id&&l.event_id===scene.direction.primary_event_id?120:l.role==='distance'?10:l.event_id?100:l.kind==='hook_reveal'?90:['city','country','location'].includes(l.role)?70:60;
 const primary=[...active].sort((a,b)=>rank(b)-rank(a))[0];
 // Below .55, the approved fade/semantic-alpha contract can reveal a bound
 // support label two frames after its core SFX. Keep it subordinate by rank
 // and size without delaying its factual visibility receipt.
 return source.map(l=>({...l,opacity:l===primary?.98:Math.min(l.opacity??1,.35),size:l===primary?50:40}));
}
export function directionLighting(t,scene,value){
 const policy=scene.direction.lighting,entry=scene.direction.lighting_entry||policy;
 const blend=smooth(t/Math.max(.1,scene.direction.move_end));
 const lerp=(key)=>entry[key]+(policy[key]-entry[key])*blend;
 return {...value,exposure:lerp('exposure'),surfaceFill:lerp('surface_fill'),
  cloudOpacity:Math.min(value.cloudOpacity,lerp('cloud_opacity')),dayWeight:lerp('day_weight'),
  cityGain:lerp('city_gain'),hero:scene.direction.intent==='RESULT_HERO'?.27:0};
}
export function installDirectionEntities(app){
 const update=app.entities.update.bind(app.entities),policy=app.sceneSpec.direction;
 const base=new Map(app.entities.items.map(i=>[i.spec.id,i.spec.scale??(i.spec.type==='cargo_ship'?(app.sceneSpec.lighting_preset==='HERO'?.006:.0032):.0075)]));
 app.entities.update=(t,camera)=>{
  for(const item of app.entities.items){
   const spec=item.spec;if(!['cargo_ship','aircraft'].includes(spec.type))continue;
   const r=spec.route_id?app.routes.byId(spec.route_id):null,p=r?app.routes.progress(t,r):0;
   const position=r?r.curve.getPoint(spec.action==='stop'?(spec.stop_progress??r.progress_start??0):clamp(p+(spec.phase_offset||0))):sphere(spec.coordinates?.lon??app.sceneSpec.coordinates.lon,spec.coordinates?.lat??app.sceneSpec.coordinates.lat);
   const requested=policy.entity_min_pixels_1080*app.w/1080*camera.position.distanceTo(position)*Math.tan(camera.fov*Math.PI/360)/(.9*app.h);
   spec.scale=Math.max(base.get(spec.id),Math.min(spec.type==='cargo_ship'?policy.entity_scale_cap:.024,requested));
  }
  update(t,camera); // Preserve alpha, route progress and the actual posed mesh.
  for(const item of app.entities.items){
   if(item.spec.type!=='aircraft')continue;
   const {model,bounds}=item,radial=model.position.clone().normalize();let minimum=Infinity;
   for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])minimum=Math.min(minimum,new THREE.Vector3(x,y,z).multiply(model.scale).applyQuaternion(model.quaternion).add(model.position).dot(radial));
   // Cartographic display clearance for the enlarged proxy. The verified
   // route and its physical altitude are unchanged; no audit is bypassed.
   const lift=Math.max(0,1+.035/6371-minimum);
   model.position.addScaledVector(radial,lift);model.userData.displayClearanceLift=lift;model.updateMatrixWorld(true);
  }
 };
}
/** Approved geographic label layout with a versioned 0.16s reveal, shared
 * by actual drawing and native prediction. Clipping/receipt thresholds stay
 * unchanged; a slower inherited fade must not make SFX precede information. */
export function drawDirectionLabels(t){
 if(this.sceneSpec.text_density==='NONE'){this.labels=[];this.eventVisibility=[];return;}
 const flatCoordinate=value=>{const q=value?.coordinates||value;return {lon:Number(q.lon??q.longitude??q[0]),lat:Number(q.lat??q.latitude??q[1])};};
 const incomingCityBoxes=this.incomingCityBoxes;
 if(!incomingCityBoxes)this.incomingCityBoxes=()=>[];
 try {

  this.labels=[];const c=this.ctx,scale=this.w/1080,placed=[];
  const handoff=this.geographicHandoff,blend=handoff?smooth(t/handoff.duration):1,incoming=this.incomingCityBoxes();
  const candidates=[...(this.sceneSpec.labels||[])];
  for(const e of this.sceneSpec.visual_events||[])if(['destination_preview','region_reveal','country_reveal'].includes(String(e.kind).toLowerCase())&&e.coordinates&&e.text)candidates.push({text:e.text,event_id:e.id,kind:'world_label',coordinates:e.coordinates,start_time:e.time,end_time:e.time+1.4,opacity:.96,offset_x:90,offset_y:110});
  for(const label of candidates){
   if(!label.text||!label.coordinates)continue;const start=Number(label.start_time||0),end=Number(label.end_time??this.duration);
   const hold=this.sceneSpec.scene_type==='FINAL_OVERVIEW'&&end>=this.duration-1e-6,fade=Math.min(.16,Math.max(.01,(end-start)/3));
   let opacity=t<start||t>end?0:smooth((t-start)/fade)*(hold?1:1-smooth((t-end+.4)/.4));
   const previous=incoming.find(b=>b.text===label.text),registered=previous&&handoff&&t<handoff.duration;
   if(registered)opacity=Math.max(opacity,previous.opacity*(1-blend));
   if(opacity<.01)continue;const q=flatCoordinate(label.coordinates),point=new THREE.Vector3(Math.cos(q.lat*Math.PI/180)*Math.cos(q.lon*Math.PI/180),Math.sin(q.lat*Math.PI/180),-Math.cos(q.lat*Math.PI/180)*Math.sin(q.lon*Math.PI/180)).multiplyScalar(1+.003*blend),p=this.project(point);
   if(!p.visible||p.x<this.w*.04||p.x>this.w*.96||p.y<this.h*.10||p.y>this.h*.78)continue;
   const font=Math.max(34,Number(label.size||46))*scale,spacing=1.8*scale;c.save();c.font=`400 ${font}px 'Noto Cinema'`;
   const width=c.measureText(label.text).width+Math.max(0,[...label.text].length-1)*spacing;
   let x=clamp(p.x+Number(label.offset_x??100)*scale,this.w*.13+width/2,this.w*.83-width/2)-width/2,y=clamp(p.y+Number(label.offset_y??110)*scale,this.h*.15+font,this.h*.78)-font;
   if(registered){x=previous.x+(x-previous.x)*blend;y=previous.y+(y-previous.y)*blend;}
   let box={text:label.text,event_id:label.event_id||null,kind:label.kind||'world_label',opacity:opacity*Number(label.opacity??.96),x,y,width,height:font*1.25,font,fontFamily:'Noto Cinema',anchor:p,incomingAircraftAvoidance:registered?previous.aircraftAvoidance:null};
   let tries=0;while(placed.some(b=>box.x<b.x+b.width+10*scale&&box.x+box.width>b.x-10*scale&&box.y<b.y+b.height+10*scale&&box.y+box.height>b.y-10*scale)&&tries++<4)box.y+=font*1.3;
   if(box.y+box.height>this.h*.82){c.restore();continue;}
   // A small feathered text shadow supports city names over dense amber lights.
   // It is local to the measured name box, never a map-wide opacity veil.
   c.save();c.translate(box.x+width/2,box.y+font*.65);c.scale((width+30*scale)/(font+20*scale),1);
   const radius=font*.92,shade=c.createRadialGradient(0,0,0,0,0,radius),support=.28*blend;
   shade.addColorStop(0,`rgba(3,12,22,${support})`);shade.addColorStop(.6,`rgba(3,12,22,${support*.7})`);shade.addColorStop(1,'rgba(3,12,22,0)');c.fillStyle=shade;c.fillRect(-radius,-radius,2*radius,2*radius);c.restore();
   c.globalAlpha=box.opacity;c.fillStyle=label.color||'#f3f1e5';c.shadowColor='rgba(6,22,31,.90)';c.shadowBlur=3*scale;c.shadowOffsetY=scale;c.strokeStyle='rgba(7,25,36,.78)';c.lineWidth=1.45*scale;
   let at=box.x;for(const ch of label.text){c.strokeText(ch,at,box.y+font);c.fillText(ch,at,box.y+font);at+=c.measureText(ch).width+spacing;}
   c.restore();this.labels.push(box);placed.push(box);
  }
  this.drawStoryInformation(t);
 }finally{if(!incomingCityBoxes)delete this.incomingCityBoxes;}
}
export function directionAudit(scene,t,labels=[]){
 const p=scene.direction,warnings=[];
 const boxes=labels.filter(l=>l.opacity>.1);
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
  const a=boxes[i],b=boxes[j];if(a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y)
   warnings.push({code:'LABEL_COLLISION',severity:'WARNING'});
 }
 if(boxes.length>3)warnings.push({code:'INFORMATION_DENSITY_HIGH',severity:'WARNING'});
 return {version:p.version,intent:p.intent,phase:directionPhase(t,scene),settled:t>=p.move_end,
  protected_settle:p.settle,reveal_time:p.reveal_time,reveal_to_next_move:p.perception_hold,required_perception_hold:p.required_hold,camera_locked:t>=p.move_end,perception_active:t>=p.reveal_time,next_major_move:p.next_major_move,text_visibility:boxes.map(b=>({text:b.text,event_id:b.event_id,opacity:b.opacity,box:[b.x,b.y,b.width,b.height]})),primary:p.primary,zoom_information_level:p.zoom_level,warnings,pixel_checks:'ACTUAL_FRAME_AUDIT_REQUIRED'};
}
function directionPixelMetrics(app,t){
 const frame=Math.round(t*30);
 if(app.directionPixelAudit&&frame%15!==0)return app.directionPixelAudit;
 const canvas=app.directionSampleCanvas||(app.directionSampleCanvas=document.createElement('canvas'));
 canvas.width=32;canvas.height=56;
 const c=canvas.getContext('2d',{willReadFrequently:true});c.drawImage(app.canvas,0,0,32,56);
 const pixels=c.getImageData(0,0,32,56).data;let body=0,total=0,dark=0;
 const origin=app.camera.position,ray=new THREE.Vector3();
 for(let y=0;y<56;y++)for(let x=0;x<32;x++){
  ray.set((x+.5)/16-1,1-(y+.5)/28,.5).unproject(app.camera).sub(origin).normalize();
  const b=origin.dot(ray),disc=b*b-origin.lengthSq()+1;if(disc<=0||-b-Math.sqrt(disc)<0)continue;
  const i=(y*32+x)*4,l=(pixels[i]*.2126+pixels[i+1]*.7152+pixels[i+2]*.0722)/255;
  body++;total+=l;if(l<.08)dark++;
 }
 const routeContrast=[];
 for(const r of app.routes.routes){
  if(r.faint||t<r.start||t>r.end)continue;const head=app.project(r.curve.getPoint(app.routes.progress(t,r)));
  const k=app.w/1080,half=Math.ceil(8*k),x=Math.round(head.x)-half,y=Math.round(head.y)-half;
  if(!head.visible||x<0||y<0||x+half*2>=app.w||y+half*2>=app.h)continue;
  const patch=app.ctx.getImageData(x,y,half*2,half*2).data,background=[];let peak=0;
  for(let i=0;i<patch.length;i+=4){const px=(i/4)%(half*2),py=Math.floor(i/4/(half*2));
   const l=(patch[i]*.2126+patch[i+1]*.7152+patch[i+2]*.0722)/255;
   if(Math.hypot(px-half,py-half)<3*k)peak=Math.max(peak,l);else if(Math.hypot(px-half,py-half)>6*k)background.push(l);
  }
  background.sort((a,b)=>a-b);routeContrast.push({route_id:r.id,luminance_delta:peak-(background[Math.floor(background.length/2)]||0)});
 }
 return app.directionPixelAudit={measurement:'MEASURED_COMPOSITED_FRAME',frame_index:frame,
  earth_screen_occupancy:body/(32*56),geography_mean_luma:body?total/body:null,
  geography_dark_fraction:body?dark/body:null,route_head_contrast:routeContrast};
}
export class SceneDirectionEarthRenderer extends SceneProductionEarthRenderer {
 constructor(scene,plan){super(directionLabelScene(scene),plan);this.directionReady=false;}
 async init(){
  await super.init();installDirectionCamera(this.cam);installDirectionEntities(this);
  const material=this.map.surface,token='vec3(1.,.90,.74)*spec';
  if(!material.fragmentShader.includes(token))throw Error('DIRECTION_SPECULAR_CONTRACT_CHANGED');
  material.fragmentShader=material.fragmentShader.replace(token,'vec3(1.,.90,.74)*spec*.45');material.needsUpdate=true;
  this.directionReady=true;this.frame(0);return this;
 }
 lightingAt(t){const value=super.lightingAt(t);return this.sceneSpec.direction?directionLighting(t,this.sceneSpec,value):value;}
 overlay(t){
  if(this.directionReady){
   const ctx=this.ctx,stroke=ctx.stroke.bind(ctx),width=this.sceneSpec.direction.route_width_1080;
   // The approved path overlay retains its geometry, occlusion and priority;
   // adapt only the primary 3px/5px stroke pair to the planned zoom level.
   ctx.stroke=()=>{const k=this.w/1080;if(Math.abs(ctx.lineWidth-3*k)<.0001)ctx.lineWidth=width*k;else if(Math.abs(ctx.lineWidth-5*k)<.0001)ctx.lineWidth=(width+2)*k;stroke();};
   try{SceneReadableEarthRenderer.prototype.drawReadableRoutes.call(this,t);}finally{ctx.stroke=stroke;}
  }
  const original=this.sceneSpec;
  this.sceneSpec={...original,labels:directionLabelsAt(original,t).map(label=>{
   const anchored=label.route_id&&(['distance','route'].includes(label.role)||label.display_anchor==='route_head');
   const route=anchored?this.routes.byId(label.route_id):null;if(!route)return label;
   const point=route.curve.getPoint(this.routes.progress(t,route)).normalize();
   return {...label,coordinates:{...label.coordinates,lon:Math.atan2(-point.z,point.x)*180/Math.PI,lat:Math.asin(clamp(point.y,-1,1))*180/Math.PI}};
  })};
  try{if(this.directionReady)drawDirectionLabels.call(this,t);else super.overlay(t);}finally{this.sceneSpec=original;}
 }
 audit(t){
  const value=super.audit(t);value.direction=directionAudit(this.sceneSpec,t,this.labels);
  for(const e of value.entities||[])if(e.visible&&e.screenVisible&&e.visibility_role==='primary'&&2*e.screenRadius*1080/this.w<this.sceneSpec.direction.entity_min_pixels_1080)
   value.direction.warnings.push({code:'ENTITY_TOO_SMALL',severity:'WARNING',entity_id:e.id,screen_pixels_1080:2*e.screenRadius*1080/this.w});
  if(this.directionReady){
   try{
    const m=directionPixelMetrics(this,t);value.direction.pixel_metrics=m;
    if(m.geography_mean_luma!==null&&m.geography_mean_luma<.08)value.direction.warnings.push({code:'GEOGRAPHY_TOO_DARK',severity:'WARNING'});
    if(this.sceneSpec.direction.intent==='RESULT_HERO'&&t>=this.sceneSpec.direction.move_end&&m.earth_screen_occupancy<.38)value.direction.warnings.push({code:'RESULT_HERO_TOO_SMALL',severity:'WARNING'});
    if(m.route_head_contrast.some(r=>r.luminance_delta<.12))value.direction.warnings.push({code:'ROUTE_LOW_CONTRAST',severity:'WARNING'});
   }catch{value.direction.pixel_metrics={measurement:'UNAVAILABLE',code:'DIRECTION_PIXEL_SAMPLE_FAILED'};}
  }
  return value;
 }
}
export class SceneDirectionFlatRenderer extends SceneProductionFlatRenderer {
 constructor(scene,plan){super(directionLabelScene(scene),plan);}
 async init(){await super.init();installDirectionFlat(this.core);
  const overlay=this.core.overlayLabels.bind(this.core);
  this.core.overlayLabels=t=>{const original=this.core.sceneSpec;this.core.sceneSpec={...original,labels:directionLabelsAt(original,t)};try{return overlay(t);}finally{this.core.sceneSpec=original;}};
  this.frame(0);return this;}
 audit(t){const value=super.audit(t);value.direction=directionAudit(this.sceneSpec,t,value.labels||this.labels||[]);return value;}
}
