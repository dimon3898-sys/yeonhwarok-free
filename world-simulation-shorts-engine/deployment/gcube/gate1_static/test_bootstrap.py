"""Focused GPU-less bootstrap diagnostics, real subprocess and API contracts."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bootstrap
import server


class Bootstrap(unittest.TestCase):
    def test_home_xdg_actual_account_ownership(self):
        with tempfile.TemporaryDirectory() as root:
            account = type('Account', (), {'pw_dir': root + '/home', 'pw_uid': os.getuid()})
            env = bootstrap.prepare_user_environment(account, root + '/run', {'HOME': '/root'})
            self.assertEqual(env['HOME'], account.pw_dir)
            self.assertEqual(env['WORLD_ENGINE_CHROMIUM_REAL'], '/usr/bin/chromium')
            evidence = bootstrap.environment_evidence(env)
            self.assertTrue(all(row['accessible'] for row in evidence['directories'].values()))
            self.assertEqual(evidence['directories']['XDG_RUNTIME_DIR']['mode'], '0o700')

    def test_reject_symlink_user_directory(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root, 'target'); target.mkdir()
            home = Path(root, 'home'); home.symlink_to(target)
            account = type('Account', (), {'pw_dir': str(home), 'pw_uid': os.getuid()})
            with self.assertRaisesRegex(ValueError, 'SYMLINK'):
                bootstrap.prepare_user_environment(account, root + '/run', {})

    def test_reject_wrong_directory_owner(self):
        with tempfile.TemporaryDirectory() as root:
            account = type('Account', (), {'pw_dir': root, 'pw_uid': os.getuid() + 100})
            with self.assertRaisesRegex(ValueError, 'INACCESSIBLE'):
                bootstrap.prepare_user_environment(account, root + '/run', {})

    def test_secret_values_and_url_credentials_redacted(self):
        text = 'secretvalue https://alice:private@proxy.test token=another Authorization: Bearer xyz'
        value = bootstrap.redact(text, {'API_TOKEN': 'secretvalue'})
        for secret in ['secretvalue', 'private', 'another', 'xyz']:
            self.assertNotIn(secret, value)

    def test_secrets_not_forwarded_to_browser(self):
        env = bootstrap.worker_environment({'WORLD_ENGINE_OWNER_CODE': 'owner', 'API_TOKEN': 'token', 'HOME': '/home/engine', 'NVIDIA_DRIVER_CAPABILITIES': 'graphics,utility'})
        self.assertNotIn('WORLD_ENGINE_OWNER_CODE', env)
        self.assertNotIn('API_TOKEN', env)
        self.assertIn('NVIDIA_DRIVER_CAPABILITIES', env)

    def test_worker_stdout_stderr_and_exit_retained(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'worker.mjs').write_text('console.log("raw stdout"); console.error("raw stderr"); console.log(JSON.stringify({stage:"BROWSER_LAUNCH",result:"FAIL"}));process.exitCode=7;')
            events = []
            with patch.object(server, 'HERE', Path(root)):
                result = server.ProofService.child('probe', Path(root), os.environ.copy(), events.append)
            self.assertEqual(result['exit_code'], 7)
            self.assertIn('raw stdout', result['stdout'])
            self.assertIn('raw stderr', result['stderr'])
            self.assertEqual(events[0]['stage'], 'BROWSER_LAUNCH')

    def test_worker_signal_retained(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'worker.mjs').write_text('process.kill(process.pid,"SIGTERM");')
            with patch.object(server, 'HERE', Path(root)):
                result = server.ProofService.child('probe', Path(root), os.environ.copy(), lambda _: None)
            self.assertEqual(result['signal'], signal.SIGTERM)
            self.assertIsNone(result['exit_code'])

    def test_browser_capture_stdout_stderr_exit_and_flags(self):
        # No GPU or browser: executable fixture proves transport capture itself.
        with tempfile.TemporaryDirectory() as root:
            for name in ['browser_capture.py', 'bootstrap.py']:
                shutil.copyfile(HERE / name, Path(root, name))
            shutil.copyfile(HERE.parent / 'chromium_wrapper.py', Path(root, 'chromium_wrapper.py'))
            browser = Path(root, 'browser')
            browser.write_text('#!/usr/bin/env python3\nimport sys\nprint("browser stdout")\nprint("EGL_NOT_INITIALIZED",file=sys.stderr)\nsys.exit(9)\n')
            browser.chmod(0o755)
            env = {**os.environ, 'GATE1_CAPTURE_DIR': root, 'WORLD_ENGINE_CHROMIUM_REAL': str(browser),
                   'WORLD_ENGINE_GPU_PROFILE': 'egl', 'WORLD_ENGINE_RENDER_MODE': 'gpu-required',
                   'PYTHONPATH': str(HERE.parent)}
            result = subprocess.run([sys.executable, str(Path(root, 'browser_capture.py')), '--no-sandbox'], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 9)
            self.assertIn('browser stdout', result.stdout)
            self.assertIn('EGL_NOT_INITIALIZED', Path(root, 'chromium.stderr.log').read_text())
            record = json.loads(Path(root, 'chromium-process.json').read_text())
            self.assertEqual(record['exit_code'], 9)
            self.assertIn('--use-angle=gl-egl', record['arguments'])

    def test_backend_attempts_independent_and_runtime_inventory(self):
        with tempfile.TemporaryDirectory() as root:
            service = object.__new__(server.ProofService)
            service.bundle = Path(root)
            output = Path(root, 'output'); output.mkdir()
            def child(mode, path, env, emit):
                profile = env['WORLD_ENGINE_GPU_PROFILE']
                doc = {'error_code': profile.upper() + '_INITIALIZATION_FAILED', 'failed_stage': 'BROWSER_LAUNCH',
                       'capability_result': {'result': 'FAIL'}, 'stages': [{'name': 'BROWSER_LAUNCH', 'result': 'FAIL'}]}
                (path / 'diagnostic.json').write_text(json.dumps(doc))
                return {'exit_code': 1, 'signal': None, 'timed_out': False, 'stdout': profile, 'stderr': profile + ' error'}
            with patch.object(service, 'child', child), patch.dict(os.environ, {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'}):
                ok, diagnostic = service.run_worker('probe', output, lambda _: None)
            self.assertFalse(ok)
            self.assertEqual(set(diagnostic['attempts']), {'vulkan', 'egl'})
            self.assertEqual(diagnostic['attempts']['vulkan']['error_code'], 'VULKAN_INITIALIZATION_FAILED')
            self.assertEqual(diagnostic['attempts']['egl']['worker_process']['stderr'], 'egl error')
            for profile in ['vulkan', 'egl']:
                self.assertIn('libraries', diagnostic['attempts'][profile]['inventory'])
                self.assertIn('egl', diagnostic['attempts'][profile]['graphics_runtime'])
                self.assertTrue((output / profile / 'diagnostic.json').is_file())

    def test_worker_failure_without_json_preserves_process(self):
        with tempfile.TemporaryDirectory() as root:
            process = {'exit_code': 2, 'stderr': 'missing module', 'timed_out': False}
            value = server.ProofService.read_attempt(Path(root), 'egl', {'environment': {}}, process)
            self.assertEqual(value['error_code'], 'WORKER_PROCESS_FAILED')
            self.assertEqual(value['worker_process']['stderr'], 'missing module')

    def test_runtime_preparation_error_saved_for_both_backends(self):
        with tempfile.TemporaryDirectory() as root:
            service = object.__new__(server.ProofService); service.bundle = Path(root)
            with patch('graphics_runtime.prepare_graphics_runtime', side_effect=ValueError('GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE')), patch.dict(os.environ, {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'}):
                ok, value = service.run_worker('probe', Path(root), lambda _: None)
            self.assertFalse(ok)
            for attempt in value['attempts'].values():
                self.assertEqual(attempt['failed_stage'], 'GRAPHICS_RUNTIME')
                self.assertIn('GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE', attempt['error']['message'])
                self.assertEqual(attempt['worker_process']['result'], 'NOT_RUN')

    def test_backend_failure_then_success_preserves_first_failure(self):
        with tempfile.TemporaryDirectory() as root:
            service = object.__new__(server.ProofService); service.bundle = Path(root)
            def child(mode, path, env, emit):
                passed = env['WORLD_ENGINE_GPU_PROFILE'] == 'egl'
                (path / 'diagnostic.json').write_text(json.dumps({'error_code': None if passed else 'CHROMIUM_LAUNCH_FAILED',
                    'gpu_renderer': 'TEST_NOT_HARDWARE', 'capability_result': {'result': 'PASS' if passed else 'FAIL'}}))
                return {'exit_code': 0 if passed else 1, 'timed_out': False}
            with patch.object(service, 'child', child), patch.dict(os.environ, {'WORLD_ENGINE_GPU_PROFILE': 'vulkan'}):
                ok, value = service.run_worker('probe', Path(root), lambda _: None)
            self.assertTrue(ok)
            self.assertEqual(value['attempts']['vulkan']['error_code'], 'CHROMIUM_LAUNCH_FAILED')
            self.assertEqual(value['attempts']['egl']['capability_result']['result'], 'PASS')


class LiveResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test); self.began = time.monotonic(); self.outcome = 'PASS'
        print(json.dumps({'test': test.id(), 'stage': 'START'}), flush=True)
    def stopTest(self, test):
        super().stopTest(test)
        print(json.dumps({'test': test.id(), 'stage': 'END', 'result': self.outcome, 'elapsed': round(time.monotonic() - self.began, 3)}), flush=True)
    def addFailure(self, test, error):
        self.outcome = 'FAIL'; super().addFailure(test, error)
    def addError(self, test, error):
        self.outcome = 'ERROR'; super().addError(test, error)


if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(verbosity=2, resultclass=LiveResult))
