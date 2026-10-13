/** Continuous complementary control over unchanged supplied land; no story or camera owner. */
import {freezeEventData, validateEventAnchor} from './event_contract_v1.mjs';
import {areaGeometryCoordinates} from './area_core_v3.mjs';
import {detailSmootherstep} from './camera_detail_approach_adapter_v1.mjs';

export const TERRITORY_CONTROL_INTENT_V1_VERSION = 'TERRITORY_CONTROL_INTENT_V1';
export const TERRITORY_CONTROL_PLAN_V1_VERSION = 'TERRITORY_CONTROL_PLAN_V1';
export const TERRITORY_CONTROL_FRAME_V1_VERSION = 'TERRITORY_CONTROL_FRAME_V1';
export const TERRITORY_CONTROL_MAX_LONGITUDINAL_KNOTS = 64;
const knownIntents = new WeakSet(), knownPlans = new WeakSet(), knownFrames = new WeakSet();
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b), copy = value => structuredClone(value);
const epsilon = 1e-10;
function record(value, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error(`CONTROL_${label}_OBJECT_REQUIRED`);
 return value;
}
function text(value, label) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value)) throw Error(`CONTROL_${label}_TEXT_REQUIRED`);
 return value;
}
function integer(value, label, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error(`CONTROL_${label}_INTEGER_REQUIRED`);
 return value;
}
function sourceRecord(value) {
 const source = record(value, 'SOURCE');
 return {source_type: text(source.source_type, 'SOURCE_TYPE'),
  source_reference: text(source.source_reference, 'SOURCE_REFERENCE'),
  verification_status: text(source.verification_status, 'SOURCE_VERIFICATION')};
}
function domainRecord(value) {
 const domain = record(value, 'DOMAIN'), geometry = copy(record(domain.geometry, 'DOMAIN_GEOMETRY'));
 if (!['Polygon', 'MultiPolygon'].includes(geometry.type)) throw Error('CONTROL_POLYGON_DOMAIN_REQUIRED');
 const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
 if (!Array.isArray(polygons) || !polygons.length) throw Error('CONTROL_DOMAIN_PART_REQUIRED');
 for (const polygon of polygons) {
  if (!Array.isArray(polygon) || !polygon.length) throw Error('CONTROL_DOMAIN_OUTER_RING_REQUIRED');
  for (const ring of polygon) {
   if (!Array.isArray(ring) || ring.length < 4 || !same(ring[0], ring.at(-1))) throw Error('CONTROL_CLOSED_DOMAIN_RING_REQUIRED');
   for (let index = 0; index < ring.length; index++) {
    validateEventAnchor(ring[index], 'CONTROL_DOMAIN_VERTEX');
    if (index && Math.abs(ring[index][0] - ring[index - 1][0]) > 180) throw Error('CONTROL_WRAPPED_DOMAIN_UNSUPPORTED');
   }
  }
 }
 // Reuse the Area coordinate reader; do not repair, simplify, reorder or regenerate native topology.
 areaGeometryCoordinates(geometry);
 return {id: text(domain.id, 'DOMAIN_ID'), geometry};
}
function factionRecord(value, label) {
 const faction = record(value, label);
 return {id: text(faction.id, `${label}_ID`), ...(faction.label === undefined ? {} : {label: text(faction.label, `${label}_LABEL`)})};
}
function latitudeProfile(value, count, label) {
 if (!Array.isArray(value) || value.length !== count || !value.every(v => Number.isFinite(v) && v >= -90 && v <= 90))
  throw Error(`CONTROL_${label}_LATITUDES_REQUIRED`);
 return [...value];
}

