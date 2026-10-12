/** Fixed supplied metric coverage, measured by the existing pinned-font atlas. */
import {assertEventIntent, freezeEventData} from './event_contract_v1.mjs';
import {createMeasuredGlyph} from './glyph_atlas.mjs';

export const EVENT_METRIC_V1_VERSION = 'METRIC_ANNOTATION_V1';
const rasters = new WeakMap();
const styleKeys = new Set(['fontSize', 'minFontSize', 'fontFamily', 'lineHeight', 'outlineRadius', 'maxWidth', 'maxLines']);
function positive(value, name) {
 if (!Number.isFinite(value) || value <= 0) throw Error(`EVENT_METRIC_${name}_POSITIVE_REQUIRED`);
 return value;
}
function styleRecord(given) {
 if (!given || typeof given !== 'object' || Array.isArray(given)) throw Error('EVENT_METRIC_STYLE_REQUIRED');
 if (Object.keys(given).some(key => !styleKeys.has(key))) throw Error('EVENT_METRIC_UNKNOWN_STYLE_FIELD');
 const fontSize = positive(given.fontSize, 'FONT_SIZE'), minFontSize = positive(given.minFontSize ?? fontSize, 'MIN_FONT_SIZE');
 if (fontSize < minFontSize) throw Error('EVENT_METRIC_SUPPLIED_FONT_BELOW_MINIMUM');
 if (given.maxLines !== undefined && given.maxLines !== 1) throw Error('EVENT_METRIC_SINGLE_LINE_REQUIRED');
 const outlineRadius = given.outlineRadius ?? 0;
 if (!Number.isFinite(outlineRadius) || outlineRadius < 0) throw Error('EVENT_METRIC_OUTLINE_RADIUS_REQUIRED');
 return {fontSize, minFontSize, fontFamily: given.fontFamily ?? 'Gate1Bold',
  lineHeight: positive(given.lineHeight ?? 1.28, 'LINE_HEIGHT'), outlineRadius,
  maxWidth: positive(given.maxWidth, 'MAX_WIDTH'), maxLines: 1};
}

/** One full native measurement. No prefix atlas, font resize or re-centering. */
export function compileMetricAnnotation(intent, {style} = {}) {
 const data = assertEventIntent(intent);
 if (!data.metric) throw Error('EVENT_METRIC_PRIMITIVE_REQUIRED');
 const s = styleRecord(style), text = `${data.metric.display_value} ${data.metric.unit}`;
 const glyph = createMeasuredGlyph(text, s);
 if (glyph.lines.length !== 1 || glyph.lines[0] !== text) throw Error('EVENT_METRIC_UNEXPECTED_WRAP');
 if (!glyph.fits || glyph.alphaTouchesEdge || glyph.lineLimitExceeded) throw Error('EVENT_METRIC_CLIPPED_OR_UNREADABLE');
 const context = glyph.canvas.getContext('2d', {willReadFrequently: true});
 if (!context) throw Error('EVENT_METRIC_CANVAS_CONTEXT_REQUIRED');
 const fullRgba = new Uint8ClampedArray(context.getImageData(0, 0, glyph.canvas.width, glyph.canvas.height).data);
 const segments = [...new Intl.Segmenter('ko', {granularity: 'grapheme'}).segment(text)].map(item => item.segment);
 // Native full coverage is partitioned into ordered grapheme bands. Prefix
 // advance measurements use this same font context, not another glyph engine.
 const origin = Math.ceil(glyph.outlineRadius) + 6 + Math.max(0, glyph.measuredInk[0].left);
 const boundaries = [0]; let prefix = '';
 for (let index = 0; index < segments.length - 1; index++) {
  prefix += segments[index];
  const advance = context.measureText(prefix).width;
  if (!Number.isFinite(advance)) throw Error('EVENT_METRIC_PREFIX_ADVANCE_REQUIRED');
  const boundary = Math.max(0, Math.min(glyph.canvas.width, origin + advance));
  if (boundary < boundaries.at(-1)) throw Error('EVENT_METRIC_NONMONOTONE_GRAPHEME_ADVANCE');
  boundaries.push(boundary);
 }
 boundaries.push(glyph.canvas.width);
 const primitive = freezeEventData({version: EVENT_METRIC_V1_VERSION, intent: data, text,
  displayValue: data.metric.display_value, unit: data.metric.unit, anchor: [...data.metric.anchor],
  style: s, dataMode: data.data_mode, productionEligible: data.data_mode === 'PRODUCTION',
  graphemes: segments, coverageBoundariesPixels: boundaries,
  atlasDimensions: [...glyph.atlasDimensions], alphaBounds: [...glyph.alphaBounds],
  inkDimensions: [...glyph.inkDimensions], baselines: [...glyph.baselines],
  measuredInk: structuredClone(glyph.measuredInk), alphaPixels: glyph.alphaPixels,
  fullReservation: true, glyphOwnership: 'EXISTING_PINNED_MEASURED_GLYPH'});
 rasters.set(primitive, fullRgba);
 return primitive;
}

/** Sequential alpha coverage over full-size native glyph positions and baseline. */
export function evaluateMetricAnnotation(primitive, visibleFraction) {
 const source = rasters.get(primitive);
 if (primitive?.version !== EVENT_METRIC_V1_VERSION || !source) throw Error('EVENT_METRIC_COMPILED_BROWSER_PRIMITIVE_REQUIRED');
 if (!Number.isFinite(visibleFraction) || visibleFraction < 0 || visibleFraction > 1)
  throw Error('EVENT_METRIC_FRACTION_RANGE_REQUIRED');
 const [width, height] = primitive.atlasDimensions;
 const graphemeAlphas = primitive.graphemes.map((_, index) => Math.max(0, Math.min(1, visibleFraction * primitive.graphemes.length - index)));
 const pixels = new Uint8ClampedArray(source.length);
 if (visibleFraction === 1) pixels.set(source);
 else if (visibleFraction !== 0) {
  let band = 0;
  for (let x = 0; x < width; x++) {
   while (band + 1 < graphemeAlphas.length && x + .5 >= primitive.coverageBoundariesPixels[band + 1]) band++;
   const opacity = graphemeAlphas[band];
   if (opacity === 0) continue;
   for (let y = 0; y < height; y++) {
    const index = (y * width + x) * 4, alpha = Math.round(source[index + 3] * opacity);
    if (alpha === 0) continue;
    pixels[index] = source[index]; pixels[index + 1] = source[index + 1]; pixels[index + 2] = source[index + 2]; pixels[index + 3] = alpha;
   }
  }
 }
 const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
 const context = canvas.getContext('2d', {willReadFrequently: true});
 if (!context) throw Error('EVENT_METRIC_CANVAS_CONTEXT_REQUIRED');
 context.putImageData(new ImageData(pixels, width, height), 0, 0);
 return Object.freeze({version: EVENT_METRIC_V1_VERSION, canvas, text: primitive.text,
  displayValue: primitive.displayValue, unit: primitive.unit, anchor: primitive.anchor,
  atlasDimensions: primitive.atlasDimensions, alphaBounds: primitive.alphaBounds, baselines: primitive.baselines,
  visibleFraction, visibleGlyphCount: graphemeAlphas.filter(alpha => alpha > 0).length,
  graphemeAlphas: Object.freeze(graphemeAlphas), fullCoverage: visibleFraction === 1,
  fullReservation: true, dataMode: primitive.dataMode, productionEligible: primitive.productionEligible});
}
