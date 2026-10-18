"""Load the unchanged, separately verified Studio payload from trusted locations."""
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ORIGINAL = (Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt')
            else HERE.parent / 'production-studio-mvp-v1')


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_originals():
    if any(path.is_symlink() for path in (ORIGINAL, *ORIGINAL.parents)):
        raise RuntimeError('STUDIO_FROZEN_PATH_REQUIRED')
    sys.path.insert(0, str(ORIGINAL))
    server = _load('_https_frozen_studio_server', ORIGINAL / 'server.py')
    bootstrap = _load('_https_frozen_studio_bootstrap', ORIGINAL / 'bootstrap.py')
    return SimpleNamespace(server=server, bootstrap=bootstrap, root=ORIGINAL)
