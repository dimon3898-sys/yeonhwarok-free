import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_REFERENCE_OCEAN_PROFILE_V4,REFERENCE_OCEAN_GLSL_V4,REFERENCE_OCEAN_EVIDENCE_V4,
 buildReferenceOceanGlslV4,validateReferenceOceanProfileV4} from '../web/map_infographic_v1/reference_ocean_material_v4.mjs';

test('the V4 ocean cannot re-enable the removed moving stripe/glint effect',()=>{
 for(const input of [{microStrength:.001},{glintStrength:.001},{driftRadiansPerSecond:.001}])
  assert.throws(()=>validateReferenceOceanProfileV4(input),/PROCEDURAL_PATTERN_REMOVED/);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V4.proceduralWaveEnergy,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V4.frameDependentPattern,false);
});

test('source-only appearance rejects invalid source-tone and overstrong coast profiles',()=>{
 for(const input of [{sourceLumaRange:[.8,.4]},{sourceChromaRetention:1},{nearshoreMix:.9},
  {deepTint:[-1,0,0]},{randomSeed:1},{microCyclesPerDegree:19}])
  assert.throws(()=>validateReferenceOceanProfileV4(input));
 assert.doesNotThrow(()=>validateReferenceOceanProfileV4({sourceChromaRetention:0,nearshoreMix:0}));
});

test('profile copies and shader generation remain deterministic without new resources',()=>{
 const p=validateReferenceOceanProfileV4();
 assert.equal(buildReferenceOceanGlslV4(p),REFERENCE_OCEAN_GLSL_V4);
 p.deepTint[0]=1;
 assert.notEqual(p.deepTint[0],DEFAULT_REFERENCE_OCEAN_PROFILE_V4.deepTint[0]);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V4.extraTextureReads,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V4.extraTextures,0);
 assert.equal(REFERENCE_OCEAN_EVIDENCE_V4.coastlineChanged,false);
});
