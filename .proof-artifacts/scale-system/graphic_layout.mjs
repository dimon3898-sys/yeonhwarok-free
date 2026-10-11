/** Canonical, measured GPU-graphic layout. No rendering or map mutation occurs here. */
export const GRAPHIC_LAYOUT_VERSION = 'KOREAN_LAYOUT_STAGE3_V1';
export const UNIVERSAL_LAYOUT_VERSION = 'UNIVERSAL_LAYOUT_V1';

const expand = (b, p) => [b[0] - p, b[1] - p, b[2] + 2 * p, b[3] + 2 * p];
const rectBounds = b => [b[0], b[1], b[0] + b[2], b[1] + b[3]];
const overlaps = (a, b) => a[0] < b[0] + b[2] && a[0] + a[2] > b[0] && a[1] < b[1] + b[3] && a[1] + a[3] > b[1];
const inRect = (p, b) => p[0] >= b[0] && p[0] <= b[0] + b[2] && p[1] >= b[1] && p[1] <= b[1] + b[3];
const inSafe = (b, safe) => b[0] >= safe[0] && b[1] >= safe[1] && b[0] + b[2] <= safe[2] && b[1] + b[3] <= safe[3];
const boundsCache = new WeakMap();
const bounds = points => {
 if (boundsCache.has(points)) return boundsCache.get(points);
 let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
 for (const p of points) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); }
 const value = [x0, y0, x1 - x0, y1 - y0];
 boundsCache.set(points, value);
 return value;
};
const corners = b => [[b[0], b[1]], [b[0] + b[2], b[1]], [b[0] + b[2], b[1] + b[3]], [b[0], b[1] + b[3]]];

