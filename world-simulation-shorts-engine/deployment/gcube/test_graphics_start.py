"""Synthetic startup admission tests; these are not GPU compatibility results."""
import unittest
from unittest.mock import patch

from deployment.gcube.gpu import GPUError
from deployment.gcube.graphics_start import select_graphics_profile


def report(profile='egl', mode='gpu-required'):
    cpu = mode == 'cpu'
    return {
        'schema_version': 1,
        'render_mode': mode,
        'gpu_profile': profile,
        'gpu_rendering_verified': not cpu,
        'hardware_status': 'unavailable' if cpu else 'visible',
        'nvidia_devices': [] if cpu else [{'name': 'NVIDIA GeForce RTX 5070'}],
        'browser_version': '151.0.0.0',
        'webgl': {
            'context_available': True, 'context_version': 2,
            'draw_passed': True, 'webgl_error': 0,
            'debug_renderer_available': True,
            'renderer': 'ANGLE (Google, SwiftShader)' if cpu else 'ANGLE (NVIDIA, RTX 5070)',
            'vendor': 'Google Inc.' if cpu else 'NVIDIA Corporation',
        },
        'cache_namespace': 'preserved-probe-namespace',
    }


class ProfileSelection(unittest.TestCase):
    def test_default_egl_success_preserves_report_runner_and_private_environment(self):
        source_report = report()
        source_env = {'PRIVATE_TOKEN': 'private-value', 'PATH': '/usr/bin'}
        original_env = dict(source_env)
        calls, runner = [], object()
        def probe(**kwargs):
            calls.append(kwargs)
            return source_report
        selected = select_graphics_profile(source_env, runner=runner, probe=probe)
        self.assertEqual(source_env, original_env)
        self.assertIs(calls[0]['runner'], runner)
        self.assertEqual(calls[0]['environ'], {**source_env, 'WORLD_ENGINE_GPU_PROFILE': 'egl'})
        self.assertIsNot(calls[0]['environ'], source_env)
        self.assertEqual({key: selected[key] for key in source_report}, source_report)
        self.assertNotIn('safe_profile_attempts', source_report)
        self.assertEqual(selected['safe_profile_attempts'], [{'profile': 'egl', 'status': 'verified'}])
        self.assertNotIn('PRIVATE_TOKEN', str(selected['safe_profile_attempts']))
        self.assertNotIn('private-value', str(selected['safe_profile_attempts']))

    def test_each_retryable_error_can_select_vulkan_without_mutating_base_environment(self):
        for code in ('GPU_BROWSER_PROBE_FAILED', 'GPU_WEBGL_UNVERIFIED'):
            with self.subTest(code=code):
                calls, source_env = [], {'PATH': '/usr/bin'}
                def probe(**kwargs):
                    attempt = kwargs['environ']
                    calls.append(dict(attempt))
                    if len(calls) == 1:
                        attempt['PRIVATE_TOKEN'] = 'mutation-must-not-propagate'
                        raise GPUError(code)
                    return report('vulkan')
                selected = select_graphics_profile(source_env, probe=probe)
                self.assertEqual(calls, [
                    {'PATH': '/usr/bin', 'WORLD_ENGINE_GPU_PROFILE': 'egl'},
                    {'PATH': '/usr/bin', 'WORLD_ENGINE_GPU_PROFILE': 'vulkan'},
                ])
                self.assertEqual(source_env, {'PATH': '/usr/bin'})
                self.assertEqual(selected['gpu_profile'], 'vulkan')
                self.assertEqual(selected['safe_profile_attempts'], [
                    {'profile': 'egl', 'status': 'failed', 'error_code': code},
                    {'profile': 'vulkan', 'status': 'verified'},
                ])

    def test_both_failures_raise_original_fixed_error_with_only_two_attempts(self):
        first = GPUError('GPU_BROWSER_PROBE_FAILED')
        for second_code in ('GPU_WEBGL_UNVERIFIED', 'GPU_HARDWARE_UNAVAILABLE'):
            with self.subTest(second_code=second_code):
                calls = []
                def probe(**kwargs):
                    calls.append(kwargs['environ']['WORLD_ENGINE_GPU_PROFILE'])
                    raise first if len(calls) == 1 else GPUError(second_code)
                with self.assertRaises(GPUError) as raised:
                    select_graphics_profile({}, probe=probe)
                self.assertIs(raised.exception, first)
                self.assertEqual(calls, ['egl', 'vulkan'])

    def test_hardware_wrapper_configuration_and_cpu_errors_do_not_retry(self):
        for code in ('GPU_HARDWARE_UNAVAILABLE', 'GPU_WRAPPER_NOT_EXECUTABLE',
                     'GPU_BROWSER_UNAVAILABLE', 'GPU_PROFILE_INVALID', 'CPU_FALLBACK_UNVERIFIED'):
            with self.subTest(code=code):
                calls = []
                def probe(**kwargs):
                    calls.append(kwargs)
                    raise GPUError(code)
                with self.assertRaisesRegex(GPUError, code):
                    select_graphics_profile({}, probe=probe)
                self.assertEqual(len(calls), 1)

    def test_explicit_profile_is_honored_with_one_attempt(self):
        for profile in ('egl', 'vulkan'):
            for fails in (False, True):
                with self.subTest(profile=profile, fails=fails):
                    calls = []
                    def probe(**kwargs):
                        calls.append(kwargs['environ']['WORLD_ENGINE_GPU_PROFILE'])
                        if fails:
                            raise GPUError('GPU_WEBGL_UNVERIFIED')
                        return report(profile)
                    env = {'WORLD_ENGINE_GPU_PROFILE': profile}
                    if fails:
                        with self.assertRaisesRegex(GPUError, 'GPU_WEBGL_UNVERIFIED'):
                            select_graphics_profile(env, probe=probe)
                    else:
                        self.assertEqual(select_graphics_profile(env, probe=probe)['gpu_profile'], profile)
                    self.assertEqual(calls, [profile])

    def test_explicit_cpu_uses_one_probe_and_never_claims_gpu_success(self):
        calls = []
        def probe(**kwargs):
            calls.append(kwargs)
            return report(mode='cpu')
        selected = select_graphics_profile({'WORLD_ENGINE_RENDER_MODE': 'cpu'}, probe=probe)
        self.assertFalse(selected['gpu_rendering_verified'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['environ']['WORLD_ENGINE_GPU_PROFILE'], 'egl')

    def test_invalid_explicit_configuration_fails_before_probe(self):
        for env in ({'WORLD_ENGINE_RENDER_MODE': 'auto'}, {'WORLD_ENGINE_GPU_PROFILE': ''},
                    {'WORLD_ENGINE_GPU_PROFILE': 'cuda'}):
            with self.subTest(env=env):
                with patch('deployment.gcube.graphics_start.probe_gpu_runtime') as probe:
                    with self.assertRaisesRegex(GPUError, 'GPU_PROFILE_INVALID'):
                        select_graphics_profile(env)
                    probe.assert_not_called()

    def test_mismatched_reports_and_false_or_nonboolean_gpu_verification_cannot_pass(self):
        for field, value in (('render_mode', 'cpu'), ('gpu_profile', 'wrong-profile'),
                             ('gpu_rendering_verified', False), ('gpu_rendering_verified', 1),
                             ('hardware_status', 'unavailable'), ('nvidia_devices', []),
                             ('nvidia_devices', ['not-a-device-record'])):
            with self.subTest(field=field, value=value):
                calls = []
                def probe(**kwargs):
                    calls.append(kwargs)
                    result = report(kwargs['environ']['WORLD_ENGINE_GPU_PROFILE'])
                    result[field] = value
                    return result
                with self.assertRaisesRegex(GPUError, 'GPU_WEBGL_UNVERIFIED'):
                    select_graphics_profile({}, probe=probe)
                self.assertEqual(len(calls), 2)

    def test_claimed_gpu_success_rechecks_actual_webgl_identity_and_draw(self):
        for field, value in (('renderer', 'ANGLE (Google, SwiftShader)'),
                             ('renderer', 'llvmpipe'), ('draw_passed', False),
                             ('webgl_error', 1282), ('context_version', 1),
                             ('debug_renderer_available', False)):
            with self.subTest(field=field, value=value):
                def probe(**kwargs):
                    result = report(kwargs['environ']['WORLD_ENGINE_GPU_PROFILE'])
                    result['webgl'][field] = value
                    return result
                with self.assertRaisesRegex(GPUError, 'GPU_WEBGL_UNVERIFIED'):
                    select_graphics_profile({}, probe=probe)

    def test_bad_cpu_report_is_rejected_without_retry_or_switching_modes(self):
        for field, value in (('render_mode', 'gpu-required'), ('gpu_profile', 'vulkan'),
                             ('gpu_rendering_verified', True), ('gpu_rendering_verified', 0)):
            with self.subTest(field=field, value=value):
                calls = []
                def probe(**kwargs):
                    calls.append(kwargs)
                    result = report(mode='cpu')
                    result[field] = value
                    return result
                with self.assertRaisesRegex(GPUError, 'CPU_FALLBACK_UNVERIFIED'):
                    select_graphics_profile({'WORLD_ENGINE_RENDER_MODE': 'cpu'}, probe=probe)
                self.assertEqual(len(calls), 1)

    def test_unexpected_exception_is_not_retried_or_reported_as_gpu_success(self):
        with patch('deployment.gcube.graphics_start.probe_gpu_runtime', side_effect=RuntimeError('fixed failure')) as probe:
            with self.assertRaisesRegex(RuntimeError, 'fixed failure'):
                select_graphics_profile({})
            self.assertEqual(probe.call_count, 1)

    def test_default_probe_calls_existing_runtime_probe_with_selected_environment(self):
        with patch('deployment.gcube.graphics_start.probe_gpu_runtime', return_value=report()) as probe:
            selected = select_graphics_profile({})
            probe.assert_called_once_with(environ={'WORLD_ENGINE_GPU_PROFILE': 'egl'}, runner=None)
        self.assertTrue(selected['gpu_rendering_verified'])


if __name__ == '__main__':
    unittest.main()
