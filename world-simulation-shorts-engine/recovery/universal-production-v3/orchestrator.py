#!/usr/bin/env python3
"""V3 entrypoint over the immutable multi-scene coordinator; no new scheduler."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'universal-auto-video-v2'
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/universal-production-v3')
EXPORT_ROOT = Path('/world-storage')
PARENT_SHA256 = '2e1e9d76c6ecf760f69fa2204c80d91da251fa0ee2abf8ed7cf3fe2388afcca4'
SOURCE_VERIFIER_SHA256 = 'c63757663cba3c3e8efd4f9606be5a78ef8ac5e6d9c54a18c1adfab8f6e8ca42'


def _load_parent():
    path = PARENT / 'orchestrator.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SHA256:
        raise RuntimeError('PRODUCTION_PARENT_COORDINATOR_CHANGED')
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(PARENT))
        spec = importlib.util.spec_from_file_location('_production_v3_frozen_coordinator', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
    # Only this independent instance is configured. Source bytes, old module
    # instances, caches, jobs, claim paths and inherited GPU guards are intact.
    module.HERE, module.CONTROL_ROOT = HERE, CONTROL_ROOT
    return module


parent = _load_parent()
_parent_run_job, _parent_start_job, _parent_status = parent.run_job, parent.start_job, parent.status
CoordinatorError = parent.CoordinatorError
validate_approval = parent.validate_approval
manager = parent.manager
_identity, _alive = parent._identity, parent._alive
_adapter = None


def _verify_sources():
    path = HERE / 'source_manifest.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_VERIFIER_SHA256:
        raise RuntimeError('PRODUCTION_SOURCE_VERIFIER_CHANGED')
    spec = importlib.util.spec_from_file_location('_production_coordinator_source_manifest', path)
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)
    return manifest.verify_sources()


def _validate_plan(plan):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location('_production_coordinator_scene_planner', HERE / 'scene_planner.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_production_plan(plan, require_renderable=True)
    finally:
        sys.path[:] = original_path


def _fixed_adapter():
    global _adapter
    if _adapter is None:
        path = HERE / 'render_adapter.py'
        spec = importlib.util.spec_from_file_location('_production_v3_fixed_render_adapter', path)
        candidate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(candidate)
        if Path(candidate.__file__).resolve() != path:
            raise RuntimeError('PRODUCTION_RENDER_ADAPTER_ORIGIN_INVALID')
        _adapter = candidate
    return _adapter


@contextmanager
def _fixed_entry_modules():
    """Bind only fixed in-image modules during the dedicated main-thread call."""
    originals = {name: sys.modules.get(name) for name in ('render_adapter', 'orchestrator')}
    module = sys.modules.get(__name__)
    if module is None or Path(module.__file__).resolve() != HERE / 'orchestrator.py':
        raise RuntimeError('PRODUCTION_COORDINATOR_ORIGIN_INVALID')
    adapter = _fixed_adapter()
    sys.modules['render_adapter'], sys.modules['orchestrator'] = adapter, module
    try:
        with adapter._parent_imports():
            yield
    finally:
        for name, previous in originals.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def run_job(plan, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT, **options):
    _verify_sources()
    _validate_plan(plan)
    with _fixed_entry_modules():
        return _parent_run_job(plan, control_root=control_root, export_root=export_root, **options)


def start_job(plan, approval_path, *, control_root=CONTROL_ROOT, export_root=EXPORT_ROOT, resume=False):
    _verify_sources()
    _validate_plan(plan)
    with _fixed_entry_modules():
        return _parent_start_job(plan, approval_path, control_root=control_root,
                                export_root=export_root, resume=resume)


def status(plan, control_root=CONTROL_ROOT):
    _verify_sources()
    _validate_plan(plan)
    with _fixed_entry_modules():
        return _parent_status(plan, control_root)


def main(argv=None):
    try:
        _verify_sources()
        with _fixed_entry_modules():
            return parent.main(argv)
    except Exception as error:
        import json
        code = parent._safe_code(error)
        print(json.dumps({'schema': 'WORLD_ENGINE_PRODUCTION_COORDINATOR_FAILURE_V3',
                          'state': 'BLOCKED', 'code': code, 'renderAllowed': False,
                          'gpuRenderingVerified': False}), flush=True)
        return 2


# The inherited parser dispatches through this isolated module's fixed wrappers.
# Its original implementations above remain the actual execution owners.
parent.run_job, parent.start_job, parent.status = run_job, start_job, status


if __name__ == '__main__':
    raise SystemExit(main())
