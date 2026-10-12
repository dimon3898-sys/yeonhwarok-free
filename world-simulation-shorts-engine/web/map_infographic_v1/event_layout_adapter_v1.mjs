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
