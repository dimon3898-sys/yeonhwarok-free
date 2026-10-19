"""Retain the previous private state/claims and select only a stricter bridge.

No old submission, operator policy, claim or result is migrated, reset or copied.
The immutable image digest remains part of the existing capture identity. An
old approval is not approval for a new image; the original policy owns that gate.
"""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


preserved = _load('_reconcile_preserved_controller', HERE.parent / 'universal-overnight-v3/studio_controller.py')
bridge = _load('_reconcile_studio_bridge', HERE / 'runtime_bridge.py')
StudioError = preserved.StudioError


class StudioController(preserved.StudioController):
    def __init__(self, *, control_root, export_root, image_digest, backend=None, bridge_module=None):
        super().__init__(control_root=control_root, export_root=export_root,
                         image_digest=image_digest, backend=backend,
                         bridge_module=bridge if bridge_module is None else bridge_module)

    def _integration_gate(self, root, submission):
        report = bridge.preflight(submission, control_root=self.control_root,
                                  export_root=self.export_root, image_digest=self.image_digest)
        return {'allowed': report.get('renderAllowed') is True, 'phase': 'PREVIEW_5S',
                'blockers': [{'code': row.get('code', 'RECONCILE_NATIVE_GATE_BLOCKED')}
                             for row in report['checks'] if row['status'] in {'FAIL', 'BLOCKED'}]}
