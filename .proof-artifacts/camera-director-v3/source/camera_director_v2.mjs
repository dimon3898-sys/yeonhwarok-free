/**
 * Camera Director V2: one geographic flat-map camera trajectory. This pure
 * compiler/evaluator owns camera and reveal timing, not pixels, LOD or style.
 */
import { geometryBounds, fitGeographicExtent } from './scale_contract.mjs';
import { CAMERA_PROFILE as V1_PROFILE, CAMERA_TARGET_INTENTS,
 cameraEase, cameraEaseDerivative } from './camera_director.mjs';

export { cameraEase, cameraEaseDerivative };
export const CONTINUOUS_CAMERA_DIRECTOR_VERSION = 'CAMERA_DIRECTOR_V2';
export const CONTINUOUS_CAMERA_STATES = Object.freeze([
 'CONTEXT', 'ACCELERATE', 'TRAVEL', 'DECELERATE', 'SETTLE', 'LOCK', 'REVEAL', 'HOLD', 'NEXT',
]);
export const CONTINUOUS_CAMERA_PROFILE = Object.freeze({
 version: 'CONTINUOUS_CONTINENT_MOTION_GRAMMAR_V2', fps: 30,
 wideContextSeconds: 1.5, flatMotionSeconds: 5.3,
 accelerationFraction: .30, decelerationFraction: .35,
 settleSeconds: V1_PROFILE.settleSeconds, lockSeconds: V1_PROFILE.lockSeconds,
 primaryRevealSeconds: V1_PROFILE.primaryRevealSeconds,
 markerRevealSeconds: V1_PROFILE.markerRevealSeconds,
 locationRevealSeconds: V1_PROFILE.locationRevealSeconds,
 titleRevealSeconds: V1_PROFILE.titleRevealSeconds,
 minimumHoldSeconds: V1_PROFILE.minimumHoldSeconds,
 readingGraphemesPerSecond: V1_PROFILE.readingGraphemesPerSecond,
 nextSeconds: V1_PROFILE.nextSeconds,
 easing: V1_PROFILE.easing, holdDrift: false,
});

const clone = value => structuredClone(value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const boundsOK = b => Array.isArray(b) && b.length === 4 && b.every(Number.isFinite)
 && b[0] < b[2] && b[1] < b[3] && b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;
const pointOK = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const centerOf = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
const sizeOf = b => [b[2] - b[0], b[3] - b[1]];
const contains = (a, b) => a[0] <= b[0] && a[1] <= b[1] && a[2] >= b[2] && a[3] >= b[3];
const union = a => [Math.min(...a.map(b => b[0])), Math.min(...a.map(b => b[1])),
 Math.max(...a.map(b => b[2])), Math.max(...a.map(b => b[3]))];
const freeze = value => {
 if (value && typeof value === 'object' && !Object.isFrozen(value)) {
  Object.values(value).forEach(freeze); Object.freeze(value);
 }
 return value;
};
const zeroVelocity = () => ({ longitudeDegreesPerSecond: 0, latitudeDegreesPerSecond: 0,
 logWidthPerSecond: 0, logHeightPerSecond: 0 });

function scaleSummary(plan, name) {
 if (plan?.scale?.name !== name || !boundsOK(plan.framing?.bounds)
  || !pointOK(plan.anchor?.coordinates)) throw Error(`CONTINUOUS_CAMERA_COMPILED_${name}_SCALE_REQUIRED`);
 if (!equal(plan.scale.canonicalOutput, [1080, 1920])) throw Error('CONTINUOUS_CAMERA_CANONICAL_OUTPUT_REQUIRED');
 if (plan.framing.projection !== 'REGIONAL_EQUIRECTANGULAR')
  throw Error('CONTINUOUS_CAMERA_FLAT_PROJECTION_REQUIRED');
 return { name, projection: plan.framing.projection, bounds: [...plan.framing.bounds],
  center: [...(plan.framing.center ?? centerOf(plan.framing.bounds))],
  geographicAnchor: [...plan.anchor.coordinates], scaleVersion: plan.scale.version,
  information: clone(plan.scale.information),
  sourceBinding: { renderer: plan.renderer, primary: plan.primary,
   geometries: (plan.geometries ?? []).map(g => ({ id: g.id, sha256: g.sha256 ?? g.source_feature_sha256 ?? null })),
   assets: Object.fromEntries(Object.entries(plan.assets ?? {}).map(([key, asset]) => [key, asset.sha256 ?? null])) } };
}

function targetFromGeometry(regional, target) {
 const intent = target.intent ?? 'SAFE_CLOSEST';
 if (!CAMERA_TARGET_INTENTS.includes(intent)) throw Error(`CONTINUOUS_CAMERA_UNKNOWN_TARGET_INTENT: ${intent}`);
 const records = [...(regional.geometries ?? []), ...(target.eventGeometry ?? [])];
 const byID = new Map(records.map(g => [g.id, g]));
 let ids, extent, source;
 if (intent === 'REGION_SHAPE') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : [regional.primary];
  source = 'Verified region geometry extent';
 } else if (intent === 'RELATION') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : [regional.primary, ...(regional.secondary ?? [])];
  if (ids.length < 2) throw Error('CONTINUOUS_CAMERA_RELATION_REQUIRES_TWO_GEOMETRIES');
  source = 'Verified relation geometry union';
 } else if (intent === 'EVENT_LOCATION') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : (target.eventGeometry ?? []).map(g => g.id);
  source = ids.length ? 'Verified event geometry extent' : 'Verified Scene event anchor; Point does not imply an area';
 } else {
  ids = [];
  source = 'Data admission safe closest extent, preserving approved Regional framing';
 }
 if (ids.length) extent = union(ids.map(id => {
  const geometry = byID.get(id);
  if (!geometry) throw Error(`CONTINUOUS_CAMERA_TARGET_GEOMETRY_MISSING: ${id}`);
  return geometryBounds(geometry);
 }));
 else if (intent === 'EVENT_LOCATION') {
  const [lon, lat] = regional.anchor.coordinates; extent = [lon, lat, lon, lat];
 } else extent = [...regional.framing.bounds];
 return { intent, geometryIds: ids, extent, source, eventAnchor: [...regional.anchor.coordinates],
  requestedScale: target.requestedScale ?? 'REGIONAL', fabricatedArea: false };
}

