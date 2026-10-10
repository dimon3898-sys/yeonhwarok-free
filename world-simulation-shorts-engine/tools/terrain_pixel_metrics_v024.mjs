/** Captured CPU pixels only; never an NVIDIA or human visual acceptance result. */
import {
  imageDifference, boundaryPixelMetrics, containmentPixelMetrics,
} from './bold_pixel_metrics_v023.mjs';

export {imageDifference, boundaryPixelMetrics, containmentPixelMetrics};
const quantile = (values, q) => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * q)];
};
const validImage = (image, width, height) => {
  if (!(image instanceof Uint8ClampedArray || image instanceof Uint8Array)
      || !Number.isInteger(width) || !Number.isInteger(height)
      || width < 1 || height < 1 || image.length !== width * height * 4) {
    throw Error('TERRAIN_PIXEL_IMAGE_INVALID');
  }
};
export const pixelLuminance = (image, index, standard = 'W3C') => {
  const weights = standard === 'W3C' ? [.30, .59, .11]
    : standard === 'REC709' ? [.2126, .7152, .0722] : null;
  if (!weights) throw Error('TERRAIN_LUMINANCE_STANDARD_INVALID');
  return weights.reduce((sum, weight, channel) => sum + weight * image[index + channel], 0) / 255;
};

const sourcePolygons = new WeakMap();
function prepareSourcePolygons(record) {
  if(sourcePolygons.has(record))return sourcePolygons.get(record);
  if(!record||!['Polygon','MultiPolygon'].includes(record.geometry_type))throw Error('TERRAIN_SOURCE_POLYGON_REQUIRED');
  const parts=record.geometry_type==='Polygon'?[record.coordinates]:record.coordinates;
  const polygons=parts.map(rings=>rings.map(raw=>{
    const points=[];for(const [lon,lat] of raw){let unwrapped=lon;if(points.length){const previous=points.at(-1)[0];while(unwrapped-previous>180)unwrapped-=360;while(unwrapped-previous< -180)unwrapped+=360;}points.push([unwrapped,lat]);}
    const anchor=points.reduce((sum,p)=>sum+p[0],0)/points.length;
    return {points,anchor,minLon:Math.min(...points.map(p=>p[0])),maxLon:Math.max(...points.map(p=>p[0])),minLat:Math.min(...points.map(p=>p[1])),maxLat:Math.max(...points.map(p=>p[1]))};
  }));sourcePolygons.set(record,polygons);return polygons;
}
const insideSourceRing=(ring,lon,lat)=>{
  lon+=Math.round((ring.anchor-lon)/360)*360;
  if(lon<ring.minLon||lon>ring.maxLon||lat<ring.minLat||lat>ring.maxLat)return false;
  let inside=false;const points=ring.points;
  for(let i=0,j=points.length-1;i<points.length;j=i++){
    const a=points[i],b=points[j];if((a[1]>lat)!==(b[1]>lat)&&lon<(b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0])inside=!inside;
  }return inside;
};
/** Independent raw EPSG:4326 source-ring membership, never projected triangles. */
export function nativeGeometryContains(record,lon,lat){
  if(!Number.isFinite(lon)||!Number.isFinite(lat))throw Error('TERRAIN_SOURCE_POINT_INVALID');
  return prepareSourcePolygons(record).some(rings=>insideSourceRing(rings[0],lon,lat)&&!rings.slice(1).some(hole=>insideSourceRing(hole,lon,lat)));
}
export function sourceGeometryMask(record,longitude,latitude,validRay,width,height){
  if(!(longitude instanceof Float32Array||longitude instanceof Float64Array)||!(latitude instanceof Float32Array||latitude instanceof Float64Array)||!(validRay instanceof Uint8Array)||[longitude,latitude,validRay].some(a=>a.length!==width*height))throw Error('TERRAIN_SOURCE_RAY_GRID_INVALID');
  const out=new Uint8ClampedArray(width*height*4);prepareSourcePolygons(record);
  for(let pixel=0;pixel<width*height;pixel++)if(validRay[pixel]&&nativeGeometryContains(record,longitude[pixel],latitude[pixel]))out[pixel*4+3]=255;
  return out;
}

