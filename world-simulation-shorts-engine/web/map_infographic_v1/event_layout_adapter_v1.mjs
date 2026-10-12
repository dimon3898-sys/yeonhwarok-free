/** Move only the Event annotation; existing Camera, labels and marker are immutable. */
import {freezeEventData} from './event_contract_v1.mjs';

export const EVENT_LAYOUT_ADAPTER_V1_VERSION = 'EVENT_LAYOUT_ADAPTER_V1';
function rectangle(value, label) {
 if (!Array.isArray(value) || value.length !== 4 || !value.every(Number.isFinite)
  || !(value[0] < value[2] && value[1] < value[3])) throw Error(`EVENT_LAYOUT_${label}_RECTANGLE_REQUIRED`);
 return [...value];
}
function nonnegative(value, label) {
 if (!Number.isFinite(value) || value < 0) throw Error(`EVENT_LAYOUT_${label}_NONNEGATIVE_REQUIRED`);
 return value;
}
const overlap = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const contains = (outer, inner) => inner[0] >= outer[0] && inner[1] >= outer[1] && inner[2] <= outer[2] && inner[3] <= outer[3];
function protectedRectangle(item) {
 // Rect arrays are already reserved/expanded by the owner of the old layout.
 if (Array.isArray(item)) return rectangle(item, 'PROTECTED');
 if (!item || typeof item !== 'object' || !['TEXT', 'MARKER', 'PANEL'].includes(item.kind))
  throw Error('EVENT_LAYOUT_PROTECTED_KIND_REQUIRED');
 const bounds = rectangle(item.box, 'PROTECTED');
 const padding = item.kind === 'TEXT' ? nonnegative(item.outlineRadius, 'TEXT_OUTLINE') + 2 : 0;
 const expanded = [bounds[0] - padding, bounds[1] - padding, bounds[2] + padding, bounds[3] + padding];
 if (!expanded.every(Number.isFinite)) throw Error('EVENT_LAYOUT_PROTECTED_BOUNDS_OVERFLOW');
 return expanded;
}

/** Input anchor/rectangles are screen coordinates supplied by the native projection. */
export function chooseMetricPlacement({anchor, measurement, safeArea, protectedBoxes, markerSize, gap, lineRoi = null} = {}) {
 if (!Array.isArray(anchor) || anchor.length !== 2 || !anchor.every(Number.isFinite))
  throw Error('EVENT_LAYOUT_PROJECTED_ANCHOR_REQUIRED');
 const dimensions = measurement?.atlasDimensions;
 if (!Array.isArray(dimensions) || dimensions.length !== 2
  || !dimensions.every(value => Number.isSafeInteger(value) && value > 0)) throw Error('EVENT_LAYOUT_FULL_MEASURED_ATLAS_REQUIRED');
 const [width, height] = dimensions, safe = rectangle(safeArea, 'SAFE_AREA');
 if (anchor[0] < safe[0] || anchor[1] < safe[1] || anchor[0] > safe[2] || anchor[1] > safe[3])
  throw Error('EVENT_LAYOUT_ANCHOR_OUTSIDE_SAFE_AREA');
 if (!Number.isFinite(markerSize) || markerSize <= 0) throw Error('EVENT_LAYOUT_MARKER_SIZE_POSITIVE_REQUIRED');
 const spacing = nonnegative(gap, 'GAP'), distance = markerSize / 2 + spacing;
 if (!Number.isFinite(distance)) throw Error('EVENT_LAYOUT_DISTANCE_OVERFLOW');
 if (!Array.isArray(protectedBoxes)) throw Error('EVENT_LAYOUT_PROTECTED_BOXES_REQUIRED');
 const oldBoxes = protectedBoxes.map(protectedRectangle), line = lineRoi === null ? null : rectangle(lineRoi, 'LINE_ROI');
 const [x, y] = anchor;
 const origins = [['RIGHT', x + distance, y - height / 2], ['LEFT', x - distance - width, y - height / 2],
  ['ABOVE', x - width / 2, y - distance - height], ['BELOW', x - width / 2, y + distance]];
 const candidates = origins.map(([placement, left, top]) => {
  const roi = [left, top, left + width, top + height];
  if (!roi.every(Number.isFinite)) throw Error('EVENT_LAYOUT_CANDIDATE_OVERFLOW');
  const safeOK = contains(safe, roi), collisions = oldBoxes.flatMap((box, index) => overlap(roi, box) ? [index] : []);
  const lineCollision = Boolean(line && overlap(roi, line));
  return {placement, box: [left, top, width, height], roi,
   safe: safeOK, protectedCollisions: collisions, lineCollision, eligible: safeOK && collisions.length === 0 && !lineCollision};
 });
 const chosen = candidates.find(candidate => candidate.eligible);
 if (!chosen) throw Error('EVENT_METRIC_LAYOUT_BLOCKED');
 return freezeEventData({version: EVENT_LAYOUT_ADAPTER_V1_VERSION, status: 'PLACED',
  placement: chosen.placement, box: [...chosen.box], roi: [...chosen.roi], anchor: [...anchor],
  atlasDimensions: [...dimensions], safeArea: safe, markerSize, gap: spacing,
  protectedBoxes: oldBoxes, lineRoi: line, candidates,
  reservationSpace: 'FULL_MEASURED_ATLAS', ownership: 'EVENT_ANNOTATION_ONLY'});
}

