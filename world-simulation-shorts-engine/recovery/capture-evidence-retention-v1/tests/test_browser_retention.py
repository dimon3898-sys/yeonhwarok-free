"""New CPU-only checks for bounded capture diagnostics, not GPU validation."""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / 'codex-to-gcube-handoff-v1/controller'


def extract(path, names, namespace):
    tree = ast.parse(path.read_text())
    selected = []
    for node in tree.body:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None
        assigned = [t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else []
        if name in names or any(n in names for n in assigned):
            selected.append(node)
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(path), 'exec'), namespace)


ENV = {'PATH': os.environ.get('PATH', ''), 'HOME': '/tmp',
       'GPU_BACKEND': 'vulkan', 'WORLD_ENGINE_RENDER_MODE': 'gpu-required',
       'NVIDIA_DRIVER_CAPABILITIES': 'utility,graphics,compute',
       'NVIDIA_VISIBLE_DEVICES': 'GPU-private-uuid',
       'VK_ICD_FILENAMES': '/private/secret/icd.json',
       'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': 'sha256:' + 'a' * 64}
SPACE = dict(os=os, re=__import__('re'), Path=Path, hashlib=hashlib, json=json,
             select=select, signal=signal, stat=stat, subprocess=subprocess,
             time=time, RECOVERY=ROOT, _stop_requested=False)
extract(CONTROLLER / 'nvidia_backend.py', {'_runtime_environment', '_capture_diagnostic_environment'}, SPACE)
extract(CONTROLLER / 'lease_supervisor.py', {
    '_BROWSER_EXECUTABLES', '_BROWSER_ARGS', '_NATIVE_CODES', '_NATIVE_FUNCTIONS',
    '_BROWSER_SIGNALS', '_DRIVER_CAPABILITIES', '_BrowserDiagnostics',
    '_CaptureLineBuffer', 'validate_lease_descriptor', 'parent_identity',
    'supervise_owned_capture'}, SPACE)
Diagnostic = SPACE['_BrowserDiagnostics']
Buffer = SPACE['_CaptureLineBuffer']