/** Newly healed mesh gaps must be genuine native-GIS interior. Raw outside
 * source coverage is separately reported because spherical arc/raster edge
 * conventions are not identical to linear EPSG:4326 source-ring membership.
 */
export function sourceGeometryCoveragePixels(oldCoverage,newCoverage,sourceMask,nativeEdgeMask,width,height,{nativeEdgeExclusion=4}={}){
  for(const image of [oldCoverage,newCoverage,sourceMask,nativeEdgeMask])validImage(image,width,height);
  const inverse=new Uint8ClampedArray(sourceMask.length);
  for(let pixel=0;pixel<width*height;pixel++)if(!nativeEdgeMask[pixel*4+3])inverse[pixel*4+3]=255;
  const distance=interiorDistance(inverse,width,height);
  let healed=0,healedInterior=0,healedInteriorOutside=0,newOutside=0,newOutsideInterior=0;
  const examples=[];
  for(let pixel=0;pixel<width*height;pixel++){
    const a=pixel*4,interior=distance[pixel]>nativeEdgeExclusion;
    if(newCoverage[a+3]>=250&&oldCoverage[a+3]<250){
      healed++;if(interior){healedInterior++;if(!sourceMask[a+3]){healedInteriorOutside++;if(examples.length<8)examples.push({x:pixel%width,y:Math.floor(pixel/width),source_contains:false,native_edge_distance_px:distance[pixel]});}}
    }
    if(newCoverage[a+3]>=3&&!sourceMask[a+3]){newOutside++;if(interior)newOutsideInterior++;}
  }
  return {healed_old_mesh_pixels:healed,healed_interior_pixels:healedInterior,healed_interior_outside_source_geometry_pixels:healedInteriorOutside,
    new_coverage_outside_raw_source_geometry_pixels:newOutside,new_coverage_outside_source_far_from_native_edges_pixels:newOutsideInterior,native_edge_exclusion_px:nativeEdgeExclusion,examples,
    source_oracle:'Independent inverse frozen-camera ray lat/lon + raw verified EPSG:4326 Polygon/MultiPolygon ring/hole membership, antimeridian unwrapped; no projected mesh or outline-fill implementation used.'};
}

/** Native polygon interior distance excludes lines, shadows and antialiased shores. */
function interiorDistance(mask, width, height) {
  const field = new Float32Array(width * height), diagonal = Math.SQRT2;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = y * width + x;
    field[i] = mask[i * 4 + 3] >= 250 ? Math.min(x + 1, y + 1, width - x, height - y) : 0;
  }
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = y * width + x;
    if (!field[i]) continue;
    let distance = field[i];
    if (x) distance = Math.min(distance, field[i - 1] + 1);
    if (y) distance = Math.min(distance, field[i - width] + 1);
    if (x && y) distance = Math.min(distance, field[i - width - 1] + diagonal);
    if (x + 1 < width && y) distance = Math.min(distance, field[i - width + 1] + diagonal);
    field[i] = distance;
  }
  for (let y = height - 1; y >= 0; y--) for (let x = width - 1; x >= 0; x--) {
    const i = y * width + x;
    if (!field[i]) continue;
    let distance = field[i];
    if (x + 1 < width) distance = Math.min(distance, field[i + 1] + 1);
    if (y + 1 < height) distance = Math.min(distance, field[i + width] + 1);
    if (x + 1 < width && y + 1 < height) distance = Math.min(distance, field[i + width + 1] + diagonal);
    if (x && y + 1 < height) distance = Math.min(distance, field[i + width - 1] + diagonal);
    field[i] = distance;
  }
  return field;
}