function projectedPoint(point) {
 if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))
  throw Error('EVENT_LAYOUT_VISIBLE_GEOMETRY_REQUIRED');
 return [...point];
}
function projectedSegments({visibleGeometry, linePrimitive}) {
 const geometry = visibleGeometry ?? linePrimitive;
 let paths;
 if (Array.isArray(geometry)) paths = [geometry];
 else if (Array.isArray(geometry?.segments)) paths = geometry.segments;
 else paths = [geometry?.screenCoordinates ?? geometry?.path];
 if (!paths.length || paths.some(path => !Array.isArray(path) || path.length < 2))
  throw Error('EVENT_LAYOUT_VISIBLE_GEOMETRY_REQUIRED');
 const segments = [];
 for (const path of paths) {
  const points = path.map(projectedPoint);
  for (let index = 1; index < points.length; index++) {
   const a = points[index - 1], b = points[index], length = Math.hypot(b[0] - a[0], b[1] - a[1]);
   if (!Number.isFinite(length)) throw Error('EVENT_LAYOUT_VISIBLE_GEOMETRY_OVERFLOW');
   if (length > 0) segments.push({a, b, length, sourceSegment: segments.length});
  }
 }
 if (!segments.length) throw Error('EVENT_LAYOUT_VISIBLE_GEOMETRY_REQUIRED');
 return segments;
}

// Liang-Barsky clipping supplies annotation support only. It never replaces the
// renderer's path, source geometry, direction, or arc-length reveal primitive.
function segmentRectangleInterval(a, b, box) {
 let lo = 0, hi = 1;
 for (let axis = 0; axis < 2; axis++) {
  const delta = b[axis] - a[axis];
  if (delta === 0) {
   if (a[axis] < box[axis] || a[axis] > box[axis + 2]) return null;
  } else {
   const first = (box[axis] - a[axis]) / delta, last = (box[axis + 2] - a[axis]) / delta;
   lo = Math.max(lo, Math.min(first, last)); hi = Math.min(hi, Math.max(first, last));
   if (lo > hi) return null;
  }
 }
 return [lo, hi];
}
const interpolate = (a, b, t) => a.map((value, axis) => value + (b[axis] - value) * t);
function visibleSupport(segments, occlusions) {
 return segments.flatMap(segment => {
  let intervals = [[0, 1]];
  for (const box of occlusions) {
   const cut = segmentRectangleInterval(segment.a, segment.b, box);
   if (!cut) continue;
   intervals = intervals.flatMap(([lo, hi]) => {
    if (cut[1] <= lo || cut[0] >= hi) return [[lo, hi]];
    const next = [];
    if (cut[0] > lo) next.push([lo, Math.min(cut[0], hi)]);
    if (cut[1] < hi) next.push([Math.max(cut[1], lo), hi]);
    return next;
   });
  }
  return intervals.filter(([lo, hi]) => hi - lo > 1e-12).map(([lo, hi]) => ({
   a: interpolate(segment.a, segment.b, lo), b: interpolate(segment.a, segment.b, hi),
   length: segment.length * (hi - lo), sourceSegment: segment.sourceSegment, interval: [lo, hi],
  }));
 });
}
function segmentBoxDistance(segment, box) {
 const intersection = segmentRectangleInterval(segment.a, segment.b, box);
 if (intersection) return {distance: 0, point: interpolate(segment.a, segment.b, intersection[0])};
 let best = {distance: Infinity, point: null};
 function consider(point, other) {
  const distance = Math.hypot(point[0] - other[0], point[1] - other[1]);
  if (distance < best.distance) best = {distance, point: [...point]};
 }
 for (const point of [segment.a, segment.b])
  consider(point, [Math.max(box[0], Math.min(box[2], point[0])), Math.max(box[1], Math.min(box[3], point[1]))]);
 const delta = segment.b.map((value, axis) => value - segment.a[axis]), denominator = segment.length ** 2;
 for (const corner of [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]) {
  const t = Math.max(0, Math.min(1, ((corner[0] - segment.a[0]) * delta[0] + (corner[1] - segment.a[1]) * delta[1]) / denominator));
  consider(interpolate(segment.a, segment.b, t), corner);
 }
 return best;
}
function supportDistance(segments, box) {
 let best = {distance: Infinity, point: null, sourceSegment: null};
 for (const segment of segments) {
  const next = segmentBoxDistance(segment, box);
  if (next.distance < best.distance) best = {...next, sourceSegment: segment.sourceSegment};
 }
 return best;
}
function supportSamples(segments) {
 // Uniform arc-length samples cover short connected segments; midpoint samples
 // additionally cover long, isolated visible spans on either side of Markers.
 const samples = [], seen = new Set();
 function add(segment, t) {
  const point = interpolate(segment.a, segment.b, t), key = point.map(value => value.toFixed(6)).join(',');
  if (seen.has(key)) return;
  seen.add(key); samples.push({point, tangent: segment.b.map((value, axis) => (value - segment.a[axis]) / segment.length), sourceSegment: segment.sourceSegment});
 }
 const total = segments.reduce((sum, segment) => sum + segment.length, 0);
 const count = Math.max(2, Math.min(128, Math.ceil(total / 8)));
 let cursor = 0, start = 0;
 for (let index = 0; index <= count; index++) {
  const position = total * index / count;
  while (cursor < segments.length - 1 && start + segments[cursor].length < position) start += segments[cursor++].length;
  add(segments[cursor], Math.max(0, Math.min(1, (position - start) / segments[cursor].length)));
 }
 for (const segment of [...segments].sort((a, b) => b.length - a.length).slice(0, 64)) add(segment, .5);
 return samples;
}

