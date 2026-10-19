"""Bounded, package-owned observations of unchanged camera output.

Only frames actually measured in saved source-bound captures are known. This
cache does not create camera motion, interpolate missing poses or admit GPU
execution. Original history admission must run before loading this authority.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "WORLD_ENGINE_CAMERA_ACTIVITY_EVIDENCE_V3"
CAMERA_MODULE_PATHS = (
    "web/map_infographic_v1/camera_director_v5.mjs",
    "web/map_infographic_v1/camera_director_v4.mjs",
    "web/map_infographic_v1/camera_gpu_pipeline_v5.mjs",
    "web/map_infographic_v1/camera_gpu_pipeline_v2.mjs",
    "web/map_infographic_v1/moving_layout_v4.mjs",
    "web/map_infographic_v1/area_native_bridge_v3.mjs",
    "recovery/universal-integration-completion-v2/camera_extension.mjs",
    "recovery/universal-integration-completion-v2/production_camera_bridge.mjs",
    "recovery/universal-production-v3/production_camera.mjs",
    "recovery/universal-integration-v1/presentation.mjs",
)
QUALIFICATION = {"origin": "ACTUAL_SAVED_SWIFTSHADER_FRAMES", "physicalNvidiaVerified": False,
                 "interpolationAdded": False, "unknownFramesAreStatic": False}
_SOURCE_READER = None


class CameraEvidenceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def _hex(value, count=64):
    return type(value) is str and len(value) == count and all(c in "0123456789abcdef" for c in value)


def _fail(code):
    raise CameraEvidenceError(code)


def camera_semantic_sha(plan):
    """Ignore only existing image-binding slots allowed by old history owner.

    All geometry, events, timing, camera inputs, source hashes, material and
    marker fields remain in the identity. No new slot or historical state is
    added. This identity is not a substitute for original source admission.
    """
    result = deepcopy(plan)
    records = [result, *result.get("scenes", [])]
    for record in records:
        profile = record.get("renderProfile") if isinstance(record, dict) else None
        if isinstance(profile, dict) and "imageDigest" in profile:
            profile["imageDigest"] = "OPERATOR_IMAGE_DIGEST_SLOT"
    return sha(canonical(result))


def _read_regular(file, limit=16 * 1024 * 1024):
    # Reuse the already bounded no-follow source reader, not a network request.
    global _SOURCE_READER
    if _SOURCE_READER is None:
        spec = importlib.util.spec_from_file_location("_camera_evidence_exact_source_reader", HERE / "preview_contract.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SOURCE_READER = module._read_regular
    raw = _SOURCE_READER(Path(file).absolute())
    if len(raw) > limit:
        _fail("CAMERA_EVIDENCE_SOURCE_TOO_LARGE")
    return raw


def camera_module_hashes(engine_root=None):
    root = Path(engine_root) if engine_root is not None else HERE.parent.parent
    return {name: sha(_read_regular(root / name)) for name in CAMERA_MODULE_PATHS}


def validate_camera_evidence(value, plan, bindings, *, module_hashes=None):
    """Pure validation of a trusted caller's evidence, never a client field.

    The package loader below separately verifies the manifest and actual old
    camera bytes. A test may supply an isolated trusted evidence fixture.
    """
    if (not isinstance(value, dict) or set(value) != {"schema", "binding", "sourceProofs", "observations",
            "qualification", "evidenceSHA256"} or value.get("schema") != SCHEMA
            or value.get("qualification") != QUALIFICATION):
        _fail("CAMERA_EVIDENCE_SCHEMA_INVALID")
    body = {key: item for key, item in value.items() if key != "evidenceSHA256"}
    if not _hex(value.get("evidenceSHA256")) or sha(canonical(body)) != value["evidenceSHA256"]:
        _fail("CAMERA_EVIDENCE_BODY_CHANGED")
    binding = value.get("binding")
    if not isinstance(binding, dict) or set(binding) != {"planCameraSemanticSHA256", "completionProfileSHA256", "cameraModuleSHA256"}:
        _fail("CAMERA_EVIDENCE_BINDING_INVALID")
    modules = binding.get("cameraModuleSHA256")
    if (not isinstance(modules, dict) or set(modules) != set(CAMERA_MODULE_PATHS)
            or any(not _hex(item) for item in modules.values())):
        _fail("CAMERA_EVIDENCE_CAMERA_MODULES_REQUIRED")
    if (binding["planCameraSemanticSHA256"] != camera_semantic_sha(plan)
            or binding["completionProfileSHA256"] != bindings.get("completionProfileSHA256")):
        _fail("CAMERA_EVIDENCE_PROFILE_NOT_THIS_SOURCE")
    if module_hashes is not None and modules != module_hashes:
        _fail("CAMERA_EVIDENCE_OLD_CAMERA_BYTES_CHANGED")
    proofs = value.get("sourceProofs")
    proof_keys = {"traceSourceCommit", "framesSHA256", "receiptSHA256", "sourceManifestSHA256", "frameCount",
                  "startFrame", "endFrame", "originalPlanSHA256"}
    if not isinstance(proofs, list) or not 1 <= len(proofs) <= 32:
        _fail("CAMERA_EVIDENCE_ACTUAL_SOURCE_PROOFS_REQUIRED")
    for proof in proofs:
        if (not isinstance(proof, dict) or set(proof) != proof_keys
                or not _hex(proof.get("traceSourceCommit"), 40)
                or any(not _hex(proof.get(key)) for key in ("framesSHA256", "receiptSHA256", "sourceManifestSHA256", "originalPlanSHA256"))
                or any(type(proof.get(key)) is not int for key in ("frameCount", "startFrame", "endFrame"))
                or not 0 <= proof["startFrame"] < proof["endFrame"] <= plan["totalFrames"]
                or proof["endFrame"] - proof["startFrame"] != proof["frameCount"]):
            _fail("CAMERA_EVIDENCE_SOURCE_PROOF_INVALID")
    observations = value.get("observations")
    if not isinstance(observations, list) or not 1 <= len(observations) <= min(plan["totalFrames"], 72000):
        _fail("CAMERA_EVIDENCE_BOUNDED_ACTUAL_OBSERVATIONS_REQUIRED")
    previous = -1
    for row in observations:
        if not isinstance(row, dict) or set(row) != {"frame", "bounds", "rawRgbaSHA256", "pngSHA256", "sourceProofIndices"}:
            _fail("CAMERA_EVIDENCE_OBSERVATION_INVALID")
        frame, bounds, indices = row.get("frame"), row.get("bounds"), row.get("sourceProofIndices")
        if (type(frame) is not int or not previous < frame < plan["totalFrames"]
                or not isinstance(bounds, list) or len(bounds) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds)
                or not -180 <= bounds[0] < bounds[2] <= 180 or not -90 <= bounds[1] < bounds[3] <= 90
                or not _hex(row.get("rawRgbaSHA256")) or not _hex(row.get("pngSHA256"))
                or not isinstance(indices, list) or not indices or len(indices) != len(set(indices))
                or any(type(i) is not int or not 0 <= i < len(proofs)
                       or not proofs[i]["startFrame"] <= frame < proofs[i]["endFrame"] for i in indices)):
            _fail("CAMERA_EVIDENCE_OBSERVATION_INVALID")
        previous = frame
    return deepcopy(value)


def load_bound_camera_evidence(plan, bindings, *, evidence_file=None, module_hashes=None):
    """Read only package-owned, manifest-bound observations; mismatches UNKNOWN.

    No missing or different-source cache is interpreted as a static camera.
    The caller must perform existing source admission before using this helper.
    """
    file = Path(evidence_file) if evidence_file is not None else HERE / "CAMERA_ACTIVITY_EVIDENCE.json"
    if not file.exists():
        return None
    raw = _read_regular(file)
    value = json.loads(raw)
    expected = value.get("binding", {}) if isinstance(value, dict) else {}
    if (expected.get("planCameraSemanticSHA256") != camera_semantic_sha(plan)
            or expected.get("completionProfileSHA256") != bindings.get("completionProfileSHA256")):
        return None
    if evidence_file is None:
        manifest = json.loads(_read_regular(HERE / "OVERNIGHT_FILES.json"))
        if manifest.get("files", {}).get(file.name) != sha(raw):
            _fail("CAMERA_EVIDENCE_PACKAGE_MANIFEST_MISMATCH")
    actual_modules = camera_module_hashes() if module_hashes is None else module_hashes
    return validate_camera_evidence(value, plan, bindings, module_hashes=actual_modules)


def camera_window_metrics(evidence, start, end):
    if evidence is None:
        return {"status": "NOT_OBSERVED", "observedFrames": 0, "motionPairs": None, "boundsVariants": None}
    indexed = {row["frame"]: row["bounds"] for row in evidence["observations"]}
    measured = [indexed[frame] for frame in range(start, end) if frame in indexed]
    if len(measured) != end - start:
        return {"status": "NOT_FULLY_OBSERVED", "observedFrames": len(measured), "motionPairs": None, "boundsVariants": None}
    variants = len({tuple(bounds) for bounds in measured})
    pairs = sum(a != b for a, b in zip(measured, measured[1:]))
    return {"status": "OBSERVED_MOVING" if pairs else "OBSERVED_STATIC", "observedFrames": len(measured),
            "motionPairs": pairs, "boundsVariants": variants}


def measured_candidate_windows(evidence, frame_count):
    if evidence is None:
        return []
    frames = {row["frame"] for row in evidence["observations"]}
    return [start for start in sorted(frames) if all(frame in frames for frame in range(start, start + frame_count))]
