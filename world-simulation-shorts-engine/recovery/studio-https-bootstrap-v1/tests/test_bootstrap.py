"""CPU-only supervisor and configuration regression; no GPU success implied."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

PROFILE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROFILE))
import https_bootstrap as module

OWNER = 'TEST_ONLY-unchanged-owner-fixture'


class Child:
    def __init__(self, codes):
        self.codes = iter(codes)
        self.last = None
        self.pid = 123456789
        self.polls = 0

    def poll(self):
        self.polls += 1
        try:
            self.last = next(self.codes)
        except StopIteration:
            pass
        return self.last


class HttpsBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.environment = {'WORLD_ENGINE_STUDIO_STATE_ROOT': str(self.root),
                            'WORLD_ENGINE_STUDIO_OWNER_CODE': OWNER}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, env=None):
        return module.prepare_configuration(self.environment if env is None else env,
                                            uid=os.getuid(), gid=os.getgid())

    def policy(self, **overrides):
        result = {'validUntil': '2099-01-01T00:00:00+00:00', 'maxWallSeconds': 60, 'maxRetries': 0,
                  'maxCostAmount': '1.00', 'currency': 'USD', 'gpuHourlyRate': '0.50'}
        result.update(overrides)
        return result

    def assertCode(self, code, call):
        with self.assertRaises(Exception) as raised:
            call()
        self.assertEqual(getattr(raised.exception, 'code', None) or str(raised.exception), code)

    def test_missing_origin_now_prepares_setup_without_fake_origin(self):
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_HTTPS_ORIGIN_REQUIRED'):
            module.original.prepare_configuration(self.environment, uid=os.getuid(), gid=os.getgid())
        configuration = self.prepare()
        self.assertEqual(configuration['origin'], '')
        self.assertEqual(configuration['port'], 8080)
        self.assertEqual(configuration['configuration_error'], 'STUDIO_OPERATOR_POLICY_REQUIRED')
        self.assertFalse((self.root / 'https-origin.json').exists())

    def test_missing_owner_remains_fatal(self):
        env = dict(self.environment)
        env.pop('WORLD_ENGINE_STUDIO_OWNER_CODE')
        self.assertCode('STUDIO_OWNER_CONFIGURATION_REQUIRED', lambda: self.prepare(env))
        self.assertFalse((self.root / 'owner-code').exists())

    def test_owner_existing_secret_reused_and_never_replaced(self):
        first = self.prepare()
        digest = hashlib.sha256(first['owner'].read_bytes()).hexdigest()
        env = dict(self.environment)
        env.pop('WORLD_ENGINE_STUDIO_OWNER_CODE')
        self.prepare(env)
        self.assertEqual(hashlib.sha256(first['owner'].read_bytes()).hexdigest(), digest)
        env['WORLD_ENGINE_STUDIO_OWNER_CODE'] = OWNER + '-different'
        self.assertCode('STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED', lambda: self.prepare(env))
        self.assertEqual(hashlib.sha256(first['owner'].read_bytes()).hexdigest(), digest)

    def test_policy_missing_does_not_create_defaults(self):
        config = self.prepare()
        self.assertEqual(config['configuration_error'], 'STUDIO_OPERATOR_POLICY_REQUIRED')
        self.assertFalse((self.root / 'production/operator_policy.json').exists())

    def test_policy_json_and_semantic_errors_keep_setup_but_block_render(self):
        variants = [('{bad', 'STUDIO_OPERATOR_POLICY_JSON_REQUIRED'),
                    ('{}', 'STUDIO_OPERATOR_POLICY_FIELDS_REQUIRED'),
                    (json.dumps(self.policy(maxWallSeconds=0)), 'STUDIO_OPERATOR_POLICY_INVALID'),
                    (json.dumps(self.policy(validUntil='2000-01-01T00:00:00+00:00')), 'STUDIO_OPERATOR_POLICY_EXPIRED'),
                    (json.dumps(self.policy(maxCostAmount='0.0001')), 'STUDIO_COST_LIMIT_EXCEEDED'),
                    (json.dumps(self.policy(gpuHourlyRate='unknown')), 'STUDIO_OPERATOR_POLICY_INVALID')]
        for raw, expected in variants:
            with self.subTest(code=expected):
                env = dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON=raw)
                self.assertEqual(self.prepare(env)['configuration_error'], expected)
        self.assertFalse((self.root / 'production/operator_policy.json').exists())

    def test_valid_policy_preserved_and_reused_from_private_storage(self):
        policy = self.policy()
        config = self.prepare(dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON=json.dumps(policy)))
        self.assertIsNone(config['configuration_error'])
        path = self.root / 'production/operator_policy.json'
        original = path.read_bytes()
        config = self.prepare()
        self.assertIsNone(config['configuration_error'])
        self.assertEqual(path.read_bytes(), original)
        different = self.policy(maxRetries=1)
        config = self.prepare(dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON=json.dumps(different)))
        self.assertEqual(config['configuration_error'], 'STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED')
        self.assertEqual(path.read_bytes(), original)

    def test_duplicate_json_fields_and_nonfinite_values_block_policy(self):
        policy = json.dumps(self.policy())
        raw = policy[:-1] + ', "maxRetries": 1}'
        config = self.prepare(dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON=raw))
        self.assertEqual(config['configuration_error'], 'STUDIO_OPERATOR_POLICY_JSON_REQUIRED')
        raw = policy.replace('"maxRetries": 0', '"maxRetries": NaN')
        config = self.prepare(dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON=raw))
        self.assertEqual(config['configuration_error'], 'STUDIO_OPERATOR_POLICY_JSON_REQUIRED')

    def test_untrusted_error_environment_cannot_bypass_or_forge_gate(self):
        config = self.prepare()
        env = dict(self.environment, WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR='forged-token-value')
        studio = module.child_environment(env, studio=True, config=config)
        legacy = module.child_environment(env)
        self.assertEqual(studio[module.CONFIGURATION_ERROR], 'STUDIO_OPERATOR_POLICY_REQUIRED')
        self.assertNotIn(module.CONFIGURATION_ERROR, legacy)
        config['configuration_error'] = None
        self.assertNotIn(module.CONFIGURATION_ERROR, module.child_environment(env, studio=True, config=config))

    def test_secrets_not_forwarded_and_existing_gpu_required_preserved(self):
        config = self.prepare()
        env = dict(self.environment, WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON='secret-policy',
                   WORLD_ENGINE_RENDER_MODE='software', NVIDIA_DRIVER_CAPABILITIES='graphics,utility')
        studio = module.child_environment(env, studio=True, config=config)
        legacy = module.child_environment(env)
        for child in (studio, legacy):
            self.assertNotIn('WORLD_ENGINE_STUDIO_OWNER_CODE', child)
            self.assertNotIn('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON', child)
        self.assertEqual(studio['WORLD_ENGINE_RENDER_MODE'], 'gpu-required')
        self.assertNotIn('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN', studio)
        self.assertEqual(studio['HOME'], str(config['home']))
        self.assertEqual(studio['XDG_RUNTIME_DIR'], str(config['xdg']['XDG_RUNTIME_DIR']))

    def test_ui_starts_before_gpu_and_survives_gpu_exit_without_retry(self):
        config = self.prepare()
        ui, gpu = Child([None, None, None, 42]), Child([7])
        calls, stopped, pauses = [], [], []
        def spawn(command, **kwargs):
            calls.append((command, kwargs))
            return ui if len(calls) == 1 else gpu
        output = io.StringIO()
        with redirect_stdout(output):
            code = module.supervise(config, self.environment, spawn=spawn, device_groups=lambda: [44],
                                    stop=stopped.append, pause=pauses.append)
        self.assertEqual(code, 42)
        self.assertEqual(len(calls), 2)
        self.assertIn('https_server.py', calls[0][0][2])
        self.assertEqual(calls[1][0], module.original.LEGACY_COMMAND)
        self.assertEqual(calls[0][1]['user'], 1000)
        self.assertEqual(calls[0][1]['group'], 1000)
        self.assertEqual(calls[0][1]['extra_groups'], [44])
        self.assertTrue(calls[0][1]['start_new_session'])
        self.assertEqual(gpu.polls, 1)
        self.assertEqual(len(pauses), 3)
        self.assertEqual(stopped, [ui, gpu])
        records = [json.loads(row) for row in output.getvalue().splitlines()]
        self.assertEqual([row['stage'] for row in records], ['SETUP_SERVICE_STARTED', 'GPU_ADMISSION_EXITED', 'SETUP_SERVICE_EXITED'])
        self.assertFalse(any(row['gpuRenderingVerified'] for row in records))
        self.assertNotIn(OWNER, output.getvalue())

    def test_legacy_spawn_error_keeps_setup_and_logs_only_safe_code(self):
        config = self.prepare()
        ui = Child([None, 2])
        calls, stopped = [], []
        def spawn(command, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                return ui
            raise RuntimeError('secret-containing diagnostic must not escape')
        output = io.StringIO()
        with redirect_stdout(output):
            result = module.supervise(config, self.environment, spawn=spawn, device_groups=lambda: [],
                                      stop=stopped.append, pause=lambda _: None)
        self.assertEqual(result, 2)
        self.assertEqual(len(calls), 2)
        self.assertIn('STUDIO_GPU_SERVICE_START_FAILED', output.getvalue())
        self.assertNotIn('secret-containing', output.getvalue())
        self.assertEqual(stopped, [ui, None])

    def test_sigterm_stops_both_owned_children_and_restores_handlers(self):
        config = self.prepare()
        ui, gpu = Child([None]), Child([None])
        children = iter([ui, gpu])
        stopped = []
        previous = signal.getsignal(signal.SIGTERM)
        def pause(_):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        with redirect_stdout(io.StringIO()):
            result = module.supervise(config, self.environment, spawn=lambda *a, **k: next(children),
                                      device_groups=lambda: [], pause=pause, stop=stopped.append)
        self.assertEqual(result, 143)
        self.assertEqual(stopped, [ui, gpu])
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    def test_ui_unexpected_zero_exit_is_failure_and_no_automatic_render(self):
        config = self.prepare()
        ui, gpu = Child([0]), Child([None])
        children = iter([ui, gpu])
        with redirect_stdout(io.StringIO()):
            result = module.supervise(config, self.environment, spawn=lambda *a, **k: next(children),
                                      device_groups=lambda: [], stop=lambda _: None)
        self.assertEqual(result, 1)
        self.assertEqual(gpu.polls, 0)

    def test_shared_private_state_and_port_8000_remain_forbidden(self):
        self.assertCode('STUDIO_PRIVATE_LOCAL_STATE_REQUIRED', lambda: self.prepare(
            dict(self.environment, WORLD_ENGINE_STUDIO_STATE_ROOT='/world-storage/private')))
        self.assertCode('STUDIO_DISTINCT_PORT_REQUIRED', lambda: self.prepare(
            dict(self.environment, WORLD_ENGINE_STUDIO_PORT='8000')))


if __name__ == '__main__':
    unittest.main()