/**
 * Reserve the full measured annotation beside the full visible Event geometry.
 * Caller supplies the complete projected line, not the current reveal prefix:
 * placement consequently remains stable for every Metric reveal fraction.
 * Marker clipping here affects candidate derivation only; Markers remain strict
 * exclusions for the annotation and no native graphic is relocated.
 */
export function chooseRelatedMetricPlacement({visibleGeometry, linePrimitive, measurement, safeArea, protectedBoxes,
 markerOcclusions = [], linePaddingPixels, gap = 10, minGap = Math.max(0, gap - 2), maxGap = gap + 4,
 anchor = null, distanceWeight = 1} = {}) {
 const dimensions = measurement?.atlasDimensions;
 if (!Array.isArray(dimensions) || dimensions.length !== 2
  || !dimensions.every(value => Number.isSafeInteger(value) && value > 0)) throw Error('EVENT_LAYOUT_FULL_MEASURED_ATLAS_REQUIRED');
 const [width, height] = dimensions, safe = rectangle(safeArea, 'SAFE_AREA');
 if (!Array.isArray(protectedBoxes)) throw Error('EVENT_LAYOUT_PROTECTED_BOXES_REQUIRED');
 if (!Array.isArray(markerOcclusions)) throw Error('EVENT_LAYOUT_MARKER_OCCLUSIONS_REQUIRED');
 const oldBoxes = protectedBoxes.map(protectedRectangle), occlusions = markerOcclusions.map(box => rectangle(box, 'MARKER_OCCLUSION'));
 const padding = nonnegative(linePaddingPixels, 'LINE_PADDING'), spacing = nonnegative(gap, 'GAP');
 const minimum = nonnegative(minGap, 'MIN_GAP'), maximum = nonnegative(maxGap, 'MAX_GAP');
 const weight = nonnegative(distanceWeight, 'DISTANCE_WEIGHT');
 if (minimum > spacing || maximum < spacing) throw Error('EVENT_LAYOUT_RELATION_GAP_RANGE_REQUIRED');
 const reference = anchor === null ? null : projectedPoint(anchor);
 const segments = projectedSegments({visibleGeometry, linePrimitive}), support = visibleSupport(segments, occlusions);
 if (!support.length) throw Error('EVENT_METRIC_LAYOUT_BLOCKED');
 const candidates = [], seen = new Set();
 for (const sample of supportSamples(support)) {
  const [tx, ty] = sample.tangent;
  const directions = [['NORMAL_LEFT', -ty, tx], ['NORMAL_RIGHT', ty, -tx],
   ['RIGHT', 1, 0], ['LEFT', -1, 0], ['ABOVE', 0, -1], ['BELOW', 0, 1]];
  for (const [placement, nx, ny] of directions) {
   const offset = Math.abs(nx) * width / 2 + Math.abs(ny) * height / 2 + padding + spacing;
   const left = sample.point[0] + nx * offset - width / 2, top = sample.point[1] + ny * offset - height / 2;
   const roi = [left, top, left + width, top + height];
   if (!roi.every(Number.isFinite)) throw Error('EVENT_LAYOUT_CANDIDATE_OVERFLOW');
   const key = roi.map(value => value.toFixed(6)).join(',');
   if (seen.has(key)) continue;
   seen.add(key);
   const safeOK = contains(safe, roi), collisions = oldBoxes.flatMap((box, index) => overlap(roi, box) ? [index] : []);
   const closest = supportDistance(support, roi), relationshipGapPixels = closest.distance - padding;
   // Check individual segment capsules, not the large bounding rectangle of a
   // curved line. The latter falsely excludes safe space beside the curve.
   const lineCollision = supportDistance(segments, roi).distance < padding - 1e-9;
   const relationOK = relationshipGapPixels >= minimum - 1e-9 && relationshipGapPixels <= maximum + 1e-9;
   const anchorDistancePixels = reference === null ? 0 : Math.hypot((left + width / 2) - reference[0], (top + height / 2) - reference[1]);
   candidates.push({placement, box: [left, top, width, height], roi, safe: safeOK, protectedCollisions: collisions,
    lineCollision, relationshipGapPixels, nearestVisiblePoint: closest.point, sourceSegment: closest.sourceSegment,
    anchorDistancePixels, relationOK, eligible: safeOK && collisions.length === 0 && !lineCollision && relationOK});
  }
 }
 // Relation distance is the primary objective; an optional descriptive anchor
 // breaks ties only, without dragging the annotation away from the actual line.
 const score = candidate => [Math.round(Math.abs(candidate.relationshipGapPixels - spacing) * 1e6),
  Math.round(candidate.anchorDistancePixels * weight * 1e6), Math.round(candidate.roi[1] * 1e6), Math.round(candidate.roi[0] * 1e6)];
 const ordered = candidates.filter(candidate => candidate.eligible).sort((a, b) => {
  const first = score(a), second = score(b);
  for (let index = 0; index < first.length; index++) if (first[index] !== second[index]) return first[index] - second[index];
  return 0;
 });
 const chosen = ordered[0];
 if (!chosen) throw Error('EVENT_METRIC_LAYOUT_BLOCKED');
 const rejectionCounts = {unsafe: 0, protected: 0, line: 0, relation: 0};
 for (const candidate of candidates) {
  if (!candidate.safe) rejectionCounts.unsafe++;
  if (candidate.protectedCollisions.length) rejectionCounts.protected++;
  if (candidate.lineCollision) rejectionCounts.line++;
  if (!candidate.relationOK) rejectionCounts.relation++;
 }
 return freezeEventData({version: EVENT_LAYOUT_ADAPTER_V1_VERSION, status: 'PLACED',
  placement: chosen.placement, box: [...chosen.box], roi: [...chosen.roi], anchor: reference,
  atlasDimensions: [...dimensions], safeArea: safe, protectedBoxes: oldBoxes, markerOcclusions: occlusions,
  gap: spacing, linePaddingPixels: padding, minGap: minimum, maxGap: maximum,
  relationshipGapPixels: chosen.relationshipGapPixels, nearestVisiblePoint: chosen.nearestVisiblePoint,
  anchorDistancePixels: chosen.anchorDistancePixels, lineCollision: chosen.lineCollision,
  visibleSupportSegments: support.map(segment => ({path: [segment.a, segment.b], sourceSegment: segment.sourceSegment, interval: segment.interval})),
  candidateCount: candidates.length, eligibleCandidateCount: ordered.length, rejectionCounts,
  candidates: ordered.slice(0, 8), candidateDiagnostics: 'BEST_ELIGIBLE_PLUS_COMPLETE_REJECTION_COUNTS',
  relationshipSpace: 'FULL_VISIBLE_PROJECTED_GEOMETRY_AFTER_MARKER_OCCLUSION',
  reservationSpace: 'FULL_MEASURED_ATLAS', ownership: 'EVENT_ANNOTATION_ONLY'});
}
