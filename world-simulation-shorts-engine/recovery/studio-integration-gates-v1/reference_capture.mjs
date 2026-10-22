/**
 * G1 capture orchestration only. Importing this module never opens a browser,
 * renders a frame, or admits a paid GPU job. The immutable source capsule owns
 * every visual algorithm; this module records a fresh SOFTWARE_PREVIEW.
 */
import path from 'node:path';
import {constants} from 'node:fs';
import {open, lstat, mkdir, readdir, rename, unlink, realpath} from 'node:fs/promises';
import {createHash, randomBytes} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath, pathToFileURL} from 'node:url';

const execute = promisify(execFile);
const namespaceRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(namespaceRoot, '../../..');
const SHA256 = /^[a-f0-9]{64}$/;
const own = (x, k) => Object.prototype.hasOwnProperty.call(x, k);
const within = (child, parent) => child === parent || child.startsWith(parent + path.sep);
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
export const REFERENCE_CAPTURE_CONSTANTS = Object.freeze({
  schema: 'WORLD_ENGINE_STUDIO_REFERENCE_EXECUTION_V1',
  sourceCommit: '2c097df2d02432a3f9ae4dae5d714dbc9eacd434',
  sourceSceneSHA256: 'aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159',
  runtimeSourceSignature: 'b81774e0d8627f0269901daff6fdbd5fdbc06f7dec85f35849f4150525c1126c',
  originalReportSHA256: '550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656',
  runtimeRelativePath: 'world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs',
  sceneRelativePath: 'world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json',
});

function check(condition, code) {
  if (!condition) { const error = new Error(code); error.code = code; throw error; }
}

/** This receipt authenticates an internal, bounded software capture, not GPU admission. */
export function validateExecutionReceipt(receipt, {now = Date.now()} = {}) {
  check(receipt && typeof receipt === 'object' && !Array.isArray(receipt), 'REFERENCE_RECEIPT_OBJECT_REQUIRED');
  const fields = ['schema', 'jobId', 'requestSHA256', 'normalizerSHA256', 'sourceSceneSHA256',
    'sourceCommit', 'runtimeSourceSignature', 'softwareOnly', 'approvedFrameRange', 'maxWallSeconds', 'expiresAt', 'traceStages'];
  check(Object.keys(receipt).every(key => fields.includes(key)) && fields.every(key => own(receipt, key)), 'REFERENCE_RECEIPT_FIELDS_INVALID');
  check(receipt.schema === REFERENCE_CAPTURE_CONSTANTS.schema, 'REFERENCE_RECEIPT_SCHEMA_INVALID');
  check(typeof receipt.jobId === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(receipt.jobId), 'REFERENCE_RECEIPT_JOB_ID_INVALID');
  for (const key of ['requestSHA256', 'normalizerSHA256']) check(typeof receipt[key] === 'string' && SHA256.test(receipt[key]), 'REFERENCE_RECEIPT_' + key.toUpperCase() + '_INVALID');
  for (const key of ['sourceSceneSHA256', 'sourceCommit', 'runtimeSourceSignature']) check(receipt[key] === REFERENCE_CAPTURE_CONSTANTS[key], 'REFERENCE_RECEIPT_' + key.toUpperCase() + '_MISMATCH');
  check(receipt.softwareOnly === true, 'REFERENCE_SOFTWARE_ONLY_REQUIRED');
  check(Array.isArray(receipt.approvedFrameRange) && receipt.approvedFrameRange.length === 2 && receipt.approvedFrameRange[0] === 0 && receipt.approvedFrameRange[1] === 150, 'REFERENCE_FRAME_RANGE_MUST_BE_0_150');
  check(Number.isInteger(receipt.maxWallSeconds) && receipt.maxWallSeconds > 0 && receipt.maxWallSeconds <= 900, 'REFERENCE_WALL_LIMIT_INVALID');
  check(typeof receipt.expiresAt === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(receipt.expiresAt), 'REFERENCE_RECEIPT_EXPIRY_INVALID');
  const expiry = Date.parse(receipt.expiresAt);
  check(Number.isFinite(expiry) && expiry > now, 'REFERENCE_RECEIPT_EXPIRED');
  check(Array.isArray(receipt.traceStages) && receipt.traceStages.length >= 1 && receipt.traceStages.length <= 32 &&
    receipt.traceStages.every(stage => typeof stage === 'string' && /^[a-zA-Z0-9_./:>-]{1,128}$/.test(stage)), 'REFERENCE_RECEIPT_TRACE_INVALID');
  return structuredClone(receipt);
}

