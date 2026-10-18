#!/usr/bin/env python3
"""Detached child entry; reapply only the durability process adapter."""
import json
from durable_backend import backend


def main(argv=None):
    return backend().main(argv)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'schema': 'WORLD_ENGINE_STUDIO_DURABILITY_WORKER_V1',
            'state': 'BLOCKED', 'code': backend()._safe(error), 'renderAllowed': False,
            'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(2)
