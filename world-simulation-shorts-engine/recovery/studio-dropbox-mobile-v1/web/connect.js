/* Android-first UI. Credentials stay in this tab's memory, never in telemetry. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const config = window.WORLD_CONNECT_CONFIG;
  const api = window.WorldDropboxConnect;
  let client = null, grant = null, pat = "", appKey = "", busy = false;
  let checked = false, savingDone = false, currentRun = null, timer = null;
  let previousRuns = new Set(), pollCount = 0;
  const errors = {
    APP_KEY_INVALID: "App key를 확인해 주세요. 기존 App Folder 앱의 Settings에 있습니다.",
    GITHUB_CREDENTIAL_INVALID: "GitHub의 일회 연결 권한을 비공개 입력칸에 넣어 주세요.",
    GITHUB_HTTP_401: "GitHub 인증이 만료됐거나 유효하지 않습니다. 새 권한을 발급해 주세요.",
    GITHUB_HTTP_403: "이 저장소의 Secrets·Actions 쓰기 권한이 필요합니다. 권한 설정을 확인해 주세요.",
    GITHUB_HTTP_404: "이 저장소 또는 검증 작업에 접근할 수 없습니다. 저장소 선택과 권한을 확인해 주세요.",
    APP_SECRET_REQUIRED: "기존 실행에 필요한 App secret이 아직 없습니다. 아래 비공개 입력칸에 넣어 주세요.",
    EXISTING_BACKUP_KEY_REQUIRED: "기존 백업은 있지만 암호화 키가 연결되지 않았습니다. 기존 키를 GitHub Secret에 복원해야 합니다. 새 키로 바꾸지 않습니다.",
    DROPBOX_AUTHORIZATION_DENIED: "Dropbox 접근 승인이 취소됐습니다. 연결 버튼으로 다시 시작할 수 있습니다.",
    OAUTH_STATE_INVALID_OR_EXPIRED: "연결 승인의 유효 시간이 지났습니다. Dropbox 연결부터 다시 시작해 주세요.",
    OAUTH_STATE_MISSING: "이 탭의 연결 정보가 없습니다. Dropbox 연결부터 다시 시작해 주세요.",
    OAUTH_STATE_MISMATCH: "승인 정보가 일치하지 않아 연결을 차단했습니다. Dropbox 연결부터 다시 시작해 주세요.",
    DROPBOX_TOKEN_NETWORK_OR_CORS_FAILED: "Dropbox 인증 응답을 받지 못했습니다. 인터넷 연결과 앱의 Redirect URI를 확인한 뒤 다시 연결해 주세요.",
    DROPBOX_TOKEN_INVALID_OR_SCOPE_MISSING: "Dropbox가 필수 권한이나 offline 토큰을 발급하지 않았습니다. 앱 Permissions의 세 권한을 확인해 주세요.",
    DROPBOX_GRANT_EXPIRED: "Dropbox 승인의 유효 시간이 지났습니다. 다시 연결해 주세요.",
    DROPBOX_BACKUP_PREFIX_UNVERIFIED: "기존 백업 경로를 확인하지 못해 키 생성을 중단했습니다. 기존 데이터는 변경하지 않았습니다.",
    CONFIGURE_ALREADY_RUNNING: "이미 저장 중입니다. 잠시 기다려 주세요.",
    EXISTING_DROPBOX_CONNECTION_UNVERIFIED: "기존 Dropbox 연결과 같은 앱·계정인지 확인할 수 없어 교체를 차단했습니다. 기존 인증은 그대로 유지됩니다. 무료 검증 기록으로 먼저 기존 연결을 확인해야 합니다."
  };
  function state(text) { $("status").textContent = text; }
  function showError(error) {
    const code = error && typeof error.message === "string" && /^[A-Z][A-Z0-9_]{2,95}$/.test(error.message) ? error.message : "CONNECTION_BLOCKED";
    $("error").textContent = errors[code] || "연결을 완료하지 못했습니다. 오류 코드: " + code + ". 저장된 기존 백업은 유지됩니다.";
    $("error").hidden = false;
    $("restart").hidden = false;
  }
  function screen(id) {
    for (const name of ["consent", "saving", "verification"]) $(name).hidden = name !== id;
    const index = { consent: 1, saving: 2, verification: 3 }[id];
    for (let n = 1; n <= 3; n++) {
      if (n === index) $("step" + n).setAttribute("aria-current", "step");
      else $("step" + n).removeAttribute("aria-current");
    }
  }
  function buttons() {
    $("connectDropbox").disabled = busy;
    $("checkGithub").disabled = busy;
    $("saveConnection").disabled = busy || !checked || savingDone;
    $("refreshStatus").disabled = busy;
  }
  async function task(action) {
    if (busy) return;
    busy = true; buttons(); $("error").hidden = true;
    try { await action(); } catch (error) { state(""); showError(error); }
    finally { busy = false; buttons(); }
  }
  function forget() {
    if (grant) { grant.accessToken = ""; grant.refreshToken = ""; }
    grant = null; pat = "";
    $("githubCredential").value = ""; $("appSecret").value = "";
    if (timer !== null) clearTimeout(timer);
    timer = null;
  }
  window.addEventListener("pagehide", forget);
  $("restart").addEventListener("click", () => { forget(); location.replace(location.pathname); });

  async function checkRun() {
    if (!pat || !savingDone) return;
    const runs = await client.workflowStatus(pat, currentRun ? currentRun.id : undefined);
    const candidate = currentRun ? runs[0] : runs.find(run => !previousRuns.has(run.id));
    if (!candidate) {
      $("verificationState").textContent = "검증 실행을 기다리고 있습니다. 브라우저를 닫아도 이미 시작된 검사는 계속됩니다.";
    } else {
      currentRun = candidate;
      $("runLink").href = candidate.url; $("runLink").hidden = false;
      const proof = await client.workflowProof(candidate.id, candidate.attempt);
      if (proof) {
        if (proof.status === "PASS") {
          $("verificationState").textContent = "실제 Dropbox 토큰 갱신·백업·다운로드·복구 검증을 통과했습니다.";
          state("Dropbox 연결 완료 · GPU는 시작하지 않았습니다.");
          $("refreshStatus").hidden = true; forget();
        } else {
          $("verificationState").textContent = "실제 Dropbox 검증은 완료되지 않았습니다. 오류 코드: " + proof.reasonCode;
          state("연결 설정은 저장됐습니다. 검증 기록을 확인해 주세요.");
          $("refreshStatus").hidden = true;
          $("restart").hidden = false;
          forget();
        }
        return;
      }
      $("verificationState").textContent = candidate.status === "completed"
        ? "검증 작업이 종료됐습니다. 실제 백업·복구 판정 기록을 기다리고 있습니다. 작업 완료만으로 성공 처리하지 않습니다."
        : "무료 CPU 검증이 진행 중입니다. 실제 백업·복구 결과가 기록되면 여기에 표시합니다.";
    }
    if (++pollCount < 24) timer = setTimeout(() => task(checkRun), 15000);
    else state("자동 상태 확인을 마쳤습니다. 검증 기록 보기에서 결과를 확인할 수 있습니다.");
  }

  if (window.__worldConnectBlocked || !window.isSecureContext || !config || config.enabled !== true || !config.redirectUri) {
    $("blocked").hidden = false;
    $("blockedReason").textContent = window.__worldConnectBlocked
      ? "다른 페이지 안에 삽입된 연결 화면에서는 인증을 시작하지 않습니다."
      : "호스팅 계정 권한 확인 전에는 인증 요청을 보내지 않습니다.";
    return;
  }
  try {
    if (location.origin + location.pathname !== config.redirectUri) throw new Error("REDIRECT_NOT_REGISTERED");
    client = api.createClient({ redirectUri: config.redirectUri, allowedRedirectUris: config.allowedRedirectUris,
      storage: sessionStorage, sodium: window.sodium });
    $("redirectUri").textContent = config.redirectUri;
    $("copyRedirect").addEventListener("click", () => task(async () => {
      await navigator.clipboard.writeText(config.redirectUri); state("Redirect URI를 복사했습니다.");
    }));
    $("connectDropbox").addEventListener("click", () => task(async () => {
      const key = $("appKey").value.trim();
      const flow = await client.begin(key);
      state("Dropbox 승인 화면으로 이동합니다.");
      location.assign(flow.authorizationURL);
    }));
    $("githubCredential").addEventListener("input", () => { pat = ""; checked = false; buttons(); });
    $("checkGithub").addEventListener("click", () => task(async () => {
      pat = $("githubCredential").value.trim();
      $("githubCredential").value = "";
      const result = await client.githubPreflight(pat);
      $("appSecretArea").hidden = result.existing.appSecret;
      checked = true;
      state(result.existing.appSecret ? "GitHub 권한을 확인했습니다. 기존 키와 앱 설정을 유지합니다." : "GitHub 권한을 확인했습니다. 최초 App secret 설정만 추가해 주세요.");
    }));
    $("saveConnection").addEventListener("click", () => task(async () => {
      state("Secret을 암호화해 저장하고 있습니다.");
      await client.configure({ pat, grant, appKey, appSecret: $("appSecret").value.trim() });
      $("appSecret").value = "";
      // Record existing run IDs first so a previous successful run cannot be
      // mistaken for this new connection's proof.
      previousRuns = new Set((await client.workflowStatus(pat)).map(run => run.id));
      await client.dispatch(pat);
      savingDone = true;
      if (grant) { grant.accessToken = ""; grant.refreshToken = ""; }
      grant = null;
      screen("verification"); state("연결 설정 저장 완료 · 무료 실제 백업 검증을 시작했습니다.");
      await checkRun();
    }));
    $("refreshStatus").addEventListener("click", () => task(checkRun));
    const callback = window.__worldConnectCallback;
    delete window.__worldConnectCallback;
    if (callback) {
      screen("saving"); state("Dropbox 승인 결과를 확인하고 있습니다.");
      task(async () => {
        const pending = client.pending();
        if (!pending) throw new Error("OAUTH_STATE_MISSING");
        appKey = pending.appKey;
        grant = await client.finish(callback, appKey);
        state("Dropbox 승인을 확인했습니다. 최초 GitHub 권한 연결만 남았습니다.");
      });
    } else screen("consent");
  } catch (error) {
    $("blocked").hidden = false;
    $("blockedReason").textContent = "등록된 HTTPS 주소와 현재 주소가 일치하지 않아 인증을 차단했습니다.";
    showError(error);
  }
})();
