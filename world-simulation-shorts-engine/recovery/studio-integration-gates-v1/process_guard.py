"""Bounded cleanup of observed, owned descendants, across detached sessions.

Linux pidfds bind every signal to the observed process rather than a reused PID.
Only processes observed under a verified descendant are tracked. This is cleanup
for a local software job, not a cgroup or a promise to observe instantaneous
fork/reparent races between polls. No command lines or environment are read.
"""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import select
import signal
import threading
import time


@dataclass(frozen=True)
class Identity:
    pid: int
    parent_pid: int
    start_ticks: str
    uid: int


def read_identity(pid):
    """Read only process identity metadata; a disappearing process is absent."""
    try:
        directory = Path('/proc') / str(pid)
        uid = directory.stat().st_uid
        fields = (directory / 'stat').read_text().rsplit(') ', 1)[1].split()
        return Identity(int(pid), int(fields[1]), fields[19], uid)
    except (OSError, ValueError, IndexError):
        return None


def same_process(left, right):
    return bool(left and right and (left.pid, left.start_ticks, left.uid) ==
                (right.pid, right.start_ticks, right.uid))


class DescendantGuard:
    """Use around one owned Popen child; cleanup is idempotent and bounded.

    with DescendantGuard(child.pid) as guard:
        try:
            child.wait(timeout=remaining)
        finally:
            guard.cleanup()

    The root must be a direct child of this process. Signals use pinned pidfds,
    including for grandchildren that have moved to separate process groups.
    """
    def __init__(self, root_pid, *, poll_interval=.05, cleanup_timeout=2., max_tracked=512):
        if (type(root_pid) is not int or root_pid <= 1 or root_pid == os.getpid()
                or not math.isfinite(poll_interval) or not .01 <= poll_interval <= 1
                or not math.isfinite(cleanup_timeout) or not .1 <= cleanup_timeout <= 5
                or type(max_tracked) is not int or not 1 <= max_tracked <= 4096):
            raise ValueError('PROCESS_GUARD_LIMITS_INVALID')
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise RuntimeError('PROCESS_GUARD_PIDFD_REQUIRED')
        self.root_pid, self.uid = root_pid, os.getuid()
        self.poll_interval, self.cleanup_timeout, self.max_tracked = poll_interval, cleanup_timeout, max_tracked
        self._lock, self._stop = threading.RLock(), threading.Event()
        self._tracked, self._thread, self._result = {}, None, None

    @property
    def tracked_pids(self):
        with self._lock:
            return tuple(sorted(self._tracked))

    def _pin(self, identity):
        if identity.uid != self.uid or identity.pid in self._tracked:
            return False
        if len(self._tracked) >= self.max_tracked:
            raise RuntimeError('PROCESS_GUARD_TRACK_LIMIT_REACHED')
        try:
            descriptor = os.pidfd_open(identity.pid, 0)
        except ProcessLookupError:
            return False
        if not same_process(identity, read_identity(identity.pid)):
            os.close(descriptor)
            return False
        self._tracked[identity.pid] = (identity, descriptor)
        return True

    def _scan(self):
        with self._lock:
            # Detached processes retain their parent until it exits. Retain
            # already pinned identities after reparenting; never infer an orphan.
            live = {pid: identity for pid, (identity, _) in self._tracked.items()
                    if same_process(identity, read_identity(pid))}
            until = time.monotonic() + .2
            candidates = {}
            for path in Path('/proc').iterdir():
                if time.monotonic() >= until:
                    break
                if not path.name.isdigit():
                    continue
                value = read_identity(int(path.name))
                if value and value.uid == self.uid and value.pid not in self._tracked:
                    candidates[value.pid] = value
            # Repeat to find grandchildren even if /proc enumeration order differs.
            for _ in range(min(len(candidates) + 1, 32)):
                added = False
                for pid, value in tuple(candidates.items()):
                    parent = live.get(value.parent_pid)
                    if parent and same_process(parent, read_identity(parent.pid)) and self._pin(value):
                        live[pid] = value
                        del candidates[pid]
                        added = True
                if not added:
                    break

    def start(self):
        with self._lock:
            if self._thread is not None or self._result is not None:
                raise RuntimeError('PROCESS_GUARD_ALREADY_STARTED')
            root = read_identity(self.root_pid)
            if not root or root.uid != self.uid or root.parent_pid != os.getpid():
                raise RuntimeError('PROCESS_GUARD_OWN_CHILD_REQUIRED')
            if not self._pin(root):
                raise RuntimeError('PROCESS_GUARD_ROOT_CHANGED')
        try:
            self._scan()
        except (OSError, RuntimeError):
            self.cleanup()
            raise
        self._thread = threading.Thread(target=self._watch, name='software-descendant-guard', daemon=True)
        self._thread.start()
        return self

    def _watch(self):
        try:
            while not self._stop.wait(self.poll_interval):
                self._scan()
        except (OSError, RuntimeError) as error:
            # A bounded track failure is reported to the caller, never expanded
            # into an unscoped process search or broad kill command.
            self._watch_error = type(error).__name__
            self._stop.set()

    def cleanup(self):
        with self._lock:
            if self._result is not None:
                return dict(self._result)
        deadline = time.monotonic() + self.cleanup_timeout
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=min(.3, self.cleanup_timeout / 3))
        try:
            self._scan()
        except (OSError, RuntimeError) as error:
            self._watch_error = type(error).__name__
        with self._lock:
            entries = list(self._tracked.items())
            sent, skipped, errors = [], [], []
            for pid, (identity, descriptor) in reversed(entries):
                if not same_process(identity, read_identity(pid)):
                    skipped.append(pid)
                    continue
                try:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                    sent.append(pid)
                except ProcessLookupError:
                    skipped.append(pid)
                except OSError as error:
                    errors.append(type(error).__name__)
            remaining = []
            for pid, (_, descriptor) in entries:
                wait = max(0, deadline - time.monotonic())
                if not select.select([descriptor], [], [], wait)[0]:
                    remaining.append(pid)
            for _, (_, descriptor) in entries:
                os.close(descriptor)
            self._result = {'tracked': len(entries), 'signalsSent': sent, 'skipped': skipped,
                            'remaining': remaining, 'errors': errors,
                            'observationError': getattr(self, '_watch_error', None)}
            return dict(self._result)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.cleanup()
