#!/usr/bin/env python3
"""Freeze the user-approved Area V3 and Wave visual from remote reproduction.

Read frozen manifests and retained receipts once; never render, tune a visual,
rerun historical synthetic tests, or edit a Candidate file. --write requires an
actual successful clean checkout receipt. --scan examines only this new final
verification folder with pinned Gitleaks defaults and redacted output.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/event-tsunami-wave-polish-v3"
AREA = ENGINE + "/recovery/event-area-propagation-v3"
APPROVED_BRANCH = "development/event-tsunami-wave-polish-v3-20261013"
FINAL_BRANCH = "development/event-area-v3-final-planner-v1-20261013"
VALIDATION = "a6ef67fa16143dc2bd53b334d583c05cf1476bed"
MEDIA = "263a5250671a36297892ebe4b11380fdfb927a9b"
SOURCE = "1e52b58deaf0fa1a48d6966c0d0e19f55e8b8cd0"
FLOW = "fbc3be89d94040271c7f54a051162913ad134bac"
FLOW_MANIFEST = ENGINE + "/recovery/event-flow-v2-final/FINAL_MANIFEST.json"
FLOW_SHA = "43f83ff77895ef8f4749b328a49a3acd0bb6b13667198347bb606e187efbe1e3"
V1 = "f79f3d55d945ef0e53b03ac2ed666f48f28b5881"
V5 = "29b8ee294360812b55ef577b62411de58159003b"
MP4 = "TOHOKU_2011_TSUNAMI_WAVE_VISUAL_POLISH.mp4"
APPROVED_SHA = "d41891620cf08aa953eed78e5b0d443b51843b173912fa1f887fb7e163d9ead7"
BASELINE = "EVENT_FEATURE_BUNDLE_V3_AREA_FINAL_BASELINE"
PINNED_SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
NAMES = ("SOURCE", "FIXTURE", "RUNTIME_ASSET", "DEPENDENCY", "IMPORT", "HASH",
         "REPRODUCTION", "BUILD_INPUT", "DATA", "EVIDENCE")
TEXT_SUFFIXES = {".json", ".geojson", ".py", ".mjs", ".js", ".md", ".txt", ".lock", ".log", ".sh", ""}


def frozen_helpers():
    path = ENGINE + "/recovery/event-v1-final/finalize_baseline.py"
    body = (REPO / path).read_bytes()
    approved = subprocess.check_output(["git", "show", VALIDATION + ":" + path], cwd=REPO)
    if body != approved:
        raise ValueError("FROZEN_CANONICAL_GATE_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("readonly_area_final_gate_helpers", REPO / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO, module.FINAL, module.BASE = REPO, ROOT, BASE
    module.SOURCE_COMMIT, module.MEDIA_COMMIT, module.RENDER_COMMIT = VALIDATION, MEDIA, SOURCE
    module.BRANCH, module.APPROVED_SHA, module.MP4_NAME = APPROVED_BRANCH, APPROVED_SHA, MP4
    return module, path


H, HELPER = frozen_helpers()
require, git, record, load, encode = H.require, H.git, H.record, H.load, H.encode


def verify_original_paths():
    original = set(git(REPO, "ls-tree", "-r", "--name-only", VALIDATION).decode().splitlines())
    changed = original & set(git(REPO, "diff", "--name-only", VALIDATION).decode().splitlines())
    require(not changed, "APPROVED_TRACKED_PATH_CHANGED")
    parent = record(REPO / FLOW_MANIFEST)
    require(parent["sha256"] == FLOW_SHA and (REPO / FLOW_MANIFEST).read_bytes()
            == git(REPO, "show", FLOW + ":" + FLOW_MANIFEST), "PARENT_FLOW_FINAL_CHANGED")
    return {"approved_revision": VALIDATION, "original_tracked_paths": len(original),
            "changed_original_paths": [], "parent_flow_manifest": parent}


def verify_approval():
    approval = load(ROOT / "USER_REVIEW_APPROVAL.json")
    expected = {"schema": 1, "user_video_review": "PASS", "approved_branch": APPROVED_BRANCH,
                "approved_media_commit": MEDIA, "approved_source_commit": VALIDATION,
                "original_render_source_commit": SOURCE, "approved_mp4_sha256": APPROVED_SHA}
    for name, value in expected.items():
        require(approval.get(name) == value, "USER_APPROVAL_BINDING_CHANGED: " + name)
    instruction = ROOT / "USER_INSTRUCTION.txt"
    require(approval.get("instruction") == record(instruction), "USER_INSTRUCTION_BINDING_CHANGED")
    text = instruction.read_text()
    require(APPROVED_SHA in text and "USER_VIDEO_REVIEW:\nPASS" in text
            and "263a525" in text, "EXPLICIT_APPROVED_CANDIDATE_NOT_IN_INSTRUCTION")
    return approval


def verify_inventory():
    docs, bindings = H.load_frozen_manifests()
    expected = H.normalized_records(docs["HASH_MANIFEST"]["required_files"]
            + [bindings["HASH_MANIFEST"], record(REPO / BASE / "manifests/SHA256SUMS")])
    persistence = load(REPO / BASE / "evidence/POST_COMMIT_VERIFICATION.json")
    require(persistence.get("inventory_status") == "PASS"
            and persistence.get("inventory_stage") == "candidate"
            and persistence.get("head_and_index_compared") is True
            and persistence.get("required_temp_only_files") == 0, "APPROVED_PERSISTENCE_RECEIPT_FAILED")
    require(persistence.get("required_files") == len(expected), "APPROVED_INVENTORY_COUNT_CHANGED")
    for relative, row in expected.items():
        require(record(REPO / relative) == row, "APPROVED_INPUT_HASH_CHANGED: " + relative)
        saved = git(REPO, "show", VALIDATION + ":" + relative)
        if saved.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            lines = saved.decode().splitlines()
            require(lines[1] == "oid sha256:" + row["sha256"]
                    and lines[2] == "size " + str(row["bytes"]), "SAVED_LFS_BINDING_CHANGED")
        else:
            require(hashlib.sha256(saved).hexdigest() == row["sha256"] and len(saved) == row["bytes"],
                    "APPROVED_INPUT_NOT_PERSISTED: " + relative)
    for doc in docs.values():
        require(doc.get("required_temp_only_files") == [], "REQUIRED_TEMPORARY_INPUT_FOUND")
    imports = docs["IMPORT_MANIFEST"]
    require(imports.get("issues") == [], "UNRESOLVED_IMPORT")
    require(persistence.get("reachable_import_modules") == len(imports["reachable_modules"])
            and persistence.get("import_edges") == len(imports["edges"]), "IMPORT_INVENTORY_COUNT_CHANGED")
    for name in imports["reachable_modules"]:
        require(name in expected, "IMPORT_MODULE_OUTSIDE_PERSISTED_INVENTORY: " + name)
    for row in docs["SOURCE_MANIFEST"]["entries"] + docs["FIXTURE_MANIFEST"]["entries"]:
        require(expected.get(row["path"]) == {k: row[k] for k in ("path", "sha256", "bytes")},
                "SOURCE_OR_FIXTURE_BINDING_CHANGED")
    for route in docs["RUNTIME_ASSET_MANIFEST"]["runtime_routes"]:
        require(route["file"] in expected, "RUNTIME_ASSET_NOT_PERSISTED")
    inherited = load(REPO / AREA / "evidence/SYNTHETIC.json")
    require(inherited.get("status") == "PASS", "INHERITED_AREA_WAR_GENERALIZATION_NOT_PASS")
    return docs, bindings, expected, persistence


def verify_reproduction(docs, expected):
    setup = load(ROOT / "evidence/CLEAN_CHECKOUT_SETUP.json")
    receipt = load(ROOT / "evidence/CLEAN_REPRODUCTION.json")
    require(H.normalized_records(receipt.get("requiredInputs")) == expected,
            "REMOTE_REQUIRED_INPUT_SET_CHANGED")
    checkout = H.verify_remote_setup(setup, receipt, docs, expected)
    golden = load(REPO / BASE / "evidence/proof/REPORT.json")
    require(golden.get("status") == "PASS" and golden.get("sourceCommit") == SOURCE
            and golden.get("totalFrames") == 240 and golden.get("durationSeconds") == 8,
            "APPROVED_PROOF_BINDING_CHANGED")
    conditions = {"schema": 1, "status": "PASS", "approvedSourceRevision": VALIDATION,
                  "originalRenderSourceRevision": SOURCE, "cleanCheckoutBefore": True,
                  "cleanCheckoutAfter": True, "sharedSystemToolchain": True,
                  "noLocalSourceOrAssetCopies": True, "originalPublicProofModified": False,
                  "rawFramesBitExact": 240, "nativePngFramesBitExact": 240,
                  "checkpointPngsBitExact": 8, "requiredTempOnlyFiles": []}
    for name, value in conditions.items():
        require(receipt.get(name) == value, "CLEAN_REPRODUCTION_FAILED: " + name)
    actual_frames = receipt.get("frames", [])
    require(len(actual_frames) == len(golden["frames"]) == 240, "REPRODUCED_FRAME_COUNT_CHANGED")
    for index, (actual, approved) in enumerate(zip(actual_frames, golden["frames"], strict=True)):
        require(actual.get("frame") == approved["frame"] == index, "REPRODUCED_FRAME_ORDER_CHANGED")
        require(actual.get("rawBitExact") is True and actual.get("pngBitExact") is True
                and actual.get("cameraTimelineEventIdentical") is True, "APPROVED_VISUAL_OR_TIMING_CHANGED")
        require(all(actual.get(k) == approved[k] for k in ("state", "raw_rgba_sha256", "png_sha256")),
                "APPROVED_FRAME_HASH_CHANGED")
    output = ROOT / "evidence/clean-reproduction"
    checkpoints = receipt.get("checkpoints", [])
    require(len(checkpoints) == len(golden["checkpoints"]) == 8, "APPROVED_CHECKPOINT_COUNT_CHANGED")
    outputs = []
    for actual, approved in zip(checkpoints, golden["checkpoints"], strict=True):
        require(actual.get("bitExact") is True and all(actual.get(k) == approved[k]
                for k in ("frame", "state", "file", "sha256", "bytes")), "CHECKPOINT_APPROVAL_BINDING_CHANGED")
        require(Path(actual["file"]).name == actual["file"], "UNSAFE_CHECKPOINT_FILENAME")
        body = record(output / actual["file"])
        require(all(body[k] == approved[k] for k in ("sha256", "bytes")), "CHECKPOINT_BODY_CHANGED")
        outputs.append(body)
    require(receipt.get("encodeCommand", [])[:-1] == golden["encodeCommand"][:-1], "ENCODER_PARAMETERS_CHANGED")
    require(receipt["encodeCommand"][-1] == str(output / MP4), "ENCODER_OUTPUT_PATH_CHANGED")
    video = receipt.get("video", {})
    body = record(output / MP4)
    require(video.get("file") == MP4 and video.get("approvedSha256") == APPROVED_SHA
            and all(video.get(k) == body[k] for k in ("sha256", "bytes")), "REPRODUCED_MP4_BINDING_CHANGED")
    if receipt.get("result") == "BIT_EXACT":
        require(video.get("bitExact") is True and body["sha256"] == APPROVED_SHA
                and body["bytes"] == golden["video"]["bytes"]
                and video.get("decodedEquality") == "IMPLIED_BY_IDENTICAL_MP4_BYTES", "MP4_NOT_BIT_EXACT")
    else:
        require(receipt.get("result") == "DECODED_PIXEL_EQUALITY" and video.get("bitExact") is False
                and video.get("decodedEquality") == "240_OF_240_FRAME_HASHES_EQUAL", "DECODED_PIXEL_EQUALITY_NOT_VERIFIED")
    streams = receipt.get("ffprobe", {}).get("streams", [])
    require(len(streams) == 1, "REPRODUCED_MP4_NOT_SILENT_SINGLE_STREAM")
    stream = streams[0]
    require((stream.get("codec_type"), stream.get("codec_name"), stream.get("width"), stream.get("height"),
             stream.get("avg_frame_rate")) == ("video", "h264", 1080, 1920, "30/1")
            and int(stream.get("nb_read_frames", 0)) == 240 and float(stream.get("duration", 0)) == 8,
            "REPRODUCED_MP4_FORMAT_CHANGED")
    public = REPO / BASE / "public-review"
    allow = {MP4, "SHA256SUMS"} | {row["file"] for row in golden["checkpoints"]}
    require({p.name for p in public.iterdir()} == allow, "APPROVED_PUBLIC_REVIEW_ALLOWLIST_CHANGED")
    for file in public.iterdir():
        require(file.is_file() and not file.is_symlink()
                and file.read_bytes() == git(REPO, "show", MEDIA + ":" + file.relative_to(REPO).as_posix()),
                "ORIGINAL_APPROVED_PUBLIC_BODY_CHANGED")
    require(record(public / MP4)["sha256"] == APPROVED_SHA, "USER_APPROVED_MP4_SHA_CHANGED")
    return receipt, golden, [*outputs, body], checkout


def build():
    verify_approval()
    protection = verify_original_paths()
    docs, bindings, expected, persistence = verify_inventory()
    reproduction, approved, outputs, checkout = verify_reproduction(docs, expected)
    receipts = {name: record(ROOT / relative) for name, relative in {
        "approval": "USER_REVIEW_APPROVAL.json", "setup": "evidence/CLEAN_CHECKOUT_SETUP.json",
        "reproduction": "evidence/CLEAN_REPRODUCTION.json"}.items()}
    receipts["candidate_persistence"] = record(REPO / BASE / "evidence/POST_COMMIT_VERIFICATION.json")
    gates = {name: "PASS" for name in H.GATE_NAMES}
    gate = {"schema": 1, "baseline_name": BASELINE, "status": "PASS", "user_video_review": "PASS",
            "passed": 7, "total": 7, "gates": gates, "required_temp_only_files": [],
            "manifest_bindings": bindings, "verification_receipts": receipts, "protection": protection,
            "verification_scope": {"candidate_builder_reruns": 0, "historical_synthetic_reruns": 0,
                "required_inputs_verified": len(expected), "remote_required_input_hashes": len(expected),
                "raw_frames_bit_exact": 240, "native_png_frames_bit_exact": 240,
                "checkpoint_pngs_bit_exact": 8, "mp4_result": reproduction["result"],
                "shared_pinned_system_toolchain": True, "new_os_image_claimed": False,
                "approved_source_or_visual_changed": False, "historical_candidate_flags_rewritten": False,
                "public_proof_changed": False, "part_b_executed_during_final_gate": False},
            "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    feature = {"quality_grade": "FACT_BASED_VISUAL_GRADE",
        "primitives": ["AREA_REVEAL", "AREA_GROW", "AREA_CONTRACT", "AREA_MOVE", "AREA_HOLD",
            "PROPAGATION_RING", "PROPAGATION_WAVE", "IMPACT_ZONE", "FRONT_LINE", "STATE_TRANSITION", "TIME_STEP"],
        "approved_wave_visual": {"profile": "IRREGULAR_OPEN_WAVE_FRONT_V3", "major_fronts": 3,
            "sequential_contact_segments": 9, "closed_ring_in_approved_proof": False,
            "physics_simulation": False, "fixture": record(REPO / BASE / "fixtures/REAL_FIXTURE.json"),
            "native_coastline": record(REPO / BASE / "data/NATIVE_COASTLINE.json")},
        "duration_seconds": 8, "frames": 240, "fps": 30, "wave_plan_timing": approved["wavePlanTiming"],
        "area_war_generalization": {"status": "INHERITED_PASS_UNCHANGED",
            "receipt": record(REPO / AREA / "evidence/SYNTHETIC.json")}}
    parent_flow = {"name": "EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE", "commit": FLOW,
                   "manifest": protection["parent_flow_manifest"], "manifest_sha256": FLOW_SHA}
    manifest = {"schema": 1, "baseline_name": BASELINE, "state": "EVENT_FEATURE_BUNDLE_V3_AREA_FINAL",
        "user_video_review": "PASS", "branch": FINAL_BRANCH, "parent_flow": parent_flow,
        "parent_event_v1": {"name": "EVENT_SYSTEM_V1_FINAL_BASELINE", "commit": V1},
        "parent_v5": {"name": "V5_CAMERA_DIRECTOR_FINAL_BASELINE", "commit": V5},
        "area_candidate_commit": git(REPO, "rev-parse", "a479033").decode().strip(),
        "source_commit": SOURCE, "approved_candidate_commit": MEDIA, "approved_media_commit": MEDIA,
        "approved_validation_commit": VALIDATION, "approved_mp4": BASE + "/public-review/" + MP4,
        "approved_mp4_sha256": APPROVED_SHA, "source_manifest_sha256": bindings["SOURCE_MANIFEST"]["sha256"],
        "asset_manifest_sha256": bindings["RUNTIME_ASSET_MANIFEST"]["sha256"],
        "fixture_manifest_sha256": bindings["FIXTURE_MANIFEST"]["sha256"],
        "dependency_manifest_sha256": bindings["DEPENDENCY_MANIFEST"]["sha256"],
        "import_manifest_sha256": bindings["IMPORT_MANIFEST"]["sha256"],
        "all_manifest_bindings": bindings, "asset_manifest": bindings["RUNTIME_ASSET_MANIFEST"],
        "dependency_manifest": bindings["DEPENDENCY_MANIFEST"], "feature_profile": feature,
        "gate_result": {"status": "PASS", "passed": 7, "total": 7, "gates": gates},
        "clean_reproduction": {"result": reproduction["result"], "source_revision": VALIDATION,
            "original_render_source_revision": SOURCE, "remote_checkout": True, "fresh_npm_ci": True,
            "raw_frames_bit_exact": 240, "native_png_frames_bit_exact": 240,
            "checkpoint_pngs_bit_exact": 8, "runtime_checkout": str(checkout),
            "verification_outputs": outputs, "new_os_image_claimed": False},
        "verification_receipts": receipts, "readonly_canonical_helper": record(REPO / HELPER),
        "reproduction_instructions": record(ROOT / "README.md"), "required_temp_only_files": [],
        "public_proof": {"unchanged": True, "new_user_video_required": False,
            "source_diagnostics_internal_plan_added": False},
        "containing_commit_binding": "GIT_COMMIT_CONTAINING_THIS_MANIFEST_REPORTED_EXTERNALLY",
        "self_hash_policy": "SHA256_OF_EXACT_MANIFEST_BYTES_REPORTED_AFTER_WRITE"}
    return gate, manifest


def scan(scanner):
    scanner = Path(scanner).resolve()
    require(hashlib.sha256(scanner.read_bytes()).hexdigest() == PINNED_SCANNER_SHA, "UNPINNED_SECRET_SCANNER")
    require(subprocess.check_output([str(scanner), "version"], text=True).strip() == "8.24.3", "SCANNER_VERSION_CHANGED")
    paths = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "SECRET_SCAN.json"
                   and p.suffix.lower() in TEXT_SUFFIXES)
    rows = []
    env = os.environ.copy()
    env.pop("GITLEAKS_CONFIG", None)
    env.pop("GITLEAKS_CONFIG_TOML", None)
    with tempfile.TemporaryDirectory(prefix="area-v3-final-secret-scan-") as tmpname:
        tmp, stage = Path(tmpname), Path(tmpname) / "scope"
        stage.mkdir()
        config, ignore = tmp / "default.toml", tmp / "empty.gitleaksignore"
        config.write_text("[extend]\nuseDefault = true\n")
        ignore.write_text("")
        for path in paths:
            require(not path.is_symlink(), "SYMLINK_IN_SECRET_SCAN_SCOPE")
            body = path.read_bytes()
            require(b"\x00" not in body, "BINARY_DECLARED_AS_TEXT")
            body.decode("utf-8")
            destination = stage / path.relative_to(REPO)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            rows.append(record(path))
        report = tmp / "findings.json"
        command = [str(scanner), "dir", str(stage), "--redact=100", "--max-decode-depth=3",
            "--ignore-gitleaks-allow", "--no-banner", "--no-color", "--config", str(config),
            "--gitleaks-ignore-path", str(ignore), "--report-format=json", "--report-path", str(report)]
        result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        findings = json.loads(report.read_text()) if report.exists() else None
        sanitized = [{"file": item.get("File", "").removeprefix(str(stage) + "/"),
            "rule": item.get("RuleID"), "start_line": item.get("StartLine"), "end_line": item.get("EndLine")}
            for item in (findings or [])]
    mutated = [row["path"] for row in rows if record(REPO / row["path"]) != row]
    passed = result.returncode == 0 and findings is not None and not sanitized and not mutated
    receipt = {"schema": 1, "status": "PASS" if passed else "FAIL", "scope": "NEW_AREA_V3_FINAL_FILES_ONLY",
        "scanner": {"name": "Gitleaks", "version": "8.24.3", "sha256": PINNED_SCANNER_SHA},
        "rules": "Pinned embedded defaults; empty ignore list; no custom allowlist; allow comments ignored",
        "redaction_percent": 100, "max_decode_depth": 3, "exit_code": result.returncode,
        "findings_count": len(sanitized), "findings": sanitized, "input_mutations": mutated,
        "input_files": rows, "self_receipt_excluded": "SECRET_SCAN.json", "required_temp_only_files": []}
    (ROOT / "evidence/SECRET_SCAN.json").write_bytes(encode(receipt))
    print(json.dumps({"status": receipt["status"], "secret_findings": len(sanitized), "text_files": len(rows)}))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--scan", metavar="PINNED_GITLEAKS")
    args = parser.parse_args()
    if args.scan:
        require(not args.write, "WRITE_AND_SCAN_ARE_SEPARATE_STEPS")
        return scan(args.scan)
    require(args.write, "EXPLICIT_WRITE_FLAG_REQUIRED")
    gate_file, manifest_file = ROOT / "evidence/PERMANENT_GATE.json", ROOT / "FINAL_MANIFEST.json"
    require(not gate_file.exists() and not manifest_file.exists(), "FINAL_OUTPUT_ALREADY_EXISTS")
    try:
        gate, manifest = build()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        failure = {"schema": 1, "baseline_name": BASELINE, "status": "FAIL", "passed": 0, "total": 7,
            "gates": {name: "NOT_ADMITTED" for name in H.GATE_NAMES},
            "decision": "AREA_V3_FINAL_BLOCKED", "error": str(error),
            "checked_at_utc": datetime.now(timezone.utc).isoformat()}
        gate_file.write_bytes(encode(failure))
        print(json.dumps(failure), file=sys.stderr)
        return 1
    gate_file.write_bytes(encode(gate))
    manifest["permanent_gate_receipt"] = record(gate_file)
    manifest_file.write_bytes(encode(manifest))
    print(json.dumps({"status": "PASS", "decision": "EVENT_FEATURE_BUNDLE_V3_AREA_FINAL",
        "gates": "7/7", "manifest": record(manifest_file), "permanent_gate": record(gate_file)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
