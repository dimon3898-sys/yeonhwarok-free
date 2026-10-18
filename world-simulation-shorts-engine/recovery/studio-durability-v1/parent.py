"""Pinned, independent instances of the unchanged production implementation."""
from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
RECOVERY = (Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery')
            if HERE.is_relative_to('/opt') else HERE.parent)
STUDIO = (Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt')
          else RECOVERY / 'production-studio-mvp-v1')
PROXY = (Path('/opt/world-engine-studio-https-proxy-fix') if HERE.is_relative_to('/opt')
         else RECOVERY / 'studio-https-proxy-fix-v1')


def load_file(name, path, expected=None):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('DURABILITY_PARENT_SYMLINK_FORBIDDEN')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('DURABILITY_FROZEN_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def runtime():
    sys.path.insert(0, str(STUDIO))
    return load_file('_durability_frozen_studio_runtime', STUDIO / 'studio_runtime.py',
        '79f8a58a3bf99b6edfc73f9fc7266b23ebd7b6646257f3ffeed08afd68a00f1e')


@lru_cache(maxsize=1)
def proxy():
    previous = sys.modules.get('parent')
    oldpath = list(sys.path)
    try:
        sys.path.insert(0, str(PROXY))
        p = load_file('_durability_frozen_proxy_parent', PROXY / 'parent.py',
            '20f6e5fe6badce1bbdcda88fab17d42f8f629b487e88981815361ac0fce62f63')
        sys.modules['parent'] = p
        server = load_file('_durability_frozen_proxy_server', PROXY / 'proxy_server.py',
            'e042a617e15d4823eaffaba23a10755a01528a590cb995ec8161f9744fb0b5f4')
        return SimpleNamespace(server=server, https=p.modules(), root=PROXY)
    finally:
        sys.path[:] = oldpath
        if previous is None:
            sys.modules.pop('parent', None)
        else:
            sys.modules['parent'] = previous
