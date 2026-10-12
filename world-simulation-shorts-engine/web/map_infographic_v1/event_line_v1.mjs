/** Supplied geographic polyline -> directed screen arc-length reveal controls. */
import {assertEventIntent, freezeEventData} from './event_contract_v1.mjs';

export const EVENT_LINE_V1_VERSION = 'GEOGRAPHIC_LINE_REVEAL_V1';
function screenPoint(point) {
 if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))
  throw Error('EVENT_LINE_FINITE_SCREEN_POINT_REQUIRED');
 return [...point];
}
function buildPrimitive(intent, points) {
 const data = assertEventIntent(intent);
 if (!data.line) throw Error('EVENT_LINE_PRIMITIVE_REQUIRED');
 if (!Array.isArray(points) || points.length !== data.line.geometry.coordinates.length)
  throw Error('EVENT_LINE_PROJECTED_VERTEX_COUNT_MISMATCH');
 const screenCoordinates = points.map(screenPoint), segmentLengthsPixels = [], cumulativeLengthsPixels = [0];
 for (let index = 1; index < screenCoordinates.length; index++) {
  const a = screenCoordinates[index - 1], b = screenCoordinates[index];
  const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (!Number.isFinite(length)) throw Error('EVENT_LINE_SCREEN_LENGTH_OVERFLOW');
  segmentLengthsPixels.push(length);
  const total = cumulativeLengthsPixels.at(-1) + length;
  if (!Number.isFinite(total)) throw Error('EVENT_LINE_SCREEN_LENGTH_OVERFLOW');
  cumulativeLengthsPixels.push(total);
 }
 const totalLengthPixels = cumulativeLengthsPixels.at(-1);
 if (!(totalLengthPixels > 0)) throw Error('EVENT_LINE_ZERO_VISIBLE_LENGTH');
 return freezeEventData({version: EVENT_LINE_V1_VERSION, intent: data, direction: data.line.direction,
  styleRole: data.line.style_role, source: data.line.source, dataMode: data.data_mode,
  measurementSpace: 'CURRENT_PROJECTED_SCREEN_PIXELS', screenCoordinates,
  segmentLengthsPixels, cumulativeLengthsPixels, totalLengthPixels});
}

/** Uses the existing projection; does not compute a new map transform or metric. */
export function compileGeographicLinePrimitive(intent, {project} = {}) {
 const data = assertEventIntent(intent);
 if (!data.line) throw Error('EVENT_LINE_PRIMITIVE_REQUIRED');
 if (typeof project !== 'function') throw Error('EVENT_LINE_EXISTING_PROJECTION_REQUIRED');
 const points = data.line.geometry.coordinates.map(point => screenPoint(project([...point])));
 if (data.line.direction === 'REVERSE') points.reverse();
 return buildPrimitive(data, points);
}

/** Serialized projected plans must retain computed lengths and input provenance. */
export function assertGeographicLinePrimitive(primitive) {
 if (primitive?.version !== EVENT_LINE_V1_VERSION) throw Error('EVENT_LINE_VERSION_REQUIRED');
 const canonical = buildPrimitive(primitive.intent, primitive.screenCoordinates);
 if (JSON.stringify(canonical) !== JSON.stringify(primitive)) throw Error('EVENT_LINE_PRIMITIVE_NON_CANONICAL');
 return canonical;
}

/** The cut point lies on the supplied projected segment, never an invented route. */
export function evaluateGeographicLineReveal(primitive, visibleFraction, {paddingPixels = 0} = {}) {
 const p = assertGeographicLinePrimitive(primitive);
 if (!Number.isFinite(visibleFraction) || visibleFraction < 0 || visibleFraction > 1)
  throw Error('EVENT_LINE_FRACTION_RANGE_REQUIRED');
 if (!Number.isFinite(paddingPixels) || paddingPixels < 0) throw Error('EVENT_LINE_NONNEGATIVE_PADDING_REQUIRED');
 const visibleLengthPixels = visibleFraction * p.totalLengthPixels;
 let path;
 if (visibleFraction === 0) path = [];
 else if (visibleFraction === 1) path = p.screenCoordinates.map(point => [...point]);
 else {
  path = [[...p.screenCoordinates[0]]];
  for (let index = 1; index < p.screenCoordinates.length; index++) {
   const endLength = p.cumulativeLengthsPixels[index], startLength = p.cumulativeLengthsPixels[index - 1];
   if (endLength <= visibleLengthPixels) path.push([...p.screenCoordinates[index]]);
   else {
    const segmentLength = p.segmentLengthsPixels[index - 1];
    const t = (visibleLengthPixels - startLength) / segmentLength;
    if (t > 0) {
     const a = p.screenCoordinates[index - 1], b = p.screenCoordinates[index];
     path.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
    }
    break;
   }
  }
 }
 let roi = null;
 if (path.length) {
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (const [x, y] of path) { left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x); bottom = Math.max(bottom, y); }
  roi = [left - paddingPixels, top - paddingPixels, right + paddingPixels, bottom + paddingPixels];
  if (!roi.every(Number.isFinite)) throw Error('EVENT_LINE_ROI_OVERFLOW');
 }
 return freezeEventData({version: EVENT_LINE_V1_VERSION, visibleFraction, visibleLengthPixels, path, roi,
  direction: p.direction, styleRole: p.styleRole, dataMode: p.dataMode, complete: visibleFraction === 1});
}
