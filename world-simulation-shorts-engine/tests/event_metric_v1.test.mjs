import test, {before, after} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const engine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.dirname(engine), require = createRequire(path.join(repo, 'cinematic-world-map/package.json'));
let server, browser, page;
before(async () => {
 assert.equal(require('playwright/package.json').version, '1.62.1');
 server = spawn('/usr/bin/python3', ['-B', path.join(engine, 'recovery/v5/serve.py'), '--port', '0'], {stdio: ['ignore', 'pipe', 'pipe']});
 let stderr = ''; server.stderr.on('data', chunk => {stderr += chunk;});
 const url = await new Promise((resolve, reject) => {
  const lines = createInterface({input: server.stdout});
  const timer = setTimeout(() => {lines.close(); reject(Error('METRIC_TEST_SERVER_START_TIMEOUT'));}, 15000);
  server.once('exit', code => {clearTimeout(timer); reject(Error(`METRIC_TEST_SERVER_EXIT_${code}: ${stderr}`));});
  lines.on('line', line => { try {const message = JSON.parse(line); if (message.event === 'READY') {clearTimeout(timer); lines.close(); resolve(message.url);}} catch {} });
 });
 browser = await require('playwright').chromium.launch({executablePath: '/usr/bin/chromium', headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--disable-dev-shm-usage']});
 assert.equal(browser.version(), '154.0.8037.57');
 page = await browser.newPage();
 // Load only the JSON document, not the V5 harness or map Renderer.
 await page.goto(url + '/runtime-config.json');
 await page.evaluate(async () => {
  const face = new FontFace('Gate1Bold', 'url("/static/fonts/NotoSansCJKkr-Bold.otf")');
  await face.load(); document.fonts.add(face); await document.fonts.ready;
  window.metricModule = await import('/modules/event_metric_v1.mjs');
  window.eventContract = await import('/modules/event_contract_v1.mjs');
  window.glyphModule = await import('/modules/glyph_atlas.mjs');
  window.metricInput = (display_value = '9.25', unit = 'km') => ({data_mode: 'SYNTHETIC_TEST', metric: {display_value, unit, anchor: [2, 3],
   source: {source_type: 'SYNTHETIC_TEST', source_reference: 'fixture://native-metric-font', verification_status: 'SYNTHETIC_TEST'}}});
  window.metricStyle = () => ({fontSize: 36, minFontSize: 36, fontFamily: 'Gate1Bold', lineHeight: 1.28, outlineRadius: 1, maxWidth: 500, maxLines: 1});
  window.rgba = canvas => [...canvas.getContext('2d', {willReadFrequently: true}).getImageData(0, 0, canvas.width, canvas.height).data];
 });
});
after(async () => {if (browser) await browser.close(); if (server && server.exitCode === null) server.kill('SIGTERM');});

test('full numeric/unit native pinned-font RGBA, measurement and baseline match exactly', async () => {
 const result = await page.evaluate(() => {
  const i = eventContract.compileEventIntent(metricInput()), style = metricStyle();
  const p = metricModule.compileMetricAnnotation(i, {style}), full = metricModule.evaluateMetricAnnotation(p, 1);
  const native = glyphModule.createMeasuredGlyph('9.25 km', style);
  return {samePixels: JSON.stringify(rgba(full.canvas)) === JSON.stringify(rgba(native.canvas)),
   dims: full.atlasDimensions, nativeDims: native.atlasDimensions, bounds: full.alphaBounds, nativeBounds: native.alphaBounds,
   baseline: full.baselines, nativeBaseline: native.baselines, text: full.text, value: full.displayValue, unit: full.unit, count: full.visibleGlyphCount};
 });
 assert.equal(result.samePixels, true); assert.deepEqual(result.dims, result.nativeDims); assert.deepEqual(result.bounds, result.nativeBounds);
 assert.deepEqual(result.baseline, result.nativeBaseline); assert.equal(result.text, '9.25 km'); assert.equal(result.value, '9.25'); assert.equal(result.unit, 'km'); assert.equal(result.count, 7);
});
test('actual Korean unit coverage uses the same native glyph atlas with no fallback or new font engine', async () => {
 const result = await page.evaluate(() => {
  const p = metricModule.compileMetricAnnotation(eventContract.compileEventIntent(metricInput('12', '킬로미터')), {style: metricStyle()});
  const out = metricModule.evaluateMetricAnnotation(p, 1), native = glyphModule.createMeasuredGlyph('12 킬로미터', metricStyle());
  return {same: JSON.stringify(rgba(out.canvas)) === JSON.stringify(rgba(native.canvas)), glyphs: p.graphemes, dims: p.atlasDimensions,
   source: p.glyphOwnership, touches: native.alphaTouchesEdge};
 });
 assert.equal(result.same, true); assert.deepEqual(result.glyphs, ['1', '2', ' ', '킬', '로', '미', '터']);
 assert.equal(result.source, 'EXISTING_PINNED_MEASURED_GLYPH'); assert.equal(result.touches, false);
});
test('sequential grapheme alpha leaves unit last and reserves fixed dimensions/baseline throughout', async () => {
 const result = await page.evaluate(() => {
  const p = metricModule.compileMetricAnnotation(eventContract.compileEventIntent(metricInput()), {style: metricStyle()});
  const outputs = [0, 1 / 7, 2.5 / 7, 5 / 7, 6.5 / 7, 1].map(f => {
   const out = metricModule.evaluateMetricAnnotation(p, f);
   return {f, alphas: out.graphemeAlphas, count: out.visibleGlyphCount, dims: out.atlasDimensions, baseline: out.baselines, value: out.displayValue, unit: out.unit,
    zero: rgba(out.canvas).every(channel => channel === 0)};
  }); return {outputs, dims: p.atlasDimensions, baseline: p.baselines};
 });
 assert.equal(result.outputs[0].zero, true); assert.deepEqual(result.outputs[1].alphas, [1, 0, 0, 0, 0, 0, 0]);
 assert.deepEqual(result.outputs[2].alphas, [1, 1, .5, 0, 0, 0, 0]);
 assert.deepEqual(result.outputs[3].alphas, [1, 1, 1, 1, 1, 0, 0]);
 assert.deepEqual(result.outputs[4].alphas, [1, 1, 1, 1, 1, 1, .5]);
 for (const out of result.outputs) {assert.deepEqual(out.dims, result.dims); assert.deepEqual(out.baseline, result.baseline); assert.equal(out.value, '9.25'); assert.equal(out.unit, 'km');}
});
test('all full native alpha coverage is partitioned without clipping, missing pixels or unexpected wrap', async () => {
 const result = await page.evaluate(() => {
  const p = metricModule.compileMetricAnnotation(eventContract.compileEventIntent(metricInput('123.456', 'm²')), {style: metricStyle()});
  const zero = metricModule.evaluateMetricAnnotation(p, 0), full = metricModule.evaluateMetricAnnotation(p, 1);
  const native = glyphModule.createMeasuredGlyph(p.text, metricStyle());
  return {fullSame: JSON.stringify(rgba(full.canvas)) === JSON.stringify(rgba(native.canvas)), boundaries: p.coverageBoundariesPixels,
   width: p.atlasDimensions[0], lineCount: native.lines.length, fits: native.fits, alphaEdge: native.alphaTouchesEdge,
   zeroPixels: rgba(zero.canvas).every(v => v === 0)};
 });
 assert.equal(result.fullSame, true); assert.equal(result.lineCount, 1); assert.equal(result.fits, true); assert.equal(result.alphaEdge, false);
 assert.equal(result.zeroPixels, true); assert.equal(result.boundaries[0], 0); assert.equal(result.boundaries.at(-1), result.width);
 assert(result.boundaries.every((v, i) => i === 0 || v >= result.boundaries[i - 1]));
});
test('random frame access and repeated full Hold remain identical after returned canvas mutation', async () => {
 const result = await page.evaluate(() => {
  const input = metricInput(), style = metricStyle(), original = JSON.stringify({input, style});
  const p = metricModule.compileMetricAnnotation(eventContract.compileEventIntent(input), {style});
  const first = rgba(metricModule.evaluateMetricAnnotation(p, 1).canvas), middle = rgba(metricModule.evaluateMetricAnnotation(p, .5).canvas);
  for (const f of [.9, 0, .3, 1, .1]) metricModule.evaluateMetricAnnotation(p, f);
  const modified = metricModule.evaluateMetricAnnotation(p, 1); modified.canvas.getContext('2d').clearRect(0, 0, ...p.atlasDimensions);
  return {sameHold: JSON.stringify(first) === JSON.stringify(rgba(metricModule.evaluateMetricAnnotation(p, 1).canvas)),
   sameMiddle: JSON.stringify(middle) === JSON.stringify(rgba(metricModule.evaluateMetricAnnotation(p, .5).canvas)),
   fixed: JSON.stringify({input, style}) === original, frozen: Object.isFrozen(p) && Object.isFrozen(p.baselines)};
 });
 assert.deepEqual(result, {sameHold: true, sameMiddle: true, fixed: true, frozen: true});
});
test('grapheme segmentation treats a combining mark as one reveal unit', async () => {
 const result = await page.evaluate(() => {
  const p = metricModule.compileMetricAnnotation(eventContract.compileEventIntent(metricInput('3', 'e\u0301')), {style: metricStyle()});
  return p.graphemes;
 });
 assert.deepEqual(result, ['3', ' ', 'e\u0301']);
});
test('wrapping, invalid profile, unsupported font, fractions and forged serialized primitive fail closed', async () => {
 const errors = await page.evaluate(() => {
  const intent = eventContract.compileEventIntent(metricInput()), style = metricStyle(), result = [];
  const attempts = [() => metricModule.compileMetricAnnotation(intent),
   () => metricModule.compileMetricAnnotation(intent, {style: {...style, maxWidth: 20}}),
   () => metricModule.compileMetricAnnotation(intent, {style: {...style, fontSize: 35}}),
   () => metricModule.compileMetricAnnotation(intent, {style: {...style, maxLines: 2}}),
   () => metricModule.compileMetricAnnotation(intent, {style: {...style, fontFamily: 'Arial'}}),
   () => metricModule.compileMetricAnnotation(intent, {style: {...style, arbitrary: 1}})];
  const p = metricModule.compileMetricAnnotation(intent, {style});
  for (const f of [-.01, 1.01, NaN, Infinity]) attempts.push(() => metricModule.evaluateMetricAnnotation(p, f));
  attempts.push(() => metricModule.evaluateMetricAnnotation(JSON.parse(JSON.stringify(p)), 1));
  for (const attempt of attempts) {try {attempt(); result.push('NO_ERROR');} catch (error) {result.push(error.message);}}
  return result;
 });
 assert.equal(errors.length, 11); assert(errors.every(message => message !== 'NO_ERROR'));
 assert(errors.includes('EVENT_METRIC_UNEXPECTED_WRAP')); assert(errors.includes('EVENT_METRIC_SUPPLIED_FONT_BELOW_MINIMUM'));
 assert(errors.includes('PINNED_GLYPH_FONT_REQUIRED')); assert(errors.includes('EVENT_METRIC_COMPILED_BROWSER_PRIMITIVE_REQUIRED'));
});
test('metric compilation keeps production versus explicit synthetic provenance unchanged', async () => {
 const result = await page.evaluate(() => {
  const data = metricInput(); data.data_mode = 'PRODUCTION'; data.metric.source = {source_type: 'VERIFIED_DATA_RECORD', source_reference: 'fixture://source-proof', verification_status: 'VERIFIED'};
  const intent = eventContract.compileEventIntent(data), p = metricModule.compileMetricAnnotation(intent, {style: metricStyle()});
  const out = metricModule.evaluateMetricAnnotation(p, 1);
  data.metric.source.verification_status = 'UNVERIFIED'; let blocked = false;
  try {eventContract.compileEventIntent(data);} catch {blocked = true;}
  return {mode: out.dataMode, eligible: out.productionEligible, source: p.intent.metric.source.source_reference, value: out.displayValue, unit: out.unit, blocked};
 });
 assert.deepEqual(result, {mode: 'PRODUCTION', eligible: true, source: 'fixture://source-proof', value: '9.25', unit: 'km', blocked: true});
});
