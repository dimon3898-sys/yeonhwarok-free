"""Critical additive entrypoint boundaries; no child or GPU is started."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import proxy_bootstrap as boot


class BootstrapTests(unittest.TestCase):
    def test_only_exact_frozen_ui_entry_is_substituted_and_uid_policy_is_retained(self):
        command = ['/usr/bin/python3', '-B', str(boot.parent.root / 'https_server.py'),
                   '--state-root', '/private/test-only']
        options = {'user': 1000, 'group': 1000, 'extra_groups': [44], 'start_new_session': True}
        with patch.object(boot.subprocess, 'Popen', return_value=object()) as spawn:
            boot.spawn_proxy(command, **options)
        actual = spawn.call_args.args[0]
        self.assertEqual(actual, [*command[:2], str(boot.HERE / 'proxy_server.py'), *command[3:]])
        self.assertEqual(spawn.call_args.kwargs, options)
        self.assertEqual(command[2], str(boot.parent.root / 'https_server.py'))

    def test_legacy_gpu_admission_command_and_environment_are_not_changed(self):
        command = [*boot.parent.bootstrap.original.LEGACY_COMMAND]
        options = {'env': {'WORLD_ENGINE_RENDER_MODE': 'gpu-required'}, 'start_new_session': True}
        with patch.object(boot.subprocess, 'Popen', return_value=object()) as spawn:
            boot.spawn_proxy(command, **options)
        self.assertEqual(spawn.call_args.args[0], command)
        self.assertEqual(spawn.call_args.kwargs, options)


if __name__ == '__main__':
    unittest.main()
