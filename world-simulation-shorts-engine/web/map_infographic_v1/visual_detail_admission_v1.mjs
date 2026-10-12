/**
 * Fact-based visual admission is separate from the unchanged survey audit.
 * The trusted producer must inspect the actual native 1080x1920 PNG, verify its
 * bytes and supply fresh layout/semantic evidence. This pure module validates
 * those bindings and geometry; a digest alone cannot attest rendered pixels.
 */
import {generateDetailExtentCandidates} from './detail_data_profile_v1.mjs';

export const VISUAL_DETAIL_ADMISSION_V1_VERSION = 'VISUAL_DETAIL_ADMISSION_V1';
export const EVENT_DETAIL_FRAMING_REQUEST_V1_VERSION = 'EVENT_DETAIL_FRAMING_REQUEST_V1';
export const PRODUCTION_DETAIL_GRADE = 'FACT_BASED_VISUAL_GRADE';
const digest = value => /^[a-f0-9]{64}$/i.test(value ?? '');
const point = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite);
const box = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const extent = value => box(value) && value[0] >= -180 && value[2] <= 180 && value[1] >= -90 && value[3] <= 90;
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
 ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const same = (a, b) => canonical(a) === canonical(b);
const clone = value => structuredClone(value);
const freeze = value => {
 if (value && typeof value === 'object' && !Object.isFrozen(value)) {
  Object.values(value).forEach(freeze); Object.freeze(value);
 }
 return value;
};
const contains = (outer, inner) => inner[0] >= outer[0] && inner[1] >= outer[1]
 && inner[2] <= outer[2] && inner[3] <= outer[3];
const overlap = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const project = (p, bounds, output) => [(p[0] - bounds[0]) / (bounds[2] - bounds[0]) * output[0],
 (bounds[3] - p[1]) / (bounds[3] - bounds[1]) * output[1]];
const boundsOf = coordinates => [Math.min(...coordinates.map(p => p[0])), Math.min(...coordinates.map(p => p[1])),
 Math.max(...coordinates.map(p => p[0])), Math.max(...coordinates.map(p => p[1]))];
const validOutput = value => Array.isArray(value) && value.length === 2
 && value.every(v => Number.isSafeInteger(v) && v > 0);
function sourceLine(record) {
 const geometry = record?.geometry ?? record;
 if (geometry?.type !== 'LineString' || !Array.isArray(geometry.coordinates) || geometry.coordinates.length < 2
  || !geometry.coordinates.every(p => point(p) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90))
  throw Error('VISUAL_DETAIL_FULL_LINESTRING_REQUIRED');
 if (!geometry.coordinates.slice(1).some((p, index) => !same(p, geometry.coordinates[index])))
  throw Error('VISUAL_DETAIL_NONZERO_GEOMETRY_REQUIRED');
 return geometry;
}
function segmentIntersectsBox(a, b, rectangle) {
 let start = 0, end = 1;
 for (let axis = 0; axis < 2; axis++) {
  const delta = b[axis] - a[axis];
  if (delta === 0) {
   if (a[axis] < rectangle[axis] || a[axis] > rectangle[axis + 2]) return false;
  } else {
   const lo = (rectangle[axis] - a[axis]) / delta, hi = (rectangle[axis + 2] - a[axis]) / delta;
   start = Math.max(start, Math.min(lo, hi)); end = Math.min(end, Math.max(lo, hi));
   if (start > end) return false;
  }
 }
 return true;
}
const inflate = (rectangle, pixels) => [rectangle[0] - pixels, rectangle[1] - pixels,
 rectangle[2] + pixels, rectangle[3] + pixels];

