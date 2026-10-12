/** The sole permitted overlap is a geographic Event line beneath its native Marker. */
import {freezeEventData} from './event_contract_v1.mjs';

export const GEOGRAPHIC_OCCLUSION_POLICY = freezeEventData({
 version: 'GEOGRAPHIC_OCCLUSION_POLICY_V1',
 allowedPair: ['EVENT_GEOGRAPHIC_LINE', 'PROTECTED_GEOGRAPHIC_MARKER'],
 composition: ['EVENT_GEOGRAPHIC_LINE', 'PROTECTED_GEOGRAPHIC_MARKER'],
 lineGeometry: 'UNCHANGED', markerGeometry: 'UNCHANGED',
 progress: 'UNINTERRUPTED_PROJECTED_ARC_LENGTH',
 protection: 'FULL_NATIVE_MARKER_RESERVATION',
 otherCollisions: 'REJECT',
});
export const EVENT_MARKER_OCCLUSION_CAPACITY = 32;

function rectangle(box) {
 if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)
  || box[0] >= box[2] || box[1] >= box[3]) throw Error('EVENT_LINE_LAYOUT_RECT_REQUIRED');
 return [...box];
}

/** Untyped legacy reservations remain strict. Only an explicit Marker is exempt. */
export function classifyEventLineProtection({protectedBoxes = [], protectedGraphics = []} = {}) {
 if (!Array.isArray(protectedBoxes) || !Array.isArray(protectedGraphics))
  throw Error('EVENT_LINE_LAYOUT_RECT_REQUIRED');
 const strictBoxes = protectedBoxes.map(rectangle), markerOcclusions = [];
 for (const item of protectedGraphics) {
  if (!item || !['MARKER', 'TEXT', 'PANEL'].includes(item.kind))
   throw Error('EVENT_LINE_PROTECTED_KIND_REQUIRED');
  const box = rectangle(item.box);
  (item.kind === 'MARKER' ? markerOcclusions : strictBoxes).push(box);
 }
 if (markerOcclusions.length > EVENT_MARKER_OCCLUSION_CAPACITY)
  throw Error('EVENT_MARKER_OCCLUSION_CAPACITY_EXCEEDED');
 return freezeEventData({policy: GEOGRAPHIC_OCCLUSION_POLICY.version, strictBoxes, markerOcclusions});
}
