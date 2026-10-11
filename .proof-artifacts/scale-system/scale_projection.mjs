/**
 * Scale System V1 geographic projection helpers.
 *
 * These functions prepare coordinates for the explicit GPU passes. They do not
 * draw a frame, create terrain, change source GIS, or provide a CPU renderer.
 * The geographic atlas retains source polygons/holes; the globe layout uses
 * only the front hemisphere, including the actual projected clipping limb.
 */
export const SCALE_PROJECTION_VERSION = 'SCALE_PROJECTION_V1';
const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const TWO_PI = Math.PI * 2;
const EPS = 1e-10;

function coordinate(p) {
 if (!Array.isArray(p) || !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || Math.abs(p[1]) > 90)
  throw Error('Projection requires finite longitude/latitude coordinates');
 return [p[0], p[1]];
}
function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function sphere(geo) {
 const [lon, lat] = coordinate(geo).map(v => v * RAD), c = Math.cos(lat);
 return [c * Math.cos(lon), Math.sin(lat), c * Math.sin(lon)];
}
function geoFromSphere(p) {
 return [Math.atan2(p[2], p[0]) * DEG, Math.asin(Math.max(-1, Math.min(1, p[1]))) * DEG];
}
function sourcePolygons(record) {
 const type = record.geometry_type ?? record.geometry?.type;
 const coordinates = record.coordinates ?? record.geometry?.coordinates;
 if (type === 'Polygon') return [coordinates];
 if (type === 'MultiPolygon') return coordinates;
 throw Error(`Scale coverage requires verified Polygon/MultiPolygon, received ${type}`);
}
function same(a, b) { return Math.abs(a[0] - b[0]) < EPS && Math.abs(a[1] - b[1]) < EPS; }
function uniqueAppend(path, point) {
 if (!path.length || !same(path[path.length - 1], point)) path.push(point);
}
function close(path) {
 if (path.length && !same(path[0], path[path.length - 1])) path.push([...path[0]]);
 return path;
}

/** Camera-facing unit basis. The same basis is supplied to the globe shader. */
export function globeBasis(centerLongitudeLatitude) {
 const [lon, lat] = coordinate(centerLongitudeLatitude).map(v => v * RAD);
 return {
  east: [-Math.sin(lon), 0, Math.cos(lon)],
  north: [-Math.sin(lat) * Math.cos(lon), Math.cos(lat), -Math.sin(lat) * Math.sin(lon)],
  center: [Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon)]
 };
}
function config(options = {}) {
 const center = coordinate(options.center ?? [0, 0]);
 const canonical = options.canonical ?? [1080, 1920];
 const diameter = options.diameter ?? .88 * Math.min(...canonical);
 const screenCenter = options.screenCenter ?? [canonical[0] / 2, canonical[1] / 2];
 if (!canonical.every(v => Number.isFinite(v) && v > 0) || !Number.isFinite(diameter) || diameter <= 0 ||
  !screenCenter.every(Number.isFinite)) throw Error('Invalid canonical globe projection extent');
 return { center, canonical: [...canonical], diameter, screenCenter: [...screenCenter], basis: globeBasis(center) };
}
function projectWithConfig(geo, projection) {
 const p = sphere(geo), x = dot(p, projection.basis.east), y = dot(p, projection.basis.north);
 const frontDepth = dot(p, projection.basis.center), radius = projection.diameter / 2;
 const result = [projection.screenCenter[0] + x * radius, projection.screenCenter[1] - y * radius];
 // Array shape is deliberately compatible with the existing measured Layout.
 // Visibility is explicit so a backside point cannot masquerade as a marker.
 result.frontDepth = frontDepth;
 result.visible = frontDepth >= -EPS;
 return result;
}

/** Orthographic projection of the actual spherical geographic position. */
export function globeScreen(geo, options) { return projectWithConfig(geo, config(options)); }

/**
 * Unwrap each geographic ring without moving its latitude or inventing edges.
 * Already antimeridian-split GIS stays unchanged. Holes are shifted into their
 * outer ring's longitude interval, and atlas copies are explicit +/-360 views.
 */
