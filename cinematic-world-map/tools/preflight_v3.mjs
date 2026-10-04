// CPU geometry/scheduling checks only: this tool does not start a browser,
// initialize WebGL, load textures, render frames, or assess graphic quality.
// Run: node tools/preflight_v3.mjs [--output=outputs/v3_geometric_preflight.json]
// An existing report is never overwritten; choose a new --output for a rerun.
import * as THREE from 'three';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {
  CameraController, RouteAnimator, EntityAnimator, SceneManager, CITIES, SHOTS,
} from '../src/engine_v3.js';

const root = path.resolve(import.meta.dirname, '..');
const outputArg = process.argv.slice(2).find(x => x.startsWith('--output='));
const output = path.resolve(root, outputArg?.slice('--output='.length)
  || 'outputs/v3_geometric_preflight.json');
const FPS = 30, DURATION = 20, EARTH_RADIUS_KM = 6371;
const NUMERIC_EPS = 1e-10, ALTITUDE_EPS_KM = 1e-6;
const VISIBILITY_ALPHA = .12;
const REPRESENTATIVE_TIMES = [0, .5, 1.5, 2, 6, 10, 14, 15, 16, 17, 19];
const camera = new THREE.PerspectiveCamera(44, 9 / 16, .02, 30);
const routes = new RouteAnimator(), entity = new EntityAnimator(routes);
const controller = new CameraController(camera, routes), scenes = new SceneManager();
const violations = [];

function percentile(sorted, p) {
  if (!sorted.length) return null;
  const i = (sorted.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}
function stats(samples) {
  const finite = samples.filter(s => Number.isFinite(s.value));
  if (!finite.length) return {count: samples.length, finiteCount: 0};
  const sorted = finite.map(s => s.value).sort((a, b) => a - b);
  const min = finite.reduce((a, b) => a.value <= b.value ? a : b);
  const max = finite.reduce((a, b) => a.value >= b.value ? a : b);
  return {count: samples.length, finiteCount: finite.length, min, max,
    mean: sorted.reduce((a, b) => a + b, 0) / sorted.length,
    median: percentile(sorted, .5), p95: percentile(sorted, .95)};
}
const vectorDistance = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));
const quaternionAngleDeg = (a, b) => new THREE.Quaternion(...a)
  .angleTo(new THREE.Quaternion(...b)) * 180 / Math.PI;
function addViolation(category, details) { violations.push({category, ...details}); }

// The aircraft's part geometry/local transforms are static in this version.
// Cache them once, in aircraft-local space, instead of walking all vertices at
// every pose. The representative checks below still transform every vertex.
entity.model.updateMatrixWorld(true);
const initialModelInverse = entity.model.matrixWorld.clone().invert();
const localBounds = new THREE.Box3(), parts = [], vertices = [];
entity.model.traverse(mesh => {
  if (!mesh.isMesh) return;
  const attr = mesh.geometry?.getAttribute('position');
  if (!attr) {
    addViolation('missing_aircraft_position_attribute', {part: mesh.name || parts.length});
    return;
  }
  const localMatrix = initialModelInverse.clone().multiply(mesh.matrixWorld);
  const name = mesh.name || `AIRCRAFT_PART_${parts.length}`;
  const first = vertices.length;
  for (let i = 0; i < attr.count; i++) {
    const p = new THREE.Vector3().fromBufferAttribute(attr, i).applyMatrix4(localMatrix);
    if (!p.toArray().every(Number.isFinite)) {
      addViolation('non_finite_aircraft_local_vertex', {part: name, vertexIndex: i});
      continue;
    }
    localBounds.expandByPoint(p);
    vertices.push({part: name, index: i, point: p});
  }
  parts.push({name, vertices: attr.count, firstCachedVertex: first});
});
if (!vertices.length) throw new Error('Aircraft geometry has no position vertices');
const localCorners = [];
for (const x of [localBounds.min.x, localBounds.max.x])
  for (const y of [localBounds.min.y, localBounds.max.y])
    for (const z of [localBounds.min.z, localBounds.max.z])
      localCorners.push(new THREE.Vector3(x, y, z));

