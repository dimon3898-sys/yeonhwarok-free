/* WORLD ENGINE mobile enrollment. No DOM, analytics, token logging, or token persistence. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.WorldDropboxConnect = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const REPOSITORY = "dimon3898-sys/yeonhwarok-free";
  const GITHUB = "https://api.github.com";
  const AUTHORIZE = "https://www.dropbox.com/oauth2/authorize";
  const TOKEN = "https://api.dropboxapi.com/oauth2/token";
  const LIST = "https://api.dropboxapi.com/2/files/list_folder";
  const PREFIX = "/WORLD_ENGINE_STUDIO_BACKUPS_V1";
  const SCOPES = Object.freeze(["files.content.read", "files.content.write", "files.metadata.read"]);
  const NAMES = Object.freeze({
    key: "WORLD_ENGINE_STUDIO_BACKUP_KEY",
    appKey: "WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY",
    appSecret: "WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET",
    refresh: "WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN"
  });
  const WORKFLOW = "studio-dropbox-mobile-v1.yml";
  const REF = "development/dropbox-mobile-connect-v1-20261018";
  const SOURCE_IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0";
  const STATE_KEY = "world-engine.dropbox.pkce.v1";
  const BINDING_PREFIX = "WORLD_ENGINE_STUDIO_DROPBOX_BINDING_";
  const TTL = 10 * 60 * 1000;
  const TIMEOUT = 30000;
  const object = value => !!value && typeof value === "object" && !Array.isArray(value);
  function fail(code) { throw new Error(code); }
  function validString(value, min, max) {
    return typeof value === "string" && value.length >= min && value.length <= max && !/[\u0000-\u0020\u007f]/.test(value);
  }
  function validateAppKey(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9_-]{8,128}$/.test(value)) fail("APP_KEY_INVALID");
    return value;
  }
  function callbackURL(value, allowedRedirectUris) {
    if (!Array.isArray(allowedRedirectUris) || allowedRedirectUris.length < 1 || allowedRedirectUris.length > 8) fail("REDIRECT_ALLOWLIST_REQUIRED");
    let url;
    try { url = new URL(value); } catch (_) { fail("REDIRECT_INVALID"); }
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || /^(localhost|127\.|\[?::1)/i.test(url.hostname)) fail("REDIRECT_INVALID");
    if (value !== url.href || !allowedRedirectUris.includes(url.href)) fail("REDIRECT_NOT_REGISTERED");
    return url.href;
  }
  function base64(bytes) {
    let binary = "";
    for (const value of bytes) binary += String.fromCharCode(value);
    return btoa(binary);
  }
  function unbase64(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) fail("GITHUB_PUBLIC_KEY_INVALID");
    let binary;
    try { binary = atob(value); } catch (_) { fail("GITHUB_PUBLIC_KEY_INVALID"); }
    return Uint8Array.from(binary, ch => ch.charCodeAt(0));
  }
  function url64(bytes) { return base64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, ""); }
  async function makePkce(cryptoProvider) {
    if (!cryptoProvider || !cryptoProvider.subtle || typeof cryptoProvider.getRandomValues !== "function") fail("SECURE_BROWSER_REQUIRED");
    const verifier = url64(cryptoProvider.getRandomValues(new Uint8Array(48)));
    const digest = await cryptoProvider.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
    return { verifier, challenge: url64(new Uint8Array(digest)), state: url64(cryptoProvider.getRandomValues(new Uint8Array(32))) };
  }
  function createClient(options) {
    const opts = options || {};
    const redirectUri = callbackURL(opts.redirectUri, opts.allowedRedirectUris);
    const fetcher = opts.fetch || globalThis.fetch;
    const cryptoProvider = opts.crypto || globalThis.crypto;
    const storage = opts.storage;
    const now = opts.now || Date.now;
    const sodium = opts.sodium;
    if (!storage || typeof storage.setItem !== "function" || typeof storage.getItem !== "function" || typeof storage.removeItem !== "function") fail("PRIVATE_SESSION_REQUIRED");
    if (typeof fetcher !== "function") fail("FETCH_REQUIRED");
    let lastConfigured = false;
    let configuring = false;

    async function request(url, init, expected, code, limit) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT);
      try {
        const response = await fetcher(url, {
          ...init, credentials: "omit", redirect: "error", cache: "no-store",
          referrerPolicy: "no-referrer", signal: controller.signal
        });
        if (!response || !expected.includes(response.status) || response.redirected) fail(code + "_HTTP_" + (response && Number.isInteger(response.status) ? response.status : "INVALID"));
        if (response.status === 204) return { status: 204, data: null };
        const headerLength = response.headers && response.headers.get("content-length");
        if (headerLength && (!/^\d+$/.test(headerLength) || Number(headerLength) > limit)) fail(code + "_RESPONSE_TOO_LARGE");
        if (!response.body || typeof response.body.getReader !== "function") fail(code + "_RESPONSE_INVALID");
        const reader = response.body.getReader();
        const chunks = [];
        let length = 0;
        while (true) {
          const part = await reader.read();
          if (part.done) break;
          length += part.value.byteLength;
          if (length > limit) { await reader.cancel(); fail(code + "_RESPONSE_TOO_LARGE"); }
          chunks.push(part.value);
        }
        const buffer = new Uint8Array(length);
        let offset = 0;
        for (const part of chunks) { buffer.set(part, offset); offset += part.byteLength; }
        let data;
        try { data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buffer)); } catch (_) { fail(code + "_RESPONSE_INVALID"); }
        if (!object(data)) fail(code + "_RESPONSE_INVALID");
        return { status: response.status, data };
      } catch (error) {
        // Only our enumerated diagnostics leave this boundary. Provider bodies and URLs never do.
        if (error && typeof error.message === "string" && new RegExp("^" + code + "_(HTTP_[0-9A-Z]+|RESPONSE_(TOO_LARGE|INVALID))$").test(error.message)) throw error;
        fail(code + "_NETWORK_OR_CORS_FAILED");
      } finally { clearTimeout(timer); }
    }
    function githubHeaders(pat) {
      if (!validString(pat, 20, 256) || !/^[A-Za-z0-9_]+$/.test(pat)) fail("GITHUB_CREDENTIAL_INVALID");
      return { "Accept": "application/vnd.github+json", "Authorization": "Bearer " + pat, "X-GitHub-Api-Version": "2022-11-28" };
    }
    async function github(pat, suffix, method = "GET", body, expected = [200]) {
      const headers = githubHeaders(pat);
      if (body !== undefined) headers["Content-Type"] = "application/json";
      return request(GITHUB + "/repos/" + REPOSITORY + suffix, {
        method, headers, ...(body === undefined ? {} : { body: JSON.stringify(body) })
      }, expected, "GITHUB", 262144);
    }
    async function begin(appKey) {
      validateAppKey(appKey);
      const pkce = await makePkce(cryptoProvider);
      const createdAt = now();
      const session = { version: 1, state: pkce.state, verifier: pkce.verifier, expiresAt: createdAt + TTL, createdAt, appKey, redirectUri };
      try { storage.setItem(STATE_KEY, JSON.stringify(session)); } catch (_) { fail("PRIVATE_SESSION_UNAVAILABLE"); }
      const url = new URL(AUTHORIZE);
      url.search = new URLSearchParams({ client_id: appKey, response_type: "code", redirect_uri: redirectUri,
        token_access_type: "offline", scope: SCOPES.join(" "), state: pkce.state,
        code_challenge: pkce.challenge, code_challenge_method: "S256" }).toString();
      return { authorizationURL: url.href, expiresAt: session.expiresAt };
    }
    function pending() {
      // Public app identifier only; the verifier/state stay encapsulated in session storage.
      try {
        const raw = storage.getItem(STATE_KEY);
        if (!raw || raw.length > 4096) return null;
        const session = JSON.parse(raw);
        if (!object(session) || session.redirectUri !== redirectUri || !Number.isFinite(session.expiresAt) || session.expiresAt <= now()) return null;
        return { appKey: validateAppKey(session.appKey), expiresAt: session.expiresAt };
      } catch (_) { return null; }
    }
    async function finish(value, appKey) {
      let session;
      try {
        const raw = storage.getItem(STATE_KEY);
        storage.removeItem(STATE_KEY); // Consumed before validation or exchange; retries require a fresh authorization.
        if (!raw || raw.length > 4096) fail("OAUTH_STATE_MISSING");
        session = JSON.parse(raw);
      } catch (error) {
        if (error && error.message === "OAUTH_STATE_MISSING") throw error;
        fail("OAUTH_STATE_INVALID");
      }
      let callback;
      try { callback = new URL(value); } catch (_) { fail("OAUTH_CALLBACK_INVALID"); }
      if (callback.origin + callback.pathname !== redirectUri || callback.hash || callback.username || callback.password) fail("OAUTH_CALLBACK_INVALID");
      if (!object(session) || session.version !== 1 || session.appKey !== appKey || session.redirectUri !== redirectUri ||
          !Number.isFinite(session.expiresAt) || !Number.isFinite(session.createdAt) || session.createdAt > now() || session.expiresAt <= now() ||
          session.expiresAt - session.createdAt !== TTL || !/^[A-Za-z0-9_-]{43}$/.test(session.state) || !/^[A-Za-z0-9_-]{64}$/.test(session.verifier)) fail("OAUTH_STATE_INVALID_OR_EXPIRED");
      validateAppKey(appKey);
      if (callback.searchParams.getAll("state").length !== 1 || callback.searchParams.get("state") !== session.state) fail("OAUTH_STATE_MISMATCH");
      if (callback.searchParams.has("error")) fail("DROPBOX_AUTHORIZATION_DENIED");
      if (callback.searchParams.getAll("code").length !== 1 || !validString(callback.searchParams.get("code"), 8, 4096)) fail("OAUTH_CODE_INVALID");
      for (const key of callback.searchParams.keys()) if (!["code", "state"].includes(key)) fail("OAUTH_CALLBACK_INVALID");
      const { data } = await request(TOKEN, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ grant_type: "authorization_code", code: callback.searchParams.get("code"), client_id: appKey,
          redirect_uri: redirectUri, code_verifier: session.verifier }).toString()
      }, [200], "DROPBOX_TOKEN", 65536);
      const scopes = typeof data.scope === "string" ? data.scope.split(/\s+/).filter(Boolean) : [];
      if (data.token_type !== "bearer" || !validString(data.access_token, 16, 16384) || !validString(data.refresh_token, 16, 16384) ||
          !validString(data.account_id, 8, 256) || !/^[A-Za-z0-9:_-]+$/.test(data.account_id) ||
          !Number.isInteger(data.expires_in) || data.expires_in <= 0 || data.expires_in > 604800 || !SCOPES.every(scope => scopes.includes(scope))) fail("DROPBOX_TOKEN_INVALID_OR_SCOPE_MISSING");
      return { appKey, accountId: data.account_id, accessToken: data.access_token, refreshToken: data.refresh_token, expiresAt: now() + data.expires_in * 1000, scope: SCOPES.slice() };
    }
    async function githubPreflight(pat) {
      // Metadata-only GET; GitHub never returns existing Secret values.
      const result = {};
      for (const [key, name] of Object.entries(NAMES)) {
        const response = await github(pat, "/actions/secrets/" + name, "GET", undefined, [200, 404]);
        if (response.status === 200 && response.data.name !== name) fail("GITHUB_SECRET_METADATA_INVALID");
        result[key] = response.status === 200;
      }
      const { data: key } = await github(pat, "/actions/secrets/public-key");
      if (!validString(key.key_id, 1, 128) || !/^[A-Za-z0-9_-]+$/.test(key.key_id) || unbase64(key.key).length !== 32) fail("GITHUB_PUBLIC_KEY_INVALID");
      return { existing: result, publicKey: { key: key.key, keyId: key.key_id } };
    }
    async function bindingName(appKey, accountId) {
      if (!validString(accountId, 8, 256) || !/^[A-Za-z0-9:_-]+$/.test(accountId)) fail("DROPBOX_ACCOUNT_ID_REQUIRED");
      if (!cryptoProvider || !cryptoProvider.subtle) fail("SECURE_BROWSER_REQUIRED");
      const bytes = new TextEncoder().encode(appKey + "\u0000" + accountId);
      let digest;
      try { digest = new Uint8Array(await cryptoProvider.subtle.digest("SHA-256", bytes)); }
      catch (_) { fail("IDENTITY_BINDING_UNAVAILABLE"); }
      finally { bytes.fill(0); }
      return BINDING_PREFIX + Array.from(digest, value => value.toString(16).padStart(2, "0")).join("").toUpperCase();
    }
    async function secretExists(pat, name) {
      const response = await github(pat, "/actions/secrets/" + name, "GET", undefined, [200, 404]);
      if (response.status === 200 && response.data.name !== name) fail("GITHUB_SECRET_METADATA_INVALID");
      return response.status === 200;
    }
    async function backupPrefixEmpty(grant) {
      if (!grant || !validString(grant.accessToken, 16, 16384) || !Number.isFinite(grant.expiresAt) || grant.expiresAt <= now()) fail("DROPBOX_GRANT_EXPIRED");
      const response = await request(LIST, { method: "POST", headers: { "Authorization": "Bearer " + grant.accessToken, "Content-Type": "application/json" },
        body: JSON.stringify({ path: PREFIX, recursive: false, include_deleted: false, limit: 1 })
      }, [200, 409], "DROPBOX_METADATA", 262144);
      if (response.status === 409) {
        const error = response.data.error;
        if (object(error) && error[".tag"] === "path" && object(error.path) && error.path[".tag"] === "not_found") return true;
        fail("DROPBOX_BACKUP_PREFIX_UNVERIFIED");
      }
      if (!Array.isArray(response.data.entries) || response.data.entries.length > 2000 || typeof response.data.has_more !== "boolean") fail("DROPBOX_METADATA_INVALID");
      return response.data.entries.length === 0 && response.data.has_more === false;
    }
    async function configure(input) {
      if (configuring) fail("CONFIGURATION_ALREADY_RUNNING");
      configuring = true;
      try {
      lastConfigured = false;
      const { pat, grant, appSecret } = input || {};
      const appKey = validateAppKey(input && input.appKey);
      if (!grant || grant.appKey !== appKey || !validString(grant.accountId, 8, 256) || !validString(grant.refreshToken, 16, 16384) || !Array.isArray(grant.scope) || !SCOPES.every(scope => grant.scope.includes(scope))) fail("DROPBOX_OFFLINE_GRANT_REQUIRED");
      const preflight = await githubPreflight(pat);
      const binding = await bindingName(appKey, grant.accountId);
      const bound = await secretExists(pat, binding);
      if ((preflight.existing.appKey || preflight.existing.refresh) && !bound) fail("EXISTING_DROPBOX_CONNECTION_UNVERIFIED");
      if (!preflight.existing.appSecret && (!validString(appSecret, 8, 256) || !/^[A-Za-z0-9_-]+$/.test(appSecret))) fail("APP_SECRET_REQUIRED");
      if (!sodium || !sodium.ready) fail("SEALED_BOX_UNAVAILABLE");
      try { await sodium.ready; } catch (_) { fail("SEALED_BOX_UNAVAILABLE"); }
      if (typeof sodium.crypto_box_seal !== "function") fail("SEALED_BOX_UNAVAILABLE");
      const publicKey = unbase64(preflight.publicKey.key);
      const values = [[NAMES.appKey, appKey], [NAMES.refresh, grant.refreshToken]];
      if (!preflight.existing.appSecret) values.push([NAMES.appSecret, appSecret]);
      if (!preflight.existing.key) {
        if (!(await backupPrefixEmpty(grant))) fail("EXISTING_BACKUP_KEY_REQUIRED");
        const bytes = cryptoProvider.getRandomValues(new Uint8Array(32));
        values.unshift([NAMES.key, base64(bytes)]);
        bytes.fill(0);
      }
      // Enrollment identity is committed first, allowing a same-account retry after
      // a partial Secret write. Existing unbound credentials cannot be migrated blindly.
      if (!bound) values.unshift([binding, "WORLD_ENGINE_DROPBOX_BINDING_V1"]);
      const saved = [];
      for (const [name, value] of values) {
        // GitHub has no conditional-create API. Recheck the two preserve-only Secrets
        // immediately before writing; another operator must not enroll concurrently.
        if ((name === NAMES.key || name === NAMES.appSecret || name === binding) && await secretExists(pat, name)) continue;
        let sealed;
        const plaintext = new TextEncoder().encode(value);
        const plaintextLength = plaintext.length;
        try { sealed = sodium.crypto_box_seal(plaintext, publicKey); } catch (_) { fail("SEALED_BOX_FAILED"); }
        finally { plaintext.fill(0); }
        if (!(sealed instanceof Uint8Array) || sealed.length !== plaintextLength + 48) fail("SEALED_BOX_INVALID");
        await github(pat, "/actions/secrets/" + name, "PUT", { encrypted_value: base64(sealed), key_id: preflight.publicKey.keyId }, [201, 204]);
        if (name === binding && !(await secretExists(pat, binding))) fail("GITHUB_BINDING_METADATA_INCOMPLETE");
        saved.push(name);
      }
      const verified = await githubPreflight(pat);
      if (!Object.values(verified.existing).every(Boolean)) fail("GITHUB_SECRET_METADATA_INCOMPLETE");
      lastConfigured = true;
      return { repository: REPOSITORY, saved, preserved: [NAMES.key, NAMES.appSecret].filter(name => !saved.includes(name)), secretsReady: true,
        dropboxBackupVerified: false, gpuAllowed: false };
      } finally { configuring = false; }
    }
    async function dispatch(pat) {
      if (!lastConfigured) fail("SECRETS_NOT_CONFIGURED_THIS_SESSION");
      const { existing } = await githubPreflight(pat);
      if (!Object.values(existing).every(Boolean)) fail("GITHUB_SECRET_METADATA_INCOMPLETE");
      await github(pat, "/actions/workflows/" + WORKFLOW + "/dispatches", "POST", { ref: REF }, [204]);
      return { dispatched: true, workflow: WORKFLOW, ref: REF, backupVerified: false, gpuAllowed: false };
    }
    async function workflowStatus(pat, runId) {
      if (runId !== undefined && !/^[1-9][0-9]{0,19}$/.test(String(runId))) fail("WORKFLOW_RUN_ID_INVALID");
      const suffix = runId === undefined ? "/actions/workflows/" + WORKFLOW + "/runs?branch=" + encodeURIComponent(REF) + "&event=workflow_dispatch&per_page=5" : "/actions/runs/" + String(runId);
      const { data } = await github(pat, suffix);
      const runs = runId === undefined ? data.workflow_runs : [data];
      if (!Array.isArray(runs) || runs.length > 5) fail("WORKFLOW_METADATA_INVALID");
      return runs.map(run => {
        if (!Number.isSafeInteger(run.id) || run.id < 1 || !["completed", "queued", "in_progress", "waiting", "pending", "requested"].includes(run.status) ||
            !Number.isSafeInteger(run.run_attempt) || run.run_attempt < 1 || run.run_attempt > 1000 ||
            run.head_branch !== REF || run.event !== "workflow_dispatch" || typeof run.path !== "string" || run.path.split("@")[0] !== ".github/workflows/" + WORKFLOW) fail("WORKFLOW_METADATA_INVALID");
        return { id: run.id, attempt: run.run_attempt, status: run.status, conclusion: typeof run.conclusion === "string" ? run.conclusion : null,
          url: "https://github.com/" + REPOSITORY + "/actions/runs/" + run.id, backupVerified: false };
      });
    }
    async function workflowProof(runId, attempt = 1) {
      if (!/^[1-9][0-9]{0,15}$/.test(String(runId)) || !Number.isSafeInteger(Number(runId)) ||
          !Number.isSafeInteger(attempt) || attempt < 1 || attempt > 1000) fail("WORKFLOW_PROOF_ID_INVALID");
      const path = "world-simulation-shorts-engine/recovery/studio-dropbox-mobile-v1/runs/" + String(runId) + "-" + attempt + "/proof.json";
      // Public repository proof only: no PAT, arbitrary URL, raw download URL, or provider redirect.
      const { status, data } = await request(GITHUB + "/repos/" + REPOSITORY + "/contents/" + path + "?ref=" + encodeURIComponent(REF),
        { method: "GET", headers: { "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" } },
        [200, 404], "WORKFLOW_PROOF", 262144);
      if (status === 404) return null;
      if (data.type !== "file" || data.path !== path || data.encoding !== "base64" || typeof data.content !== "string" ||
          !Number.isSafeInteger(data.size) || data.size < 2 || data.size > 196608) fail("WORKFLOW_PROOF_CONTENT_INVALID");
      let proof;
      try {
        const compact = data.content.replace(/[\r\n]/g, "");
        const bytes = unbase64(compact);
        if (bytes.length !== data.size || base64(bytes) !== compact) fail("WORKFLOW_PROOF_CONTENT_INVALID");
        proof = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
      } catch (_) { fail("WORKFLOW_PROOF_CONTENT_INVALID"); }
      if (!object(proof) || proof.schema !== "WORLD_ENGINE_MOBILE_DROPBOX_PROOF_V1" || proof.sourceImage !== SOURCE_IMAGE ||
          proof.runId !== Number(runId) || proof.attempt !== attempt || !["PASS", "BLOCKED", "FAIL"].includes(proof.status) ||
          typeof proof.reasonCode !== "string" || !/^[A-Z][A-Z0-9_]{2,95}$/.test(proof.reasonCode) ||
          proof.gpuExecuted !== false || proof.productionRenderingStarted !== false ||
          typeof proof.offlineTokenRefreshVerified !== "boolean" || typeof proof.metadataReadVerified !== "boolean" ||
          typeof proof.externalStorageRecoveryVerified !== "boolean") fail("WORKFLOW_PROOF_INVALID");
      const verified = [proof.offlineTokenRefreshVerified, proof.metadataReadVerified, proof.externalStorageRecoveryVerified];
      if (proof.status === "PASS") {
        if (!verified.every(value => value === true) || proof.reasonCode !== "MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED" ||
            !/^[a-f0-9]{64}$/.test(proof.proofId) || !/^[a-f0-9]{64}$/.test(proof.checkpointId) ||
            !Number.isSafeInteger(proof.expiresUnix) || proof.expiresUnix <= 0) fail("WORKFLOW_PROOF_INVALID");
        if (proof.expiresUnix * 1000 <= now()) fail("WORKFLOW_PROOF_EXPIRED");
      } else if (!verified.every(value => value === false) || proof.reasonCode === "MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED") fail("WORKFLOW_PROOF_INVALID");
      return { schema: proof.schema, sourceImage: proof.sourceImage, runId: proof.runId, attempt: proof.attempt,
        status: proof.status, reasonCode: proof.reasonCode, offlineTokenRefreshVerified: proof.offlineTokenRefreshVerified,
        metadataReadVerified: proof.metadataReadVerified, externalStorageRecoveryVerified: proof.externalStorageRecoveryVerified,
        gpuExecuted: false, productionRenderingStarted: false, ...(proof.status === "PASS" ? { proofId: proof.proofId, checkpointId: proof.checkpointId, expiresUnix: proof.expiresUnix } : {}) };
    }
    return Object.freeze({ begin, pending, finish, githubPreflight, configure, dispatch, workflowStatus, workflowProof });
  }
  return Object.freeze({ createClient, validateAppKey, callbackURL, makePkce, REPOSITORY, SCOPES, NAMES, WORKFLOW, REF, SOURCE_IMAGE });
});
