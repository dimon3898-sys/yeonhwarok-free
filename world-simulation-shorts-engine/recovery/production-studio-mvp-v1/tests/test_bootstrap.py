import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_bootstrap_test', HERE / 'bootstrap.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'studio'
        self.uid, self.gid = os.geteuid(), os.getegid()
        self.environment = {'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': 'https://studio.example.invalid',
            'WORLD_ENGINE_STUDIO_OWNER_CODE': 'test-' + os.urandom(24).hex()}
    def tearDown(self):
        self.temp.cleanup()
    def prepare(self):
        return m.prepare_configuration(self.environment, default_root=self.root, uid=self.uid, gid=self.gid)
    def test_explicit_owner_is_private_and_not_changed(self):
        config = self.prepare()
        self.assertEqual(config['owner'].stat().st_mode & 0o777, 0o600)
        self.assertEqual(config['root'].stat().st_mode & 0o777, 0o700)
        self.assertEqual(config['owner'].read_text(), self.environment['WORLD_ENGINE_STUDIO_OWNER_CODE'])
        self.prepare()
        self.environment['WORLD_ENGINE_STUDIO_OWNER_CODE'] += 'different'
        with self.assertRaisesRegex(RuntimeError, 'PRESERVED'):
            self.prepare()
    def test_missing_owner_never_generated(self):
        self.environment.pop('WORLD_ENGINE_STUDIO_OWNER_CODE')
        with self.assertRaisesRegex(RuntimeError, 'OWNER_CONFIGURATION_REQUIRED'):
            self.prepare()
        self.assertFalse((self.root / 'owner-code').exists())
    def test_existing_private_owner_can_be_reused_without_env_value(self):
        config = self.prepare(); digest = config['owner'].read_bytes()
        self.environment.pop('WORLD_ENGINE_STUDIO_OWNER_CODE')
        self.assertEqual(self.prepare()['owner'].read_bytes(), digest)
    def test_weak_owner_rejected(self):
        self.environment['WORLD_ENGINE_STUDIO_OWNER_CODE'] = 'short'
        with self.assertRaisesRegex(RuntimeError, 'LENGTH_REQUIRED'):
            self.prepare()
    def test_https_origin_required(self):
        for origin in ['', 'http://example.invalid', 'https://example.invalid/path', 'https://a:b@example.invalid']:
            with self.subTest(origin=origin):
                self.environment['WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'] = origin
                with self.assertRaisesRegex(RuntimeError, 'HTTPS_ORIGIN_REQUIRED'):
                    self.prepare()
    def test_owner_symlink_or_public_file_rejected(self):
        self.root.mkdir(mode=0o700)
        outside = Path(self.temp.name) / 'outside'; outside.write_text('unchanged')
        (self.root / 'owner-code').symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, 'PRIVATE_FILE_REQUIRED'):
            self.prepare()
        self.assertEqual(outside.read_text(), 'unchanged')
    def test_shared_mount_cannot_be_private_state(self):
        self.environment['WORLD_ENGINE_STUDIO_STATE_ROOT'] = '/world-storage/studio'
        with self.assertRaisesRegex(RuntimeError, 'PRIVATE_LOCAL_STATE_REQUIRED'):
            self.prepare()
    def test_dotdot_cannot_disguise_shared_storage_as_local(self):
        self.environment['WORLD_ENGINE_STUDIO_STATE_ROOT'] = '/tmp/../world-storage/studio'
        with self.assertRaisesRegex(RuntimeError, 'PRIVATE_LOCAL_STATE_REQUIRED'):
            self.prepare()
    def test_health_port_cannot_be_reused(self):
        self.environment['WORLD_ENGINE_STUDIO_PORT'] = '8000'
        with self.assertRaisesRegex(RuntimeError, 'DISTINCT_PORT_REQUIRED'):
            self.prepare()
    def test_explicit_policy_is_preserved_and_does_not_grant_render(self):
        policy = {'validUntil': '2030-01-01T00:00:00Z', 'maxWallSeconds': 60, 'maxRetries': 0,
            'maxCostAmount': '1.00', 'currency': 'USD', 'gpuHourlyRate': '0.50'}
        self.environment['WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'] = json.dumps(policy)
        config = self.prepare(); target = config['root'] / 'production/operator_policy.json'
        self.assertEqual(json.loads(target.read_text()), policy)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('approved', json.loads(target.read_text()))
        policy['maxRetries'] = 1
        self.environment['WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'] = json.dumps(policy)
        with self.assertRaisesRegex(RuntimeError, 'PRESERVED'):
            self.prepare()
    def test_missing_policy_is_not_fabricated(self):
        config = self.prepare()
        self.assertFalse((config['root'] / 'production/operator_policy.json').exists())
    def test_owner_and_policy_do_not_reach_any_child_environment(self):
        config = self.prepare(); self.environment['WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'] = '{}'
        for studio in [False, True]:
            child = m.child_environment(self.environment, studio=studio, config=config)
            self.assertNotIn('WORLD_ENGINE_STUDIO_OWNER_CODE', child)
            self.assertNotIn('WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON', child)
            if studio:
                self.assertEqual(child['WORLD_ENGINE_STUDIO_OWNER_FILE'], str(config['owner']))
            else:
                self.assertFalse(any(k.startswith('WORLD_ENGINE_STUDIO_') for k in child))
    def test_legacy_failure_prevents_studio_start(self):
        config = self.prepare(); child = mock.Mock(); child.poll.return_value = 7
        spawn = mock.Mock(return_value=child)
        self.assertEqual(m.supervise(config, self.environment, spawn=spawn, health=lambda: True), 7)
        spawn.assert_called_once()
        self.assertEqual(spawn.call_args.args[0], m.LEGACY_COMMAND)
    def test_zero_child_exit_is_not_hidden_as_service_success(self):
        config = self.prepare(); child = mock.Mock(); child.poll.return_value = 0
        self.assertEqual(m.supervise(config, self.environment, spawn=mock.Mock(return_value=child), health=lambda: True), 1)
    def test_no_health_does_not_start_studio(self):
        config = self.prepare(); child = mock.Mock(); child.poll.return_value = None
        spawn = mock.Mock(return_value=child)
        with mock.patch.object(m, 'stop_child') as stop:
            with self.assertRaisesRegex(RuntimeError, 'ORIGINAL_GPU_HEALTH_NOT_READY'):
                m.supervise(config, self.environment, spawn=spawn, health=lambda: False,
                    monotonic=mock.Mock(side_effect=[0, 2]), pause=lambda _: None, startup_timeout=1)
            spawn.assert_called_once(); self.assertEqual(stop.call_count, 2)
    def test_only_actual_nonroot_device_groups_are_reused(self):
        groups = m.device_groups()
        self.assertEqual(groups, sorted(set(groups)))
        self.assertTrue(all(type(group) is int and group > 0 for group in groups))
    def test_studio_children_have_engine_home_and_private_xdg(self):
        config = self.prepare()
        child = m.child_environment(self.environment, studio=True, config=config)
        self.assertEqual(child['HOME'], str(config['home']))
        self.assertEqual(child['WORLD_ENGINE_RENDER_MODE'], 'gpu-required')
        for name in ['XDG_RUNTIME_DIR', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME']:
            self.assertTrue(Path(child[name]).is_relative_to(config['root']))
            self.assertEqual(Path(child[name]).stat().st_mode & 0o777, 0o700)
    def test_fixed_commands_no_shell_or_workload_execution(self):
        config = self.prepare(); native, service = mock.Mock(), mock.Mock()
        native.poll.side_effect = [None, 13]; service.poll.return_value = None
        spawn = mock.Mock(side_effect=[native, service])
        with mock.patch.object(m, 'stop_child'), mock.patch.object(m, 'device_groups', return_value=[44, 109]):
            self.assertEqual(m.supervise(config, self.environment, spawn=spawn, health=lambda: True), 13)
        service_call = spawn.call_args_list[1]
        self.assertEqual(service_call.kwargs['user'], 1000)
        self.assertEqual(service_call.kwargs['extra_groups'], [44, 109])
        self.assertIn(str(HERE / 'server.py'), service_call.args[0])
        self.assertNotIn('shell', service_call.kwargs)
        self.assertFalse(any('orchestrator' in str(c) for c in spawn.call_args_list))


if __name__ == '__main__':
    unittest.main()
