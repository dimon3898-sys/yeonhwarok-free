/** Camera-only continuation. All graphics, effects, audio and first-event poses inherited. */
import * as THREE from 'three';
import {returnCameraValues,installReturnCamera,SceneReturnWideRenderer} from './return_wide_camera.js';
export function secondCameraState(t){
 const steps=[['EVENT1_WIDE',2],['EVENT1_LOCATION',3],['EVENT1_ZOOM_IN',5],['EVENT1_VIEW',6],['EVENT1_HOLD',11],['EVENT1_RESOLVED',12],['ZOOM_OUT',14],['ADAPTIVE_WIDE',15],['EVENT2_LOCATION',16.5],['EVENT2_ZOOM_IN',19.5],['EVENT2_VIEW',20.5],['EVENT2_HOLD',24]];
 return steps.find(([,end])=>t<end)?.[0]||'END';
}
function normal(v){const lat=v.lat*Math.PI/180,lon=v.lon*Math.PI/180;return new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));}
function transition(a,b,u){
 const x=Math.max(0,Math.min(1,u)),p=x*x*x*(x*(x*6-15)+10),n=normal(a),m=normal(b),angle=n.angleTo(m);
 if(angle>1e-8)n.multiplyScalar(Math.sin((1-p)*angle)/Math.sin(angle)).add(m.multiplyScalar(Math.sin(p*angle)/Math.sin(angle)));n.normalize();
 const v={p:0,e:p,lon:Math.atan2(-n.z,n.x)*180/Math.PI,lat:Math.asin(n.y)*180/Math.PI};
 for(const key of ['height','fov','yaw','tilt','bank'])v[key]=a[key]+(b[key]-a[key])*p;
 return v;
}
export function secondCameraValues(t,scene){
 const c=scene.second_event_camera;
 if(t<12)return returnCameraValues(t,{...scene,return_wide_camera:{event_camera:c.event1_camera,final_camera:scene.camera_start}});
 if(t<14)return transition(c.event1_camera,c.adaptive_camera,(t-12)/2);
 if(t<16.5)return {...c.adaptive_camera,p:0,e:0};
 if(t<19.5)return transition(c.adaptive_camera,c.event2_camera,(t-16.5)/3);
 return {...c.event2_camera,p:0,e:1};
}
export function installSecondCamera(cam){
 preserveFirstEventFocus(cam.scene);
 installReturnCamera(cam);cam.values=t=>secondCameraValues(t,cam.scene);
}
export function preserveFirstEventFocus(scene){
 // Frozen Earth init uses the first three geographic labels as shader focus
 // slots. Append the new location after existing resolved-event labels so the
 // approved first-event lighting and label ordering remain identical.
 const next=scene?.second_event_camera?.next_coordinates;
 if(next&&scene.labels)scene.labels.sort((a,b)=>Number(a.coordinates?.location_id===next.location_id)-Number(b.coordinates?.location_id===next.location_id));
}
export class SceneSecondEventRenderer extends SceneReturnWideRenderer{
 constructor(scene,plan){super(scene,plan);preserveFirstEventFocus(this.sceneSpec);}
 async init(){
  // The inherited resolved-state effect/barrier cleanup stays unchanged.
  this.sceneSpec.return_wide_camera={event_camera:this.sceneSpec.second_event_camera.event1_camera,final_camera:this.sceneSpec.camera_start};
  await super.init();installSecondCamera(this.cam);this.frame(0);return this;
 }
 audit(t){return {...super.audit(t),cameraState:secondCameraState(t),cameraFrame:Math.round(t*30),cameraPreset:'SECOND_EVENT_ADAPTIVE_WIDE_TEST'};}
}
