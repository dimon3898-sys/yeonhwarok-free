import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve('.');
const THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const scene=JSON.parse(fs.readFileSync(process.argv[2])).scenes[0];
const code=fs.readFileSync(path.join(root,'web/single_event_camera.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const {installSingleCamera}=new Function('THREE','SceneProductionEarthRenderer',code+';return {installSingleCamera};')(THREE,class{});
const cam={scene,camera:new THREE.PerspectiveCamera(64,9/16,.02,30)};installSingleCamera(cam);
const frames=[];
for(let frame=0;frame<=360;frame++){
 const values=cam.update(frame/30);
 frames.push({frame,seconds:frame/30,position:cam.camera.position.toArray(),quaternion:cam.camera.quaternion.toArray(),fov:cam.camera.fov,height:values.height});
}
for(let k=1;k<=90;k++)assert.deepEqual(frames[k],{...frames[0],frame:k,seconds:k/30});
for(let k=150;k<=360;k++)assert.deepEqual(frames[k],{...frames[150],frame:k,seconds:k/30});
for(let k=91;k<=150;k++){assert(frames[k].height<=frames[k-1].height);assert(frames[k].fov<=frames[k-1].fov);}
for(const frame of frames)assert(new THREE.Quaternion(...frame.quaternion).angleTo(new THREE.Quaternion(...frames[0].quaternion))<1e-6);
function occupancy(frame){
 cam.update(frame/30);let hit=0,total=0;const ray=new THREE.Raycaster(),sphere=new THREE.Sphere(new THREE.Vector3(),1),point=new THREE.Vector3();
 for(let y=0;y<160;y++)for(let x=0;x<90;x++){ray.setFromCamera(new THREE.Vector2((x+.5)/90*2-1,1-(y+.5)/160*2),cam.camera);total++;if(ray.ray.intersectSphere(sphere,point))hit++;}
 return hit/total;
}
const wide=occupancy(0),close=occupancy(150);assert(close>wide*2);assert(close>.95);
console.log(JSON.stringify({passed:true,frames,wide:{distance:3.5,height:2.5,fov:64,target:scene.coordinates,earth_screen_occupancy:wide},event:{distance:1.2,height:.2,fov:48,target:scene.coordinates,earth_screen_occupancy:close},occupancy_scope:'native projected Earth ray coverage, not GPU pixels',GPU:'NOT_RUN'}));
