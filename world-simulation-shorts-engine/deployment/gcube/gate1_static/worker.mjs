/** Single frame release worker; imports the original factory unchanged. */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {admission} from './capability.mjs';
import {classify, createDiagnostic, redact} from './diagnostic.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const bundle = process.env.STATIC_PROOF_BUNDLE || path.join(here, 'bundle');
const args = process.argv.slice(2);
const mode = args[0];
if (!['probe', 'proof', 'validate-software', 'validate-probe-software'].includes(mode) || args.length !== 2) throw Error('WORKER_ARGUMENT_INVALID');
// Public server never accepts this CLI-only validation mode.
const softwareTest = mode === 'validate-software' || mode === 'validate-probe-software';
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
const deadline = setTimeout(() => {
  diagnostic.error_code = 'WORKER_TIMEOUT'; diagnostic.failed_stage = currentStage;
  diagnostic.capability_result = {result: 'FAIL', failures: ['WORKER_TIMEOUT']};
  record.set(currentStage, 'FAIL'); record.set('RESULT', 'FAIL');
  fs.mkdirSync(output, {recursive: true}); fs.writeFileSync(path.join(output, 'diagnostic.json'), JSON.stringify(diagnostic, null, 2));
  progress('WORKER_TIMEOUT', 'FAIL'); process.exit(124);
}, 150000);
const heartbeat = setInterval(() => progress('WORKER_HEARTBEAT'), 10000);
const backend = process.env.WORLD_ENGINE_GPU_PROFILE || 'egl';
const context = process.env.GATE1_ATTEMPT_CONTEXT ? JSON.parse(fs.readFileSync(process.env.GATE1_ATTEMPT_CONTEXT)) : {};
const record = createDiagnostic(backend, context);
let diagnostic = record.diagnostic;
Object.assign(diagnostic, {renderer_source_hash: plan.provenance.shaderHash, renderer_version: plan.provenance.rendererVersion,
  scene_hash: plan.provenance.sceneHash, data_hash: plan.provenance.dataHash, gis_hash: plan.provenance.gisHash});
