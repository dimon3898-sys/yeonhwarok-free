/** Deterministic scene planning from a topic and supplied facts. No renderer or camera solver. */
import {compileEventIntent, freezeEventData, validateEventAnchor} from './event_contract_v1.mjs';
import {validateAreaGeometry} from './area_core_v3.mjs';
import {compileFlowIntent} from './flow_core_v2.mjs';

export const PLANNER_FACTS_VERSION = 'PLANNER_FACTS_V1';
export const PLANNER_SCENE_VERSION = 'PLANNER_SCENE_JSON_V1';
export const PLANNER_FAMILIES = Object.freeze(['TRANSPORT', 'LINE_METRIC', 'DISASTER', 'WAR']);
export const PLANNER_FEATURES = Object.freeze(['ROUTE_REVEAL', 'DIRECTIONAL_FLOW', 'MOVING_OBJECT',
 'ENDPOINT_PULSE', 'ROUTE_HOLD', 'GEOGRAPHIC_LINE_REVEAL', 'METRIC_ANNOTATION', 'INFORMATION_HOLD',
 'PROPAGATION_WAVE', 'IMPACT_ZONE', 'AREA_HOLD', 'FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP']);
const copy = value => structuredClone(value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const normalize = value => value.normalize('NFKC').toLocaleLowerCase('en-US').replace(/\s+/gu, ' ').trim();

export class PlannerDataRequiredError extends Error {
 constructor(reason) { super('DATA_REQUIRED: ' + reason); this.name = 'PlannerDataRequiredError'; this.code = 'DATA_REQUIRED'; }
}
function record(value, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error('PLANNER_' + label + '_OBJECT_REQUIRED');
 return value;
}
function text(value, label) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value)) throw Error('PLANNER_' + label + '_TEXT_REQUIRED');
 return value;
}
function id(value, label = 'ID') {
 text(value, label);
 if (!/^[A-Za-z0-9_.:-]+$/u.test(value)) throw Error('PLANNER_' + label + '_IDENTIFIER_REQUIRED');
 return value;
}
function integer(value, label, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error('PLANNER_' + label + '_INTEGER_REQUIRED');
 return value;
}
function list(value, label) {
 if (!Array.isArray(value)) throw Error('PLANNER_' + label + '_ARRAY_REQUIRED');
 return value;
}
function unique(records, label) {
 if (new Set(records.map(value => value.id)).size !== records.length) throw Error('PLANNER_DUPLICATE_' + label + '_ID');
 return records;
}
function refs(values, existing, label) {
 const result = list(values, label).map(value => id(value, label));
 if (new Set(result).size !== result.length || result.some(value => !existing.has(value))) throw Error('PLANNER_' + label + '_REFERENCE_REQUIRED');
 return [...result];
}
function date(value, label) {
 text(value, label);
 if (!/^\d{4}-\d{2}-\d{2}$/u.test(value) || !Number.isFinite(Date.parse(value + 'T00:00:00Z'))
  || new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) !== value) throw Error('PLANNER_' + label + '_ISO_DATE_REQUIRED');
 return value;
}
function sourceRecord(value, mode) {
 record(value, 'SOURCE');
 const result = {id: id(value.id, 'SOURCE_ID'), source_type: text(value.source_type, 'SOURCE_TYPE'),
  source_reference: text(value.source_reference, 'SOURCE_REFERENCE'), verification_status: text(value.verification_status, 'SOURCE_VERIFICATION')};
 if (mode === 'PRODUCTION' && (result.verification_status !== 'VERIFIED'
  || ['SYNTHETIC_TEST', 'REFERENCE_DISPLAY_VALUE'].includes(result.source_type))) throw new PlannerDataRequiredError('verified fact source');
 if (mode === 'SYNTHETIC_TEST' && (result.verification_status !== 'SYNTHETIC_TEST' || result.source_type !== 'SYNTHETIC_TEST'))
  throw Error('PLANNER_EXPLICIT_SYNTHETIC_SOURCE_REQUIRED');
 if (value.note !== undefined) result.note = text(value.note, 'SOURCE_NOTE');
 for (const key of ['verification_basis', 'live_access', 'retrieval_date', 'license', 'version'])
  if (value[key] !== undefined) result[key] = text(value[key], 'SOURCE_' + key.toUpperCase());
 for (const key of ['original_sha256', 'source_wrapper_sha256', 'sha256']) if (value[key] !== undefined) {
  if (typeof value[key] !== 'string' || !/^[a-f0-9]{64}$/u.test(value[key])) throw Error('PLANNER_SOURCE_SHA256_REQUIRED');
  result[key] = value[key];
 }
 for (const key of ['crs', 'resolution']) if (value[key] !== undefined) result[key] = text(value[key], 'SOURCE_' + key.toUpperCase());
 return result;
}
function contractSource(source) {
 return {source_type: source.source_type, source_reference: source.source_reference, verification_status: source.verification_status};
}
function geometryRecord(value, sources, mode) {
 record(value, 'GEOMETRY_RECORD');
 const source = sources.get(value.source_id);
 if (!source) throw Error('PLANNER_GEOMETRY_SOURCE_REFERENCE_REQUIRED');
 record(value.geometry, 'GEOMETRY');
 let geometry;
 if (value.geometry.type === 'Point') geometry = {type: 'Point', coordinates: validateEventAnchor(value.geometry.coordinates)};
 else if (value.geometry.type === 'LineString') geometry = compileEventIntent({data_mode: mode,
  line: {geometry: value.geometry, source: contractSource(source), direction: 'FORWARD', style_role: 'PRIMARY'}}).line.geometry;
 else geometry = validateAreaGeometry(value.geometry);
 return {id: id(value.id, 'GEOMETRY_ID'), geometry: copy(geometry), source_id: source.id,
  ...(value.note === undefined ? {} : {note: text(value.note, 'GEOMETRY_NOTE')})};
}
function expectGeometry(ref, geometries, types, label) {
 const found = geometries.get(ref);
 if (!found || !types.includes(found.geometry.type)) throw Error('PLANNER_' + label + '_GEOMETRY_REFERENCE_REQUIRED');
 return found;
}
function nativeContext(value) {
 if (value === undefined) return undefined;
 record(value, 'NATIVE_CONTEXT');
 const allowed = ['country_ids', 'primary_country_id', 'secondary_country_ids', 'context_location_ids'];
 if (Object.keys(value).some(key => !allowed.includes(key))) throw Error('PLANNER_NATIVE_CONTEXT_UNKNOWN_FIELD');
 const result = {};
 for (const key of allowed) if (value[key] !== undefined) result[key] = key === 'primary_country_id'
  ? id(value[key], 'COUNTRY_ID') : list(value[key], key).map(item => id(item, 'CONTEXT_ID'));
 return result;
}
const timingFields = Object.freeze(['fps', 'total_frames', 'duration_seconds', 'camera_lock_frame',
 'event_start_frame', 'initial_reveal_frames', 'state_transition_frames', 'final_hold_frames',
 'action_frames', 'frame_policy', 'blank_interstage_frames']);
