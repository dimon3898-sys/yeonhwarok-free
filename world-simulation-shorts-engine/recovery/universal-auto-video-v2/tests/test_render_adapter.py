"""Focused CPU allocation/control mocks; never an NVIDIA execution result."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import stat
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import render_adapter as adapter
from cache import PrivateTree


def test_temp_parent():
    for candidate in (Path(tempfile.gettempdir()), Path('/workspace')):
        if not candidate.is_dir() or candidate.is_symlink() or not os.access(candidate, os.W_OK):
            continue
        info = candidate.stat()
        root_sticky = info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if info.st_uid in {0, os.geteuid()} and (not info.st_mode & 0o022 or root_sticky):
            return candidate
    raise unittest.SkipTest('BLOCKED: no safe writable test temporary parent')


class RenderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=test_temp_parent())
        self.root = Path(self.temp.name)
        self.allocation = {'uuid': 'GPU-1111', 'model': 'RTX 4080 SUPER', 'driver_version': '1.2',
            'memory_total_mib': 16384, 'memory_free_mib': 15000}
        self.admission = types.SimpleNamespace(test_only=False,
            safe_report={'gpuRenderingVerified': True, 'vramBudgetBytes': 8192 * 1024**2},
            private_report={'allocation': self.allocation}, environ={'SAFE_TEST_FLAG': '1'})
        self.config = types.SimpleNamespace(render_timeout_seconds=10)
        self.gpu = types.SimpleNamespace(ENGINE_ROOT=self.root, MIB=1024**2,
            RESERVED_MEMORY_BYTES=2048 * 1024**2, query_allocation=mock.Mock(return_value=deepcopy(self.allocation)),
            _stop_render=mock.Mock())

    def tearDown(self):
        self.temp.cleanup()

    def run_native(self, process, **kwargs):
        with mock.patch.object(adapter.subprocess, 'Popen', return_value=process):
            return adapter._run_native_capture(self.gpu, self.admission, self.config,
                ['node', 'fixed-native-capture.mjs'], {'SAFE_TEST_FLAG': '1'}, self.root / 'native.log', **kwargs)

    def test_test_only_admission_refused_before_any_process(self):
        self.admission.test_only = True
        with mock.patch.object(adapter.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(adapter.RenderError, 'TEST_ADMISSION_NOT_EXECUTABLE'):
                self.run_native(mock.Mock())
            spawn.assert_not_called()

    def test_success_keeps_fixed_command_new_session_and_env(self):
        process = mock.Mock(returncode=0)
        process.poll.side_effect = [0, 0]
        with mock.patch.object(adapter.subprocess, 'Popen', return_value=process) as spawn:
            adapter._run_native_capture(self.gpu, self.admission, self.config,
                ['node', 'fixed-native-capture.mjs'], {'SAFE_TEST_FLAG': '1'}, self.root / 'native.log')
        self.assertEqual(spawn.call_args.args[0], ['node', 'fixed-native-capture.mjs'])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        self.assertTrue(spawn.call_args.kwargs['close_fds'])
        self.assertEqual(spawn.call_args.kwargs['stdin'], adapter.subprocess.DEVNULL)
        self.gpu._stop_render.assert_not_called()

    def test_allocation_change_stops_native_child(self):
        changed = deepcopy(self.allocation)
        changed['uuid'] = 'GPU-2222'
        self.gpu.query_allocation.return_value = changed
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        with self.assertRaisesRegex(adapter.RenderError, 'GPU_ALLOCATION_CHANGED_DURING_RENDER'):
            self.run_native(process)
        self.gpu._stop_render.assert_called_once_with(process)

    def test_vram_growth_or_reserved_floor_stops_native_child(self):
        changed = deepcopy(self.allocation)
        changed['memory_free_mib'] = 1000
        self.gpu.query_allocation.return_value = changed
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        with self.assertRaisesRegex(adapter.RenderError, 'GPU_RENDER_VRAM_BUDGET_EXCEEDED'):
            self.run_native(process)
        self.gpu._stop_render.assert_called_once_with(process)

    def test_failed_exit_is_not_a_segment_success(self):
        process = mock.Mock(returncode=2)
        process.poll.return_value = 2
        with self.assertRaisesRegex(adapter.RenderError, 'GPU_RENDER_PROCESS_FAILED'):
            self.run_native(process)

    def test_deadline_stops_child_without_retry(self):
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        with mock.patch.object(adapter.time, 'monotonic', side_effect=[100, 111]):
            with self.assertRaisesRegex(adapter.RenderError, 'GPU_RENDER_DEADLINE_EXCEEDED'):
                self.run_native(process)
        self.gpu._stop_render.assert_called_once_with(process)

    def test_interruption_stops_child(self):
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        self.gpu.query_allocation.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_native(process)
        self.gpu._stop_render.assert_called_once_with(process)

    def test_normal_mode_gpu_required_and_engine_account(self):
        with mock.patch.dict(os.environ, {'WORLD_ENGINE_STARTUP_MODE': 'diagnostic', 'WORLD_ENGINE_RENDER_MODE': 'gpu-required'}):
            with self.assertRaisesRegex(adapter.RenderError, 'EXPLICIT_NORMAL_GPU_REQUIRED_MODE_REQUIRED'):
                adapter._normal_mode()
        with mock.patch.object(adapter.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(adapter.RenderError, 'ENGINE_UID_GID_1000_REQUIRED'):
                adapter._normal_mode()

    def test_generated_artifact_copy_hashes_original_and_destination(self):
        source_path, destination_path = self.root / 'source', self.root / 'destination'
        with PrivateTree(source_path, create=True) as source, PrivateTree(destination_path, create=True) as destination:
            descriptor = os.open('evidence.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=source.fd)
            os.write(descriptor, b'TEST_ONLY_CPU_ARTIFACT')
            os.close(descriptor)
            expected = source.hash_file('evidence.json')
            self.assertEqual(adapter._copy_artifact(source, 'evidence.json', destination), expected)
            self.assertEqual(destination.hash_file('evidence.json'), expected)

    def test_unprepared_job_refuses_before_native_gpu(self):
        with mock.patch.object(adapter, '_normal_mode'), mock.patch.object(adapter, '_image_binding'), mock.patch.object(adapter, '_SESSION', None), mock.patch.object(adapter, 'native_gpu') as native:
            with self.assertRaisesRegex(adapter.RenderError, 'JOB_INPUT_PREPARATION_REQUIRED'):
                adapter.render_segment({}, {}, self.root, approval={})
            native.assert_not_called()

    def test_configured_image_binding_matches_exact_approved_plan(self):
        digest = 'sha256:' + 'a' * 64
        plan = {'renderProfile': {'imageDigest': digest}}
        with mock.patch.dict(os.environ, {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': digest}):
            self.assertEqual(adapter._image_binding(plan), digest)
        for configured in ('', 'latest', 'sha256:' + 'b' * 64):
            with mock.patch.dict(os.environ, {'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': configured}):
                with self.assertRaisesRegex(adapter.RenderError, 'CONFIGURED_IMMUTABLE_IMAGE_BINDING_MISMATCH'):
                    adapter._image_binding(plan)

    def test_original_common_kernel_lease_excludes_legacy_capture(self):
        path = ROOT.parent / 'rtx-gpu-package-v1/gpu_launcher.py'
        spec = importlib.util.spec_from_file_location('_universal_test_original_gpu', path)
        original = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = original
        spec.loader.exec_module(original)
        native = types.SimpleNamespace(gpu=lambda: original)
        with mock.patch.object(adapter, 'native_gpu', return_value=native), \
                mock.patch.object(adapter.storage, 'PRIVATE_BASE', self.root), \
                mock.patch.dict(os.environ, {'WORLD_ENGINE_STARTUP_MODE': 'normal', 'WORLD_ENGINE_RENDER_MODE': 'gpu-required'}):
            with original.capture_guard(self.root):
                with self.assertRaisesRegex(original.LauncherError, 'GPU_CAPTURE_ALREADY_RUNNING'):
                    with adapter.common_gpu_lease():
                        self.fail('legacy and new job used the same physical GPU concurrently')
            with adapter.common_gpu_lease():
                pass


if __name__ == '__main__':
    unittest.main()