class BrowserRetentionTests(unittest.TestCase):
    def test_fixed_debug_only_for_capture_child(self):
        original = dict(ENV, DEBUG='*', DEBUG_FILE='/private/owner.log',
                        OWNER_CODE='secret-owner', DEBUG_COLORS='1')
        regular = SPACE['_runtime_environment'](original)
        child = SPACE['_capture_diagnostic_environment'](original)
        self.assertNotIn('DEBUG', regular)
        self.assertEqual(child['DEBUG'], 'pw:browser')
        self.assertEqual(child['DEBUG_COLORS'], '0')
        self.assertNotIn('DEBUG_FILE', child)
        self.assertNotIn('OWNER_CODE', child)
        self.assertEqual(child['NVIDIA_VISIBLE_DEVICES'], original['NVIDIA_VISIBLE_DEVICES'])
        self.assertEqual(original['DEBUG'], '*')

    def test_launch_flags_are_actual_known_subset_not_full_argv(self):
        d = Diagnostic(ENV)
        line = b'2026-11-01T00:00:00 pw:browser <launching> /usr/bin/chromium --headless --use-angle=vulkan --enable-unsafe-swiftshader --user-data-dir=/private/secret --proxy-password=secret-password'
        d.consume(line)
        self.assertTrue(d.value['launchObserved'])
        self.assertFalse(d.value['fullArgvCaptured'])
        self.assertEqual(d.value['safeActualArgs'], ['--headless', '--use-angle=vulkan', '--enable-unsafe-swiftshader'])
        self.assertEqual(d.value['omittedArgumentCount'], 2)
        self.assertEqual(d.value['executable']['knownPath'], '/usr/bin/chromium')
        self.assertEqual(d.value['argumentLineSHA256'], hashlib.sha256(line).hexdigest())
        encoded = json.dumps(d.value)
        for secret in ('secret-password', '/private/secret', 'GPU-private-uuid'):
            self.assertNotIn(secret, encoded)
        self.assertEqual(d.value['graphicsEnvironment']['deviceSelectionClass'], 'EXPLICIT')
        self.assertFalse(d.value['graphicsEnvironment']['nativeGraphicsInitializationVerified'])

    def test_unknown_executable_and_argument_values_are_never_copied(self):
        d = Diagnostic(ENV)
        d.consume(b'pw:browser <launching> /private/owner-password --use-angle=supersecret --no-sandbox')
        self.assertEqual(d.value['executable']['knownPath'], None)
        self.assertEqual(d.value['executable']['basename'], None)
        self.assertEqual(d.value['safeActualArgs'], ['--no-sandbox'])
        self.assertNotIn('supersecret', json.dumps(d.value))
        self.assertNotIn('owner-password', json.dumps(d.value))

    def test_native_error_exact_allowlist_and_exit(self):
        d = Diagnostic(ENV)
        line = b'pw:browser [pid=12][err] ANGLE Error vkCreateInstance VK_ERROR_INCOMPATIBLE_DRIVER /secret/token abc-password VK_ERROR_PRIVATE_SECRET'
        d.consume(line)
        d.consume(b'pw:browser [pid=12] <process did exit: exitCode=null, signal=SIGSEGV>')
        self.assertEqual(d.value['nativeErrors'][0]['codes'], ['VK_ERROR_INCOMPATIBLE_DRIVER'])
        self.assertEqual(d.value['nativeErrors'][0]['functions'], ['vkCreateInstance'])
        self.assertEqual(d.value['nativeErrors'][0]['category'], 'VULKAN')
        self.assertEqual(d.value['browserExit'], {'exitCode': None, 'signal': 'SIGSEGV', 'observed': True})
        for secret in ('PRIVATE_SECRET', 'abc-password', '/secret/token'):
            self.assertNotIn(secret, json.dumps(d.value))
        d.consume(b'raw unrelated VK_ERROR_DEVICE_LOST owner-secret')
        self.assertEqual(len(d.value['nativeErrors']), 1)

    def test_diagnostic_volume_and_line_bounds(self):
        d = Diagnostic(ENV)
        for _ in range(1000):
            d.consume(b'pw:browser [pid=2][err] vkCreateDevice VK_ERROR_DEVICE_LOST ' + b'x' * 300)
        self.assertEqual(len(d.value['nativeErrors']), 32)
        self.assertTrue(d.value['truncated'])
        self.assertGreater(d.value['droppedLines'], 0)
        self.assertLess(len(json.dumps(d.value)), 16384)

    def test_long_non_json_line_does_not_mask_following_progress(self):
        d = Diagnostic(ENV)
        b = Buffer(d)
        result = b.feed(b'pw:browser ' + b's' * 65536)
        result += b.feed(b's' * 65536 + b'\n{"stage":"ACTUAL_FRAME_DRAW","renderedFrames":1}\n')
        self.assertEqual(result, [b'{"stage":"ACTUAL_FRAME_DRAW","renderedFrames":1}'])
        self.assertTrue(d.value['truncated'])
        self.assertLessEqual(len(b.pending), 16384)

    def test_json_progress_limit_is_preserved(self):
        d = Diagnostic(ENV)
        b = Buffer(d)
        with self.assertRaisesRegex(RuntimeError, '^HANDOFF_CAPTURE_PROGRESS_LIMIT$'):
            b.feed(b'{"stage":"ACTUAL_FRAME_DRAW","padding":"' + b'x' * (128 * 1024))

    def run_supervisor(self, rows, exit_code, expected_error=None, fail_snapshot=False):
        cleanup_calls, observed_env, early = [], [], []
        class Guard:
            def __init__(self, pid): self.pid = pid
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def cleanup(self):
                cleanup_calls.append(self.pid)
                return {'remaining': [], 'errors': [], 'observationError': None}
        def atomic(path, value):
            if fail_snapshot and path.name == 'BROWSER_DIAGNOSTIC.json':
                raise OSError('fixture-only-storage-error')
            path.write_text(json.dumps(value))
            path.chmod(0o600)
        def load(name, path):
            return types.SimpleNamespace(DescendantGuard=Guard) if path.name == 'process_guard.py' else types.SimpleNamespace(atomic=atomic)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            lock = output / 'CAPTURE.guard'
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
            fake_export = types.SimpleNamespace(preserve_before_cleanup=lambda root: early.append((root / 'BROWSER_DIAGNOSTIC.json').exists()))
            old_module = sys.modules.get('capture_diagnostics_safe')
            sys.modules['capture_diagnostics_safe'] = fake_export
            SPACE['load'] = load
            parent = SPACE['parent_identity'](os.getppid())
            payload = b''.join(row + b'\n' for row in rows)
            code = 'import os,sys; os.write(1,' + repr(payload) + '); sys.exit(' + str(exit_code) + ')'
            def factory(command, **options):
                observed_env.append(options['env'])
                return subprocess.Popen(command, **options)
            try:
                args = dict(lease_fd=fd, lease_path=lock, parent=parent, seconds=5,
                            environment=ENV, output=output, capture_factory=factory, total_frames=300)
                if expected_error:
                    with self.assertRaisesRegex(RuntimeError, '^' + expected_error + '$'):
                        SPACE['supervise_owned_capture']([sys.executable, '-c', code], **args)
                    result = None
                else:
                    result = SPACE['supervise_owned_capture']([sys.executable, '-c', code], **args)
                receipt = json.loads((output / 'LEASE_SUPERVISOR_RESULT.json').read_text())
                first = json.loads((output / 'FIRST_CAPTURE_FAILURE.json').read_text()) if (output / 'FIRST_CAPTURE_FAILURE.json').exists() else None
                self.assertTrue(receipt['cleanupVerified'])
                self.assertEqual(len(cleanup_calls), 1)
                self.assertEqual(observed_env[0]['DEBUG'], 'pw:browser')
                return receipt, first, early, result
            finally:
                os.close(fd)
                if old_module is None: sys.modules.pop('capture_diagnostics_safe', None)
                else: sys.modules['capture_diagnostics_safe'] = old_module

    def test_real_cpu_failure_pipe_preserves_safe_facts_and_original_failure(self):
        rows = [b'pw:browser <launching> /usr/bin/chromium --headless=new --use-angle=vulkan --password=secret-value',
                b'pw:browser [pid=24][err] vkCreateInstance VK_ERROR_INITIALIZATION_FAILED /private/owner',
                b'pw:browser [pid=24] <process did exit: exitCode=9, signal=null>',
                b'{"status":"FAILED","code":"GCUBE_CAPTURE_RUNTIME_FAILED","stage":"RENDER_RUNTIME"}']
        receipt, first, early, _ = self.run_supervisor(rows, 3, 'GCUBE_CAPTURE_RUNTIME_FAILED')
        self.assertEqual(receipt['captureProcessExitCode'], 3)
        self.assertEqual(receipt['browserDiagnostics']['browserExit']['exitCode'], 9)
        self.assertEqual(first['code'], 'GCUBE_CAPTURE_RUNTIME_FAILED')
        self.assertTrue(early[0])
        self.assertNotIn('secret-value', json.dumps(receipt))
        self.assertEqual(receipt['browserDiagnostics']['nativeErrors'][0]['codes'], ['VK_ERROR_INITIALIZATION_FAILED'])

    def test_snapshot_storage_failure_does_not_change_capture_reason(self):
        rows = [b'{"status":"FAILED","code":"GCUBE_CAPTURE_RUNTIME_FAILED","stage":"RENDER_RUNTIME"}']
        receipt, first, _, _ = self.run_supervisor(rows, 3, 'GCUBE_CAPTURE_RUNTIME_FAILED', fail_snapshot=True)
        self.assertEqual(receipt['reason'], first['code'])
        self.assertEqual(receipt['captureProcessExitCode'], 3)

    def test_bad_progress_still_fails_with_existing_code(self):
        rows = [b'pw:browser ' + b'x' * 20000,
                b'{"stage":"ACTUAL_FRAME_DRAW","renderedFrames":2,"totalFrames":300,"frame":1}']
        receipt, _, _, _ = self.run_supervisor(rows, 0, 'HANDOFF_ACTUAL_FRAME_PROGRESS_INVALID')
        self.assertEqual(receipt['reason'], 'HANDOFF_ACTUAL_FRAME_PROGRESS_INVALID')

    def test_successful_cpu_progress_semantics_unchanged(self):
        rows = [b'pw:browser log without native error',
                b'{"stage":"ACTUAL_FRAME_DRAW","renderedFrames":1,"totalFrames":300,"frame":0}']
        receipt, first, _, result = self.run_supervisor(rows, 0)
        self.assertIsNone(first)
        self.assertIsNone(receipt['reason'])
        self.assertEqual(result['processedFramesObserved'], 1)
        self.assertEqual(result['status'], 'CAPTURE_PROCESS_AND_CLEANUP_COMPLETE')


if __name__ == '__main__':
    unittest.main()