function suppliedTiming(value) {
 record(value, 'SCENE_TIMING');
 if (Object.keys(value).some(key => !timingFields.includes(key)) || timingFields.some(key => value[key] === undefined))
  throw Error('PLANNER_COMPLETE_SCENE_TIMING_REQUIRED');
 const result = {};
 for (const key of timingFields) result[key] = ['duration_seconds', 'frame_policy'].includes(key) ? value[key]
  : integer(value[key], 'SCENE_TIMING_' + key.toUpperCase(), ['fps', 'total_frames', 'final_hold_frames'].includes(key) ? 1 : 0);
 if (result.duration_seconds !== result.total_frames / result.fps || result.frame_policy !== 'INTEGER_DETERMINISTIC'
  || result.blank_interstage_frames !== 0 || result.camera_lock_frame !== result.event_start_frame
  || result.event_start_frame >= result.total_frames) throw Error('PLANNER_SCENE_TIMING_LOCK_AND_DURATION_REQUIRED');
 return result;
}
function causalTrackRecord(value) {
 record(value, 'CAUSAL_TRACK');
 const allowed = ['id', 'source_id', 'action_kind', 'from_state_id', 'to_state_id', 'motion_start_frame',
  'contact_frame', 'control_start_frame', 'control_end_frame', 'end_frame', 'contact_kind', 'semantic_mode',
  'represents_historical_unit', 'route_id', 'object_id', 'target_front_line_id', 'contact_anchor'];
 if (Object.keys(value).some(key => !allowed.includes(key))) throw Error('PLANNER_CAUSAL_TRACK_UNKNOWN_FIELD');
 const result = {id: id(value.id, 'CAUSAL_TRACK_ID'), source_id: id(value.source_id, 'CAUSAL_SOURCE_ID'),
  action_kind: text(value.action_kind, 'CAUSAL_ACTION'), from_state_id: id(value.from_state_id, 'CAUSAL_FROM_STATE'),
  to_state_id: id(value.to_state_id, 'CAUSAL_TO_STATE')};
 for (const key of ['motion_start_frame', 'contact_frame', 'control_start_frame', 'control_end_frame', 'end_frame'])
  result[key] = integer(value[key], 'CAUSAL_' + key.toUpperCase());
 if (!['SCHEMATIC_FRONT_CONTACT', 'ARRIVAL', 'NONE'].includes(value.contact_kind)
  || value.semantic_mode !== 'SCHEMATIC_STATE_TRANSITION' || value.represents_historical_unit !== false)
  throw Error('PLANNER_CAUSAL_SCHEMATIC_SEMANTICS_REQUIRED');
 Object.assign(result, {contact_kind: value.contact_kind, semantic_mode: value.semantic_mode, represents_historical_unit: false});
 for (const key of ['route_id', 'object_id', 'target_front_line_id']) if (value[key] !== undefined) result[key] = id(value[key], 'CAUSAL_' + key.toUpperCase());
 if (value.contact_anchor !== undefined) result.contact_anchor = validateEventAnchor(value.contact_anchor, 'CAUSAL_CONTACT_ANCHOR');
 return result;
}
function pointOnLine(point, geometry) {
 return geometry.coordinates.slice(1).some((b, index) => {
  const a = geometry.coordinates[index], dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy);
  return length > 0 && Math.abs(dx * (point[1] - a[1]) - dy * (point[0] - a[0])) <= 1e-8 * length
   && point[0] >= Math.min(a[0], b[0]) - 1e-8 && point[0] <= Math.max(a[0], b[0]) + 1e-8
   && point[1] >= Math.min(a[1], b[1]) - 1e-8 && point[1] <= Math.max(a[1], b[1]) + 1e-8;
 });
}
/** Optional composition data binds existing actors and state snapshots; it supplies no simulation. */
function validateCausalTracks(tracks, {sourceMap, geometryMap, routes, objects, steps, fronts, timing, mode}) {
 if (!tracks.length) throw Error('PLANNER_NONEMPTY_CAUSAL_TRACKS_REQUIRED');
 const routeMap = new Map(routes.map(row => [row.id, row])), objectMap = new Map(objects.map(row => [row.id, row]));
 const frontMap = new Map(fronts.map(row => [row.id, row]));
 for (const track of tracks) {
  if (!sourceMap.has(track.source_id)) throw Error('PLANNER_CAUSAL_SOURCE_REFERENCE_REQUIRED');
  const index = steps.findIndex(step => step.id === track.from_state_id), target = steps[index + 1];
  if (index < 0 || target?.id !== track.to_state_id) throw Error('PLANNER_CAUSAL_ADJACENT_STATES_REQUIRED');
  const start = track.motion_start_frame, contact = track.contact_frame, controlStart = track.control_start_frame,
   controlEnd = track.control_end_frame, end = track.end_frame;
  if (!(start < contact && contact <= controlStart && controlStart < controlEnd && controlEnd <= end))
   throw Error('PLANNER_CAUSAL_FRAME_ORDER_REQUIRED');
  if (timing && (start < timing.camera_lock_frame || end > timing.total_frames
   || start < steps[index].start_frame || controlStart < target.start_frame
   || controlEnd > target.start_frame + target.transition_frames)) throw Error('PLANNER_CAUSAL_STATE_WINDOW_REQUIRED');
  const actor = track.route_id !== undefined, controlOnly = ['CONTROL_ONLY', 'SETTLEMENT'].includes(track.action_kind);
  if (actor !== (track.object_id !== undefined) || controlOnly === actor
   || (!actor || controlOnly) && track.contact_kind !== 'NONE') throw Error('PLANNER_CAUSAL_ACTOR_BINDING_REQUIRED');
  const frontDeclared = track.target_front_line_id !== undefined;
  if (frontDeclared !== (track.contact_anchor !== undefined) || frontDeclared && (!actor || track.contact_kind === 'NONE'))
   throw Error('PLANNER_CAUSAL_FRONT_ANCHOR_BINDING_REQUIRED');
  if (!actor) continue;
  const route = routeMap.get(track.route_id), object = objectMap.get(track.object_id);
  if (!route || !object || object.route_id !== route.id) throw Error('PLANNER_CAUSAL_ROUTE_OBJECT_REFERENCE_REQUIRED');
  const geo = expectGeometry(route.geometry_ref, geometryMap, ['LineString'], 'CAUSAL_ROUTE');
  if (!sourceMap.has(route.source_id) || route.source_id !== geo.source_id || !['FORWARD', 'REVERSE'].includes(route.direction))
   throw Error('PLANNER_CAUSAL_ROUTE_SOURCE_DIRECTION_REQUIRED');
  if (!object.graphic) throw new PlannerDataRequiredError('supplied causal moving-object graphic');
  const points = geo.geometry.coordinates, endpoint = route.direction === 'REVERSE' ? points[0] : points.at(-1);
  compileFlowIntent({data_mode: mode,
   route_geometry: geo.geometry, route_source: contractSource(sourceMap.get(route.source_id)), direction: route.direction,
   start_anchor: route.direction === 'REVERSE' ? points.at(-1) : points[0], end_anchor: endpoint,
   object_role: object.role, object_graphic: object.graphic});
  if (frontDeclared) {
   const front = frontMap.get(track.target_front_line_id);
   if (!front || front.stage_id !== target.id || !target.front_line_ids.includes(front.id)
    || !equal(track.contact_anchor, endpoint)
    || !pointOnLine(track.contact_anchor, expectGeometry(front.geometry_ref, geometryMap, ['LineString'], 'CAUSAL_FRONT').geometry))
    throw Error('PLANNER_CAUSAL_SUPPLIED_FRONT_CONTACT_REQUIRED');
  } else if (track.contact_kind === 'SCHEMATIC_FRONT_CONTACT' && !target.front_line_ids.some(ref => {
   const front = frontMap.get(ref);
   return front && pointOnLine(endpoint, expectGeometry(front.geometry_ref, geometryMap, ['LineString'], 'CAUSAL_FRONT').geometry);
  })) throw Error('PLANNER_CAUSAL_SUPPLIED_FRONT_CONTACT_REQUIRED');
 }
}
/** Sources and geographical validation reuse Final contracts; no geometry is invented or repaired. */
export function validateFactDataset(input) {
 const given = record(input, 'FACTS');
 if (given.version !== PLANNER_FACTS_VERSION) throw Error('PLANNER_FACTS_VERSION_REQUIRED');
 const mode = given.data_mode ?? 'PRODUCTION';
 if (!['PRODUCTION', 'SYNTHETIC_TEST'].includes(mode)) throw Error('PLANNER_DATA_MODE_REQUIRED');
 const subject = record(given.subject, 'SUBJECT');
 if (!PLANNER_FAMILIES.includes(subject.event_family)) throw new PlannerDataRequiredError('supported event family');
 const subjectRecord = {id: id(subject.id, 'SUBJECT_ID'), label: text(subject.label, 'SUBJECT_LABEL'),
  aliases: list(subject.aliases, 'SUBJECT_ALIASES').map(value => text(value, 'SUBJECT_ALIAS')), event_family: subject.event_family};
 if (!subjectRecord.aliases.length) throw new PlannerDataRequiredError('subject aliases');
 const sources = unique(list(given.source_notes, 'SOURCE_NOTES').map(value => sourceRecord(value, mode)), 'SOURCE');
 if (!sources.length) throw new PlannerDataRequiredError('fact provenance');
 const sourceMap = new Map(sources.map(value => [value.id, value]));
 const geometries = unique(list(given.geometries, 'GEOMETRIES').map(value => geometryRecord(value, sourceMap, mode)), 'GEOMETRY');
 const geometryMap = new Map(geometries.map(value => [value.id, value]));
 const locations = unique(list(given.locations, 'LOCATIONS').map(value => {
  record(value, 'LOCATION');
  return {id: id(value.id, 'LOCATION_ID'), label: text(value.label, 'LOCATION_LABEL'), anchor: validateEventAnchor(value.anchor),
   ...(value.country_id === undefined ? {} : {country_id: id(value.country_id, 'LOCATION_COUNTRY_ID')})};
 }), 'LOCATION');
 if (!locations.length) throw new PlannerDataRequiredError('geographical context');
 const range = record(given.time_range, 'TIME_RANGE');
 const timeRange = {start: date(range.start, 'TIME_RANGE_START'), end: date(range.end, 'TIME_RANGE_END')};
 if (timeRange.end < timeRange.start) throw Error('PLANNER_TIME_RANGE_ORDER');
 const stages = unique(list(given.stages ?? [], 'STAGES').map(value => {
  record(value, 'STAGE');
  const areas = refs(value.area_refs ?? [], geometryMap, 'STAGE_AREA');
  const fronts = refs(value.front_refs ?? [], geometryMap, 'STAGE_FRONT');
  areas.forEach(ref => expectGeometry(ref, geometryMap, ['Polygon', 'MultiPolygon'], 'STAGE_AREA'));
  fronts.forEach(ref => expectGeometry(ref, geometryMap, ['LineString'], 'STAGE_FRONT'));
  return {id: id(value.id, 'STAGE_ID'), date: date(value.date, 'STAGE_DATE'), label: text(value.label, 'STAGE_LABEL'),
   area_refs: areas, front_refs: fronts};
 }), 'STAGE');
 for (let index = 0; index < stages.length; index++) {
  if (stages[index].date < timeRange.start || stages[index].date > timeRange.end
   || index > 0 && stages[index].date <= stages[index - 1].date) throw Error('PLANNER_CHRONOLOGICAL_STAGES_REQUIRED');
 }
 const routes = unique(list(given.routes ?? [], 'ROUTES').map(value => {
  record(value, 'ROUTE'); expectGeometry(value.geometry_ref, geometryMap, ['LineString'], 'ROUTE');
  const direction = value.direction ?? 'FORWARD';
  if (!['FORWARD', 'REVERSE'].includes(direction)) throw Error('PLANNER_ROUTE_DIRECTION_REQUIRED');
  if (value.object_graphic !== undefined) {
   const geo = geometryMap.get(value.geometry_ref), coordinates = geo.geometry.coordinates;
   compileFlowIntent({data_mode: mode, route_geometry: geo.geometry, route_source: contractSource(sourceMap.get(geo.source_id)),
    direction, start_anchor: direction === 'FORWARD' ? coordinates[0] : coordinates.at(-1),
    end_anchor: direction === 'FORWARD' ? coordinates.at(-1) : coordinates[0],
    object_role: value.object_role, object_graphic: value.object_graphic});
  }
  return {id: id(value.id, 'ROUTE_ID'), geometry_ref: value.geometry_ref, direction,
   object_role: text(value.object_role, 'OBJECT_ROLE'), object_profile: text(value.object_profile ?? value.object_role, 'OBJECT_PROFILE'),
   required_for_story: value.required_for_story === true,
   ...(value.object_graphic === undefined ? {} : {object_graphic: copy(value.object_graphic)})};
 }), 'ROUTE');
 const geographicLines = unique(list(given.geographic_lines ?? [], 'GEOGRAPHIC_LINES').map(value => {
  record(value, 'GEOGRAPHIC_LINE'); expectGeometry(value.geometry_ref, geometryMap, ['LineString'], 'GEOGRAPHIC_LINE');
  if (!['FORWARD', 'REVERSE'].includes(value.direction ?? 'FORWARD')) throw Error('PLANNER_LINE_DIRECTION_REQUIRED');
  return {id: id(value.id), geometry_ref: value.geometry_ref, direction: value.direction ?? 'FORWARD',
   style_role: text(value.style_role ?? 'PRIMARY', 'LINE_STYLE_ROLE')};
 }), 'GEOGRAPHIC_LINE');
 const impacts = unique(list(given.impacts ?? [], 'IMPACTS').map(value => {
  record(value, 'IMPACT'); expectGeometry(value.geometry_ref, geometryMap, ['Polygon', 'MultiPolygon'], 'IMPACT');
  return {id: id(value.id), geometry_ref: value.geometry_ref};
 }), 'IMPACT');
 const propagations = unique(list(given.propagations ?? [], 'PROPAGATIONS').map(value => {
  record(value, 'PROPAGATION');
  const source = sourceMap.get(value.source_id);
  if (!source) throw Error('PLANNER_PROPAGATION_SOURCE_REFERENCE_REQUIRED');
  const result = {id: id(value.id), origin: validateEventAnchor(value.origin), source_id: source.id,
   visual_only: true, physical_simulation: false};
  if (value.geometry_ref !== undefined) {
   expectGeometry(value.geometry_ref, geometryMap, ['LineString'], 'PROPAGATION'); result.geometry_ref = value.geometry_ref;
  }
  for (const key of ['radius_start_degrees', 'radius_end_degrees']) if (value[key] !== undefined) {
   if (!Number.isFinite(value[key]) || value[key] < 0 || value[key] > 60) throw Error('PLANNER_VISUAL_PROPAGATION_RADIUS_REQUIRED');
   result[key] = value[key];
  }
  if (value.angular_range_degrees !== undefined) {
   const range = value.angular_range_degrees;
   if (!Array.isArray(range) || range.length !== 2 || !range.every(Number.isFinite)
    || range[1] <= range[0] || range[1] - range[0] > 360) throw Error('PLANNER_VISUAL_ANGULAR_RANGE_REQUIRED');
   result.angular_range_degrees = [...range];
  }
  if (!result.geometry_ref && !(result.radius_end_degrees > (result.radius_start_degrees ?? 0)))
   throw new PlannerDataRequiredError('propagation geometry or sourced visual extent');
  return result;
 }), 'PROPAGATION');
 const metrics = unique(list(given.metrics ?? [], 'METRICS').map(value => {
  record(value, 'METRIC');
  const source = sourceMap.get(value.source_id);
  if (!source) throw Error('PLANNER_METRIC_SOURCE_REFERENCE_REQUIRED');
  const metric = compileEventIntent({data_mode: mode, metric: {...value, source: contractSource(source)}}).metric;
  return {id: id(value.id), display_value: metric.display_value, unit: metric.unit, anchor: metric.anchor, source_id: source.id};
 }), 'METRIC');
 const markers = unique(list(given.markers ?? [], 'MARKERS').map(value => {
  record(value, 'MARKER');
  if (value.source_id !== undefined && !sourceMap.has(value.source_id)) throw Error('PLANNER_MARKER_SOURCE_REFERENCE_REQUIRED');
  return {id: id(value.id), label: text(value.label, 'MARKER_LABEL'), anchor: validateEventAnchor(value.anchor),
   ...(value.source_id === undefined ? {} : {source_id: value.source_id})};
 }), 'MARKER');
 const texts = unique(list(given.text ?? [], 'TEXT').map(value => {
  record(value, 'TEXT_RECORD');
  return {id: id(value.id), content: text(value.content, 'TEXT_CONTENT'), role: text(value.role, 'TEXT_ROLE')};
 }), 'TEXT');
 const camera = record(given.camera, 'CAMERA_INTENT');
 const targetRefs = refs(camera.target_geometry_refs, geometryMap, 'CAMERA_GEOMETRY');
 if (!targetRefs.length) throw new PlannerDataRequiredError('camera target geometry');
 if (camera.detail_policy !== undefined && camera.detail_policy !== 'FACT_BASED_VISUAL_GRADE') throw Error('PLANNER_VISUAL_POLICY_REQUIRED');
 const context = nativeContext(given.native_context ?? camera.native_context);
 const preferred = given.scale?.preferred ?? 'REGIONAL';
 if (!['CONTINENT', 'REGIONAL', 'LOCAL'].includes(preferred)) throw Error('PLANNER_SCALE_INTENT_REQUIRED');
 const sceneTiming = given.scene_timing === undefined ? undefined : suppliedTiming(given.scene_timing);
 const causalTracks = given.causal_tracks === undefined ? undefined
  : unique(list(given.causal_tracks, 'CAUSAL_TRACKS').map(causalTrackRecord), 'CAUSAL_TRACK');
 if (causalTracks) {
  const fronts = stages.flatMap(stage => stage.front_refs.map((ref, part) =>
   ({id: 'FRONT_' + stage.id + '_' + part, stage_id: stage.id, geometry_ref: ref})));
  const steps = stages.map((stage, index) => ({id: stage.id,
   front_line_ids: fronts.filter(front => front.stage_id === stage.id).map(front => front.id),
   ...(sceneTiming === undefined ? {} : {start_frame: sceneTiming.event_start_frame + (index === 0 ? 0
    : sceneTiming.initial_reveal_frames + (index - 1) * sceneTiming.state_transition_frames),
   transition_frames: index === 0 ? sceneTiming.initial_reveal_frames : sceneTiming.state_transition_frames})}));
  validateCausalTracks(causalTracks, {sourceMap, geometryMap,
   routes: routes.filter(route => route.required_for_story).map(route => ({...route, source_id: geometryMap.get(route.geometry_ref).source_id})),
   objects: routes.map(route => ({id: 'OBJECT_' + route.id, route_id: route.id, role: route.object_role, graphic: route.object_graphic})),
   steps, fronts, timing: sceneTiming, mode});
 }
 const allIds = [...geometries, ...locations, ...stages, ...routes, ...geographicLines, ...impacts, ...propagations,
  ...metrics, ...markers, ...texts, ...(causalTracks ?? [])].map(value => value.id);
 if (new Set(allIds).size !== allIds.length) throw Error('PLANNER_DUPLICATE_DATA_ID');
 if (!['ILLUSTRATIVE_FACT_BASED_VISUAL', 'SUPPLIED_OBSERVED_STATES'].includes(given.semantic_mode ?? 'ILLUSTRATIVE_FACT_BASED_VISUAL'))
  throw Error('PLANNER_SEMANTIC_MODE_REQUIRED');
 return freezeEventData({version: PLANNER_FACTS_VERSION, data_mode: mode, subject: subjectRecord,
  locations, time_range: timeRange, source_notes: sources, geometries, stages, routes, geographic_lines: geographicLines,
  impacts, propagations, metrics, markers, text: texts,
  semantic_mode: given.semantic_mode ?? 'ILLUSTRATIVE_FACT_BASED_VISUAL',
  camera: {anchor: validateEventAnchor(camera.anchor), target_geometry_refs: targetRefs,
   minimum_context_geometry_refs: refs(camera.minimum_context_geometry_refs ?? [], geometryMap, 'MINIMUM_CONTEXT_GEOMETRY'),
   detail_policy: 'FACT_BASED_VISUAL_GRADE', ...(context === undefined ? {} : {native_context: context})},
  scale: {preferred}, ...(sceneTiming === undefined ? {} : {scene_timing: sceneTiming}),
  ...(causalTracks === undefined ? {} : {causal_tracks: causalTracks})});
}

