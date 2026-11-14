import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {capturePresentation} from '../../recovery/universal-presentation-v2/capture_presentation.mjs';
const base=new URL('./',import.meta.url),stage=process.argv[2],attempt=process.argv[3];
assert.equal(stage,'map');assert.match(attempt,/^a[1-9][0-9]*$/);
const hash=x=>createHash('sha256').update(x).digest('hex');
const old=await fs.readFile(new URL('../continuous-territory-20261114/RUNTIME_REQUEST.json',base));
assert.equal(hash(old),'adf13d8c7c9ed0ee06bf7c2ef867d4e55d2ce405c33203adf76f77463580c95e');
const request=JSON.parse(old),segment=request.segments[0],p=segment.presentation;
const geometryHash=hash(JSON.stringify(p.territoryChanges)),cameraHash=hash(JSON.stringify(p.camera));
p.mapStyle={...p.mapStyle,sourceReliefDetail:'SOURCE_RELIEF_V1',physicalContext:'NATURAL_EARTH_V1'};
p.territoryColors=Object.fromEntries(Object.keys(p.territoryColors).map(id=>[id,[1,.75,.12,.28]]));
assert.equal(hash(JSON.stringify(p.territoryChanges)),geometryHash);
assert.equal(hash(JSON.stringify(p.camera)),cameraHash);
const inputFile='/workspace/integrated-input-'+stage+'-'+attempt+'.json',outputRoot='/workspace/integrated-'+stage+'-'+attempt;
const raw=JSON.stringify(request);await fs.writeFile(inputFile,raw,{flag:'wx',mode:0o600});
try{
 const receipt=await capturePresentation({packageFile:inputFile,outputRoot,expectedSHA256:hash(raw),depsRoot:process.env.WORLD_ENGINE_NODE_DEPS,probeFrames:[0,79,131,179]});
 await fs.writeFile(outputRoot+'/CHANGE_SCOPE.json',JSON.stringify({stage,attempt,inputSHA256:hash(raw),baseInputSHA256:hash(old),geometryUnchanged:true,geometryHash,cameraUnchanged:true,cameraHash,oldPassReruns:0,gpuStarts:0,status:receipt.status},null,2)+'\n');
 console.log(JSON.stringify({status:receipt.status,outputRoot}));
}catch(error){await fs.mkdir(outputRoot,{recursive:true});await fs.writeFile(outputRoot+'/TASK_FAILURE.json',JSON.stringify({stage,attempt,status:'BLOCKED',error:error.message,stack:error.stack,oldPassReruns:0,gpuStarts:0},null,2)+'\n');throw error;}
