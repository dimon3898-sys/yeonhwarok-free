/** Flow data and integer-frame controls. Camera, projection and graphics remain external owners. */
import {compileEventIntent, freezeEventData, validateEventAnchor} from './event_contract_v1.mjs';
import {compileEventPlan, evaluateEventFrame} from './event_timeline_v1.mjs';
import {compileGeographicLinePrimitive, assertGeographicLinePrimitive,
 evaluateGeographicLineReveal} from './event_line_v1.mjs';

export const FLOW_INTENT_V2_VERSION = 'FLOW_INTENT_V2';
export const FLOW_PLAN_V2_VERSION = 'FLOW_PLAN_V2';
export const FLOW_STATES_V2 = Object.freeze(['FLOW_READY', 'ROUTE_REVEAL', 'DIRECTIONAL_FLOW',
 'MOVING_OBJECT', 'ENDPOINT_PULSE', 'ROUTE_HOLD']);
const defaults = Object.freeze({fps: 30, start_frame: 0, reveal_frames: 32,
 direction_start_frame: 12, object_start_frame: 20, travel_frames: 108,
 departure_pulse_frames: 14, arrival_pulse_frames: 18, hold_frames: 34});
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const clamp = value => Math.max(0, Math.min(1, value));
const smootherstep = value => value * value * value * (value * (value * 6 - 15) + 10);
function record(value, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error(`FLOW_${label}_OBJECT_REQUIRED`);
 return value;
}
function text(value, label) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value))
  throw Error(`FLOW_${label}_TEXT_REQUIRED`);
 return value;
}
function integer(value, label, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error(`FLOW_${label}_INTEGER_REQUIRED`);
 return value;
}
function graphicRecord(input) {
 const given = record(input, 'OBJECT_GRAPHIC');
 for (const key of ['width_px', 'height_px'])
  if (!Number.isFinite(given[key]) || given[key] <= 0) throw Error(`FLOW_OBJECT_${key.toUpperCase()}_POSITIVE_REQUIRED`);
 if (!Array.isArray(given.polygons) || !given.polygons.length) throw Error('FLOW_OBJECT_POLYGONS_REQUIRED');
 const polygons = given.polygons.map(value => {
  const polygon = record(value, 'OBJECT_POLYGON');
  if (!Array.isArray(polygon.points) || polygon.points.length < 3) throw Error('FLOW_OBJECT_POLYGON_POINTS_REQUIRED');
  const points = polygon.points.map(point => {
   if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
    || point.some(coordinate => coordinate < -.5 || coordinate > .5)) throw Error('FLOW_OBJECT_NORMALIZED_POINT_REQUIRED');
   return [...point];
  });
  // Nonzero signed area rejects an invisible polygon while retaining authored vertices.
  const area = points.reduce((sum, point, index) => {
   const next = points[(index + 1) % points.length]; return sum + point[0] * next[1] - point[1] * next[0];
  }, 0);
  if (Math.abs(area) <= Number.EPSILON) throw Error('FLOW_OBJECT_POLYGON_AREA_REQUIRED');
  if (!Array.isArray(polygon.color) || polygon.color.length !== 4
   || !polygon.color.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1)
   || polygon.color[3] <= 0) throw Error('FLOW_OBJECT_RGBA_COLOR_REQUIRED');
  return {points, color: [...polygon.color]};
 });
 return {width_px: given.width_px, height_px: given.height_px, polygons};
}