/** Measure color transfer and source-relative terrain at multiple pixel scales.
 * W3C nonseparable color uses .30/.59/.11; Rec.709 is measured separately.
 * Neither is silently described as physical radiance or exact shader lighting.
 */
export function terrainRegionPixels(before, after, mask, width, height,
  {erosion = 8, stride = 2, spatialScales = [1, 3, 7], expectedLuminanceScale = 1} = {}) {
  for (const image of [before, after, mask]) validImage(image, width, height);
  if (!Number.isInteger(erosion) || erosion < 1 || !Number.isInteger(stride) || stride < 1
      || !Array.isArray(spatialScales) || !spatialScales.length
      || spatialScales.some(value => !Number.isInteger(value) || value < 1 || value > 32)
      || !Number.isFinite(expectedLuminanceScale) || expectedLuminanceScale < .80 || expectedLuminanceScale > 1) {
    throw Error('TERRAIN_SAMPLE_POLICY_INVALID');
  }
  const field = interiorDistance(mask, width, height), deltas = [], errors = {W3C: [], REC709: []};
  const scaledErrors = {W3C: [], REC709: []};
  const accumulators = spatialScales.map(scale => ({scale, W3C: {xx: 0, yy: 0, xy: 0, count: 0},
    REC709: {xx: 0, yy: 0, xy: 0, count: 0}}));
  const source = {W3C: [], REC709: []}, painted = {W3C: [], REC709: []};
  let changed = 0;
  for (let y = erosion; y < height - erosion; y += stride) {
    for (let x = erosion; x < width - erosion; x += stride) {
      const pixel = y * width + x, index = pixel * 4;
      if (field[pixel] <= erosion) continue;
      const delta = Math.hypot(before[index] - after[index], before[index + 1] - after[index + 1],
        before[index + 2] - after[index + 2]) / (255 * Math.sqrt(3));
      deltas.push(delta); if (delta > 2 / 255) changed++;
      for (const standard of ['W3C', 'REC709']) {
        const original = pixelLuminance(before, index, standard), result = pixelLuminance(after, index, standard);
        source[standard].push(original); painted[standard].push(result); errors[standard].push(Math.abs(result - original));
        scaledErrors[standard].push(Math.abs(result - original * expectedLuminanceScale));
        for (const accumulator of accumulators) {
          for (const step of [accumulator.scale, accumulator.scale * width]) {
            const next = pixel + step;
            if (next >= width * height || step < width && x + step >= width
                || field[next] <= erosion) continue;
            const a = pixelLuminance(before, next * 4, standard) - original;
            const b = pixelLuminance(after, next * 4, standard) - result;
            accumulator[standard].xx += a * a;
            accumulator[standard].yy += b * b;
            accumulator[standard].xy += a * b;
            accumulator[standard].count++;
          }
        }
      }
    }
  }
  const luminance = {};
  for (const standard of ['W3C', 'REC709']) {
    const values = errors[standard];
    luminance[standard] = {
      mean_absolute_error: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
      p95_absolute_error: quantile(values, .95),
      expected_local_luminance_scale: expectedLuminanceScale,
      mean_absolute_error_against_scaled_source: scaledErrors[standard].length
        ? scaledErrors[standard].reduce((a,b) => a + b, 0) / scaledErrors[standard].length : null,
      p95_absolute_error_against_scaled_source: quantile(scaledErrors[standard], .95),
      source_p10: quantile(source[standard], .10), source_p50: quantile(source[standard], .50), source_p90: quantile(source[standard], .90),
      output_p10: quantile(painted[standard], .10), output_p50: quantile(painted[standard], .50), output_p90: quantile(painted[standard], .90),
    };
  }
  return {
    interior_samples: deltas.length, changed_fraction: deltas.length ? changed / deltas.length : 0,
    median_rgb_contrast: quantile(deltas, .5), p10_rgb_contrast: quantile(deltas, .1), luminance,
    detail: accumulators.map(row => ({scale_px: row.scale, ...Object.fromEntries(['W3C', 'REC709'].map(standard => {
      const a = row[standard], available = a.count > 0 && a.xx > 1e-7;
      return [standard, {samples: a.count, source_texture_available: available,
        retention: available ? Math.sqrt(a.yy / a.xx) : null,
        normalized_retention_against_expected_local_scale: available ? Math.sqrt(a.yy / a.xx) / expectedLuminanceScale : null,
        correlation: available && a.yy > 1e-12 ? a.xy / Math.sqrt(a.xx * a.yy) : null}];
    }))})),
    scope: 'Actual source/painted Canvas2D pixels. Raw original-source W3C/Rec.709 luminance and absolute detail retention retained; expected geometry-local tonal scale error and normalized retention reported separately. Not physical GPU radiance.',
  };
}

