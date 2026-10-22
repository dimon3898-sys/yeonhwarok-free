/** Opt-in reference-director mathematical contract. NOT a renderer integration.
 * The protected native factory has no shared rotated forward/inverse hook.
 * No factory, shader, framebuffer or old V2 validation is changed by this file.
 */
export const DIRECTOR_CAMERA_SCHEMA = 'REFERENCE_DIRECTOR_CAMERA_MATH_V1';
export const RENDERER_CONNECTION = 'NOT_CONNECTED_CAPABILITY_EXTENSION_REQUIRED';
const finitePoint = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const radians = x => x * Math.PI / 180;
const rotate = (p, a) => [Math.cos(a) * p[0] - Math.sin(a) * p[1], Math.sin(a) * p[0] + Math.cos(a) * p[1]];
const assert = (value, code) => { if (!value) throw Object.assign(Error(code), {code}); };
const clone = value => structuredClone(value);
function canvasSize(canvas) {
 assert(Array.isArray(canvas) && canvas.length === 2 && canvas.every(x => Number.isSafeInteger(x) && x > 0), 'DIRECTOR_CANVAS_INVALID');
 return canvas;
}
function geographic(point) {
 assert(finitePoint(point) && Math.abs(point[0]) <= 180 && Math.abs(point[1]) <= 90, 'DIRECTOR_GEOGRAPHIC_POINT_INVALID');
 return point;
}

/** Same flat standard-parallel world coordinates as renderer.mjs:355/374,
 * with y down explicitly to match canonical screen pixels. No terrain inferred.
 */
export function createFactoryFlatProjection(initialBounds) {
 assert(Array.isArray(initialBounds) && initialBounds.length === 4 && initialBounds.every(Number.isFinite), 'DIRECTOR_PROJECTION_BOUNDS_INVALID');
 const [w, s, e, n] = initialBounds;
 assert(w >= -180 && e <= 180 && s >= -90 && n <= 90 && e > w && n > s, 'DIRECTOR_PROJECTION_BOUNDS_INVALID');
 const center = [(w + e) / 2, (s + n) / 2], standardParallelCosine = Math.cos(radians(center[1]));
 assert(standardParallelCosine > 1e-8, 'DIRECTOR_POLAR_PROJECTION_UNSUPPORTED');
 return {schema: 'NATIVE_FLAT_Q_MODEL_V1', initialBounds: [...initialBounds], center, standardParallelCosine,
  note: 'Pure factory-coordinate model; private native camera is not changed'};
}
export function projectQ(point, projection) {
 geographic(point); assert(projection?.schema === 'NATIVE_FLAT_Q_MODEL_V1', 'DIRECTOR_PROJECTION_REQUIRED');
 return [(point[0] - projection.center[0]) * projection.standardParallelCosine, projection.center[1] - point[1]];
}
export function inverseQ(point, projection) {
 assert(finitePoint(point) && projection?.schema === 'NATIVE_FLAT_Q_MODEL_V1', 'DIRECTOR_PROJECTION_REQUIRED');
 return [point[0] / projection.standardParallelCosine + projection.center[0], projection.center[1] - point[1]];
}
function pose(state) {
 assert(finitePoint(state?.centerQ) && Number.isFinite(state.scale) && state.scale > 0 && Number.isFinite(state.angleDegrees), 'DIRECTOR_POSE_INVALID');
 return state;
}
export function projectDirectorPoint(point, state, projection, canvas = [1080, 1920]) {
 pose(state); canvasSize(canvas);
 const q = projectQ(point, projection), r = rotate(q.map((v, i) => v - state.centerQ[i]), radians(state.angleDegrees));
 return r.map((v, i) => canvas[i] / 2 + state.scale * v);
}
export function inverseDirectorScreen(pixel, state, projection, canvas = [1080, 1920]) {
 pose(state); canvasSize(canvas); assert(finitePoint(pixel), 'DIRECTOR_PIXEL_INVALID');
 const r = rotate(pixel.map((v, i) => (v - canvas[i] / 2) / state.scale), -radians(state.angleDegrees));
 return inverseQ(r.map((v, i) => v + state.centerQ[i]), projection);
}

