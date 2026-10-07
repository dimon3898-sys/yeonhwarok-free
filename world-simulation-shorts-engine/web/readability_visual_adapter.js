/** Additive presentation over the frozen production/V3 renderer. No GPU,
 * strict frame audit, textures, route coordinates or global-time changes. */
import * as THREE from 'three';
import {SceneProductionEarthRenderer} from './production_visual_adapter.js';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{const p=clamp(v);return p*p*(3-2*p);};
export function readableCameraPhase(t,scene){
 const s=scene.visual_readability,d=scene.duration,lead=s.initial_hold,travel=d-lead-s.final_hold;
 if(!(travel>0))throw Error('READABILITY_CAMERA_WINDOW_INVALID');
 const p=clamp((t-lead)/travel),a=s.acceleration_fraction;
 // Integral of a sinusoidal velocity ramp. Zero velocity at either hold;
 // no discontinuous stop, no perpetual ease-out zoom, no global resampling.
 if(!(a>0&&a<.5))throw Error('READABILITY_ACCELERATION_INVALID');
 const area=1-a;
 if(p<a)return (p/2-a*Math.sin(Math.PI*p/a)/(2*Math.PI))/area;
 if(p>1-a){const q=1-p;return 1-(q/2-a*Math.sin(Math.PI*q/a)/(2*Math.PI))/area;}
 return (p-a/2)/area;
}
const sphere=(lon,lat)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180));
const blendSphere=(a,b,p)=>a.clone().applyQuaternion(new THREE.Quaternion().identity().slerp(new THREE.Quaternion().setFromUnitVectors(a,b),p));
export function installReadableCamera(cam){
 const scene=cam.scene;if(scene.visual_readability?.version!=='readability_v011'||scene.camera_preset==='HORIZON_REVEAL')return;
 cam.values=t=>{
  const e=readableCameraPhase(t,scene),n=blendSphere(sphere(cam.start.lon,cam.start.lat),sphere(cam.end.lon,cam.end.lat),e);
  const value={lon:Math.atan2(-n.z,n.x)*180/Math.PI,lat:Math.asin(clamp(n.y,-1,1))*180/Math.PI,p:e,e};
  for(const key of ['height','tilt','yaw','bank','fov'])value[key]=cam.start[key]+(cam.end[key]-cam.start[key])*e;
  return value;
 };
 // Reduce the independent oscillating follow envelope, retaining true route time.
 cam.scene={...scene,camera_tracking:.12,camera_target_tracking:.16};
}
export function readableEntityScale(spec,camera,position,width,height){
 const base=spec.scale??(spec.type==='cargo_ship'?.0032:.0075);
 if(!['cargo_ship','aircraft'].includes(spec.type))return base;
 const requested=18*width/1080*camera.position.distanceTo(position)*Math.tan(camera.fov*Math.PI/360)/height;
 return Math.max(base,Math.min(spec.type==='cargo_ship'?.012:.020,requested));
}
export function installReadableEntities(app){
 const update=app.entities.update.bind(app.entities),base=new Map(app.entities.items.map(i=>[i.spec.id,i.spec.scale??(i.spec.type==='cargo_ship'?(app.sceneSpec.lighting_preset==='HERO'?.006:.0032):.0075)]));
 app.entities.update=(t,camera)=>{
  for(const item of app.entities.items){
   const spec=item.spec,r=spec.route_id?app.routes.byId(spec.route_id):null;
   const p=r?app.routes.progress(t,r):0,position=r?r.curve.getPoint(spec.action==='stop'?(spec.stop_progress??r.progress_start??0):clamp(p+(spec.phase_offset||0))):sphere(spec.coordinates?.lon??app.sceneSpec.coordinates.lon,spec.coordinates?.lat??app.sceneSpec.coordinates.lat);
   spec.scale=readableEntityScale({...spec,scale:base.get(spec.id)},camera,position,app.w,app.h);
  }
  // Existing grounding/vertex clearance/material alpha remain authoritative.
  update(t,camera);
 };
}
export function readableLighting(t,scene,value){
 const global=clamp(((scene.render_time_offset??scene.start_time??0)+t)/scene.visual_readability.total_duration);
 return {...value,exposure:1.14,surfaceFill:.14,cloudOpacity:Math.min(value.cloudOpacity,.22),
  dayWeight:.82-.22*smooth(global),hero:.35*smooth(global),cityGain:Math.max(value.cityGain,1.03)};
}
export function readableLabelScene(scene){
 const source=JSON.parse(JSON.stringify(scene));
 for(const label of source.labels||[]){label.color='#f4f3ec';if(label.coordinates?.location_id&&label.coordinates.location_id!==source.coordinates?.location_id)label.opacity=Math.min(label.opacity??1,.66);}
 return source;
}
export class SceneReadableEarthRenderer extends SceneProductionEarthRenderer {
 constructor(scene,plan){
  if(scene.visual_readability?.version!=='readability_v011')throw Error('READABILITY_POLICY_REQUIRED');
  super(readableLabelScene(scene),plan);this.readabilityReady=false;
 }
 async init(){
  await super.init();installReadableCamera(this.cam);installReadableEntities(this);
  // Bounded ocean-specular reduction, preserving the complete V3 lighting shader.
  const material=this.map.surface,token='vec3(1.,.90,.74)*spec';
  if(!material.fragmentShader.includes(token))throw Error('READABILITY_SPECULAR_CONTRACT_CHANGED');
  material.fragmentShader=material.fragmentShader.replace(token,'vec3(1.,.90,.74)*spec*.55');material.needsUpdate=true;
  this.readabilityReady=true;this.frame(0);return this;
 }
 lightingAt(t){const value=super.lightingAt(t);return this.sceneSpec.visual_readability?readableLighting(t,this.sceneSpec,value):value;}
 drawReadableRoutes(t){
  const c=this.ctx,k=this.w/1080;c.save();
  const shown=r=>t>=r.start||(r.progress_start>0);
  const primary=this.routes.routes.find(r=>!r.faint&&shown(r)&&t<r.end&&r.progress_end>r.progress_start)||this.routes.routes.find(r=>!r.faint&&shown(r));
  for(const r of this.routes.routes){
   const progress=this.routes.progress(t,r);if((t<r.start&&!(r.progress_start>0))||progress<=0)continue;
   const secondary=r.faint||primary&&r.id!==primary.id,steps=Math.max(2,Math.ceil(progress*120));let previous=null;
   for(let i=0;i<=steps;i++){
    const p=progress*i/steps,point=this.project(r.curve.getPoint(p)),on=point.visible&&point.x>=0&&point.x<=this.w&&point.y>=0&&point.y<=this.h;
    if(previous&&on&&previous.on&&Math.hypot(point.x-previous.x,point.y-previous.y)<this.w*.25){
     c.globalAlpha=secondary?.18:.28+.60*Math.exp(-(progress-p)*13);
     c.lineCap='round';c.beginPath();c.moveTo(previous.x,previous.y);c.lineTo(point.x,point.y);
     c.strokeStyle='#113442';c.lineWidth=(secondary?2:5)*k;c.stroke();c.strokeStyle='#9cdee5';c.lineWidth=(secondary?1:3)*k;c.stroke();
    }previous={...point,on};
   }
   const head=this.project(r.curve.getPoint(progress));
   if(!secondary&&t<r.end&&head.visible&&head.x>=0&&head.x<this.w&&head.y>=0&&head.y<this.h){c.globalAlpha=.95;c.fillStyle='#e4f7f2';c.beginPath();c.arc(head.x,head.y,3.2*k,0,2*Math.PI);c.fill();}
  }c.restore();
 }
 overlay(t){
  if(this.readabilityReady)this.drawReadableRoutes(t);
  super.overlay(t);if(!this.readabilityReady)return;
  const c=this.ctx,k=this.w/1080;
  // Short, measured local support only; no fog/veil, enlarged slogan or HUD.
  for(const box of this.labels){
   c.save();c.globalAlpha=box.opacity;c.fillStyle='rgba(5,19,28,.46)';c.fillRect(box.x-5*k,box.y-2*k,box.width+10*k,box.height+4*k);
   c.font=`400 ${box.font}px 'Noto Cinema'`;c.fillStyle='#f4f3ec';c.shadowColor='rgba(4,15,22,.8)';c.shadowBlur=2*k;
   let x=box.x;for(const char of box.text){c.fillText(char,x,box.y+box.font);x+=c.measureText(char).width+1.8*k;}
   c.restore();
  }
 }
 audit(t){const value=super.audit(t);value.visualReadability={version:'readability_v011',camera_policy:this.sceneSpec.camera_preset==='HORIZON_REVEAL'?'preserved_native_horizon_tracking':'accelerate_decelerate_settle',camera_phase:this.sceneSpec.camera_preset==='HORIZON_REVEAL'?null:readableCameraPhase(t,this.sceneSpec),initial_hold:this.sceneSpec.camera_preset==='HORIZON_REVEAL'?0:this.sceneSpec.visual_readability.initial_hold,final_hold:this.sceneSpec.camera_preset==='HORIZON_REVEAL'?0:this.sceneSpec.visual_readability.final_hold,route_core_pixels_1080:3,software_gpu_fallback:false};return value;}
}
