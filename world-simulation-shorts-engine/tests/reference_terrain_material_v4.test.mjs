import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_REFERENCE_TERRAIN_PROFILE_V4,validateReferenceTerrainProfileV4}
 from '../web/map_infographic_v1/reference_terrain_material_v4.mjs';

test('new terrain profile has no elevation or synthetic texture escape hatch',()=>{
 for(const input of [{heightFromRGB:true},{generateRelief:true},{ridgeNoise:1},{physicalNormals:true}])
  assert.throws(()=>validateReferenceTerrainProfileV4(input),/UNKNOWN_PROFILE_FIELD/);
});

test('relief and warm faces stay within the explicit artistic material contract',()=>{
 for(const input of [{sourceChromaRetention:2},{warmHighlightStrength:.9},{landContrast:5},
  {landTint:[1,2,3]},{warmHighlightColor:[-1,0,0]}])
  assert.throws(()=>validateReferenceTerrainProfileV4(input));
 assert.doesNotThrow(()=>validateReferenceTerrainProfileV4({warmHighlightStrength:0,bakedShadeLocalContrast:0}));
 assert.equal(DEFAULT_REFERENCE_TERRAIN_PROFILE_V4.oceanProfile.microStrength,0);
});

test('copying and validating a scene cannot mutate its shared material defaults',()=>{
 const p=validateReferenceTerrainProfileV4();
 p.landTint[0]=1;p.oceanProfile.nearshoreTint[0]=1;
 assert.notEqual(p.landTint[0],DEFAULT_REFERENCE_TERRAIN_PROFILE_V4.landTint[0]);
 assert.notEqual(p.oceanProfile.nearshoreTint[0],DEFAULT_REFERENCE_TERRAIN_PROFILE_V4.oceanProfile.nearshoreTint[0]);
 assert.deepEqual(validateReferenceTerrainProfileV4(),structuredClone(DEFAULT_REFERENCE_TERRAIN_PROFILE_V4));
});
