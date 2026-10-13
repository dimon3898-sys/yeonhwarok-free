/** Bake measured source badge trajectories into geographic per-frame fixture data.
 * Motion lives in the reference data; the renderer only picks the supplied frame.
 * Uses the exact same existing camera track + new presentation inverse as GPU.
 */
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {compileReferenceCameraTrack, evaluateReferenceCameraTrackFrame}
 from '../../web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan, evaluateReferencePresentationFrame,
 expandNativeBounds, presentationScreenToGeo, geoToPresentationScreen}
 from '../../web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {validateReferenceCombatUnits, evaluateReferenceCombatLayout}
 from '../../web/map_infographic_v1/reference_combat_overlay_v2.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const engineRoot = path.resolve(directory, '../..');
const read = filename => JSON.parse(fs.readFileSync(filename, 'utf8'));
const scenePath = process.argv[2] ?? path.join(directory, 'fixtures/SCENE_PLAN.json');
const scene = read(scenePath);
const native = read(path.join(engineRoot, 'recovery/reference-reproduction-v1/fixtures/RUNTIME_FIXTURE.json'));
const source = read(path.join(directory, 'evidence/combat_reference/COMBAT_SCREEN_MEASUREMENTS.json'));
const front = read(path.join(directory, 'evidence/front_reference/REPORT.json'));
const authored = read(path.join(directory, 'fixtures/REFERENCE_COMBAT_VISUAL_PROFILE.json'));
const baseCameraPlan = read(path.join(engineRoot, native.nativeFiles.cameraPlan));
const track = compileReferenceCameraTrack({baseCameraPlan, currentNativeFrame: native.currentNativeFrame,
 keyframes: scene.cameraKeyframes, totalFrames: native.totalFrames, fps: native.fps});
const presentation = compileReferencePresentationPlan({
 rollKeyframes: scene.cameraKeyframes.map(key => ({frame: key.frame, rollDegrees: key.rotationDegrees})),
 totalFrames: native.totalFrames, fps: native.fps, overscan: scene.presentationProfile.overscan,
 width: 1080, height: 1920});
const samples = source.source_samples.map(sample => {
 const registration = front.samples.find(item => item.source_frame === sample.source_frame);
 if (!registration) throw Error('REFERENCE_COMBAT_SHARED_CAMERA_REGISTRATION_MISSING');
 return {time: registration.actual_relative_seconds, units: sample.units};
});
const interpolationInput = {samples, times: Array.from({length: native.totalFrames}, (_, frame) => frame/native.fps)};
// Build-time dependency only. SciPy is already pinned in this cloud environment;
// no package download or installation is performed. Runtime stores the results.
const interpolationPath = path.join(directory, 'evidence/combat_reference/INTERPOLATION_INPUT.json');
fs.writeFileSync(interpolationPath, JSON.stringify(interpolationInput, null, 2)+'\n');
const interpolator = `import sys,json,numpy as np\nfrom scipy.interpolate import PchipInterpolator\nd=json.load(open(sys.argv[1]))\nt=[r['time'] for r in d['samples']]\nframes=d['times']\nresult=[]\nfor item in d['samples'][0]['units']:\n rows=[next(u for u in r['units'] if u['id']==item['id']) for r in d['samples']]\n centers=np.array([r['center_px'] for r in rows],dtype=float)\n sizes=np.array([r['bbox_size_px'] for r in rows],dtype=float)\n result.append({'id':item['id'],'profile_id':item['profile_id'],'centers':PchipInterpolator(t,centers,axis=0,extrapolate=True)(frames).tolist(),'sizes':PchipInterpolator(t,sizes,extrapolate=True)(frames).tolist()})\njson.dump(result,sys.stdout)\n`;
const run = spawnSync('/usr/bin/python3', ['-B', '-c', interpolator, interpolationPath], {
 encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 30000});
if (run.status !== 0) throw Error(`REFERENCE_COMBAT_BUILD_INTERPOLATION_FAILED:${run.stderr}`);
const interpolated = JSON.parse(run.stdout);
const units = interpolated.map(item => ({id: item.id, profile_id: item.profile_id,
 anchor_frames: [], size_frames: item.sizes, rotation_frames: []}));
