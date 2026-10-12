import test from 'node:test';
import assert from 'node:assert/strict';
import {generateDetailExtentCandidates} from '../web/map_infographic_v1/detail_data_profile_v1.mjs';
import {LOCAL_QUALITY_POLICY} from '../web/map_infographic_v1/local_detail_admission.mjs';
import {PRODUCTION_DETAIL_GRADE, evaluateVisualDetailCandidate, selectVisualDetailExtent,
 createEventDetailFramingRequest} from '../web/map_infographic_v1/visual_detail_admission_v1.mjs';

// Invented hashes and producer reviews validate only pure contract behavior.
// No synthetic test result certifies production pixels or a real dataset.
const digest = letter => letter.repeat(64);
const input = () => ({eventGeometry: {type: 'LineString', coordinates: [[0, 0], [.1, .4], [.2, 1]]},
 eventAnchor: [.1, .4], currentBounds: [-5, -10, 5, 10], output: [1080, 1920], safeArea: [48, 72, 1032, 1848]});
function evidence(candidate) {
 const box = candidate.projectedGeometryBounds, middle = (box[1] + box[3]) / 2,
  anchor = [(candidate.eventAnchor[0] - candidate.bounds[0]) / candidate.widthDegrees * candidate.output[0],
   (candidate.bounds[3] - candidate.eventAnchor[1]) / candidate.heightDegrees * candidate.output[1]];
 return {evidenceKind: 'SYNTHETIC_TEST_ONLY',
  render: {verified: true, width: 1080, height: 1920, sha256: digest('a'), byteLength: 1234,
   candidateBounds: [...candidate.bounds], geometryBinding: candidate.geometryBinding},
  visual: {terrain: 'VISUAL_PASS', coastline: 'VISUAL_PASS', canal: 'VISUAL_PASS', marker: 'VISUAL_PASS',
   labels: 'VISUAL_PASS', safeArea: 'VISUAL_PASS', metric: 'VISUAL_PASS', lineReadable: true, metricRelated: true},
  semantic: {sameGeography: true, sameObject: true, relationCorrect: true, geometryMeaningPreserved: true, metricMateriallyTrue: true},
  protection: {cameraV5: true, eventV2: true, rendererVisual: true, geometry: true, marker: true},
  layout: {verified: true, candidateBounds: [...candidate.bounds], geometryBinding: candidate.geometryBinding,
   metricBounds: [box[2] + 20, middle - 30, box[2] + 220, middle + 30],
   protectedGraphics: [{kind: 'TEXT', bounds: [60, 80, 300, 130]},
    {kind: 'MARKER', bounds: [anchor[0] - 20, anchor[1] - 20, anchor[0] + 20, anchor[1] + 20]}]},
  quality: {gisAbsoluteAccuracyCertified: false, coastAlignmentMeasured: false,
   nativeTexelToScreenPixelRatio: [4, 5]}};
}
function fixture(given = input()) {
 const candidates = generateDetailExtentCandidates(given), evidenceByCandidate = {};
 for (const candidate of candidates) evidenceByCandidate[candidate.id] = evidence(candidate);
 return {given, candidates, eventGeometry: given.eventGeometry, evidenceByCandidate, surveyDetailStatus: 'LOCAL_NOT_ADMITTED'};
}
const audit = (data, index = 1) => evaluateVisualDetailCandidate({candidate: data.candidates[index],
 eventGeometry: data.eventGeometry, evidence: data.evidenceByCandidate[data.candidates[index].id], surveyDetailStatus: data.surveyDetailStatus});
function request(data, admission) {
 return createEventDetailFramingRequest({...data.given,
  currentCameraState: {bounds: data.given.currentBounds, output: data.given.output},
  protectedGraphics: data.evidenceByCandidate.D0.layout.protectedGraphics,
  evidenceByCandidate: data.evidenceByCandidate, surveyDetailStatus: data.surveyDetailStatus, detailAdmission: admission});
}

