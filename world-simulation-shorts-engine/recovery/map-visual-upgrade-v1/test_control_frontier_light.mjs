import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileTerritoryControlPlan, evaluateTerritoryControlFrame, sampleControlBoundary,
 classifyControlPoint} from '../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileControlFrontierLightMotion, evaluateControlFrontierLightMotion,
 controlTerrainLightingFactor, validateControlFrontierLightProfile}
 from '../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';

const fixture = JSON.parse(readFileSync(new URL('../reference-quality-rework-v2/fixtures/SCENE_PLAN.json', import.meta.url))),
 profile = {profileName: 'WORLD_ENGINE_REAL_CONTROL_MATERIAL_LIGHT_V3'},
 plan = compileTerritoryControlPlan(fixture.controlIntent);

test('all 150 light frames bind the already saved 64-knot control without source or ownership changes', () => {
 const sourceBefore = JSON.stringify(fixture), planBefore = JSON.stringify(plan),
  motion = compileControlFrontierLightMotion(plan, profile);
 assert.equal(plan.intent.longitudinal_knots.length, 64);
 assert.equal(plan.intent.boundary_keyframes.length, 11);
 assert.equal(motion.domainGeometryBinding, plan.domainGeometryBinding);
 assert.equal(motion.boundaryKeyframeBinding, plan.boundaryKeyframeBinding);
 for (let relativeFrame = 0; relativeFrame < 150; relativeFrame++) {
  const frame = plan.startFrame + relativeFrame, controls = evaluateTerritoryControlFrame(plan, frame),
   light = evaluateControlFrontierLightMotion(motion, frame);
  assert.ok(light.strength >= .20 && light.strength <= 1);
  assert.equal(light.stopAssumedAtOutputEnd, false);
  for (let knot = 0; knot < 64; knot++) {
   const longitude = controls.longitudinalKnots[knot], latitude = controls.boundaryLatitudes[knot];
   assert.equal(sampleControlBoundary(controls, longitude), latitude);
   if (knot < 63) {
    const midpoint = (longitude + controls.longitudinalKnots[knot + 1]) / 2;
    assert.ok(Math.abs(sampleControlBoundary(controls, midpoint)
     - (latitude + controls.boundaryLatitudes[knot + 1]) / 2) < 1e-10);
   }
  }
  const oracle = classifyControlPoint(controls, [127.0, 37.7]);
  assert.equal(oracle.winner, !oracle.loser);
 }
 assert.equal(JSON.stringify(fixture), sourceBefore);
 assert.equal(JSON.stringify(plan), planBefore);
 assert.equal(evaluateControlFrontierLightMotion(motion, 149).advancing, true);
});

test('an actual stop settles deterministically rather than introducing a repeated pulse or false clip-end stop', () => {
 const syntheticIntent = {
  semantic_mode: 'FACT_BASED_VISUAL_CONTROL',
  source: {source_type: 'SYNTHETIC', source_reference: 'GENERIC_STYLE_STOP_FIXTURE', verification_status: 'SYNTHETIC'},
  domain: [{id: 'GENERIC_LAND', geometry: {type: 'Polygon', coordinates: [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}}],
  factions: {winner: {id: 'FIRST'}, loser: {id: 'SECOND'}},
  longitudinal_knots: [0, 2], base_boundary_latitudes: [.5, .5], advance_direction: 'POSITIVE_LATITUDE',
  fps: 30, total_frames: 60, start_frame: 7,
  boundary_keyframes: [{frame: 0, latitudes: [.5, .5]}, {frame: 20, latitudes: [1.5, 1.5]},
   {frame: 59, latitudes: [1.5, 1.5]}], interpolation: 'LINEAR'
 }, syntheticPlan = compileTerritoryControlPlan(syntheticIntent),
  motion = compileControlFrontierLightMotion(syntheticPlan, profile);
 assert.ok(evaluateControlFrontierLightMotion(motion, 10).strength > .9);
 for (const frame of [66, 40, 60, 40, 66]) {
  const light = evaluateControlFrontierLightMotion(motion, frame);
  assert.equal(light.strength, .2); assert.equal(light.advancing, false);
 }
 const ramp = Array.from({length: 14}, (_, offset) => evaluateControlFrontierLightMotion(motion, 21 + offset).strength);
 for (let index = 1; index < ramp.length; index++) assert.ok(ramp[index] <= ramp[index - 1] + 1e-12);
 assert.throws(() => evaluateControlFrontierLightMotion(motion, 67), /FRAME_OUT_OF_RANGE/);
});

test('real-terrain light is bounded, chromatically neutral, and monotonic with actual terrain luminance', () => {
 const p = validateControlFrontierLightProfile(profile);
 assert.equal(controlTerrainLightingFactor([0, 0, 0], p), p.minimumLightingFactor);
 assert.equal(controlTerrainLightingFactor([1, 1, 1], p), 1);
 let previous = 0;
 for (let index = 0; index <= 100; index++) {
  const y = index / 100, light = controlTerrainLightingFactor([y, y, y], p);
  assert.ok(light >= p.minimumLightingFactor && light <= 1); assert.ok(light >= previous);
  previous = light;
 }
 assert.throws(() => controlTerrainLightingFactor([1.5, 0, 0], p), /ACTUAL_TERRAIN_RGB_REQUIRED/);
 assert.throws(() => validateControlFrontierLightProfile({...profile, haloAlpha: .9}), /STYLE_RANGE/);
 assert.throws(() => validateControlFrontierLightProfile({...profile, centerWidthPixels: 7}), /STYLE_RANGE/);
});

test('existing source arbitrary and repeated frame evaluation stays deterministic and source unmodified', () => {
 const motion = compileControlFrontierLightMotion(plan, profile), sequential = Array.from({length: 150},
  (_, frame) => evaluateControlFrontierLightMotion(motion, frame));
 for (const frame of [149, 0, 74, 38, 112, 74, 149])
  assert.deepEqual(evaluateControlFrontierLightMotion(motion, frame), sequential[frame]);
 assert.equal(motion.syntheticPulse, false);
 assert.throws(() => validateControlFrontierLightProfile({}), /EXPLICIT_STYLE_PROFILE_REQUIRED/);
});
