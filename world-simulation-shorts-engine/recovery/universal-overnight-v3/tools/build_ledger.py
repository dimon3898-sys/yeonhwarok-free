#!/usr/bin/env python3
"""Recount all 151 / 53 identities from the preserved review and new receipts.

No old audit/test suite is rerun.  Explicit source-bound CPU connections may be
added independently; no generated video or build receipt automatically becomes
feature-output proof.  Source/data gaps are kept separate from hardware work.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
PARENT = ROOT.parent / "universal-integration-completion-v2"
BASE_COMMIT = "57de569"
FEATURE_AXES = ("implementationExists", "studioV2Exposed", "sceneJSONAddressable",
                "runtimeSelected", "actualRendererConsumer", "cpuProof", "gpuProof", "relevantToKoreanWar")
AXIS_VALUES = {
    "implementationExists": {"YES", "NO", "NOT_VERIFIED"},
    "studioV2Exposed": {"YES", "CONDITIONAL", "NO", "INTERNAL_ONLY"},
    "sceneJSONAddressable": {"YES", "CONDITIONAL", "NO"},
    "runtimeSelected": {"YES", "CONDITIONAL", "NO"},
    "actualRendererConsumer": {"SOURCE_BOUND", "CPU_INSTRUMENTED", "NONE"},
    "cpuProof": {"PASS_NEW_FOCUSED_CPU", "NOT_VERIFIED_FOR_OVERNIGHT"},
    "gpuProof": {"NOT_VERIFIED"},
    "relevantToKoreanWar": {"REQUIRED", "SUPPORTING", "UNRELATED"},
}
GAPS = {
    "ASTRA.BATHYMETRY_COLOR": ("GPU_PENDING", "Existing signed-depth shader must be inspected in composed pixels under real native ocean coverage."),
    "ASTRA.SUPPORT_DISTANCE_BLEND": ("GPU_PENDING", "Existing per-role support-distance blend must be inspected at actual source and NoData boundaries."),
    "ASTRA.SURFACE_TEXTURE": ("GPU_PENDING", "Existing real-surface shader has regional valid support only; pixel appearance is not yet observed."),
    "ASTRA.TERRAIN_NORMAL_LIGHTING": ("GPU_PENDING", "Existing finite-difference lighting is source-bound; final elevation/light appearance is unobserved."),
    "BACKUP.DROPBOX_OFFLINE_OAUTH": ("OPTIONAL_OPERATING_PROFILE", "Later offline-auth adapter is separate from current accepted no-backup profile; do not require reauthentication or alter Secrets."),
    "BACKUP.ENCRYPTED_CHECKPOINT": ("OPTIONAL_OPERATING_PROFILE", "Existing encrypted durability adapter is separate; preserve current backup path/key and any existing records."),
    "BACKUP.FRESH_ROOT_RESTORE": ("OPTIONAL_OPERATING_PROFILE", "Existing restore owner needs actual durability configuration; fresh-root restore does not grant paid-render approval."),
    "BACKUP.PRODUCTION_INPUT_ADAPTER": ("OPTIONAL_OPERATING_PROFILE", "Existing later production-input adapter is not the selected no-backup operating route."),
    "DETAIL.POST_ARRIVAL_APPROACH": ("SOURCE_CONTRACT_AND_VISUAL_ADMISSION", "Separate post-arrival adapter needs admitted target extent plus native-render visual evidence; preserve existing initial Detail lock."),
    "DETAIL.VISUAL_GRADE_ADMISSION": ("GPU_PENDING", "Real target/native static evidence is needed for VISUAL_DETAIL_ADMITTED; GIS certificate absence alone is not a blocker."),
    "FLOW.DIRECTIONAL_FLOW": ("HISTORICAL_DATA", "Existing historical catalog has no source-backed actor/role/date/route plan; no invented visible path."),
    "FLOW.ENDPOINT_PULSE": ("HISTORICAL_DATA", "Source-backed arrival timing and route/actor plan are absent; generic engine tests do not supply historical facts."),
    "FLOW.HEADING": ("HISTORICAL_DATA", "Source-backed historical route geometry/actor plan is absent; existing arc-length tangent owner can be reused when supplied."),
    "FLOW.MOVING_OBJECT": ("HISTORICAL_DATA", "Participation dates and flags are not positions; dated actor/role/route proof is absent."),
    "FLOW.ROUTE_HOLD": ("HISTORICAL_DATA", "Historical route/actor/arrival state is absent, despite existing generic held-state evaluator."),
    "FLOW.ROUTE_REVEAL": ("HISTORICAL_DATA", "Historical transport plan is absent and decorative paths remain forbidden; production route mode stays hidden."),
    "FLOW.VISUAL_POLISH_PROFILE": ("SOURCE_CONNECTION_AND_HISTORICAL_DATA", "Approved role-based polish module exists; needs actual selected consumer plus admitted actor plan, not ship-specific sizing."),
    "FRONTIER.MOVING_SCALAR_LIGHT": ("SOURCE_CONTRACT_AND_HISTORICAL_DATA", "Exact scalar-light owner needs a compatible complete scalar plan; partial dated fronts cannot be silently converted."),
    "FRONTIER.OUTER_DOMAIN_GOLD": ("SOURCE_CONTRACT_AND_HISTORICAL_DATA", "Requires same-frame genuine domain coverage; coastline/domain edge must not be mislabeled military front."),
    "FRONTIER.TERRAIN_DESTINATION_LIGHT": ("SOURCE_CONTRACT_AND_GPU_PENDING", "Exact destination-light owner needs same-frame genuine sourceTerrainTexture; never relight a completed screen overlay."),
    "MAP.NATIVE_WEBGL_FACTORY": ("GPU_PENDING", "Protected native WebGL factory is reused; actual draw/readPixels output needs software/hardware evidence separately."),
    "MAP.REFERENCE_PRESENTATION_ROLL": ("SOURCE_CONNECTION", "Existing coherent roll/overscan presentation must consume the same source geography/camera; old V5 core stays unchanged."),
    "MAP.SOURCE_GRADE": ("GPU_PENDING", "Supported source-grade material is already selected; appearance cannot be established by alias/config tests."),
    "MAP.SOURCE_OCEAN_TONE": ("GPU_PENDING", "Existing source-derived ocean tone is selected; no fabricated ripple/physics or output claim."),
    "MAP.WARM_TERRAIN_TREATMENT": ("GPU_PENDING", "Existing bounded warm/gold relief is source-bound; terrain/front color separation remains a pixel check."),
    "PLANNER.CAUSAL_TRACKS": ("SOURCE_CONTRACT_AND_HISTORICAL_DATA", "Schematic causal-track validator is not historical route/contact evidence; no invented troop tracks."),
    "PLANNER.FAMILY_TRANSPORT": ("SOURCE_CONNECTION_AND_HISTORICAL_DATA", "Portable family compiler is separate from frozen WAR preset; no admitted historical transport subevent exists."),
    "STUDIO.ACTUAL_80S_INPUT_OUTPUT": ("ACTUAL_ARTIFACT_UNAVAILABLE", "66430/private actual 80s input/output is unavailable; repository example is not asserted to be the user's original job."),
    "STUDIO.SFX_MUX": ("CPU_MEDIA_PENDING", "Existing FFmpeg mux can be tested without GPU using exact audio clock and verified synthetic video; do not label synthetic test a map render."),
    "TERRITORY.COMPLEMENTARY_SCALAR_CONTROL": ("HISTORICAL_DATA", "Complete faction/domain scalar control input is absent; never infer opponent ownership from held-core complement."),
    "TERRITORY.GAIN_STYLE": ("SOURCE_CONNECTION_AND_HISTORICAL_DATA", "Existing gain-style owner requires actual scalar consumer and source-backed ownership; no fabricated gain region."),
    "UNITS.NATIONAL_TABLETS": ("HISTORICAL_DATA", "National artwork exists, but dated country/role/position anchors are absent in historical source authority."),
    "UNITS.SAFE_STATIC_SCALE": ("HISTORICAL_DATA", "Bounded scale owner requires admitted per-frame anchors and layout; no guessed national-unit locations."),
}


def fail(code):
    raise ValueError(code)


def relative(path):
    return Path(path).relative_to(REPO).as_posix()


def reference(path):
    path = Path(path)
    if not path.is_file() or any(part.is_symlink() for part in (path, *path.parents)):
        fail("OVERNIGHT_LEDGER_SOURCE_UNAVAILABLE")
    return {"path": relative(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked_reference(value):
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        fail("OVERNIGHT_LEDGER_SOURCE_REFERENCE_INVALID")
    path = Path(value["path"])
    if path.is_absolute() or ".." in path.parts or not str(path).startswith("world-simulation-shorts-engine/"):
        fail("OVERNIGHT_LEDGER_SOURCE_PATH_INVALID")
    if reference(REPO / path) != value:
        fail("OVERNIGHT_LEDGER_SOURCE_HASH_MISMATCH")
    return deepcopy(value)


def _json(path):
    return json.loads(Path(path).read_text())


def _git_bytes(path):
    """Read an existing pinned Git blob; never download a new data source."""
    if not path.startswith("world-simulation-shorts-engine/") or ".." in Path(path).parts:
        fail("OVERNIGHT_DATA_GIT_PATH_INVALID")
    result = subprocess.run(["git", "show", BASE_COMMIT + ":" + path], cwd=REPO,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        return None
    if len(result.stdout) > 16 * 1024 * 1024:
        fail("OVERNIGHT_DATA_GIT_METADATA_LIMIT")
    return result.stdout


def _existing_metadata(path):
    target = REPO / path
    raw = target.read_bytes() if target.is_file() else _git_bytes(path)
    if raw is None:
        return {"path": path, "state": "UNAVAILABLE_LOCAL_AND_GIT_BLOB_NOT_READ"}, None
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "state": "ACTUAL_EXISTING_BYTES_READ", "sourceCommit": BASE_COMMIT}, raw


def build_data():
    spec = importlib.util.spec_from_file_location("_overnight_data_report", ROOT / "data_readiness.py")
    data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data)
    readiness = data.assess_existing_data()
    recovery = ROOT.parent
    front = _json(recovery / "verified-front-data-v4-recovery/FRONT_PROFILE.json")
    parent_coverage = _json(PARENT / "reports/CHAPTER_FEATURE_COVERAGE.json")
    original_review_path = "world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/evidence/CMH_21_2_SOURCE_REVIEW.json"
    review_ref, review_raw = _existing_metadata(original_review_path)
    review = json.loads(review_raw) if review_raw is not None else {}
    fronts = []
    for item in front["fronts"]:
        path = "world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/" + item["sourceFile"]
        record, raw = _existing_metadata(path)
        if raw is not None and record["sha256"] != item["geoJsonSha256"]:
            fail("OVERNIGHT_DATA_FRONT_SOURCE_HASH_MISMATCH")
        fronts.append({"frontId": item["frontId"], "mapDate": item["mapDate"], "sourceFile": record,
            "classification": item["source"]["classification"], "sourceReview": deepcopy(item["source"]),
            "partialSegments": item["partialSegments"], "verifiedSourceExtent": item["verifiedSourceExtent"],
            "militaryOccupationPolygon": False, "observedDailyMorphAllowed": False,
            "historicalSurveyCertified": False, "wholeBookLicenseClaim": False,
            "rightsEvidence": review_ref, "rightsBasis": review.get("rights", {}).get("basis", "NOT_VERIFIED_THIS_RUN")})
    astra_report_path = "world-simulation-shorts-engine/recovery/astra-map-quality-v1/inputs/ESSENTIAL_DATA_REPORT.md"
    astra_report, _ = _existing_metadata(astra_report_path)
    archive_manifest_path = "world-simulation-shorts-engine/recovery/astra-map-quality-v1/inputs/INPUT_MANIFEST.json"
    archive_manifest, manifest_raw = _existing_metadata(archive_manifest_path)
    manifest = json.loads(manifest_raw) if manifest_raw is not None else {}
    archive = next((row for row in manifest.get("files", []) if row["path"].endswith("ESSENTIAL_MAP_SAMPLES.zip")), None)
    catalog = data.load_existing_catalog()
    sources = deepcopy(readiness["dataAdmission"]["assets"]["sources"])
    license_text = {
      "terrain": "Preserved Copernicus license review permits commercial use/cache/derivatives with required attribution, disclaimer and onward obligations; not implied institutional endorsement.",
      "bathymetry": "Preserved GEBCO terms review permits commercial use and redistribution with attribution; not for navigation and no official endorsement.",
      "surfaceTexture": "Preserved NASA Earth Observatory/BMNG review permits editorial/informational commercial use with credit; no blanket third-party or logo license."}
    for role, row in sources.items():
        row.update({"sourceBytesReparsedThisTask": False, "original24InternalHashesRecheckedThisTask": False,
                    "licenseEvidence": astra_report, "licenseBasis": license_text[role],
                    "gpuOutputVerified": False})
    return {"schema": "WORLD_ENGINE_OVERNIGHT_EXISTING_DATA_READINESS_V1",
       "status": "EXISTING_QUALIFIED_DATA_ADMITTED_OPTIONAL_HISTORICAL_CAPABILITIES_BLOCKED",
       "sourceAuthority": reference(PARENT / "SOURCE_DATA_CATALOG.json"),
       "historyAssessment": readiness, "frontSnapshotCount": len(fronts), "fronts": fronts,
       "sourceFrameUse": parent_coverage["sourceCounts"],
       "sourceClockUse": parent_coverage["sourceClockCounts"],
       "schematicStates": {"count": 5, "interpretation": "AUTHORED_ROK_UN_HELD_CORE_ONLY",
                            "opponentComplementAllowed": False,
                            "sourcePlan": reference(recovery / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json")},
       "chronology": [{"chapterId": row["chapterId"], "eventId": row["eventId"],
                       "startFrame": row["startFrame"], "endFrame": row["endFrame"],
                       "chronology": row["chronology"], "moduleCoverage": row["moduleCoverage"]}
                      for row in readiness["dataAdmission"]["chapterCoverage"]],
       "astra": {"roles": sources, "archive": archive,
                 "archiveManifest": archive_manifest, "reusedLicenseReport": astra_report,
                 "fullSceneHighDetailAdmitted": False, "coverageOwner": "EXISTING_NATIVE_GIS_LAND_SEA_COVERAGE",
                 "fallback": "UNCHANGED_BASE_MATERIAL_OUTSIDE_VALID_REGIONAL_SUPPORT",
                 "negativeLandIsOcean": False, "noDataReplacedByZero": False},
       "trustedSourceRoleCounts": {role: sum(row.get("role") == role for row in catalog["trustedSources"])
                                   for role in sorted(data.SOURCE_ROLES)},
       "newDataAcquired": False, "newCoordinatesCreated": False, "originalDataChanged": False,
       "newWholeArchiveParsePerformed": False, "gpuExecuted": False, "renderAllowed": False}


def _validate_evidence(value, ids):
    """Only explicit checked CPU evidence can change an engine connection axis."""
    if not isinstance(value, dict) or set(value) != {"schema", "features"} or value["schema"] != "WORLD_ENGINE_OVERNIGHT_FEATURE_EVIDENCE_V1":
        fail("OVERNIGHT_LEDGER_NEW_EVIDENCE_SCHEMA_INVALID")
    result = {}
    allowed = {"featureId", "sourceFiles", "cpuReceipt", "runtimeConsumer", "axes", "status", "reason"}
    for row in value["features"]:
        if (not isinstance(row, dict) or set(row) != allowed or row["featureId"] not in ids
                or row["featureId"] in result or row["status"] not in {"SUPPORTING", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE"}):
            fail("OVERNIGHT_LEDGER_NEW_FEATURE_INVALID")
        if not isinstance(row["sourceFiles"], list) or not row["sourceFiles"]:
            fail("OVERNIGHT_LEDGER_NEW_SOURCE_EVIDENCE_REQUIRED")
        for source in row["sourceFiles"]:
            checked_reference(source)
        checked_reference(row["cpuReceipt"])
        receipt = _json(REPO / row["cpuReceipt"]["path"])
        if receipt.get("status") != "PASS" or not isinstance(receipt.get("executed"), int) or receipt["executed"] <= 0:
            fail("OVERNIGHT_LEDGER_CPU_RECEIPT_NOT_PASS")
        consumer = row["runtimeConsumer"]
        if (not isinstance(consumer, dict) or set(consumer) != {"path", "symbol", "invocationProof"}
                or consumer["path"] not in {source["path"] for source in row["sourceFiles"]}
                or not all(isinstance(consumer[k], str) and consumer[k] for k in ("symbol", "invocationProof"))):
            fail("OVERNIGHT_LEDGER_RUNTIME_CONSUMER_PROOF_REQUIRED")
        if (not isinstance(row["axes"], dict) or set(row["axes"]) - set(FEATURE_AXES)
                or any(value not in AXIS_VALUES[key] for key, value in row["axes"].items())):
            fail("OVERNIGHT_LEDGER_CONNECTION_AXES_INVALID")
        if row["axes"].get("gpuProof", "NOT_VERIFIED") != "NOT_VERIFIED":
            fail("OVERNIGHT_LEDGER_CPU_CANNOT_GRANT_GPU_PROOF")
        result[row["featureId"]] = deepcopy(row)
    return result


def build(*, new_evidence=None):
    prior_path = PARENT / "reports/FEATURE_LEDGER_151.json"
    unwired_path = PARENT / "reports/UNWIRED_LEDGER_53.json"
    prior, unwired = _json(prior_path), _json(unwired_path)
    ids = {row["id"] for row in prior["features"]}
    unwired_ids = {row["id"] for row in unwired["features"]}
    if len(ids) != 151 or len(unwired_ids) != 53 or not unwired_ids <= ids:
        fail("OVERNIGHT_LEDGER_151_53_IDENTITIES_CHANGED")
    gap_ids = {row["id"] for row in prior["features"] if row["status"] in {"BLOCKED", "UNVERIFIED"}}
    if gap_ids != set(GAPS):
        fail("OVERNIGHT_LEDGER_33_INDIVIDUAL_REVIEWS_INCOMPLETE")
    additions = _validate_evidence(new_evidence, ids) if new_evidence is not None else {}
    rows = deepcopy(prior["features"])
    for row in rows:
        original = row["status"]
        gap = GAPS.get(row["id"])
        row["overnightReview"] = {"previousStatus": original, "reviewed": True,
            "gapClass": gap[0] if gap else "REUSE_COMPLETED_OR_NOT_APPLICABLE",
            "actionOrLimitation": gap[1] if gap else "Preserve existing source and receipt; do not redevelop.",
            "sourceEvidence": deepcopy(row.get("evidence", [])),
            "newCpuEvidence": None, "newOutputFeatureProof": None}
        if row["id"] in additions:
            update = additions[row["id"]]
            row.update(update["axes"])
            row["status"], row["reason"] = update["status"], update["reason"]
            row["overnightReview"]["newCpuEvidence"] = deepcopy(update)
        row["gpuProof"] = "NOT_VERIFIED"
        row["outputAppliedThisOvernightTask"] = False
        row["overnightReview"]["changedStatus"] = row["status"] != original
    counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    report = {"schema": "WORLD_ENGINE_OVERNIGHT_FEATURE_LEDGER_V1", "baseCommit": BASE_COMMIT,
        "previousLedger": reference(prior_path), "previousUnwiredLedger": reference(unwired_path),
        "featureCount": 151, "previouslyUnwiredCount": 53,
        "all151Reviewed": True, "all53UnwiredReviewed": True, "all33PendingIndividuallyReviewed": True,
        "featureAxisNames": list(FEATURE_AXES), "auditAxesPreserved": True,
        "statusCounts": counts, "newCpuConnectionFeatureCount": len(additions),
        "actualOutputAppliedCount": 0, "gpuProofCount": 0,
        "cpuSoftwareEvidenceIsNvidiaProof": False, "full80sRenderAllowed": False,
        "features": rows}
    remaining = [{"id": row["id"], "status": row["status"], "domain": row["domain"],
                  "required": row["relevantToKoreanWar"] == "REQUIRED",
                  "gapClass": row["overnightReview"]["gapClass"], "reason": row["reason"],
                  "nextAction": row["overnightReview"]["actionOrLimitation"],
                  "exactExistingEntrypoint": row.get("input", {}).get("entrypoint"),
                  "sourceEvidence": deepcopy(row.get("evidence", []))}
                 for row in rows if row["status"] in {"BLOCKED", "UNVERIFIED"}]
    report_unwired = {"schema": "WORLD_ENGINE_OVERNIGHT_UNWIRED_LEDGER_V1", "count": 53,
        "allReviewed": True, "actualOutputAppliedCount": 0,
        "statusCounts": dict(sorted(Counter(row["status"] for row in rows if row["id"] in unwired_ids).items())),
        "features": [row for row in rows if row["id"] in unwired_ids]}
    return report, report_unwired, {"schema": "WORLD_ENGINE_OVERNIGHT_REMAINING_FEATURES_V1",
             "count": len(remaining), "allPendingIndividuallyReviewed": True,
             "statusCounts": dict(sorted(Counter(row["status"] for row in remaining).items())),
             "gapClassCounts": dict(sorted(Counter(row["gapClass"] for row in remaining).items())),
             "features": remaining, "noGpuOrPaidWorkPerformed": True}


def write(report, path):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def csv_rows(rows):
    output = io.StringIO(newline="")
    fields = ["id", "domain", "name", "status", *FEATURE_AXES,
              "gapClass", "exactEntrypoint", "reason", "nextAction"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({**{key: row.get(key, "") for key in fields if key in row},
            "gapClass": row["overnightReview"]["gapClass"],
            "exactEntrypoint": row.get("input", {}).get("entrypoint", ""),
            "nextAction": row["overnightReview"]["actionOrLimitation"]})
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--skip-data", action="store_true", help="Only recount ledgers; no original Git blob reads.")
    args = parser.parse_args()
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    ledger, unwired, remaining = build(new_evidence=_json(args.evidence) if args.evidence else None)
    write(ledger, out / "FEATURE_LEDGER_151.json")
    write(unwired, out / "UNWIRED_LEDGER_53.json")
    write(remaining, out / "REMAINING_FEATURES.json")
    (out / "FEATURE_LEDGER_151.csv").write_text(csv_rows(ledger["features"]))
    (out / "UNWIRED_LEDGER_53.csv").write_text(csv_rows(unwired["features"]))
    if not args.skip_data:
        write(build_data(), out / "DATA_READINESS.json")
    print(json.dumps({"featureCount": 151, "previouslyUnwiredCount": 53,
                      "statusCounts": ledger["statusCounts"], "pendingCount": remaining["count"]}))


if __name__ == "__main__":
    main()
