/** CPU material/classifier and explicit mock-factory checks, never GPU pixels. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {registerHooks} from 'node:module';
import {applyReferenceTerritoryStyle,describeReferenceGainStyle,validateReferenceTerritoryProfile}
 from '../gain_style_core.mjs';
import {applyQualityTerritoryStyle,compositeTerritorySample}
 from '../../visual-quality-upgrade-v1/territory_style_core.mjs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame,classifyControlPoint}
 from '../../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
const saved=JSON.parse(await readFile(new URL('../../moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json',import.meta.url))),
 enabled={enabled:true,gainBrightness:1.12,gainedAlpha:.84},oldF=applyQualityTerritoryStyle(saved.style);
const rgb=rgba=>rgba.slice(0,3),luma=color=>color[0]*.2126+color[1]*.7152+color[2]*.0722;

const synthetic={version:'TERRITORY_CONTROL_INTENT_V1',semantic_mode:'REFERENCE_VISUAL_STUDY',
 source:{source_type:'SYNTHETIC_TEST',source_reference:'CUMULATIVE_REAL_CLASSIFIER',verification_status:'TEST_ONLY'},
 domain:[{id:'ANY',geometry:{type:'Polygon',coordinates:[[[-2,-2],[2,-2],[2,2],[-2,2],[-2,-2]]]}}],
 factions:{winner:{id:'A'},loser:{id:'B'}},longitudinal_knots:[-2,2],base_boundary_latitudes:[-1,-1],
 boundary_keyframes:[{frame:0,latitudes:[-1,-1]},{frame:19,latitudes:[1,1]}],advance_direction:'POSITIVE_LATITUDE',
 start_frame:0,total_frames:20,fps:30,interpolation:'LINEAR'};
const assignedColor=(controls,point,style)=>{
 const actual=classifyControlPoint(controls,point);
 return actual.region==='WINNER_GAINED'?style.gainedWinningColor:actual.region==='WINNER_EXISTING'?style.existingWinningColor:
  actual.region==='LOSER'?style.losingColor:null;
};

test('default disabled is exact old F style; unsupported age/timing/geometry controls fail',()=>{
 assert.deepEqual(applyReferenceTerritoryStyle(oldF),oldF);
 for(const value of [{enabled:'yes'},{gainBrightness:.9},{gainBrightness:1.3},{gainBrightness:NaN},
  {gainedAlpha:1},{gainedAlpha:-.1},{settleDuration:2},{gainAge:1},{bandWidth:20},{frontLine:true},
  {country:'fixture'},{hue:'violet'},{speed:2}])assert.throws(()=>validateReferenceTerritoryProfile(value));
});

test('enabled gain changes only gained RGBA and style name, never held/loser/interface/source input',()=>{
 const before=structuredClone(oldF),after=applyReferenceTerritoryStyle(oldF,enabled);
 assert.deepEqual(oldF,before);
 for(const field of ['losingColor','existingWinningColor','interfaceColor','interfaceWidthPixels','sharedDomainBoundary'])
  assert.deepEqual(after[field],before[field]);
 assert.notDeepEqual(after.gainedWinningColor,after.existingWinningColor);
 assert.equal(after.gainedWinningColor[3],.84);
 const scale=after.gainedWinningColor[2]/before.gainedWinningColor[2];
 for(let channel=0;channel<3;channel++)assert.ok(Math.abs(after.gainedWinningColor[channel]-before.gainedWinningColor[channel]*scale)<1e-12);
 assert.ok(luma(after.gainedWinningColor)>luma(before.gainedWinningColor));
 assert.ok(1-after.gainedWinningColor[3]>=.15);
});

test('actual original classifier changes a gaining point but preserves held/losing/outside points',()=>{
 const plan=compileTerritoryControlPlan(synthetic),style=applyReferenceTerritoryStyle(oldF,enabled),
  first=evaluateTerritoryControlFrame(plan,0),last=evaluateTerritoryControlFrame(plan,19);
 assert.equal(classifyControlPoint(first,[0,.5]).region,'LOSER');
 assert.equal(classifyControlPoint(last,[0,.5]).region,'WINNER_GAINED');
 assert.deepEqual(assignedColor(first,[0,.5],style),oldF.losingColor);
 assert.deepEqual(assignedColor(last,[0,.5],style),style.gainedWinningColor);
 for(const point of [[0,-1.5],[0,1.5],[3,0]])
  assert.deepEqual(assignedColor(last,point,style),assignedColor(last,point,oldF));
 assert.equal(classifyControlPoint(last,[0,-1.5]).region,'WINNER_EXISTING');
 assert.equal(classifyControlPoint(last,[3,0]).newlyGained,false);
});

test('all 150 saved original boundaries, geometry bindings, ownership and timing remain exact',()=>{
 const input=JSON.stringify(saved),plan=compileTerritoryControlPlan(saved.controlIntent),
  baseline=Array.from({length:150},(_,frame)=>evaluateTerritoryControlFrame(plan,frame)),
  altered=structuredClone(saved);
 altered.style=applyReferenceTerritoryStyle(altered.style,enabled);
 const unchanged=compileTerritoryControlPlan(altered.controlIntent);
 for(let frame=0;frame<150;frame++){
  const actual=evaluateTerritoryControlFrame(unchanged,frame);
  assert.deepEqual(actual,baseline[frame]);
  for(const longitude of actual.longitudinalKnots){
   const boundary=actual.boundaryLatitudes[actual.longitudinalKnots.indexOf(longitude)];
   for(const offset of [-.1,0,.1])assert.deepEqual(classifyControlPoint(actual,[longitude,boundary+offset]),
    classifyControlPoint(baseline[frame],[longitude,boundary+offset]));
  }
 }
 assert.equal(JSON.stringify(saved),input);
});

test('arbitrary red/green/blue/teal source palettes keep channel ratios and contain no fixture color choice',()=>{
 for(const color of [[.7,.2,.1,.5],[.1,.6,.2,.5],[.1,.2,.7,.5],[.1,.7,.7,.5]]){
  const source={profileName:'ANY_PALETTE',losingColor:[.3,.4,.1,.6],existingWinningColor:color,gainedWinningColor:color},
   before=structuredClone(source),after=applyReferenceTerritoryStyle(source,enabled),scale=after.gainedWinningColor[0]/color[0];
  assert.deepEqual(source,before);assert.deepEqual(after.existingWinningColor,color);
  for(let channel=0;channel<3;channel++)assert.ok(Math.abs(after.gainedWinningColor[channel]-color[channel]*scale)<1e-12);
  assert.ok(after.gainedWinningColor.every(channel=>channel>=0&&channel<=1));
 }
});

test('black, near-white, transparent and pre-opaque source roles are handled without invented hue or weakening',()=>{
 for(const color of [[0,0,0,.5],[1,.9,.85,.5],[.2,.3,.8,0],[.2,.3,.8,.95]]){
  const source={...oldF,gainedWinningColor:color},after=applyReferenceTerritoryStyle(source,enabled),
   evidence=describeReferenceGainStyle(source,after,enabled);
  if(color[3]===0)assert.equal(after.gainedWinningColor[3],0);
  else assert.ok(after.gainedWinningColor[3]>=color[3]);
  if(Math.max(...rgb(color))===0)assert.deepEqual(rgb(after.gainedWinningColor),[0,0,0]);
  if(Math.max(...rgb(color))>=.98)assert.deepEqual(rgb(after.gainedWinningColor),rgb(color));
  assert.equal(evidence.temporalSettleImplemented,false);assert.equal(evidence.recentGainAgeAvailable,false);
 }
});

test('varying source terrain remains visible and CPU working-channel blend gain is measurable',()=>{
 const after=applyReferenceTerritoryStyle(oldF,enabled),low=[.1,.12,.08],high=low.map(value=>value+.3),
  gainLow=compositeTerritorySample(low,after.gainedWinningColor),gainHigh=compositeTerritorySample(high,after.gainedWinningColor),
  held=compositeTerritorySample(low,after.existingWinningColor);
 for(let channel=0;channel<3;channel++)assert.ok(Math.abs(gainHigh[channel]-gainLow[channel]-.3*.16)<1e-12);
 assert.ok(luma(gainLow)>luma(held)*1.10);
 const evidence=describeReferenceGainStyle(oldF,after,enabled);
 assert.equal(evidence.gainedMaterialDistinct,true);assert.equal(evidence.timeChanged,false);
 assert.equal(evidence.gpuPixelsVerified,false);assert.deepEqual(evidence.effectiveHeldColor,oldF.existingWinningColor);
});

const oldStyleURL=new URL('../../visual-quality-upgrade-v1/territory_style_core.mjs',import.meta.url).href;
const fakeQualityURL='data:text/javascript;base64,'+Buffer.from(`
 import {applyQualityTerritoryStyle} from ${JSON.stringify(oldStyleURL)};
 export const created=[]; export let forwarded=null;
 export function setQualityTerritoryProfile(value){forwarded=value;return value;}
 export function createTerritoryControlPass(options){
  const style=applyQualityTerritoryStyle(options.style),pass={evidence:{material:style,qualityTerritory:{effectiveStyle:style}},
   cpuMock:true,draw(args){return {frame:args.controls.frame,controls:args.controls,qualityTerritory:{effectiveStyle:style}};},
   dispose(){pass.disposed=true;}};created.push(pass);return pass;
 }
 `).toString('base64');
async function adapter(id){
 const hook=registerHooks({resolve(specifier,context,nextResolve){
  if(specifier==='/quality/quality_territory.mjs?baseline')return{url:fakeQualityURL,shortCircuit:true};
  return nextResolve(specifier,context);
 }});
 try{return await import(new URL('../gain_territory.mjs?test='+id,import.meta.url));}
 finally{hook.deregister();}
}

test('disabled decorator returns exact old pass with no extra allocation, draw wrapper or evidence',async()=>{
 const extension=await adapter('disabled'),old=await import(fakeQualityURL),style=structuredClone(saved.style),
  pass=extension.createTerritoryControlPass({style});
 assert.equal(pass,old.created.at(-1));assert.equal(pass.evidence.gainTerritory,undefined);
 assert.deepEqual(pass.evidence.material,oldF);
 pass.dispose();assert.equal(pass.disposed,true);
 assert.throws(()=>extension.setReferenceTerritoryProfile(enabled));
});

test('enabled decorator selects old quality factory once and reports actual effective gain on all frames',async()=>{
 const extension=await adapter('enabled'),old=await import(fakeQualityURL);
 extension.setQualityTerritoryProfile({enabled:true,profile:{}});assert.equal(old.forwarded.enabled,true);
 extension.setReferenceTerritoryProfile(enabled);assert.throws(()=>extension.setReferenceTerritoryProfile(enabled));
 const before=old.created.length,input=structuredClone(saved.style),pass=extension.createTerritoryControlPass({style:input});
 assert.equal(old.created.length,before+1);assert.deepEqual(input,saved.style);
 assert.equal(pass.evidence.gainTerritory.actualFactorySelected,true);
 assert.equal(pass.evidence.gainTerritory.gainedMaterialDistinct,true);
 assert.deepEqual(pass.evidence.gainTerritory.effectiveHeldColor,oldF.existingWinningColor);
 const plan=compileTerritoryControlPlan(saved.controlIntent);
 for(let frame=0;frame<150;frame++){
  const controls=evaluateTerritoryControlFrame(plan,frame),actual=pass.draw({controls});
  assert.equal(actual.gainTerritory.frame,frame);
  assert.deepEqual(actual.gainTerritory.effectiveGainedColor,pass.evidence.gainTerritory.effectiveGainedColor);
  assert.equal(actual.gainTerritory.domainGeometryBinding,controls.domainGeometryBinding);
  assert.equal(actual.gainTerritory.boundaryKeyframeBinding,controls.boundaryKeyframeBinding);
  assert.equal(actual.gainTerritory.originalProtectedReservationsRetained,true);
 }
 pass.dispose();assert.equal(old.created.at(-1).disposed,true);
});