test('production detail grade is visual and the old survey policy is unchanged', () => {
 assert.equal(PRODUCTION_DETAIL_GRADE, 'FACT_BASED_VISUAL_GRADE');
 assert.equal(LOCAL_QUALITY_POLICY.maxPixelsPerNativeTexel, 1);
 assert.equal(LOCAL_QUALITY_POLICY.maxGeometryErrorPixels, 1);
 assert.equal(Object.isFrozen(LOCAL_QUALITY_POLICY), true);
});

test('A: already readable full geometry asks to use the current view', () => {
 const given = input(); given.eventGeometry.coordinates = [[0, -3], [.3, 3]];
 const data = fixture(given), before = structuredClone(data), result = request(data);
 assert.equal(result.decision, 'USE_CURRENT_VIEW');
 assert.deepEqual(result.targetFraming.bounds, given.currentBounds);
 assert.equal(result.surveyDetailStatus, 'LOCAL_NOT_ADMITTED');
 assert.equal(result.surveyAdmissionModified, false);
 assert.deepEqual(data, before);
});

test('B: small geometry asks for the least sufficient approach without a named-candidate constant', () => {
 const data = fixture(), selected = selectVisualDetailExtent(data), result = request(data, selected);
 assert.equal(selected.status, 'SYNTHETIC_VISUAL_DETAIL_PASS');
 assert.equal(selected.certificate.candidateId, 'D1');
 assert.equal(result.decision, 'DETAIL_APPROACH_REQUIRED');
 assert.deepEqual(result.targetFraming.bounds, data.candidates[1].bounds);
 assert.ok(result.admission.audits[0].blockingErrors.includes('MINIMUM_SUFFICIENT_EVENT_COVERAGE'));
 assert.equal(result.eventAnimationStarted, false);
 assert.equal(result.cameraV5Modified, false);
});

test('C: a long narrow line keeps the complete source and halo inside the safe area', () => {
 const given = input(); given.eventGeometry.coordinates = [[0, -1], [.01, 0], [0, 1]];
 const data = fixture(given), result = request(data), selected = result.admission.selectedCandidate;
 assert.equal(result.decision, 'DETAIL_APPROACH_REQUIRED');
 assert.equal(selected.sourceCoordinateCount, 3);
 assert.equal(selected.wholeGeometryVisible, true);
 assert.equal(result.eventGeometryBinding, selected.geometryBinding);
 assert.ok(result.admission.audits.find(row => row.candidate.id === selected.id).checks
  .some(row => row.name === 'FULL_GEOMETRY_SAFE_AREA' && row.status === 'PASS'));
});

test('missing metre certificates, enlarged texels and minor visual warnings do not block', () => {
 const data = fixture(); data.evidenceByCandidate.D1.visual.coastline = 'VISUAL_WARNING';
 data.evidenceByCandidate.D1.visual.terrain = 'VISUAL_WARNING';
 const result = audit(data);
 assert.equal(result.status, 'VISUAL_DETAIL_ADMITTED');
 assert.equal(result.visual, 'VISUAL_WARNING');
 for (const name of ['GIS_ABSOLUTE_ACCURACY_NOT_SURVEY_CERTIFIED', 'COAST_ALIGNMENT_NOT_METRE_MEASURED', 'NATIVE_TEXEL_ENLARGEMENT'])
  assert.ok(result.warnings.some(row => row.name === name));
 assert.equal(result.surveyDetailStatus, 'LOCAL_NOT_ADMITTED');
 assert.equal(result.surveyAdmissionModified, false);
});

test('selection can choose a later candidate when reviewed readability is insufficient', () => {
 const data = fixture(); data.evidenceByCandidate.D1.visual.lineReadable = false;
 assert.equal(selectVisualDetailExtent(data).certificate.candidateId, 'D2');
 const renamed = structuredClone(data); renamed.candidates.forEach((candidate, index) => {
  const old = candidate.id; candidate.id = 'PROPOSAL_' + index;
  renamed.evidenceByCandidate[candidate.id] = renamed.evidenceByCandidate[old]; delete renamed.evidenceByCandidate[old];
 });
 assert.equal(selectVisualDetailExtent(renamed).certificate.candidateId, 'PROPOSAL_2');
});