async function noSymlinkAncestry(file) {
  const absolute = path.resolve(file);
  let current = path.parse(absolute).root;
  for (const segment of absolute.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, segment);
    try { check(!(await lstat(current)).isSymbolicLink(), 'REFERENCE_SYMLINK_PATH_REJECTED'); }
    catch (error) { if (error.code === 'ENOENT') break; throw error; }
  }
  return absolute;
}

async function readRegular(file, {privateOwned = false, maxBytes = 64 * 1024 * 1024} = {}) {
  await noSymlinkAncestry(file);
  const fd = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const before = await fd.stat();
    check(before.isFile(), 'REFERENCE_REGULAR_FILE_REQUIRED');
    check(before.size <= maxBytes, 'REFERENCE_FILE_TOO_LARGE');
    if (privateOwned) {
      check(before.uid === process.getuid(), 'REFERENCE_RECEIPT_OWNER_INVALID');
      check((before.mode & 0o077) === 0, 'REFERENCE_RECEIPT_PRIVATE_MODE_REQUIRED');
      const parent = await lstat(path.dirname(path.resolve(file)));
      check(parent.isDirectory() && parent.uid === process.getuid() && (parent.mode & 0o077) === 0, 'REFERENCE_RECEIPT_PRIVATE_PARENT_REQUIRED');
    }
    const bytes = await fd.readFile();
    const after = await fd.stat();
    check(before.dev === after.dev && before.ino === after.ino && before.size === after.size &&
      before.mtimeMs === after.mtimeMs && bytes.length === before.size, 'REFERENCE_FILE_CHANGED_DURING_READ');
    return bytes;
  } finally { await fd.close(); }
}

export async function readExecutionReceipt(receiptFile, {expectedReceiptSHA256, now = Date.now()} = {}) {
  check(typeof receiptFile === 'string' && path.isAbsolute(receiptFile), 'REFERENCE_RECEIPT_ABSOLUTE_PATH_REQUIRED');
  if (expectedReceiptSHA256 !== undefined) check(typeof expectedReceiptSHA256 === 'string' && SHA256.test(expectedReceiptSHA256), 'REFERENCE_RECEIPT_EXPECTED_HASH_INVALID');
  const bytes = await readRegular(receiptFile, {privateOwned: true, maxBytes: 64 * 1024});
  const sha256 = digest(bytes);
  if (expectedReceiptSHA256 !== undefined) check(sha256 === expectedReceiptSHA256, 'REFERENCE_RECEIPT_HASH_MISMATCH');
  let receipt;
  try { receipt = JSON.parse(bytes.toString('utf8')); }
  catch { check(false, 'REFERENCE_RECEIPT_JSON_INVALID'); }
  return {receipt: validateExecutionReceipt(receipt, {now}), sha256};
}

