#!/usr/bin/env python3
"""Exact SHA-bound, read-only ASTRA browser closure on loopback. No render HTTP API."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parents[1]
REPO = ENGINE.parent
SHA = re.compile(r"[a-f0-9]{64}\Z")
LIMIT = 128 * 1024 * 1024
IMPORT_MAP = json.dumps({'imports': {'/modules/reference_terrain_material_v4.mjs': '/astra/astra_material.mjs'}}, separators=(',', ':'))
IMPORT_MAP_SHA = base64.b64encode(hashlib.sha256(IMPORT_MAP.encode()).digest()).decode()
INDEX = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
         '<link rel="icon" href="data:,">'
         '<style>html,body{margin:0;background:#000}canvas{display:block}</style>'
         '<script type="importmap">' + IMPORT_MAP + '</script>'
         '<script type="module" src="/astra/bootstrap.mjs"></script></head><body></body></html>').encode()
BOOTSTRAP = b"import {bootAstraRuntime} from '/astra/astra_adapter.mjs';window.astraBoot=bootAstraRuntime();\n"
SOFTWARE_BOOTSTRAP = b"import {bootAstraRuntime} from '/astra/astra_adapter.mjs';window.astraBoot=bootAstraRuntime({testOnlySoftwareProbe:true});\n"


def safe_bytes(file, *, limit=LIMIT):
    """Do not follow source/bundle symlinks, devices, or a file replaced during reading."""
    file = Path(file)
    if not file.is_absolute() or any(p in ('.', '..') for p in file.parts):
        raise ValueError('ABSOLUTE_CANONICAL_FILE_REQUIRED')
    cursor = Path(file.anchor)
    for part in file.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError('SOURCE_SYMLINK_FORBIDDEN')
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= limit:
            raise ValueError('BOUNDED_REGULAR_SOURCE_REQUIRED')
        data = source.read(limit + 1)
        after = os.fstat(source.fileno())
        if len(data) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('SOURCE_CHANGED_WHILE_READING')
    return data


def route_path(value):
    parsed = urlsplit(value)
    result = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or parsed.fragment or not result.startswith('/') or '\\' in result or '\x00' in result or any(p in ('.', '..') for p in result.split('/')):
        raise ValueError('UNSAFE_HTTP_PATH')
    if parsed.query and not (result == '/modules/reference_terrain_material_v4.mjs' and parsed.query == 'baseline'):
        raise ValueError('UNEXPECTED_QUERY')
    return result


def load_config(file, expected_sha):
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise ValueError('CONFIG_SHA_REQUIRED')
    data = safe_bytes(file, limit=4 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError('CONFIG_SHA_MISMATCH')
    config = json.loads(data)
    if config.get('schema') != 'ASTRA_RUNTIME_SERVER_CONFIG_V1' or not isinstance(config.get('bindings'), list) or not 1 <= len(config['bindings']) <= 512:
        raise ValueError('EXPLICIT_BOUNDED_CLOSURE_REQUIRED')
    roots = [REPO, Path(config['bundleRoot'])]
    if not roots[1].is_absolute():
        raise ValueError('ABSOLUTE_BUNDLE_ROOT_REQUIRED')
    exact = {}
    for binding in config['bindings']:
        url = binding['url']
        if route_path(url) != url or url in exact or url in ('/', '/index.html', '/runtime-config.json', '/astra/bootstrap.mjs'):
            raise ValueError('UNIQUE_EXACT_HTTP_PATH_REQUIRED')
        file = Path(binding['path'])
        if not any(file.is_relative_to(root) for root in roots):
            raise ValueError('CLOSURE_FILE_OUTSIDE_ALLOWED_ROOT')
        if type(binding['bytes']) is not int or not SHA.fullmatch(binding['sha256']):
            raise ValueError('SOURCE_BINDING_REQUIRED')
        raw = safe_bytes(file)
        if len(raw) != binding['bytes'] or hashlib.sha256(raw).hexdigest() != binding['sha256']:
            raise ValueError('BOUND_SOURCE_MISMATCH')
        exact[url] = dict(binding)
    return config, exact


def make_server(config, exact, *, port=0):
    runtime = json.dumps(config['runtimeConfig'], sort_keys=True, separators=(',', ':')).encode()
    bootstrap = SOFTWARE_BOOTSTRAP if config['runtimeConfig'].get('testOnlySoftwareProbe') is True else BOOTSTRAP

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
            elif path == '/astra/bootstrap.mjs':
                body, content_type = bootstrap, 'text/javascript'
            elif path == '/runtime-config.json':
                body, content_type = runtime, 'application/json'
            else:
                record = exact.get(path)
                if record is None:
                    self.send_error(404, 'Not found')
                    return
                try:
                    body = safe_bytes(record['path'])
                    if len(body) != record['bytes'] or hashlib.sha256(body).hexdigest() != record['sha256']:
                        raise ValueError('BOUND_SOURCE_CHANGED')
                except (OSError, ValueError):
                    self.send_error(409, 'Bound source changed')
                    return
                content_type = 'text/javascript' if Path(path).suffix in ('.mjs', '.js') else mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'sha256-" + IMPORT_MAP_SHA + "'; style-src 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'")
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
        parser.error('port must be between 0 and 65535')
    config, exact = load_config(args.config, args.expected_config_sha256)
    with make_server(config, exact, port=args.port) as server:
        print(json.dumps({'event': 'READY', 'url': f'http://127.0.0.1:{server.server_port}', 'closureFiles': len(exact)}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None
