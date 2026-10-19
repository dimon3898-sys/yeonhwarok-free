import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {extendDirectorCaptureWindow,validateCommonNativeContext} from '../runtime_adapter.mjs';

const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
function source(){
 const payload={path:'fixtures/generic.json',sha256:'a'.repeat(64),validationStatus:'VERIFIED'},
  scenes=[{sceneId:'alpha',startFrame:0,endFrame:180,renderProfile:{nativePayload:payload}},
   {sceneId:'beta',startFrame:180,endFrame:600,renderProfile:{nativePayload:payload}}],
  document={schema:'WORLD_ENGINE_UNIVERSAL_VIDEO_V2',fps:30,totalFrames:600,durationSeconds:20,scenes,
   legacyScenePlan:{time_steps:[{id:'state-one',start_frame:0},{id:'state-two',start_frame:180}],
    geometries:[{id:'west',geometry:{type:'LineString',coordinates:[[-3,-32],[-2,-31]]}}]}};
 return{document,scene:structuredClone(scenes[1]),planSha256:digest(document),
  legacySceneSha256:digest(document.legacyScenePlan),sourceSignature:'b'.repeat(64),
  serverConfig:{bindings:[],runtimeConfig:{testOnlySoftwareProbe:true,universalVideo:{
   plan:structuredClone(document),scene:structuredClone(scenes[1]),sceneRangeSha256:digest(scenes[1])}}},
  assertSourceUnchanged:async()=>true};
}

test('global sampling preserves source chronology and avoids per-chapter resets',async()=>{
 const inherited=source(),original=JSON.stringify(inherited),extended=extendDirectorCaptureWindow(inherited);
 assert.equal(extended.scene.startFrame,0);assert.equal(extended.scene.endFrame,600);
 assert.equal(extended.scene.globalFrameOffset,0);
 assert.deepEqual(extended.document.legacyScenePlan,inherited.document.legacyScenePlan);
 assert.equal(extended.storyDirector.sourceSceneRanges[1].startFrame,180);
 assert.equal(extended.storyDirector.singleRuntimeGlobalTime,true);
 assert.equal(Object.hasOwn(extended.scene,'eventTimeline'),false);
 assert.equal(JSON.stringify(inherited),original);
 assert.equal(await extended.assertSourceUnchanged(),true);
});

test('a source context change cannot be silently sampled with the earlier context',()=>{
 const inherited=source();inherited.document.scenes[1].renderProfile.nativePayload={
  ...inherited.document.scenes[1].renderProfile.nativePayload,sha256:'c'.repeat(64)};
 assert.throws(()=>validateCommonNativeContext(inherited.document),
  /DIRECTOR_MULTIPLE_NATIVE_CONTEXTS_REQUIRE_SEPARATE_STATE_RESTORE/);
});

test('a chapter gap is rejected rather than filled with invented state',()=>{
 const inherited=source();inherited.document.scenes[1].startFrame=181;
 assert.throws(()=>validateCommonNativeContext(inherited.document),/DIRECTOR_CONTIGUOUS_SOURCE_CHAPTERS_REQUIRED/);
});

test('the director adapter never creates production or GPU admission',()=>{
 const inherited=source();inherited.serverConfig.runtimeConfig.testOnlySoftwareProbe=false;
 assert.throws(()=>extendDirectorCaptureWindow(inherited),/DIRECTOR_SOFTWARE_ONLY_CONTEXT_REQUIRED/);
 const extended=extendDirectorCaptureWindow(source());
 assert.equal(extended.storyDirector.productionEligible,false);
 assert.equal(extended.storyDirector.nvidiaHardwareVerified,false);
});

test('source mutation after selection is detected before a successful handoff',async()=>{
 const inherited=source(),extended=extendDirectorCaptureWindow(inherited);
 inherited.document.legacyScenePlan.geometries[0].geometry.coordinates[0][0]=-4;
 await assert.rejects(extended.assertSourceUnchanged(),/DIRECTOR_SOURCE_DOCUMENT_MUTATED/);
});

test('only the independent camera input edge may replace a preserved browser owner',()=>{
 assert.throws(()=>extendDirectorCaptureWindow(source(),{bindingRecords:[{
  url:'/production-v3/production_area_pass.mjs',path:'/workspace/unwanted.mjs',
  sha256:'d'.repeat(64),bytes:10}]}),/DIRECTOR_UNAPPROVED_SOURCE_EDGE_REPLACEMENT/);
});
