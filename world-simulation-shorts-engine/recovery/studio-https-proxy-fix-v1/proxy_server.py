#!/usr/bin/env python3
"""Explicit HTTPS-edge adapter; authentication, CSRF, jobs and GPU stay frozen."""
import argparse
import json
import os
from pathlib import Path
import re
from parent import modules, load_file
from proxy_policy import FixedHTTPSProxyPolicy, normalize_headers, request_diagnostics

HERE = Path(__file__).resolve().parent
parent = modules()
original = parent.server.original
_audit_rate = parent.security.RateLimiter()


class ProxySetupCore(parent.server.SetupCore):
    def _request(self, headers, peer_ip, request_origin):
        # The inherited begin authenticates the owner before reaching here.
        # The candidate is an explicitly confirmed value, never inferred from
        # Forwarded, XFP, XFH or an arbitrary request authority.
        headers = normalize_headers(headers, request_origin, local_port=self.port,
                                    method='POST', peer_ip=peer_ip)
        return super()._request(headers, peer_ip, request_origin)


class Application(parent.server.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reopen the existing private auth records through the inherited class.
        # No credential, signing key, file or pending job is reset by this step.
        self.core = ProxySetupCore(self.state_root, self.core.owner_file, port=self.port)
        if self.normal is not None:
            self.core.bind_production_sessions(self.normal.sessions)
        self._sync_normal()

    def _sync_normal(self):
        super()._sync_normal()
        if self.normal is not None:
            self.normal.policy = FixedHTTPSProxyPolicy([self.normal.config.public_origin],
                                                        local_port=self.port, environ={})

    def handler(self):
        base = super().handler()
        app = self
        class Handler(base):
            def _dispatch(self):
                try:
                    return super()._dispatch()
                except parent.security.SecurityError as error:
                    if _audit_rate.allow('all-proxy-errors', count=20, window=60) and error.code in {'INVALID_HOST', 'INVALID_ORIGIN', 'INVALID_FORWARDED_HEADERS',
                                      'STUDIO_SETUP_SAME_ORIGIN_REQUIRED', 'STUDIO_ORIGIN_MISMATCH'}:
                        # Closed enums and comparison booleans only. Never log
                        # raw headers, cookies, credentials, path/query or body.
                        facts = request_diagnostics(self.headers, app.core.public_origin)
                        print(json.dumps({'schema': 'WORLD_ENGINE_PROXY_REQUEST_DIAGNOSTIC_V1',
                            'stage': 'REQUEST_POLICY', 'errorCode': error.code, 'facts': facts,
                            'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
                    raise
        return Handler


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True, type=Path)
    parser.add_argument('--owner-file', required=True, type=Path)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    load_file('_proxy_server_manifest', HERE / 'manifest.py').verify_sources()
    app = Application(args.state_root, args.owner_file, args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'), args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server = original.StudioHTTPServer((args.host, args.port), app.handler())
    print(json.dumps({'stage': 'STUDIO_PROXY_WEB_STARTED',
        'mode': 'CONFIGURED' if app.normal else 'SETUP', 'renderAllowed': False,
        'gpuRenderingVerified': False, 'actualGcubeProxyHeadersVerified': False}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = getattr(error, 'code', None) or str(error)
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_PROXY_SERVER_FAILED'
        print(json.dumps({'stage': 'STUDIO_PROXY_WEB_FAILED', 'errorCode': code,
            'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(1)