/** Unknown metre accuracy is a warning; unknown actual visual proof is blocked. */
export function evaluateVisualDetailCandidate({candidate, eventGeometry, evidence, surveyDetailStatus = 'NOT_ADMITTED'} = {}) {
 const geometry = sourceLine(eventGeometry);
 if (!candidate || !extent(candidate.bounds) || !validOutput(candidate.output) || !box(candidate.safeArea)
  || !contains([0, 0, ...candidate.output], candidate.safeArea)
  || !Number.isFinite(candidate.linePaddingPixels) || candidate.linePaddingPixels <= 0)
  throw Error('VISUAL_DETAIL_CANDIDATE_CONTRACT_REQUIRED');
 const checks = [], blockingErrors = [], warnings = [];
 function check(name, pass, detail = null) {
  checks.push({name, status: pass ? 'PASS' : 'FAIL', detail});
  if (!pass) blockingErrors.push(name);
 }
 function warning(name, detail = null) { warnings.push({name, detail}); }
 const binding = canonical(geometry), projected = geometry.coordinates.map(p => project(p, candidate.bounds, candidate.output)),
  projectedBounds = boundsOf(projected), halo = inflate(projectedBounds, candidate.linePaddingPixels),
  projectedLengthPixels = projected.slice(1).reduce((total, p, index) => total + Math.hypot(p[0] - projected[index][0], p[1] - projected[index][1]), 0),
  axisCoverage = [(projectedBounds[2] - projectedBounds[0]) / (candidate.safeArea[2] - candidate.safeArea[0]),
   (projectedBounds[3] - projectedBounds[1]) / (candidate.safeArea[3] - candidate.safeArea[1])],
  screenCoverage = Math.max(...axisCoverage);
 check('SOURCE_GEOMETRY_UNCHANGED', candidate.geometryBinding === binding
  && candidate.sourceCoordinateCount === geometry.coordinates.length);
 check('FRESH_FULL_GEOMETRY_PROJECTION', same(candidate.projectedCoordinates, projected)
  && same(candidate.projectedGeometryBounds, projectedBounds) && same(candidate.projectedHaloBounds, halo)
  && candidate.projectedLengthPixels === projectedLengthPixels && same(candidate.axisCoverage, axisCoverage)
  && candidate.screenCoverage === screenCoverage);
 check('FULL_GEOMETRY_SAFE_AREA', contains(candidate.safeArea, halo), {projectedHaloBounds: halo});
 const anchorInner = [candidate.safeArea[0] + candidate.linePaddingPixels, candidate.safeArea[1] + candidate.linePaddingPixels,
  candidate.safeArea[2] - candidate.linePaddingPixels, candidate.safeArea[3] - candidate.linePaddingPixels],
  anchor = point(candidate.eventAnchor) ? project(candidate.eventAnchor, candidate.bounds, candidate.output) : null;
 check('ANCHOR_SAFE_AREA', anchor && box(anchorInner) && anchor[0] >= anchorInner[0] && anchor[0] <= anchorInner[2]
  && anchor[1] >= anchorInner[1] && anchor[1] <= anchorInner[3]);
 check('NATIVE_PROOF_OUTPUT', same(candidate.output, [1080, 1920]));

 const synthetic = evidence?.evidenceKind === 'SYNTHETIC_TEST_ONLY',
  production = evidence?.evidenceKind === 'ACTUAL_NATIVE_RENDER' && !synthetic,
  render = evidence?.render;
 check('ACTUAL_RENDER_EVIDENCE', (synthetic || production) && render?.verified === true && digest(render.sha256)
  && Number.isSafeInteger(render.byteLength) && render.byteLength > 0
  && render.width === candidate.output[0] && render.height === candidate.output[1]
  && same(render.candidateBounds, candidate.bounds) && render.geometryBinding === binding);
 for (const name of ['sameGeography', 'sameObject', 'relationCorrect', 'geometryMeaningPreserved', 'metricMateriallyTrue'])
  check('SEMANTIC_' + name, evidence?.semantic?.[name] === true);
 for (const name of ['cameraV5', 'eventV2', 'rendererVisual', 'geometry', 'marker'])
  check('PROTECTED_' + name, evidence?.protection?.[name] === true);
 const visual = evidence?.visual;
 for (const name of ['terrain', 'coastline', 'canal', 'marker', 'labels', 'safeArea', 'metric']) {
  const status = visual?.[name];
  check('VISUAL_' + name, status === 'VISUAL_PASS' || status === 'VISUAL_WARNING', {status: status ?? 'NOT_REVIEWED'});
  if (status === 'VISUAL_WARNING') warning('VISUAL_' + name);
 }
 check('EVENT_LINE_READABLE', visual?.lineReadable === true);
 check('METRIC_GEOMETRY_RELATION_READABLE', visual?.metricRelated === true);
 const readable = Number.isFinite(candidate.readabilityMinimum) && candidate.readabilityMinimum > 0
  && screenCoverage >= candidate.readabilityMinimum - 1e-12;
 check('MINIMUM_SUFFICIENT_EVENT_COVERAGE', readable, {screenCoverage, minimum: candidate.readabilityMinimum});

 const layout = evidence?.layout, graphics = layout?.protectedGraphics, metricBounds = layout?.metricBounds;
 const freshLayout = layout?.verified === true && same(layout.candidateBounds, candidate.bounds)
  && layout.geometryBinding === binding && box(metricBounds) && Array.isArray(graphics)
  && graphics.every(item => ['MARKER', 'TEXT', 'PANEL'].includes(item.kind) && box(item.bounds));
 check('FRESH_MEASURED_LAYOUT', freshLayout);
 if (freshLayout) {
  check('METRIC_SAFE_AREA', contains(candidate.safeArea, metricBounds));
  check('PROTECTED_GRAPHIC_SAFE_AREA', graphics.every(item => contains(candidate.safeArea, item.bounds)));
  check('METRIC_CRITICAL_COLLISION_ZERO', !graphics.some(item => overlap(item.bounds, metricBounds)));
  const strict = [...graphics.filter(item => item.kind !== 'MARKER'), {kind: 'METRIC', bounds: metricBounds}];
  const collisions = strict.flatMap((item, index) => projected.slice(1).some((p, segment) =>
   segmentIntersectsBox(projected[segment], p, inflate(item.bounds, candidate.linePaddingPixels))) ? [index] : []);
  check('LINE_CRITICAL_COLLISION_ZERO', collisions.length === 0, {collisions,
   allowedCollision: 'EVENT_GEOGRAPHIC_LINE_WITH_PROTECTED_GEOGRAPHIC_MARKER_ONLY'});
 }
 // Geographic labels may naturally project outside this view. Their owners
 // retain the original geographic anchor and style; no annotation is dragged
 // or resized to make room. Title/panel hiding is not a geographic-label cull.
 if (layout?.hiddenGeographicLabels !== undefined) {
  const hidden = layout.hiddenGeographicLabels;
  check('HIDDEN_GEOGRAPHIC_LABELS_PRESERVED', Array.isArray(hidden) && hidden.every(item =>
   ['COUNTRY', 'LOCATION', 'COUNTRY_LABEL', 'LOCATION_LABEL'].includes(item.role)
   && item.reason === 'PROJECTION_OUTSIDE_SAFE_AREA' && item.originalAnchorPreserved === true && item.stylePreserved === true));
  if (Array.isArray(hidden)) hidden.forEach(item => warning('GEOGRAPHIC_LABEL_OUTSIDE_SAFE_AREA', clone(item)));
 }
 const quality = evidence?.quality;
 if (quality?.gisAbsoluteAccuracyCertified !== true) warning('GIS_ABSOLUTE_ACCURACY_NOT_SURVEY_CERTIFIED');
 if (quality?.coastAlignmentMeasured !== true) warning('COAST_ALIGNMENT_NOT_METRE_MEASURED');
 const density = quality?.nativeTexelToScreenPixelRatio;
 if (!Array.isArray(density) || density.length !== 2 || !density.every(v => Number.isFinite(v) && v > 0))
  warning('NATIVE_TERRAIN_RATIO_NOT_MEASURED');
 else if (Math.max(...density) > 1) warning('NATIVE_TEXEL_ENLARGEMENT', {ratio: [...density]});
 if (Array.isArray(evidence?.warnings)) evidence.warnings.forEach(item => warning('PRODUCER_VISUAL_WARNING', clone(item)));
 const admitted = blockingErrors.length === 0;
 return freeze({version: VISUAL_DETAIL_ADMISSION_V1_VERSION, grade: PRODUCTION_DETAIL_GRADE,
  candidate: clone(candidate), status: admitted ? 'VISUAL_DETAIL_ADMITTED' : 'VISUAL_DETAIL_NOT_ADMITTED',
  visual: blockingErrors.some(name => name.startsWith('VISUAL_')) ? 'VISUAL_FAIL'
   : admitted && warnings.length ? 'VISUAL_WARNING' : admitted ? 'VISUAL_PASS' : 'VISUAL_FAIL',
  semanticIntegrity: checks.filter(item => item.name.startsWith('SEMANTIC_')).every(item => item.status === 'PASS') ? 'PASS' : 'FAIL',
  checks, blockingErrors, warnings, readable, surveyDetailStatus, surveyAdmissionModified: false,
  evidenceKind: synthetic ? 'SYNTHETIC_TEST_ONLY' : production ? 'ACTUAL_NATIVE_RENDER' : 'UNVERIFIED',
  productionEligible: admitted && production,
  metrics: {projectedLengthPixels, projectedBounds, projectedHaloBounds: halo, axisCoverage, screenCoverage},
  eventGeometryBinding: binding, evidenceBinding: canonical({candidate, evidence, eventGeometry: geometry, surveyDetailStatus})});
}

