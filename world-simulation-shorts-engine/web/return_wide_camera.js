/** v015 camera until 12s; explicit close-to-wide state transition after resolution. */
import {singleCameraValues,installSingleCamera,SceneSingleEventRenderer} from './single_event_camera.js';
export function returnCameraState(t){
 const bounds=[[2,'WIDE'],[3,'EVENT_LOCATION'],[5,'ZOOM_IN'],[6,'SETTLE'],[8,'EVENT_REVEAL'],[11,'EVENT_HOLD'],[12,'EVENT_RESOLVED'],[14,'ZOOM_OUT'],[15.000001,'FINAL_WIDE']];
 return bounds.find(([end])=>t<end)?.[1]||'END';
}
export function returnCameraValues(t,scene){
 if(t<12)return singleCameraValues(t,{...scene,camera_end:scene.return_wide_camera.event_camera});
 const a=scene.return_wide_camera.event_camera,b=scene.return_wide_camera.final_camera,u=Math.max(0,Math.min(1,(t-12)/2)),p=u*u*u*(u*(u*6-15)+10),v={p:0,e:p};
 for(const key of ['lon','lat','height','fov','yaw','tilt','bank'])v[key]=a[key]+(b[key]-a[key])*p;
 return v;
}
export function installReturnCamera(cam){installSingleCamera(cam);cam.values=t=>returnCameraValues(t,cam.scene);}
export class SceneReturnWideRenderer extends SceneSingleEventRenderer{
 async init(){
  await super.init();installReturnCamera(this.cam);
  const update=this.effects.update.bind(this.effects);
  this.effects.update=t=>{update(t);if(t>=11)for(const item of this.effects.items)if(item.event.kind==='route_blocked'){item.group.visible=false;if(item.group.userData.barrier)item.group.userData.barrier.visible=false;}};
  this.frame(0);return this;
 }
 audit(t){return {...super.audit(t),cameraState:returnCameraState(t),cameraFrame:Math.round(t*30),cameraPreset:'SINGLE_EVENT_RETURN_TO_WIDE_TEST'};}
}
