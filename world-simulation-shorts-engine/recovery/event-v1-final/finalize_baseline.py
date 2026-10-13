#!/usr/bin/env python3
"""Freeze the approved Event V1 Candidate from retained final-verification receipts.

This procedure performs no rendering, data research, source tuning, or historical
manifest rewriting. Run the approved Candidate inventory builder once before the
clean reproduction, save its stdout as CANDIDATE_PERSISTENCE_CHECK.json, and run
reproduce_clean_candidate.mjs once against an actual remote checkout. This script
then validates those receipts and binds the seven Permanent Gate results.

Usage (from repository root):
  /usr/bin/python3 -B world-simulation-shorts-engine/recovery/event-v1-final/
      finalize_baseline.py --write

The clean checkout is a fresh remote Git checkout with remote Git LFS hydration
and a fresh frozen npm install, using the existing pinned system tools. It is not
a claim that a new operating-system image was created. The older generic gate
validator uses a different manifest schema, rejects the retained Node/import
closure, and does not hydrate Git LFS; it is deliberately not used or modified.

Required CLEAN_CHECKOUT_SETUP.json schema (extra metadata is permitted):
  schema: 1; status: PASS; checkout: absolute real path; remote: REMOTE below;
  branch: BRANCH below; revision: SOURCE_COMMIT below;
  clone_method: REMOTE_GIT_CLONE; source_or_asset_copies: false;
  git_alternates: []; git_status_before_reproduction: "";
  shared_system_toolchain: true; toolchain: manifest interpreter name/version map;
  npm_ci: {status: PASS, command: exact DEPENDENCY_MANIFEST.setup list,
           fresh_install: true, packages: [{name, version}, ...]};
  lfs_objects: [{path, sha256, bytes, source: REMOTE_GIT_LFS, status: PASS}, ...].

Required USER_REVIEW_APPROVAL.json schema (extra metadata is permitted):
  schema: 1; user_video_review: PASS; approved_branch: BRANCH below;
  approved_media_commit: MEDIA_COMMIT below; approved_source_commit: SOURCE_COMMIT;
  approved_mp4_sha256: APPROVED_SHA below.

Successful outputs are private FINAL_MANIFEST.json and evidence/PERMANENT_GATE.json
in this sibling folder. The final manifest's containing Git commit is reported
externally after committing; no manifest can contain its own commit/hash without
a circular binding. A failed run writes a FAIL gate receipt, never a final manifest.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


REPO = Path(__file__).resolve().parents[3]
FINAL = Path(__file__).resolve().parent
BASE = "world-simulation-shorts-engine/recovery/event-v1-v3-visual-detail"
BRANCH = "development/event-system-v1-20261012"
REMOTE = "https://github.com/dimon3898-sys/yeonhwarok-free.git"
SOURCE_COMMIT = "a7241a1e69d901fdd7ef5212ea5faf34d0ea6baf"
MEDIA_COMMIT = "d1cc0488688e2611e3f449cbdf97007b5147085f"
RENDER_COMMIT = "ef95c08da99ab3aebcafd3b7c8fc6d7861fd4438"
V5_COMMIT = "29b8ee294360812b55ef577b62411de58159003b"
APPROVED_SHA = "adea9790ee91834622cdee2cf96ef5715812ea2eb846a18a70984a81469f1049"
MP4_NAME = "SUEZ_EVENT_SYSTEM_V1_V3_VISUAL_DETAIL.mp4"
GATE_NAMES = (
    "SOURCE_PERSISTED", "ASSETS_PERSISTED", "HASH_MANIFEST_PASS",
    "DEPENDENCY_MANIFEST_PASS", "IMPORT_MANIFEST_PASS",
    "NO_REQUIRED_TEMP_FILES", "CLEAN_ENV_REPRODUCIBLE",
)
MANIFEST_NAMES = (
    "SOURCE_MANIFEST", "FIXTURE_MANIFEST", "RUNTIME_ASSET_MANIFEST",
    "DEPENDENCY_MANIFEST", "IMPORT_MANIFEST", "HASH_MANIFEST",
    "REPRODUCTION_MANIFEST", "BUILD_INPUT_MANIFEST", "DATA_MANIFEST",
    "EVIDENCE_MANIFEST",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *args):
    return subprocess.check_output(
        ["git", *args], cwd=checkout, stderr=subprocess.DEVNULL
    )


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def record(file):
    file = Path(file)
    require(file.is_file() and not file.is_symlink(), "NOT_A_REGULAR_INPUT: " + str(file))
    data = file.read_bytes()
    return {
        "path": file.relative_to(REPO).as_posix(),
        "sha256": sha256_bytes(data), "bytes": len(data),
    }


def load(file):
    file = Path(file)
    require(file.is_file() and not file.is_symlink(), "MISSING_RECEIPT: " + str(file))
    return json.loads(file.read_text())


def normalized_records(rows):
    require(isinstance(rows, list), "INPUT_RECORDS_NOT_LIST")
    result = {}
    for row in rows:
        name = row["path"]
        parts = PurePosixPath(name)
        require(not parts.is_absolute() and ".." not in parts.parts and str(parts) == name,
                "UNSAFE_REQUIRED_INPUT_PATH: " + name)
        require(name not in result, "DUPLICATE_REQUIRED_INPUT: " + name)
        require(isinstance(row["bytes"], int) and row["bytes"] >= 0,
                "INVALID_REQUIRED_INPUT_SIZE: " + name)
        digest = row["sha256"]
        require(isinstance(digest, str) and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest),
                "INVALID_REQUIRED_INPUT_HASH: " + name)
        result[name] = {"path": name, "bytes": row["bytes"], "sha256": digest}
    return result


def receipt_paths():
    return {
        "approval": FINAL / "USER_REVIEW_APPROVAL.json",
        "persistence": FINAL / "evidence/CANDIDATE_PERSISTENCE_CHECK.json",
        "setup": FINAL / "evidence/CLEAN_CHECKOUT_SETUP.json",
        "reproduction": FINAL / "evidence/clean-reproduction/CLEAN_REPRODUCTION.json",
    }


def load_frozen_manifests():
    documents, bindings = {}, {}
    for name in MANIFEST_NAMES:
        relative = BASE + "/manifests/" + name + ".json"
        actual = REPO / relative
        data = actual.read_bytes()
        require(data == git(REPO, "show", SOURCE_COMMIT + ":" + relative),
                "APPROVED_MANIFEST_CHANGED: " + relative)
        documents[name] = json.loads(data)
        bindings[name] = record(actual)
        require(documents[name].get("event_final") is False,
                "HISTORICAL_CANDIDATE_FINAL_FLAG_CHANGED: " + relative)
        require(documents[name].get("user_video_approved") is False,
                "HISTORICAL_CANDIDATE_REVIEW_FLAG_CHANGED: " + relative)
        require(documents[name].get("permanent_gate_executed") is False,
                "HISTORICAL_CANDIDATE_GATE_FLAG_CHANGED: " + relative)
    return documents, bindings


def verify_user_review(approval):
    expected = {
        "schema": 1, "user_video_review": "PASS", "approved_branch": BRANCH,
        "approved_media_commit": MEDIA_COMMIT, "approved_source_commit": SOURCE_COMMIT,
        "approved_mp4_sha256": APPROVED_SHA,
    }
    for name, value in expected.items():
        require(approval.get(name) == value, "APPROVAL_BINDING_FAILED: " + name)


def verify_persistence(persistence, documents):
    expected = {
        "scope": "EVENT_SYSTEM_V1_V3_VISUAL_DETAIL", "inventory_status": "PASS",
        "inventory_stage": "candidate", "required_temp_only_files": 0,
        "head_and_index_compared": True,
    }
    for name, value in expected.items():
        require(persistence.get(name) == value, "PERSISTENCE_RECEIPT_FAILED: " + name)
    require(persistence["required_files"] == len(documents["HASH_MANIFEST"]["required_files"]) + 2,
            "PERSISTENCE_REQUIRED_INPUT_COUNT_MISMATCH")
    imports = documents["IMPORT_MANIFEST"]
    require(persistence["reachable_import_modules"] == len(imports["reachable_modules"]),
            "PERSISTENCE_IMPORT_CLOSURE_COUNT_MISMATCH")
    require(persistence["import_edges"] == len(imports["edges"]),
            "PERSISTENCE_IMPORT_EDGE_COUNT_MISMATCH")
    require(persistence["new_engine_modules"] == len(documents["SOURCE_MANIFEST"]["new_engine_modules"]),
            "PERSISTENCE_ENGINE_SOURCE_COUNT_MISMATCH")
    require(persistence["focused_tests"] == len(documents["SOURCE_MANIFEST"]["focused_tests"]),
            "PERSISTENCE_FOCUSED_TEST_COUNT_MISMATCH")
    # A new sibling final-verification folder is permitted. Every previously
    # tracked approved path remains frozen, including historical report flags.
    original_paths = set(git(REPO, "ls-tree", "-r", "--name-only", SOURCE_COMMIT).decode().splitlines())
    changed = set(git(REPO, "diff", "--name-only", SOURCE_COMMIT).decode().splitlines())
    require(not original_paths.intersection(changed), "APPROVED_TRACKED_PATH_CHANGED")


def verify_remote_setup(setup, reproduction, documents, required_inputs):
    expected = {
        "schema": 1, "status": "PASS", "remote": REMOTE, "branch": BRANCH,
        "revision": SOURCE_COMMIT, "clone_method": "REMOTE_GIT_CLONE",
        "source_or_asset_copies": False, "git_alternates": [],
        "git_status_before_reproduction": "", "shared_system_toolchain": True,
    }
    for name, value in expected.items():
        require(setup.get(name) == value, "CLEAN_SETUP_RECEIPT_FAILED: " + name)
    checkout_input = Path(setup["checkout"])
    require(checkout_input.is_absolute() and checkout_input.is_dir(), "INVALID_CLEAN_CHECKOUT")
    checkout = checkout_input.resolve()
    require(str(checkout) == setup["checkout"] and checkout != REPO,
            "CLEAN_CHECKOUT_MUST_BE_SEPARATE_REAL_PATH")
    require(reproduction.get("checkout") == str(checkout), "CLEAN_CHECKOUT_RECEIPT_PATH_MISMATCH")
    require(git(checkout, "rev-parse", "HEAD").decode().strip() == SOURCE_COMMIT,
            "ACTUAL_CLEAN_CHECKOUT_REVISION_MISMATCH")
    require(git(checkout, "remote", "get-url", "origin").decode().strip() == REMOTE,
            "ACTUAL_CLEAN_CHECKOUT_REMOTE_MISMATCH")
    require(git(checkout, "status", "--porcelain", "--untracked-files=no") == b"",
            "ACTUAL_CLEAN_CHECKOUT_TRACKED_FILES_DIRTY")
    alternate_name = git(checkout, "rev-parse", "--git-path", "objects/info/alternates").decode().strip()
    alternate = Path(alternate_name)
    if not alternate.is_absolute():
        alternate = checkout / alternate
    require(not alternate.exists() or not alternate.read_text().strip(), "LOCAL_GIT_OBJECT_ALTERNATES_FOUND")
    dependencies = documents["DEPENDENCY_MANIFEST"]
    npm = setup.get("npm_ci", {})
    require(npm.get("status") == "PASS" and npm.get("fresh_install") is True,
            "FRESH_NPM_CI_NOT_VERIFIED")
    require(npm.get("command") == dependencies["setup"], "NPM_SETUP_COMMAND_CHANGED")
    packages = {row["name"]: row["version"] for row in npm.get("packages", [])}
    for row in dependencies["dependencies"]:
        if row["ecosystem"] != "npm":
            continue
        name, version = row["name"], row["version"]
        require(packages.get(name) == version, "NPM_SETUP_VERSION_MISMATCH: " + name)
        installed = load(checkout / "cinematic-world-map/node_modules" / name / "package.json")
        require(installed.get("name") == name and installed.get("version") == version,
                "ACTUAL_INSTALLED_NPM_VERSION_MISMATCH: " + name)
    require(setup.get("toolchain") == dependencies["observed_toolchain"]["interpreters"],
            "PINNED_SYSTEM_TOOLCHAIN_VERSION_MISMATCH")
    # Remote LFS hydration must include exactly the retained original LFS bodies,
    # rather than current-workspace asset copies or pointer files.
    expected_lfs = {}
    for name, body in required_inputs.items():
        pointer = git(checkout, "show", "HEAD:" + name)
        if pointer.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            lines = pointer.decode().splitlines()
            require(lines[1] == "oid sha256:" + body["sha256"]
                    and lines[2] == "size " + str(body["bytes"]),
                    "LFS_POINTER_BODY_BINDING_MISMATCH: " + name)
            expected_lfs[name] = body
    hydrated = {}
    for row in setup.get("lfs_objects", []):
        require(row.get("source") == "REMOTE_GIT_LFS" and row.get("status") == "PASS",
                "LFS_REMOTE_HYDRATION_NOT_VERIFIED")
        require(row["path"] not in hydrated, "DUPLICATE_LFS_RECEIPT")
        hydrated[row["path"]] = {k: row[k] for k in ("path", "sha256", "bytes")}
    require(hydrated == expected_lfs and expected_lfs, "REMOTE_LFS_INPUT_SET_MISMATCH")
    # Frozen lock files are covered by the reproduced required-input body hashes.
    for row in dependencies["dependency_locks"]:
        require(required_inputs.get(row["path"]) == {k: row[k] for k in ("path", "sha256", "bytes")},
                "DEPENDENCY_LOCK_NOT_BOUND_TO_REPRODUCED_INPUT: " + row["path"])
    return checkout


def verify_clean_reproduction(reproduction, documents, checkout):
    approved_report = load(REPO / BASE / "evidence/proof/REPORT.json")
    require(approved_report["status"] == "PASS" and approved_report["sourceCommit"] == RENDER_COMMIT,
            "APPROVED_RENDER_SOURCE_BINDING_FAILED")
    expected = {
        "schema": 1, "status": "PASS", "approvedSourceRevision": SOURCE_COMMIT,
        "cleanCheckoutBefore": True, "cleanCheckoutAfter": True,
        "sharedSystemToolchain": True, "noLocalSourceOrAssetCopies": True,
        "originalPublicProofModified": False, "rawFramesBitExact": 210,
        "nativePngFramesBitExact": 210, "checkpointPngsBitExact": 7,
        "actualRuntimeOrigin": str(checkout), "requiredTempOnlyFiles": [],
    }
    for name, value in expected.items():
        require(reproduction.get(name) == value, "CLEAN_REPRODUCTION_RECEIPT_FAILED: " + name)
    frames = reproduction.get("frames", [])
    require(len(frames) == 210 and len(approved_report["frames"]) == 210,
            "CLEAN_REPRODUCTION_FRAME_COUNT_MISMATCH")
    for frame, (actual, golden) in enumerate(zip(frames, approved_report["frames"], strict=True)):
        require(actual.get("frame") == frame and golden["frame"] == frame,
                "REPRODUCTION_FRAME_SEQUENCE_CHANGED")
        require(actual.get("rawBitExact") is True and actual.get("pngBitExact") is True
                and actual.get("cameraTimelineEventIdentical") is True,
                "REPRODUCTION_CAMERA_TIMELINE_EVENT_OR_PIXELS_CHANGED: " + str(frame))
        require(actual.get("state") == golden["state"]
                and actual.get("raw_rgba_sha256") == golden["raw_rgba_sha256"]
                and actual.get("png_sha256") == golden["png_sha256"],
                "REPRODUCTION_APPROVED_FRAME_HASH_MISMATCH: " + str(frame))
    output = FINAL / "evidence/clean-reproduction"
    checkpoints = reproduction.get("checkpoints", [])
    require(len(checkpoints) == 7 and len(approved_report["checkpoints"]) == 7,
            "REPRODUCTION_CHECKPOINT_COUNT_MISMATCH")
    output_bindings = []
    for actual, golden in zip(checkpoints, approved_report["checkpoints"], strict=True):
        require(actual.get("bitExact") is True, "CHECKPOINT_NOT_BIT_EXACT")
        require(all(actual.get(k) == golden[k] for k in ("frame", "state", "file", "sha256", "bytes")),
                "CHECKPOINT_APPROVED_BINDING_MISMATCH")
        require(Path(actual["file"]).name == actual["file"], "UNSAFE_CHECKPOINT_FILENAME")
        body = record(output / actual["file"])
        require(body["sha256"] == golden["sha256"] and body["bytes"] == golden["bytes"],
                "ACTUAL_REPRODUCED_CHECKPOINT_BODY_MISMATCH")
        output_bindings.append(body)
    require(reproduction.get("encodeCommand", [])[:-1] == approved_report["encodeCommand"][:-1],
            "APPROVED_ENCODER_PARAMETERS_CHANGED")
    require(reproduction["encodeCommand"][-1] == str(output / MP4_NAME),
            "REPRODUCED_VIDEO_OUTPUT_PATH_MISMATCH")
    video = reproduction.get("video", {})
    require(video.get("file") == MP4_NAME and video.get("approvedSha256") == APPROVED_SHA,
            "REPRODUCED_VIDEO_APPROVAL_BINDING_MISMATCH")
    video_body = record(output / MP4_NAME)
    require(video.get("sha256") == video_body["sha256"] and video.get("bytes") == video_body["bytes"],
            "ACTUAL_REPRODUCED_MP4_BODY_MISMATCH")
    if reproduction.get("result") == "BIT_EXACT":
        require(video.get("bitExact") is True and video_body["sha256"] == APPROVED_SHA
                and video_body["bytes"] == approved_report["video"]["bytes"]
                and video.get("decodedEquality") == "IMPLIED_BY_IDENTICAL_MP4_BYTES",
                "REPRODUCED_MP4_NOT_BIT_EXACT")
    else:
        require(reproduction.get("result") == "DECODED_PIXEL_EQUALITY"
                and video.get("bitExact") is False
                and video.get("decodedEquality") == "210_OF_210_FRAME_HASHES_EQUAL",
                "REPRODUCED_MP4_DECODED_PIXEL_EQUALITY_NOT_VERIFIED")
    streams = reproduction.get("ffprobe", {}).get("streams", [])
    require(len(streams) == 1, "REPRODUCED_VIDEO_NOT_SILENT_SINGLE_STREAM")
    stream = streams[0]
    require(stream.get("width") == 1080 and stream.get("height") == 1920
            and stream.get("avg_frame_rate") == "30/1"
            and int(stream.get("nb_read_frames", 0)) == 210
            and float(stream.get("duration", 0)) == 7,
            "REPRODUCED_VIDEO_FORMAT_CHANGED")
    output_bindings.append(video_body)
    # Original public proof is frozen at its immutable media commit. Private
    # verification media are not exposed through or added to public-review.
    approved_public = REPO / BASE / "public-review"
    approved_body = record(approved_public / MP4_NAME)
    require(approved_body["sha256"] == APPROVED_SHA, "APPROVED_PUBLIC_MP4_CHANGED")
    require(git(REPO, "show", MEDIA_COMMIT + ":" + BASE + "/public-review/" + MP4_NAME)
            == (approved_public / MP4_NAME).read_bytes(), "APPROVED_MEDIA_COMMIT_BINDING_FAILED")
    require({p.name for p in approved_public.iterdir()} == {MP4_NAME, "SHA256SUMS"}
            | {row["file"] for row in approved_report["checkpoints"]},
            "APPROVED_PUBLIC_PROOF_CONTENT_SET_CHANGED")
    return output_bindings


def build():
    receipts = receipt_paths()
    approval, persistence, setup, reproduction = (load(receipts[name]) for name in
                                                ("approval", "persistence", "setup", "reproduction"))
    verify_user_review(approval)
    documents, bindings = load_frozen_manifests()
    verify_persistence(persistence, documents)
    expected_inputs = normalized_records(documents["HASH_MANIFEST"]["required_files"])
    actual_inputs = normalized_records(reproduction.get("requiredInputs"))
    require(actual_inputs == expected_inputs, "ACTUAL_REPRODUCED_INPUT_HASH_SET_MISMATCH")
    checkout = verify_remote_setup(setup, reproduction, documents, actual_inputs)
    outputs = verify_clean_reproduction(reproduction, documents, checkout)
    for name, document in documents.items():
        require(document.get("required_temp_only_files") == [],
                "REQUIRED_TEMP_ONLY_INPUT_IN_MANIFEST: " + name)
    require(documents["IMPORT_MANIFEST"].get("issues") == [], "UNRESOLVED_APPROVED_IMPORTS")
    for name in documents["IMPORT_MANIFEST"]["reachable_modules"]:
        require(name in actual_inputs, "REACHABLE_IMPORT_MISSING_FROM_REPRODUCED_INPUTS: " + name)
    for row in documents["SOURCE_MANIFEST"]["entries"] + documents["FIXTURE_MANIFEST"]["entries"]:
        require(actual_inputs.get(row["path"]) == {k: row[k] for k in ("path", "sha256", "bytes")},
                "SOURCE_OR_FIXTURE_NOT_BOUND_TO_ACTUAL_REPRODUCTION: " + row["path"])
    for route in documents["RUNTIME_ASSET_MANIFEST"]["runtime_routes"]:
        require(route["file"] in actual_inputs, "RUNTIME_ASSET_ROUTE_NOT_PERSISTED: " + route["file"])
    plan = load(REPO / BASE / "fixtures/DETAIL_ADAPTER_PLAN.json")
    require(plan["totalFrames"] == 210 and plan["fps"] == 30 and plan["durationSeconds"] == 7,
            "APPROVED_EVENT_PROFILE_CHANGED")
    gate = {
        "schema": 1, "baseline_name": "EVENT_SYSTEM_V1_FINAL_BASELINE", "status": "PASS",
        "user_video_review": "PASS", "approved_source_commit": SOURCE_COMMIT,
        "approved_media_commit": MEDIA_COMMIT, "gates": {name: "PASS" for name in GATE_NAMES},
        "passed": 7, "total": 7, "required_temp_only_files": [],
        "verification_receipts": {name: record(file) for name, file in receipts.items()},
        "manifest_bindings": bindings,
        "verification_scope": {
            "candidate_persistence_builder_runs": 1,
            "candidate_required_inputs_including_self_bindings": persistence["required_files"],
            "actual_remote_reproduction_required_input_hashes": len(actual_inputs),
            "raw_rgba_frames_bit_exact": 210, "native_png_frames_bit_exact": 210,
            "checkpoint_pngs_bit_exact": 7, "mp4_result": reproduction["result"],
            "legacy_full_visual_suites_repeated": False,
            "same_pinned_system_toolchain": True, "new_operating_system_image_claimed": False,
            "approved_candidate_historical_flags_rewritten": False,
            "approved_public_proof_modified": False,
        },
        "gate_evidence": {
            "SOURCE_PERSISTED": ["persistence", "setup", "reproduction", "SOURCE_MANIFEST"],
            "ASSETS_PERSISTED": ["persistence", "setup", "reproduction", "RUNTIME_ASSET_MANIFEST", "FIXTURE_MANIFEST"],
            "HASH_MANIFEST_PASS": ["persistence", "reproduction", "HASH_MANIFEST"],
            "DEPENDENCY_MANIFEST_PASS": ["persistence", "setup", "reproduction", "DEPENDENCY_MANIFEST"],
            "IMPORT_MANIFEST_PASS": ["persistence", "reproduction", "IMPORT_MANIFEST"],
            "NO_REQUIRED_TEMP_FILES": ["persistence", "setup", "reproduction", "all_frozen_manifests"],
            "CLEAN_ENV_REPRODUCIBLE": ["setup", "reproduction"],
        },
    }
    event = plan["eventPlan"]
    manifest = {
        "schema": 1, "baseline_name": "EVENT_SYSTEM_V1_FINAL_BASELINE",
        "state": "EVENT_SYSTEM_V1_FINAL", "user_video_review": "PASS",
        "branch": BRANCH, "parent_v5_baseline": {
            "name": "V5_CAMERA_DIRECTOR_FINAL_BASELINE", "commit": V5_COMMIT,
        },
        "event_source_commit": SOURCE_COMMIT,
        "event_original_render_source_commit": RENDER_COMMIT,
        "approved_media_commit": MEDIA_COMMIT,
        "approved_mp4": BASE + "/public-review/" + MP4_NAME,
        "approved_mp4_sha256": APPROVED_SHA,
        "source_manifest_sha256": bindings["SOURCE_MANIFEST"]["sha256"],
        "asset_manifest_sha256": bindings["RUNTIME_ASSET_MANIFEST"]["sha256"],
        "fixture_manifest_sha256": bindings["FIXTURE_MANIFEST"]["sha256"],
        "asset_fixture_manifests": {
            "asset": bindings["RUNTIME_ASSET_MANIFEST"], "fixture": bindings["FIXTURE_MANIFEST"],
        },
        "dependency_manifest_sha256": bindings["DEPENDENCY_MANIFEST"]["sha256"],
        "import_manifest_sha256": bindings["IMPORT_MANIFEST"]["sha256"],
        "hash_manifest_sha256": bindings["HASH_MANIFEST"]["sha256"],
        "all_manifest_bindings": bindings,
        "verification_procedures": [record(FINAL / name) for name in (
            "reproduce_clean_candidate.mjs", "finalize_baseline.py", "scan_final_freeze.py"
        )],
        "event_profile": {
            "version": event["version"], "intent_version": event["intent"]["version"],
            "detail_adapter_version": plan["version"], "detail_timeline_version": plan["timelineVersion"],
            "profile": event["profile"], "fps": plan["fps"], "total_frames": plan["totalFrames"],
            "duration_seconds": plan["durationSeconds"], "detail_lock_frame": plan["detailLockFrame"],
            "camera_ownership": plan["ownership"],
        },
        "protected_baselines": documents["SOURCE_MANIFEST"]["baselines"],
        "protected_original_paths_changed": [],
        "permanent_gate_result": {"status": "PASS", "passed": 7, "total": 7,
                                  "gates": gate["gates"]},
        "clean_reproduction": {
            "result": reproduction["result"], "source_revision": SOURCE_COMMIT,
            "actual_remote_checkout": True, "fresh_npm_ci": True,
            "system_toolchain": "EXISTING_PINNED_SYSTEM_TOOLS",
            "new_operating_system_image_claimed": False,
            "raw_rgba_frames_bit_exact": 210, "native_png_frames_bit_exact": 210,
            "checkpoint_pngs_bit_exact": 7, "verification_outputs": outputs,
        },
        "verification_receipts": gate["verification_receipts"],
        "required_temp_only_files": [],
        "public_proof": {"unchanged": True, "new_user_review_media_required": False,
                         "private_verification_evidence_published": False},
        "containing_commit_binding": "GIT_COMMIT_CONTAINING_THIS_MANIFEST_REPORTED_EXTERNALLY",
        "self_hash_policy": "SHA256_OF_EXACT_MANIFEST_BYTES_REPORTED_AFTER_WRITE",
    }
    return gate, manifest


def encode(document):
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write private final gate and baseline manifest.")
    args = parser.parse_args()
    require(args.write, "EXPLICIT_WRITE_FLAG_REQUIRED")
    gate_file = FINAL / "evidence/PERMANENT_GATE.json"
    manifest_file = FINAL / "FINAL_MANIFEST.json"
    require(not gate_file.exists() and not manifest_file.exists(), "FINAL_OUTPUT_ALREADY_EXISTS")
    try:
        gate, manifest = build()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        failure = {
            "schema": 1, "baseline_name": "EVENT_SYSTEM_V1_FINAL_BASELINE", "status": "FAIL",
            "gates": {name: "NOT_ADMITTED" for name in GATE_NAMES}, "passed": 0, "total": 7,
            "decision": "EVENT_SYSTEM_V1_FINAL_BLOCKED", "error": str(error),
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        gate_file.parent.mkdir(parents=True, exist_ok=True)
        gate_file.write_bytes(encode(failure))
        print(json.dumps(failure), file=sys.stderr)
        return 1
    gate["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    gate_file.write_bytes(encode(gate))
    manifest["permanent_gate_receipt"] = record(gate_file)
    manifest_file.write_bytes(encode(manifest))
    print(json.dumps({"status": "PASS", "decision": "EVENT_SYSTEM_V1_FINAL", "gates": 7,
                      "manifest": record(manifest_file), "permanent_gate": record(gate_file)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
