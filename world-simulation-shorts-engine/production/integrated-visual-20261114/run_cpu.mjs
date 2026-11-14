import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {compileFrontierCamera} from '../../recovery/universal-presentation-v2/territory_camera_v1.mjs';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),stage=process.argv[2],attempt=process.argv[3];
assert.ok(['map','territory','camera','final'].includes(stage));assert.match(attempt,/^a[1-9][0-9]*$/);
const hash=x=>createHash('sha256').update(x).digest('hex');
const old=await fs.readFile(new URL('../continuous-territory-20261114/RUNTIME_REQUEST.json',base));
assert.equal(hash(old),'adf13d8c7c9ed0ee06bf7c2ef867d4e55d2ce405c33203adf76f77463580c95e');
const request=JSON.parse(old),segment=request.segments[0],p=segment.presentation;
const geometryHash=hash(JSON.stringify(p.territoryChanges.items.map(x=>x.continuous))),cameraHash=hash(JSON.stringify(p.camera));
if(stage!=='map'){const gate=JSON.parse(await fs.readFile(new URL('MAP_REVIEW.json',base)));assert.equal(gate.status,'PASS_CHANGED_MAP_SCOPE');p.territoryChanges.config.visualProfile='FRONTIER_LIGHT_V1';}
p.mapStyle={...p.mapStyle,sourceReliefDetail:'SOURCE_RELIEF_V1',physicalContext:'NATURAL_EARTH_V1'};
p.territoryColors=Object.fromEntries(Object.keys(p.territoryColors).map(id=>[id,[1,.75,.12,.28]]));
assert.equal(hash(JSON.stringify(p.territoryChanges.items.map(x=>x.continuous))),geometryHash);
let cameraAudit=null;
if(['camera','final'].includes(stage)){
 const gate=JSON.parse(await fs.readFile(new URL('TERRITORY_REVIEW.json',base)));assert.equal(gate.status,'PASS_CHANGED_TERRITORY_SCOPE');
 const a=segment.automaticDirection,directed=compileFrontierCamera({scene:segment.scene,territoryChanges:p.territoryChanges,timingAudit:a.timing,sourceLevels:segment.regionEvidence.sourceLevels,closestBounds:segment.regionEvidence.fittedBounds,initialPose:p.camera.frames[0],resultPoses:a.timing.choreography.map(c=>p.camera.frames[c.cameraEnd]),changeMetrics:a.changes});
 p.camera=directed.camera;cameraAudit=directed.audit;segment.automaticDirection={...a,cameraKeys:cameraAudit.cameraKeys,cameraDirection:cameraAudit};
}else assert.equal(hash(JSON.stringify(p.camera)),cameraHash);
if(stage==='final'){
 for(const [file,status]of [['CAMERA_REVIEW.json','PASS_CHANGED_CAMERA_SCOPE'],['INTEGRATION_REVIEW.json','PASS_CHANGED_INTERACTIONS']]){const gate=JSON.parse(await fs.readFile(new URL(file,base)));assert.equal(gate.status,status);}
 const proven=JSON.parse(await fs.readFile(new URL('camera-a1/CHANGE_SCOPE.json',base)));assert.equal(hash(JSON.stringify(request)),proven.inputSHA256);
}
const inputFile='/workspace/integrated-input-'+stage+'-'+attempt+'.json',outputRoot='/workspace/integrated-'+stage+'-'+attempt;
const raw=JSON.stringify(request);await fs.writeFile(inputFile,raw,{flag:'wx',mode:0o600});
try{
 const receipt=await capturePresentation({packageFile:inputFile,outputRoot,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:stage==='final'?null:stage==='camera'?[0,...Array.from({length:10},(_,i)=>23+i),53,79,105,131,179]:stage==='map'?[0,79,131,179]:[26,53,...Array.from({length:8},(_,i)=>76+i),105,126,130,131,149]});
 await fs.writeFile(outputRoot+'/CHANGE_SCOPE.json',JSON.stringify({stage,attempt,inputSHA256:hash(raw),baseInputSHA256:hash(old),geometryUnchanged:true,geometryHash,cameraUnchanged:!['camera','final'].includes(stage),oldCameraHash:cameraHash,cameraHash:hash(JSON.stringify(p.camera)),cameraAudit,oldPassReruns:0,gpuStarts:0,status:receipt.status},null,2)+'\n');
 console.log(JSON.stringify({status:receipt.status,outputRoot}));
}catch(error){await fs.mkdir(outputRoot,{recursive:true});await fs.writeFile(outputRoot+'/TASK_FAILURE.json',JSON.stringify({stage,attempt,status:'BLOCKED',error:error.message,stack:error.stack,oldPassReruns:0,gpuStarts:0},null,2)+'\n');throw error;}
