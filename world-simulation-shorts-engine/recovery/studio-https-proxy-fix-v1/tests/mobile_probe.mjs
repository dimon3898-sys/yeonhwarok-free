#!/usr/bin/env node
// Reuse the unchanged mobile HTTPS/auth/CSRF/registration/login browser probe
// against a controlled inner HTTP proxy hop. This never starts a GPU job.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const parent = here.startsWith('/opt/') ? '/opt/world-engine-studio-https-bootstrap'
  : path.resolve(here, '../../studio-https-bootstrap-v1');
const output = process.env.WORLD_ENGINE_STUDIO_EVIDENCE_DIR
  || await mkdtemp(path.join(tmpdir(), 'studio-proxy-mobile-evidence-'));
await mkdir(output, {recursive: true});
const report = {schema: 'WORLD_ENGINE_STUDIO_HTTPS_PROXY_MOBILE_CPU_TEST_V1',
  verificationScope: 'SYNTHETIC_PROXY_HOP_CHROMIUM', testOnly: true,
  actualChromium: false, gpuExecuted: false, gpuRenderingVerified: false,
  gcubeHeadersObserved: false, tlsFixture: true, checks: []};
let fixture, fixtureTemp;
let activeCheck = 'synthetic_proxy_fixture_configuration';
try {
  // Always use our controlled fixture, never an operator-supplied public URL.
  fixtureTemp = await mkdtemp(path.join(tmpdir(), 'studio-proxy-mobile-fixture-'));
  const infoPath = path.join(fixtureTemp, 'info.json');
  let fixtureError = false;
  fixture = spawn(process.env.WORLD_ENGINE_PYTHON || '/usr/bin/python3',
    ['-B', path.join(here, 'tls_fixture.py'), '--info', infoPath],
    {stdio: ['ignore', 'ignore', 'ignore'], env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}});
  fixture.once('error', () => { fixtureError = true; });
  let info;
  for (let attempt = 0; attempt < 150; attempt += 1) {
    if (fixtureError || fixture.exitCode !== null) throw new Error('PROXY_TEST_TLS_FIXTURE_START_FAILED');
    try { info = JSON.parse(await readFile(infoPath, 'utf8')); break; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(info, 'PROXY_TEST_TLS_FIXTURE_START_TIMEOUT');
  assert.equal(info.scope, 'CPU_TEST_ONLY');
  assert.equal(info.gpuRenderingVerified, false);
  assert.equal(info.renderAllowed, false);
  activeCheck = 'frozen_mobile_chromium_probe';
  const probeEnv = {...process.env,
    WORLD_ENGINE_HTTPS_TEST_URL: info.origin,
    WORLD_ENGINE_HTTPS_TEST_OWNER_FILE: info.ownerFile,
    WORLD_ENGINE_STUDIO_EVIDENCE_DIR: output};
  // This fixture is loopback-only and has no external requests. A session's
  // outbound HTTP proxy cannot resolve its private .invalid test hostname.
  for (const key of ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy']) delete probeEnv[key];
  probeEnv.NO_PROXY = 'studio-ci.invalid,127.0.0.1,localhost';
  probeEnv.no_proxy = probeEnv.NO_PROXY;
  const probe = spawn(process.execPath, [path.join(parent, 'tests/mobile_probe.mjs')],
    {stdio: ['ignore', 'pipe', 'ignore'], env: probeEnv});
  let stdout = '';
  probe.stdout.on('data', chunk => { stdout += chunk; });
  const exit = await new Promise((resolve, reject) => {
    probe.once('error', reject);
    probe.once('exit', (code, signal) => resolve({code, signal}));
  });
  const inherited = JSON.parse(stdout.trim().split('\n').at(-1));
  Object.assign(report, inherited, {
    schema: report.schema, verificationScope: 'SYNTHETIC_PROXY_HOP_CHROMIUM',
    gcubeHeadersObserved: false, syntheticInnerHop: {
      externalTransport: 'HTTPS', host: 'EXACT_EXTERNAL_AUTHORITY',
      forwardedHost: 'EXACT_EXTERNAL_AUTHORITY', forwardedProto: 'http',
    }, reusedFrozenProbe: true,
  });
  assert.equal(exit.code, 0, 'PROXY_FROZEN_MOBILE_PROBE_FAILED');
  assert.equal(inherited.status, 'PASS', 'PROXY_MOBILE_TESTS_FAILED');
  assert.equal(inherited.actualChromium, true, 'PROXY_ACTUAL_CHROMIUM_REQUIRED');
  assert.equal(inherited.gpuExecuted, false, 'PROXY_GPU_EXECUTION_FORBIDDEN');
  assert.ok(inherited.passCount >= 11, 'PROXY_FROZEN_MOBILE_CHECKS_REQUIRED');
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.failedCheck = report.failedCheck || activeCheck;
  const wrapperErrorCode = /^[A-Z][A-Z0-9_]{3,100}$/.test(String(error?.message || ''))
    ? error.message : 'PROXY_MOBILE_ASSERTION_FAILED';
  if (report.errorCode) report.wrapperErrorCode = wrapperErrorCode;
  else report.errorCode = wrapperErrorCode;
  process.exitCode = 2;
} finally {
  if (fixture && fixture.exitCode === null) {
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
