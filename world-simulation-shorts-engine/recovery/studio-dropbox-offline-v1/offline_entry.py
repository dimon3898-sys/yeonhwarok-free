#!/usr/bin/env python3
"""Independent offline-token entry point for the unchanged durability runtime."""
from __future__ import annotations

import json
import re
import sys


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    stage = arguments.pop(0) if arguments else 'bootstrap'
    stages = {'bootstrap', 'server', 'runtime', 'coordinator', 'startup-restore', 'cli'}
    if stage not in stages:
        raise RuntimeError('DURABILITY_OFFLINE_FIXED_STAGE_REQUIRED')
    from offline_manifest import verify_sources
    verify_sources()
    from offline_runtime import install
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
            code = 'DURABILITY_OFFLINE_STARTUP_FAILED'
        print(json.dumps({'stage': 'OFFLINE_STARTUP_BLOCKED', 'errorCode': code,
                          'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        raise SystemExit(2)
