#!/usr/bin/env python3
"""TEST ONLY: ephemeral loopback TLS fixture for the mobile Chromium probe.

The dependency-injected controller cannot start rendering. No GPU, external
service, operator credential, production owner code, or public TLS endpoint is
used. A fresh private directory and self-signed localhost certificate are
destroyed when this process exits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class NoRenderController:
    """UI fixture only; every production operation is denied explicitly."""

    def __init__(self, **_kwargs):
        pass

    def __getattr__(self, _name):
        def blocked(*_args, **_kwargs):
            from frozen import load_originals
            raise load_originals().server.SecurityError(
                'TEST_FIXTURE_RENDERING_DISABLED', 'CPU test fixture cannot render.', 503)
        return blocked


def deny_gpu():
    raise RuntimeError('TEST_FIXTURE_RENDERING_DISABLED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--info', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.info.is_absolute() or args.info.is_symlink():
        raise SystemExit('TEST_INFO_PRIVATE_PATH_REQUIRED')
    args.info.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.info.parent, 0o700)
    from frozen import load_originals
    from https_server import Application
    original = load_originals().server
    with tempfile.TemporaryDirectory(prefix='world-studio-https-test-') as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        state = root / 'state'
        state.mkdir(mode=0o700)
        exports = root / 'exports'
        exports.mkdir(mode=0o700)
        owner = state / 'owner-code'
        owner.write_text(secrets.token_urlsafe(32), encoding='ascii')
        owner.chmod(0o600)
        cert, key = root / 'localhost.crt', root / 'localhost.key'
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-sha256',
            '-nodes', '-days', '1', '-keyout', str(key), '-out', str(cert),
            '-subj', '/CN=studio-ci.invalid', '-addext', 'subjectAltName=DNS:studio-ci.invalid',
        ], check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=30)
        key.chmod(0o600)
        # The selected test-only TLS port is the actual origin, never inferred
        # from untrusted Host, Origin, or forwarded request headers.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        app = Application(state, owner, exports, 'sha256:' + 'a' * 64,
            port=port, controller_factory=NoRenderController, gpu_check=deny_gpu)
        server = original.StudioHTTPServer(('127.0.0.1', port), app.handler())
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert), str(key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        info = {'schema': 'WORLD_ENGINE_TEST_TLS_FIXTURE_V1',
            'origin': f'https://studio-ci.invalid:{port}', 'url': f'https://studio-ci.invalid:{port}',
            'ownerFile': str(owner), 'scope': 'CPU_TEST_ONLY',
            'gpuRenderingVerified': False, 'renderAllowed': False}
        descriptor = os.open(args.info, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as target:
            json.dump(info, target, sort_keys=True)
            target.write('\n')
        stopping = threading.Event()

        def stop(_signal, _frame):
            if not stopping.is_set():
                stopping.set()
                threading.Thread(target=server.shutdown, daemon=True).start()

        for name in (signal.SIGTERM, signal.SIGINT):
            signal.signal(name, stop)
        print(json.dumps({'fixture': 'READY', 'scope': 'CPU_TEST_ONLY',
            'gpuRenderingVerified': False}), flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        finally:
            server.server_close()
            # Only our own one-time info pointer is removed; no user files.
            if args.info.is_file() and not args.info.is_symlink():
                args.info.unlink()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
