"""Hash-pinned access to the existing durability engine; no duplicate backup."""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
DURABILITY = (Path('/opt/world-engine-studio-durability') if HERE.is_relative_to('/opt')
              else HERE.parent / 'studio-durability-v1')


def _load(name, filename, digest):
    path = DURABILITY / filename
    if (any(p.is_symlink() for p in (path, *path.parents))
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
        raise RuntimeError('OFFLINE_FROZEN_DURABILITY_SOURCE_CHANGED')
    previous = sys.modules.get(name)
    if previous is not None:
        if Path(getattr(previous, '__file__', '')).resolve() != path.resolve():
            raise RuntimeError('OFFLINE_FROZEN_MODULE_COLLISION')
        return previous
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def modules():
    data = json.loads((HERE / 'PARENT_SOURCES.json').read_text())
    if (data.get('schema') != 'WORLD_ENGINE_FROZEN_DURABILITY_SOURCE_V1'
            or data.get('parentCommit') != '165a3489eede6e6f66c20f2d6ca1d70fd8c79560'):
        raise RuntimeError('OFFLINE_FROZEN_PROVENANCE_REQUIRED')
    if str(DURABILITY) not in sys.path:
        sys.path.insert(0, str(DURABILITY))
    aliases = [('stores', 'stores'), ('vault', 'vault'), ('checkpoint', 'checkpoint'),
               ('preflight', 'preflight'), ('parent', 'parent'),
               ('durable_backend', 'backend'), ('manifest', 'manifest'),
               ('bootstrap', 'bootstrap'), ('durable_coordinator', 'coordinator'),
               ('runtime_entry', 'runtime_entry'), ('startup_restore', 'startup_restore'),
               ('cli', 'cli'), ('durable_server', 'server')]
    result = {}
    for name, attr in aliases:
        result[attr] = _load(name, name + '.py', data['files'][name + '.py'])
    return SimpleNamespace(**result)
