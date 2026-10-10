const $ = id => document.getElementById(id);
let csrf = '', busy = false;
async function api(url, body) {
  const response = await fetch(url, {credentials: 'same-origin', ...(body !== undefined ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Proof-CSRF': csrf}, body: JSON.stringify(body)} : {})});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'REQUEST_FAILED');
  return result;
}
function loggedIn(token) { csrf = token; $('login').hidden = true; $('controls').hidden = false; $('status').textContent = 'Ready. Check GPU / WebGL2, then generate a static proof.'; }
$('login').addEventListener('submit', async event => {
  event.preventDefault();
  try { const value = await api('/auth/login', {password: $('password').value}); $('password').value = ''; loggedIn(value.csrf); }
  catch (error) { $('status').textContent = error.message; }
});
async function start(proof) {
  if (busy) return;
  busy = true; $('check').disabled = $('generate').disabled = true; $('result').hidden = true; $('progress').textContent = '';
  try {
    const {job} = await api(proof ? '/api/generate' : '/api/check-gpu', {});
    const deadline = Date.now() + 570000;
    while (true) {
      if (Date.now() > deadline) throw Error('STATUS_POLL_TIMEOUT');
      const value = await api('/api/jobs/' + job);
      $('status').textContent = value.status + ' · ' + Math.round(Date.now() / 1000 - value.started) + ' seconds';
      $('progress').textContent = value.events.map(x => `${x.elapsed_seconds}s  ${x.stage}  ${x.result}`).join('\n');
      if (value.status !== 'RUNNING') {
        $('gpu').textContent = value.diagnostic?.gpu_renderer || 'UNKNOWN / FAIL';
        $('diagnostic').href = '/download/' + job + '/diagnostic';
        $('result').hidden = false; $('png').hidden = !(proof && value.status === 'PASS');
        if (!$('png').hidden) $('png').href = '/download/' + job + '/png';
        $('status').textContent = value.status === 'PASS' ? (proof ? 'PNG ready. GPU visual approval: USER PENDING.' : 'GPU / WebGL2 capability PASS.') : 'FAIL: ' + (value.diagnostic?.error_code || value.diagnostic?.capability_result?.failures?.join(', ') || 'GPU_REQUIRED');
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  } catch (error) { $('status').textContent = error.message; }
  finally { busy = false; $('check').disabled = $('generate').disabled = false; }
}
$('check').addEventListener('click', () => start(false));
$('generate').addEventListener('click', () => start(true));
api('/api/session').then(value => loggedIn(value.csrf)).catch(() => {});
