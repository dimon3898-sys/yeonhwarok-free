#!/usr/bin/env python3
"""Freeze approved Flow V2 from actual persistence and remote-reproduction receipts.

Reuse the immutable V1 final helper for canonical records, frozen manifest checks,
approval binding and remote Git/LFS/npm setup validation. This wrapper adds only
the Flow scope and 240-frame/six-checkpoint comparison. It never renders, tunes a
profile, investigates data, or rewrites any approved Candidate file.
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FINAL = Path(__file__).resolve().parent
BASE = "world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish"
BRANCH = "development/event-flow-polish-v2-20261013"
VALIDATION_COMMIT = "4a1f773dcf377ebca5e46d83b81204707a56b59d"
MEDIA_COMMIT = "a0add53bc5d9182bf24a17ac9dd13e69129c9fa0"
RENDER_COMMIT = "be428ab6dbe6723f8b3cc25a287c18a744a9c318"
PARENT_COMMIT = "f79f3d55d945ef0e53b03ac2ed666f48f28b5881"
PARENT_MANIFEST = "world-simulation-shorts-engine/recovery/event-v1-final/FINAL_MANIFEST.json"
PARENT_SHA = "52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1"
APPROVED_SHA = "5ff055643ded594198f3dc5e313d9acadb6b636d4f621294ad69456d4b6449fe"
MP4_NAME = "SUEZ_EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH.mp4"
BASELINE = "EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE"
DECISION = "EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL"
SCOPE = "EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH"


def frozen_helpers():
    relative = "world-simulation-shorts-engine/recovery/event-v1-final/finalize_baseline.py"
    file = REPO / relative
    expected = subprocess.check_output(["git", "show", PARENT_COMMIT + ":" + relative], cwd=REPO)
    if file.read_bytes() != expected:
        raise ValueError("FROZEN_V1_FINAL_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("frozen_event_v1_final_helpers", file)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.REPO, helper.FINAL, helper.BASE = REPO, FINAL, BASE
    helper.BRANCH, helper.SOURCE_COMMIT = BRANCH, VALIDATION_COMMIT
    helper.MEDIA_COMMIT, helper.RENDER_COMMIT = MEDIA_COMMIT, RENDER_COMMIT
    helper.APPROVED_SHA, helper.MP4_NAME = APPROVED_SHA, MP4_NAME
    return helper, relative


H, HELPER_PATH = frozen_helpers()
require, git, record, load, encode = H.require, H.git, H.record, H.load, H.encode


def verify_persistence(receipt, docs):
    expected = {"scope": SCOPE, "inventory_status": "PASS", "inventory_stage": "candidate",
                "required_temp_only_files": 0, "head_and_index_compared": True,
                "permanent_gate_executed": False, "user_video_approved": False, "event_final": False}
    for key, value in expected.items():
        require(receipt.get(key) == value, "CANDIDATE_PERSISTENCE_FAILED: " + key)
    counts = {
        "required_files": len(docs["HASH_MANIFEST"]["required_files"]) + 2,
        "reachable_import_modules": len(docs["IMPORT_MANIFEST"]["reachable_modules"]),
        "import_edges": len(docs["IMPORT_MANIFEST"]["edges"]),
        "new_engine_modules": len(docs["SOURCE_MANIFEST"]["new_engine_modules"]),
        "focused_tests": len(docs["SOURCE_MANIFEST"]["focused_tests"]),
    }
    for key, value in counts.items():
        require(receipt.get(key) == value, "CANDIDATE_PERSISTENCE_COUNT_FAILED: " + key)
    original = set(git(REPO, "ls-tree", "-r", "--name-only", VALIDATION_COMMIT).decode().splitlines())
    changed = set(git(REPO, "diff", "--name-only", VALIDATION_COMMIT).decode().splitlines())
    require(not original.intersection(changed), "APPROVED_CANDIDATE_TRACKED_PATH_CHANGED")


def verify_reproduction(receipt, checkout):
    golden = load(REPO / BASE / "evidence/proof/REPORT.json")
    require(golden.get("status") == "PASS" and golden.get("sourceCommit") == RENDER_COMMIT,
            "APPROVED_FLOW_RENDER_SOURCE_CHANGED")
    expected = {"schema": 1, "status": "PASS", "approvedSourceRevision": VALIDATION_COMMIT,
                "originalRenderSourceRevision": RENDER_COMMIT, "cleanCheckoutBefore": True,
                "cleanCheckoutAfter": True, "sharedSystemToolchain": True,
                "noLocalSourceOrAssetCopies": True, "originalPublicProofModified": False,
                "rawFramesBitExact": 240, "nativePngFramesBitExact": 240,
                "checkpointPngsBitExact": 6, "actualRuntimeOrigin": str(checkout),
                "requiredTempOnlyFiles": []}
    for key, value in expected.items():
        require(receipt.get(key) == value, "CLEAN_REPRODUCTION_FAILED: " + key)
    frames = receipt.get("frames", [])
    require(len(frames) == len(golden["frames"]) == 240, "FLOW_FRAME_COUNT_CHANGED")
    for frame, (actual, approved) in enumerate(zip(frames, golden["frames"], strict=True)):
        require(actual.get("frame") == approved["frame"] == frame, "FLOW_FRAME_ORDER_CHANGED")
        require(actual.get("rawBitExact") is True and actual.get("pngBitExact") is True
                and actual.get("cameraTimelineFlowIdentical", actual.get("cameraTimelineEventIdentical")) is True,
                "FLOW_CAMERA_TIMELINE_OR_PIXEL_CHANGE: " + str(frame))
        for key in ("state", "raw_rgba_sha256", "png_sha256"):
            require(actual.get(key) == approved[key], "APPROVED_FLOW_FRAME_HASH_CHANGED: " + str(frame))
    output = FINAL / "evidence/clean-reproduction"
    actual_checkpoints = receipt.get("checkpoints", [])
    require(len(actual_checkpoints) == len(golden["checkpoints"]) == 6, "FLOW_CHECKPOINT_COUNT_CHANGED")
    outputs = []
    for actual, approved in zip(actual_checkpoints, golden["checkpoints"], strict=True):
        require(actual.get("bitExact") is True, "FLOW_CHECKPOINT_NOT_BIT_EXACT")
        require(all(actual.get(key) == approved[key] for key in ("frame", "state", "file", "sha256", "bytes")),
                "FLOW_CHECKPOINT_APPROVAL_BINDING_CHANGED")
        require(Path(actual["file"]).name == actual["file"], "UNSAFE_FLOW_CHECKPOINT_NAME")
        body = record(output / actual["file"])
        require(all(body[key] == approved[key] for key in ("sha256", "bytes")), "FLOW_CHECKPOINT_BODY_CHANGED")
        outputs.append(body)
    require(receipt.get("encodeCommand", [])[:-1] == golden["encodeCommand"][:-1], "FLOW_ENCODER_PARAMETERS_CHANGED")
    require(receipt["encodeCommand"][-1] == str(output / MP4_NAME), "FLOW_VIDEO_OUTPUT_PATH_CHANGED")
    video = receipt.get("video", {})
    require(video.get("file") == MP4_NAME and video.get("approvedSha256") == APPROVED_SHA,
            "FLOW_VIDEO_APPROVAL_BINDING_CHANGED")
    body = record(output / MP4_NAME)
    require(all(video.get(key) == body[key] for key in ("sha256", "bytes")), "FLOW_VIDEO_BODY_CHANGED")
    if receipt.get("result") == "BIT_EXACT":
        require(video.get("bitExact") is True and body["sha256"] == APPROVED_SHA
                and body["bytes"] == golden["video"]["bytes"]
                and video.get("decodedEquality") == "IMPLIED_BY_IDENTICAL_MP4_BYTES", "FLOW_MP4_NOT_BIT_EXACT")
    else:
        require(receipt.get("result") == "DECODED_PIXEL_EQUALITY" and video.get("bitExact") is False
                and video.get("decodedEquality") == "240_OF_240_FRAME_HASHES_EQUAL",
                "FLOW_FULL_DECODED_EQUALITY_NOT_VERIFIED")
    stream = receipt.get("ffprobe", {}).get("streams", [])
    require(len(stream) == 1, "FLOW_VIDEO_NOT_SILENT_SINGLE_STREAM")
    s = stream[0]
    require((s.get("codec_type"), s.get("codec_name"), s.get("width"), s.get("height"), s.get("avg_frame_rate"))
            == ("video", "h264", 1080, 1920, "30/1") and int(s.get("nb_read_frames", 0)) == 240
            and float(s.get("duration", 0)) == 8, "FLOW_VIDEO_FORMAT_CHANGED")
    public = REPO / BASE / "public-review"
    allowed = {MP4_NAME, "SHA256SUMS"} | {row["file"] for row in golden["checkpoints"]}
    require({p.name for p in public.iterdir()} == allowed, "APPROVED_PUBLIC_PROOF_CONTENT_CHANGED")
    for file in public.iterdir():
        require(file.is_file() and not file.is_symlink(), "NON_REGULAR_PUBLIC_PROOF")
        require(file.read_bytes() == git(REPO, "show", MEDIA_COMMIT + ":" + file.relative_to(REPO).as_posix()),
                "ORIGINAL_APPROVED_PUBLIC_BODY_CHANGED")
    require(record(public / MP4_NAME)["sha256"] == APPROVED_SHA, "APPROVED_MP4_SHA_CHANGED")
    return [*outputs, body], golden


def build():
    paths = H.receipt_paths()
    approval, persistence, setup, reproduction = (load(paths[name]) for name in
                                                ("approval", "persistence", "setup", "reproduction"))
    H.verify_user_review(approval)
    require(approval.get("original_render_source_commit") == RENDER_COMMIT, "REVIEW_ORIGINAL_SOURCE_CHANGED")
    docs, bindings = H.load_frozen_manifests()
    verify_persistence(persistence, docs)
    expected_rows = list(docs["HASH_MANIFEST"]["required_files"])
    expected_rows += [bindings["HASH_MANIFEST"], record(REPO / BASE / "manifests/SHA256SUMS")]
    expected = H.normalized_records(expected_rows)
    actual = H.normalized_records(reproduction.get("requiredInputs"))
    require(actual == expected, "REMOTE_APPROVED_REQUIRED_INPUT_HASH_SET_CHANGED")
    checkout = H.verify_remote_setup(setup, reproduction, docs, actual)
    outputs, approved = verify_reproduction(reproduction, checkout)
    for name, doc in docs.items():
        require(doc.get("required_temp_only_files") == [], "REQUIRED_TEMP_ONLY_INPUT: " + name)
    require(docs["IMPORT_MANIFEST"].get("issues") == [], "UNRESOLVED_APPROVED_FLOW_IMPORTS")
    for path in docs["IMPORT_MANIFEST"]["reachable_modules"]:
        require(path in actual, "REMOTE_SOURCE_IMPORT_MISSING: " + path)
    for row in docs["SOURCE_MANIFEST"]["entries"] + docs["FIXTURE_MANIFEST"]["entries"]:
        require(actual.get(row["path"]) == {k: row[k] for k in ("path", "sha256", "bytes")},
                "REMOTE_SOURCE_OR_FIXTURE_BODY_CHANGED")
    for route in docs["RUNTIME_ASSET_MANIFEST"]["runtime_routes"]:
        require(route["file"] in actual, "REMOTE_RUNTIME_ASSET_ROUTE_MISSING")
    parent = record(REPO / PARENT_MANIFEST)
    require(parent["sha256"] == PARENT_SHA and (REPO / PARENT_MANIFEST).read_bytes()
            == git(REPO, "show", PARENT_COMMIT + ":" + PARENT_MANIFEST), "PARENT_V1_FINAL_CHANGED")
    profile = load(REPO / BASE / "fixtures/VISUAL_PROFILE.json")
    require(profile == approved.get("visualProfile") and profile.get("objectScale") == 1.2,
            "APPROVED_FLOW_VISUAL_PROFILE_CHANGED")
    require(approved.get("polish", {}).get("afterSize") == [62.4, 36]
            and approved["polish"].get("holdFrames") == 34
            and approved["polish"].get("arrivalPulseCount") == 1, "APPROVED_FLOW_RHYTHM_CHANGED")
    receipts = {name: record(file) for name, file in paths.items()}
    gates = {name: "PASS" for name in H.GATE_NAMES}
    gate = {"schema": 1, "baseline_name": BASELINE, "status": "PASS", "user_video_review": "PASS",
            "approved_source_commit": RENDER_COMMIT, "approved_validation_commit": VALIDATION_COMMIT,
            "approved_media_commit": MEDIA_COMMIT, "gates": gates, "passed": 7, "total": 7,
            "required_temp_only_files": [], "verification_receipts": receipts, "manifest_bindings": bindings,
            "verification_scope": {"candidate_persistence_builder_runs": 1, "candidate_required_inputs": len(expected),
                                   "remote_required_input_hashes": len(actual), "raw_frames_bit_exact": 240,
                                   "native_png_frames_bit_exact": 240, "checkpoint_pngs_bit_exact": 6,
                                   "mp4_result": reproduction["result"], "same_pinned_system_toolchain": True,
                                   "new_os_image_claimed": False, "approved_candidate_changed": False,
                                   "historical_candidate_flags_rewritten": False, "public_proof_changed": False,
                                   "additional_feature_work_executed": False},
            "gate_evidence": {"SOURCE_PERSISTED": ["persistence", "reproduction", "SOURCE_MANIFEST"],
                              "ASSETS_PERSISTED": ["persistence", "setup", "reproduction", "RUNTIME_ASSET_MANIFEST", "FIXTURE_MANIFEST"],
                              "HASH_MANIFEST_PASS": ["persistence", "reproduction", "HASH_MANIFEST"],
                              "DEPENDENCY_MANIFEST_PASS": ["setup", "reproduction", "DEPENDENCY_MANIFEST"],
                              "IMPORT_MANIFEST_PASS": ["persistence", "reproduction", "IMPORT_MANIFEST"],
                              "NO_REQUIRED_TEMP_FILES": ["all_frozen_manifests", "reproduction"],
                              "CLEAN_ENV_REPRODUCIBLE": ["setup", "reproduction"]}}
    procedures = ["bootstrap_clean_checkout.py", "reproduce_clean_flow.mjs", "finalize_baseline.py", "scan_final_freeze.py"]
    manifest = {"schema": 1, "baseline_name": BASELINE, "state": DECISION, "user_video_review": "PASS",
                "branch": BRANCH, "parent_event_v1_baseline": {"name": "EVENT_SYSTEM_V1_FINAL_BASELINE",
                        "commit": PARENT_COMMIT, "manifest": parent, "manifest_sha256": PARENT_SHA},
                "parent_event_v1": {"name": "EVENT_SYSTEM_V1_FINAL_BASELINE", "commit": PARENT_COMMIT,
                                    "manifest": parent, "manifest_sha256": PARENT_SHA},
                "source_commit": RENDER_COMMIT, "approved_candidate_commit": MEDIA_COMMIT,
                "approved_validation_commit": VALIDATION_COMMIT, "approved_media_commit": MEDIA_COMMIT,
                "approved_mp4": BASE + "/public-review/" + MP4_NAME, "approved_mp4_sha256": APPROVED_SHA,
                "source_manifest_sha256": bindings["SOURCE_MANIFEST"]["sha256"],
                "asset_manifest_sha256": bindings["RUNTIME_ASSET_MANIFEST"]["sha256"],
                "fixture_manifest_sha256": bindings["FIXTURE_MANIFEST"]["sha256"],
                "dependency_manifest_sha256": bindings["DEPENDENCY_MANIFEST"]["sha256"],
                "import_manifest_sha256": bindings["IMPORT_MANIFEST"]["sha256"],
                "hash_manifest_sha256": bindings["HASH_MANIFEST"]["sha256"], "all_manifest_bindings": bindings,
                "asset_manifest": bindings["RUNTIME_ASSET_MANIFEST"],
                "dependency_manifest": bindings["DEPENDENCY_MANIFEST"],
                "feature_profile": {"primitives": ["ROUTE_REVEAL", "DIRECTIONAL_FLOW", "MOVING_OBJECT", "ENDPOINT_PULSE", "ROUTE_HOLD"],
                    "quality_grade": "FACT_BASED_VISUAL_GRADE", "visual_profile": profile,
                    "route_reveal": "REUSED_GEOGRAPHIC_LINE_ARC_LENGTH_V1", "polish": approved["polish"],
                    "duration_seconds": 8, "frames": 240, "fps": 30, "detail_lock_frame": 60,
                    "flow_plan": record(REPO / BASE / "fixtures/FLOW_PLAN.json"),
                    "detail_plan": record(REPO / BASE / "fixtures/DETAIL_ADAPTER_PLAN.json")},
                "permanent_gate_result": {"status": "PASS", "passed": 7, "total": 7, "gates": gates},
                "gate_result": {"status": "PASS", "passed": 7, "total": 7, "gates": gates},
                "clean_reproduction": {"result": reproduction["result"], "source_revision": VALIDATION_COMMIT,
                    "original_render_source_revision": RENDER_COMMIT, "remote_checkout": True, "fresh_npm_ci": True,
                    "system_toolchain": "EXISTING_PINNED_SYSTEM_TOOLS", "new_os_image_claimed": False,
                    "raw_frames_bit_exact": 240, "native_png_frames_bit_exact": 240,
                    "checkpoint_pngs_bit_exact": 6, "verification_outputs": outputs},
                "verification_receipts": receipts, "verification_procedures": [record(FINAL / p) for p in procedures],
                "reused_frozen_final_helper": record(REPO / HELPER_PATH),
                "verification_recipe": record(FINAL / "CLEAN_REPRODUCTION_RECIPE.json"),
                "required_temp_only_files": [], "public_proof": {"unchanged": True,
                    "new_review_media_required": False, "private_verification_evidence_published": False},
                "containing_commit_binding": "GIT_COMMIT_CONTAINING_THIS_MANIFEST_REPORTED_EXTERNALLY",
                "self_hash_policy": "SHA256_OF_EXACT_MANIFEST_BYTES_REPORTED_AFTER_WRITE"}
    return gate, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    require(args.write, "EXPLICIT_WRITE_FLAG_REQUIRED")
    gate_file, manifest_file = FINAL / "evidence/PERMANENT_GATE.json", FINAL / "FINAL_MANIFEST.json"
    require(not gate_file.exists() and not manifest_file.exists(), "FINAL_OUTPUT_ALREADY_EXISTS")
    try:
        gate, manifest = build()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        failure = {"schema": 1, "baseline_name": BASELINE, "status": "FAIL", "passed": 0, "total": 7,
                   "gates": {name: "NOT_ADMITTED" for name in H.GATE_NAMES},
                   "decision": "EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BLOCKED", "error": str(error),
                   "checked_at_utc": datetime.now(timezone.utc).isoformat()}
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_bytes(encode(failure)); print(json.dumps(failure), file=sys.stderr)
        return 1
    gate["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    gate_file.write_bytes(encode(gate)); manifest["permanent_gate_receipt"] = record(gate_file)
    manifest_file.write_bytes(encode(manifest))
    print(json.dumps({"status": "PASS", "decision": DECISION, "gates": 7,
                      "manifest": record(manifest_file), "permanent_gate": record(gate_file)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
