// Admission only. The frozen renderer owns every visual pixel.
export function admission(capability, {softwareTest = false} = {}) {
  const failures = [];
  if (!capability.webgl2) failures.push('WEBGL2_REQUIRED');
  if (!capability.debugRendererAvailable) failures.push('GPU_IDENTITY_UNAVAILABLE');
  const name = String(capability.renderer || '');
  const software = /SwiftShader|llvmpipe|softpipe|software|lavapipe/i.test(name);
  if (!softwareTest && software) failures.push('SOFTWARE_RENDERER_REJECTED');
  if (!softwareTest && !/NVIDIA/i.test(name)) failures.push('NVIDIA_RENDERER_REQUIRED');
  if (!softwareTest && !/RTX\s*4080\s*(SUPER|S\b)/i.test(name)) failures.push('RTX4080S_REQUIRED');
  if (softwareTest && !software) failures.push('SOFTWARE_TEST_IDENTITY_REQUIRED');
  if (!capability.actualPixelDraw) failures.push('ACTUAL_PIXEL_DRAW_FAILED');
  if (capability.maxTextureSize < 8192) failures.push('MAX_TEXTURE_SIZE_INSUFFICIENT');
  if (capability.maxRenderbufferSize < 1920) failures.push('MAX_RENDERBUFFER_SIZE_INSUFFICIENT');
  if (capability.maxTextureUnits < 6) failures.push('TEXTURE_UNITS_INSUFFICIENT');
  if (capability.maxSamples < 4) failures.push('MSAA_COVERAGE_CAPABILITY_INSUFFICIENT');
  return {result: failures.length ? 'FAIL' : softwareTest ? 'SOFTWARE_TEST_ONLY' : 'PASS', failures};
}
