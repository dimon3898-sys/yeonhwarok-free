/** Pure integer-frame Event controls. Existing Camera/Scale remain read-only owners. */
import {assertEventIntent, freezeEventData} from './event_contract_v1.mjs';
import {SCALE_NAMES} from './scale_contract.mjs';
import {assertLocalDetailAdmission} from './local_detail_admission.mjs';

export const EVENT_TIMELINE_V1_VERSION = 'EVENT_TIMELINE_V1';
export const EVENT_STATES_V1 = Object.freeze(['EVENT_READY', 'LINE_REVEAL', 'LINE_HOLD', 'METRIC_REVEAL', 'INFORMATION_HOLD']);
const counts = Object.freeze({ready_frames: 1, line_reveal_frames: 2, line_hold_frames: 0,
 metric_reveal_frames: 2, information_hold_frames: 1});
function integer(value, label, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error(`EVENT_${label}_INTEGER_REQUIRED`);
 return value;
}
function profileRecord(profile) {
 if (!profile || typeof profile !== 'object' || Array.isArray(profile)) throw Error('EVENT_PROFILE_REQUIRED');
 if (Object.keys(profile).some(key => !Object.hasOwn(counts, key))) throw Error('EVENT_UNKNOWN_PROFILE_FIELD');
 const result = {};
 for (const [name, minimum] of Object.entries(counts)) result[name] = integer(profile[name], name.toUpperCase(), minimum);
 return result;
}
function seedValue(seed) {
 if (!Number.isSafeInteger(seed)) throw Error('EVENT_SEED_INTEGER_REQUIRED');
 return seed;
}

/** All durations are explicit data. Absent primitives omit their beats. */
export function compileEventPlan(intent, {fps, profile, seed = 0} = {}) {
 const data = assertEventIntent(intent), p = profileRecord(profile);
 integer(fps, 'FPS', 1); seedValue(seed);
 const timeline = []; let cursor = 0;
 function add(state, durationFrames) {
  if (durationFrames === 0) return;
  const end = integer(cursor + durationFrames, 'TOTAL_FRAMES', 1);
  timeline.push({state, startFrame: cursor, endFrame: end, durationFrames}); cursor = end;
 }
 add('EVENT_READY', p.ready_frames);
 if (data.line) { add('LINE_REVEAL', p.line_reveal_frames); add('LINE_HOLD', p.line_hold_frames); }
 if (data.metric) add('METRIC_REVEAL', p.metric_reveal_frames);
 add('INFORMATION_HOLD', p.information_hold_frames);
 return freezeEventData({version: EVENT_TIMELINE_V1_VERSION, intent: data, fps, seed, profile: p,
  totalFrames: cursor, durationSeconds: cursor / fps, timeline,
  ownership: {camera: 'READ_ONLY', scale: 'READ_ONLY', metric: 'SUPPLIED_FIXED_VALUE'}});
}
export function assertEventPlan(plan) {
 if (plan?.version !== EVENT_TIMELINE_V1_VERSION) throw Error('EVENT_PLAN_VERSION_REQUIRED');
 const canonical = compileEventPlan(plan.intent, {fps: plan.fps, profile: plan.profile, seed: plan.seed});
 if (JSON.stringify(canonical) !== JSON.stringify(plan)) throw Error('EVENT_PLAN_NON_CANONICAL');
 return canonical;
}
function box(value, label) {
 if (!Array.isArray(value) || value.length !== 4 || !value.every(Number.isFinite)
  || !(value[0] < value[2] && value[1] < value[3])) throw Error(`EVENT_${label}_RECTANGLE_REQUIRED`);
 return [...value];
}
function projected(value, project) {
 const result = project([...value]);
 if (!Array.isArray(result) || result.length !== 2 || !result.every(Number.isFinite))
  throw Error('EVENT_PROJECTION_POINT_REQUIRED');
 return [...result];
}
const inside = (point, safe) => point[0] >= safe[0] && point[1] >= safe[1] && point[0] <= safe[2] && point[1] <= safe[3];