test('wrong place, false relation, wrong object and materially false metric fail', () => {
 for (const key of ['sameGeography', 'sameObject', 'relationCorrect', 'geometryMeaningPreserved', 'metricMateriallyTrue']) {
  const data = fixture(); data.evidenceByCandidate.D1.semantic[key] = false;
  const result = audit(data);
  assert.equal(result.status, 'VISUAL_DETAIL_NOT_ADMITTED');
  assert.equal(result.semanticIntegrity, 'FAIL');
  assert.ok(result.blockingErrors.includes('SEMANTIC_' + key));
 }
});

test('severe visible terrain or coastline errors fail rather than becoming accuracy warnings', () => {
 for (const key of ['terrain', 'coastline', 'canal']) {
  const data = fixture(); data.evidenceByCandidate.D1.visual[key] = 'VISUAL_FAIL';
  assert.equal(audit(data).status, 'VISUAL_DETAIL_NOT_ADMITTED');
 }
});

test('missing or stale actual render evidence blocks despite otherwise favorable flags', () => {
 for (const mutate of [
  proof => {proof.render.verified = false;},
  proof => {proof.render.width = 540;},
  proof => {proof.render.sha256 = null;},
  proof => {proof.render.candidateBounds[0] += 1;},
  proof => {proof.render.geometryBinding = '{}';},
  proof => {proof.evidenceKind = 'DOCUMENTATION_ONLY';},
 ]) {
  const data = fixture(); mutate(data.evidenceByCandidate.D1);
  assert.ok(audit(data).blockingErrors.includes('ACTUAL_RENDER_EVIDENCE'));
 }
});

test('source replacement, forged coverage, crop and changed protected source fail', () => {
 const changed = fixture(); changed.eventGeometry = structuredClone(changed.eventGeometry);
 changed.eventGeometry.coordinates[1][0] += .001;
 assert.ok(audit(changed).blockingErrors.includes('SOURCE_GEOMETRY_UNCHANGED'));
 const forged = fixture(); forged.candidates = structuredClone(forged.candidates);
 forged.candidates[1].screenCoverage = 1;
 assert.ok(audit(forged).blockingErrors.includes('FRESH_FULL_GEOMETRY_PROJECTION'));
 const cropInput = input(); cropInput.currentBounds = [-.01, .35, .11, .45];
 const cropped = fixture(cropInput), croppedResult = audit(cropped, 0);
 assert.ok(croppedResult.blockingErrors.includes('FULL_GEOMETRY_SAFE_AREA'));
 const protectedChange = fixture(); protectedChange.evidenceByCandidate.D1.protection.marker = false;
 assert.ok(audit(protectedChange).blockingErrors.includes('PROTECTED_marker'));
});

test('line behind geographic marker is allowed while text and metric collisions fail', () => {
 const data = fixture(); assert.equal(audit(data).status, 'VISUAL_DETAIL_ADMITTED');
 const box = data.candidates[1].projectedGeometryBounds, middle = (box[1] + box[3]) / 2;
 data.evidenceByCandidate.D1.layout.protectedGraphics.push({kind: 'TEXT', bounds: [box[0] - 10, middle - 20, box[2] + 10, middle + 20]});
 assert.ok(audit(data).blockingErrors.includes('LINE_CRITICAL_COLLISION_ZERO'));
 const metric = fixture(); metric.evidenceByCandidate.D1.layout.metricBounds = [...metric.evidenceByCandidate.D1.layout.protectedGraphics[1].bounds];
 assert.ok(audit(metric).blockingErrors.includes('METRIC_CRITICAL_COLLISION_ZERO'));
});

