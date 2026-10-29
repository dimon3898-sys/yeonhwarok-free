/** Focused new tests for one launch-options change. No browser/GPU/network calls.
 * Usage: node test_profile_surface.mjs <baseline-profile.mjs> <evidence-directory>
 * Baseline must be the exact file from the recorded base commit.
 */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const baselinePath = path.resolve(process.argv[2]);
const evidenceDir = path.resolve(process.argv[3]);
const afterPath = new URL('../codex-to-gcube-handoff-v1/backend/profile_contract.mjs', import.meta.url);
const beforeBytes = await readFile(baselinePath);
const afterBytes = await readFile(afterPath);
const before = await import(pathToFileURL(baselinePath));
const after = await import(afterPath);
const surface = '--disable-vulkan-surface';
const originalFragment = "'--use-angle=vulkan','--enable-features='+features.join(','),'--disable-vulkan-surface',";
const replacementFragment = "'--use-angle=vulkan','--enable-features='+features.join(','),";
const records = [], comparisons = [];

function run(name, task) {
  try { task(); records.push({name, status: 'PASS'}); console.log('PASS ' + name); }
  catch (error) { records.push({name, status: 'FAIL', message: error.message}); console.log('FAIL ' + name + ': ' + error.message); }
}
function compare(options, identity, name) {
  const initial = structuredClone(options);
  const oldResult = before.buildVulkanLaunchOptions(options, identity);
  const newResult = after.buildVulkanLaunchOptions(options, identity);
  assert.deepEqual(options, initial, 'input options must not mutate');
  assert.equal(oldResult.options.args.filter(a => a === surface).length, 1);
  assert.equal(oldResult.evidence.selectedArgs.filter(a => a === surface).length, 1);
  const expected = structuredClone(oldResult);
  expected.options.args = expected.options.args.filter(a => a !== surface);
  expected.evidence.selectedArgs = expected.evidence.selectedArgs.filter(a => a !== surface);
  assert.deepEqual(newResult, expected, 'entire return object may differ only by the surface flag');
  assert.deepEqual(newResult.options.args, newResult.evidence.selectedArgs);
  assert.equal(newResult.options.args.some(a => a.split('=')[0] === surface), false);
  const args = newResult.options.args;
  assert.equal(args.filter(a => a === '--use-gl=angle').length, 1);
  assert.equal(args.filter(a => a === '--use-angle=vulkan').length, 1);
  assert.equal(args.filter(a => a === '--disable-software-rasterizer').length, 1);
  assert.equal(args.some(a => /swiftshader|--disable-gpu(?:=|$)|--disable-webgl2?(?:=|$)/.test(a)), false);
  comparisons.push({name, inputOptions: initial, identity,
    before: oldResult, after: newResult, removed: [surface], added: []});
  return newResult;
}
const actualCaptureOptions = {
  executablePath: '/usr/bin/chromium', headless: true,
  args: ['--no-sandbox', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--disable-dev-shm-usage']
};

run('source delta is exactly one final push item; other functions unchanged', () => {
  const original = beforeBytes.toString('utf8');
  assert.equal(original.split(originalFragment).length - 1, 1);
  assert.equal(afterBytes.toString('utf8'), original.replace(originalFragment, replacementFragment));
  assert.ok(afterBytes.toString('utf8').includes("'--disable-software-rasterizer','--disable-vulkan-surface','--headless'"));
});
run('actual G2 capture call: complete output differs by surface flag only', () => {
  assert.equal(process.getuid(), 1000, 'focused test runs as UID 1000');
  const result = compare(actualCaptureOptions, {uid: process.getuid(), rootTestOptIn: false}, 'actual-G2-capture-call');
  assert.equal(result.options.chromiumSandbox, true);
  assert.equal(result.evidence.sandbox, 'CHROMIUM_SANDBOX');
  assert.equal(result.options.args.includes('--no-sandbox'), false);
  assert.equal(result.options.args.includes('--disable-setuid-sandbox'), false);
});
run('caller surface flag and conflicting duplicated backend/features normalize safely', () => {
  const result = compare({executablePath: '/usr/bin/chromium', headless: false,
    args: ['--disable-vulkan-surface', '--disable-vulkan-surface',
      '--use-angle=swiftshader', '--use-angle', 'gl', '--use-gl=desktop', '--use-vulkan', 'swiftshader',
      '--enable-features=Vulkan,Alpha,Alpha', '--enable-features', 'Beta,Vulkan',
      '--disable-features=Vulkan,Gamma,Gamma', '--disable-features', 'Delta',
      '--no-sandbox', '--disable-setuid-sandbox', '--enable-unsafe-swiftshader',
      '--disable-gpu', '--disable-gpu-compositing', '--disable-webgl2', '--disable-software-rasterizer',
      '--disable-dev-shm-usage'], ignoreDefaultArgs: ['--mute-audio']},
    {uid: 1000}, 'conflicting-caller-args');
  assert.equal(result.options.args.filter(a => a.startsWith('--enable-features=')).length, 1);
  assert.equal(result.options.args.filter(a => a.startsWith('--disable-features=')).length, 1);
  assert.ok(result.options.args.includes('--enable-features=Alpha,Beta,Vulkan'));
  assert.ok(result.options.args.includes('--disable-features=Gamma,Delta'));
  assert.equal(result.options.args.some(a => a.startsWith('--use-vulkan')), false, 'do not add native-selection change');
  assert.equal(result.options.chromiumSandbox, true);
});
run('default arguments and feature parameters preserve all unrelated options', () => {
  compare({executablePath: '/usr/bin/chromium'}, {uid: 1000}, 'default-options');
  const result = compare({executablePath: '/usr/bin/chromium', timeout: 12000,
    args: ['--enable-features=Vulkan:Example/1,Alpha:param/value',
      '--disable-features=Vulkan<Trial,Gamma'], ignoreDefaultArgs: []}, {uid: 1000}, 'parameterized-features');
  assert.equal(result.options.timeout, 12000);
  assert.ok(result.options.args.includes('--enable-features=Alpha:param/value,Vulkan'));
  assert.ok(result.options.args.includes('--disable-features=Gamma'));
});
run('UID and explicit root-test sandbox rejection policies unchanged', () => {
  for (const [identity, code] of [
    [{uid: 0}, 'HANDOFF_NONROOT_SANDBOX_REQUIRED'],
    [{uid: 1000, rootTestOptIn: true}, 'HANDOFF_ROOT_TEST_OPTIN_ROOT_ONLY']
  ]) {
    for (const module of [before, after])
      assert.throws(() => module.buildVulkanLaunchOptions(actualCaptureOptions, identity), {message: code});
  }
  const root = compare(actualCaptureOptions, {uid: 0, rootTestOptIn: true}, 'explicit-root-test-only');
  assert.equal(root.options.chromiumSandbox, false);
  assert.equal(root.options.args.filter(a => a === '--no-sandbox').length, 1);
  assert.equal(root.evidence.sandbox, 'EXPLICIT_ROOT_TEST_ONLY');
});
run('all five security-bypass options remain rejected in both forms', () => {
  for (const flag of ['--disable-web-security', '--allow-running-insecure-content',
    '--ignore-certificate-errors', '--proxy-server', '--host-resolver-rules']) {
    for (const args of [[flag], [flag + '=test-only']]) {
      const options = {executablePath: '/usr/bin/chromium', args};
      for (const module of [before, after])
        assert.throws(() => module.buildVulkanLaunchOptions(options, {uid: 1000}),
          {message: 'HANDOFF_BROWSER_SECURITY_BYPASS_FORBIDDEN'});
    }
  }
});
run('default-argument and executable-path safety guards remain rejected', () => {
  for (const [options, code] of [
    [{executablePath: '/usr/bin/chromium', ignoreDefaultArgs: true}, 'HANDOFF_BROWSER_DEFAULTS_REQUIRED'],
    [{executablePath: 'chromium'}, 'HANDOFF_BROWSER_EXECUTABLE_INVALID']
  ]) {
    for (const module of [before, after])
      assert.throws(() => module.buildVulkanLaunchOptions(options, {uid: 1000}), {message: code});
  }
});

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
await writeFile(path.join(evidenceDir, 'CHROMIUM_ARGS_BEFORE_AFTER.json'), JSON.stringify({
  schema: 'WORLD_ENGINE_VULKAN_SURFACE_ARGS_COMPARISON_V1',
  scope: 'BUILD_FUNCTION_OUTPUT_NOT_OBSERVED_BROWSER_PROCESS_ARGV',
  comparisons
}, null, 2) + '\n');
const result = {
  schema: 'WORLD_ENGINE_VULKAN_SURFACE_FOCUSED_CPU_TESTS_V1',
  status: records.every(row => row.status === 'PASS') ? 'PASS' : 'BLOCKED',
  scope: 'SINGLE_LAUNCH_OPTION_FUNCTION_ONLY_NOT_GPU_INITIALIZATION_PASS',
  node: process.version, uid: process.getuid(), tests: records,
  beforeSourceSHA256: sha256(beforeBytes), afterSourceSHA256: sha256(afterBytes),
  priorPassSuitesRerun: false, nativeGuardTestsRerun: false,
  browserLaunched: false, gpuExecuted: false, imageBuiltOrPublished: false,
  gpuInitialization: 'NOT_RUN_NOT_CLAIMED'
};
await writeFile(path.join(evidenceDir, 'TEST_RESULTS.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({status: result.status, passed: records.filter(row => row.status === 'PASS').length,
  total: records.length, beforeSourceSHA256: result.beforeSourceSHA256,
  afterSourceSHA256: result.afterSourceSHA256, gpuInitialization: result.gpuInitialization}));
if (result.status !== 'PASS') process.exitCode = 1;