function visibility() {
  const opacities = [];
  entity.model.traverse(mesh => {
    if (!mesh.isMesh) return;
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material])
      if (material?.visible !== false) opacities.push(material?.opacity ?? 1);
  });
  const authoredAlpha = entity.model.userData.alpha;
  const alpha = Number.isFinite(authoredAlpha) ? authoredAlpha : Math.max(0, ...opacities);
  return {sceneVisible: entity.model.visible, alpha,
    visibleForMetrics: entity.model.visible && alpha > VISIBILITY_ALPHA,
    alphaSource: Number.isFinite(authoredAlpha) ? 'model.userData.alpha' : 'maximum_part_opacity',
    minPartOpacity: Math.min(1, ...opacities), maxPartOpacity: Math.max(0, ...opacities)};
}

function aircraftBox() {
  const matrix = entity.model.matrixWorld;
  const cornerMinRadius = Math.min(...localCorners.map(p => p.clone().applyMatrix4(matrix).length()));
  // Corner radii alone do NOT prove Earth clearance: a face may be closer.
  // With the uniform aircraft root scale used here, the closest point in its
  // enclosing oriented box is obtained by clamping Earth's center in local
  // coordinates. A positive lower bound proves the whole enclosed model is
  // outside Earth. A negative bound is only a candidate, not a collision.
  const centerLocal = new THREE.Vector3().applyMatrix4(matrix.clone().invert());
  const nearestBoxPoint = localBounds.clampPoint(centerLocal, new THREE.Vector3())
    .applyMatrix4(matrix);
  const columns = [0, 1, 2].map(i => new THREE.Vector3().setFromMatrixColumn(matrix, i));
  const lengths = columns.map(v => v.length());
  const uniformOrthogonal = Math.max(...lengths) - Math.min(...lengths) < 1e-9
    && columns.every((v, i) => columns.every((w, j) => i === j || Math.abs(v.dot(w)) < 1e-9));
  return {cornerMinClearanceKm: (cornerMinRadius - 1) * EARTH_RADIUS_KM,
    enclosingBoxLowerBoundClearanceKm: uniformOrthogonal
      ? (nearestBoxPoint.length() - 1) * EARTH_RADIUS_KM : null,
    boundApplicable: uniformOrthogonal};
}

function evaluate(t, kind) {
  controller.update(t); entity.update(t, camera); entity.model.updateMatrixWorld(true);
  const cameraPosition = camera.position.toArray(), cameraQuaternion = camera.quaternion.toArray();
  const entityPosition = entity.model.position.toArray(), entityQuaternion = entity.model.quaternion.toArray();
  const progress = routes.routes.map(r => routes.progress(t, r));
  const finiteValues = [...cameraPosition, ...cameraQuaternion, ...entityPosition,
    ...entityQuaternion, ...camera.matrixWorld.elements, ...camera.projectionMatrix.elements,
    ...entity.model.matrixWorld.elements, ...entity.model.scale.toArray(), ...progress];
  const finite = finiteValues.every(Number.isFinite);
  const cameraRadius = camera.position.length(), aircraftRadius = entity.model.position.length();
  if (!finite) addViolation('non_finite_pose', {t, kind});
  if (!(cameraRadius > 1)) addViolation('camera_at_or_inside_earth', {t, cameraRadius});
  const bounds = aircraftBox(), vis = visibility();
  return {t, kind, finite, cameraPosition, cameraQuaternion,
    cameraQuaternionNormError: Math.abs(camera.quaternion.length() - 1),
    cameraRadiusEarthUnits: cameraRadius, cameraAltitudeKm: (cameraRadius - 1) * EARTH_RADIUS_KM,
    cameraFovDeg: camera.fov, entityPosition, entityQuaternion,
    aircraftCenterAltitudeKm: (aircraftRadius - 1) * EARTH_RADIUS_KM,
    entityScale: entity.model.scale.toArray(), visibility: vis, aircraftBox: bounds,
    routeIndex: routes.routes.indexOf(routes.active(t)), progress, shot: scenes.shot(t)?.name ?? null};
}