/** Route provenance/geometry use the original V1 contract; object shape is fixture data. */
export function compileFlowIntent(input) {
 const given = record(input, 'INPUT');
 const route = compileEventIntent({data_mode: given.data_mode, line: {geometry: given.route_geometry,
  source: given.route_source, direction: given.direction, style_role: 'PRIMARY'}});
 const start = validateEventAnchor(given.start_anchor, 'FLOW_START_ANCHOR');
 const end = validateEventAnchor(given.end_anchor, 'FLOW_END_ANCHOR');
 const coordinates = route.line.geometry.coordinates;
 const directedStart = route.line.direction === 'FORWARD' ? coordinates[0] : coordinates.at(-1);
 const directedEnd = route.line.direction === 'FORWARD' ? coordinates.at(-1) : coordinates[0];
 if (!same(start, directedStart) || !same(end, directedEnd)) throw Error('FLOW_ANCHORS_MUST_MATCH_DIRECTED_ROUTE_ENDPOINTS');
 return freezeEventData({version: FLOW_INTENT_V2_VERSION, data_mode: route.data_mode,
  provenance_class: route.provenance_class, route_geometry: route.line.geometry, route_source: route.line.source,
  start_anchor: start, end_anchor: end, direction: route.line.direction,
  object_role: text(given.object_role, 'OBJECT_ROLE'), object_graphic: graphicRecord(given.object_graphic)});
}
export function assertFlowIntent(intent) {
 if (intent?.version !== FLOW_INTENT_V2_VERSION) throw Error('FLOW_INTENT_VERSION_REQUIRED');
 const canonical = compileFlowIntent(intent);
 if (!same(canonical, intent)) throw Error('FLOW_INTENT_NON_CANONICAL');
 return canonical;
}
function routeIntent(intent) {
 return compileEventIntent({data_mode: intent.data_mode, line: {geometry: intent.route_geometry,
  source: intent.route_source, direction: intent.direction, style_role: 'PRIMARY'}});
}
function timingRecord(options) {
 record(options, 'TIMING');
 if (Object.keys(options).some(key => !Object.hasOwn(defaults, key))) throw Error('FLOW_UNKNOWN_TIMING_FIELD');
 const timing = {...defaults, ...options};
 for (const [key, value] of Object.entries(timing)) {
  const minimum = ['fps', 'hold_frames'].includes(key) ? 1
   : ['reveal_frames', 'travel_frames'].includes(key) ? 2 : 0;
  integer(value, key.toUpperCase(), minimum);
 }
 for (const key of ['departure_pulse_frames', 'arrival_pulse_frames'])
  if (timing[key] === 1) throw Error('FLOW_PULSE_REQUIRES_ZERO_OR_AT_LEAST_TWO_FRAMES');
 if (timing.direction_start_frame < 1 || timing.direction_start_frame > timing.object_start_frame
  || timing.object_start_frame < 1) throw Error('FLOW_DIRECTION_MUST_FOLLOW_ROUTE_AND_PRECEDE_OBJECT');
 return timing;
}
function objectFractionAt(frame, timing) {
 return smootherstep(clamp((frame - timing.object_start_frame) / (timing.travel_frames - 1)));
}
function routeFractionAt(frame, timing) {
 return clamp((frame - 1) / (timing.reveal_frames - 1));
}

/** Overlap short introduction/reveal beats with travel rather than adding blank holds. */
export function compileFlowPlan(intent, options = {}) {
 const data = assertFlowIntent(intent), timing = timingRecord(options);
 const arrivalFrame = integer(timing.object_start_frame + timing.travel_frames, 'ARRIVAL_FRAME');
 const holdFrame = integer(arrivalFrame + timing.arrival_pulse_frames, 'HOLD_FRAME');
 const totalFrames = integer(holdFrame + timing.hold_frames, 'TOTAL_FRAMES', 1);
 const endFrame = integer(timing.start_frame + totalFrames, 'END_FRAME', 1);
 if (timing.departure_pulse_frames > timing.travel_frames) throw Error('FLOW_DEPARTURE_PULSE_MUST_FINISH_DURING_TRAVEL');
 if (totalFrames <= timing.reveal_frames + 1) throw Error('FLOW_ROUTE_REVEAL_MUST_FINISH_BEFORE_HOLD');
 for (let frame = timing.object_start_frame; frame < arrivalFrame; frame++)
  if (objectFractionAt(frame, timing) > routeFractionAt(frame, timing) + 1e-12)
   throw Error('FLOW_OBJECT_CANNOT_OVERTAKE_ROUTE_REVEAL');
 const routeEventPlan = compileEventPlan(routeIntent(data), {fps: timing.fps, profile: {ready_frames: 1,
  line_reveal_frames: timing.reveal_frames, line_hold_frames: 0, metric_reveal_frames: 2,
  information_hold_frames: totalFrames - 1 - timing.reveal_frames}});
 const timeline = [];
 const add = (state, start, end) => {
  if (end > start) timeline.push({state, startFrame: timing.start_frame + start,
   endFrame: timing.start_frame + end, durationFrames: end - start});
 };
 add('FLOW_READY', 0, 1);
 add('ROUTE_REVEAL', 1, timing.direction_start_frame);
 add('DIRECTIONAL_FLOW', timing.direction_start_frame, timing.object_start_frame);
 add('MOVING_OBJECT', timing.object_start_frame, arrivalFrame);
 add('ENDPOINT_PULSE', arrivalFrame, holdFrame);
 add('ROUTE_HOLD', holdFrame, totalFrames);
 return freezeEventData({version: FLOW_PLAN_V2_VERSION, intent: data, timing, fps: timing.fps,
  startFrame: timing.start_frame, endFrame, totalFrames, durationSeconds: totalFrames / timing.fps,
  arrivalFrame: timing.start_frame + arrivalFrame, holdFrame: timing.start_frame + holdFrame,
  timeline, routeEventPlan, ownership: {camera: 'READ_ONLY', scale: 'READ_ONLY', projection: 'EXISTING',
   objectGraphic: 'SUPPLIED_FIXTURE_DATA', motion: 'PROJECTED_ROUTE_ARC_LENGTH', physics: 'NONE'}});
}
export function assertFlowPlan(plan) {
 if (plan?.version !== FLOW_PLAN_V2_VERSION) throw Error('FLOW_PLAN_VERSION_REQUIRED');
 const canonical = compileFlowPlan(plan.intent, plan.timing);
 if (!same(canonical, plan)) throw Error('FLOW_PLAN_NON_CANONICAL');
 return canonical;
}

