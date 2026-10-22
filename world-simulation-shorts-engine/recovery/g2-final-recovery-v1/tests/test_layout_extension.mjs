import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildMeasuredGraphicLayout as oldLayout } from '../../../web/map_infographic_v1/graphic_layout.mjs';
import { buildMeasuredGraphicLayout, auditRuntimeLayout, validateLocationPlacementPolicy } from '../layout_extension.mjs';

const fixture = JSON.parse(readFileSync(new URL('../fixtures/LAYOUT_FAILURE_CASES.json', import.meta.url)));
const policy = { schema: 'WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1', mode: 'BOUNDED_GAP_SEARCH', maxGap: 216, step: 16 };
const clone = v => structuredClone(v);
const casePlan = id => clone(fixture.cases.find(row => row.caseId === id).plan);
const project = bounds => p => [(p[0] - bounds[0]) / (bounds[2] - bounds[0]) * 1080, (bounds[3] - p[1]) / (bounds[3] - bounds[1]) * 1920];
// These dimensions are the actual pinned-font export, not a browser draw.
const measure = (text, style) => {
 const item = fixture.actualGlyphExports.find(row => row.text === text && row.fontSize === style.fontSize && row.fontFamily === style.fontFamily);
 if (!item) throw Error('RECORDED_GLYPH_NOT_AVAILABLE');
 return clone(item);
};
const input = plan => ({ plan, screen: project(plan.framing.bounds), measure });
let count = 0;
const test = (name, fn) => { fn(); count++; console.log('PASS ' + name); };

test('absent opt-in is exactly the unchanged legacy Nepal failure', () => {
 const plan = casePlan('nepal_himalaya');
 const old = oldLayout(input(plan)), now = buildMeasuredGraphicLayout(input(plan));
 assert.deepEqual(now, old);
 assert.equal(now.validation.valid, false);
 assert.equal(now.validation.failures[0].code, 'NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT');
 assert.deepEqual(now.validation.anchor, [486, 1020]);
 assert.deepEqual(now.validation.placementAttempts[0].candidates.map(c => c.inkBox), [
  [353, 1006.5, 95, 27], [524, 1006.5, 95, 27], [438.5, 955, 95, 27], [438.5, 1058, 95, 27]]);
});

test('opt-in resolves Nepal using the unchanged guards and glyphs', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy);
 const result = buildMeasuredGraphicLayout(input(plan));
 assert.equal(result.validation.valid, true);
 assert.equal(result.validation.locationRecovery.status, 'SAFE_GAP_SELECTED');
 assert.ok(result.validation.locationRecovery.selectedGap > plan.layout.measured.location.gap);
 assert.ok(result.validation.locationRecovery.selectedGap <= policy.maxGap);
 const label = result.items.find(row => row.role === 'LOCATION_LABEL');
 assert.deepEqual(label.metrics.inkDimensions, [95, 27]); assert.equal(label.metrics.fontSize, 36);
 assert.deepEqual(label.placement.geographicAnchor, [84, 28]);
 assert.equal(plan.scale.information.location, true);
 assert.deepEqual(result.validation.collisions, []); assert.deepEqual(result.validation.boundaryCollisions, []);
 assert.deepEqual(result.validation.safeArea.violations, []);
});

test('already valid Namibia preserves every original item and validation field', () => {
 const plan = casePlan('namibia_desert_coast'); const old = oldLayout(input(plan));
 plan.layout.locationPlacement = clone(policy);
 const result = buildMeasuredGraphicLayout(input(plan));
 const { locationRecovery, ...guards } = result.validation;
 assert.deepEqual(result.items, old.items); assert.deepEqual(guards, old.validation);
 assert.equal(locationRecovery.status, 'DEFAULT_PRESERVED'); assert.equal(locationRecovery.selectedGap, 18);
 assert.equal(locationRecovery.attempts.length, 1);
});

test('policy adaptation is deterministic and never mutates input', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy);
 const before = JSON.stringify(plan); const first = buildMeasuredGraphicLayout(input(plan));
 assert.deepEqual(buildMeasuredGraphicLayout(input(plan)), first); assert.equal(JSON.stringify(plan), before);
});

