"""Fail unsupported native selections before the unchanged GPU manager starts.

This wraps a separately loaded previous bridge. Original source/catalog/image
admission runs first; its exact receipt is supplied to the additional guard.
The guard never substitutes for source authority or grants GPU approval.
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


preserved = _load('_reconcile_preserved_bridge', HERE.parent / 'universal-overnight-v3/runtime_bridge.py')
capabilities = _load('_reconcile_native_capabilities', HERE / 'native_capabilities.py')
_preserved_gate_context = preserved.gate_context


def gate_context(submission, *, image_digest, control_root=None):
    context = _preserved_gate_context(submission, image_digest=image_digest, control_root=control_root)
    capabilities.guard_native_selection(submission['overnightV3']['visualExtensions'],
                                        source_admission=context['selectedVisualAdmission'])
    # Null selections preserve the complete prior context byte-for-byte. New
    # diagnostic facts are not mistaken for image/render/source approval.
    return context


# All these original functions resolve their module-global gate_context at call
# time. Patching this isolated module instance covers preflight, prepare and
# authorization without duplicating manager/capture logic or touching its file.
preserved.gate_context = gate_context
preflight = preserved.preflight
prepare_runtime_request = preserved.prepare_runtime_request
_authorize_start = preserved._authorize_start
start_studio_job = preserved.start_studio_job
studio_status = preserved.studio_status
start_studio_recovery = preserved.start_studio_recovery
