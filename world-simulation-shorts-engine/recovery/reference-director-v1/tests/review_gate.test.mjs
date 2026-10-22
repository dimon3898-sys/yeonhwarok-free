import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildReview} from '../tools/build_review.mjs';
const target=JSON.parse(fs.readFileSync(new URL('../supplied/REFERENCE_DIRECTOR_TARGET_V1.json',import.meta.url)));
const input={schema:'WORLD_ENGINE_REFERENCE_DIRECTOR_INPUT_V1',gate:{renderAllowed:false},dataBindings:{}};
const sourceAudit={decodedFrames:635,decodedPixelHashComparison:{matched:635,mismatchedFrames:[]},planContractErrors:[]};
const args=()=>({target:structuredClone(target),input:structuredClone(input),sourceAudit:structuredClone(sourceAudit),targetSHA256:'a'.repeat(64)});
test('partial compilation cannot turn authored targets into a render admission',()=>{
 const out=buildReview(args());assert.equal(out.track.frameCount,546);assert.equal(out.track.actualRenderedFrames,0);
 assert.ok(out.track.frames.every(f=>f.camera===null&&f.actualDraw===null&&f.renderAllowed===false));
 assert.deepEqual(out.requests.map(r=>r.outputFrames),[180,180,186]);
 assert.ok(out.requests.every(r=>r.executable===false&&r.renderAllowed===false));
 assert.equal(out.gates.REFERENCE_VISUAL_MATCH,'NOT_EVALUATED');
});
test('honest unbound schedule retains global event state across both review boundaries',()=>{
 const {track}=buildReview(args());
 assert.deepEqual(track.frames.slice(179,181).map(f=>f.referenceFrame),[208,209]);
 assert.deepEqual(track.frames.slice(359,361).map(f=>f.referenceFrame),[388,389]);
 assert.ok(track.frames[179].eventAuthoringState.contextPins.every(p=>p.scale===1));
 assert.equal(track.frames[359].eventAuthoringState.heroPin.scale,1);
 assert.equal(track.frames[360].eventAuthoringState.heroPin.scale,1);
 const final=track.frames.at(-1).eventAuthoringState;
 assert.equal(final.boundary.revealFraction,1);assert.equal(final.metric.fullyReadable,true);
});
test('source audit mismatch and claimed available input fail before producing requests',()=>{
 for(const change of [p=>p.sourceAudit.decodedPixelHashComparison.matched=634,
  p=>p.sourceAudit.decodedPixelHashComparison.mismatchedFrames=[12],
  p=>p.sourceAudit.planContractErrors=['bad-window'],p=>p.input.gate.renderAllowed=true]){
  const p=args();change(p);assert.throws(()=>buildReview(p));
 }
});
test('trace leaves actual pixels empty rather than mistaking authored values for measurements',()=>{
 const out=buildReview(args());assert.equal(out.traceCSV.trim().split('\n').length,4915);
 assert.ok(out.traceCSV.includes('NOT_EXECUTED_BLOCKED'));assert.ok(!out.traceCSV.includes('ACTUAL_PIXEL_PASS'));
 assert.ok(out.gates.omittedArtifacts.includes('REFERENCE_VS_RENDER_CONTACT_SHEET.png'));
});