/** REVERSE is applied once by the original primitive compiler, never by Flow. */
export function compileFlowRoute(intent, {project} = {}) {
 return compileGeographicLinePrimitive(routeIntent(assertFlowIntent(intent)), {project});
}
function pointAt(primitive, fraction) {
 return fraction === 0 ? [...primitive.screenCoordinates[0]]
  : [...evaluateGeographicLineReveal(primitive, fraction).path.at(-1)];
}
function unwrap(raw, reference) {
 return raw + Math.round((reference - raw) / (Math.PI * 2)) * Math.PI * 2;
}
function headingReference(primitive, distance) {
 let previous = null, heading = 0, chosen = null;
 for (let index = 0; index < primitive.segmentLengthsPixels.length; index++) {
  if (primitive.segmentLengthsPixels[index] === 0) continue;
  const a = primitive.screenCoordinates[index], b = primitive.screenCoordinates[index + 1];
  const raw = Math.atan2(b[1] - a[1], b[0] - a[0]);
  heading = previous === null ? raw : unwrap(raw, previous);
  previous = heading;
  if (chosen === null && distance <= primitive.cumulativeLengthsPixels[index + 1]) chosen = heading;
 }
 return chosen ?? heading;
}

/** Sample exact supplied arc length; a symmetric secant smooths authored polyline corners. */
export function sampleFlowRoute(primitive, fraction, {lookAheadPixels = 12} = {}) {
 const route = assertGeographicLinePrimitive(primitive);
 if (!Number.isFinite(fraction) || fraction < 0 || fraction > 1) throw Error('FLOW_ROUTE_FRACTION_RANGE_REQUIRED');
 if (!Number.isFinite(lookAheadPixels) || lookAheadPixels <= 0) throw Error('FLOW_POSITIVE_HEADING_LOOKAHEAD_REQUIRED');
 const distancePixels = fraction * route.totalLengthPixels, offset = lookAheadPixels / route.totalLengthPixels;
 const before = pointAt(route, Math.max(0, fraction - offset));
 const after = pointAt(route, Math.min(1, fraction + offset));
 const dx = after[0] - before[0], dy = after[1] - before[1], length = Math.hypot(dx, dy);
 const reference = headingReference(route, distancePixels);
 const heading = length > 1e-12 ? unwrap(Math.atan2(dy, dx), reference) : reference;
 return freezeEventData({fraction, distancePixels, position: pointAt(route, fraction), heading,
  headingVector: [Math.cos(heading), Math.sin(heading)]});
}
function pulseAt(frame, startFrame, duration, anchor, size) {
 const active = duration > 0 && frame >= startFrame && frame < startFrame + duration;
 const progress = active ? (frame - startFrame) / (duration - 1) : frame < startFrame ? 0 : 1;
 const amplitude = active ? (progress === 0 || progress === 1 ? 0 : Math.sin(Math.PI * progress)) : 0;
 return {active, anchor: [...anchor], position: [...anchor], progress, amplitude,
  radius: size * (.18 + .5 * progress), alpha: amplitude};
}