const rasterAlpha = (image, width, height, x, y) => {
  if (x < 0 || y < 0 || x >= width - 1 || y >= height - 1) return 0;
  const left = Math.floor(x), top = Math.floor(y), dx = x - left, dy = y - top;
  const at = (xx, yy) => image[(yy * width + xx) * 4 + 3] / 255;
  return at(left, top) * (1 - dx) * (1 - dy) + at(left + 1, top) * dx * (1 - dy)
    + at(left, top + 1) * (1 - dx) * dy + at(left + 1, top + 1) * dx * dy;
};

/** Actual halo threshold reach, not Canvas shadowBlur treated as a hard radius. */
export function haloPixelMetrics(halo, width, height, segments,
  {maximumSamples = 48, radius = 30, step = .25, visibilityAlpha = 3 / 255, nativeEdgeMask = null} = {}) {
  validImage(halo, width, height);
  if (!Array.isArray(segments) || !Number.isFinite(radius) || radius <= 0
      || !Number.isFinite(step) || step <= 0 || !Number.isFinite(visibilityAlpha)
      || visibilityAlpha <= 0 || visibilityAlpha > 1) throw Error('TERRAIN_HALO_POLICY_INVALID');
  const reaches = [], peaks = [], centerEdges = []; let limitHits = 0;
  for (const [a, b] of segments) {
    if (reaches.length >= maximumSamples) break;
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    if (length < 2) continue;
    const x = (a.x + b.x) / 2, y = (a.y + b.y) / 2;
    if (x < radius || x > width - radius || y < radius || y > height - radius) continue;
    const nx = -(b.y - a.y) / length, ny = (b.x - a.x) / length;
    let reach = 0, peak = 0, energy = 0;
    for (let distance = -radius; distance <= radius; distance += step) {
      const alpha = rasterAlpha(halo, width, height, x + nx * distance, y + ny * distance);
      peak = Math.max(peak, alpha); energy += alpha * step;
      if (alpha >= visibilityAlpha) reach = Math.max(reach, Math.abs(distance));
    }
    if (peak < visibilityAlpha) continue;
    if (reach >= radius - step) limitHits++;
    reaches.push(reach); peaks.push(peak); centerEdges.push(energy);
  }
  let paintedPixels = 0, maximumAlpha = 0;
  for (let i = 3; i < halo.length; i += 4) {
    if (halo[i] >= visibilityAlpha * 255) paintedPixels++;
    maximumAlpha = Math.max(maximumAlpha, halo[i] / 255);
  }
  let nearestEdge = null;
  if (nativeEdgeMask !== null) {
    validImage(nativeEdgeMask, width, height);
    const inverse = new Uint8ClampedArray(halo.length), distances = [];
    for (let pixel = 0; pixel < width * height; pixel++) {
      if (!nativeEdgeMask[pixel * 4 + 3]) inverse[pixel * 4 + 3] = 255;
    }
    const field = interiorDistance(inverse, width, height);
    for (let pixel = 0; pixel < width * height; pixel++) {
      if (halo[pixel * 4 + 3] >= visibilityAlpha * 255) distances.push(field[pixel]);
    }
    nearestEdge = {measured_pixels: distances.length, distance_px_median: quantile(distances, .5),
      distance_px_p90: quantile(distances, .9), distance_px_max: distances.reduce((a,b) => Math.max(a,b), 0),
      reference: 'Actual 1px raster of all verified native GIS edges; nearest-edge distance includes adjacent native edges and excludes false remote-cross-section attribution.'};
  }
  return {cross_sections: reaches.length, reach_from_native_edge_px_median: quantile(reaches, .5),
    reach_from_native_edge_px_p90: quantile(reaches, .9), reach_from_native_edge_px_max: reaches.length ? Math.max(...reaches) : null,
    peak_alpha_median: quantile(peaks, .5), maximum_alpha: maximumAlpha,
    cross_section_alpha_energy_median: quantile(centerEdges, .5), threshold_painted_pixels: paintedPixels,
    sampling_limit_hits: limitHits, visibility_alpha_threshold: visibilityAlpha, nearest_native_edge: nearestEdge,
    scope: 'Actual isolated halo RGBA, sampled perpendicular to native GIS edges. Gaussian tail measured at declared alpha threshold.'};
}

