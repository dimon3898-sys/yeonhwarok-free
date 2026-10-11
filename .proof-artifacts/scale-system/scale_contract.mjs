/**
 * Static geographic Scale contract. This compiler neither renders nor invents
 * detail. Source coordinate arrays remain intact; projection and display
 * admission are explicit plan inputs, shared by Preview and Final.
 */
export const SCALE_CONTRACT_VERSION = 'MAP_INFOGRAPHIC_SCALE_V1';
export const SCALE_NAMES = Object.freeze(['WORLD', 'CONTINENT', 'REGIONAL', 'LOCAL']);
export const SCALE_POLICIES = Object.freeze({
 WORLD: Object.freeze({ purpose: 'World context and geographic recognition', boundaryRatio: .35,
  minimumCorePixels: Object.freeze({ primary: 3, secondary: 2 }),
  markerPixels: 20, information: Object.freeze({ location: false, country: false, title: true, disclosure: true }) }),
 CONTINENT: Object.freeze({ purpose: 'Broad geographic and country relationships', boundaryRatio: .65,
  minimumCorePixels: Object.freeze({ primary: 3, secondary: 2 }),
  markerPixels: 28, information: Object.freeze({ location: false, country: true, title: true, disclosure: true }) }),
 REGIONAL: Object.freeze({ purpose: 'Primary country, neighbors and event location', boundaryRatio: 1,
  markerPixels: 40, information: Object.freeze({ location: true, country: true, title: true, disclosure: true }) }),
 LOCAL: Object.freeze({ purpose: 'Verified event target and geographic location', boundaryRatio: .8,
  markerPixels: 40, information: Object.freeze({ location: true, country: false, title: false, disclosure: true }) }),
});

const radians = d => d * Math.PI / 180;
const finitePoint = p => Array.isArray(p) && p.length >= 2 && p.slice(0, 2).every(Number.isFinite);
const clone = value => structuredClone(value);
const union = bounds => [Math.min(...bounds.map(b => b[0])), Math.min(...bounds.map(b => b[1])),
 Math.max(...bounds.map(b => b[2])), Math.max(...bounds.map(b => b[3]))];
const intersects = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
const intersection = (a, b) => intersects(a, b)
 ? [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])] : null;
const contains = (a, b) => a[0] <= b[0] && a[1] <= b[1] && a[2] >= b[2] && a[3] >= b[3];

export function geometryBounds(record) {
 const coordinates = record?.coordinates ?? record?.geometry?.coordinates;
 const points = [];
 const visit = c => {
  if (finitePoint(c)) points.push(c);
  else if (Array.isArray(c)) c.forEach(visit);
 };
 visit(coordinates);
 if (!points.length) throw Error(`SCALE_GEOMETRY_COORDINATES_REQUIRED: ${record?.id ?? 'unknown'}`);
 return union(points.map(p => [p[0], p[1], p[0], p[1]]));
}

/** Geographic aspect fit, not camera distance. Padding is a universal fraction. */
export function fitGeographicExtent(extent, { center = null, output = [1080, 1920], padding = 1.08 } = {}) {
 if (!Array.isArray(extent) || extent.length !== 4 || !extent.every(Number.isFinite)
  || extent[0] >= extent[2] || extent[1] >= extent[3]) throw Error('SCALE_TARGET_EXTENT_REQUIRED');
 if (!(padding >= 1) || !(output[0] > 0 && output[1] > 0)) throw Error('SCALE_INVALID_DISPLAY_CONTRACT');
 const c = center ?? [(extent[0] + extent[2]) / 2, (extent[1] + extent[3]) / 2];
 if (!finitePoint(c)) throw Error('SCALE_TARGET_CENTER_REQUIRED');
 const cos = Math.cos(radians(c[1]));
 if (cos < .01) throw Error('SCALE_PROJECTION_POLAR_LIMIT: regional equirectangular extent');
 let halfLon = Math.max(c[0] - extent[0], extent[2] - c[0]) * padding;
 let halfLat = Math.max(c[1] - extent[1], extent[3] - c[1]) * padding;
 if (!(halfLon > 0 && halfLat > 0)) throw Error('SCALE_TARGET_AREA_REQUIRED');
 halfLat = Math.max(halfLat, halfLon * cos * output[1] / output[0]);
 halfLon = Math.max(halfLon, halfLat / cos * output[0] / output[1]);
 // Clamping one side would alter projection aspect or fabricate coverage.
 if (c[1] - halfLat < -90 || c[1] + halfLat > 90 || halfLon > 180)
  throw Error('SCALE_EXTENT_REQUIRES_GLOBE_OR_POLAR_PROJECTION');
 return [c[0] - halfLon, c[1] - halfLat, c[0] + halfLon, c[1] + halfLat];
}