function unwrapRing(ring) {
 if (!Array.isArray(ring) || ring.length < 4) throw Error('Verified polygon ring is missing or degenerate');
 const out = [coordinate(ring[0])];
 for (let i = 1; i < ring.length; i++) {
  const [lon, lat] = coordinate(ring[i]);
  const previous = out[out.length - 1][0];
  const shifted = lon + 360 * Math.round((previous - lon) / 360);
  out.push([shifted, lat]);
 }
 if (!same(ring[0], ring[ring.length - 1])) throw Error('Verified GIS ring must be closed');
 // An ordinary closed geographic ring also closes after unwrapping. A polar
 // source ring with explicit world-map seam vertices is already pre-split and
 // must retain that source representation rather than gaining an artificial
 // chord across the atlas.
 if (!same(out[0], out[out.length - 1])) {
  const sourceHasJump = ring.some((p, i) => i > 0 && Math.abs(p[0] - ring[i - 1][0]) > 180);
  if (!sourceHasJump) return ring.map(coordinate);
  throw Error('Geographic ring winds around a pole; require a verified antimeridian split');
 }
 return out;
}
function longitudeRange(ring) {
 let min = Infinity, max = -Infinity;
 for (const p of ring) { min = Math.min(min, p[0]); max = Math.max(max, p[0]); }
 return [min, max];
}
export function geographicAtlasRecord(record) {
 const atlasPolygons = [];
 for (const polygon of sourcePolygons(record)) {
  const outer = unwrapRing(polygon[0]);
  const [left, right] = longitudeRange(outer), outerCenter = (left + right) / 2;
  const holes = polygon.slice(1).map(ring => {
   const unwrapped = unwrapRing(ring), [a, b] = longitudeRange(unwrapped);
   const shift = 360 * Math.round((outerCenter - (a + b) / 2) / 360);
   return unwrapped.map(p => [p[0] + shift, p[1]]);
  });
  // Calculate copies from geographic extent, not a region-specific threshold.
  const first = Math.ceil((-180 - right) / 360), last = Math.floor((180 - left) / 360);
  for (let copy = first; copy <= last; copy++) {
   const shift = copy * 360;
   if (right + shift <= -180 || left + shift >= 180) continue;
   atlasPolygons.push([outer, ...holes].map(ring => ring.map(p => [p[0] + shift, p[1]])));
  }
 }
 return { ...record, geometry_type: 'MultiPolygon', coordinates: atlasPolygons,
  projectionEvidence: { version: SCALE_PROJECTION_VERSION, sourceGeometryType: record.geometry_type ?? record.geometry?.type,
   sourceParts: sourcePolygons(record).length, atlasParts: atlasPolygons.length,
   method: 'Source rings unwrapped with aligned holes; longitude-periodic copies clipped by GPU atlas viewport; source GIS unchanged' } };
}

function denseRing(ring, maxStep = 1) {
 const unwrapped = unwrapRing(ring), result = [];
 for (let i = 0; i < unwrapped.length - 1; i++) {
  const a = unwrapped[i], b = unwrapped[i + 1];
  const segments = Math.max(1, Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) / maxStep));
  for (let j = 0; j < segments; j++) result.push([a[0] + (b[0] - a[0]) * j / segments, a[1] + (b[1] - a[1]) * j / segments]);
 }
 result.push([...result[0]]);
 return result;
}
function horizonIntersection(a, b, projection) {
 const depthA = dot(sphere(a), projection.basis.center), depthB = dot(sphere(b), projection.basis.center);
 const onLimb = q => {
  const point = projectWithConfig(q, projection), radius = projection.diameter / 2;
  const x = (point[0] - projection.screenCenter[0]) / radius, y = (projection.screenCenter[1] - point[1]) / radius;
  const length = Math.hypot(x, y);
  return [projection.screenCenter[0] + x / length * radius, projection.screenCenter[1] - y / length * radius];
 };
 // Canonical 90-degree coordinates can acquire a tiny negative cosine. Treat
 // a near-zero source endpoint as the limb rather than bisecting two points
 // that are both numerically behind the camera.
 if (Math.abs(depthA) <= EPS) return onLimb(a);
 if (Math.abs(depthB) <= EPS) return onLimb(b);
 if (depthA * depthB > 0) throw Error('Horizon clipping requires a front/back geographic segment');
 let lo = 0, hi = 1;
 const aInside = depthA >= 0;
 for (let i = 0; i < 48; i++) {
  const t = (lo + hi) / 2, q = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  if ((dot(sphere(q), projection.basis.center) >= 0) === aInside) lo = t; else hi = t;
 }
 const t = (lo + hi) / 2, q = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
 return onLimb(q);
}
function pointInGeographicRing(geo, ring) {
 const [left, right] = longitudeRange(ring), x = geo[0] + 360 * Math.round(((left + right) / 2 - geo[0]) / 360), y = geo[1];
 let inside = false;
 for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
  const a = ring[i], b = ring[j];
  if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
 }
 return inside;
}
function limbGeo(angle, projection, frontDepth = .000001) {
 const scale = Math.sqrt(1 - frontDepth * frontDepth), x = Math.cos(angle) * scale, y = Math.sin(angle) * scale;
 const p = [0, 1, 2].map(i => x * projection.basis.east[i] + y * projection.basis.north[i] + frontDepth * projection.basis.center[i]);
 return geoFromSphere(p);
}
function limbArc(exit, entry, ring, projection) {
 const radius = projection.diameter / 2;
 const angle = p => Math.atan2((projection.screenCenter[1] - p[1]) / radius, (p[0] - projection.screenCenter[0]) / radius);
 const from = angle(exit), to = angle(entry), ccw = ((to - from) % TWO_PI + TWO_PI) % TWO_PI, cw = ccw - TWO_PI;
 const samples = [.125, .25, .5, .75, .875];
 const score = delta => samples.reduce((n, t) => n + Number(pointInGeographicRing(limbGeo(from + delta * t, projection), ring)), 0);
 const positive = score(ccw), negative = score(cw);
 let area = 0;
 for (let i = 1; i < ring.length; i++) area += ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1];
 const delta = positive === negative ? (area >= 0 ? ccw : cw) : positive > negative ? ccw : cw;
 const steps = Math.max(1, Math.ceil(Math.abs(delta) / RAD)), points = [];
 for (let i = 1; i < steps; i++) {
  const a = from + delta * i / steps;
  points.push([projection.screenCenter[0] + Math.cos(a) * radius, projection.screenCenter[1] - Math.sin(a) * radius]);
 }
 return points;
}
function clipRingForLayout(ring, projection) {
 const dense = denseRing(ring), points = dense.slice(0, -1), front = points.map(p => dot(sphere(p), projection.basis.center) >= -EPS);
 if (front.every(Boolean)) return close(points.map(p => projectWithConfig(p, projection)));
 if (!front.some(Boolean)) {
  // A polygon whose boundary is all behind may enclose the full front disk.
  // Test the actual source ring instead of assuming visibility from its box.
  if (!pointInGeographicRing(projection.center, unwrapRing(ring))) return [];
  const radius = projection.diameter / 2;
  return close(Array.from({ length: 360 }, (_, i) => [projection.screenCenter[0] + radius * Math.cos(i * RAD), projection.screenCenter[1] - radius * Math.sin(i * RAD)]));
 }
 const start = front.findIndex(Boolean), result = [projectWithConfig(points[start], projection)];
 let pendingExit = null;
 for (let step = 1; step <= points.length; step++) {
  const previous = (start + step - 1) % points.length, current = (start + step) % points.length;
  const a = points[previous], b = points[current];
  if (front[previous] && front[current]) uniqueAppend(result, projectWithConfig(b, projection));
  else if (front[previous]) {
   pendingExit = horizonIntersection(a, b, projection); uniqueAppend(result, pendingExit);
  } else if (front[current]) {
   const entry = horizonIntersection(a, b, projection);
   if (pendingExit) for (const p of limbArc(pendingExit, entry, dense, projection)) uniqueAppend(result, p);
   uniqueAppend(result, entry); uniqueAppend(result, projectWithConfig(b, projection)); pendingExit = null;
  }
 }
 return close(result);
}

