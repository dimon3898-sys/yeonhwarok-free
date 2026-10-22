"""Free CPU process cleanup tests; no browser, renderer or GPU is started."""
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('g1_guard_review', HERE / 'process_guard.py')
guard_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard_module
spec.loader.exec_module(guard_module)
Guard = guard_module.DescendantGuard


def stop_child(child):
    if child.poll() is None:
        child.kill()
    child.wait(timeout=3)


class ProcessGuardTests(unittest.TestCase):
    def test_detached_grandchild_is_pinned_before_reparenting_and_stopped(self):
        child_code = "import time; time.sleep(30)"
        root_code = (
            "import subprocess,sys,time,json; "
            "c=subprocess.Popen([sys.executable,'-c'," + repr(child_code) + "],start_new_session=True); "
            "print(json.dumps({'pid':c.pid}),flush=True); time.sleep(30)"
        )
        root = subprocess.Popen([sys.executable, '-c', root_code], stdout=subprocess.PIPE, text=True)
        detached_pid, detached_fd = None, None
        try:
            with Guard(root.pid, poll_interval=.01, cleanup_timeout=1) as guard:
                detached_pid = json.loads(root.stdout.readline())['pid']
                detached_fd = os.pidfd_open(detached_pid)
                deadline = time.monotonic() + 2
                while detached_pid not in guard.tracked_pids and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertIn(detached_pid, guard.tracked_pids)
                self.assertEqual(os.getpgid(detached_pid), detached_pid)
                root.kill()
                root.wait(timeout=3)
                result = guard.cleanup()
                self.assertIn(detached_pid, result['signalsSent'])
                self.assertEqual(result['remaining'], [])
                self.assertTrue(select.select([detached_fd], [], [], 1)[0])
                self.assertEqual(guard.cleanup(), result)
        finally:
            stop_child(root)
            root.stdout.close()
            if detached_fd is not None:
                if not select.select([detached_fd], [], [], 0)[0]:
                    signal.pidfd_send_signal(detached_fd, signal.SIGKILL)
                os.close(detached_fd)

    def test_unrelated_same_uid_process_is_not_signalled(self):
        root = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            with Guard(root.pid, cleanup_timeout=1) as guard:
                time.sleep(.06)
                self.assertNotIn(unrelated.pid, guard.tracked_pids)
                result = guard.cleanup()
                self.assertNotIn(unrelated.pid, result['signalsSent'])
                self.assertIsNone(unrelated.poll())
        finally:
            stop_child(root)
            stop_child(unrelated)

    def test_changed_start_identity_never_receives_signal(self):
        root = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            guard = Guard(root.pid, cleanup_timeout=.1).start()
            original_read = guard_module.read_identity
            original_identity = original_read(root.pid)

            def reused_pid(pid):
                if pid == root.pid:
                    return guard_module.Identity(pid, original_identity.parent_pid,
                        str(int(original_identity.start_ticks) + 1), original_identity.uid)
                return original_read(pid)

            with patch.object(guard_module, 'read_identity', side_effect=reused_pid), \
                    patch.object(guard_module.signal, 'pidfd_send_signal') as send:
                result = guard.cleanup()
                send.assert_not_called()
            self.assertIn(root.pid, result['skipped'])
            self.assertIsNone(root.poll())
        finally:
            stop_child(root)

    def test_rejects_self_and_non_child_roots(self):
        with self.assertRaisesRegex(ValueError, 'PROCESS_GUARD_LIMITS_INVALID'):
            Guard(os.getpid())
        with self.assertRaisesRegex(RuntimeError, 'PROCESS_GUARD_OWN_CHILD_REQUIRED'):
            Guard(os.getppid()).start()

    def test_rejects_unbounded_polling_and_cleanup_limits(self):
        for settings in ({'poll_interval': 0}, {'poll_interval': 2}, {'cleanup_timeout': 10}, {'max_tracked': 0}):
            with self.subTest(settings=settings):
                with self.assertRaisesRegex(ValueError, 'PROCESS_GUARD_LIMITS_INVALID'):
                    Guard(999999999, **settings)


if __name__ == '__main__':
    unittest.main()