/** Prefer the least enlargement that reads as one line/metric information unit. */
export function selectVisualDetailExtent({candidates, eventGeometry, evidenceByCandidate, surveyDetailStatus = 'NOT_ADMITTED'} = {}) {
 if (!Array.isArray(candidates) || !candidates.length || !evidenceByCandidate || typeof evidenceByCandidate !== 'object')
  throw Error('VISUAL_DETAIL_CANDIDATES_AND_EVIDENCE_REQUIRED');
 if (candidates.some(candidate => !Number.isFinite(candidate.zoomFactor) || candidate.zoomFactor <= 0))
  throw Error('VISUAL_DETAIL_FINITE_ZOOM_FACTOR_REQUIRED');
 const audits = [...candidates].sort((a, b) => a.zoomFactor - b.zoomFactor)
  .map(candidate => evaluateVisualDetailCandidate({candidate, eventGeometry, evidence: evidenceByCandidate[candidate.id], surveyDetailStatus}));
 const selected = audits.find(audit => audit.status === 'VISUAL_DETAIL_ADMITTED');
 const candidate = selected?.candidate;
 const certificate = selected ? {version: VISUAL_DETAIL_ADMISSION_V1_VERSION, status: 'VISUAL_DETAIL_ADMITTED',
  grade: PRODUCTION_DETAIL_GRADE, candidateId: candidate.id, bounds: clone(candidate.bounds),
  eventGeometryBinding: selected.eventGeometryBinding, output: clone(candidate.output), safeArea: clone(candidate.safeArea),
  evidenceKind: selected.evidenceKind, productionEligible: selected.productionEligible, surveyDetailStatus,
  surveyAdmissionModified: false, evidenceBinding: selected.evidenceBinding,
  selection: 'MINIMUM_SUFFICIENT_VISUAL_DETAIL_LEAST_ENLARGEMENT'} : null;
 return freeze({version: VISUAL_DETAIL_ADMISSION_V1_VERSION,
  status: selected ? selected.productionEligible ? 'VISUAL_DETAIL_ADMITTED' : 'SYNTHETIC_VISUAL_DETAIL_PASS' : 'VISUAL_DETAIL_BLOCKED',
  grade: PRODUCTION_DETAIL_GRADE, certificate, selectedCandidate: candidate ?? null, audits,
  surveyDetailStatus, surveyAdmissionModified: false, cameraV5Modified: false, eventAnimationStarted: false});
}

