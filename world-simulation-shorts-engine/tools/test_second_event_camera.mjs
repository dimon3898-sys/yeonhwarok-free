import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve('.');
const THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const plan=JSON.parse(fs.readFileSync(process.argv[2])),scene=plan.scenes[0],config=scene.second_event_camera;
const strip=p=>fs.readFileSync(path.join(root,p),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const old=new Function('THREE','SceneProductionEarthRenderer',strip('web/single_event_camera.js')+';return {singleCameraValues,installSingleCamera};')(THREE,class{});
const previous=new Function('singleCameraValues','installSingleCamera','SceneSingleEventRenderer',strip('web/return_wide_camera.js')+';return {returnCameraValues,installReturnCamera,SceneReturnWideRenderer};')(old.singleCameraValues,old.installSingleCamera,class{audit(t){return {t};}});
const next=new Function('THREE','returnCameraValues','installReturnCamera','SceneReturnWideRenderer',strip('web/second_event_camera.js')+';return {installSecondCamera,secondCameraState,SceneSecondEventRenderer};')(THREE,previous.returnCameraValues,previous.installReturnCamera,previous.SceneReturnWideRenderer);
const adapter=fs.readFileSync(path.join(root,'web/production_visual_adapter.js'),'utf8');
const labelStart=adapter.indexOf('export function productionLabelScene('),labelEnd=adapter.indexOf('\n/** Real, independent camera',labelStart);
assert(labelStart>=0&&labelEnd>labelStart);
const helpers=adapter.match(/const largeTitlesApproved=.*;\nconst cloneScene=.*;/)?.[0];assert(helpers);
const semantics=new Function('THREE',strip('web/flat_semantics.js')+';return {flatNumber};')(THREE);
const productionLabelScene=new Function('flatNumber',helpers+'\n'+adapter.slice(labelStart,labelEnd).replace('export ','')+'\nreturn productionLabelScene;')(semantics.flatNumber);
const firstEventLabels=productionLabelScene({...scene,labels:scene.labels.filter(l=>l.coordinates?.location_id!==config.next_coordinates.location_id),text_events:scene.text_events.filter(l=>l.coordinates?.location_id!==config.next_coordinates.location_id)}).labels.slice(0,3);
const baselineScene={...scene,return_wide_camera:{event_camera:config.event1_camera,final_camera:scene.camera_start}};
const cam={scene,camera:new THREE.PerspectiveCamera(64,9/16,.02,30)},baseline={scene:baselineScene,camera:new THREE.PerspectiveCamera(64,9/16,.02,30)};
next.installSecondCamera(cam);previous.installReturnCamera(baseline);
// Exercise the real child init method while distinguishing renderer THREE.Scene
// from its actual Scene JSON. The parent fixture creates only native camera state.
let initFrames=0;
class ParentInitFixture{
 constructor(scene){
  this.scene=new THREE.Scene();this.sceneSpec=productionLabelScene(scene);
  this.cam={scene:this.sceneSpec,camera:new THREE.PerspectiveCamera(64,9/16,.02,30)};
 }
 async init(){
  assert(this.scene instanceof THREE.Scene);
  assert.equal(this.sceneSpec.return_wide_camera.event_camera,this.sceneSpec.second_event_camera.event1_camera);
  this.cam.scene=this.sceneSpec;previous.installReturnCamera(this.cam);this.frame(0);return this;
 }
 audit(t){return {t};}
}
const initModule=new Function('THREE','returnCameraValues','installReturnCamera','SceneReturnWideRenderer',strip('web/second_event_camera.js')+';return {SceneSecondEventRenderer};')(THREE,previous.returnCameraValues,previous.installReturnCamera,ParentInitFixture);
const initRenderer=new initModule.SceneSecondEventRenderer(structuredClone(scene),plan);
assert.deepEqual(initRenderer.sceneSpec.labels.slice(0,3),firstEventLabels);
initRenderer.frame=t=>{initFrames++;initRenderer.cam.update(t);};
await initRenderer.init();assert(initFrames>=2);
assert.deepEqual(initRenderer.cam.values(0),previous.returnCameraValues(0,baselineScene));
assert.equal(initRenderer.cam.values(24).lon,config.event2_camera.lon);
assert.equal(initRenderer.cam.values(24).lat,config.event2_camera.lat);
assert.equal(initRenderer.cam.values(24).height,config.event2_camera.height);
const rows=[];
for(let i=0;i<720;i++){
 const t=i/30;cam.update(t);
 if(i<360){baseline.update(t);assert.deepEqual(cam.camera.position.toArray(),baseline.camera.position.toArray());assert.deepEqual(cam.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(cam.camera.fov,baseline.camera.fov);}
 const a=next.SceneSecondEventRenderer.prototype.audit.call({scene,cam},t);
 const labels=t>=20.5?[{text:'SINGAPORE',opacity:.75}]:t>=15?[{text:'SINGAPORE',opacity:.75}]:t>=11?[{text:'SUEZ CANAL',opacity:.75},{text:'CANAL OPEN',opacity:.75}]:t>=6?[{text:'SUEZ CANAL',opacity:.75},{text:'CANAL CLOSED',opacity:.75}]:t>=2?[{text:'SUEZ CANAL',opacity:.75}]:[];
 rows.push({...a,scene_id:'S001',frame_index:i,timestamp:t,cameraPosition:cam.camera.position.toArray(),cameraQuaternion:cam.camera.quaternion.toArray(),cameraFov:cam.camera.fov,labels});
}
const expected=['EVENT1_WIDE','EVENT1_LOCATION','EVENT1_ZOOM_IN','EVENT1_VIEW','EVENT1_HOLD','EVENT1_RESOLVED','ZOOM_OUT','ADAPTIVE_WIDE','EVENT2_LOCATION','EVENT2_ZOOM_IN','EVENT2_VIEW','EVENT2_HOLD'];
assert.deepEqual([...new Set(rows.map(row=>row.cameraState))],expected);
assert.equal(next.secondCameraState(24),'END');
let maximumQuaternionStepDegrees=0,maximumTranslationStep=0;
for(let i=1;i<rows.length;i++){
 const previousQuaternion=new THREE.Quaternion(...rows[i-1].cameraQuaternion),currentQuaternion=new THREE.Quaternion(...rows[i].cameraQuaternion);
 maximumQuaternionStepDegrees=Math.max(maximumQuaternionStepDegrees,previousQuaternion.angleTo(currentQuaternion)*180/Math.PI);
 maximumTranslationStep=Math.max(maximumTranslationStep,new THREE.Vector3(...rows[i].cameraPosition).distanceTo(new THREE.Vector3(...rows[i-1].cameraPosition)));
}
assert(maximumQuaternionStepDegrees<2.5,'Existing camera angular-step limit must remain respected.');
assert(maximumTranslationStep<.25,'Existing camera translation-step limit must remain respected.');
for(const [a,b] of [[0,90],[150,360],[420,495],[585,720]])for(let i=a+1;i<b;i++){
 assert.deepEqual(rows[i].cameraPosition,rows[a].cameraPosition);
 assert.deepEqual(rows[i].cameraQuaternion,rows[a].cameraQuaternion);
 assert.equal(rows[i].cameraFov,rows[a].cameraFov);
}
function project(coordinate,frame){
 cam.update(frame/30);const lat=coordinate.lat*Math.PI/180,lon=coordinate.lon*Math.PI/180;
 const point=new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));
 const visible=point.dot(cam.camera.position.clone().sub(point))>0;
 const ndc=point.clone().project(cam.camera);return {x:(ndc.x+1)/2,y:(1-ndc.y)/2,visible,z:ndc.z};
}
const current=project(scene.coordinates,420),destination=project(config.event2_camera,420);
assert(current.visible&&destination.visible);
// Independent native projection; padded safe area is defined by the allocator.
const safe=config.adaptive_wide.safe_area;
assert(safe,'Adaptive framing must publish its actual screen safe area.');
for(const position of [current,destination]){
 assert(position.x>=safe.x_min-1e-7&&position.x<=safe.x_max+1e-7);
 assert(position.y>=safe.y_min-1e-7&&position.y<=safe.y_max+1e-7);
 assert(position.z>=-1&&position.z<=1);
}
for(const [actual,reported] of [[current,config.adaptive_wide.current_screen],[destination,config.adaptive_wide.next_screen]]){
 assert(Math.abs(actual.x-reported.x)<1e-7&&Math.abs(actual.y-reported.y)<1e-7);
 assert(reported.visible&&reported.in_safe_area);
}
const {frameEvidence,SceneJournal}=await import('./scene_diagnostic_journal.mjs');
const folder=fs.mkdtempSync('/tmp/second-camera-journal-');const journal=new SceneJournal(folder,'S001');
for(const frame of [330,420,450,495,585,615]){
 const evidence=frameEvidence({sceneId:'S001',frameIndex:frame,t:frame/30,audit:rows[frame],errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});journal.frame(evidence);
}
const saved=fs.readFileSync(path.join(folder,'S001/frame-audit.jsonl'),'utf8').trim().split('\n').map(row=>JSON.parse(row));
assert.deepEqual(saved.map(row=>row.cameraState),['EVENT1_RESOLVED','ADAPTIVE_WIDE','EVENT2_LOCATION','EVENT2_ZOOM_IN','EVENT2_VIEW','EVENT2_HOLD']);
fs.rmSync(folder,{recursive:true});
console.log(JSON.stringify({passed:true,baseline_first_360_identical:true,scene_json_init_scope_passed:true,first_event_focus_labels_identical:true,maximum_quaternion_step_degrees:maximumQuaternionStepDegrees,maximum_translation_step:maximumTranslationStep,audits:rows,frames:720,adaptive_projection:{current,destination,safe_area:safe},GPU:'NOT_RUN',scope:'Native camera mathematics, actual production label preparation, child init scope and diagnostic journal capture; labels are planning fixtures, not GPU pixels'}));
