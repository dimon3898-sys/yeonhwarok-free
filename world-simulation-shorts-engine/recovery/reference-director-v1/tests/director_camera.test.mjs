import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
 createFactoryFlatProjection, projectQ, inverseQ, projectDirectorPoint, inverseDirectorScreen,
 solveAnchorPose, solveContextPairPose, solvePolygonFramingPose, projectedGeometryBBox,
 solveBoundaryHeading, createWindowContract, mapWindowFrame, compileCameraMathTrack,
 evaluateCameraMathTrack, sourceEnvelopeForPose, auditTrackSourceCoverage,
 RENDERER_CONNECTION,
} from '../director_camera.mjs';
const close = (a, b, eps = 1e-8) => assert.ok(Math.abs(a - b) <= eps, `${a} != ${b}`);
const target = {
 schema: 'WORLD_ENGINE_REFERENCE_DIRECTOR_TARGET_V1',
 framePolicy: {fps: 30, indexBase: 0, intervals: 'HALF_OPEN', coreSourceFrames: [29, 575], coreFrameCount: 546},
 reviewWindows: [
  {id: 'A_CONTEXT', sourceFrameRange: [29, 209], outputFrames: 180},
  {id: 'B_FOCUS', sourceFrameRange: [209, 389], outputFrames: 180},
  {id: 'C_BOUNDARY_METRIC', sourceFrameRange: [389, 575], outputFrames: 186},
 ],
};
const contract = createWindowContract(target), projection = createFactoryFlatProjection([0, -20, 30, 50]);
function track(keys = [
 {referenceFrame: 29, centerQ: [0, 0], scale: 500, angleDegrees: 0},
 {referenceFrame: 170, centerQ: [1, 1], scale: 100, angleDegrees: 12},
 {referenceFrame: 332, centerQ: [4, 2], scale: 200, angleDegrees: 20},
 {referenceFrame: 455, centerQ: [5, 3], scale: 700, angleDegrees: 40},
 {referenceFrame: 574, centerQ: [6, 4], scale: 900, angleDegrees: 80},
]) {
 return compileCameraMathTrack({contract, projection, keyframes: keys, inputEvidence: {dataMode: 'SYNTHETIC_TEST', note: 'Explicit mathematical fixture, no geographic reference match claim'}});
}