/** Data-owned piecewise longitudinal boundary. Source land geometry remains byte-for-byte comparable. */
export function compileTerritoryControlIntent(input) {
 const value = record(input, 'INPUT');
 if (value.version !== undefined && value.version !== TERRITORY_CONTROL_INTENT_V1_VERSION) throw Error('CONTROL_INTENT_VERSION_REQUIRED');
 const semanticMode = value.semantic_mode;
 if (!['REFERENCE_VISUAL_STUDY', 'FACT_BASED_VISUAL_CONTROL'].includes(semanticMode)) throw Error('CONTROL_EXPLICIT_SEMANTIC_MODE_REQUIRED');
 const fps = integer(value.fps, 'FPS', 1), totalFrames = integer(value.total_frames, 'TOTAL_FRAMES', 2);
 const startFrame = integer(value.start_frame ?? 0, 'START_FRAME');
 if (!Array.isArray(value.domain) || !value.domain.length) throw Error('CONTROL_DOMAIN_ARRAY_REQUIRED');
 const domain = value.domain.map(domainRecord);
 if (new Set(domain.map(item => item.id)).size !== domain.length) throw Error('CONTROL_DUPLICATE_DOMAIN_ID');
 const factionsInput = record(value.factions, 'FACTIONS'), factions = {
  winner: factionRecord(factionsInput.winner, 'WINNER'), loser: factionRecord(factionsInput.loser, 'LOSER')};
 if (factions.winner.id === factions.loser.id) throw Error('CONTROL_DISTINCT_FACTIONS_REQUIRED');
 const longitudinalKnots = value.longitudinal_knots;
 if (!Array.isArray(longitudinalKnots) || longitudinalKnots.length < 2
  || longitudinalKnots.length > TERRITORY_CONTROL_MAX_LONGITUDINAL_KNOTS
  || !longitudinalKnots.every((v, index) => Number.isFinite(v) && v >= -180 && v <= 180
   && (index === 0 || v > longitudinalKnots[index - 1]))) throw Error('CONTROL_INCREASING_LONGITUDINAL_KNOTS_REQUIRED');
 let minimumLongitude = Infinity, maximumLongitude = -Infinity;
 for (const item of domain) for (const point of areaGeometryCoordinates(item.geometry)) {
  minimumLongitude = Math.min(minimumLongitude, point[0]); maximumLongitude = Math.max(maximumLongitude, point[0]);
 }
 if (longitudinalKnots[0] > minimumLongitude || longitudinalKnots.at(-1) < maximumLongitude)
  throw Error('CONTROL_LONGITUDINAL_PROFILE_MUST_COVER_DOMAIN');
 const baseBoundaryLatitudes = latitudeProfile(value.base_boundary_latitudes, longitudinalKnots.length, 'BASE_BOUNDARY');
 const advanceDirection = value.advance_direction;
 if (!['POSITIVE_LATITUDE', 'NEGATIVE_LATITUDE'].includes(advanceDirection)) throw Error('CONTROL_ADVANCE_DIRECTION_REQUIRED');
 const sign = advanceDirection === 'POSITIVE_LATITUDE' ? 1 : -1;
 if (!Array.isArray(value.boundary_keyframes) || value.boundary_keyframes.length < 2) throw Error('CONTROL_BOUNDARY_KEYFRAMES_REQUIRED');
 const boundaryKeyframes = value.boundary_keyframes.map(keyframe => ({
  frame: integer(record(keyframe, 'KEYFRAME').frame, 'KEYFRAME_FRAME'),
  latitudes: latitudeProfile(keyframe.latitudes, longitudinalKnots.length, 'KEYFRAME_BOUNDARY')}));
 if (boundaryKeyframes[0].frame !== 0 || boundaryKeyframes.at(-1).frame !== totalFrames - 1)
  throw Error('CONTROL_KEYFRAME_ENDPOINT_BINDING_REQUIRED');
 for (let index = 0; index < boundaryKeyframes.length; index++) {
  const current = boundaryKeyframes[index], previous = index ? boundaryKeyframes[index - 1] : {latitudes: baseBoundaryLatitudes};
  if (index && current.frame <= previous.frame) throw Error('CONTROL_INCREASING_KEYFRAME_FRAMES_REQUIRED');
  if (current.latitudes.some((latitude, knot) => sign * (latitude - previous.latitudes[knot]) < 0))
   throw Error('CONTROL_BOUNDARY_MUST_ADVANCE_MONOTONICALLY');
 }
 const interpolation = value.interpolation ?? 'LINEAR';
 if (!['LINEAR', 'SMOOTHERSTEP'].includes(interpolation)) throw Error('CONTROL_INTERPOLATION_REQUIRED');
 const intent = freezeEventData({version: TERRITORY_CONTROL_INTENT_V1_VERSION, semantic_mode: semanticMode,
  source: sourceRecord(value.source), domain, factions, longitudinal_knots: [...longitudinalKnots],
  base_boundary_latitudes: baseBoundaryLatitudes, boundary_keyframes: boundaryKeyframes,
  advance_direction: advanceDirection, start_frame: startFrame, total_frames: totalFrames, fps, interpolation});
 knownIntents.add(intent); return intent;
}