/** Random-access controls require the unchanged V1 camera lock/admission/safe-area contract. */
export function evaluateFlowFrame(plan, frame, {primitive, eventContext} = {}) {
 const flow = assertFlowPlan(plan); integer(frame, 'FRAME');
 if (frame < flow.startFrame || frame >= flow.endFrame) throw Error('FLOW_FRAME_OUT_OF_RANGE');
 const localFrame = frame - flow.startFrame;
 const eventControls = evaluateEventFrame(flow.routeEventPlan, localFrame, eventContext);
 const route = primitive === undefined ? compileFlowRoute(flow.intent, {project: eventContext?.project})
  : assertGeographicLinePrimitive(primitive);
 if (!same(route.intent, flow.routeEventPlan.intent)
  || !same(route.screenCoordinates, flow.intent.direction === 'FORWARD'
   ? eventControls.readiness.projectedGeometry : [...eventControls.readiness.projectedGeometry].reverse()))
  throw Error('FLOW_ROUTE_MUST_BIND_CURRENT_INTENT_AND_PROJECTION');
 const objectFraction = objectFractionAt(localFrame, flow.timing);
 const headingLookAheadPixels = Math.max(12,
  Math.max(flow.intent.object_graphic.width_px, flow.intent.object_graphic.height_px) * .5);
 const object = sampleFlowRoute(route, objectFraction, {lookAheadPixels: headingLookAheadPixels});
 const objectVisible = localFrame >= flow.timing.object_start_frame;
 const directionalActive = localFrame >= flow.timing.direction_start_frame && frame < flow.arrivalFrame;
 const directionalFraction = Math.min(eventControls.lineFraction,
  objectFraction + Math.min(24, route.totalLengthPixels * .08) / route.totalLengthPixels);
 const directional = sampleFlowRoute(route, directionalFraction, {lookAheadPixels: headingLookAheadPixels});
 const size = Math.max(flow.intent.object_graphic.width_px, flow.intent.object_graphic.height_px);
 const departurePulse = pulseAt(localFrame, flow.timing.object_start_frame, flow.timing.departure_pulse_frames,
  route.screenCoordinates[0], size);
 const arrivalPulse = pulseAt(frame, flow.arrivalFrame, flow.timing.arrival_pulse_frames,
  route.screenCoordinates.at(-1), size);
 const pulse = arrivalPulse.active ? arrivalPulse : departurePulse;
 const beat = flow.timeline.find(item => frame >= item.startFrame && frame < item.endFrame);
 return freezeEventData({version: FLOW_PLAN_V2_VERSION, frame, localFrame, timeSeconds: frame / flow.fps,
  state: beat.state, stateFrame: frame - beat.startFrame,
  stateProgress: beat.durationFrames === 1 ? 1 : (frame - beat.startFrame) / (beat.durationFrames - 1),
  routeFraction: eventControls.lineFraction, routeActive: eventControls.lineActive,
  routeReveal: evaluateGeographicLineReveal(route, eventControls.lineFraction),
  directionalActive, directionalFraction, directionalPosition: directional.position,
  directionalHeading: directional.heading, objectVisible, movingObjectVisible: objectVisible,
  objectFraction, objectPosition: object.position, heading: object.heading, objectHeading: object.heading,
  headingVector: object.headingVector, headingLookAheadPixels, objectRole: flow.intent.object_role,
  departurePulse, arrivalPulse, pulse, complete: localFrame >= flow.timing.object_start_frame + flow.timing.travel_frames - 1,
  hold: frame >= flow.holdFrame, eventControls, dataMode: flow.intent.data_mode,
  productionEligible: flow.intent.data_mode === 'PRODUCTION'});
}
