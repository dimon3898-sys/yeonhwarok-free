#!/usr/bin/env python3
"""Fixed reference V2 capture over the unchanged original GPU launch controller."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ENGINE_HERE = Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/reference-visual-master-v2')
if not ENGINE_HERE.is_dir():
    ENGINE_HERE = HERE
ORIGINAL = ENGINE_HERE.parent / 'astra-gpu-activation-v1/launch_astra.py'
if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() != 'b5c86c7d409955422cd780c91672ac932c78955e970425fcf55236d615033c87':
    raise RuntimeError('PINNED_ASTRA_LAUNCH_REQUIRED')
spec = importlib.util.spec_from_file_location('_reference_v2_isolated_astra_launcher', ORIGINAL)
inherited = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inherited)
sys.path.insert(0, str(ENGINE_HERE))
import prepare_ref2


def native_command(admission):
    return ['node', str(ENGINE_HERE / 'capture_ref2.mjs'), '--admission-file',
            str(admission.admission_file), '--output-root', str(admission.output_root)]


def main(argv=None):
    # The isolated original controller retains normal mode, source/dependency
    # checks, common native lease, fresh admission, budgets, termination, exact
    # seven-file export and native ASTRA receipt. No Quality nested hook runs.
    inherited._native_command = native_command
    inherited.prepare_activation = prepare_ref2
    return inherited.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