export function solveAnchorPose({anchor, targetUV, scale, angleDegrees, projection, canvas = [1080, 1920]}) {
 geographic(anchor); assert(finitePoint(targetUV) && targetUV.every(v => v >= 0 && v <= 1), 'DIRECTOR_ANCHOR_TARGET_INVALID');
 canvasSize(canvas); pose({centerQ: [0, 0], scale, angleDegrees});
 const anchorQ = projectQ(anchor, projection), offset = rotate(targetUV.map((v, i) => (v - .5) * canvas[i] / scale), -radians(angleDegrees));
 return {centerQ: anchorQ.map((v, i) => v - offset[i]), scale, angleDegrees};
}
export function solveContextPairPose({anchors, targetUVs, projection, canvas = [1080, 1920]}) {
 assert(Array.isArray(anchors) && anchors.length === 2 && Array.isArray(targetUVs) && targetUVs.length === 2, 'DIRECTOR_PAIR_REQUIRED');
 canvasSize(canvas); anchors.forEach(geographic);
 assert(targetUVs.every(p => finitePoint(p) && p.every(v => v >= 0 && v <= 1)), 'DIRECTOR_ANCHOR_TARGET_INVALID');
 const q = anchors.map(p => projectQ(p, projection)), delta = q[1].map((v, i) => v - q[0][i]), d = targetUVs[1].map((v, i) => (v - targetUVs[0][i]) * canvas[i]);
 assert(Math.hypot(...delta) > 1e-12 && Math.hypot(...d) > 1e-12, 'DIRECTOR_DEGENERATE_PAIR');
 const scale = Math.hypot(...d) / Math.hypot(...delta), angleDegrees = (Math.atan2(d[1], d[0]) - Math.atan2(delta[1], delta[0])) * 180 / Math.PI;
 return solveAnchorPose({anchor: anchors[0], targetUV: targetUVs[0], scale, angleDegrees, projection, canvas});
}
function polygonPoints(geometry) {
 assert(['Polygon', 'MultiPolygon'].includes(geometry?.type), 'DIRECTOR_POLYGON_REQUIRED');
 const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
 assert(Array.isArray(polygons) && polygons.length > 0, 'DIRECTOR_POLYGON_REQUIRED');
 const points = polygons.flat(2); assert(points.length >= 4, 'DIRECTOR_POLYGON_REQUIRED'); points.forEach(geographic);
 return points;
}
export function projectedGeometryBBox(geometry, state, projection, canvas = [1080, 1920]) {
 const points = polygonPoints(geometry).map(p => projectDirectorPoint(p, state, projection, canvas));
 return [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
}
/** Fits one uniform scale to supplied polygon extents. Conflicting width/height
 * goals produce residuals; geometry is never stretched to satisfy both.
 * centroidAnchor must be a source-qualified centroid, not a bbox surrogate.
 */
export function solvePolygonFramingPose({geometry, centroidAnchor, targetCentroidUV, widthFraction, heightFraction = null, angleDegrees = 0, projection, canvas = [1080, 1920]}) {
 canvasSize(canvas); geographic(centroidAnchor);
 assert(Number.isFinite(widthFraction) && widthFraction > 0 && (heightFraction === null || Number.isFinite(heightFraction) && heightFraction > 0), 'DIRECTOR_POLYGON_TARGET_INVALID');
 const points = polygonPoints(geometry).map(p => rotate(projectQ(p, projection), radians(angleDegrees)));
 const w = Math.max(...points.map(p => p[0])) - Math.min(...points.map(p => p[0])), h = Math.max(...points.map(p => p[1])) - Math.min(...points.map(p => p[1]));
 assert(w > 0 && h > 0, 'DIRECTOR_DEGENERATE_POLYGON');
 const scale = heightFraction === null ? widthFraction * canvas[0] / w :
  (w * widthFraction * canvas[0] + h * heightFraction * canvas[1]) / (w * w + h * h);
 const state = solveAnchorPose({anchor: centroidAnchor, targetUV: targetCentroidUV, scale, angleDegrees, projection, canvas});
 return {...state, residuals: {widthFraction: w * scale / canvas[0] - widthFraction, heightFraction: heightFraction === null ? null : h * scale / canvas[1] - heightFraction}, geometryChanged: false};
}
/** Caller supplies a verified segment/tangent; a curved line is not silently
 * replaced with an endpoint chord. desiredDegrees is screen-y-down direction.
 */
export function solveBoundaryHeading({segment, desiredDegrees, projection}) {
 assert(Array.isArray(segment) && segment.length === 2 && Number.isFinite(desiredDegrees), 'DIRECTOR_BOUNDARY_TANGENT_REQUIRED');
 const a = projectQ(segment[0], projection), b = projectQ(segment[1], projection);
 assert(Math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-12, 'DIRECTOR_DEGENERATE_BOUNDARY');
 return desiredDegrees - Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
}

export function createWindowContract(target) {
 assert(target?.schema === 'WORLD_ENGINE_REFERENCE_DIRECTOR_TARGET_V1', 'DIRECTOR_TARGET_SCHEMA_REQUIRED');
 const p = target.framePolicy, windows = target.reviewWindows;
 assert(p?.fps === 30 && p.intervals === 'HALF_OPEN' && p.indexBase === 0 && p.coreSourceFrames?.length === 2 && p.coreSourceFrames.every(Number.isSafeInteger), 'DIRECTOR_FRAME_POLICY_INVALID');
 const [start, end] = p.coreSourceFrames;
 assert(start >= 0 && end > start && p.coreFrameCount === end - start && Array.isArray(windows) && windows.length > 0, 'DIRECTOR_FRAME_POLICY_INVALID');
 let cursor = start; const ids = new Set();
 const contract = windows.map(w => {
  assert(typeof w.id === 'string' && !ids.has(w.id) && Array.isArray(w.sourceFrameRange) && w.sourceFrameRange.length === 2 && w.sourceFrameRange.every(Number.isSafeInteger), 'DIRECTOR_WINDOW_INVALID');
  const [a, b] = w.sourceFrameRange;
  assert(a === cursor && b > a && w.outputFrames === b - a && w.outputFrames <= 240, 'DIRECTOR_WINDOW_GAP_OVERLAP_OR_SCOPE');
  cursor = b; ids.add(w.id);
  return {id: w.id, sourceFrameRange: [a, b], coreFrameRange: [a - start, b - start], outputFrames: b - a, fps: p.fps, durationSeconds: (b - a) / p.fps};
 });
 assert(cursor === end, 'DIRECTOR_WINDOW_INCOMPLETE');
 return {schema: 'REFERENCE_DIRECTOR_REVIEW_WINDOWS_V1', sourceFrameRange: [start, end], totalFrames: end - start, fps: p.fps, windows: contract,
  boundaryPolicy: 'CONTIGUOUS_SAMPLES_OF_ONE_GLOBAL_TRACK_NO_RESTART_NO_SYNTHETIC_ENDPOINT', rendererConnection: RENDERER_CONNECTION};
}
export function mapWindowFrame(contract, windowId, localFrame) {
 const window = contract.windows.find(w => w.id === windowId);
 assert(window && Number.isSafeInteger(localFrame) && localFrame >= 0 && localFrame < window.outputFrames, 'DIRECTOR_LOCAL_FRAME_INVALID');
 const referenceFrame = window.sourceFrameRange[0] + localFrame;
 return {referenceFrame, coreFrame: referenceFrame - contract.sourceFrameRange[0], localFrame, windowId};
}
function curve(values, frames) {
 const secants = values.slice(1).map((v, i) => (v - values[i]) / (frames[i + 1] - frames[i]));
 const slopes = values.map((_, i) => {
  if (i === 0) return secants[0]; if (i === values.length - 1) return secants.at(-1);
  const a = secants[i - 1], b = secants[i]; if (!a || !b || Math.sign(a) !== Math.sign(b)) return 0;
  const h0 = frames[i] - frames[i - 1], h1 = frames[i + 1] - frames[i], w0 = 2 * h1 + h0, w1 = h1 + 2 * h0;
  return (w0 + w1) / (w0 / a + w1 / b);
 });
 return {values, frames, slopes};
}
function sampleCurve(c, frame) {
 const i = Math.max(0, Math.min(c.frames.length - 2, c.frames.findIndex((f, i) => i > 0 && frame <= f) - 1));
 const duration = c.frames[i + 1] - c.frames[i], u = (frame - c.frames[i]) / duration;
 const a = c.values[i], v0 = c.slopes[i] * duration, delta = c.values[i + 1] - a, v1 = c.slopes[i + 1] * duration;
 const b = v0, cc = 3 * delta - 2 * v0 - v1, d = -2 * delta + v0 + v1;
 return {value: a + u * (b + u * (cc + u * d)), derivativePerFrame: (b + u * (2 * cc + 3 * u * d)) / duration};
}
function unwrap(values) {
 const result = [values[0]];
 for (const value of values.slice(1)) { let next = value; while (next - result.at(-1) > 180) next -= 360; while (next - result.at(-1) < -180) next += 360; result.push(next); }
 return result;
}
export function compileCameraMathTrack({contract, projection, keyframes, inputEvidence}) {
 assert(['SYNTHETIC_TEST', 'SOURCE_BOUND_GEOMETRY'].includes(inputEvidence?.dataMode), 'DIRECTOR_SOURCE_EVIDENCE_REQUIRED');
 assert(inputEvidence.dataMode !== 'SOURCE_BOUND_GEOMETRY' || Array.isArray(inputEvidence.sourceHashes) && inputEvidence.sourceHashes.length > 0 && inputEvidence.sourceHashes.every(h => /^[a-f0-9]{64}$/.test(h)), 'DIRECTOR_REAL_SOURCE_HASHES_REQUIRED');
 assert(projection?.schema === 'NATIVE_FLAT_Q_MODEL_V1' && contract?.schema === 'REFERENCE_DIRECTOR_REVIEW_WINDOWS_V1', 'DIRECTOR_CONTRACT_REQUIRED');
 assert(Array.isArray(keyframes) && keyframes.length >= 2, 'DIRECTOR_GLOBAL_CAMERA_KEYS_REQUIRED');
 keyframes.forEach((k, i) => { pose(k); assert(Number.isSafeInteger(k.referenceFrame) && (!i || k.referenceFrame > keyframes[i - 1].referenceFrame), 'DIRECTOR_ORDERED_KEYS_REQUIRED'); });
 const [start, end] = contract.sourceFrameRange;
 assert(keyframes[0].referenceFrame === start && keyframes.at(-1).referenceFrame === end - 1, 'DIRECTOR_WHOLE_TRACK_KEYS_REQUIRED');
 const frames = keyframes.map(k => k.referenceFrame), angles = unwrap(keyframes.map(k => k.angleDegrees));
 return {schema: DIRECTOR_CAMERA_SCHEMA, contract: clone(contract), projection: clone(projection), inputEvidence: clone(inputEvidence), keyframes: clone(keyframes),
  curves: [curve(keyframes.map(k => k.centerQ[0]), frames), curve(keyframes.map(k => k.centerQ[1]), frames), curve(keyframes.map(k => Math.log(k.scale)), frames), curve(angles, frames)],
  interpolation: 'BOUNDED_C1_MONOTONE_CUBIC_CENTER_LOG_SCALE_UNWRAPPED_ANGLE', rendererConnection: RENDERER_CONNECTION,
  actualPixelVerified: false, referenceVisualMatch: 'UNVERIFIED', sourceAdmission: 'NOT_VERIFIED_BY_MATH_MODULE', cameraLocked: false, settle: {locked: false, settled: false}};
}
export function evaluateCameraMathTrack(track, referenceFrame) {
 assert(track?.schema === DIRECTOR_CAMERA_SCHEMA && Number.isFinite(referenceFrame) && referenceFrame >= track.contract.sourceFrameRange[0] && referenceFrame <= track.contract.sourceFrameRange[1] - 1, 'DIRECTOR_GLOBAL_FRAME_INVALID');
 const samples = track.curves.map(c => sampleCurve(c, referenceFrame));
 return {referenceFrame, coreFrame: referenceFrame - track.contract.sourceFrameRange[0], centerQ: samples.slice(0, 2).map(s => s.value), scale: Math.exp(samples[2].value), angleDegrees: samples[3].value,
  velocityPerSecond: {centerQ: samples.slice(0, 2).map(s => s.derivativePerFrame * track.contract.fps), logScale: samples[2].derivativePerFrame * track.contract.fps, angleDegrees: samples[3].derivativePerFrame * track.contract.fps},
  rendererConnection: RENDERER_CONNECTION, cameraLocked: false, settle: {locked: false, settled: false}};
}
/** Every rotated viewport corner is inverse projected; an unrotated geographic
 * rectangle is deliberately not used as the source coverage proof.
 */
export function sourceEnvelopeForPose(state, projection, canvas = [1080, 1920]) {
 canvasSize(canvas); const [w, h] = canvas;
 const corners = [[0, 0], [w, 0], [w, h], [0, h]].map(p => inverseDirectorScreen(p, state, projection, canvas));
 const bounds = [Math.min(...corners.map(p => p[0])), Math.min(...corners.map(p => p[1])), Math.max(...corners.map(p => p[0])), Math.max(...corners.map(p => p[1]))];
 return {corners, bounds, method: 'INVERSE_OF_ALL_FOUR_ROTATED_VIEWPORT_CORNERS', geographicDomainValid: corners.every(p => Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90)};
}
export function auditTrackSourceCoverage(track, source, canvas = [1080, 1920]) {
 assert(Array.isArray(source?.bounds) && source.bounds.length === 4 && source.bounds.every(Number.isFinite) && source.bounds[0] < source.bounds[2] && source.bounds[1] < source.bounds[3] && finitePoint(source.pixelSpacing) && source.pixelSpacing.every(v => v > 0), 'DIRECTOR_SOURCE_DESCRIPTOR_INVALID');
 const failures = [], frames = [], [start, end] = track.contract.sourceFrameRange;
 for (let f = start; f < end; f++) {
  const state = evaluateCameraMathTrack(track, f), envelope = sourceEnvelopeForPose(state, track.projection, canvas), b = envelope.bounds, s = source.bounds;
  const gutterPixels = Math.min((b[0] - s[0]) / source.pixelSpacing[0], (b[1] - s[1]) / source.pixelSpacing[1], (s[2] - b[2]) / source.pixelSpacing[0], (s[3] - b[3]) / source.pixelSpacing[1]);
  const requiredOutputGroundSpacing = 1 / state.scale / track.projection.standardParallelCosine;
  const record = {referenceFrame: f, ...envelope, minimumGutterPixels: gutterPixels, sufficientPixelSpacing: source.pixelSpacing[0] <= requiredOutputGroundSpacing && source.pixelSpacing[1] <= 1 / state.scale};
  frames.push(record); if (!envelope.geographicDomainValid || gutterPixels < 1 || !record.sufficientPixelSpacing) failures.push(record);
 }
 return {status: failures.length ? 'DATA_DETAIL_BLOCKED' : 'MATH_COVERAGE_PASS_NOT_PIXEL_PASS', framesChecked: frames.length, frames, failures, rendererConnection: RENDERER_CONNECTION,
  scope: 'BBOX_PIXEL_SPACING_AND_GEOGRAPHIC_DOMAIN_ONLY', sourceHashVerified: false, licenseVerified: false, noDataMaskVerified: false};
}
