import test from 'node:test';
import assert from 'node:assert/strict';
import {referenceV2Profile,validateReferenceParameters,REFERENCE_PARAMETER_CONTRACT} from '../ref2_profiles.mjs';

test('missing V2 profile selects all-disabled old F path, never implicit production',()=>{
 const p=referenceV2Profile();assert.equal(p.variant,'A');
 for(const group of ['territory','source','frontier','units','camera'])assert.equal(p[group].enabled,false);
 assert.equal(p.source.registerDomainCoverage,false);assert.equal(p.profileId,'REFERENCE_VISUAL_MASTER_V2_A');
 assert.equal(p.qualityApproved,false);assert.equal(p.hardwareVerified,false);assert.equal(p.finalPromotion,false);
});
test('A through F have independent explicit feature gates and correct camera comparison groups',()=>{
 const expected={A:[0,0,0,0,0],B:[1,0,0,0,0],C:[0,1,0,0,0],D:[0,0,1,1,0],E:[0,0,0,0,1],F:[1,1,1,1,1]};
 for(const [letter,flags]of Object.entries(expected)){
  const p=referenceV2Profile(letter);
  assert.deepEqual(['territory','source','frontier','units','camera'].map(k=>+p[k].enabled),flags);
  assert.equal(p.source.registerDomainCoverage,['D','F'].includes(letter));
 }
 assert.deepEqual(referenceV2Profile('E').camera,referenceV2Profile('F').camera);
 assert.deepEqual(referenceV2Profile('D').units,referenceV2Profile('F').units);
});
test('ten requested controls distinguish eight supported visual controls from unchanged event timing and hold',()=>{
 const p=referenceV2Profile('F'),names=['territoryColorStrength','territoryTransitionTiming','frontierGlowIntensity',
  'frontierGlowWidth','terrainContrast','astraEdgeBlending','unitMarkerScale','cameraFocusPriority','cameraMotionSmoothing','eventHoldDuration'];
 assert.equal(names.filter(k=>p.capabilities[k]).length,8);
 assert.equal(REFERENCE_PARAMETER_CONTRACT.territoryTransitionTiming.supported,false);
 assert.equal(REFERENCE_PARAMETER_CONTRACT.eventHoldDurationFrames.supported,false);
 for(const input of [{territoryTransitionTiming:'SLOW'},{eventHoldDurationFrames:10},{eventHoldDurationFrames:false},
  {territoryTransitionTiming:null},{eventHoldDurationFrames:null},{cameraReadHoldFrames:null}])
  assert.throws(()=>referenceV2Profile('F',input));
 assert.equal(p.parameters.eventHoldDurationFrames,0);assert.equal(p.camera.holdDurationFrames,10);
 assert.equal(p.comparison.scenarioTimeWarp,false);
});
test('bounded profile controls reach the actual factory groups without renderer API changes',()=>{
 const input={territoryColorStrength:.87,gainBrightness:1.2,frontierGlowIntensity:.9,frontierGlowWidth:2,
  terrainContrast:1.3,astraEdgeBlending:64,unitMarkerScale:1.2,cameraFocusPriority:.5,cameraMotionSmoothing:.9,
  cameraReadHoldFrames:12},before=JSON.stringify(input),p=referenceV2Profile('F',input);
 assert.equal(p.territory.gainedAlpha,.87);assert.equal(p.territory.gainBrightness,1.2);
 assert.equal(p.frontier.frontierIntensity,.9);assert.equal(p.frontier.frontierWidth,2);
 assert.equal(p.source.terrainLocalContrast,1.3);assert.equal(p.source.screenFeatherPixels,64);
 assert.equal(p.units.markerScale,1.2);assert.equal(p.camera.focusPriority,.5);
 assert.equal(p.camera.cameraSmoothing,.9);assert.equal(p.camera.holdDurationFrames,12);
 assert.equal(JSON.stringify(input),before);assert.ok(Object.isFrozen(p));assert.ok(Object.isFrozen(p.frontier.outerGoldColor));
});
test('unknown, nonfinite and unsafe controls fail explicitly rather than bypassing original limits',()=>{
 for(const input of [{country:'any'},{forceAllow:true},{frontierGlowWidth:3},{unitMarkerScale:1.3},
  {terrainContrast:Infinity},{astraEdgeBlending:0},{oceanExposure:NaN},{cameraFocusPriority:'1'},
  {cameraReadHoldFrames:8},{outerGoldSupport:2},{territoryColorStrength:.5}])assert.throws(()=>validateReferenceParameters(input));
 for(const letter of ['G','f',null,1])assert.throws(()=>referenceV2Profile(letter));
});
test('disabling only outer gold removes its coverage dependency while retaining original white-front extension',()=>{
 const p=referenceV2Profile('D',{outerGoldIntensity:0});assert.equal(p.frontier.enabled,true);
 assert.equal(p.source.enabled,false);assert.equal(p.source.registerDomainCoverage,false);
 assert.equal(p.frontier.outerGoldIntensity,0);
});
test('production candidate composition remains source before territory before original front before national art',()=>{
 const p=referenceV2Profile('F'),order=p.compositionOrder;
 assert.ok(order.indexOf('OPTIONAL_SUPPORTED_SOURCE_GRADE')<order.indexOf('UNCHANGED_OWNERSHIP_MASK_OPTIONAL_GAIN_STYLE'));
 assert.ok(order.indexOf('UNCHANGED_OWNERSHIP_MASK_OPTIONAL_GAIN_STYLE')<order.indexOf('ORIGINAL_TERRAIN_LIGHTING_AND_MOVING_WHITE_FRONT'));
 assert.ok(order.indexOf('OPTIONAL_ACTUAL_DOMAIN_OUTER_GOLD')<order.indexOf('ORIGINAL_NATIONAL_ARTWORK_OPTIONAL_SAFE_SIZE'));
 assert.equal(p.parameters.cameraMotionSmoothing,.8);assert.equal(p.parameters.astraEdgeBlending,48);
});
