import test from 'node:test';
import assert from 'node:assert/strict';
import {GEOGRAPHIC_OCCLUSION_POLICY,classifyEventLineProtection,EVENT_MARKER_OCCLUSION_CAPACITY}
 from '../web/map_infographic_v1/event_occlusion_policy_v1.mjs';

test('only explicitly typed geographic Markers permit raster occlusion',()=>{
 const original={protectedBoxes:[[1,2,3,4]],protectedGraphics:[
  {kind:'MARKER',box:[20,30,40,50]},{kind:'TEXT',box:[60,70,80,90]},{kind:'PANEL',box:[100,110,120,130]}]};
 const before=structuredClone(original),result=classifyEventLineProtection(original);
 assert.deepEqual(result.markerOcclusions,[[20,30,40,50]]);
 assert.deepEqual(result.strictBoxes,[[1,2,3,4],[60,70,80,90],[100,110,120,130]]);
 assert.deepEqual(original,before);assert(Object.isFrozen(result.markerOcclusions[0]));
 assert.deepEqual(GEOGRAPHIC_OCCLUSION_POLICY.allowedPair,['EVENT_GEOGRAPHIC_LINE','PROTECTED_GEOGRAPHIC_MARKER']);
 assert.equal(GEOGRAPHIC_OCCLUSION_POLICY.progress,'UNINTERRUPTED_PROJECTED_ARC_LENGTH');
});
test('ambiguous kinds, malformed boxes and excess Marker uniforms fail closed',()=>{
 for(const input of [{protectedGraphics:[{kind:'TITLE',box:[1,2,3,4]}]},
  {protectedGraphics:[{box:[1,2,3,4]}]}, {protectedGraphics:[{kind:'MARKER',box:[1,2,1,4]}]},
  {protectedBoxes:[[1,2,NaN,4]]},{protectedGraphics:null}])assert.throws(()=>classifyEventLineProtection(input),/EVENT_/);
 assert.throws(()=>classifyEventLineProtection({protectedGraphics:Array.from({length:EVENT_MARKER_OCCLUSION_CAPACITY+1},
  ()=>({kind:'MARKER',box:[1,2,3,4]}))}),/CAPACITY_EXCEEDED/);
});