test('three honest windows partition546frames without padding, reset or fakeendpoint', () => {
 assert.deepEqual(contract.windows.map(w => w.outputFrames), [180, 180, 186]);
 const rows = contract.windows.flatMap(w => Array.from({length: w.outputFrames}, (_, f) => mapWindowFrame(contract, w.id, f)));
 assert.equal(rows.length, 546); assert.equal(new Set(rows.map(r => r.referenceFrame)).size, 546);
 assert.deepEqual(rows.map(r => r.referenceFrame), Array.from({length: 546}, (_, f) => f + 29));
 assert.deepEqual([mapWindowFrame(contract, 'A_CONTEXT', 179).referenceFrame, mapWindowFrame(contract, 'B_FOCUS', 0).referenceFrame], [208, 209]);
 assert.deepEqual([mapWindowFrame(contract, 'B_FOCUS', 179).referenceFrame, mapWindowFrame(contract, 'C_BOUNDARY_METRIC', 0).referenceFrame], [388, 389]);
 assert.throws(() => mapWindowFrame(contract, 'A_CONTEXT', 180), /DIRECTOR_LOCAL_FRAME_INVALID/);
});
test('window contracts reject gaps/overlaps/falsecounts and requests over240', () => {
 for (const mutate of [x => x.reviewWindows[1].sourceFrameRange[0]++, x => x.reviewWindows[0].outputFrames++, x => {x.reviewWindows[0].sourceFrameRange[1] = 300; x.reviewWindows[0].outputFrames = 271;}]) {
  const input = structuredClone(target); mutate(input); assert.throws(() => createWindowContract(input));
 }
});
test('factorycoordinateQ model preserves standardparallel and inverse without assigningprivatecamera', () => {
 const p = createFactoryFlatProjection([8, 30, 16, 40]);
 const actual = projectQ([13, 36], p); close(actual[0], Math.cos(35 * Math.PI / 180)); close(actual[1], -1);
 inverseQ(actual, p).forEach((v, i) => close(v, [13, 36][i]));
 assert.equal(p.note.includes('not changed'), true);
 assert.throws(() => projectQ([181, 0], p), /DIRECTOR_GEOGRAPHIC_POINT_INVALID/);
});
test('similarityproject/inverse keepsworldanchors for variedscales andwrappedangles', () => {
 for (const angleDegrees of [-179, -90, -33, 0, 45, 181, 720]) for (const scale of [.1, 100, 30000]) {
  const state = {centerQ: [3, 2], scale, angleDegrees};
  for (const p of [[12, 36], [15, -5], [17, 20]]) inverseDirectorScreen(projectDirectorPoint(p, state, projection), state, projection).forEach((v, i) => close(v, p[i]));
 }
});
test('heroanchor constraint solvesgeographicbottomtip, neverafloatingfixedscreenpin', () => {
 const anchor = [12.8, 36.2], targetUV = [.3942, .2056];
 const state = solveAnchorPose({anchor, targetUV, scale: 2800, angleDegrees: 39, projection});
 projectDirectorPoint(anchor, state, projection).forEach((v, i) => close(v, targetUV[i] * [1080, 1920][i]));
 const moved = {...state, centerQ: [state.centerQ[0] + .5, state.centerQ[1]]};
 assert.notDeepEqual(projectDirectorPoint(anchor, moved, projection), projectDirectorPoint(anchor, state, projection));
});
test('twoactualanchors jointlydeterminescaleandheading forcanonicalpairgoals', () => {
 const anchors = [[11.2, 35.4], [13.8, 35.1]], targetUVs = [[.309, .378], [.731, .406]];
 const state = solveContextPairPose({anchors, targetUVs, projection});
 anchors.forEach((p, j) => projectDirectorPoint(p, state, projection).forEach((v, i) => close(v, targetUVs[j][i] * [1080, 1920][i])));
 assert.throws(() => solveContextPairPose({anchors: [anchors[0], anchors[0]], targetUVs, projection}), /DEGENERATE_PAIR/);
});
test('polygonfittingpreservesverticesandreportscrossaspectresidualratherthanwarping', () => {
 const geometry = {type: 'Polygon', coordinates: [[[11, 35], [12, 35], [12.2, 35.5], [11.5, 36], [11, 35]]]}, original = JSON.stringify(geometry);
 const result = solvePolygonFramingPose({geometry, centroidAnchor: [11.6, 35.5], targetCentroidUV: [.56, .414], widthFraction: .6, projection, angleDegrees: 17});
 const bbox = projectedGeometryBBox(geometry, result, projection); close((bbox[2] - bbox[0]) / 1080, .6);
 assert.equal(JSON.stringify(geometry), original); assert.equal(result.geometryChanged, false);
 const conflicting = solvePolygonFramingPose({geometry, centroidAnchor: [11.6, 35.5], targetCentroidUV: [.5, .5], widthFraction: .66, heightFraction: .01, projection});
 assert.ok(Math.abs(conflicting.residuals.widthFraction) > .04 || Math.abs(conflicting.residuals.heightFraction) > .04);
});
test('boundaryheadingsolvedfromsuppliedsegmentprojection,notEulerassumption', () => {
 const segment = [[12, 35], [12.02, 35.05]], angleDegrees = solveBoundaryHeading({segment, desiredDegrees: -31.08, projection});
 const pose = {centerQ: [0, 0], scale: 1000, angleDegrees}, [a, b] = segment.map(p => projectDirectorPoint(p, pose, projection));
 close(Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI, -31.08);
 assert.throws(() => solveBoundaryHeading({segment: [segment[0], segment[0]], desiredDegrees: 0, projection}));
});
test('globaltrackusesboundedlogscaleC1anddoesnotstopateachconstraint', () => {
 const t = track();
 for (let f = 29; f <= 574; f++) {
  const s = evaluateCameraMathTrack(t, f); assert.ok(s.scale >= 100 - 1e-8 && s.scale <= 900 + 1e-8);
  assert.equal(s.cameraLocked, false); assert.equal(s.settle.locked, false);
 }
 for (const f of [170, 332, 455]) {
  const a = evaluateCameraMathTrack(t, f - 1e-5), b = evaluateCameraMathTrack(t, f + 1e-5);
  close(a.velocityPerSecond.logScale, b.velocityPerSecond.logScale, 1e-5);
  a.velocityPerSecond.centerQ.forEach((v, i) => close(v, b.velocityPerSecond.centerQ[i], 1e-5));
  close(a.velocityPerSecond.angleDegrees, b.velocityPerSecond.angleDegrees, 1e-5);
 }
 assert.ok(evaluateCameraMathTrack(t, 332).velocityPerSecond.logScale > 0);
 assert.ok(evaluateCameraMathTrack(t, 170).velocityPerSecond.centerQ.some(v => v !== 0));
});
test('headingunwrapavoids358degreejump', () => {
 const t = track([{referenceFrame: 29, centerQ: [0, 0], scale: 1, angleDegrees: 179}, {referenceFrame: 574, centerQ: [1, 1], scale: 2, angleDegrees: -179}]);
 close(evaluateCameraMathTrack(t, 574).angleDegrees, 181); close(evaluateCameraMathTrack(t, (29 + 574) / 2).angleDegrees, 180);
});
test('randomaccesswholetrackindependentofwindowanditerationorder', () => {
 const t = track(), frames = [574, 208, 29, 389, 209, 388, 420, 455];
 const before = frames.map(f => evaluateCameraMathTrack(t, f));
 for (let f = 29; f <= 574; f++) evaluateCameraMathTrack(t, f);
 assert.deepEqual(frames.map(f => evaluateCameraMathTrack(t, f)), before);
 for (const [id, f] of [['A_CONTEXT', 179], ['B_FOCUS', 0], ['B_FOCUS', 179], ['C_BOUNDARY_METRIC', 0]]) {
  const mapped = mapWindowFrame(contract, id, f); assert.equal(evaluateCameraMathTrack(t, mapped.referenceFrame).coreFrame, mapped.coreFrame);
 }
});
test('reviewAwindowsmayendwideandmustnotrequirefakeclosestendpoint', () => {
 const t = track(); assert.ok(evaluateCameraMathTrack(t, 208).scale < evaluateCameraMathTrack(t, 29).scale);
 assert.equal(t.keyframes.length, 5); assert.equal(t.keyframes.some(k => k.referenceFrame === 208), false);
});
test('rotatedsourceenvelopeinverseprojectsallfourcorners', () => {
 const state = {centerQ: [0, 0], scale: 1000, angleDegrees: 40}, envelope = sourceEnvelopeForPose(state, projection);
 assert.equal(envelope.corners.length, 4);
 envelope.corners.forEach((p, i) => projectDirectorPoint(p, state, projection).forEach((v, axis) => close(v, [[0, 0], [1080, 0], [1080, 1920], [0, 1920]][i][axis])));
 const straight = sourceEnvelopeForPose({...state, angleDegrees: 0}, projection);
 assert.ok(envelope.bounds[2] - envelope.bounds[0] > straight.bounds[2] - straight.bounds[0]);
});
test('every546framecoverageanddeepestsourcepixelspacingcheckedbeforewindows', () => {
 const t = track(), source = {bounds: [-10, -20, 40, 50], pixelSpacing: [.00001, .00001]};
 const accepted = auditTrackSourceCoverage(t, source); assert.equal(accepted.framesChecked, 546); assert.equal(accepted.failures.length, 0);
 assert.equal(accepted.status, 'MATH_COVERAGE_PASS_NOT_PIXEL_PASS');
 const coarse = auditTrackSourceCoverage(t, {...source, pixelSpacing: [.5, .5]}); assert.equal(coarse.status, 'DATA_DETAIL_BLOCKED'); assert.equal(coarse.failures.length, 546);
 const uncovered = auditTrackSourceCoverage(t, {...source, bounds: [15, 15, 16, 16]}); assert.equal(uncovered.status, 'DATA_DETAIL_BLOCKED');
});
test('unbounddataandpartialtrackrejected;mathematicalresultneverclaimsactualrendererorvisualPASS', () => {
 assert.throws(() => compileCameraMathTrack({contract, projection, keyframes: [], inputEvidence: {dataMode: 'UNBOUND'}}), /SOURCE_EVIDENCE_REQUIRED/);
 assert.throws(() => compileCameraMathTrack({contract, projection, keyframes: track().keyframes.slice(1), inputEvidence: {dataMode: 'SYNTHETIC_TEST'}}), /WHOLE_TRACK_KEYS_REQUIRED/);
 assert.throws(() => compileCameraMathTrack({contract, projection, keyframes: track().keyframes, inputEvidence: {dataMode: 'SOURCE_BOUND_GEOMETRY', sourceHashes: []}}), /REAL_SOURCE_HASHES_REQUIRED/);
 const t = track(); assert.equal(t.rendererConnection, RENDERER_CONNECTION); assert.equal(t.actualPixelVerified, false); assert.equal(t.referenceVisualMatch, 'UNVERIFIED');
});

