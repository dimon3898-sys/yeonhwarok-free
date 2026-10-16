"""Small pinned accessors to the preserved CPU/long-video implementation.

The Studio is installed outside the parent's strict source closure.  It imports
the original helpers in place and neither copies nor edits those implementations.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
_LOCK = threading.RLock()
_MODULES = {}
_SOURCES = {
    "cache": ("universal-auto-video-v2/cache.py",
              "4ad9dc03c11ccb39df027cb39dc31715525f2eb7be6da76bedbccfaefd5984fd"),
    "contracts": ("universal-auto-video-v2/contracts.py",
                  "42774c1e9761c56453ab864ef70f4c965bfad99df1b612ea649c8b6a50e9cc5e"),
    "production_planner": ("universal-production-v3/scene_planner.py",
                           "7b7bfbe132903714279f5308d32827fe80a34578fbb5a3bd7f6747e584919f62"),
}


def recovery_root():
    """Return the real parent closure, never an arbitrary caller-supplied path."""
    checkout = HERE.parent
    installed = Path("/opt/rtx-package/repo/world-simulation-shorts-engine/recovery")
    root = checkout if (checkout / "universal-auto-video-v2/cache.py").is_file() else installed
    for component in (root, *root.parents):
        if component.is_symlink():
            raise RuntimeError("STUDIO_ORIGINAL_SOURCE_SYMLINK_FORBIDDEN")
    if not root.is_dir():
        raise RuntimeError("STUDIO_ORIGINAL_SOURCE_UNAVAILABLE")
    return root


def load_original(name):
    """Load one allowlisted, hash-pinned original module without API changes."""
    if name not in _SOURCES:
        raise RuntimeError("STUDIO_ORIGINAL_MODULE_UNSUPPORTED")
    relative, expected = _SOURCES[name]
    path = recovery_root() / relative
    for component in (path, *path.parents):
        if component.is_symlink():
            raise RuntimeError("STUDIO_ORIGINAL_SOURCE_SYMLINK_FORBIDDEN")
    if not path.is_file() or not 0 < path.stat().st_size < 2 * 1024**2:
        raise RuntimeError("STUDIO_ORIGINAL_SOURCE_UNAVAILABLE")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("STUDIO_ORIGINAL_SOURCE_CHANGED")
    with _LOCK:
        if name not in _MODULES:
            module_name = "_studio_preserved_" + name
            spec = importlib.util.spec_from_file_location(module_name, path)
            candidate = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = candidate
            try:
                spec.loader.exec_module(candidate)
            except BaseException:
                sys.modules.pop(module_name, None)
                raise
            if Path(candidate.__file__).absolute() != path.absolute():
                raise RuntimeError("STUDIO_ORIGINAL_MODULE_ORIGIN_INVALID")
            _MODULES[name] = candidate
        return _MODULES[name]


def canonical_sha256(value):
    return load_original("cache").canonical_sha256(value)
