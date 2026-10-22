/** Opt-in input adaptation; all placement and collision decisions stay legacy. */
const legacy = await import(typeof window === 'undefined'
 ? new URL('../../web/map_infographic_v1/graphic_layout.mjs', import.meta.url).href
 : './graphic_layout_legacy.mjs');

export const GRAPHIC_LAYOUT_VERSION = legacy.GRAPHIC_LAYOUT_VERSION;
export const UNIVERSAL_LAYOUT_VERSION = legacy.UNIVERSAL_LAYOUT_VERSION;
export const LOCATION_PLACEMENT_POLICY_SCHEMA = 'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1';
const keys = ['schema', 'mode', 'maxGap', 'step'];
const clone = value => structuredClone(value);
const admittedMeasures = new WeakMap();

export function validateLocationPlacementPolicy(plan) {
 const policy = plan?.layout?.locationPlacement;
 if (policy === undefined) return null;
 const canonical = plan.layout.canonical ?? [1080, 1920];
 const baseGap = plan.layout.measured?.location?.gap;
 if (!policy || typeof policy !== 'object' || Array.isArray(policy)
  || Object.keys(policy).length !== keys.length || Object.keys(policy).some(key => !keys.includes(key))
  || policy.schema !== LOCATION_PLACEMENT_POLICY_SCHEMA || policy.mode !== 'BOUNDED_GAP_SEARCH'
  || !Array.isArray(canonical) || canonical.length !== 2 || canonical.some(v => !Number.isFinite(v) || v <= 0)
  || !Number.isFinite(baseGap) || baseGap < 0 || !Number.isFinite(policy.maxGap)
  || policy.maxGap < baseGap || policy.maxGap > Math.min(...canonical) * .2
  || !Number.isSafeInteger(policy.step) || policy.step < 4 || policy.step > 32
  || plan.scale?.information?.location === false) {
  throw Error('LOCATION_PLACEMENT_POLICY_INVALID');
 }
 return { ...policy };
}

function summary(result, gap) {
 return { gap, valid: result.validation.valid,
  failures: clone(result.validation.failures),
  boundaryCollisions: clone(result.validation.boundaryCollisions),
  safeAreaViolations: clone(result.validation.safeArea.violations),
  collisions: clone(result.validation.collisions),
  locationCandidates: clone(result.validation.placementAttempts.find(row => row.role === 'LOCATION_LABEL')?.candidates ?? []) };
}

function recorded(result, { baseGap, selectedGap, attempts, status }) {
 // Extra evidence is opt-in only. No existing validation, item or source field
 // is overwritten; absence of the policy returns the exact legacy object.
 return { ...result, validation: { ...result.validation, locationRecovery: {
  schema: 'WORLD_ENGINE_LOCATION_PLACEMENT_AUDIT_V1', status, baseGap, selectedGap,
  attempts, originalGuardUsed: true, originalGlyphSizePreserved: true,
  geographicAnchorMoved: false, locationRoleDisabled: false,
  minimumPrimaryBoundaryClearancePixels: 8,
  defaultFirst: true, sourceOrNationSpecificBranch: false } } };
}

export function buildMeasuredGraphicLayout(input) {
 const { plan } = input;
 const policy = validateLocationPlacementPolicy(plan);
 const first = legacy.buildMeasuredGraphicLayout(input);
 if (!policy) return first;
 if (!admittedMeasures.has(plan)) admittedMeasures.set(plan, input.measure);
 const baseGap = plan.layout.measured.location.gap;
 const attempts = [summary(first, baseGap)];
 if (first.validation.valid) return recorded(first, { baseGap, selectedGap: baseGap, attempts, status: 'DEFAULT_PRESERVED' });
 const failures = first.validation.failures;
 // This adapter addresses only the confirmed exhausted location candidates.
 // Unrelated validation failures and all thrown exceptions remain failures.
 if (!failures.length || failures.some(f => f.role !== 'LOCATION_LABEL' || f.code !== 'NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT')) {
  return recorded(first, { baseGap, selectedGap: null, attempts, status: 'UNRELATED_FAILURE_PRESERVED' });
 }
 const gaps = [];
 for (let gap = baseGap + policy.step; gap <= policy.maxGap; gap += policy.step) gaps.push(gap);
 if (policy.maxGap > baseGap && gaps.at(-1) !== policy.maxGap) gaps.push(policy.maxGap);
 let last = first;
 for (const gap of gaps) {
  const nextPlan = { ...plan, layout: { ...plan.layout, measured: { ...plan.layout.measured,
   location: { ...plan.layout.measured.location, gap } } } };
  const result = legacy.buildMeasuredGraphicLayout({ ...input, plan: nextPlan });
  attempts.push(summary(result, gap));
  last = result;
  if (result.validation.valid) return recorded(result, { baseGap, selectedGap: gap, attempts, status: 'SAFE_GAP_SELECTED' });
 }
 return recorded(last, { baseGap, selectedGap: null, attempts, status: 'BOUNDED_SEARCH_EXHAUSTED' });
}

/** A diagnostic check through the same caller's real glyph callback and current
 * native projection. It is not a new rendering pass or proof a hidden label drew.
 */
export function auditRuntimeLayout({ plan, screen }) {
 const measure = admittedMeasures.get(plan);
 if (!measure || typeof screen !== 'function') throw Error('ACTUAL_FACTORY_LAYOUT_MEASURE_REQUIRED');
 const result = buildMeasuredGraphicLayout({ plan, screen, measure });
 return { schema: 'WORLD_ENGINE_DYNAMIC_LAYOUT_AUDIT_V1',
  measurement: 'SAME_FACTORY_GLYPH_MEASURE_CALLBACK', projection: 'CALLER_CURRENT_FACTORY_SCREEN',
  diagnosticOnly: true, visibleLabelRenderingClaimed: false,
  validation: result.validation,
  items: result.items.map(item => ({ kind: item.kind, role: item.role,
   box: item.box, ...(item.inkBox ? { inkBox: item.inkBox } : {}),
   ...(item.placement ? { placement: item.placement } : {}),
   ...(item.metrics ? { fontSize: item.metrics.fontSize, inkDimensions: item.metrics.inkDimensions } : {}) })) };
}
