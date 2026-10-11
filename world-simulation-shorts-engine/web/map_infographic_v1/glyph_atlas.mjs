/**
 * REBUILT glyph-only implementation (2026-10-12).
 * The original module bytes were unavailable. Preserved callers and the four
 * historical pinned-font measurements define this implementation's contract.
 * Canvas prepares measured alpha coverage only; the existing GPU draws text.
 */
const DEFAULT_FONT_FAMILY = 'Gate1Bold';
const DEFAULT_LINE_HEIGHT = 1.28;

function positive(value, name, unlimited = false) {
 if ((unlimited && value === Infinity) || (Number.isFinite(value) && value > 0)) return value;
 throw new TypeError(`GLYPH_${name}_MUST_BE_POSITIVE`);
}

function measuredInk(context, text) {
 const metrics = context.measureText(text);
 const ink = { advance: metrics.width, left: metrics.actualBoundingBoxLeft,
  right: metrics.actualBoundingBoxRight, ascent: metrics.actualBoundingBoxAscent,
  descent: metrics.actualBoundingBoxDescent };
 if (!Object.values(ink).every(Number.isFinite)) throw new Error('ACTUAL_GLYPH_METRICS_REQUIRED');
 return ink;
}

const inkWidth = ink => Math.max(0, Math.max(0, ink.left) + ink.right);

function measuredLines(context, text, maxWidth) {
 const segmenter = new Intl.Segmenter('ko', { granularity: 'grapheme' });
 const lines = [];
 for (const paragraph of text.split(/\r\n|\r|\n/u)) {
  let line = '';
  for (const { segment } of segmenter.segment(paragraph)) {
   const candidate = line + segment;
   if (line && inkWidth(measuredInk(context, candidate)) > maxWidth) {
    lines.push(line);
    line = segment;
   } else line = candidate;
  }
  lines.push(line);
 }
 return lines;
}

/** Synchronous actual-font measurement for the unchanged measured layout. */
export function createMeasuredGlyph(text, style = {}) {
 if (typeof text !== 'string') throw new TypeError('GLYPH_TEXT_MUST_BE_STRING');
 if (!globalThis.document?.createElement || !document.fonts) throw new Error('GLYPH_ATLAS_BROWSER_CANVAS_REQUIRED');
 const fontSize = positive(style.fontSize, 'FONT_SIZE');
 const lineHeight = positive(style.lineHeight ?? DEFAULT_LINE_HEIGHT, 'LINE_HEIGHT');
 const outlineRadius = style.outlineRadius ?? 0;
 if (!Number.isFinite(outlineRadius) || outlineRadius < 0) throw new TypeError('GLYPH_OUTLINE_RADIUS_MUST_BE_NONNEGATIVE');
 const maxWidth = positive(style.maxWidth ?? Infinity, 'MAX_WIDTH', true);
 const maxLines = positive(style.maxLines ?? Infinity, 'MAX_LINES', true);
 if (maxLines !== Infinity && !Number.isInteger(maxLines)) throw new TypeError('GLYPH_MAX_LINES_MUST_BE_INTEGER');
 const fontFamily = style.fontFamily ?? DEFAULT_FONT_FAMILY;
 if (fontFamily !== DEFAULT_FONT_FAMILY) throw new Error('PINNED_GLYPH_FONT_REQUIRED');
 const font = `${fontSize}px "${fontFamily}"`;
 const loaded = [...document.fonts].some(face => face.family.replace(/^['"]|['"]$/g, '') === fontFamily && face.status === 'loaded');
 if (!loaded || !document.fonts.check(font, text || '한')) throw new Error('PINNED_GLYPH_FONT_NOT_LOADED');

 const canvas = document.createElement('canvas');
 const context = canvas.getContext('2d', { willReadFrequently: true });
 if (!context) throw new Error('GLYPH_CANVAS_CONTEXT_REQUIRED');
 context.font = font;
 const lines = measuredLines(context, text, maxWidth);
 const measurements = lines.map(line => measuredInk(context, line));
 const padding = Math.ceil(outlineRadius) + 6;
 const ascent = Math.max(0, ...measurements.map(ink => ink.ascent));
 const descent = Math.max(0, ...measurements.map(ink => ink.descent));
 const lineStep = Math.max(fontSize * lineHeight, ascent + descent);
 const baselines = lines.map((_, index) => padding + ascent + index * lineStep);
 canvas.width = Math.max(1, Math.ceil(Math.max(0, ...measurements.map(inkWidth))) + padding * 2);
 canvas.height = Math.max(1, Math.ceil(ascent + descent + (lines.length - 1) * lineStep) + padding * 2);
 context.font = font;
 context.textBaseline = 'alphabetic';
 context.fillStyle = '#fff';
 lines.forEach((line, index) => context.fillText(line, padding + Math.max(0, measurements[index].left), baselines[index]));

 const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
 let alphaPixels = 0, x0 = canvas.width, y0 = canvas.height, x1 = -1, y1 = -1;
 for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
  if (pixels[(y * canvas.width + x) * 4 + 3] === 0) continue;
  alphaPixels++;
  x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
 }
 const alphaBounds = alphaPixels ? [x0, y0, x1 - x0 + 1, y1 - y0 + 1] : [0, 0, 0, 0];
 const inkDimensions = alphaBounds.slice(2);
 const alphaTouchesEdge = alphaPixels > 0 && (x0 === 0 || y0 === 0 || x1 === canvas.width - 1 || y1 === canvas.height - 1);
 const lineLimitExceeded = lines.length > maxLines;
 const fits = alphaPixels > 0 && !alphaTouchesEdge && !lineLimitExceeded &&
  inkDimensions[0] <= maxWidth && measurements.every(ink => inkWidth(ink) <= maxWidth);
 return { canvas, lines, fontSize, fontFamily, lineHeight, outlineRadius,
  atlasDimensions: [canvas.width, canvas.height], alphaBounds, alphaPixels,
  alphaTouchesEdge, inkDimensions, baselines, measuredInk: measurements, fits, lineLimitExceeded };
}
