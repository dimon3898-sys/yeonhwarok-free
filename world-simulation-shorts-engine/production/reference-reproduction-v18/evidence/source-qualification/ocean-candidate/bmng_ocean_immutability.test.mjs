import test from 'node:test';
import assert from 'node:assert/strict';
import {BMNG_PROFILE,CANDIDATE_GLSL,evaluateSourceTone} from './bmng_ocean_candidate.mjs';
import {buildReferenceOceanGlslV4} from './source/reference_ocean_material_v4.mjs';
test('every exposed nested profile array is frozen and rejects mutation',()=>{
 const initial=structuredClone(BMNG_PROFILE);
 assert.ok(Object.isFrozen(BMNG_PROFILE));
 const arrays=Object.entries(BMNG_PROFILE).filter(([,value])=>Array.isArray(value));
 assert.deepEqual(arrays.map(([key])=>key).sort(),['deepTint','midTint','nearshoreTint','sourceLumaRange'].sort());
 for(const [key,value] of arrays){
  assert.ok(Object.isFrozen(value),key);
  assert.throws(()=>{value[0]=.99;},TypeError,key+' indexed write');
  assert.throws(()=>value.push(.5),TypeError,key+' push');
  assert.throws(()=>value.splice(0,1),TypeError,key+' splice');
  assert.throws(()=>{BMNG_PROFILE[key]=[.1,.2,.3];},TypeError,key+' replacement');
 }
 assert.deepEqual(BMNG_PROFILE,initial);
});
test('failed mutation cannot desynchronize fixed GLSL and CPU profile response',()=>{
 const source=[.02,.04,.08],before=evaluateSourceTone(source),shader=CANDIDATE_GLSL;
 for(const key of ['deepTint','midTint','nearshoreTint','sourceLumaRange'])assert.throws(()=>{BMNG_PROFILE[key][0]=0;},TypeError);
 assert.deepEqual(evaluateSourceTone(source),before);
 assert.equal(buildReferenceOceanGlslV4(BMNG_PROFILE),shader);
});
