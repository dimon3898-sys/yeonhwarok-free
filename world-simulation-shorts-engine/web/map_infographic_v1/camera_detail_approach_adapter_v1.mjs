/** Camera-owned extension after V5 arrival; existing Camera/Event sources stay read-only. */
import {freezeEventData} from './event_contract_v1.mjs';
import {assertEventPlan, evaluateEventFrame} from './event_timeline_v1.mjs';

export const CAMERA_DETAIL_APPROACH_ADAPTER_V1_VERSION = 'CAMERA_DETAIL_APPROACH_ADAPTER_V1';
export const EVENT_DETAIL_TIMELINE_V1_VERSION = 'EVENT_DETAIL_TIMELINE_V1';
export const EVENT_DETAIL_STATES_V1 = Object.freeze(['EVENT_ARRIVAL', 'DETAIL_DECISION', 'DETAIL_APPROACH',
 'DETAIL_SETTLE', 'DETAIL_LOCK', 'LINE_REVEAL', 'LINE_HOLD', 'METRIC_REVEAL', 'INFORMATION_HOLD']);
const knownPlans = new WeakSet();
// Match the framing contract's stable object-key order; coordinate arrays retain exact order/value.
const canonical = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
 ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const same = (a, b) => canonical(a) === canonical(b);
const copy = value => JSON.parse(JSON.stringify(value));
const inside = (p, b) => p[0] >= b[0] && p[1] >= b[1] && p[0] <= b[2] && p[1] <= b[3];
function integer(value, label, minimum = 0) {
 if (!Number.isSafeInteger(value) || value < minimum) throw Error(`DETAIL_${label}_INTEGER_REQUIRED`);
 return value;
}
function bounds(value, label, geographic = false) {
 if (!Array.isArray(value) || value.length !== 4 || !value.every(Number.isFinite)
  || value[0] >= value[2] || value[1] >= value[3]
  || (geographic && (value[0] < -180 || value[2] > 180 || value[1] < -90 || value[3] > 90)))
  throw Error(`DETAIL_${label}_BOUNDS_REQUIRED`);
 return [...value];
}
function outputPair(value) {
 if (!Array.isArray(value) || value.length !== 2 || !value.every(v => Number.isSafeInteger(v) && v > 0))
  throw Error('DETAIL_OUTPUT_REQUIRED');
 return [...value];
}
export const detailSmootherstep = t => {
 if (!Number.isFinite(t) || t < 0 || t > 1) throw Error('DETAIL_NORMALIZED_TIME_REQUIRED');
 return t === 0 ? 0 : t === 1 ? 1 : t * t * t * (t * (t * 6 - 15) + 10);
};
const center = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
const spans = b => [b[2] - b[0], b[3] - b[1]];
function interpolateBounds(start, target, t) {
 if (t === 0) return [...start];
 if (t === 1) return [...target];
 const u = detailSmootherstep(t), a = center(start), b = center(target), as = spans(start), bs = spans(target);
 const c = a.map((v, i) => v + (b[i] - v) * u);
 const s = as.map((v, i) => Math.exp(Math.log(v) + (Math.log(bs[i]) - Math.log(v)) * u));
 return [c[0] - s[0] / 2, c[1] - s[1] / 2, c[0] + s[0] / 2, c[1] + s[1] / 2];
}
const project = (p, b, output) => [(p[0] - b[0]) / (b[2] - b[0]) * output[0],
 (b[3] - p[1]) / (b[3] - b[1]) * output[1]];
function projectedSafety(geometry, cameraBounds, output, safeArea, padding, anchor) {
 const projected = geometry.coordinates.map(p => project(p, cameraBounds, output));
 const inner = [safeArea[0] + padding, safeArea[1] + padding, safeArea[2] - padding, safeArea[3] - padding];
 const projectedBounds = [Math.min(...projected.map(p => p[0])), Math.min(...projected.map(p => p[1])),
  Math.max(...projected.map(p => p[0])), Math.max(...projected.map(p => p[1]))];
 return {wholeGeometryVisible: projected.every(p => inside(p, inner)),
  anchorVisible: !anchor || inside(project(anchor, cameraBounds, output), inner),
  projectedGeometryBounds: projectedBounds,
  projectedHaloBounds: [projectedBounds[0] - padding, projectedBounds[1] - padding,
   projectedBounds[2] + padding, projectedBounds[3] + padding],
  projectedLengthPixels: projected.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - projected[i][0], p[1] - projected[i][1]), 0)};
}
function cameraAt(plan, frame) {
 if (plan.request.decision === 'USE_CURRENT_VIEW' || frame < plan.approachStartFrame) return [...plan.startBounds];
 if (frame >= plan.approachEndFrame - 1) return [...plan.targetBounds];
 return interpolateBounds(plan.startBounds, plan.targetBounds,
  (frame - plan.approachStartFrame) / (plan.timing.approachFrames - 1));
}

