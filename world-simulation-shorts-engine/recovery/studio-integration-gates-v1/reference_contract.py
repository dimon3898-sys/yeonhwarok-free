"""Explicit regression family; no implicit conversion of production Scenes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_STUDIO_EXACT_REFERENCE_V1"
PROFILE = "FREE_SWIFTSHADER_EXACT_65422"
SCENE_SHA = "aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159"
SOURCE_COMMIT = "2c097df2d02432a3f9ae4dae5d714dbc9eacd434"
RUNTIME_SIGNATURE = "b81774e0d8627f0269901daff6fdbd5fdbc06f7dec85f35849f4150525c1126c"
REQUEST = {"schema": SCHEMA, "profile": PROFILE, "sourceSceneSHA256": SCENE_SHA,
           "startFrame": 0, "endFrame": 150, "fps": 30, "width": 1080,
           "height": 1920, "audio": False}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def selected(value):
    return isinstance(value, dict) and (value.get("schema") == SCHEMA or value.get("profile") == PROFILE)


def normalize(value, *, capsule_root, error):
    # Equality alone permits bool/int aliases in Python. Check types as well.
    if (not isinstance(value, dict) or set(value) != set(REQUEST)
            or any(type(value[k]) is not type(v) or value[k] != v for k, v in REQUEST.items())):
        raise error("STUDIO_EXACT_REFERENCE_FIELDS_INVALID", status=400)
    scene_path = Path(capsule_root) / "world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json"
    if not scene_path.is_file() or scene_path.is_symlink() or hashlib.sha256(scene_path.read_bytes()).hexdigest() != SCENE_SHA:
        raise error("STUDIO_EXACT_REFERENCE_SOURCE_CHANGED")
    # Preserve the complete original bytes; no historical planner or resampling.
    scene = json.loads(scene_path.read_bytes())
    return {"schema": SCHEMA, "title": "65422 original source regression", "profile": PROFILE,
            "request": deepcopy(value), "requestSHA256": sha(value),
            "normalizerSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "sourceSceneSHA256": SCENE_SHA, "sourceCommit": SOURCE_COMMIT,
            "runtimeSourceSignature": RUNTIME_SIGNATURE, "videoPlan": scene,
            "sfx": {"enabled": False}, "softwareOnly": True}
