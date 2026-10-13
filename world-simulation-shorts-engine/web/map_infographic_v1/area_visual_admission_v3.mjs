/** Polygon/front-aware visual admission. No Line certificate transfer or native policy modification. */
import {freezeEventData} from './event_contract_v1.mjs';
import {geometryBounds, fitGeographicExtent} from './scale_contract.mjs';
import {assertAreaPlan} from './area_core_v3.mjs';

export const AREA_DATA_PROFILE_V3_VERSION = 'AREA_DATA_PROFILE_V3';
export const AREA_VISUAL_ADMISSION_V3_VERSION = 'AREA_VISUAL_ADMISSION_V3';
export const AREA_DETAIL_FRAMING_REQUEST_V3_VERSION = 'AREA_DETAIL_FRAMING_REQUEST_V3';
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b), copy = value => structuredClone(value);
const box = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
const digest = value => /^[a-f0-9]{64}$/u.test(value ?? '');
const inside = (outer, inner) => inner[0] >= outer[0] && inner[1] >= outer[1] && inner[2] <= outer[2] && inner[3] <= outer[3];
function points(geometry) {
 const result = [];
 const visit = value => {
  if (Array.isArray(value) && value.length === 2 && value.every(Number.isFinite)) result.push([...value]);
  else if (Array.isArray(value)) value.forEach(visit);
 };
 visit(geometry.coordinates); return result;
}
const bounds = values => [Math.min(...values.map(point => point[0])), Math.min(...values.map(point => point[1])),
 Math.max(...values.map(point => point[0])), Math.max(...values.map(point => point[1]))];
const inflate = (value, padding) => [value[0] - padding, value[1] - padding, value[2] + padding, value[3] + padding];
function nativeProject(project, point) {
 const projected = project([...point]);
 if (!Array.isArray(projected) || projected.length !== 2 || !projected.every(Number.isFinite))
  throw Error('AREA_ADMISSION_EXISTING_NATIVE_PROJECTION_REQUIRED');
 return [...projected];
}
export function compileAreaDataProfile({areaPlan, terrain = null, gis = [], surveyDetailStatus = 'NOT_ADMITTED'} = {}) {
 const plan = assertAreaPlan(areaPlan);
 if (!Array.isArray(gis)) throw Error('AREA_PROFILE_GIS_RECORDS_REQUIRED');
 return freezeEventData({version: AREA_DATA_PROFILE_V3_VERSION, grade: 'FACT_BASED_VISUAL_GRADE',
  geometryBinding: plan.geometryBinding, terrain: copy(terrain), gis: copy(gis), surveyDetailStatus,
  surveyAdmissionModified: false, dataMode: plan.intent.data_mode, physicalSimulation: false});
}

