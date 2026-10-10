/** Bounded diagnostic state only. No renderer/material imports. */
export const stages = ['START', 'ENVIRONMENT', 'GRAPHICS_RUNTIME', 'BROWSER_LAUNCH', 'PAGE_CREATE', 'PAGE_LOAD', 'WEBGL2_CREATE', 'GPU_IDENTITY', 'READPIXELS', 'RESULT'];
const secretName = /OWNER_CODE|PASSWORD|PASSWD|TOKEN|SECRET|CREDENTIAL|API_KEY|PRIVATE_KEY|ACCESS_KEY/i;
export function redact(input, env = process.env) {
  let text = String(input ?? '');
  for (const [name, value] of Object.entries(env)) if (secretName.test(name) && value) text = text.split(value).join('[REDACTED]');
  return text.replace(/(https?:\/\/)[^\s/@]+:[^\s/@]+@/g, '$1[REDACTED]@')
    .replace(/(Bearer\s+)[\w.+/=-]+/gi, '$1[REDACTED]')
    .replace(/((?:password|token|secret|api[_-]?key|authorization|cookie|owner[_-]?code)[\s"':=]+)[^\s,;"']+/gi, '$1[REDACTED]')
    .slice(0, 65536);
}
export function classify(error, stage, backend) {
  const message = String(error?.message || error);
  if (/timeout/i.test(message)) return stage === 'BROWSER_LAUNCH' ? 'CHROMIUM_LAUNCH_TIMEOUT' : stage + '_TIMEOUT';
  if (/VK_ERROR|failed.*vulkan|vulkan.*(?:failed|initializ)|libvulkan/i.test(message) && backend === 'vulkan') return 'VULKAN_INITIALIZATION_FAILED';
  if (/EGL_NOT_INITIALIZED|EGL_BAD|failed.*egl|egl.*(?:failed|initializ)|libEGL/i.test(message) && backend === 'egl') return 'EGL_INITIALIZATION_FAILED';
  if (/^(WEBGL2_REQUIRED|GPU_IDENTITY_UNAVAILABLE|SOFTWARE_RENDERER_REJECTED|NVIDIA_RENDERER_REQUIRED|RTX4080S_REQUIRED|ACTUAL_PIXEL_DRAW_FAILED|MAX_.*_INSUFFICIENT|TEXTURE_UNITS_INSUFFICIENT|MSAA_COVERAGE_CAPABILITY_INSUFFICIENT|BROWSER_PAGE_ERROR|BROWSER_CONSOLE_ERROR|PNG_FORMAT_INVALID|RENDERER_IDENTITY_CHANGED|RENDER_FACTORY_MISMATCH)$/.test(message)) return message;
  return ({BROWSER_LAUNCH: 'CHROMIUM_LAUNCH_FAILED', PAGE_CREATE: 'BROWSER_PAGE_CREATE_FAILED', PAGE_LOAD: 'BROWSER_PAGE_LOAD_FAILED', WEBGL2_CREATE: 'WEBGL2_EVALUATION_FAILED', GPU_IDENTITY: 'GPU_IDENTITY_EVALUATION_FAILED', READPIXELS: 'READPIXELS_EVALUATION_FAILED', SOURCE: 'FROZEN_SOURCE_FAILED', PROOF_FRAME: 'STATIC_PROOF_RENDER_FAILED'})[stage] || 'WORKER_INITIALIZATION_FAILED';
}
export function createDiagnostic(backend, context = {}) {
  const began = Date.now();
  const diagnostic = {schema_version: 2, backend, ...context, stages: stages.map(name => ({name, result: 'NOT_RUN'})),
    capability_result: {result: 'FAIL', failures: []}, peak_memory: 'UNKNOWN', gpu_visual_quality: 'NOT_RUN', frame_count: 0};
  const set = (name, result, evidence) => {
    const row = diagnostic.stages.find(row => row.name === name);
    if (row) Object.assign(row, {result, elapsed_seconds: (Date.now() - began) / 1000}, evidence ? {evidence} : {});
  };
  return {diagnostic, set};
}