let currentStage = 'START';
const enter = name => { currentStage = name; record.set(name, 'IN_PROGRESS'); progress(name); };
record.set('START', 'PASS');
record.set('ENVIRONMENT', 'PASS', context.environment || {uid: process.getuid(), gid: process.getgid(), HOME: process.env.HOME});
record.set('GRAPHICS_RUNTIME', context.graphics_runtime ? 'PASS' : 'NOT_RUN', context.graphics_runtime);
process.env.GATE1_CAPTURE_DIR = output;
if (mode === 'validate-probe-software') {
  process.env.WORLD_ENGINE_RENDER_MODE = 'cpu';
  process.env.WORLD_ENGINE_GPU_PROFILE = 'egl';
}
try {
  const launch = mode === 'validate-software' ? '/usr/bin/chromium' : path.join(here, 'browser_capture.py');
  enter('BROWSER_LAUNCH');
  browser = await chromium.launch({executablePath: launch, headless: true, timeout: 30000,
    args: ['--no-sandbox', '--disable-dev-shm-usage', ...(softwareTest ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : [])]});
  record.set('BROWSER_LAUNCH', 'PASS', {browser_version: browser.version()});
  enter('PAGE_CREATE');
  const page = await browser.newPage({viewport: {width: 1080, height: 1920}, deviceScaleFactor: 1});
  record.set('PAGE_CREATE', 'PASS');
  page.setDefaultTimeout(30000);
  const browserErrors = [];
  diagnostic.browser_errors = [];
  page.on('pageerror', error => { browserErrors.push('BROWSER_PAGE_ERROR'); diagnostic.browser_errors.push({name: error.name, message: redact(error.message), stack: redact(error.stack)}); });
  page.on('console', msg => { if (msg.type() === 'error') { browserErrors.push('BROWSER_CONSOLE_ERROR'); diagnostic.browser_errors.push({message: redact(msg.text())}); } else if (msg.text().startsWith('GATE1:')) progress(msg.text()); });
  enter('PAGE_LOAD');
  await page.goto(`http://127.0.0.1:${server.address().port}/`, {timeout: 30000});
  record.set('PAGE_LOAD', 'PASS');
  enter('WEBGL2_CREATE');
  const capability = await page.evaluate(() => {
    const canvas = document.getElementById('proof');
    const gl = canvas.getContext('webgl2', {alpha: false, antialias: false, preserveDrawingBuffer: true});
    if (!gl) return {webgl2: false, renderer: null, vendor: null, gl_vendor: 'NOT_RUN', gl_renderer: 'NOT_RUN', gl_version: 'NOT_RUN', actualPixelDraw: false};
    window.__gate1ProbeGL = gl;
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    const values = {webgl2: true, webglVersion: gl.getParameter(gl.VERSION), glslVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      debugRendererAvailable: !!debug, renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
      vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
      gl_vendor: gl.getParameter(gl.VENDOR), gl_renderer: gl.getParameter(gl.RENDERER), gl_version: gl.getParameter(gl.VERSION),
      maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE), maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
      maxTextureUnits: gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS), maxSamples: gl.getParameter(gl.MAX_SAMPLES),
      extensions: gl.getSupportedExtensions(), anisotropyAvailable: !!gl.getExtension('EXT_texture_filter_anisotropic')};
    return values;
  });
  diagnostic.capability = capability;
  record.set('WEBGL2_CREATE', capability.webgl2 ? 'PASS' : 'FAIL', {context_created: capability.webgl2});
  if (!capability.webgl2) throw Error('WEBGL2_REQUIRED');
  enter('GPU_IDENTITY');
  record.set('GPU_IDENTITY', capability.debugRendererAvailable ? 'PASS' : 'FAIL',
    {vendor: capability.vendor, renderer: capability.renderer, gl_vendor: capability.gl_vendor, gl_renderer: capability.gl_renderer, gl_version: capability.gl_version});
  enter('READPIXELS');
  Object.assign(capability, await page.evaluate(() => {
    const gl = window.__gate1ProbeGL;
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.clearColor(1, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.finish();
    const pixel = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    const error = gl.getError();
    return {pixel: Array.from(pixel), gl_error: error, actualPixelDraw: error === 0 && pixel[0] === 255 && pixel[1] === 0 && pixel[2] === 0 && pixel[3] === 255};
  }));
  record.set('READPIXELS', capability.actualPixelDraw ? 'PASS' : 'FAIL', {pixel: capability.pixel, gl_error: capability.gl_error});
  const capabilityResult = admission(capability, {softwareTest});
  diagnostic = {...diagnostic, schema_version: 2, purpose: 'GATE1_STATIC_PROOF', gpu_renderer: capability.renderer,
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
  if (capabilityResult.result === 'FAIL') {
    currentStage = ['GPU_IDENTITY_UNAVAILABLE', 'SOFTWARE_RENDERER_REJECTED', 'NVIDIA_RENDERER_REQUIRED', 'RTX4080S_REQUIRED'].includes(capabilityResult.failures[0]) ? 'GPU_IDENTITY' : 'READPIXELS';
    throw Error(capabilityResult.failures[0]);
  }
  progress('CAPABILITY', capabilityResult.result);
  if (mode !== 'probe' && mode !== 'validate-probe-software') {
    currentStage = 'PROOF_FRAME';
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
  record.set('RESULT', softwareTest ? 'SOFTWARE_TEST_ONLY' : 'PASS');
} catch (error) {
  const code = classify(error, currentStage, backend);
  diagnostic.error = {name: error.name, message: redact(error.message), stack: redact(error.stack)};
  diagnostic.failed_stage = currentStage;
  diagnostic.capability_result = {result: 'FAIL', failures: [code]};
  record.set(currentStage, 'FAIL'); record.set('RESULT', 'FAIL', {error_code: code});
  diagnostic.error_code = code;
  fs.mkdirSync(output, {recursive: true}); fs.writeFileSync(path.join(output, 'diagnostic.json'), JSON.stringify(diagnostic, null, 2));
  progress(code, 'FAIL'); process.exitCode = 1;
} finally {
  clearInterval(heartbeat); clearTimeout(deadline);
  if (browser) { let timer; await Promise.race([browser.close().catch(() => {}), new Promise(resolve => {timer = setTimeout(resolve, 5000);})]); clearTimeout(timer); }
  diagnostic.stages = record.diagnostic.stages;
  for (const stream of ['stdout', 'stderr']) {
    const filename = path.join(output, 'chromium.' + stream + '.log');
    diagnostic['chromium_' + stream] = fs.existsSync(filename) ? redact(fs.readFileSync(filename, 'utf8')) : '';
  }
  const processFile = path.join(output, 'chromium-process.json');
  diagnostic.chromium_process = fs.existsSync(processFile) ? JSON.parse(fs.readFileSync(processFile)) : {exit_code: 'UNKNOWN', signal: 'UNKNOWN'};
  fs.mkdirSync(output, {recursive: true}); fs.writeFileSync(path.join(output, 'diagnostic.json'), JSON.stringify(diagnostic, null, 2));
  await new Promise(resolve => server.close(resolve));
}
