/** Test-only camera. Production rendering, text, lighting, assets and audio are inherited. */
import * as THREE from 'three';
import {SceneProductionEarthRenderer} from './production_visual_adapter.js';
export function singleCameraValues(t,scene){
 const a=scene.camera_start,b=scene.camera_end;
 const u=Math.max(0,Math.min(1,(t-3)/2)),p=u*u*u*(u*(u*6-15)+10);
 const value={p:0,e:p};
 for(const key of ['lon','lat','height','fov','yaw','tilt','bank'])value[key]=a[key]+(b[key]-a[key])*p;
 return value;
}
export function installSingleCamera(cam){
 cam.values=t=>singleCameraValues(t,cam.scene);
 cam.scene={...cam.scene,camera_tracking:0,camera_target_tracking:0};
 cam.update=t=>{
  const v=cam.values(t),lat=v.lat*Math.PI/180,lon=v.lon*Math.PI/180;
  const n=new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));
  const up=new THREE.Vector3(-Math.sin(lat)*Math.cos(lon),Math.cos(lat),Math.sin(lat)*Math.sin(lon));
  cam.camera.position.copy(n).multiplyScalar(1+v.height);cam.camera.up.copy(up);
  cam.camera.fov=v.fov;cam.camera.updateProjectionMatrix();cam.camera.lookAt(n.clone().multiplyScalar(.99));cam.camera.updateMatrixWorld();return v;
 };
}
export class SceneSingleEventRenderer extends SceneProductionEarthRenderer{
 async init(){await super.init();installSingleCamera(this.cam);this.frame(0);return this;}
}