/** Certificate producer owns actual native visual inspection. This consumes its exact data binding. */
export function compileCameraDetailApproach({currentCamera, framingRequest, eventPlan, eventGeometry,
 output = [1080, 1920], safeArea, linePaddingPixels = 5.75, mode = 'PRODUCTION', timing = {}} = {}) {
 const event = assertEventPlan(eventPlan), geometry = copy(eventGeometry ?? event.intent.line?.geometry);
 if (geometry?.type !== 'LineString' || !same(geometry, event.intent.line?.geometry))
  throw Error('DETAIL_UNCHANGED_EVENT_GEOMETRY_REQUIRED');
 const geometryBinding = canonical(geometry), start = bounds(currentCamera?.flatBounds ?? currentCamera?.camera?.flatBounds ?? currentCamera?.bounds, 'CURRENT_CAMERA', true);
 const request = copy(framingRequest), out = outputPair(output), safe = bounds(safeArea, 'SAFE_AREA');
 if (!inside([safe[0], safe[1]], [0, 0, ...out]) || !inside([safe[2], safe[3]], [0, 0, ...out])
  || !Number.isFinite(linePaddingPixels) || linePaddingPixels <= 0
  || safe[2] - safe[0] <= linePaddingPixels * 2 || safe[3] - safe[1] <= linePaddingPixels * 2)
  throw Error('DETAIL_SAFE_AREA_HALO_REQUIRED');
 if (!['PRODUCTION', 'SYNTHETIC_TEST'].includes(mode)) throw Error('DETAIL_EXPLICIT_MODE_REQUIRED');
 if (request?.version !== 'EVENT_DETAIL_FRAMING_REQUEST_V1'
  || !['USE_CURRENT_VIEW', 'DETAIL_APPROACH_REQUIRED'].includes(request.decision))
  throw Error('DETAIL_ADMITTED_FRAMING_REQUEST_REQUIRED');
 const certificate = request.certificate, target = bounds(request.targetFraming?.bounds, 'TARGET_CAMERA', true);
 if (certificate?.version !== 'VISUAL_DETAIL_ADMISSION_V1' || certificate.status !== 'VISUAL_DETAIL_ADMITTED'
  || !same(certificate.bounds, target) || certificate.eventGeometryBinding !== geometryBinding
  || request.eventGeometryBinding !== geometryBinding || !same(certificate.output, out)
  || !same(certificate.safeArea, safe) || !same(request.targetFraming.output, out)
  || !same(request.targetFraming.safeArea, safe)) throw Error('DETAIL_VISUAL_CERTIFICATE_BINDING_REQUIRED');
 if (mode === 'PRODUCTION' && (certificate.productionEligible !== true || certificate.evidenceKind !== 'ACTUAL_NATIVE_RENDER'
  || event.intent.data_mode !== 'PRODUCTION')) throw Error('DETAIL_PRODUCTION_VISUAL_EVIDENCE_REQUIRED');
 if (mode === 'SYNTHETIC_TEST' && (certificate.productionEligible !== false || certificate.evidenceKind !== 'SYNTHETIC_TEST_ONLY'
  || event.intent.data_mode !== 'SYNTHETIC_TEST')) throw Error('DETAIL_EXPLICIT_SYNTHETIC_EVIDENCE_REQUIRED');
 if (request.decision === 'USE_CURRENT_VIEW' && !same(start, target)) throw Error('DETAIL_CURRENT_VIEW_MUST_NOT_MOVE');
 const a = spans(start), b = spans(target);
 if (Math.abs(a[0] / a[1] - b[0] / b[1]) > Math.abs(a[0] / a[1]) * 1e-10)
  throw Error('DETAIL_CAMERA_ASPECT_MUST_REMAIN_UNCHANGED');
 if (request.currentCameraState) {
  const supplied = request.currentCameraState.flatBounds ?? request.currentCameraState.camera?.flatBounds ?? request.currentCameraState.bounds;
  if (supplied && !same(supplied, start)) throw Error('DETAIL_REQUEST_CURRENT_CAMERA_BINDING_REQUIRED');
 }
 const approaching = request.decision === 'DETAIL_APPROACH_REQUIRED';
 const t = {arrivalFrames: integer(timing.arrivalFrames ?? 6, 'ARRIVAL_FRAMES', 2),
  approachFrames: approaching ? integer(timing.approachFrames ?? 42, 'APPROACH_FRAMES', 2) : 0,
  settleFrames: integer(timing.settleFrames ?? (approaching ? 12 : 0), 'SETTLE_FRAMES')};
 const approachStartFrame = t.arrivalFrames, approachEndFrame = approachStartFrame + t.approachFrames;
 const detailLockFrame = integer(approachEndFrame + t.settleFrames, 'LOCK_FRAME', 1);
 const totalFrames = integer(detailLockFrame + event.totalFrames, 'TOTAL_FRAMES', 1), timeline = [];
 function add(state, startFrame, endFrame) { if (endFrame > startFrame) timeline.push({state, startFrame, endFrame, durationFrames: endFrame - startFrame}); }
 add('EVENT_ARRIVAL', 0, t.arrivalFrames - 1); add('DETAIL_DECISION', t.arrivalFrames - 1, t.arrivalFrames);
 add('DETAIL_APPROACH', approachStartFrame, approachEndFrame); add('DETAIL_SETTLE', approachEndFrame, detailLockFrame);
 for (const beat of event.timeline) add(beat.state === 'EVENT_READY' ? 'DETAIL_LOCK' : beat.state,
  detailLockFrame + beat.startFrame, detailLockFrame + beat.endFrame);
 const plan = {version: CAMERA_DETAIL_APPROACH_ADAPTER_V1_VERSION, timelineVersion: EVENT_DETAIL_TIMELINE_V1_VERSION,
  mode, productionEligible: mode === 'PRODUCTION', request, eventPlan: event, eventGeometry: geometry, eventGeometryBinding: geometryBinding,
  startBounds: start, targetBounds: target, output: out, safeArea: safe, linePaddingPixels,
  timing: t, fps: event.fps, approachStartFrame, approachEndFrame, detailLockFrame, totalFrames,
  durationSeconds: totalFrames / event.fps, timeline,
  interpolation: {center: 'QUINTIC_SMOOTHERSTEP', spans: 'LOG_SPAN_QUINTIC_SMOOTHERSTEP',
   endpointVelocity: 0, endpointAcceleration: 0},
  ownership: {v5: 'READ_ONLY_FINAL_BASELINE', camera: 'POST_ARRIVAL_DETAIL_EXTENSION',
   eventTimeline: 'DELEGATE_EXISTING_V2_PLAN', geometry: 'UNCHANGED_SOURCE_VERTICES', surveyAdmission: 'PRESERVED_SEPARATE_RECORD'}};
 for (let frame = 0; frame < totalFrames; frame++) {
  const cameraBounds = bounds(cameraAt(plan, frame), 'MOTION_CAMERA', true);
  const safety = projectedSafety(geometry, cameraBounds, out, safe, linePaddingPixels, request.eventAnchor);
  if (!safety.wholeGeometryVisible || !safety.anchorVisible) throw Error(`DETAIL_MOTION_GEOMETRY_OR_HALO_CROP_FRAME_${frame}`);
 }
 freezeEventData(plan); knownPlans.add(plan); return plan;
}

