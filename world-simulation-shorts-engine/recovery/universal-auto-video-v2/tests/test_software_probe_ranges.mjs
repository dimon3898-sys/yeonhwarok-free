/** Real-plan range proof: neighboring frame numbers alone are not a scene cut. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {selectTemporalFrames,assertActualAdjacentScenePair} from '../software_probe_long.mjs';
const document=JSON.parse(await readFile(new URL('../fixtures/PLAN_80S.json',import.meta.url)));
test('actualproductionrange-derivedprobe straddlesdifferentadjacentscenes duringmotion',()=>{
 const {frames,witness}=selectTemporalFrames(document);
 assert.deepEqual(frames,[0,419,420,1200,2399]);assert.equal(witness.cutFrame,420);
 assert.notEqual(witness.leftSceneId,witness.rightSceneId);
 assert.equal(witness.leftRange[1],witness.rightRange[0]);assert.equal(witness.rightRange[0],witness.afterFrame);
 assert.deepEqual(assertActualAdjacentScenePair(document,419,420),witness);
});
test('fixed299/300same-scenecomparison cannotcertifyarealrendercut',()=>{
 assert.throws(()=>assertActualAdjacentScenePair(document,299,300),/UNIVERSAL_DISTINCT_ADJACENT_SCENES_REQUIRED/);
 assert.throws(()=>assertActualAdjacentScenePair(document,419,421),/UNIVERSAL_ADJACENT_GLOBAL_FRAMES_REQUIRED/);
});
test('selector followsactualchangedranges ratherthanfixed420',()=>{
 const altered=structuredClone(document),left=altered.scenes.find(row=>row.endFrame===420),right=altered.scenes.find(row=>row.startFrame===420);
 left.endFrame=500;right.startFrame=500;
 const {frames,witness}=selectTemporalFrames(altered);assert.deepEqual(frames,[0,499,500,1200,2399]);assert.equal(witness.cutFrame,500);
});
