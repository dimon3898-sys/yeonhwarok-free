import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePresentation,assertPresentationBoundaryContinuity} from '../presentation_plan.mjs';

const RED=[.85,.12,.12,.28],BLUE=[.1,.35,.95,.28],GRAY=[.5,.5,.5,.2];
const geometry={type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
 line={type:'LineString',coordinates:[[1,0],[1,1]]};
function scene(suffix,date){return{event_type:'WAR',timing:{fps:30,total_frames:30,event_start_frame:0},
 source_notes:[{id:'TEST',source_type:'SYNTHETIC_TEST',source_reference:'PALETTE_CONTRACT_TEST_ONLY',verification_status:'FIXTURE'}],
 geometries:[{id:'POLY',geometry},{id:'LINE',geometry:line}],
 areas:[{id:'area'+suffix,geometry_ref:'POLY',role:'CONTROL_AREA',source_id:'TEST'}],
 front_lines:[{id:'front'+suffix,geometry_ref:'LINE',role:'FRONT_LINE',source_id:'TEST'}],
 time_steps:[{id:'state'+suffix,date,area_ids:['area'+suffix],front_line_ids:['front'+suffix]}],locations:[]};}
function presentation(suffix,color){return{camera:{mode:'KEYFRAMES',keyframes:[{frame:0,center:[.5,.5],zoom:1},{frame:29,center:[.5,.5],zoom:1}]},
 initialStateVisibility:'PRESERVE_PROVIDED',areaColors:{['area'+suffix]:color}};}

test('real presentation validator admits an explicit per-area palette without requiring state color',()=>{
 const s=scene('A','2000-01-01'),p=presentation('A',RED),v=validatePresentation(p,{scene:s});
 assert.deepEqual(v.areaColors,p.areaColors);assert.equal(v.territoryColors,undefined);
 assert.throws(()=>validatePresentation({...p,areaColors:{missing:RED}},{scene:s}),/PRESENTATION_AREA_COLOR_BINDING_INVALID/);
});

test('actual PART continuity rejects an owner-color discontinuity despite identical source geometry',()=>{
 const before={scene:scene('A','2000-01-01'),presentation:presentation('A',RED)},
  after={scene:scene('B','2000-01-02'),presentation:presentation('B',BLUE)};
 assert.throws(()=>assertPresentationBoundaryContinuity(before,after),/PRESENTATION_CUT_PROVIDED_STATE_DISCONTINUITY/);
 after.presentation.areaColors.areaB=RED;
 assert.equal(assertPresentationBoundaryContinuity(before,after).status,'SOURCE_STATE_CONTINUITY_CONFIRMED');
});

test('unused state color cannot conceal or manufacture a per-area continuity change',()=>{
 const before={scene:scene('A','2000-01-01'),presentation:{...presentation('A',RED),territoryColors:{stateA:GRAY}}},
  after={scene:scene('B','2000-01-02'),presentation:{...presentation('B',RED),territoryColors:{stateB:BLUE}}};
 assert.equal(assertPresentationBoundaryContinuity(before,after).status,'SOURCE_STATE_CONTINUITY_CONFIRMED');
 delete after.presentation.areaColors;
 assert.throws(()=>assertPresentationBoundaryContinuity(before,after),/PRESENTATION_CUT_PROVIDED_STATE_DISCONTINUITY/);
});