/** Event requests readable framing; a separate Camera adapter owns motion. */
export function createEventDetailFramingRequest({eventGeometry, eventAnchor, safeArea, protectedGraphics = [],
 currentCameraState, desiredScreenCoverageRange = [.2, .35, .5], detailAdmission,
 evidenceByCandidate, surveyDetailStatus = 'NOT_ADMITTED', linePaddingPixels = 5.75} = {}) {
 const geometry = sourceLine(eventGeometry);
 if (!currentCameraState || !extent(currentCameraState.bounds) || !Array.isArray(protectedGraphics)
  || protectedGraphics.some(item => !['MARKER', 'TEXT', 'PANEL'].includes(item.kind) || !box(item.bounds)))
  throw Error('EVENT_DETAIL_CURRENT_CAMERA_AND_PROTECTED_GRAPHICS_REQUIRED');
 const candidates = generateDetailExtentCandidates({eventGeometry: geometry, eventAnchor,
  currentBounds: currentCameraState.bounds, output: currentCameraState.output ?? [1080, 1920],
  safeArea, desiredScreenCoverageRange, linePaddingPixels});
 // Re-evaluate supplied evidence rather than accepting a transferable opaque
 // certificate. Changing geometry, safe area or current framing invalidates it.
 const admission = selectVisualDetailExtent({candidates, eventGeometry: geometry, evidenceByCandidate, surveyDetailStatus});
 const certificate = admission.certificate;
 if (detailAdmission && (!certificate || detailAdmission.certificate?.evidenceBinding !== certificate.evidenceBinding
  || detailAdmission.status !== admission.status)) throw Error('EVENT_DETAIL_STALE_ADMISSION');
 const selected = admission.selectedCandidate;
 const decision = selected ? same(selected.bounds, currentCameraState.bounds) ? 'USE_CURRENT_VIEW' : 'DETAIL_APPROACH_REQUIRED'
  : 'EVENT_DETAIL_FRAMING_BLOCKED';
 const targetFraming = selected ? {bounds: clone(selected.bounds), center: clone(selected.center),
  widthDegrees: selected.widthDegrees, heightDegrees: selected.heightDegrees,
  output: clone(selected.output), safeArea: clone(selected.safeArea)} : null;
 return freeze({version: EVENT_DETAIL_FRAMING_REQUEST_V1_VERSION, decision, grade: PRODUCTION_DETAIL_GRADE,
  eventGeometryBinding: canonical(geometry), eventAnchor: clone(eventAnchor), safeArea: clone(safeArea),
  protectedGraphics: clone(protectedGraphics), currentCameraState: clone(currentCameraState),
  desiredScreenCoverageRange: clone(desiredScreenCoverageRange), targetFraming, certificate, admission,
  surveyDetailStatus, surveyAdmissionModified: false, ownership: 'CAMERA_DETAIL_APPROACH_ADAPTER',
  cameraV5Modified: false, eventAnimationStarted: false});
}
