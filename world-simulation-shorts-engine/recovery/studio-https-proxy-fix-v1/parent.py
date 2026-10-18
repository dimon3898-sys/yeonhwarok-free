"""Fixed-location access to the unchanged HTTPS21/Studio51/engine373 image."""
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PARENT = (Path('/opt/world-engine-studio-https-bootstrap') if HERE.is_relative_to('/opt')
          else HERE.parent / 'studio-https-bootstrap-v1')


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def modules():
    if any(p.is_symlink() for p in (PARENT, *PARENT.parents)):
        raise RuntimeError('PROXY_FROZEN_PARENT_PATH_REQUIRED')
    sys.path.insert(0, str(PARENT))
    server = load_file('_proxy_frozen_https_server', PARENT / 'https_server.py')
    bootstrap = load_file('_proxy_frozen_https_bootstrap', PARENT / 'https_bootstrap.py')
    manifest = load_file('_proxy_frozen_https_manifest', PARENT / 'manifest.py')
    return SimpleNamespace(server=server, bootstrap=bootstrap, manifest=manifest,
                           security=server.security, root=PARENT)
