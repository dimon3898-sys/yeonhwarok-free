/** Focused probe-contract tests; these do not claim a real browser draw. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {selectProductionTemporalFrames,assertSuppliedGeometry,frameWitness,compareActualPixels,configFor} from '../software_probe_production.mjs';
import {assertActualAdjacentScenePair} from '../../universal-auto-video-v2/software_probe_long.mjs';
const document=JSON.parse(await readFile(new URL('../fixtures/PLAN_80S.json',import.meta.url)));

test('actual operational cut is inside one bound source transition with real frame advance',()=>{
 const {frames,witness,abFrame}=selectProductionTemporalFrames(document),schedule=document.productionV3.geometrySchedule.find(row=>row.scheduleId===witness.geometryScheduleId);
 assert.equal(frames.length,5);assert.equal(new Set(frames).size,5);assert.equal(frames[0],0);assert.equal(frames[4],document.totalFrames-1);
 assert.equal(frames[3],abFrame);assert.equal(witness.afterFrame,witness.beforeFrame+1);assert.notEqual(witness.leftSceneId,witness.rightSceneId);
 assert.ok(witness.beforeFrame>schedule.startFrame);assert.ok(witness.afterFrame<schedule.endFrame-1);
 assert.notEqual(witness.sourceBeforeFrame,witness.sourceAfterFrame);assert.equal(document.productionV3.eventChapters.length,12);
});
test('changing the work partition moves the witness without changing story or source clock',()=>{
 const edited=structuredClone(document),old=selectProductionTemporalFrames(edited).witness,
  left=edited.scenes.find(row=>row.endFrame===old.cutFrame),right=edited.scenes.find(row=>row.startFrame===old.cutFrame);
 left.endFrame+=3;right.startFrame+=3;
 const now=selectProductionTemporalFrames(edited).witness;
 assert.equal(now.cutFrame,old.cutFrame+3);assert.equal(now.geometryScheduleId,old.geometryScheduleId);
 assert.deepEqual(edited.productionV3,document.productionV3);
});
test('same work scene, nonadjacent frames and chapter-only cuts cannot fake cut proof',()=>{
 assert.throws(()=>assertActualAdjacentScenePair(document,document.scenes[0].startFrame+2,document.scenes[0].startFrame+3),/DISTINCT_ADJACENT_SCENES/);
 assert.throws(()=>assertActualAdjacentScenePair(document,1,3),/ADJACENT_GLOBAL_FRAMES/);
 const chapterOnly=structuredClone(document),chapters=chapterOnly.productionV3.eventChapters;
 chapterOnly.scenes=chapters.map((chapter,index)=>({...document.scenes[0],sceneId:'chapter-only-'+index,startFrame:chapter.startFrame,endFrame:chapter.endFrame}));
 assert.throws(()=>selectProductionTemporalFrames(chapterOnly),/REAL_WORK_CUT_INSIDE_SOURCE_TRANSITION/);
});
function suppliedControls(){
 const legacy=document.legacyScenePlan,first=legacy.areas[0],front=legacy.front_lines[0],lookup=id=>legacy.geometries.find(row=>row.id===id).geometry;
 return{areas:[{id:first.id,geometry:structuredClone(lookup(first.geometry_ref)),alpha:1}],
  fronts:[{id:front.id,geometry:structuredClone(lookup(front.geometry_ref)),alpha:1}]};
}
test('actual control IDs and every coordinate must equal supplied geometry and explicit owner',()=>{
 const controls=suppliedControls(),facts=assertSuppliedGeometry(document,controls);
 assert.equal(facts.exactSuppliedCoordinates,true);assert.equal(facts.noEnemyComplementCreated,true);assert.equal(facts.areas.length,1);
 const reordered=structuredClone(controls);for(const item of [...reordered.areas,...reordered.fronts])item.geometry={type:item.geometry.type,coordinates:item.geometry.coordinates};
 assert.deepEqual(assertSuppliedGeometry(document,reordered),facts);
 const modified=structuredClone(controls);modified.areas[0].geometry.coordinates[0][0][0]+=.01;
 assert.throws(()=>assertSuppliedGeometry(document,modified),/ACTUAL_GEOMETRY_CHANGED/);
 const invented=structuredClone(controls);invented.areas[0].id='INFERRED_OPPONENT_COMPLEMENT';
 assert.throws(()=>assertSuppliedGeometry(document,invented),/UNKNOWN_ACTUAL_GEOMETRY_ID/);
});
test('A/B hashes independently bind actual camera, controls and chapter/date glyph',()=>{
 const diagnostic={camera:{camera:{flatBounds:[1,2,3,4]}},area:{controls:suppliedControls(),date:{text:'snapshot disclosure'}},
  productionV3:{chapter:{chapterId:'x'},geometryClock:{sourceGeometryFrame:123}}},before=frameWitness(diagnostic),same=frameWitness(structuredClone(diagnostic));
 assert.equal(before.cameraSha256,same.cameraSha256);assert.equal(before.geometrySha256,same.geometrySha256);assert.equal(before.dateSha256,same.dateSha256);
 const changed=structuredClone(diagnostic);changed.productionV3.geometryClock.sourceGeometryFrame++;
 assert.notEqual(frameWitness(changed).dateSha256,before.dateSha256);
 const moved=structuredClone(diagnostic);moved.camera.camera.flatBounds[0]++;
 assert.notEqual(frameWitness(moved).cameraSha256,before.cameraSha256);
});
function pixelsAt(x,y){const before=new Uint8Array(1080*1920*4),after=new Uint8Array(before.length);after[((1919-y)*1080+x)*4]=255;return{before,after};}
test('actual A/B readback count uses lower-left RGBA and protects supplied screen regions',()=>{
 const {before,after}=pixelsAt(500,500),measured=compareActualPixels(before,after,{safeArea:[10,10,1070,1910],protectedGraphics:[{box:[10,10,100,100]}]});
 assert.equal(measured.changedPixelCount,1);assert.equal(measured.protectedGraphicChangedPixelCount,0);assert.equal(measured.outsideSafeAreaChangedPixelCount,0);
 assert.throws(()=>compareActualPixels(before,after,{safeArea:[10,10,1070,1910],protectedGraphics:[{box:[490,490,510,510]}]}),/CHANGED_PROTECTED/);
 const edge=pixelsAt(1,1);assert.throws(()=>compareActualPixels(edge.before,edge.after,{safeArea:[10,10,1070,1910]}),/CHANGED_OUTSIDE_SAFE_AREA/);
 assert.throws(()=>compareActualPixels(before,before,{safeArea:[10,10,1070,1910]}),/MUST_CHANGE_ACTUAL_PIXELS/);
});
test('probe config changes only explicit test variant and range metadata',()=>{
 const scene=document.scenes[0],base={runtimeConfig:{universalVideo:{plan:document,scene},productionAdapter:'UNIVERSAL_PRODUCTION_V3'},bindings:[{url:'/fixed'}]},copy=JSON.stringify(base),
  before=configFor(base,scene,'BEFORE'),after=configFor(base,scene,'AFTER');
 assert.equal(JSON.stringify(base),copy);assert.equal(before.runtimeConfig.testOnlySoftwareProbe,true);assert.equal(after.runtimeConfig.testOnlySoftwareProbe,true);
 assert.deepEqual(before.runtimeConfig.universalVideo,after.runtimeConfig.universalVideo);assert.deepEqual(before.bindings,after.bindings);
 assert.equal(before.runtimeConfig.productionV3ProbeVariant,'BEFORE');assert.equal(after.runtimeConfig.productionV3ProbeVariant,'AFTER');
 assert.throws(()=>configFor(base,scene,'INVENTED'),/SUPPORTED_AB_VARIANT/);
});