function framingAssessment(regional, target, measuredLayout) {
 const canonical = [1080, 1920], safe = [...(regional.layout.safe ?? [48, 72, 1032, 1848])];
 if (safe.length !== 4 || !safe.every(Number.isFinite) || safe[0] < 0 || safe[1] < 0
  || safe[2] > canonical[0] || safe[3] > canonical[1] || safe[0] >= safe[2] || safe[1] >= safe[3])
  throw Error('CONTINUOUS_CAMERA_SAFE_AREA_CONTRACT_REQUIRED');
 const bounds = regional.framing.bounds, size = sizeOf(bounds);
 const screen = ([lon, lat]) => [(lon - bounds[0]) / size[0] * canonical[0],
  (bounds[3] - lat) / size[1] * canonical[1]];
 const radius = regional.layout.measured.markerSize / 2;
 if (!(Number.isFinite(radius) && radius > 0)) throw Error('CONTINUOUS_CAMERA_MEASURED_MARKER_REQUIRED');
 const marker = screen(regional.anchor.coordinates);
 const markerBox = [marker[0] - radius, marker[1] - radius, marker[0] + radius, marker[1] + radius];
 const items = Array.isArray(measuredLayout) ? measuredLayout : measuredLayout?.items ?? measuredLayout?.layout ?? [];
 const labels = items.filter(item => ['LOCATION_LABEL', 'COUNTRY', 'EVENT_TITLE'].includes(item.role))
  .map(item => ({ role: item.role, box: clone(item.inkBox ?? item.box) }));
 if (labels.some(item => !Array.isArray(item.box) || item.box.length !== 4 || !item.box.every(Number.isFinite)))
  throw Error('CONTINUOUS_CAMERA_VALID_MEASURED_INK_BOUNDS_REQUIRED');
 const inSafe = b => b[0] >= safe[0] && b[1] >= safe[1] && b[2] <= safe[2] && b[3] <= safe[3];
 const markerFits = inSafe(markerBox);
 const labelsFit = labels.every(({ box: [x, y, width, height] }) => inSafe([x, y, x + width, y + height]));
 const a = screen([target.extent[0], target.extent[3]]), b = screen([target.extent[2], target.extent[1]]);
 const targetFits = target.intent === 'SAFE_CLOSEST' || inSafe([...a, ...b]);
 let candidateExtent = null;
 if (boundsOK(target.extent)) {
  const largestLabel = labels.reduce((v, item) => [Math.max(v[0], item.box[2]), Math.max(v[1], item.box[3])], [0, 0]);
  const margin = Math.max(radius, ...largestLabel.map(v => v / 2));
  const available = [safe[2] - safe[0] - margin * 2, safe[3] - safe[1] - margin * 2];
  if (available.every(v => v > 0)) {
   try { candidateExtent = fitGeographicExtent(target.extent, { output: canonical,
    padding: Math.max(canonical[0] / available[0], canonical[1] / available[1]) }); }
   catch (error) { candidateExtent = null; }
  }
 }
 return { policy: 'APPROVED_REGIONAL_FIXED_STOP', safeArea: safe, canonicalOutput: canonical,
  geometricCandidateExtent: candidateExtent, measuredLabelCount: labels.length,
  measuredLabelEvidence: labels.length ? 'ACTUAL_INK_BOUNDS' : 'NOT_SUPPLIED; runtime measured Universal Layout remains authoritative',
  targetFitsApprovedSafeArea: targetFits, markerFitsApprovedSafeArea: markerFits,
  labelsFitApprovedSafeArea: labels.length ? labelsFit : null,
  chosenExtent: [...bounds], allowedCloserThanApproved: false,
  status: targetFits && markerFits && labelsFit ? 'TARGET_FITS_APPROVED_STOP' : 'TARGET_NOT_FIT_BY_APPROVED_STOP',
  warning: targetFits ? null : 'Requested target does not fit approved Regional safe area; no closer framing is authorized.' };
}

