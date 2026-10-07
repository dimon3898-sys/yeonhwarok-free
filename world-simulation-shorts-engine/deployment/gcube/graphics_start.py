"""Bounded startup profile selection; mocked tests do not certify a GPU driver.

Only an unspecified GPU profile can try Vulkan and then GL-EGL. Each attempt uses
the existing hardware/WebGL probe; CPU fallback always requires explicit mode.
The caller must carry the selected ``gpu_profile`` into the backend environment.
"""
from __future__ import annotations

from deployment.gcube.chromium_wrapper import BrowserProfileError, browser_profile
from deployment.gcube.gpu import GPUError, classify_probe, probe_gpu_runtime, sanitize_gpu_diagnostics


_RETRYABLE = frozenset({'GPU_BROWSER_PROBE_FAILED', 'GPU_WEBGL_UNVERIFIED'})


def _verified_report(report, *, mode, profile):
    """Recheck admission so a mismatched or software report cannot be selected."""
    failure = 'GPU_WEBGL_UNVERIFIED' if mode == 'gpu-required' else 'CPU_FALLBACK_UNVERIFIED'
    if (not isinstance(report, dict) or report.get('render_mode') != mode or
            report.get('gpu_profile') != profile):
        raise GPUError(failure)
    expected_verified = mode == 'gpu-required'
    if report.get('gpu_rendering_verified') is not expected_verified:
        raise GPUError(failure)
    hardware = report.get('nvidia_devices')
    if not isinstance(hardware, list):
        raise GPUError(failure)
    if expected_verified and (report.get('hardware_status') != 'visible' or not hardware or
                              not all(isinstance(device, dict) for device in hardware)):
        raise GPUError(failure)
    if classify_probe(report, hardware, mode=mode) is not expected_verified:
        raise GPUError(failure)


def select_graphics_profile(environ, *, runner=None, probe=None):
    """Return the original probe fields plus safe, bounded attempt metadata.

    Explicit profiles and CPU mode receive one attempt. An unspecified profile
    in GPU mode receives at most two attempts, on the existing bounded probe.
    If neither passes, both attempts remain in a safe diagnostic report. This
    helper neither logs subprocess output nor modifies the caller's environment.
    """
    env = dict(environ)
    try:
        mode, initial_profile = browser_profile(env)
    except BrowserProfileError as error:
        raise GPUError(str(error)) from None
    profiles = (initial_profile,)
    if mode == 'gpu-required' and 'WORLD_ENGINE_GPU_PROFILE' not in env:
        profiles = ('vulkan', 'egl')
    runtime_probe = probe_gpu_runtime if probe is None else probe
    attempts, detailed_attempts, original_error = [], [], None
    for index, profile in enumerate(profiles):
        attempt_env = dict(env)
        attempt_env['WORLD_ENGINE_GPU_PROFILE'] = profile
        try:
            report = runtime_probe(environ=attempt_env, runner=runner)
            _verified_report(report, mode=mode, profile=profile)
        except GPUError as error:
            detailed_attempts.append({'backend': profile, 'status': 'failed',
                                      'error_code': error.code, 'diagnostics': error.diagnostics})
            if index == 0 and len(profiles) == 2 and error.code in _RETRYABLE:
                original_error = error
                attempts.append({'profile': profile, 'status': 'failed', 'error_code': error.code})
                continue
            raised = original_error if original_error is not None else error
            raised.diagnostics = sanitize_gpu_diagnostics({**(raised.diagnostics or {
                'render_mode': mode, 'gpu_profile': profile, 'reason_code': raised.code}),
                'profile_attempts': detailed_attempts})
            raise raised from None
        attempts.append({'profile': profile, 'status': 'verified'})
        detailed_attempts.append({'backend': profile, 'status': 'verified',
                                  'error_code': None, 'diagnostics': report.get('diagnostics')})
        diagnostics = sanitize_gpu_diagnostics({**(report.get('diagnostics') or {
            'render_mode': mode, 'gpu_profile': profile, 'reason_code': 'VERIFIED'}),
            'profile_attempts': detailed_attempts})
        return {**report, 'safe_profile_attempts': attempts, 'diagnostics': diagnostics}
    # The bounded loop either returns an admitted report or raises a GPU error.
    raise GPUError('GPU_WEBGL_UNVERIFIED')
