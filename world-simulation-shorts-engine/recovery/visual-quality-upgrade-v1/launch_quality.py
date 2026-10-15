#!/usr/bin/env python3
"""Fixed quality runtime selection over the unchanged ASTRA launch controller."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ENGINE_HERE=Path('/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/visual-quality-upgrade-v1')
if not ENGINE_HERE.is_dir():
    ENGINE_HERE=HERE
ORIGINAL=ENGINE_HERE.parent/'astra-gpu-activation-v1'/'launch_astra.py'
# Original controller imports verified original bootstrap/storage/GPU modules.
# This isolated module instance changes no imported singleton or source file.
spec=importlib.util.spec_from_file_location('_quality_isolated_astra_launcher',ORIGINAL)
inherited=importlib.util.module_from_spec(spec)
spec.loader.exec_module(inherited)
sys.path.insert(0,str(ENGINE_HERE))
import prepare_quality


def native_command(admission):
    return ['node',str(ENGINE_HERE/'capture_quality.mjs'),'--admission-file',
            str(admission.admission_file),'--output-root',str(admission.output_root)]


def main(argv=None):
    # Only fixed explicit selectors differ. The original GPU admission, common
    # lease, VRAM/deadline/termination monitor, export and receipt checks execute.
    inherited._native_command=native_command
    inherited.prepare_activation=prepare_quality
    return inherited.main(argv)


if __name__=='__main__':
    raise SystemExit(main())
