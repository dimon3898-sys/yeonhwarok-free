"""Select the reconciliation entry through the unchanged secure supervisor.

The previous bootstrap still owns UID dropping, private state, image proof,
secret cleanup, child environment, health and failure handling. Its namespace
and proofs are not rewritten to make a new extension appear pre-approved.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
PRESERVED = HERE.parent / 'universal-overnight-v3'
PRESERVED_MANIFEST_SHA256 = 'ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


_manifest_raw = (PRESERVED / 'OVERNIGHT_FILES.json').read_bytes()
if hashlib.sha256(_manifest_raw).hexdigest() != PRESERVED_MANIFEST_SHA256:
    raise RuntimeError('RECONCILE_PRESERVED_MANIFEST_CHANGED')
_source = PRESERVED / 'bootstrap.py'
if hashlib.sha256(_source.read_bytes()).hexdigest() != json.loads(_manifest_raw)['files']['bootstrap.py']:
    raise RuntimeError('RECONCILE_PRESERVED_BOOTSTRAP_CHANGED')
_preserved_bootstrap = _load('_reconcile_preserved_bootstrap', _source)
_owner = _preserved_bootstrap._owner
_preserved_spawn = _owner.spawn


def spawn(command, **kwargs):
    # Only the supervisor's exact known child changes. Arbitrary commands,
    # arguments, UID/GID, environment and subprocess behavior stay unchanged.
    expected = ['/usr/bin/python3', '-B', str(_owner.parent.parent.root / 'https_server.py')]
    if command[:3] == expected:
        command = [*command[:2], str(HERE / 'studio_entry.py'), *command[3:]]
    return _preserved_spawn(command, **kwargs)


_owner.spawn = spawn


def main(argv=None):
    _load('_reconcile_boot_manifest', HERE / 'package_manifest.py').verify_sources()
    return _preserved_bootstrap.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
