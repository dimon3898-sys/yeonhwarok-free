// Actual mobile Chromium UI with intercepted synthetic providers only.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const origin = 'https://mobile-fixture.invalid';
const redirectUri = origin + '/connect/';
const repository = 'dimon3898-sys/yeonhwarok-free';
const ref = 'development/dropbox-mobile-connect-v1-20261018';
const names = {
  key: 'WORLD_ENGINE_STUDIO_BACKUP_KEY', appKey: 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY',
  appSecret: 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET', refresh: 'WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN'
};
const appKey = 'appkeyfixture', pat = 'github_pat_SYNTHETIC_FIXTURE_ONLY_1234567890';
const access = 'accessfixture'.repeat(3), refresh = 'refreshfixture'.repeat(3);
const image = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0';
const evidence = process.env.MOBILE_EVIDENCE_DIR;
if (evidence) mkdirSync(evidence, { recursive: true });
let browser;
let assertions = 0;
function check(condition, label) { assert.ok(condition, label); assertions++; }
try {
  browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined),
    args: ['--no-sandbox', '--disable-gpu'] });
  for (const mode of ['disabled', 'pending', 'pass', 'blocked']) {
    const context = await browser.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    const errors = [], writes = [], unexpected = [], secretBodies = [];
    const existing = new Set([names.key, names.appSecret]);
    let authorization = null, publicKey = null, dispatches = 0, proofReady = mode === 'pass' || mode === 'blocked';
    page.on('pageerror', () => errors.push('PAGE_SCRIPT_ERROR'));
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      const cors = { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Headers': 'Authorization,Content-Type,X-GitHub-Api-Version,Accept', 'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS' };
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors, body: '' });
      if (url.origin === origin) {
        let path = url.pathname === '/connect/' ? 'index.html' : url.pathname.replace('/connect/', '');
        if (path === 'config.js' && mode !== 'disabled') {
          return route.fulfill({ contentType: 'application/javascript', body:
            'window.WORLD_CONNECT_CONFIG=' + JSON.stringify({ enabled: true, redirectUri, allowedRedirectUris: [redirectUri] }) + ';' });
        }
        check(!request.headers()['referer']?.includes('code='), 'authorization code not in asset referrer');
        if (!/^[A-Za-z0-9_./-]+$/.test(path) || path.includes('..') || !existsSync(join(root, 'web', path))) return route.fulfill({ status: 404, body: '' });
        return route.fulfill({ contentType: path.endsWith('.js') ? 'application/javascript' : path.endsWith('.css') ? 'text/css' : 'text/html', body: readFileSync(join(root, 'web', path)) });
      }
      if (url.origin === 'https://www.dropbox.com' && url.pathname === '/oauth2/authorize') {
        authorization = url;
        return route.fulfill({ contentType: 'text/html', body: '<html><body>CPU synthetic consent fixture</body></html>' });
      }
      if (url.href === 'https://api.dropboxapi.com/oauth2/token') {
        const form = new URLSearchParams(request.postData());
        check(form.get('code_verifier')?.length >= 43 && !form.has('client_secret'), 'browser PKCE without App Secret');
        return route.fulfill({ contentType: 'application/json', headers: cors, body: JSON.stringify({ token_type: 'bearer', access_token: access, refresh_token: refresh,
          expires_in: 14400, account_id: 'account_fixture_123456789', scope: 'files.content.read files.content.write files.metadata.read' }) });
      }
      const prefix = '/repos/' + repository;
      if (url.origin === 'https://api.github.com' && url.pathname.startsWith(prefix)) {
        const suffix = url.pathname.slice(prefix.length);
        const body = request.postData() || '';
        if (request.method() !== 'GET') secretBodies.push(body);
        const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', headers: cors, body: JSON.stringify(data) });
        if (suffix === '/actions/secrets/public-key') return json({ key: publicKey, key_id: 'keyfixture123' });
        if (suffix.startsWith('/actions/secrets/')) {
          const name = suffix.split('/').at(-1);
          if (request.method() === 'GET') return json(existing.has(name) ? { name } : { message: 'Not Found' }, existing.has(name) ? 200 : 404);
          check(request.method() === 'PUT', 'only Secret PUT');
          const sealed = JSON.parse(body);
          check(Object.keys(sealed).sort().join(',') === 'encrypted_value,key_id', 'sealed Secret body only');
          check(Buffer.from(sealed.encrypted_value, 'base64').length >= 48, 'real sealed box overhead');
          writes.push(name); existing.add(name);
          return route.fulfill({ status: 204, headers: cors, body: '' });
        }
        if (suffix.endsWith('/dispatches')) { dispatches++; return route.fulfill({ status: 204, headers: cors, body: '' }); }
        if (suffix.endsWith('/runs')) {
          return json({ workflow_runs: dispatches ? [{ id: 123456789, run_attempt: 1, status: 'completed', conclusion: 'success',
            head_branch: ref, event: 'workflow_dispatch', path: '.github/workflows/studio-dropbox-mobile-v1.yml' }] : [] });
        }
        if (suffix === '/actions/runs/123456789') return json({ id: 123456789, run_attempt: 1, status: 'completed', conclusion: 'success',
          head_branch: ref, event: 'workflow_dispatch', path: '.github/workflows/studio-dropbox-mobile-v1.yml' });
        if (suffix.startsWith('/contents/')) {
          if (!proofReady) return json({ message: 'Not Found' }, 404);
          const proof = { schema: 'WORLD_ENGINE_MOBILE_DROPBOX_PROOF_V1', runId: 123456789, attempt: 1,
            status: 'PASS', reasonCode: 'MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED', sourceImage: image,
            offlineTokenRefreshVerified: true, metadataReadVerified: true, externalStorageRecoveryVerified: true,
            gpuExecuted: false, productionRenderingStarted: false,
            proofId: 'a'.repeat(64), checkpointId: 'b'.repeat(64), expiresUnix: Math.floor(Date.now() / 1000) + 3600 };
          if (mode === 'blocked') Object.assign(proof, { status: 'BLOCKED', reasonCode: 'MOBILE_DROPBOX_SECRETS_NOT_BOUND',
            offlineTokenRefreshVerified: false, metadataReadVerified: false, externalStorageRecoveryVerified: false });
          const text = JSON.stringify(proof);
          return json({ type: 'file', path: suffix.slice('/contents/'.length), encoding: 'base64', size: Buffer.byteLength(text), content: Buffer.from(text).toString('base64') });
        }
      }
      unexpected.push(url.origin + url.pathname); return route.abort();
    });
    await page.goto(redirectUri);
    if (mode === 'disabled') {
      await page.locator('#blocked').waitFor({ state: 'visible' });
      check(await page.locator('#consent').isHidden(), 'no unconfigured OAuth start');
      check(dispatches === 0 && writes.length === 0, 'disabled hosting performs no external writes');
      if (evidence) await page.screenshot({ path: join(evidence, '01_AUTHORIZATION_REQUIRED.png'), fullPage: true });
      await context.close(); continue;
    }
    await page.locator('#consent').waitFor({ state: 'visible' });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile has no horizontal overflow');
    publicKey = await page.evaluate(async () => { await sodium.ready; return sodium.to_base64(sodium.crypto_box_keypair().publicKey, sodium.base64_variants.ORIGINAL); });
    if (evidence && mode === 'pass') await page.screenshot({ path: join(evidence, '02_MOBILE_CONNECT.png'), fullPage: true });
    await page.locator('#appKey').fill(appKey);
    await page.locator('#connectDropbox').click();
    await page.waitForURL('https://www.dropbox.com/**');
    check(authorization.searchParams.get('token_access_type') === 'offline', 'offline grant requested');
    check(authorization.searchParams.get('code_challenge_method') === 'S256', 'S256 PKCE requested');
    await page.goto(redirectUri + '?code=codefixture123&state=' + authorization.searchParams.get('state'));
    await page.locator('#status').filter({ hasText: 'Dropbox 승인을 확인했습니다' }).waitFor();
    check(page.url() === redirectUri, 'callback query immediately scrubbed');
    check(await page.evaluate(() => sessionStorage.length === 0 && localStorage.length === 0), 'only consumed PKCE session persisted');
    check(!((await page.locator('body').innerText()).includes(refresh)), 'Refresh Token absent from screen');
    await page.locator('#githubCredential').fill(pat);
    await page.locator('#checkGithub').click();
    await page.locator('#status').filter({ hasText: 'GitHub 권한을 확인했습니다' }).waitFor();
    check(await page.locator('#appSecretArea').isHidden(), 'existing App Secret not requested again');
    if (evidence && mode === 'pass') await page.screenshot({ path: join(evidence, '03_SECRET_PERMISSION.png'), fullPage: true });
    await page.locator('#saveConnection').click();
    await page.locator('#verification').waitFor({ state: 'visible' });
    check(dispatches === 1, 'exactly one free proof dispatch');
    check(writes.length === 3 && writes.includes(names.appKey) && writes.includes(names.refresh)
      && writes.some(name => name.startsWith('WORLD_ENGINE_STUDIO_DROPBOX_BINDING_')), 'needed connection Secrets and identity binding updated');
    check(!writes.includes(names.key) && !writes.includes(names.appSecret), 'existing key and App Secret preserved');
    check(secretBodies.every(body => !body.includes(refresh) && !body.includes(pat) && !body.includes(access)), 'no plaintext secret body sent to GitHub');
    if (mode === 'pending') {
      check(!((await page.locator('body').innerText()).includes('복구 검증을 통과했습니다')), 'workflow success alone never shown as backup PASS');
      proofReady = true;
      await page.locator('#refreshStatus').click();
    }
    if (mode === 'blocked') {
      await page.locator('#verificationState').filter({ hasText: '완료되지 않았습니다' }).waitFor();
      check(await page.locator('#refreshStatus').isHidden() && await page.locator('#restart').isVisible(), 'failed proof exposes a working restart instead of a dead refresh button');
    } else await page.locator('#status').filter({ hasText: 'Dropbox 연결 완료' }).waitFor();
    check(await page.locator('#githubCredential').inputValue() === '', 'authorization input cleared');
    if (evidence && mode === 'pass') await page.screenshot({ path: join(evidence, '04_SYNTHETIC_PROOF_RESULT.png'), fullPage: true });
    check(errors.length === 0 && unexpected.length === 0, 'no browser script failure or unexpected network');
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'result remains mobile safe');
    await context.close();
  }
  process.stdout.write(JSON.stringify({ status: 'PASS', assertions, browser: browser.version(), viewport: '412x915',
    syntheticProvidersOnly: true, realDropboxConnected: false, realGitHubSecretWritten: false, gpuExecuted: false }) + '\n');
} catch (error) {
  const reason = error?.message?.split('\n')[0] || 'MOBILE_PROBE_FAILED';
  process.stderr.write(JSON.stringify({ status: 'FAIL', reasonCode: 'MOBILE_PROBE_FAILED', detail: reason.slice(0, 160), gpuExecuted: false }) + '\n');
  process.exitCode = 1;
} finally { if (browser) await browser.close(); }