// 600 encoded-frame nominal times, 600 half-frame times, and the 20s boundary.
// The last half pose is the closing interval from frame 599 to the endpoint.
const poses = Array.from({length: DURATION * FPS * 2 + 1}, (_, i) =>
  evaluate(i / (FPS * 2), i === DURATION * FPS * 2 ? 'end_boundary'
    : i % 2 === 0 ? 'nominal' : 'half'));
const nominal = poses.filter(p => p.kind === 'nominal');
const endpoint = poses.at(-1);

function stepMetrics(samples) {
  const cameraAngle = [], cameraPosition = [], aircraftPosition = [];
  const aircraftAllAngle = [], aircraftVisibleAngle = [], aircraftVisiblePosition = [];
  const routeSwitches = [];
  for (let i = 1; i < samples.length; i++) {
    const a = samples[i - 1], b = samples[i], dt = b.t - a.t;
    const item = {from: a.t, to: b.t, dt};
    cameraAngle.push({...item, value: quaternionAngleDeg(a.cameraQuaternion, b.cameraQuaternion)});
    cameraPosition.push({...item, value: vectorDistance(a.cameraPosition, b.cameraPosition)});
    aircraftPosition.push({...item, value: vectorDistance(a.entityPosition, b.entityPosition)});
    const angle = quaternionAngleDeg(a.entityQuaternion, b.entityQuaternion);
    aircraftAllAngle.push({...item, value: angle});
    const bothVisible = a.visibility.visibleForMetrics && b.visibility.visibleForMetrics;
    if (bothVisible) {
      aircraftVisibleAngle.push({...item, value: angle});
      aircraftVisiblePosition.push({...item, value: vectorDistance(a.entityPosition, b.entityPosition)});
    }
    if (a.routeIndex !== b.routeIndex) routeSwitches.push({...item,
      oldRoute: a.routeIndex, newRoute: b.routeIndex,
      entityCenterStepKm: vectorDistance(a.entityPosition, b.entityPosition) * EARTH_RADIUS_KM,
      headingStepDeg: angle, bothVisible,
      hiddenTransition: !a.visibility.visibleForMetrics && !b.visibility.visibleForMetrics});
  }
  return {cameraAngularStepDeg: stats(cameraAngle), cameraPositionStepEarthUnits: stats(cameraPosition),
    aircraftCenterStepEarthUnits: stats(aircraftPosition), aircraftAngularStepAllPosesDeg: stats(aircraftAllAngle),
    aircraftAngularStepBothVisibleDeg: stats(aircraftVisibleAngle),
    aircraftCenterStepBothVisibleEarthUnits: stats(aircraftVisiblePosition), routeSwitches};
}

