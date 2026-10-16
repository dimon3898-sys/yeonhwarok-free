#!/usr/bin/env python3
"""Exact loopback reference harness; original sources and validation helpers stay immutable."""
import argparse
import base64
import hashlib
import importlib.util
import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('preserved_reference_quality_server', ROOT.parent / 'visual-quality-upgrade-v1/serve_quality.py')
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)
parent = quality.parent
IMPORT_MAP = json.dumps({'imports': {
    '/modules/reference_terrain_material_v4.mjs': '/reference/reference_source_material.mjs',
    '/astra/astra_material.mjs': '/reference/reference_source_material.mjs',
    '/quality/quality_material.mjs': '/reference/reference_source_material.mjs',
    '/modules/territory_control_gpu_adapter_v1.mjs': '/reference/gain_territory.mjs',
    '/quality/quality_territory.mjs': '/reference/gain_territory.mjs',
    '/modules/reference_control_frontier_light_v3.mjs': '/reference/frontier_ref2.mjs',
}}, separators=(',', ':'))
IMPORT_MAP_SHA = base64.b64encode(hashlib.sha256(IMPORT_MAP.encode()).digest()).decode()
INDEX = ('<!doctype html><html><head><meta charset="utf-8"><link rel="icon" href="data:,">'
         '<meta name="viewport" content="width=device-width"><style>html,body{margin:0;background:#000}canvas{display:block}</style>'
         '<script type="importmap">' + IMPORT_MAP + '</script>'
         '<script type="module" src="/reference/bootstrap.mjs"></script></head><body></body></html>').encode()
BASELINE = quality.BASELINE | {'/quality/quality_material.mjs', '/quality/quality_territory.mjs', '/modules/reference_control_frontier_light_v3.mjs'}


def route_path(value):
    parsed = urlsplit(value)
    if parsed.query and not (parsed.path in BASELINE and parsed.query == 'baseline'):
        raise ValueError('UNEXPECTED_QUERY')
    return parent.route_path(parsed._replace(query='').geturl())


def make_server(config, exact, *, port=0):
    # Preserve original nested canonical control-intent property order.
    runtime = json.dumps(config['runtimeConfig'], separators=(',', ':')).encode()
    invocation = '({testOnlySoftwareProbe:true})' if config['runtimeConfig'].get('testOnlySoftwareProbe') is True else '()'
    bootstrap = ("import {bootReferenceRuntime} from '/reference/ref2_adapter.mjs';"
                 'window.referenceV2Boot=bootReferenceRuntime' + invocation + ';'
                 'window.astraBoot=window.referenceV2Boot;window.qualityBoot=window.referenceV2Boot;\n').encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            if self.client_address[0] != '127.0.0.1' or self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(403, 'Loopback host required')
                return
            try:
                path = route_path(self.path)
            except ValueError:
                self.send_error(400, 'Unsafe path')
                return
            if path in ('/', '/index.html'):
                body, content_type = INDEX, 'text/html; charset=utf-8'
            elif path == '/reference/bootstrap.mjs':
                body, content_type = bootstrap, 'text/javascript'
            elif path == '/runtime-config.json':
                body, content_type = runtime, 'application/json'
            else:
                record = exact.get(path)
                if record is None:
                    self.send_error(404, 'Not found')
                    return
                try:
                    body = parent.safe_bytes(record['path'])
                    if len(body) != record['bytes'] or hashlib.sha256(body).hexdigest() != record['sha256']:
                        raise ValueError('BOUND_SOURCE_CHANGED')
                except (OSError, ValueError):
                    self.send_error(409, 'Bound source changed')
                    return
                content_type = 'text/javascript' if Path(path).suffix in ('.mjs', '.js') else mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self.send_response(200)
            for key, value in {'Content-Type': content_type, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
                               'X-Content-Type-Options': 'nosniff', 'Cross-Origin-Resource-Policy': 'same-origin',
                               'Content-Security-Policy': "default-src 'none'; script-src 'self' 'sha256-" + IMPORT_MAP_SHA + "'; style-src 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'"}.items():
                self.send_header(key, value)
            self.end_headers()
            if not head:
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--expected-config-sha256', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between0 and65535')
    config, exact = parent.load_config(args.config, args.expected_config_sha256)
    with make_server(config, exact, port=args.port) as server:
        print(json.dumps({'event': 'READY', 'url': f'http://127.0.0.1:{server.server_port}', 'closureFiles': len(exact)}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None
