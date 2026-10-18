import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { webcrypto } from 'node:crypto';
const require = createRequire(import.meta.url);
const core = require('../web/connect-core.js');

const REDIRECT = 'https://example.github.io/world-engine-connect/';
const APP = 'publicappkeyexample';
const APPSECRET = 'test_app_secret_only';
const PAT = 'github_pat_test_credential_only';
const ACCESS = 'test_access_credential_only';
const REFRESH = 'test_refresh_credential_only';
const ACCOUNT = 'dbid:test_account_only';
const BINDING = 'WORLD_ENGINE_STUDIO_DROPBOX_BINDING_' + Buffer.from(await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(APP + '\0' + ACCOUNT))).toString('hex').toUpperCase();
const PUB = btoa(String.fromCharCode(...new Uint8Array(32).fill(7)));
const STATE = 'world-engine.dropbox.pkce.v1';
const validGrant = () => ({ appKey: APP, accountId: ACCOUNT, accessToken: ACCESS, refreshToken: REFRESH, expiresAt: 1700000010000, scope: [...core.SCOPES] });
const reply = (value, status = 200) => new Response(status === 204 ? null : JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } });
class MemoryStorage {
  data = new Map();
  getItem(name) { return this.data.get(name) ?? null; }
  setItem(name, value) { this.data.set(name, value); }
  removeItem(name) { this.data.delete(name); }
}
function fixture(options = {}) {
  const storage = new MemoryStorage();
  const calls = [];
  const secretNames = new Set(options.existing ?? [...Object.values(core.NAMES), BINDING]);
  let time = 1700000000000;
  const sodium = {
    ready: Promise.resolve(),
    crypto_box_seal(bytes, key) {
      assert.equal(key.length, 32);
      return new Uint8Array(bytes.length + 48).fill(81); // Mock cryptographic boundary, never provider proof.
    }
  };
  const fetcher = async (url, init) => {
    calls.push({ url, init });
    if (options.fetch) return options.fetch(url, init, secretNames);
    if (url === 'https://api.dropboxapi.com/oauth2/token') return reply({ account_id: ACCOUNT, access_token: ACCESS, refresh_token: REFRESH, token_type: 'bearer', expires_in: 14400, scope: core.SCOPES.join(' ') });
    if (url === 'https://api.dropboxapi.com/2/files/list_folder') return reply({ entries: [], has_more: false });
    const prefix = 'https://api.github.com/repos/' + core.REPOSITORY;
    assert.ok(url.startsWith(prefix));
    const path = url.slice(prefix.length);
    if (path === '/actions/secrets/public-key') return reply({ key: PUB, key_id: '1234' });
    if (path.startsWith('/actions/secrets/')) {
      const name = path.slice('/actions/secrets/'.length);
      if (init.method === 'PUT') { secretNames.add(name); return reply({}, 204); }
      return secretNames.has(name) ? reply({ name, created_at: '2026-10-18T00:00:00Z' }) : reply({ message: 'Not Found' }, 404);
    }
    if (path.endsWith('/dispatches')) return reply({}, 204);
    throw new Error('unexpected mock endpoint');
  };
  const client = core.createClient({ redirectUri: REDIRECT, allowedRedirectUris: [REDIRECT], storage, fetch: fetcher, crypto: webcrypto, sodium: options.sodium ?? sodium, now: () => time });
  return { client, storage, calls, secretNames, setTime: value => time = value };
}
async function callback(f, mutate) {
  const started = await f.client.begin(APP);
  const auth = new URL(started.authorizationURL);
  const url = new URL(REDIRECT);
  url.searchParams.set('code', 'test_code_only');
  url.searchParams.set('state', auth.searchParams.get('state'));
  if (mutate) mutate(url);
  return url.href;
}

