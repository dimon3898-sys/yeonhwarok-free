/** Single frame release worker; imports the original factory unchanged. */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {admission} from './capability.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const bundle = process.env.STATIC_PROOF_BUNDLE || path.join(here, 'bundle');
const args = process.argv.slice(2);
const mode = args[0];
if (!['probe', 'proof', 'validate-software'].includes(mode) || args.length !== 2) throw Error('WORKER_ARGUMENT_INVALID');
// Public server never accepts this CLI-only validation mode.
const softwareTest = mode === 'validate-software';
const output = path.resolve(args[1]);
const started = Date.now();
const progress = (stage, result = 'IN_PROGRESS') => console.log(JSON.stringify({stage, result, elapsed_seconds: (Date.now() - started) / 1000}));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const manifest = JSON.parse(fs.readFileSync(path.join(bundle, 'manifest.json')));
const planBytes = fs.readFileSync(path.join(bundle, 'compiled-plan.json'));
const plan = JSON.parse(planBytes);
for (const row of manifest.files) {
  const bytes = fs.readFileSync(path.join(bundle, row.file));
  if (bytes.length !== row.bytes || sha(bytes) !== row.sha256) throw Error('FROZEN_SOURCE_INTEGRITY_FAILED');
}
progress('SOURCE_FROZEN', 'PASS');
const require = createRequire(process.env.STATIC_PROOF_PLAYWRIGHT_PACKAGE || path.join(here, 'package.json'));
const {chromium} = require('playwright');
const mappings = new Map(manifest.routes.map(r => [r.url, r.file]));
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost').pathname;
  if (url === '/') { res.setHeader('Content-Type', 'text/html'); res.end('<!doctype html><canvas id="proof"></canvas>'); return; }
  if (url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (url === '/plan.json') { res.setHeader('Content-Type', 'application/json'); res.end(planBytes); return; }
  const file = mappings.get(url);
  if (!file) { res.writeHead(404); res.end(); return; }
  const mime = file.endsWith('.png') ? 'image/png' : file.endsWith('.jpg') ? 'image/jpeg' : file.endsWith('.otf') ? 'font/otf' : 'text/javascript';
  res.setHeader('Content-Type', mime);
  fs.createReadStream(path.join(bundle, file)).pipe(res);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
const deadline = setTimeout(() => { progress('WORKER_TIMEOUT', 'FAIL'); process.exit(124); }, 150000);
const heartbeat = setInterval(() => progress('WORKER_HEARTBEAT'), 10000);
let diagnostic;
try {
  const launch = softwareTest ? '/usr/bin/chromium' : path.join(here, 'chromium_wrapper.py');
  progress('BROWSER_START');
  browser = await chromium.launch({executablePath: launch, headless: true, timeout: 30000,
    args: ['--no-sandbox', '--disable-dev-shm-usage', ...(softwareTest ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : [])]});
  const page = await browser.newPage({viewport: {width: 1080, height: 1920}, deviceScaleFactor: 1});
  page.setDefaultTimeout(30000);
  const browserErrors = [];
  page.on('pageerror', () => browserErrors.push('BROWSER_PAGE_ERROR'));
  page.on('console', msg => { if (msg.type() === 'error') browserErrors.push('BROWSER_CONSOLE_ERROR'); else if (msg.text().startsWith('GATE1:')) progress(msg.text()); });
  await page.goto(`http://127.0.0.1:${server.address().port}/`, {timeout: 30000});
  const capability = await page.evaluate(() => {
    const canvas = document.getElementById('proof');
    const gl = canvas.getContext('webgl2', {alpha: false, antialias: false, preserveDrawingBuffer: true});
    if (!gl) return {webgl2: false, renderer: null, actualPixelDraw: false};
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    const values = {webgl2: true, webglVersion: gl.getParameter(gl.VERSION), glslVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      debugRendererAvailable: !!debug, renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
      vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
      maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE), maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
      maxTextureUnits: gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS), maxSamples: gl.getParameter(gl.MAX_SAMPLES),
      extensions: gl.getSupportedExtensions(), anisotropyAvailable: !!gl.getExtension('EXT_texture_filter_anisotropic')};
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.clearColor(1, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.finish();
    const pixel = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    values.pixel = Array.from(pixel); values.actualPixelDraw = gl.getError() === 0 && pixel[0] === 255 && pixel[1] === 0 && pixel[2] === 0 && pixel[3] === 255;
    return values;
  });
  const capabilityResult = admission(capability, {softwareTest});
  diagnostic = {schema_version: 1, purpose: 'GATE1_STATIC_PROOF', gpu_renderer: capability.renderer,
    webgl_version: capability.webglVersion || 'UNKNOWN', output_resolution: [1080, 1920], format: 'lossless PNG',
    scene_hash: plan.provenance.sceneHash, gis_hash: plan.provenance.gisHash, data_hash: plan.provenance.dataHash,
    compiled_plan_hash: sha(planBytes), renderer_source_hash: plan.provenance.shaderHash,
    renderer_version: plan.provenance.rendererVersion, shader_version: manifest.shader_version,
    theme_version: manifest.theme_version, theme_hash: plan.provenance.themeHash,
    font_version: plan.assets.font.version, font_hash: plan.provenance.fontHash, seed: plan.seed,
    render_timestamp: 'NOT_RUN', render_duration_ms: 'UNKNOWN', peak_memory: 'UNKNOWN', capability, capability_result: capabilityResult,
    runtime_profile: softwareTest ? 'SOFTWARE_TEST_ONLY' : 'GPU_REQUIRED_RTX4080S',
    selected_gpu_backend: process.env.WORLD_ENGINE_GPU_PROFILE || 'egl',
    final_approval: 'USER_PENDING', gpu_visual_quality: 'NOT_EVALUATED', frame_count: 0};
  if (capabilityResult.result === 'FAIL') throw Error(capabilityResult.failures[0]);
  progress('CAPABILITY', capabilityResult.result);
  if (mode !== 'probe') {
    const timestamp = new Date().toISOString(); const renderStart = Date.now();
    const result = await page.evaluate(async () => {
      const module = await import('/static/map_infographic_v1/renderer.mjs');
      if (module.createProofPreview !== module.createProofFinal) throw Error('RENDER_FACTORY_MISMATCH');
      const plan = await fetch('/plan.json').then(r => r.json());
      const renderer = await module.createProofFinal({canvas: document.getElementById('proof'), plan, width: 1080, height: 1920});
      try { const png = renderer.render(); return {png, evidence: renderer.evidence}; } finally { renderer.dispose(); }
    });
    if (browserErrors.length) throw Error(browserErrors[0]);
    if (result.evidence.unmaskedRenderer !== capability.renderer) throw Error('RENDERER_IDENTITY_CHANGED');
    const png = Buffer.from(result.png.split(',')[1], 'base64');
    if (!png.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10])) || png.readUInt32BE(16) !== 1080 || png.readUInt32BE(20) !== 1920) throw Error('PNG_FORMAT_INVALID');
    Object.assign(diagnostic, {render_timestamp: timestamp, render_duration_ms: Date.now() - renderStart,
      renderer_frame_duration_ms: result.evidence.frameMilliseconds, png_sha256: sha(png), png_bytes: png.length,
      frame_count: 1, same_renderer_factory: true, renderer_evidence: result.evidence});
    fs.mkdirSync(output, {recursive: true});
    fs.writeFileSync(path.join(output, softwareTest ? 'SOFTWARE_TEST_ONLY.png' : 'SUEZ_STATIC_PROOF_RTX4080S.png'), png);
    progress('SINGLE_PNG', softwareTest ? 'SOFTWARE_TEST_ONLY' : 'PASS');
  }
  fs.mkdirSync(output, {recursive: true});
  fs.writeFileSync(path.join(output, 'diagnostic.json'), JSON.stringify(diagnostic, null, 2));
  progress('COMPLETE', softwareTest ? 'SOFTWARE_TEST_ONLY' : 'PASS');
} catch (error) {
  const safeCodes = /^(WEBGL2_REQUIRED|GPU_IDENTITY_UNAVAILABLE|SOFTWARE_RENDERER_REJECTED|NVIDIA_RENDERER_REQUIRED|RTX4080S_REQUIRED|ACTUAL_PIXEL_DRAW_FAILED|MAX_.*_INSUFFICIENT|TEXTURE_UNITS_INSUFFICIENT|MSAA_COVERAGE_CAPABILITY_INSUFFICIENT|BROWSER_PAGE_ERROR|BROWSER_CONSOLE_ERROR|PNG_FORMAT_INVALID|RENDERER_IDENTITY_CHANGED|RENDER_FACTORY_MISMATCH)$/;
  const code = safeCodes.test(error.message) ? error.message : /timeout/i.test(error.message) ? 'WORKER_TIMEOUT' : 'STATIC_PROOF_FAILED';
  diagnostic ||= {capability_result: {result: 'FAIL', failures: [code]}, peak_memory: 'UNKNOWN'};
  diagnostic.error_code = code;
  fs.mkdirSync(output, {recursive: true}); fs.writeFileSync(path.join(output, 'diagnostic.json'), JSON.stringify(diagnostic, null, 2));
  progress(code, 'FAIL'); process.exitCode = 1;
} finally {
  clearInterval(heartbeat); clearTimeout(deadline);
  if (browser) { let timer; await Promise.race([browser.close().catch(() => {}), new Promise(resolve => {timer = setTimeout(resolve, 5000);})]); clearTimeout(timer); }
  await new Promise(resolve => server.close(resolve));
}
