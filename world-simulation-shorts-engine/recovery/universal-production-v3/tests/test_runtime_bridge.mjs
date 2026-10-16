/** CPU binding evidence; no browser/GPU admission or fictional rendered frame. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {BROWSER_BINDINGS,extendProductionServerPlan,validateLongRuntimeDocument,
 assertProductionCapturedFrame} from '../long_runtime.mjs';
import {resolveProductionCapture,originalCaptureURL,productionRuntimeURL} from '../long_capture.mjs';
import {evaluateProductionGeometryClock} from '../production_visual_profile.mjs';
const h='a'.repeat(64),g='b'.repeat(64),hash=bytes=>createHash('sha256').update(bytes).digest('hex');
function fixture(){
 const profile={gpuMode:'gpu-required',adapter:'UNIVERSAL_AREA_ASTRA_V2',productionAdapter:'UNIVERSAL_PRODUCTION_V3',
  status:'READY',nativePayload:{path:'TEST_ONLY_NATIVE.json',sha256:h,validationStatus:'VERIFIED'}},
  chapter={chapterId:'source-held',startFrame:0,endFrame:60,displayLabel:'QUALIFIED_CONTEXT'},
  scene={sceneId:'s0',startFrame:0,endFrame:60,renderProfile:profile},
  document={schema:'WORLD_ENGINE_UNIVERSAL_VIDEO_V2',durationSeconds:2,totalFrames:60,fps:30,
   resolution:{width:1080,height:1920},aspectRatio:'9:16',audioSettings:{enabled:false},renderProfile:profile,scenes:[scene],
   legacyScenePlan:{timing:{total_frames:60,fps:30,event_start_frame:0},event_type:'WAR'},
   sourceManifest:{records:[{verification_status:'VERIFIED'}],semanticPolicy:{inventMissingHistory:false}},
   productionV3:{runtimeProfile:'UNIVERSAL_PRODUCTION_V3',eventChapters:[chapter],geometrySchedule:[{
    startFrame:0,endFrame:60,mode:'HOLD_SUPPLIED_SNAPSHOT',sourceStartFrame:3,sourceEndFrame:3,
    sourceStateId:'ONLY_EXISTING_CONTEXT',snapshotDate:'SUPPLIED_DATE',eventDateMatchesSnapshot:false}]}},
  records=Object.entries(BROWSER_BINDINGS).map(([url,name])=>({url,path:'/TEST_ONLY/'+name,bytes:50,sha256:h})),
  inherited={document,scene,sourceSignature:g,sourceBindings:[{path:'old/frame-owner.mjs',bytes:20,sha256:g}],
   serverConfig:{runtimeConfig:{universalVideo:{plan:document,scene,planSha256:h}},bindings:[
    {url:'/universal/long_adapter.mjs',path:'/FROZEN/long_adapter.mjs',bytes:100,sha256:g},
    {url:'/universal/long_area_timeline.mjs',path:'/FROZEN/long_area_timeline.mjs',bytes:70,sha256:g},
    {url:'/reference/reference_source_material.mjs',path:'/FROZEN/reference_source_material.mjs',bytes:90,sha256:g}]}},
  descriptor={manifestSha256:h,browserRecords:records,sourceRecords:records.map(r=>({file:r.path,bytes:r.bytes,sha256:r.sha256}))};
 return{document,scene,records,inherited,descriptor};
}
test('V3 only replaces actual browser boot edge and retains source/Area owners',()=>{
 const f=fixture(),before=structuredClone(f.inherited),actual=extendProductionServerPlan(f.inherited,f.descriptor),
  bindings=new Map(actual.serverConfig.bindings.map(row=>[row.url,row]));
 assert.deepEqual(f.inherited,before);
 assert.equal(bindings.get('/universal/long_adapter.mjs').path,'/TEST_ONLY/production_adapter.mjs');
 assert.equal(bindings.get('/universal/long_area_timeline.mjs').sha256,g);
 assert.equal(bindings.get('/reference/reference_source_material.mjs').sha256,g);
 assert.equal(actual.serverConfig.runtimeConfig.productionAdapter,'UNIVERSAL_PRODUCTION_V3');
 assert.equal(actual.sourceBindings.length,1+f.records.length);
 assert.notEqual(actual.sourceSignature,f.inherited.sourceSignature);
 assert.deepEqual(actual.serverConfig.runtimeConfig.universalVideo.productionV3,actual.productionIntegrity);
});
test('runtime binding rejects absent or conflicting sources and missing V3 adapter',()=>{
 let f=fixture();f.descriptor.browserRecords.pop();assert.throws(()=>extendProductionServerPlan(f.inherited,f.descriptor),/PRODUCTION_EXACT_BROWSER_CLOSURE_REQUIRED/);
 f=fixture();f.inherited.serverConfig.bindings.push(f.records[1]);assert.throws(()=>extendProductionServerPlan(f.inherited,f.descriptor),/PRODUCTION_BROWSER_EDGE_COLLISION/);
 f=fixture();delete f.document.productionV3;assert.throws(()=>validateLongRuntimeDocument(f.document,'s0'),/PRODUCTION_DOCUMENT_PROFILE_REQUIRED/);
 f=fixture();f.scene.renderProfile.productionAdapter='OTHER';assert.throws(()=>validateLongRuntimeDocument(f.document,'s0'),/PRODUCTION_DOCUMENT_ADAPTER_REQUIRED/);
});
test('fixed query hook rewires only original capture exact runtime import',()=>{
 const calls=[],next=(specifier,context)=>{calls.push([specifier,context]);return'UNCHANGED';};
 assert.deepEqual(resolveProductionCapture('./long_runtime.mjs',{parentURL:originalCaptureURL},next),{url:productionRuntimeURL,shortCircuit:true});
 assert.equal(calls.length,0);
 for(const[specifier,parentURL]of [['./long_runtime.mjs','file:///OTHER.mjs'],['../long_runtime.mjs',originalCaptureURL],['./other.mjs',originalCaptureURL]])
  assert.equal(resolveProductionCapture(specifier,{parentURL},next),'UNCHANGED');
 assert.equal(calls.length,3);assert.match(originalCaptureURL,/\?production-v3-fixed-entry$/);
});
test('actual frame verifier compares sourced chapter and new geometry clock, not old signature alone',async()=>{
 const f=fixture(),plan=extendProductionServerPlan(f.inherited,f.descriptor),frame=31,
  diagnostic={frame,productionV3:{runtimeProfile:'UNIVERSAL_PRODUCTION_V3',integrity:plan.productionIntegrity,
   probeVariant:'AFTER',chapter:structuredClone(f.document.productionV3.eventChapters[0]),
   geometryClock:evaluateProductionGeometryClock(f.document,frame),noInferredEnemyComplement:true,
   noInferredHistoricalUnits:true,originalProjectionUsed:true,originalNativeMarkerStyleAndAnchor:true}},
  captured={diagnostic};
 assert.equal(await assertProductionCapturedFrame(captured,plan),captured);
 for(const mutate of [v=>v.productionV3.geometryClock.sourceGeometryFrame++,v=>v.productionV3.chapter.displayLabel='UNSOURCED',
  v=>v.productionV3.integrity={...v.productionV3.integrity,sourceManifestSha256:g},v=>v.productionV3.probeVariant='BEFORE',
  v=>v.productionV3.noInferredEnemyComplement=false]){
  const bad=structuredClone(diagnostic);mutate(bad);await assert.rejects(assertProductionCapturedFrame({diagnostic:bad},plan));
 }
});
test('frozen capture and runtime sources remain exact pinned bytes',async()=>{
 assert.equal(hash(await readFile(new URL('../../universal-auto-video-v2/long_capture.mjs',import.meta.url))),
  'a4a6904dabd9a3306ffeafe0c1b0035f6062af81a56f62a0eb55dd055924d4d0');
 assert.equal(hash(await readFile(new URL('../../universal-auto-video-v2/long_runtime.mjs',import.meta.url))),
  'ee50049ad9967b22d5aa7dae09bd9e5295d22882c5d5c3db2b2cd4dec25dc606');
});