/** Contrast from composited pixels against native terrain along actual edges. */
export function outlineContrastPixels(before, after, width, height, segments,
  {maximumSamples = 48, radius = 12, step = .5} = {}) {
  validImage(before, width, height); validImage(after, width, height);
  const contrasts = [];
  for (const [a, b] of segments) {
    if (contrasts.length >= maximumSamples) break;
    const length = Math.hypot(b.x - a.x, b.y - a.y); if (length < 2) continue;
    const x = (a.x + b.x) / 2, y = (a.y + b.y) / 2;
    if (x < radius || x > width - radius || y < radius || y > height - radius) continue;
    const nx = -(b.y - a.y) / length, ny = (b.x - a.x) / length;
    let contrast = 0;
    for (let distance = -radius; distance <= radius; distance += step) {
      const xx = Math.round(x + nx * distance), yy = Math.round(y + ny * distance), index = (yy * width + xx) * 4;
      contrast = Math.max(contrast, Math.abs(pixelLuminance(before, index) - pixelLuminance(after, index)));
    }
    contrasts.push(contrast);
  }
  return {cross_sections: contrasts.length, median_luminance_contrast: quantile(contrasts, .5),
    p10_luminance_contrast: quantile(contrasts, .1), method: 'Maximum actual W3C luminance contrast within 12px native-edge cross-section.'};
}

/** Separate existing-raster shoreline observation, without RGB water inference.
 * A rasterized 1:50m country union and spherical native polygon raster need
 * not select the same edge pixel. Both raw changed-water pixels and measured
 * distance to the actual raster land edge are reported; no mismatch is hidden.
 */
export function existingLandMaskPixels(before, after, landMask, coverage, width, height) {
  for (const image of [before, after, landMask]) validImage(image, width, height);
  if (!(coverage instanceof Uint8Array) || coverage.length !== width * height) throw Error('TERRAIN_LAND_MASK_COVERAGE_INVALID');
  const waterMask = new Uint8ClampedArray(before.length);
  let covered = 0, water = 0, changed = 0; const distances = [];
  for (let pixel = 0; pixel < width * height; pixel++) {
    if (coverage[pixel] && landMask[pixel * 4 + 3] === 0) waterMask[pixel * 4 + 3] = 255;
  }
  const field = interiorDistance(waterMask, width, height);
  for (let pixel = 0; pixel < width * height; pixel++) {
    if (!coverage[pixel]) continue;
    covered++; if (landMask[pixel * 4 + 3]) continue;
    water++; const index = pixel * 4;
    if (Math.max(Math.abs(before[index] - after[index]), Math.abs(before[index + 1] - after[index + 1]),
      Math.abs(before[index + 2] - after[index + 2])) > 2) {
      changed++; distances.push(field[pixel]);
    }
  }
  return {covered_pixels: covered, existing_mask_ocean_or_hole_pixels: water,
    changed_ocean_or_hole_pixels: changed, ocean_or_hole_exact_unchanged: changed === 0,
    changed_ocean_distance_from_raster_land_px_median: quantile(distances, .5),
    changed_ocean_distance_from_raster_land_px_p95: quantile(distances, .95),
    changed_ocean_distance_from_raster_land_px_max: distances.reduce((maximum, value) => Math.max(maximum, value), 0),
    scope: 'Actual source-relative fill-only RGB changes on existing v018 land-mask water/hole pixels. 1:50m rasterization mismatch is a separate observation, not inferred water color or a survey shoreline claim.'};
}

