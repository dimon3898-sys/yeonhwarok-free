/** CPU-only checks of the real aircraft meshes, registered morph camera and
 * separation adapter. This creates no WebGL context and renders no video.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const THREE=await import(new URL('../../cinematic-world-map/node_modules/three/build/three.module.js',import.meta.url));
const read=file=>fs.readFileSync(path.join(root,file),'utf8');
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex');
const strip=source=>source.replace(/^import .*;\s*$/gm,'').replace(/^export /gm,'');
const load=(file,args,names)=>new Function(...Object.keys(args),strip(read(file))+`;return {${names.join(',')}};`)(...Object.values(args));
const frozen={
 'web/flat_renderer.js':'144487d6824a10cedb4c002629620859817d0b0b89e4fdc65d805c6e29c8dde4',
 'web/flat_semantics.js':'cd023936304a4579f1fe52849c66b47c5e94d69958c714e437b371dce511eedd',
 'web/flat_polish_renderer.js':'329e0da4ec4d21f0f4d26e63257709718dd27c7af3c406fe062e320657da554b',
};
for(const [file,hash] of Object.entries(frozen))assert.equal(sha(file),hash,`Frozen source changed: ${file}`);
const separationSourceHash=sha('web/flat_entity_separation_polish.js');
const otherFrozen=Object.fromEntries(['web/geographic_polish_transition.js','web/earth_polish_adapter.js','web/earth_adapter.js','web/render_flat_polish.html','tools/render_flat_polish_scene.mjs'].map(file=>[file,sha(file)]));
const core=load('web/flat_semantics.js',{THREE},['FlatSceneCore','FlatProjection','FlatCameraRig','flatCoordinate','flatNumber','flatClamp','flatSmooth','flatWindow']);
const aircraftSource=fs.readFileSync(path.join(root,'../cinematic-world-map/src/aircraft_v3.js'),'utf8');
const {createAircraftV3}=new Function('THREE',strip(aircraftSource)+';return {createAircraftV3};')(THREE);
const base=load('web/flat_renderer.js',{THREE,createAircraftV3,...core,drawAtmosphericVeil(){},mapTransitionOpacity(){return 0;},transitionAuditVisibility:a=>a},['SceneFlatRenderer','FlatEntitiesGraphics']);
const polish=load('web/flat_polish_renderer.js',{THREE,createAircraftV3,...core,...base},['SceneFlatPolishRenderer','avoidCityLabelObstacles']);
const separation=load('web/flat_entity_separation_polish.js',{THREE,...core,...polish},['SceneFlatEntitySeparationPolishRenderer','separateAircraftDisplayProxies','projectedAircraftFootprint','projectedScreenOffsetDelta']);
const geo=load('web/geographic_polish_transition.js',{THREE,...core},['FlatGeographicController']);
const planFile=process.argv[2]||'projects-flat-validation/project_c047b389d1f8/versions/v004/scene_plan.json';
const plan=JSON.parse(read(planFile)),scene=structuredClone(plan.scenes.find(scene=>scene.scene_id==='S004'));
scene.visual_polish.entity_separation='v1';
const renderer=Object.create(separation.SceneFlatEntitySeparationPolishRenderer.prototype);
Object.assign(renderer,{w:2160,h:3840,duration:scene.duration,sceneSpec:scene,plan,displayOffsets:new Map(),world:new THREE.Scene()});
renderer.world.background=new THREE.Color('#071521');
renderer.core=new core.FlatSceneCore(scene,plan,{width:renderer.w,height:renderer.h});
renderer.camera=renderer.core.camera;
renderer.entities=new base.FlatEntitiesGraphics(renderer);
const controller=new geo.FlatGeographicController(renderer);
// Initialize the actual geometric rig without material cloning, tessellation,
// asset fetches or a GPU context. Its original before/project math is used.
controller.baseCamera=renderer.core.camera;
renderer.core.cam.scene={...renderer.core.cam.scene,transition_in:'camera_continuity',transition_out:'camera_continuity'};
const geoMore=load('web/geographic_polish_transition.js',{THREE,...core},['GeographicWarp','registeredHandoffCamera']);
controller.warp=new geoMore.GeographicWarp(scene);controller.boundary=geoMore.registeredHandoffCamera(scene,renderer.w/renderer.h);
controller.duration=.65;controller.start=scene.duration-controller.duration;controller.uniforms=controller.warp.uniforms();controller.initialized=true;
renderer.polishHooks={beforeWorldRender:(_,t)=>controller.before(t),projectDisplayPoint:(_,point)=>controller.project(point)};
const previous=JSON.parse(read('docs/evidence/flat_polish_final_stills_v004_r03/S004_LAYOUT_SCAN.json'));
const records=[];let maxOffset1080=0,maxResidualLabelOverlap=0,maxLayoutStep1080=0,maxLayoutAcceleration1080=0;
let lastOffsets=new Map(),lastOffsetSteps=new Map();
const area=(a,b)=>Math.max(0,Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y));
const prepare=t=>{
 const frame=renderer.core.semanticFrame(t),anchors=frame.entities.map(pose=>pose.position.toArray());
 const routeProgress=renderer.core.routes.map(route=>renderer.core.routeProgress(route,t));
 renderer.entities.update(t,frame.entities);
 separation.SceneFlatEntitySeparationPolishRenderer.prototype.polishEntities.call(renderer,t,frame);
 assert.deepEqual(frame.entities.map(pose=>pose.position.toArray()),anchors,'Verified coordinates were mutated');
 assert.deepEqual(renderer.core.routes.map(route=>renderer.core.routeProgress(route,t)),routeProgress,'Route progress was changed');
 return structuredClone(renderer.entitySeparationFrame);
};
for(let i=0;i<90;i++){
 const t=i/30,result=prepare(t),old=previous.records[i];
 const boxes=result.records.map(record=>({...record.finalFootprint,entity_id:record.entity_id}));
 const fontLabels=(old.labels||[]).map(label=>({...label,polishCity:true,airportReservation:{side:label.avoidance.stableAirportSlot},aircraftAvoidance:null}));
 const labels=polish.avoidCityLabelObstacles(fontLabels,boxes,renderer.w,renderer.h);
 for(let j=0;j<labels.length;j++){
  assert.equal(labels[j].x,fontLabels[j].x,'Reserved label x changed');assert.equal(labels[j].y,fontLabels[j].y,'Reserved label y changed');
  maxResidualLabelOverlap=Math.max(maxResidualLabelOverlap,...boxes.map(box=>area(labels[j],box)));
 }
 for(const record of result.records){
  const box=record.finalFootprint,offset=record.additionalDisplayOffsetPixels;
  assert.ok(box.x>=renderer.w*.055-.1&&box.x+box.width<=renderer.w*.945+.1,'Aircraft outside horizontal safe bounds');
  assert.ok(box.y>=renderer.h*.08-.1&&box.y+box.height<=renderer.h*.82+.1,'Aircraft outside vertical safe bounds');
  maxOffset1080=Math.max(maxOffset1080,Math.hypot(offset.x,offset.y)/2);
  const last=lastOffsets.get(record.entity_id);
  if(last){
   const step={x:(offset.x-last.x)/2,y:(offset.y-last.y)/2};
   maxLayoutStep1080=Math.max(maxLayoutStep1080,Math.hypot(step.x,step.y));
   const previousStep=lastOffsetSteps.get(record.entity_id);
   if(previousStep)maxLayoutAcceleration1080=Math.max(maxLayoutAcceleration1080,Math.hypot(step.x-previousStep.x,step.y-previousStep.y));
   lastOffsetSteps.set(record.entity_id,step);
  }
  lastOffsets.set(record.entity_id,offset);
 }
 for(const pair of result.pairs)if(pair.minimumAlpha>.015)assert.equal(pair.actualProjectedBoxesOverlap,false,`Actual aircraft mesh bounds overlap at ${t}: ${pair.entity_ids}`);
 records.push({...result,labels});
}
// Absolute projection proxy layout must be independent of sampling order.
const forward=JSON.stringify(prepare(89/30));prepare(1.8);const afterRewind=JSON.stringify(prepare(89/30));assert.equal(afterRewind,forward,'Layout retained previous frame state');
assert.equal(maxResidualLabelOverlap,0,'Aircraft proxy overlaps a reserved city label');
for(const [file,hash] of Object.entries(frozen))assert.equal(sha(file),hash);
for(const [file,hash] of Object.entries(otherFrozen))assert.equal(sha(file),hash,'Frozen render source changed during CPU check');
assert.equal(sha('web/flat_entity_separation_polish.js'),separationSourceHash,'New adapter changed during CPU check');
assert.ok(maxLayoutStep1080<12,'Additional display layout step exceeded 12 final pixels');
assert.ok(maxLayoutAcceleration1080<5,'Additional display layout acceleration exceeded 5 final pixels per frame squared');
const report={passed:true,frames:90,scope:'CPU-only actual private aircraft meshes + original registered camera/warp projection; no GL pixels or encoded-video review',plan:planFile,
 source_sha256:separationSourceHash,frozen_sources:{...frozen,...otherFrozen},max_additional_offset_1080_px:maxOffset1080,
 max_additional_offset_step_1080_px:maxLayoutStep1080,reserved_label_overlap_area: maxResidualLabelOverlap,
 max_additional_offset_acceleration_1080_px_per_frame_squared:maxLayoutAcceleration1080,
 velocity_at_30fps_1080_px_per_second:maxLayoutStep1080*30,
 acceleration_at_30fps_1080_px_per_second_squared:maxLayoutAcceleration1080*900,
 final_frame:records.at(-1),records};
const destination=process.argv[3];if(destination){fs.mkdirSync(path.dirname(destination),{recursive:true});fs.writeFileSync(destination,JSON.stringify(report,null,2),{flag:'wx'});}
console.log(JSON.stringify({...report,records:undefined,final_frame:report.final_frame.records.map(record=>({entity_id:record.entity_id,offset:record.additionalDisplayOffsetPixels,bounds:record.finalFootprint}))},null,2));
