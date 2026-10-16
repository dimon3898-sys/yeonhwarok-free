"""Fixed archival capture target over the unchanged V3/NVIDIA hardware owner."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRODUCTION = HERE.parent / 'universal-production-v3'
PARENT_SHA256 = 'a8b4dd862f458fb4e5c5cd262db7f26779c9f2b7690e77763ed3552ee7a1186f'
_binding = None


def _load_fixed(name, path, expected=None):
    if path.is_symlink() or expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('FRONT_EXECUTION_FROZEN_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The V3 loader creates a new U2 module instance. Only that instance's capture
# target is configured; original source, sessions and claims are never mutated.
production = _load_fixed('_archival_front_v4_frozen_hardware', PRODUCTION / 'render_adapter.py', PARENT_SHA256)
parent = production.parent
parent.HERE = HERE
RenderError, native_gpu = parent.RenderError, parent.native_gpu


def _scene_binding():
    global _binding
    if _binding is None:
        _binding = _load_fixed('_archival_front_v4_hardware_scene_binding', HERE / 'scene_binding.py')
    return _binding


def _verify_sources():
    return _scene_binding().verify_sources()


def _validate_plan(plan):
    return _scene_binding().validate_execution_plan(plan)


@contextmanager
def _parent_imports():
    with production._parent_imports():
        yield


@contextmanager
def common_gpu_lease():
    _verify_sources()
    with _parent_imports(), parent.common_gpu_lease():
        yield


def prepare_job(plan, private_root, *, approval):
    _verify_sources()
    _validate_plan(plan)
    with _parent_imports():
        return parent.prepare_job(plan, private_root, approval=approval)


def render_segment(plan, scene, output_directory, *, approval, progress=None):
    _verify_sources()
    _validate_plan(plan)
    with _parent_imports():
        return parent.render_segment(plan, scene, output_directory,
                                     approval=approval, progress=progress)