const familyPatterns = Object.freeze({
 TRANSPORT: /(?:운송|물류|이동|항로|노선|배송|교역|항공|여객|선박|transport|logistics|movement|shipping|route|journey|travel)/iu,
 LINE_METRIC: /(?:운하|국경|길이|거리|철도|도로|canal|border|length|distance|geographic line)/iu,
 DISASTER: /(?:쓰나미|지진|재난|홍수|산불|태풍|확산|파동|tsunami|earthquake|disaster|flood|wildfire|typhoon|propagat|wave)/iu,
 WAR: /(?:전쟁|전선|점령|진격|퇴각|휴전|war|battle|front.?line|conflict|territor|armistice|occupation)/iu
});
/** Historical names are supplied aliases, never hardcoded engine branches. */
export function topicIntent(topic, factsInput) {
 const facts = validateFactDataset(factsInput), normalized = normalize(text(topic, 'TOPIC'));
 const subjectMatched = [facts.subject.label, ...facts.subject.aliases].some(alias => normalized.includes(normalize(alias)));
 const recognized = PLANNER_FAMILIES.filter(family => familyPatterns[family].test(normalized));
 if (!subjectMatched) throw new PlannerDataRequiredError('topic has no supplied matching subject');
 if (!recognized.includes(facts.subject.event_family)) throw new PlannerDataRequiredError('topic has no supported supplied event intent');
 return freezeEventData({version: 'TOPIC_INTENT_V1', topic: topic.trim(), subject_id: facts.subject.id,
  event_family: facts.subject.event_family, subject_match: 'SUPPLIED_DATA_ALIAS', data_policy: 'FACT_BASED_VISUAL_GRADE',
  question: /[?？]|(?:어떻게|왜|얼마|what|how|why)/iu.test(normalized) ? 'EXPLAIN_CHANGE' : 'SHOW_EVENT',
  facts_required: true, natural_language_owner: 'PLANNER_ONLY'});
}
/** Select only primitives justified by both intent and supplied facts. */
export function selectFeatures(intent, factsInput) {
 const facts = validateFactDataset(factsInput);
 if (intent?.version !== 'TOPIC_INTENT_V1' || intent.subject_id !== facts.subject.id || intent.event_family !== facts.subject.event_family)
  throw Error('PLANNER_INTENT_FACT_BINDING_REQUIRED');
 let selected;
 if (intent.event_family === 'TRANSPORT') {
  if (!facts.routes.length) throw new PlannerDataRequiredError('supplied transport route and object role');
  selected = ['ROUTE_REVEAL', 'DIRECTIONAL_FLOW', 'MOVING_OBJECT', 'ENDPOINT_PULSE', 'ROUTE_HOLD'];
 } else if (intent.event_family === 'LINE_METRIC') {
  if (!facts.geographic_lines.length || !facts.metrics.length) throw new PlannerDataRequiredError('supplied line and metric');
  selected = ['GEOGRAPHIC_LINE_REVEAL', 'METRIC_ANNOTATION', 'INFORMATION_HOLD'];
 } else if (intent.event_family === 'DISASTER') {
  if (!facts.propagations.length || !facts.impacts.length) throw new PlannerDataRequiredError('supplied propagation and impact geography');
  selected = ['PROPAGATION_WAVE', 'IMPACT_ZONE', 'AREA_HOLD'];
 } else {
  if (facts.stages.length < 2 || facts.stages.some(stage => !stage.area_refs.length || !stage.front_refs.length))
   throw new PlannerDataRequiredError('chronological front and area states');
  selected = ['FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP', 'AREA_HOLD'];
  if (facts.routes.some(route => route.required_for_story)) selected.push('ROUTE_REVEAL', 'DIRECTIONAL_FLOW', 'MOVING_OBJECT', 'ENDPOINT_PULSE');
 }
 return freezeEventData(selected);
}
function planningTiming(family, facts, fps) {
 if (facts.scene_timing !== undefined) {
  const timing = suppliedTiming(facts.scene_timing), action = family === 'WAR'
   ? timing.initial_reveal_frames + timing.state_transition_frames * (facts.stages.length - 1) : timing.action_frames;
  if (timing.fps !== fps || timing.total_frames !== timing.event_start_frame + action + timing.final_hold_frames
   || family === 'WAR' && (timing.initial_reveal_frames < 2 || timing.state_transition_frames < 2 || timing.action_frames !== action)
   || family !== 'WAR' && timing.action_frames < 2) throw Error('PLANNER_SCENE_TIMING_STATE_AND_OUTPUT_BINDING_REQUIRED');
  return timing;
 }
 const context = Math.round(fps), approach = Math.round(fps), initial = Math.round(1.2 * fps), hold = Math.round(1.2 * fps);
 const transition = family === 'WAR' ? Math.max(Math.round(2.4 * fps),
  Math.ceil((10 * fps - context - approach - initial - hold) / (facts.stages.length - 1))) : 0;
 const action = family === 'TRANSPORT' ? Math.round((3.6 + Math.min(1.2, facts.routes.length * .4)) * fps)
  : family === 'DISASTER' ? Math.round(4.4 * fps) : Math.round(2.8 * fps);
 const total = context + approach + (family === 'WAR' ? initial + transition * (facts.stages.length - 1) : action) + hold;
 return {fps, total_frames: total, duration_seconds: total / fps, camera_lock_frame: context + approach,
  event_start_frame: context + approach, initial_reveal_frames: initial,
  state_transition_frames: transition, final_hold_frames: hold, action_frames: action,
  frame_policy: 'INTEGER_DETERMINISTIC', blank_interstage_frames: 0};
}
function planBeats(intent, facts, timing) {
 const beats = [], targets = facts.camera.target_geometry_refs;
 let start = 0;
 const add = (type, duration, extra = {}) => {
  const beat = {id: 'BEAT_' + String(beats.length + 1).padStart(2, '0'), type,
   start_frame: start, end_frame: start + duration, duration_frames: duration,
   geometry_refs: [...targets], ...extra};
  start += duration; beats.push(beat); return beat;
 };
 const contextFrames = Math.min(timing.fps, timing.camera_lock_frame), approachFrames = timing.camera_lock_frame - contextFrames;
 if (contextFrames) add('GEOGRAPHIC_CONTEXT', contextFrames, {camera_intent: 'ARRIVE_WITH_CONTEXT'});
 if (approachFrames) add('EVENT_APPROACH', approachFrames, {camera_intent: 'DETAIL_IF_ADMITTED'});
 if (intent.event_family === 'WAR') {
  add('EVENT_ACTION', timing.initial_reveal_frames, {state_id: facts.stages[0].id});
  for (const stage of facts.stages.slice(1)) add('STATE_CHANGE', timing.state_transition_frames, {state_id: stage.id});
 } else add('EVENT_ACTION', timing.action_frames);
 add('HOLD', timing.final_hold_frames, {camera_intent: 'LOCK'});
 return beats;
}
/** Output is portable data. Rendering, projection, glyphs, motion and scale remain Final owners. */
export function compileScenePlan({topic, facts: factsInput, output = {}}) {
 const facts = validateFactDataset(factsInput), intent = topicIntent(topic, facts), features = selectFeatures(intent, facts);
 const fps = integer(output.fps ?? 30, 'OUTPUT_FPS', 1);
 const width = integer(output.width ?? 1080, 'OUTPUT_WIDTH', 1), height = integer(output.height ?? 1920, 'OUTPUT_HEIGHT', 1);
 const timing = planningTiming(intent.event_family, facts, fps), beats = planBeats(intent, facts, timing);
 const scene = {metadata: {schema: PLANNER_SCENE_VERSION, planner_version: '1.0.0',
   fact_dataset_version: PLANNER_FACTS_VERSION, data_mode: facts.data_mode, topic: topic.trim(),
   policy: 'FACT_BASED_VISUAL_GRADE', deterministic: true, user_video_review_required: true,
   semantic_mode: facts.semantic_mode, output: {width, height, fps, audio: false}}, subject: copy(facts.subject), locations: copy(facts.locations),
  time_range: copy(facts.time_range), topic_intent: copy(intent), event_type: intent.event_family,
  selected_features: [...features], camera_intent: {owner: 'CAMERA_DIRECTOR_V5_WITH_DETAIL_ADAPTER',
   arrival_required: true, ...copy(facts.camera)},
  scale_intent: {owner: 'EXISTING_SCALE_CORE', preferred: facts.scale.preferred,
   target_geometry_refs: [...facts.camera.target_geometry_refs]}, beats, geometries: copy(facts.geometries),
  visual_roles: {base_map: 'EXISTING_TERRAIN_AND_REGION_MATERIAL', event: 'EXISTING_AUTO_CONTRAST',
   geographic_markers: 'PROTECTED_NATIVE_MARKERS', text: 'EXISTING_GLYPH_AND_LAYOUT',
   camera: 'READ_ONLY_EXISTING_DIRECTOR', physics: 'NONE'}, timing, source_notes: copy(facts.source_notes)};
 if (facts.markers.length) scene.markers = copy(facts.markers);
 if (facts.text.length) scene.text = copy(facts.text);
 if (intent.event_family === 'WAR') {
  scene.areas = []; scene.front_lines = []; scene.time_steps = [];
  for (const [index, stage] of facts.stages.entries()) {
   const areaIds = [], frontIds = [];
   for (const [part, ref] of stage.area_refs.entries()) {
    const geometry = facts.geometries.find(item => item.id === ref), itemId = 'AREA_' + stage.id + '_' + part;
    scene.areas.push({id: itemId, geometry_ref: ref, stage_id: stage.id, source_id: geometry.source_id,
     role: 'EVENT_AREA', style_role: 'PRIMARY'}); areaIds.push(itemId);
   }
   for (const [part, ref] of stage.front_refs.entries()) {
    const geometry = facts.geometries.find(item => item.id === ref), itemId = 'FRONT_' + stage.id + '_' + part;
    scene.front_lines.push({id: itemId, geometry_ref: ref, stage_id: stage.id, source_id: geometry.source_id,
     role: 'FRONT_LINE', style_role: 'PRIMARY', direction: 'FORWARD'}); frontIds.push(itemId);
   }
   scene.time_steps.push({id: stage.id, date: stage.date, label: stage.label, area_ids: areaIds,
    front_line_ids: frontIds, start_frame: timing.event_start_frame + (index === 0 ? 0
     : timing.initial_reveal_frames + (index - 1) * timing.state_transition_frames),
    transition_frames: index === 0 ? timing.initial_reveal_frames : timing.state_transition_frames});
  }
 }
 const routes = intent.event_family === 'TRANSPORT' ? facts.routes
  : intent.event_family === 'WAR' ? facts.routes.filter(value => value.required_for_story) : [];
 if (routes.length) {
  scene.routes = routes.map(value => ({id: value.id, geometry_ref: value.geometry_ref, direction: value.direction,
   source_id: facts.geometries.find(item => item.id === value.geometry_ref).source_id}));
  scene.moving_objects = routes.map(value => ({id: 'OBJECT_' + value.id, route_id: value.id,
   role: value.object_role, profile: value.object_profile,
   ...(value.object_graphic === undefined ? {} : {graphic: copy(value.object_graphic)})}));
 }
 if (intent.event_family === 'DISASTER') {
  scene.propagations = copy(facts.propagations); scene.impact_zones = copy(facts.impacts);
 }
 if (intent.event_family === 'LINE_METRIC') {
  scene.geographic_lines = copy(facts.geographic_lines); scene.metrics = copy(facts.metrics);
 }
 if (facts.causal_tracks !== undefined) scene.causal_tracks = copy(facts.causal_tracks);
 validateScenePlan(scene);
 return freezeEventData(scene);
}

