"""GPU argument selection tests do not claim a physical NVIDIA browser pass."""
import unittest

from deployment.gcube.chromium_wrapper import BrowserProfileError, browser_arguments


class HardwareBrowserArguments(unittest.TestCase):
    def test_egl_keeps_headless_transport_but_removes_hardware_blockers(self):
        arguments = ['--headless', '--remote-debugging-pipe', '--no-sandbox',
                     '--disable-dev-shm-usage', '--disable-gpu', '--disable-gpu-compositing',
                     '--disable-gpu-rasterization', '--disable-webgl', '--disable-webgl2',
                     '--enable-unsafe-swiftshader', '--use-angle=swiftshader']
        result = browser_arguments(arguments, {})
        for retained in arguments[:4]:
            self.assertIn(retained, result)
        for removed in arguments[4:]:
            self.assertNotIn(removed, result)
        self.assertIn('--use-angle=gl-egl', result)
        self.assertIn('--disable-software-rasterizer', result)
        self.assertNotIn('--enable-unsafe-webgpu', result)

    def test_vulkan_merges_features_and_replaces_only_vulkan_disable(self):
        arguments = ['--no-sandbox', '--enable-features=CDPScreenshotNewSurface,FeatureA',
                     '--enable-features=FeatureA,Vulkan<OldTrial',
                     '--disable-features=Translate,Vulkan,PaintHolding',
                     '--use-vulkan', 'swiftshader', '--use-angle=swiftshader']
        result = browser_arguments(arguments, {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'})
        self.assertIn('--enable-features=CDPScreenshotNewSurface,FeatureA,Vulkan', result)
        self.assertIn('--disable-features=Translate,PaintHolding', result)
        self.assertIn('--use-angle=vulkan', result)
        self.assertIn('--use-vulkan=native', result)
        self.assertIn('--disable-vulkan-surface', result)
        self.assertEqual(sum(a.startswith('--enable-features=') for a in result), 1)
        self.assertEqual(sum(a.startswith('--use-vulkan=') for a in result), 1)
        self.assertNotIn('--enable-unsafe-webgpu', result)
        self.assertNotIn('--enable-zero-copy', result)
        self.assertNotIn('--enable-gpu-rasterization', result)

    def test_split_features_selectors_and_empty_vulkan_disable(self):
        result = browser_arguments(['--enable-features', 'Other', '--disable-features=Vulkan'],
                                   {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'})
        self.assertIn('--enable-features=Other,Vulkan', result)
        self.assertFalse(any(arg.startswith('--disable-features') for arg in result))
        for arguments in (['--enable-features'], ['--use-vulkan', '--headless']):
            with self.subTest(arguments=arguments), self.assertRaises(BrowserProfileError):
                browser_arguments(arguments, {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'})

    def test_cpu_profile_preserves_existing_cpu_flags_and_never_enables_vulkan(self):
        original = ['--headless', '--disable-gpu-compositing', '--disable-webgl',
                    '--enable-features=Other', '--disable-features=Vulkan']
        result = browser_arguments(original, {'WORLD_ENGINE_RENDER_MODE': 'cpu'})
        self.assertEqual(result[:len(original)], original)
        self.assertIn('--use-angle=swiftshader', result)
        self.assertNotIn('--enable-gpu', result)
        self.assertNotIn('--use-vulkan=native', result)


if __name__ == '__main__':
    unittest.main()
