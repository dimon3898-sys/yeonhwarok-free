/**
 * Deterministic Camera Director V1. This module compiles/evaluates a geographic
 * camera/reveal plan; it neither renders pixels nor changes a Scale/Scene.
 */
import { geometryBounds, fitGeographicExtent } from './scale_contract.mjs';

export const CAMERA_DIRECTOR_VERSION = 'CAMERA_DIRECTOR_V1';
export const CAMERA_STATES = Object.freeze(['CONTEXT', 'APPROACH', 'DECELERATE', 'SETTLE', 'LOCK', 'REVEAL', 'HOLD', 'NEXT']);
export const CAMERA_TARGET_INTENTS = Object.freeze(['REGION_SHAPE', 'RELATION', 'EVENT_LOCATION', 'SAFE_CLOSEST']);
export const CAMERA_PROFILE = Object.freeze({
 version: 'REFERENCE_MOTION_GRAMMAR_V1', fps: 30,
 worldContextSeconds: 1.8, projectionTransitionSeconds: 1.2,
 continentContextSeconds: .6, flatMotionSeconds: 3.7, decelerationFraction: .35,
 settleSeconds: .6, lockSeconds: .2,
 primaryRevealSeconds: .4, markerRevealSeconds: .4,
 locationRevealSeconds: .5, titleRevealSeconds: .7,
 minimumHoldSeconds: 3, readingGraphemesPerSecond: 6, nextSeconds: .2,
 easing: 'QUINTIC_SMOOTHSTEP', holdDrift: false,
});

const clone = value => structuredClone(value);
const finitePoint = p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const boundsOK = b => Array.isArray(b) && b.length === 4 && b.every(Number.isFinite)
 && b[0] < b[2] && b[1] < b[3] && b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;
const boundsCenter = b => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
const boundsSize = b => [b[2] - b[0], b[3] - b[1]];
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const union = a => [Math.min(...a.map(b => b[0])), Math.min(...a.map(b => b[1])),
 Math.max(...a.map(b => b[2])), Math.max(...a.map(b => b[3]))];
const contains = (a, b) => a[0] <= b[0] && a[1] <= b[1] && a[2] >= b[2] && a[3] >= b[3];
const freeze = value => {
 if (value && typeof value === 'object' && !Object.isFrozen(value)) {
  Object.values(value).forEach(freeze); Object.freeze(value);
 }
 return value;
};
const zeroVelocity = () => ({ longitudeDegreesPerSecond: 0, latitudeDegreesPerSecond: 0,
 logWidthPerSecond: 0, logHeightPerSecond: 0 });

/** C2 easing: zero velocity and acceleration at both endpoints. */
export function cameraEase(progress) {
 if (!Number.isFinite(progress)) throw Error('CAMERA_FINITE_EASING_PROGRESS_REQUIRED');
 const t = Math.max(0, Math.min(1, progress));
 return t * t * t * (10 + t * (-15 + 6 * t));
}
export function cameraEaseDerivative(progress) {
 if (!Number.isFinite(progress)) throw Error('CAMERA_FINITE_EASING_PROGRESS_REQUIRED');
 const t = Math.max(0, Math.min(1, progress));
 return 30 * t * t * (1 - t) * (1 - t);
}

function scaleSummary(plan, name) {
 if (plan?.scale?.name !== name || !boundsOK(plan.framing?.bounds)
  || !finitePoint(plan.anchor?.coordinates)) throw Error(`CAMERA_COMPILED_${name}_SCALE_REQUIRED`);
 if (!equal(plan.scale.canonicalOutput, [1080, 1920])) throw Error('CAMERA_CANONICAL_OUTPUT_REQUIRED');
 if ((name === 'WORLD') !== (plan.framing.projection === 'WORLD_GLOBE_ORTHOGRAPHIC'))
  throw Error('CAMERA_SCALE_PROJECTION_CONTRACT_MISMATCH');
 if (name !== 'WORLD' && plan.framing.projection !== 'REGIONAL_EQUIRECTANGULAR')
  throw Error('CAMERA_UNSUPPORTED_FLAT_PROJECTION');
 return { name, projection: plan.framing.projection, bounds: [...plan.framing.bounds],
  center: [...(plan.framing.center ?? boundsCenter(plan.framing.bounds))],
  globe: plan.framing.globe ? clone(plan.framing.globe) : null,
  geographicAnchor: [...plan.anchor.coordinates],
  scaleVersion: plan.scale.version, information: clone(plan.scale.information),
  sourceBinding: { renderer: plan.renderer, primary: plan.primary,
   geometries: (plan.geometries ?? []).map(g => ({ id: g.id, sha256: g.sha256 ?? g.source_feature_sha256 ?? null })),
   assets: Object.fromEntries(Object.entries(plan.assets ?? {}).map(([key, asset]) => [key, asset.sha256 ?? null])) } };
}

