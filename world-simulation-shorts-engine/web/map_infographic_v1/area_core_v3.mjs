/** Supplied geographical areas/states and visual progression; no camera, story or physical simulation. */
import {compileEventIntent, freezeEventData, validateEventAnchor} from './event_contract_v1.mjs';
import {compileGeographicLinePrimitive, evaluateGeographicLineReveal} from './event_line_v1.mjs';
import {sampleFlowRoute} from './flow_core_v2.mjs';

export const AREA_INTENT_V3_VERSION = 'AREA_INTENT_V3';
export const AREA_PLAN_V3_VERSION = 'AREA_PLAN_V3';
export const AREA_FRAME_V3_VERSION = 'AREA_FRAME_V3';
export const AREA_FEATURES_V3 = Object.freeze(['AREA_REVEAL', 'AREA_GROW', 'AREA_CONTRACT', 'AREA_MOVE',
 'AREA_HOLD', 'PROPAGATION_RING', 'PROPAGATION_WAVE', 'IMPACT_ZONE', 'FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP']);
const copy = value => structuredClone(value), same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const clamp = value => Math.max(0, Math.min(1, value));
const smooth = value => value ** 3 * (value * (value * 6 - 15) + 10);
const RAD = Math.PI / 180, DEG = 180 / Math.PI, EPS = 1e-10;
function record(value, name) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error(`AREA_${name}_OBJECT_REQUIRED`);
 return value;
}
function text(value, name) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value)) throw Error(`AREA_${name}_TEXT_REQUIRED`);
 return value;
}
function integer(value, name, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error(`AREA_${name}_INTEGER_REQUIRED`);
 return value;
}
function ratio(value, name) {
 if (!Number.isFinite(value) || value < 0 || value > 1) throw Error(`AREA_${name}_FRACTION_REQUIRED`);
 return value;
}
function list(value, name) {
 if (!Array.isArray(value)) throw Error(`AREA_${name}_ARRAY_REQUIRED`);
 return value;
}
function sourceRecord(input, mode) {
 const value = record(input, 'SOURCE');
 const source = {source_type: text(value.source_type, 'SOURCE_TYPE'), source_reference: text(value.source_reference, 'SOURCE_REFERENCE'),
  verification_status: text(value.verification_status, 'SOURCE_VERIFICATION')};
 if (mode === 'PRODUCTION') {
  if (source.verification_status !== 'VERIFIED' || ['SYNTHETIC_TEST', 'REFERENCE_DISPLAY_VALUE'].includes(source.source_type))
   throw Error('AREA_VERIFIED_PRODUCTION_SOURCE_REQUIRED');
 } else if (source.source_type !== 'SYNTHETIC_TEST' || source.verification_status !== 'SYNTHETIC_TEST')
  throw Error('AREA_EXPLICIT_SYNTHETIC_SOURCE_REQUIRED');
 return source;
}
const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const on = (a, b, p) => Math.abs(cross(a, b, p)) <= EPS && p[0] >= Math.min(a[0], b[0]) - EPS
 && p[0] <= Math.max(a[0], b[0]) + EPS && p[1] >= Math.min(a[1], b[1]) - EPS && p[1] <= Math.max(a[1], b[1]) + EPS;
