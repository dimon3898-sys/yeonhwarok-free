"""Instance-scoped dispatch: opting into V2 can never fall back to frozen V1.

The old backend remains the owner of exact Scene binding and GPU leases. The
new bridge must explicitly consume the complete submission, including sibling
integration metadata. Missing bridges are a blocking condition, not a no-op.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def _load_bridge():
    path = HERE / 'runtime_bridge.py'
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        return None
    name = '_world_unified_runtime_bridge'
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


class RuntimeBackend:
    def __init__(self, parent_backend, *, image_digest, bridge=None):
        self.parent_backend, self.image_digest = parent_backend, image_digest
        self.bridge = _load_bridge() if bridge is None else bridge

    def __getattr__(self, name):
        # Binding/validation/status reuse is deliberate. V2 execution calls
        # below never reach this fallback through a missing bridge method.
        return getattr(self.parent_backend, name)

    def _bridge(self, name, *args, **kwargs):
        method = getattr(self.bridge, name, None)
        if not callable(method):
            raise RuntimeError('STUDIO_UNIFIED_RUNTIME_NOT_CONNECTED')
        return method(*args, **kwargs, image_digest=self.image_digest)

    def integration_context(self, submission, **kwargs):
        return self._bridge('gate_context', deepcopy(submission), **kwargs)

    def integration_preflight(self, submission, **kwargs):
        return self._bridge('preflight', deepcopy(submission), **kwargs)

    def integration_start(self, submission, approval_path, sfx, request_id, **kwargs):
        return self._bridge('start_studio_job', deepcopy(submission), approval_path,
                            deepcopy(sfx), request_id, **kwargs)

    def studio_status(self, job_id, **kwargs):
        return self._bridge('studio_status', job_id, **kwargs)

    def integration_recover(self, job_id, approval_path, request_id, **kwargs):
        return self._bridge('start_studio_recovery', job_id, approval_path, request_id, **kwargs)