function targetFromGeometry(regional, target) {
 const intent = target.intent ?? 'SAFE_CLOSEST';
 if (!CAMERA_TARGET_INTENTS.includes(intent)) throw Error(`CAMERA_UNKNOWN_TARGET_INTENT: ${intent}`);
 const records = [...(regional.geometries ?? []), ...(target.eventGeometry ?? [])];
 const byID = new Map(records.map(g => [g.id, g]));
 let ids, extent, source;
 if (intent === 'REGION_SHAPE') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : [regional.primary];
  source = 'Verified region geometry extent';
 } else if (intent === 'RELATION') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : [regional.primary, ...(regional.secondary ?? [])];
  if (ids.length < 2) throw Error('CAMERA_RELATION_REQUIRES_TWO_GEOMETRIES');
  source = 'Verified relation geometry union';
 } else if (intent === 'EVENT_LOCATION') {
  ids = target.geometryIds?.length ? [...target.geometryIds] : (target.eventGeometry ?? []).map(g => g.id);
  source = ids.length ? 'Verified event geometry extent' : 'Verified Scene event anchor; Point does not imply an area';
 } else {
  ids = [];
  source = 'Data admission safe closest extent, preserving approved Regional framing';
 }
 if (ids.length) {
  const selected = ids.map(id => {
   const g = byID.get(id); if (!g) throw Error(`CAMERA_TARGET_GEOMETRY_MISSING: ${id}`); return g;
  });
  extent = union(selected.map(geometryBounds));
 } else if (intent === 'EVENT_LOCATION') {
  const [lon, lat] = regional.anchor.coordinates; extent = [lon, lat, lon, lat];
 } else extent = [...regional.framing.bounds];
 return { intent, geometryIds: ids, extent, source, eventAnchor: [...regional.anchor.coordinates],
  requestedScale: target.requestedScale ?? 'REGIONAL', fabricatedArea: false };
}