/** Detect partial coverage along internal tessellation edges independently of
 * terrain-detail sampling, which intentionally erodes antialiased boundaries.
 * Both coverage and true outer/hole edges are actual native Canvas rasters.
 */
export function interiorCoveragePixels(coverage, nativeEdgeMask, width, height, {edgeExclusion = 4} = {}) {
  validImage(coverage,width,height);validImage(nativeEdgeMask,width,height);
  if(!Number.isFinite(edgeExclusion)||edgeExclusion<1||edgeExclusion>16)throw Error('TERRAIN_SEAM_POLICY_INVALID');
  const inverse=new Uint8ClampedArray(coverage.length);
  for(let pixel=0;pixel<width*height;pixel++)if(!nativeEdgeMask[pixel*4+3])inverse[pixel*4+3]=255;
  const distance=interiorDistance(inverse,width,height), examples=[];
  let partial=0,maximumDistance=0;
  for(let pixel=0;pixel<width*height;pixel++){
    const alpha=coverage[pixel*4+3];
    if(alpha>0&&alpha<250&&distance[pixel]>edgeExclusion){
      partial++;maximumDistance=Math.max(maximumDistance,distance[pixel]);
      if(examples.length<12)examples.push({x:pixel%width,y:Math.floor(pixel/width),alpha,distance_from_native_edge_px:distance[pixel]});
    }
  }
  return {partial_coverage_away_from_native_boundary_pixels:partial,
    maximum_distance_from_native_edge_px:maximumDistance,native_edge_exclusion_px:edgeExclusion,examples,
    scope:'Actual opaque native-polygon coverage raster vs actual verified outer/hole edge raster. Finds internal AA/T-junction coverage seams that terrain interior erosion would omit.'};
}

/** Actual inherited marker/text ink against a matching native geographic draw
 * with marker heads/text suppressed. No OCR or fabricated labels are used.
 */
export function annotationContrastPixels(map,overlay,box,width,height,{minimumDifference=2/255}={}) {
  validImage(map,width,height);validImage(overlay,width,height);
  if(!box||![box.x,box.y,box.width,box.height].every(Number.isFinite)||box.width<=0||box.height<=0)throw Error('TERRAIN_ANNOTATION_BOX_INVALID');
  const left=Math.max(0,Math.floor(box.x)-4),right=Math.min(width,Math.ceil(box.x+box.width)+4),top=Math.max(0,Math.floor(box.y)-4),bottom=Math.min(height,Math.ceil(box.y+box.height)+4);
  const deltas=[],luma=[];
  for(let y=top;y<bottom;y++)for(let x=left;x<right;x++){
    const index=(y*width+x)*4,delta=Math.hypot(map[index]-overlay[index],map[index+1]-overlay[index+1],map[index+2]-overlay[index+2])/(255*Math.sqrt(3));
    if(delta>minimumDifference){deltas.push(delta);luma.push(Math.abs(pixelLuminance(map,index)-pixelLuminance(overlay,index)));}
  }
  return {measured_ink_pixels:deltas.length,box_pixels:(right-left)*(bottom-top),median_rgb_contrast:quantile(deltas,.5),p90_rgb_contrast:quantile(deltas,.9),
    median_luminance_contrast:quantile(luma,.5),p90_luminance_contrast:quantile(luma,.9),
    scope:'Actual original marker-head/text RGBA difference vs matching native geometry-only control, including local outline/shadow; no authored or OCR replacement labels.'};
}