/** Runtime validation supplements the published JSON Schema with references and Final geometry contracts. */
export function validateScenePlan(scene) {
 const value = record(scene, 'SCENE');
 const allowed = ['metadata', 'subject', 'locations', 'time_range', 'topic_intent', 'event_type', 'selected_features',
  'camera_intent', 'scale_intent', 'beats', 'geometries', 'markers', 'routes', 'moving_objects', 'areas', 'front_lines',
  'metrics', 'time_steps', 'text', 'visual_roles', 'timing', 'source_notes', 'propagations', 'impact_zones', 'geographic_lines', 'causal_tracks'];
 if (Object.keys(value).some(key => !allowed.includes(key))) throw Error('PLANNER_SCENE_UNKNOWN_FIELD');
 const meta = record(value.metadata, 'METADATA');
 if (meta.schema !== PLANNER_SCENE_VERSION || meta.policy !== 'FACT_BASED_VISUAL_GRADE' || meta.deterministic !== true)
  throw Error('PLANNER_SCENE_VERSION_OR_POLICY_REQUIRED');
 const output = record(meta.output, 'OUTPUT');
 for (const key of ['width', 'height', 'fps']) integer(output[key], 'OUTPUT_' + key.toUpperCase(), 1);
 if (output.audio !== false || meta.user_video_review_required !== true) throw Error('PLANNER_SILENT_CANDIDATE_REVIEW_REQUIRED');
 if (!PLANNER_FAMILIES.includes(value.event_type) || value.subject?.event_family !== value.event_type)
  throw Error('PLANNER_SCENE_EVENT_TYPE_REQUIRED');
 if (value.topic_intent?.version !== 'TOPIC_INTENT_V1' || value.topic_intent.subject_id !== value.subject.id
  || value.topic_intent.event_family !== value.event_type || value.topic_intent.topic !== meta.topic)
  throw Error('PLANNER_TOPIC_SCENE_BINDING_REQUIRED');
 const mode = meta.data_mode;
 if (!['PRODUCTION', 'SYNTHETIC_TEST'].includes(mode)) throw Error('PLANNER_SCENE_DATA_MODE_REQUIRED');
 const sources = unique(list(value.source_notes, 'SOURCE_NOTES').map(item => sourceRecord(item, mode)), 'SOURCE');
 const sourceMap = new Map(sources.map(item => [item.id, item]));
 const geometryRecords = unique(list(value.geometries, 'GEOMETRIES').map(item => geometryRecord(item, sourceMap, mode)), 'GEOMETRY');
 if (!equal(geometryRecords, value.geometries)) throw Error('PLANNER_SCENE_NON_CANONICAL_GEOMETRY');
 const geometryMap = new Map(geometryRecords.map(item => [item.id, item]));
 const camera = record(value.camera_intent, 'CAMERA_INTENT'), scale = record(value.scale_intent, 'SCALE_INTENT');
 if (camera.owner !== 'CAMERA_DIRECTOR_V5_WITH_DETAIL_ADAPTER' || camera.detail_policy !== 'FACT_BASED_VISUAL_GRADE'
  || scale.owner !== 'EXISTING_SCALE_CORE') throw Error('PLANNER_EXISTING_ENGINE_OWNERSHIP_REQUIRED');
 validateEventAnchor(camera.anchor); refs(camera.target_geometry_refs, geometryMap, 'CAMERA_GEOMETRY');
 refs(camera.minimum_context_geometry_refs ?? [], geometryMap, 'MINIMUM_CONTEXT_GEOMETRY');
 refs(scale.target_geometry_refs, geometryMap, 'SCALE_GEOMETRY'); nativeContext(camera.native_context);
 const timing = record(value.timing, 'TIMING');
 for (const key of ['fps', 'total_frames', 'camera_lock_frame', 'event_start_frame', 'initial_reveal_frames',
  'state_transition_frames', 'final_hold_frames', 'action_frames']) integer(timing[key], key.toUpperCase(), ['fps', 'total_frames'].includes(key) ? 1 : 0);
 if (timing.camera_lock_frame !== timing.event_start_frame || timing.event_start_frame >= timing.total_frames
  || timing.duration_seconds !== timing.total_frames / timing.fps || timing.blank_interstage_frames !== 0)
  throw Error('PLANNER_TIMELINE_LOCK_AND_DURATION_REQUIRED');
 if (timing.fps !== output.fps) throw Error('PLANNER_OUTPUT_TIMING_FPS_BINDING_REQUIRED');
 const beats = unique(list(value.beats, 'BEATS'), 'BEAT');
 let end = 0;
 for (const beat of beats) {
  id(beat.id, 'BEAT_ID'); text(beat.type, 'BEAT_TYPE');
  integer(beat.start_frame, 'BEAT_START'); integer(beat.end_frame, 'BEAT_END', 1); integer(beat.duration_frames, 'BEAT_DURATION', 1);
  if (beat.start_frame !== end || beat.end_frame - beat.start_frame !== beat.duration_frames) throw Error('PLANNER_CONTIGUOUS_BEATS_REQUIRED');
  if (['EVENT_ACTION', 'STATE_CHANGE', 'HOLD'].includes(beat.type) && beat.start_frame < timing.camera_lock_frame)
   throw Error('PLANNER_EVENT_MUST_FOLLOW_CAMERA_LOCK');
  refs(beat.geometry_refs, geometryMap, 'BEAT_GEOMETRY'); end = beat.end_frame;
 }
 if (end !== timing.total_frames || beats.at(-1)?.type !== 'HOLD' || beats.at(-1).duration_frames !== timing.final_hold_frames)
  throw Error('PLANNER_FINAL_HOLD_REQUIRED');
 const features = list(value.selected_features, 'SELECTED_FEATURES');
 if (!features.length || new Set(features).size !== features.length || features.some(feature => !PLANNER_FEATURES.includes(feature)))
  throw Error('PLANNER_KNOWN_UNIQUE_FEATURES_REQUIRED');
 const excluded = value.event_type === 'WAR' ? ['PROPAGATION_WAVE', 'IMPACT_ZONE', 'GEOGRAPHIC_LINE_REVEAL', 'METRIC_ANNOTATION']
  : value.event_type === 'DISASTER' ? ['ROUTE_REVEAL', 'MOVING_OBJECT', 'FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP', 'METRIC_ANNOTATION']
   : value.event_type === 'TRANSPORT' ? ['PROPAGATION_WAVE', 'IMPACT_ZONE', 'FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP', 'METRIC_ANNOTATION']
    : ['ROUTE_REVEAL', 'MOVING_OBJECT', 'PROPAGATION_WAVE', 'IMPACT_ZONE', 'FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP'];
 if (features.some(feature => excluded.includes(feature))) throw Error('PLANNER_UNJUSTIFIED_FEATURE_FOR_EVENT');
 const excludedCategories = value.event_type === 'WAR' ? ['propagations', 'impact_zones', 'geographic_lines', 'metrics']
  : value.event_type === 'DISASTER' ? ['routes', 'moving_objects', 'front_lines', 'areas', 'time_steps', 'geographic_lines', 'metrics']
   : value.event_type === 'TRANSPORT' ? ['propagations', 'impact_zones', 'front_lines', 'areas', 'time_steps', 'geographic_lines', 'metrics']
    : ['routes', 'moving_objects', 'propagations', 'impact_zones', 'front_lines', 'areas', 'time_steps'];
 if (excludedCategories.some(category => value[category] !== undefined)) throw Error('PLANNER_UNUSED_CATEGORY_MUST_BE_OMITTED');
 const ranges = record(value.time_range, 'TIME_RANGE');
 date(ranges.start, 'TIME_RANGE_START'); date(ranges.end, 'TIME_RANGE_END');
 if (ranges.start > ranges.end) throw Error('PLANNER_TIME_RANGE_ORDER');
 const locations = unique(list(value.locations, 'LOCATIONS'), 'LOCATION');
 if (!locations.length) throw Error('PLANNER_LOCATION_CONTEXT_REQUIRED');
 for (const location of locations) { id(location.id); text(location.label, 'LOCATION_LABEL'); validateEventAnchor(location.anchor); }
 const categoryMap = {};
 for (const [category, types] of Object.entries({areas: ['Polygon', 'MultiPolygon'], front_lines: ['LineString'],
  routes: ['LineString'], impact_zones: ['Polygon', 'MultiPolygon'], geographic_lines: ['LineString']})) {
  categoryMap[category] = new Map(unique(list(value[category] ?? [], category), category).map(item => {
   id(item.id); expectGeometry(item.geometry_ref, geometryMap, types, category); return [item.id, item];
  }));
 }
 if (features.some(feature => ['ROUTE_REVEAL', 'DIRECTIONAL_FLOW', 'MOVING_OBJECT', 'ENDPOINT_PULSE'].includes(feature))
  && (!categoryMap.routes.size || !value.moving_objects?.length)) throw Error('PLANNER_MOVING_OBJECT_ROUTE_DATA_REQUIRED');
 if (value.event_type === 'WAR') {
  const steps = unique(list(value.time_steps, 'TIME_STEPS'), 'TIME_STEP');
  if (steps.length < 2 || !categoryMap.areas.size || !categoryMap.front_lines.size
   || !['FRONT_LINE', 'STATE_TRANSITION', 'TIME_STEP'].every(feature => features.includes(feature)))
   throw Error('PLANNER_WAR_STATE_FEATURES_REQUIRED');
  let priorDate = '', priorEnd = timing.event_start_frame;
  for (const step of steps) {
   date(step.date, 'STATE_DATE'); text(step.label, 'STATE_LABEL');
   integer(step.start_frame, 'STATE_START'); integer(step.transition_frames, 'STATE_DURATION', 2);
   if (step.date <= priorDate || step.date < ranges.start || step.date > ranges.end || step.start_frame !== priorEnd)
    throw Error('PLANNER_CHRONOLOGICAL_STATE_TIMELINE_REQUIRED');
   const areaIds = refs(step.area_ids, categoryMap.areas, 'STATE_AREA'), frontIds = refs(step.front_line_ids, categoryMap.front_lines, 'STATE_FRONT');
   if (!areaIds.length || !frontIds.length || areaIds.some(ref => categoryMap.areas.get(ref).stage_id !== step.id)
    || frontIds.some(ref => categoryMap.front_lines.get(ref).stage_id !== step.id)) throw Error('PLANNER_STATE_GEOMETRY_BINDING_REQUIRED');
   priorDate = step.date; priorEnd = step.start_frame + step.transition_frames;
  }
  if (priorEnd !== beats.at(-1).start_frame) throw Error('PLANNER_STATE_TIMELINE_MUST_END_AT_HOLD');
 }
 if (value.event_type === 'TRANSPORT' && (!categoryMap.routes.size || !value.moving_objects?.length
  || !features.includes('MOVING_OBJECT'))) throw Error('PLANNER_TRANSPORT_ROUTE_OBJECT_REQUIRED');
 for (const object of unique(list(value.moving_objects ?? [], 'MOVING_OBJECTS'), 'MOVING_OBJECT')) {
  id(object.id); text(object.role, 'OBJECT_ROLE'); text(object.profile, 'OBJECT_PROFILE');
  if (!categoryMap.routes.has(object.route_id)) throw Error('PLANNER_OBJECT_ROUTE_REFERENCE_REQUIRED');
 }
 if (value.event_type === 'DISASTER' && (!value.propagations?.length || !categoryMap.impact_zones.size
  || !features.includes('PROPAGATION_WAVE') || !features.includes('IMPACT_ZONE'))) throw Error('PLANNER_DISASTER_PROPAGATION_IMPACT_REQUIRED');
 if (value.event_type === 'LINE_METRIC' && (!categoryMap.geographic_lines.size || !value.metrics?.length))
  throw Error('PLANNER_LINE_METRIC_REQUIRED');
 for (const marker of unique(list(value.markers ?? [], 'MARKERS'), 'MARKER')) {
  id(marker.id); text(marker.label, 'MARKER_LABEL'); validateEventAnchor(marker.anchor);
 }
 for (const metric of unique(list(value.metrics ?? [], 'METRICS'), 'METRIC')) {
  const source = sourceMap.get(metric.source_id);
  if (!source) throw Error('PLANNER_METRIC_SOURCE_REFERENCE_REQUIRED');
  compileEventIntent({data_mode: mode, metric: {...metric, source: contractSource(source)}});
 }
 for (const propagation of unique(list(value.propagations ?? [], 'PROPAGATIONS'), 'PROPAGATION')) {
  id(propagation.id); validateEventAnchor(propagation.origin);
  if (!sourceMap.has(propagation.source_id) || propagation.visual_only !== true || propagation.physical_simulation !== false)
   throw Error('PLANNER_PROPAGATION_SOURCE_AND_VISUAL_ONLY_REQUIRED');
  if (propagation.geometry_ref !== undefined) expectGeometry(propagation.geometry_ref, geometryMap, ['LineString'], 'PROPAGATION');
  else if (!Number.isFinite(propagation.radius_end_degrees) || !Number.isFinite(propagation.radius_start_degrees ?? 0)
   || propagation.radius_end_degrees <= (propagation.radius_start_degrees ?? 0) || propagation.radius_end_degrees > 60
   || (propagation.radius_start_degrees ?? 0) < 0) throw Error('PLANNER_VISUAL_PROPAGATION_RADIUS_REQUIRED');
 }
 if (value.causal_tracks !== undefined) {
  const tracks = unique(list(value.causal_tracks, 'CAUSAL_TRACKS').map(causalTrackRecord), 'CAUSAL_TRACK');
  if (!equal(tracks, value.causal_tracks)) throw Error('PLANNER_CAUSAL_NON_CANONICAL_TRACKS_REQUIRED');
  validateCausalTracks(tracks, {sourceMap, geometryMap, routes: value.routes ?? [], objects: value.moving_objects ?? [],
   steps: value.time_steps ?? [], fronts: value.front_lines ?? [], timing, mode});
 }
 // No timestamp, environment path, renderer state or screen layout is part of this portable contract.
 return {valid: true, schema: PLANNER_SCENE_VERSION, event_type: value.event_type,
  selected_features: [...features], total_frames: timing.total_frames, geometry_count: geometryRecords.length,
  timeline_deterministic: true, camera_owned_by_existing_engine: true};
}