test('strict registered HTTPS redirect; no inferred Host or arbitrary redirect', () => {
  assert.equal(core.callbackURL(REDIRECT, [REDIRECT]), REDIRECT);
  for (const url of ['http://example.github.io/', 'https://evil.example/', REDIRECT + '?a=b', REDIRECT + '#x', 'https://u:p@example.github.io/world-engine-connect/', 'https://localhost/']) {
    assert.throws(() => core.callbackURL(url, [REDIRECT]));
  }
  assert.throws(() => core.callbackURL(REDIRECT, []), /REDIRECT_ALLOWLIST_REQUIRED/);
});
test('app key is validated without accepting credential or URL syntax', () => {
  assert.equal(core.validateAppKey(APP), APP);
  for (const value of ['', 'abc', 'https://example.com', APP + '\n', null]) assert.throws(() => core.validateAppKey(value), /APP_KEY_INVALID/);
});
test('S256 verifier/challenge matches Web Crypto and state is unpredictable length', async () => {
  const pkce = await core.makePkce(webcrypto);
  assert.match(pkce.verifier, /^[A-Za-z0-9_-]{64}$/);
  assert.match(pkce.state, /^[A-Za-z0-9_-]{43}$/);
  const digest = new Uint8Array(await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(pkce.verifier)));
  assert.equal(pkce.challenge, Buffer.from(digest).toString('base64url'));
});
test('authorization URL requests offline mode and exact three scopes; only PKCE session stored', async () => {
  const f = fixture();
  const { authorizationURL } = await f.client.begin(APP);
  const url = new URL(authorizationURL);
  assert.equal(url.origin + url.pathname, 'https://www.dropbox.com/oauth2/authorize');
  assert.equal(url.searchParams.get('token_access_type'), 'offline');
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(url.searchParams.get('redirect_uri'), REDIRECT);
  assert.deepEqual(url.searchParams.get('scope').split(' '), core.SCOPES);
  const text = JSON.stringify([...f.storage.data]);
  for (const credential of [APPSECRET, PAT, ACCESS, REFRESH]) assert.ok(!text.includes(credential));
  assert.equal(f.calls.length, 0);
});
test('valid callback exchanges public PKCE without app secret, then consumes session', async () => {
  const f = fixture();
  const grant = await f.client.finish(await callback(f), APP);
  assert.equal(grant.refreshToken, REFRESH);
  assert.equal(grant.accountId, ACCOUNT);
  assert.equal(f.storage.getItem(STATE), null);
  const request = f.calls[0];
  const form = new URLSearchParams(request.init.body);
  assert.equal(form.get('grant_type'), 'authorization_code');
  assert.equal(form.get('redirect_uri'), REDIRECT);
  assert.ok(form.has('code_verifier'));
  assert.equal(form.has('client_secret'), false);
  assert.equal(request.init.redirect, 'error');
  assert.equal(request.init.credentials, 'omit');
  assert.equal(request.init.referrerPolicy, 'no-referrer');
  assert.equal(f.storage.data.size, 0);
});
test('callback page can recover public app key without exposing verifier or OAuth tokens', async () => {
  const f = fixture();
  assert.equal(f.client.pending(), null);
  await f.client.begin(APP);
  const pending = f.client.pending();
  assert.deepEqual(Object.keys(pending).sort(), ['appKey', 'expiresAt']);
  assert.equal(pending.appKey, APP);
  f.setTime(pending.expiresAt);
  assert.equal(f.client.pending(), null);
});
test('state mismatch consumes session and makes replay impossible', async () => {
  const f = fixture();
  const url = await callback(f, parsed => parsed.searchParams.set('state', 'other'));
  await assert.rejects(f.client.finish(url, APP), /OAUTH_STATE_MISMATCH/);
  await assert.rejects(f.client.finish(url, APP), /OAUTH_STATE_MISSING/);
  assert.equal(f.calls.length, 0);
});
test('expired/future or malformed PKCE state fails before token request', async () => {
  for (const mutation of [value => { value.expiresAt = 1699999999999; }, value => { value.createdAt += 1; }, value => { value.verifier = 'bad'; }]) {
    const f = fixture();
    const url = await callback(f);
    const session = JSON.parse(f.storage.getItem(STATE));
    mutation(session);
    f.storage.setItem(STATE, JSON.stringify(session));
    await assert.rejects(f.client.finish(url, APP), /OAUTH_STATE_INVALID_OR_EXPIRED/);
    assert.equal(f.calls.length, 0);
  }
});
test('callback rejects unregistered path, duplicate state/code and unexpected parameters', async () => {
  for (const mutate of [u => u.pathname = '/other', u => u.searchParams.append('state', u.searchParams.get('state')), u => u.searchParams.append('code', 'another_code'), u => u.searchParams.set('next', 'https://evil.example')]) {
    const f = fixture();
    await assert.rejects(f.client.finish(await callback(f, mutate), APP), /OAUTH_(CALLBACK_INVALID|STATE_MISMATCH|CODE_INVALID)/);
    assert.equal(f.calls.length, 0);
  }
});
test('authorization denial is not token success and no remote exchange occurs', async () => {
  const f = fixture();
  const url = await callback(f, u => { u.searchParams.delete('code'); u.searchParams.set('error', 'access_denied'); });
  await assert.rejects(f.client.finish(url, APP), /DROPBOX_AUTHORIZATION_DENIED/);
  assert.equal(f.calls.length, 0);
});
test('missing refresh token/account, invalid TTL, wrong type or missing metadata scope fail closed', async () => {
  for (const change of [{ refresh_token: '' }, { account_id: '' }, { account_id: undefined }, { expires_in: 0 }, { token_type: 'other' }, { scope: 'files.content.read files.content.write' }]) {
    const f = fixture({ fetch: () => reply({ account_id: ACCOUNT, access_token: ACCESS, refresh_token: REFRESH, token_type: 'bearer', expires_in: 14400, scope: core.SCOPES.join(' '), ...change }) });
    await assert.rejects(f.client.finish(await callback(f), APP), /DROPBOX_TOKEN_INVALID_OR_SCOPE_MISSING/);
  }
});
test('provider HTTP/body/CORS errors expose only safe enum, without automatic retries', async () => {
  for (const handler of [() => reply({ secret: REFRESH }, 400), () => { throw new Error(REFRESH); }, () => new Response(REFRESH, { status: 200 })]) {
    const f = fixture({ fetch: handler });
    await assert.rejects(f.client.finish(await callback(f), APP), error => !error.message.includes(REFRESH) && /^DROPBOX_TOKEN_/.test(error.message));
    assert.equal(f.calls.length, 1);
  }
});
test('oversize streaming token response is rejected', async () => {
  const f = fixture({ fetch: () => new Response('x'.repeat(65537), { status: 200 }) });
  await assert.rejects(f.client.finish(await callback(f), APP), /DROPBOX_TOKEN_RESPONSE_TOO_LARGE/);
});
test('GitHub metadata uses only fixed repository and never reads Secret values', async () => {
  const f = fixture();
  const metadata = await f.client.githubPreflight(PAT);
  assert.deepEqual(metadata.existing, { key: true, appKey: true, appSecret: true, refresh: true });
  assert.equal(f.calls.length, 5);
  for (const call of f.calls) {
    assert.ok(call.url.startsWith('https://api.github.com/repos/' + core.REPOSITORY + '/actions/secrets/'));
    assert.equal(call.init.headers.Authorization, 'Bearer ' + PAT);
    assert.ok(!call.url.includes(PAT));
    assert.equal(call.init.method, 'GET');
  }
});
test('existing encryption key/app secret preserved; refresh+app key use sealed-box PUT', async () => {
  const f = fixture();
  const receipt = await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP });
  assert.equal(receipt.secretsReady, true);
  assert.equal(receipt.dropboxBackupVerified, false);
  assert.equal(receipt.gpuAllowed, false);
  assert.deepEqual(receipt.preserved, [core.NAMES.key, core.NAMES.appSecret]);
  const puts = f.calls.filter(c => c.init.method === 'PUT');
  assert.deepEqual(puts.map(c => c.url.split('/').at(-1)), [core.NAMES.appKey, core.NAMES.refresh]);
  for (const call of puts) {
    const body = JSON.parse(call.init.body);
    assert.equal(body.key_id, '1234');
    assert.deepEqual(Object.keys(body).sort(), ['encrypted_value', 'key_id']);
    for (const value of [APP, REFRESH, APPSECRET]) assert.ok(!call.init.body.includes(value));
  }
  assert.equal(f.storage.data.size, 0);
});
test('grant is bound to same Dropbox app and cannot save an unrelated refresh credential', async () => {
  const f = fixture();
  await assert.rejects(f.client.configure({ pat: PAT, grant: { ...validGrant(), appKey: 'anotherpublicapp' }, appKey: APP }), /DROPBOX_OFFLINE_GRANT_REQUIRED/);
  assert.equal(f.calls.length, 0);
});
test('legacy unbound app credentials remain unchanged rather than blindly migrated', async () => {
  const f = fixture({ existing: Object.values(core.NAMES) });
  const before = [...f.secretNames];
  await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /EXISTING_DROPBOX_CONNECTION_UNVERIFIED/);
  assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 0);
  assert.deepEqual([...f.secretNames], before);
});
test('different Dropbox account or app cannot overwrite an enrolled connection', async () => {
  for (const change of [{ accountId: 'dbid:another_account_only' }, { appKey: 'anotherpublicapp' }]) {
    const f = fixture();
    const grant = { ...validGrant(), ...change };
    await assert.rejects(f.client.configure({ pat: PAT, grant, appKey: grant.appKey }), /EXISTING_DROPBOX_CONNECTION_UNVERIFIED/);
    assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 0);
    assert.equal(f.secretNames.size, 5);
  }
});
test('sealing plaintext byte arrays are wiped after success and failure', async () => {
  for (const broken of [false, true]) {
    const observed = [];
    const sodium = { ready: Promise.resolve(), crypto_box_seal: bytes => {
      observed.push(bytes);
      if (broken) throw new Error(REFRESH);
      return new Uint8Array(bytes.length + 48).fill(33);
    } };
    const f = fixture({ sodium });
    if (broken) await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /SEALED_BOX_FAILED/);
    else await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP });
    assert.ok(observed.length > 0);
    assert.ok(observed.every(bytes => bytes.every(value => value === 0)));
  }
});
test('missing app secret blocks before any Secret writes', async () => {
  const f = fixture({ existing: [core.NAMES.key] });
  await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /APP_SECRET_REQUIRED/);
  assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 0);
});
test('new encryption key only when API verifies App Folder backup prefix empty', async () => {
  const f = fixture({ existing: [] });
  const result = await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP, appSecret: APPSECRET });
  assert.deepEqual(new Set(result.saved), new Set([...Object.values(core.NAMES), BINDING]));
  const metadata = f.calls.find(c => c.url === 'https://api.dropboxapi.com/2/files/list_folder');
  assert.deepEqual(JSON.parse(metadata.init.body), { path: '/WORLD_ENGINE_STUDIO_BACKUPS_V1', recursive: false, include_deleted: false, limit: 1 });
  const firstPut = f.calls.find(c => c.init.method === 'PUT');
  assert.ok(firstPut.url.endsWith('/' + BINDING));
  assert.ok(!JSON.stringify(f.calls).includes(ACCOUNT));
});
test('partial Secret failure can resume only through its precommitted same-identity marker', async () => {
  let failed = false;
  const f = fixture({ existing: [], fetch: (url, init, names) => {
    if (url === 'https://api.dropboxapi.com/2/files/list_folder') return reply({ entries: [], has_more: false });
    if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
    const name = url.split('/').at(-1);
    if (init.method === 'PUT') {
      if (name === core.NAMES.refresh && !failed) { failed = true; throw new Error(REFRESH); }
      names.add(name); return reply({}, 204);
    }
    return names.has(name) ? reply({ name }) : reply({}, 404);
  } });
  const input = { pat: PAT, grant: validGrant(), appKey: APP, appSecret: APPSECRET };
  await assert.rejects(f.client.configure(input), /GITHUB_NETWORK_OR_CORS_FAILED/);
  assert.ok(f.secretNames.has(BINDING));
  assert.ok(f.secretNames.has(core.NAMES.appKey));
  assert.ok(!f.secretNames.has(core.NAMES.refresh));
  const receipt = await f.client.configure(input);
  assert.equal(receipt.secretsReady, true);
  assert.ok(receipt.preserved.includes(core.NAMES.key));
  assert.equal(f.calls.filter(c => c.init.method === 'PUT' && c.url.endsWith('/' + BINDING)).length, 1);
  assert.equal(f.calls.filter(c => c.init.method === 'PUT' && c.url.endsWith('/' + core.NAMES.key)).length, 1);
});
test('encryption key appearing after preflight is preserved by immediate metadata recheck', async () => {
  let keyReads = 0;
  const f = fixture({ existing: [core.NAMES.appSecret], fetch: (url, init, names) => {
    if (url === 'https://api.dropboxapi.com/2/files/list_folder') return reply({ entries: [], has_more: false });
    if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
    const name = url.split('/').at(-1);
    if (name === core.NAMES.key && init.method === 'GET') { keyReads += 1; if (keyReads >= 2) names.add(name); }
    if (init.method === 'PUT') { names.add(name); return reply({}, 204); }
    return names.has(name) ? reply({ name }) : reply({}, 404);
  } });
  const receipt = await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP });
  assert.ok(receipt.preserved.includes(core.NAMES.key));
  assert.equal(f.calls.filter(c => c.init.method === 'PUT' && c.url.endsWith('/' + core.NAMES.key)).length, 0);
});
test('nonempty backup without old encryption key fails rather than replacing key', async () => {
  const f = fixture({ existing: [core.NAMES.appSecret], fetch: (url, init, names) => {
    if (url === 'https://api.dropboxapi.com/2/files/list_folder') return reply({ entries: [{ '.tag': 'folder', name: 'opaque' }], has_more: false });
    if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
    const name = url.split('/').at(-1);
    return names.has(name) ? reply({ name }) : reply({}, 404);
  } });
  await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /EXISTING_BACKUP_KEY_REQUIRED/);
  assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 0);
});
test('Dropbox metadata 409 accepted only for exact path not_found', async () => {
  for (const tag of ['not_found', 'no_permission']) {
    const f = fixture({ existing: [core.NAMES.appSecret], fetch: (url, init, names) => {
      if (url === 'https://api.dropboxapi.com/2/files/list_folder') return reply({ error: { '.tag': 'path', path: { '.tag': tag } } }, 409);
      if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
      const name = url.split('/').at(-1);
      if (init.method === 'PUT') { names.add(name); return reply({}, 204); }
      return names.has(name) ? reply({ name }) : reply({}, 404);
    } });
    if (tag === 'not_found') assert.equal((await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP })).secretsReady, true);
    else await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /DROPBOX_BACKUP_PREFIX_UNVERIFIED/);
  }
});
test('sodium missing or broken seal fails without plain-text fallback', async () => {
  for (const sodium of [{}, { ready: Promise.resolve(), crypto_box_seal: () => new Uint8Array(1) }]) {
    const f = fixture({ sodium });
    await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /SEALED_BOX_(UNAVAILABLE|INVALID)/);
    assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 0);
  }
});
test('ambiguous Secret-write failure is not retried or reported configured', async () => {
  const f = fixture({ fetch: (url, init) => {
    if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
    if (init.method === 'PUT') throw new Error(REFRESH);
    return reply({ name: url.split('/').at(-1) });
  } });
  await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /GITHUB_NETWORK_OR_CORS_FAILED/);
  assert.equal(f.calls.filter(c => c.init.method === 'PUT').length, 1);
  await assert.rejects(f.client.dispatch(PAT), /SECRETS_NOT_CONFIGURED_THIS_SESSION/);
});
test('duplicate same-session configure is blocked before any network writes', async () => {
  let release;
  const wait = new Promise(resolve => { release = resolve; });
  const f = fixture({ fetch: async (url, init) => {
    await wait;
    if (url.endsWith('/public-key')) return reply({ key: PUB, key_id: '1234' });
    if (init.method === 'PUT') return reply({}, 204);
    return reply({ name: url.split('/').at(-1) });
  } });
  const first = f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP });
  await assert.rejects(f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP }), /CONFIGURATION_ALREADY_RUNNING/);
  assert.equal(f.calls.length, 1);
  release();
  assert.equal((await first).secretsReady, true);
});
test('dispatch only after successful same-session configuration; fixed existing workflow/ref', async () => {
  const f = fixture();
  await assert.rejects(f.client.dispatch(PAT), /SECRETS_NOT_CONFIGURED_THIS_SESSION/);
  await f.client.configure({ pat: PAT, grant: validGrant(), appKey: APP });
  const receipt = await f.client.dispatch(PAT);
  assert.equal(receipt.backupVerified, false);
  assert.equal(receipt.gpuAllowed, false);
  const call = f.calls.at(-1);
  assert.equal(call.url, 'https://api.github.com/repos/' + core.REPOSITORY + '/actions/workflows/studio-dropbox-mobile-v1.yml/dispatches');
  assert.deepEqual(JSON.parse(call.init.body), { ref: core.REF });
});
test('workflow run metadata cannot claim real Dropbox backup success', async () => {
  const f = fixture({ fetch: () => reply({ workflow_runs: [{ id: 123, run_attempt: 2, head_branch: core.REF, event: 'workflow_dispatch', path: '.github/workflows/' + core.WORKFLOW, status: 'completed', conclusion: 'success' }] }) });
  const runs = await f.client.workflowStatus(PAT);
  assert.equal(runs[0].backupVerified, false);
  assert.equal(runs[0].attempt, 2);
  assert.equal(runs[0].url, 'https://github.com/' + core.REPOSITORY + '/actions/runs/123');
  await assert.rejects(f.client.workflowStatus(PAT, '../../secrets'), /WORKFLOW_RUN_ID_INVALID/);
});
const proofDocument = (change = {}) => ({
  schema: 'WORLD_ENGINE_MOBILE_DROPBOX_PROOF_V1', sourceImage: core.SOURCE_IMAGE, runId: 123, attempt: 2,
  status: 'PASS', reasonCode: 'MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED', offlineTokenRefreshVerified: true,
  metadataReadVerified: true, externalStorageRecoveryVerified: true, gpuExecuted: false, productionRenderingStarted: false,
  proofId: 'a'.repeat(64), checkpointId: 'b'.repeat(64), expiresUnix: 1800000000, ...change
});
const proofEnvelope = (proof, change = {}) => {
  const bytes = new TextEncoder().encode(JSON.stringify(proof));
  return { type: 'file', path: 'world-simulation-shorts-engine/recovery/studio-dropbox-mobile-v1/runs/123-2/proof.json',
    encoding: 'base64', content: Buffer.from(bytes).toString('base64'), size: bytes.length,
    download_url: 'https://untrusted.example/never-follow', ...change };
};
test('public workflow proof reads fixed Contents API without PAT or download URL following', async () => {
  const f = fixture({ fetch: () => reply(proofEnvelope(proofDocument())) });
  const proof = await f.client.workflowProof(123, 2);
  assert.equal(proof.status, 'PASS');
  assert.equal(proof.externalStorageRecoveryVerified, true);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].init.headers.Authorization, undefined);
  assert.equal(f.calls[0].url, 'https://api.github.com/repos/' + core.REPOSITORY + '/contents/world-simulation-shorts-engine/recovery/studio-dropbox-mobile-v1/runs/123-2/proof.json?ref=' + encodeURIComponent(core.REF));
  assert.equal(proof.download_url, undefined);
  assert.equal(proof.gpuExecuted, false);
});
test('missing proof remains null despite successful workflow conclusion elsewhere', async () => {
  const f = fixture({ fetch: () => reply({ message: 'Not Found' }, 404) });
  assert.equal(await f.client.workflowProof(123, 2), null);
});
test('blocked public proof remains explicitly unverified', async () => {
  const proof = proofDocument({ status: 'BLOCKED', reasonCode: 'MOBILE_DROPBOX_SECRETS_NOT_BOUND',
    offlineTokenRefreshVerified: false, metadataReadVerified: false, externalStorageRecoveryVerified: false });
  const f = fixture({ fetch: () => reply(proofEnvelope(proof)) });
  const result = await f.client.workflowProof(123, 2);
  assert.equal(result.status, 'BLOCKED');
  assert.equal(result.proofId, undefined);
  assert.equal(result.externalStorageRecoveryVerified, false);
});
test('malicious or incomplete PASS proof cannot authorize recovery or GPU', async () => {
  for (const change of [{ sourceImage: 'other' }, { metadataReadVerified: false }, { gpuExecuted: true }, { productionRenderingStarted: true },
    { schema: 'other' }, { runId: 124 }, { attempt: 1 }, { reasonCode: 'MOBILE_DROPBOX_SECRETS_NOT_BOUND' }, { proofId: '' }, { expiresUnix: 1 },
    { status: 'BLOCKED' }, { reasonCode: 'secret-value\n' }, { externalStorageRecoveryVerified: 'true' }]) {
    const f = fixture({ fetch: () => reply(proofEnvelope(proofDocument(change))) });
    await assert.rejects(f.client.workflowProof(123, 2), /WORKFLOW_PROOF_(INVALID|EXPIRED)/);
  }
});
test('public proof rejects path mismatch, invalid base64 and bad run/attempt before network', async () => {
  for (const change of [{ path: '/other/proof.json' }, { content: 'broken!!' }, { encoding: 'utf-8' }, { size: 999999 }]) {
    const f = fixture({ fetch: () => reply(proofEnvelope(proofDocument(), change)) });
    await assert.rejects(f.client.workflowProof(123, 2), /WORKFLOW_PROOF_CONTENT_INVALID/);
  }
  const f = fixture();
  for (const [runId, attempt] of [['../other', 1], [123, 0], [123, 1.5], [Number.MAX_SAFE_INTEGER + 1, 1]]) await assert.rejects(f.client.workflowProof(runId, attempt), /WORKFLOW_PROOF_ID_INVALID/);
  assert.equal(f.calls.length, 0);
});
test('no localStorage, cookies, dynamic service endpoints or console sinks in core', async () => {
  const fs = await import('node:fs/promises');
  const source = await fs.readFile(new URL('../web/connect-core.js', import.meta.url), 'utf8');
  for (const pattern of [/localStorage/, /document\.cookie/, /console\./, /eval\(/, /new Function/, /window\.location/]) assert.ok(!pattern.test(source));
});
