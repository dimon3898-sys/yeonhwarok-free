"""Bootstrap preservation and scope boundaries; no render or provider call."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import os
import shutil
import time
import unittest
from unittest.mock import Mock, patch

from deployment.gcube.start import (BootError, configure_image_paths, integer_option,
                                     link_image_path, seed_audio)
from deployment.gcube import start


class BootstrapTests(unittest.TestCase):
    def test_initial_limit_is20_and_invalid_values_cannot_expand_it_accidentally(self):
        self.assertEqual(integer_option({}, 'WORLD_ENGINE_MAX_DURATION', 20, 5, 180), 20)
        for value in ('NaN', '20.0', '-1', '181', '20;echo'):
            with self.subTest(value=value), self.assertRaises(BootError):
                integer_option({'WORLD_ENGINE_MAX_DURATION': value}, 'WORLD_ENGINE_MAX_DURATION', 20, 5, 180)

    def test_library_copy_is_repeatable_but_conflicts_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);source = root/'src';destination = root/'dst'
            source.mkdir();(source/'pulse.wav').write_bytes(b'approved-original')
            seed_audio(source,destination);seed_audio(source,destination)
            (destination/'pulse.wav').write_bytes(b'prior-user-file')
            with self.assertRaisesRegex(BootError,'PERSISTED_AUDIO_CONFLICT'):
                seed_audio(source,destination)
            self.assertEqual((destination/'pulse.wav').read_bytes(),b'prior-user-file')

    def test_library_parent_symlink_cannot_write_outside_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'src';destination=root/'dst';outside=root/'other'
            (source/'sfx').mkdir(parents=True);destination.mkdir();outside.mkdir()
            (source/'sfx/pulse.wav').write_bytes(b'approved')
            (destination/'sfx').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(BootError,'UNSAFE_PERSISTED_AUDIO'):
                seed_audio(source,destination)
            self.assertFalse((outside/'pulse.wav').exists())

    def test_writable_link_never_deletes_nonempty_prior_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'cache';target=root/'persisted'
            source.mkdir();target.mkdir();(source/'old.mp4').write_bytes(b'keep')
            with self.assertRaisesRegex(BootError,'IMAGE_WRITABLE_PATH_NOT_EMPTY'):
                link_image_path(source,target)
            self.assertEqual((source/'old.mp4').read_bytes(),b'keep')

    def test_namespace_and_audio_links_are_separate_from_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'image';cache=root/'persisted-cache';audio=root/'persisted-audio'
            (app/'cache').mkdir(parents=True);(app/'assets/audio').mkdir(parents=True)
            (app/'assets/audio/license.json').write_bytes(b'approved');cache.mkdir();audio.mkdir()
            storage=SimpleNamespace(cache_root=cache,audio_root=audio,
                                    uid=os.getuid(),gid=os.getgid())
            with self.assertRaisesRegex(BootError,'INVALID_RENDER_PROFILE'):
                configure_image_paths(app,storage,'gpu-'+('../'*21)+'x')
            namespace='gpu-'+'a'*64
            selected=configure_image_paths(app,storage,namespace)
            self.assertEqual((app/'cache').resolve(),selected.resolve())
            self.assertEqual((app/'assets/audio').resolve(),audio)
            self.assertEqual((app/'assets/image_audio_seed/license.json').read_bytes(),b'approved')
            self.assertFalse((audio/'license.json').exists())
            seed_audio(app/'assets/image_audio_seed', audio)
            self.assertEqual((audio/'license.json').read_bytes(),b'approved')

    def test_persisted_namespace_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=root/'image';cache=root/'cache';audio=root/'audio';outside=root/'outside'
            app.mkdir();cache.mkdir();audio.mkdir();outside.mkdir()
            namespace='gpu-'+'b'*64
            (cache/namespace).symlink_to(outside,target_is_directory=True)
            before=outside.stat()
            with self.assertRaisesRegex(BootError,'UNSAFE_PERSISTED_CACHE'):
                configure_image_paths(app,SimpleNamespace(cache_root=cache,audio_root=audio),namespace)
            self.assertEqual(outside.stat().st_uid,before.st_uid)
            self.assertFalse((app/'cache').exists())

    def test_preflight_failure_keeps_a_read_only_foreground_status(self):
        for code in ('GPU_HARDWARE_UNAVAILABLE', 'WORLD_ENGINE_OWNER_CODE_REQUIRED',
                     'STORAGE_MOUNT_REQUIRED'):
            with self.subTest(code=code):
                listener = Mock()
                listener.start.return_value = listener
                listener.error_code = code
                stopping = Mock()
                stopping.is_set.return_value = False
                # A successful wait models an external SIGTERM, not a retry.
                stopping.wait.return_value = True
                with patch('deployment.gcube.boot_status.BootStatusServer', return_value=listener), \
                     patch.object(start, 'run_engine', side_effect=BootError(code)) as engine, \
                     patch.object(start.threading, 'Event', return_value=stopping), \
                     patch.object(start.signal, 'signal'), patch('builtins.print'):
                    self.assertEqual(start.main(), 0)
                self.assertEqual(listener.start.call_count, 2)
                listener.set_phase.assert_called_once_with('blocked', error_code=code)
                stopping.wait.assert_called_once_with(1)
                engine.assert_called_once_with(listener, stopping)
                listener.close.assert_called_once()

    def test_unexpected_engine_exit_is_visible_and_does_not_retry_render(self):
        listener = Mock()
        listener.start.return_value = listener
        listener.error_code = 'WORLD_ENGINE_PROCESS_EXITED'
        stopping = Mock()
        stopping.is_set.return_value = False
        stopping.wait.return_value = True
        with patch('deployment.gcube.boot_status.BootStatusServer', return_value=listener), \
             patch.object(start, 'run_engine', return_value=2) as engine, \
             patch.object(start.threading, 'Event', return_value=stopping), \
             patch.object(start.signal, 'signal'), patch('builtins.print'):
            self.assertEqual(start.main(), 0)
        listener.set_phase.assert_called_once_with('blocked', error_code='WORLD_ENGINE_PROCESS_EXITED')
        self.assertEqual(engine.call_count, 1)

    def test_gpu_exception_delivers_diagnostics_without_retry_or_raw_exception_log(self):
        listener = Mock()
        listener.start.return_value = listener
        listener.error_code = 'GPU_WEBGL_UNVERIFIED'
        listener.gpu_diagnostics = {'failed_stage': 'E', 'gpu_profile': 'egl'}
        stopping = Mock()
        stopping.is_set.return_value = False
        stopping.wait.return_value = True
        error = BootError('GPU_WEBGL_UNVERIFIED')
        error.diagnostics = {'failed_stage': 'E', 'gpu_profile': 'egl',
                             'raw_stderr': 'private-stderr-secret'}
        with patch('deployment.gcube.boot_status.BootStatusServer', return_value=listener), \
             patch.object(start, 'run_engine', side_effect=error) as engine, \
             patch.object(start.threading, 'Event', return_value=stopping), \
             patch.object(start.signal, 'signal'), patch('builtins.print') as logger:
            self.assertEqual(start.main(), 0)
        listener.set_phase.assert_called_once_with('blocked', error_code=error.code,
                                                   gpu_diagnostics=error.diagnostics)
        engine.assert_called_once_with(listener, stopping)
        self.assertNotIn('private-stderr-secret', str(logger.call_args_list))
        self.assertIn('failed_stage', str(logger.call_args_list))
        listener.close.assert_called_once()

    def test_timed_out_browser_probe_kills_only_its_created_process_group(self):
        process = Mock()
        process.pid = 123456
        process.returncode = -9
        process.communicate.side_effect = [subprocess.TimeoutExpired(['node', 'gpu_probe.mjs'], 60),
                                           ('', '')]
        process.__enter__ = Mock(return_value=process)
        process.__exit__ = Mock(return_value=False)
        with patch.object(start.subprocess, 'Popen', return_value=process) as launch, \
             patch.object(start.os, 'killpg') as terminate_group:
            with self.assertRaises(subprocess.TimeoutExpired):
                start.run_graphics_probe(['node', 'gpu_probe.mjs'], capture_output=True,
                                         text=True, timeout=60, check=False,
                                         user=1000, group=1000, extra_groups=[44, 109])
        terminate_group.assert_called_once_with(process.pid, start.signal.SIGKILL)
        opts = launch.call_args.kwargs
        self.assertTrue(opts['start_new_session'])
        self.assertEqual(opts['user'], 1000)
        self.assertEqual(opts['extra_groups'], [44, 109])
        self.assertNotIn('timeout', opts)
        self.assertNotIn('check', opts)

    def test_nvidia_query_keeps_the_existing_bounded_runner(self):
        result = subprocess.CompletedProcess(['nvidia-smi'], 0, 'observed', '')
        with patch.object(start.subprocess, 'run', return_value=result) as run, \
             patch.object(start.subprocess, 'Popen') as launch:
            observed = start.run_graphics_probe(['nvidia-smi'], capture_output=True,
                                                text=True, timeout=10, check=False)
        self.assertIs(observed, result)
        run.assert_called_once_with(['nvidia-smi'], capture_output=True, text=True, timeout=10,
                                    check=False)
        launch.assert_not_called()

    @unittest.skipUnless(os.name == 'posix' and shutil.which('node') and Path('/proc').is_dir(),
                         'Requires local Node and Linux process inspection')
    def test_actual_timed_out_probe_leaves_no_running_child(self):
        script = ("const{spawn}=require('node:child_process');"
                  "const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],"
                  "{stdio:'ignore'});console.log(child.pid);setInterval(()=>{},1000)")
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            start.run_graphics_probe(['node', '-e', script], capture_output=True,
                                     text=True, timeout=.5, check=False)
        output = caught.exception.output
        if isinstance(output, bytes):
            output = output.decode()
        pid = int(output.strip())
        state_path = Path('/proc') / str(pid) / 'stat'
        # An orphan already killed with SIGKILL can briefly await init's reaping.
        # A zombie has no CPU/GPU execution and is acceptable during that wait.
        deadline = time.monotonic() + 2
        while state_path.exists() and time.monotonic() < deadline:
            try:
                if state_path.read_text().split(') ', 1)[1][0] == 'Z':
                    return
            except FileNotFoundError:
                return
            time.sleep(.02)
        self.assertFalse(state_path.exists(), 'Timed-out private browser child is still running')

    def test_nvidia_loader_selectors_reach_only_the_explicit_probe_and_child_env(self):
        env = {'WORLD_ENGINE_RENDER_MODE': 'gpu-required', 'WORLD_ENGINE_OWNER_CODE': 'private-secret'}
        before = dict(os.environ)
        facts = {'hardware_verification_performed': False, 'status': 'prepared'}
        updates = {'__EGL_VENDOR_LIBRARY_FILENAMES': '/run/world-engine/nvidia-graphics-test/10_nvidia.json',
                   'VK_DRIVER_FILES': '/run/world-engine/nvidia-graphics-test/nvidia_icd.json',
                   'VK_ICD_FILENAMES': '/run/world-engine/nvidia-graphics-test/nvidia_icd.json',
                   'WORLD_ENGINE_RENDER_MODE': 'cpu', 'WORLD_ENGINE_OWNER_CODE': 'changed-secret'}
        with patch('deployment.gcube.graphics_runtime.prepare_graphics_runtime',
                   return_value=(updates, facts)) as prepare:
            observed = start.prepare_gpu_environment(env)
        self.assertIs(observed, facts)
        self.assertEqual(env['WORLD_ENGINE_RENDER_MODE'], 'gpu-required')
        self.assertEqual(env['WORLD_ENGINE_OWNER_CODE'], 'private-secret')
        self.assertEqual(env['VK_DRIVER_FILES'], updates['VK_DRIVER_FILES'])
        self.assertEqual(env['__EGL_VENDOR_LIBRARY_FILENAMES'], updates['__EGL_VENDOR_LIBRARY_FILENAMES'])
        self.assertEqual(dict(os.environ), before)
        prepare.assert_called_once_with(env)

    def test_graphics_runtime_path_errors_remain_blocked_and_have_a_fixed_failed_stage(self):
        from deployment.gcube.graphics_runtime import GraphicsRuntimeError
        for code in ('GPU_GRAPHICS_RUNTIME_PATH_UNSAFE', 'GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE',
                     'raw-private-filesystem-error'):
            with self.subTest(code=code), \
                 patch('deployment.gcube.graphics_runtime.prepare_graphics_runtime',
                       side_effect=GraphicsRuntimeError(code)), \
                 self.assertRaises(BootError) as caught:
                start.prepare_gpu_environment({'WORLD_ENGINE_RENDER_MODE': 'gpu-required'})
            expected = code if code.startswith('GPU_GRAPHICS_RUNTIME_') else 'GPU_BROWSER_PROBE_FAILED'
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(caught.exception.diagnostics['failed_stage'], 'C')
            self.assertNotIn('raw-private-filesystem-error', str(caught.exception.diagnostics))

    def test_requested_stop_closes_listener_without_a_false_boot_failure(self):
        listener = Mock()
        listener.start.return_value = listener
        stopping = Mock()
        stopping.is_set.return_value = True
        with patch('deployment.gcube.boot_status.BootStatusServer', return_value=listener), \
             patch.object(start, 'run_engine', return_value=0), \
             patch.object(start.threading, 'Event', return_value=stopping), \
             patch.object(start.signal, 'signal'):
            self.assertEqual(start.main(), 0)
        listener.set_phase.assert_not_called()
        stopping.wait.assert_not_called()
        listener.close.assert_called_once()

    def test_fixed_image_links_use_only_the_writable_runtime_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);app = root/'image';runtime = root/'run'
            cache = root/'saved-cache';audio = root/'saved-audio'
            (app/'assets/image_audio_seed').mkdir(parents=True)
            (app/'assets/image_audio_seed/pulse.wav').write_bytes(b'approved')
            runtime.mkdir(mode=0o700);cache.mkdir();audio.mkdir()
            (app/'cache').symlink_to(runtime/'cache')
            (app/'assets/audio').symlink_to(runtime/'audio')
            storage = SimpleNamespace(cache_root=cache,audio_root=audio,
                                      uid=os.geteuid(),gid=os.getegid())
            old = 'cpu-'+'a'*64;new = 'gpu-'+'b'*64
            configure_image_paths(app,storage,old,link_root=runtime)
            (cache/old/'prior.mp4').write_bytes(b'keep')
            configure_image_paths(app,storage,new,link_root=runtime)
            configure_image_paths(app,storage,new,link_root=runtime)
            self.assertEqual((app/'cache').resolve(),cache/new)
            self.assertEqual((cache/old/'prior.mp4').read_bytes(),b'keep')
            self.assertEqual(os.readlink(app/'cache'),str(runtime/'cache'))
            self.assertEqual(os.readlink(app/'assets/audio'),str(runtime/'audio'))
            self.assertEqual((app/'assets/image_audio_seed/pulse.wav').read_bytes(),b'approved')

    def test_fixed_runtime_link_rejects_a_foreign_target_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);app = root/'image';runtime = root/'run'
            cache = root/'saved-cache';audio = root/'saved-audio';outside = root/'other'
            app.mkdir();runtime.mkdir(mode=0o700);cache.mkdir();audio.mkdir();outside.mkdir()
            (app/'cache').symlink_to(runtime/'cache')
            (runtime/'cache').symlink_to(outside)
            with self.assertRaisesRegex(BootError,'IMAGE_WRITABLE_PATH_CONFLICT'):
                configure_image_paths(app,SimpleNamespace(cache_root=cache,audio_root=audio,
                                                         uid=os.getuid(),gid=os.getgid()),
                                      'cpu-'+'a'*64,link_root=runtime)
            self.assertEqual((runtime/'cache').resolve(),outside)


if __name__=='__main__':
    unittest.main()
