/** Optional source-bound consumers of the EXISTING scalar-control and national
 * unit owners. No historical geometry, opposing ownership, troop position,
 * renderer, camera, shader, texture or animation engine is authored here.
 * CPU instrumentation is explicitly distinct from GPU pixel verification.
 */
const moduleURL = name => typeof window === 'undefined'
 ? new URL(`../../web/map_infographic_v1/${name}`, import.meta.url).href : `/modules/${name}`;
const referenceURL = name => typeof window === 'undefined'
 ? new URL(`../reference-visual-master-v2/${name}`, import.meta.url).href : `/ref2/${name}`;
const [control, frontierOwner, badges, gain, frontierStyle, unitScale, nativeDomain] = await Promise.all([
 import(moduleURL('territory_control_adapter_v1.mjs')),
 import(moduleURL('reference_control_frontier_light_v3.mjs')),
 import(moduleURL('national_unit_badge_v1.mjs')), import(referenceURL('gain_style_core.mjs')),
 import(referenceURL('frontier_profile_core.mjs')), import(referenceURL('unit-size-profile.mjs')),
 import(referenceURL('native_domain_coverage.mjs'))]);
export const VISUAL_EXTENSIONS_SCHEMA = 'WORLD_ENGINE_OVERNIGHT_VISUAL_V1';
export const VISUAL_BINDING_VERSION = 'WORLD_ENGINE_OVERNIGHT_VISUAL_BINDING_V1';
const clone = value => structuredClone(value), knownBindings = new WeakSet();
const plain = value => value && typeof value === 'object' && !Array.isArray(value)
 && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const identifier = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value);
const sha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const box = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
 && value[0] < value[2] && value[1] < value[3];
function fail(code) { throw Object.assign(Error(code), {code}); }
function exact(value, keys) {
 if (!plain(value) || Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key)))
  fail('OVERNIGHT_VISUAL_FIELDS_UNSUPPORTED');
}
function freeze(value) { if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
export function canonicalVisualJSON(value) {
 if (value === null || typeof value !== 'object') return JSON.stringify(value);
 if (Array.isArray(value)) return '[' + value.map(canonicalVisualJSON).join(',') + ']';
 return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonicalVisualJSON(value[key])).join(',') + '}';
}
export async function visualSourceSHA(value) {
 const bytes = new TextEncoder().encode(canonicalVisualJSON(value));
 const owner = globalThis.crypto ?? (await import('node:crypto')).webcrypto;
 return [...new Uint8Array(await owner.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2, '0')).join('');
}
function sourceReference(value) {
 if (!identifier(value.sourceId) || !sha(value.sha256)) fail('OVERNIGHT_VISUAL_SOURCE_REFERENCE_REQUIRED');
}
/** Only implemented consumers are exposed. Roll/Detail/terrain style knobs are
 * intentionally absent: they require slots the current native owner lacks. */
export function normalizeVisualExtensionsRequest(input) {
 exact(input, ['schema', 'scalarTerritory', 'nationalUnits']);
 if (input.schema !== VISUAL_EXTENSIONS_SCHEMA) fail('OVERNIGHT_VISUAL_SCHEMA_REQUIRED');
 let scalarTerritory = null, nationalUnits = null;
 if (input.scalarTerritory !== null) {
  const value = input.scalarTerritory; exact(value, ['sourceId', 'sha256', 'gain', 'frontier']); sourceReference(value);
  const gainProfile = gain.validateReferenceTerritoryProfile(value.gain);
  const selectedFrontier = value.frontier === null ? null : frontierStyle.validateReferenceFrontierProfile(value.frontier);
  if (selectedFrontier && !selectedFrontier.enabled) fail('OVERNIGHT_DISABLED_FRONTIER_MUST_BE_NULL');
  scalarTerritory = {sourceId: value.sourceId, sha256: value.sha256, gain: clone(gainProfile), frontier: clone(selectedFrontier)};
 }
 if (input.nationalUnits !== null) {
  const value = input.nationalUnits; exact(value, ['sourceId', 'sha256', 'markerScale']); sourceReference(value);
  unitScale.validateReferenceUnitProfile({enabled: true, markerScale: value.markerScale});
  nationalUnits = clone(value);
 }
 return {schema: VISUAL_EXTENSIONS_SCHEMA, scalarTerritory, nationalUnits};
}
/** Catalog bytes are loaded by the server; a public prompt never supplies its
 * own authority. Hash all payload bytes again before selecting an owner. */
