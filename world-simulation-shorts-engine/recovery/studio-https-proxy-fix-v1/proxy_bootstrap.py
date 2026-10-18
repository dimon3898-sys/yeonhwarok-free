#!/usr/bin/env python3
"""Reuse the existing supervisor; substitute only the explicit proxy UI entry."""
import json
import os
from pathlib import Path
import subprocess
import sys
from parent import load_file, modules

HERE = Path(__file__).resolve().parent
parent = modules()


def spawn_proxy(command, **kwargs):
    expected = ['/usr/bin/python3', '-B', str(parent.root / 'https_server.py')]
    if command[:3] == expected:
        command = [*command[:2], str(HERE / 'proxy_server.py'), *command[3:]]
    return subprocess.Popen(command, **kwargs)


def main(argv=None):
    try:
        if os.geteuid() != 0:
            raise RuntimeError('STUDIO_ROOT_BOOTSTRAP_REQUIRED')
        load_file('_proxy_own_manifest', HERE / 'manifest.py').verify_sources()
        config = parent.bootstrap.prepare_configuration(os.environ)
        environment = parent.bootstrap.child_environment(os.environ, studio=True, config=config)
        for name in parent.bootstrap.original.SECRET_ENV:
            os.environ.pop(name, None)
        return parent.bootstrap.supervise(config, environment,
            sys.argv[1:] if argv is None else argv, spawn=spawn_proxy)
    except Exception as error:
        parent.bootstrap._record('STARTUP_BLOCKED', status='FAIL',
            errorCode=parent.bootstrap._safe_code(error), renderAllowed=False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