/** WGS84 differential lengths, adequate for admission metadata (no resampling). */
export function geographicGroundSpacing(latitude, pixelSpacing) {
 const p = radians(latitude), a = 6378137, e2 = 0.00669437999014;
 const root = Math.sqrt(1 - e2 * Math.sin(p) ** 2);
 const eastPerRadian = a / root * Math.cos(p);
 const northPerRadian = a * (1 - e2) / root ** 3;
 return [eastPerRadian * radians(pixelSpacing[0]), northPerRadian * radians(pixelSpacing[1])];
}

function sourceMetadata(asset, given, global = false) {
 const geographicExtent = asset.bounds ?? given?.geographicExtent ?? (global ? [-180, -90, 180, 90] : null);
 let dimensions = asset.dimensions ?? given?.dimensions ?? null;
 let pixelSpacing = asset.pixelSpacing ?? given?.pixelSpacing ?? null;
 // A native crop can inherit spacing from its verified global source manifest.
 if (!pixelSpacing && !global && asset.source?.resolution) {
  pixelSpacing = [360 / asset.source.resolution[0], 180 / asset.source.resolution[1]];
 }
 if (!pixelSpacing && dimensions && geographicExtent) pixelSpacing = [
  (geographicExtent[2] - geographicExtent[0]) / dimensions[0],
  (geographicExtent[3] - geographicExtent[1]) / dimensions[1]];
 if (!dimensions && pixelSpacing && geographicExtent) dimensions = [
  Math.round((geographicExtent[2] - geographicExtent[0]) / pixelSpacing[0]),
  Math.round((geographicExtent[3] - geographicExtent[1]) / pixelSpacing[1])];
 return { file: asset.file, url: asset.url, sha256: asset.sha256, dimensions,
  geographicExtent, pixelSpacing, classification: asset.classification ?? given?.classification ?? 'RGB_TERRAIN_SOURCE',
  resolutionEvidence: asset.dimensions || asset.pixelSpacing || given ? 'Read from existing asset metadata' : asset.source?.resolution ? 'Verified native source raster spacing' : 'UNKNOWN' };
}

function displayTexelPixels(source, extent, output) {
 if (!source.pixelSpacing) return null;
 return [source.pixelSpacing[0] * output[0] / (extent[2] - extent[0]),
  source.pixelSpacing[1] * output[1] / (extent[3] - extent[1])];
}

/** Select registered, verified raster coverage; no crop or resampling occurs here. */
function selectCoveringTerrain(current, available, extent, output) {
 const candidates = [current, ...available].filter(asset => {
  if (!asset?.bounds || !contains(asset.bounds, extent)) return false;
  if (!/^[a-f0-9]{64}$/i.test(asset.sha256 ?? '') || !asset.file || !asset.url)
   throw Error('SCALE_TERRAIN_SOURCE_INTEGRITY_REQUIRED');
  return true;
 }).map(asset => {
  const source = sourceMetadata(asset, null);
  const pixels = displayTexelPixels(source, extent, output);
  return { asset, source, pixels, density: pixels ? Math.max(...pixels) : Infinity };
 }).filter(candidate => Number.isFinite(candidate.density) && candidate.density > 0);
 if (!candidates.length) return { asset: current, evidence: {
  status: 'NO_FULL_COVERAGE_RASTER', policy: 'Existing regional crop plus global fallback', candidateCount: 0 } };
 const adequate = candidates.filter(candidate => candidate.density <= 1);
 // Prefer the coarsest raster that still meets the output sampling density.
 // If none does, select the finest existing raster and report its native spacing.
 const admitted = (adequate.length ? adequate : candidates).sort((a, b) =>
  adequate.length ? b.density - a.density : a.density - b.density)[0];
 return { asset: admitted.asset, evidence: { status: 'FULL_COVERAGE_RASTER',
  policy: adequate.length ? 'Adequate native detail nearest output sampling density' : 'Finest available native detail; no artificial upscale detail',
  candidateCount: candidates.length, adequateResolution: adequate.length > 0,
  selectedSha256: admitted.asset.sha256, projectedPixelsPerNativeTexel: admitted.pixels } };
}