export function assertTerritoryControlIntent(intent) {
 if (knownIntents.has(intent)) return intent;
 if (intent?.version !== TERRITORY_CONTROL_INTENT_V1_VERSION) throw Error('CONTROL_INTENT_VERSION_REQUIRED');
 const canonical = compileTerritoryControlIntent(intent);
 if (!same(canonical, intent)) throw Error('CONTROL_INTENT_NON_CANONICAL');
 return canonical;
}

/** Minimal Area extension: one shared ownership field, not two independently animated polygon fills. */
export function compileTerritoryControlPlan(input) {
 const intent = input?.version === TERRITORY_CONTROL_INTENT_V1_VERSION ? assertTerritoryControlIntent(input)
  : compileTerritoryControlIntent(input);
 const plan = freezeEventData({version: TERRITORY_CONTROL_PLAN_V1_VERSION, intent,
  startFrame: intent.start_frame, totalFrames: intent.total_frames, fps: intent.fps,
  durationSeconds: intent.total_frames / intent.fps,
  domainGeometryBinding: JSON.stringify(intent.domain), boundaryKeyframeBinding: JSON.stringify({
   longitudinalKnots: intent.longitudinal_knots, baseBoundaryLatitudes: intent.base_boundary_latitudes,
   boundaryKeyframes: intent.boundary_keyframes, advanceDirection: intent.advance_direction,
   interpolation: intent.interpolation}),
  ownership: {domain: 'UNCHANGED_SOURCE_LAND_GEOMETRY', control: 'ONE_COMPLEMENTARY_GEOGRAPHIC_FIELD',
   camera: 'EXTERNAL_CAMERA_ADAPTER', finalCores: 'READ_ONLY', physicalSimulation: false,
   routeVisuals: false, standaloneFrontLine: false}});
 knownPlans.add(plan); return plan;
}

export function assertTerritoryControlPlan(plan) {
 if (knownPlans.has(plan)) return plan;
 if (plan?.version !== TERRITORY_CONTROL_PLAN_V1_VERSION) throw Error('CONTROL_PLAN_VERSION_REQUIRED');
 const canonical = compileTerritoryControlPlan(plan.intent);
 if (!same(canonical, plan)) throw Error('CONTROL_PLAN_NON_CANONICAL');
 return canonical;
}

/** Frame is an absolute integer; keyframe time is relative to startFrame, with no accumulated mutable state. */
export function evaluateTerritoryControlFrame(plan, frame) {
 const p = assertTerritoryControlPlan(plan); integer(frame, 'FRAME');
 const relative = frame - p.startFrame;
 if (relative < 0 || relative >= p.totalFrames) throw Error('CONTROL_FRAME_OUT_OF_RANGE');
 const keys = p.intent.boundary_keyframes;
 let keyIndex = keys.findIndex((key, index) => index < keys.length - 1 && relative >= key.frame && relative < keys[index + 1].frame);
 if (keyIndex < 0) keyIndex = keys.length - 2;
 const first = keys[keyIndex], second = keys[keyIndex + 1], fraction = (relative - first.frame) / (second.frame - first.frame);
 const t = p.intent.interpolation === 'SMOOTHERSTEP' ? detailSmootherstep(fraction) : fraction;
 const boundaryLatitudes = fraction === 0 ? [...first.latitudes] : fraction === 1 ? [...second.latitudes]
  : first.latitudes.map((latitude, knot) => latitude + (second.latitudes[knot] - latitude) * t);
 const controls = freezeEventData({version: TERRITORY_CONTROL_FRAME_V1_VERSION, frame, localFrame: relative,
  timeSeconds: relative / p.fps, progress: relative / (p.totalFrames - 1),
  semanticMode: p.intent.semantic_mode, landDomain: p.intent.domain, factions: p.intent.factions,
  longitudinalKnots: p.intent.longitudinal_knots, baseBoundaryLatitudes: p.intent.base_boundary_latitudes,
  boundaryLatitudes, advanceDirection: p.intent.advance_direction,
  advanceSign: p.intent.advance_direction === 'POSITIVE_LATITUDE' ? 1 : -1,
  keyframeInterval: {startFrame: first.frame + p.startFrame, endFrame: second.frame + p.startFrame, fraction},
  domainGeometryBinding: p.domainGeometryBinding, boundaryKeyframeBinding: p.boundaryKeyframeBinding,
  geometryUnchanged: true, physicalSimulation: false, routeVisuals: false, standaloneFrontLine: false});
 knownFrames.add(controls); return controls;
}