export function validateCapturePaths({outputRoot, cacheRoot, capsuleRoot}) {
  for (const [key, value] of Object.entries({outputRoot, cacheRoot, capsuleRoot})) check(typeof value === 'string' && path.isAbsolute(value), 'REFERENCE_' + key.toUpperCase() + '_ABSOLUTE_REQUIRED');
  outputRoot = path.resolve(outputRoot); cacheRoot = path.resolve(cacheRoot); capsuleRoot = path.resolve(capsuleRoot);
  check(within(outputRoot, namespaceRoot) && outputRoot !== namespaceRoot, 'REFERENCE_OUTPUT_MUST_USE_NEW_NAMESPACE_RUN');
  check(!within(capsuleRoot, repositoryRoot) && !capsuleRoot.split(path.sep).includes('.onboarding'), 'REFERENCE_CAPSULE_MUST_BE_INDEPENDENT');
  check(!within(cacheRoot, repositoryRoot) && !within(cacheRoot, capsuleRoot) && !within(capsuleRoot, cacheRoot) &&
    !cacheRoot.split(path.sep).includes('.onboarding') && !within(outputRoot, cacheRoot), 'REFERENCE_CACHE_MUST_BE_NEW_INDEPENDENT');
  return {outputRoot, cacheRoot, capsuleRoot};
}

async function freshPrivateDirectory(directory) {
  await noSymlinkAncestry(directory);
  try { await mkdir(directory, {mode: 0o700}); }
  catch (error) { if (error.code !== 'EEXIST') throw error; }
  const info = await lstat(directory);
  check(info.isDirectory() && info.uid === process.getuid() && (info.mode & 0o077) === 0, 'REFERENCE_PRIVATE_DIRECTORY_REQUIRED');
  check((await readdir(directory)).length === 0, 'REFERENCE_FRESH_EMPTY_DIRECTORY_REQUIRED');
}

