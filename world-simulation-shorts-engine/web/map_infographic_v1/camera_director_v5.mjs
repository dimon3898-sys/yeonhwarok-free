/** V5 camera-only Minimum Context. No rendering, style, Reveal or GIS mutation. */
import {compileCameraIntent, compileReferenceCameraPlan, evaluateReferenceCameraFrame} from './camera_director_v4.mjs';
import {geometryBounds} from './scale_contract.mjs';

export const CAMERA_DIRECTOR_V5_VERSION = 'CAMERA_DIRECTOR_V5';
export const CAMERA_INTENT_V5_VERSION = 'GEOGRAPHIC_CAMERA_INTENT_V5';
const copy = value => structuredClone(value);
const freeze = value => { if (value && typeof value === 'object' && !Object.isFrozen(value)) {
 Object.values(value).forEach(freeze); Object.freeze(value); } return value; };
const union = bounds => [Math.min(...bounds.map(b => b[0])), Math.min(...bounds.map(b => b[1])),
 Math.max(...bounds.map(b => b[2])), Math.max(...bounds.map(b => b[3]))];
const spans = b => [b[2] - b[0], b[3] - b[1]];
const contains = (outer, inner) => outer[0] <= inner[0] + 1e-9 && outer[1] <= inner[1] + 1e-9 &&
 outer[2] + 1e-9 >= inner[2] && outer[3] + 1e-9 >= inner[3];
const validExtent = b => b.every(Number.isFinite) && b[0] < b[2] && b[1] < b[3] &&
 b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;
function records(value) {
 if (!value) return [];
 if (Array.isArray(value)) return value.flatMap(records);
 if (value.type === 'FeatureCollection') return value.features.flatMap(records);
 if (value.type === 'GeometryCollection') return value.geometries.flatMap(records);
 return [value];
}
function safeViewport(bounds, display) {
 const [width, height] = spans(bounds), [w, h] = display.canonicalOutput, a = display.safeArea;
 return [bounds[0] + a[0] / w * width, bounds[3] - a[3] / h * height,
  bounds[0] + a[2] / w * width, bounds[3] - a[1] / h * height];
}

// The focus is centered in the actual safe rectangle. Geographic aspect fixes
// width from height and center latitude; the smallest feasible height is solved.
function minimumSafeExtent(required, display, start, final) {
 const [ow, oh] = display.canonicalOutput, safe = display.safeArea;
 const left = safe[0] / ow, right = safe[2] / ow;
 const bottom = 1 - safe[3] / oh, top = 1 - safe[1] / oh;
 const sx = (left + right) / 2, sy = (bottom + top) / 2;
 const requiredCenter = [(required[0] + required[2]) / 2, (required[1] + required[3]) / 2];
 const requiredSpans = spans(required), initial = spans(start), approved = spans(final);
 const minWidth = Math.max(requiredSpans[0] / (right - left), initial[0], approved[0]);
 const minHeight = Math.max(requiredSpans[1] / (top - bottom), initial[1], approved[1]);
 const maxHeight = Math.min((requiredCenter[1] + 90) / sy, (90 - requiredCenter[1]) / (1 - sy));
 const widthAt = height => {
  const latitude = requiredCenter[1] + (.5 - sy) * height;
  const cosine = Math.cos(latitude * Math.PI / 180);
  if (cosine < .01) throw Error('CAMERA_V5_MINIMUM_CONTEXT_POLAR_LIMIT');
  return height * ow / oh / cosine;
 };
 if (!(minHeight > 0) || minHeight > maxHeight) throw Error('CAMERA_V5_MINIMUM_CONTEXT_OUT_OF_RANGE');
 let low = minHeight, high = minHeight;
 while (widthAt(high) < minWidth) {
  const next = Math.min(maxHeight, high * 2);
  if (next <= high) throw Error('CAMERA_V5_MINIMUM_CONTEXT_OUT_OF_RANGE');
  high = next;
 }
 if (high > low) for (let i = 0; i < 64; i++) {
  const middle = (low + high) / 2;
  if (widthAt(middle) < minWidth) low = middle; else high = middle;
 }
 const height = high, width = widthAt(height);
 const c = [requiredCenter[0] + (.5 - sx) * width, requiredCenter[1] + (.5 - sy) * height];
 const result = [c[0] - width / 2, c[1] - height / 2, c[0] + width / 2, c[1] + height / 2];
 if (!validExtent(result) || !contains(safeViewport(result, display), required))
  throw Error('CAMERA_V5_MINIMUM_CONTEXT_OUT_OF_RANGE');
 return result;
}

