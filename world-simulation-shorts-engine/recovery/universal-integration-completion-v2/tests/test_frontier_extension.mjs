/** CPU-only adapters: injected draw owners never create a WebGL context. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {registerHooks} from 'node:module';
import {normalizeFrontierProfile,compileSuppliedFrontMotion,evaluateSuppliedFrontMotion,
 bindFrontierProductionFactory} from '../frontier_extension.mjs';
const line=(latitude=0,id='front-a')=>({id,geometry:{type:'LineString',coordinates:[[-40,latitude],[-39,latitude+1]]},
 alpha:.8,revealFraction:1,linePrimitive:{existingOwner:true}});
const observations=[0,1,2,2,2].map((latitude,frame)=>({frame,fronts:[line(latitude)]})),
 profile={settledStrength:.2,settleFrames:2},
 plan=()=>compileSuppliedFrontMotion({observations,totalFrames:5,profile});
function factory(calls){return options=>({evidence:{version:'CPU_DRAW_OWNER'},draw(input){calls.push({options,input});return{fronts:input.controls.fronts,productionVisual:{unchanged:true}};},dispose(){calls.push('dispose');}});}
const input=front=>({controls:{frame:4,fronts:[front],areas:[{id:'owned-area'}],impacts:[],propagations:[]},
 project:point=>point,safeArea:[12,20,1068,1900],protectedGraphics:[{kind:'MARKER',box:[30,40,60,70]}],
 boundarySegments:[{a:[10,30],b:[20,50],radiusPx:3}],primaryMaterialColor:[.1,.2,.3]});

test('strict bounded presentation profile rejects unsupported or unsafe values',()=>{
 assert.equal(normalizeFrontierProfile().profile,'AUTHORED_FRONT_MOTION_V2');
 for(const value of [{terrainLighting:true},{settleFrames:0},{settleFrames:121},{settledStrength:1.1},{enabled:'true'}])
  assert.throws(()=>normalizeFrontierProfile(value),/COMPLETION_FRONTIER_PROFILE/);
});
test('dense exact source observations compile without inferred frames or coordinates',()=>{
 const source=JSON.stringify(observations),value=plan();
 assert.deepEqual(value.fronts['front-a'].changeFrames,[1,2]);
 assert.equal(value.interpolation,'NONE');assert.equal(value.cameraMotionExcluded,true);
 assert.equal(JSON.stringify(observations),source);
 assert.throws(()=>compileSuppliedFrontMotion({observations:observations.slice(1),totalFrames:5}),/DENSE_SOURCE_FRAMES/);
 assert.throws(()=>compileSuppliedFrontMotion({observations:[{frame:2,fronts:[]}],totalFrames:1}),/EXACT_FRAME/);
});
test('same supplied geography determines moving then naturally settled light',()=>{
 const value=plan();
 assert.equal(evaluateSuppliedFrontMotion(value,2,line(2)).strength,1);
 assert.ok(Math.abs(evaluateSuppliedFrontMotion(value,3,line(2)).strength-.6)<1e-12);
 assert.equal(evaluateSuppliedFrontMotion(value,4,line(2)).strength,.2);
 assert.equal(evaluateSuppliedFrontMotion(value,4,line(2)).syntheticPulse,false);
});
test('stateless evaluation preserves scene-boundary and random-seek equivalence',()=>{
 const value=plan(),full=observations.map(row=>evaluateSuppliedFrontMotion(value,row.frame,row.fronts[0]));
 for(const frame of [4,1,3,2,0,4])assert.deepEqual(evaluateSuppliedFrontMotion(value,frame,observations[frame].fronts[0]),full[frame]);
});
test('a static observed front is preserved rather than invented movement',()=>{
 const value=compileSuppliedFrontMotion({observations:Array.from({length:3},(_,frame)=>({frame,fronts:[line(4)]})),totalFrames:3});
 const state=evaluateSuppliedFrontMotion(value,2,line(4));
 assert.equal(state.strength,1);assert.equal(state.measuredComparableChange,false);
});
test('topology changes are not falsely measured as corresponding-point motion',()=>{
 const changed=line();changed.geometry.coordinates.push([-38,3]);
 const value=compileSuppliedFrontMotion({observations:[{frame:0,fronts:[line()]},{frame:1,fronts:[changed]}],totalFrames:2});
 const state=evaluateSuppliedFrontMotion(value,1,changed);
 assert.equal(state.sourceTopologyChanged,true);assert.equal(state.strength,1);
 assert.equal(state.measuredComparableChange,false);
});
test('only the exact supplied front can consume its compiled motion envelope',()=>{
 assert.throws(()=>evaluateSuppliedFrontMotion(plan(),4,line(9)),/GEOMETRY_BINDING_MISMATCH/);
 assert.throws(()=>evaluateSuppliedFrontMotion(plan(),4,line(2,'invented-front')),/GEOMETRY_BINDING_MISMATCH/);
 const duplicate=[{frame:0,fronts:[line(),line()]}];
 assert.throws(()=>compileSuppliedFrontMotion({observations:duplicate,totalFrames:1}),/DUPLICATE_ID/);
});
test('actual factory is reused and only front alpha changes; masks and polygons are identical',()=>{
 const calls=[],canvas={},owner=bindFrontierProductionFactory(factory(calls),{profile,motionPlan:plan(),
  readFrameContext:target=>{assert.equal(target,canvas);return{frame:4};}})({canvas,profile:{existing:true}}),
  current=input(line(2)),before=JSON.stringify(current),result=owner.draw(current),forward=calls[0].input;
 assert.equal(forward.controls.areas,current.controls.areas);
 for(const key of ['safeArea','protectedGraphics','boundarySegments','project'])assert.equal(forward[key],current[key]);
 assert.equal(forward.controls.fronts[0].geometry,current.controls.fronts[0].geometry);
 assert.equal(forward.controls.fronts[0].linePrimitive,current.controls.fronts[0].linePrimitive);
 assert.equal(forward.controls.fronts[0].alpha,.8*.2);
 assert.equal(JSON.stringify(current),before);
 assert.equal(result.productionVisual.unchanged,true);
 assert.equal(result.completionFrontier.actualSuppliedGeometryRetained,true);
 assert.equal(result.completionFrontier.terrainLightingConnected,false);
 owner.dispose();assert.equal(calls.at(-1),'dispose');
});
test('missing motion evidence preserves the parent draw and reports a blocker',()=>{
 const calls=[],owner=bindFrontierProductionFactory(factory(calls))({canvas:{}}),current=input(line()),result=owner.draw(current);
 assert.equal(calls[0].input.controls.fronts[0],current.controls.fronts[0]);
 assert.equal(result.completionFrontier.motionConnected,false);
 assert.equal(result.completionFrontier.motionBlocker,'COMPLETION_FRONTIER_MOTION_SOURCE_NOT_CONNECTED');
});
test('disabled extension returns the exact original owner and allocates no extra pass',()=>{
 const owner={draw(){},evidence:{preserved:true}},wrapped=bindFrontierProductionFactory(()=>owner,{profile:{enabled:false}})({canvas:{}});
 assert.equal(wrapped,owner);
});
test('other hemispheres and longitude/date-line coordinates need no country branch',()=>{
 const dates=[179,-179,-178].map((longitude,frame)=>({frame,fronts:[{...line(-45),geometry:{type:'LineString',coordinates:[[longitude,-45],[longitude,-44]]}}]}));
 const value=compileSuppliedFrontMotion({observations:dates,totalFrames:3});
 assert.equal(evaluateSuppliedFrontMotion(value,2,dates[2].fronts[0]).strength,1);
 assert.equal(evaluateSuppliedFrontMotion(value,2,dates[2].fronts[0]).projectionMotionExcluded,true);
});
test('reserved identifiers cannot modify prototypes in source planning',()=>{
 const value=compileSuppliedFrontMotion({observations:[{frame:0,fronts:[line(1,'__proto__')]}],totalFrames:1});
 assert.equal(evaluateSuppliedFrontMotion(value,0,line(1,'__proto__')).strength,1);
 assert.equal({}.geometryRuns,undefined);
});
test('the preserved production factory consumes the wrapper output (CPU injected GPU boundary)',async()=>{
 // Execute the unchanged real production factory. Replace only its deepest
 // WebGL allocator with an explicit CPU observation fixture, never a renderer.
 const mockURL='data:text/javascript,'+encodeURIComponent(`export function createAreaOverlayPass(options){return {evidence:{cpuFixture:true},draw(input){return {areas:input.controls.areas,fronts:input.controls.fronts,style:options.style};},dispose(){}};}`),
  visual=new URL('../../universal-production-v3/production_visual_profile.mjs',import.meta.url).href,
  original=new URL('../../universal-production-v3/production_area_pass.mjs',import.meta.url).href+'?completion-frontier-cpu';
 const hook=registerHooks({resolve(specifier,context,next){
  if(specifier==='/modules/area_overlay_pass_v3.mjs')return{url:mockURL,shortCircuit:true};
  if(specifier==='/production-v3/production_visual_profile.mjs')return{url:visual,shortCircuit:true};
  return next(specifier,context);
 }});
 let imported;try{imported=await import(original);}finally{hook.deregister();}
 const {normalizeProductionVisualProfile}=await import(visual),p=normalizeProductionVisualProfile(),
  owner=bindFrontierProductionFactory(imported.createProductionAreaPass,{profile,motionPlan:plan()})({canvas:{},profile:p,
   bindings:[{areaId:'owned-area',factionId:'a',sourceId:'source-a',color:[.7,.2,.4]}]}),
  result=owner.draw(input(line(2)));
 assert.equal(result.productionVisual.originalAreaEngine,true);
 assert.equal(result.productionVisual.noComplementOwnership,true);
 assert.equal(result.style.FRONT.width,p.frontCoreWidthPixels);
 assert.equal(result.fronts[0].alpha,.8*.2);
 assert.equal(result.completionFrontier.actualConsumer,'AREA_OVERLAY_PASS_V3.drawLine -> contour');
 owner.dispose();
});
