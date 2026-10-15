"""CPU child processes exercise the monitor; no native GPU launcher is invoked."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import job_manager as manager
import job_store


class NativeMonitorTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='test-only-native-monitor-', dir='/workspace')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.script = self.root / 'SYNTHETIC_CPU_CHILD.py'
        self.state = manager._initial(True)
        self.updates = []

    def invoke(self, code, **patches):
        self.script.write_text(code)
        with mock.patch.object(manager, 'LAUNCH', self.script), (mock.patch.multiple(manager, **patches) if patches else contextlib.nullcontext()):
            return manager.native_work(self.state, self.updates.append, self.root)

    def test_cpu_subprocess_keeps_first_failure_and_real_identity(self):
        first = manager.records.make_record('NVIDIA', 'GPU_HARDWARE_UNAVAILABLE', 2, test_only=True)
        second = manager.records.make_record('STORAGE', 'STORAGE_UNAVAILABLE', 1, test_only=True)
        result = self.invoke('import json\nprint('+repr(json.dumps(first))+',flush=True)\nprint('+repr(json.dumps(second))+',flush=True)\nraise SystemExit(2)\n')
        self.assertEqual(result['firstFailure'], first)
        self.assertEqual(result['exitCode'], 2)
        identity = next(v['rendererIdentity'] for v in self.updates if 'rendererIdentity' in v)
        self.assertNotEqual(identity['pid'], os.getpid())
        self.assertFalse(manager.is_alive(identity))
        self.assertEqual(len([v for v in self.updates if 'firstFailure' in v]), 1)
        self.assertEqual((self.root / ('native-' + self.state['jobId'] + '.log')).stat().st_mode & 0o777, 0o600)

    def test_log_limit_terminates_only_this_cpu_child(self):
        with self.assertRaisesRegex(manager.ManagerError, '^LOG_LIMIT_EXCEEDED$'):
            self.invoke("import time\nprint('SYNTHETIC_'*100,flush=True)\ntime.sleep(10)\n", MAX_LOG=32)
        identity = next(v['rendererIdentity'] for v in self.updates if 'rendererIdentity' in v)
        self.assertFalse(manager.is_alive(identity))

    def test_deadline_stops_silent_cpu_child(self):
        with self.assertRaisesRegex(manager.ManagerError, '^DEADLINE_EXCEEDED$'):
            self.invoke('import time\ntime.sleep(10)\n', JOB_DEADLINE=0.02)
        identity = next(v['rendererIdentity'] for v in self.updates if 'rendererIdentity' in v)
        self.assertFalse(manager.is_alive(identity))

    def test_no_export_is_invented_from_a_zero_exit(self):
        result = self.invoke("print('SYNTHETIC_NOT_A_RECEIPT',flush=True)\n")
        self.assertEqual(result['exitCode'], 0)
        self.assertIsNone(result['result'])
        self.assertIsNone(result['firstFailure'])