test('safe area and fresh candidate layout remain mandatory', () => {
 const unsafe = fixture(); unsafe.evidenceByCandidate.D1.layout.metricBounds = [0, 0, 100, 60];
 assert.ok(audit(unsafe).blockingErrors.includes('METRIC_SAFE_AREA'));
 const stale = fixture(); stale.evidenceByCandidate.D1.layout.candidateBounds = [...stale.candidates[2].bounds];
 assert.ok(audit(stale).blockingErrors.includes('FRESH_MEASURED_LAYOUT'));
});

test('offscreen geographic labels keep their anchor/style while visible title and panels remain protected', () => {
 const data = fixture(); data.evidenceByCandidate.D1.layout.hiddenGeographicLabels = [{role: 'COUNTRY',
  reason: 'PROJECTION_OUTSIDE_SAFE_AREA', originalAnchorPreserved: true, stylePreserved: true}];
 assert.equal(audit(data).status, 'VISUAL_DETAIL_ADMITTED');
 assert.ok(audit(data).warnings.some(row => row.name === 'GEOGRAPHIC_LABEL_OUTSIDE_SAFE_AREA'));
 data.evidenceByCandidate.D1.layout.hiddenGeographicLabels[0].role = 'TITLE';
 assert.ok(audit(data).blockingErrors.includes('HIDDEN_GEOGRAPHIC_LABELS_PRESERVED'));
});

test('synthetic certificates remain ineligible for production even when the pure audit passes', () => {
 const data = fixture(), selected = selectVisualDetailExtent(data), result = request(data, selected);
 assert.equal(selected.status, 'SYNTHETIC_VISUAL_DETAIL_PASS');
 assert.equal(selected.certificate.productionEligible, false);
 assert.equal(result.certificate.evidenceKind, 'SYNTHETIC_TEST_ONLY');
 assert.equal(result.certificate.productionEligible, false);
 // This is a simulated trusted producer declaration, not real imagery.
 const declared = fixture(); Object.values(declared.evidenceByCandidate).forEach(row => {row.evidenceKind = 'ACTUAL_NATIVE_RENDER';});
 assert.equal(selectVisualDetailExtent(declared).status, 'VISUAL_DETAIL_ADMITTED');
});

test('all unusable visual candidates produce an explicit blocked framing request', () => {
 const data = fixture(); Object.values(data.evidenceByCandidate).forEach(row => {row.visual.terrain = 'VISUAL_FAIL';});
 const result = request(data);
 assert.equal(result.decision, 'EVENT_DETAIL_FRAMING_BLOCKED');
 assert.equal(result.certificate, null);
 assert.equal(result.targetFraming, null);
});

test('framing requests reject a stale certificate and freeze the accepted contract', () => {
 const data = fixture(), selected = selectVisualDetailExtent(data), result = request(data, selected);
 assert.equal(Object.isFrozen(result.targetFraming.bounds), true);
 const stale = structuredClone(selected); stale.certificate.evidenceBinding = '{}';
 assert.throws(() => request(data, stale), /EVENT_DETAIL_STALE_ADMISSION/);
});

test('translation preserves visual framing rather than testing a place name or coordinate', () => {
 const data = fixture(), original = selectVisualDetailExtent(data), shifted = input(), delta = [12, 8];
 shifted.eventGeometry.coordinates = shifted.eventGeometry.coordinates.map(p => p.map((v, axis) => v + delta[axis]));
 shifted.eventAnchor = shifted.eventAnchor.map((v, axis) => v + delta[axis]);
 shifted.currentBounds = shifted.currentBounds.map((v, axis) => v + delta[axis % 2]);
 const translated = selectVisualDetailExtent(fixture(shifted));
 assert.equal(translated.certificate.candidateId, original.certificate.candidateId);
 translated.certificate.bounds.forEach((v, index) => assert.ok(Math.abs(v - original.certificate.bounds[index] - delta[index % 2]) < 1e-12));
});
