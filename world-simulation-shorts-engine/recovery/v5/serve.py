#!/usr/bin/env python3
"""Read-only loopback mounts for the V5 candidate adapter; never serves the repository root."""
import argparse
import hashlib
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

RUNTIME = Path(__file__).resolve().parent
ENGINE = RUNTIME.parents[1]
REPO = ENGINE.parent


def contained_regular(candidate):
    """Reject traversal, symlinks and nonregular files before opening anything."""
    candidate = Path(candidate).absolute()
    try:
        relative = candidate.relative_to(REPO)
    except ValueError:
        raise ValueError('PATH_OUTSIDE_REPOSITORY') from None
    current = REPO
    for part in relative.parts:
        if part in ('.', '..'):
            raise ValueError('UNSAFE_PATH')
        current = current / part
        if current.is_symlink():
            raise ValueError('SYMLINK_FORBIDDEN')
    if not candidate.is_file():
        raise ValueError('REGULAR_FILE_REQUIRED')
    return candidate


def selected_path(value):
    candidate = Path(value)
    return candidate if candidate.is_absolute() else ENGINE / candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--phase', choices=('v5',), default='v5')
    defaults = {
        'regional-plan': 'recovery/v4/equivalent-plans/REGIONAL-plan.json',
        'continent-plan': 'recovery/v4/equivalent-plans/CONTINENT-plan.json',
        'scene': 'recovery/v5/inputs/scene.json',
        'camera-plan': 'recovery/v5/inputs/camera-plan.json',
        'input-manifest': 'recovery/v4/V4-state-records/input-manifest.json',
    }
    for name, default in defaults.items():
        parser.add_argument('--' + name, default=default, help='Path relative to engine or absolute under repository')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    inputs = {name: selected_path(getattr(args, name.replace('-', '_'))) for name in defaults}
    required = ('regional-plan', 'continent-plan', 'input-manifest', 'scene', 'camera-plan')
    files = {}
    for name in required:
        file = contained_regular(inputs[name])
        files[name] = {'path': file.relative_to(REPO).as_posix(), 'bytes': file.stat().st_size,
                       'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    config = {'schema': 1, 'phase': args.phase, 'output': [1080, 1920], 'fps': 30, 'inputs': files}
    exact = {
        '/': RUNTIME / 'index.html', '/index.html': RUNTIME / 'index.html',
        '/harness.mjs': RUNTIME / 'harness.mjs',
        '/three.js': ENGINE / 'web/vendor/three/0.170.0/three.module.js',
        '/height.f32': ENGINE / 'web/dem/glo30/height.f32',
        **{'/inputs/' + key + '.json': inputs[name] for key, name in (
            ('regional', 'regional-plan'), ('continent', 'continent-plan'), ('scene', 'scene'),
            ('camera-plan', 'camera-plan'), ('input-manifest', 'input-manifest'))},
    }
    mounts = {'/modules/': ENGINE / 'web/map_infographic_v1',
              '/camera-v4-assets/': ENGINE / 'web/camera-v4-assets',
              '/static/': ENGINE / 'web', '/v3/assets/': REPO / 'cinematic-world-map/assets'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            path = unquote(urlsplit(self.path).path)
            if '\\' in path or '\x00' in path or any(part in ('.', '..') for part in path.split('/')):
                self.send_error(400, 'Unsafe path')
                return
            if path == '/runtime-config.json':
                body = json.dumps(config, sort_keys=True).encode()
                self.send_response(200)
                self.send_content_headers('application/json', len(body))
                if not head:
                    self.wfile.write(body)
                return
            candidate = exact.get(path)
            if candidate is None:
                for prefix, root in mounts.items():
                    if path.startswith(prefix):
                        candidate = root / path[len(prefix):]
                        break
            try:
                file = contained_regular(candidate) if candidate is not None else None
            except (ValueError, OSError):
                file = None
            if file is None:
                self.send_error(404, 'Not found')
                return
            self.send_response(200)
            content_type = 'text/javascript' if file.suffix in ('.mjs', '.js') else mimetypes.guess_type(file)[0]
            self.send_content_headers(content_type or 'application/octet-stream', file.stat().st_size)
            if not head:
                try:
                    with file.open('rb') as source:
                        while chunk := source.read(1024 * 1024):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def send_content_headers(self, content_type, length):
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(length))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'")
            self.end_headers()

    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(json.dumps({'event': 'READY', 'url': f'http://127.0.0.1:{server.server_port}', 'config': config}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