async function exclusiveWrite(file, bytes) {
  const fd = await open(file, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
  try { await fd.writeFile(bytes); await fd.sync(); } finally { await fd.close(); }
}

async function atomicJSON(file, value) {
  const temporary = file + '.' + randomBytes(8).toString('hex') + '.writing';
  await exclusiveWrite(temporary, JSON.stringify(value) + '\n');
  await rename(temporary, file);
}

/**
 * Called only after the current Studio controller authenticated and claimed the
 * request. Neither arbitrary Scene JSON nor a receipt selects a different runtime.
 */
export async function captureStudioReference({receiptFile, outputRoot, cacheRoot,
  capsuleRoot = '/workspace/exact-65422-capsule-20261020',
  originalReportFile = '/workspace/exact-65422-original-report-20261020.json', expectedReceiptSHA256} = {}) {
  const {receipt, sha256: receiptSHA256} = await readExecutionReceipt(receiptFile, {expectedReceiptSHA256});
  const locations = validateCapturePaths({outputRoot, cacheRoot, capsuleRoot});
  ({outputRoot, cacheRoot, capsuleRoot} = locations);
  await Promise.all([noSymlinkAncestry(capsuleRoot), noSymlinkAncestry(outputRoot), noSymlinkAncestry(cacheRoot)]);
  check(await realpath(capsuleRoot) === capsuleRoot, 'REFERENCE_CAPSULE_REALPATH_MISMATCH');
  const originalBytes = await readRegular(originalReportFile);
  check(digest(originalBytes) === REFERENCE_CAPTURE_CONSTANTS.originalReportSHA256, 'REFERENCE_ORIGINAL_REPORT_HASH_MISMATCH');
  const original = JSON.parse(originalBytes.toString('utf8'));
  check(original.sourceCommit === receipt.sourceCommit && original.runtimeSourceSignature === receipt.runtimeSourceSignature &&
    original.frames.length === 150 && original.frames.every((row, frame) => row.frame === frame && SHA256.test(row.raw_rgba_sha256) && SHA256.test(row.png_sha256)), 'REFERENCE_ORIGINAL_REPORT_CONTRACT_MISMATCH');
  const verifySources = async () => {
    for (const binding of original.sourceBindings) {
      check(typeof binding.path === 'string' && !path.isAbsolute(binding.path) && !binding.path.split(/[\\/]/).includes('..'), 'REFERENCE_SOURCE_PATH_INVALID');
      const bytes = await readRegular(path.join(capsuleRoot, binding.path));
      check(bytes.length === binding.bytes && digest(bytes) === binding.sha256, 'REFERENCE_SOURCE_BINDING_MISMATCH');
    }
    check(digest(await readRegular(path.join(capsuleRoot, REFERENCE_CAPTURE_CONSTANTS.sceneRelativePath))) === receipt.sourceSceneSHA256, 'REFERENCE_SOURCE_SCENE_MISMATCH');
  };
  await verifySources();
  await freshPrivateDirectory(outputRoot);
  await freshPrivateDirectory(cacheRoot);
  const proofRoot = path.join(outputRoot, 'proof'), publicRoot = path.join(outputRoot, 'public-review');
  const framesRoot = path.join(cacheRoot, 'frames'), rowsRoot = path.join(cacheRoot, 'rows');
  for (const directory of [proofRoot, publicRoot, path.join(outputRoot, 'reports'), framesRoot, rowsRoot]) await mkdir(directory, {mode: 0o700});
  const lockFile = path.join(cacheRoot, 'ACTIVE_CAPTURE.json');
  await exclusiveWrite(lockFile, JSON.stringify({jobId: receipt.jobId, pid: process.pid, startedAt: new Date().toISOString()}));
  const started = performance.now(), deadline = Date.now() + receipt.maxWallSeconds * 1000;
  // Keep failure persistence and cooperative browser cleanup inside the bound.
  const cleanupReserveMilliseconds = Math.min(2000, receipt.maxWallSeconds * 100);
  const operationDeadline = deadline - cleanupReserveMilliseconds;
  const report = {schema: 'WORLD_ENGINE_STUDIO_REFERENCE_CAPTURE_V1', status: 'IN_PROGRESS',
    jobId: receipt.jobId, executionReceiptSHA256: receiptSHA256, requestSHA256: receipt.requestSHA256,
    normalizerSHA256: receipt.normalizerSHA256, controllerTraceStages: receipt.traceStages,
    sourceSceneSHA256: receipt.sourceSceneSHA256, sourceCommit: receipt.sourceCommit,
    runtimeSourceSignature: receipt.runtimeSourceSignature, originalReportSHA256: digest(originalBytes),
    originalCaptureSignature: original.resume.signature, sourceBindings: original.sourceBindings,
    captureKind: 'NEW_DRAW_FROM_UNCHANGED_ORIGINAL_RUNTIME', classification: 'SOFTWARE_PREVIEW',
    backendKind: 'SWIFTSHADER_SOFTWARE', nvidiaVerified: false, gpuRenderingVerified: false,
    productionEligible: false, visualQualityApproved: false, finalPromotion: false, paidGpuExecuted: false,
    width: 1080, height: 1920, fps: 30, totalFrames: 150, durationSeconds: 5, audio: false,
    originalVideoReused: false, oldCacheReused: false, reusedFrames: 0, newlyRenderedFrames: 0,
    startedAtUtc: new Date().toISOString(), frames: [], checkpoints: [], firstDivergence: null};
  let session, closing, failure, stage = 'RUNTIME_IMPORT', activeFrame = null;
  const remaining = () => { const ms = operationDeadline - Date.now(); check(ms > 0, 'REFERENCE_CAPTURE_WALL_LIMIT_EXCEEDED'); return ms; };
  const closeRuntime = () => closing ??= session.close();
  const bounded = async promise => {
    let timer;
    try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => { const error = new Error('REFERENCE_CAPTURE_WALL_LIMIT_EXCEEDED'); error.code = error.message; reject(error); }, remaining()); })]); }
    finally { clearTimeout(timer); }
  };
  const run = (command, args, maxBuffer) => execute(command, args, {maxBuffer, timeout: remaining(), killSignal: 'SIGTERM'});
  try {
    const {openQualityRuntime, assertQualityDiagnostic} = await import(pathToFileURL(path.join(capsuleRoot, REFERENCE_CAPTURE_CONSTANTS.runtimeRelativePath)).href);
    stage = 'RUNTIME_OPEN';
    const opening = openQualityRuntime({mode: 'VISUAL_REFERENCE_STUDY'});
    try { session = await bounded(opening); }
    catch (error) { opening.then(late => late.close()).catch(() => {}); throw error; }
    check(session.sourceSignature === receipt.runtimeSourceSignature, 'REFERENCE_RUNTIME_SOURCE_SIGNATURE_MISMATCH');
    check(String(session.info.backend).includes('SwiftShader'), 'REFERENCE_SOFTWARE_BACKEND_REQUIRED');
    check(session.info.cameraMotion.status === 'PASS' && session.info.cameraMotion.fakeLockCount === 0, 'REFERENCE_ORIGINAL_CAMERA_CONTRACT_MISMATCH');
    report.runtime = session.info;
    // The immutable runtime's legacy productionEligible is not GPU authorization.
    report.runtimeLegacyProductionEligibleIsNotAdmission = true;
    for (let frame = 0; frame < 150; frame++) {
      activeFrame = frame; stage = 'DRAW_READBACK'; remaining();
      const captureStarted = performance.now();
      const captured = await bounded(session.page.evaluate(f => window.referenceProof.capture(f, {png: true}), frame));
      stage = 'DIAGNOSTIC_CONTRACT';
      const diagnostic = assertQualityDiagnostic(captured.diagnostic, {frame});
      check(typeof captured.png === 'string' && captured.png.startsWith('data:image/png;base64,'), 'REFERENCE_PNG_DATA_INVALID');
      const bytes = Buffer.from(captured.png.slice('data:image/png;base64,'.length), 'base64');
      check(bytes.length >= 24 && bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10])) && bytes.readUInt32BE(16) === 1080 && bytes.readUInt32BE(20) === 1920, 'REFERENCE_PNG_DIMENSIONS_INVALID');
      check(digest(bytes) === captured.png_sha256 && SHA256.test(captured.raw_rgba_sha256), 'REFERENCE_READBACK_HASH_INVALID');
      const rawEqual = captured.raw_rgba_sha256 === original.frames[frame].raw_rgba_sha256;
      const pngEqual = captured.png_sha256 === original.frames[frame].png_sha256;
      if ((!rawEqual || !pngEqual) && report.firstDivergence === null) report.firstDivergence = {stage: 'RAW_RGBA_OR_PNG_COMPARISON', frame, rawEqual, pngEqual};
      const row = {frame, timeSeconds: frame / 30, sourceCommit: receipt.sourceCommit,
        runtimeSourceSignature: session.sourceSignature, raw_rgba_sha256: captured.raw_rgba_sha256,
        png_sha256: captured.png_sha256, originalRawRgbaEqual: rawEqual, originalPngEqual: pngEqual,
        camera: diagnostic.camera, scalarControl: diagnostic.territory.controls,
        frontier: diagnostic.frontierLight, units: diagnostic.units,
        material: {terrain: diagnostic.terrain, territory: diagnostic.territory.material},
        protection: diagnostic.protection, diagnostic, captureWallMilliseconds: performance.now() - captureStarted};
      stage = 'FRAME_PERSIST';
      const name = String(frame).padStart(3, '0');
      await exclusiveWrite(path.join(framesRoot, name + '.png'), bytes);
      await exclusiveWrite(path.join(rowsRoot, name + '.json'), JSON.stringify(row) + '\n');
      report.frames.push(row); report.newlyRenderedFrames++;
      if ([0, 30, 60, 90, 120].includes(frame)) {
        const file = 'STUDIO_G1_' + String(frame / 30).padStart(2, '0') + 'S.png';
        await exclusiveWrite(path.join(publicRoot, file), bytes);
        report.checkpoints.push({file, frame, sha256: digest(bytes), bytes: bytes.length});
      }
      if (frame % 15 === 0 || frame === 149) await atomicJSON(path.join(proofRoot, 'CAPTURE_STATUS.json'), {
        classification: 'SOFTWARE_PREVIEW', status: 'CAPTURING', jobId: receipt.jobId,
        lastFrame: frame, capturedFrames: report.frames.length, firstDivergence: report.firstDivergence,
        nvidiaVerified: false, visualQualityApproved: false});
    }
    stage = 'RUNTIME_CLOSE';
    check(session.errors.length === 0, 'REFERENCE_BROWSER_ERRORS');
    await bounded(closeRuntime()); session = null;
    await verifySources();
    stage = 'VIDEO_ENCODE'; activeFrame = null;
    const videoFile = 'WORLD_ENGINE_STUDIO_G1_REFERENCE_5S.mp4', videoPath = path.join(publicRoot, videoFile);
    const args = ['-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-framerate', '30', '-start_number', '0', '-threads', '2',
      '-i', path.join(framesRoot, '%03d.png'), '-frames:v', '150', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '16',
      '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', videoPath];
    report.encoding = {codec: 'libx264', preset: 'fast', crf: 16, threads: 2, pixelFormat: 'yuv420p', frames: 150, audio: false};
    await run('ffmpeg', args, 8 * 1024 * 1024);
    const videoBytes = await readRegular(videoPath);
    report.video = {file: videoFile, sha256: digest(videoBytes), bytes: videoBytes.length};
    stage = 'FFPROBE';
    report.ffprobe = JSON.parse((await run('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', videoPath], 2 * 1024 * 1024)).stdout);
    const streams = report.ffprobe.streams, stream = streams[0];
    check(streams.length === 1 && stream.codec_name === 'h264' && stream.width === 1080 && stream.height === 1920 &&
      stream.avg_frame_rate === '30/1' && Number(stream.nb_frames) === 150 && Number(stream.duration) === 5, 'REFERENCE_VIDEO_CONTRACT_MISMATCH');
    stage = 'VIDEO_FULL_DECODE';
    await run('ffmpeg', ['-v', 'error', '-nostdin', '-i', videoPath, '-f', 'null', '-'], 1024 * 1024);
    report.fullDecode = 'PASS';
    report.rawRgbaEqualFrames = report.frames.filter(row => row.originalRawRgbaEqual).length;
    report.pngEqualFrames = report.frames.filter(row => row.originalPngEqual).length;
    report.status = report.firstDivergence === null ? 'SOFTWARE_REFERENCE_RAW_MATCH_USER_REVIEW_REQUIRED' : 'REPRODUCTION_NEEDS_REWORK';
    const sums = [report.video, ...report.checkpoints].map(item => item.sha256 + '  ' + item.file).join('\n') + '\n';
    await exclusiveWrite(path.join(publicRoot, 'SHA256SUMS'), sums);
    await atomicJSON(path.join(outputRoot, 'reports', 'SAFE_CAPTURE_SUMMARY.json'), {
      schema: report.schema, status: report.status, classification: report.classification,
      jobId: report.jobId, frames: report.frames.length, newlyRenderedFrames: report.newlyRenderedFrames,
      reusedFrames: 0, rawRgbaEqualFrames: report.rawRgbaEqualFrames, pngEqualFrames: report.pngEqualFrames,
      firstDivergence: report.firstDivergence, video: report.video, checkpoints: report.checkpoints,
      nvidiaVerified: false, visualQualityApproved: false, finalPromotion: false});
  } catch (error) {
    failure = error; report.status = 'FAILED';
    report.failure = {stage, frame: activeFrame, code: error.code && /^[A-Z0-9_]+$/.test(error.code) ? error.code : 'REFERENCE_CAPTURE_FAILED', reason: String(error.message).slice(0, 2048)};
    report.firstFailure = report.failure;
  } finally {
    // A browser stalled during cleanup must not swallow the first failure.
    if (failure) {
      await atomicJSON(path.join(proofRoot, 'CAPTURE_REPORT.json'), report);
      await atomicJSON(path.join(proofRoot, 'CAPTURE_STATUS.json'), {status: 'FAILED', jobId: report.jobId,
        classification: 'SOFTWARE_PREVIEW', capturedFrames: report.frames.length,
        firstDivergence: report.firstDivergence, failure: report.failure,
        nvidiaVerified: false, visualQualityApproved: false});
    }
    let cleanupTimer;
    try {
      if (session) await Promise.race([closeRuntime(), new Promise((_, reject) => {
        cleanupTimer = setTimeout(() => {
          const error = new Error('REFERENCE_RUNTIME_CLOSE_DEADLINE'); error.code = error.message; reject(error);
        }, Math.max(1, Math.min(1000, deadline - Date.now())));
      })]);
    } catch (error) {
      report.closeFailure = {code: 'REFERENCE_RUNTIME_CLOSE_FAILED', reason: String(error.message).slice(0, 2048)};
      failure ??= error;
    } finally { clearTimeout(cleanupTimer); }
    report.completedAtUtc = new Date().toISOString(); report.wallSeconds = (performance.now() - started) / 1000;
    if (failure && report.status !== 'FAILED') report.status = 'FAILED';
    await atomicJSON(path.join(proofRoot, 'CAPTURE_REPORT.json'), report);
    await atomicJSON(path.join(proofRoot, 'CAPTURE_STATUS.json'), {status: report.status, jobId: report.jobId,
      classification: 'SOFTWARE_PREVIEW', capturedFrames: report.frames.length, firstDivergence: report.firstDivergence,
      failure: report.failure ?? null, nvidiaVerified: false, visualQualityApproved: false});
    await unlink(lockFile);
  }
  if (failure) { failure.captureReportFile = path.join(proofRoot, 'CAPTURE_REPORT.json'); throw failure; }
  return {reportFile: path.join(proofRoot, 'CAPTURE_REPORT.json'), outputRoot,
    publicRoot, status: report.status, classification: report.classification, video: report.video,
    rawRgbaEqualFrames: report.rawRgbaEqualFrames, pngEqualFrames: report.pngEqualFrames,
    newlyRenderedFrames: report.newlyRenderedFrames, reusedFrames: 0, firstDivergence: report.firstDivergence};
}

