#!/usr/bin/env python3
"""Independent opt-in Studio entry over the preserved HTTPS/auth application.

No new unauthenticated production endpoint is introduced. The existing port,
owner login, Origin/CSRF policy, proxy normalization and GPU admission remain.
This candidate must be source-manifested and packaged before deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PROXY = (Path('/opt/world-engine-studio-https-proxy-fix') if HERE.is_relative_to('/opt')
         else HERE.parent / 'studio-https-proxy-fix-v1')


def _load(name, path, expected=None):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('STUDIO_INTEGRATION_SOURCE_SYMLINK_FORBIDDEN')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('STUDIO_INTEGRATION_PARENT_CHANGED')
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


sys.path.insert(0, str(PROXY))
proxy = _load('_unified_frozen_proxy_server', PROXY / 'proxy_server.py',
              'e042a617e15d4823eaffaba23a10755a01528a590cb995ec8161f9744fb0b5f4')
controller_module = _load('_unified_controller_extension', HERE / 'studio_controller.py')


def verify_extension():
    """Verify the explicit packaging manifest; missing packaging fails closed."""
    path = HERE / 'RUNTIME_SOURCE_MANIFEST.json'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_REQUIRED')
    value = json.loads(path.read_bytes())
    if value.get('schema') != 'WORLD_ENGINE_UNIFIED_RUNTIME_SOURCE_MANIFEST_V1':
        raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_INVALID')
    rows = value.get('files')
    if not isinstance(rows, list) or not rows:
        raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_INVALID')
    found = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
            raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_INVALID')
        name, expected = row['path'], row['sha256']
        relative = Path(name) if isinstance(name, str) else Path('..')
        if (relative.is_absolute() or '..' in relative.parts or name in found
                or not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected)):
            raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_INVALID')
        target = HERE / relative
        if any(p.is_symlink() for p in (target, *target.parents)) or not target.is_file():
            raise RuntimeError('STUDIO_UNIFIED_SOURCE_MISSING')
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError('STUDIO_UNIFIED_SOURCE_CHANGED')
        found.add(name)
    required = {'studio_entry.py', 'studio_controller.py', 'runtime_backend.py',
                'runtime_bridge.py', 'contract_v2.py', 'quality_gate.py'}
    if not required <= found:
        raise RuntimeError('STUDIO_UNIFIED_SOURCE_MANIFEST_INCOMPLETE')
    return {'status': 'PASS', 'files': len(found)}


class Application(proxy.Application):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('controller_factory', controller_module.StudioController)
        super().__init__(*args, **kwargs)

    def handler(self):
        base, app = super().handler(), self

        class Handler(base):
            def _dispatch(self):
                target = urlsplit(self.path)
                extension_path = target.path in {'/api/integration/profile', '/app.js'}
                if self.command == 'GET' and extension_path and not (target.scheme or target.netloc or target.query or target.fragment):
                    with app.core.lock:
                        if app.normal is None:
                            return super()._dispatch()
                        self._configured_policy()
                        self._authenticate(False)
                        if target.path == '/api/integration/profile':
                            return self._send(200, {
                                'schema': 'WORLD_ENGINE_STUDIO_INTEGRATION_STATUS_V1',
                                'profile': 'VISUAL_UNIFIED_V1',
                                'promptSchema': 'WORLD_ENGINE_STUDIO_PROMPT_V2',
                                'fullVideoRequires5sUserReview': True,
                                'renderAllowed': False, 'gpuRenderingVerified': False,
                                'existingStudioEntryUnchanged': True})
                        # Reuse the actual shipped UI without copying or editing
                        # it. Only browser-local job keys receive a new namespace.
                        source = (proxy.parent.server.original.HERE / 'web' / 'app.js').read_text()
                        source = source.replace('world-studio-job', 'world-studio-unified-v1-job')
                        source = source.replace('world-studio-start-', 'world-studio-unified-v1-start-')
                        source = source.replace('world-studio-resume-', 'world-studio-unified-v1-resume-')
                        return self._send(200, source.encode(), 'text/javascript; charset=utf-8')
                return super()._dispatch()

        return Handler


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True, type=Path)
    parser.add_argument('--owner-file', required=True, type=Path)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    verify_extension()
    # Preserve all inherited source/security validation before server exposure.
    proxy.load_file('_unified_proxy_source_manifest', PROXY / 'manifest.py').verify_sources()
    app = Application(args.state_root, args.owner_file, args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'), args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server = proxy.original.StudioHTTPServer((args.host, args.port), app.handler())
    print(json.dumps({'stage': 'STUDIO_UNIFIED_WEB_STARTED',
        'mode': 'CONFIGURED' if app.normal else 'SETUP', 'renderAllowed': False,
        'gpuRenderingVerified': False, 'fullVideoRequires5sUserReview': True}), flush=True)
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
        if not isinstance(code, str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'STUDIO_UNIFIED_STARTUP_FAILED'
        print(json.dumps({'stage': 'STUDIO_UNIFIED_STARTUP_BLOCKED', 'errorCode': code,
                          'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(1)