function geographicUnit(city) {
  const lon = city.lon * Math.PI / 180, lat = city.lat * Math.PI / 180;
  return new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.sin(lat), -Math.cos(lat) * Math.sin(lon));
}
function endpointError(point, airport) {
  const unit = point.clone().normalize(), expected = geographicUnit(airport);
  // atan2 avoids acos's large relative error at tiny endpoint differences.
  const angle = Math.atan2(unit.clone().cross(expected).length(), unit.dot(expected));
  return {geographicErrorKm: angle * EARTH_RADIUS_KM,
    radialAltitudeKm: (point.length() - 1) * EARTH_RADIUS_KM, airport};
}
const routeResults = routes.routes.map((route, routeIndex) => {
  const samples = Array.from({length: 720}, (_, i) => {
    const u = i / 719, point = route.curve.getPoint(u);
    return {u, altitudeKm: (point.length() - 1) * EARTH_RADIUS_KM,
      finite: point.toArray().every(Number.isFinite)};
  });
  const altitudeViolations = samples.filter(s => !s.finite || s.altitudeKm < 11 - ALTITUDE_EPS_KM
    || s.altitudeKm > 15 + ALTITUDE_EPS_KM);
  for (const sample of altitudeViolations) addViolation('route_centerline_altitude', {routeIndex, ...sample});
  const progressViolations = [];
  for (let i = 0; i < poses.length; i++) {
    const p = poses[i].progress[routeIndex], previous = i ? poses[i - 1].progress[routeIndex] : p;
    if (!Number.isFinite(p) || p < -NUMERIC_EPS || p > 1 + NUMERIC_EPS || p < previous - NUMERIC_EPS)
      progressViolations.push({t: poses[i].t, progress: p, previous});
  }
  for (const item of progressViolations) addViolation('non_monotonic_route_progress', {routeIndex, ...item});
  const start = endpointError(route.curve.getPoint(0), route.a);
  const end = endpointError(route.curve.getPoint(1), route.b);
  for (const [name, value] of Object.entries({start, end}))
    if (value.geographicErrorKm > ALTITUDE_EPS_KM)
      addViolation('route_airport_geographic_endpoint', {routeIndex, endpoint: name, ...value});
  return {routeIndex, startTime: route.start, endTime: route.end, samples: 720,
    altitudeKm: stats(samples.map(s => ({value: s.altitudeKm, u: s.u}))), altitudeViolations,
    progressSamples: poses.length, progressViolations, startAirport: start, endAirport: end,
    endpointInterpretation: 'Horizontal geographic error; 11km radial endpoint altitude is intentional, not airport location error'};
});

function checkFullVertices(t, kind, violationCategory) {
  controller.update(t); entity.update(t, camera); entity.model.updateMatrixWorld(true);
  let nearest = {radius: Infinity}, negativeVertices = 0, nonFiniteVertices = 0;
  const worldPoint = new THREE.Vector3();
  for (const vertex of vertices) {
    worldPoint.copy(vertex.point).applyMatrix4(entity.model.matrixWorld);
    const radius = worldPoint.length();
    if (!Number.isFinite(radius)) { nonFiniteVertices++; continue; }
    if ((radius - 1) * EARTH_RADIUS_KM < -ALTITUDE_EPS_KM) negativeVertices++;
    if (radius < nearest.radius) nearest = {radius, part: vertex.part,
      vertexIndex: vertex.index, worldPosition: worldPoint.toArray()};
  }
  const clearanceKm = (nearest.radius - 1) * EARTH_RADIUS_KM;
  if (clearanceKm < -ALTITUDE_EPS_KM)
    addViolation(violationCategory, {t, kind, clearanceKm, negativeVertices,
      part: nearest.part, vertexIndex: nearest.vertexIndex});
  if (nonFiniteVertices) addViolation('non_finite_transformed_aircraft_vertex', {t, kind, nonFiniteVertices});
  return {t, kind, verticesChecked: vertices.length, visibility: visibility(),
    minEarthClearanceKm: clearanceKm, negativeVertices, nonFiniteVertices,
    nearestPart: nearest.part, nearestVertexIndex: nearest.vertexIndex,
    nearestWorldPosition: nearest.worldPosition};
}
const fullVertexChecks = REPRESENTATIVE_TIMES.map(t => checkFullVertices(t, 'representative',
  'representative_aircraft_vertex_inside_earth'));

const intervalSamples = scenes.events.slice(1).map((time, i) =>
  ({from: scenes.events[i], to: time, value: time - scenes.events[i]}));
