"""Reuse the original HTTPS/login/CSRF service with a completion controller."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
from urllib.parse import urlsplit
HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    spec.loader.exec_module(value); return value


prior = _load('_completion_preserved_web', HERE.parent / 'universal-integration-v1/studio_entry.py')
controller = _load('_completion_web_controller', HERE / 'studio_controller.py')


def verify_extension():
    return _load('_completion_web_sources', HERE / 'package_manifest.py').verify_sources()


class Application(prior.Application):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('controller_factory', controller.StudioController)
        super().__init__(*args, **kwargs)

    def handler(self):
        original, app = super().handler(), self
        class Handler(original):
            def _dispatch(self):
                target = urlsplit(self.path)
                if (self.command == 'GET' and target.path in {'/api/integration/profile', '/app.js'}
                        and not (target.scheme or target.netloc or target.query or target.fragment)):
                    with app.core.lock:
                        if app.normal is None:
                            return super()._dispatch()
                        self._configured_policy(); self._authenticate(False)
                        if target.path == '/api/integration/profile':
                            return self._send(200, {'schema': 'WORLD_ENGINE_STUDIO_COMPLETION_STATUS_V2',
                                'profile': 'VISUAL_UNIFIED_COMPLETION_V2',
                                'promptSchema': 'WORLD_ENGINE_STUDIO_PROMPT_V2',
                                'fullVideoRequires5sUserReview': True, 'renderAllowed': False,
                                'gpuRenderingVerified': False, 'sceneGeometryInvented': False})
                        source = (prior.proxy.parent.server.original.HERE / 'web/app.js').read_text()
                        for key in ('job', 'start-', 'resume-'):
                            source = source.replace('world-studio-' + key, 'world-studio-completion-v2-' + key)
                        return self._send(200, source.encode(), 'text/javascript; charset=utf-8')
                return super()._dispatch()
        return Handler


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True, type=Path)
    parser.add_argument('--owner-file', required=True, type=Path)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0'); parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    verify_extension()
    prior.proxy.load_file('_completion_proxy_manifest', prior.PROXY / 'manifest.py').verify_sources()
    app = Application(args.state_root, args.owner_file, args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'), args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server = prior.proxy.original.StudioHTTPServer((args.host, args.port), app.handler())
    print(json.dumps({'stage': 'STUDIO_COMPLETION_WEB_STARTED', 'renderAllowed': False,
                      'gpuRenderingVerified': False}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
