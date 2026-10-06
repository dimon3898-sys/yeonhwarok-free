#!/usr/bin/env node
/**
 * Owner-authenticated, real 375px browser checks for the deployment wrapper.
 * Existing engine, UI, renderer and ui_end_to_end.mjs remain untouched.
 *
 * node deployment/mobile_e2e.mjs --base ORIGIN --access-file PRIVATE_JSON \
 *   --mode plan-only --output NEW_DIRECTORY
 * node deployment/mobile_e2e.mjs --base ORIGIN --access-file PRIVATE_JSON \
 *   --mode approve --project PROJECT_ID --version v001 --output NEW_DIRECTORY
 * node deployment/mobile_e2e.mjs --base ORIGIN --access-file PRIVATE_JSON \
 *   --mode inspect --project PROJECT_ID --version v001 --output NEW_DIRECTORY
 *
 * approve explicitly approves an existing <=20-second QA plan, enqueues once,
 * closes the browser context, logs in again and restores the actual saved job.
 * It does not wait for the renderer, stop a process or retry a render request.
 * inspect never requests an engine mutation. Authentication/security probes
 * are recorded separately and never retain access values or cookie headers.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const flags = new Set(['help', 'self-test']);
const allowed = new Set(['help', 'self-test', 'base', 'project', 'version', 'access-file', 'output', 'mode', 'topic', 'duration', 'quality', 'pace', 'chromium']);
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i];
  if (!key.startsWith('--') || !allowed.has(key.slice(2))) throw new Error('Unknown command-line option. Use --help.');
  const name = key.slice(2);
  if (Object.hasOwn(args, name)) throw new Error(`Duplicate --${name}.`);
  if (flags.has(name)) args[name] = true;
  else {
    const value = process.argv[++i];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for --${name}.`);
    args[name] = value;
  }
}
if (args.help) {
  console.log('Use --base ORIGIN --access-file PRIVATE_FILE --output NEW_DIRECTORY --mode plan-only|approve|inspect. approve/inspect require --project PROJECT_ID [--version v001]. plan-only accepts --topic TEXT --duration 20 --quality FAST|HIGH|CINEMA --pace FAST_PLUS|FAST|NORMAL|CINEMATIC. The private (0600) access file contains a one-line code or JSON with password; its values/hashes are never logged. approve is bounded to existing <=20-second internal QA plans, returns after background-job reconnect, and never controls server processes. --self-test performs only local sanitizer/origin checks.');
  process.exit(0);
}

let confidential = [];
function redact(value) {
  if (typeof value === 'string') {
    let result = value;
    for (const secret of confidential) if (secret) result = result.split(secret).join('[redacted]');
    return result;
  }
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, /password|session_secret|scrypt|salt|authorization|cookie|token/i.test(key) ? '[redacted]' : redact(item)]));
  return value;
}
if (args['self-test']) {
  confidential = ['synthetic-private-value'];
  const result = redact({ nested: ['prefix synthetic-private-value suffix'], password: 'other', session_secret: 'other', ordinary: 'ok' });
  if (JSON.stringify(result).includes(confidential[0]) || result.password !== '[redacted]' || result.ordinary !== 'ok') throw new Error('Local redaction self-test failed.');
  const parsed = new URL('https://example.invalid');
  if (parsed.origin !== 'https://example.invalid') throw new Error('Local origin self-test failed.');
  console.log(JSON.stringify({ passed: true, scope: 'local redaction/origin checks only', browser_started: false, credential_file_read: false }));
  process.exit(0);
}

const mode = args.mode || 'inspect';
if (!['plan-only', 'approve', 'inspect'].includes(mode)) throw new Error('Mode must be plan-only, approve or inspect.');
if (!args.base || !args['access-file'] || !args.output) throw new Error('--base, --access-file and --output are required.');
const originURL = new URL(args.base);
if (!['http:', 'https:'].includes(originURL.protocol) || originURL.username || originURL.password || originURL.search || originURL.hash || !['', '/'].includes(originURL.pathname)) throw new Error('--base must be a plain HTTP(S) origin without credentials, query or path.');
const base = originURL.origin;
const pid = args.project;
if (mode !== 'plan-only' && !/^project_[a-z0-9_]{6,64}$/.test(pid || '')) throw new Error('approve/inspect require a valid --project.');
if (args.version && !/^v\d{3,}$/.test(args.version)) throw new Error('Invalid immutable version.');
const duration = Number(args.duration || 20);
if (mode === 'plan-only' && (!Number.isFinite(duration) || duration < 20 || duration > 3600)) throw new Error('New UI plans require duration20–3600.');
const quality = args.quality || 'HIGH';
const pace = args.pace || 'FAST_PLUS';
if (!['FAST', 'HIGH', 'CINEMA'].includes(quality) || !['FAST_PLUS', 'FAST', 'NORMAL', 'CINEMATIC'].includes(pace)) throw new Error('Invalid quality or pace.');
const output = path.resolve(args.output);
const accessPath = path.resolve(args['access-file']);
const accessStat = await fs.stat(accessPath);
if (!accessStat.isFile() || (accessStat.mode & 0o077)) throw new Error('The private access file must be a regular file with no group/world permissions (0600).');
let password;
try {
  const raw = (await fs.readFile(accessPath, 'utf8')).trim();
  password = raw.startsWith('{') ? JSON.parse(raw).password : raw;
  if (typeof password !== 'string' || password.length < 12) throw new Error();
} catch { throw new Error('The private access file is not a valid owner password fixture.'); }
confidential = [password, encodeURIComponent(password)];
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(output); // Existing evidence is never overwritten.
await fs.mkdir(path.join(output, 'downloads'));
const evidence = { schema_version: 1, started_at_utc: new Date().toISOString(), mode, base, access_file_path: accessPath, secret_values_recorded: false, viewport: { width: 375, height: 812 }, real_browser: true, real_phone_hardware: false, direct_listening: false, public_origin_reachability_proven_by_this_run: false, engine_requests: [], security_probes: [], browser_errors: [], screenshots: [], downloads: [], failures: [], process_control_actions: [] };
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
const save = (name, data) => fs.writeFile(path.join(output, name), JSON.stringify(redact(data), null, 2) + '\n', { flag: 'wx' });
function check(ok, message) { if (!ok) { evidence.failures.push(message); throw new Error(message); } }
const url = (route) => base + route;
const projectRoute = (project, suffix = '') => `/api/projects/${encodeURIComponent(project)}${suffix}`;
let browser, context, page;
let exitCode = 0;

async function createContext() {
  context = await browser.newContext({ viewport: evidence.viewport, deviceScaleFactor: 1, acceptDownloads: true });
  page = await context.newPage();
  page.on('pageerror', (error) => evidence.browser_errors.push({ message: redact(error.message), at_utc: new Date().toISOString() }));
  page.on('request', (request) => {
    const requestURL = new URL(request.url());
    if (request.method() !== 'POST' || !requestURL.pathname.startsWith('/api/')) return;
    const action = requestURL.pathname === '/api/projects' ? 'create_plan' : requestURL.pathname.split('/').pop();
    // Never save arbitrary bodies, headers, auth requests, cookies or passwords.
    let body;
    if (action === 'approve' || action === 'render') {
      const data = request.postDataJSON();
      body = { version: data?.version };
      if (action === 'approve' && data?.plan_hash) body.plan_hash = data.plan_hash;
    }
    evidence.engine_requests.push({ sequence: evidence.engine_requests.length, action, path: requestURL.pathname, ...(body ? { body } : {}), at_utc: new Date().toISOString() });
  });
}
async function screenshot(name, element) {
  check(!new URL(page.url()).pathname.startsWith('/auth/login'), 'Screenshots of a populated login form are prohibited.');
  await (element || page).screenshot({ path: path.join(output, name), fullPage: !element });
  evidence.screenshots.push(name);
}
async function jsonGET(route) {
  const response = await context.request.get(url(route));
  check(response.ok(), `HTTP ${response.status()} reading ${route.split('?')[0]}.`);
  const data = await response.json();
  const legitimateFailedJob = ['failed', 'error', 'interrupted', 'qc_failed'].includes(data.status) && (data.job_id || Object.hasOwn(data, 'progress'));
  check(!data.error || legitimateFailedJob, `The API reported a non-job error at ${route.split('?')[0]}.`);
  return data;
}
async function login(label) {
  await page.goto(url('/auth/login'), { waitUntil: 'domcontentloaded' });
  await page.locator('#owner-password').fill(password);
  const responseWaiter = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/auth/login', { timeout: 45000 });
  await page.locator('#owner-login-submit').click();
  const response = await responseWaiter;
  check([200, 303].includes(response.status()), 'Owner login failed; response body is intentionally not recorded.');
  await page.waitForSelector('#brief-form', { timeout: 45000 });
  const session = await jsonGET('/auth/session');
  check(session.authenticated === true, 'Owner login did not establish an authenticated session.');
  evidence[`login_${label}`] = { successful: true, response_status: response.status(), authenticated: true, input_value_recorded: false };
}
async function controls() {
  const result = await page.evaluate(() => ({
    pace: document.getElementById('pace')?.value,
    pace_options: [...document.getElementById('pace').options].map((x) => x.value),
    quality: document.getElementById('quality')?.value,
    quality_options: [...document.getElementById('quality').options].map((x) => x.value),
    tts: document.getElementById('tts').checked, subtitles: document.getElementById('subtitles').checked,
    bgm: document.getElementById('bgm').checked, sfx: document.getElementById('sfx').checked,
    duration_min: Number(document.getElementById('duration').min), duration_max: Number(document.getElementById('duration').max)
  }));
  evidence.default_controls = result;
  check(result.pace === 'FAST_PLUS' && JSON.stringify(result.pace_options.slice().sort()) === JSON.stringify(['FAST_PLUS', 'FAST', 'NORMAL', 'CINEMATIC'].sort()), 'Current four pace presets/default were not preserved.');
  check(JSON.stringify(result.quality_options.slice().sort()) === JSON.stringify(['FAST', 'HIGH', 'CINEMA'].sort()), 'Three quality controls are not present.');
  check(!result.tts && !result.subtitles && result.bgm && result.sfx, 'Default audio switches were changed.');
}
async function layout(label) {
  const result = await page.evaluate(() => ({ viewport_width: innerWidth, page_width: document.documentElement.scrollWidth, horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 1 }));
  evidence[`layout_${label}`] = result;
  check(!result.horizontal_overflow && result.viewport_width === 375, `375px layout overflow at ${label}.`);
}
async function securityProbes() {
  for (const route of ['/api/projects', '/download/project_auth_probe/v001/final/final.mp4', '/media/project_auth_probe/v001/final/final.mp4']) {
    const response = await context.request.get(url(route));
    evidence.security_probes.push({ action: 'unauthenticated_GET', path: route, status: response.status() });
    check(response.status() === 401, `Unauthenticated access was not blocked for ${route}.`);
  }
}
async function originProbes() {
  for (const origin of [null, 'https://foreign-origin.invalid']) {
    const response = await context.request.post(url('/api/projects'), { data: {}, headers: origin ? { Origin: origin } : {} });
    evidence.security_probes.push({ action: 'authenticated_empty_plan_POST', origin: origin || 'absent', status: response.status(), core_mutation_expected: false });
    check(response.status() === 403, 'Missing/foreign Origin was not rejected before core dispatch.');
  }
}
async function loadProject(project, version) {
  const stored = await jsonGET(projectRoute(project, version ? `?version=${encodeURIComponent(version)}` : ''));
  const wanted = version || stored.version || stored.project.current_version;
  await page.evaluate((id) => localStorage.setItem('world-simulation.last-project', id), project);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#plan-panel:not([hidden])');
  await page.waitForFunction((v) => [...document.getElementById('version-select').options].some((x) => x.value === v), wanted);
  await page.locator('#version-select').selectOption(wanted);
  await page.waitForFunction((v) => document.getElementById('version-select').value === v, wanted);
  check(stored.plan?.gate?.passed === true && !!stored.plan.plan_hash, 'The immutable stored plan did not pass its complete gate.');
  check(await page.locator('.scene-item').count() === stored.plan.scenes.length, 'The complete Scene Plan is not visible.');
  await layout('plan');
  return { ...stored, version: wanted };
}
async function planOnly() {
  await page.locator('#topic').fill(args.topic || '서울에서 도쿄를 거쳐 타이베이로 이어지는 민간 항공 연결');
  await page.locator('#duration').fill(String(duration));
  await page.locator('#quality').selectOption(quality);
  await page.locator('#pace').selectOption(pace);
  const waiter = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/projects', { timeout: 60000 });
  const started = Date.now(); await page.locator('#create-plan').click();
  const response = await waiter; const data = await response.json();
  check(response.ok() && !!data.project && data.plan?.gate?.passed === true && !!data.plan.plan_hash, 'Natural-language planning failed its complete gate.');
  evidence.planning_seconds = (Date.now() - started) / 1000;
  evidence.project_id = data.project.id; evidence.version = data.version; evidence.plan_hash = data.plan.plan_hash;
  await page.waitForSelector('#plan-panel:not([hidden])');
  const stored = await jsonGET(projectRoute(data.project.id));
  check(stored.plan.plan_hash === data.plan.plan_hash, 'Stored and displayed planning hashes differ.');
  const status = await jsonGET(projectRoute(data.project.id, '/status'));
  check(status.status === 'planned', 'Planning unexpectedly queued or rendered a video.');
  check(!evidence.engine_requests.some((x) => ['approve', 'render', 'revise'].includes(x.action)), 'Plan-only mode performed an approval/render/edit.');
  evidence.approved = false; evidence.render_started = false;
  await save('scene_plan.json', stored.plan); await save('status.json', status);
  await layout('plan'); await screenshot('02_plan_mobile.png', page.locator('#plan-panel'));
}
async function approve() {
  const data = await loadProject(pid, args.version);
  const status = await jsonGET(projectRoute(pid, `/status?version=${encodeURIComponent(data.version)}`));
  check(data.version === data.project.current_version, 'Historical versions cannot be approved.');
  check(Number(data.plan.duration || data.plan.request?.duration) <= 20, 'approve mode is bounded to <=20-second internal QA plans.');
  check(['planned', 'approved', 'failed', 'interrupted', 'qc_failed'].includes(status.status), 'The plan is already active or complete; no duplicate render will be requested.');
  check(await page.locator('#approve-render').isEnabled(), 'The displayed gate did not permit UI approval.');
  evidence.project_id = pid; evidence.version = data.version; evidence.plan_hash = data.plan.plan_hash;
  evidence.approval_scope = 'Explicit CLI-selected internal short QA plan; not user acceptance of visual style.';
  await save('scene_plan.json', data.plan); await save('status_before_approval.json', status);
  await screenshot('02_before_approval_mobile.png', page.locator('#plan-panel'));
  check(!evidence.engine_requests.some((x) => x.action === 'render'), 'A render began before explicit UI approval.');
  const approveWaiter = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === projectRoute(pid, '/approve'));
  const renderWaiter = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === projectRoute(pid, '/render'));
  renderWaiter.catch(() => {});
  await page.locator('#approve-render').click();
  const approvedResponse = await approveWaiter; const approved = await approvedResponse.json();
  check(approvedResponse.ok() && !approved.error, 'The exact displayed plan approval failed.');
  const jobResponse = await renderWaiter; const job = await jobResponse.json();
  check(jobResponse.status() === 202 && !!job.job_id && !job.error, 'The background render did not return HTTP202 and a real job ID.');
  const approvalRequest = evidence.engine_requests.find((x) => x.action === 'approve');
  const renderRequest = evidence.engine_requests.find((x) => x.action === 'render');
  check(approvalRequest?.body?.plan_hash === data.plan.plan_hash && approvalRequest?.body?.version === data.version && approvalRequest.sequence < renderRequest.sequence, 'Approval hash/version/order differs from the displayed plan.');
  evidence.approved = true; evidence.render_started = true; evidence.job_id = job.job_id;
  await save('approval_response.json', approved); await save('render_job_response.json', job);
  await page.waitForFunction(() => !document.getElementById('progress-panel').hidden || (!document.getElementById('output-panel').hidden && !document.getElementById('result-video').hidden));
  await screenshot('03_background_job_mobile.png');
  await context.close(); // Renderer belongs to the server, not this browser.
  evidence.browser_context_closed_after_enqueue = true;
  await createContext(); await login('reconnect');
  const restored = await loadProject(pid, data.version);
  const resumedStatus = await jsonGET(projectRoute(pid, `/status?version=${encodeURIComponent(data.version)}`));
  check(restored.plan.plan_hash === data.plan.plan_hash && resumedStatus.job_id === job.job_id, 'Browser reconnect did not restore the same immutable plan and background job.');
  check(['queued', 'pending', 'running', 'rendering', 'assembling', 'audio', 'qc', 'resuming', 'processing', 'complete', 'completed'].includes(resumedStatus.status), 'The restored job has failed; no retry is requested automatically.');
  const history = await jsonGET(projectRoute(pid, '/versions'));
  evidence.reconnected_job_status = resumedStatus.status; evidence.history_count = history.versions?.length || 0;
  evidence.background_status_restored = true;
  check(evidence.engine_requests.filter((x) => x.action === 'render').length === 1, 'Browser reconnect issued an unnecessary render request.');
  await save('status_after_reconnect.json', resumedStatus); await save('versions.json', history);
  await layout('reconnect'); await screenshot('04_reconnected_mobile.png');
}
async function download(record, index) {
  const absolute = new URL(record.url, base);
  check(absolute.origin === base, 'An output download unexpectedly points outside the authenticated origin.');
  const response = await context.request.get(absolute.href); check(response.ok(), `Attachment HTTP failure for output ${index + 1}.`);
  const disposition = response.headers()['content-disposition'] || '';
  check(/attachment/i.test(disposition), 'An output response is not an attachment.');
  const bytes = await response.body();
  if (record.bytes != null) check(bytes.length === record.bytes, 'Advertised attachment size differs from the HTTP body.');
  const links = await page.locator('#downloads a').evaluateAll((items) => items.map((x) => x.href));
  const link = links.indexOf(absolute.href); check(link >= 0, 'Actual UI download link is missing.');
  await page.waitForTimeout(250);
  const [attachment] = await Promise.all([page.waitForEvent('download', { timeout: 60000 }), page.locator('#downloads a').nth(link).click()]);
  const name = record.name || absolute.pathname.split('/').pop();
  const target = path.join(output, 'downloads', `${String(index + 1).padStart(2, '0')}_${path.basename(name).replace(/[^\p{L}\p{N}_. -]/gu, '_')}`);
  await attachment.saveAs(target); const downloaded = await fs.readFile(target);
  const result = { name, bytes: downloaded.length, sha256: hash(downloaded), http_sha256: hash(bytes), content_disposition: disposition, browser_suggested_filename: attachment.suggestedFilename(), stored_file: path.relative(output, target) };
  check(result.sha256 === result.http_sha256, 'Browser attachment bytes differ from the authenticated HTTP body.');
  evidence.downloads.push(result);
}
async function play(durationExpected, dimensions) {
  await page.locator('#result-video').scrollIntoViewIfNeeded();
  await page.waitForFunction(() => { const v = document.getElementById('result-video'); return v && !v.hidden && v.readyState >= 2; });
  const result = await page.evaluate(async ({ expected }) => {
    const video = document.getElementById('result-video'); video.pause(); video.currentTime = 0; video.muted = false;
    const frames = [], stalls = [], audio = []; let callback, sampler, last, stopped = false, analyser, audioContext;
    const started = performance.now();
    try { const Audio = window.AudioContext || window.webkitAudioContext; if (Audio) { audioContext = new Audio(); analyser = audioContext.createAnalyser(); analyser.fftSize = 2048; const source = audioContext.createMediaElementSource(video); source.connect(analyser); analyser.connect(audioContext.destination); await audioContext.resume(); } } catch {}
    const samples = new Float32Array(2048);
    function sample() { if (stopped) return; if (analyser && !video.paused && (!audio.length || performance.now() - audio.at(-1).wall_ms > 95)) { analyser.getFloatTimeDomainData(samples); let peak = 0, sum = 0; for (const x of samples) { peak = Math.max(peak, Math.abs(x)); sum += x * x; } audio.push({ media_time: video.currentTime, wall_ms: performance.now(), peak, rms: Math.sqrt(sum / samples.length) }); } sampler = requestAnimationFrame(sample); }
    function frame(now, metadata) { if (stopped) return; if (last != null && now - last > 250) stalls.push({ media_time: metadata.mediaTime, presentation_gap_ms: now - last }); last = now; frames.push({ media_time: metadata.mediaTime, presented_frames: metadata.presentedFrames, wall_elapsed_ms: now - started }); callback = video.requestVideoFrameCallback(frame); }
    const outcome = await new Promise((resolve) => {
      const timeout = setTimeout(() => finish('timeout'), (expected + 45) * 1000);
      function finish(reason) { if (stopped) return; stopped = true; clearTimeout(timeout); if (callback != null) video.cancelVideoFrameCallback?.(callback); if (sampler != null) cancelAnimationFrame(sampler); const q = video.getVideoPlaybackQuality?.(); resolve({ reason, ended: video.ended, duration: video.duration, current_time: video.currentTime, width: video.videoWidth, height: video.videoHeight, decoded_frames: q?.totalVideoFrames ?? null, dropped_frames: q?.droppedVideoFrames ?? null, corrupted_frames: q?.corruptedVideoFrames ?? null, audio_decoded_byte_count: video.webkitAudioDecodedByteCount ?? null, element_error: video.error?.code ?? null, wall_seconds: (performance.now() - started) / 1000 }); }
      video.addEventListener('ended', () => finish('ended'), { once: true }); video.addEventListener('error', () => finish('media_error'), { once: true });
      if (video.requestVideoFrameCallback) callback = video.requestVideoFrameCallback(frame); sampler = requestAnimationFrame(sample); video.play().catch(() => finish('play_rejected'));
    });
    const summary = { windows: audio.length, peak: Math.max(0, ...audio.map((x) => x.peak)), max_rms: Math.max(0, ...audio.map((x) => x.rms)), sample_rate: audioContext?.sampleRate, direct_listening: false };
    if (audioContext) await audioContext.close().catch(() => {});
    return { ...outcome, frame_callbacks: frames.length, frames, presentation_stalls: stalls, audio: summary, audio_windows: audio };
  }, { expected: durationExpected });
  await save('full_playback.json', result);
  evidence.playback = { ...result }; delete evidence.playback.frames; delete evidence.playback.audio_windows;
  check(result.ended && result.reason === 'ended' && !result.element_error, 'The entire video did not finish actual browser playback.');
  check(result.width === dimensions[0] && result.height === dimensions[1], 'Actual media resolution does not match its approved quality mode.');
  check(Math.abs(result.duration - durationExpected) < .15 && result.frame_callbacks > 0 && (result.corrupted_frames || 0) === 0, 'Actual duration/frame presentation/decoding validation failed.');
  await screenshot('04_playback_ended_mobile.png');
}
async function inspect() {
  const data = await loadProject(pid, args.version);
  const status = await jsonGET(projectRoute(pid, `/status?version=${encodeURIComponent(data.version)}`));
  check(['complete', 'completed'].includes(status.status) && (status.result?.qc?.passed === true || status.qc?.passed === true), 'Only completed, automatically QC-passed versions can be inspected.');
  evidence.project_id = pid; evidence.version = data.version; evidence.plan_hash = data.plan.plan_hash;
  const versions = await jsonGET(projectRoute(pid, '/versions')); evidence.history_count = versions.versions?.length || 0;
  await save('scene_plan.json', data.plan); await save('status.json', status); await save('versions.json', versions);
  await page.waitForFunction((v) => document.getElementById('output-version').textContent === v && !document.getElementById('result-video').hidden, data.version);
  await layout('completed'); await screenshot('02_completed_mobile.png');
  const outputs = status.outputs; check(Array.isArray(outputs) && outputs.length > 0, 'No downloadable outputs were returned.');
  const final = outputs.find((x) => x.name === 'final.mp4'); const muted = outputs.find((x) => x.name === 'final_muted.mp4');
  check(final && muted, 'Both final and muted MP4 outputs are required.');
  const media = new URL(final.media_url || final.url.replace('/download/', '/media/'), base);
  check(media.origin === base, 'Media is not served on the authenticated origin.');
  const response = await context.request.get(media.href, { headers: { Range: 'bytes=0-1023' } });
  const bytes = await response.body(); evidence.range = { status: response.status(), content_range: response.headers()['content-range'], bytes: bytes.length, sha256: hash(bytes) };
  check(response.status() === 206 && bytes.length === 1024 && /^bytes 0-1023\//.test(evidence.range.content_range || ''), 'Authenticated MP4 Range delivery failed.');
  for (let i = 0; i < outputs.length; i++) await download(outputs[i], i);
  const selectedQuality = data.plan.request?.quality || data.plan.options?.quality || data.plan.quality;
  const dimensions = selectedQuality === 'FAST' ? [540, 960] : [1080, 1920]; evidence.expected_resolution = dimensions;
  await play(Number(data.plan.duration || data.plan.request.duration), dimensions);
  check(evidence.engine_requests.length === 0, 'Read-only inspection unexpectedly mutated the engine.');
}

try {
  const { chromium } = await import(pathToFileURL(path.join(APP, '..', 'cinematic-world-map/node_modules/playwright/index.mjs')).href);
  browser = await chromium.launch({ headless: true, executablePath: args.chromium || '/usr/bin/chromium', args: ['--no-sandbox', '--disable-gpu', '--autoplay-policy=no-user-gesture-required'] });
  await createContext();
  await securityProbes();
  await login('initial');
  await controls(); await layout('input'); await screenshot('01_authenticated_mobile.png');
  await originProbes();
  await save('health.json', await jsonGET('/api/health'));
  if (mode === 'plan-only') await planOnly(); else if (mode === 'approve') await approve(); else await inspect();
  check(evidence.browser_errors.length === 0, 'The actual browser emitted JavaScript errors.');
  evidence.passed = true;
} catch (error) {
  exitCode = 1; evidence.passed = false;
  const message = redact(error.message || 'Unknown check failure.');
  if (!evidence.failures.includes(message)) evidence.failures.push(message);
  if (page && !page.isClosed() && !new URL(page.url()).pathname.startsWith('/auth/login')) await screenshot('failure_mobile.png').catch(() => {});
} finally {
  await browser?.close();
  evidence.ended_at_utc = new Date().toISOString();
  await save('MOBILE_DEPLOYMENT_E2E.json', evidence);
  console.log(JSON.stringify(redact({ passed: evidence.passed, mode, project_id: evidence.project_id, version: evidence.version, job_id: evidence.job_id, output, failures: evidence.failures }), null, 2));
  password = undefined; confidential = [];
  process.exitCode = exitCode;
}