let maximumRoundtripError = 0;
for (let frame = 0; frame < native.totalFrames; frame++) {
 const camera = evaluateReferenceCameraTrackFrame(track, frame);
 const state = evaluateReferencePresentationFrame(presentation, frame);
 const expanded = expandNativeBounds({bounds: camera.flatBounds, referenceStartBounds: track.startBounds,
  rollDegrees: state.rollDegrees, overscan: state.overscan, width: 1080, height: 1920, correctMeasuredPan: true});
 for (let index = 0; index < units.length; index++) {
  const anchor = presentationScreenToGeo(interpolated[index].centers[frame], expanded, state);
  const roundtrip = geoToPresentationScreen(anchor, expanded, state);
  maximumRoundtripError = Math.max(maximumRoundtripError,
   Math.hypot(roundtrip[0]-interpolated[index].centers[frame][0], roundtrip[1]-interpolated[index].centers[frame][1]));
  units[index].anchor_frames.push(anchor); units[index].rotation_frames.push(state.rollDegrees);
 }
}
validateReferenceCombatUnits(units, authored.profiles);
let safeAreaViolations = 0, criticalCollisions = 0, unitOverlaps = 0;
for (let frame = 0; frame < native.totalFrames; frame++) {
 const camera = evaluateReferenceCameraTrackFrame(track, frame);
 const state = evaluateReferencePresentationFrame(presentation, frame);
 const expanded = expandNativeBounds({bounds: camera.flatBounds, referenceStartBounds: track.startBounds,
  rollDegrees: state.rollDegrees, overscan: state.overscan, width: 1080, height: 1920, correctMeasuredPan: true});
 const layout = evaluateReferenceCombatLayout(units, frame, {
  project: point => geoToPresentationScreen(point, expanded, state), safeArea: [48, 72, 1032, 1848], protectedGraphics: []});
 safeAreaViolations += layout.safeAreaViolations.length;
 criticalCollisions += layout.criticalCollisions.length; unitOverlaps += layout.unitOverlaps.length;
}
if (maximumRoundtripError > 1e-8 || safeAreaViolations || criticalCollisions || unitOverlaps)
 throw Error('REFERENCE_COMBAT_SHARED_PROJECTION_LAYOUT_FAILED:'+JSON.stringify({maximumRoundtripError,
  safeAreaViolations,criticalCollisions,unitOverlaps}));
const result = {version: 'REFERENCE_COMBAT_FIXTURE_V2', units, profiles: authored.profiles,
 source_semantics: authored.semantic_mode, source_visible_unit_count: source.visible_unit_count,
 motion_owner: 'MEASURED_REFERENCE_DATA_NO_SIMULATION', interpolation: 'BUILD_TIME_SOURCE_SAMPLE_PCHIP_C1',
 artwork: authored.authorship, visual_gap: authored.visual_gap};
fs.writeFileSync(path.join(directory, 'fixtures/COMBAT_PROFILE.json'), JSON.stringify(result, null, 2)+'\n');
const report = {schema: 'REFERENCE_COMBAT_FIXTURE_BUILD_V2', status: 'PASS', samples: samples.length,
 units: units.length, frames: native.totalFrames, maximum_projection_roundtrip_error_px: maximumRoundtripError,
 safe_area_violations: safeAreaViolations, critical_collisions: criticalCollisions, unit_overlaps: unitOverlaps,
 renderer_motion_engine_created: false, original_camera_projection_core_modified: false,
 source_camera_registration_shared_with_front: true,
 build_dependency: {python: '/usr/bin/python3', scipy: '1.15.3', runtime_requires_scipy: false},
 no_explosion_aircraft_route_arrow_text: true, source_artwork_pixel_equality_claimed: false};
fs.writeFileSync(path.join(directory, 'evidence/combat_reference/BUILD_REPORT.json'), JSON.stringify(report, null, 2)+'\n');
console.log(JSON.stringify(report));