for (const name of ['SYNTHETIC_NORTH', 'SYNTHETIC_SOUTH']) test(`samegenericmathcontracton${name}withoutcountryalgorithm`, () => {
 const path = new URL(`../fixtures/${name}.json`, import.meta.url);
 assert.ok(fs.existsSync(path), 'Data agent must supply the explicit nonhistorical fixture before this test can pass');
 const fixture = JSON.parse(fs.readFileSync(path, 'utf8'));
 assert.equal(fixture.dataMode, 'SYNTHETIC_TEST');
 const coordinates = fixture.primaryGeometry.coordinates.flat(), xs = coordinates.map(p => p[0]), ys = coordinates.map(p => p[1]);
 const p = createFactoryFlatProjection([Math.min(...xs) - 2, Math.min(...ys) - 2, Math.max(...xs) + 2, Math.max(...ys) + 2]);
 const s = solveContextPairPose({anchors: fixture.contextAnchors, targetUVs: [[.285, .402], [.68, .394]], projection: p});
 fixture.contextAnchors.forEach((point, j) => projectDirectorPoint(point, s, p).forEach((v, i) => close(v, [[.285, .402], [.68, .394]][j][i] * [1080, 1920][i])));
 const hero = solveAnchorPose({anchor: fixture.detailAnchor, targetUV: [.3942, .2056], scale: s.scale * 2, angleDegrees: s.angleDegrees + 40, projection: p});
 projectDirectorPoint(fixture.detailAnchor, hero, p).forEach((v, i) => close(v, [.3942, .2056][i] * [1080, 1920][i]));
 assert.ok(fixture.primaryGeometry.coordinates[0].length > 5); assert.equal(typeof fixture.sourceTruth, 'string'); assert.match(fixture.sourceTruth, /no real|nonhistorical|nonhistorical/i);
 assert.equal(RENDERER_CONNECTION, 'NOT_CONNECTED_CAPABILITY_EXTENSION_REQUIRED');
});
