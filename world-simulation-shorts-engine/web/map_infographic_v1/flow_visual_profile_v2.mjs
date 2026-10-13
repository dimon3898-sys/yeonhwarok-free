/** Presentation-only Flow polish. Authored geography, camera and object motion remain external owners. */
import {freezeEventData} from './event_contract_v1.mjs';
import {assertFlowPlan, sampleFlowRoute} from './flow_core_v2.mjs';
import {assertGeographicLinePrimitive, evaluateGeographicLineReveal} from './event_line_v1.mjs';

export const FLOW_VISUAL_PROFILE_V2_VERSION = 'FLOW_VISUAL_PROFILE_V2';
export const FLOW_OBJECT_SCALE_CANDIDATES = Object.freeze([1, 1.12, 1.20, 1.28]);
const defaults = Object.freeze({profileName: 'TRANSPORT_MOBILE', roleGroup: 'TRANSPORT',
 objectScale: 1.12, routeLeadPixels: 55, directionalLeadBodyRatio: .78,
 arrivalRadiusScale: 1.18, arrivalPeakProgress: .22});
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const clamp = value => Math.max(0, Math.min(1, value));
const smootherstep = value => value * value * value * (value * (value * 6 - 15) + 10);
const smoothstep = value => value * value * (3 - 2 * value);
function record(value, label) {
 if (!value || typeof value !== 'object' || Array.isArray(value)
  || ![Object.prototype, null].includes(Object.getPrototypeOf(value)))
  throw Error(`FLOW_VISUAL_${label}_OBJECT_REQUIRED`);
 return value;
}
function within(value, minimum, maximum, label) {
 if (!Number.isFinite(value) || value < minimum || value > maximum)
  throw Error(`FLOW_VISUAL_${label}_RANGE_REQUIRED`);
}

/** Role groups and selected size are explicit fixture/profile data, never geography or object-name branches. */
export function compileFlowVisualProfile(input = {}) {
 const given = record(input, 'PROFILE');
 if (Object.keys(given).some(key => !Object.hasOwn(defaults, key))) throw Error('FLOW_VISUAL_UNKNOWN_PROFILE_FIELD');
 const options = {...defaults, ...given};
 if (typeof options.profileName !== 'string' || !/^[A-Z][A-Z0-9_]{1,63}$/u.test(options.profileName))
  throw Error('FLOW_VISUAL_PROFILE_NAME_REQUIRED');
 if (!['TRANSPORT', 'GENERIC'].includes(options.roleGroup)) throw Error('FLOW_VISUAL_ROLE_GROUP_REQUIRED');
 within(options.objectScale, 1, 1.35, 'OBJECT_SCALE');
 within(options.routeLeadPixels, 1, 96, 'ROUTE_LEAD');
 within(options.directionalLeadBodyRatio, .55, 1.25, 'DIRECTIONAL_LEAD');
 within(options.arrivalRadiusScale, 1, 1.35, 'ARRIVAL_RADIUS');
 within(options.arrivalPeakProgress, .1, .45, 'ARRIVAL_PEAK');
 return freezeEventData({version: FLOW_VISUAL_PROFILE_V2_VERSION, ...options});
}

export function assertFlowVisualProfile(profile) {
 if (profile?.version !== FLOW_VISUAL_PROFILE_V2_VERSION) throw Error('FLOW_VISUAL_PROFILE_VERSION_REQUIRED');
 const {version: _version, ...options} = profile;
 const canonical = compileFlowVisualProfile(options);
 if (!same(canonical, profile)) throw Error('FLOW_VISUAL_PROFILE_NON_CANONICAL');
 return canonical;
}

/** A once-only, faster onset with a quieter tail, within the unchanged arrival pulse window. */
function arrivalPresentation(pulse, size, profile) {
 const progress = pulse.progress, peak = profile.arrivalPeakProgress;
 const alpha = !pulse.active || progress === 0 || progress === 1 ? 0
  : progress <= peak ? smoothstep(progress / peak)
   : 1 - smoothstep((progress - peak) / (1 - peak));
 return {...structuredClone(pulse), amplitude: alpha, alpha,
  radius: size * (.18 + .5 * (1 - (1 - progress) ** 3)) * profile.arrivalRadiusScale};
}