const firstThreeEvents = scenes.events.filter(t => t >= 0 && t < 3);
const firstHalfSecond = poses.filter(p => p.t <= .5);
const firstHalfMotion = {
  start: 0, end: .5,
  cameraPositionDeltaEarthUnits: vectorDistance(firstHalfSecond[0].cameraPosition, firstHalfSecond.at(-1).cameraPosition),
  cameraAngleDeltaDeg: quaternionAngleDeg(firstHalfSecond[0].cameraQuaternion, firstHalfSecond.at(-1).cameraQuaternion),
  ...stepMetrics(firstHalfSecond),
  scope: 'Authored camera pose movement, not a black/frozen/visible-pixel test',
};
firstHalfMotion.nonzeroPoseMotion = firstHalfMotion.cameraPositionDeltaEarthUnits > NUMERIC_EPS
  || firstHalfMotion.cameraAngleDeltaDeg > NUMERIC_EPS;

function checkInsertContract() {
  const manager = new SceneManager(), calls = [], start = 8, end = 8.5;
  const source = localSeconds => { calls.push(localSeconds); return {kind: 'prepared-frame-contract-probe', localSeconds}; };
  manager.insert_cinematic_clip({start, end, source});
  const before = manager.active(start - .001), atStart = manager.active(start);
  const active = manager.active(8.25), atEnd = manager.active(end);
  const firstResult = atStart?.source(start - atStart.start);
  const middleResult = active?.source(8.25 - active.start);
  const passed = before === null && atEnd === null && atStart === active
    && active?.source === source && firstResult?.localSeconds === 0
    && middleResult?.localSeconds === .25 && calls.length === 2;
  if (!passed) addViolation('cinematic_insert_interval_or_callback_contract', {calls});
  return {passed, start, end, endExclusive: atEnd === null, callbackLocalSeconds: calls,
    scope: 'Scheduling and caller handoff only; no video decoding, frame compositing, or transition quality claim'};
}

const hashes = {};
for (const file of ['src/aircraft_v3.js', 'src/engine_v3.js', 'src/core_v1_preserved.js', 'tools/preflight_v3.mjs'])
  hashes[file] = createHash('sha256').update(await readFile(path.join(root, file))).digest('hex');
const uncertainBoxes = poses.filter(p => p.visibility.visibleForMetrics
  && (p.aircraftBox.enclosingBoxLowerBoundClearanceKm === null
    || p.aircraftBox.enclosingBoxLowerBoundClearanceKm < -ALTITUDE_EPS_KM))
  .map(p => ({t: p.t, kind: p.kind, ...p.aircraftBox}));
const visiblePoseCount = poses.filter(p => p.visibility.visibleForMetrics).length;
// Only poses that the enclosing box cannot prove safe need the full cached
// 1,912-vertex (or current model vertex count) walk. No new mesh is constructed.
const uncertainFullVertexChecks = uncertainBoxes.map(p => checkFullVertices(p.t, p.kind,
  'uncertain_visible_aircraft_vertex_inside_earth'));
const negativeUncertainChecks = uncertainFullVertexChecks
  .filter(p => p.minEarthClearanceKm < -ALTITUDE_EPS_KM);
const allMeasuredVisibleChecks = [...new Map([...fullVertexChecks, ...uncertainFullVertexChecks]
  .map(p => [p.t, p])).values()].filter(p => p.visibility.visibleForMetrics).sort((a, b) => a.t - b.t);
const measuredVisibleClearance = stats(allMeasuredVisibleChecks.map(p => ({
  value: p.minEarthClearanceKm, t: p.t, kind: p.kind,
  part: p.nearestPart, vertexIndex: p.nearestVertexIndex,
})));
const uncertainTimeSet = new Set(uncertainBoxes.map(p => p.t));
const provenVisibleBoxes = poses.filter(p => p.visibility.visibleForMetrics && !uncertainTimeSet.has(p.t));
const lowerCandidates = [...provenVisibleBoxes.map(p => p.aircraftBox.enclosingBoxLowerBoundClearanceKm),
  ...uncertainFullVertexChecks.map(p => p.minEarthClearanceKm)].filter(Number.isFinite);
