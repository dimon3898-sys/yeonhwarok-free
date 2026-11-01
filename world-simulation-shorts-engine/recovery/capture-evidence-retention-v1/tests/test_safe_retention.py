"""Only the new retention boundary; no GPU, browser, existing PASS or renderer run."""
from datetime import datetime, timedelta, timezone
import ast
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


CONTROLLER = Path(__file__).resolve().parents[2] / 'codex-to-gcube-handoff-v1/controller'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, CONTROLLER / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


exporter = module('retention_exporter', 'safe_capture_export.py')
boundary = module('retention_boundary', 'capture_diagnostics_safe.py')
JOB = 'studio-11111111111111111111111111111111'  # Synthetic job, never original failure evidence.
DIGEST = 'sha256:' + 'a' * 64
SECRET = 'OWNER_SECRET_DO_NOT_EXPORT_992645'


def browser_collector(environment):
    # Isolate only new stdlib diagnostics from production GPU/lease imports.
    tree = ast.parse((CONTROLLER / 'lease_supervisor.py').read_text())
    names = {'_BROWSER_EXECUTABLES', '_BROWSER_ARGS', '_NATIVE_CODES', '_NATIVE_FUNCTIONS',
             '_BROWSER_SIGNALS', '_DRIVER_CAPABILITIES'}
    body = [node for node in tree.body if
            isinstance(node, ast.ClassDef) and node.name == '_BrowserDiagnostics' or
            isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
    scope = {'hashlib': hashlib, 'os': os, 'Path': Path, 're': re}
    exec(compile(ast.Module(body=body, type_ignores=[]), '<new-browser-diagnostics-only>', 'exec'), scope)
    return scope['_BrowserDiagnostics'](environment)


class SafeRetentionTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        job = root / 'private/handoff-gpu-jobs' / JOB
        capture = job / 'capture'
        capture.mkdir(parents=True, mode=0o700)
        job.chmod(0o700)
        export = root / 'world-storage'
        export.mkdir(mode=0o700)
        supervisor = {'cleanupVerified': True, 'reason': 'GCUBE_CAPTURE_RUNTIME_FAILED',
                      'captureProcessExitCode': 1}
        self.write(job / 'LEASE_SUPERVISOR_RESULT.json', supervisor)
        self.write(job / 'FIRST_CAPTURE_FAILURE.json',
                   {'code': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'stage': 'RENDER_RUNTIME'})
        self.write(job / 'PLAN.json', {'renderProfile': {'imageDigest': DIGEST},
                                     'private': SECRET})
        self.write(job / 'GPU_ALLOCATION.json', {
            'model': 'NVIDIA GeForce RTX 4080 SUPER', 'driverVersion': '580.159.03',
            'memoryTotalMiB': 16376, 'uuidSHA256': 'b' * 64, 'uuid': SECRET})
        self.write(capture / 'CAPTURE_RECEIPT.json', {
            'durationSeconds': 10, 'totalFrames': 300, 'renderedFrames': 0,
            'nvidiaVerified': False,
            'failure': {'code': 'page.evaluate: Error: UP2_WEBGL2_REQUIRED\n' + SECRET,
                        'diagnosticStage': 'PAGE_EVALUATE_FIRST_NATIVE_DRAW'},
            'dependencies': {'node': 'v24.19.0', 'playwright': '1.62.1',
                             'chromium': '155.0.8059.79', 'owner': SECRET},
            'browserProfile': {'backend': 'vulkan', 'rootTestOnly': False,
                               'sandbox': 'CHROMIUM_SANDBOX', 'selectedArgs': [
                                   '--use-angle=vulkan', '--disable-vulkan-surface'],
                               'privatePath': '/private/' + SECRET}})
        return root, job, export

    @staticmethod
    def write(path, body):
        path.write_text(json.dumps(body))
        path.chmod(0o600)

    def run_export(self, job, export):
        destination = export / ('capture-diagnostic-' + job.name)
        result = exporter.export_failure(job, destination)
        raw = (destination / 'CAPTURE_DIAGNOSTIC.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
        self.assertEqual((destination / 'SHA256SUMS').read_text(),
                         result['sha256'] + '  CAPTURE_DIAGNOSTIC.json\n')
        self.assertEqual(json.loads(raw), result['diagnostic'])
        self.assertLessEqual(len(raw), exporter.LIMIT)
        return result['diagnostic'], raw, destination

    def test_runtime_metadata_has_job_binding_and_no_image_attestation(self):
        _, job, export = self.fixture()
        payload, raw, _ = self.run_export(job, export)
        evidence = payload['runtimeEvidence']
        self.assertEqual(evidence['jobId'], JOB)
        self.assertEqual(evidence['dependencies'],
                         {'node': 'v24.19.0', 'playwright': '1.62.1', 'chromium': '155.0.8059.79'})
        self.assertEqual(evidence['browserProfile']['selectedArgs'],
                         ['--use-angle=vulkan', '--disable-vulkan-surface'])
        self.assertEqual(evidence['browserProfile']['scope'], 'PROFILE_SELECTED_ARGS_NOT_FINAL_ARGV')
        self.assertEqual(evidence['gpuAllocation']['driverVersion'], '580.159.03')
        self.assertEqual(evidence['imageIdentity']['expectedImageDigest'], DIGEST)
        self.assertIsNone(evidence['imageIdentity']['actualImageDigest'])
        self.assertEqual(evidence['captureProcess']['exitCode'], 1)
        self.assertEqual(payload['supervisor'],
                         {'reason': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'cleanupVerified': True})
        self.assertEqual(payload['capture']['failure']['code'], 'UP2_WEBGL2_REQUIRED')
        self.assertEqual(payload['schema'], 'WORLD_ENGINE_CAPTURE_DIAGNOSTIC_SAFE_V3')
        self.assertNotIn(SECRET.encode(), raw)
        self.assertNotIn(b'/private/', raw)

    def test_real_export_child_survives_private_fixture_removal_and_is_readable(self):
        _, job, export = self.fixture()
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        result = boundary.export_after_cleanup(job, export, deadline)
        self.assertEqual(result, {'status': 'EXPORTED'})
        destination = export / ('capture-diagnostic-' + JOB)
        shutil.rmtree(job)  # This test-created private directory only.
        raw = (destination / 'CAPTURE_DIAGNOSTIC.json').read_bytes()
        payload = json.loads(raw)
        self.assertEqual(payload['runtimeEvidence']['jobId'], JOB)
        self.assertEqual(payload['runtimeEvidence']['gpuAllocation']['memoryTotalMiB'], 16376)
        self.assertEqual((destination / 'SHA256SUMS').read_text(),
                         hashlib.sha256(raw).hexdigest() + '  CAPTURE_DIAGNOSTIC.json\n')
        self.assertNotIn(SECRET.encode(), raw)

    def test_hostile_metadata_and_unknown_args_are_never_exported(self):
        _, job, export = self.fixture()
        receipt = json.loads((job / 'capture/CAPTURE_RECEIPT.json').read_text())
        receipt['dependencies'] = {'node': SECRET, 'chromium': {'secret': SECRET}, 'playwright': True}
        receipt['browserProfile'] = {'backend': SECRET, 'rootTestOnly': 'true', 'sandbox': SECRET,
            'selectedArgs': ['--use-angle=vulkan', '--user-data-dir=/private/' + SECRET,
                             '--proxy-server=https://user:password@host', SECRET, {'secret': SECRET}]}
        self.write(job / 'capture/CAPTURE_RECEIPT.json', receipt)
        self.write(job / 'GPU_ALLOCATION.json', {'model': SECRET, 'driverVersion': SECRET,
            'memoryTotalMiB': True, 'uuidSHA256': SECRET, 'environment': {'TOKEN': SECRET}})
        self.write(job / 'PLAN.json', {'renderProfile': {'imageDigest': SECRET}, 'token': SECRET})
        payload, raw, _ = self.run_export(job, export)
        e = payload['runtimeEvidence']
        self.assertTrue(all(v is None for v in e['dependencies'].values()))
        self.assertEqual(e['browserProfile']['selectedArgs'], ['--use-angle=vulkan'])
        self.assertEqual(e['browserProfile']['omittedArgumentCount'], 4)
        self.assertFalse(e['browserProfile']['selectedArgsFullyRetained'])
        self.assertIsNone(e['gpuAllocation']['model'])
        self.assertIsNone(e['gpuAllocation']['memoryTotalMiB'])
        self.assertIsNone(e['imageIdentity']['expectedImageDigest'])
        for forbidden in (SECRET, 'password', '/private/', 'user-data-dir', 'proxy-server'):
            self.assertNotIn(forbidden.encode(), raw)

    def test_actual_collector_snapshot_survives_export_and_expected_digest_fallback(self):
        _, job, export = self.fixture()
        collector = browser_collector({'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': DIGEST,
            'NVIDIA_VISIBLE_DEVICES': 'GPU-' + SECRET, 'NVIDIA_DRIVER_CAPABILITIES': 'all',
            'VK_ICD_FILENAMES': '/private/' + SECRET, 'LD_LIBRARY_PATH': '/private/' + SECRET,
            'GPU_BACKEND': 'vulkan', 'WORLD_ENGINE_RENDER_MODE': 'gpu-required'})
        collector.consume(('2026-11-01 pw:browser <launching> /usr/bin/chromium --use-angle=vulkan '
                           '--user-data-dir=/private/' + SECRET + ' --disable-vulkan-surface').encode())
        collector.consume(('2026-11-01 pw:browser [pid=123][err] vkCreateInstance: '
                           'VK_ERROR_INCOMPATIBLE_DRIVER /private/' + SECRET).encode())
        collector.consume(b'2026-11-01 pw:browser <process did exit: exitCode=1, signal=null>')
        self.write(job / 'BROWSER_DIAGNOSTIC.json', collector.value)
        self.write(job / 'PLAN.json', {'large': 'x' * (exporter.LIMIT + 1)})
        supervisor = json.loads((job / 'LEASE_SUPERVISOR_RESULT.json').read_text())
        supervisor.pop('captureProcessExitCode')
        self.write(job / 'LEASE_SUPERVISOR_RESULT.json', supervisor)
        self.write(job / 'CAPTURE_PROCESS_RESULT.json', {'exitCode': -9})
        payload, raw, _ = self.run_export(job, export)
        e = payload['runtimeEvidence']
        self.assertEqual(e['imageIdentity']['expectedSource'], 'CAPTURE_ENVIRONMENT')
        self.assertEqual(e['imageIdentity']['expectedImageDigest'], DIGEST)
        self.assertIsNone(e['imageIdentity']['actualImageDigest'])
        self.assertEqual(e['captureProcess']['source'], 'CAPTURE_PROCESS_RESULT')
        self.assertEqual(e['captureProcess']['exitCode'], -9)
        b = e['browserDiagnostics']
        self.assertEqual(b['executable']['knownPath'], '/usr/bin/chromium')
        self.assertEqual(b['safeActualArgs'], ['--use-angle=vulkan', '--disable-vulkan-surface'])
        self.assertEqual(b['omittedArgumentCount'], 1)
        self.assertEqual(b['browserExit']['exitCode'], 1)
        self.assertEqual(b['nativeErrors'][0]['codes'], ['VK_ERROR_INCOMPATIBLE_DRIVER'])
        self.assertEqual(b['nativeErrors'][0]['functions'], ['vkCreateInstance'])
        self.assertFalse(b['graphicsEnvironment']['nativeGraphicsInitializationVerified'])
        self.assertEqual(b['graphicsEnvironment']['deviceSelectionClass'], 'EXPLICIT')
        self.assertNotIn(SECRET.encode(), raw)
        self.assertNotIn(b'/private/', raw)

    def test_private_browser_fields_are_revalidated_and_capped_at_export(self):
        _, job, export = self.fixture()
        collector = browser_collector({'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': 'sha256:' + 'c' * 64})
        b = collector.value
        b.update({'actualImageDigest': DIGEST, 'fullArgvCaptured': True,
                  'safeActualArgs': ['--use-angle=vulkan'] * 70 + [SECRET],
                  'argumentLineSHA256': SECRET, 'observedLines': True})
        b['executable'] = {'knownPath': '/private/' + SECRET, 'basename': SECRET, 'pathSHA256': SECRET}
        b['nativeErrors'] = [{'category': 'VULKAN', 'codes': ['VK_ERROR_INITIALIZATION_FAILED', SECRET],
                             'functions': ['vkCreateDevice', SECRET], 'message': SECRET,
                             'lineSHA256': 'd' * 64}] * 40
        b['browserExit'] = {'exitCode': True, 'signal': SECRET, 'observed': True}
        b['graphicsEnvironment'].update({'driverCapabilities': ['graphics', SECRET],
            'nativeGraphicsInitializationVerified': True, 'uid': True, 'gid': SECRET,
            'gpuBackend': {'secret': SECRET}, 'renderMode': [SECRET],
            'vulkanICDOverrideSet': SECRET, 'environment': {'TOKEN': SECRET}})
        supervisor = json.loads((job / 'LEASE_SUPERVISOR_RESULT.json').read_text())
        supervisor['browserDiagnostics'] = b
        self.write(job / 'LEASE_SUPERVISOR_RESULT.json', supervisor)
        payload, raw, _ = self.run_export(job, export)
        e = payload['runtimeEvidence']; safe = e['browserDiagnostics']
        self.assertFalse(e['imageIdentity']['expectedDigestsAgree'])
        self.assertEqual(e['imageIdentity']['expectedImageDigest'], DIGEST)
        self.assertIsNone(e['imageIdentity']['actualImageDigest'])
        self.assertEqual(len(safe['safeActualArgs']), 64)
        self.assertEqual(len(safe['nativeErrors']), 32)
        self.assertTrue(safe['truncated'])
        self.assertFalse(safe['fullArgvCaptured'])
        self.assertIsNone(safe['executable']['knownPath'])
        self.assertIsNone(safe['browserExit']['exitCode'])
        self.assertIsNone(safe['browserExit']['signal'])
        self.assertEqual(safe['graphicsEnvironment']['driverCapabilities'], ['graphics'])
        self.assertIsNone(safe['graphicsEnvironment']['uid'])
        self.assertIsNone(safe['graphicsEnvironment']['gpuBackend'])
        self.assertIsNone(safe['graphicsEnvironment']['vulkanICDOverrideSet'])
        self.assertFalse(safe['graphicsEnvironment']['nativeGraphicsInitializationVerified'])
        self.assertNotIn(SECRET.encode(), raw)

    def test_new_reads_reject_symlink_oversize_and_nonprivate_sources(self):
        root, job, export = self.fixture()
        (job / 'GPU_ALLOCATION.json').unlink()
        outside = root / 'outside.json'
        self.write(outside, {'model': SECRET})
        (job / 'GPU_ALLOCATION.json').symlink_to(outside)
        self.write(job / 'PLAN.json', {'private': 'X' * (exporter.LIMIT + 1)})
        (job / 'capture/CAPTURE_RECEIPT.json').chmod(0o644)
        payload, raw, _ = self.run_export(job, export)
        self.assertTrue(payload['runtimeEvidence']['missingEvidence']['plan'])
        self.assertTrue(payload['runtimeEvidence']['missingEvidence']['gpuAllocation'])
        self.assertTrue(payload['missingEvidence']['capture'])
        self.assertIsNone(payload['runtimeEvidence']['gpuAllocation'])
        self.assertNotIn(SECRET.encode(), raw)

    def test_output_size_gate_and_write_failure_keep_original_failure(self):
        _, job, export = self.fixture()
        first = (job / 'FIRST_CAPTURE_FAILURE.json').read_bytes()
        supervisor = (job / 'LEASE_SUPERVISOR_RESULT.json').read_bytes()
        with mock.patch.object(exporter, 'runtime_evidence', return_value={'large': 'x' * exporter.LIMIT}):
            with self.assertRaisesRegex(OSError, 'DIAGNOSTIC_STORAGE_TOO_LARGE'):
                exporter.export_failure(job, export / 'too-large')
        self.assertFalse((export / 'too-large').exists())
        with mock.patch.object(exporter.os, 'mkdir', side_effect=PermissionError(13, 'fixture')):
            with self.assertRaises(PermissionError):
                exporter.export_failure(job, export / 'cannot-write')
        self.assertEqual((job / 'FIRST_CAPTURE_FAILURE.json').read_bytes(), first)
        self.assertEqual((job / 'LEASE_SUPERVISOR_RESULT.json').read_bytes(), supervisor)

    def test_new_evidence_does_not_bypass_cleanup_or_overwrite_existing_export(self):
        _, job, export = self.fixture()
        supervisor = json.loads((job / 'LEASE_SUPERVISOR_RESULT.json').read_text())
        supervisor['cleanupVerified'] = False
        self.write(job / 'LEASE_SUPERVISOR_RESULT.json', supervisor)
        with self.assertRaisesRegex(ValueError, 'DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED'):
            exporter.export_failure(job, export / 'blocked')
        self.assertFalse((export / 'blocked').exists())
        supervisor['cleanupVerified'] = True
        self.write(job / 'LEASE_SUPERVISOR_RESULT.json', supervisor)
        _, raw, destination = self.run_export(job, export)
        with self.assertRaises(FileExistsError):
            exporter.export_failure(job, destination)
        self.assertEqual((destination / 'CAPTURE_DIAGNOSTIC.json').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