export async function compileVisualExtensions({request, trustedSources = [], fps, totalFrames, allowSynthetic = false} = {}) {
 const selected = normalizeVisualExtensionsRequest(request);
 if (fps !== 30 || !Number.isSafeInteger(totalFrames) || totalFrames < 2 || totalFrames > 18000
  || !Array.isArray(trustedSources) || typeof allowSynthetic !== 'boolean') fail('OVERNIGHT_VISUAL_CONTEXT_REQUIRED');
 const catalog = new Map();
 for (const record of trustedSources) {
  if (!plain(record) || !identifier(record.sourceId) || !sha(record.sha256) || catalog.has(record.sourceId))
   fail('OVERNIGHT_VISUAL_CATALOG_INVALID');
  catalog.set(record.sourceId, record);
 }
 async function source(ref, role) {
  const record = catalog.get(ref.sourceId);
  if (!record || record.role !== role || record.sha256 !== ref.sha256
   || !['VERIFIED', 'SYNTHETIC_TEST'].includes(record.verificationStatus)
   || await visualSourceSHA(record.payload) !== record.sha256) fail('OVERNIGHT_VISUAL_VERIFIED_SOURCE_REQUIRED');
  const synthetic = record.verificationStatus === 'SYNTHETIC_TEST';
  if (synthetic && !allowSynthetic) fail('OVERNIGHT_VISUAL_SYNTHETIC_NOT_PRODUCTION');
  return {payload: clone(record.payload), synthetic};
 }
 let scalar = null, national = null;
 if (selected.scalarTerritory) {
  const {payload, synthetic} = await source(selected.scalarTerritory, 'SCALAR_CONTROL_PLAN');
  exact(payload, ['schema', 'plan', 'territoryStyle', 'frontierStyle', 'nativeDomain']);
  if (payload.schema !== 'WORLD_ENGINE_SCALAR_CONTROL_SOURCE_V1') fail('OVERNIGHT_SCALAR_SOURCE_SCHEMA_REQUIRED');
  const plan = control.compileTerritoryControlPlan(payload.plan?.intent);
  if (canonicalVisualJSON(plan) !== canonicalVisualJSON(payload.plan)) fail('OVERNIGHT_SCALAR_CANONICAL_PLAN_REQUIRED');
  if (plan.fps !== fps || plan.startFrame + plan.totalFrames > totalFrames) fail('OVERNIGHT_SCALAR_CLOCK_BINDING_REQUIRED');
  if ((plan.intent.semantic_mode === 'REFERENCE_VISUAL_STUDY') !== synthetic) fail('OVERNIGHT_SCALAR_SEMANTIC_BINDING_REQUIRED');
  // These original profiles alter expression only, never classifier/timing.
  const territoryStyle = gain.applyReferenceTerritoryStyle(payload.territoryStyle, selected.scalarTerritory.gain);
  const selectedFrontier = selected.scalarTerritory.frontier;
  let effectiveFrontier = null, motion = null, domainMetadata = null;
  if (selectedFrontier) {
   effectiveFrontier = frontierOwner.validateControlFrontierLightProfile(
    frontierStyle.applyReferenceFrontierStyle(payload.frontierStyle, selectedFrontier));
   motion = frontierOwner.compileControlFrontierLightMotion(plan, effectiveFrontier);
   if (selectedFrontier.outerGoldIntensity > 0) {
    if (!payload.nativeDomain) fail('OVERNIGHT_ACTUAL_NATIVE_ROLE_DOMAIN_REQUIRED');
    const handle = await nativeDomain.createNativeDomainBinding({...payload.nativeDomain, domain: plan.intent.domain,
     eventStartFrame: plan.startFrame});
    domainMetadata = nativeDomain.describeNativeDomainBinding(handle);
   }
  }
  scalar = {plan, territoryStyle, selectedFrontier, effectiveFrontier, motion, nativeDomain: payload.nativeDomain,
   domainMetadata, sourceReference: {sourceId: selected.scalarTerritory.sourceId, sha256: selected.scalarTerritory.sha256},
   synthetic, gainEvidence: gain.describeReferenceGainStyle(payload.territoryStyle, territoryStyle, selected.scalarTerritory.gain)};
 }
 if (selected.nationalUnits) {
  const {payload, synthetic} = await source(selected.nationalUnits, 'NATIONAL_UNIT_SCENE');
  exact(payload, ['schema', 'scenePlan', 'baseCameraPlan', 'currentNativeFrame', 'safeArea']);
  if (payload.schema !== 'WORLD_ENGINE_NATIONAL_UNIT_SCENE_SOURCE_V1') fail('OVERNIGHT_NATIONAL_SOURCE_SCHEMA_REQUIRED');
  const fixture = badges.validateNationalUnitBadgeFixture(payload.scenePlan?.combatProfile?.units, payload.scenePlan?.combatProfile?.profiles);
  if (fixture.frames !== totalFrames || payload.scenePlan.controlIntent?.fps !== fps
   || payload.scenePlan.controlIntent?.total_frames !== totalFrames) fail('OVERNIGHT_NATIONAL_CLOCK_BINDING_REQUIRED');
  const result = unitScale.selectReferenceUnitScale({...payload, profile: {enabled: true, markerScale: selected.nationalUnits.markerScale}});
  national = {units: result.scenePlan.combatProfile.units, profiles: result.scenePlan.combatProfile.profiles,
   safeArea: clone(payload.safeArea), scaleAudit: result.audit, synthetic,
   sourceReference: {sourceId: selected.nationalUnits.sourceId, sha256: selected.nationalUnits.sha256}};
 }
 const binding = freeze({version: VISUAL_BINDING_VERSION, request: selected, fps, totalFrames, scalar, national,
  historicalGeometryInferred: false, enemyComplementInferred: false, historicalUnitPositionsInferred: false,
  cpuCompilationOnly: true, gpuOutputVerified: false});
 knownBindings.add(binding); return binding;
}
function compiled(binding) { if (!knownBindings.has(binding)) fail('OVERNIGHT_VISUAL_COMPILED_BINDING_REQUIRED'); }
export function evaluateVisualExtensionsFrame(binding, frame, context = {}) {
 compiled(binding);
 if (!Number.isSafeInteger(frame) || frame < 0 || frame >= binding.totalFrames) fail('OVERNIGHT_VISUAL_FRAME_OUT_OF_RANGE');
 const scalarActive = binding.scalar && frame >= binding.scalar.plan.startFrame
  && frame < binding.scalar.plan.startFrame + binding.scalar.plan.totalFrames;
 if ((scalarActive || binding.national) && (typeof context.project !== 'function' || !box(context.safeArea)
  || !Array.isArray(context.protectedGraphics))) fail('OVERNIGHT_VISUAL_NATIVE_CONTEXT_REQUIRED');
 if (scalarActive && (context.parentGeographicFrontPresent !== false || context.parentTerritoryFillPresent !== false
  || context.nativeBoundarySourceVerified !== true || !Array.isArray(context.boundarySegments)
  || !Array.isArray(context.internalBoundarySegments))) fail('OVERNIGHT_SCALAR_PARENT_COMPOSITION_SLOT_REQUIRED');
 const scalar = scalarActive ? {controls: control.evaluateTerritoryControlFrame(binding.scalar.plan, frame),
  motion: binding.scalar.motion ? frontierOwner.evaluateControlFrontierLightMotion(binding.scalar.motion, frame) : null} : null;
 const national = binding.national ? badges.evaluateNationalUnitBadgeLayout(binding.national.units, frame,
  {project: context.project, safeArea: context.safeArea, protectedGraphics: context.protectedGraphics}) : null;
 if (national && (national.safeAreaViolations.length || national.criticalCollisions.length || national.unitOverlaps.length))
  fail('OVERNIGHT_NATIONAL_CURRENT_LAYOUT_UNSAFE');
 return {frame, scalar, national, cpuEvaluationOnly: true, gpuOutputVerified: false};
}
/** Use the preserved real GPU factories in a browser. Injected consumers are
 * permitted exclusively for labelled CPU tests; they never prove GPU pixels. */