/** Same forward projection for GPU ribbons, anchors, and measured Layout. */
export function createGlobeProjection(options) {
 const projection = config(options), screen = geo => projectWithConfig(geo, projection);
 screen.options = projection;
 screen.basis = projection.basis;
 screen.geometry = record => {
  const result = [];
  for (const polygon of sourcePolygons(record)) {
   const outer = clipRingForLayout(polygon[0], projection);
   if (outer.length < 4) continue;
   const holes = polygon.slice(1).map(ring => clipRingForLayout(ring, projection)).filter(ring => ring.length >= 4);
   result.push([outer, ...holes]);
  }
  return result;
 };
 return screen;
}

function selectedRecord(record, role, projection) {
 if (role == null) return true;
 if (typeof role === 'function') return !!role(record);
 if (role instanceof Set) return role.has(record.id);
 if (Array.isArray(role)) return role.includes(record.id);
 if (role === 'PRIMARY' || role === 2) return record.id === projection.primary || record.role === role;
 if (role === 'SECONDARY' || role === 1) return (projection.secondary ?? []).includes(record.id) || record.role === role;
 return record.id === role || record.role === role;
}

/**
 * Canonical-screen, front-visible boundary paths. Open paths stop at the true
 * horizon; they are never closed by a fabricated country boundary on the limb.
 * Subdivision follows source geographic segments, at most one degree per step.
 */
export function globeBoundaryRings(records, role, screenOrOptions) {
 const projection = typeof screenOrOptions === 'function' ? screenOrOptions.options : config(screenOrOptions);
 if (!projection?.basis) throw Error('Globe boundary requires the admitted globe projection');
 const paths = [];
 for (const record of records) {
  if (!selectedRecord(record, role, projection)) continue;
  for (const polygon of sourcePolygons(record)) for (const ring of polygon) {
   const points = denseRing(ring).slice(0, -1), front = points.map(p => dot(sphere(p), projection.basis.center) >= -EPS);
   if (!front.some(Boolean)) continue;
   if (front.every(Boolean)) {
    const path = close(points.map(p => projectWithConfig(p, projection))); path.closed = true; path.sourceRecord = record.id; paths.push(path); continue;
   }
   const start = front.findIndex(v => !v); let path = [];
   for (let step = 1; step <= points.length; step++) {
    const previous = (start + step - 1) % points.length, current = (start + step) % points.length;
    const a = points[previous], b = points[current];
    if (!front[previous] && front[current]) {
     path = [horizonIntersection(a, b, projection)]; uniqueAppend(path, projectWithConfig(b, projection));
    } else if (front[previous] && front[current]) uniqueAppend(path, projectWithConfig(b, projection));
    else if (front[previous]) {
     uniqueAppend(path, horizonIntersection(a, b, projection));
     if (path.length > 1) { path.closed = false; path.sourceRecord = record.id; paths.push(path); }
     path = [];
    }
   }
  }
 }
 return paths;
}
