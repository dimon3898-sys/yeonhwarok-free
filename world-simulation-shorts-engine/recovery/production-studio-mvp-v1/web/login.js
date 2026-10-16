'use strict';
document.getElementById('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('login');
  if (button.disabled) return;
  button.disabled = true;
  const error = document.getElementById('login-error');
  error.textContent = '';
  try {
    const local = ['127.0.0.1', 'localhost'].includes(location.hostname);
    if ((location.protocol !== 'https:' && !(local && location.protocol === 'http:')) || window.isSecureContext !== true) throw new Error('HTTPS_REQUIRED');
    const response = await fetch('/api/login', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password: document.getElementById('owner-code').value})});
    const record = await response.json();
    if (!response.ok) throw new Error(record.error?.code || 'LOGIN_FAILED');
    document.getElementById('owner-code').value = '';
    location.assign('/');
  } catch (reason) { error.textContent = `로그인을 확인해 주세요. ${reason.message}`; }
  finally { button.disabled = false; }
});
