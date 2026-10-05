#!/usr/bin/env node
/**
 * Real mobile-browser checks. Rendering requires --start-render,
 * --approve-project, or --approve-revision with --revise-project.
 *
 * Planning only:
 *   node tools/ui_end_to_end.mjs --topic '서울에서 도쿄를 거쳐 싱가포르까지' --duration 20
 * Approve and enqueue the actual renderer (returns without waiting for the render):
 *   node tools/ui_end_to_end.mjs --topic 'London to Paris to Rome' --duration 20 --start-render
 * Inspect a completed version, download its actual outputs, and play the whole video:
 *   node tools/ui_end_to_end.mjs --inspect-project project_0123456789ab --version v001
 * Approve an existing immutable plan without creating another project:
 *   node tools/ui_end_to_end.mjs --approve-project project_0123456789ab --version v001
 * Preview a natural-language edit; optionally explicitly approve and enqueue it:
 *   node tools/ui_end_to_end.mjs --revise-project project_0123456789ab --request '첫 3초가 약해' --approve-revision
 *
 * All evidence goes into an exclusively created directory; prior evidence is preserved.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i];
  if (!key.startsWith('--')) throw new Error(`Unexpected argument: ${key}`);
  args[key.slice(2)] = process.argv[i + 1]?.startsWith('--') || i + 1 === process.argv.length ? true : process.argv[++i];
}
for (const flag of ['help', 'start-render', 'approve-revision', 'tts', 'subtitles', 'no-bgm', 'no-sfx']) if (args[flag] != null && args[flag] !== true) throw new Error(`--${flag} is a flag and takes no value.`);
if (args.help) {
  console.log('Use --topic TEXT [--duration 20] [--quality HIGH] [--start-render], --approve-project PID [--version v001], --revise-project PID --request TEXT [--approve-revision], or --inspect-project PID [--version v001]. Optional --tts --subtitles --no-bgm --base-url URL --output-dir NEW_PATH --chromium PATH --playback-timeout-ms NUMBER --narration-file FILE.');
  process.exit(0);
}
const baseURL = String(args['base-url'] || process.env.WORLD_UI_BASE_URL || 'http://127.0.0.1:8090').replace(/\/$/, '');
const inspectID = args['inspect-project'];
const approveID = args['approve-project'];
const reviseID = args['revise-project'];
if ([inspectID, approveID, reviseID].filter(Boolean).length > 1) throw new Error('Choose one existing-project action.');
if (args['approve-revision'] && !reviseID) throw new Error('--approve-revision requires --revise-project.');
if (reviseID && (typeof args.request !== 'string' || !args.request.trim())) throw new Error('--revise-project requires --request TEXT.');
const topic = String(args.topic || process.env.WORLD_UI_TOPIC || '런던에서 파리를 거쳐 로마까지 연결하는 항공 경로');
const duration = Number(args.duration || process.env.WORLD_UI_DURATION || 20);
const quality = String(args.quality || process.env.WORLD_UI_QUALITY || 'HIGH').toUpperCase();
if (!Number.isFinite(duration) || duration < 20 || duration > 3600) throw new Error('Duration must be between 20 and 3600 seconds.');
if (!['FAST', 'HIGH', 'CINEMA'].includes(quality)) throw new Error('Quality must be FAST, HIGH, or CINEMA.');
for (const pid of [inspectID, approveID, reviseID].filter(Boolean)) if (!/^project_[a-z0-9_]{6,64}$/.test(String(pid))) throw new Error('Invalid project ID.');
if (inspectID && args['start-render']) throw new Error('Inspection never starts rendering; remove --start-render.');
if (reviseID && args['start-render']) throw new Error('Use --approve-revision to explicitly approve the displayed revision.');
if (args.version && !/^v\d{3,}$/.test(String(args.version))) throw new Error('Invalid version.');
const unique = `${new Date().toISOString().replace(/[:.]/g, '-')}_${crypto.randomBytes(3).toString('hex')}`;
const mode = inspectID ? 'inspect_completed_project' : approveID ? 'approve_existing_plan' : reviseID ? args['approve-revision'] ? 'revise_approve_enqueue' : 'revision_preview' : args['start-render'] ? 'plan_approve_enqueue' : 'plan_only';
const output = path.resolve(String(args['output-dir'] || path.join(APP, 'validation', `mobile_${mode}_${unique}`)));
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(output); // Fails if the output directory already exists.
await fs.mkdir(path.join(output, 'downloads'));
const evidence = { schema_version: 1, started_at_utc: new Date().toISOString(), mode, base_url: baseURL, viewport: { width: 375, height: 812 }, real_browser: true, real_phone_hardware: false, direct_listening: false, requests: [], browser_errors: [], failures: [], screenshots: [], downloads: [] };
let browser, context, page;
let exitCode = 0;
const sha = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
const save = async (name, value) => fs.writeFile(path.join(output, name), typeof value === 'string' ? value : `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx' });
function check(condition, message) { if (!condition) { evidence.failures.push(message); throw new Error(message); } }
function projectURL(id, suffix = '') { return `/api/projects/${encodeURIComponent(id)}${suffix}`; }
function isJobStatePayload(payload) {
  const knownStatus = new Set(['planned', 'approved', 'queued', 'pending', 'running', 'rendering', 'assembling', 'audio', 'qc', 'resuming', 'processing', 'completed', 'complete', 'done', 'finished', 'failed', 'error', 'interrupted', 'qc_failed']);
  const status = String(payload?.status || payload?.job?.status || '').toLowerCase();
  return knownStatus.has(status) && !!(payload?.job_id || payload?.job?.job_id || Object.hasOwn(payload || {}, 'progress') || Array.isArray(payload?.outputs));
}
async function getJSON(relative) {
  const response = await context.request.get(`${baseURL}${relative}`);
  const payload = await response.json();
  check(response.ok() && (!payload.error || isJobStatePayload(payload)), `HTTP ${response.status()} for ${relative}: ${payload.error?.message || ''}`);
  return payload;
}
async function screenshot(name, locator) {
  await (locator || page).screenshot({ path: path.join(output, name), fullPage: !locator });
  evidence.screenshots.push(name);
}
function gatePassed(plan) { const gate = plan.gate || plan.retention_gate || {}; return gate.passed === true; }
async function layoutCheck(label) {
  const layout = await page.evaluate(() => ({ viewport_width: innerWidth, page_width: document.documentElement.scrollWidth, horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 1, connection: document.getElementById('connection')?.textContent }));
  evidence[`layout_${label}`] = layout;
  check(!layout.horizontal_overflow, `Mobile horizontal overflow at ${label}.`);
}
async function setToggle(id, checked) { await page.locator(`#${id}`).setChecked(checked); }

async function createPlan() {
  await page.goto(baseURL, { waitUntil: 'networkidle' });
  await layoutCheck('input');
  await screenshot('01_input_mobile.png');
  await page.locator('#topic').fill(topic);
  await page.locator('#duration').fill(String(duration));
  await page.locator('#quality').selectOption(quality);
  if (args.pace) await page.locator('#pace').selectOption(String(args.pace).replace(/^PACE_/, '').toUpperCase());
  if (await page.locator('#sfx').count()) await setToggle('sfx', !args['no-sfx']);
  evidence.production_input_options = await page.evaluate(() => ({pace: document.getElementById('pace')?.value, sfx: document.getElementById('sfx')?.checked}));
  if (args.style) await page.locator('#style').selectOption(String(args.style));
  await setToggle('tts', !!args.tts);
  await setToggle('subtitles', !!args.subtitles);
  await setToggle('bgm', !args['no-bgm']);
  if (args['narration-file']) { await page.locator('.audio-import').evaluate((el) => { el.open = true; }); await page.locator('#narration-file').setInputFiles(path.resolve(String(args['narration-file']))); await setToggle('narration-rights', true); }
  const responsePromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/projects', { timeout: 60000 });
  const before = Date.now();
  await page.locator('#create-plan').click();
  const response = await responsePromise;
  const payload = await response.json();
  evidence.planning_seconds = (Date.now() - before) / 1000;
  await save('planning_response.json', payload);
  check(response.ok() && payload.plan && payload.project, `Planning failed: ${payload.error?.message || response.status()}`);
  const pid = payload.project.id || payload.project.project_id;
  const version = payload.version || payload.project.current_version;
  const plan = payload.plan;
  evidence.project_id = pid; evidence.version = version; evidence.plan_hash = plan.plan_hash; evidence.topic = topic; evidence.duration = duration; evidence.quality = quality;
  check(gatePassed(plan), 'The complete planning gate did not pass.');
  check(!!plan.plan_hash, 'The generated plan has no immutable approval hash.');
  await page.waitForSelector('#plan-panel:not([hidden])');
  await page.waitForFunction(() => !document.getElementById('create-plan').disabled);
  const stored = await getJSON(projectURL(pid));
  check(stored.plan.plan_hash === plan.plan_hash, 'Saved plan hash differs from the plan shown for approval.');
  await save('scene_plan.json', stored.plan);
  await save('project.json', stored.project);
  evidence.scene_count = plan.scenes.length;
  evidence.scene_plan_visible = await page.locator('.scene-item').count();
  check(evidence.scene_plan_visible === plan.scenes.length, 'Visible Scene Plan is incomplete.');
  evidence.render_requests_before_approval = evidence.requests.filter((request) => request.action === 'render').length;
  check(evidence.render_requests_before_approval === 0, 'A render request occurred before approval.');
  const beforeStatus = await getJSON(projectURL(pid, '/status'));
  await save('status_before_approval.json', beforeStatus);
  check(!['rendering', 'queued', 'complete'].includes(beforeStatus.status), 'Planning unexpectedly began rendering.');
  await layoutCheck('plan'); await screenshot('02_plan_mobile.png', page.locator('#plan-panel'));
  check(await page.locator('#approve-render').isEnabled(), 'A validated plan cannot be approved through the UI.');
  if (!args['start-render']) {
    evidence.user_approval_clicked = false; evidence.render_started = false;
    return;
  }
  await approveDisplayedPlan(pid, version, plan);
}

async function approveDisplayedPlan(pid, version, plan) {
  const approvePromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === projectURL(pid, '/approve'), { timeout: 60000 });
  const renderPromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === projectURL(pid, '/render'), { timeout: 60000 });
  renderPromise.catch(() => {}); // Approval failure must not leave an unhandled deferred render waiter.
  await page.locator('#approve-render').click();
  evidence.user_approval_clicked = true;
  const approvedResponse = await approvePromise;
  const approved = await approvedResponse.json(); await save('approval_response.json', approved);
  check(approvedResponse.ok() && !approved.error, `Approval failed: ${approved.error?.message || approvedResponse.status()}`);
  const jobResponse = await renderPromise;
  const job = await jobResponse.json(); await save('render_job_response.json', job);
  check(jobResponse.ok() && !job.error, `Render enqueue failed: ${job.error?.message || jobResponse.status()}`);
  const approvalRequest = evidence.requests.find((request) => request.action === 'approve');
  const renderRequest = evidence.requests.find((request) => request.action === 'render');
  check(approvalRequest?.body?.plan_hash === plan.plan_hash, 'UI approval did not use the exact displayed plan hash.');
  check(approvalRequest?.body?.version === version, 'UI approval did not target the selected immutable version.');
  check(approvalRequest?.sequence < renderRequest?.sequence, 'Rendering was requested before explicit approval.');
  evidence.render_started = true; evidence.job_id = job.job_id; evidence.job_status = job.status;
  await page.waitForFunction(() => !document.getElementById('progress-panel').hidden || (!document.getElementById('output-panel').hidden && !document.getElementById('result-video').hidden));
  await screenshot('03_enqueued_mobile.png');
  await save('status_after_enqueue.json', await getJSON(projectURL(pid, '/status')));
  // This command deliberately returns now; the durable backend keeps the job running.
}

async function loadExistingFromLibrary(pid) {
  const data = await getJSON(projectURL(pid, args.version ? `?version=${encodeURIComponent(args.version)}` : ''));
  const version = args.version || data.version || data.project.current_version;
  evidence.project_id = pid; evidence.version = version; evidence.plan_hash = data.plan.plan_hash;
  evidence.duration = data.plan.duration || data.plan.request?.duration; evidence.quality = data.plan.request?.quality; evidence.topic = data.plan.request?.topic || data.project.title;
  check(version === data.project.current_version, 'Approval and editing use the current immutable version; historical versions remain read-only.');
  await page.goto(baseURL, { waitUntil: 'networkidle' });
  await page.locator('#projects-toggle').click();
  const button = page.locator(`#project-list button[data-project-id="${pid}"]`);
  await button.waitFor({ state: 'visible' });
  const loadedResponse = page.waitForResponse((response) => response.request().method() === 'GET' && new URL(response.url()).pathname === projectURL(pid), { timeout: 60000 });
  await button.click();
  const loaded = await (await loadedResponse).json();
  check(loaded.plan?.plan_hash === data.plan.plan_hash, 'The plan loaded through the project library differs from the saved plan.');
  await page.waitForSelector('#plan-panel:not([hidden])');
  await page.waitForFunction((wanted) => document.getElementById('version-select').value === wanted, version);
  await save('project.json', data.project); await save('scene_plan.json', data.plan);
  await save('status_before_approval.json', await getJSON(projectURL(pid, `/status?version=${encodeURIComponent(version)}`)));
  await layoutCheck('existing_plan'); await screenshot('01_existing_plan_mobile.png', page.locator('#plan-panel'));
  check(gatePassed(data.plan) && !!data.plan.plan_hash, 'The existing plan has not passed the complete approval gate.');
  check(await page.locator('.scene-item').count() === data.plan.scenes.length, 'The existing Scene Plan is not fully visible.');
  evidence.render_requests_before_approval = evidence.requests.filter((request) => request.action === 'render').length;
  evidence.created_project_requests = evidence.requests.filter((request) => request.action === 'create_plan').length;
  check(evidence.render_requests_before_approval === 0 && evidence.created_project_requests === 0, 'Loading an existing project created a new plan or started rendering.');
  return { ...data, version };
}

async function approveExistingPlan() {
  const pid = String(approveID);
  const data = await loadExistingFromLibrary(pid);
  check(await page.locator('#approve-render').isVisible() && await page.locator('#approve-render').isEnabled(), 'The existing plan cannot currently be approved and rendered.');
  await approveDisplayedPlan(pid, data.version, data.plan);
}

async function reviseExistingPlan() {
  const pid = String(reviseID);
  const data = await loadExistingFromLibrary(pid);
  check(await page.locator('#revision-panel').isVisible(), 'The current project is not available for editing.');
  const revisionPromise = page.waitForResponse((response) => response.request().method() === 'POST' && new URL(response.url()).pathname === projectURL(pid, '/revise'), { timeout: 60000 });
  await page.locator('#revision-request').fill(String(args.request));
  await page.locator('#preview-revision').click();
  const response = await revisionPromise;
  const revision = await response.json(); await save('revision_preview.json', revision);
  check(response.ok() && !revision.error && !!revision.revision_id, `Revision preview failed: ${revision.error?.message || response.status()}`);
  check(revision.base_plan_hash === data.plan.plan_hash, 'The revision was not derived from the exact displayed plan.');
  check(gatePassed(revision.plan), 'The revision plan failed the complete planning gate.');
  await page.waitForSelector('#revision-preview:not([hidden])');
  await screenshot('02_revision_diff_mobile.png', page.locator('#revision-preview'));
  evidence.revision_id = revision.revision_id; evidence.affected_scenes = revision.affected_scenes; evidence.diff_count = revision.diff?.length || 0;
  evidence.render_requests_before_revision_approval = evidence.requests.filter((request) => request.action === 'render').length;
  check(evidence.render_requests_before_revision_approval === 0, 'Previewing a revision started rendering before approval.');
  if (!args['approve-revision']) { evidence.revision_approval_clicked = false; evidence.render_started = false; return; }
  check(await page.locator('#approve-revision').isEnabled(), 'The revision approval button is disabled.');
  const approvedPath = projectURL(pid, `/revisions/${revision.revision_id}/approve`);
  const approvalPromise = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname === approvedPath, { timeout: 60000 });
  const renderPromise = page.waitForResponse((item) => item.request().method() === 'POST' && new URL(item.url()).pathname === projectURL(pid, '/render'), { timeout: 60000 });
  renderPromise.catch(() => {});
  await page.locator('#approve-revision').click(); evidence.revision_approval_clicked = true;
  const approvalResponse = await approvalPromise;
  const approved = await approvalResponse.json(); await save('revision_approval_response.json', approved);
  check(approvalResponse.ok() && approved.plan && !approved.error, `Revision approval failed: ${approved.error?.message || approvalResponse.status()}`);
  check(approved.version !== data.version && approved.plan.plan_hash !== data.plan.plan_hash, 'Revision approval did not create a new immutable version.');
  const jobResponse = await renderPromise;
  const job = await jobResponse.json(); await save('render_job_response.json', job);
  check(jobResponse.ok() && !job.error, `Partial rerender enqueue failed: ${job.error?.message || jobResponse.status()}`);
  const approvalRequest = evidence.requests.find((request) => request.path === approvedPath);
  const renderRequest = evidence.requests.find((request) => request.action === 'render');
  check(approvalRequest?.sequence < renderRequest?.sequence, 'The partial rerender began before revision approval.');
  check(renderRequest?.body?.version === approved.version, 'The partial rerender did not target the approved new version.');
  evidence.base_version = data.version; evidence.version = approved.version; evidence.plan_hash = approved.plan.plan_hash; evidence.job_id = job.job_id; evidence.render_started = true;
  await save('approved_revision_scene_plan.json', approved.plan);
  const previous = await getJSON(projectURL(pid, `?version=${encodeURIComponent(data.version)}`));
  check(previous.plan.plan_hash === data.plan.plan_hash, 'The previous immutable plan was modified by the revision.');
  evidence.previous_plan_preserved = true;
  await page.waitForFunction(() => !document.getElementById('progress-panel').hidden || (!document.getElementById('output-panel').hidden && !document.getElementById('result-video').hidden));
  await screenshot('03_partial_rerender_enqueued_mobile.png');
  await save('status_after_enqueue.json', await getJSON(projectURL(pid, `/status?version=${encodeURIComponent(approved.version)}`)));
}

async function actualDownload(outputRecord, index) {
  const downloadURL = outputRecord.url || outputRecord.download_url;
  check(!!downloadURL, 'An output has no actual browser-download URL.');
  const absolute = new URL(downloadURL, baseURL).href;
  check(new URL(absolute).origin === new URL(baseURL).origin, 'An unexpected external download URL was returned.');
  const name = outputRecord.name || outputRecord.filename || new URL(absolute).pathname.split('/').pop();
  const response = await context.request.get(absolute);
  check(response.ok(), `Download endpoint failed for ${name}: HTTP ${response.status()}.`);
  const headers = response.headers();
  check(/attachment/i.test(headers['content-disposition'] || ''), `Output ${name} is not served as an attachment.`);
  const bytes = await response.body();
  const expectedHash = sha(bytes);
  if (outputRecord.bytes != null) check(bytes.length === outputRecord.bytes, `Advertised byte count differs for ${name}.`);
  const links = await page.locator('#downloads a').evaluateAll((elements) => elements.map((element) => element.href));
  const linkIndex = links.indexOf(absolute);
  check(linkIndex >= 0, `No actual UI download link is present for ${name}.`);
  // Click at a human pace: completed projects include independent Scene files,
  // so an unpaced burst can hit Chromium's automatic-download rate limiter.
  // Keep the normal browser policy enabled and verify every real attachment.
  evidence.download_pacing_ms = 250;
  await page.waitForTimeout(evidence.download_pacing_ms);
  const [download] = await Promise.all([page.waitForEvent('download', { timeout: 60000 }), page.locator('#downloads a').nth(linkIndex).click()]);
  const target = path.join(output, 'downloads', `${String(index + 1).padStart(2, '0')}_${path.basename(name).replace(/[^\p{L}\p{N}_. -]/gu, '_')}`);
  await download.saveAs(target);
  const downloaded = await fs.readFile(target);
  const record = { name, url: absolute, bytes: downloaded.length, sha256: sha(downloaded), http_sha256: expectedHash, browser_suggested_filename: download.suggestedFilename(), content_disposition: headers['content-disposition'], stored_file: path.relative(output, target), browser_attachment_complete: true };
  evidence.downloads.push(record);
  check(record.sha256 === expectedHash, `Browser download bytes differ from the actual HTTP output for ${name}.`);
  return record;
}

async function playWholeVideo(expectedDuration) {
  await page.locator('#result-video').scrollIntoViewIfNeeded();
  await page.waitForFunction(() => { const video = document.getElementById('result-video'); return video && !video.hidden && video.readyState >= 2; }, { timeout: 60000 });
  const playbackTimeout = Number(args['playback-timeout-ms'] || (Number(expectedDuration || 180) + 45) * 1000);
  page.setDefaultTimeout(playbackTimeout + 5000);
  const result = await page.evaluate(async ({ timeoutMS }) => {
    const video = document.getElementById('result-video');
    video.pause(); video.currentTime = 0; video.muted = false; video.volume = 1;
    const frames = []; const audio = []; const stalls = []; let callback, animationFrame, finished = false, lastFrameAt = null, analyser = null, audioContext = null, source = null;
    const started = performance.now();
    const audioSetup = { supported: !!(window.AudioContext || window.webkitAudioContext), actual_listening: false };
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) {
        audioContext = new Context(); source = audioContext.createMediaElementSource(video); analyser = audioContext.createAnalyser(); analyser.fftSize = 2048;
        source.connect(analyser); analyser.connect(audioContext.destination); await audioContext.resume(); audioSetup.context_state = audioContext.state; audioSetup.sample_rate = audioContext.sampleRate;
      }
    } catch (error) { audioSetup.error = error.message; }
    const samples = new Float32Array(2048);
    function sampleAudio() {
      if (finished) return;
      if (analyser && !video.paused) {
        analyser.getFloatTimeDomainData(samples); let squared = 0, peak = 0;
        for (const value of samples) { squared += value * value; peak = Math.max(peak, Math.abs(value)); }
        if (!audio.length || performance.now() - audio[audio.length - 1].wall_ms > 95) audio.push({ media_time: video.currentTime, wall_ms: performance.now(), rms: Math.sqrt(squared / samples.length), peak });
      }
      animationFrame = requestAnimationFrame(sampleAudio);
    }
    function frame(now, metadata) {
      if (finished) return;
      if (lastFrameAt != null && now - lastFrameAt > 250) stalls.push({ media_time: metadata.mediaTime, presentation_gap_ms: now - lastFrameAt });
      lastFrameAt = now;
      frames.push({ media_time: metadata.mediaTime, presented_frames: metadata.presentedFrames, width: metadata.width, height: metadata.height, wall_elapsed_ms: now - started });
      callback = video.requestVideoFrameCallback(frame);
    }
    const outcome = await new Promise(async (resolve) => {
      const timer = setTimeout(() => finish('timeout'), timeoutMS);
      function finish(reason) { if (finished) return; finished = true; clearTimeout(timer); if (callback != null) video.cancelVideoFrameCallback?.(callback); if (animationFrame != null) cancelAnimationFrame(animationFrame); const quality = video.getVideoPlaybackQuality?.(); resolve({ reason, ended: video.ended, current_time: video.currentTime, duration: video.duration, video_width: video.videoWidth, video_height: video.videoHeight, decoded_frames: quality?.totalVideoFrames ?? null, dropped_frames: quality?.droppedVideoFrames ?? null, corrupted_frames: quality?.corruptedVideoFrames ?? null, audio_decoded_byte_count: video.webkitAudioDecodedByteCount ?? null, video_decoded_byte_count: video.webkitVideoDecodedByteCount ?? null, element_error: video.error ? { code: video.error.code, message: video.error.message } : null, elapsed_seconds: (performance.now() - started) / 1000 }); }
      video.addEventListener('ended', () => finish('ended'), { once: true });
      video.addEventListener('error', () => finish('media_error'), { once: true });
      if (video.requestVideoFrameCallback) callback = video.requestVideoFrameCallback(frame);
      else audioSetup.frame_callback_unavailable = true;
      animationFrame = requestAnimationFrame(sampleAudio);
      try { await video.play(); } catch (error) { audioSetup.play_error = error.message; finish('play_rejected'); }
    });
    const audioSummary = { windows: audio.length, peak: Math.max(0, ...audio.map((item) => item.peak)), max_rms: Math.max(0, ...audio.map((item) => item.rms)), mean_rms: audio.length ? audio.reduce((total, item) => total + item.rms, 0) / audio.length : 0, setup: audioSetup, direct_listening: false, interpretation: 'Decoded WebAudio samples only; no claim of physical speaker playback or direct listening.' };
    if (audioContext) await audioContext.close().catch(() => {});
    return { ...outcome, frame_callback_count: frames.length, frames, presentation_stalls: stalls, audio: audioSummary, audio_windows: audio };
  }, { timeoutMS: playbackTimeout });
  await save('full_playback.json', result);
  evidence.playback = { ...result }; delete evidence.playback.frames; delete evidence.playback.audio_windows;
  check(result.reason === 'ended' && result.ended && !result.element_error, `Full video playback failed: ${result.reason}.`);
  check(result.video_width === 1080 && result.video_height === 1920, 'The browser video dimensions are not 1080×1920.');
  check(Math.abs(result.duration - Number(expectedDuration)) < 0.15, 'The played MP4 duration does not match the approved plan.');
  check(result.frame_callback_count > 0, 'No actual video frame callbacks were observed.');
  check((result.corrupted_frames || 0) === 0, 'The browser reported corrupted video frames.');
  await screenshot('04_playback_ended_mobile.png');
}

async function inspectCompleted() {
  const pid = String(inspectID); const versionQuery = args.version ? `?version=${encodeURIComponent(args.version)}` : '';
  const data = await getJSON(projectURL(pid, versionQuery));
  const version = args.version || data.version || data.project.current_version;
  const status = await getJSON(projectURL(pid, `/status?version=${encodeURIComponent(version)}`));
  const versions = await getJSON(projectURL(pid, '/versions'));
  evidence.project_id = pid; evidence.version = version; evidence.plan_hash = data.plan.plan_hash; evidence.status = status.status; evidence.history_count = versions.versions?.length || 0;
  await save('project.json', data.project); await save('scene_plan.json', data.plan); await save('status.json', status); await save('versions.json', versions);
  check(gatePassed(data.plan), 'Saved planning gate failed.');
  check(['complete', 'completed', 'done', 'finished'].includes(status.status), `Project is not complete: ${status.status}.`);
  check(status.qc?.passed !== false && status.result?.qc?.passed !== false, 'Project QC reports failure.');
  await context.addInitScript((savedID) => { localStorage.setItem('world-simulation.last-project', savedID); }, pid);
  await page.goto(baseURL, { waitUntil: 'networkidle' });
  await page.waitForSelector('#plan-panel:not([hidden])');
  await page.waitForFunction((wanted) => [...document.getElementById('version-select').options].some((option) => option.value === wanted), version);
  await page.locator('#version-select').selectOption(version);
  await page.waitForSelector('#output-panel:not([hidden])');
  await page.waitForFunction((wanted) => document.getElementById('output-version').textContent === wanted, version);
  await layoutCheck('completed'); await screenshot('01_completed_mobile.png');
  evidence.render_requests_during_inspection = evidence.requests.filter((request) => request.action === 'render').length;
  check(evidence.render_requests_during_inspection === 0, 'Inspection unexpectedly requested rendering.');
  const outputs = status.outputs || [];
  check(Array.isArray(outputs) && outputs.length > 0, 'Completed project has no actual output downloads.');
  const video = outputs.find((item) => (item.name || item.filename) === 'final.mp4');
  const muted = outputs.find((item) => (item.name || item.filename) === 'final_muted.mp4');
  check(!!video && !!muted, 'Final and muted MP4 outputs are both required.');
  const mediaURL = new URL(video.media_url || video.url.replace('/download/', '/media/'), baseURL).href;
  const range = await context.request.get(mediaURL, { headers: { Range: 'bytes=0-1023' } });
  const rangeBytes = await range.body();
  evidence.media_range = { url: mediaURL, status: range.status(), content_range: range.headers()['content-range'], bytes: rangeBytes.length, sha256: sha(rangeBytes) };
  check(range.status() === 206 && rangeBytes.length === 1024 && /^bytes 0-1023\//.test(range.headers()['content-range'] || ''), 'Actual MP4 Range delivery failed.');
  // Downloading first guarantees the tested attachment and the later playback refer to the same saved version.
  for (let i = 0; i < outputs.length; i++) await actualDownload(outputs[i], i);
  await playWholeVideo(data.plan.duration || data.plan.request.duration);
  evidence.semantic_visual_quality = 'This evidence verifies transport, complete playback, frame presentation and decoded audio. Semantic scene events and V3 visual fidelity must also pass renderer audits and direct frame review.';
}

try {
  const playwrightPath = path.join(APP, '..', 'cinematic-world-map', 'node_modules', 'playwright', 'index.mjs');
  const { chromium } = await import(pathToFileURL(playwrightPath).href);
  browser = await chromium.launch({ headless: true, executablePath: String(args.chromium || process.env.CHROMIUM_PATH || '/usr/bin/chromium'), args: ['--no-sandbox', '--disable-gpu', '--autoplay-policy=no-user-gesture-required'] });
  context = await browser.newContext({ viewport: evidence.viewport, deviceScaleFactor: 1, acceptDownloads: true });
  page = await context.newPage();
  page.on('pageerror', (error) => evidence.browser_errors.push({ message: error.message, at_utc: new Date().toISOString() }));
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname;
    const action = pathname === '/api/projects' ? 'create_plan' : pathname.split('/').pop();
    if (request.method() === 'POST' && ['create_plan', 'approve', 'render', 'revise', 'clip'].includes(action)) {
      let body = null; try { body = request.postDataJSON(); } catch {}
      evidence.requests.push({ sequence: evidence.requests.length, action, path: pathname, body, at_utc: new Date().toISOString() });
    }
  });
  await save('health.json', await getJSON('/api/health'));
  if (inspectID) await inspectCompleted(); else if (approveID) await approveExistingPlan(); else if (reviseID) await reviseExistingPlan(); else await createPlan();
  check(evidence.browser_errors.length === 0, 'The application emitted JavaScript errors.');
  evidence.passed = true;
} catch (error) {
  exitCode = 1; evidence.passed = false;
  if (!evidence.failures.includes(error.message)) evidence.failures.push(error.message);
  evidence.exception = { message: error.message, stack: error.stack };
  if (page && !page.isClosed()) await screenshot('failure_mobile.png').catch(() => {});
} finally {
  evidence.ended_at_utc = new Date().toISOString();
  await save('UI_END_TO_END_REPORT.json', evidence);
  await browser?.close();
  console.log(JSON.stringify({ passed: evidence.passed, mode: evidence.mode, project_id: evidence.project_id, version: evidence.version, plan_hash: evidence.plan_hash, job_id: evidence.job_id, output_directory: output, failures: evidence.failures }, null, 2));
  process.exitCode = exitCode;
}
