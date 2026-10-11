const $ = id => document.getElementById(id);
let csrf = '', busy = false, probeReady = false;
async function api(url, body) {
  const response = await fetch(url, {credentials: 'same-origin', ...(body !== undefined ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Proof-CSRF': csrf}, body: JSON.stringify(body)} : {})});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'REQUEST_FAILED');
  return result;
}
async function refreshSession() {
  const value = await api('/api/session');
  probeReady = value.gpu_probe_ready === true;
  $('generate').disabled = busy || !probeReady;
  $('renderer-hash').textContent = value.source.shaderHash;
  if (value.png_filename) {
    $('png').download = value.png_filename;
    $('diagnostic').download = value.png_filename.replace(/\.png$/, '.diagnostic.json');
  }
}
async function loggedIn(token) {
  csrf = token; $('login').hidden = true; $('controls').hidden = false;
  await refreshSession();
  $('status').textContent = probeReady ? 'GPU check is current. Generate the frozen D-final static proof.' : 'Check GPU / WebGL2 first. Generation is enabled only after hardware PASS.';
}
$('login').addEventListener('submit', async event => {
  event.preventDefault();
  try { const value = await api('/auth/login', {password: $('password').value}); $('password').value = ''; await loggedIn(value.csrf); }
  catch (error) { $('status').textContent = error.message; }
});
async function start(proof) {
  if (busy || (proof && !probeReady)) return;
  if (!proof) probeReady = false;
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
        $('status').textContent = value.status === 'PASS' ? (proof ? 'PNG ready. GPU visual approval: USER PENDING.' : 'GPU / WebGL2 capability PASS.') : 'FAIL: ' + (value.diagnostic?.error_code || value.diagnostic?.capability_result?.failures?.join(', ') || 'GPU_REQUIRED') + (value.diagnostic?.failed_stage ? ' · ' + value.diagnostic.failed_stage : '') + ' · Download Diagnostic for Vulkan/EGL details.';
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  } catch (error) { $('status').textContent = error.message; }
  finally {
    busy = false; $('check').disabled = false;
    try { await refreshSession(); } catch { probeReady = false; $('generate').disabled = true; }
  }
}
$('check').addEventListener('click', () => start(false));
$('generate').addEventListener('click', () => start(true));
api('/api/session').then(value => loggedIn(value.csrf)).catch(() => {});
