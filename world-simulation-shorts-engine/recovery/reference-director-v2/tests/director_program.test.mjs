import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {compileDirectorProgram,evaluateDirectorProgram,programWindowFrame,PROGRAM_SCHEMA} from '../director_program.mjs';

import {fixture,source} from '../fixtures/component_program.mjs';
export {fixture};

test('generic program accepts non-reference timing and preserves supplied source geometry',()=>{
 const input=fixture(),raw=JSON.stringify(input),p=compileDirectorProgram(input);
 assert.deepEqual(p.frameRange,[700,820]);assert.equal(p.sourceTruth,'INPUT_PROVENANCE_IS_NOT_INDEPENDENT_FACT_VERIFICATION');
 assert.equal(JSON.stringify(input),raw);assert.deepEqual(p.data.areas[0].geometry,input.areas[0].geometry);assert.ok(Object.isFrozen(p));
});
test('the same program handles a different origin, hemisphere, label length and time range',()=>{
 const input=fixture();input.frameRange=input.frameRange.map(v=>v+1000);input.windows.forEach(w=>w.frameRange=w.frameRange.map(v=>v+1000));
 for(const e of input.events){for(const k of ['startFrame','holdUntilFrame','fullyReadableFrame'])if(e[k]!==undefined)e[k]+=1000;if(e.requiredRange)e.requiredRange=e.requiredRange.map(v=>v+1000);}
 for(const location of input.locations)location.anchor=[-70,-30];input.locations[0].label='Southern port';
 for(const record of [...input.areas,...input.lines]){const points=record.geometry.type==='Polygon'?record.geometry.coordinates.flat():record.geometry.coordinates;points.forEach(p=>{p[0]-=80;p[1]-=40;});}
 const p=compileDirectorProgram(input);assert.equal(evaluateDirectorProgram(p,1780).globalFrame,1780);assert.equal(p.data.locations[0].label,'Southern port');
});
test('global evaluation is deterministic and window seams never restart event state',()=>{
 const p=compileDirectorProgram(fixture()),a=programWindowFrame(p,'first',59),b=programWindowFrame(p,'second',0);
 assert.equal(a.globalFrame,759);assert.equal(b.globalFrame,760);assert.equal(b.records.find(r=>r.id==='boundary').fraction,.5);
 assert.deepEqual(programWindowFrame(p,'second',0),evaluateDirectorProgram(p,760));
 evaluateDirectorProgram(p,819);assert.deepEqual(programWindowFrame(p,'second',0),b);
});
test('only visible graphemes receive beats; whitespace is reserved but never pops',()=>{
 const p=compileDirectorProgram(fixture()),m=evaluateDirectorProgram(p,794).records.find(r=>r.id==='metric');
 assert.deepEqual(m.glyphs.filter(g=>!g.layoutOnly).map(g=>g.startFrame),[772,776,780,784]);
 assert.equal(m.glyphs.find(g=>g.grapheme===' ').layoutOnly,true);assert.equal(m.fullyReadable,true);
});
test('required visibility is an event interval; older context is allowed to cull',()=>{
 const p=compileDirectorProgram(fixture());assert.equal(evaluateDirectorProgram(p,720).records.find(r=>r.id==='label').role,'REQUIRED_VISIBLE_SAFE');
 assert.equal(evaluateDirectorProgram(p,741).records.find(r=>r.id==='label').role,'CONTEXT_CULL');
 assert.equal(evaluateDirectorProgram(p,800).records.find(r=>r.id==='area').role,'AREA_VIEWPORT_CLIP');
});
test('missing geographic bindings and null data are rejected before any draw',()=>{
 for(const change of [x=>x.locations[0].anchor=null,x=>x.lines[0].geometry=null,x=>x.events[0].locationId='absent',x=>x.metrics=[]]){const p=fixture();change(p);assert.throws(()=>compileDirectorProgram(p));}
});
test('unknown fields including irrelevant event-type fields are never silently ignored',()=>{
 for(const change of [x=>x.hiddenRenderer='other',x=>x.events[0].areaId='land',x=>x.events[0].style.fov=60,x=>x.locations[0].source.trustMe=true]){const p=fixture();change(p);assert.throws(()=>compileDirectorProgram(p),/UNKNOWN_FIELD/);}
});
test('false source verification cannot be promoted by choosing a production data mode',()=>{
 const p=fixture();p.dataMode='VERIFIED_GEOGRAPHY';assert.throws(()=>compileDirectorProgram(p),/SOURCE_VERIFICATION/);
});
test('observed metric text is accepted separately from verified geographic data',()=>{
 const p=fixture();p.dataMode='VERIFIED_GEOGRAPHY';for(const record of [...p.locations,...p.areas,...p.lines])record.source={...source,verification:'VERIFIED'};
 p.metrics[0].source={...source,verification:'OBSERVED_REFERENCE_TEXT'};
 assert.equal(compileDirectorProgram(p).data.metrics[0].source.verification,'OBSERVED_REFERENCE_TEXT');
});
test('short event windows, reversed time, unsafe geometry and wrapped edges fail explicitly',()=>{
 for(const change of [x=>x.events[2].holdUntilFrame=714,x=>x.events[4].revealFrames=100,x=>x.frameRange=[820,700],x=>x.lines[0].geometry.coordinates=[[179,0],[-179,1]],x=>x.areas[0].geometry.coordinates[0][0]=[181,0]]){const p=fixture();change(p);assert.throws(()=>compileDirectorProgram(p));}
});
test('review jobs remain individually bounded with honest contiguous global windows',()=>{
 for(const change of [x=>x.windows[1].frameRange[0]++,x=>x.windows[1].frameRange[0]--,x=>x.windows.pop(),x=>x.windows[1].id=x.windows[0].id]){const p=fixture();change(p);assert.throws(()=>compileDirectorProgram(p));}
 const p=compileDirectorProgram(fixture());assert.throws(()=>programWindowFrame(p,'first',60));assert.throws(()=>evaluateDirectorProgram(p,820));
});
test('the metric keeps its configured reading deadline and final hold',()=>{
 const p=compileDirectorProgram(fixture());for(let f=794;f<820;f++)assert.ok(evaluateDirectorProgram(p,f).records.find(r=>r.id==='metric').fullyReadable);
 const input=fixture();input.events.at(-1).fullyReadableFrame=780;assert.throws(()=>compileDirectorProgram(input),/TEXT_READ_DEADLINE/);
});
test('source detail and uncertainty metadata are preserved but nonfinite values are rejected',()=>{
 const input=fixture();input.locations[0].source={...input.locations[0].source,sourceURL:'https://example.invalid/synthetic-source',license:'CC0-1.0',date:'2026-10-22',crs:'EPSG:4326',nativeResolution:{status:'SYNTHETIC_NOT_MEASURED'},uncertainty:{status:'NOT_REAL_GEOGRAPHY'}};
 assert.deepEqual(compileDirectorProgram(input).data.locations[0].source,input.locations[0].source);
 const bad=fixture();bad.locations[0].source={...bad.locations[0].source,uncertainty:{meters:Infinity}};
 assert.throws(()=>compileDirectorProgram(bad),/SOURCE_METADATA_FINITE/);
});
test('required range cannot extend before or after its active event interval',()=>{
 for(const range of [[700,740],[712,821],[720,710]]){const input=fixture();input.events[2].requiredRange=range;assert.throws(()=>compileDirectorProgram(input),/REQUIRED_RANGE/);}
});
test('label pin must be active throughout the complete label interval',()=>{
 for(const change of [x=>x.events[0].startFrame=714,x=>x.events[0].holdUntilFrame=800]){const input=fixture();change(input);assert.throws(()=>compileDirectorProgram(input),/LABEL_PIN_ACTIVE_INTERVAL/);}
});
test('area-specific ignored direction fields and excessive glyph resources are rejected',()=>{
 const area=fixture();area.areas[0].direction='REVERSE';assert.throws(()=>compileDirectorProgram(area),/UNKNOWN_FIELD_areas/);
 const many=fixture();for(let i=0;i<140;i++)many.events.push({...many.events[2],id:'label-'+i});assert.throws(()=>compileDirectorProgram(many),/TOTAL_GLYPH_RESOURCE_CAPACITY/);
});
test('line context culling is explicitly unsupported rather than accepted then rejected by the native line pass',()=>{
 const input=fixture();input.events.find(e=>e.type==='LINE').role='CONTEXT_CULL';
 assert.throws(()=>compileDirectorProgram(input),/UNSUPPORTED_LINE_CONTEXT_CULL/);
});
test('area/line required ranges cannot claim a visibility behavior their fixed-role consumers do not support',()=>{
 for(const type of ['AREA','LINE']){const input=fixture(),event=input.events.find(e=>e.type===type);event.requiredRange=[event.startFrame,event.holdUntilFrame];assert.throws(()=>compileDirectorProgram(input),/UNSUPPORTED_REQUIRED_RANGE_FOR_AREA_LINE/);}
});
test('pin artwork scales uniformly and cannot silently turn its circular hole into an ellipse',()=>{
 const invalid=fixture();invalid.events[0].style.widthPx=100;invalid.events[0].style.heightPx=400;assert.throws(()=>compileDirectorProgram(invalid),/PIN_UNIFORM_ART_ASPECT_REQUIRED/);
 const valid=fixture();valid.events[0].style.widthPx/=2;valid.events[0].style.heightPx/=2;assert.equal(compileDirectorProgram(valid).events[0].style.widthPx,24.5);
});
test('known pinned-font text is supported while unmapped glyphs are explicit unsupported input',()=>{
 const input=fixture();input.locations[0].label='세우타';assert.ok(compileDirectorProgram(input));
 input.locations[0].label='\u{1FAE0}';assert.throws(()=>compileDirectorProgram(input),/FONT_CODEPOINT_UNSUPPORTED/);
});
test('font cmap evidence is bound to the actual preserved font bytes',async()=>{
 const {PINNED_FONT_COVERAGE}=await import('../font_coverage.mjs'),fs=await import('node:fs');
 const bytes=fs.readFileSync(new URL('../../../web/fonts/NotoSansCJKkr-Bold.otf',import.meta.url));
 assert.equal(createHash('sha256').update(bytes).digest('hex'),PINNED_FONT_COVERAGE.fontSHA256);
});