function framingAssessment(regional, target, measuredLayout) {
 const canonical = [1080, 1920], safe = [...(regional.layout.safe ?? [48, 72, 1032, 1848])];
 if (safe.length !== 4 || !safe.every(Number.isFinite) || safe[0] < 0 || safe[1] < 0
  || safe[2] > canonical[0] || safe[3] > canonical[1] || safe[0] >= safe[2] || safe[1] >= safe[3])
  throw Error('CAMERA_SAFE_AREA_CONTRACT_REQUIRED');
 const bounds = regional.framing.bounds, spans = boundsSize(bounds);
 const screen = ([lon, lat]) => [(lon - bounds[0]) / spans[0] * canonical[0],
  (bounds[3] - lat) / spans[1] * canonical[1]];
 const marker = screen(regional.anchor.coordinates), radius = regional.layout.measured.markerSize / 2;
 const markerBounds = [marker[0] - radius, marker[1] - radius, marker[0] + radius, marker[1] + radius];
 const items = Array.isArray(measuredLayout) ? measuredLayout : measuredLayout?.items ?? measuredLayout?.layout ?? [];
 const requiredLabels = items.filter(item => ['LOCATION_LABEL', 'COUNTRY', 'EVENT_TITLE'].includes(item.role))
  .map(item => ({ role: item.role, box: clone(item.inkBox ?? item.box) }));
 const inSafe = b => b[0] >= safe[0] && b[1] >= safe[1] && b[2] <= safe[2] && b[3] <= safe[3];
 const labelFit = requiredLabels.every(({ box: [x, y, w, h] }) => inSafe([x, y, x + w, y + h]));
 const markerFit = inSafe(markerBounds);
 const p0 = screen([target.extent[0], target.extent[3]]), p1 = screen([target.extent[2], target.extent[1]]);
 const geometryFit = target.intent === 'SAFE_CLOSEST' || inSafe([...p0, ...p1]);
 // Compute the target's closest geometric aspect fit using actual measured ink
 // and safe-area fractions. It is evidence, not permission to bypass admission.
 let candidateExtent = null;
 if (boundsOK(target.extent)) {
  const largestLabel = requiredLabels.reduce((v, i) => [Math.max(v[0], i.box[2]), Math.max(v[1], i.box[3])], [0, 0]);
  const margin = Math.max(radius, ...largestLabel.map(v => v / 2));
  const available = [safe[2] - safe[0] - margin * 2, safe[3] - safe[1] - margin * 2];
  if (available.every(v => v > 0)) {
   const padding = Math.max(canonical[0] / available[0], canonical[1] / available[1]);
   try { candidateExtent = fitGeographicExtent(target.extent, { output: canonical, padding }); }
   catch (error) { candidateExtent = null; }
  }
 }
 return { policy: 'APPROVED_REGIONAL_FIXED_STOP', safeArea: safe, canonicalOutput: canonical,
  geometricCandidateExtent: candidateExtent, measuredLabelCount: requiredLabels.length,
  measuredLabelEvidence: requiredLabels.length ? 'ACTUAL_INK_BOUNDS' : 'NOT_SUPPLIED; runtime measured Universal Layout remains authoritative',
  targetFitsApprovedSafeArea: geometryFit, markerFitsApprovedSafeArea: markerFit,
  labelsFitApprovedSafeArea: requiredLabels.length ? labelFit : null,
  chosenExtent: [...bounds], allowedCloserThanApproved: false,
  status: geometryFit && markerFit && labelFit ? 'TARGET_FITS_APPROVED_STOP' : 'TARGET_NOT_FIT_BY_APPROVED_STOP',
  warning: geometryFit ? null : 'This intent does not fit approved Regional safe area; do not claim a complete shape/relation framing.' };
}

function buildProfile(overrides) {
 const profile = { ...CAMERA_PROFILE, ...overrides };
 if (profile.fps !== 30 || profile.easing !== 'QUINTIC_SMOOTHSTEP' || profile.holdDrift !== false)
  throw Error('CAMERA_V1_FIXED_FRAME_PROFILE_REQUIRED');
 for (const key of ['worldContextSeconds', 'projectionTransitionSeconds', 'continentContextSeconds',
  'flatMotionSeconds', 'settleSeconds', 'lockSeconds', 'primaryRevealSeconds', 'markerRevealSeconds',
  'locationRevealSeconds', 'titleRevealSeconds', 'minimumHoldSeconds', 'readingGraphemesPerSecond', 'nextSeconds']) {
  if (!(Number.isFinite(profile[key]) && profile[key] > 0)) throw Error(`CAMERA_POSITIVE_PROFILE_VALUE_REQUIRED: ${key}`);
 }
 if (!(profile.decelerationFraction > 0 && profile.decelerationFraction < .5))
  throw Error('CAMERA_DECELERATION_FRACTION_REQUIRED');
 if (Math.round(profile.projectionTransitionSeconds * 30) < 2 || Math.round(profile.flatMotionSeconds * 30) < 4)
  throw Error('CAMERA_MOTION_REQUIRES_MULTIPLE_FRAMES');
 return profile;
}

/**
 * Inputs are approved compiled Scale plans, immutable actual GIS/Scene target
 * records and LocalDetailAdmission evidence. No coordinate/region special cases.
 */