/** Full evolving/swept geometry is projected through the supplied native callback. A point/initial polygon alone is insufficient. */
export function evaluateAreaVisualAdmission({areaPlan, project, safeArea, protectedGraphics = [], currentCameraState,
 semanticIntegrity, visualEvidence, desiredCoverageRange = [.2, .6], paddingPixels = 6, dataProfile = null} = {}) {
 const plan = assertAreaPlan(areaPlan);
 if (typeof project !== 'function' || !box(safeArea) || !box(currentCameraState?.bounds)
  || !Array.isArray(currentCameraState.output) || !same(currentCameraState.output, [1080, 1920])
  || !Array.isArray(desiredCoverageRange) || desiredCoverageRange.length !== 2
  || !desiredCoverageRange.every(value => Number.isFinite(value) && value > 0 && value <= 1)
  || desiredCoverageRange[0] > desiredCoverageRange[1] || !Number.isFinite(paddingPixels) || paddingPixels <= 0)
  throw Error('AREA_VISUAL_ADMISSION_CONTRACT_REQUIRED');
 if (!Array.isArray(protectedGraphics) || protectedGraphics.some(item => !['MARKER', 'TEXT', 'PANEL', 'METRIC'].includes(item?.kind) || !box(item.box)))
  throw Error('AREA_VISUAL_TYPED_PROTECTED_GRAPHICS_REQUIRED');
 if (dataProfile && (dataProfile.version !== AREA_DATA_PROFILE_V3_VERSION || dataProfile.geometryBinding !== plan.geometryBinding
  || dataProfile.grade !== 'FACT_BASED_VISUAL_GRADE' || dataProfile.surveyAdmissionModified !== false))
  throw Error('AREA_VISUAL_STALE_DATA_PROFILE');
 const sourcePoints = [...plan.sweepGeometries.flatMap(points), [...plan.intent.origin],
  ...(plan.intent.metric ? [[...plan.intent.metric.anchor]] : [])];
 if (!sourcePoints.length) throw Error('AREA_FULL_SWEEP_GEOMETRY_REQUIRED');
 const projected = sourcePoints.map(point => nativeProject(project, point));
 const geographicBounds = bounds(sourcePoints), projectedBounds = bounds(projected), supportBounds = inflate(projectedBounds, paddingPixels);
 const axisCoverage = [(projectedBounds[2] - projectedBounds[0]) / (safeArea[2] - safeArea[0]),
  (projectedBounds[3] - projectedBounds[1]) / (safeArea[3] - safeArea[1])];
 const coverage = Math.max(...axisCoverage), fullSweepSafe = inside(safeArea, supportBounds);
 const warnings = [], blockingErrors = [], checks = [];
 const check = (name, success, detail = null) => {checks.push({name, status: success ? 'PASS' : 'FAIL', detail}); if (!success) blockingErrors.push(name);};
 for (const name of ['sameGeography', 'sameObject', 'relationCorrect', 'geometryMeaningPreserved', 'metricMateriallyTrue'])
  check('SEMANTIC_' + name, semanticIntegrity?.[name] === true);
 check('NO_SEVERE_VISUAL_ERROR', Array.isArray(visualEvidence?.severeErrors) && visualEvidence.severeErrors.length === 0);
 check('VISIBLE_VISUAL_GRADE', ['VISUAL_PASS', 'VISUAL_WARNING'].includes(visualEvidence?.status));
 check('CRITICAL_COLLISION_ZERO', visualEvidence?.criticalCollisions === 0);
 if (visualEvidence?.status === 'VISUAL_WARNING') warnings.push({name: 'PRODUCER_VISUAL_WARNING', detail: copy(visualEvidence.warnings ?? [])});
 const synthetic = plan.intent.data_mode === 'SYNTHETIC_TEST' && visualEvidence?.evidenceKind === 'SYNTHETIC_TEST_ONLY';
 const render = visualEvidence?.render;
 const production = plan.intent.data_mode === 'PRODUCTION' && visualEvidence?.evidenceKind === 'ACTUAL_NATIVE_RENDER'
  && render?.verified === true && digest(render.sha256) && Number.isSafeInteger(render.byteLength) && render.byteLength > 0
  && render.width === 1080 && render.height === 1920 && same(render.bounds, currentCameraState.bounds)
  && render.geometryBinding === plan.geometryBinding;
 check('NATIVE_OR_EXPLICIT_SYNTHETIC_EVIDENCE', synthetic || production);
 if (dataProfile?.terrain?.nativeTexelToScreenPixelRatio && Math.max(...dataProfile.terrain.nativeTexelToScreenPixelRatio) > 1)
  warnings.push({name: 'NATIVE_TEXEL_ENLARGEMENT_VISUAL_REVIEW_REQUIRED', detail: copy(dataProfile.terrain.nativeTexelToScreenPixelRatio)});
 if (dataProfile?.gis?.some(item => item.absoluteAccuracyCertified !== true) || !dataProfile?.gis?.length)
  warnings.push({name: 'GIS_ABSOLUTE_ACCURACY_NOT_SURVEY_CERTIFIED'});
 if (dataProfile?.surveyDetailStatus !== 'ADMITTED') warnings.push({name: 'SURVEY_STATUS_PRESERVED', detail: dataProfile?.surveyDetailStatus ?? 'NOT_ADMITTED'});
 const semanticPass = blockingErrors.length === 0;
 let decision = 'AREA_VISUAL_BLOCKED', targetFraming = null, status = 'AREA_VISUAL_NOT_ADMITTED';
 const readable = coverage >= desiredCoverageRange[0];
 if (semanticPass && fullSweepSafe && readable) {decision = 'USE_CURRENT_VIEW'; status = 'AREA_VISUAL_ADMITTED';}
 else if (semanticPass) {
  // A typed Area request uses the actual full sweep. It does not claim native proof at a yet-unrendered target.
  try {
   const sourceBounds = geometryBounds({geometry: {type: 'MultiPoint', coordinates: sourcePoints}});
   const fitted = fitGeographicExtent(sourceBounds, {output: currentCameraState.output,
    padding: Math.max(1.08, currentCameraState.output[0] / (safeArea[2] - safeArea[0]), currentCameraState.output[1] / (safeArea[3] - safeArea[1]))});
   targetFraming = {bounds: fitted, center: [(fitted[0] + fitted[2]) / 2, (fitted[1] + fitted[3]) / 2],
    output: [...currentCameraState.output], safeArea: [...safeArea], fullSweepBinding: plan.geometryBinding,
    admissionRequired: true, evidenceKind: 'UNRENDERED_AREA_TARGET_REQUEST'};
   decision = 'DETAIL_APPROACH_REQUIRED'; status = 'AREA_DETAIL_REQUEST_REQUIRED';
  } catch (error) {blockingErrors.push('AREA_TARGET_FRAMING_UNSUPPORTED'); warnings.push({name: 'FRAMING_ERROR', detail: error.message});}
 }
 return freezeEventData({version: AREA_VISUAL_ADMISSION_V3_VERSION, grade: 'FACT_BASED_VISUAL_GRADE', status, decision,
  geometryBinding: plan.geometryBinding, fullSweepBinding: plan.geometryBinding, fullSweepCoordinateCount: sourcePoints.length,
  fullSweepGeographicBounds: geographicBounds, projectedBounds, projectedSupportBounds: supportBounds,
  fullSweepSafe, screenCoverage: coverage, axisCoverage, readable, desiredCoverageRange: [...desiredCoverageRange],
  targetFraming, requestVersion: targetFraming ? AREA_DETAIL_FRAMING_REQUEST_V3_VERSION : null,
  protectedGraphics: copy(protectedGraphics), protectedPixelPolicy: 'MASK_ALL_NATIVE_RESERVATIONS_WITHOUT_CHANGING_GEOGRAPHY',
  checks, warnings, blockingErrors, productionEligible: status === 'AREA_VISUAL_ADMITTED' && production,
  evidenceKind: synthetic ? 'SYNTHETIC_TEST_ONLY' : production ? 'ACTUAL_NATIVE_RENDER' : 'UNVERIFIED',
  surveyDetailStatus: dataProfile?.surveyDetailStatus ?? 'NOT_ADMITTED', surveyAdmissionModified: false,
  cameraV5Modified: false, physicalSimulation: false});
}
