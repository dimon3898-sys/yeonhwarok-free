#!/usr/bin/env python3
"""Existing owner/Origin/CSRF server with only a durability-aware backend."""
import argparse
import json
import os
from pathlib import Path
import sys

from parent import STUDIO, proxy, runtime
import durable_backend

frozen = proxy()


def controller_factory(**kwargs):
    # Import the preserved class after the proxy loader resolves fixed paths.
    if str(STUDIO) not in sys.path:
        sys.path.insert(0, str(STUDIO))
    from studio_controller import StudioController
    return StudioController(backend=durable_backend, **kwargs)


class Application(frozen.server.Application):
    def __init__(self, *args, **kwargs):
        if 'controller_factory' in kwargs:
            raise RuntimeError('DURABILITY_FIXED_CONTROLLER_REQUIRED')
        super().__init__(*args, controller_factory=controller_factory, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--owner-file', type=Path, required=True)
    parser.add_argument('--export-root', type=Path, default=Path('/world-storage'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    app = Application(args.state_root, args.owner_file, args.export_root,
        os.environ.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST'), args.port,
        initial_origin=os.environ.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN'),
        configuration_error=os.environ.get('WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR'))
    server = frozen.server.original.StudioHTTPServer((args.host, args.port), app.handler())
    print(json.dumps({'stage': 'STUDIO_DURABILITY_WEB_STARTED', 'renderAllowed': False,
                      'gpuRenderingVerified': False}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'stage': 'STUDIO_DURABILITY_WEB_FAILED', 'errorCode': runtime()._safe(error),
            'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(1)