export function compileCameraPlan({ world, continent, regional, localAdmission = null,
 target = { intent: 'SAFE_CLOSEST' }, measuredLayout = null, seed = 0, profile: overrides = {} } = {}) {
 const scales = { WORLD: scaleSummary(world, 'WORLD'), CONTINENT: scaleSummary(continent, 'CONTINENT'),
  REGIONAL: scaleSummary(regional, 'REGIONAL') };
 const anchor = scales.REGIONAL.geographicAnchor;
 if (!equal(scales.WORLD.geographicAnchor, anchor) || !equal(scales.CONTINENT.geographicAnchor, anchor))
  throw Error('CAMERA_SCALE_GEOGRAPHIC_ANCHOR_MISMATCH');
 if (!Number.isInteger(seed)) throw Error('CAMERA_INTEGER_SEED_REQUIRED');
 const local = localAdmission?.localDetail ?? localAdmission;
 const admission = local?.admission ?? local;
 const safeClosest = local?.safeClosest ?? null;
 if (safeClosest?.bounds && !equal(safeClosest.bounds, regional.framing.bounds))
  throw Error('CAMERA_SAFE_CLOSEST_MUST_MATCH_APPROVED_REGIONAL_STOP');
 const requestedTarget = targetFromGeometry(regional, target);
 if (!['WORLD', 'CONTINENT', 'REGIONAL', 'LOCAL'].includes(requestedTarget.requestedScale))
  throw Error('CAMERA_UNKNOWN_REQUESTED_SCALE');
 const profile = buildProfile(overrides), fps = profile.fps, frames = s => Math.max(1, Math.round(s * fps));
 const timeline = [], add = (state, key, count, extra = {}) => {
  const start = timeline.length ? timeline.at(-1).endFrame : 0;
  timeline.push({ state, key, startFrame: start, endFrame: start + count,
   durationFrames: count, startSeconds: start / fps, endSeconds: (start + count) / fps, ...extra });
  return timeline.at(-1);
 };
 add('CONTEXT', 'WORLD_CONTEXT', frames(profile.worldContextSeconds), { scale: 'WORLD', motion: 'FIXED' });
 const projection = add('APPROACH', 'WORLD_TO_CONTINENT', frames(profile.projectionTransitionSeconds),
  { scale: 'WORLD_TO_CONTINENT', motion: 'PROJECTION_DISSOLVE' });
 const continentContext = add('CONTEXT', 'CONTINENT_CONTEXT', frames(profile.continentContextSeconds), { scale: 'CONTINENT', motion: 'FIXED' });
 const motionCount = frames(profile.flatMotionSeconds), decelerationCount = Math.max(2, Math.round(motionCount * profile.decelerationFraction));
 const approach = add('APPROACH', 'CONTINENT_TO_REGIONAL_APPROACH', motionCount - decelerationCount,
  { scale: 'CONTINENT_TO_REGIONAL', motion: 'CENTER_AND_LOG_EXTENT' });
 const deceleration = add('DECELERATE', 'CONTINENT_TO_REGIONAL_DECELERATE', decelerationCount,
  { scale: 'CONTINENT_TO_REGIONAL', motion: 'CENTER_AND_LOG_EXTENT' });
 const settle = add('SETTLE', 'REGIONAL_SETTLE', frames(profile.settleSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const lock = add('LOCK', 'REGIONAL_LOCK', frames(profile.lockSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const revealStages = [], revealStart = timeline.at(-1).endFrame;
 let revealOffset = 0;
 for (const [role, seconds] of [['primary', profile.primaryRevealSeconds], ['marker', profile.markerRevealSeconds],
  ['location', profile.locationRevealSeconds], ['title', profile.titleRevealSeconds]]) {
  const count = frames(seconds);
  revealStages.push({ role, startFrame: revealStart + revealOffset, endFrame: revealStart + revealOffset + count, durationFrames: count });
  revealOffset += count;
 }
 const reveal = add('REVEAL', 'REGIONAL_INFORMATION_REVEAL', revealOffset, { scale: 'REGIONAL', motion: 'FIXED' });
 const readable = [regional.text?.eventTitle, regional.text?.locationLabel,
  ...(regional.layout.countryLabels ?? []).map(label => label.text)].filter(Boolean).join('');
 const graphemeCount = [...new Intl.Segmenter('ko', { granularity: 'grapheme' }).segment(readable)].length;
 const holdSeconds = Math.max(profile.minimumHoldSeconds, graphemeCount / profile.readingGraphemesPerSecond);
 const hold = add('HOLD', 'REGIONAL_READ_HOLD', frames(holdSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const next = add('NEXT', 'NEXT_READY', frames(profile.nextSeconds), { scale: 'REGIONAL', motion: 'FIXED' });
 const framing = framingAssessment(regional, requestedTarget, measuredLayout);
 if (!contains(scales.CONTINENT.bounds, scales.REGIONAL.bounds))
  throw Error('CAMERA_APPROACH_REQUIRES_REGIONAL_WITHIN_CONTINENT');
 // The final framing is unchanged even for a requested LOCAL: this V1 has no
 // LOCAL camera stage and cannot reinterpret a data denial as a rendering error.
 return freeze({ version: CAMERA_DIRECTOR_VERSION, kind: 'CAMERA_MOTION_PROOF', fps, seed,
  canonicalOutput: [1080, 1920], totalFrames: next.endFrame, durationSeconds: next.endFrame / fps,
  profile, scales, target: { ...requestedTarget, effectiveScale: 'REGIONAL', framing },
  anchor: [...anchor], timeline,
  motion: { startFrame: approach.startFrame, endFrame: deceleration.endFrame,
   from: 'CONTINENT', to: 'REGIONAL', easing: profile.easing, interpolation: 'LINEAR_GEOGRAPHIC_CENTER_AND_LOG_GEOGRAPHIC_EXTENT',
   noCloserThanApprovedStop: true, frameEndpointsExact: true },
  projectionTransition: { startFrame: projection.startFrame, endFrame: projection.endFrame,
   from: 'WORLD', to: 'CONTINENT', method: 'EXPLICIT_GPU_CROSS_DISSOLVE', easing: profile.easing,
   fromCameraFixed: true, toCameraFixed: true, morphClaimed: false, hardCut: false, blackFrame: false },
  reveal: { startFrame: reveal.startFrame, endFrame: reveal.endFrame, stages: revealStages,
   cameraDependency: 'AFTER_SETTLE_AND_LOCK', countryWithLocation: true,
   secondaryGeography: 'STATIC_CONTEXT', disclosure: regional.text?.watermark ? 'ALWAYS_VISIBLE_VERIFIED_SCENARIO_DISCLAIMER' : 'NOT_PRESENT',
   disclosurePresent: Boolean(regional.text?.watermark) },
  hold: { startFrame: hold.startFrame, endFrame: hold.endFrame, graphemeCount,
   readingGraphemesPerSecond: profile.readingGraphemesPerSecond, drift: false },
  admission: { status: admission?.status ?? regional.scale.admission.status,
   requestedScale: requestedTarget.requestedScale, effectiveScale: 'REGIONAL', localUsed: false,
   localRejected: admission?.status !== 'LOCAL_ADMITTED',
   safeClosestStatus: safeClosest?.status ?? 'APPROVED_REGIONAL_FIXED_STOP',
   closestExtentCertified: safeClosest?.closestExtentCertified ?? false,
   regionalStopBounds: [...scales.REGIONAL.bounds], diagnosticCategory: 'DATA_ADMISSION' },
  checkpoints: { WORLD: 0,
   CONTINENT: continentContext.startFrame + Math.floor(continentContext.durationFrames / 2),
   REGIONAL_SETTLE: settle.endFrame - 1, REVEAL: reveal.endFrame - 1,
   HOLD: hold.startFrame + Math.floor(hold.durationFrames / 2) },
  protections: { sceneGeometry: 'UNCHANGED', scaleContracts: 'UNCHANGED', terrainMaterial: 'UNCHANGED',
   theme: 'UNCHANGED', markerDesign: 'UNCHANGED', typography: 'UNCHANGED', universalLayout: 'UNCHANGED',
   layoutDuringMotion: 'HIDDEN; final measured Regional placements reused without relayout',
   eventState: 'UNCHANGED', audio: 'NONE', newLocalDetail: false },
  visualIterationLimit: 3 });
}

function interpolateFlat(plan, frame) {
 const motion = plan.motion, denominator = motion.endFrame - motion.startFrame - 1;
 const progress = Math.max(0, Math.min(1, (frame - motion.startFrame) / denominator));
 const eased = cameraEase(progress), from = plan.scales.CONTINENT.bounds, to = plan.scales.REGIONAL.bounds;
 if (progress === 0) return { bounds: [...from], center: boundsCenter(from), progress, eased, velocity: zeroVelocity() };
 if (progress === 1) return { bounds: [...to], center: boundsCenter(to), progress, eased, velocity: zeroVelocity() };
 const a = boundsCenter(from), b = boundsCenter(to), sizeA = boundsSize(from), sizeB = boundsSize(to);
 const center = a.map((v, i) => v + (b[i] - v) * eased);
 const size = sizeA.map((v, i) => Math.exp(Math.log(v) + (Math.log(sizeB[i]) - Math.log(v)) * eased));
 const derivative = cameraEaseDerivative(progress) * plan.fps / denominator;
 return { bounds: [center[0] - size[0] / 2, center[1] - size[1] / 2, center[0] + size[0] / 2, center[1] + size[1] / 2],
  center, progress, eased,
  velocity: { longitudeDegreesPerSecond: (b[0] - a[0]) * derivative,
   latitudeDegreesPerSecond: (b[1] - a[1]) * derivative,
   logWidthPerSecond: (Math.log(sizeB[0]) - Math.log(sizeA[0])) * derivative,
   logHeightPerSecond: (Math.log(sizeB[1]) - Math.log(sizeA[1])) * derivative } };
}

/** Pure integer-frame evaluation. No clock, randomness, accumulating motion or drift. */
export function evaluateCameraFrame(plan, frame) {
 if (plan?.version !== CAMERA_DIRECTOR_VERSION) throw Error('CAMERA_DIRECTOR_PLAN_VERSION_REQUIRED');
 if (!Number.isInteger(frame) || frame < 0 || frame >= plan.totalFrames) throw Error('CAMERA_FRAME_OUT_OF_RANGE');
 const segment = plan.timeline.find(s => frame >= s.startFrame && frame < s.endFrame);
 if (!segment) throw Error('CAMERA_FRAME_TIMELINE_GAP');
 const inTransition = frame >= plan.projectionTransition.startFrame && frame < plan.projectionTransition.endFrame;
 const transitionProgress = inTransition ? (frame - plan.projectionTransition.startFrame)
  / (plan.projectionTransition.endFrame - plan.projectionTransition.startFrame - 1)
  : frame >= plan.projectionTransition.endFrame ? 1 : 0;
 const world = frame < plan.projectionTransition.endFrame;
 const motionActive = frame >= plan.motion.startFrame && frame < plan.motion.endFrame;
 const regional = frame >= plan.motion.endFrame;
 const pose = motionActive ? interpolateFlat(plan, frame) : {
  bounds: [...plan.scales[regional ? 'REGIONAL' : 'CONTINENT'].bounds],
  center: [...plan.scales[regional ? 'REGIONAL' : 'CONTINENT'].center],
  progress: regional ? 1 : 0, eased: regional ? 1 : 0, velocity: zeroVelocity() };
 const revealed = { primary: 0, marker: 0, location: 0, country: 0, title: 0, disclosure: Number(plan.reveal.disclosurePresent) };
 for (const stage of plan.reveal.stages) {
  const progress = (frame - stage.startFrame) / Math.max(1, stage.durationFrames - 1);
  revealed[stage.role] = cameraEase(progress);
 }
 revealed.country = revealed.location;
 const lock = plan.timeline.find(s => s.state === 'LOCK');
 const center = world ? [...plan.scales.WORLD.center] : pose.center;
 const extent = world ? [...plan.scales.WORLD.bounds] : pose.bounds;
 return {
  version: CAMERA_DIRECTOR_VERSION, frame, timeSeconds: frame / plan.fps,
  state: segment.state, stateKey: segment.key, stateFrame: frame - segment.startFrame,
  stateProgress: (frame - segment.startFrame) / Math.max(1, segment.durationFrames - 1),
  scale: world ? 'WORLD' : regional ? 'REGIONAL' : 'CONTINENT',
  projection: world ? plan.scales.WORLD.projection : plan.scales.REGIONAL.projection,
  target: plan.target.intent, targetGeometryIds: [...plan.target.geometryIds],
  center, extent, geographicCenter: [...center], geographicExtent: [...extent],
  velocity: pose.velocity, easingProgress: pose.eased, motionProgress: pose.progress,
  settle: { phase: segment.state, settled: frame >= lock.startFrame, locked: frame >= lock.startFrame },
  reveal: revealed,
  transition: { active: inTransition, from: 'WORLD', to: 'CONTINENT',
   mix: cameraEase(transitionProgress), easing: plan.profile.easing, method: plan.projectionTransition.method },
  camera: { flatBounds: [...pose.bounds], worldCenter: [...plan.scales.WORLD.center],
   worldDiameterFraction: plan.scales.WORLD.globe.diameterFraction, noCloserThanApprovedStop: true },
  admission: clone(plan.admission), geographicAnchor: [...plan.anchor],
  layoutLocked: regional, cameraLocked: frame >= plan.motion.endFrame,
 };
}