function buildProfile(overrides) {
 const allowed = new Set(['wideContextSeconds', 'flatMotionSeconds', 'accelerationFraction', 'decelerationFraction', 'settleSeconds']);
 for (const [key, value] of Object.entries(overrides)) {
  if (!(key in CONTINUOUS_CAMERA_PROFILE)) throw Error(`CONTINUOUS_CAMERA_UNKNOWN_PROFILE_FIELD: ${key}`);
  if (!allowed.has(key) && value !== CONTINUOUS_CAMERA_PROFILE[key])
   throw Error(`CONTINUOUS_CAMERA_V1_TAIL_PROFILE_IS_PROTECTED: ${key}`);
 }
 const profile = { ...CONTINUOUS_CAMERA_PROFILE, ...overrides };
 for (const key of ['wideContextSeconds', 'flatMotionSeconds', 'settleSeconds']) {
  if (!(Number.isFinite(profile[key]) && profile[key] > 0)) throw Error(`CONTINUOUS_CAMERA_POSITIVE_PROFILE_REQUIRED: ${key}`);
 }
 if (!(profile.accelerationFraction > 0 && profile.accelerationFraction < .5
  && profile.decelerationFraction > 0 && profile.decelerationFraction < .5
  && profile.accelerationFraction + profile.decelerationFraction < 1))
  throw Error('CONTINUOUS_CAMERA_MOTION_PHASE_FRACTIONS_REQUIRED');
 if (Math.round(profile.flatMotionSeconds * profile.fps) < 8)
  throw Error('CONTINUOUS_CAMERA_MOTION_REQUIRES_MULTIPLE_FRAMES');
 return profile;
}

/**
 * Context is supplied geographic data, normally an approved CONTINENT plan.
 * An explicit contextExtent is aspect-fitted by the shared geographic contract.
 * The end extent always remains the exact approved Regional stop.
 */
