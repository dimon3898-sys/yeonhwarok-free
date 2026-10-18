#!/usr/bin/env python3
"""Fixed production stages only: reuse offline Studio and GPU admission."""
from __future__ import annotations
import json
import re
import sys

STAGES = {'bootstrap', 'server', 'runtime', 'coordinator', 'startup-restore', 'cli'}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    stage = arguments.pop(0) if arguments else 'bootstrap'
    if stage not in STAGES:
        raise RuntimeError('PRODUCTION_FIXED_STAGE_REQUIRED')
    from production_manifest import verify_sources
    verify_sources()
    from production_runtime import install
    old = install()
    target = {'bootstrap': old.bootstrap, 'server': old.server,
              'runtime': old.runtime_entry, 'coordinator': old.coordinator,
              'startup-restore': old.startup_restore, 'cli': old.cli}[stage]
    return target.main(arguments)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        code = getattr(error, 'code', str(error))
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,95}', code):
            code = 'PRODUCTION_STARTUP_BLOCKED'
        print(json.dumps({'stage': 'PRODUCTION_STARTUP_BLOCKED', 'errorCode': code,
                          'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(2)