test('unknown policy fields invalid bounds fractional step or inactive role reject', () => {
 for (const mutate of [p => p.extra = true, p => p.maxGap = 217, p => p.step = 3, p => p.step = 4.5,
  p => p.schema = 'unknown', p => p.mode = 'skip', p => p.maxGap = 17]) {
  const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy); mutate(plan.layout.locationPlacement);
  assert.throws(() => validateLocationPlacementPolicy(plan), /LOCATION_PLACEMENT_POLICY_INVALID/);
 }
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy); plan.scale.information.location = false;
 assert.throws(() => validateLocationPlacementPolicy(plan), /LOCATION_PLACEMENT_POLICY_INVALID/);
});

test('an exhausted explicit search remains an invalid layout', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = { ...policy, maxGap: 18 };
 const result = buildMeasuredGraphicLayout(input(plan));
 assert.equal(result.validation.valid, false); assert.equal(result.validation.locationRecovery.status, 'BOUNDED_SEARCH_EXHAUSTED');
 assert.equal(result.validation.locationRecovery.selectedGap, null); assert.equal(result.validation.locationRecovery.attempts.length, 1);
});

test('impossible safe area is not bypassed', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy); plan.layout.safe = [482, 1016, 490, 1024];
 const result = buildMeasuredGraphicLayout(input(plan));
 assert.equal(result.validation.valid, false); assert.ok(result.validation.safeArea.violations.length);
});

test('unrelated measured glyph failures remain failures without gap retries', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy);
 const badMeasure = (text, style) => ({ ...measure(text, style), fits: false });
 const result = buildMeasuredGraphicLayout({ ...input(plan), measure: badMeasure });
 assert.equal(result.validation.valid, false); assert.equal(result.validation.locationRecovery.status, 'UNRELATED_FAILURE_PRESERVED');
 assert.equal(result.validation.locationRecovery.attempts.length, 1);
 assert.ok(result.validation.failures.some(row => row.code === 'TEXT_EXCEEDS_MEASURED_BOUNDS'));
});

test('unexpected glyph exceptions propagate unchanged', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy);
 assert.throws(() => buildMeasuredGraphicLayout({ ...input(plan), measure: () => { throw Error('ACTUAL_FONT_FAILURE'); } }), /ACTUAL_FONT_FAILURE/);
});

test('dynamic diagnostic requires an actual prior callback and does not claim rendering', () => {
 const plan = casePlan('nepal_himalaya'); plan.layout.locationPlacement = clone(policy);
 assert.throws(() => auditRuntimeLayout({ plan, screen: project(plan.framing.bounds) }), /ACTUAL_FACTORY_LAYOUT_MEASURE_REQUIRED/);
 buildMeasuredGraphicLayout(input(plan));
 const result = auditRuntimeLayout({ plan, screen: project([70, 6, 100, 52]) });
 assert.equal(result.validation.valid, true); assert.equal(result.diagnosticOnly, true);
 assert.equal(result.visibleLabelRenderingClaimed, false);
 assert.equal(result.measurement, 'SAME_FACTORY_GLYPH_MEASURE_CALLBACK');
});

test('country ids and geometry names cannot select an exception branch', () => {
 const a = casePlan('nepal_himalaya'); a.layout.locationPlacement = clone(policy);
 const b = clone(a); b.primary = 'ARBITRARY_SOURCE_POLYGON'; b.geometries[0].id = b.primary;
 const aa = buildMeasuredGraphicLayout(input(a)), bb = buildMeasuredGraphicLayout(input(b));
 assert.deepEqual(aa.items, bb.items); assert.equal(aa.validation.valid, bb.validation.valid);
 assert.equal(aa.validation.locationRecovery.selectedGap, bb.validation.locationRecovery.selectedGap);
});

console.log(JSON.stringify({ status: 'PASS', tests: count, skipped: 0, backend: 'CPU_RECORDED_METRICS_NOT_GPU' }));
