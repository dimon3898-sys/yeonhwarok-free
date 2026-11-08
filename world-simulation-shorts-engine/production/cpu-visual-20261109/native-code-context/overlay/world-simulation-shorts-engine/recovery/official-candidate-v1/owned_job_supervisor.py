"""One deadline for owned subprocesses; caller supplies the existing DescendantGuard.

No process discovery or environment capture. Only start_new_session children created
here are signalled through pinned pidfds, never numeric PID/PGID. The original guard supplies descendant escape/reparent cleanup.
"""
import os
import signal
import subprocess
import time
import threading
import selectors


class BoundedPipeCollector:
    """Read only owned pipes. Never return truncated output on overflow.

    2 MiB matches the existing capture execute maxBuffer. Limits apply to each
    stream and to their combined bytes; a read allocates at most 64 KiB extra.
    """
    def __init__(self, child, *, per_stream_bytes=2*1024**2, combined_bytes=2*1024**2,
                 selector_factory=selectors.DefaultSelector, read=os.read):
        if type(per_stream_bytes) is not int or type(combined_bytes) is not int or min(per_stream_bytes, combined_bytes)<=0:
            raise ValueError('UP2_OUTPUT_LIMIT_INVALID')
        self.child, self.read = child, read
        self.per_stream_bytes, self.combined_bytes = per_stream_bytes, combined_bytes
        self.selector = selector_factory()
        self.buffers = {'stdout': bytearray(), 'stderr': bytearray()}
        self.open_streams, self.total = 0, 0
        try:
            for name in self.buffers:
                stream = getattr(child, name)
                self.selector.register(stream.fileno(), selectors.EVENT_READ, name)
                self.open_streams += 1
        except BaseException:
            self.selector.close()
            raise

    def read_available(self, timeout):
        for key, _ in self.selector.select(timeout):
            chunk = self.read(key.fd, 65536)
            if not chunk:
                self.selector.unregister(key.fd)
                self.open_streams -= 1
                continue
            buffer = self.buffers[key.data]
            if len(buffer)+len(chunk)>self.per_stream_bytes or self.total+len(chunk)>self.combined_bytes:
                raise RuntimeError('UP2_CHILD_OUTPUT_LIMIT_EXCEEDED')
            buffer.extend(chunk)
            self.total += len(chunk)
        if self.open_streams == 0 and self.child.poll() is not None:
            return bytes(self.buffers['stdout']), bytes(self.buffers['stderr'])
        return None

    def close(self):
        self.selector.close()


