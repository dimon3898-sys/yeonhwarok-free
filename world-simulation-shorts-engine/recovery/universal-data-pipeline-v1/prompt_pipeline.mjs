/** Additive structured-prompt adapter. It does not modify, simulate or replace any engine. */
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compileScenePlan, validateFactDataset, validateScenePlan} from '../../web/map_infographic_v1/planner_scene_v1.mjs';
import {compileExistingEnginePlan} from '../../web/map_infographic_v1/planner_engine_adapter_v1.mjs';

export const SCHEMA = 'WORLD_ENGINE_DATA_PROMPT_V1';
export const COMPILER_VERSION = 'universal-data-pipeline-v1.0.0';
export const REGIONS = Object.freeze(['namibia_desert_coast', 'europe_germany', 'south_america_chile', 'korean_peninsula', 'nepal_himalaya']);
export const CAPABILITIES = Object.freeze({
  prompt: 'STRUCTURED_JSON_OR_SINGLE_JSON_FENCE; NO_EXTERNAL_AI',
  families: ['WAR', 'TRANSPORT'],
  plannerOnlyFamilies: ['LINE_METRIC', 'DISASTER'],
  camera: 'EXISTING_SERVER_OWNED_REGION_PROFILE_LOCKED; supplied targets must fit its coverage',
  dates: 'GREGORIAN_ISO_DATE_0001_TO_9999; BCE and precision-only dates are unsupported',
  routeMotion: 'PROJECTED_ARC_LENGTH_PLAYBACK; not physical velocity or inferred navigation',
  bounds: 'EPSG:4326 [longitude,latitude]; antimeridian-spanning segments unsupported',
  historical: 'SERVER_REVIEWED_CLAIM_AND_GEOMETRY_BINDINGS; SHA and VERIFIED labels alone are insufficient',
  rendering: 'FREE_SOFTWARE_PREVIEW_ONLY; 30fps,16..240 frames per scene; no NVIDIA quality claim',
  legacy: 'Existing PLANNER_SCENE_JSON_V1 validated without reinterpretation by validateLegacyScene',
});
const here = path.dirname(fileURLToPath(import.meta.url));
const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
const copy = x => structuredClone(x);
const sha = value => createHash('sha256').update(typeof value === 'string' ? value : canonicalJSON(value)).digest('hex');
export function canonicalJSON(value) {
  if (Array.isArray(value)) return '[' + value.map(canonicalJSON).join(',') + ']';
  if (object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonicalJSON(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
const ENGINE_FILES = ['planner_scene_v1.mjs', 'planner_engine_adapter_v1.mjs', 'area_core_v3.mjs', 'flow_core_v2.mjs', 'event_contract_v1.mjs'];
const engineHashes = Object.fromEntries(ENGINE_FILES.map(name => [name, sha(fs.readFileSync(path.resolve(here, '../../web/map_infographic_v1', name), 'utf8'))]));
const issue = (status, code, field, reason, example) => ({status, code, field, reason, example});
const statusOf = issues => ['INVALID', 'CONFLICT', 'UNSUPPORTED', 'NEEDS_INPUT'].find(status => issues.some(x => x.status === status)) ?? 'PASS';
const txt = x => typeof x === 'string' && x.trim().length > 0;
const safeID = x => txt(x) && /^[A-Za-z0-9_.:-]+$/u.test(x);
const isoDate = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/u.test(x) && !x.startsWith('0000') && Number.isFinite(Date.parse(x + 'T00:00:00Z')) && new Date(x + 'T00:00:00Z').toISOString().slice(0, 10) === x;
function unknowns(value, allowed, field, out) {
  if (value !== undefined && !object(value)) {
    out.push(issue('INVALID', 'OBJECT_REQUIRED', field, 'This field must be an object.', {objectFields: allowed})); return;
  }
  if (!object(value)) return;
  for (const key of Object.keys(value)) if (!allowed.includes(key)) out.push(issue('UNSUPPORTED', 'UNSUPPORTED_FIELD', field + '.' + key,
    'This field has no implemented consumer. It will not be silently ignored.', {removeField: key, supportedFields: allowed}));
}
function requireFields(value, fields, field, out) {
  for (const key of fields) if (value?.[key] === undefined || value[key] === null) out.push(issue('NEEDS_INPUT', 'REQUIRED_FIELD', field + '.' + key,
    'Supply the field required by the selected feature.', {field: key, contract: 'PROMPT_CONTRACT.md'}));
}
function duplicates(rows, field, out) {
  if (!Array.isArray(rows)) return;
  const seen = new Set();
  for (const [i, row] of rows.entries()) {
    if (!safeID(row?.id)) out.push(issue('INVALID', 'IDENTIFIER_REQUIRED', `${field}[${i}].id`, 'Use a nonempty identifier.', {id: 'supplied_item_1'}));
    else if (seen.has(row.id)) out.push(issue('CONFLICT', 'DUPLICATE_ID', `${field}[${i}].id`, 'Identifiers must be unique.', {id: row.id + '_2'}));
    seen.add(row?.id);
  }
}
function coordinates(value, field, out) {
  if (!Array.isArray(value)) return out.push(issue('INVALID', 'COORDINATE_ARRAY_REQUIRED', field, 'Coordinates must be arrays.', {coordinates: [10, -20]}));
  if (value.length && typeof value[0] === 'number') {
    if (value.length !== 2 || !value.every(Number.isFinite) || Math.abs(value[0]) > 180 || Math.abs(value[1]) > 90)
      out.push(issue('INVALID', 'COORDINATE_RANGE', field, 'Use finite [longitude,latitude] in EPSG:4326 within ±180,±90.', {coordinates: [10, -20]}));
  } else for (const [i, child] of value.entries()) coordinates(child, `${field}[${i}]`, out);
}
const FACT_KEYS = ['version', 'data_mode', 'subject', 'locations', 'time_range', 'source_notes', 'geometries', 'stages', 'routes',
  'geographic_lines', 'impacts', 'propagations', 'metrics', 'markers', 'text', 'camera', 'scale', 'native_context', 'semantic_mode', 'scene_timing', 'causal_tracks'];
const RECORD_KEYS = {
  source_notes: ['id', 'source_type', 'source_reference', 'verification_status', 'note', 'verification_basis', 'live_access', 'retrieval_date', 'license', 'version', 'original_sha256', 'source_wrapper_sha256', 'sha256', 'crs', 'resolution'],
  geometries: ['id', 'geometry', 'source_id', 'note'], locations: ['id', 'label', 'anchor', 'country_id'],
  stages: ['id', 'date', 'label', 'area_refs', 'front_refs'],
  routes: ['id', 'geometry_ref', 'direction', 'object_role', 'object_profile', 'required_for_story', 'object_graphic'],
  geographic_lines: ['id', 'geometry_ref', 'direction', 'style_role'], impacts: ['id', 'geometry_ref'],
  propagations: ['id', 'origin', 'source_id', 'geometry_ref', 'radius_start_degrees', 'radius_end_degrees', 'angular_range_degrees'],
  metrics: ['id', 'display_value', 'unit', 'anchor', 'source_id'], markers: ['id', 'label', 'anchor', 'source_id'],
  text: ['id', 'content', 'role'],
  causal_tracks: ['id', 'source_id', 'action_kind', 'from_state_id', 'to_state_id', 'motion_start_frame', 'contact_frame', 'control_start_frame', 'control_end_frame', 'end_frame', 'contact_kind', 'semantic_mode', 'represents_historical_unit', 'route_id', 'object_id', 'target_front_line_id', 'contact_anchor'],
};
function inspectFacts(facts, field, mode, out) {
  if (!object(facts)) { out.push(issue('NEEDS_INPUT', 'FACTS_REQUIRED', field, 'Supply existing PLANNER_FACTS_V1 structured data.', {version: 'PLANNER_FACTS_V1'})); return; }
  unknowns(facts, FACT_KEYS, field, out);
  requireFields(facts, ['version', 'data_mode', 'subject', 'locations', 'time_range', 'source_notes', 'geometries', 'camera'], field, out);
  unknowns(facts.subject, ['id', 'label', 'aliases', 'event_family'], field + '.subject', out);
  unknowns(facts.camera, ['anchor', 'target_geometry_refs', 'minimum_context_geometry_refs', 'detail_policy', 'native_context'], field + '.camera', out);
  for (const [context, where] of [[facts.native_context, field + '.native_context'], [facts.camera?.native_context, field + '.camera.native_context']])
    unknowns(context, ['country_ids', 'primary_country_id', 'secondary_country_ids', 'context_location_ids'], where, out);
  if (facts.native_context !== undefined && facts.camera?.native_context !== undefined && canonicalJSON(facts.native_context) !== canonicalJSON(facts.camera.native_context))
    out.push(issue('CONFLICT', 'AMBIGUOUS_NATIVE_CONTEXT', field + '.native_context', 'Top-level and camera native contexts disagree. No context is silently shadowed.', {action: 'Supply one context object or identical objects'}));
  unknowns(facts.scene_timing, ['fps', 'total_frames', 'duration_seconds', 'camera_lock_frame', 'event_start_frame', 'initial_reveal_frames', 'state_transition_frames', 'final_hold_frames', 'action_frames', 'frame_policy', 'blank_interstage_frames'], field + '.scene_timing', out);
  unknowns(facts.scale, ['preferred'], field + '.scale', out);
  if (facts.scale?.preferred !== undefined && facts.scale.preferred !== 'REGIONAL') out.push(issue('UNSUPPORTED', 'REGIONAL_SCALE_ONLY', field + '.scale.preferred', 'This free preview consumer has an existing regional camera profile only. LOCAL/CONTINENT are not silently remapped.', {preferred: 'REGIONAL'}));
  for (const [context, where] of [[facts.native_context, field + '.native_context'], [facts.camera?.native_context, field + '.camera.native_context']])
    if (context?.secondary_country_ids?.length) out.push(issue('UNSUPPORTED', 'SECONDARY_CONTEXT_NOT_CONNECTED', where + '.secondary_country_ids', 'Secondary camera contexts are not connected in this consumer.', {secondary_country_ids: []}));
  unknowns(facts.time_range, ['start', 'end'], field + '.time_range', out);
  if (object(facts.time_range)) requireFields(facts.time_range, ['start', 'end'], field + '.time_range', out);
  if (object(facts.camera)) requireFields(facts.camera, ['anchor', 'target_geometry_refs'], field + '.camera', out);
  for (const [key, allowed] of Object.entries(RECORD_KEYS)) if (facts[key] !== undefined) {
    if (!Array.isArray(facts[key])) out.push(issue('INVALID', 'ARRAY_REQUIRED', `${field}.${key}`, 'Expected an array.', {[key]: []}));
    else {
      duplicates(facts[key], `${field}.${key}`, out);
      facts[key].forEach((row, i) => unknowns(row, allowed, `${field}.${key}[${i}]`, out));
    }
  }
  if (Object.keys(RECORD_KEYS).some(key => facts[key] !== undefined && (!Array.isArray(facts[key]) || facts[key].some(row => !object(row))))) return;
  for (const [i, row] of (Array.isArray(facts.geometries) ? facts.geometries : []).entries()) {
    unknowns(row.geometry, ['type', 'coordinates'], `${field}.geometries[${i}].geometry`, out);
    coordinates(row.geometry?.coordinates, `${field}.geometries[${i}].geometry.coordinates`, out);
    if (row.geometry?.type === 'LineString' && Array.isArray(row.geometry.coordinates)) {
      for (let j = 1; j < row.geometry.coordinates.length; j++) if (Math.abs(row.geometry.coordinates[j]?.[0] - row.geometry.coordinates[j - 1]?.[0]) > 180)
        out.push(issue('UNSUPPORTED', 'ANTIMERIDIAN_SEGMENT', `${field}.geometries[${i}].geometry.coordinates[${j}]`, 'Split antimeridian geometry using a supported projection before submission.', {supportedCRS: 'EPSG:4326', splitAt: 180}));
    }
  }
  for (const key of ['locations', 'markers', 'metrics']) for (const [i, row] of (Array.isArray(facts[key]) ? facts[key] : []).entries()) coordinates(row.anchor, `${field}.${key}[${i}].anchor`, out);
  if (facts.camera?.anchor) coordinates(facts.camera.anchor, field + '.camera.anchor', out);
  for (const [i, row] of (Array.isArray(facts.routes) ? facts.routes : []).entries()) {
    const graphic = row.object_graphic;
    if (graphic) {
      unknowns(graphic, ['width_px', 'height_px', 'polygons'], `${field}.routes[${i}].object_graphic`, out);
      if (!(Number.isFinite(graphic.width_px) && graphic.width_px >= 24 && graphic.width_px <= 80 && Number.isFinite(graphic.height_px) && graphic.height_px >= 12 && graphic.height_px <= 80) || !Array.isArray(graphic.polygons) || graphic.polygons.length > 8)
        out.push(issue('INVALID', 'FLOW_GRAPHIC_GPU_LIMIT', `${field}.routes[${i}].object_graphic`, 'Preserved Flow GPU pass accepts width24..80px,height12..80px and at most eight polygons.', {width_px: 32, height_px: 32, maximumPolygons: 8}));
      for (const [j, poly] of (Array.isArray(graphic.polygons) ? graphic.polygons : []).entries()) {
        unknowns(poly, ['points', 'color'], `${field}.routes[${i}].object_graphic.polygons[${j}]`, out);
        if (!object(poly) || !Array.isArray(poly.points) || poly.points.length > 12) out.push(issue('INVALID', 'FLOW_GRAPHIC_VERTEX_LIMIT', `${field}.routes[${i}].object_graphic.polygons[${j}].points`, 'At most twelve vertices per Flow polygon.', {maximumVertices: 12}));
      }
    }
  }
  const dates = [...Object.entries(facts.time_range ?? {}).map(([key, date]) => ({date, path: `${field}.time_range.${key}`})),
    ...(Array.isArray(facts.stages) ? facts.stages : []).map((row, i) => ({date: row.date, path: `${field}.stages[${i}].date`}))];
  for (const item of dates) if (!isoDate(item.date)) out.push(issue(/BCE|BC|era|^-|^\d{1,3}-/iu.test(String(item.date)) ? 'UNSUPPORTED' : 'INVALID', 'ISO_DATE_REQUIRED', item.path,
    'The preserved Planner supports complete Gregorian YYYY-MM-DD only. Do not replace ancient or approximate dates with invented precise dates.', {supportedExample: '1950-06-25', unsupported: '27 BCE'}));
  if (isoDate(facts.time_range?.start) && isoDate(facts.time_range?.end) && facts.time_range.end < facts.time_range.start)
    out.push(issue('CONFLICT', 'REVERSED_TIME_RANGE', field + '.time_range', 'End date precedes start date.', {start: facts.time_range.end, end: facts.time_range.start}));
  const family = facts.subject?.event_family;
  if (!CAPABILITIES.families.includes(family)) out.push(issue('UNSUPPORTED', 'FAMILY_NOT_CONNECTED', field + '.subject.event_family', 'This preview pixel profile connects WAR and TRANSPORT. LINE_METRIC and DISASTER retain existing Planner contracts but are not connected to this new capture consumer.', {supported: CAPABILITIES.families}));
  if (family === 'TRANSPORT' && !(facts.routes?.length)) out.push(issue('NEEDS_INPUT', 'ROUTE_DATA_REQUIRED', field + '.routes', 'Transport requires supplied geographic routes and supplied object graphics, not military territories.', {routes: [{id: 'route_1', geometry_ref: 'supplied_line', object_role: 'AIRCRAFT', object_graphic: 'See contract'}]}));
  if (family === 'LINE_METRIC' && (!facts.geographic_lines?.length || !facts.metrics?.length)) out.push(issue('NEEDS_INPUT', 'LINE_METRIC_DATA_REQUIRED', field, 'Supply the line and its source-bound metric; neither is inferred.', {geographic_lines: [{id: 'line_1', geometry_ref: 'supplied_line'}], metrics: 'Supply explicit metric'}));
  if (family === 'WAR' && (!Array.isArray(facts.stages) || facts.stages.length < 2 || facts.stages.some(x => !x.area_refs?.length || !x.front_refs?.length)))
    out.push(issue('NEEDS_INPUT', 'TERRITORY_AND_FRONT_STATES_REQUIRED', field + '.stages', 'Area animation requires at least two supplied dated territory and front states. A partial front line is not a complete occupation polygon.', {minimumStates: 2, eachStateRequires: ['date', 'area_refs', 'front_refs']}));
  const unconsumed = family === 'WAR' ? ['metrics', 'geographic_lines', 'impacts', 'propagations', 'text', 'causal_tracks', 'routes']
    : family === 'TRANSPORT' ? ['stages', 'geographic_lines', 'metrics', 'impacts', 'propagations', 'text', 'causal_tracks'] : [];
  for (const key of unconsumed) if (facts[key]?.length) out.push(issue('UNSUPPORTED', 'FEATURE_HAS_NO_PIXEL_CONSUMER', field + '.' + key,
    'This category has no connected pixel consumer in the selected family; supplied content will not be silently discarded.', {field: key, connectedFamilies: CAPABILITIES.families}));
  if (mode === 'HISTORICAL' && facts.data_mode !== 'PRODUCTION') out.push(issue('INVALID', 'HISTORY_MODE_BINDING', field + '.data_mode', 'Historical input cannot masquerade as SYNTHETIC_TEST.', {data_mode: 'PRODUCTION'}));
  if (mode === 'FICTIONAL' && facts.data_mode !== 'SYNTHETIC_TEST') out.push(issue('INVALID', 'FICTION_MODE_BINDING', field + '.data_mode', 'Fiction must be explicitly synthetic; no historical evidence is required.', {data_mode: 'SYNTHETIC_TEST'}));
}
function checkEvidence(scene, facts, field, registry, out) {
  const rows = scene.historicalEvidence;
  if (rows !== undefined && !Array.isArray(rows)) { out.push(issue('INVALID', 'EVIDENCE_ARRAY_REQUIRED', field + '.historicalEvidence', 'Evidence bindings must be an array.', {historicalEvidence: []})); return; }
  if (!Array.isArray(rows) || !rows.length) {
    out.push(issue('NEEDS_INPUT', 'REVIEWED_EVIDENCE_REQUIRED', field + '.historicalEvidence', 'Historical or observed claims need server-reviewed source/claim bindings. A SHA or VERIFIED label alone proves no historical fact.', {historicalEvidence: [{recordId: 'approved_record', sourceId: 'source_1', claimId: 'approved_claim', geometryIds: [], stageIds: []}]})); return;
  }
  const records = Array.isArray(registry) ? registry : registry?.records ?? [];
  if (![facts.source_notes, facts.geometries].every(rows => Array.isArray(rows) && rows.every(object)) || facts.stages !== undefined && (!Array.isArray(facts.stages) || facts.stages.some(row => !object(row)))) return;
  const boundGeometries = new Set(), boundStages = new Set(), boundSources = new Set();
  for (const [i, binding] of rows.entries()) {
    const where = `${field}.historicalEvidence[${i}]`;
    unknowns(binding, ['recordId', 'sourceId', 'claimId', 'geometryIds', 'stageIds'], where, out);
    if (!object(binding)) continue;
    for (const key of ['geometryIds', 'stageIds']) if (binding[key] !== undefined && (!Array.isArray(binding[key]) || binding[key].some(id => !safeID(id))))
      out.push(issue('INVALID', 'EVIDENCE_ID_LIST_REQUIRED', where + '.' + key, 'Evidence references must be identifier arrays.', {[key]: []}));
    if (out.some(row => row.field.startsWith(where) && row.status === 'INVALID')) continue;
    const found = (Array.isArray(records) ? records : []).find(record => object(record) && record.id === binding.recordId && record.claimId === binding.claimId && record.sourceId === binding.sourceId);
    const src = facts.source_notes?.find(row => row.id === binding.sourceId);
    if (!found || found.reviewStatus !== 'VERIFIED' || !src) { out.push(issue('NEEDS_INPUT', 'EVIDENCE_NOT_ADMITTED', where, 'No matching server-reviewed evidence record exists.', {action: 'Provide an approved claim reference; do not self-label as verified.'})); continue; }
    if (!found.sourceSHA256 || found.sourceSHA256 !== (src.original_sha256 ?? src.sha256) || found.sourceReference !== src.source_reference) {
      out.push(issue('CONFLICT', 'EVIDENCE_SOURCE_MISMATCH', where, 'Source reference or original SHA differs from the reviewed record.', {sourceId: binding.sourceId, action: 'Use exact reviewed source identity'})); continue;
    }
    if (found.canonicalFactsSHA256 !== sha(facts)) {
      out.push(issue('NEEDS_INPUT', 'EVIDENCE_DATASET_NOT_REVIEWED', where, 'This exact supplied fact dataset has no server-reviewed digest binding. Reusing a source identifier does not qualify new locations, dates or territory.', {action: 'Review exact dataset and bind its canonicalFactsSHA256 in the server-owned registry'})); continue;
    }
    boundSources.add(binding.sourceId);
    for (const gid of binding.geometryIds ?? []) {
      const geometry = facts.geometries?.find(row => row.id === gid);
      if (!geometry || geometry.source_id !== binding.sourceId || found.geometrySHA256ById?.[gid] !== sha(geometry.geometry))
        out.push(issue('CONFLICT', 'EVIDENCE_GEOMETRY_MISMATCH', where + '.geometryIds', 'Supplied geometry is not the reviewed geometry for this claim.', {geometryId: gid, action: 'Supply matching reviewed geometry; partial lines cannot qualify full territories'}));
      else if (['Polygon', 'MultiPolygon'].includes(geometry.geometry.type) && found.scope !== 'FULL_TERRITORY')
        out.push(issue('NEEDS_INPUT', 'EVIDENCE_SCOPE_INSUFFICIENT', where + '.geometryIds', 'A partial-front/event-date review does not establish complete occupation polygons.', {requiredScope: 'FULL_TERRITORY'}));
      else boundGeometries.add(gid);
    }
    for (const sid of binding.stageIds ?? []) {
      const stage = facts.stages?.find(row => row.id === sid), dates = found.applicableDates;
      if (!stage || !dates || stage.date < dates.start || stage.date > dates.end)
        out.push(issue('CONFLICT', 'EVIDENCE_DATE_MISMATCH', where + '.stageIds', 'Event/map validity dates do not qualify this stage date.', {stageId: sid, action: 'Keep event date, map date and geometry date separate'}));
      else boundStages.add(sid);
    }
  }
  for (const geometry of facts.geometries ?? []) if (!boundGeometries.has(geometry.id)) out.push(issue('NEEDS_INPUT', 'UNREVIEWED_GEOMETRY', field + '.facts.geometries.' + geometry.id,
    'No reviewed claim binds this exact geometry.', {geometryId: geometry.id, action: 'Provide reviewed geographic evidence, not a document hash alone'}));
  for (const stage of facts.stages ?? []) if (!boundStages.has(stage.id)) out.push(issue('NEEDS_INPUT', 'UNREVIEWED_STAGE_DATE', field + '.facts.stages.' + stage.id, 'No reviewed claim qualifies this stage date.', {stageId: stage.id}));
  for (const src of facts.source_notes ?? []) if (!boundSources.has(src.id)) out.push(issue('NEEDS_INPUT', 'UNREVIEWED_SOURCE_CLAIM', field + '.facts.source_notes.' + src.id, 'No admitted claim binds this source.', {sourceId: src.id}));
}
function timingFor(facts, frames, fps) {
  const hold = Math.max(2, Math.floor(frames * .25)), action = frames - hold;
  const count = facts.subject.event_family === 'WAR' ? facts.stages.length : 1;
  const initial = count > 1 ? action - Math.floor(action / count) * (count - 1) : 0;
  return {fps, total_frames: frames, duration_seconds: frames / fps, camera_lock_frame: 0, event_start_frame: 0,
    initial_reveal_frames: initial, state_transition_frames: count > 1 ? Math.floor(action / count) : 0,
    final_hold_frames: hold, action_frames: action, frame_policy: 'INTEGER_DETERMINISTIC', blank_interstage_frames: 0};
}
function classifyEngineError(error, field) {
  const code = String(error.message ?? error);
  const status = /DATA_REQUIRED|_REQUIRED|_REFERENCE_REQUIRED/u.test(code) ? 'NEEDS_INPUT'
    : /ORDER|CHRONOLOGICAL|DUPLICATE|BINDING/u.test(code) ? 'CONFLICT' : 'INVALID';
  return issue(status, code.split(':')[0], field, code, {contract: 'PROMPT_CONTRACT.md', action: 'Supply valid explicit data for the selected engine feature'});
}
function plainJSON(value, active = new Set(), depth = 0, count = {nodes: 0}) {
  if (depth > 64 || ++count.nodes > 200000) throw Error('INPUT_COMPLEXITY_LIMIT');
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return;
  if (typeof value === 'number') { if (!Number.isFinite(value)) throw Error('NONFINITE_JSON_NUMBER'); return; }
  if (typeof value !== 'object' || active.has(value)) throw Error('PLAIN_ACYCLIC_JSON_REQUIRED');
  if (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error('PLAIN_JSON_OBJECT_REQUIRED');
  active.add(value);
  for (const key of Object.keys(value)) {
    if (['__proto__', 'prototype', 'constructor'].includes(key)) throw Error('RESERVED_JSON_KEY');
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor.get || descriptor.set) throw Error('JSON_ACCESSOR_NOT_ALLOWED');
    plainJSON(value[key], active, depth + 1, count);
  }
  if (Array.isArray(value) && Object.keys(value).length !== value.length) throw Error('SPARSE_JSON_ARRAY_NOT_ALLOWED');
  active.delete(value);
}
function strictJSONParse(text) {
  // JSON.parse accepts duplicate keys with last-wins semantics; this scanner rejects ambiguity first.
  let position = 0, nodes = 0;
  const white = () => { while (/\s/u.test(text[position] ?? '') && position < text.length) position++; };
  function string() {
    const start = position++;
    while (position < text.length) {
      const char = text[position++];
      if (char === '\\') position++;
      else if (char === '"') return JSON.parse(text.slice(start, position));
    }
    throw Error('UNTERMINATED_JSON_STRING');
  }
  function value(depth = 0) {
    if (depth > 64 || ++nodes > 200000) throw Error('INPUT_COMPLEXITY_LIMIT');
    white();
    if (text[position] === '{') {
      position++; white(); const keys = new Set();
      if (text[position] === '}') { position++; return; }
      while (position < text.length) {
        white(); if (text[position] !== '"') throw Error('JSON_OBJECT_KEY_REQUIRED');
        const key = string(); if (keys.has(key)) throw Error('DUPLICATE_JSON_KEY:' + key); keys.add(key);
        white(); if (text[position++] !== ':') throw Error('JSON_COLON_REQUIRED'); value(depth + 1); white();
        const delimiter = text[position++]; if (delimiter === '}') return; if (delimiter !== ',') throw Error('JSON_OBJECT_DELIMITER_REQUIRED');
      }
      throw Error('UNTERMINATED_JSON_OBJECT');
    }
    if (text[position] === '[') {
      position++; white(); if (text[position] === ']') { position++; return; }
      while (position < text.length) {
        value(depth + 1); white(); const delimiter = text[position++]; if (delimiter === ']') return;
        if (delimiter !== ',') throw Error('JSON_ARRAY_DELIMITER_REQUIRED');
      }
      throw Error('UNTERMINATED_JSON_ARRAY');
    }
    if (text[position] === '"') { string(); return; }
    const start = position; while (position < text.length && !/[\s,\]}]/u.test(text[position])) position++;
    if (start === position) throw Error('JSON_VALUE_REQUIRED');
    const primitive = JSON.parse(text.slice(start, position));
    if (typeof primitive === 'number' && !Number.isFinite(primitive)) throw Error('NONFINITE_JSON_NUMBER');
  }
  value(); white(); if (position !== text.length) throw Error('TRAILING_JSON_CONTENT');
  return JSON.parse(text);
}
export function parsePrompt(input) {
  if (object(input)) { plainJSON(input); if (Buffer.byteLength(canonicalJSON(input)) > 8 * 1024 * 1024) throw Error('INPUT_TOO_LARGE'); return copy(input); }
  if (typeof input !== 'string') throw Error('INPUT_OBJECT_OR_TEXT_REQUIRED');
  if (Buffer.byteLength(input, 'utf8') > 8 * 1024 * 1024) throw Error('INPUT_TOO_LARGE');
  const fences = [...input.matchAll(/```(?:json)?\s*\n([\s\S]*?)\n```/gu)];
  if (fences.length > 1) throw Error('SINGLE_JSON_FENCE_REQUIRED');
  const text = fences.length ? fences[0][1] : input.trim();
  if (text.startsWith('[')) throw Error('INPUT_OBJECT_REQUIRED');
  if (!text.startsWith('{')) throw Error('FREE_NATURAL_LANGUAGE_NOT_SUPPORTED');
  const parsed = strictJSONParse(text); plainJSON(parsed); return parsed;
}
export function validateLegacyScene(scene) { validateScenePlan(scene); return {status: 'PASS', schema: 'PLANNER_SCENE_JSON_V1', scene: copy(scene), enginePlan: compileExistingEnginePlan(scene), reinterpretation: false}; }

export function analyzePrompt(input, {evidenceRegistry = []} = {}) {
  const result = {schema: 'WORLD_ENGINE_DATA_PIPELINE_RESULT_V1', compilerVersion: COMPILER_VERSION, engineHashes,
    status: 'INVALID', issues: [], sceneResults: [], renderableSceneIds: [], blockedSceneIds: [], renderRequests: [], capabilities: CAPABILITIES};
  let data;
  try { data = parsePrompt(input); } catch (error) {
    result.issues.push(issue(String(error.message).includes('NATURAL_LANGUAGE') ? 'UNSUPPORTED' : 'INVALID', String(error.message), '$',
      'Use the structured production prompt; no AI facts or coordinates are inferred.', {schema: SCHEMA, contract: 'PROMPT_CONTRACT.md'}));
    result.status = statusOf(result.issues); return result;
  }
  result.inputSHA256 = sha(data);
  result.simulationType = data.simulationType;
  unknowns(data, ['schema', 'topic', 'simulationType', 'durationSeconds', 'fps', 'resolution', 'scenes', 'renderSettings'], '$', result.issues);
  requireFields(data, ['schema', 'topic', 'simulationType', 'durationSeconds', 'fps', 'resolution', 'scenes'], '$', result.issues);
  if (data.schema !== SCHEMA) result.issues.push(issue('INVALID', 'PROMPT_SCHEMA_REQUIRED', '$.schema', 'Select the versioned structured prompt schema.', {schema: SCHEMA}));
  if (!txt(data.topic)) result.issues.push(issue('NEEDS_INPUT', 'TOPIC_REQUIRED', '$.topic', 'Supply the subject and selected feature intent.', {topic: 'Supplied aviation transport routes'}));
  if (!['HISTORICAL', 'FICTIONAL', 'GENERAL'].includes(data.simulationType)) result.issues.push(issue('INVALID', 'SIMULATION_TYPE_REQUIRED', '$.simulationType', 'Historical, fictional and general data use separate evidence rules.', {simulationType: 'GENERAL'}));
  unknowns(data.resolution, ['width', 'height'], '$.resolution', result.issues);
  if (!Number.isInteger(data.fps) || data.fps < 1 || data.fps > 60) result.issues.push(issue('INVALID', 'FPS_RANGE', '$.fps', 'Use a valid integer fps.', {fps: 30}));
  else if (data.fps !== 30) result.issues.push(issue('UNSUPPORTED', 'PREVIEW_FPS', '$.fps', 'The connected free capture profile preserves 30fps only.', {fps: 30}));
  if (!Number.isFinite(data.durationSeconds) || data.durationSeconds <= 0 || data.durationSeconds > 600 || !Number.isSafeInteger(data.durationSeconds * data.fps))
    result.issues.push(issue('INVALID', 'DURATION_FRAME_BINDING', '$.durationSeconds', 'Duration × fps must be an exact positive integer; maximum contract duration is 600s.', {durationSeconds: 3, fps: 30}));
  if (data.resolution?.width !== 1080 || data.resolution?.height !== 1920) result.issues.push(issue('UNSUPPORTED', 'PREVIEW_RESOLUTION', '$.resolution', 'This additive preview consumer preserves 1080×1920; it does not silently change requested resolution.', {width: 1080, height: 1920}));
  unknowns(data.renderSettings, ['sourceRegionId'], '$.renderSettings', result.issues);
  if (!Array.isArray(data.scenes) || data.scenes.length < 1 || data.scenes.length > 64) result.issues.push(issue('NEEDS_INPUT', 'SCENES_REQUIRED', '$.scenes', 'Provide 1..64 explicit scenes.', {scenes: [{sceneId: 'scene_1', startFrame: 0, endFrame: 90, facts: 'PLANNER_FACTS_V1'}]}));
  const seen = new Set(); let next = 0;
  for (const [i, row] of (Array.isArray(data.scenes) ? data.scenes : []).entries()) {
    if (!safeID(row?.sceneId) || seen.has(row.sceneId)) result.issues.push(issue('CONFLICT', 'SCENE_ID_UNIQUE', `$.scenes[${i}].sceneId`, 'Scene identifiers must be valid and unique.', {sceneId: 'scene_' + (i + 1)}));
    seen.add(row?.sceneId);
    if (!Number.isSafeInteger(row?.startFrame) || !Number.isSafeInteger(row?.endFrame) || row.startFrame !== next || row.endFrame <= row.startFrame)
      result.issues.push(issue('CONFLICT', 'CONTIGUOUS_HALF_OPEN_TIMELINE', `$.scenes[${i}]`, 'Scene frame ranges must cover the timeline without overlap or gaps, [startFrame,endFrame).', {startFrame: next, endFrame: next + 90}));
    next = row?.endFrame;
  }
  result.totalFrames = data.durationSeconds * data.fps;
  if (next !== result.totalFrames) result.issues.push(issue('CONFLICT', 'TOTAL_FRAME_MISMATCH', '$.scenes', 'Scene frame sum must equal durationSeconds × fps.', {expectedEndFrame: result.totalFrames, actualEndFrame: next}));
  if (result.issues.length) { result.status = statusOf(result.issues); return result; }
  for (const [i, row] of data.scenes.entries()) {
    const field = `$.scenes[${i}]`, problems = [], renderSettings = {...data.renderSettings, ...row.renderSettings};
    unknowns(row, ['sceneId', 'startFrame', 'endFrame', 'facts', 'renderSettings', 'dependsOn', 'historicalEvidence'], field, problems);
    unknowns(row.renderSettings, ['sourceRegionId'], field + '.renderSettings', problems);
    if (!REGIONS.includes(renderSettings.sourceRegionId)) problems.push(issue('UNSUPPORTED', 'SOURCE_REGION_NOT_AVAILABLE', field + '.renderSettings.sourceRegionId', 'Only already-preserved, source-qualified regional texture profiles are available; arbitrary uncovered texture data is not invented.', {sourceRegionId: REGIONS[0], available: REGIONS}));
    if (row.dependsOn !== undefined && (!Array.isArray(row.dependsOn) || row.dependsOn.some(id => !seen.has(id) || id === row.sceneId))) problems.push(issue('INVALID', 'DEPENDENCY_REFERENCE', field + '.dependsOn', 'Dependencies must name other supplied scene IDs.', {dependsOn: []}));
    const frames = row.endFrame - row.startFrame;
    if (frames < 16 || frames > 240) problems.push(issue('UNSUPPORTED', 'BOUNDED_PREVIEW_FRAME_BUDGET', field, 'This free preview profile supports 16..240 frames per scene. Long production rendering remains on the preserved long-form pipeline.', {minimumFrames: 16, maximumFrames: 240}));
    const facts = row.facts === undefined ? undefined : copy(row.facts);
    inspectFacts(facts, field + '.facts', data.simulationType, problems);
    if (object(facts) && (data.simulationType === 'HISTORICAL' || data.simulationType === 'GENERAL' && facts.data_mode === 'PRODUCTION')) checkEvidence(row, facts, field, evidenceRegistry, problems);
    let scene, enginePlan;
    if (!problems.length) try {
      // Sorting only supplied dated states; neither positions nor historical dates are invented.
      if (Array.isArray(facts.stages)) facts.stages.sort((a, b) => a.date.localeCompare(b.date));
      facts.scene_timing ??= timingFor(facts, frames, data.fps);
      validateFactDataset(facts);
      scene = compileScenePlan({topic: data.topic, facts, output: {fps: data.fps, width: data.resolution.width, height: data.resolution.height}});
      validateScenePlan(scene); enginePlan = compileExistingEnginePlan(scene);
      if (scene.timing.total_frames !== frames) problems.push(issue('CONFLICT', 'SCENE_TIMING_FRAME_MISMATCH', field + '.facts.scene_timing', 'Supplied internal timing must exactly match the explicit scene range.', {total_frames: frames, fps: data.fps}));
    } catch (error) { problems.push(classifyEngineError(error, field + '.facts')); }
    const state = {sceneId: row.sceneId, startFrame: row.startFrame, endFrame: row.endFrame, status: statusOf(problems), issues: problems, dependsOn: row.dependsOn ?? []};
    result.sceneResults.push(state);
    if (!problems.length) {
      const trace = [{inputPath: field, scenePath: '$', inputSHA256: sha(row), sceneSHA256: sha(scene)},
        ...(scene.geometries ?? []).map(geometry => ({inputPath: field + '.facts.geometries[' + row.facts.geometries.findIndex(x => x.id === geometry.id) + ']', scenePath: '$.geometries[' + scene.geometries.findIndex(x => x.id === geometry.id) + ']', id: geometry.id, geometrySHA256: sha(geometry.geometry), sourceId: geometry.source_id})),
        ...(scene.time_steps ?? []).map(step => ({inputPath: field + '.facts.stages[' + row.facts.stages.findIndex(x => x.id === step.id) + ']', scenePath: '$.time_steps[' + scene.time_steps.findIndex(x => x.id === step.id) + ']', id: step.id, date: step.date, globalStartFrame: row.startFrame + step.start_frame})),
        ...(scene.routes ?? []).map(route => ({inputPath: field + '.facts.routes[' + row.facts.routes.findIndex(x => x.id === route.id) + ']', scenePath: '$.routes[' + scene.routes.findIndex(x => x.id === route.id) + ']', id: route.id, geometryRef: route.geometry_ref, direction: route.direction})),
        {inputPath: field + '.facts.camera', scenePath: '$.camera_intent', owner: scene.camera_intent.owner},
        {inputPath: field + '.renderSettings', scenePath: '$.runtime.sourceRegionId', sourceRegionId: renderSettings.sourceRegionId}];
      result.renderRequests.push({sceneId: row.sceneId, startFrame: row.startFrame, endFrame: row.endFrame, scene, enginePlan, renderSettings,
        inputTrace: trace, displayMetadataOnly: ['subject.label', 'locations[].label', 'markers[].label', 'moving_objects[].profile'], sceneSHA256: sha(scene), sourceManifest: scene.source_notes.map(source => ({sourceId: source.id, sourceReference: source.source_reference,
          originalSHA256: source.original_sha256 ?? source.sha256 ?? null, canonicalMetadataSHA256: sha(source), originalBytesVerified: false,
          claimValidation: data.simulationType === 'HISTORICAL' || facts.data_mode === 'PRODUCTION' ? 'SERVER_EVIDENCE_BINDING' : 'EXPLICIT_USER_DEFINED_SIMULATION'}))});
    }
  }
  const byId = new Map(result.sceneResults.map(row => [row.sceneId, row]));
  const visited = new Set(), active = [];
  function visit(id) {
    if (active.includes(id)) {
      for (const cycleId of active.slice(active.indexOf(id))) {
        const row = byId.get(cycleId);
        if (!row.issues.some(x => x.code === 'CYCLIC_SCENE_DEPENDENCY')) row.issues.push(issue('CONFLICT', 'CYCLIC_SCENE_DEPENDENCY', '$.scenes.' + cycleId + '.dependsOn', 'Scene dependencies must form an acyclic graph.', {action: 'Remove cyclic dependency', cycle: [...active, id]}));
        row.status = statusOf(row.issues);
      }
      return;
    }
    if (visited.has(id)) return;
    active.push(id);
    for (const dependency of byId.get(id)?.dependsOn ?? []) visit(dependency);
    active.pop(); visited.add(id);
  }
  for (const id of byId.keys()) visit(id);
  // Transitive dependency blocks are local: unrelated qualified scenes are retained at original frame ranges.
  let changed = true;
  while (changed) {
    changed = false;
    for (const row of result.sceneResults) if (row.status === 'PASS') {
      const failed = row.dependsOn.filter(id => result.sceneResults.find(x => x.sceneId === id)?.status !== 'PASS');
      if (failed.length) { row.issues.push(issue('NEEDS_INPUT', 'DEPENDENCY_BLOCKED', '$.scenes.' + row.sceneId + '.dependsOn', 'A declared dependency is blocked; no implicit dependency on unrelated scenes is introduced.', {blockedSceneIds: failed})); row.status = 'NEEDS_INPUT'; changed = true; }
    }
  }
  result.renderableSceneIds = result.sceneResults.filter(x => x.status === 'PASS').map(x => x.sceneId);
  result.blockedSceneIds = result.sceneResults.filter(x => x.status !== 'PASS').map(x => x.sceneId);
  result.renderRequests = result.renderRequests.filter(x => result.renderableSceneIds.includes(x.sceneId));
  result.issues = result.sceneResults.flatMap(x => x.issues);
  result.status = statusOf(result.issues);
  result.timelinePreserved = true;
  result.partialRenderRequiresExplicitSceneSelection = result.blockedSceneIds.length > 0;
  return result;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const args = process.argv.slice(2), allowed = ['--input', '--output', '--evidence-registry'];
    const options = {};
    for (let i = 0; i < args.length; i += 2) {
      if (!allowed.includes(args[i]) || !args[i + 1]) throw Error('CLI_EXPECTS_INPUT_OUTPUT_AND_OPTIONAL_EVIDENCE_REGISTRY');
      options[args[i]] = args[i + 1];
    }
    if (!options['--input']) throw Error('CLI_INPUT_REQUIRED');
    const registry = options['--evidence-registry'] ? JSON.parse(fs.readFileSync(options['--evidence-registry'], 'utf8')) : [];
    const result = analyzePrompt(fs.readFileSync(options['--input'], 'utf8'), {evidenceRegistry: registry});
    const output = JSON.stringify(result, null, 2) + '\n';
    if (options['--output']) fs.writeFileSync(options['--output'], output, {mode: 0o600, flag: 'wx'}); else process.stdout.write(output);
    process.stderr.write(JSON.stringify({status: result.status, renderableScenes: result.renderableSceneIds.length, blockedScenes: result.blockedSceneIds.length}) + '\n');
  } catch (error) { process.stderr.write(JSON.stringify({status: 'INVALID', error: String(error.message)}) + '\n'); process.exitCode = 2; }
}