const globalVertexMinimumLowerBound = lowerCandidates.length ? Math.min(...lowerCandidates) : null;
const globalVertexMinimumUpperBound = measuredVisibleClearance.min?.value ?? null;
const noCandidateVertexPenetrations = negativeUncertainChecks.length === 0
  && uncertainFullVertexChecks.every(p => p.nonFiniteVertices === 0)
  && uncertainFullVertexChecks.length === uncertainBoxes.length;
const globalVertexMinimumResolved = Number.isFinite(globalVertexMinimumLowerBound)
  && Number.isFinite(globalVertexMinimumUpperBound)
  && Math.abs(globalVertexMinimumUpperBound - globalVertexMinimumLowerBound) <= ALTITUDE_EPS_KM;
const report = {
  schema: 1, scope: 'V3 CPU scene geometry and scheduling preflight; does not certify final graphic quality',
  sourceHashes: hashes, threeRevision: THREE.REVISION,
  sampling: {fps: FPS, durationSeconds: DURATION, nominalPoses: nominal.length,
    halfPoses: poses.filter(p => p.kind === 'half').length, endBoundaryPoses: 1,
    closingHalfPoseIncluded: true, totalPoses: poses.length,
    routeSamplesPerRoute: 720, representativeFullVertexTimes: REPRESENTATIVE_TIMES,
    actualVisibilityAlphaThreshold: VISIBILITY_ALPHA},
  coordinateSystem: 'Right-handed Three.js: geographic (cos(lat)cos(lon), sin(lat), -cos(lat)sin(lon)); Earth radius=1',
  earthRadiusKm: EARTH_RADIUS_KM, cities: CITIES, shots: SHOTS,
  camera: {
    finitePoses: poses.filter(p => p.finite).length,
    radiusEarthUnits: stats(poses.map(p => ({value: p.cameraRadiusEarthUnits, t: p.t}))),
    actualAltitudeKm: stats(poses.map(p => ({value: p.cameraAltitudeKm, t: p.t}))),
    quaternionNormError: stats(poses.map(p => ({value: p.cameraQuaternionNormError, t: p.t}))),
    nominalFrameSteps: stepMetrics(nominal), halfFrameSteps: stepMetrics(poses),
    closingBoundaryStep: stepMetrics([nominal.at(-1), endpoint]), firstHalfSecondMotion: firstHalfMotion,
    thresholdNote: 'Angular/position steps are observations, not automatic judgments of cinematic smoothness',
  },
  routes: routeResults,
  aircraft: {parts: parts.length, cachedLocalVertices: vertices.length,
    visibleDensePoses: visiblePoseCount,
    localBounds: {min: localBounds.min.toArray(), max: localBounds.max.toArray()},
    visibleCornerClearanceKm: stats(poses.filter(p => p.visibility.visibleForMetrics)
      .map(p => ({value: p.aircraftBox.cornerMinClearanceKm, t: p.t}))),
    visibleEnclosingBoxLowerBoundClearanceKm: stats(poses.filter(p => p.visibility.visibleForMetrics)
      .map(p => ({value: p.aircraftBox.enclosingBoxLowerBoundClearanceKm, t: p.t}))),
    potentialEnclosingBoxIntersections: uncertainBoxes, representativeFullVertexChecks: fullVertexChecks,
    allVisibleDensePosesProvenOutsideEarthByEnclosingBox: visiblePoseCount > 0 && uncertainBoxes.length === 0,
    uncertainVisibleFullVertexValidation: {
      uncertainVisiblePoses: uncertainBoxes.length, fullVertexCheckedPoses: uncertainFullVertexChecks.length,
      totalVertexTransformations: uncertainFullVertexChecks.length * vertices.length,
      actualNegativePoseCount: negativeUncertainChecks.length,
      actualNegativePoseTimes: negativeUncertainChecks.map(p => p.t),
      totalNegativeVerticesAtCheckedPoses: uncertainFullVertexChecks.reduce((sum, p) => sum + p.negativeVertices, 0),
      negativeToleranceKm: ALTITUDE_EPS_KM,
      measuredVisibleVertexClearanceKm: measuredVisibleClearance,
      allVisibleDenseSampledVerticesOutsideEarth: visiblePoseCount > 0 && noCandidateVertexPenetrations,
      globalVisibleVertexMinimumBracketKm: {
        lowerBound: globalVertexMinimumLowerBound, measuredUpperBound: globalVertexMinimumUpperBound,
        exactMinimumProvenByBounds: globalVertexMinimumResolved,
        scope: 'Uncertain poses use all actual vertices. Other poses use conservative box bounds. An unresolved bracket must not be described as an exact global minimum',
      },
      checks: uncertainFullVertexChecks,
      scope: 'Actual transformed vertex distances at uncertain visible nominal/half poses; negative box bounds remain candidates, not detected collisions',
    },
    boundNote: 'Cached static part geometry; positive oriented-box lower bound covers the entire model. Negative box bound is inconclusive, not a detected model collision',
    transitionNote: 'Route endpoints share the same Narita coordinates. Route-switch heading is reported separately and only included in visible-heading metrics when both samples exceed the opacity threshold',
  },
  authoredEvents: {times: scenes.events, intervalsSeconds: stats(intervalSamples),
    firstThreeSecondsTimes: firstThreeEvents, countIncludingOpening: firstThreeEvents.length,
    countAfterOpening: firstThreeEvents.filter(t => t > 0).length,
    atLeastThreeAuthoredEventsAfterOpening: firstThreeEvents.filter(t => t > 0).length >= 3,
    scope: 'Declared event schedule; actual meaningful visual-event visibility must be inspected in encoded frames'},
  cinematicInsertContract: checkInsertContract(),
  numericalViolations: violations,
  limitations: [
    'No browser/GPU, asset load, black/duplicate frame, text/viewport clipping, color, audio or playback validation.',
    'Routes are checked at their centerlines; visual tube thickness and glow envelopes require renderer/frame checks.',
    'Full vertex tests do not prove triangle-interior clearance between vertices or motion between the sampled times; dense conservative box bounds cover complete geometry only at poses where positive.',
    'Aircraft scale is illustrative, not a statement of physical fuselage length or real elapsed flight time.',
    'Pixel visibility and empirical viewer attention/retention are not measured.',
  ],
  poses,
};

