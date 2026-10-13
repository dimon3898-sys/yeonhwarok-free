import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_REFERENCE_OCEAN_PROFILE_V3,REFERENCE_OCEAN_GLSL_V3,
 REFERENCE_OCEAN_EVIDENCE_V3,buildReferenceOceanGlslV3,
 validateReferenceOceanProfileV3} from '../web/map_infographic_v1/reference_ocean_material_v3.mjs';

test('ocean visual profile rejects animated noise/flash energy outside the restrained contract',()=>{
 for(const input of [{microStrength:.2},{glintStrength:.8},{driftRadiansPerSecond:4},
  {sourceLumaRange:[.8,.5]},{deepTint:[-1,0,0]},{randomSeed:1}])
  assert.throws(()=>validateReferenceOceanProfileV3(input));
 assert.doesNotThrow(()=>validateReferenceOceanProfileV3({microStrength:0,glintStrength:0}));
});

test('profile compilation is deterministic and does not require any new geography or resource',()=>{
 assert.equal(buildReferenceOceanGlslV3(),REFERENCE_OCEAN_GLSL_V3);
 assert.equal(buildReferenceOceanGlslV3(structuredClone(DEFAULT_REFERENCE_OCEAN_PROFILE_V3)),REFERENCE_OCEAN_GLSL_V3);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V3.extraTextureReads,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V3.extraTextures,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V3.extraDrawCalls,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V3.coastlineChanged,false);
});

test('callers cannot mutate frozen default colours through validated copies',()=>{
 const p=validateReferenceOceanProfileV3();
 p.deepTint[0]=1;
 assert.notEqual(p.deepTint[0],DEFAULT_REFERENCE_OCEAN_PROFILE_V3.deepTint[0]);
 assert.equal(Object.isFrozen(DEFAULT_REFERENCE_OCEAN_PROFILE_V3.deepTint),true);
});
