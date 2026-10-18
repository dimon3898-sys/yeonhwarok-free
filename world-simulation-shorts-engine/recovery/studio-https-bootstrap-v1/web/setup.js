'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const form = byId('setup-login-form');
  const authenticate = byId('setup-authenticate');
  const password = byId('setup-owner-code');
  const originInput = byId('setup-origin');
  const confirmation = byId('setup-confirmation');
  const register = byId('setup-register');
  const consent = byId('setup-origin-confirm');
  let challenge = '';
  let commitNonce = '';
  let approvedOrigin = '';
  let busy = false;

  const messages = {
    LOGIN_FAILED: '관리자 접근 코드가 일치하지 않습니다.',
    LOGIN_RATE_LIMIT: '확인 시도가 많습니다. 잠시 후 다시 시도해 주세요.',
    AUTH_REQUIRED: '관리자 확인이 필요합니다. 다시 로그인해 주세요.',
    CSRF_REQUIRED: '보안 확인이 만료되었습니다. 다시 관리자 확인을 진행해 주세요.',
    INVALID_HOST: '이 접속 주소는 허용되지 않습니다. gCube의 실제 HTTPS 주소로 접속해 주세요.',
    INVALID_ORIGIN: '주소창과 등록하려는 HTTPS 주소가 일치하지 않습니다.',
    INVALID_FORWARDED_HEADERS: 'gCube의 HTTPS 프록시 주소를 확인할 수 없습니다. 실제 서비스 주소로 다시 접속해 주세요.',
    STUDIO_SETUP_BUSY: '설정 요청이 많습니다. 잠시 후 다시 시도해 주세요.',
    STUDIO_SETUP_SAME_ORIGIN_REQUIRED: '같은 Studio 주소에서 설정을 진행해 주세요.',
    STUDIO_SETUP_JSON_REQUIRED: '설정 요청 형식을 확인할 수 없습니다. 페이지를 새로고침해 주세요.',
    STUDIO_SETUP_CHALLENGE_REQUIRED: '보안 확인이 만료되었습니다. 다시 관리자 확인을 진행해 주세요.',
    STUDIO_SETUP_ORIGIN_CHANGED: '등록 주소가 변경되었습니다. 다시 접속하여 관리자 확인을 진행해 주세요.',
    STUDIO_SETUP_EXPLICIT_CONFIRMATION_REQUIRED: '실제 Studio 주소인지 확인한 뒤 동의해 주세요.',
    HTTPS_REQUIRED: 'gCube에서 발급한 HTTPS 주소로 접속해 주세요.',
    HTTPS_ORIGIN_REQUIRED: '경로 없이 실제 HTTPS 주소만 입력해 주세요.',
    ORIGIN_MISMATCH: '주소창과 입력한 HTTPS 주소가 다릅니다. 실제 Studio 주소를 확인해 주세요.',
    STUDIO_HTTPS_ORIGIN_REQUIRED: '실제 HTTPS 주소를 다시 확인해 주세요.',
    STUDIO_SETUP_ORIGIN_REQUIRED: '실제 HTTPS 주소를 다시 확인해 주세요.',
    STUDIO_SETUP_ORIGIN_MISMATCH: '주소창과 입력한 HTTPS 주소가 다릅니다.',
    STUDIO_SETUP_AUTHENTICATION_FAILED: '관리자 접근 코드가 일치하지 않습니다.',
    STUDIO_AUTHENTICATION_FAILED: '관리자 접근 코드가 일치하지 않습니다.',
    STUDIO_OWNER_AUTHENTICATION_FAILED: '관리자 접근 코드가 일치하지 않습니다.',
    STUDIO_LOGIN_FAILED: '관리자 접근 코드를 확인해 주세요.',
    STUDIO_UNAUTHORIZED: '관리자 확인이 필요합니다. 다시 로그인해 주세요.',
    STUDIO_SETUP_CSRF_FAILED: '보안 확인이 만료되었습니다. 다시 관리자 확인을 진행해 주세요.',
    STUDIO_CSRF_REQUIRED: '보안 확인이 만료되었습니다. 다시 관리자 확인을 진행해 주세요.',
    STUDIO_CSRF_INVALID: '보안 확인이 만료되었습니다. 다시 관리자 확인을 진행해 주세요.',
    STUDIO_ORIGIN_REJECTED: '등록하려는 주소와 브라우저의 보안 출처가 일치하지 않습니다.',
    STUDIO_HOST_REJECTED: '이 접속 주소는 허용되지 않습니다. gCube의 실제 HTTPS 주소로 접속해 주세요.',
    STUDIO_SETUP_RATE_LIMITED: '확인 시도가 많습니다. 잠시 후 다시 시도해 주세요.',
    STUDIO_RATE_LIMITED: '확인 시도가 많습니다. 잠시 후 다시 시도해 주세요.',
    STUDIO_SETUP_CONFIRMATION_REQUIRED: '실제 Studio 주소인지 확인한 뒤 동의해 주세요.',
    CONNECTION_FAILED: '보안 연결을 확인할 수 없습니다. 네트워크를 확인하고 다시 시도해 주세요.',
    SETUP_RESPONSE_INVALID: '설정 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  };

  function showError(code) {
    byId('setup-error-message').textContent = messages[code] || '설정을 완료할 수 없습니다. 실제 주소와 관리자 코드를 확인한 뒤 다시 시도해 주세요.';
    byId('setup-error').hidden = false;
  }
  function clearError() {
    byId('setup-error').hidden = true;
    byId('setup-error-message').textContent = '';
    byId('setup-retry').hidden = true;
  }
  function secureBrowser() {
    if (location.protocol !== 'https:' || window.isSecureContext !== true || window.top !== window.self) throw new Error('HTTPS_REQUIRED');
  }
  function typedOrigin() {
    const value = originInput.value.trim();
    let parsed;
    try { parsed = new URL(value); } catch { throw new Error('HTTPS_ORIGIN_REQUIRED'); }
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash || value !== parsed.origin) throw new Error('HTTPS_ORIGIN_REQUIRED');
    // The server pins initial requests to the explicit candidate after owner
    // authentication. Later changes are authenticated against the saved origin.
    // Never infer a trusted server origin from browser/request headers here.
    return parsed.origin;
  }
  async function request(url, options) {
    let response;
    try { response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options}); }
    catch { throw new Error('CONNECTION_FAILED'); }
    let record;
    try { record = await response.json(); } catch { throw new Error('SETUP_RESPONSE_INVALID'); }
    if (!response.ok) throw new Error(typeof record?.error?.code === 'string' ? record.error.code : 'SETUP_RESPONSE_INVALID');
    return record;
  }
  async function loadChallenge() {
    challenge = '';
    authenticate.disabled = true;
    clearError();
    try {
      secureBrowser();
      const record = await request('/setup/challenge', {method: 'GET'});
      if (typeof record.challenge !== 'string' || record.challenge.length < 16 || record.challenge.length > 512) throw new Error('SETUP_RESPONSE_INVALID');
      challenge = record.challenge;
      byId('setup-progress').textContent = '관리자 확인 후 주소를 등록할 수 있습니다.';
      authenticate.disabled = false;
    } catch (reason) {
      byId('setup-progress').textContent = '영상 제작은 잠겨 있습니다.';
      showError(reason.message);
      byId('setup-retry').hidden = false;
    }
  }
  function returnToLogin() {
    commitNonce = '';
    approvedOrigin = '';
    consent.checked = false;
    register.disabled = true;
    confirmation.hidden = true;
    form.hidden = false;
    byId('confirmed-origin').textContent = '';
    password.value = '';
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !challenge) return;
    busy = true;
    authenticate.disabled = true;
    clearError();
    try {
      secureBrowser();
      const origin = typedOrigin();
      byId('setup-progress').textContent = '관리자를 확인하고 있습니다.';
      const record = await request('/api/setup/login', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Studio-Setup-CSRF': challenge}, body: JSON.stringify({password: password.value, origin, challenge})});
      if (record.authenticated !== true || record.origin !== origin || typeof record.csrf !== 'string' || record.csrf.length < 16 || record.csrf.length > 512) throw new Error('SETUP_RESPONSE_INVALID');
      commitNonce = record.csrf;
      approvedOrigin = origin;
      byId('confirmed-origin').textContent = origin;
      consent.checked = false;
      register.disabled = true;
      form.hidden = true;
      confirmation.hidden = false;
      byId('setup-progress').textContent = '주소를 확인한 뒤 등록해 주세요. 아직 제작은 시작되지 않습니다.';
    } catch (reason) {
      byId('setup-progress').textContent = '주소는 등록되지 않았습니다.';
      showError(reason.message);
      challenge = '';
      byId('setup-retry').hidden = false;
    } finally {
      password.value = '';
      busy = false;
      authenticate.disabled = !challenge;
    }
  });
  consent.addEventListener('change', () => { register.disabled = !consent.checked || busy || !commitNonce; });
  byId('setup-back').addEventListener('click', () => { if (!busy) { returnToLogin(); loadChallenge(); } });
  byId('setup-retry').addEventListener('click', () => { if (!busy) { returnToLogin(); loadChallenge(); } });
  register.addEventListener('click', async () => {
    if (busy || !consent.checked || !commitNonce || !approvedOrigin) return;
    busy = true;
    register.disabled = true;
    byId('setup-back').disabled = true;
    clearError();
    try {
      secureBrowser();
      byId('setup-progress').textContent = 'HTTPS 주소를 안전하게 저장하고 있습니다.';
      const record = await request('/api/setup/origin', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Studio-Setup-CSRF': commitNonce}, body: JSON.stringify({origin: approvedOrigin, confirm: true})});
      if (record.registered !== true || record.origin !== approvedOrigin || record.reloginRequired !== true) throw new Error('SETUP_RESPONSE_INVALID');
      commitNonce = '';
      approvedOrigin = '';
      challenge = '';
      confirmation.hidden = true;
      byId('setup-complete').hidden = false;
      byId('setup-progress').textContent = '설정이 저장되었습니다. 제작 권한은 로그인 후 다시 검사합니다.';
    } catch (reason) {
      returnToLogin();
      challenge = '';
      showError(reason.message);
      byId('setup-retry').hidden = false;
      byId('setup-progress').textContent = '저장 결과를 확인할 수 없습니다. 다시 접속하여 상태를 확인해 주세요.';
    } finally {
      busy = false;
      byId('setup-back').disabled = false;
    }
  });
  window.addEventListener('pagehide', () => { password.value = ''; challenge = ''; commitNonce = ''; approvedOrigin = ''; });
  loadChallenge();
})();