// A child process is launched only by the authenticated Studio job controller.
// Merely importing this module has no execution side effects.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const flags = {};
    for (const argument of process.argv.slice(2)) {
      const match = /^--(receipt|output-root|cache-root|receipt-sha256|capsule|capsule-root|original-report)=(.+)$/.exec(argument);
      const key = match?.[1] === 'capsule-root' ? 'capsule' : match?.[1];
      check(match && !own(flags, key), 'REFERENCE_CLI_ARGUMENT_INVALID');
      flags[key] = match[2];
    }
    for (const key of ['receipt', 'output-root', 'cache-root', 'receipt-sha256']) check(own(flags, key), 'REFERENCE_CLI_ARGUMENT_REQUIRED');
    const result = await captureStudioReference({receiptFile: flags.receipt, outputRoot: flags['output-root'],
      cacheRoot: flags['cache-root'], expectedReceiptSHA256: flags['receipt-sha256'],
      ...(flags.capsule ? {capsuleRoot: flags.capsule} : {}),
      ...(flags['original-report'] ? {originalReportFile: flags['original-report']} : {})});
    process.stdout.write(JSON.stringify(result) + '\n');
    if (result.status === 'REPRODUCTION_NEEDS_REWORK') process.exitCode = 2;
  } catch (error) {
    process.stderr.write(JSON.stringify({status: 'FAILED', classification: 'SOFTWARE_PREVIEW',
      code: /^[A-Z0-9_]+$/.test(error.code ?? '') ? error.code : 'REFERENCE_CAPTURE_FAILED',
      ...(error.captureReportFile ? {captureReportFile: error.captureReportFile} : {})}) + '\n');
    process.exitCode = 1;
  }
}