await mkdir(path.dirname(output), {recursive: true});
await writeFile(output, JSON.stringify(report, null, 2), {flag: 'wx'});
console.log(JSON.stringify({output, nominalPoses: nominal.length, halfPoses: 600,
  numericViolationCount: violations.length,
  cameraNominalAngularStepMaxDeg: report.camera.nominalFrameSteps.cameraAngularStepDeg.max,
  visibleAircraftHeadingStepMaxDeg: report.camera.halfFrameSteps.aircraftAngularStepBothVisibleDeg.max,
  visibleAircraftEnclosingBoxMinimumClearanceKm: report.aircraft.visibleEnclosingBoxLowerBoundClearanceKm.min,
  uncertainVisibleBoxPoses: uncertainBoxes.length,
  fullVertexCheckedUncertainVisiblePoses: uncertainFullVertexChecks.length,
  actualNegativeVertexPoseCount: negativeUncertainChecks.length,
  actualNegativeVertexPoseTimes: negativeUncertainChecks.map(p => p.t),
  measuredVisibleVertexMinimumClearanceKm: measuredVisibleClearance.min,
  globalVisibleVertexMinimumBracketKm: report.aircraft.uncertainVisibleFullVertexValidation.globalVisibleVertexMinimumBracketKm,
  authoredEventMeanIntervalSeconds: report.authoredEvents.intervalsSeconds.mean,
  insertContract: report.cinematicInsertContract.passed,
  scope: report.scope}, null, 2));
if (violations.length) process.exitCode = 1;
