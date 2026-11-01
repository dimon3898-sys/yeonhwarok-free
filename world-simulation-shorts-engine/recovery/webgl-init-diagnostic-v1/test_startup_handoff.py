"""New CPU-only checks for startup-contract handoff; no child/GPU is executed.

The expected environment comes from the original pinned pure startup function
and original backend projection, not a copy of the diagnostic implementation.
"""
import ast
from collections.abc import Mapping
from contextlib import contextmanager, ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import capture_environment_runner_v2 as runner


HERE = Path(__file__).resolve().parent
STARTUP_FIXTURE = HERE / 'evidence/startup-environment-source/production_bootstrap.py'
BACKEND_CANDIDATES = (
    HERE.parent / 'codex-to-gcube-handoff-v1/controller/nvidia_backend.py',
    HERE.parent / 'capture-evidence-retention-fix/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_backend.py',
)


def pure_function(source, name, bindings=None):
    """Load one actual pure function without executing its module or imports."""
    tree = ast.parse(source)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = dict(bindings or {})
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<original-pure-fixture>', 'exec'), namespace)
    return namespace[name]


class KeyOnlyEnvironment(Mapping):
    """Fail if code enumerates the whole environment or reads a secret value."""
    def __init__(self, values, readable):
        self.values = values
        self.readable = readable
        self.read = []

    def __getitem__(self, key):
        if key not in self.readable:
            raise AssertionError('non-allowlisted environment value was read')
        self.read.append(key)
        return self.values[key]

    def __iter__(self):
        raise AssertionError('whole environment must not be enumerated')

    def __len__(self):
        return len(self.values)


class StartupHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.startup_source = STARTUP_FIXTURE.read_bytes()
        cls.backend_source = next(path for path in BACKEND_CANDIDATES if path.is_file()).read_bytes()
        if hashlib.sha256(cls.startup_source).hexdigest() != runner.STARTUP_BOOTSTRAP_SHA:
            raise AssertionError('original startup fixture pin changed')
        if hashlib.sha256(cls.backend_source).hexdigest() != runner.BACKEND_SHA:
            raise AssertionError('original backend fixture pin changed')
        tree = ast.parse(cls.startup_source)
        secret_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                                 and any(isinstance(target, ast.Name) and target.id == 'SECRET_ENV'
                                         for target in node.targets))
        cls.original_child = staticmethod(pure_function(cls.startup_source, 'child_environment',
            {'SECRET_ENV': ast.literal_eval(secret_assignment.value)}))
        cls.original_projection = staticmethod(pure_function(cls.backend_source, '_runtime_environment'))
        cls.allowed = runner.allowed_environment_names(cls.backend_source)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='world-engine-startup-handoff-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'private-state'
        self.home = self.base / 'engine-home'
        self.cwd = self.base / 'image-workdir'
        for path in (self.root, self.root / 'xdg-runtime', self.home, self.cwd):
            path.mkdir(mode=0o700)
        self.bootstrap = self.base / 'bootstrap.py'
        self.bootstrap.write_bytes(self.startup_source)
        self.controller = self.base / 'controller'
        self.controller.mkdir()
        (self.controller / 'nvidia_backend.py').write_bytes(self.backend_source)
        self.js = self.base / 'diagnostic.mjs'
        self.js.write_text('// fixture only: never executed\n')
        self.raw = {
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': '/root',
            'XDG_RUNTIME_DIR': '/root/wrong-xdg',
            'WORLD_ENGINE_RENDER_MODE': 'cpu-only',
            'NVIDIA_VISIBLE_DEVICES': 'void',
            'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility,graphics',
            'GPU_BACKEND': 'vulkan',
            'LD_LIBRARY_PATH': '',
            'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST': runner.IMAGE_DIGEST,
            'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST': runner.IMAGE_DIGEST,
            'WORLD_ENGINE_STUDIO_STATE_ROOT': str(self.root),
            'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN': 'https://studio.invalid',
            'WORLD_ENGINE_STUDIO_OWNER_CODE': 'do-not-read-owner-sentinel',
            'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON': 'do-not-read-policy-sentinel',
            'DROPBOX_TOKEN': 'do-not-read-token-sentinel',
            'DEBUG': 'do-not-forward-debug',
        }
        self.readable = self.allowed | {
            'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST',
            'WORLD_ENGINE_STUDIO_STATE_ROOT', 'WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN',
        }
        self.identity = {'pid': 52, 'ticks': 'original-worker-ticks', 'groups': [44, 109]}
        self.args = SimpleNamespace(approved_single_diagnostic=True, inner=False, worker_pid=52,
            runner=self.js, runner_sha256=hashlib.sha256(self.js.read_bytes()).hexdigest(),
            output='/world-storage/test-not-executed')
        self.contract_uid = 1000
        self.contract_mode = 0o700

    def expected_environment(self):
        config = {'root': self.root, 'owner': self.root / 'owner-code',
                  'origin': self.raw['WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'], 'home': self.home,
                  'xdg': {key: self.root / suffix for key, suffix in
                          [('XDG_RUNTIME_DIR', 'xdg-runtime'), ('XDG_CONFIG_HOME', 'xdg-config'),
                           ('XDG_CACHE_HOME', 'xdg-cache')]}}
        # Original bootstrap passes the transformed environment through supervise
        # and child_environment again. The capture backend projects the result.
        first = self.original_child(self.raw, studio=True, config=config)
        second = self.original_child(first, studio=True, config=config)
        return self.original_projection(second)

    @contextmanager
    def handoff_context(self, *, identities=None, observed_cwd=None):
        original_open = Path.open
        original_stat = Path.stat
        original_readlink = os.readlink
        environment = KeyOnlyEnvironment(self.raw, self.readable)

        def guarded_open(path, *args, **kwargs):
            if str(path).startswith('/proc/') or path.name == 'owner-code':
                raise AssertionError('protected process/owner data was opened')
            return original_open(path, *args, **kwargs)

        def guarded_readlink(path, *args, **kwargs):
            if str(path).startswith('/proc/'):
                raise AssertionError('cross-process cwd was read')
            return original_readlink(path, *args, **kwargs)

        def fixture_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path in {self.root, self.root / 'xdg-runtime'}:
                fields = list(result)
                fields[0] = stat.S_IFDIR | self.contract_mode
                fields[4] = self.contract_uid
                return os.stat_result(fields)
            return result

        with ExitStack() as stack:
            stack.enter_context(patch.object(runner, 'STARTUP_BOOTSTRAP', self.bootstrap))
            stack.enter_context(patch.object(runner, 'CONTROLLER', self.controller))
            stack.enter_context(patch.object(runner, 'IMAGE_WORKDIR', self.cwd))
            stack.enter_context(patch.object(runner.os, 'environ', environment))
            stack.enter_context(patch.object(runner.os, 'geteuid', return_value=0))
            stack.enter_context(patch.object(runner.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir=str(self.home))))
            stack.enter_context(patch.object(Path, 'open', guarded_open))
            stack.enter_context(patch.object(Path, 'stat', fixture_stat))
            stack.enter_context(patch.object(Path, 'cwd', return_value=self.cwd if observed_cwd is None else observed_cwd))
            stack.enter_context(patch.object(runner.os, 'readlink', guarded_readlink))
            identity = stack.enter_context(patch.object(runner, 'worker_identity',
                side_effect=identities or [dict(self.identity), dict(self.identity)]))
            popen = stack.enter_context(patch.object(runner.subprocess, 'Popen'))
            popen.return_value.returncode = 0
            popen.return_value.communicate.return_value = (json.dumps({
                'status': 'PASS_CONTEXT_ONLY', 'contextAttempts': 1, 'browserLaunches': 1,
                'renderedFrames': 0, 'environmentSource': 'PINNED_STARTUP_CONTRACT',
                'workerEnvironmentDirectlyCompared': False,
            }).encode(), None)
            # These functions must never run in the test except inside the
            # explicitly mocked privilege-drop assertion below.
            drop = Mock()
            for name in ('setgroups', 'setgid', 'setuid'):
                drop.attach_mock(stack.enter_context(patch.object(runner.os, name)), name)
            yield environment, identity, popen, drop

    def test_projection_matches_original_startup_without_secret_reads(self):
        expected = self.expected_environment()
        with self.handoff_context() as (environment, _, popen, _):
            actual = runner.startup_environment(self.allowed, environment)
        self.assertEqual(actual, expected)
        self.assertEqual(actual['HOME'], str(self.home))
        self.assertEqual(actual['XDG_RUNTIME_DIR'], str(self.root / 'xdg-runtime'))
        self.assertEqual(actual['WORLD_ENGINE_RENDER_MODE'], 'gpu-required')
        self.assertEqual(actual['NVIDIA_VISIBLE_DEVICES'], 'void')
        self.assertEqual(actual['LD_LIBRARY_PATH'], '')
        self.assertNotIn('DISPLAY', actual)
        self.assertNotIn('DEBUG', actual)
        self.assertFalse(set(environment.read) - self.readable)
        self.assertNotIn('sentinel', json.dumps(actual))
        popen.assert_not_called()

    def test_main_transfers_contract_and_identity_without_process_data_access(self):
        expected = self.expected_environment()
        output = io.StringIO()
        with self.handoff_context() as (_, identity, popen, drop), redirect_stdout(output):
            self.assertEqual(runner.main(self.args), 0)
            self.assertEqual(identity.call_count, 2)
            popen.assert_called_once()
            command = popen.call_args.args[0]
            options = popen.call_args.kwargs
            self.assertEqual(options['env'], expected)
            self.assertEqual(options['cwd'], str(self.cwd))
            self.assertEqual(command.count('--inner'), 1)
            self.assertEqual(command.count('--approved-single-diagnostic'), 1)
            self.assertTrue(options['start_new_session'])
            drop.assert_not_called()
            options['preexec_fn']()
            self.assertEqual([(call[0], call.args) for call in drop.mock_calls],
                             [('setgroups', ([44, 109],)), ('setgid', (1000,)), ('setuid', (1000,))])
        summary = json.loads(output.getvalue())
        self.assertEqual(summary['environmentSource'], 'PINNED_STARTUP_CONTRACT')
        self.assertFalse(summary['workerEnvironmentDirectlyCompared'])
        self.assertNotIn('workerEnvironmentReused', summary)
        self.assertNotIn('sentinel', output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())

    def test_startup_source_pin_mismatch_blocks_before_launch(self):
        self.bootstrap.write_bytes(self.startup_source + b'\n# changed\n')
        with self.handoff_context() as (_, _, popen, _):
            with self.assertRaisesRegex(RuntimeError, '^DIAG_STARTUP_ENV_SOURCE_CHANGED$'):
                runner.main(self.args)
            popen.assert_not_called()

    def test_each_image_digest_mismatch_blocks_before_launch(self):
        for key in ('WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST', 'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'):
            with self.subTest(key=key):
                original = self.raw[key]
                self.raw[key] = 'sha256:' + '0' * 64
                try:
                    with self.handoff_context() as (_, _, popen, _):
                        with self.assertRaisesRegex(RuntimeError, '^DIAG_STARTUP_IMAGE_CONTRACT_CHANGED$'):
                            runner.main(self.args)
                        popen.assert_not_called()
                finally:
                    self.raw[key] = original

    def test_wrong_private_directory_identity_or_mode_blocks_before_launch(self):
        for uid, mode in ((0, 0o700), (1000, 0o755)):
            with self.subTest(uid=uid, mode=mode):
                self.contract_uid, self.contract_mode = uid, mode
                with self.handoff_context() as (_, _, popen, _):
                    with self.assertRaisesRegex(RuntimeError, '^DIAG_'):
                        runner.main(self.args)
                    popen.assert_not_called()

    def test_cwd_mismatch_blocks_before_launch(self):
        with self.handoff_context(observed_cwd=self.base) as (_, _, popen, _):
            with self.assertRaisesRegex(RuntimeError, '^DIAG_IMAGE_WORKING_DIRECTORY_REQUIRED$'):
                runner.main(self.args)
            popen.assert_not_called()

    def test_worker_change_blocks_before_launch(self):
        changed = dict(self.identity, ticks='replacement-worker-ticks')
        with self.handoff_context(identities=[self.identity, changed]) as (_, _, popen, _):
            with self.assertRaisesRegex(RuntimeError, '^DIAG_WORKER_CHANGED$'):
                runner.main(self.args)
            popen.assert_not_called()

    def test_handoff_provenance_remains_closed_and_honest_in_summary(self):
        raw = {'status': 'BLOCKED', 'environmentSource': 'PINNED_STARTUP_CONTRACT',
               'workerEnvironmentDirectlyCompared': False, 'workerEnvironmentReused': True,
               'environment': {'OWNER': 'secret-sentinel'}, 'cwd': '/private/path'}
        safe = runner.safe_stdout(json.dumps(raw).encode())
        self.assertEqual(safe, {'status': 'BLOCKED', 'environmentSource': 'PINNED_STARTUP_CONTRACT',
                                'workerEnvironmentDirectlyCompared': False})
        raw['environmentSource'] = '/private/secret-sentinel'
        self.assertEqual(runner.safe_stdout(json.dumps(raw).encode()),
                         {'status': 'BLOCKED', 'workerEnvironmentDirectlyCompared': False})


if __name__ == '__main__':
    unittest.main()
