"""Fixed V3 capture target with unchanged native admission and VRAM controller."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'universal-auto-video-v2'
PARENT_SHA256 = '669073cbd6f3fa9fbfae0a1472fd141a87c6616f1d25acf935a4173dfd32136d'
SOURCE_VERIFIER_SHA256 = 'c63757663cba3c3e8efd4f9606be5a78ef8ac5e6d9c54a18c1adfab8f6e8ca42'
PARENT_MANIFEST_SHA256 = '982cf2c0a5f435afe936605c0aeb76cbf40b6990da41d27c0ea0bd5ef22eb756'
PARENT_IMPORTS = ('cache', 'contracts', 'planner', 'compose', 'delivery', 'universal_files', 'prepare_video')


def _load_parent():
    path = PARENT / 'render_adapter.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SHA256:
        raise RuntimeError('PRODUCTION_PARENT_HARDWARE_ADAPTER_CHANGED')
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(PARENT))
        spec = importlib.util.spec_from_file_location('_production_v3_frozen_hardware_adapter', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
    module.HERE = HERE
    return module


parent = _load_parent()
RenderError = parent.RenderError
native_gpu = parent.native_gpu


@contextmanager
def _parent_imports():
    """Resolve lazy frozen imports in a clean worker, then restore its path.

    No module code or existing instance is changed. A preloaded wrong-origin
    module is rejected rather than silently replacing it or selecting a plugin.
    """
    raw = (PARENT / 'UNIVERSAL_FILES.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_MANIFEST_SHA256:
        raise RuntimeError('PRODUCTION_PARENT_IMPORT_MANIFEST_CHANGED')
    manifest = json.loads(raw)
    original_path = list(sys.path)
    previous = {name: sys.modules.get(name) for name in PARENT_IMPORTS}
    try:
        sys.path[:] = [str(HERE), str(PARENT), *[item for item in original_path if item not in {str(HERE), str(PARENT)}]]
        for name in PARENT_IMPORTS:
            path = PARENT / (name + '.py')
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'][path.name]:
                raise RuntimeError('PRODUCTION_PARENT_LAZY_SOURCE_CHANGED')
            module = importlib.import_module(name)
            if Path(module.__file__).resolve() != path:
                raise RuntimeError('PRODUCTION_PARENT_LAZY_MODULE_ORIGIN_INVALID')
        yield
    finally:
        sys.path[:] = original_path
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            elif sys.modules.get(name) is not module:
                sys.modules[name] = module


def _verify_sources():
    path = HERE / 'source_manifest.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_VERIFIER_SHA256:
        raise RuntimeError('PRODUCTION_SOURCE_VERIFIER_CHANGED')
    spec = importlib.util.spec_from_file_location('_production_hardware_source_manifest', HERE / 'source_manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_sources()


def _validate_plan(plan):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location('_production_hardware_scene_planner', HERE / 'scene_planner.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_production_plan(plan, require_renderable=True)
    finally:
        sys.path[:] = original_path


@contextmanager
def common_gpu_lease():
    _verify_sources()
    with _parent_imports(), parent.common_gpu_lease():
        yield


def prepare_job(plan, private_root, *, approval):
    _verify_sources()
    _validate_plan(plan)
    # The inherited function prepares existing ASTRA data only. The new visual
    # metadata is supplied by the immutable approved plan to the new browser
    # entry; no fictional F scene is booted and no camera source is changed.
    with _parent_imports():
        return parent.prepare_job(plan, private_root, approval=approval)


def render_segment(plan, scene, output_directory, *, approval, progress=None):
    _verify_sources()
    _validate_plan(plan)
    with _parent_imports():
        return parent.render_segment(plan, scene, output_directory,
                                     approval=approval, progress=progress)
