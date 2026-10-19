"""Preserved HTTPS/auth/CSRF application with native-capability admission."""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


preserved = _load('_reconcile_preserved_web', HERE.parent / 'universal-overnight-v3/studio_entry.py')
controller = _load('_reconcile_web_controller', HERE / 'studio_controller.py')
_PreservedApplication = preserved.Application


class Application(_PreservedApplication):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('controller_factory', controller.StudioController)
        super().__init__(*args, **kwargs)


# Reuse the complete existing CLI, setup mode, authenticated handlers and server.
preserved.Application = Application


def main(argv=None):
    _load('_reconcile_web_manifest', HERE / 'package_manifest.py').verify_sources()
    return preserved.main(argv)


if __name__ == '__main__':
    main()