/** Readiness is checked on every random-access frame, with no hidden prior state. */
export function evaluateEventReadiness(intent, {cameraState, project, safeArea, scalePlan, heightSource,
 protectedBoxes = []} = {}) {
 const data = assertEventIntent(intent), safe = box(safeArea, 'SAFE_AREA');
 if (!cameraState || !SCALE_NAMES.includes(cameraState.scale)) throw Error('EVENT_ADMITTED_CAMERA_SCALE_REQUIRED');
 if (cameraState.cameraLocked !== true || cameraState.settle?.locked !== true)
  throw Error('EVENT_GEOGRAPHIC_ARRIVAL_REQUIRED');
 if (typeof cameraState.projection !== 'string' || !cameraState.projection.trim())
  throw Error('EVENT_CAMERA_GEOGRAPHIC_TRANSFORM_REQUIRED');
 const geographicBounds = box(cameraState.camera?.flatBounds, 'CAMERA_GEOGRAPHIC_TRANSFORM');
 if (geographicBounds[0] < -180 || geographicBounds[2] > 180 || geographicBounds[1] < -90 || geographicBounds[3] > 90)
  throw Error('EVENT_CAMERA_GEOGRAPHIC_TRANSFORM_REQUIRED');
 if (!['LOCAL_ADMITTED', 'LOCAL_NOT_ADMITTED'].includes(cameraState.admission?.status))
  throw Error('EVENT_CAMERA_SCALE_ADMISSION_REQUIRED');
 if (cameraState.admission.effectiveScale !== cameraState.scale)
  throw Error('EVENT_CAMERA_SCALE_ADMISSION_MISMATCH');
 if (cameraState.scale === 'LOCAL') {
  if (cameraState.admission?.status !== 'LOCAL_ADMITTED' || cameraState.admission?.localUsed !== true
   || scalePlan?.scale?.name !== 'LOCAL') throw Error('EVENT_LOCAL_NOT_ADMITTED');
  // Reuse the existing complete source/binding admission check, not a new policy.
  assertLocalDetailAdmission(scalePlan, heightSource);
 } else if (cameraState.admission?.localUsed === true) {
  throw Error('EVENT_CAMERA_SCALE_ADMISSION_MISMATCH');
 }
 if (typeof project !== 'function') throw Error('EVENT_EXISTING_PROJECTION_REQUIRED');
 if (!Array.isArray(protectedBoxes)) throw Error('EVENT_PROTECTED_BOXES_REQUIRED');
 const protectedCopy = protectedBoxes.map(item => box(item, 'PROTECTED_BOX'));
 const geometry = data.line ? data.line.geometry.coordinates.map(point => projected(point, project)) : [];
 const anchors = [data.line?.anchor, data.metric?.anchor].filter(Boolean).map(point => projected(point, project));
 if (!geometry.every(point => inside(point, safe))) throw Error('EVENT_GEOMETRY_OUTSIDE_SAFE_AREA');
 if (!anchors.every(point => inside(point, safe))) throw Error('EVENT_ANCHOR_OUTSIDE_SAFE_AREA');
 return freezeEventData({status: 'EVENT_READY', scale: cameraState.scale, projection: cameraState.projection,
  safeArea: safe, protectedBoxes: protectedCopy, projectedGeometry: geometry, projectedAnchors: anchors,
  cameraOwnership: 'READ_ONLY', productionEligible: data.data_mode === 'PRODUCTION'});
}

const fraction = (frame, beat) => frame < beat.startFrame ? 0 : frame >= beat.endFrame ? 1
 : (frame - beat.startFrame) / (beat.durationFrames - 1);
export function evaluateEventFrame(plan, frame, context = {}) {
 const p = assertEventPlan(plan); integer(frame, 'FRAME');
 if (frame >= p.totalFrames) throw Error('EVENT_FRAME_OUT_OF_RANGE');
 const readiness = evaluateEventReadiness(p.intent, context);
 const beat = p.timeline.find(item => frame >= item.startFrame && frame < item.endFrame);
 const line = p.timeline.find(item => item.state === 'LINE_REVEAL');
 const metric = p.timeline.find(item => item.state === 'METRIC_REVEAL');
 return freezeEventData({version: EVENT_TIMELINE_V1_VERSION, frame, timeSeconds: frame / p.fps,
  state: beat.state, stateFrame: frame - beat.startFrame,
  stateProgress: beat.durationFrames === 1 ? 1 : (frame - beat.startFrame) / (beat.durationFrames - 1),
  lineFraction: line ? fraction(frame, line) : null, metricFraction: metric ? fraction(frame, metric) : null,
  lineActive: Boolean(line && frame >= line.startFrame), metricActive: Boolean(metric && frame >= metric.startFrame),
  metricValue: p.intent.metric?.display_value ?? null, metricUnit: p.intent.metric?.unit ?? null,
  dataMode: p.intent.data_mode, productionEligible: p.intent.data_mode === 'PRODUCTION', readiness});
}
