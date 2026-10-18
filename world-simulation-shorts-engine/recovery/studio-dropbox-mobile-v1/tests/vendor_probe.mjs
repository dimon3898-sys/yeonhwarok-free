// CPU-only interoperability test. It never contacts GitHub or Dropbox.
// Requirements: Node, existing Playwright/Chromium, Python 3 and system libsodium.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(join(root, 'VENDOR_MANIFEST.json'), 'utf8'));
for (const item of manifest.packages) {
  for (const [path, expected] of Object.entries(item.files)) {
    const bytes = readFileSync(join(root, path));
    assert.equal(bytes.length, expected.sizeBytes);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256);
  }
}

// The native process retains its ephemeral private key in memory. Only its
// public key leaves the process; no key, ciphertext or plaintext is logged.
const nativeProgram = String.raw`
import base64, ctypes, ctypes.util, json, sys
path = ctypes.util.find_library('sodium')
if not path:
    raise SystemExit('NATIVE_SODIUM_REQUIRED')
lib = ctypes.cdll.LoadLibrary(path)
assert lib.sodium_init() >= 0
public = ctypes.create_string_buffer(32)
private = ctypes.create_string_buffer(32)
assert lib.crypto_box_keypair(public, private) == 0
print(json.dumps({'publicKey': base64.b64encode(public.raw).decode()}), flush=True)
request = json.loads(sys.stdin.readline())
message = request['message'].encode('utf-8')
ciphertext = base64.b64decode(request['ciphertext'], validate=True)
assert len(ciphertext) == len(message) + 48
output = ctypes.create_string_buffer(len(message))
assert lib.crypto_box_seal_open(output, ciphertext, len(ciphertext), public, private) == 0
assert output.raw == message
tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
assert lib.crypto_box_seal_open(output, tampered, len(tampered), public, private) == -1
lib.sodium_memzero(private, len(private))
lib.sodium_memzero(output, len(output))
print(json.dumps({'nativeOpen': True, 'tamperRejected': True}), flush=True)
`;
const native = spawn(process.env.PYTHON_EXECUTABLE || 'python3', ['-B', '-c', nativeProgram], {
  stdio: ['pipe', 'pipe', 'pipe'],
});
const lines = createInterface({ input: native.stdout })[Symbol.asyncIterator]();
const nativeExit = new Promise((accept, reject) => {
  native.on('error', () => reject(new Error('NATIVE_PROCESS_UNAVAILABLE')));
  native.on('exit', code => code === 0 ? accept() : reject(new Error('NATIVE_PROCESS_FAILED')));
});
// Handle early native failure without exposing subprocess stderr or creating an
// unhandled rejection while the browser is still starting.
nativeExit.catch(() => {});
native.stderr.resume();
let browser;
const timeout = setTimeout(() => {
  native.kill('SIGKILL');
  process.stderr.write('VENDOR_PROBE_TIMEOUT\n');
  process.exit(1);
}, 40_000);

try {
  const first = await lines.next();
  assert.equal(first.done, false, 'NATIVE_PUBLIC_KEY_UNAVAILABLE');
  const { publicKey } = JSON.parse(first.value);
  const browserPath = process.env.CHROMIUM_EXECUTABLE || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  browser = await chromium.launch({ executablePath: browserPath, args: ['--no-sandbox', '--disable-gpu'] });
  const context = await browser.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const errors = [];
  const csp = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'none'; style-src 'none'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
  page.on('pageerror', () => errors.push('BROWSER_SCRIPT_ERROR'));
  await page.route('https://mobile-fixture.invalid/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') {
      await route.fulfill({ status: 200, contentType: 'text/html', headers: { 'Content-Security-Policy': csp },
        body: '<!doctype html><html><head><script src="/libsodium.js"></script><script src="/libsodium-wrappers.js"></script></head><body>CPU cryptography fixture</body></html>' });
    } else if (path === '/libsodium.js' || path === '/libsodium-wrappers.js') {
      await route.fulfill({ status: 200, contentType: 'application/javascript', body: readFileSync(join(root, 'web/vendor', path.slice(1))) });
    } else {
      await route.abort();
    }
  });
  await page.goto('https://mobile-fixture.invalid/');
  const message = 'CPU interoperability fixture — not a credential';
  const result = await page.evaluate(async ({ publicKey, message }) => {
    await sodium.ready;
    const plaintext = sodium.from_string(message);
    const publicBytes = sodium.from_base64(publicKey, sodium.base64_variants.ORIGINAL);
    const sealed = sodium.crypto_box_seal(plaintext, publicBytes);
    const ciphertext = sodium.to_base64(sealed, sodium.base64_variants.ORIGINAL);
    const overhead = sealed.length - plaintext.length;
    sodium.memzero(plaintext);
    return { ciphertext, zeroed: plaintext.every(value => value === 0), overhead, sodiumVersion: sodium.sodium_version_string() };
  }, { publicKey, message });
  assert.deepEqual(errors, []);
  assert.equal(result.zeroed, true);
  assert.equal(result.overhead, 48);
  native.stdin.end(JSON.stringify({ message, ciphertext: result.ciphertext }) + '\n');
  const receipt = await lines.next();
  assert.equal(receipt.done, false, 'NATIVE_RECEIPT_UNAVAILABLE');
  assert.deepEqual(JSON.parse(receipt.value), { nativeOpen: true, tamperRejected: true });
  await nativeExit;
  process.stdout.write(JSON.stringify({ status: 'PASS', browser: browser.version(), viewport: '412x915 mobile',
    sodiumVersion: result.sodiumVersion, localClassicScripts: true, wasmOnlyCsp: true,
    browserSealToNativeOpen: 'PASS', tamperedCiphertextRejected: 'PASS', plaintextByteArrayZeroed: 'PASS',
    ciphertextOverheadBytes: result.overhead, realGitHubSecretWritten: false, realDropboxUsed: false, gpuExecuted: false }) + '\n');
} catch {
  process.stderr.write('VENDOR_PROBE_FAILED\n');
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
  native.kill();
  if (browser) await browser.close();
}
