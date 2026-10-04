import * as THREE from 'three';
import fs from 'node:fs';
import path from 'node:path';
import {CameraController,RouteAnimator,EntityAnimator,SceneManager,CITIES,SHOTS} from '../src/engine_v3.js';
const root=path.resolve(import.meta.dirname,'..'),output=path.join(root,'outputs/v3_scene.json');
const camera=new THREE.PerspectiveCamera(44,9/16,.00001,30),routes=new RouteAnimator(),entities=new EntityAnimator(routes),scenes=new SceneManager();
const cam=new CameraController(camera,routes);
const convert=v=>[v[0],-v[2],v[1]];
function evaluate(t){let pose=cam.update(t),entity=entities.update(t,camera);return {t,camera:{matrix:camera.matrixWorld.toArray(),position:convert(camera.position.toArray()),fov:camera.fov,...pose},entity:{matrix:entities.model.matrixWorld.toArray(),...entity},progress:routes.routes.map(r=>routes.progress(t,r)),shot:scenes.shot(t).name}}
const model=[];entities.model.traverse(m=>{if(!m.isMesh)return;m.updateMatrix();model.push({name:m.name||'AIRCRAFT_PART_'+model.length,position:Array.from(m.geometry.attributes.position.array),normal:Array.from(m.geometry.attributes.normal.array),index:m.geometry.index?Array.from(m.geometry.index.array):null,matrix:m.matrix.toArray(),material:{color:m.material.color.toArray(),roughness:m.material.roughness??.5,metalness:m.material.metalness??0,emission:m.material.emissive?.toArray()||[0,0,0]}})});
const frames=Array.from({length:1201},(_,i)=>evaluate(i/60));
const data={schema:1,coordinate_conversion:'(x,y,z) -> (x,-z,y), right-handed',earth_radius_km:6371,fps:30,frames,cities:CITIES,shots:SHOTS,events:scenes.events,routes:routes.routes.map(r=>({a:r.a,b:r.b,start:r.start,end:r.end,points:Array.from({length:721},(_,i)=>convert(r.curve.getPoint(i/720).toArray())),base_altitude_km:11,max_altitude_km:15})),model};
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(data));console.log(JSON.stringify({output,poses:frames.length,aircraft_parts:model.length,events:data.events.length}));
