#!/usr/bin/env node
// Actual mobile Chromium against an isolated TEST_ONLY local TLS fixture.
// This verifies browser/security behavior, never NVIDIA or paid GPU operation.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, readFile, rm, stat, writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {tmpdir, userInfo} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const output = process.env.WORLD_ENGINE_STUDIO_EVIDENCE_DIR || await mkdtemp(path.join(tmpdir(), 'studio-https-mobile-evidence-'));
await mkdir(output, {recursive: true});
const report = {schema: 'WORLD_ENGINE_STUDIO_HTTPS_MOBILE_CPU_TEST_V1', testOnly: true, actualChromium: false, tlsFixture: true, gpuExecuted: false, gpuRenderingVerified: false, dropboxExternalVerified: false, checks: []};
let browser, browserTemp, fixture, fixtureTemp;
let activeCheck = 'fixture_configuration';
async function check(name, action) {
  activeCheck = name;
  await action();
  report.checks.push({name, status: 'PASS'});
}
async function waitKoreanFont(page) {
  const loaded = await page.evaluate(async () => {
    const font = '16px WorldEngineStudioSetup';
    const sample = '초기 설정 관리자 영상 제작';
    const faces = await document.fonts.load(font, sample);
    await document.fonts.ready;
    return {faceCount: faces.length, allLoaded: faces.every(face => face.status === 'loaded'),
      available: document.fonts.check(font, sample),
      bodyUsesFamily: getComputedStyle(document.body).fontFamily.includes('WorldEngineStudioSetup')};
  });
  assert.ok(loaded.faceCount > 0, 'KOREAN_UI_FONT_FACE_REQUIRED');
  assert.equal(loaded.allLoaded, true, 'KOREAN_UI_FONT_LOAD_REQUIRED');
  assert.equal(loaded.available, true, 'KOREAN_UI_FONT_AVAILABLE_REQUIRED');
  assert.equal(loaded.bodyUsesFamily, true, 'KOREAN_UI_FONT_STYLE_REQUIRED');
}
try {
  let testURL = process.env.WORLD_ENGINE_HTTPS_TEST_URL;
  let ownerFile = process.env.WORLD_ENGINE_HTTPS_TEST_OWNER_FILE;
  if (!testURL) {
    fixtureTemp = await mkdtemp(path.join(tmpdir(), 'studio-https-mobile-fixture-'));
    const infoPath = path.join(fixtureTemp, 'info.json');
    let fixtureError = false;
    fixture = spawn(process.env.WORLD_ENGINE_PYTHON || '/usr/bin/python3', ['-B', path.join(here, 'tls_fixture.py'), '--info', infoPath], {stdio: ['ignore', 'ignore', 'ignore'], env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}});
    fixture.once('error', () => { fixtureError = true; });
    let info;
    for (let attempt = 0; attempt < 150; attempt += 1) {
      if (fixtureError || fixture.exitCode !== null) throw new Error('TEST_ONLY_TLS_FIXTURE_START_FAILED');
      try { info = JSON.parse(await readFile(infoPath, 'utf8')); break; } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    if (!info) throw new Error('TEST_ONLY_TLS_FIXTURE_START_TIMEOUT');
    testURL = info.origin || info.url;
    ownerFile = info.ownerFile;
  }
  assert.ok(testURL && ownerFile, 'TEST_ONLY_TLS_FIXTURE_REQUIRED');
  const origin = new URL(testURL).origin;
  assert.equal(new URL(origin).protocol, 'https:', 'TEST_ONLY_HTTPS_REQUIRED');
  assert.match(new URL(origin).hostname, /(?:^localhost$|^127\.0\.0\.1$|\.invalid$)/, 'TEST_ONLY_LOCAL_HOST_REQUIRED');
  const ownerStat = await stat(ownerFile);
  assert.equal(ownerStat.isFile(), true, 'TEST_ONLY_OWNER_FILE_REQUIRED');
  assert.equal(ownerStat.mode & 0o077, 0, 'TEST_ONLY_OWNER_FILE_MUST_BE_PRIVATE');
  const owner = (await readFile(ownerFile, 'utf8')).trimEnd();
  assert.ok(owner.length >= 16 && owner.length <= 256, 'TEST_ONLY_OWNER_LENGTH_REQUIRED');
  let playwright;
  const require = createRequire(import.meta.url);
  for (const manifest of [path.resolve(here, '../../../../cinematic-world-map/package.json'), '/opt/rtx-package/repo/cinematic-world-map/package.json']) {
    try { if (existsSync(manifest)) { playwright = createRequire(manifest)('playwright'); break; } } catch {}
  }
  if (!playwright) { try { playwright = require('playwright'); } catch {} }
  if (!playwright) throw new Error('PLAYWRIGHT_UNAVAILABLE');
  const executablePath = process.env.WORLD_ENGINE_CHROMIUM_PATH || ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/opt/google/chrome/chrome'].find(existsSync);
  browserTemp = await mkdtemp(path.join(tmpdir(), 'studio-https-mobile-browser-'));
  browser = await playwright.chromium.launch({headless: true, executablePath, env: {...process.env, HOME: userInfo().homedir, XDG_CONFIG_HOME: path.join(browserTemp, 'config'), XDG_CACHE_HOME: path.join(browserTemp, 'cache')}, args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--host-resolver-rules=MAP studio-ci.invalid 127.0.0.1', '--proxy-bypass-list=studio-ci.invalid']});
  report.actualChromium = true;
  const context = await browser.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 1, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true});
  let page = await context.newPage();
  let renderStartRequests = 0;
  const fontRequests = [];
  context.on('request', request => { if (request.resourceType() === 'font') fontRequests.push(new URL(request.url())); });
  context.on('request', request => { if (/\/api\/(?:start|jobs\/[^/]+\/start)(?:\?|$)/.test(request.url()) && request.method() === 'POST') renderStartRequests += 1; });
  activeCheck = 'mobile_browser_navigation';
  await page.goto(origin + '/setup');
  activeCheck = 'mobile_setup_challenge_ready';
  await page.waitForFunction(() => !document.getElementById('setup-authenticate').disabled);
  await check('setup_screen_mobile_tls_no_horizontal_overflow', async () => {
    assert.equal(await page.evaluate(() => isSecureContext && location.protocol === 'https:'), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.match(await page.textContent('main'), /영상 제작이 시작되지 않습니다/);
    assert.equal(await page.inputValue('#setup-origin'), '');
    assert.equal(await page.locator('#studio-login-link').isVisible(), false);
  });
  await check('setup_challenge_cookie_secure_httponly_strict', async () => {
    const cookies = await context.cookies(origin);
    const challenge = cookies.find(cookie => cookie.name === '__Host-world_studio_setup_challenge');
    assert.ok(challenge);
    assert.equal(challenge.secure, true);
    assert.equal(challenge.httpOnly, true);
    assert.equal(challenge.sameSite, 'Strict');
    assert.equal(challenge.path, '/');
  });
  await check('korean_ui_font_loaded_in_actual_mobile_chromium', async () => {
    await waitKoreanFont(page);
    assert.ok(fontRequests.some(url => url.origin === origin && url.pathname === '/setup-font.woff2'), 'KOREAN_UI_LOCAL_FONT_REQUEST_REQUIRED');
    assert.equal(fontRequests.every(url => url.origin === origin), true, 'EXTERNAL_UI_FONT_REQUEST_FORBIDDEN');
    report.koreanUIFont = {family: 'WorldEngineStudioSetup', status: 'LOADED', externalFontRequest: false};
  });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({path: path.join(output, '01_MOBILE_HTTPS_SETUP.png'), fullPage: true});
  await check('initial_setup_blocks_unauthenticated_render_start', async () => {
    const status = await page.evaluate(async () => (await fetch('/api/start', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: '{}'})).status);
    assert.ok([401, 403, 409, 423, 503].includes(status));
    report.setupRenderDeniedStatus = status;
    renderStartRequests = 0;
  });
  await check('initial_address_mismatch_rejected_by_server_origin_policy', async () => {
    await page.fill('#setup-origin', 'https://other-test-only.invalid');
    await page.fill('#setup-owner-code', owner);
    await page.click('#setup-authenticate');
    await page.waitForFunction(() => !document.getElementById('setup-error').hidden);
    assert.match(await page.textContent('#setup-error-message'), /주소/);
    assert.equal(await page.inputValue('#setup-owner-code'), '');
    assert.equal(await page.locator('#setup-confirmation').isVisible(), false);
    await page.click('#setup-retry');
    await page.waitForFunction(() => !document.getElementById('setup-authenticate').disabled);
  });
  await check('incorrect_owner_rejected_and_password_cleared', async () => {
    await page.fill('#setup-origin', origin);
    const incorrect = owner.slice(0, -1) + (owner.endsWith('x') ? 'y' : 'x');
    await page.fill('#setup-owner-code', incorrect);
    await page.click('#setup-authenticate');
    await page.waitForFunction(() => !document.getElementById('setup-error').hidden);
    assert.equal(await page.inputValue('#setup-owner-code'), '');
    assert.equal(await page.locator('#setup-confirmation').isVisible(), false);
    assert.match(await page.textContent('#setup-error-message'), /관리자|설정/);
    await page.click('#setup-retry');
    await page.waitForFunction(() => !document.getElementById('setup-authenticate').disabled);
  });
  await check('setup_administrator_authentication_and_explicit_confirmation', async () => {
    await page.fill('#setup-origin', origin);
    await page.fill('#setup-owner-code', owner);
    await page.click('#setup-authenticate');
    await page.waitForFunction(() => !document.getElementById('setup-confirmation').hidden);
    assert.equal(await page.textContent('#confirmed-origin'), origin);
    assert.equal(await page.inputValue('#setup-owner-code'), '');
    assert.equal(await page.isDisabled('#setup-register'), true);
    assert.equal(await page.isChecked('#setup-origin-confirm'), false);
    assert.equal(await page.evaluate(() => localStorage.length), 0);
    const cookies = await context.cookies(origin);
    const session = cookies.find(cookie => cookie.name === '__Host-world_studio_setup');
    assert.ok(session);
    assert.equal(session.secure, true);
    assert.equal(session.httpOnly, true);
    assert.equal(session.sameSite, 'Strict');
  });
  await waitKoreanFont(page);
  await page.screenshot({path: path.join(output, '02_MOBILE_HTTPS_CONFIRMATION.png'), fullPage: true});
  await check('double_activation_commits_once_and_requires_fresh_normal_login', async () => {
    let commits = 0;
    page.on('request', request => { if (new URL(request.url()).pathname === '/api/setup/origin' && request.method() === 'POST') commits += 1; });
    await page.check('#setup-origin-confirm');
    await page.evaluate(() => { const button = document.getElementById('setup-register'); button.click(); button.click(); });
    await page.waitForFunction(() => !document.getElementById('setup-complete').hidden);
    assert.equal(commits, 1);
    assert.equal(await page.getAttribute('#studio-login-link', 'href'), '/login');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  });
  await waitKoreanFont(page);
  await page.screenshot({path: path.join(output, '03_MOBILE_HTTPS_REGISTERED.png'), fullPage: true});
  // The explicit API denial check is separate from requests made by the UI.
  await check('setup_ui_never_posts_render_start', async () => { assert.equal(renderStartRequests, 0); });
  await check('registered_origin_survives_browser_disconnect_and_reconnect', async () => {
    await page.close();
    page = await context.newPage();
    await page.goto(origin + '/login');
    await page.waitForSelector('#login-form');
    assert.equal(await page.locator('#owner-code').count(), 1);
    assert.equal(await page.inputValue('#owner-code'), '');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  });
  await check('normal_studio_login_is_separate_and_existing_ui_is_reused', async () => {
    await page.fill('#owner-code', owner);
    await page.click('#login');
    await page.waitForURL(origin + '/');
    await page.waitForSelector('#prompt');
    assert.equal(await page.locator('#sfx-enabled').count(), 1);
    assert.equal(await page.locator('#duration').count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  });
  await waitKoreanFont(page);
  await page.screenshot({path: path.join(output, '04_MOBILE_STUDIO_READY.png'), fullPage: true});
  assert.equal(renderStartRequests, 0);
  assert.equal(fontRequests.every(url => url.origin === origin), true, 'EXTERNAL_UI_FONT_REQUEST_FORBIDDEN');
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.failedCheck = activeCheck;
  report.errorType = /^[A-Za-z]{1,40}$/.test(error?.name || '') ? error.name : 'Error';
  // Error messages can contain request context. Keep only named, non-secret classifications.
  report.errorCode = /^[A-Z][A-Z0-9_]{3,100}$/.test(String(error?.message || '')) ? error.message : 'MOBILE_HTTPS_ASSERTION_FAILED';
  const networkFailure = String(error?.message || '').match(/net::(ERR_[A-Z0-9_]+)/);
  if (networkFailure) report.errorCode = networkFailure[1];
  process.exitCode = 2;
} finally {
  if (browser) await browser.close();
  if (browserTemp) await rm(browserTemp, {recursive: true, force: true});
  if (fixture) {
    const stopped = new Promise(resolve => fixture.once('exit', resolve));
    fixture.kill('SIGTERM');
    await Promise.race([stopped, new Promise(resolve => setTimeout(resolve, 3000))]);
    if (fixture.exitCode === null && fixture.signalCode === null) fixture.kill('SIGKILL');
  }
  if (fixtureTemp) await rm(fixtureTemp, {recursive: true, force: true});
  report.passCount = report.checks.filter(row => row.status === 'PASS').length;
  await writeFile(path.join(output, 'MOBILE_HTTPS_REPORT.json'), JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify(report) + '\n');
}
