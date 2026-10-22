import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compileReferenceEvents,compileUnboundReferenceSchedule,evaluateReferenceEvents,graphemes,popScale,compileSourceArclength,geographicPointAt,revealSourceLine,metricScreenPlacement,compileMetricScreenTrack,visibilityDecision,labelPlacement,authoredPinSvg} from '../director_events.mjs';

const target=JSON.parse(fs.readFileSync(new URL('../supplied/REFERENCE_DIRECTOR_TARGET_V1.json',import.meta.url)));
const authored=compileUnboundReferenceSchedule(target);
const s={id:'explicit-synthetic-fixture',sha256:'a'.repeat(64),verification:'SYNTHETIC_TEST'};
const input={schema:'REFERENCE_DIRECTOR_EVENT_INPUT_V1',dataMode:'SYNTHETIC_TEST',contextLocations:[{id:'c1',label:'새별',anchor:[12,-15],source:s},{id:'c2',label:'긴섬길',anchor:[14,-16],source:s}],heroLocation:{id:'h',label:'대상',anchor:[13,-15.5],source:s},boundary:{id:'b',geometry:{type:'LineString',coordinates:[[13,-15.5],[13.02,-15.49],[13.03,-15.47]]},direction:'FORWARD',source:s},metric:{id:'m',text:'42 m',source:s}};
const fixture=compileReferenceEvents(input);
test('strict null binding cannot be promoted to a compiled actual event plan',()=>assert.throws(()=>compileReferenceEvents({...input,heroLocation:null}),/HERO_OBJECT_REQUIRED/));
test('target authoring schedule explicitly lacks geometry, pixels and render permission',()=>{
 assert.equal(authored.status,'AUTHORING_ONLY_UNBOUND_NOT_EXECUTABLE');assert.equal(authored.renderAllowed,false);assert.equal(authored.heroLocation.anchor,null);assert.equal(authored.boundary.geometry,null);assert.equal(authored.projection,null);
});
test('unknown root and nested production fields fail rather than disappear',()=>{
 assert.throws(()=>compileReferenceEvents({...input,ignored:'bad'}),/UNKNOWN_FIELD/);
 assert.throws(()=>compileReferenceEvents({...input,heroLocation:{...input.heroLocation,longitude:20}}),/UNKNOWN_FIELD/);
 assert.throws(()=>compileReferenceEvents({...input,boundary:{...input.boundary,geometry:{...input.boundary.geometry,crs:'ignored'}}}),/UNKNOWN_FIELD/);
});
test('verified and observed-reference provenance remains separate from synthetic data',()=>{
 const verified=structuredClone(input);verified.dataMode='REFERENCE_BOUND';
 for(const l of [...verified.contextLocations,verified.heroLocation])l.source={...s,verification:'VERIFIED'};
 verified.boundary.source={...s,verification:'VERIFIED'};verified.metric.source={...s,verification:'OBSERVED_REFERENCE_TEXT'};
 assert.equal(compileReferenceEvents(verified).metric.source.verification,'OBSERVED_REFERENCE_TEXT');
 verified.boundary.source.verification='OBSERVED_REFERENCE_TEXT';assert.throws(()=>compileReferenceEvents(verified),/BOUNDARY_SOURCE_VERIFICATION_REQUIRED/);
});
test('source identities require pinned SHA and distinct input IDs',()=>{
 const bad=structuredClone(input);bad.heroLocation.source.sha256='missing';assert.throws(()=>compileReferenceEvents(bad),/SHA256_REQUIRED/);
 assert.throws(()=>compileReferenceEvents({...input,metric:{...input.metric,id:'h'}}),/UNIQUE_INPUT_IDS_REQUIRED/);
});
test('graphemes retain combining sequences and complex emoji as a unit',()=>assert.deepEqual(graphemes('가e\u0301👩🏽‍🚀'),['가','é','👩🏽‍🚀']));
test('long labels and metric text fail explicit fixed-window admission without postponing events',()=>{
 assert.throws(()=>compileReferenceEvents({...input,contextLocations:[{...input.contextLocations[0],label:'너무너무긴이름이다'},input.contextLocations[1]]}),/REVEAL_WINDOW_TOO_SHORT/);
 assert.throws(()=>compileReferenceEvents({...input,metric:{...input.metric,text:'1234 m'}}),/REVEAL_WINDOW_TOO_SHORT/);
});
test('context and hero pins pop once and remain at unity after settle',()=>{
 assert.equal(popScale(176,177,16),0);assert.equal(popScale(177,177,16),0);assert.equal(popScale(192,177,16),1);
 assert.equal(popScale(338,333,15),.95652);assert.equal(popScale(339,333,15),.92174);
 for(let f=348;f<575;f++)assert.equal(evaluateReferenceEvents(authored,f).heroPin.scale,1);
});
test('pin dimensions remain in screen pixels while anchors are only geographic data',()=>{
 const f=evaluateReferenceEvents(fixture,420);assert.deepEqual(f.heroPin.anchor,[13,-15.5]);assert.equal(f.heroPin.heightPx,151);assert.equal(f.contextPins[0].heightPx,64);assert.equal(f.heroPin.sizeSpace,'SCREEN_PIXELS');assert.equal(f.heroPin.anchorMode,'BOTTOM_TIP');
});
test('labels reveal at specified global frames and hold during the second name',()=>{
 assert.equal(evaluateReferenceEvents(authored,288).labels[0].glyphs[0].opacity,0);
 assert.equal(evaluateReferenceEvents(authored,290).labels[0].glyphs[0].startFrame,289);
 assert.deepEqual(evaluateReferenceEvents(authored,311).labels[0].glyphs.map(g=>g.opacity),[1,1,1]);
 assert.deepEqual(evaluateReferenceEvents(authored,323).labels[1].glyphs.map(g=>g.opacity),[1,1,1]);
});
test('labels change from required readability to context culling without being deleted',()=>{
 assert.equal(evaluateReferenceEvents(authored,332).labels[0].role,'REQUIRED_VISIBLE_SAFE');
 const f=evaluateReferenceEvents(authored,333);assert.equal(f.labels[0].role,'CONTEXT_CULL');assert.deepEqual(f.labels[0].glyphs.map(g=>g.opacity),[1,1,1]);
});
test('whole-word reservation is stable while prefixes reveal',()=>{
 const m={fullWord:'긴섬길',advances:[0,48,96],totalAdvance:144,fullWordInkBounds:[0,-48,144,0]};const p=labelPlacement(m,[400,800]);
 assert.equal(p.left,328);assert.equal(p.bottom,724);assert.deepEqual(p.glyphOrigins,[[328,724],[376,724],[424,724]]);
 assert.equal(p.centering,'FULL_WORD_INK_FIXED');
 const overhang=labelPlacement({...m,fullWordInkBounds:[-2,-48,140,3]},[400,800]);assert.equal(overhang.left,331);assert.equal(overhang.baseline,721);assert.equal((overhang.left-2+overhang.left+140)/2,400);assert.equal(overhang.baseline+3,724);
});
test('boundary reveal is monotonic, completes at 485 and never pulses or vanishes',()=>{
 let last=0;for(let f=29;f<575;f++){const b=evaluateReferenceEvents(authored,f).boundary;assert.ok(b.revealFraction>=last);assert.equal(b.repeatPulse,false);last=b.revealFraction;}
 assert.equal(evaluateReferenceEvents(authored,455).boundary.revealFraction,0);assert.equal(evaluateReferenceEvents(authored,485).boundary.revealFraction,1);
});
test('metric whitespace consumes layout only, not an extra pop beat or number count-up',()=>{
 const f=evaluateReferenceEvents(authored,505).metric;
 assert.deepEqual(f.glyphs.filter(g=>!g.layoutOnly).map(g=>g.startFrame),[487,492,497]);assert.equal(f.glyphs[2].layoutOnly,true);assert.equal(f.countUp,false);assert.equal(f.text,'85 m');
 for(let n=505;n<575;n++)assert.ok(evaluateReferenceEvents(authored,n).metric.glyphs.filter(g=>!g.layoutOnly).every(g=>g.opacity===1&&g.scale===1));
});
test('all 546 samples and review-window seams preserve one global state',()=>{
 const full=Array.from({length:546},(_,i)=>evaluateReferenceEvents(authored,i+29));
 const windows=[[29,209],[209,389],[389,575]].flatMap(([a,b])=>Array.from({length:b-a},(_,i)=>evaluateReferenceEvents(authored,a+i)));
 assert.deepEqual(full,windows);assert.equal(full[180].referenceFrame,209);assert.equal(full[360].referenceFrame,389);assert.equal(full[360].heroPin.scale,1);
 assert.throws(()=>evaluateReferenceEvents(authored,28),/OUTSIDE_CORE/);assert.throws(()=>evaluateReferenceEvents(authored,575),/OUTSIDE_CORE/);
});
test('authoring target cannot quietly alter event timing or windows',()=>{
 const bad=structuredClone(target);bad.events.find(e=>e.id==='metric').glyphStartReferenceFrames[0]=488;
 assert.throws(()=>compileUnboundReferenceSchedule(bad),/TIMING_MISMATCH/);
 const w=structuredClone(target);w.reviewWindows[0].outputFrames=546;assert.throws(()=>compileUnboundReferenceSchedule(w),/REVIEW_WINDOWS_REQUIRED/);
 const unknown=structuredClone(target);unknown.events[0].ignored='unsupported';assert.throws(()=>compileUnboundReferenceSchedule(unknown),/UNKNOWN_FIELD/);
});
test('geographic arclength is independent of projection scale, rotation and visible clipping',()=>{
 const arc=fixture.arclength;const before=JSON.stringify(arc),cut=revealSourceLine(arc,.6),mid=geographicPointAt(arc,.5);
 for(const project of [p=>p.map(v=>v*100),p=>[-p[1]*1000,p[0]*1000]]){
  assert.deepEqual(revealSourceLine(arc,.6),cut);assert.deepEqual(metricScreenPlacement(arc,{project}).geographicAnchor,mid);
 }assert.equal(JSON.stringify(arc),before);
});
test('directed source endpoints, duplicate segments and original vertices remain intact',()=>{
 const points=[[0,0],[0,0],[1,0],[1,2]],arc=compileSourceArclength(points,'REVERSE');
 assert.deepEqual(revealSourceLine(arc,0),[]);assert.deepEqual(revealSourceLine(arc,1),[...points].reverse());assert.deepEqual(geographicPointAt(arc,0),[1,2]);assert.deepEqual(geographicPointAt(arc,1),[0,0]);assert.deepEqual(points,[[0,0],[0,0],[1,0],[1,2]]);
});
test('invalid and dateline-wrapped source lines are blocked, never silently rerouted',()=>{
 assert.throws(()=>compileSourceArclength([[0,0],[0,0]]),/ZERO_LENGTH/);assert.throws(()=>compileSourceArclength([[179,0],[-179,1]]),/WRAPPED_LINE_UNSUPPORTED/);assert.throws(()=>compileSourceArclength([[0,91],[1,1]]),/GEOGRAPHIC_POINT_REQUIRED/);
});
test('metric uses canonical midpoint and 24px upward normal with readable direction',()=>{
 const arc=compileSourceArclength([[0,0],[1,0]]),p=metricScreenPlacement(arc,{project:([x,y])=>[x*1000,y*1000]});
 assert.deepEqual(p.position,[500,-24]);assert.equal(p.angleRadians,0);assert.equal(p.offsetPixels,24);
 const reversed=compileSourceArclength([[1,0],[0,0]]);assert.deepEqual(metricScreenPlacement(reversed,{project:([x,y])=>[x*1000,y*1000],normalSign:-1}).position,[500,-24]);
});
test('source curve midpoint integrates latitude-varying segment speed rather than averaging coordinates',()=>{
 const arc=compileSourceArclength([[0,0],[120,60]]),mid=geographicPointAt(arc,.5);
 assert.ok(mid[0]<60 && mid[1]<30);assert.ok(Math.abs(arc.total-12942078)<2);
 const first=compileSourceArclength([[0,0],mid]);assert.ok(Math.abs(first.total/arc.total-.5)<1e-10);
});
test('metric normal stays on one source side near vertical and unreadable global flip is explicitly blocked',()=>{
 const arc=compileSourceArclength([[0,0],[1,0]]),project=deg=>([x,y])=>{const t=deg*Math.PI/180;return [1000*(Math.cos(t)*x-Math.sin(t)*y),1000*(Math.sin(t)*x+Math.cos(t)*y)];};
 const a=metricScreenPlacement(arc,{project:project(89.9)}),b=metricScreenPlacement(arc,{project:project(90.1)});
 assert.ok(Math.hypot(a.normal[0]-b.normal[0],a.normal[1]-b.normal[1])<.01);
 assert.throws(()=>compileMetricScreenTrack(arc,{projectAt:(f,p)=>project(f===0?89.9:90.1)(p),referenceFrames:[0,1]}),/READABLE_ORIENTATION_DISCONTINUITY/);
});
test('unsafe required objects fail; prior context and large areas clip without geometry mutation',()=>{
 assert.throws(()=>visibilityDecision('REQUIRED_VISIBLE_SAFE',[0,0,49,64]),/OUTSIDE_SAFE/);
 assert.equal(visibilityDecision('CONTEXT_CULL',[-200,20,-10,100]).draw,false);
 assert.equal(visibilityDecision('AREA_VIEWPORT_CLIP',[-1000,-1000,2000,2000]).draw,true);
 assert.equal(visibilityDecision('AREA_VIEWPORT_CLIP',[-1000,-1000,2000,2000]).geometryMutation,false);
});
test('new authored SVG has real evenodd holes and explicit tip, no opaque background circle',()=>{
 const hero=authoredPinSvg('HERO'),small=authoredPinSvg('CONTEXT');
 assert.match(hero,/width="116" height="151"/);assert.match(small,/width="49" height="64"/);assert.match(hero,/fill-rule="evenodd"/);assert.match(small,/data-hole-diameter="29"/);assert.match(hero,/data-tip="58,151"/);assert.doesNotMatch(hero,/<circle/);assert.match(hero,/stroke-width="1.5"/);
});