function frameControls(value, frame) {
 if (knownFrames.has(value)) return value;
 if (value?.version === TERRITORY_CONTROL_PLAN_V1_VERSION) {
  if (frame === undefined) throw Error('CONTROL_PLAN_CLASSIFICATION_FRAME_REQUIRED');
  return evaluateTerritoryControlFrame(value, frame);
 }
 // Classifier consumes trusted evaluated frames only; a mutable copy cannot spoof source binding.
 throw Error('CONTROL_EVALUATED_FRAME_REQUIRED');
}

/** Same interpolation is used by the CPU oracle and material shader. Longitude never changes geometry. */
export function sampleControlBoundary(planOrFrame, longitude, {kind = 'moving', frame} = {}) {
 const controls = frameControls(planOrFrame, frame);
 if (!Number.isFinite(longitude) || !['base', 'moving'].includes(kind)) throw Error('CONTROL_BOUNDARY_SAMPLE_REQUIRED');
 const knots = controls.longitudinalKnots, latitudes = kind === 'base' ? controls.baseBoundaryLatitudes : controls.boundaryLatitudes;
 if (longitude <= knots[0]) return latitudes[0];
 if (longitude >= knots.at(-1)) return latitudes.at(-1);
 const index = knots.findIndex((value, i) => i < knots.length - 1 && longitude >= value && longitude <= knots[i + 1]);
 const fraction = (longitude - knots[index]) / (knots[index + 1] - knots[index]);
 return latitudes[index] + (latitudes[index + 1] - latitudes[index]) * fraction;
}

function ringContains(point, ring) {
 let inside = false;
 for (let index = 0; index < ring.length - 1; index++) {
  const a = ring[index], b = ring[index + 1], cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]);
  if (Math.abs(cross) <= epsilon && point[0] >= Math.min(a[0], b[0]) - epsilon
   && point[0] <= Math.max(a[0], b[0]) + epsilon && point[1] >= Math.min(a[1], b[1]) - epsilon
   && point[1] <= Math.max(a[1], b[1]) + epsilon) return true;
  if ((a[1] > point[1]) !== (b[1] > point[1])
   && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function geometryContains(point, geometry) {
 const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
 return polygons.some(polygon => ringContains(point, polygon[0]) && !polygon.slice(1).some(hole => ringContains(point, hole)));
}

/** Verification oracle, not a renderer or clipping engine. Every land point has exactly one owner. */
export function classifyControlPoint(planOrFrame, point, {frame} = {}) {
 const controls = frameControls(planOrFrame, frame), geographicPoint = validateEventAnchor(point, 'CONTROL_CLASSIFICATION_POINT');
 const domainIds = controls.landDomain.filter(domain => geometryContains(geographicPoint, domain.geometry)).map(domain => domain.id);
 const inDomain = domainIds.length > 0;
 if (!inDomain) return freezeEventData({inDomain: false, domainIds: [], owner: null,
  region: 'OUTSIDE_DOMAIN', winner: false, loser: false, newlyGained: false});
 const boundaryLatitude = sampleControlBoundary(controls, geographicPoint[0]),
  baseLatitude = sampleControlBoundary(controls, geographicPoint[0], {kind: 'base'}),
  winner = controls.advanceSign * (geographicPoint[1] - boundaryLatitude) <= 0,
  existingWinner = controls.advanceSign * (geographicPoint[1] - baseLatitude) <= 0,
  newlyGained = winner && !existingWinner;
 return freezeEventData({inDomain, domainIds, owner: winner ? controls.factions.winner.id : controls.factions.loser.id,
  region: winner ? newlyGained ? 'WINNER_GAINED' : 'WINNER_EXISTING' : 'LOSER',
  winner, loser: !winner, newlyGained, boundaryLatitude, baseLatitude});
}