export function assertCameraDetailApproachPlan(plan) {
 if (knownPlans.has(plan)) return plan;
 if (plan?.version !== CAMERA_DETAIL_APPROACH_ADAPTER_V1_VERSION) throw Error('DETAIL_ADAPTER_PLAN_VERSION_REQUIRED');
 const canonical = compileCameraDetailApproach({currentCamera: {flatBounds: plan.startBounds}, framingRequest: plan.request,
  eventPlan: plan.eventPlan, eventGeometry: plan.eventGeometry, output: plan.output, safeArea: plan.safeArea,
  linePaddingPixels: plan.linePaddingPixels, mode: plan.mode, timing: plan.timing});
 if (!same(canonical, plan)) throw Error('DETAIL_ADAPTER_PLAN_NON_CANONICAL');
 return canonical;
}

/** Stateless random-access frame; no Event controls are evaluated while Camera is moving. */
export function evaluateCameraDetailApproachFrame(plan, frame, {eventContext} = {}) {
 const p = assertCameraDetailApproachPlan(plan); integer(frame, 'FRAME');
 if (frame >= p.totalFrames) throw Error('DETAIL_FRAME_OUT_OF_RANGE');
 const flatBounds = cameraAt(p, frame), beat = p.timeline.find(item => frame >= item.startFrame && frame < item.endFrame);
 const cameraLocked = frame >= p.detailLockFrame, eventFrame = cameraLocked ? frame - p.detailLockFrame : null;
 const safety = projectedSafety(p.eventGeometry, flatBounds, p.output, p.safeArea, p.linePaddingPixels, p.request.eventAnchor);
 let controls = null;
 if (cameraLocked && eventContext) {
  if (!same(eventContext.cameraState?.camera?.flatBounds, flatBounds) || !same(eventContext.safeArea, p.safeArea))
   throw Error('DETAIL_LOCKED_EVENT_CONTEXT_BINDING_REQUIRED');
  // Existing readiness owns scale/LOCAL policy and native geographic projection.
  controls = evaluateEventFrame(p.eventPlan, eventFrame, eventContext);
 }
 return freezeEventData({version: CAMERA_DETAIL_APPROACH_ADAPTER_V1_VERSION, frame, timeSeconds: frame / p.fps,
  state: beat.state, stateFrame: frame - beat.startFrame,
  stateProgress: beat.durationFrames === 1 ? 1 : (frame - beat.startFrame) / (beat.durationFrames - 1),
  flatBounds, center: center(flatBounds), extent: spans(flatBounds), cameraLocked, settle: {locked: cameraLocked},
  eventEnabled: cameraLocked, eventFrame, scheduledEventState: cameraLocked ? p.eventPlan.timeline.find(item => eventFrame >= item.startFrame && eventFrame < item.endFrame).state : null,
  lineAllowed: cameraLocked, metricAllowed: cameraLocked, controls, safety,
  visualAdmission: p.request.certificate.status, surveyAdmission: p.request.certificate.surveyDetailStatus,
  productionEligible: p.productionEligible});
}

