import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateWorldEngineUnitFixture, evaluateWorldEngineUnitLayout}
 from '../../web/map_infographic_v1/world_engine_unit_overlay_v3.mjs';
import {compileReferenceCameraTrack, evaluateReferenceCameraTrackFrame}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan, evaluateReferencePresentationFrame, expandNativeBounds, geoToPresentationScreen}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const engine = path.resolve(root, '../..');
const read = file => JSON.parse(fs.readFileSync(path.join(engine, file)));
const authored = read('recovery/map-visual-upgrade-v1/fixtures/ORIGINAL_UNIT_PROFILE.json');
const previous = read('recovery/reference-quality-rework-v2/fixtures/COMBAT_PROFILE.json');
const scene = read('recovery/reference-quality-rework-v2/fixtures/SCENE_PLAN.json');
const fixture = read('recovery/reference-reproduction-v1/fixtures/RUNTIME_FIXTURE.json');
const camera = read(fixture.nativeFiles.cameraPlan);
const track = compileReferenceCameraTrack({baseCameraPlan: camera, currentNativeFrame: fixture.currentNativeFrame,
 keyframes: scene.cameraKeyframes, totalFrames: fixture.totalFrames, fps: fixture.fps});
const presentation = compileReferencePresentationPlan({rollKeyframes: scene.cameraKeyframes.map(key => ({frame: key.frame,
 rollDegrees: key.rotationDegrees})), totalFrames: fixture.totalFrames, fps: fixture.fps,
 overscan: scene.presentationProfile.overscan, width: 1080, height: 1920});

test('original role artwork preserves all eight supplied geographic and temporal bindings', () => {
 const before = JSON.stringify(authored);
 const actual = validateWorldEngineUnitFixture(authored.units, authored.profiles);
 assert.equal(actual.units, 8); assert.equal(actual.frames, 150); assert.equal(actual.sourceIconArtworkCopied, false);
 for (let index = 0; index < previous.units.length; index++) {
  const old = previous.units[index], current = authored.units[index];
  assert.equal(current.id, old.id); assert.deepEqual(current.anchor_frames, old.anchor_frames);
  assert.deepEqual(current.rotation_frames, old.rotation_frames);
  for (let frame = 0; frame < 150; frame++)
   assert.ok(Math.abs(current.size_frames[frame] / current.size_frames[0] - old.size_frames[frame] / old.size_frames[0]) < 1e-12);
 }
 assert.equal(JSON.stringify(authored), before);
});

test('all 150 real camera projections retain safe area and protected layout without motion engine duplication', () => {
 let maximumStep = 0, previousLayout;
 for (let frame = 0; frame < 150; frame++) {
  const cameraFrame = evaluateReferenceCameraTrackFrame(track, frame), state = evaluateReferencePresentationFrame(presentation, frame);
  const bounds = expandNativeBounds({bounds: cameraFrame.flatBounds, referenceStartBounds: track.startBounds,
   rollDegrees: state.rollDegrees, overscan: state.overscan, width: 1080, height: 1920, correctMeasuredPan: true});
  const project = point => geoToPresentationScreen(point, bounds, state);
  const layout = evaluateWorldEngineUnitLayout(authored.units, frame, {project, safeArea: [48, 72, 1032, 1848], protectedGraphics: []});
  assert.equal(layout.safeAreaViolations.length, 0); assert.equal(layout.criticalCollisions.length, 0);
  assert.equal(layout.unitOverlaps.length, 0); assert.equal(layout.sourceIconArtworkCopied, false);
  for (let index = 0; index < layout.units.length; index++) {
   assert.deepEqual(layout.units[index].position, project(authored.units[index].anchor_frames[frame]));
   if (previousLayout) maximumStep = Math.max(maximumStep, Math.hypot(...layout.units[index].position.map((value, axis) => value - previousLayout.units[index].position[axis])));
  }
  previousLayout = layout;
 }
 assert.ok(maximumStep < 10, 'supplied original motion must remain continuous');
});

test('source insignia and portrait-style input is rejected, not silently rendered', () => {
 const invalid = structuredClone(authored.profiles);
 invalid.WORLD_ENGINE_WARM_INFANTRY.flag_shapes = [];
 assert.throws(() => validateWorldEngineUnitFixture(authored.units, invalid), /ORIGINAL_INFANTRY_PROFILE_REQUIRED/);
 const invalidSize = structuredClone(authored.units); invalidSize[0].size_frames[0] = 140;
 assert.throws(() => validateWorldEngineUnitFixture(invalidSize, authored.profiles), /RESTRAINED_ROLE_SIZE_REQUIRED/);
});

test('protection reports a collision without moving unit or existing graphic', () => {
 const input = structuredClone(authored.units.slice(0, 1));
 const graphics = [{id: 'EXISTING_TEXT', bounds: [500, 900, 580, 980]}];
 const before = JSON.stringify({input, graphics});
 const output = evaluateWorldEngineUnitLayout(input, 0, {project: () => [540, 940], safeArea: [48, 72, 1032, 1848], protectedGraphics: graphics});
 assert.equal(output.criticalCollisions.length, 1); assert.equal(JSON.stringify({input, graphics}), before);
 assert.equal(output.flags, 0); assert.equal(output.speculativeImpactCues, 0);
});