class OwnedJobSupervisor:
    def __init__(self, *, deadline, guard_factory, cancelled=lambda: False,
                 clock=time.monotonic, popen=subprocess.Popen,
                 pin_process=os.pidfd_open, signal_process=signal.pidfd_send_signal, close_process=os.close,
                 collector_factory=BoundedPipeCollector,
                 term_seconds=1., kill_seconds=2., reserve_seconds=5.):
        if deadline <= clock() or min(term_seconds, kill_seconds, reserve_seconds) <= 0:
            raise ValueError('UP2_SUPERVISOR_DEADLINE_INVALID')
        self.deadline, self.guard_factory, self.cancelled = deadline, guard_factory, cancelled
        self.clock, self.popen = clock, popen
        self.pin_process, self.signal_process, self.close_process = pin_process, signal_process, close_process
        self.collector_factory = collector_factory
        self.term_seconds, self.kill_seconds, self.reserve_seconds = term_seconds, kill_seconds, reserve_seconds
        self.records, self.active = [], None
        self.failed = False

    def check(self):
        if self.failed:
            raise RuntimeError('UP2_SUPERVISOR_PREVIOUS_FAILURE')
        if self.cancelled():
            raise RuntimeError('UP2_SOFTWARE_REVIEW_CANCELLED')
        if self.clock() >= self.deadline - self.reserve_seconds:
            raise RuntimeError('UP2_SOFTWARE_REVIEW_DEADLINE_EXCEEDED')

    def _signal(self, pin, sig, row):
        if pin is None:
            if 'CHILD_PIDFD_UNAVAILABLE' not in row['errors']:
                row['errors'].append('CHILD_PIDFD_UNAVAILABLE')
            return
        try:
            self.signal_process(pin, sig)
            row['signals'].append(sig.name)
        except ProcessLookupError:
            pass
        except OSError as error:
            row['errors'].append(type(error).__name__)

    def _wait(self, child, seconds):
        budget = min(seconds, max(0., self.deadline - self.clock()))
        if budget <= 0:
            return child.poll() is not None
        try:
            child.wait(timeout=budget)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _cleanup(self, child, guard, row, pin):
        # A reaped PID/PGID may have been reused. Never signal by numeric ID.
        # The root pidfd is pinned before any wait/reap; the existing guard owns
        # all observed descendant pidfds, including detached descendants.
        exited = child.poll() is not None
        if not exited:
            self._signal(pin, signal.SIGTERM, row)
            exited = self._wait(child, self.term_seconds)
        if not exited:
            self._signal(pin, signal.SIGKILL, row)
            exited = self._wait(child, self.kill_seconds)
        row['leaderExitConfirmed'] = exited
        # Bound waiting for the preserved guard, never pretend a stuck cleanup
        # thread was killed. Its incomplete state prevents any success receipt.
        outcome = {}
        def finish_guard():
            try:
                outcome['descendants'] = guard.cleanup()
                guard.__exit__(None, None, None)
            except BaseException as error:
                outcome['error'] = type(error).__name__
        thread = threading.Thread(target=finish_guard, daemon=True)
        thread.start()
        thread.join(timeout=max(0., self.deadline-self.clock()))
        descendants = outcome.get('descendants')
        row['descendants'] = descendants
        observed = (isinstance(descendants, dict) and 'remaining' in descendants
                    and 'errors' in descendants and 'observationError' in descendants)
        clear = (not thread.is_alive() and 'error' not in outcome and observed
                 and not any(descendants[k] for k in ('remaining', 'errors', 'observationError')))
        if thread.is_alive():
            row['errors'].append('DESCENDANT_CLEANUP_DEADLINE')
        if 'error' in outcome:
            row['errors'].append(outcome['error'])
        for stream in (child.stdout, child.stderr):
            if stream is not None:
                stream.close()
        row['state'] = 'COMPLETE' if exited and clear and not row['errors'] else 'INCOMPLETE'
        self.active = None
        return row

    def run(self, argv, *, cwd=None, text=False, timeout=None, capture_output=True, check=False):
        self.check()
        child = self.popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=False, start_new_session=True)
        self.active = child
        row = {'state': 'PENDING', 'leaderExitConfirmed': False, 'signals': [], 'errors': []}
        self.records.append(row)
        guard, pin, collector = None, None, None
        error, result = None, None
        try:
            # Popen owns this unreaped child. Pin before pipe reads/poll/wait.
            pin = self.pin_process(child.pid, 0)
            guard = self.guard_factory(child.pid)
            guard.__enter__()
            collector = self.collector_factory(child)
            stage_deadline = min(self.deadline-self.reserve_seconds,
                                 self.clock()+timeout if timeout is not None else self.deadline)
            while True:
                self.check()
                remaining = stage_deadline-self.clock()
                if remaining <= 0:
                    raise RuntimeError('UP2_SOFTWARE_REVIEW_DEADLINE_EXCEEDED')
                output = collector.read_available(timeout=min(.2, remaining))
                if output is not None:
                    stdout, stderr = output
                    if text:
                        stdout, stderr = stdout.decode('utf-8'), stderr.decode('utf-8')
                    result = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
                    break
        except BaseException as caught:
            error = caught
        finally:
            if guard is None:
                # No descendant ownership evidence. Only the exact pinned root
                # may be signalled; missing pidfd never falls back to PID/PGID.
                exited = child.poll() is not None
                if not exited:
                    self._signal(pin, signal.SIGTERM, row)
                    exited = self._wait(child, self.term_seconds)
                if not exited:
                    self._signal(pin, signal.SIGKILL, row)
                    exited = self._wait(child, self.kill_seconds)
                row['leaderExitConfirmed'] = exited
                row['state'] = 'INCOMPLETE'
                row['errors'].append('DESCENDANT_GUARD_UNAVAILABLE')
                self.active = None
            else:
                try:
                    self._cleanup(child, guard, row, pin)
                except BaseException as caught:
                    row['state'] = 'INCOMPLETE'
                    row['errors'].append(type(caught).__name__)
                    error = error or caught
                    self.active = None
            if collector is not None:
                try:
                    collector.close()
                except OSError as caught:
                    row['state'] = 'INCOMPLETE'
                    row['errors'].append(type(caught).__name__)
                    error = error or caught
            if pin is not None:
                try:
                    self.close_process(pin)
                except OSError as caught:
                    row['state'] = 'INCOMPLETE'
                    row['errors'].append(type(caught).__name__)
                    error = error or caught
            self.failed = error is not None or row['state'] != 'COMPLETE'
        if error is not None:
            raise error
        if row['state'] != 'COMPLETE':
            raise RuntimeError('UP2_WORKER_CLEANUP_INCOMPLETE')
        if result.returncode:
            self.failed = True
            raise RuntimeError('UP2_NATIVE_CHILD_FAILED')
        self.check()
        return result

    def assert_complete(self):
        self.check()
        if self.active is not None or any(r['state'] != 'COMPLETE' for r in self.records):
            raise RuntimeError('UP2_WORKER_CLEANUP_INCOMPLETE')
        return {'state': 'COMPLETE', 'children': self.records}
