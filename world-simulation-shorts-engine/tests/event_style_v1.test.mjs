import test from 'node:test';
import assert from 'node:assert/strict';
import {selectEventLineStyle,evaluateEventLineCandidates,relativeLuminanceSrgb,contrastRatioSrgb,oklabSrgb,
 EVENT_LINE_COLOR_CANDIDATES_SRGB} from '../web/map_infographic_v1/event_style_v1.mjs';

const theme=()=>({primary:[.94,.57,.12],secondary:[.14,.44,.45],primaryWidth:5,secondaryWidth:2.5,
 primaryCoreColor:[1,.94,.68,.86],secondaryCoreColor:[.43,.87,.82,.68],glowRadius:1.7,glowGain:.1,
 glowColor:[.88,.52,.07,1]});
const goldSamples=[[.68,.56,.20],[.72,.60,.22],[.60,.51,.19],[.73,.63,.31]];
const tealSamples=[[.14,.61,.60],[.16,.65,.62],[.18,.58,.55],[.19,.67,.63]];

test('gold material selects a measured cyan/teal accent and preserves native inputs',()=>{
 const t=theme(),samples=structuredClone(goldSamples),before=structuredClone({t,samples});
 const style=selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:samples});
 assert.equal(style.selection.selectedFamily,'CYAN_TEAL');
 assert.equal(style.selection.sampleSource,'ACTUAL_NATIVE_FRAMEBUFFER_SRGB');
 assert.deepEqual({t,samples},before);
 assert.equal(style.width,7);assert.equal(style.selection.nativeBaseWidth,5);
 assert.deepEqual(style.glowColor.slice(0,3),style.coreColor.slice(0,3));
 assert(style.glowRadius<=t.glowRadius);assert(style.glowGain<=t.glowGain);
 assert.equal(style.selection.coreAlpha,style.coreColor[3]);
 assert.equal(style.selection.centerCompositeAlpha,style.coreColor[3]+style.glowGain*(1-style.coreColor[3]));
 assert.equal(style.selection.alpha,style.selection.centerCompositeAlpha);
 assert.deepEqual(style.selection.backgroundSamples,samples);
 const best=style.selection.candidates.reduce((a,b)=>a.score>b.score?a:b);
 assert.equal(style.selection.selectedName,best.name);
});
test('opposed primary hue and actual samples automatically select a different family',()=>{
 const warm=selectEventLineStyle({role:'PRIMARY',theme:theme(),backgroundSamples:goldSamples});
 const t=theme();t.primary=[.08,.85,.82];
 const cool=selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:tealSamples});
 assert.notEqual(warm.selection.selectedName,cool.selection.selectedName);
 assert.notEqual(cool.selection.selectedFamily,'CYAN_TEAL');
 assert.equal(cool.selection.sampleCount,tealSamples.length);
});
test('sRGB relative luminance uses the standard transfer exactly once',()=>{
 assert.equal(relativeLuminanceSrgb([0,0,0]),0);
 assert.equal(relativeLuminanceSrgb([1,1,1]),1);
 assert(Math.abs(relativeLuminanceSrgb([.5,.5,.5])-.21404114048223255)<1e-12);
 assert.equal(contrastRatioSrgb([1,1,1],[0,0,0]),21);
 assert(Math.abs(oklabSrgb([1,1,1])[0]-1)<1e-7);
});
test('actual sample differences influence selection and produce reproducible measurements',()=>{
 const t=theme(),a=selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:goldSamples});
 const b=selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:tealSamples});
 assert.notDeepEqual(a.selection.candidates.map(item=>item.score),b.selection.candidates.map(item=>item.score));
 assert.deepEqual(a,selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:goldSamples}));
 for(const row of a.selection.candidates){
  assert(Number.isFinite(row.score));assert(row.luminanceContrast.minimum>=1);
  assert(row.colorDistance.minimum>=0);assert(row.chromaticDistance.minimum>=0);
 }
});
test('width increment is positive but bounded by two pixels and forty percent',()=>{
 for(const base of [.5,1,2.5,5,8,15]){
  const t=theme();t.primaryWidth=base;
  const style=selectEventLineStyle({role:'PRIMARY',theme:t});
  assert(style.width>base);assert(style.width<=base+2);assert(style.width<=base*1.4+1e-12);
  assert.equal(style.selection.sampleSource,'PRIMARY_MATERIAL_SRGB_FALLBACK');
 }
 const secondary=selectEventLineStyle({role:'SECONDARY',theme:theme()});assert.equal(secondary.width,3.5);
});
test('output colors are detached from inputs and the reusable palette',()=>{
 const t=theme(),before=structuredClone(t),paletteBefore=structuredClone(EVENT_LINE_COLOR_CANDIDATES_SRGB);
 const style=selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:goldSamples});
 style.coreColor[0]=0;style.selection.primaryMaterialColor[0]=0;style.selection.candidates[0].rgb[0]=0;
 style.selection.backgroundSamples[0][0]=0;
 assert.deepEqual(t,before);assert.deepEqual(EVENT_LINE_COLOR_CANDIDATES_SRGB,paletteBefore);
 assert(Object.isFrozen(EVENT_LINE_COLOR_CANDIDATES_SRGB));
 assert(Object.isFrozen(EVENT_LINE_COLOR_CANDIDATES_SRGB[0].rgb));
});
test('invalid roles, colors, backgrounds and native style tokens fail without a fallback',()=>{
 const t=theme();
 assert.throws(()=>selectEventLineStyle({role:'UNKNOWN',theme:t}),/UNKNOWN_STYLE_ROLE/);
 for(const width of [0,-1,NaN,Infinity])assert.throws(()=>selectEventLineStyle({role:'PRIMARY',theme:{...t,primaryWidth:width}}),/STYLE_TOKENS/);
 for(const color of [[256,0,0],[NaN,0,0],[0,0],null])
  assert.throws(()=>evaluateEventLineCandidates({primaryMaterialColor:color,backgroundSamples:goldSamples}),/SRGB_REQUIRED/);
 for(const samples of [[],[[256,0,0]],null])
  assert.throws(()=>selectEventLineStyle({role:'PRIMARY',theme:t,backgroundSamples:samples}),/SAMPLES_REQUIRED|SRGB_REQUIRED/);
});