/** Numerical sampled evidence plus analytic endpoint derivatives; no rendering claim. */
export function assessCameraDetailMotion(plan) {
 const p = assertCameraDetailApproachPlan(plan), samples = Array.from({length: p.totalFrames}, (_, frame) => evaluateCameraDetailApproachFrame(p, frame));
 let maximumNormalizedCornerStep = 0, maximumLogSpanStep = 0, maximumCenterStepPixels = 0;
 for (let i = 1; i < samples.length; i++) {
  const previous = samples[i - 1], current = samples[i], s = spans(previous.flatBounds);
  maximumNormalizedCornerStep = Math.max(maximumNormalizedCornerStep,
   ...current.flatBounds.map((value, j) => Math.abs(value - previous.flatBounds[j]) / s[j % 2]));
  maximumLogSpanStep = Math.max(maximumLogSpanStep, ...current.extent.map((value, j) => Math.abs(Math.log(value / previous.extent[j]))));
  maximumCenterStepPixels = Math.max(maximumCenterStepPixels,
   Math.hypot((current.center[0] - previous.center[0]) / s[0] * p.output[0], (current.center[1] - previous.center[1]) / s[1] * p.output[1]));
 }
 const locked = samples.filter(sample => sample.cameraLocked);
 return freezeEventData({status: 'PASS', framesChecked: samples.length, continuousInterpolant: true,
  exactStart: same(samples[0].flatBounds, p.startBounds), exactTarget: locked.every(sample => same(sample.flatBounds, p.targetBounds)),
  endpointVelocity: 0, endpointAcceleration: 0, maximumNormalizedCornerStep, maximumLogSpanStep, maximumCenterStepPixels,
  wholeGeometryAndHaloSafeEveryFrame: samples.every(sample => sample.safety.wholeGeometryVisible && sample.safety.anchorVisible),
  noEventBeforeLock: samples.filter(sample => !sample.cameraLocked).every(sample => !sample.eventEnabled && sample.eventFrame === null && sample.controls === null),
  detailLockFrame: p.detailLockFrame, approachFrames: p.timing.approachFrames, settleFrames: p.timing.settleFrames,
  approachDurationSeconds: p.timing.approachFrames / p.fps, settleDurationSeconds: p.timing.settleFrames / p.fps,
  surveyAdmissionPreserved: true, v5SourceModificationRequired: false, geometryRegenerated: false});
}
