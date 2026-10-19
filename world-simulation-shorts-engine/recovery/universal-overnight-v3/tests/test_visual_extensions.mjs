/** Synthetic source-bound CPU oracles + instrumented consumers. No GPU/render. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {normalizeVisualExtensionsRequest, compileVisualExtensions, evaluateVisualExtensionsFrame,
 createVisualExtensionsPass, visualSourceSHA, VISUAL_UNCONNECTED_CONTRACTS} from '../visual_extensions.mjs';
import {compileTerritoryControlPlan, classifyControlPoint, evaluateTerritoryControlFrame}
 from '../../../web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {evaluateControlFrontierLightMotion} from '../../../web/map_infographic_v1/reference_control_frontier_light_v3.mjs';
const empty = () => ({schema: 'WORLD_ENGINE_OVERNIGHT_VISUAL_V1', scalarTerritory: null, nationalUnits: null});
const rect = (id, west, east) => ({id, geometry: {type: 'Polygon', coordinates: [
 [[west, -2], [east, -2], [east, 2], [west, 2], [west, -2]] ]}});
const plan = () => compileTerritoryControlPlan({semantic_mode: 'REFERENCE_VISUAL_STUDY',
 source: {source_type: 'SYNTHETIC_TEST_ONLY', source_reference: 'AUTHORED_GENERIC_SOUTHWEST_FIXTURE', verification_status: 'SYNTHETIC_TEST'},
 domain: [rect('CALLER_A', -4, -2), rect('CALLER_B', -2, 0)],
 factions: {winner: {id: 'GENERIC_WINNER'}, loser: {id: 'GENERIC_LOSER'}},
 longitudinal_knots: [-4, -2, 0], base_boundary_latitudes: [-1, -1, -1],
 boundary_keyframes: [{frame: 0, latitudes: [-1, -1, -1]}, {frame: 24, latitudes: [.8, 1, .8]},
  {frame: 59, latitudes: [.8, 1, .8]}], advance_direction: 'POSITIVE_LATITUDE',
 start_frame: 0, total_frames: 60, fps: 30, interpolation: 'SMOOTHERSTEP'});
const style = () => ({profileName: 'AUTHORED_STYLE', losingColor: [.4, .1, .7, .7],
 existingWinningColor: [.7, .1, .1, .7], gainedWinningColor: [.7, .1, .1, .72]});
const light = () => ({profileName: 'ORIGINAL_LIGHT', centerColor: [1, .985, .94], haloColor: [1, .7, .25],
 centerWidthPixels: 2.5, haloSigmaPixels: 3.5, haloSupportPixels: 10, centerAlpha: 1, haloAlpha: .35,
 settledStrength: .08, velocityWindowFrames: 6, luminanceAnchor: .36, minimumLightingFactor: .83, reliefLightingEnabled: true});
async function scalarFixture({frontier = null, outer = false} = {}) {
 const actual = plan(), payload = {schema: 'WORLD_ENGINE_SCALAR_CONTROL_SOURCE_V1', plan: actual,
  territoryStyle: style(), frontierStyle: light(), nativeDomain: outer ? {primary: 'CALLER_A', secondary: ['CALLER_B'],
   geometries: actual.intent.domain.map(row => ({id: row.id, geometry_type: row.geometry.type, coordinates: row.geometry.coordinates}))} : null},
  record = {sourceId: 'synthetic-scalar', sha256: await visualSourceSHA(payload), role: 'SCALAR_CONTROL_PLAN',
   verificationStatus: 'SYNTHETIC_TEST', payload}, request = empty();
 request.scalarTerritory = {sourceId: record.sourceId, sha256: record.sha256,
  gain: {enabled: true, gainBrightness: 1.12, gainedAlpha: .84}, frontier};
 return {request, record, binding: await compileVisualExtensions({request, trustedSources: [record], fps: 30, totalFrames: 60, allowSynthetic: true})};
}
const context = () => ({project: point => [(point[0] + 4) / 4 * 1080, (2 - point[1]) / 4 * 1920],
 safeArea: [0, 0, 1080, 1920], protectedGraphics: [], boundarySegments: [], internalBoundarySegments: [],
 parentGeographicFrontPresent: false, parentTerritoryFillPresent: false, nativeBoundarySourceVerified: true,
 presentationScale: 1});
function spies() {
 const calls = [];
 const owner = name => options => { calls.push({name: name + ':create', options}); return {
  draw: args => { calls.push({name: name + ':draw', args}); return {name, cpuOnly: true}; },
  dispose: () => calls.push({name: name + ':dispose'})}; };
 return {calls, consumers: {territory: owner('territory'), frontier: owner('frontier'), outer: owner('outer'), national: owner('national')}};
}
test('strict request exposes only implemented opt-ins and rejects unsupported roll/detail/unchecked metadata', () => {
 assert.deepEqual(normalizeVisualExtensionsRequest(empty()), empty());
 for (const key of ['cameraRoll', 'detailApproach', 'terrainShader', 'allowSynthetic', 'sourcePayload'])
  assert.throws(() => normalizeVisualExtensionsRequest({...empty(), [key]: true}), /FIELDS_UNSUPPORTED/);
 for (const value of [null, [], {}, {...empty(), schema: 'V4'}]) assert.throws(() => normalizeVisualExtensionsRequest(value));
});
test('absent optional modules compile without sources or GPU allocation', async () => {
 const binding = await compileVisualExtensions({request: empty(), fps: 30, totalFrames: 2400}), pass = await createVisualExtensionsPass({binding});
 assert.equal(binding.scalar, null); assert.equal(binding.national, null);
 assert.equal(pass.evidence.emptySelection, true); assert.equal(pass.drawFrame(120).gpuOutputVerified, false);
 assert.throws(() => pass.drawFrame(2400), /OUT_OF_RANGE/); pass.dispose();
 assert.throws(() => pass.drawFrame(120), /DISPOSED/);
});
test('actual existing scalar compiler and material preserve source domain, control keys and opposing classifier', async () => {
 const {binding, record} = await scalarFixture(), before = JSON.stringify(record.payload);
 for (const frame of [0, 12, 24, 59]) {
  const actual = evaluateVisualExtensionsFrame(binding, frame, context());
  assert.deepEqual(actual.scalar.controls, evaluateTerritoryControlFrame(record.payload.plan, frame));
  assert.deepEqual(classifyControlPoint(actual.scalar.controls, [-3, 0]), classifyControlPoint(record.payload.plan, [-3, 0], {frame}));
 }
 assert.deepEqual(binding.scalar.plan.domainGeometryBinding, record.payload.plan.domainGeometryBinding);
 assert.equal(binding.scalar.territoryStyle.gainedWinningColor[3], .84);
 assert.deepEqual(binding.scalar.territoryStyle.losingColor, record.payload.territoryStyle.losingColor);
 assert.equal(JSON.stringify(record.payload), before); assert.equal(binding.enemyComplementInferred, false);
});
test('source-byte mutation, role substitution, missing source and duplicate catalog IDs reject', async () => {
 const {request, record} = await scalarFixture();
 const compile = trustedSources => compileVisualExtensions({request, trustedSources, fps: 30, totalFrames: 60, allowSynthetic: true});
 await assert.rejects(compile([]), /VERIFIED_SOURCE_REQUIRED/);
 await assert.rejects(compile([{...record, role: 'GEOMETRY'}]), /VERIFIED_SOURCE_REQUIRED/);
 const tamper = structuredClone(record); tamper.payload.plan.intent.boundary_keyframes[1].latitudes[0] += .1;
 await assert.rejects(compile([tamper]), /VERIFIED_SOURCE_REQUIRED/);
 await assert.rejects(compile([record, record]), /CATALOG_INVALID/);
});
test('synthetic sources cannot enter production and verified label cannot turn study data into historical control', async () => {
 const {request, record} = await scalarFixture();
 await assert.rejects(compileVisualExtensions({request, trustedSources: [record], fps: 30, totalFrames: 60}), /SYNTHETIC_NOT_PRODUCTION/);
 await assert.rejects(compileVisualExtensions({request, trustedSources: [{...record, verificationStatus: 'VERIFIED'}], fps: 30, totalFrames: 60}), /SEMANTIC_BINDING_REQUIRED/);
});
test('canonical scalar plans reject hidden ignored fields and time mismatch', async () => {
 const {request, record} = await scalarFixture(), bad = structuredClone(record); bad.payload.plan.hiddenIgnoredOption = true;
 bad.sha256 = await visualSourceSHA(bad.payload); const changed = structuredClone(request); changed.scalarTerritory.sha256 = bad.sha256;
 await assert.rejects(compileVisualExtensions({request: changed, trustedSources: [bad], fps: 30, totalFrames: 60, allowSynthetic: true}), /CANONICAL_PLAN_REQUIRED/);
 await assert.rejects(compileVisualExtensions({request, trustedSources: [record], fps: 30, totalFrames: 59, allowSynthetic: true}), /CLOCK_BINDING_REQUIRED/);
});
test('existing frontier motion/stop evaluator follows the same ownership boundary and settles after actual stop', async () => {
 const {binding} = await scalarFixture({frontier: {enabled: true, outerGoldIntensity: 0}}), motion = binding.scalar.motion;
 for (const frame of [0, 10, 24, 40, 59]) assert.deepEqual(evaluateVisualExtensionsFrame(binding, frame, context()).scalar.motion,
  evaluateControlFrontierLightMotion(motion, frame));
 assert.ok(motion.strengths[10] > motion.strengths[50]); assert.equal(motion.strengths[59], .08);
 assert.equal(binding.scalar.effectiveFrontier.centerWidthPixels, 2.5);
 assert.deepEqual(binding.scalar.effectiveFrontier.centerColor, [1, 1, 1]);
});
test('instrumented consumers receive original controls and protected/native context in strict fill-front order', async () => {
 const {binding} = await scalarFixture({frontier: {enabled: true, outerGoldIntensity: 0}}), cpu = spies(),
  pass = await createVisualExtensionsPass({binding, consumers: cpu.consumers, testOnlyCPU: true}), ctx = context();
 ctx.actualTerrainSnapshot = {frame: 10, source: 'ACTUAL_CURRENT_NATIVE_TERRAIN', texture: {cpuInstrumentOnly: true}};
 ctx.protectedGraphics = [{kind: 'TEXT', box: [5, 5, 40, 40]}];
 const result = pass.drawFrame(10, ctx), draws = cpu.calls.filter(row => row.name.endsWith(':draw'));
 assert.deepEqual(draws.map(row => row.name), ['territory:draw', 'frontier:draw']);
 assert.deepEqual(draws[0].args.controls, evaluateTerritoryControlFrame(binding.scalar.plan, 10));
 assert.equal(draws[1].args.actualTerrainTexture, ctx.actualTerrainSnapshot.texture);
 assert.equal(draws[0].args.protectedGraphics, ctx.protectedGraphics); assert.equal(result.gpuOutputVerified, false);
 assert.equal(pass.evidence.cpuInstrumentation, true); pass.dispose();
 assert.throws(() => pass.drawFrame(10, ctx), /DISPOSED/);
});
test('existing parent fill/front or stale terrain causes zero downstream draw calls', async () => {
 const {binding} = await scalarFixture({frontier: {enabled: true, outerGoldIntensity: 0}}), cpu = spies(),
  pass = await createVisualExtensionsPass({binding, consumers: cpu.consumers, testOnlyCPU: true});
 for (const patch of [{parentGeographicFrontPresent: true}, {parentTerritoryFillPresent: true},
  {nativeBoundarySourceVerified: false}, {presentationScale: 0.9}, {presentationScale: 2.01},
  {actualTerrainSnapshot: {frame: 9, source: 'ACTUAL_CURRENT_NATIVE_TERRAIN', texture: {}}}])
  assert.throws(() => pass.drawFrame(10, {...context(), ...patch}));
 assert.equal(cpu.calls.filter(row => row.name.endsWith(':draw')).length, 0); pass.dispose();
});
test('consumer injection requires explicit CPU instrumentation and compiled binding cannot be spoofed', async () => {
 const {binding} = await scalarFixture(), cpu = spies();
 await assert.rejects(createVisualExtensionsPass({binding, consumers: cpu.consumers}), /TEST_CONSUMERS_FORBIDDEN/);
 await assert.rejects(createVisualExtensionsPass({binding: structuredClone(binding), consumers: cpu.consumers, testOnlyCPU: true}), /COMPILED_BINDING_REQUIRED/);
 await assert.rejects(createVisualExtensionsPass({binding}), /BROWSER_NATIVE_CANVAS_REQUIRED/);
});
test('outer glow requires exact original native roles and same-frame native coverage, never inferred RGB', async () => {
 await assert.rejects(scalarFixture({frontier: {enabled: true}}), /ACTUAL_NATIVE_ROLE_DOMAIN_REQUIRED/);
 const {binding} = await scalarFixture({frontier: {enabled: true}, outer: true}), cpu = spies(), canvas = {},
  pass = await createVisualExtensionsPass({canvas, binding, consumers: cpu.consumers, testOnlyCPU: true}), ctx = context();
 ctx.actualTerrainSnapshot = {frame: 10, source: 'ACTUAL_CURRENT_NATIVE_TERRAIN', texture: {cpuOnly: true}};
 assert.throws(() => pass.drawFrame(10, ctx), /SAME_FRAME_NATIVE_ROLE_COVERAGE_REQUIRED/);
 assert.equal(cpu.calls.filter(row => row.name.endsWith(':draw')).length, 0);
 const bytes = new Uint8Array(1080 * 1920 * 4);
 for (let i = 0; i < bytes.length; i += 4) {bytes[i] = 255; bytes[i + 1] = 127; bytes[i + 2] = 128;}
 ctx.nativeRoleCoverage = {frame: 10, width: 1080, height: 1920, bounds: [-4, -2, 0, 2], coverage: bytes};
 const before = bytes.slice(), result = pass.drawFrame(10, ctx);
 assert.deepEqual(cpu.calls.filter(row => row.name.endsWith(':draw')).map(row => row.name), ['territory:draw', 'frontier:draw', 'outer:draw']);
 assert.equal(result.consumerResults.outer.cpuOnly, true); assert.deepEqual(bytes, before); pass.dispose();
});
async function nationalFixture() {
 const engine = new URL('../../../', import.meta.url), payload = JSON.parse(await readFile(new URL('recovery/universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json', engine))),
  base = JSON.parse(await readFile(new URL(payload.nativeFiles.cameraPlan.path, engine))), frames = 60,
  profile = {id: 'CALLER_FLAG', country_id: 'CALLER_COUNTRY', artwork: 'WORLD_ENGINE_ORIGINAL_ROUNDED_TABLET',
   aspect_ratio: 1.5, default_role: 'SUPPORT', flag_geometry: [{type: 'rect', x: 0, y: 0, width: 1.5, height: 1, fill: '#125599'}]},
  unit = {id: 'SOURCE_UNIT', profile_id: 'CALLER_FLAG', role: 'SUPPORT', anchor_frames: Array.from({length: frames}, () => [-70, -30]),
   size_frames: Array(frames).fill(80), rotation_frames: Array(frames).fill(0)},
  source = {schema: 'WORLD_ENGINE_NATIONAL_UNIT_SCENE_SOURCE_V1', baseCameraPlan: base, currentNativeFrame: 0,
   safeArea: [48, 72, 1032, 1848], scenePlan: {controlIntent: {total_frames: frames, fps: 30},
    cameraKeyframes: [{frame: 0, bounds: [-80, -40, -60, -20], rotationDegrees: 0}, {frame: 59, bounds: [-80, -40, -60, -20], rotationDegrees: 0}],
    presentationProfile: {overscan: 1}, combatProfile: {units: [unit], profiles: {CALLER_FLAG: profile}}}},
  record = {sourceId: 'synthetic-unit', sha256: await visualSourceSHA(source), role: 'NATIONAL_UNIT_SCENE', verificationStatus: 'SYNTHETIC_TEST', payload: source}, request = empty();
 request.nationalUnits = {sourceId: record.sourceId, sha256: record.sha256, markerScale: 1.14};
 return {record, request, binding: await compileVisualExtensions({request, trustedSources: [record], fps: 30, totalFrames: frames, allowSynthetic: true})};
}
test('actual national all-frame static scale owner preserves original anchors, roles, flags and camera', async () => {
 const {binding, record} = await nationalFixture(), original = record.payload.scenePlan.combatProfile.units[0], actual = binding.national.units[0];
 assert.equal(binding.national.scaleAudit.effective.framesChecked, 60); assert.equal(binding.national.scaleAudit.sizePumping, false);
 assert.ok(Math.abs(actual.size_frames[0] - 91.2) < 1e-10); assert.deepEqual(actual.anchor_frames, original.anchor_frames);
 assert.deepEqual(actual.rotation_frames, original.rotation_frames); assert.equal(actual.role, original.role);
 assert.deepEqual(binding.national.profiles, record.payload.scenePlan.combatProfile.profiles);
});
test('actual national layout is checked against CURRENT native projection/protection before consumer paint', async () => {
 const {binding} = await nationalFixture(), cpu = spies(), pass = await createVisualExtensionsPass({binding, consumers: cpu.consumers, testOnlyCPU: true}),
  ctx = {...context(), project: () => [540, 960]};
 assert.equal(pass.drawFrame(10, ctx).national.units.length, 1);
 const before = cpu.calls.filter(row => row.name.endsWith(':draw')).length;
 assert.throws(() => pass.drawFrame(11, {...ctx, project: () => [1, 1]}), /CURRENT_LAYOUT_UNSAFE/);
 assert.throws(() => pass.drawFrame(11, {...ctx, protectedGraphics: [{kind: 'TEXT', box: [490, 910, 590, 1010]}]}), /CURRENT_LAYOUT_UNSAFE/);
 assert.equal(cpu.calls.filter(row => row.name.endsWith(':draw')).length, before); pass.dispose();
});
test('roll/Detail missing contracts remain explicit and no unavailable historical data is silently synthesized', async () => {
 assert.equal(VISUAL_UNCONNECTED_CONTRACTS.presentationRoll.state, 'BLOCKED');
 assert.equal(VISUAL_UNCONNECTED_CONTRACTS.postArrivalDetail.state, 'BLOCKED');
 assert.equal(VISUAL_UNCONNECTED_CONTRACTS.historicalScalarControl.state, 'DATA_BLOCKED');
 assert.equal(VISUAL_UNCONNECTED_CONTRACTS.historicalNationalUnits.state, 'DATA_BLOCKED');
 const {request, record} = await nationalFixture();
 await assert.rejects(compileVisualExtensions({request, trustedSources: [record], fps: 30, totalFrames: 2400, allowSynthetic: true}), /CLOCK_BINDING_REQUIRED/);
});
test('partial factory allocation is disposed on downstream factory failure', async () => {
 const {binding} = await scalarFixture({frontier: {enabled: true, outerGoldIntensity: 0}}), cpu = spies();
 cpu.consumers.frontier = () => {throw Error('SYNTHETIC_FACTORY_FAILURE');};
 await assert.rejects(createVisualExtensionsPass({binding, consumers: cpu.consumers, testOnlyCPU: true}), /SYNTHETIC_FACTORY_FAILURE/);
 assert.deepEqual(cpu.calls.map(row => row.name), ['territory:create', 'territory:dispose']);
});
