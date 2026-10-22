"""Strict source-to-Scene adapter. Geometry receipts remain server-owned.

This adds a source Scene family; it neither rewrites the protected historical
planner nor infers ownership from an open position line or a country polygon.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2"
PROFILE = "FREE_SOURCE_SCENE_REVIEW"
spec = importlib.util.spec_from_file_location("_source_reused_control", HERE.parent / "studio-integration-gates-v1/control_provider.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
TOP = {"schema", "scenario_id", "event_id", "title", "durationSeconds", "fps", "resolution", "startFrame",
       "time_interval", "source_bundle_id", "source_refs", "geometry", "actors", "control_states",
       "frontline_geometries", "event_location", "camera", "transition", "confidence", "visual_annotations", "audio_cue_slots"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def selected(value):
    return isinstance(value, dict) and value.get("schema") == SCHEMA


def same_json_value(left,right):
    """JSON numbers have no integer/float lexical identity; booleans do."""
    if type(left) in (int,float) and type(right) in (int,float):
        return math.isfinite(left) and math.isfinite(right) and left==right
    if type(left) is not type(right):return False
    if isinstance(left,dict):
        return left.keys()==right.keys() and all(same_json_value(left[k],right[k]) for k in left)
    if isinstance(left,list):
        return len(left)==len(right) and all(same_json_value(a,b) for a,b in zip(left,right))
    return left==right


def fail(code):
    raise ValueError(code)


def _text(value):
    return isinstance(value, str) and 1 <= len(value) <= 256 and not any(ord(c) < 32 for c in value)


def _bound(root, row):
    if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
        fail("SOURCE_FILE_BINDING_REQUIRED")
    path = Path(row["path"])
    if path.is_absolute() or ".." in path.parts:
        fail("SOURCE_PATH_ESCAPE")
    file = root / path
    if any(p.is_symlink() for p in (file, *file.parents)) or not file.resolve().is_relative_to(root.resolve()):
        fail("SOURCE_SYMLINK_OR_SCOPE_REJECTED")
    raw = file.read_bytes()
    if sha(raw) != row["sha256"]:
        fail("SOURCE_FILE_HASH_MISMATCH")
    return control.parse(raw)


def normalize_submission(value, *, source_root, expected_index_sha256):
    if not isinstance(value, dict) or set(value) != TOP or value.get("schema") != SCHEMA:
        fail("SOURCE_SCENE_UNKNOWN_OR_MISSING_FIELDS")
    if any(not _text(value[k]) for k in ("scenario_id", "event_id", "title", "source_bundle_id")):
        fail("SOURCE_SCENE_IDENTIFIERS_REQUIRED")
    if (type(value["durationSeconds"]) not in (int, float) or not math.isfinite(value["durationSeconds"])
            or type(value["fps"]) is not int or value["fps"] != 30 or value["resolution"] != [1080, 1920]
            or type(value["startFrame"]) is not int or value["startFrame"] < 0):
        fail("SOURCE_SCENE_CLOCK_AND_OUTPUT_REQUIRED")
    total = value["durationSeconds"] * value["fps"]
    if not float(total).is_integer() or not 2 <= total <= 240:
        fail("SOURCE_SCENE_BOUNDED_SOFTWARE_FRAME_RANGE")
    total = int(total)
    root = Path(source_root)
    if not root.is_absolute() or root.is_symlink():
        fail("SOURCE_SERVER_ROOT_REQUIRED")
    index_raw = (root / "INDEX.json").read_bytes()
    if sha(index_raw) != expected_index_sha256:
        fail("SOURCE_SERVER_INDEX_HASH_MISMATCH")
    index = control.parse(index_raw)
    if index.get("schema") != "WORLD_ENGINE_SERVER_SOURCE_PACKAGES_V2":
        fail("SOURCE_SERVER_INDEX_SCHEMA")
    entry = index["packages"].get(value["source_bundle_id"])
    if entry is None:
        fail("SOURCE_BUNDLE_NOT_REGISTERED")
    bundle = _bound(root, entry)
    # Fields below select source-qualified data and execution settings. The
    # request cannot replace geometry, camera admission, dates or rights.
    expected = bundle["scene"]
    for field in TOP - {"title", "actors"}:
        if not same_json_value(value[field],expected[field]):
            fail("SOURCE_SCENE_BINDING_MISMATCH_" + field.upper())
    actors = value["actors"]
    if not isinstance(actors, list) or len(actors) != len(expected["actors"]):
        fail("SOURCE_ACTOR_LIST_REQUIRED")
    for actor, original in zip(actors, expected["actors"]):
        if not isinstance(actor, dict) or set(actor) != {"actor_id", "actor_color"} or actor["actor_id"] != original["actor_id"]:
            fail("SOURCE_ACTOR_ID_MISMATCH")
        color = actor["actor_color"]
        if not isinstance(color, list) or len(color) != 3 or any(type(c) not in (int, float) or not math.isfinite(c) or not 0 <= c <= 1 for c in color):
            fail("SOURCE_ACTOR_COLOR_RANGE")
    blockers = list(bundle.get("blockers", []))
    if value["geometry"] != {"crs": "EPSG:4326", "coordinate_transform": {"kind": "IDENTITY", "status": "VERIFIED", "axis_order": "longitude_latitude"}}:
        blockers.append("SOURCE_GEOGRAPHIC_REGISTRATION_UNVERIFIED")
    if value["audio_cue_slots"]:
        blockers.append("SOURCE_AUDIO_CUE_ADAPTER_NOT_CONNECTED")
    if value["visual_annotations"]:
        blockers.append("SOURCE_CUSTOM_ANNOTATION_ADAPTER_NOT_CONNECTED")
    mode = bundle["mode"]
    if mode not in ("SYNTHETIC_TEST", "PRODUCTION"):
        fail("SOURCE_DATA_MODE_UNSUPPORTED")
    frames = []
    rows = bundle["states"]
    if rows and len(rows) != total:
        blockers.append("SOURCE_CONTINUOUS_SAMPLED_FRAME_STATES_MISSING")
    if not rows:
        blockers.append("SOURCE_CONTROL_START_AND_END_MISSING")
    for local, row in enumerate(rows):
        state = _bound(root, row["state"])
        if state["frame"] != value["startFrame"] + local:
            fail("SOURCE_FRAME_GAP_DUPLICATE_OR_OFFSET")
        manifest = root / row["receipts"]["path"]
        registry = control.SourceRegistry.from_manifest(manifest,
            expected_sha256=row["receipts"]["sha256"], mode=mode)
        frame = control.compile_control_state(state, registry)
        if not frame.source_binding_valid():
            fail("SOURCE_COMPILED_STATE_CHANGED")
        if set(m["factionId"] for m in frame["ownerMasks"]) != {a["actor_id"] for a in actors}:
            fail("SOURCE_OWNER_ACTOR_MISSING_OR_WRONG")
        if frame["completeExplicitDomainPartition"] is not True:
            blockers.append("SOURCE_FULL_CONTROL_AREA_NOT_QUALIFIED")
        if not frame["sharedFront"]["geometry"]["coordinates"]:
            blockers.append("SOURCE_SHARED_FRONT_NOT_PRESENT")
        if mode == "PRODUCTION" and frame["classification"] != "observed":
            blockers.append("SOURCE_HISTORICAL_OBSERVED_CONTROL_REQUIRED")
        frames.append(dict(frame))
    native = _bound(root, bundle["native"]) if bundle.get("native") else None
    if native and len(native.get("cameraSchedule", [])) != total:
        fail("SOURCE_CAMERA_GLOBAL_CLOCK_GAP")
    if not native:
        blockers.append("SOURCE_CAMERA_PLAN_AND_ADMISSION_MISSING")
    if mode == "PRODUCTION" and bundle.get("full_control_area_status") != "SOURCE_QUALIFIED_FULL_AREA":
        blockers.append("G2_FULL_CONTROL_AREA_BLOCKED")
    if mode == "PRODUCTION":
        blockers.append("SOURCE_HISTORICAL_PIXEL_CONSUMER_NOT_ADMITTED")
    artifacts = [_bound(root, binding) for binding in bundle.get("source_artifacts", [])]
    blockers = sorted(set(blockers))
    ready = not blockers
    runtime = {**({k: native[k] for k in ("nativePlan", "cameraPlan", "cameraSchedule", "sourceBindings")} if native else {}),
        "frames": frames, "actors": deepcopy(actors), "annotations": deepcopy(value["visual_annotations"]),
        "eventLocation": deepcopy(value["event_location"]["coordinates"]), "profile": {}}
    return {"schema": SCHEMA, "title": value["title"], "profile": PROFILE, "videoPlan": deepcopy(value),
        "sfx": {"enabled": False}, "sourcePipeline": {"version": 2, "ready": ready,
            "mode": mode, "scope": "SYNTHETIC_TECHNICAL_DEMO" if mode == "SYNTHETIC_TEST" else "G3_SOURCE_QUALIFIED_HISTORICAL",
            "blockers": blockers, "totalFrames": total, "startFrame": value["startFrame"], "fps": 30,
            "requestSHA256": sha(canonical(value)), "sourceIndexSHA256": expected_index_sha256,
            "sourceBundleSHA256": entry["sha256"], "runtimePayload": runtime,
            "traceStages": ["STRICT_SOURCE_SCENE", "SERVER_PINNED_INDEX", "SOURCE_MANIFEST_AND_GEOMETRY_SHA",
                "UNCHANGED_AREA_V3_VALIDATOR", "SOURCE_CONTROL_STATE_PROVIDER", "SAME_FRAME_OWNER_AND_SHARED_FRONT",
                "ACTUAL_CAMERA_V5_SCHEDULE", "NATIVE_FACTORY_AND_AREA_ADAPTER"],
            "geographicRegistration": deepcopy(bundle.get("geographic_registration")),
            "sourceObservations": [{"schema": item.get("schema"), "sourceSHA256": item.get("source_sha256"),
                "crs": item.get("page_coordinates", {}).get("crs"), "positionPaths": len(item.get("positions", [])),
                "positions": deepcopy(item.get("positions", [])),
                "coordinateTransform": deepcopy(item.get("page_coordinates", {}).get("coordinate_transform")),
                "geographicRenderAllowed": item.get("render_allowed", False)} for item in artifacts],
            "adapterSourceBindings": [{"path": name, "sha256": sha((HERE/name).read_bytes())}
                for name in ("source_contract.py", "native_runtime.mjs", "camera_numeric_contract.mjs", "source_geometry_contract.mjs", "capture_source.mjs")],
            "fullControlAreaStatus": bundle.get("full_control_area_status"), "gpuVerified": False, "userApproved": False}}
