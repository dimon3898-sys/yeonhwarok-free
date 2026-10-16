/** Pure CPU validation only; no fakeGPUadmission is supplied. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,symlink,rm} from 'node:fs/promises';
import path from 'node:path';
import {validateLongRuntimeDocument,validateNativePayload,engineRelative,boundedSource} from '../long_runtime.mjs';
const h='a'.repeat(64);
function document(){return {schema:'WORLD_ENGINE_UNIVERSAL_VIDEO_V2',durationSeconds:80,totalFrames:2400,fps:30,
 resolution:{width:1080,height:1920},aspectRatio:'9:16',audioSettings:{enabled:false},
 scenes:[{sceneId:'s0',startFrame:0,endFrame:1200,renderProfile:{gpuMode:'gpu-required',adapter:'UNIVERSAL_AREA_ASTRA_V2',status:'READY',nativePayload:{path:'test.json',sha256:h,validationStatus:'VERIFIED'}}},
 {sceneId:'s1',startFrame:1200,endFrame:2400,renderProfile:{gpuMode:'gpu-required',adapter:'UNIVERSAL_AREA_ASTRA_V2',status:'READY',nativePayload:{path:'test.json',sha256:h,validationStatus:'VERIFIED'}}}],
 legacyScenePlan:{timing:{total_frames:2400,fps:30},event_type:'WAR'},sourceManifest:{records:[{verification_status:'VERIFIED'}],semanticPolicy:{inventMissingHistory:false}}};}
test('longSceneacceptsactualglobalrange andrejectsfictional/incompletebindings',()=>{
 const doc=document();assert.equal(validateLongRuntimeDocument(doc,'s1').startFrame,1200);
 for(const mutate of [d=>d.scenes[1].startFrame=1199,d=>d.scenes[1].endFrame=2399,
  d=>d.scenes[1].renderProfile.status='BLOCKED_NATIVE_PAYLOAD_REQUIRED',d=>d.sourceManifest.records[0].verification_status='UNVERIFIED',
  d=>d.legacyScenePlan.timing.total_frames=150,d=>d.audioSettings.enabled=true]){
  const value=document();mutate(value);assert.throws(()=>validateLongRuntimeDocument(value,'s1'));
 }
});
test('nativepayloadrequiresfiveactualhashboundinputs andnoenginepathtraversal',()=>{
 const nativeFiles=Object.fromEntries(['regionalPlan','continentPlan','scene','cameraPlan','inputManifest'].map(key=>[key,{path:'recovery/existing/'+key+'.json',sha256:h}]));
 const payload={schema:'WORLD_ENGINE_UNIVERSAL_NATIVE_INPUT_V1',sourcePolicy:'EXISTING_VERIFIED_NATIVE_INPUTS',cameraStartFrame:116,nativeFiles};
 assert.equal(validateNativePayload(payload),payload);
 for(const file of ['../secret','/private/file','a/../b','a\\b','a//b'])assert.throws(()=>engineRelative(file));
 const wrong=structuredClone(payload);delete wrong.nativeFiles.scene;assert.throws(()=>validateNativePayload(wrong));
});
test('boundedsourcerejectssymlinks andoverlimitdata',async()=>{
 const dir=await mkdtemp('/tmp/long-runtime-source-');
 try{const file=path.join(dir,'original');await writeFile(file,'preserve');assert.equal((await boundedSource(file)).toString(),'preserve');
 await assert.rejects(boundedSource(file,2),/LONG_BOUNDED_REGULAR_SOURCE_REQUIRED/);
 const link=path.join(dir,'alias');await symlink(file,link);await assert.rejects(boundedSource(link),/LONG_SOURCE_SYMLINK_FORBIDDEN/);
 }finally{await rm(dir,{recursive:true});}
});
