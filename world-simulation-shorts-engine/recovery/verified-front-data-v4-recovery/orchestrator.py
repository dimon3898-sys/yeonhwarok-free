#!/usr/bin/env python3
"""Separate archival-data job namespace around the frozen production manager."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRODUCTION = HERE.parent / 'universal-production-v3'
CONTROL_ROOT = Path('/var/lib/world-engine-private/engine/verified-front-v4')
EXPORT_ROOT = Path('/world-storage')
PARENT_SHA256 = 'd9ea3ddca051c80ff2811928dcd0c480926e671014691c16ea6a2ede845ccbed'


def _load_fixed(name, path, expected=None):
    if path.is_symlink() or expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('FRONT_EXECUTION_FROZEN_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


production = _load_fixed('_archival_front_v4_frozen_coordinator', PRODUCTION / 'orchestrator.py', PARENT_SHA256)
parent = production.parent
parent.HERE, parent.CONTROL_ROOT = HERE, CONTROL_ROOT
_parent_run_job = production._parent_run_job
_parent_start_job = production._parent_start_job
_parent_status = production._parent_status
CoordinatorError, validate_approval = parent.CoordinatorError, parent.validate_approval
manager, _identity, _alive = parent.manager, parent._identity, parent._alive
_binding = _adapter = None


def _scene_binding():
    global _binding
    if _binding is None:
        _binding = _load_fixed('_archival_front_v4_coordinator_scene_binding', HERE / 'scene_binding.py')
    return _binding


def _verify_sources():
    return _scene_binding().verify_sources()


def _validate_plan(plan):
    return _scene_binding().validate_execution_plan(plan)


def _fixed_adapter():
    global _adapter
    if _adapter is None:
        _adapter = _load_fixed('_archival_front_v4_fixed_render_adapter', HERE / 'render_adapter.py')
    return _adapter


@contextmanager
def _fixed_entry_modules():
    previous = {name: sys.modules.get(name) for name in ('render_adapter', 'orchestrator')}
    module = sys.modules.get(__name__)
    if module is None or Path(module.__file__).resolve() != HERE / 'orchestrator.py':
        raise RuntimeError('FRONT_EXECUTION_COORDINATOR_ORIGIN_INVALID')
    adapter = _fixed_adapter()
    sys.modules['render_adapter'], sys.modules['orchestrator'] = adapter, module
    try:
        with adapter._parent_imports():
            yield
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


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
        print(json.dumps({'schema': 'WORLD_ENGINE_ARCHIVAL_FRONT_COORDINATOR_FAILURE_V4',
            'state': 'BLOCKED', 'code': parent._safe_code(error),
            'renderAllowed': False, 'gpuRenderingVerified': False}), flush=True)
        return 2


parent.run_job, parent.start_job, parent.status = run_job, start_job, status


if __name__ == '__main__':
    raise SystemExit(main())
