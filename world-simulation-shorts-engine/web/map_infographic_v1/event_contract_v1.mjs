/** Data-only Event contract. No camera, measurement, geometry invention or graphics. */
export const EVENT_INTENT_V1_VERSION = 'EVENT_INTENT_V1';
export const EVENT_DATA_MODES = Object.freeze(['PRODUCTION', 'SYNTHETIC_TEST']);

export function freezeEventData(value) {
 if (value && typeof value === 'object') {
  for (const child of Object.values(value)) freezeEventData(child);
  Object.freeze(value);
 }
 return value;
}

function record(value, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error(`EVENT_${label}_OBJECT_REQUIRED`);
 return value;
}
function text(value, label) {
 if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\u007f]/u.test(value))
  throw Error(`EVENT_${label}_TEXT_REQUIRED`);
 return value;
}
export function validateEventAnchor(value, label = 'ANCHOR') {
 if (!Array.isArray(value) || value.length !== 2 || !value.every(Number.isFinite)
  || value[0] < -180 || value[0] > 180 || value[1] < -90 || value[1] > 90)
  throw Error(`EVENT_${label}_GEOGRAPHIC_POINT_REQUIRED`);
 return [...value];
}
function sourceRecord(value, mode, label) {
 const given = record(value, `${label}_SOURCE`);
 const source = {source_type: text(given.source_type, `${label}_SOURCE_TYPE`),
  source_reference: text(given.source_reference, `${label}_SOURCE_REFERENCE`),
  verification_status: text(given.verification_status, `${label}_VERIFICATION_STATUS`)};
 if (mode === 'PRODUCTION') {
  if (source.verification_status !== 'VERIFIED' || ['REFERENCE_DISPLAY_VALUE', 'SYNTHETIC_TEST'].includes(source.source_type))
   throw Error(`EVENT_${label}_VERIFIED_PRODUCTION_SOURCE_REQUIRED`);
 } else if (source.verification_status !== 'SYNTHETIC_TEST' || source.source_type !== 'SYNTHETIC_TEST') {
  throw Error(`EVENT_${label}_EXPLICIT_SYNTHETIC_PROVENANCE_REQUIRED`);
 }
 return source;
}

/** Consecutive duplicate vertices remain intact; wholly zero-length lines fail. */
function lineRecord(value, mode) {
 const given = record(value, 'LINE'), geometry = record(given.geometry, 'LINE_GEOMETRY');
 if (geometry.type !== 'LineString' || !Array.isArray(geometry.coordinates) || geometry.coordinates.length < 2)
  throw Error('EVENT_LINESTRING_REQUIRED');
 const coordinates = geometry.coordinates.map(point => validateEventAnchor(point, 'LINE_VERTEX'));
 if (!coordinates.some((point, index) => index > 0 &&
  (point[0] !== coordinates[index - 1][0] || point[1] !== coordinates[index - 1][1])))
  throw Error('EVENT_LINE_ZERO_LENGTH');
 // The active flat geographic projection has no wrapped line representation.
 // Reject crossings rather than silently creating an alternate geographic path.
 if (coordinates.some((point, index) => index > 0 && Math.abs(point[0] - coordinates[index - 1][0]) > 180))
  throw Error('EVENT_LINE_WRAPPED_GEOMETRY_UNSUPPORTED');
 if (!['FORWARD', 'REVERSE'].includes(given.direction)) throw Error('EVENT_LINE_DIRECTION_REQUIRED');
 return {geometry: {type: 'LineString', coordinates}, source: sourceRecord(given.source, mode, 'LINE'),
  direction: given.direction, style_role: text(given.style_role, 'LINE_STYLE_ROLE'),
  ...(given.anchor === undefined ? {} : {anchor: validateEventAnchor(given.anchor, 'LINE_ANCHOR')})};
}
function metricRecord(value, mode) {
 const given = record(value, 'METRIC');
 return {display_value: text(given.display_value, 'METRIC_DISPLAY_VALUE'), unit: text(given.unit, 'METRIC_UNIT'),
  source: sourceRecord(given.source, mode, 'METRIC'), anchor: validateEventAnchor(given.anchor, 'METRIC_ANCHOR')};
}

/** Production provenance is explicit input evidence, never inferred from labels. */
export function compileEventIntent(input) {
 const given = record(input, 'INPUT'), mode = given.data_mode ?? 'PRODUCTION';
 if (!EVENT_DATA_MODES.includes(mode)) throw Error('EVENT_DATA_MODE_REQUIRED');
 if (given.line == null && given.metric == null) throw Error('EVENT_PRIMITIVE_REQUIRED');
 return freezeEventData({version: EVENT_INTENT_V1_VERSION, data_mode: mode,
  provenance_class: mode === 'PRODUCTION' ? 'VERIFIED_INPUT_DATA' : 'SYNTHETIC_TEST_NOT_PRODUCTION',
  line: given.line == null ? null : lineRecord(given.line, mode),
  metric: given.metric == null ? null : metricRecord(given.metric, mode)});
}

/** Also validates JSON-roundtripped input; a saved version tag alone is insufficient. */
export function assertEventIntent(intent) {
 if (intent?.version !== EVENT_INTENT_V1_VERSION) throw Error('EVENT_INTENT_VERSION_REQUIRED');
 const canonical = compileEventIntent(intent);
 if (JSON.stringify(canonical) !== JSON.stringify(intent)) throw Error('EVENT_INTENT_NON_CANONICAL');
 return canonical;
}
