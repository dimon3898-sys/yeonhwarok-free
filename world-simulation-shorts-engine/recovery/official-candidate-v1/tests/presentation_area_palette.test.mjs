import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePresentationAreaColors,resolvePresentationAreaColor,groupPresentationAreasByColor,bindPresentationBoundaryAreaColors} from '../presentation_area_palette.mjs';

const RED=[.85,.12,.12,.28],BLUE=[.1,.35,.95,.28],DEFAULT=[1,.8,.1,.14];
const areas=[{id:'north',state_id:'DAY_ONE',geometry:{type:'Polygon',coordinates:[[[0,0],[2,0],[2,2],[0,2],[0,0]]]}},
 {id:'south',state_id:'DAY_ONE',geometry:{type:'MultiPolygon',coordinates:[[[[3,0],[4,0],[4,1],[3,1],[3,0]]],[[[6,0],[7,0],[7,1],[6,1],[6,0]]]]}}];
const palette={areaColors:{north:RED,south:BLUE},territoryColors:{DAY_ONE:DEFAULT}};

test('two supplied areas at one date receive distinct colors without geometry or clock mutation',()=>{
 const original=structuredClone({areas,palette});validatePresentationAreaColors(palette.areaColors,{areas});
 const groups=groupPresentationAreasByColor(areas,palette,DEFAULT);
 assert.deepEqual(groups.map(g=>({state:g.stateId,color:g.color,ids:g.areas.map(a=>a.id)})),[
  {state:'DAY_ONE',color:RED,ids:['north']},{state:'DAY_ONE',color:BLUE,ids:['south']}]);
 assert.strictEqual(groups[0].areas[0],areas[0]);assert.strictEqual(groups[1].areas[0],areas[1]);
 assert.deepEqual({areas,palette},original);
});

test('color entries cannot introduce an unsupplied area',()=>{
 assert.throws(()=>validatePresentationAreaColors({invented:RED},{areas}),/PRESENTATION_AREA_COLOR_BINDING_INVALID/);
});

test('area opacity uses the existing accepted range; invalid/opaque fills fail',()=>{
 for(const color of [[1,0,0,.079],[1,0,0,.601],[1,0,0,1],[1.01,0,0,.2],[1,0,0],null])
  assert.throws(()=>validatePresentationAreaColors({north:color},{areas}),/PRESENTATION_AREA_COLOR_BINDING_INVALID/);
 for(const alpha of [.08,.6])assert.doesNotThrow(()=>validatePresentationAreaColors({north:[1,0,0,alpha]},{areas}));
});

test('explicit area overrides state color; absent area entry retains state/default colors',()=>{
 assert.deepEqual(resolvePresentationAreaColor(palette,areas[0],DEFAULT),RED);
 assert.deepEqual(resolvePresentationAreaColor({territoryColors:{DAY_ONE:BLUE}},areas[0],DEFAULT),BLUE);
 assert.deepEqual(resolvePresentationAreaColor({},areas[0],DEFAULT),DEFAULT);
 const result=resolvePresentationAreaColor(palette,areas[0],DEFAULT);result[0]=0;assert.equal(RED[0],.85);
});

test('same-color groups retain painter order when interleaved with another color',()=>{
 const input=[areas[0],areas[1],{...areas[0],id:'northLater'}],p={areaColors:{north:RED,south:BLUE,northLater:RED}};
 const groups=groupPresentationAreasByColor(input,p,DEFAULT);
 assert.deepEqual(groups.map(g=>g.areas.map(a=>a.id)),[['north'],['south'],['northLater']]);
});

test('adjacent equal colors reuse a draw group, but different temporal states stay distinct',()=>{
 const input=[areas[0],{...areas[0],id:'northTwo'},{...areas[0],id:'northDayTwo',state_id:'DAY_TWO'}],
  p={territoryColors:{DAY_ONE:RED,DAY_TWO:RED}};
 assert.deepEqual(groupPresentationAreasByColor(input,p,DEFAULT).map(g=>g.areas.map(a=>a.id)),[['north','northTwo'],['northDayTwo']]);
});

test('boundary color signature ignores local IDs but preserves the effective source-ordered colors',()=>{
 const records=areas.map(a=>({geometry:a.geometry,role:'CONTROL_AREA',source:{source_reference:'SYNTHETIC_TEST_ONLY'}}));
 const before=bindPresentationBoundaryAreaColors(records,areas,'DAY_ONE',palette),
  afterRows=areas.map(a=>({...a,id:a.id+'After'})),
  after=bindPresentationBoundaryAreaColors(records,afterRows,'DAY_TWO',{areaColors:{northAfter:RED,southAfter:BLUE}});
 assert.deepEqual(before,after);
 const changed=bindPresentationBoundaryAreaColors(records,afterRows,'DAY_TWO',{areaColors:{northAfter:RED,southAfter:RED}});
 assert.notDeepEqual(before,changed,'same geometry with changed owner color must differ at a PART cut');
});

test('boundary continuity requires an explicit area or state color for every supplied area',()=>{
 const records=areas.map(a=>({geometry:a.geometry}));
 assert.throws(()=>bindPresentationBoundaryAreaColors(records,areas,'DAY_ONE',{areaColors:{north:RED}}),/PRESENTATION_CONTINUITY_EXPLICIT_STATE_COLOR_REQUIRED/);
});

test('palette capacity is bounded by the admitted scene and does not accept arrays',()=>{
 assert.throws(()=>validatePresentationAreaColors([RED],{areas}),/PRESENTATION_AREA_PALETTE_INVALID/);
 const rows=Array.from({length:65},(_,i)=>({id:'area'+i}));
 assert.throws(()=>validatePresentationAreaColors(Object.fromEntries(rows.map(a=>[a.id,RED])),{areas:rows}),/PRESENTATION_AREA_PALETTE_INVALID/);
});

// New optional-field compatibility case; not a rerun of a prior renderer PASS.
test('omitted areaColors preserves legacy global state grouping for interleaved states',()=>{
 const input=[areas[0],{...areas[1],id:'dayTwo',state_id:'DAY_TWO'},{...areas[0],id:'dayOneAgain'}],
  p={territoryColors:{DAY_ONE:RED,DAY_TWO:BLUE}};
 assert.deepEqual(groupPresentationAreasByColor(input,p,DEFAULT).map(g=>g.areas.map(a=>a.id)),[['north','dayOneAgain'],['dayTwo']]);
 assert.deepEqual(groupPresentationAreasByColor(input,{...p,areaColors:{}},DEFAULT).map(g=>g.areas.map(a=>a.id)),[['north'],['dayTwo'],['dayOneAgain']]);
});
