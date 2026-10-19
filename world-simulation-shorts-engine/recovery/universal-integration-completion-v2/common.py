"""Source-only loading helpers for the isolated completion profile."""
from pathlib import Path
import hashlib
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'universal-integration-v1'
BASE_COMMIT = '61c7fc3a36cc987c3f88844aba98c57bb62fe22e'


def load(name, path, expected=None):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('COMPLETION_SOURCE_SYMLINK_FORBIDDEN')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('COMPLETION_PARENT_SOURCE_CHANGED')
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


def previous(name):
    # Source manifests are checked before launch. Stable V1 source is never edited.
    return load('_completion_preserved_' + name.removesuffix('.py'), PREVIOUS / name)
