import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=path.resolve('.');
const THREE=await import(pathToFileURL(path.join(root,'../cinematic-world-map/node_modules/three/build/three.module.js')));
const plan=JSON.parse(fs.readFileSync(process.argv[2])),scene=plan.scenes[0];
const strip=p=>fs.readFileSync(path.join(root,p),'utf8').replace(/^import .*;$/gm,'').replace(/^export /gm,'');
const old=new Function('THREE','SceneProductionEarthRenderer',strip('web/single_event_camera.js')+';return {singleCameraValues,installSingleCamera};')(THREE,class{});
const next=new Function('singleCameraValues','installSingleCamera','SceneSingleEventRenderer',strip('web/return_wide_camera.js')+';return {installReturnCamera,returnCameraState,SceneReturnWideRenderer};')(old.singleCameraValues,old.installSingleCamera,class{audit(t){return {t};}});
const cam={scene,camera:new THREE.PerspectiveCamera(64,9/16,.02,30)},baseline={scene:{...scene,camera_end:scene.return_wide_camera.event_camera},camera:new THREE.PerspectiveCamera(64,9/16,.02,30)};
next.installReturnCamera(cam);old.installSingleCamera(baseline);
const rows=[];
for(let i=0;i<450;i++){
 const t=i/30;cam.update(t);
 if(i<360){baseline.update(t);assert.deepEqual(cam.camera.position.toArray(),baseline.camera.position.toArray());assert.deepEqual(cam.camera.quaternion.toArray(),baseline.camera.quaternion.toArray());assert.equal(cam.camera.fov,baseline.camera.fov);}
 const a=next.SceneReturnWideRenderer.prototype.audit.call({},t);
 const labels=t>=11?[{text:'SUEZ CANAL',opacity:.75},{text:'CANAL OPEN',opacity:.75}]:t>=6?[{text:'SUEZ CANAL',opacity:.75},{text:'CANAL CLOSED',opacity:.75}]:t>=2?[{text:'SUEZ CANAL',opacity:.75}]:[];
 rows.push({...a,scene_id:'S001',frame_index:i,timestamp:t,cameraPosition:cam.camera.position.toArray(),cameraQuaternion:cam.camera.quaternion.toArray(),cameraFov:cam.camera.fov,labels});
}
assert(rows[330].cameraState==='EVENT_RESOLVED');assert(rows[360].cameraState==='ZOOM_OUT');assert(rows[420].cameraState==='FINAL_WIDE');
for(let i=421;i<450;i++){assert.deepEqual(rows[i].cameraPosition,rows[420].cameraPosition);assert.deepEqual(rows[i].cameraQuaternion,rows[420].cameraQuaternion);assert.equal(rows[i].cameraFov,64);}
const {frameEvidence,SceneJournal}=await import('./scene_diagnostic_journal.mjs');
const folder=fs.mkdtempSync('/tmp/return-camera-journal-');const journal=new SceneJournal(folder,'S001');
const evidence=frameEvidence({sceneId:'S001',frameIndex:330,t:11,audit:rows[330],errors:[],renderer:{},failedInvariants:[],decoded:[1080,1920],decodeError:false});journal.frame(evidence);
const saved=JSON.parse(fs.readFileSync(path.join(folder,'S001/frame-audit.jsonl'),'utf8'));assert.equal(saved.cameraState,'EVENT_RESOLVED');assert.equal(saved.cameraFrame,330);fs.rmSync(folder,{recursive:true});
console.log(JSON.stringify({passed:true,baseline_first_360_identical:true,audits:rows,frames:450,GPU:'NOT_RUN',scope:'Native camera mathematics and journal capture; labels are planning fixtures, not GPU pixels'}));
