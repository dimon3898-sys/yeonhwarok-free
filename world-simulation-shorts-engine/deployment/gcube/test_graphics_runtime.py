"""Loader manifest repairs use synthetic drivers, never claimed NVIDIA passes."""
import ctypes
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from deployment.gcube import graphics_runtime as runtime


def fake_loader(name):
    if name == 'libEGL_nvidia.so.0':
        return SimpleNamespace(__egl_Main=object())
    if name == 'libGLX_nvidia.so.0':
        return SimpleNamespace(vk_icdGetInstanceProcAddr=object())
    raise OSError('not a known synthetic NVIDIA driver')


class GraphicsDescriptors(unittest.TestCase):
    def test_explicit_cpu_and_missing_nvidia_libraries_do_not_generate_files(self):
        forbidden = Mock(side_effect=AssertionError('CPU must not load NVIDIA'))
        updates, facts = runtime.prepare_graphics_runtime({'WORLD_ENGINE_RENDER_MODE': 'cpu'},
                                                         loader=forbidden)
        self.assertEqual(updates, {})
        self.assertEqual(facts['status'], 'explicit_cpu_mode')
        forbidden.assert_not_called()
        def unavailable(_name):
            raise OSError()
        updates, facts = runtime.prepare_graphics_runtime({}, loader=unavailable)
        self.assertEqual(updates, {})
        self.assertFalse(facts['egl']['nvidia_library_loadable'])
        self.assertFalse(facts['vulkan']['nvidia_library_loadable'])
        self.assertEqual(facts['descriptors_created'], [])

    def test_missing_entrypoint_is_not_a_usable_nvidia_library(self):
        updates, facts = runtime.prepare_graphics_runtime({}, loader=lambda _: object())
        self.assertEqual(updates, {})
        self.assertFalse(facts['egl']['driver_entrypoint_available'])

    def test_existing_valid_descriptors_are_unchanged(self):
        updates, facts = runtime.prepare_graphics_runtime({}, loader=fake_loader,
                                                         descriptor_checker=lambda *_: True)
        self.assertEqual(updates, {})
        self.assertTrue(facts['egl']['usable_vendor_descriptor_present'])
        self.assertEqual(facts['descriptors_created'], [])

    def test_missing_descriptors_are_generated_only_from_loadable_driver(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            updates, facts = runtime.prepare_graphics_runtime(
                {}, loader=fake_loader, runtime_directory=parent,
                descriptor_checker=lambda *_: False, vulkan_version_reader=lambda _: '1.3.280')
            self.assertEqual(set(updates), {'__EGL_VENDOR_LIBRARY_FILENAMES', 'VK_DRIVER_FILES',
                                           'VK_ICD_FILENAMES'})
            egl_path = Path(updates['__EGL_VENDOR_LIBRARY_FILENAMES'])
            vulkan_path = Path(updates['VK_DRIVER_FILES'])
            self.assertEqual(json.loads(egl_path.read_text())['ICD']['library_path'],
                             'libEGL_nvidia.so.0')
            self.assertEqual(json.loads(vulkan_path.read_text())['ICD']['api_version'], '1.3.280')
            self.assertEqual(stat.S_IMODE(egl_path.stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(egl_path.parent.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
            self.assertEqual(facts['descriptors_created'], ['egl', 'vulkan'])
            self.assertFalse(facts['hardware_verification_performed'])
            self.assertFalse(facts['driver_installation_performed'])

    def test_vulkan_api_query_failure_does_not_prevent_egl(self):
        def unavailable(_library):
            raise runtime.GraphicsRuntimeError('GPU_GRAPHICS_DRIVER_API_UNAVAILABLE')
        with tempfile.TemporaryDirectory() as directory:
            updates, facts = runtime.prepare_graphics_runtime(
                {}, loader=fake_loader, runtime_directory=directory,
                descriptor_checker=lambda *_: False, vulkan_version_reader=unavailable)
            self.assertIn('__EGL_VENDOR_LIBRARY_FILENAMES', updates)
            self.assertNotIn('VK_DRIVER_FILES', updates)
            self.assertEqual(facts['vulkan']['descriptor_status'], 'driver_api_query_failed')

    def test_unsafe_runtime_parent_is_rejected_without_any_path_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o755)
            with self.assertRaisesRegex(runtime.GraphicsRuntimeError,
                                        'GPU_GRAPHICS_RUNTIME_PATH_UNSAFE'):
                runtime.prepare_graphics_runtime({}, loader=fake_loader,
                    runtime_directory=path, descriptor_checker=lambda *_: False,
                    vulkan_version_reader=lambda _: '1.3.280')
            self.assertEqual(list(path.iterdir()), [])

    def test_vendor_descriptor_cannot_escape_through_dotdot_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            allowed = base / 'allowed'
            allowed.mkdir()
            outside = base / 'outside.json'
            outside.write_text(json.dumps({'file_format_version': '1.0.0',
                                          'ICD': {'library_path': 'libEGL_nvidia.so.0'}}))
            link = allowed / '10_nvidia.json'
            link.symlink_to(outside)
            with patch.dict(runtime.DESCRIPTOR_DIRECTORIES, {'egl': (allowed,)}):
                for candidate in (allowed / '..' / 'outside.json', link):
                    env = {'__EGL_VENDOR_LIBRARY_FILENAMES': str(candidate)}
                    loader = Mock(side_effect=fake_loader)
                    self.assertFalse(runtime._existing_descriptor('egl', env, loader))
                    loader.assert_not_called()

    def test_absolute_manifest_library_cannot_be_root_dlopen_from_arbitrary_path(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            arbitrary_library = base / 'libEGL_nvidia.so.0'
            arbitrary_library.touch()
            manifest = base / '10_nvidia.json'
            manifest.write_text(json.dumps({'file_format_version': '1.0.0',
                                           'ICD': {'library_path': str(arbitrary_library)}}))
            loader = Mock(side_effect=fake_loader)
            self.assertFalse(runtime._descriptor_valid(manifest, 'egl', loader))
            loader.assert_not_called()
            manifest.write_text(json.dumps({'file_format_version': '1.0.0',
                                           'ICD': {'library_path': 'libEGL_nvidia.so.0'}}))
            self.assertTrue(runtime._descriptor_valid(manifest, 'egl', loader))
            loader.assert_called_once_with('libEGL_nvidia.so.0')

    def test_actual_icd_api_version_entrypoint_result_is_used(self):
        @ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.POINTER(ctypes.c_uint32))
        def enumerate_version(pointer):
            pointer.contents.value = (1 << 22) | (3 << 12) | 280
            return 0
        class EntryPoint:
            def __call__(self, instance, name):
                self.called = (instance, name)
                return ctypes.cast(enumerate_version, ctypes.c_void_p).value
        function = EntryPoint()
        library = SimpleNamespace(vk_icdGetInstanceProcAddr=function)
        self.assertEqual(runtime._vulkan_api_version(library), '1.3.280')
        self.assertEqual(function.called, (None, b'vkEnumerateInstanceVersion'))

    def test_provider_gpu_device_selection_is_not_replaced(self):
        env = {'CUDA_VISIBLE_DEVICES': 'GPU-test', 'NVIDIA_VISIBLE_DEVICES': 'GPU-test',
               'WORLD_ENGINE_OWNER_CODE': 'do-not-report-this-secret'}
        original = dict(env)
        updates, facts = runtime.prepare_graphics_runtime(env, loader=lambda _: object())
        self.assertEqual(env, original)
        self.assertNotIn('CUDA_VISIBLE_DEVICES', updates)
        self.assertNotIn('NVIDIA_VISIBLE_DEVICES', updates)
        self.assertNotIn('do-not-report-this-secret', json.dumps(facts))

    @unittest.skipUnless(os.geteuid() == 0, 'Root-only UID 1000 descriptor read check')
    def test_root_prepared_descriptors_are_readable_after_engine_uid_drop(self):
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            outer.chmod(0o755)
            parent = outer / 'engine-runtime'
            parent.mkdir(mode=0o700)
            os.chown(parent, 1000, 1000)
            updates, _ = runtime.prepare_graphics_runtime(
                {}, loader=fake_loader, runtime_directory=parent,
                descriptor_checker=lambda *_: False, vulkan_version_reader=lambda _: '1.3.280')
            script = ('import json,sys; '
                      'assert all(json.load(open(p))["ICD"]["library_path"].endswith("nvidia.so.0") '
                      'for p in sys.argv[1:]); print("READABLE_AS_ENGINE")')
            result = subprocess.run([sys.executable, '-c', script,
                                     updates['__EGL_VENDOR_LIBRARY_FILENAMES'],
                                     updates['VK_DRIVER_FILES']],
                                    user=1000, group=1000, extra_groups=[],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'READABLE_AS_ENGINE')


if __name__ == '__main__':
    unittest.main()
