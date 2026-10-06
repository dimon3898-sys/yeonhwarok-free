"""Run the unchanged gateway in a bounded, named compute container.

This is an optional provider adapter, not the Codespaces startup replacement.
The control-plane writes a trusted tunnel origin after allocating a sandbox.
No user shell command or request body is executed. No provider credential is
injected. Provider volume durability must pass a live restart acceptance test.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

APP = Path(__file__).resolve().parents[2]
ORIGIN_FILE = Path('/tmp/world-engine-trusted-tunnel.json')
HEARTBEAT = APP / 'deployment/runtime/portal-heartbeat'
BUSY = frozenset({'queued', 'rendering', 'interrupted'})
FINISHED = frozenset({'complete', 'failed', 'cancelled'})


def trusted_tunnel(value):
    if (not isinstance(value, str) or not value.isascii() or
            re.search(r'[\s\\]', value) or '?' in value or '#' in value):
        raise ValueError('UNTRUSTED_PROVIDER_TUNNEL')
    p = urlsplit(value)
    if (p.scheme != 'https' or p.username or p.password or p.port not in (None, 443)
            or p.query or p.fragment or p.path not in ('', '/')
            or not p.hostname or not p.hostname.endswith('.modal.host')):
        raise ValueError('UNTRUSTED_PROVIDER_TUNNEL')
    return 'https://' + p.hostname


def configure(value):
    origin = trusted_tunnel(value)
    fd = os.open(ORIGIN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'origin': origin}, f)
        f.flush()
        os.fsync(f.fileno())


def busy_jobs(runtime):
    """Unknown/unreadable work is busy, never an excuse to kill it."""
    root = Path(runtime) / 'jobs'
    if not root.exists():
        return False
    for p in root.glob('job_*.json'):
        if re.fullmatch(r'job_[a-f0-9]{12}\.failure\.json', p.name):
            continue  # A failure diagnostic is not a runnable ticket.
        try:
            if p.is_symlink() or p.stat().st_size > 1024 * 1024:
                return True
            record = json.loads(p.read_text())
            if not isinstance(record, dict) or record.get('status') not in FINISHED:
                return True
        except (OSError, ValueError, TypeError):
            return True
    return False


def prepare_owner(runtime, password):
    if not isinstance(password, str) or not 16 <= len(password) <= 512:
        raise ValueError('OWNER_PASSWORD_REQUIRED')
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    p = runtime / 'owner-code.txt'
    if p.exists() or p.is_symlink():
        if p.is_symlink() or not p.is_file() or p.stat().st_mode & 0o077:
            raise ValueError('UNSAFE_OWNER_FILE')
        import hmac
        if not hmac.compare_digest(p.read_text().strip(), password):
            raise ValueError('OWNER_PASSWORD_CHANGED_EXPLICIT_MIGRATION_REQUIRED')
    else:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(password + '\n')
            f.flush()
            os.fsync(f.fileno())
    return p


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure-origin')
    parser.add_argument('--touch', action='store_true')
    args = parser.parse_args(argv)
    if args.configure_origin:
        configure(args.configure_origin)
        return 0
    if args.touch:
        HEARTBEAT.touch(exist_ok=True)
        return 0
    # A new provider image has no Codespaces identity. Never alter the existing
    # user's Codespaces environment or weaken its exact-Origin checks.
    if os.environ.get('CODESPACE_NAME'):
        raise ValueError('WRONG_RUNTIME')
    runtime = APP / 'deployment/runtime'
    owner = prepare_owner(runtime, os.environ.get('WORLD_OWNER_PASSWORD'))
    deadline = time.monotonic() + 60
    while not ORIGIN_FILE.exists():
        if time.monotonic() >= deadline:
            raise ValueError('TRUSTED_ORIGIN_NOT_CONFIGURED')
        time.sleep(.25)
    origin = trusted_tunnel(json.loads(ORIGIN_FILE.read_text())['origin'])
    HEARTBEAT.touch(exist_ok=True)
    argv = [sys.executable, '-m', 'deployment.mobile_server', '--host', '0.0.0.0',
            '--port', '7860', '--internal-port', '7861', '--state-root', str(runtime),
            '--access-file', str(owner), '--public-origin', origin,
            '--maximum-job-seconds', '13800', '--max-duration', '20']
    child_env = {k: v for k, v in os.environ.items()
                 if k not in {'WORLD_OWNER_PASSWORD', 'WORLD_PORTAL_SESSION_KEY'}}
    child = subprocess.Popen(argv, cwd=APP, env=child_env)
    stopping = False
    def stop(*unused):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while child.poll() is None and not stopping:
            age = time.time() - HEARTBEAT.stat().st_mtime
            if age > 900 and not busy_jobs(runtime):
                break
            time.sleep(2)
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=25)
            except subprocess.TimeoutExpired:
                # Only the exact child started above. Its checkpoint remains.
                child.kill()
                child.wait(timeout=5)
    # fsync is local durability, not a substitute for a provider Volume commit.
    # Modal's background/on-exit mount commit still needs live acceptance.
    return child.returncode or 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError):
        print('World Engine compute startup blocked; check private deployment configuration.', file=sys.stderr)
        raise SystemExit(2)
