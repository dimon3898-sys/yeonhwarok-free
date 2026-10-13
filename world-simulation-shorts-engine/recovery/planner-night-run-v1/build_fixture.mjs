/** New fixture data only. Original state sketches and FINAL feature owners remain unchanged. */
import {compileEventIntent, freezeEventData} from '../../web/map_infographic_v1/event_contract_v1.mjs';
import {compileGeographicLinePrimitive, evaluateGeographicLineReveal} from '../../web/map_infographic_v1/event_line_v1.mjs';
import {compileScenePlan, validateFactDataset, validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';

const copy = value => structuredClone(value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const clamp = value => Math.max(0, Math.min(1, value));
const point = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const rectangle = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const serialize = value => JSON.stringify(value, null, 2) + '\n';
let nodeFiles, nodePaths, nodeUrl, nodeCrypto, defaults;
if (typeof process !== 'undefined' && process.versions?.node) {
 [nodeFiles, nodePaths, nodeUrl, nodeCrypto] = await Promise.all([
  import('node:fs'), import('node:path'), import('node:url'), import('node:crypto')]);
 const load = (path, expected) => {
  const bytes = nodeFiles.readFileSync(new URL(path, import.meta.url));
  const actual = nodeCrypto.createHash('sha256').update(bytes).digest('hex');
  if (actual !== expected) throw Error('NIGHT_ORIGINAL_INPUT_HASH_CHANGED: ' + path);
  return JSON.parse(bytes);
 };
 defaults = {
  facts: load('../planner-scene-json-v1/data/FACT_DATA.json', '753f629a22f8bc2e5676ebdf4d7c9e64edd6a7314188f55cd3ca3237355a9e65'),
  native: load('../planner-scene-json-v1/data/NATIVE_PENINSULA.json', '6d1f7518080a9ea753963aecb7310ad20eff460f7d19ac94268597688990b3a1'),
  scene: load('../planner-scene-json-v1/fixtures/SCENE_PLAN.json', 'ee4fdfc84798849288037cc4c8718cfe5c210c0da076eb0551a084d379e41074')
 };
}

export const NIGHT_TIMING = freezeEventData({fps: 30, total_frames: 420, duration_seconds: 14,
 camera_lock_frame: 0, event_start_frame: 0, initial_reveal_frames: 36, state_transition_frames: 87,
 final_hold_frames: 36, action_frames: 384, frame_policy: 'INTEGER_DETERMINISTIC', blank_interstage_frames: 0});
export const NIGHT_PHASES = freezeEventData([
 {index: 0, action_kind: 'RETREAT', contact_kind: 'ARRIVAL', motion_start_frame: 0,
  contact_frame: 70, control_start_frame: 84, control_end_frame: 123, end_frame: 123},
 {index: 1, action_kind: 'ADVANCE', contact_kind: 'SCHEMATIC_FRONT_CONTACT', motion_start_frame: 123,
  contact_frame: 174, control_start_frame: 188, control_end_frame: 210, end_frame: 210},
 {index: 2, action_kind: 'RETREAT', contact_kind: 'ARRIVAL', motion_start_frame: 210,
  contact_frame: 261, control_start_frame: 275, control_end_frame: 297, end_frame: 297},
 {index: 3, action_kind: 'SETTLEMENT', contact_kind: 'NONE', motion_start_frame: 297,
  contact_frame: 298, control_start_frame: 298, control_end_frame: 384, end_frame: 384}
]);
export const SCHEMATIC_ACTOR_GRAPHIC = freezeEventData({width_px: 64, height_px: 40, polygons: [
 {points: [[-.5, -.25], [.03, -.25], [.03, -.5], [.5, 0], [.03, .5], [.03, .25], [-.5, .25]], color: [.07, .1, .13, 1]},
 {points: [[-.44, -.16], [.09, -.16], [.09, -.35], [.4, 0], [.09, .35], [.09, .16], [-.44, .16]], color: [.98, .94, .82, 1]},
 {points: [[.1, -.3], [.38, 0], [.1, .3], [.1, .12], [.19, 0], [.1, -.12]], color: [.08, .8, .76, 1]}
]});
export const NIGHT_SCHEMATIC_SOURCE = freezeEventData({id: 'AUTHORED_SCHEMATIC_STATE_TRANSITION',
 source_type: 'AUTHORED_SCHEMATIC_STATE_TRANSITION', verification_status: 'VERIFIED',
 verification_basis: 'DERIVED_CURATED_STATE_GEOMETRY',
 source_reference: 'SCHEMATIC_STATES; HISTORY_START; HISTORY_CAMPAIGNS; HISTORY_OVERVIEW',
 original_fact_data_sha256: '753f629a22f8bc2e5676ebdf4d7c9e64edd6a7314188f55cd3ca3237355a9e65',
 original_native_peninsula_sha256: '6d1f7518080a9ea753963aecb7310ad20eff460f7d19ac94268597688990b3a1',
 semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false,
 historical_accuracy: 'CURATED_PHASE_DIRECTION_ONLY_NOT_SURVEYED_UNIT_DATA',
 note: 'GraphicDirectionCueNotUnit/BattleRoute. Short local arrows communicate the established direction of broad control phases. They do not show a surveyed military unit position, unit journey, exact attack location, fabricated battle, or observed timing. A front contact is a graphic contact with supplied schematic front geometry only.'});

function originalFacts(value) {
 const facts = value ?? defaults?.facts;
 if (!facts || facts.stages?.length !== 5) throw Error('NIGHT_ORIGINAL_FIVE_STATE_FACTS_REQUIRED');
 return facts;
}
function nativeData(value) {
 const native = value ?? defaults?.native;
 if (!native?.countries?.COUNTRY_KOR || !native.countries.COUNTRY_PRK || !native.mainland?.geometry)
  throw Error('NIGHT_UNCHANGED_NATIVE_PENINSULA_REQUIRED');
 return native;
}
function phaseIds(index) {
 const suffix = String(index + 1).padStart(2, '0');
 return {routeId: 'PHASE_ROUTE_' + suffix, geometryId: 'PHASE_ROUTE_GEOMETRY_' + suffix, trackId: 'PHASE_TRACK_' + suffix};
}
function frontPrimitive(facts, stage) {
 const row = facts.geometries.find(item => item.id === stage.front_refs[0]);
 const source = facts.source_notes.find(item => item.id === row?.source_id);
 if (!row || !source) throw Error('NIGHT_SUPPLIED_FRONT_GEOMETRY_REQUIRED');
 return compileGeographicLinePrimitive(compileEventIntent({data_mode: facts.data_mode,
  line: {geometry: row.geometry, source, direction: 'FORWARD', style_role: 'PRIMARY'}}),
  {project: coordinates => coordinates});
}
/** The existing V1 arc sampler supplies the exact point on each unchanged geographic front. */
export function sampleSuppliedFront({facts, stageIndex, fraction}) {
 const original = originalFacts(facts);
 if (!Number.isInteger(stageIndex) || !original.stages[stageIndex] || !Number.isFinite(fraction) || fraction < 0 || fraction > 1)
  throw Error('NIGHT_FRONT_SAMPLE_REQUIRED');
 const primitive = frontPrimitive(original, original.stages[stageIndex]);
 return fraction === 0 ? copy(primitive.screenCoordinates[0])
  : copy(evaluateGeographicLineReveal(primitive, fraction).path.at(-1));
}

function pointOnSegment(p, a, b) {
 const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
 return length > 0 && Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) <= 1e-10 * length
  && p[0] >= Math.min(a[0], b[0]) - 1e-10 && p[0] <= Math.max(a[0], b[0]) + 1e-10
  && p[1] >= Math.min(a[1], b[1]) - 1e-10 && p[1] <= Math.max(a[1], b[1]) + 1e-10;
}
function inRing(p, ring) {
 let inside = false;
 for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
  const a = ring[j], b = ring[i];
  if (pointOnSegment(p, a, b)) return true;
  if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function inPolygon(p, rings) { return inRing(p, rings[0]) && !rings.slice(1).some(ring => inRing(p, ring)); }
/** Containment tests use the unchanged Natural Earth native geometries, including holes. */
export function nativeLandPoint(coordinates, {nativePeninsula} = {}) {
 const native = nativeData(nativePeninsula);
 if (!point(coordinates)) throw Error('NIGHT_NATIVE_LAND_POINT_REQUIRED');
 const inside = geometry => geometry.type === 'Polygon' ? inPolygon(coordinates, geometry.coordinates)
  : geometry.type === 'MultiPolygon' && geometry.coordinates.some(rings => inPolygon(coordinates, rings));
 return {mainland: inside(native.mainland.geometry),
  country_ids: Object.entries(native.countries).filter(([, geometry]) => inside(geometry)).map(([id]) => id)};
}
function pointSegmentDistance(p, a, b) {
 const dx = b[0] - a[0], dy = b[1] - a[1], length = dx * dx + dy * dy;
 const t = length ? clamp(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length) : 0;
 return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
function segmentDistance(a, b, c, d) {
 const ac = cross(a, b, c), ad = cross(a, b, d), ca = cross(c, d, a), cb = cross(c, d, b);
 if (((ac > 0 && ad < 0) || (ac < 0 && ad > 0)) && ((ca > 0 && cb < 0) || (ca < 0 && cb > 0))) return 0;
 return Math.min(pointSegmentDistance(a, c, d), pointSegmentDistance(b, c, d), pointSegmentDistance(c, a, b), pointSegmentDistance(d, a, b));
}
function projectedPreflight(geometry, {project, nativeBoundarySegments, protectedGraphics, safeArea, sweptSupportPx}) {
 const path = geometry.coordinates.map(coordinates => project(copy(coordinates)));
 if (!path.every(point)) throw Error('NIGHT_NATIVE_PROJECTED_COORDINATES_REQUIRED');
 const roi = [Math.min(...path.map(p => p[0])) - sweptSupportPx, Math.min(...path.map(p => p[1])) - sweptSupportPx,
  Math.max(...path.map(p => p[0])) + sweptSupportPx, Math.max(...path.map(p => p[1])) + sweptSupportPx];
 if (roi[0] < safeArea[0] || roi[1] < safeArea[1] || roi[2] > safeArea[2] || roi[3] > safeArea[3])
  return {passed: false, reason: 'SWEPT_SUPPORT_OUTSIDE_SAFE_AREA', roi};
 let minimumClearancePixels = Infinity;
 for (const edge of nativeBoundarySegments) for (let index = 1; index < path.length; index++) {
  const clearance = segmentDistance(path[index - 1], path[index], edge.a, edge.b) - edge.radiusPx - sweptSupportPx;
  minimumClearancePixels = Math.min(minimumClearancePixels, clearance);
  if (clearance <= 0) return {passed: false, reason: 'NATIVE_BOUNDARY_COLLISION', sourceId: edge.sourceId, clearancePixels: clearance};
 }
 // Strict measured text/panel exclusion covers the entire actor and pulse sweep as well as route halo.
 for (const item of protectedGraphics.filter(item => item.kind !== 'MARKER')) {
  const [left, top, right, bottom] = item.box;
  if (roi[0] <= right && roi[2] >= left && roi[1] <= bottom && roi[3] >= top)
   return {passed: false, reason: 'STRICT_TEXT_OR_PANEL_COLLISION', kind: item.kind, role: item.role};
 }
 return {passed: true, sweptSupportPx, sweptRoi: roi, projectedLengthPixels: Math.hypot(path[1][0] - path[0][0], path[1][1] - path[0][1]),
  boundarySegmentCount: nativeBoundarySegments.length, minimumClearancePixels,
  strictTextAndPanelExclusion: true, nativeGeometryUnchanged: true, noBoundaryOcclusionException: true};
}

function geographicCandidateData({facts, native, frontFractions, tailFractions}) {
 if (!frontFractions.length || frontFractions.some(value => !Number.isFinite(value) || value < .15 || value > .85)
  || !tailFractions.length || tailFractions.some(value => !Number.isFinite(value) || value <= 0 || value > 1))
  throw Error('NIGHT_LOCAL_CUE_CANDIDATES_REQUIRED');
 const groups = NIGHT_PHASES.slice(0, 3).map(phase => {
  const rawCandidates = [], rejected = {}, ids = phaseIds(phase.index);
  const fromStateId = facts.stages[phase.index].id, toStateId = facts.stages[phase.index + 1].id;
  const targetFrontId = 'FRONT_' + toStateId + '_0';
  for (const arcFraction of frontFractions) for (const tailFraction of tailFractions) {
   const previous = sampleSuppliedFront({facts, stageIndex: phase.index, fraction: arcFraction});
   const target = sampleSuppliedFront({facts, stageIndex: phase.index + 1, fraction: arcFraction});
   const start = target.map((coordinate, axis) => coordinate - (coordinate - previous[axis]) * tailFraction);
   const routeGeometry = {type: 'LineString', coordinates: [start, copy(target)]};
   const points = Array.from({length: 17}, (_, index) => start.map((coordinate, axis) => coordinate + (target[axis] - coordinate) * index / 16));
   const land = points.map(coordinates => nativeLandPoint(coordinates, {nativePeninsula: native}));
   const countryIds = land[0].country_ids.filter(id => land.every(row => row.country_ids.includes(id)));
   if (!land.every(row => row.mainland) || !countryIds.length) {
    rejected.LOCAL_CUE_OUTSIDE_NATIVE_COUNTRY_INTERIOR = (rejected.LOCAL_CUE_OUTSIDE_NATIVE_COUNTRY_INTERIOR ?? 0) + 1;
    continue;
   }
   rawCandidates.push({trackId: ids.trackId, routeId: ids.routeId, geometryId: ids.geometryId,
    fromStateId, toStateId, routeGeometry, targetFrontId, contactAnchor: copy(target), arcFraction, tailFraction,
    landScreening: {passed: true, sampleCount: points.length, nativeMainland: true, nativeCountryIds: countryIds,
     source: 'UNCHANGED_NATIVE_PENINSULA_NATURAL_EARTH', requiresActualProjectedSweptSupportAdmission: true},
    id: ids.routeId, geometry_ref: ids.geometryId, geometry: copy(routeGeometry), phase_index: phase.index,
    source_id: NIGHT_SCHEMATIC_SOURCE.id, target_front_line_id: targetFrontId,
    contact_anchor: copy(target), front_fraction: arcFraction, tail_fraction: tailFraction, native_country_ids: countryIds,
    semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false,
    note: 'GraphicDirectionCueNotUnit/BattleRoute; LOCAL_COUNTRY_INTERIOR_PHASE_DIRECTION_ONLY'});
  }
  return {phase_index: phase.index, action_kind: phase.action_kind, trackId: ids.trackId, fromStateId, toStateId,
   rawCandidates, candidates: rawCandidates, rejected};
 });
 return {version: 'NIGHT_LOCAL_DIRECTION_CANDIDATES_V1', groups, groupedRawCandidates: groups,
  requires_actual_gpu_adapter_admission: true, native_geometry_unchanged: true,
  candidate_recipe: 'Existing Event V1 identity front arc sample; target-minus-phase-vector tail fraction; no new projection or geographic route simulation.'};
}

/** Without project, return geographic data for the authoritative frozen native browser preflight. */
export function candidateDataVariants({project, nativeBoundarySegments, protectedGraphics, safeArea,
 originalFacts: suppliedFacts, nativePeninsula, sweptSupportPx = 48,
 frontFractions = [.5, .45, .55, .4, .6, .35, .65, .3, .7, .25, .75, .2, .8, .15, .85],
 cueLengths = [240, 200, 160, 130, 100, 80, 64],
 tailFractions = [.05, .08, .1, .15, .2, .25, .3, .4, .5, .75, 1]} = {}) {
 const facts = originalFacts(suppliedFacts), native = nativeData(nativePeninsula);
 if (project === undefined) return geographicCandidateData({facts, native, frontFractions, tailFractions});
 if (typeof project !== 'function' || !rectangle(safeArea) || !Array.isArray(nativeBoundarySegments) || !nativeBoundarySegments.length
  || !Array.isArray(protectedGraphics) || !Number.isFinite(sweptSupportPx) || sweptSupportPx < 48)
  throw Error('NIGHT_ACTUAL_NATIVE_PREFLIGHT_CONTEXT_REQUIRED');
 if (nativeBoundarySegments.some(edge => !point(edge.a) || !point(edge.b) || !Number.isFinite(edge.radiusPx) || edge.radiusPx <= 0))
  throw Error('NIGHT_NATIVE_BOUNDARY_SUPPORT_REQUIRED');
 if (protectedGraphics.some(item => !['MARKER', 'TEXT', 'PANEL'].includes(item.kind) || !rectangle(item.box)))
  throw Error('NIGHT_NATIVE_MEASURED_RESERVATIONS_REQUIRED');
 if (!frontFractions.length || frontFractions.some(value => !Number.isFinite(value) || value < .15 || value > .85)
  || !cueLengths.length || cueLengths.some(value => !Number.isFinite(value) || value <= 0)) throw Error('NIGHT_LOCAL_CUE_CANDIDATES_REQUIRED');
 const groups = NIGHT_PHASES.slice(0, 3).map(phase => {
  const candidates = [], rejected = {}, ids = phaseIds(phase.index);
  const reject = reason => { rejected[reason] = (rejected[reason] ?? 0) + 1; };
  for (const desiredLengthPixels of cueLengths) for (const frontFraction of frontFractions) {
   const previous = sampleSuppliedFront({facts, stageIndex: phase.index, fraction: frontFraction});
   const target = sampleSuppliedFront({facts, stageIndex: phase.index + 1, fraction: frontFraction});
   const p = project(copy(previous)), q = project(copy(target));
   if (!point(p) || !point(q)) throw Error('NIGHT_NATIVE_PROJECTED_COORDINATES_REQUIRED');
   const fullLength = Math.hypot(q[0] - p[0], q[1] - p[1]);
   if (fullLength <= desiredLengthPixels) { reject('LOCAL_CUE_MUST_BE_SHORTER_THAN_PHASE_VECTOR'); continue; }
   const fraction = desiredLengthPixels / fullLength;
   const start = target.map((coordinate, axis) => coordinate - (coordinate - previous[axis]) * fraction);
   const geometry = {type: 'LineString', coordinates: [start, copy(target)]};
   const points = Array.from({length: 17}, (_, index) => start.map((coordinate, axis) => coordinate + (target[axis] - coordinate) * index / 16));
   const land = points.map(coordinates => nativeLandPoint(coordinates, {nativePeninsula: native}));
   const countryIds = land[0].country_ids.filter(id => land.every(row => row.country_ids.includes(id)));
   if (!land.every(row => row.mainland) || !countryIds.length) { reject('LOCAL_CUE_OUTSIDE_NATIVE_COUNTRY_INTERIOR'); continue; }
   const preflight = projectedPreflight(geometry, {project, nativeBoundarySegments, protectedGraphics, safeArea, sweptSupportPx});
   if (!preflight.passed) { reject(preflight.reason); continue; }
   candidates.push({id: ids.routeId, geometry_ref: ids.geometryId, phase_index: phase.index, geometry,
    front_fraction: frontFraction, desired_length_pixels: desiredLengthPixels,
    source_id: NIGHT_SCHEMATIC_SOURCE.id, target_front_line_id: 'FRONT_' + facts.stages[phase.index + 1].id + '_0',
    contact_anchor: copy(target), native_country_ids: countryIds, preflight,
    semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false,
    note: 'GraphicDirectionCueNotUnit/BattleRoute; LOCAL_COUNTRY_INTERIOR_PHASE_DIRECTION_ONLY'});
  }
  return {phase_index: phase.index, action_kind: phase.action_kind, candidates, rejected};
 });
 return {version: 'NIGHT_LOCAL_DIRECTION_CANDIDATES_V1', groups,
  requires_actual_gpu_adapter_admission: true, native_geometry_unchanged: true,
  candidate_recipe: 'Existing Event V1 identity front arc sample; short target-minus-phase-vector fraction; actual native projection admission.'};
}
export function selectNightRoutes(options) {
 const variants = candidateDataVariants(options);
 if (typeof options?.project !== 'function') throw Error('NIGHT_ROUTE_SELECTION_REQUIRES_ACTUAL_NATIVE_PROJECTION');
 const routes = variants.groups.map(group => {
  if (!group.candidates.length) throw Object.assign(Error('NIGHT_NO_NATIVE_SAFE_LOCAL_CUE'), {phaseIndex: group.phase_index, rejected: group.rejected});
  return copy(group.candidates[0]);
 });
 return {routes, variants};
}

/** Accept selected data only; never fabricate a route or a historical unit position. */
export function buildNightFacts({routes, originalFacts: suppliedFacts, nativePeninsula} = {}) {
 const original = originalFacts(suppliedFacts), native = nativeData(nativePeninsula), facts = copy(original);
 if (!Array.isArray(routes) || routes.length !== 3) throw Error('NIGHT_THREE_SELECTED_LOCAL_ROUTE_GEOMETRIES_REQUIRED');
 facts.source_notes.push(copy(NIGHT_SCHEMATIC_SOURCE));
 facts.scene_timing = copy(NIGHT_TIMING);
 facts.routes = [];
 facts.causal_tracks = NIGHT_PHASES.map(phase => {
  const ids = phaseIds(phase.index), {index, ...schedule} = phase;
  const track = {id: ids.trackId, source_id: NIGHT_SCHEMATIC_SOURCE.id,
   ...schedule, from_state_id: facts.stages[index].id, to_state_id: facts.stages[index + 1].id,
   semantic_mode: 'SCHEMATIC_STATE_TRANSITION', represents_historical_unit: false};
  if (index < 3) {
   const selected = routes[index], geometry = copy(selected?.routeGeometry ?? selected?.geometry ?? selected);
   if (geometry.type !== 'LineString' || geometry.coordinates?.length !== 2 || !geometry.coordinates.every(point)
    || equal(geometry.coordinates[0], geometry.coordinates[1])) throw Error('NIGHT_SELECTED_TWO_POINT_LOCAL_CUE_REQUIRED');
   const endpoint = geometry.coordinates.at(-1);
   const declaredAnchor = selected.contactAnchor ?? selected.contact_anchor;
   if (declaredAnchor && !equal(declaredAnchor, endpoint)) throw Error('NIGHT_SELECTED_CONTACT_ENDPOINT_MISMATCH');
   const startLand = nativeLandPoint(geometry.coordinates[0], {nativePeninsula: native});
   const endLand = nativeLandPoint(endpoint, {nativePeninsula: native});
   if (!startLand.mainland || !endLand.mainland || !startLand.country_ids.some(id => endLand.country_ids.includes(id)))
    throw Error('NIGHT_SELECTED_ROUTE_NATIVE_INTERIOR_REQUIRED');
   facts.geometries.push({id: ids.geometryId, geometry, source_id: NIGHT_SCHEMATIC_SOURCE.id});
   facts.routes.push({id: ids.routeId, geometry_ref: ids.geometryId, direction: 'FORWARD', required_for_story: true,
    object_role: 'SCHEMATIC_PHASE_ACTOR', object_profile: 'COMMON_DIRECTIONAL_ACTOR', object_graphic: copy(SCHEMATIC_ACTOR_GRAPHIC)});
   Object.assign(track, {route_id: ids.routeId, object_id: 'OBJECT_' + ids.routeId,
    target_front_line_id: 'FRONT_' + facts.stages[index + 1].id + '_0', contact_anchor: copy(endpoint)});
  }
  return track;
 });
 facts.authoring = {...facts.authoring, build_recipe: 'node recovery/planner-night-run-v1/build_fixture.mjs --routes <selected-routes.json> --write',
  actor_semantics: 'GraphicDirectionCueNotUnit/BattleRoute', represents_historical_unit: false,
  causal_schedule: 'INTEGER_FRAME_VISUAL_COMPOSITION_NOT_OBSERVED_HISTORICAL_TIMING',
  local_direction_cues: routes.map((route, index) => ({route_id: phaseIds(index).routeId,
   phase: NIGHT_PHASES[index].action_kind, supplied_target_front: facts.stages[index + 1].front_refs[0],
   front_fraction: route.arcFraction ?? route.front_fraction ?? null,
   tail_fraction: route.tailFraction ?? route.tail_fraction ?? null, desired_length_pixels: route.desired_length_pixels ?? null,
   native_country_ids: route.native_country_ids ?? route.landScreening?.nativeCountryIds ?? null, preflight: route.preflight ?? null,
   note: 'Short country-interior direction cue; no military unit route or fabricated battle implied.'}))};
 if (!equal(facts.stages, original.stages) || !equal(facts.geometries.slice(0, original.geometries.length), original.geometries)
  || !equal(facts.source_notes.slice(0, original.source_notes.length), original.source_notes))
  throw Error('NIGHT_ORIGINAL_SOURCE_STATE_CHANGED');
 validateFactDataset(facts);
 return freezeEventData(facts);
}
export function compileNightScene(options = {}) {
 const facts = options.facts ?? buildNightFacts(options);
 const scene = compileScenePlan({topic: options.topic ?? defaults?.scene.metadata.topic ?? facts.subject.label, facts,
  output: {width: 1080, height: 1920, fps: 30}});
 validateScenePlan(scene);
 if (scene.timing.total_frames !== 420 || scene.time_steps.length !== 5 || scene.beats[0].start_frame !== 0)
  throw Error('NIGHT_COMPILED_REVIEW_SCOPE_CHANGED');
 return scene;
}

// Generation is explicit and writes only new night-run fixture paths. Importing performs no writes.
if (nodePaths && process.argv[1] && nodePaths.resolve(process.argv[1]) === nodeUrl.fileURLToPath(import.meta.url)) {
 const routesArgument = process.argv.indexOf('--routes');
 if (routesArgument < 0 || !process.argv[routesArgument + 1]) throw Error('Usage: node build_fixture.mjs --routes <selected-routes.json> [--write]');
 const selected = JSON.parse(nodeFiles.readFileSync(nodePaths.resolve(process.argv[routesArgument + 1]), 'utf8'));
 const routes = Array.isArray(selected) ? selected : selected.routes;
 const facts = buildNightFacts({routes}), scene = compileNightScene({facts});
 if (process.argv.includes('--write')) {
  const folder = nodePaths.resolve(nodePaths.dirname(nodeUrl.fileURLToPath(import.meta.url)), 'fixtures');
  nodeFiles.mkdirSync(folder, {recursive: true});
  for (const [filename, data] of Object.entries({'FACT_DATA.json': facts, 'SCENE_PLAN.json': scene,
   'SELECTED_LOCAL_ROUTES.json': routes, 'SOURCE_REFERENCES.json': {version: 'NIGHT_SCHEMATIC_SOURCE_V1', source_notes: facts.source_notes}})) {
   const destination = nodePaths.resolve(folder, filename);
   const bytes = serialize(data);
   if (nodeFiles.existsSync(destination) && nodeFiles.readFileSync(destination, 'utf8') !== bytes)
    throw Error('NIGHT_EXISTING_FIXTURE_WOULD_CHANGE: ' + filename);
   nodeFiles.writeFileSync(destination, bytes);
  }
 }
 console.log(JSON.stringify({status: 'PASS', writes: process.argv.includes('--write'), states: scene.time_steps.length,
  actorRoutes: scene.routes.length, causalTracks: scene.causal_tracks.length, frames: scene.timing.total_frames,
  nativeGeometryUnchanged: true, historicalUnitClaims: false, gate: 'USER_VIDEO_REVIEW_REQUIRED'}));
}