export function compileContinuousCameraPlan({ continent, regional, contextExtent = null,
 localAdmission = null, target = { intent: 'SAFE_CLOSEST' }, measuredLayout = null,
 seed = 0, profile: overrides = {} } = {}) {
 const scales = { CONTINENT: scaleSummary(continent, 'CONTINENT'), REGIONAL: scaleSummary(regional, 'REGIONAL') };
 if (!equal(scales.CONTINENT.geographicAnchor, scales.REGIONAL.geographicAnchor))
  throw Error('CONTINUOUS_CAMERA_SCALE_ANCHOR_MISMATCH');
 if (scales.CONTINENT.sourceBinding.primary !== scales.REGIONAL.sourceBinding.primary)
  throw Error('CONTINUOUS_CAMERA_PRIMARY_REGION_MISMATCH');
 if (!Number.isInteger(seed)) throw Error('CONTINUOUS_CAMERA_INTEGER_SEED_REQUIRED');
 if (contextExtent !== null && !boundsOK(contextExtent)) throw Error('CONTINUOUS_CAMERA_CONTEXT_EXTENT_REQUIRED');
 const startBounds = contextExtent === null ? [...scales.CONTINENT.bounds]
  : fitGeographicExtent(contextExtent, { output: [1080, 1920], padding: 1 });
 if (!boundsOK(startBounds) || !contains(startBounds, scales.REGIONAL.bounds))
  throw Error('CONTINUOUS_CAMERA_CONTEXT_MUST_CONTAIN_APPROVED_REGIONAL');
 const startSize = sizeOf(startBounds), endSize = sizeOf(scales.REGIONAL.bounds);
 if (!(startSize[0] > endSize[0] && startSize[1] > endSize[1]))
  throw Error('CONTINUOUS_CAMERA_WIDE_CONTEXT_MUST_BE_LARGER_THAN_REGIONAL');
 const local = localAdmission?.localDetail ?? localAdmission;
 const localResult = local?.admission ?? local;
 const safeClosest = local?.safeClosest ?? null;
 if (safeClosest?.bounds && !equal(safeClosest.bounds, regional.framing.bounds))
  throw Error('CONTINUOUS_CAMERA_SAFE_CLOSEST_MUST_MATCH_APPROVED_REGIONAL_STOP');
 const requestedTarget = targetFromGeometry(regional, target);
 if (!['WORLD', 'CONTINENT', 'REGIONAL', 'LOCAL'].includes(requestedTarget.requestedScale))
  throw Error('CONTINUOUS_CAMERA_UNKNOWN_REQUESTED_SCALE');
 const profile = buildProfile(overrides), fps = profile.fps;
 const frames = seconds => Math.max(1, Math.round(seconds * fps));
 const timeline = [], add = (state, key, count, extra = {}) => {
  const start = timeline.length ? timeline.at(-1).endFrame : 0;
  timeline.push({ state, key, startFrame: start, endFrame: start + count,
   durationFrames: count, startSeconds: start / fps, endSeconds: (start + count) / fps, ...extra });
  return timeline.at(-1);
 };
 const context = add('CONTEXT', 'WIDE_CONTEXT', frames(profile.wideContextSeconds), { scale: 'CONTINENT', motion: 'FIXED' });
 const motionCount = frames(profile.flatMotionSeconds);
 const accelerationCount = Math.max(2, Math.round(motionCount * profile.accelerationFraction));
 const decelerationCount = Math.max(2, Math.round(motionCount * profile.decelerationFraction));
 const travelCount = motionCount - accelerationCount - decelerationCount;
 if (travelCount < 2) throw Error('CONTINUOUS_CAMERA_TRAVEL_PHASE_REQUIRED');
 const accelerate = add('ACCELERATE', 'CONTINUOUS_ACCELERATE', accelerationCount,
  { scale: 'CONTINENT_TO_REGIONAL', motion: 'CENTER_AND_LOG_EXTENT' });
 add('TRAVEL', 'CONTINUOUS_TRAVEL', travelCount, { scale: 'CONTINENT_TO_REGIONAL', motion: 'CENTER_AND_LOG_EXTENT' });
 const decelerate = add('DECELERATE', 'CONTINUOUS_DECELERATE', decelerationCount,
  { scale: 'CONTINENT_TO_REGIONAL', motion: 'CENTER_AND_LOG_EXTENT' });
 const settle = add('SETTLE', 'REGIONAL_SETTLE', frames(profile.settleSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const lock = add('LOCK', 'REGIONAL_LOCK', frames(profile.lockSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const revealStages = [], revealStart = timeline.at(-1).endFrame;
 let revealOffset = 0;
 for (const [role, seconds] of [['primary', profile.primaryRevealSeconds], ['marker', profile.markerRevealSeconds],
  ['location', profile.locationRevealSeconds], ['title', profile.titleRevealSeconds]]) {
  const count = frames(seconds);
  revealStages.push({ role, startFrame: revealStart + revealOffset,
   endFrame: revealStart + revealOffset + count, durationFrames: count });
  revealOffset += count;
 }
 const reveal = add('REVEAL', 'REGIONAL_INFORMATION_REVEAL', revealOffset, { scale: 'REGIONAL', motion: 'FIXED' });
 const readable = [regional.text?.eventTitle, regional.text?.locationLabel,
  ...(regional.layout.countryLabels ?? []).map(label => label.text)].filter(Boolean).join('');
 const graphemeCount = [...new Intl.Segmenter('ko', { granularity: 'grapheme' }).segment(readable)].length;
 const hold = add('HOLD', 'REGIONAL_READ_HOLD', frames(Math.max(profile.minimumHoldSeconds,
  graphemeCount / profile.readingGraphemesPerSecond)), { scale: 'REGIONAL', motion: 'FIXED' });
 const next = add('NEXT', 'NEXT_READY', frames(profile.nextSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const framing = framingAssessment(regional, requestedTarget, measuredLayout);
 const arrivalFrame = decelerate.endFrame - 1;
 return freeze({ version: CONTINUOUS_CAMERA_DIRECTOR_VERSION, kind: 'CONTINUOUS_CAMERA_MOTION_PROOF',
  fps, seed, canonicalOutput: [1080, 1920], totalFrames: next.endFrame, durationSeconds: next.endFrame / fps,
  profile, scales, anchor: [...scales.REGIONAL.geographicAnchor], target: { ...requestedTarget,
   effectiveScale: 'REGIONAL', framing }, timeline,
  context: { requestedExtent: [...(contextExtent ?? scales.CONTINENT.bounds)], framedExtent: [...startBounds],
   extentBasis: contextExtent === null ? 'APPROVED_GEOGRAPHIC_CONTINENT_EXTENT' : 'INPUT_GEOGRAPHIC_CONTEXT_ASPECT_FIT',
   wideHoldStartFrame: context.startFrame, wideHoldEndFrame: context.endFrame },
  motion: { startFrame: accelerate.startFrame, endFrame: decelerate.endFrame, arrivalFrame,
   startBounds: [...startBounds], endBounds: [...scales.REGIONAL.bounds],
   from: 'CONTINENT', to: 'REGIONAL', easing: profile.easing,
   interpolation: 'LINEAR_GEOGRAPHIC_CENTER_AND_LOG_GEOGRAPHIC_EXTENT',
   singleTrajectory: true, phaseCurveResets: false, noCloserThanApprovedStop: true, frameEndpointsExact: true },
  projection: { name: 'REGIONAL_EQUIRECTANGULAR', policy: 'ONE_CONTINUOUS_FLAT_MAP_SPACE', changeCount: 0 },
  projectionTransition: null,
  reveal: { startFrame: reveal.startFrame, endFrame: reveal.endFrame, stages: revealStages,
   cameraDependency: 'AFTER_SETTLE_AND_LOCK', countryWithLocation: true,
   secondaryGeography: 'STATIC_CONTEXT', disclosure: regional.text?.watermark ? 'ALWAYS_VISIBLE_VERIFIED_SCENARIO_DISCLAIMER' : 'NOT_PRESENT',
   disclosurePresent: Boolean(regional.text?.watermark), v1RelativeTimingPreserved: true },
  hold: { startFrame: hold.startFrame, endFrame: hold.endFrame, graphemeCount,
   readingGraphemesPerSecond: profile.readingGraphemesPerSecond, drift: false },
  admission: { status: localResult?.status ?? regional.scale.admission.status,
   requestedScale: requestedTarget.requestedScale, effectiveScale: 'REGIONAL', localUsed: false,
   localRejected: localResult?.status !== 'LOCAL_ADMITTED',
   safeClosestStatus: safeClosest?.status ?? 'APPROVED_REGIONAL_FIXED_STOP',
   closestExtentCertified: safeClosest?.closestExtentCertified ?? false,
   regionalStopBounds: [...scales.REGIONAL.bounds], diagnosticCategory: 'DATA_ADMISSION' },
  checkpoints: { WIDE_START: 0, APPROACH: accelerate.endFrame + Math.floor(travelCount / 2),
   DECELERATE: decelerate.startFrame + Math.floor(decelerate.durationFrames / 2),
   REGIONAL_LOCK: lock.endFrame - 1, FINAL_HOLD: hold.startFrame + Math.floor(hold.durationFrames / 2) },
  protections: { sceneGeometry: 'UNCHANGED', scaleContracts: 'UNCHANGED', terrainMaterial: 'UNCHANGED',
   theme: 'UNCHANGED', markerDesign: 'UNCHANGED', typography: 'UNCHANGED', universalLayout: 'UNCHANGED',
   layoutDuringMotion: 'HIDDEN; final measured Regional placements reused without relayout',
   eventState: 'UNCHANGED', audio: 'NONE', newLocalDetail: false, v1RevealHold: 'PRESERVED' },
  visualIterationLimit: 3 });
}

function interpolateFlat(plan, frame) {
 const motion = plan.motion, denominator = motion.endFrame - motion.startFrame - 1;
 const progress = Math.max(0, Math.min(1, (frame - motion.startFrame) / denominator));
 const eased = cameraEase(progress), from = motion.startBounds, to = motion.endBounds;
 if (progress === 0) return { bounds: [...from], center: centerOf(from), progress, eased, velocity: zeroVelocity() };
 if (progress === 1) return { bounds: [...to], center: centerOf(to), progress, eased, velocity: zeroVelocity() };
 const a = centerOf(from), b = centerOf(to), sizeA = sizeOf(from), sizeB = sizeOf(to);
 const center = a.map((value, i) => value + (b[i] - value) * eased);
 const size = sizeA.map((value, i) => Math.exp(Math.log(value) + (Math.log(sizeB[i]) - Math.log(value)) * eased));
 const derivative = cameraEaseDerivative(progress) * plan.fps / denominator;
 return { bounds: [center[0] - size[0] / 2, center[1] - size[1] / 2,
  center[0] + size[0] / 2, center[1] + size[1] / 2], center, progress, eased,
  velocity: { longitudeDegreesPerSecond: (b[0] - a[0]) * derivative,
   latitudeDegreesPerSecond: (b[1] - a[1]) * derivative,
   logWidthPerSecond: (Math.log(sizeB[0]) - Math.log(sizeA[0])) * derivative,
   logHeightPerSecond: (Math.log(sizeB[1]) - Math.log(sizeA[1])) * derivative } };
}

/** Integer-frame evaluation; no accumulated motion, random jitter or clock. */
export function evaluateContinuousCameraFrame(plan, frame) {
 if (plan?.version !== CONTINUOUS_CAMERA_DIRECTOR_VERSION) throw Error('CONTINUOUS_CAMERA_PLAN_VERSION_REQUIRED');
 if (!Number.isInteger(frame) || frame < 0 || frame >= plan.totalFrames) throw Error('CONTINUOUS_CAMERA_FRAME_OUT_OF_RANGE');
 const segment = plan.timeline.find(item => frame >= item.startFrame && frame < item.endFrame);
 if (!segment) throw Error('CONTINUOUS_CAMERA_FRAME_TIMELINE_GAP');
 const pose = interpolateFlat(plan, frame), regional = frame >= plan.motion.endFrame;
 const revealed = { primary: 0, marker: 0, location: 0, country: 0, title: 0,
  disclosure: Number(plan.reveal.disclosurePresent) };
 for (const stage of plan.reveal.stages) {
  const progress = (frame - stage.startFrame) / Math.max(1, stage.durationFrames - 1);
  revealed[stage.role] = cameraEase(progress);
 }
 revealed.country = revealed.location;
 const lock = plan.timeline.find(item => item.state === 'LOCK');
 return { version: CONTINUOUS_CAMERA_DIRECTOR_VERSION, frame, timeSeconds: frame / plan.fps,
  state: segment.state, stateKey: segment.key, stateFrame: frame - segment.startFrame,
  stateProgress: (frame - segment.startFrame) / Math.max(1, segment.durationFrames - 1),
  scale: regional ? 'REGIONAL' : 'CONTINENT', projection: plan.projection.name,
  target: plan.target.intent, targetGeometryIds: [...plan.target.geometryIds],
  center: [...pose.center], extent: [...pose.bounds], geographicCenter: [...pose.center], geographicExtent: [...pose.bounds],
  velocity: pose.velocity, easingProgress: pose.eased, motionProgress: pose.progress,
  settle: { phase: segment.state, settled: frame >= lock.startFrame, locked: frame >= lock.startFrame },
  reveal: revealed, transition: { active: false, method: 'NONE', mix: 0 },
  camera: { flatBounds: [...pose.bounds], noCloserThanApprovedStop: true },
  admission: clone(plan.admission), geographicAnchor: [...plan.anchor],
  layoutLocked: regional, cameraLocked: frame >= plan.motion.endFrame };
}
