/** Pure CPU validation tests. The actual follow-up render runs inside the pinned image. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {validateFollowupRows,evidenceNames} from './camera_hold_followup.mjs';
const units=[{id:'generic',profile_id:'test',anchor:[0,0],size_px:104,rotation_degrees:0}],
 points=Array.from({length:8},(_,index)=>[100+index*60,400+index*70]);
function row(variant,frame){return {frame,eventStartFrame:0,
 raw_rgba_sha256:(variant==='A'?'a':frame===99?'b':frame===100?'c':'d').repeat(64),
 projectedReferencePoints:points.map(([x,y])=>[x+(variant==='E'?3:0),y]),
 diagnostic:{camera:{bounds:variant==='A'?[0,0,1,1]:[-.003,0,.997,1],
 nativeExpandedBounds:variant==='A'?[0,0,1,1]:[-.003,0,.997,1],rollDegrees:0,overscan:1.2},
 territory:{controls:{frame,boundaryLatitudes:[frame/100,frame/100+1]}},
 units:{units:structuredClone(units)},protection:{sourceGeometrySha256:'f'.repeat(64)}}};}
const cases=()=>({A:[row('A',100)],E:[row('E',99),row('E',100),row('E',101)]});
test('actual pixel difference and visible projected displacement qualify the selected hold comparison',()=>{
 const result=validateFollowupRows(cases());assert.equal(result.actualCameraDeltaPixels,3);
 assert.equal(result.holdLocked,true);assert.equal(result.eventAdvances,true);assert.equal(result.pixelsDiffer,true);
});
test('rounding-only camera metadata with subpixel/equal actual pixels cannot pass',()=>{
 const value=cases();value.E.forEach(item=>{item.projectedReferencePoints=structuredClone(points);});
 assert.throws(()=>validateFollowupRows(value),/FOLLOWUP_CAMERA_DIFFERENCE_MUST_EXCEED_ONE_PIXEL/);
 const equal=cases();equal.E[1].raw_rgba_sha256=equal.A[0].raw_rgba_sha256;
 assert.throws(()=>validateFollowupRows(equal),/FOLLOWUP_SELECTED_CAMERA_MUST_CHANGE_ACTUAL_PIXELS/);
});
test('a frozen event or moving hold projection is rejected',()=>{
 const event=cases();event.E[2].diagnostic.territory.controls.boundaryLatitudes=event.E[1].diagnostic.territory.controls.boundaryLatitudes;
 assert.throws(()=>validateFollowupRows(event),/FOLLOWUP_EVENT_BOUNDARY_MUST_KEEP_ADVANCING/);
 const moving=cases();moving.E[0].projectedReferencePoints[0][0]+=.1;
 assert.throws(()=>validateFollowupRows(moving),/FOLLOWUP_ACTUAL_PROJECTION_HOLD_REQUIRED/);
});
test('same-frame source event and world unit data must remain equal',()=>{
 const value=cases();value.E[1].diagnostic.units.units[0].size_px=118.56;
 assert.throws(()=>validateFollowupRows(value),/FOLLOWUP_WORLD_UNITS_AND_SIZES_MUST_MATCH/);
 const event=cases();event.E[1].diagnostic.territory.controls.frame=101;
 assert.throws(()=>validateFollowupRows(event),/FOLLOWUP_EVENT_MUST_MATCH_AT_FRAME_100/);
});
test('follow-up output is exactly two selected test-only PNG checkpoints',()=>{
 assert.deepEqual(evidenceNames,['A_100.png','E_100.png']);
});