/** Apply only render controls; never write a new route, timeline, heading or physical object position.
 * The existing V1 evaluator is the sole reveal engine. Its fraction now leads the moving object,
 * instead of making the entire route static during the first introduction beat.
 */
export function applyFlowVisualProfile({flowPlan, controls, primitive, profile} = {}) {
 const flow = assertFlowPlan(flowPlan), route = assertGeographicLinePrimitive(primitive);
 const visual = assertFlowVisualProfile(profile);
 record(controls, 'CONTROLS');
 if (controls.version !== flow.version || !Number.isSafeInteger(controls.frame)
  || controls.frame < flow.startFrame || controls.frame >= flow.endFrame
  || controls.localFrame !== controls.frame - flow.startFrame)
  throw Error('FLOW_VISUAL_CURRENT_FRAME_BINDING_REQUIRED');
 if (!same(route.intent, flow.routeEventPlan.intent)) throw Error('FLOW_VISUAL_CURRENT_ROUTE_BINDING_REQUIRED');
 within(controls.objectFraction, 0, 1, 'OBJECT_FRACTION');
 within(controls.headingLookAheadPixels, Number.EPSILON, Number.MAX_VALUE, 'HEADING_LOOKAHEAD');
 const sourceGraphic = flow.intent.object_graphic;
 const objectGraphic = {...structuredClone(sourceGraphic),
  width_px: sourceGraphic.width_px * visual.objectScale,
  height_px: sourceGraphic.height_px * visual.objectScale};
 // Preserve the established native overlay's finite-support size contract.
 within(objectGraphic.width_px, 24, 80, 'RENDERED_OBJECT_WIDTH');
 within(objectGraphic.height_px, 12, 80, 'RENDERED_OBJECT_HEIGHT');
 const leadingDistancePixels = Math.max(visual.routeLeadPixels, objectGraphic.width_px * .8);
 const leadingFraction = clamp(leadingDistancePixels / route.totalLengthPixels);
 const introduction = smootherstep(clamp((controls.localFrame - 1) / (flow.timing.object_start_frame - 1 || 1)));
 const routeFraction = controls.routeActive
  ? clamp(controls.objectFraction + leadingFraction * introduction) : 0;
 const directionalLeadPixels = objectGraphic.width_px * visual.directionalLeadBodyRatio;
 const directionalFraction = Math.min(routeFraction,
  controls.objectFraction + directionalLeadPixels / route.totalLengthPixels);
 const directional = sampleFlowRoute(route, directionalFraction,
  {lookAheadPixels: controls.headingLookAheadPixels});
 const arrivalPulse = arrivalPresentation(controls.arrivalPulse,
  Math.max(objectGraphic.width_px, objectGraphic.height_px), visual);
 const pulse = arrivalPulse.active ? arrivalPulse : structuredClone(controls.departurePulse);
 const renderedControls = {...structuredClone(controls), routeFraction,
  routeReveal: evaluateGeographicLineReveal(route, routeFraction),
  directionalFraction, directionalPosition: directional.position, directionalHeading: directional.heading,
  arrivalPulse, pulse};
 return freezeEventData({controls: renderedControls, objectGraphic,
  metadata: {version: FLOW_VISUAL_PROFILE_V2_VERSION, profileName: visual.profileName,
   roleGroup: visual.roleGroup, objectScale: visual.objectScale,
   beforeSize: [sourceGraphic.width_px, sourceGraphic.height_px],
   afterSize: [objectGraphic.width_px, objectGraphic.height_px], leadingDistancePixels,
   directionalLeadPixels, arrivalRadiusScale: visual.arrivalRadiusScale,
   arrivalPeakProgress: visual.arrivalPeakProgress,
   revealEngine: 'GEOGRAPHIC_LINE_REVEAL_V1', objectMotion: 'UNCHANGED_FLOW_CORE_V2',
   timeline: 'UNCHANGED_FLOW_PLAN_V2', cameraOwnership: 'READ_ONLY'}});
}