function pointInRing(p, ring) {
 let inside = false;
 for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
  const a = ring[i], b = ring[j];
  if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function pointInPolygon(p, polygon) {
 return pointInRing(p, polygon[0]) && !polygon.slice(1).some(r => pointInRing(p, r));
}
function segmentHitsRect(a, b, rect) {
 // Liang-Barsky clipping handles coincident and zero-length edges explicitly.
 const [left, top, right, bottom] = rectBounds(rect);
 const d = [b[0] - a[0], b[1] - a[1]];
 let enter = 0, exit = 1;
 for (const [p, q] of [[-d[0], a[0] - left], [d[0], right - a[0]], [-d[1], a[1] - top], [d[1], bottom - a[1]]]) {
  if (p === 0) { if (q < 0) return false; continue; }
  const t = q / p;
  if (p < 0) enter = Math.max(enter, t); else exit = Math.min(exit, t);
  if (enter > exit) return false;
 }
 return true;
}
function ringHitsRect(ring, box) {
 if (!overlaps(bounds(ring), box)) return false;
 for (let i = 1; i < ring.length; i++) if (segmentHitsRect(ring[i - 1], ring[i], box)) return true;
 if (ring.length > 2 && segmentHitsRect(ring[ring.length - 1], ring[0], box)) return true;
 return false;
}
function polygonHitsRect(polygon, box) {
 if (!overlaps(bounds(polygon[0]), box)) return false;
 if (corners(box).some(p => pointInPolygon(p, polygon))) return true;
 if (polygon[0].some(p => inRect(p, box))) return true;
 return polygon.some(ring => ringHitsRect(ring, box));
}
function screenGeometry(record, screen) {
 if (typeof screen.geometry === 'function') return screen.geometry(record);
 const type = record.geometry_type ?? record.geometry?.type;
 const coordinates = record.coordinates ?? record.geometry?.coordinates;
 if (type !== 'Polygon' && type !== 'MultiPolygon') return [];
 return (type === 'Polygon' ? [coordinates] : coordinates).map(poly => poly.map(ring => ring.map(screen)));
}

function measuredFits(measure, text, style) {
 const minimum = style.minFontSize ?? style.fontSize;
 let metrics;
 for (let fontSize = style.fontSize; fontSize >= minimum; fontSize--) {
  metrics = measure(text, { ...style, fontSize });
  if (metrics.fits !== false && !metrics.lineLimitExceeded) return metrics;
 }
 return metrics;
}
function textAtInk(role, text, metrics, inkX, inkY, placement) {
 const [ax, ay, aw, ah] = metrics.alphaBounds;
 return { kind: 'TEXT', role, text, metrics,
  box: [inkX - ax, inkY - ay, ...metrics.atlasDimensions],
  inkBox: [inkX, inkY, aw, ah], placement };
}

/**
 * The caller owns font rasterization and actual glyph measurements. All boxes
 * are canonical 1080x1920 coordinates, independent of render resolution.
 * No content-specific coordinates, renderer fallback, or fabricated GIS is used.
 */
export function buildMeasuredGraphicLayout({ plan, screen, measure }) {
 if (typeof screen !== 'function' || typeof measure !== 'function') throw Error('Measured layout requires geographic projection and glyph measurement');
 const information = Object.fromEntries(['location', 'country', 'title', 'disclosure'].map(role => [role, plan.scale?.information?.[role] !== false]));
 // Scale admission changes information density, never the approved placement or
 // typography. Keep the supplied Scene immutable when country labels are hidden.
 if (!information.country) plan = { ...plan, layout: { ...plan.layout, countryLabels: [] } };
 const profile = plan.layout?.measured;
 if (profile?.version !== GRAPHIC_LAYOUT_VERSION) throw Error('Unknown measured graphic layout profile');
 const canonical = plan.layout.canonical ?? [1080, 1920];
 const safe = [...(plan.layout.safe ?? [48, 72, 1032, 1848])];
 const anchor = screen(plan.anchor.coordinates);
 const items = [], failures = [], placementAttempts = [], boundaryCollisions = [];
 const projected = (plan.geometries ?? []).map(record => ({ id: record.id,
  role: record.id === plan.primary ? 'PRIMARY' : plan.secondary.includes(record.id) ? 'SECONDARY' : 'NEUTRAL',
  polygons: screenGeometry(record, screen) }));
 const primary = projected.filter(r => r.role === 'PRIMARY');
 const viewport = [0, 0, canonical[0], canonical[1]];
 const visiblePrimaryPoints = primary.flatMap(r => r.polygons.flatMap(p => p[0])).filter(p => inRect(p, viewport));
 // A polygon spanning the viewport can have no vertex inside it. Intersect its
 // projected bounds rather than pretending that the primary has disappeared.
 let primaryBounds;
 if (visiblePrimaryPoints.length) primaryBounds = bounds(visiblePrimaryPoints);
 else {
  const all = primary.flatMap(r => r.polygons.flatMap(p => p[0]));
  if (!all.length) throw Error('Measured graphic layout requires actual Primary polygon geometry');
  const b = bounds(all), x0 = Math.max(b[0], 0), y0 = Math.max(b[1], 0);
  primaryBounds = [x0, y0, Math.min(b[0] + b[2], canonical[0]) - x0, Math.min(b[1] + b[3], canonical[1]) - y0];
 }
 const protectedBox = item => item.kind === 'TEXT' ? expand(item.inkBox, (item.metrics.outlineRadius ?? 0) + 2) : item.box;
 const occupied = () => items.map(protectedBox);
 const touchesPrimary = box => primary.some(r => r.polygons.some(p => polygonHitsRect(p, box)));
 const entirelyPrimary = box => {
  const samples = [...corners(box), [box[0] + box[2] / 2, box[1] + box[3] / 2]];
  return samples.every(p => primary.some(r => r.polygons.some(poly => pointInPolygon(p, poly)))) &&
   !primary.some(r => r.polygons.some(poly => poly.some(ring => ringHitsRect(ring, box))));
 };
 const boundaryHits = (box, textRole = null) => projected.filter(r => r.role !== 'NEUTRAL').flatMap(r => {
  const theme = plan.theme;
  const edge = r.role === 'PRIMARY' ? (theme.primaryEdgeWidth ?? theme.primaryWidth + 2) : (theme.secondaryEdgeWidth ?? theme.secondaryWidth + 2);
  // Country ink already includes its approved outline and 2px text padding.
  // Guard the actual rendered core/contrast edge plus 1px AA, not the faint
  // decorative glow tail. Other roles retain their previous clearances.
  const clearance = textRole === 'COUNTRY' ? edge / 2 + 1 :
   r.role === 'PRIMARY' ? Math.max(8, edge / 2 + (theme.glowRadius ?? 0) * 2) : Math.max(6, edge / 2 + 3);
  return r.polygons.some(poly => poly.some(ring => ringHitsRect(ring, expand(box, clearance)))) ? [{ id: r.id, role: r.role, clearance }] : [];
 });
 const clearOfOccupied = box => !occupied().some(b => overlaps(box, b));
 const bestCandidate = candidates => candidates.filter(c => c.acceptable).sort((a, b) => a.score - b.score || a.order - b.order)[0];
 const markerSize = profile.markerSize ?? plan.layout.markerSize;
 items.push({ kind: 'MARKER', role: 'MARKER', box: [anchor[0] - markerSize / 2, anchor[1] - markerSize / 2, markerSize, markerSize], anchor: [...anchor], geographicAnchor: [...plan.anchor.coordinates] });

 // Priority 2: measure all four sides without moving the geographic marker.
 if (information.location) {
 const locationMetrics = measuredFits(measure, plan.text.locationLabel, profile.location);
 const [locW, locH] = locationMetrics.inkDimensions;
 const gap = profile.location.gap;
 const locationCandidates = [
  ['LEFT', anchor[0] - markerSize / 2 - gap - locW, anchor[1] - locH / 2],
  ['RIGHT', anchor[0] + markerSize / 2 + gap, anchor[1] - locH / 2],
  ['ABOVE', anchor[0] - locW / 2, anchor[1] - markerSize / 2 - gap - locH],
  ['BELOW', anchor[0] - locW / 2, anchor[1] + markerSize / 2 + gap]
 ].map(([name, x, y], order) => {
  const item = textAtInk('LOCATION_LABEL', plan.text.locationLabel, locationMetrics, x, y,
   { candidate: name, anchor: [...anchor], geographicAnchor: [...plan.anchor.coordinates] });
  const ink = protectedBox(item), hits = boundaryHits(ink), primaryInterior = entirelyPrimary(ink);
  // Geometry-clear candidates win. Interior preference preserves readable local
  // context; direction is merely the final deterministic tie breaker.
  return { item, primaryInterior, hits, order, score: primaryInterior ? 0 : 1,
   acceptable: locationMetrics.fits !== false && !locationMetrics.lineLimitExceeded && inSafe(item.box, safe) && inSafe(ink, safe) && !hits.length && clearOfOccupied(ink) };
 });
 const locationChoice = bestCandidate(locationCandidates);
 if (!locationChoice) {
  failures.push({ role: 'LOCATION_LABEL', code: 'NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT' });
  boundaryCollisions.push(...locationCandidates[0].hits.map(h => ({ textRole: 'LOCATION_LABEL', ...h })));
 }
 const selectedLocation = locationChoice ?? locationCandidates[0];
 selectedLocation.item.placement.fit = !!locationChoice;
 selectedLocation.item.placement.primaryInterior = selectedLocation.primaryInterior;
 selectedLocation.item.placement.score = selectedLocation.score;
 if (locationMetrics.fits === false || locationMetrics.lineLimitExceeded) failures.push({ role: 'LOCATION_LABEL', code: 'TEXT_EXCEEDS_MEASURED_BOUNDS' });
 items.push(selectedLocation.item);
 placementAttempts.push({ role: 'LOCATION_LABEL', candidates: locationCandidates.map(c => ({ candidate: c.item.placement.candidate, inkBox: c.item.inkBox,
  acceptable: c.acceptable, score: c.score, primaryInterior: c.primaryInterior, boundaryHits: c.hits })) });

 }

 // Priority 3: a catalog anchor is a preference, never a fixed placement. Search
 // every visible Primary component using actual geometry and measured ink size.
 for (const label of plan.layout.countryLabels ?? []) {
  const preferredAnchor = screen(label.coordinates);
  let choice, last, candidates = [];
  for (let size = profile.country.fontSize; size >= profile.country.minFontSize; size--) {
   const fullMetrics = measure(label.text, { ...profile.country, fontSize: size });
   // Reflow long/narrow-country labels within the already approved line limit.
   // Same font and point size; only the measured wrapping constraint changes.
   const advance = Math.max(...fullMetrics.measuredInk.map(m => m.advance));
   const wrapWidths = [...new Set([profile.country.maxWidth, Math.ceil(Math.max(size, advance / profile.country.maxLines))])];
   for (const maxWidth of wrapWidths) {
   const metrics = measure(label.text, { ...profile.country, fontSize: size, maxWidth });
   const [w, h] = metrics.inkDimensions;
   const points = [{ point: preferredAnchor, name: 'PREFERRED_GIS_ANCHOR' }];
   const step = Math.max(4, Math.min(w, h) / 4);
   for (const region of primary) for (const polygon of region.polygons) {
    const b = bounds(polygon[0]);
    const x0 = Math.max(safe[0] + w / 2, b[0] + w / 2), x1 = Math.min(safe[2] - w / 2, b[0] + b[2] - w / 2);
    const y0 = Math.max(safe[1] + h / 2, b[1] + h / 2), y1 = Math.min(safe[3] - h / 2, b[1] + b[3] - h / 2);
    // A component smaller than the actual glyph box cannot contain its label.
    if (x1 < x0 || y1 < y0) continue;
    points.push({ point: [b[0] + b[2] / 2, b[1] + b[3] / 2], name: 'POLYGON_COMPONENT_CENTER' });
    for (let y = y0; y <= y1; y += step) for (let x = x0; x <= x1; x += step) points.push({ point: [x, y], name: 'POLYGON_INTERIOR_SEARCH' });
   }
   const evaluated = points.map(({ point, name }, order) => {
    const item = textAtInk('COUNTRY', label.text, metrics, point[0] - w / 2, point[1] - h / 2,
     { candidate: name, anchor: [...point], sourceGeographicAnchor: [...label.coordinates], geographicAnchor: name === 'PREFERRED_GIS_ANCHOR' ? [...label.coordinates] : null });
    const ink = protectedBox(item);
    const interior = entirelyPrimary(ink);
    const hits = interior ? boundaryHits(ink, 'COUNTRY') : [];
    const score = name === 'PREFERRED_GIS_ANCHOR' ? -1 : Math.hypot(point[0] - preferredAnchor[0], point[1] - preferredAnchor[1]) / Math.hypot(...canonical);
    return { item, hits, order, score, interior, acceptable: metrics.fits !== false && !metrics.lineLimitExceeded &&
     inSafe(item.box, safe) && inSafe(ink, safe) && interior && !hits.length && clearOfOccupied(ink) };
   });
   candidates.push(...evaluated.map(c => ({ fontSize: size, maxWidth, lines: metrics.lines, candidate: c.item.placement.candidate, anchor: c.item.placement.anchor,
    inkBox: c.item.inkBox, acceptable: c.acceptable, score: c.score, primaryInterior: c.interior, boundaryHits: c.hits })));
   last = evaluated[0];choice = bestCandidate(evaluated);
   if (choice) break;
   }
   if (choice) break;
  }
  if (!choice) {
   failures.push({ role: 'COUNTRY', text: label.text, code: 'NO_SAFE_PRIMARY_INTERIOR_COUNTRY_PLACEMENT' });
   boundaryCollisions.push(...last.hits.map(h => ({ textRole: 'COUNTRY', text: label.text, ...h })));
  }
  const selected = choice ?? last;
  selected.item.placement.fit = !!choice;
  selected.item.placement.score = selected.score;
  selected.item.placement.primaryInterior = selected.interior;
  items.push(selected.item);
  placementAttempts.push({ role: 'COUNTRY', text: label.text, candidates });
 }

 let chosenPanel = null;
 if (information.title) {
 // Priority 4: title candidates use the full safe screen, not a sea mask. The
 // previous above-Primary position remains a preference when genuinely clear.
 const eventStyle = { ...profile.event, maxWidth: canonical[0] * profile.event.maxWidthFraction };
 const eventMetrics = measuredFits(measure, plan.text.eventTitle, eventStyle);
 const [eventW, eventH] = eventMetrics.inkDimensions, [padX, padY] = eventStyle.padding;
 const panelW = eventW + padX * 2, panelH = eventH + padY * 2;
 const titleCenter = primaryBounds[0] + primaryBounds[2] / 2;
 const nominalX = Math.min(safe[2] - panelW, Math.max(safe[0], titleCenter - panelW / 2));
 const nominalY = primaryBounds[1] - eventStyle.clearance - panelH;
 const titlePoints = [{ point: [nominalX, nominalY], name: 'CLEAR_ABOVE_PRIMARY' }];
 const left = safe[0] + 8, right = safe[2] - panelW - 8, top = safe[1] + 8, bottom = safe[3] - panelH - 8;
 const center = (safe[0] + safe[2] - panelW) / 2;
 for (const [name, point] of [ ['TOP_CENTER', [center, top]], ['TOP_LEFT', [left, top]], ['TOP_RIGHT', [right, top]],
  ['UPPER_CENTER', [center, top + panelH + eventStyle.clearance]], ['BOTTOM_CENTER', [center, bottom]],
  ['BOTTOM_LEFT', [left, bottom]], ['BOTTOM_RIGHT', [right, bottom]] ]) titlePoints.push({ name, point });
 const xStep = Math.max(24, eventMetrics.fontSize), yStep = Math.max(12, eventMetrics.fontSize * .40);
 for (let y = top; y <= bottom; y += yStep) for (let x = left; x <= right; x += xStep) titlePoints.push({ point: [x, y], name: 'SAFE_SCREEN_SEARCH' });
 const titleCandidates = titlePoints.map(({ point, name }, order) => {
  const box = [...point, panelW, panelH], protectedPanel = expand(box, 8), hits = boundaryHits(protectedPanel);
  const avoidsPrimary = !touchesPrimary(protectedPanel);
  const score = name === 'CLEAR_ABOVE_PRIMARY' ? -1 : Math.hypot(point[0] - nominalX, point[1] - nominalY) / Math.hypot(...canonical);
  return { box, name, order, score, avoidsPrimary, hits,
   acceptable: inSafe(protectedPanel, safe) && avoidsPrimary && !hits.length && clearOfOccupied(expand(box, 4)) };
 });
 const titleChoice = bestCandidate(titleCandidates), chosenTitle = titleChoice ?? titleCandidates[0];
 chosenPanel = chosenTitle.box;
 if (!titleChoice) failures.push({ role: 'EVENT_TITLE', code: 'NO_SAFE_PRIMARY_CLEAR_TITLE_PLACEMENT' });
 if (eventMetrics.fits === false || eventMetrics.lineLimitExceeded) failures.push({ role: 'EVENT_TITLE', code: 'TEXT_EXCEEDS_MEASURED_BOUNDS' });
 items.push({ kind: 'PANEL', role: 'TITLE_CONTRAST_PANEL', box: chosenPanel, opacity: eventStyle.panelOpacity });
 items.push(textAtInk('EVENT_TITLE', plan.text.eventTitle, eventMetrics, chosenPanel[0] + padX, chosenPanel[1] + padY,
  { candidate: chosenTitle.name, anchor: [titleCenter, primaryBounds[1]], geographicAnchor: null, score: chosenTitle.score, fit: !!titleChoice }));
 placementAttempts.push({ role: 'EVENT_TITLE', candidates: titleCandidates.map(c => ({ box: c.box, candidate: c.name, acceptable: c.acceptable,
  score: c.score, avoidsPrimary: c.avoidsPrimary, boundaryHits: c.hits })) });

 }

 // Priority 5: auxiliary information adapts to available space; it cannot move
 // any higher-priority item. Approved typography and contrast remain unchanged.
 if (information.disclosure && plan.text.watermark) {
  const style = { ...profile.disclosure, maxWidth: canonical[0] * profile.disclosure.maxWidthFraction };
  const metrics = measuredFits(measure, plan.text.watermark, style);
  const inset = style.inset ?? 12, outline = metrics.outlineRadius ?? 0;
  const x0 = safe[0] + inset + outline, x1 = safe[2] - inset - outline - metrics.inkDimensions[0];
  const y0 = safe[1] + inset + outline, y1 = safe[3] - inset - outline - metrics.inkDimensions[1];
  const auxiliaryPoints = [[x0, y1], [x1, y1], [(x0 + x1) / 2, y1], [x0, y0], [x1, y0]];
  for (let y = y1; y >= y0; y -= Math.max(16, metrics.fontSize)) for (const x of [x0, (x0 + x1) / 2, x1]) auxiliaryPoints.push([x, y]);
  const candidates = auxiliaryPoints.map(([x, y], order) => {
   const item = textAtInk('SCENARIO_DISCLOSURE', plan.text.watermark, metrics, x, y,
    { candidate: order === 0 ? 'LOWER_LEFT_SAFE_AREA' : 'AUXILIARY_SAFE_SCREEN_SEARCH' });
   const ink = protectedBox(item);
   return { item, order, score: order, acceptable: metrics.fits !== false && !metrics.lineLimitExceeded && inSafe(item.box, safe) &&
    inSafe(ink, safe) && clearOfOccupied(ink) };
  });
  const selected = bestCandidate(candidates);
  if (!selected) failures.push({ role: 'SCENARIO_DISCLOSURE', code: 'DISCLOSURE_SAFE_AREA_OR_COLLISION' });
  if (metrics.fits === false || metrics.lineLimitExceeded) failures.push({ role: 'SCENARIO_DISCLOSURE', code: 'TEXT_EXCEEDS_MEASURED_BOUNDS' });
  const item = (selected ?? candidates[0]).item;item.placement.fit = !!selected;items.push(item);
  placementAttempts.push({ role: 'SCENARIO_DISCLOSURE', candidates: candidates.map(c => ({ inkBox: c.item.inkBox, acceptable: c.acceptable, score: c.score })) });
 }

 for (const item of items.filter(i => i.kind === 'TEXT')) {
  if (item.metrics.alphaTouchesEdge) failures.push({ role: item.role, code: 'GLYPH_ATLAS_ALPHA_TOUCHES_EDGE' });
  if (!(item.metrics.alphaPixels > 0)) failures.push({ role: item.role, code: 'EMPTY_GLYPH_COVERAGE' });
 }
 const collisions = [];
 const graphicBoxes = items.map(item => ({ item, box: protectedBox(item) }));
 for (let a = 0; a < graphicBoxes.length; a++) for (let b = a + 1; b < graphicBoxes.length; b++) {
  const aa = graphicBoxes[a], bb = graphicBoxes[b];
  const ownTitle = (aa.item.role === 'EVENT_TITLE' && bb.item.role === 'TITLE_CONTRAST_PANEL') || (bb.item.role === 'EVENT_TITLE' && aa.item.role === 'TITLE_CONTRAST_PANEL');
  if (!ownTitle && overlaps(aa.box, bb.box)) collisions.push({ first: aa.item.role, second: bb.item.role, firstBox: aa.box, secondBox: bb.box });
 }
 const safeArea = { bounds: safe, canonical, violations: graphicBoxes.filter(g => !inSafe(g.box, safe)).map(g => ({ role: g.item.role, box: g.box })) };
 return { items, validation: { layoutVersion: GRAPHIC_LAYOUT_VERSION, algorithmVersion: UNIVERSAL_LAYOUT_VERSION,
  priority: ['MARKER', 'LOCATION_LABEL', 'COUNTRY', 'EVENT_TITLE', 'SCENARIO_DISCLOSURE'],
  countryBoundaryClearance: 'Rendered core/contrast-edge half-width + 1px AA; glyph outline + 2px padding retained; faint glow tail is not a hard exclusion',
  collisions, boundaryCollisions, safeArea, failures, placementAttempts, titleRequiresSea: false,
  titleAvoidsPrimary: chosenPanel ? !touchesPrimary(expand(chosenPanel, 8)) : null, primaryScreenBounds: primaryBounds, anchor: [...anchor], geographicAnchor: [...plan.anchor.coordinates],
  ...(plan.scale ? { informationAdmission: information } : {}),
  measurement: 'Actual glyph alpha bounds; source polygon interiors and screen-wide scored candidates; no content-specific coordinates',
  valid: !collisions.length && !boundaryCollisions.length && !safeArea.violations.length && !failures.length } };
}
