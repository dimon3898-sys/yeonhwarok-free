"""New preflight-only tests: every Docker and HTTP operation is mocked."""
from contextlib import redirect_stderr
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'label-packaging-v1/preflight_build_only.py'
spec = importlib.util.spec_from_file_location('focused_preflight', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PARENT_LITERAL = module.PARENT

class Response(io.BytesIO):
    def __init__(self, raw, headers=None):
        super().__init__(raw)
        self.headers = headers or {}

class NewPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='world-preflight-new-')
        self.root = Path(self.temp.name)
        self.billing = self.root / 'billing.json'
        self.output = self.root / 'result.json'
        self.attestation = {'accountCurrent': True, 'actionsBudgetUSD': 0,
                            'stopUsageAtLimit': True, 'paymentMethodRegistered': False}
        self.billing.write_text(json.dumps(self.attestation))
        self.manifest = {'schemaVersion': 2, 'layers': [{'size': 100}, {'size': 200}]}
        self.driver = 'overlay2'
        self.free = 16 * 1024**3
        self.calls = []
        self.http_calls = []
        self.header_override = None
        self.raw_override = None
        self.parent_override = None
        self.info_root = str(self.root)
        self.env = {'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free',
                    'DOCKER_HOST': 'tcp://synthetic-redirect.invalid:2375',
                    'DOCKER_CONTEXT': 'synthetic-context', 'DOCKER_TLS_VERIFY': '1',
                    'DOCKER_CONFIG': '/synthetic/credential-selector'}
        self.patches = [mock.patch.dict(os.environ, self.env, clear=True),
                        mock.patch.object(module.subprocess, 'check_output', side_effect=self.docker),
                        mock.patch.object(module.urllib.request, 'urlopen', side_effect=self.http),
                        mock.patch.object(module.shutil, 'disk_usage', side_effect=lambda _: SimpleNamespace(free=self.free))]
        for patch in self.patches: patch.start()

    def tearDown(self):
        for patch in reversed(self.patches): patch.stop()
        self.temp.cleanup()

    def raw(self):
        return self.raw_override if self.raw_override is not None else json.dumps(self.manifest).encode()

    def http(self, target, **kwargs):
        self.http_calls.append((target, kwargs))
        if len(self.http_calls) % 2:
            return Response(b'{"token":"SYNTHETIC_TOKEN_NOT_OUTPUT"}')
        digest = 'sha256:' + hashlib.sha256(self.raw()).hexdigest()
        return Response(self.raw(), {'Docker-Content-Digest': self.header_override or digest})

    def docker(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if '{{json .}}' in args:
            return json.dumps({'DockerRootDir': self.info_root, 'Driver': self.driver})
        return self.info_root

    def invoke(self):
        expected = self.parent_override or ('sha256:' + hashlib.sha256(self.raw()).hexdigest())
        with mock.patch.object(module, 'PARENT', expected), mock.patch.object(sys, 'argv',
                [str(SOURCE), '--billing-attestation', str(self.billing), '--out', str(self.output)]):
            module.main()
        return json.loads(self.output.read_text())

    def test_01_new_script_python_syntax(self):
        compile(SOURCE.read_text(), str(SOURCE), 'exec')

    def test_02_normal_overlay_preflight_output(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['compressedLayerBytes'], 300)
        self.assertEqual(result['estimatedRequiredBytes'], 8 * 1024**3 + 1200)
        self.assertEqual(len(self.http_calls), 2)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('SYNTHETIC_TOKEN_NOT_OUTPUT', self.output.read_text())

    def test_03_missing_billing_is_safe_failure_before_external_calls(self):
        self.billing.unlink()
        with self.assertRaisesRegex(RuntimeError, 'LIVE_BILLING_ATTESTATION_REQUIRED'):
            self.invoke()
        self.assertEqual(self.http_calls, [])
        self.assertEqual(self.calls, [])

    def test_04_missing_cost_fields_retry_and_repository_are_blocked(self):
        for value in ({}, {'accountCurrent': False}, {**self.attestation, 'paymentMethodRegistered': True}):
            self.billing.write_text(json.dumps(value))
            with self.assertRaisesRegex(RuntimeError, 'LIVE_BILLING_ATTESTATION_REQUIRED'): self.invoke()
        self.billing.write_text(json.dumps(self.attestation))
        with mock.patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '2'}):
            with self.assertRaisesRegex(RuntimeError, 'RETRY_FORBIDDEN'): self.invoke()
        with mock.patch.dict(os.environ, {'GITHUB_REPOSITORY': 'other/repository'}):
            with self.assertRaisesRegex(RuntimeError, 'REPO_MISMATCH'): self.invoke()
        self.assertEqual(self.http_calls, [])

    def test_05_boolean_budget_cannot_substitute_zero_usd(self):
        self.billing.write_text(json.dumps({**self.attestation, 'actionsBudgetUSD': False}))
        with self.assertRaisesRegex(RuntimeError, 'LIVE_BILLING_ATTESTATION_REQUIRED'): self.invoke()

    def test_06_registry_header_hash_mismatch_is_blocked(self):
        self.header_override = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'PARENT_REGISTRY_DIGEST_MISMATCH'): self.invoke()
        self.assertEqual(self.calls, [])

    def test_07_fixed_parent_hash_mismatch_is_blocked(self):
        self.parent_override = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'PARENT_DIGEST_MISMATCH'): self.invoke()
        self.assertEqual(self.calls, [])

    def test_08_cli_permission_denial_does_not_print_private_error_detail(self):
        # Run the real CLI wrapper while all HTTP and process operations remain mocks.
        digest = PARENT_LITERAL.removeprefix('sha256:')
        self.header_override = PARENT_LITERAL
        captured = io.StringIO()
        with mock.patch.object(hashlib, 'sha256', return_value=SimpleNamespace(hexdigest=lambda: digest)), \
             mock.patch.object(module.subprocess, 'check_output', side_effect=PermissionError('SYNTHETIC_PRIVATE_ERROR_DETAIL')), \
             mock.patch.object(sys, 'argv', [str(SOURCE), '--billing-attestation', str(self.billing), '--out', str(self.output)]), \
             redirect_stderr(captured):
            with self.assertRaises(SystemExit) as exit_result: runpy.run_path(str(SOURCE), run_name='__main__')
        self.assertEqual(exit_result.exception.code, 1)
        self.assertNotIn('SYNTHETIC_PRIVATE_ERROR_DETAIL', captured.getvalue())
        self.assertIn('DOCKER_ACCESS_DENIED', captured.getvalue())
        self.assertFalse(self.output.exists())

    def test_09_local_daemon_endpoint_ignores_redirect_selectors_preserves_credentials(self):
        self.invoke()
        args, kwargs = self.calls[0]
        self.assertIn('--host=unix:///var/run/docker.sock', args)
        for key in ['DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH']:
            self.assertNotIn(key, kwargs['env'])
        self.assertEqual(kwargs['env']['DOCKER_CONFIG'], '/synthetic/credential-selector')

    def test_10_vfs_cumulative_layers_capacity_is_not_underestimated(self):
        self.driver = 'vfs'
        self.free = 8 * 1024**3 + 1201
        with self.assertRaisesRegex(RuntimeError, 'BLOCKED_DAEMON_CAPACITY'): self.invoke()

    def test_11_invalid_layer_sizes_do_not_lower_capacity_estimate(self):
        for invalid in [-1, True, '100', 1.5]:
            self.http_calls.clear()
            self.manifest['layers'][0]['size'] = invalid
            with self.assertRaisesRegex(RuntimeError, 'PARENT_LAYER_INVALID'): self.invoke()

    def test_12_unknown_driver_and_relative_daemon_root_are_blocked(self):
        self.driver = 'unknown-storage'
        with self.assertRaisesRegex(RuntimeError, 'DOCKER_STORAGE_DRIVER_UNSUPPORTED'): self.invoke()
        self.http_calls.clear();self.driver = 'overlay2';self.info_root = 'relative/path'
        with self.assertRaisesRegex(RuntimeError, 'DOCKER_DATA_ROOT_INVALID'): self.invoke()

    def test_13_network_denial_is_safe_before_docker(self):
        with mock.patch.object(module.urllib.request, 'urlopen', side_effect=PermissionError('SYNTHETIC_PRIVATE_NETWORK_DETAIL')):
            with self.assertRaisesRegex(RuntimeError, '^PARENT_MANIFEST_UNAVAILABLE:PermissionError$'): self.invoke()
        self.assertEqual(self.calls, [])

    def test_14_insufficient_capacity_blocks_without_success_receipt(self):
        self.free = 1
        with self.assertRaisesRegex(RuntimeError, 'BLOCKED_DAEMON_CAPACITY'): self.invoke()
        self.assertFalse(self.output.exists())

    def test_15_oversized_attestation_is_rejected_before_external_calls(self):
        self.billing.write_text(json.dumps({**self.attestation, 'padding': 'x' * 65536}))
        with self.assertRaisesRegex(RuntimeError, 'BILLING_ATTESTATION_SIZE_LIMIT'): self.invoke()
        self.assertEqual(self.http_calls, [])

    def test_16_duplicate_billing_keys_are_not_silently_overridden(self):
        self.billing.write_text('{"accountCurrent":true,"actionsBudgetUSD":100,"actionsBudgetUSD":0,"stopUsageAtLimit":true,"paymentMethodRegistered":false}')
        with self.assertRaisesRegex(RuntimeError, 'LIVE_BILLING_ATTESTATION_REQUIRED'): self.invoke()

    def test_17_registry_manifest_read_is_bounded(self):
        self.raw_override = self.raw() + b' ' * (1024 * 1024)
        with self.assertRaisesRegex(RuntimeError, 'PARENT_MANIFEST_SIZE_LIMIT'): self.invoke()

    def test_18_new_overlay_receipt_reports_local_driver_and_preserves_auth_selector(self):
        result=self.invoke()
        self.assertEqual(result['storageDriver'],'overlay2')
        self.assertEqual(result['layerCount'],2)
        self.assertEqual(result['localDaemonEndpoint'],'unix:///var/run/docker.sock')
        self.assertEqual(result['capacityEstimateBasis'],'4x compressed bytes +8GiB reserve')
        self.assertEqual(result['parentDigest'],'sha256:'+hashlib.sha256(self.raw()).hexdigest())
        self.assertEqual(self.calls[0][1]['env']['DOCKER_CONFIG'],'/synthetic/credential-selector')

    def test_19_new_successful_vfs_receipt_uses_weighted_prefix_storage(self):
        self.driver='vfs'
        result=self.invoke()
        self.assertEqual(result['estimatedRequiredBytes'],8*1024**3+4*(100*2+200))
        self.assertEqual(result['storageDriver'],'vfs')
        self.assertEqual(result['capacityEstimateBasis'],'4x cumulative compressed prefixes +8GiB reserve')

    def test_20_output_cannot_clobber_billing_proof(self):
        self.output=self.billing
        original=self.billing.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED'): self.invoke()
        self.assertEqual(self.billing.read_bytes(),original)
        self.assertEqual(self.http_calls,[])
        self.assertEqual(self.calls,[])

    def test_21_existing_output_is_preserved_and_blocked_before_external_calls(self):
        self.output.write_text('synthetic existing receipt')
        with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED'): self.invoke()
        self.assertEqual(self.output.read_text(),'synthetic existing receipt')
        self.assertEqual(self.http_calls,[])

    def test_22_output_symlink_cannot_overwrite_an_existing_file(self):
        target=self.root/'synthetic-target.txt';target.write_text('preserve synthetic target')
        self.output.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED'): self.invoke()
        self.assertEqual(target.read_text(),'preserve synthetic target')
        self.assertEqual(self.http_calls,[])

    def test_23_output_symlink_ancestor_and_relative_paths_are_blocked(self):
        target=self.root/'actual';target.mkdir();link=self.root/'linked';link.symlink_to(target,target_is_directory=True)
        self.output=link/'new.json'
        with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED'): self.invoke()
        self.output=Path('relative-synthetic-output.json')
        with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_FRESH_PATH_REQUIRED'): self.invoke()
        self.assertEqual(self.http_calls,[])
        self.assertFalse((target/'new.json').exists())

    def test_24_output_race_uses_exclusive_creation_and_preserves_new_owner_file(self):
        original_open=Path.open
        raced=[]
        def open_file(path,mode='r',*args,**kwargs):
            if path==self.output and any(flag in mode for flag in 'wax'):
                with original_open(path,'w') as stream: stream.write('synthetic racing owner')
                raced.append(mode)
            return original_open(path,mode,*args,**kwargs)
        with mock.patch.object(Path,'open',open_file):
            with self.assertRaisesRegex(RuntimeError,'PREFLIGHT_OUTPUT_UNAVAILABLE'): self.invoke()
        self.assertEqual(raced,['x'])
        self.assertEqual(self.output.read_text(),'synthetic racing owner')

    def test_25_new_fresh_output_has_exclusive_creation_and_valid_receipt(self):
        original_open=Path.open;modes=[]
        def open_file(path,mode='r',*args,**kwargs):
            if path==self.output and any(flag in mode for flag in 'wax'): modes.append(mode)
            return original_open(path,mode,*args,**kwargs)
        with mock.patch.object(Path,'open',open_file): result=self.invoke()
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(modes,['x'])

if __name__ == '__main__':
    wanted = sys.argv[1:]
    suite = unittest.defaultTestLoader.loadTestsFromNames(wanted, NewPreflightTests) if wanted else unittest.defaultTestLoader.loadTestsFromTestCase(NewPreflightTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'schema': 'WORLD_ENGINE_NEW_PREFLIGHT_FOCUSED_TESTS_V1',
                      'status': 'PASS' if result.wasSuccessful() else 'BLOCKED',
                      'cases': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                      'realDockerCalls': 0, 'realNetworkCalls': 0, 'oldPASSSuitesRun': 0}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