function clippedSegment(a, b, extent) {
 let enter = 0, exit = 1;
 const dx = b[0] - a[0], dy = b[1] - a[1];
 for (const [p, q] of [[-dx, a[0] - extent[0]], [dx, extent[2] - a[0]],
  [-dy, a[1] - extent[1]], [dy, extent[3] - a[1]]]) {
  if (p === 0) { if (q < 0) return []; }
  else { const t = q / p; if (p < 0) enter = Math.max(enter, t); else exit = Math.min(exit, t);
   if (enter > exit) return []; }
 }
 return [[a[0] + dx * enter, a[1] + dy * enter], [a[0] + dx * exit, a[1] + dy * exit]];
}
function inRing(p, ring) {
 let inside = false;
 for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
  const a = ring[i], b = ring[j];
  if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function corridorPortion(record, extent) {
 const geometry = record.geometry ?? record, type = record.geometry_type ?? geometry.type;
 const coordinates = record.coordinates ?? geometry.coordinates;
 geometryBounds(record); // Validate actual source coordinates even when optional.
 let lines = [], polygons = [], points = [];
 if (type === 'Polygon') polygons = [coordinates];
 else if (type === 'MultiPolygon') polygons = coordinates;
 else if (type === 'LineString') lines = [coordinates];
 else if (type === 'MultiLineString') lines = coordinates;
 else if (type === 'Point') points = [coordinates];
 else if (type === 'MultiPoint') points = coordinates;
 else throw Error('CAMERA_V5_CONTEXT_GEOMETRY_TYPE_REQUIRED');
 lines.push(...polygons.flatMap(polygon => polygon));
 const retained = points.filter(p => contains(extent, [p[0], p[1], p[0], p[1]]));
 for (const line of lines) for (let i = 1; i < line.length; i++) retained.push(...clippedSegment(line[i - 1], line[i], extent));
 const corners = [[extent[0], extent[1]], [extent[0], extent[3]], [extent[2], extent[1]], [extent[2], extent[3]]];
 for (const p of corners) if (polygons.some(polygon => inRing(p, polygon[0]) && !polygon.slice(1).some(hole => inRing(p, hole)))) retained.push(p);
 return retained.length ? union(retained.map(p => [p[0], p[1], p[0], p[1]])) : null;
}

function clippedRing(ring, extent) {
 let points = ring.slice(0, -1);
 for (const [axis, limit, sign] of [[0, extent[0], 1], [0, extent[2], -1], [1, extent[1], 1], [1, extent[3], -1]]) {
  const input = points; points = [];
  if (!input.length) break;
  for (let i = 0; i < input.length; i++) {
   const a = input[(i + input.length - 1) % input.length], b = input[i];
   const insideA = (a[axis] - limit) * sign >= 0, insideB = (b[axis] - limit) * sign >= 0;
   if (insideA !== insideB) {
    const t = (limit - a[axis]) / (b[axis] - a[axis]);
    points.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
   }
   if (insideB) points.push(b);
  }
 }
 return points;
}
function ringArea(points) {
 let area = 0;
 for (let i = 0; i < points.length; i++) {
  const a = points[i], b = points[(i + 1) % points.length]; area += a[0] * b[1] - b[0] * a[1];
 }
 return Math.abs(area) / 2;
}
function actualPrimaryArea(primaryGeometry, extent) {
 let area = 0;
 for (const record of records(primaryGeometry)) {
  const g = record.geometry ?? record, type = record.geometry_type ?? g.type, coordinates = record.coordinates ?? g.coordinates;
  const polygons = type === 'Polygon' ? [coordinates] : type === 'MultiPolygon' ? coordinates : [];
  for (const polygon of polygons) area += Math.max(0, ringArea(clippedRing(polygon[0], extent)) -
   polygon.slice(1).reduce((sum, hole) => sum + ringArea(clippedRing(hole, extent)), 0));
 }
 return area;
}

/**
 * context_geometry is optional scenery, not a mandate to show whole countries.
 * relationGeometry is an explicit caller-selected direct relationship constraint;
 * no ID, country name, distance or text is used to infer semantic relationships.
 */
export function compileMinimumContextIntent(scene = {}, {relationGeometry = []} = {}) {
 const baseScene = {...scene, context_geometry: null};
 delete baseScene.context_extent;
 const base = compileCameraIntent(baseScene); // Preserve V4 admission/start/final validation.
 // V4's noCloser rebuilds a validated explicit box from center/spans. If no
 // widening is needed, retain the approved literal box instead of a one-ULP
 // round trip. Narrower inputs still use the existing V4 noCloser decision.
 let startExtent = scene.start_extent && spans(scene.start_extent).every((value, index) => value >= spans(base.finalExtent)[index])
  ? [...scene.start_extent] : [...base.startExtent];
 if (!scene.start_extent && !contains(safeViewport(startExtent, base.display), base.primaryBounds))
  startExtent = minimumSafeExtent(base.primaryBounds, base.display, startExtent, base.finalExtent);
 const recognitionSafe = safeViewport(startExtent, base.display);
 if (!contains(recognitionSafe, base.primaryBounds) || actualPrimaryArea(base.primaryGeometry, recognitionSafe) <= 1e-12)
  throw Error('CAMERA_V5_PRIMARY_RECOGNITION_INFEASIBLE');
 const direct = records(relationGeometry), optional = records(scene.context_geometry);
 const anchor = [base.anchor[0], base.anchor[1], base.anchor[0], base.anchor[1]];
 const required = union([base.primaryBounds, anchor, ...records(base.eventGeometry).map(geometryBounds), ...direct.map(geometryBounds)]);
 const needsContext = !contains(safeViewport(startExtent, base.display), required);
 const contextExtent = needsContext ? minimumSafeExtent(required, base.display, startExtent, base.finalExtent) : [...startExtent];
 const portions = optional.map(record => ({id: record.id ?? null, bounds: corridorPortion(record, required)}));
 return freeze({...copy(base), directorVersion: CAMERA_DIRECTOR_V5_VERSION, intentVersion: CAMERA_INTENT_V5_VERSION,
  contextGeometry: copy(scene.context_geometry ?? null), startExtent, contextExtent,
  context: {required: needsContext, requiredGeometryBounds: required,
   basis: 'Required Primary/event geometry and explicitly selected direct relations, fitted to actual safe area and geographic aspect',
   condition: 'Required geometry is not contained by starting safe viewport',
   policy: 'MINIMUM_PRIMARY_EVENT_CONTEXT_V5', fitMethod: 'SAFE_CENTERED_GEOGRAPHIC_ASPECT_MINIMUM_HEIGHT',
   directRelationGeometry: copy(relationGeometry), directRelationSourceCount: direct.length,
   optionalContextSourceCount: optional.length, optionalContextCorridor: [...required],
   optionalContextPortions: portions, optionalContextPolicy: 'Actual corridor portions retained as evidence; full optional country bounds are not required constraints',
   legacyContextExtent: copy(scene.context_extent ?? null), legacyContextExtentUsage: 'NOT_A_REQUIRED_CONSTRAINT',
   minimumContextSkipped: !needsContext},
 });
}

const center = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
const clamp = value => Math.max(0, Math.min(1, value));
const poseVector = b => [...center(b), ...spans(b).map(Math.log)];
const zeroVector = () => [0, 0, 0, 0];
function hermite(from, to, startVelocity, endVelocity, startAcceleration, endAcceleration, start, end) {
 const duration = end - start;
 if (!(duration > 0)) throw Error('CAMERA_V5_POSITIVE_SPLINE_DURATION_REQUIRED');
 const coefficients = from.map((value, i) => {
  const c0 = value, c1 = startVelocity[i] * duration, c2 = startAcceleration[i] * duration * duration / 2;
  const a = to[i] - c0 - c1 - c2, b = endVelocity[i] * duration - c1 - 2 * c2;
  const c = endAcceleration[i] * duration * duration - 2 * c2;
  return [c0, c1, c2, 10 * a - 4 * b + c / 2, -15 * a + 7 * b - c, 6 * a - 3 * b + c / 2];
 });
 return {startSeconds: start, endSeconds: end, durationSeconds: duration, from, to,
  startVelocity, endVelocity, startAcceleration, endAcceleration, coefficients};
}
function splineAt(segment, seconds) {
 const t = clamp((seconds - segment.startSeconds) / segment.durationSeconds), d = segment.durationSeconds;
 const values = [], velocity = [], acceleration = [];
 for (const c of segment.coefficients) {
  values.push(c[0] + t * (c[1] + t * (c[2] + t * (c[3] + t * (c[4] + t * c[5])))));
  velocity.push((c[1] + t * (2 * c[2] + t * (3 * c[3] + t * (4 * c[4] + t * 5 * c[5])))) / d);
  acceleration.push((2 * c[2] + t * (6 * c[3] + t * (12 * c[4] + t * 20 * c[5]))) / (d * d));
 }
 if (t === 0) return {values: [...segment.from], velocity: [...segment.startVelocity], acceleration: [...segment.startAcceleration]};
 if (t === 1) return {values: [...segment.to], velocity: [...segment.endVelocity], acceleration: [...segment.endAcceleration]};
 return {values, velocity, acceleration};
}
function compileNaturalMotion(base) {
 const request = base.intent, fps = base.fps, timeline = [];
 const old = state => base.timeline.find(item => item.state === state);
 const add = (state, count, motion) => {
  const startFrame = timeline.at(-1)?.endFrame ?? 0, endFrame = startFrame + count;
  const item = {state, key: state, startFrame, endFrame, durationFrames: count,
   startSeconds: startFrame / fps, endSeconds: endFrame / fps, motion,
   scale: state === 'PRIMARY_RECOGNITION' ? 'REGIONAL_CONTEXT' : 'CONTEXT_TO_EVENT'};
  timeline.push(item); return item;
 };
 const recognition = add('PRIMARY_RECOGNITION', old('PRIMARY_RECOGNITION').durationFrames, 'FIXED');
 let expansion = null, turn = null;
 if (request.context.required) {
  expansion = add('CONTEXT_EXPANSION', old('CONTEXT_EXPANSION').durationFrames, 'CONTINUOUS_CENTER_LOG_EXTENT');
  const turnFrames = Math.max(3, Math.round(Math.min(base.profile.relationSeconds, base.profile.minimumFineApproachSeconds) * fps));
  turn = add('DIRECTIONAL_TURN', turnFrames, 'MOVING_RELATION_READABILITY_NO_HARD_STOP');
 }
 const approach = add('EVENT_APPROACH', old('EVENT_APPROACH').durationFrames, 'PAN_LEADING_CONTINUOUS_APPROACH');
 const guided = add('GUIDED_REVEAL', old('GUIDED_REVEAL').durationFrames, 'CONTINUOUS_READABILITY_BUDGET');
 const deceleration = add('DECELERATE', old('DECELERATE').durationFrames, 'CONTINUOUS_DECELERATION');
 const framing = add('EVENT_FRAMING', old('EVENT_FRAMING').durationFrames, 'CONTINUOUS_FINE_APPROACH');
 const settle = add('SETTLE', old('SETTLE').durationFrames, 'FIXED');
 const lock = add('LOCK', old('LOCK').durationFrames, 'FIXED');
 const title = add('EVENT_TITLE', old('EVENT_TITLE').durationFrames, 'FIXED');
 const hold = add('PERCEPTION_HOLD', old('PERCEPTION_HOLD').durationFrames, 'FIXED');
 const next = add('NEXT', old('NEXT').durationFrames, 'FIXED');
 const startFrame = expansion?.startFrame ?? approach.startFrame, arrivalFrame = framing.endFrame - 1;
 const endSeconds = (arrivalFrame - startFrame) / fps, from = poseVector(request.startExtent), to = poseVector(request.finalExtent);
 let segments, peakFrame = null;
 if (turn) {
  peakFrame = turn.startFrame;
  const middle = poseVector(request.contextExtent), a = (peakFrame - startFrame) / fps, b = endSeconds - a;
  const tangent = [0, 0, 0, 0], curvature = [0, 0, 0, 0];
  for (let i = 0; i < 2; i++) {
   const incoming = (middle[i] - from[i]) / a, outgoing = (to[i] - middle[i]) / b;
   tangent[i] = incoming * outgoing > 0 ? Math.sign(incoming) * Math.min(Math.abs(incoming), Math.abs(outgoing)) :
    incoming !== 0 ? incoming * .15 : outgoing * .15;
  }
  // Both log-span pieces are monotone (normalized endpoint curvature <= 2).
  // Their shared zero zoom velocity is a real maximum, while pan continues.
  for (let i = 2; i < 4; i++) curvature[i] = -Math.min(2 * Math.max(0, middle[i] - from[i]) / (a * a),
   2 * Math.max(0, middle[i] - to[i]) / (b * b));
  segments = [hermite(from, middle, zeroVector(), tangent, zeroVector(), curvature, 0, a),
   hermite(middle, to, tangent, zeroVector(), curvature, zeroVector(), a, endSeconds)];
 } else segments = [hermite(from, to, zeroVector(), zeroVector(), zeroVector(), zeroVector(), 0, endSeconds)];
 const zoomNeeded = [2, 3].some(axis => Math.abs(to[axis] - from[axis]) > 1e-12 ||
  (turn && Math.abs(poseVector(request.contextExtent)[axis] - to[axis]) > 1e-12));
 const panArrivalFrame = zoomNeeded ? deceleration.startFrame : arrivalFrame;
 if (zoomNeeded) {
  // Keep the complete zoom polynomial, including its shared Context tangent.
  // Center arrives at the data-timed deceleration boundary; zoom keeps moving.
  const panSeconds = (panArrivalFrame - startFrame) / fps, zoomCurve = segments.at(-1);
  const split = splineAt(zoomCurve, panSeconds), panTarget = [to[0], to[1], split.values[2], split.values[3]];
  const splitVelocity = [0, 0, split.velocity[2], split.velocity[3]];
  const splitAcceleration = [0, 0, split.acceleration[2], split.acceleration[3]];
  const incoming = hermite(zoomCurve.from, panTarget, zoomCurve.startVelocity, splitVelocity,
   zoomCurve.startAcceleration, splitAcceleration, zoomCurve.startSeconds, panSeconds);
  const outgoing = hermite(panTarget, to, splitVelocity, zeroVector(), splitAcceleration, zeroVector(), panSeconds, endSeconds);
  segments = [...segments.slice(0, -1), incoming, outgoing];
 }
 const sharedPan = turn ? Math.hypot(...segments[0].endVelocity.slice(0, 2)) : 0;
 const checkpoints = {PRIMARY_START: recognition.startFrame, EVENT_APPROACH: guided.startFrame,
  REGIONAL_LOCK: lock.endFrame - 1, EVENT_TITLE: title.endFrame - 1,
  FINAL_HOLD: hold.startFrame + Math.floor(hold.durationFrames / 2)};
 if (turn) { checkpoints.CONTEXT = peakFrame; checkpoints.DIRECTIONAL_TURN = peakFrame; }
 return {...copy(base), directorVersion: CAMERA_DIRECTOR_V5_VERSION, intentVersion: CAMERA_INTENT_V5_VERSION,
  implementationStage: 'NATURAL_TURNAROUND', timeline, totalFrames: next.endFrame, durationSeconds: next.endFrame / fps,
  naturalMotion: {version: 'ACTUAL_SECONDS_C2_CENTER_LOG_EXTENT_V5', startFrame, arrivalFrame, endSeconds,
   peakFrame, segments, contextTurnSkipped: !turn, phaseCurveResets: false,
   panArrivalFrame, zoomArrivalFrame: arrivalFrame, realZoomNeeded: zoomNeeded,
   channelPolicy: zoomNeeded ? 'CENTER_ARRIVES_AT_DECELERATION_START_ZOOM_CONTINUES_TO_FINAL' : 'NO_FORCED_ZOOM_CONTINUOUS_PAN_TO_FINAL',
   turnMode: turn ? sharedPan > 1e-12 ? 'DIRECTIONAL_PAN_CONTINUITY' : 'PURE_ZOOM_REVERSAL' : 'CONTEXT_SKIPPED',
   relationPolicy: 'Short moving relation beat; no stationary RELATION_HOLD'},
  trajectories: [{kind: 'NATURAL_TURNAROUND_V5', startFrame, endFrame: framing.endFrame,
   from: [...request.startExtent], to: [...request.finalExtent], metrics: base.motion.metrics, panBias: 0, zoomBias: 0}],
  context: {...copy(base.context), expansionStartFrame: expansion?.startFrame ?? null, expansionEndFrame: expansion?.endFrame ?? null,
   relationStartFrame: turn?.startFrame ?? null, relationEndFrame: turn?.endFrame ?? null},
  motion: {...copy(base.motion), startFrame, endFrame: framing.endFrame, arrivalFrame,
   startBounds: [...request.startExtent], endBounds: [...request.finalExtent], phaseCurveResets: false,
   interpolation: 'ACTUAL_SECONDS_C2_SHARED_CENTER_LOG_EXTENT_SPLINE_V5', velocityWeights: 'DERIVED_FROM_ACTUAL_POSE_DERIVATIVES'},
  perception: {...copy(base.perception), guidedStartFrame: guided.startFrame, guidedEndFrame: deceleration.endFrame},
  hold: {startFrame: hold.startFrame, endFrame: hold.endFrame, drift: false}, checkpoints,
  compatibility: {publicCameraPlanVersion: 'CAMERA_DIRECTOR_V4', evaluationAPI: 'evaluateMinimumContextCameraFrame', revealAlgorithm: 'UNCHANGED'},
  protections: {...copy(base.protections), minimumContextOwnership: 'CAMERA_DIRECTOR_V5_ONLY', naturalTurnaroundOwnership: 'CAMERA_DIRECTOR_V5_ONLY'},
 };
}

/** Compatible CameraPlan shape with V5-owned continuous camera mathematics. */
export function compileMinimumContextPlan({scene, intent = null, profile = {}, seed = 0, relationGeometry = []} = {}) {
 const request = intent ?? compileMinimumContextIntent(scene, {relationGeometry});
 if (request.directorVersion !== CAMERA_DIRECTOR_V5_VERSION || request.intentVersion !== CAMERA_INTENT_V5_VERSION)
  throw Error('CAMERA_V5_MINIMUM_CONTEXT_INTENT_REQUIRED');
 const plan = compileReferenceCameraPlan({intent: request, profile, seed});
 return freeze(compileNaturalMotion(plan));
}

export function evaluateMinimumContextCameraFrame(plan, frame) {
 if (plan?.directorVersion !== CAMERA_DIRECTOR_V5_VERSION) throw Error('CAMERA_V5_PLAN_REQUIRED');
 if (!Number.isInteger(frame) || frame < 0 || frame >= plan.totalFrames) throw Error('CAMERA_REFERENCE_FRAME_OUT_OF_RANGE');
 if (!plan.naturalMotion) return {...evaluateReferenceCameraFrame(plan, frame), directorVersion: CAMERA_DIRECTOR_V5_VERSION};
 const n = plan.naturalMotion, final = frame >= n.arrivalFrame, initial = frame <= n.startFrame;
 let values, v = zeroVector(), a = zeroVector(), bounds;
 if (initial) { bounds = [...plan.intent.startExtent]; values = poseVector(bounds); }
 else if (final) { bounds = [...plan.intent.finalExtent]; values = poseVector(bounds); }
 else {
  const seconds = (frame - n.startFrame) / plan.fps, segment = n.segments.find(s => seconds <= s.endSeconds) ?? n.segments.at(-1);
  const pose = splineAt(segment, seconds); values = pose.values; v = pose.velocity; a = pose.acceleration;
  const width = Math.exp(values[2]), height = Math.exp(values[3]);
  bounds = frame === n.peakFrame ? [...plan.intent.contextExtent] :
   [values[0] - width / 2, values[1] - height / 2, values[0] + width / 2, values[1] + height / 2];
 }
 const output = plan.canonicalOutput, size = spans(bounds), c = values.slice(0, 2);
 const project = p => [(p[0] - bounds[0]) / size[0] * output[0], (bounds[3] - p[1]) / size[1] * output[1]];
 const speed = p => {
  const x = output[0] / size[0] * (-v[0] - (p[0] - c[0]) * v[2]);
  const y = output[1] / size[1] * (v[1] + (p[1] - c[1]) * v[3]);
  return {xPixelsPerSecond: x, yPixelsPerSecond: y, pixelsPerSecond: Math.hypot(x, y)};
 };
 const primary = plan.intent.primaryBounds, pa = project([primary[0], primary[3]]), pb = project([primary[2], primary[1]]);
 const primaryBox = [...pa, ...pb], anchor = project(plan.anchor), safe = plan.intent.display.safeArea;
 const inSafe = anchor[0] >= safe[0] && anchor[0] <= safe[2] && anchor[1] >= safe[1] && anchor[1] <= safe[3];
 const primarySpeed = speed(center(primary)), eventSpeed = speed(plan.anchor);
 const panRate = Math.hypot(v[0] / size[0], v[1] / size[1]), zoomRate = Math.hypot(v[2], v[3]) / Math.SQRT2, rate = panRate + zoomRate;
 const state = plan.timeline.find(s => frame >= s.startFrame && frame < s.endFrame), lock = plan.timeline.find(s => s.state === 'LOCK');
 const progress = clamp((frame - n.startFrame) / (n.arrivalFrame - n.startFrame));
 const contextCenter = center(plan.intent.contextExtent), startCenter = center(plan.intent.startExtent), finalCenter = center(plan.intent.finalExtent);
 const reference = spans(plan.intent.contextExtent), distance = (a, b) => Math.hypot((a[0] - b[0]) / reference[0], (a[1] - b[1]) / reference[1]);
 const firstPan = n.peakFrame === null ? 0 : distance(startCenter, contextCenter);
 const totalPan = firstPan + distance(n.peakFrame === null ? startCenter : contextCenter, finalCenter);
 const travelledPan = n.peakFrame !== null && frame <= n.peakFrame ? distance(startCenter, c) :
  firstPan + distance(n.peakFrame === null ? startCenter : contextCenter, c);
 const panProgress = frame >= n.panArrivalFrame ? 1 : totalPan > 1e-12 ? clamp(travelledPan / totalPan) : 0;
 const fromSize = spans(plan.intent.contextExtent), finalSize = spans(plan.intent.finalExtent), denominator = Math.log(fromSize[0] / finalSize[0]);
 const visible = actualPrimaryArea(plan.intent.primaryGeometry, bounds) > 1e-12;
 return {version: 'CAMERA_DIRECTOR_V4', directorVersion: CAMERA_DIRECTOR_V5_VERSION, frame, timeSeconds: frame / plan.fps,
  state: state.state, stateKey: state.key, stateFrame: frame - state.startFrame,
  stateProgress: (frame - state.startFrame) / Math.max(1, state.durationFrames - 1),
  scale: final ? plan.intent.effectiveScale : 'CONTINENT', projection: plan.projection.name, target: 'EVENT_LOCATION',
  targetGeometryIds: [plan.intent.primaryRegionId], center: c, extent: [...bounds], geographicCenter: [...c], geographicExtent: [...bounds],
  velocity: {longitudeDegreesPerSecond: v[0], latitudeDegreesPerSecond: v[1], logWidthPerSecond: v[2], logHeightPerSecond: v[3]},
  acceleration: {longitudeDegreesPerSecondSquared: a[0], latitudeDegreesPerSecondSquared: a[1], logWidthPerSecondSquared: a[2], logHeightPerSecondSquared: a[3]},
  easingProgress: denominator > 1e-9 ? clamp(Math.log(fromSize[0] / size[0]) / denominator) : 1,
  motionProgress: progress, panProgress, zoomProgress: denominator > 1e-9 ? clamp(Math.log(fromSize[0] / size[0]) / denominator) : 1,
  panWeight: rate ? panRate / rate : 0, zoomWeight: rate ? zoomRate / rate : 0,
  screenVelocity: {primary: primarySpeed, event: eventSpeed, pixelsPerSecond: Math.max(primarySpeed.pixelsPerSecond, eventSpeed.pixelsPerSecond)},
  projectedRegion: {box: primaryBox, width: pb[0] - pa[0], height: pb[1] - pa[1], area: (pb[0] - pa[0]) * (pb[1] - pa[1]),
   visible, geometryVisible: visible, geometryVisibleInSafe: actualPrimaryArea(plan.intent.primaryGeometry, safeViewport(bounds, plan.intent.display)) > 1e-12,
   fitsSafe: primaryBox[0] >= safe[0] && primaryBox[1] >= safe[1] && primaryBox[2] <= safe[2] && primaryBox[3] <= safe[3]},
  projectedAnchor: {position: anchor, inFrame: anchor[0] >= 0 && anchor[0] <= output[0] && anchor[1] >= 0 && anchor[1] <= output[1], inSafe},
  settle: {phase: state.state, settled: frame >= lock.startFrame, locked: frame >= lock.startFrame},
  camera: {flatBounds: [...bounds], noCloserThanApprovedStop: true}, cameraLocked: final, primaryMaterial: 1,
  admission: copy(plan.admission), geographicAnchor: [...plan.anchor], layoutLocked: final,
  transition: {active: false, method: 'NONE', mix: 0}};
}
