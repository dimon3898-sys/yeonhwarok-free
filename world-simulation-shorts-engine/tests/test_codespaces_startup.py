"""Startup identity and preservation checks; no real server, render, or signal."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deployment import start_codespace as start
from deployment.security import SecurityError


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='world-startup-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root/'app'
        self.state = self.app/'deployment/runtime/isolated'
        self.state.mkdir(parents=True)
        self.proc = self.root/'proc'
        self.proc.mkdir()
        self.access = self.state/'owner-code.txt'
        self.access.write_text('private-test-owner-code\n')
        self.access.chmod(0o600)
        (self.state/'projects').mkdir()
        (self.state/'projects/preserved.txt').write_text('existing project bytes')
        (self.state/'server.log').write_text('existing append log\n')
        self.args = SimpleNamespace(port=27860, internal_port=27861)
        for name, value in [('APP', self.app), ('REPO', self.root), ('PROC_ROOT', self.proc)]:
            p = patch.object(start, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {}, clear=True); p.start(); self.addCleanup(p.stop)
        p = patch.object(start, '_runtime_preflight', return_value=28); p.start(); self.addCleanup(p.stop)
        p = patch.object(start, '_source_fingerprint', return_value='current-fingerprint'); p.start(); self.addCleanup(p.stop)
        self.options = ['--state-root', str(self.state), '--port', '27860', '--internal-port', '27861']

    def command(self):
        return [str(Path(sys.executable).absolute()), '-m', 'deployment.mobile_server',
                '--state-root', str(self.state), '--access-file', str(self.access),
                '--host', '0.0.0.0', '--port', '27860', '--internal-port', '27861']

    def proc_record(self, pid=1234, ticks=9876, argv=None, executable=None):
        p = self.proc/str(pid); p.mkdir(exist_ok=True)
        (p/'cmdline').write_bytes(b'\0'.join(x.encode() for x in (argv or self.command()))+b'\0')
        fields = ['S']+['0']*18+[str(ticks)]+['0']*15
        (p/'stat').write_text(f'{pid} (python server) '+ ' '.join(fields))
        if not (p/'exe').exists():
            (p/'exe').symlink_to(executable or Path(sys.executable).resolve())
        return start._snapshot(pid)

    def installed(self, fingerprint='current-fingerprint', marker=True):
        record = self.proc_record()
        (self.state/'server.pid').write_text('1234\n')
        if marker:
            (self.state/'startup-ready.json').write_text(json.dumps({
                'format':'world-codespaces-ready-v1', 'pid':1234, 'start_ticks':9876,
                'source_fingerprint':fingerprint}))
        return record

    def run_main(self, extra=None):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(start.main(self.options+(extra or [])), 0)
        return json.loads(output.getvalue())

    def payloads(self):
        return {p.relative_to(self.state).as_posix():p.read_bytes()
                for p in self.state.rglob('*') if p.is_file()}

    def spawn_mocks(self):
        child = Mock(pid=5678)
        child.poll.return_value = None
        ready = self.proc_record(pid=5678, ticks=4321)
        return child, ready

    def test_same_healthy_fingerprint_reuses_without_changes_or_signals(self):
        self.installed(); before = self.payloads()
        with patch.object(start, '_healthy', return_value=True), \
             patch.object(start, '_stop_owned') as stop, patch.object(start.subprocess, 'Popen') as spawn:
            report = self.run_main()
        self.assertEqual(report['status'], 'already_running')
        self.assertEqual(self.payloads(), before)
        stop.assert_not_called(); spawn.assert_not_called()

    def test_missing_marker_refreshes_exact_owned_idle_server(self):
        self.installed(marker=False)
        child, ready = self.spawn_mocks()
        before = self.payloads()
        with patch.object(start, '_stop_owned') as stop, patch.object(start, '_ports_free'), \
             patch.object(start.subprocess, 'Popen', return_value=child), \
             patch.object(start, '_wait_ready', return_value=ready):
            report = self.run_main()
        self.assertEqual(report['status'], 'refreshed'); stop.assert_called_once()
        marker = json.loads((self.state/'startup-ready.json').read_text())
        self.assertEqual(marker['source_fingerprint'], 'current-fingerprint')
        self.assertEqual(marker['pid'], 5678)
        self.assertEqual((self.state/'server.pid').read_text().strip(), '5678')
        for name in ('owner-code.txt', 'projects/preserved.txt', 'server.log'):
            self.assertEqual((self.state/name).read_bytes(), before[name])
        self.assertEqual((self.state/'server.log').stat().st_mode & 0o777, 0o600)

    def test_explicit_refresh_uses_pidfd_sigterm_only(self):
        process = self.installed()
        with patch.object(os, 'pidfd_open', return_value=81) as pinned, \
             patch.object(signal, 'pidfd_send_signal') as sent, \
             patch.object(start.select, 'select', return_value=([81], [], [])) as wait, \
             patch.object(os, 'close') as close:
            start._stop_owned(process, self.state, self.args)
        pinned.assert_called_once_with(1234)
        sent.assert_called_once_with(81, signal.SIGTERM)
        wait.assert_called_once_with([81], [], [], 15)
        close.assert_called_once_with(81)

    def test_unknown_pid_or_substring_match_is_never_stopped(self):
        for argv in ([sys.executable, '-m', 'other.deployment.mobile_server', '--state-root', str(self.state)],
                     self.command()[:-1]+['9999'],
                     [sys.executable, '-m', 'deployment.mobile_server']+self.command()[3:]+['--worker-ticket', 'x']):
            with self.subTest(argv=argv):
                self.proc_record(argv=argv)
                (self.state/'server.pid').write_text('1234\n')
                before = self.payloads()
                with patch.object(start, '_stop_owned') as stop, patch.object(start.subprocess, 'Popen') as spawn:
                    with self.assertRaises(start.StartupError) as error:
                        start.main(self.options+['--refresh'])
                self.assertEqual(error.exception.code, 'PROCESS_NOT_OWNED')
                stop.assert_not_called(); spawn.assert_not_called(); self.assertEqual(before, self.payloads())

    def test_interpreter_and_proc_executable_must_both_match(self):
        self.proc_record(argv=['/different/python']+self.command()[1:])
        with self.assertRaises(start.StartupError):
            start._owned_process(1234, self.state, self.args)
        (self.proc/'1234/exe').unlink()
        self.proc_record(executable='/bin/sh')
        with self.assertRaises(start.StartupError):
            start._owned_process(1234, self.state, self.args)

    def test_reused_pid_marker_or_identity_recheck_never_gets_signal(self):
        old = self.installed()
        self.proc_record(ticks=9877)
        with patch.object(start, '_stop_owned') as stop:
            with self.assertRaises(start.StartupError) as error:
                start.main(self.options+['--refresh'])
        self.assertEqual(error.exception.code, 'PROCESS_CHANGED'); stop.assert_not_called()
        with patch.object(os, 'pidfd_open', return_value=81), \
             patch.object(signal, 'pidfd_send_signal') as send, patch.object(os, 'close'):
            with self.assertRaises(start.StartupError):
                start._stop_owned(old, self.state, self.args)
        send.assert_not_called()

    def test_queued_rendering_or_unreadable_receipts_refuse_refresh(self):
        self.installed()
        jobs = self.state/'jobs'; jobs.mkdir()
        for status in ('queued', 'rendering', 'corrupt'):
            (jobs/'job_000000000001.json').write_text('{' if status == 'corrupt' else json.dumps({
                'job_id':'job_000000000001', 'status':status}))
            before = self.payloads()
            with self.subTest(status=status), patch.object(start, '_stop_owned') as stop, \
                 patch.object(start.subprocess, 'Popen') as spawn:
                with self.assertRaises(start.StartupError) as error:
                    start.main(self.options+['--refresh'])
                self.assertEqual(error.exception.code, 'JOB_RECEIPT_UNREADABLE' if status=='corrupt' else 'ACTIVE_JOBS')
                stop.assert_not_called(); spawn.assert_not_called(); self.assertEqual(before, self.payloads())

    def test_active_worker_refuses_even_if_receipt_failed(self):
        self.installed()
        self.proc_record(pid=4321, argv=[sys.executable, str(self.app/'deployment/mobile_server.py'),
                         '--worker-ticket', str(self.state/'jobs/job_000000000001.json'),
                         '--state-root', str(self.state)])
        with patch.object(start, '_stop_owned') as stop, patch.object(start.subprocess, 'Popen') as spawn:
            with self.assertRaises(start.StartupError) as error:
                start.main(self.options+['--refresh'])
        self.assertEqual(error.exception.code, 'ACTIVE_WORKER'); stop.assert_not_called(); spawn.assert_not_called()

    def test_readable_failure_diagnostic_without_job_id_does_not_block_refresh(self):
        self.installed()
        jobs = self.state/'jobs'; jobs.mkdir()
        failure = jobs/'job_000000000001.failure.json'
        failure.write_text(json.dumps({'error': {'code':'RENDER_FAILED'}}))
        (jobs/'job_000000000001.json').write_text(json.dumps({
            'job_id':'job_000000000001', 'status':'failed'}))
        before = failure.read_bytes()
        start._assert_idle(self.state)
        self.assertEqual(failure.read_bytes(), before)

    def test_stale_fingerprint_failed_readiness_preserves_previous_records(self):
        self.installed(fingerprint='older-source'); before = self.payloads()
        child, ready = self.spawn_mocks()
        with patch.object(start, '_stop_owned') as stop, patch.object(start, '_ports_free'), \
             patch.object(start.subprocess, 'Popen', return_value=child), \
             patch.object(start, '_wait_ready', side_effect=start.StartupError('READINESS_TIMEOUT', 'failed')):
            with self.assertRaises(start.StartupError) as error:
                start.main(self.options)
        self.assertEqual(error.exception.code, 'READINESS_TIMEOUT')
        self.assertEqual(before, self.payloads())
        self.assertEqual(stop.call_count, 2)  # Old idle process and exact-owned new idle child only.

    def test_shutdown_timeout_never_force_kills_or_spawns(self):
        process = self.installed()
        with patch.object(os, 'pidfd_open', return_value=81), \
             patch.object(signal, 'pidfd_send_signal') as send, \
             patch.object(start.select, 'select', return_value=([], [], [])), patch.object(os, 'close'):
            with self.assertRaises(start.StartupError) as error:
                start._stop_owned(process, self.state, self.args)
        self.assertEqual(error.exception.code, 'SHUTDOWN_TIMEOUT')
        send.assert_called_once_with(81, signal.SIGTERM)

    def test_origin_domain_fallback_and_invalid_environment(self):
        child, ready = self.spawn_mocks()
        with patch.dict(os.environ, {'CODESPACE_NAME':'brave-space'}), \
             patch.object(start, '_ports_free'), patch.object(start.subprocess, 'Popen', return_value=child) as spawn, \
             patch.object(start, '_wait_ready', return_value=ready):
            self.run_main()
        command = spawn.call_args.args[0]
        self.assertEqual(command[-2:], ['--public-origin', 'https://brave-space-27860.app.github.dev'])
        before = self.payloads()
        with patch.dict(os.environ, {'CODESPACE_NAME':'brave-space', 'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'wrong.example'}), \
             patch.object(start.subprocess, 'Popen') as spawn:
            with self.assertRaises(SecurityError) as error:
                start.main(self.options)
        self.assertEqual(error.exception.code, 'INVALID_CODESPACES_ORIGIN')
        spawn.assert_not_called(); self.assertEqual(before, self.payloads())

    def test_actual_proc_stat_cpu_fields_may_change_without_reusing_pid(self):
        record = self.proc_record()
        original = (self.proc/'1234/stat').read_text()
        changed = original.replace(' S 0 ', ' R 7 ', 1)
        real_read = Path.read_text
        count = [0]
        def read(path, *a, **kw):
            if path == self.proc/'1234/stat':
                count[0] += 1
                return original if count[0] == 1 else changed
            return real_read(path, *a, **kw)
        with patch.object(Path, 'read_text', new=read):
            self.assertEqual(start._snapshot(1234), record)


if __name__ == '__main__':
    unittest.main()
