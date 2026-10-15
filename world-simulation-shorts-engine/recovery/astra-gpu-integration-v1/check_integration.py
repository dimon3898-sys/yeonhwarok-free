#!/usr/bin/env python3
"""Read-only, source-bound ASTRA connection audit; never runs a renderer.

Exit 0 means that this audit completed, including an expected BLOCKED
integration decision. It is not GPU admission, a rendering test, or an image
contents inspection. Unrecognized/modified inputs fail closed with exit 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import stat
import subprocess
import sys


BASE_COMMIT = "5269521131059cacdd18de5110ee3aaae302b8b5"
CPU_COMMIT = "a002d89492734bfa9d17b98145ee6cb9a3b366a2"
PACKAGE_COMMIT = "2f9158b"
ENGINE = "world-simulation-shorts-engine"
RECOVERY = ENGINE + "/recovery/"
PACKAGE = RECOVERY + "rtx-gpu-package-v1/"
CPU = RECOVERY + "astra-cpu-data-v1/"
PHASE_A = RECOVERY + "astra-map-quality-v1/"
WEB = ENGINE + "/web/map_infographic_v1/"

# This is a focused read set, not a repeated archive / 160-file package audit.
PATHS = {
    "sourceContract": PACKAGE + "source_contract.json",
    "gpuLauncher": PACKAGE + "gpu_launcher.py",
    "hardwareRuntime": PACKAGE + "hardware_runtime.mjs",
    "hardwareCapture": PACKAGE + "hardware_render.mjs",
    "jobManager": RECOVERY + "gcube-detached-render-v1/job_manager.py",
    "storageLaunch": RECOVERY + "gcube-storage-fix-v1/launch.py",
    "imageEvidence": RECOVERY + "gcube-detached-render-v1/IMAGE.json",
    "v4Composition": WEB + "map_engine_unit_gpu_adapter_v4.mjs",
    "nativeRenderer": WEB + "renderer.mjs",
    "terrainMaterial": WEB + "reference_terrain_material_v4.mjs",
    "frontier": WEB + "reference_control_frontier_light_v3.mjs",
    "camera": WEB + "reference_camera_adapter_v1.mjs",
    "cameraV5": WEB + "camera_director_v5.mjs",
    "nativeScene": RECOVERY + "reference-reproduction-v1/fixtures/scene-native.json",
    "scenePlan": RECOVERY + "moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json",
    "originalScenePlan": RECOVERY + "map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json",
    "renderFixture": RECOVERY + "moving-frontier-glow-fix-v1/fixtures/RUNTIME_FIXTURE.json",
    "inputManifest": RECOVERY + "planner-scene-json-v1/fixtures/input-manifest.json",
    "cpuScene": CPU + "astra_cpu/scene.py",
    "cpuPipeline": CPU + "astra_cpu/pipeline.py",
    "cpuManifest": CPU + "SOURCE_ASSET_MANIFEST.json",
    "neutralManifest": CPU + "fixtures/neutral-output/CPU_PREPARATION_MANIFEST.json",
    "sampleMetadata": PHASE_A + "evidence/SAMPLE_PARSE_AUDIT.json",
    "cameraEnvelope": PHASE_A + "evidence/CAMERA_SOURCE_ENVELOPE.json",
}


class AuditError(ValueError):
    pass


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def read_regular(root: Path, relative: str) -> bytes:
    """Reject symlinks and non-regular files without altering the source tree."""
    path = root
    for part in Path(relative).parts:
        if part in {".", ".."}:
            raise AuditError("NON_CANONICAL_INPUT_PATH")
        path = path / part
        if path.is_symlink():
            raise AuditError("SYMLINK_INPUT_REJECTED")
    attributes = path.stat()
    if not stat.S_ISREG(attributes.st_mode) or attributes.st_size > 8 * 1024**2:
        raise AuditError("INVALID_OR_OVERSIZE_INPUT")
    return path.read_bytes()


def baseline_hashes(repo_root: Path) -> dict[str, str]:
    """Use the existing exact checkpoint, never current HEAD as an authority."""
    result = {}
    for relative in PATHS.values():
        try:
            completed = subprocess.run(
                ["git", "show", BASE_COMMIT + ":" + relative], cwd=repo_root,
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            raise AuditError("BASELINE_GIT_OBJECT_UNAVAILABLE") from None
        result[relative] = digest(completed.stdout)
    return result


def bbox(value):
    if (not isinstance(value, list) or len(value) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in value)
            or not -180 <= value[0] < value[2] <= 180
            or not -90 <= value[1] < value[3] <= 90):
        raise AuditError("INVALID_SAVED_NON_WRAPPING_BBOX")
    return value


def coverage(source, target):
    """Envelope overlap in degree-coordinate area, not surface/pixel coverage."""
    source, target = bbox(source), bbox(target)
    west, south = max(source[0], target[0]), max(source[1], target[1])
    east, north = min(source[2], target[2]), min(source[3], target[3])
    overlap = None if west >= east or south >= north else [west, south, east, north]
    ratio = (0.0 if overlap is None else
             (east-west)*(north-south)/((target[2]-target[0])*(target[3]-target[1])))
    return {"sourceBBox": source, "nativeEnvelopeBBox": target,
            "intersectionBBox": overlap,
            "envelopeDegreeAreaFraction": ratio,
            "fullEnvelopeCovered": (source[0] <= target[0] and source[1] <= target[1]
                                    and source[2] >= target[2] and source[3] >= target[3]),
            "measureMeaning": "BBOX_DEGREE_COORDINATE_AREA_NOT_RENDERED_PIXEL_OR_GROUND_COVERAGE"}


def _condition(texts, key, *needles):
    return all(needle in texts[key] for needle in needles)


def _reference(texts, key, needle):
    offset = texts[key].index(needle)
    return {"path": PATHS[key], "line": texts[key][:offset].count("\n") + 1,
            "sourceText": needle}


def audit(repo_root: Path, *, anchors=None):
    """Audit known immutable sources; anchors is an offline test seam only."""
    root = Path(repo_root).resolve(strict=True)
    expected = baseline_hashes(root) if anchors is None else anchors
    result = {
        "schema": "ASTRA_GPU_CONNECTION_AUDIT_V1",
        "baselineCommit": BASE_COMMIT, "cpuCommit": CPU_COMMIT,
        "gpuPackageCommit": PACKAGE_COMMIT,
        "auditStatus": "FAIL", "integrationDecision": "BLOCKED_SOURCE_AUDIT_REQUIRED",
        "gpuExecuted": False, "renderExecuted": False,
        "imageBuilt": False, "imageInspectionExecuted": False,
        "oldFullTestsExecuted": False, "archiveMembersReaudited": False,
        "sourceChecks": [], "classification": [], "blockingReasons": [],
    }
    bodies = {}
    for label, relative in PATHS.items():
        try:
            body = read_regular(root, relative)
            actual = digest(body)
            preserved = actual == expected.get(relative)
            result["sourceChecks"].append({"role": label, "path": relative,
                                           "sha256": actual, "expectedSha256": expected.get(relative),
                                           "status": "PASS" if preserved else "FAIL"})
            if preserved:
                bodies[label] = body
        except (AuditError, OSError):
            result["sourceChecks"].append({"role": label, "path": relative,
                                           "status": "FAIL", "error": "INPUT_UNREADABLE_OR_UNSAFE"})
    result["sourcePreservation"] = "PASS" if len(bodies) == len(PATHS) else "FAIL"
    if result["sourcePreservation"] != "PASS":
        result["blockingReasons"] = ["SOURCE_CHANGED_OR_UNAVAILABLE_REAUDIT_REQUIRED"]
        result["classification"] = [{"feature": "active_render_selection", "state": "UNKNOWN_SOURCE_CHANGED"}]
        return result

    texts = {key: body.decode("utf-8") for key, body in bodies.items()}
    contract = json.loads(texts["sourceContract"])
    if contract.get("sourceCommits", {}).get("cpu") != CPU_COMMIT:
        raise AuditError("CPU_PROVENANCE_CONTRACT_MISMATCH")
    records = {item["repoPath"]: item for item in contract["files"]}
    selected = []
    for role, relative in PATHS.items():
        if relative in records:
            record = records[relative]
            good = record["sha256"] == digest(bodies[role]) and record["bytes"] == len(bodies[role])
            selected.append({"path": relative, "status": "PASS" if good else "FAIL"})
    result["selectedOriginalContractChecks"] = selected
    if any(check["status"] != "PASS" for check in selected):
        raise AuditError("ORIGINAL_RENDER_SOURCE_CONTRACT_MISMATCH")

    conditions = {
        "fixedManagerToOriginalLaunch": _condition(texts, "jobManager",
            "LAUNCH = Path('/opt/world-engine-storage-fix/launch.py')",
            "str(LAUNCH), '--render-65422'"),
        "fixedGpuLauncherToOriginalCapture": _condition(texts, "gpuLauncher",
            'str(HERE / "hardware_render.mjs")', '"--admission-file"'),
        "fixedRuntimeToV4Adapter": _condition(texts, "hardwareRuntime",
            "await import('/modules/map_engine_unit_gpu_adapter_v4.mjs')",
            "const pipeline=await createMapEngineUnitGpuAdapterV4("),
        "sceneAndLightingLocked": _condition(texts, "hardwareRuntime",
            "ALL_SCENE_FIELDS_EXCEPT_CURRENT_FRONT_GLOW_ARE_LOCKED",
            "TERRAIN_RELIEF_LIGHTING_IS_LOCKED"),
        "v4DemDisabled": _condition(texts, "v4Composition",
            "factory.renderFrame({mode:5,graphics:false,boundaries:false,glow:false,dem:false,"),
        "v4TerrainBeforeOwnershipAndFrontier": _condition(texts, "v4Composition",
            "terrain.draw({bounds,coverage,frame,fps:track.fps})",
            "actualTerrainTexture:terrain.outputTexture"),
        "nativeScreenCoverageAvailable": _condition(texts, "nativeRenderer", "coverage:()=>readTarget(covTarget)"),
        "cpuSceneDoesNotActivateGpu": _condition(texts, "cpuScene",
            "renderer.pop(\"mapData\", None)", "gpu_activation: bool = field(default=False, init=False)"),
        "activeHeightRouteUnselected": contract.get("runtimePolicy", {}).get("heightSourcePresent") is False,
    }
    result["connectionConditions"] = conditions
    if not all(conditions.values()):
        result["blockingReasons"] = ["UNRECOGNIZED_SELECTOR_OR_COMPOSITION_REAUDIT_REQUIRED"]
        return result
    result["protectedConnectionReferences"] = [
        _reference(texts, "jobManager", "LAUNCH = Path('/opt/world-engine-storage-fix/launch.py')"),
        _reference(texts, "jobManager", "str(LAUNCH), '--render-65422'"),
        _reference(texts, "gpuLauncher", 'str(HERE / "hardware_render.mjs")'),
        _reference(texts, "hardwareRuntime", "await import('/modules/map_engine_unit_gpu_adapter_v4.mjs')"),
        _reference(texts, "hardwareRuntime", "ALL_SCENE_FIELDS_EXCEPT_CURRENT_FRONT_GLOW_ARE_LOCKED"),
        _reference(texts, "v4Composition", "factory.renderFrame({mode:5,graphics:false,boundaries:false,glow:false,dem:false,"),
        _reference(texts, "v4Composition", "terrain.draw({bounds,coverage,frame,fps:track.fps})"),
        _reference(texts, "v4Composition", "actualTerrainTexture:terrain.outputTexture"),
    ]

    envelope = json.loads(texts["cameraEnvelope"])
    metadata = json.loads(texts["sampleMetadata"])
    neutral = json.loads(texts["neutralManifest"])
    if (envelope.get("renderExecuted") is not False or envelope.get("actualFramesEvaluated") != len(envelope["frames"])
            or metadata.get("criticalParseErrors") != []):
        raise AuditError("SAVED_AUDIT_EVIDENCE_INCONSISTENT")
    target = bbox(envelope["nativeExpandedEnvelope"])
    # Read the original sample extents from completed Phase A parsing, not from
    # the deliberately tiny CPU overlap fixture or a new raw archive parse.
    sources = {"terrain": metadata["terrain"]["actualBounds"],
               "bathymetry": metadata["bathymetry"]["bounds"],
               "surfaceTexture": metadata["surface"]["bounds"]}
    result["savedCoverage"] = {
        "authority": PATHS["sampleMetadata"], "envelopeAuthority": PATHS["cameraEnvelope"],
        "actualFrameCountInSavedEvidence": envelope["actualFramesEvaluated"],
        "cameraReevaluatedThisRun": False,
        "derivativeGuardBandIncluded": envelope["derivativeGuardBandIncluded"],
        "roles": {role: coverage(bounds, target) for role, bounds in sources.items()},
        "partialFallbackAllowed": True,
        "fullShotAstraClaim": "BLOCKED_INCOMPLETE_SAMPLE_ENVELOPE",
        "partialIntegrationNotBlockedByCoverageAlone": True,
    }
    filenames = set(records)
    neutral_files = [CPU + "fixtures/neutral-output/" + item["file"] for item in neutral["artifacts"]]
    result["imagePackagingEvidence"] = {
        "authority": PATHS["sourceContract"],
        "meaning": "REUSED_PINNED_PACKAGE_CONTRACT_NOT_NEW_CONTAINER_INSPECTION",
        "originalContractFiles": len(records),
        "cpuModulePaths": sorted(p for p in filenames if p.startswith(CPU + "astra_cpu/")),
        "originalSampleArchivePackaged": PHASE_A + "inputs/ESSENTIAL_MAP_SAMPLES.zip" in filenames,
        "neutralArtifacts": [{"path": p, "selectedByOriginalContract": p in filenames} for p in neutral_files],
        "heightSourcePresent": contract["runtimePolicy"]["heightSourcePresent"],
        "savedDetachedImage": json.loads(texts["imageEvidence"])["imageReference"],
    }
    result["classification"] = [
        {"feature": "cpu_providers_acquisition_cache_scene_preparation", "state": "IMPLEMENTED_RENDER_UNCONNECTED"},
        {"feature": "gpu_runtime_encoding_storage_detached_manager", "state": "IMPLEMENTED_CONNECTED_BASELINE",
         "hardwareEvidence": "USER_REPORTED_EXISTING_PASS_NOT_REEXECUTED"},
        {"feature": "astra_gpu_source_material", "state": "NOT_IMPLEMENTED_IN_ACTIVE_PATH"},
        {"feature": "native_gis_screen_coverage_mask", "state": "IMPLEMENTED_BASELINE",
         "geographicRasterMaskRequiredForGpuFragmentGating": False},
        {"feature": "astra_to_native_mask_projection_binding", "state": "IMPLEMENTED_CPU_CONTRACT_RENDER_UNWIRED"},
        {"feature": "active_astra_selector", "state": "CONFLICTS_WITH_PROTECTED_SELECTOR"},
        {"feature": "nvidia_upload_visual_coast_performance", "state": "ACTUAL_GPU_ONLY"},
    ]
    result["blockingReasons"] = [
        "PROTECTED_ACTIVE_CHAIN_HAS_NO_ASTRA_MATERIAL_SELECTION_HOOK",
        "V4_DISABLES_NATIVE_DEM_AND_UNCONDITIONALLY_DRAWS_ITS_TERRAIN_MATERIAL",
    ]
    result["resolution"] = {
        "safeIndependentWork": "ADD_VERSIONED_GPU_UPLOAD_CONTRACT_AND_MASKED_SOURCE_MODULE_WITHOUT_ACTIVATING_OLD_CHAIN",
        "activeIntegrationNeeds": "EXPLICIT_NEW_SIBLING_CAPTURE_RUNTIME_LANE_OR_REVIEWED_SELECTOR_CONTRACT",
        "forbiddenShortcut": "DO_NOT_REPLACE_PINNED_FILES_OR_PAINT_ASTRA_OVER_FINISHED_FRAME",
        "compositionOrder": ["native_gis_coverage", "astra_source_material", "territory",
                             "frontier_with_actual_terrain_texture", "presentation", "national_units"],
        "newImageMeaningfulWithoutSelection": False,
    }
    result["auditStatus"] = "PASS"
    result["integrationDecision"] = "BLOCKED_PROTECTED_ACTIVE_SELECTOR"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args(argv)
    try:
        result = audit(args.repo_root)
    except (AuditError, OSError, ValueError, KeyError, TypeError) as error:
        # Only fixed errors and types are exposed, never subprocess stderr/env.
        result = {"schema": "ASTRA_GPU_CONNECTION_AUDIT_V1", "auditStatus": "FAIL",
                  "integrationDecision": "BLOCKED_SOURCE_AUDIT_REQUIRED",
                  "error": str(error) if isinstance(error, AuditError) else type(error).__name__,
                  "gpuExecuted": False, "renderExecuted": False, "imageBuilt": False}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["auditStatus"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