export function evaluateTerrainPixels({primary, secondary, core, secondaryCore, halo,
  edgeContrast, containment, off, secondaryRequired = true}) {
  const failures = [], check = (condition, code) => {if (!condition) failures.push(code);};
  check(primary?.interior_samples >= 32, 'PRIMARY_NOT_MEASURABLE');
  check(primary?.median_rgb_contrast >= .06 && primary.changed_fraction >= .9, 'PRIMARY_COLOR_NOT_VISIBLE');
  check(primary?.luminance?.W3C.expected_local_luminance_scale >= .80
    && primary.luminance.W3C.expected_local_luminance_scale <= 1
    && primary.luminance.W3C.mean_absolute_error_against_scaled_source <= .012, 'SOURCE_LUMINANCE_CHANGED');
  check(primary?.detail?.length >= 3 && primary.detail.every(row => row.W3C.source_texture_available
    && row.W3C.retention >= .80 && row.W3C.retention <= 1.10
    && row.W3C.normalized_retention_against_expected_local_scale >= .97
    && row.W3C.normalized_retention_against_expected_local_scale <= 1.05
    && row.W3C.correlation >= .97), 'TERRAIN_DETAIL_ATTENUATED');
  check(core?.cross_sections > 0 && core.width_px_median >= 6 && core.width_px_median <= 12, 'PRIMARY_CORE_NOT_READABLE');
  check(edgeContrast?.cross_sections > 0 && edgeContrast.median_luminance_contrast >= .12, 'BOUNDARY_CONTRAST_WEAK');
  const haloBounded = halo?.nearest_native_edge ? halo.nearest_native_edge.measured_pixels > 0
    && halo.nearest_native_edge.distance_px_max <= 16
    : halo?.sampling_limit_hits === 0 && halo?.reach_from_native_edge_px_median <= 16;
  check(halo?.cross_sections > 0 && haloBounded && halo.maximum_alpha <= .40,
    'HALO_UNBOUNDED_OR_DOMINANT');
  if (secondaryRequired) {
    check(secondary?.interior_samples >= 32 && secondary.median_rgb_contrast >= .025, 'SECONDARY_NOT_VISIBLE');
    check(secondary?.luminance?.W3C.expected_local_luminance_scale >= .80
      && secondary.luminance.W3C.expected_local_luminance_scale <= 1
      && secondary.luminance.W3C.mean_absolute_error_against_scaled_source <= .012, 'SECONDARY_SOURCE_LUMINANCE_CHANGED');
    check(secondary?.detail?.length >= 3 && secondary.detail.every(row => row.W3C.source_texture_available
      && row.W3C.retention >= .80 && row.W3C.retention <= 1.10
      && row.W3C.normalized_retention_against_expected_local_scale >= .97
      && row.W3C.normalized_retention_against_expected_local_scale <= 1.05
      && row.W3C.correlation >= .97), 'SECONDARY_TERRAIN_DETAIL_ATTENUATED');
    check(secondary?.median_rgb_contrast < primary?.median_rgb_contrast, 'COLOR_HIERARCHY_REVERSED');
    check(secondaryCore?.cross_sections > 0 && secondaryCore.width_px_median >= 2
      && secondaryCore.width_px_median < core?.width_px_median, 'BOUNDARY_HIERARCHY_REVERSED');
  }
  check(containment?.filled_pixels > 0 && containment.outside_native_fill_pixels === 0, 'COASTLINE_OR_HOLE_LEAK');
  check(off?.identical === true, 'OFF_V023_BASELINE_CHANGED');
  return {passed: failures.length === 0, failures, GPU: 'NOT_RUN', production_frame_render: 'NOT_RUN',
    visual_quality_acceptance: 'NOT_RUN', scope: 'CPU captured-pixel admission; visual target review and actual NVIDIA output acceptance are separate.'};
}