function buildLod(base, scale, extent, anchor, options) {
 const terrain = sourceMetadata(base.assets.terrain, options.assetMetadata?.terrain);
 const global = sourceMetadata(base.assets.global, options.assetMetadata?.global, true);
 const proxy = sourceMetadata(base.assets.topo, options.assetMetadata?.topo, true);
 const height = options.heightSource;
 const demPolicy = scale === 'REGIONAL' || scale === 'LOCAL';
 const demArea = demPolicy && height?.footprint ? intersection(extent, height.footprint) : null;
 const selection = scale === 'WORLD' ? 'GLOBAL_RGB_AND_RELIEF_PROXY'
  : scale === 'CONTINENT' ? (contains(terrain.geographicExtent, extent)
   ? 'VERIFIED_COVERING_CONTINENT_RGB' : 'GLOBAL_RGB_WITH_VERIFIED_NATIVE_REGIONAL_CROP')
  : 'VERIFIED_NATIVE_REGIONAL_RGB_WITH_GLOBAL_FALLBACK';
 const landSource = scale === 'WORLD' ? global : terrain;
 const rasterCoverage = scale === 'WORLD' ? 'GLOBAL'
  : contains(terrain.geographicExtent, extent) ? 'FULL_REGIONAL_CROP' : 'REGIONAL_CROP_PLUS_GLOBAL_FALLBACK';
 const limited = [];
 if (scale === 'LOCAL') {
  if ((base.geometries ?? []).some(g => (g.scale?.denominator ?? 0) >= 10000000))
   limited.push({ code: 'LOCAL_GIS_GENERALIZED', detail: 'Source country/centerline scales are cartographic, not detailed local boundaries.' });
  const rasterTexels = displayTexelPixels(terrain, extent, options.output);
  if (!rasterTexels || Math.max(...rasterTexels) > 1)
   limited.push({ code: 'LOCAL_RGB_RESOLUTION_LIMITED', detail: 'Native RGB is magnified; DEM normals do not supply higher-resolution color imagery.', projectedPixelsPerNativeTexel: rasterTexels });
  const preciseLines = (options.eventGeometry ?? []).filter(g => ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'].includes(g.geometry_type ?? g.geometry?.type));
  if (preciseLines.some(g => (g.scale?.denominator ?? 0) >= 1000000))
   limited.push({ code: 'LOCAL_EVENT_GEOMETRY_SCHEMATIC', detail: 'Admitted target geometry is generalized and does not establish canal banks or engineering detail.' });
  if (!demArea) limited.push({ code: 'LOCAL_DEM_MISSING', detail: 'No validated height source intersects this local extent.' });
  else if (!contains(height.footprint, extent)) limited.push({ code: 'LOCAL_DEM_PARTIAL', detail: 'Only the recorded height footprint uses real DEM normals.' });
 }
 return { selection, rasterCoverage, terrain, global, proxy,
  nativeRgbGroundSpacingMetersAtAnchor: landSource.pixelSpacing ? geographicGroundSpacing(anchor[1], landSource.pixelSpacing) : null,
  projectedPixelsPerNativeRgbTexel: scale === 'WORLD' ? null : displayTexelPixels(landSource, extent, options.output),
  dem: { enabled: Boolean(demArea), policy: demPolicy ? 'VALIDATED_COVERAGE_ONLY' : 'DISABLED_AT_BROAD_CONTEXT_SCALE',
   source: demArea ? height.source : null, sha256: height?.sha256 ?? null,
   availableFootprint: height?.footprint ?? null, admittedFootprint: demArea,
   fullRequestedExtent: Boolean(demArea && contains(height.footprint, extent)),
   format: height?.format ?? null, pixelSpacing: height?.pixelSpacing ?? null,
   fallback: 'Existing terrain lighting outside validated DEM coverage; no synthesized height' },
  restrictions: { newData: false, newDem: false, artificialDetail: false }, limitations: limited };
}

/**
 * Compile from source Scene + immutable GIS records. eventGeometry contains
 * records referenced by that same Scene event, not region-specific constants.
 */
export function compileScalePlan(base, scale, {
 eventGeometry = [], allCountries = [], heightSource = null, assetMetadata = {}, availableTerrain = [], output = [1080, 1920], padding = 1.08,
} = {}) {
 if (!SCALE_NAMES.includes(scale)) throw Error(`SCALE_UNKNOWN: ${scale}`);
 if (!finitePoint(base?.anchor?.coordinates)) throw Error('SCALE_VERIFIED_ANCHOR_REQUIRED');
 if (!(output[0] === 1080 && output[1] === 1920)) throw Error('SCALE_CANONICAL_STATIC_OUTPUT_REQUIRED');
 const plan = clone(base), policy = SCALE_POLICIES[scale], anchor = [...base.anchor.coordinates];
 const sourceCountries = allCountries.length ? allCountries : base.geometries;
 const countryRecords = sourceCountries.filter(g => ['Polygon', 'MultiPolygon'].includes(g.geometry_type ?? g.geometry?.type));
 if (!countryRecords.find(g => g.id === base.primary)) throw Error('SCALE_PRIMARY_GEOMETRY_REQUIRED');
 let extent, framing, targetExtent, extentBasis;
 if (scale === 'WORLD') {
  if (!allCountries.length) throw Error('WORLD_GLOBAL_GIS_REQUIRED');
  extent = [-180, -90, 180, 90]; targetExtent = [...extent]; extentBasis = 'Full geographic Earth, visible target-centered hemisphere';
  framing = { projection: 'WORLD_GLOBE_ORTHOGRAPHIC', bounds: [...extent], center: anchor,
   globe: { model: 'SPHERE', diameterFraction: .88, centerCanonical: [output[0] / 2, output[1] / 2],
    horizon: 'Visible hemisphere; geographic coordinates on the far side are clipped' } };
  plan.geometries = clone(countryRecords);
 } else if (scale === 'CONTINENT') {
  const ids = new Set([base.primary, ...(base.secondary ?? [])]);
  const context = countryRecords.filter(g => ids.has(g.id));
  if (context.length !== ids.size) throw Error('SCALE_CONTEXT_GEOMETRY_REQUIRED');
  targetExtent = union(context.map(geometryBounds));
  extent = fitGeographicExtent(targetExtent, { output, padding });
  framing = { projection: 'REGIONAL_EQUIRECTANGULAR', bounds: extent };
  extentBasis = 'Actual Primary plus Secondary geometry union, universal padding and output aspect fit';
  plan.geometries = clone(countryRecords.filter(g => intersects(geometryBounds(g), extent)));
 } else if (scale === 'REGIONAL') {
  // Pixel preservation: framing, geometry selection, material, glyph profile and
  // all approved screen-space tokens remain byte-equivalent to the input plan.
  extent = [...base.framing.bounds]; targetExtent = [...extent]; framing = clone(base.framing);
  extentBasis = 'Existing approved geographic regional extent';
 } else {
  if (!eventGeometry.length) throw Error('LOCAL_VERIFIED_EVENT_GEOMETRY_REQUIRED');
  targetExtent = union(eventGeometry.map(geometryBounds));
  extent = fitGeographicExtent(targetExtent, { center: anchor, output, padding });
  framing = { projection: 'REGIONAL_EQUIRECTANGULAR', bounds: extent };
  extentBasis = 'Actual event target geometry extent fitted about the unchanged geographic anchor';
 }
 plan.framing = framing;
 let terrainSelection = null;
 if (scale === 'CONTINENT') {
  const selection = selectCoveringTerrain(plan.assets.terrain, availableTerrain, extent, output);
  plan.assets.terrain = clone(selection.asset);
  terrainSelection = selection.evidence;
 }
 if (scale !== 'REGIONAL') {
  for (const key of ['primaryWidth', 'secondaryWidth', 'primaryEdgeWidth', 'secondaryEdgeWidth', 'glowWidth', 'glowRadius']) {
   if (Number.isFinite(plan.theme[key])) plan.theme[key] *= policy.boundaryRatio;
  }
  if (policy.minimumCorePixels) {
   // Canonical AA consumes part of subpixel-width ribbons. Use a device-pixel
   // floor at broad scales, retaining the approved core/contrast-edge design.
   plan.theme.primaryWidth = Math.max(plan.theme.primaryWidth, policy.minimumCorePixels.primary);
   plan.theme.secondaryWidth = Math.max(plan.theme.secondaryWidth, policy.minimumCorePixels.secondary);
   plan.theme.primaryEdgeWidth = plan.theme.primaryWidth
    + (base.theme.primaryEdgeWidth - base.theme.primaryWidth) * policy.boundaryRatio;
   plan.theme.secondaryEdgeWidth = plan.theme.secondaryWidth
    + (base.theme.secondaryEdgeWidth - base.theme.secondaryWidth) * policy.boundaryRatio;
  }
  plan.layout.measured.markerSize = policy.markerPixels;
 }
 const options = { eventGeometry, allCountries, heightSource, assetMetadata, availableTerrain, output, padding };
 const lod = buildLod(plan, scale, extent, anchor, options);
 if (terrainSelection) lod.terrainSelection = terrainSelection;
 plan.scale = { version: SCALE_CONTRACT_VERSION, name: scale, purpose: policy.purpose,
  projection: framing.projection, geographicExtent: [...extent], targetExtent, extentBasis,
  coordinateSystem: 'EPSG:4326 longitude,latitude', geographicAnchor: anchor,
  canonicalOutput: [...output], staticOnly: true, information: clone(policy.information),
  boundary: { units: 'Canonical output pixels', scaleRatio: policy.boundaryRatio,
   minimumCorePixels: policy.minimumCorePixels ? clone(policy.minimumCorePixels) : null,
   sizePolicy: policy.minimumCorePixels ? 'SCALE_RATIO_WITH_CANONICAL_AA_MINIMUM' : 'APPROVED_SCALE_RATIO',
   minimumReason: policy.minimumCorePixels ? 'Screen-space ribbon antialiasing must not erase broad-scale boundaries' : null,
   effectiveCoreRatio: { primary: plan.theme.primaryWidth / base.theme.primaryWidth,
    secondary: plan.theme.secondaryWidth / base.theme.secondaryWidth },
   primaryCore: plan.theme.primaryWidth, primaryEdge: plan.theme.primaryEdgeWidth,
   secondaryCore: plan.theme.secondaryWidth, secondaryEdge: plan.theme.secondaryEdgeWidth,
   glowWidth: plan.theme.glowWidth, glowRadius: plan.theme.glowRadius },
  marker: { pixels: plan.layout.measured.markerSize, geographicAnchor: anchor, designUnchanged: true },
  lod, admission: { status: lod.limitations.length ? 'LOCAL_DATA_LIMITED' : 'ADMITTED', limitations: clone(lod.limitations) },
  protected: { sourceGeometry: 'UNCHANGED', regionRoles: 'UNCHANGED', terrainStyle: 'UNCHANGED',
   regionMaterial: 'UNCHANGED', typography: 'UNCHANGED', layoutAlgorithm: 'UNIVERSAL_LAYOUT_V1' } };
 return plan;
}