function intersects(a, b, c, d) {
 const ca = cross(a, b, c), cb = cross(a, b, d), cc = cross(c, d, a), cd = cross(c, d, b);
 return ca * cb < -EPS && cc * cd < -EPS || on(a, b, c) || on(a, b, d) || on(c, d, a) || on(c, d, b);
}
function insideRing(point, ring) {
 let inside = false;
 for (let i = 0; i < ring.length - 1; i++) {
  const a = ring[i], b = ring[i + 1];
  if (on(a, b, point)) return false;
  if ((a[1] > point[1]) !== (b[1] > point[1])
   && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function ringsIntersect(first, second) {
 return first.slice(1).some((b, i) => second.slice(1).some((d, j) => intersects(first[i], b, second[j], d)));
}
function ringRecord(input) {
 const ring = list(input, 'RING').map(point => validateEventAnchor(point, 'AREA_RING_VERTEX'));
 if (ring.length < 4 || !same(ring[0], ring.at(-1))) throw Error('AREA_CLOSED_RING_REQUIRED');
 let area = 0;
 for (let i = 0; i < ring.length - 1; i++) {
  const a = ring[i], b = ring[i + 1];
  if (same(a, b)) throw Error('AREA_ZERO_LENGTH_RING_EDGE');
  if (Math.abs(a[0] - b[0]) > 180) throw Error('AREA_WRAPPED_GEOMETRY_UNSUPPORTED');
  area += a[0] * b[1] - b[0] * a[1];
  for (let j = i + 1; j < ring.length - 1; j++) {
   if (j === i + 1 || i === 0 && j === ring.length - 2) continue;
   if (intersects(a, b, ring[j], ring[j + 1])) throw Error('AREA_RING_SELF_INTERSECTION');
  }
 }
 if (Math.abs(area) <= EPS) throw Error('AREA_RING_ZERO_AREA');
 return ring;
}
/** Preserve source order, part count, closure and holes; reject rather than silently repair topology. */
export function validateAreaGeometry(input) {
 const geometry = record(input, 'GEOMETRY');
 if (!['Polygon', 'MultiPolygon'].includes(geometry.type)) throw Error('AREA_POLYGON_OR_MULTIPOLYGON_REQUIRED');
 const sourcePolygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
 const polygons = list(sourcePolygons, 'POLYGONS').map(inputPolygon => {
  const rings = list(inputPolygon, 'POLYGON').map(ringRecord);
  if (!rings.length) throw Error('AREA_OUTER_RING_REQUIRED');
  for (let i = 1; i < rings.length; i++) {
   if (!insideRing(rings[i][0], rings[0]) || ringsIntersect(rings[i], rings[0])) throw Error('AREA_HOLE_OUTSIDE_OR_TOUCHING_OUTER');
   for (let j = 1; j < i; j++) if (ringsIntersect(rings[i], rings[j])
    || insideRing(rings[i][0], rings[j]) || insideRing(rings[j][0], rings[i])) throw Error('AREA_HOLES_OVERLAP');
  }
  return rings;
 });
 if (!polygons.length) throw Error('AREA_POLYGON_PART_REQUIRED');
 if (polygons.reduce((sum, polygon) => sum + polygon.reduce((n, ring) => n + ring.length, 0), 0) > 4096)
  throw Error('AREA_GEOMETRY_CAPACITY_EXCEEDED');
 for (let i = 0; i < polygons.length; i++) for (let j = 0; j < i; j++) {
  const a = polygons[i][0], b = polygons[j][0];
  if (ringsIntersect(a, b) || insideRing(a[0], b) || insideRing(b[0], a)) throw Error('AREA_MULTIPOLYGON_PARTS_OVERLAP');
 }
 return freezeEventData({type: geometry.type, coordinates: geometry.type === 'Polygon' ? polygons[0] : polygons});
}
export function areaGeometryCoordinates(geometry) {
 const coordinates = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : null;
 if (!coordinates) throw Error('AREA_POLYGON_OR_MULTIPOLYGON_REQUIRED');
 return coordinates.flatMap(polygon => polygon.flatMap(ring => ring.map(point => [...point])));
}
function geometryCenter(geometry) {
 const points = areaGeometryCoordinates(geometry);
 return [(Math.min(...points.map(p => p[0])) + Math.max(...points.map(p => p[0]))) / 2,
  (Math.min(...points.map(p => p[1])) + Math.max(...points.map(p => p[1]))) / 2];
}
function areaRecord(input, source, mode, defaultRole = 'EVENT_AREA') {
 const value = record(input, 'RECORD'), geometry = validateAreaGeometry(value.geometry);
 return {id: text(value.id, 'ID'), geometry, role: text(value.role ?? defaultRole, 'ROLE'),
  style_role: text(value.style_role ?? 'PRIMARY', 'STYLE_ROLE'), source: sourceRecord(value.source ?? source, mode),
  anchor: value.anchor === undefined ? geometryCenter(geometry) : validateEventAnchor(value.anchor, 'AREA_ANCHOR')};
}
function lineRecord(input, source, mode) {
 const value = record(input, 'LINE_RECORD'), intent = compileEventIntent({data_mode: mode,
  line: {geometry: value.geometry, source: sourceRecord(value.source ?? source, mode),
   direction: value.direction ?? 'FORWARD', style_role: value.style_role ?? 'PRIMARY'}});
 if (intent.line.geometry.coordinates.length > 129) throw Error('AREA_LINE_CAPACITY_EXCEEDED');
 return {id: text(value.id, 'LINE_ID'), geometry: intent.line.geometry, source: intent.line.source,
  direction: intent.line.direction, style_role: intent.line.style_role, role: value.role ?? 'FRONT_LINE'};
}
function unique(records, label) {
 if (new Set(records.map(item => item.id)).size !== records.length) throw Error(`AREA_DUPLICATE_${label}_ID`);
 return records;
}
/** Source records distinguish illustrative presentation from observed state data. */
export function compileAreaIntent(input) {
 const value = record(input, 'INPUT'), mode = value.data_mode ?? 'PRODUCTION';
 if (!['PRODUCTION', 'SYNTHETIC_TEST'].includes(mode)) throw Error('AREA_DATA_MODE_REQUIRED');
 const source = sourceRecord(value.source, mode), origin = validateEventAnchor(value.origin, 'AREA_ORIGIN');
 const semanticMode = value.semantic_mode ?? 'ILLUSTRATIVE_FACT_BASED_VISUAL';
 if (!['ILLUSTRATIVE_FACT_BASED_VISUAL', 'SUPPLIED_OBSERVED_STATES'].includes(semanticMode)) throw Error('AREA_SEMANTIC_MODE_REQUIRED');
 const areas = unique(list(value.areas ?? [], 'AREAS').map(item => areaRecord(item, source, mode)), 'BASE_AREA');
 const impacts = unique(list(value.impacts ?? [], 'IMPACTS').map(item => areaRecord(item, source, mode, 'IMPACT_ZONE')), 'IMPACT');
 const fronts = unique(list(value.fronts ?? [], 'FRONTS').map(item => lineRecord(item, source, mode)), 'FRONT');
 const trajectories = unique(list(value.trajectories ?? [], 'TRAJECTORIES').map(item => lineRecord(item, source, mode)), 'TRAJECTORY');
 const states = list(value.states ?? [], 'STATES').map(item => {
  const state = record(item, 'STATE');
  const stateAreas = unique(list(state.areas ?? [], 'STATE_AREAS').map(area => areaRecord(area, source, mode)), 'STATE_AREA');
  const stateFronts = unique(list(state.fronts ?? [], 'STATE_FRONTS').map(front => lineRecord(front, source, mode)), 'STATE_FRONT');
  if (!stateAreas.length && !stateFronts.length) throw Error('AREA_STATE_GEOMETRY_REQUIRED');
  return {state_id: text(state.state_id, 'STATE_ID'), time_label: text(state.time_label, 'TIME_LABEL'),
   areas: stateAreas, fronts: stateFronts};
 });
 if (new Set(states.map(state => state.state_id)).size !== states.length) throw Error('AREA_DUPLICATE_STATE_ID');
 const propagations = unique(list(value.propagations ?? [], 'PROPAGATIONS').map(item => {
  const p = record(item, 'PROPAGATION'), start = p.radius_start_degrees ?? 0, end = p.radius_end_degrees;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end > 60)
   throw Error('AREA_VISUAL_ANGULAR_RADIUS_RANGE_REQUIRED');
  const range = p.angular_range_degrees ?? [0, 360];
  if (!Array.isArray(range) || range.length !== 2 || !range.every(Number.isFinite)
   || range[1] <= range[0] || range[1] - range[0] > 360) throw Error('AREA_VISUAL_ANGULAR_SWEEP_REQUIRED');
  return {id: text(p.id, 'PROPAGATION_ID'), origin: validateEventAnchor(p.origin ?? origin, 'PROPAGATION_ORIGIN'),
   radius_start_degrees: start, radius_end_degrees: end, angular_range_degrees: [...range],
   source: sourceRecord(p.source ?? source, mode), style_role: p.style_role ?? 'PROPAGATION',
   visualOnly: true, physicalSimulation: false, metricMeaning: 'ANGULAR_DISPLAY_DISTANCE_NOT_MEASURED_WAVE_RADIUS'};
 }), 'PROPAGATION');
 let metric = null;
 if (value.metric) metric = compileEventIntent({data_mode: mode, metric: value.metric}).metric;
 if (!areas.length && !states.length && !fronts.length && !propagations.length && !impacts.length) throw Error('AREA_PRIMITIVE_REQUIRED');
 return freezeEventData({version: AREA_INTENT_V3_VERSION, data_mode: mode,
  provenance_class: mode === 'PRODUCTION' ? 'VERIFIED_INPUT_DATA' : 'SYNTHETIC_TEST_NOT_PRODUCTION', source, origin,
  semantic_mode: semanticMode, areas, states, propagations, impacts, fronts, trajectories, metric,
  physicalSimulation: false});
}
export function assertAreaIntent(intent) {
 if (intent?.version !== AREA_INTENT_V3_VERSION) throw Error('AREA_INTENT_VERSION_REQUIRED');
 const canonical = compileAreaIntent(intent);
 if (!same(canonical, intent)) throw Error('AREA_INTENT_NON_CANONICAL');
 return canonical;
}
export function compileAreaLinePrimitive({geometry, source, direction = 'FORWARD', style_role = 'PRIMARY', data_mode}, {project} = {}) {
 const intent = compileEventIntent({data_mode, line: {geometry, source, direction, style_role}});
 return compileGeographicLinePrimitive(intent, {project});
}
/** A sourced angular display ring/arc, not a hydrodynamic radius or timing solver. */
export function geographicPropagationContour(propagation, radiusDegrees) {
 if (!Number.isFinite(radiusDegrees) || radiusDegrees <= 0 || radiusDegrees > 60) throw Error('AREA_POSITIVE_VISUAL_RADIUS_REQUIRED');
 const [lon, lat] = propagation.origin.map(v => v * RAD), radius = radiusDegrees * RAD;
 const [start, end] = propagation.angular_range_degrees, count = Math.max(8, Math.ceil(64 * (end - start) / 360));
 const coordinates = Array.from({length: count + 1}, (_, index) => {
  const bearing = (start + (end - start) * index / count) * RAD;
  const outLat = Math.asin(Math.sin(lat) * Math.cos(radius) + Math.cos(lat) * Math.sin(radius) * Math.cos(bearing));
  const outLon = lon + Math.atan2(Math.sin(bearing) * Math.sin(radius) * Math.cos(lat), Math.cos(radius) - Math.sin(lat) * Math.sin(outLat));
  const longitude = ((outLon * DEG + 180) % 360 + 360) % 360 - 180;
  // Canonicalize only generated display contours across the pinned Node/browser
  // math backends. Supplied source vertices are never rounded or resampled.
  return validateEventAnchor([Number(longitude.toFixed(9)), Number((outLat * DEG).toFixed(9))], 'PROPAGATION_CONTOUR');
 });
 if (end - start === 360) coordinates[coordinates.length - 1] = [...coordinates[0]];
 if (coordinates.slice(1).some((point, i) => Math.abs(point[0] - coordinates[i][0]) > 180))
  throw Error('AREA_WRAPPED_PROPAGATION_UNSUPPORTED');
 return freezeEventData({type: 'LineString', coordinates});
}
function mapGeometry(geometry, transform) {
 const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
 const coordinates = polygons.map(polygon => polygon.map(ring => ring.map(point =>
  validateEventAnchor([point[0] + transform[0], point[1] + transform[1]], 'MOVED_AREA_VERTEX'))));
 return {type: geometry.type, coordinates: geometry.type === 'Polygon' ? coordinates[0] : coordinates};
}
function operationProgress(op, localFrame) {
 return smooth(clamp((localFrame - op.start_frame) / Math.max(1, op.duration_frames - 1)));
}
function operationsRecord(intent, inputs) {
 const areaIds = new Set([...intent.areas, ...intent.states.flatMap(state => state.areas)].map(item => item.id));
 const frontIds = new Set([...intent.fronts, ...intent.states.flatMap(state => state.fronts)].map(item => item.id));
 const operations = list(inputs, 'OPERATIONS').map((input, index) => {
  const value = record(input, 'OPERATION');
  if (!AREA_FEATURES_V3.includes(value.type)) throw Error('AREA_OPERATION_TYPE_REQUIRED');
  const op = {id: value.id ?? 'OP_' + index, type: value.type,
   start_frame: integer(value.start_frame, 'OPERATION_START'), duration_frames: integer(value.duration_frames, 'OPERATION_DURATION', 1)};
  if (value.type !== 'AREA_HOLD' && op.duration_frames < 2) throw Error('AREA_VISUAL_OPERATION_REQUIRES_TWO_FRAMES');
  if (value.type !== 'AREA_HOLD') {
   if (['STATE_TRANSITION', 'TIME_STEP'].includes(value.type)) {
    op.state_ids = list(value.state_ids, 'OPERATION_STATE_IDS').map(id => text(id, 'OPERATION_STATE_ID'));
    if (op.state_ids.length < 2 || op.state_ids.some(id => !intent.states.some(state => state.state_id === id)))
     throw Error('AREA_OPERATION_EXISTING_STATES_REQUIRED');
   } else {
    op.target_id = text(value.target_id, 'OPERATION_TARGET_ID');
    const matching = value.type.startsWith('PROPAGATION_') ? intent.propagations.some(item => item.id === op.target_id)
     : value.type === 'IMPACT_ZONE' ? intent.impacts.some(item => item.id === op.target_id)
      : value.type === 'FRONT_LINE' ? frontIds.has(op.target_id) : areaIds.has(op.target_id);
    if (!matching) throw Error('AREA_OPERATION_TARGET_NOT_FOUND');
    op.from = ratio(value.from ?? (value.type === 'AREA_CONTRACT' ? 1 : 0), 'OPERATION_FROM');
    op.to = ratio(value.to ?? (value.type === 'AREA_CONTRACT' ? 0 : 1), 'OPERATION_TO');
    if (value.type === 'AREA_MOVE') {
     op.trajectory_id = text(value.trajectory_id, 'OPERATION_TRAJECTORY_ID');
     if (!intent.trajectories.some(item => item.id === op.trajectory_id)) throw Error('AREA_OPERATION_TRAJECTORY_NOT_FOUND');
    }
   }
  }
  return op;
 });
 if (!operations.length || new Set(operations.map(op => op.id)).size !== operations.length) throw Error('AREA_UNIQUE_OPERATIONS_REQUIRED');
 const end = op => op.start_frame + op.duration_frames;
 const holds = operations.filter(op => op.type === 'AREA_HOLD');
 if (holds.length !== 1 || holds[0].start_frame < Math.max(...operations.filter(op => op.type !== 'AREA_HOLD').map(end)))
  throw Error('AREA_FINAL_HOLD_AFTER_OPERATIONS_REQUIRED');
 const stateOps = operations.filter(op => ['STATE_TRANSITION', 'TIME_STEP'].includes(op.type));
 for (let i = 0; i < stateOps.length; i++) for (let j = 0; j < i; j++)
  if (stateOps[i].start_frame < end(stateOps[j]) && stateOps[j].start_frame < end(stateOps[i]))
   throw Error('AREA_STATE_OPERATION_WINDOWS_OVERLAP');
 return operations.sort((a, b) => a.start_frame - b.start_frame || a.id.localeCompare(b.id));
}
/** Deterministic schedule with immutable semantic sweep; no old timeline is altered. */
export function compileAreaPlan(intent, {fps = 30, start_frame = 0, total_frames = null, operations} = {}) {
 const data = assertAreaIntent(intent), ops = operationsRecord(data, operations);
 integer(fps, 'FPS', 1); integer(start_frame, 'START_FRAME');
 const requiredFrames = Math.max(...ops.map(op => op.start_frame + op.duration_frames));
 const totalFrames = total_frames === null ? requiredFrames : integer(total_frames, 'TOTAL_FRAMES', 1);
 if (totalFrames !== requiredFrames || totalFrames > 1200) throw Error('AREA_TOTAL_FRAMES_MUST_BIND_COMPLETE_TIMELINE');
 const endpoints = [...new Set([0, totalFrames, ...ops.flatMap(op => [op.start_frame, op.start_frame + op.duration_frames])])].sort((a, b) => a - b);
 const timeline = endpoints.slice(1).map((end, index) => {
  const start = endpoints[index], active = ops.filter(op => op.start_frame <= start && op.start_frame + op.duration_frames > start);
  return {state: active.map(op => op.type).join('+') || 'AREA_READY', types: active.map(op => op.type),
   startFrame: start_frame + start, endFrame: start_frame + end, durationFrames: end - start};
 });
 const sweepGeometries = [...data.areas, ...data.impacts, ...data.states.flatMap(state => state.areas)].map(item => copy(item.geometry));
 sweepGeometries.push(...data.fronts.map(item => copy(item.geometry)), ...data.states.flatMap(state => state.fronts.map(item => copy(item.geometry))));
 for (const op of ops) {
  if (op.type === 'AREA_MOVE') {
   const trajectory = data.trajectories.find(item => item.id === op.trajectory_id), points = trajectory.direction === 'REVERSE'
    ? [...trajectory.geometry.coordinates].reverse() : trajectory.geometry.coordinates;
   const originals = [...data.areas, ...data.states.flatMap(state => state.areas)].filter(item => item.id === op.target_id);
   for (const point of points) for (const area of originals) sweepGeometries.push(mapGeometry(area.geometry,
    [point[0] - points[0][0], point[1] - points[0][1]]));
  }
  if (op.type.startsWith('PROPAGATION_')) {
   const propagation = data.propagations.find(item => item.id === op.target_id);
   for (let frame = op.start_frame; frame < op.start_frame + op.duration_frames; frame++) {
    const progress = op.from + (op.to - op.from) * operationProgress(op, frame);
    const radius = propagation.radius_start_degrees + (propagation.radius_end_degrees - propagation.radius_start_degrees) * progress;
    if (radius > 0) sweepGeometries.push(copy(geographicPropagationContour(propagation, radius)));
   }
  }
 }
 const binding = JSON.stringify({areas: data.areas, impacts: data.impacts, fronts: data.fronts, states: data.states,
  trajectories: data.trajectories, propagations: data.propagations, operations: ops});
 return freezeEventData({version: AREA_PLAN_V3_VERSION, intent: data, fps, startFrame: start_frame,
  endFrame: start_frame + totalFrames, totalFrames, durationSeconds: totalFrames / fps, operations: ops, timeline,
  geometryBinding: binding, sweepGeometries,
  ownership: {camera: 'READ_ONLY_EXISTING_V5_AND_DETAIL', projection: 'EXISTING_NATIVE', nativeGraphics: 'READ_ONLY',
   geometry: 'SUPPLIED_TOPOLOGY_PRESERVED', progression: 'DETERMINISTIC_VISUAL_NOT_PHYSICAL', simulation: 'NONE'}});
}
export function assertAreaPlan(plan) {
 if (plan?.version !== AREA_PLAN_V3_VERSION) throw Error('AREA_PLAN_VERSION_REQUIRED');
 const canonical = compileAreaPlan(plan.intent, {fps: plan.fps, start_frame: plan.startFrame,
  total_frames: plan.totalFrames, operations: plan.operations});
 if (!same(canonical, plan)) throw Error('AREA_PLAN_NON_CANONICAL');
 return canonical;
}
function geoTrajectorySample(trajectory, progress, mode, project) {
 const coordinates = trajectory.direction === 'REVERSE' ? [...trajectory.geometry.coordinates].reverse() : trajectory.geometry.coordinates;
 const primitive = compileAreaLinePrimitive({...trajectory, data_mode: mode}, {project: project ?? (point => [...point])});
 const sample = sampleFlowRoute(primitive, progress), distance = sample.distancePixels;
 let index = primitive.segmentLengthsPixels.findIndex((_length, i) => distance <= primitive.cumulativeLengthsPixels[i + 1]);
 if (index < 0) index = primitive.segmentLengthsPixels.length - 1;
 const length = primitive.segmentLengthsPixels[index], ratio = length ? clamp((distance - primitive.cumulativeLengthsPixels[index]) / length) : 0;
 const a = coordinates[index], b = coordinates[index + 1];
 const position = progress === 1 ? [...coordinates.at(-1)] : [a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio];
 return {position, translation: position.map((value, axis) => value - coordinates[0][axis]),
  projectedPosition: sample.position, heading: sample.heading, fraction: progress, engine: 'UNCHANGED_V1_ARC_LENGTH_AND_FLOW_SAMPLE'};
}
function stateAt(plan, localFrame) {
 if (!plan.intent.states.length) return {items: [], stateId: null, timeLabel: null};
 const operations = plan.operations.filter(op => ['STATE_TRANSITION', 'TIME_STEP'].includes(op.type) && localFrame >= op.start_frame);
 const op = operations.at(-1);
 if (!op) return {items: [{state: plan.intent.states[0], alpha: 1}], stateId: plan.intent.states[0].state_id, timeLabel: plan.intent.states[0].time_label};
 const progress = operationProgress(op, localFrame), sequence = op.state_ids.map(id => plan.intent.states.find(state => state.state_id === id));
 const position = progress * (sequence.length - 1), index = Math.min(sequence.length - 1, Math.floor(position));
 if (op.type === 'TIME_STEP' || index === sequence.length - 1) return {items: [{state: sequence[index], alpha: 1}],
  stateId: sequence[index].state_id, timeLabel: sequence[index].time_label};
 const alpha = position - index, next = sequence[index + 1], current = sequence[index], chosen = alpha < .5 ? current : next;
 return {items: [{state: current, alpha: 1 - alpha}, {state: next, alpha}], stateId: chosen.state_id, timeLabel: chosen.time_label};
}
function latestOperation(plan, type, target, localFrame) {
 const matching = plan.operations.filter(op => op.type === type && op.target_id === target);
 return matching.filter(op => op.start_frame <= localFrame).at(-1) ?? matching[0] ?? null;
}
function amount(op, localFrame, fallback = 1) {
 return op ? op.from + (op.to - op.from) * operationProgress(op, localFrame) : fallback;
}
function frameArea(item, plan, localFrame, project, stateAlpha = 1, stateId = null, impact = false) {
 const reveal = latestOperation(plan, impact ? 'IMPACT_ZONE' : 'AREA_REVEAL', item.id, localFrame);
 const coverageOps = plan.operations.filter(op => ['AREA_GROW', 'AREA_CONTRACT'].includes(op.type) && op.target_id === item.id);
 const coverage = coverageOps.filter(op => op.start_frame <= localFrame).at(-1) ?? coverageOps[0];
 const move = latestOperation(plan, 'AREA_MOVE', item.id, localFrame);
 const movement = move ? geoTrajectorySample(plan.intent.trajectories.find(record => record.id === move.trajectory_id),
  amount(move, localFrame), plan.intent.data_mode, project) : null;
 const translation = movement?.translation ?? [0, 0], geometry = movement ? mapGeometry(item.geometry, translation) : copy(item.geometry);
 return {id: item.id, geometry, sourceGeometry: copy(item.geometry), source: copy(item.source), role: item.role,
  style_role: item.style_role, state_id: stateId, alpha: ratio(amount(reveal, localFrame) * stateAlpha, 'FRAME_ALPHA'),
  coverage: ratio(amount(coverage, localFrame), 'FRAME_COVERAGE'), coverageMode: 'RADIAL',
  coverageOrigin: item.anchor.map((value, axis) => value + translation[axis]),
  transform: {translation, heading: movement?.heading ?? 0}, motion: movement};
}
function frameFront(item, plan, localFrame, project, alpha = 1, stateId = null) {
 const reveal = amount(latestOperation(plan, 'FRONT_LINE', item.id, localFrame), localFrame);
 const primitive = project ? compileAreaLinePrimitive({...item, data_mode: plan.intent.data_mode}, {project}) : null;
 return {...copy(item), state_id: stateId, alpha, revealFraction: reveal,
  linePrimitive: primitive, lineReveal: primitive ? evaluateGeographicLineReveal(primitive, reveal) : null};
}
/** Random-access pure visual state. Evaluating a later frame never changes an earlier frame or source geometry. */
export function evaluateAreaFrame(plan, frame, {project} = {}) {
 const p = assertAreaPlan(plan); integer(frame, 'FRAME');
 if (frame < p.startFrame || frame >= p.endFrame) throw Error('AREA_FRAME_OUT_OF_RANGE');
 if (project !== undefined && typeof project !== 'function') throw Error('AREA_EXISTING_PROJECTION_REQUIRED');
 const localFrame = frame - p.startFrame, selected = stateAt(p, localFrame);
 const areas = p.intent.areas.map(item => frameArea(item, p, localFrame, project));
 const fronts = p.intent.fronts.map(item => frameFront(item, p, localFrame, project));
 for (const {state, alpha} of selected.items) {
  if (alpha <= 0) continue;
  areas.push(...state.areas.map(item => frameArea(item, p, localFrame, project, alpha, state.state_id)));
  fronts.push(...state.fronts.map(item => frameFront(item, p, localFrame, project, alpha, state.state_id)));
 }
 const impacts = p.intent.impacts.map(item => frameArea(item, p, localFrame, project, 1, null, true));
 const propagations = [];
 for (const item of p.intent.propagations) {
  const op = latestOperation(p, 'PROPAGATION_RING', item.id, localFrame) ?? latestOperation(p, 'PROPAGATION_WAVE', item.id, localFrame);
  if (!op || localFrame < op.start_frame) continue;
  const progress = amount(op, localFrame), radius = item.radius_start_degrees + (item.radius_end_degrees - item.radius_start_degrees) * progress;
  if (!(radius > 0)) continue;
  const geometry = geographicPropagationContour(item, radius), primitive = project
   ? compileAreaLinePrimitive({geometry, source: item.source, data_mode: p.intent.data_mode, style_role: item.style_role}, {project}) : null;
  propagations.push({...copy(item), geometry, geographicContour: geometry, progress, radius_degrees: radius,
   alpha: 1, revealFraction: 1, propagationType: op.type, linePrimitive: primitive,
   lineReveal: primitive ? evaluateGeographicLineReveal(primitive, 1) : null});
 }
 const beat = p.timeline.find(item => frame >= item.startFrame && frame < item.endFrame);
 const activeOperations = p.operations.filter(op => localFrame >= op.start_frame && localFrame < op.start_frame + op.duration_frames);
 return freezeEventData({version: AREA_FRAME_V3_VERSION, frame, localFrame, timeSeconds: frame / p.fps,
  state: beat.state, stateFrame: frame - beat.startFrame,
  stateProgress: beat.durationFrames === 1 ? 1 : (frame - beat.startFrame) / (beat.durationFrames - 1),
  stateId: selected.stateId, timeLabel: selected.timeLabel, timeLabelVisible: selected.timeLabel !== null,
  origin: [...p.intent.origin], areas, impacts, fronts, propagations, metric: copy(p.intent.metric),
  hold: activeOperations.some(op => op.type === 'AREA_HOLD'), activeFeatures: activeOperations.map(op => op.type),
  geometryBinding: p.geometryBinding, dataMode: p.intent.data_mode,
  productionEligible: p.intent.data_mode === 'PRODUCTION', physicalSimulation: false,
  projectionOwnership: 'EXISTING_NATIVE', cameraOwnership: 'READ_ONLY'});
}
