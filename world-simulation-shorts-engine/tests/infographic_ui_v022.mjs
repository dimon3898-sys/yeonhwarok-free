// Actual mobile UI module and DOM. Protocol fixtures exercise presentation only;
// no renderer, video, GPU, or external gcube service is invoked.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const root = process.cwd();
const require = createRequire(path.resolve(root, '../cinematic-world-map/package.json'));
const {chromium} = require('playwright');
const script = JSON.parse(fs.readFileSync(path.join(root, 'deployment/gcube/fixtures/infographic_production_v022.json'), 'utf8'));
const report = {passed: false, gpu_draw: 'NOT_RUN', video_render: 'NOT_RUN', transport: 'ACTUAL_LOCAL_HTTP', viewport: [393, 851], checks: {}};
const errors = [];
let nextPlan = null, savedPlan = null, posts = [], failCreation = false;
function plan(kind = 'QA') {
  const family = kind === 'QA' ? 'story-progression-v021' : 'production-earth-v1';
  const scene = {scene_id: 'S001', start_time: 0, duration: kind === 'QA' ? 24 : 8, location: 'UI protocol fixture', camera_preset: 'EARTH_ESTABLISH', visual_mode: '3D_EARTH', narration: 'UI protocol fixture'};
  if (kind !== 'NONE') scene.infographic = {version: 'v022', parent_renderer_family: family};
  return {title: 'UI selection protocol fixture', duration: scene.duration, plan_hash: 'ui-protocol-hash', gate: {passed: true},
    // The inherited QA request field is deliberately misleading. Actual metadata wins.
    request: {direction_profile: 'SECOND_EVENT_ADAPTIVE_WIDE_TEST', quality: 'HIGH'},
    metadata: kind === 'NONE' ? {} : {infographic: {version: 'v022', parent_renderer_family: family}}, scenes: [scene]};
}
function payload(selected = savedPlan) { return {project: {id: 'ui-project', current_version: 'v001', title: 'UI fixture'}, version: 'v001', plan: selected}; }
const mime = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json'};
const server = http.createServer(async (req, res) => {
  if (req.url.startsWith('/api/')) {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : null;
    if (req.method === 'POST') posts.push({path: req.url, body});
    if (req.url === '/api/projects' && req.method === 'POST' && failCreation) {res.writeHead(422, {'Content-Type': 'application/json'});res.end(JSON.stringify({error: {code: 'UI_FIXTURE_REJECTED', message: 'UI protocol create failure'}}));return;}
    let response = {};
    if (req.url === '/api/health') response = {status: 'ok'};
    else if (req.url === '/api/projects' && req.method === 'POST') {savedPlan = structuredClone(nextPlan); response = payload();}
    else if (req.url === '/api/projects') response = {projects: []};
    else if (req.url.endsWith('/versions')) response = {versions: ['v001', 'v002']};
    else if (req.url.endsWith('/versions/v002/plan')) response = {plan: plan('PRODUCTION')};
    else if (req.url.endsWith('/status')) response = {status: 'planned', outputs: []};
    else if (req.url === '/api/projects/ui-project') response = payload();
    else response = {status: 'planned'};
    res.writeHead(200, {'Content-Type': 'application/json'}); res.end(JSON.stringify(response)); return;
  }
  const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
  const filename = path.resolve(root, 'web', pathname === '/' ? 'index.html' : `.${pathname.replace(/^\/static\//, '/')}`);
  if (!filename.startsWith(path.resolve(root, 'web') + path.sep)) {res.writeHead(403);res.end();return;}
  try { const data = fs.readFileSync(filename); res.writeHead(200, {'Content-Type': mime[path.extname(filename)] || 'application/octet-stream'}); res.end(data); }
  catch {res.writeHead(404);res.end();}
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-gpu']});
async function open(options = {}) {
  posts = []; failCreation = options.failCreation === true; nextPlan = options.plan || plan('QA'); savedPlan = structuredClone(nextPlan);
  const context = await browser.newContext({viewport: {width: 393, height: 851}, isMobile: true, hasTouch: true});
  if (options.storage) await context.addInitScript(storage => {for (const [key, value] of Object.entries(storage)) localStorage.setItem(key, value);}, options.storage);
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin); await page.waitForFunction(() => document.getElementById('connection').textContent === '연결됨');
  return {context, page};
}
async function submit(page) {
  const previous = posts.filter(row => row.path === '/api/projects').length;
  await page.locator('#create-plan').click();
  await page.waitForFunction(() => document.getElementById('plan-panel').hidden === false);
  await page.waitForFunction(() => !document.getElementById('create-plan').disabled);
  assert.equal(posts.filter(row => row.path === '/api/projects').length, previous + 1);
  return posts.filter(row => row.path === '/api/projects').at(-1).body;
}
async function check(name, operation) {await operation();report.checks[name] = 'PASS';}
try {
  await check('render_plan_preserves_reference_master_and_next_request', async () => {
    const {context, page} = await open();
    await page.locator('#topic').fill('UI authored topic'); await page.locator('#duration').fill('24');
    const first = await submit(page); assert.equal(first.direction_profile, 'REFERENCE_MASTER');
    assert.equal(await page.locator('#direction-profile').inputValue(), 'REFERENCE_MASTER');
    assert.equal(await page.locator('#infographic-plan-badge').textContent(), 'INFOGRAPHIC v022 · QA');
    assert.equal((await submit(page)).direction_profile, 'REFERENCE_MASTER'); await context.close();
  });
  await check('explicit_legacy_choice_is_not_overwritten_by_scene_direction', async () => {
    const old = plan('NONE'); old.scenes[0].direction = {preset: 'REFERENCE_MASTER'};
    const {context, page} = await open({plan: old});
    await page.locator('#topic').fill('UI legacy topic'); await page.locator('#direction-profile').selectOption('FAST_PLUS_LEGACY');
    await submit(page); assert.equal(await page.locator('#direction-profile').inputValue(), 'FAST_PLUS_LEGACY');
    assert.equal((await submit(page)).direction_profile, 'FAST_PLUS_LEGACY'); await context.close();
  });
  await check('named_qa_actual_submission_and_fixed_controls', async () => {
    const {context, page} = await open();
    await page.locator('#topic').fill('UI QA topic'); await page.locator('#quality').selectOption('CINEMA');
    await page.locator('#tts').check(); await page.locator('#subtitles').check(); await page.locator('#bgm').uncheck();
    await page.locator('#infographic-mode').selectOption('QA');
    for (const id of ['duration', 'quality', 'pace', 'tts', 'subtitles', 'direction-profile', 'qa-mode']) assert.equal(await page.locator(`#${id}`).isDisabled(), true);
    const request = await submit(page);
    assert.deepEqual([request.direction_profile, request.duration, request.quality, request.pace, request.qa_mode, request.tts, request.subtitles, request.bgm], ['MAP_INFOGRAPHIC_QA_V022', 24, 'HIGH', 'FAST_PLUS', true, false, false, false]);
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'), 'QA');
    assert.equal(await page.locator('#approve-render').isDisabled(), false); await context.close();
  });
  await check('production_authored_file_actual_submission_has_no_ordinary_options', async () => {
    const {context, page} = await open({plan: plan('PRODUCTION')});
    await page.locator('#infographic-mode').selectOption('PRODUCTION');
    await page.locator('#infographic-script-file').setInputFiles({name: 'authored-script.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(script))});
    for (const id of ['duration', 'quality', 'pace', 'tts', 'subtitles', 'bgm', 'sfx', 'style', 'narration-file', 'narration-rights']) assert.equal(await page.locator(`#${id}`).isDisabled(), true);
    const request = await submit(page);
    assert.deepEqual(request, {direction_profile: 'MAP_INFOGRAPHIC_PRODUCTION_V022', script_record: script});
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'), 'PRODUCTION');
    assert.equal(await page.locator('#approve-render').isDisabled(), false); await context.close();
  });
  await check('mismatched_scene_versions_visible_and_block_approve_resume', async () => {
    const broken = plan('QA'); broken.scenes.push({...structuredClone(broken.scenes[0]), scene_id: 'S002', infographic: {version: 'v021', parent_renderer_family: 'story-progression-v021'}});
    const {context, page} = await open({plan: broken}); await page.locator('#topic').fill('UI mismatch topic');
    await page.locator('#infographic-mode').selectOption('QA'); await submit(page);
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'), 'MISMATCH');
    assert.equal(await page.locator('#notice').isVisible(), true); assert.equal(await page.locator('#approve-render').isDisabled(), true);
    await page.evaluate(() => document.getElementById('resume-render').click());
    await page.waitForFunction(() => !document.getElementById('resume-render').disabled);
    assert.equal(posts.some(row => /\/(approve|render)$/.test(row.path)), false); await context.close();
  });
  await check('named_qa_missing_metadata_is_not_shown_as_success', async () => {
    const {context, page} = await open({plan: plan('NONE')}); await page.locator('#topic').fill('UI missing contract');
    await page.locator('#infographic-mode').selectOption('QA'); await submit(page);
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'), 'MISMATCH'); assert.equal(await page.locator('#approve-render').isDisabled(), true); await context.close();
  });
  await check('saved_plan_and_history_do_not_change_explicit_creation_choices', async () => {
    const {context, page} = await open({storage: {'world-simulation.last-project': 'ui-project', 'world-simulation.direction-profile': 'FAST_PLUS_LEGACY', 'world-simulation.infographic-mode': 'NONE'}});
    await page.locator('#infographic-plan-badge').waitFor(); assert.equal(await page.locator('#direction-profile').inputValue(), 'FAST_PLUS_LEGACY');
    await page.locator('#version-select').selectOption('v002'); await page.waitForFunction(() => document.getElementById('infographic-plan-badge').dataset.infographicKind === 'PRODUCTION');
    assert.equal(await page.locator('#direction-profile').inputValue(), 'FAST_PLUS_LEGACY'); assert.equal(await page.locator('#infographic-mode').inputValue(), 'NONE');
    assert.equal(await page.locator('#approve-render').isDisabled(), true); await context.close();
  });
  await check('failed_creation_keeps_saved_plan_version_and_approval', async () => {
    const {context, page} = await open({plan: plan('PRODUCTION'), failCreation: true, storage: {'world-simulation.last-project': 'ui-project'}});
    await page.locator('#infographic-plan-badge').waitFor(); await page.locator('#topic').fill('UI failed create topic'); await page.locator('#infographic-mode').selectOption('QA');
    await page.locator('#create-plan').click(); await page.locator('#notice').waitFor({state: 'visible'}); await page.waitForFunction(() => !document.getElementById('create-plan').disabled);
    assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'), 'PRODUCTION');
    assert.equal(await page.locator('#version-select').inputValue(), 'v001'); assert.equal(await page.locator('#approve-render').isDisabled(), false);
    // The API is a local protocol fixture: these calls never invoke rendering.
    await page.locator('#approve-render').click(); await page.waitForFunction(() => !document.getElementById('approve-render').disabled);
    assert.deepEqual(posts.find(row => row.path.endsWith('/approve')).body, {plan_hash: 'ui-protocol-hash', version: 'v001'});
    assert.deepEqual(posts.find(row => row.path.endsWith('/render')).body, {version: 'v001'}); await context.close();
  });
  await check('explicit_profile_and_mode_persist_reload_without_plan_inference', async () => {
    const {context, page} = await open();
    await page.locator('#direction-profile').selectOption('FAST_PLUS_LEGACY'); await page.locator('#infographic-mode').selectOption('QA');
    await page.reload(); await page.waitForFunction(() => document.getElementById('connection').textContent === '연결됨');
    assert.equal(await page.locator('#direction-profile').inputValue(), 'FAST_PLUS_LEGACY'); assert.equal(await page.locator('#infographic-mode').inputValue(), 'QA');
    assert.equal(await page.locator('#duration').inputValue(), '24'); await context.close();
  });
  await check('short_qa_12_15_preserved_and_new_qa_24_is_not_browser_blocked', async () => {
    const {context, page} = await open({plan: plan('NONE')});
    await page.locator('#topic').fill('UI short QA'); await page.locator('#direction-profile').selectOption('FAST_PLUS_LEGACY'); await page.locator('#qa-mode').check();
    assert.equal(await page.locator('#duration').getAttribute('max'), '15'); const short = await submit(page);
    assert.deepEqual([short.duration, short.qa_mode, short.direction_profile], [12, true, 'FAST_PLUS_LEGACY']);
    nextPlan = plan('QA'); await page.locator('#infographic-mode').selectOption('QA');
    const qa = await submit(page); assert.equal(qa.duration, 24); assert.equal(await page.locator('#qa-mode').isChecked(), false); await context.close();
  });
  await check('ordinary_options_restore_after_explicit_mode_change', async () => {
    const {context, page} = await open(); await page.locator('#duration').fill('96'); await page.locator('#quality').selectOption('CINEMA'); await page.locator('#tts').check();
    await page.locator('#infographic-mode').selectOption('QA'); await page.locator('#infographic-mode').selectOption('PRODUCTION'); await page.locator('#infographic-mode').selectOption('NONE');
    assert.equal(await page.locator('#duration').inputValue(), '96'); assert.equal(await page.locator('#quality').inputValue(), 'CINEMA'); assert.equal(await page.locator('#tts').isChecked(), true); assert.equal(await page.locator('#tts').isDisabled(), false); await context.close();
  });
  await check('actual_exported_helpers_reject_partial_forged_or_unknown_selection', async () => {
    const {context, page} = await open();
    const results = await page.evaluate(async () => {
      const {buildCreationRequest, infographicPlanSelection} = await import('/static/app.js');
      const base = {metadata: {infographic: {version: 'v022', parent_renderer_family: 'story-progression-v021'}}, request: {direction_profile: 'SECOND_EVENT_ADAPTIVE_WIDE_TEST'}, scenes: [{infographic: {version: 'v022', parent_renderer_family: 'story-progression-v021'}}]};
      const variants = [structuredClone(base), structuredClone(base), structuredClone(base), structuredClone(base), structuredClone(base)];
      variants[0].metadata.infographic.version = 'v021'; delete variants[1].scenes[0].infographic; variants[2].scenes = []; variants[3].scenes[0].infographic.parent_renderer_family = 'production-earth-v1'; variants[4].request.direction_profile = 'MAP_INFOGRAPHIC_PRODUCTION_V022';
      let errors = 0;
      for (const [values, record] of [[{infographic_mode: 'UNKNOWN'}, null], [{infographic_mode: 'PRODUCTION'}, []], [{infographic_mode: 'NONE', topic: 'topic', duration: 24, direction_profile: 'UNKNOWN'}, null]]) try { buildCreationRequest(values, record); } catch {errors++;}
      return {valid: infographicPlanSelection(base), variants: variants.map(value => infographicPlanSelection(value).valid), wrongExpected: infographicPlanSelection(base, 'PRODUCTION').valid, errors};
    });
    assert.equal(results.valid.kind, 'QA'); assert.deepEqual(results.variants, [false, false, false, false, false]); assert.equal(results.wrongExpected, false); assert.equal(results.errors, 3); await context.close();
  });
  await check('invalid_authored_json_is_not_posted_and_no_script_is_invented', async () => {
    const {context, page} = await open(); await page.locator('#infographic-mode').selectOption('PRODUCTION');
    assert.equal(await page.locator('#infographic-script-file').inputValue(), '');
    await page.locator('#infographic-script-file').setInputFiles({name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{invalid')});
    await page.locator('#create-plan').click(); await page.locator('#notice').waitFor({state: 'visible'});
    assert.equal(posts.length, 0); assert.ok((await page.locator('#notice-message').textContent()).includes('JSON')); await context.close();
  });
  assert.deepEqual(errors, []); report.passed = true; report.total = Object.keys(report.checks).length;
  process.stdout.write(JSON.stringify(report) + '\n');
} finally {await browser.close();server.closeAllConnections();await new Promise(resolve => server.close(resolve));http.globalAgent.destroy();}
