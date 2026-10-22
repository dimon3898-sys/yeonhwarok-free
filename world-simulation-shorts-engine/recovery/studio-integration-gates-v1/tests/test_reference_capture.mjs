/** CPU-only contract checks. No Chromium, renderer, ffmpeg, or GPU is started. */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {mkdtemp, mkdir, writeFile, symlink, chmod, rm, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {REFERENCE_CAPTURE_CONSTANTS as C, validateExecutionReceipt, readExecutionReceipt,
  validateCapturePaths, captureStudioReference} from '../reference_capture.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const now = Date.parse('2026-10-22T12:00:00Z');
const receipt = () => ({schema: C.schema, jobId: 'studio-reference-test-001',
  requestSHA256: '1'.repeat(64), normalizerSHA256: '2'.repeat(64),
  sourceSceneSHA256: C.sourceSceneSHA256, sourceCommit: C.sourceCommit,
  runtimeSourceSignature: C.runtimeSourceSignature, softwareOnly: true,
  approvedFrameRange: [0, 150], maxWallSeconds: 900,
  expiresAt: '2026-10-22T12:15:00.000Z',
  traceStages: ['StudioController', 'normalizeSubmission', 'ReferenceCapture']});
const hash = value => createHash('sha256').update(value).digest('hex');
const rejects = (update, code) => {
  const value = receipt(); update(value);
  assert.throws(() => validateExecutionReceipt(value, {now}), error => error.code === code);
};

test('valid software receipt is copied and remains distinct from GPU admission', () => {
  const original = receipt(), validated = validateExecutionReceipt(original, {now});
  assert.deepEqual(validated, original); assert.notEqual(validated, original);
  validated.traceStages.push('different'); assert.equal(original.traceStages.length, 3);
  assert.equal(validated.softwareOnly, true); assert.equal('gpuAdmission' in validated, false);
});

test('rejects unknown fields and missing required fields', () => {
  rejects(x => {x.gpuAdmission = true;}, 'REFERENCE_RECEIPT_FIELDS_INVALID');
  rejects(x => {delete x.requestSHA256;}, 'REFERENCE_RECEIPT_FIELDS_INVALID');
});
test('rejects unsafe job identifiers', () => rejects(x => {x.jobId = '../../old-cache';}, 'REFERENCE_RECEIPT_JOB_ID_INVALID'));
test('rejects unbound request and normalizer hashes', () => {
  rejects(x => {x.requestSHA256 = 'x';}, 'REFERENCE_RECEIPT_REQUESTSHA256_INVALID');
  rejects(x => {x.normalizerSHA256 = 'X'.repeat(64);}, 'REFERENCE_RECEIPT_NORMALIZERSHA256_INVALID');
});
test('pins the original scene, source, and runtime without accepting replacements', () => {
  rejects(x => {x.sourceSceneSHA256 = '3'.repeat(64);}, 'REFERENCE_RECEIPT_SOURCESCENESHA256_MISMATCH');
  rejects(x => {x.sourceCommit = '3'.repeat(40);}, 'REFERENCE_RECEIPT_SOURCECOMMIT_MISMATCH');
  rejects(x => {x.runtimeSourceSignature = '3'.repeat(64);}, 'REFERENCE_RECEIPT_RUNTIMESOURCESIGNATURE_MISMATCH');
});
test('rejects GPU or truthy software modes', () => {
  rejects(x => {x.softwareOnly = false;}, 'REFERENCE_SOFTWARE_ONLY_REQUIRED');
  rejects(x => {x.softwareOnly = 'true';}, 'REFERENCE_SOFTWARE_ONLY_REQUIRED');
});
test('requires all original 150 frames starting from zero', () => {
  for (const range of [[1,150], [0,149], [0,150,151], ['0',150]]) rejects(x => {x.approvedFrameRange = range;}, 'REFERENCE_FRAME_RANGE_MUST_BE_0_150');
});
test('bounds total software execution time', () => {
  for (const limit of [0, 901, -1, 1.5, '900']) rejects(x => {x.maxWallSeconds = limit;}, 'REFERENCE_WALL_LIMIT_INVALID');
});
test('requires future explicit UTC receipt expiry', () => {
  rejects(x => {x.expiresAt = '2026-10-22T11:59:59Z';}, 'REFERENCE_RECEIPT_EXPIRED');
  rejects(x => {x.expiresAt = '2026-10-22';}, 'REFERENCE_RECEIPT_EXPIRY_INVALID');
});
test('bounds trace stages and rejects secret-bearing freeform objects', () => {
  rejects(x => {x.traceStages = [];}, 'REFERENCE_RECEIPT_TRACE_INVALID');
  rejects(x => {x.traceStages = [{stage: 'controller', token: 'forbidden'}];}, 'REFERENCE_RECEIPT_TRACE_INVALID');
  rejects(x => {x.traceStages = ['https://example/?token=private'];}, 'REFERENCE_RECEIPT_TRACE_INVALID');
});
test('output and cache cannot use old reproduction or capsule directories', () => {
  const valid = {outputRoot: path.join(root, 'new-job-test'), cacheRoot: '/tmp/new-g1-cache-test', capsuleRoot: '/workspace/exact-65422-capsule-20261020'};
  assert.deepEqual(validateCapturePaths(valid), valid);
  assert.throws(() => validateCapturePaths({...valid, outputRoot: path.resolve(root, '../exact-65422-reproduction-v1')}), /REFERENCE_OUTPUT_MUST_USE_NEW_NAMESPACE_RUN/);
  assert.throws(() => validateCapturePaths({...valid, cacheRoot: path.join(valid.capsuleRoot, 'cache')}), /REFERENCE_CACHE_MUST_BE_NEW_INDEPENDENT/);
  assert.throws(() => validateCapturePaths({...valid, cacheRoot: path.join(root, 'cache')}), /REFERENCE_CACHE_MUST_BE_NEW_INDEPENDENT/);
  assert.throws(() => validateCapturePaths({...valid, cacheRoot: '/workspace/.onboarding/cache'}), /REFERENCE_CACHE_MUST_BE_NEW_INDEPENDENT/);
  assert.throws(() => validateCapturePaths({...valid, outputRoot: root}), /REFERENCE_OUTPUT_MUST_USE_NEW_NAMESPACE_RUN/);
});

test('receipt reader verifies private owned regular files and caller-provided hash', async () => {
  const temporary = await mkdtemp('/tmp/g1-receipt-test-');
  try {
    await chmod(temporary, 0o700);
    const file = path.join(temporary, 'receipt.json'), data = JSON.stringify(receipt());
    await writeFile(file, data, {mode: 0o600});
    const result = await readExecutionReceipt(file, {expectedReceiptSHA256: hash(data), now});
    assert.equal(result.sha256, hash(data)); assert.deepEqual(result.receipt, receipt());
    await assert.rejects(readExecutionReceipt(file, {expectedReceiptSHA256: '0'.repeat(64), now}), /REFERENCE_RECEIPT_HASH_MISMATCH/);
    await chmod(file, 0o644);
    await assert.rejects(readExecutionReceipt(file, {now}), /REFERENCE_RECEIPT_PRIVATE_MODE_REQUIRED/);
    await chmod(file, 0o600);
    const link = path.join(temporary, 'linked.json'); await symlink(file, link);
    await assert.rejects(readExecutionReceipt(link, {now}), /REFERENCE_SYMLINK_PATH_REJECTED/);
    await chmod(temporary, 0o755);
    await assert.rejects(readExecutionReceipt(file, {now}), /REFERENCE_RECEIPT_PRIVATE_PARENT_REQUIRED/);
  } finally { await rm(temporary, {recursive: true, force: true}); }
});
test('rejects symlink directory ancestry even if leaf is private', async () => {
  const temporary = await mkdtemp('/tmp/g1-receipt-ancestor-test-');
  try {
    await chmod(temporary, 0o700);
    const real = path.join(temporary, 'real'); await mkdir(real, {mode: 0o700});
    await writeFile(path.join(real, 'receipt.json'), JSON.stringify(receipt()), {mode: 0o600});
    await symlink(real, path.join(temporary, 'link'));
    await assert.rejects(readExecutionReceipt(path.join(temporary, 'link', 'receipt.json'), {now}), /REFERENCE_SYMLINK_PATH_REJECTED/);
  } finally { await rm(temporary, {recursive: true, force: true}); }
});
test('invalid receipt cannot create capture artifacts or start a runtime', async () => {
  const temporary = await mkdtemp('/tmp/g1-reject-before-render-');
  try {
    await chmod(temporary, 0o700);
    const file = path.join(temporary, 'receipt.json');
    const invalid = receipt(); invalid.softwareOnly = false;
    await writeFile(file, JSON.stringify(invalid), {mode: 0o600});
    await assert.rejects(captureStudioReference({receiptFile: file,
      outputRoot: path.join(root, 'must-not-exist'), cacheRoot: path.join(temporary, 'cache')}), /REFERENCE_SOFTWARE_ONLY_REQUIRED/);
    assert.deepEqual(await readdir(temporary), ['receipt.json']);
  } finally { await rm(temporary, {recursive: true, force: true}); }
});
