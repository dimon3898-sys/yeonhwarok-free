// Pure geometry contract verification. Does not render images or claim visual QC.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.env.WORLD_ENGINE_ROOT||path.resolve(import.meta.dirname,'..');
const legacy=path.resolve(root,'../cinematic-world-map');
const THREE=await import(pathToFileURL(path.join(legacy,'node_modules/three/build/three.module.js')));
const {createAircraftV3}=await import(pathToFileURL(path.join(legacy,'src/aircraft_v3.js')));
const geo=(lon,lat,r=1)=>new THREE.Vector3(Math.cos(lat*Math.PI/180)*Math.cos(lon*Math.PI/180),Math.sin(lat*Math.PI/180),-Math.cos(lat*Math.PI/180)*Math.sin(lon*Math.PI/180)).multiplyScalar(r);
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
const source=fs.readFileSync(path.join(root,'web/earth_adapter.js'),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const {SceneRoutes,GenericCamera,GenericEntities,SceneEarthRenderer}=new Function('THREE','Renderer','RouteGraphics','createAircraftV3','geo','clamp','smooth',source+';return {SceneRoutes,GenericCamera,GenericEntities,SceneEarthRenderer};')(THREE,class {},{},createAircraftV3,geo,clamp,smooth);
const planPath=process.argv[2];if(!planPath)throw Error('Usage: node renderer_contract_test.mjs PLAN_JSON [OUTPUT_JSON]');
const plan=JSON.parse(fs.readFileSync(planPath,'utf8'));let previousExit=null;const results=[];
for(const scene of plan.scenes){
 const camera=new THREE.PerspectiveCamera(44,9/16,.02,30),routes=new SceneRoutes(scene),cam=new GenericCamera(camera,scene,routes),entities=new GenericEntities(scene,routes,new THREE.Group());
 const context={camera,cam,entities,routes,duration:scene.duration,lastFrameTime:0,w:2160,h:3840};
 const numeric=SceneEarthRenderer.prototype.numericPreflight.call(context);cam.update(0);
 const boundary=previousExit?{position_distance:previousExit.position.distanceTo(camera.position),quaternion_degrees:previousExit.quaternion.angleTo(camera.quaternion)*180/Math.PI}:null;
 let out=0,occluded=0,shown=0;const range=[Infinity,Infinity,-Infinity,-Infinity];
 for(let i=0;i<Math.round(scene.duration*30);i++){
  const time=i/30;cam.update(time);entities.update(time,camera);
  for(const {model} of entities.items){
   if(!model.visible||model.userData.alpha<.1)continue;
   const p=SceneEarthRenderer.prototype.project.call(context,model.position),normalized=[p.x/context.w,p.y/context.h];shown++;
   if(!p.visible)occluded++;
   if(p.visible&&(normalized[0]<0||normalized[0]>1||normalized[1]<0||normalized[1]>1))out++;
   range[0]=Math.min(range[0],normalized[0]);range[1]=Math.min(range[1],normalized[1]);range[2]=Math.max(range[2],normalized[0]);range[3]=Math.max(range[3],normalized[1]);
  }
 }
 cam.update(scene.duration);previousExit={position:camera.position.clone(),quaternion:camera.quaternion.clone()};
 const result={scene_id:scene.scene_id,...numeric,records:undefined,boundary,entity_shown_frames:shown,entity_out_of_frame:out,entity_occluded_frames:occluded,entity_screen_range:range.map(x=>Number.isFinite(x)?x:null)};
 result.passed=result.finite&&!result.entityWithinEarth&&!result.routeWithinEarth&&!result.cameraWithinEarth&&result.maxCameraAngleDegreesPerFrame<=2.5&&out===0&&occluded===0&&(!boundary||boundary.position_distance<1e-5&&boundary.quaternion_degrees<.01);
 results.push(result);console.log(JSON.stringify(result));
}
const evidence={created_at_utc:new Date().toISOString(),method:'Pure Three.js geometry and projection; no canvas or rendered-image claim',plan_source:planPath,passed:results.every(r=>r.passed),results};
if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(evidence,null,2),{flag:'wx'});
if(!evidence.passed)process.exitCode=1;