export async function createVisualExtensionsPass({canvas, binding, consumers = null, testOnlyCPU = false} = {}) {
 compiled(binding);
 if (consumers !== null && testOnlyCPU !== true) fail('OVERNIGHT_VISUAL_TEST_CONSUMERS_FORBIDDEN');
 const hasData = Boolean(binding.scalar || binding.national);
 if (!hasData) {
  let disposed = false;
  return {evidence: {emptySelection: true, gpuOutputVerified: false},
   drawFrame(frame, context) { if (disposed) fail('OVERNIGHT_VISUAL_PASS_DISPOSED'); return evaluateVisualExtensionsFrame(binding, frame, context); },
   dispose() { disposed = true; }};
 }
 if (!consumers) {
  if (typeof window === 'undefined' || canvas?.width !== 1080 || canvas?.height !== 1920)
   fail('OVERNIGHT_VISUAL_BROWSER_NATIVE_CANVAS_REQUIRED');
  const territory = await import(moduleURL('territory_control_gpu_adapter_v1.mjs'));
  consumers = {territory: options => territory.createTerritoryControlPass(options),
   frontier: options => frontierOwner.createControlFrontierLightPassV3(options),
   national: options => badges.createNationalUnitBadgeOverlay(options),
   outer: async options => {
    const [outer, flow, support] = await Promise.all([import(referenceURL('coverage_outer_glow.mjs')),
     import(moduleURL('flow_graphic_pass_v2.mjs')), import('/quality/support_gpu.mjs')]);
    return outer.createCoverageOuterGlowPass({...options, gl: canvas.getContext('webgl2'),
     capture: flow.captureFlowNativeGlState, restore: flow.restoreFlowNativeGlState,
     programFactory: support.qualityProgram, resetPixels: support.resetQualityPixels, setupTexture: support.setupQualityTexture});
   }};
 }
 const passes = []; let territory = null, frontier = null, outer = null, national = null, domainHandle = null;
 try {
  if (binding.scalar) {
   const value = binding.scalar, options = {canvas, territoryPlan: value.plan, landDomain: value.plan.intent.domain};
   if (typeof consumers.territory !== 'function') fail('OVERNIGHT_TERRITORY_CONSUMER_REQUIRED');
   territory = await consumers.territory({...options, style: value.territoryStyle}); passes.push(territory);
   if (value.effectiveFrontier) {
    if (typeof consumers.frontier !== 'function') fail('OVERNIGHT_FRONTIER_CONSUMER_REQUIRED');
    frontier = await consumers.frontier({...options, profile: value.effectiveFrontier}); passes.push(frontier);
    if (value.domainMetadata) {
     if (typeof consumers.outer !== 'function') fail('OVERNIGHT_OUTER_DOMAIN_CONSUMER_REQUIRED');
     domainHandle = await nativeDomain.createNativeDomainBinding({...value.nativeDomain, domain: value.plan.intent.domain,
      eventStartFrame: value.plan.startFrame});
     outer = await consumers.outer({profile: value.selectedFrontier}); passes.push(outer);
    }
   }
  }
  if (binding.national) {
   if (typeof consumers.national !== 'function') fail('OVERNIGHT_NATIONAL_CONSUMER_REQUIRED');
   national = await consumers.national({canvas, units: binding.national.units, profiles: binding.national.profiles}); passes.push(national);
  }
 } catch (error) { passes.forEach(pass => pass?.dispose?.()); throw error; }
 let disposed = false;
 return {evidence: {version: VISUAL_BINDING_VERSION, existingFactoriesSelected: true, cpuInstrumentation: testOnlyCPU,
  scalarClassifierChanged: false, cameraChanged: false, shaderSourceChanged: false, gpuOutputVerified: false},
  drawFrame(frame, context) {
   if (disposed) fail('OVERNIGHT_VISUAL_PASS_DISPOSED');
   const selected = evaluateVisualExtensionsFrame(binding, frame, context), results = {};
   let outerContext = null;
   // Validate every downstream prerequisite BEFORE any pass can paint.
   if (selected.scalar && (frontier || outer) && (!Number.isFinite(context.presentationScale)
    || context.presentationScale < 1 || context.presentationScale > 2)) fail('OVERNIGHT_FRONTIER_PRESENTATION_SCALE_REQUIRED');
   if (selected.scalar && frontier && binding.scalar.effectiveFrontier.reliefLightingEnabled
    && (context.actualTerrainSnapshot?.frame !== frame || context.actualTerrainSnapshot?.source !== 'ACTUAL_CURRENT_NATIVE_TERRAIN'
     || !context.actualTerrainSnapshot.texture)) fail('OVERNIGHT_SAME_FRAME_ACTUAL_TERRAIN_TEXTURE_REQUIRED');
   if (selected.scalar && outer) {
    if (context.nativeRoleCoverage?.frame !== frame) fail('OVERNIGHT_SAME_FRAME_NATIVE_ROLE_COVERAGE_REQUIRED');
    nativeDomain.publishNativeDomainCoverage(canvas, domainHandle, {...context.nativeRoleCoverage,
     frame: frame - binding.scalar.plan.startFrame});
    outerContext = nativeDomain.getNativeDomainCoverage(canvas, {frame, domainSHA256: binding.scalar.domainMetadata.domainSHA256});
    frontierStyle.assertOuterDomainContext(outerContext, {controls: selected.scalar.controls, project: context.project,
     domainMetadata: binding.scalar.domainMetadata});
   }
   if (selected.scalar) {
    const args = {controls: selected.scalar.controls, project: context.project, safeArea: context.safeArea,
     protectedGraphics: context.protectedGraphics, boundarySegments: context.boundarySegments,
     internalBoundarySegments: context.internalBoundarySegments};
    results.territory = territory.draw(args);
    if (frontier) results.frontier = frontier.draw({...args, actualTerrainTexture: context.actualTerrainSnapshot?.texture,
     presentationScale: context.presentationScale});
    if (outer) results.outer = outer.draw({context: outerContext, presentationScale: context.presentationScale,
     safeArea: context.safeArea, protectedGraphics: context.protectedGraphics});
   }
   if (national) results.national = national.draw({frame, project: context.project, safeArea: context.safeArea,
    protectedGraphics: context.protectedGraphics});
   return {...selected, consumerResults: results, gpuOutputVerified: false};
  }, dispose() { if (!disposed) { passes.forEach(pass => pass?.dispose?.()); if (canvas) nativeDomain.clearNativeDomainCoverage(canvas); disposed = true; } }};
}
export const VISUAL_UNCONNECTED_CONTRACTS = freeze({
 presentationRoll: {state: 'BLOCKED', missing: ['NATIVE_PRESENTATION_SLOT_BEFORE_SCREEN_FIXED_GRAPHICS',
  'OVERSCAN_COVERAGE_FOR_ALL_FRAMES', 'PRESENTED_PROJECTION_FOR_ALL_LAYOUT_OWNERS']},
 postArrivalDetail: {state: 'BLOCKED', missing: ['FRESH_NATIVE_1080X1920_VISUAL_ADMISSION',
  'SOURCE_BOUND_CANDIDATE_LAYOUT_AND_GEOMETRY', 'PARENT_CAMERA_FLOOR_COMPATIBILITY']},
 terrainDestinationLight: {state: 'CONDITIONAL', missing: ['SAME_FRAME_PRE_TERRITORY_NATIVE_TERRAIN_TEXTURE']},
 historicalScalarControl: {state: 'DATA_BLOCKED', missing: ['VERIFIED_BILATERAL_MONOTONE_OWNERSHIP_SOURCE']},
 historicalNationalUnits: {state: 'DATA_BLOCKED', missing: ['VERIFIED_PER_FRAME_UNIT_POSITIONS_AND_ROLE_SOURCE']}
});
if (typeof process !== 'undefined' && (process.argv?.includes('--normalize') || process.argv?.includes('--admit'))) {
 try {
  const chunks = []; let size = 0;
  for await (const chunk of process.stdin) { size += chunk.length; if (size > 8 * 1024 * 1024) fail('OVERNIGHT_VISUAL_INPUT_SIZE_LIMIT'); chunks.push(chunk); }
  const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (process.argv.includes('--admit')) {
   exact(value, ['request', 'trustedSources', 'fps', 'totalFrames']);
   const binding = await compileVisualExtensions({...value, allowSynthetic: false});
   process.stdout.write(JSON.stringify({schema: 'WORLD_ENGINE_OVERNIGHT_VISUAL_ADMISSION_V1', status: 'CPU_ADMITTED',
    scalarControlSelected: Boolean(binding.scalar), nationalUnitsSelected: Boolean(binding.national),
    sourceReferences: [binding.scalar?.sourceReference, binding.national?.sourceReference].filter(Boolean),
    totalFrames: binding.totalFrames, fps: binding.fps, historicalDataInferred: false, gpuOutputVerified: false}));
  } else process.stdout.write(JSON.stringify(normalizeVisualExtensionsRequest(value)));
 } catch (error) {
  const code = error.code ?? error.message;
  process.stderr.write((typeof code === 'string' && /^[A-Z][A-Z0-9_]{0,160}$/.test(code)
   ? code : 'OVERNIGHT_VISUAL_INPUT_INVALID') + '\n'); process.exitCode = 2;
 }
}
