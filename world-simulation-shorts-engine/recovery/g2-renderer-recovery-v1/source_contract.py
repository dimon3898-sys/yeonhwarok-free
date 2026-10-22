"""Bind the unchanged synthetic Scene to a verified source-native terrain style.

Historical data, ownership, camera math and Area compilation remain owned by the
unchanged source adapter. This wrapper adds no geographic interpolation.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "universal-source-pipeline-v2"
REPO = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = load("_g2_recovery_unchanged_source_contract", OLD / "source_contract.py")
SCHEMA, PROFILE = original.SCHEMA, original.PROFILE


def fail(code):
    raise ValueError(code)


def _read_json(file):
    if file.is_symlink() or not file.is_file():
        fail("G2_RECOVERY_REQUIRED_SERVER_FILE_MISSING")
    return original.control.parse(file.read_bytes())


def recovery_bindings():
    """Only server-owned entrypoints; callers cannot choose executable paths."""
    files = [HERE / name for name in ("source_contract.py", "studio_controller.py",
        "studio_service.py", "software_worker.py", "capture_source.mjs",
        "capture_recovery.mjs", "terrain_style.py")]
    files += [HERE / "fixtures" / name for name in ("MAP_STYLE.json", "RECOVERY_STYLE_RECEIPT.json")]
    files += [OLD / name for name in ("native_runtime.mjs", "camera_numeric_contract.mjs",
        "source_geometry_contract.mjs", "studio_controller.py", "software_worker.py", "source_contract.py")]
    rows = []
    for file in files:
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(REPO):
            fail("G2_RECOVERY_EXECUTION_BINDING_MISSING")
        raw = file.read_bytes()
        rows.append({"path": file.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    return rows


def normalize_submission(value, *, source_root, expected_index_sha256):
    # Identical before/after authored Scene. Float lexical differences introduced
    # by JSON.stringify are equivalent; changing a number, actor or date is not.
    baseline = _read_json(OLD / "fixtures/DEMO_SOURCE_SCENE.json")
    if not original.same_json_value(value, baseline):
        fail("G2_RECOVERY_UNCHANGED_DEMO_SCENE_REQUIRED")
    result = original.normalize_submission(value, source_root=source_root,
        expected_index_sha256=expected_index_sha256)
    pipeline = result["sourcePipeline"]
    if (pipeline.get("mode") != "SYNTHETIC_TEST"
            or pipeline.get("scope") != "SYNTHETIC_TECHNICAL_DEMO"
            or pipeline.get("totalFrames") != 180 or pipeline.get("startFrame") != 0
            or value.get("fps") != 30 or value.get("resolution") != [1080, 1920]):
        fail("G2_RECOVERY_SYNTHETIC_SIX_SECONDS_ONLY")
    receipt = _read_json(HERE / "fixtures/RECOVERY_STYLE_RECEIPT.json")
    style = load("_g2_recovery_actual_terrain_style", HERE / "terrain_style.py")
    qualified = style.validate_style(receipt,
        pipeline["runtimePayload"].get("cameraSchedule", []), asset_root=REPO)
    if qualified.get("ready") is not True:
        fail("G2_RECOVERY_SOURCE_STYLE_NOT_READY")
    # Source registry owns the Native plan as well as the separate style receipt.
    # Both must name the exact same image and geographic metadata.
    native = pipeline["runtimePayload"].get("nativePlan", {}).get("assets", {}).get("terrain", {})
    terrain = receipt.get("terrainAsset", {})
    equal = {"file": "path", "url": "url", "sha256": "sha256", "bounds": "bounds",
        "dimensions": "dimensions", "pixelSpacing": "pixelSpacing", "classification": "classification"}
    if any(not original.same_json_value(native.get(left), terrain.get(right))
           for left, right in equal.items()):
        fail("G2_RECOVERY_NATIVE_STYLE_BINDING_MISMATCH")
    pipeline["sourceStyle"] = deepcopy(receipt)
    pipeline["sourceStyleSHA256"] = hashlib.sha256(
        (HERE / "fixtures/RECOVERY_STYLE_RECEIPT.json").read_bytes()).hexdigest()
    pipeline["sourceStyleReceiptSHA256"] = pipeline["sourceStyleSHA256"]
    pipeline["recoveryBindings"] = recovery_bindings()
    pipeline["recoveryScope"] = {
        "schema": "WORLD_ENGINE_G2_RECOVERY_EXECUTION_V1", "historicalRenderAllowed": False,
        "sameSceneAsBaseline": True, "paidGpuAllowed": False, "maxFrames": 180,
        "runtime": "UNCHANGED_UNIVERSAL_SOURCE_RUNTIME_V2", "rendererChanged": False,
        "visualQualityApproved": False}
    return result
