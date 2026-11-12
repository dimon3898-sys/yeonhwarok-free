#!/usr/bin/env python3
"""Focused, non-destructive 64306 six-second input correction.
This does NOT qualify GIS sources or certify formal compiler admission.
Usage: python3 fix_reference_input.py INPUT.json OUTPUT.json
"""
import json
import sys
from pathlib import Path

def correct(source):
    assert source.get("schema") == "WORLD_ENGINE_PRESENTATION_PROMPT_V2"
    data = source["data"]
    assert data["durationSeconds"] == 6 and data["fps"] == 30
    assert data["resolution"] == {"width": 1080, "height": 1920}
    assert len(data["scenes"]) == 1
    scene = data["scenes"][0]
    assert scene["startFrame"] == 0 and scene["endFrame"] == 180
    timing = scene["facts"]["scene_timing"]
    assert timing["total_frames"] == 180 and timing["final_hold_frames"] == 30
    assert timing["event_start_frame"] + timing["action_frames"] + timing["final_hold_frames"] == 180
    assert source["presentation"]["camera"]["keyframes"][-1]["frame"] == 179
    assert source["presentation"]["camera"]["keyframes"][-1]["center"] == source["presentation"]["camera"]["keyframes"][-2]["center"]
    assert source["presentation"]["camera"]["keyframes"][-1]["zoom"] == source["presentation"]["camera"]["keyframes"][-2]["zoom"]
    colors = source["presentation"]["territoryColors"]
    changes = []
    for name, rgba in colors.items():
        assert len(rgba) == 4 and all(isinstance(v, (float, int)) for v in rgba)
        if rgba[3] > 0.6:
            changes.append({"field": f"presentation.territoryColors.{name}[3]", "before": rgba[3], "after": 0.6})
            rgba[3] = 0.6
    return changes

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: fix_reference_input.py INPUT.json OUTPUT.json")
    src, dst = map(Path, sys.argv[1:])
    if src.resolve() == dst.resolve() or dst.exists():
        raise SystemExit("Refusing to overwrite input or existing output")
    obj = json.loads(src.read_text(encoding="utf-8"))
    changes = correct(obj)
    dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PARTIAL_CORRECTION_ONLY_NOT_FORMAL_PASS",
        "changes": changes,
        "unresolved": [
            "GEOGRAPHIC event family is unsupported by existing planner",
            "Native source geometry review/admission is unverified",
            "Independent simultaneous yellow/cyan region rendering not proven",
            "Camera geographic coverage and coast-pin country membership unverified"
        ],
        "oldPASSReruns": 0, "gpuStarts": 0
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
