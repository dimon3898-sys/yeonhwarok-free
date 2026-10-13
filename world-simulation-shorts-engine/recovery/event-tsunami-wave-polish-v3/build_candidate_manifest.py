#!/usr/bin/env python3
"""Inventory Tsunami Wave visual polish using frozen canonical Git/LFS and AST helpers.

Only --write-manifests writes new Wave Candidate manifests. No render, synthetic
suite, data investigation or approval-only Permanent Gate is executed here.
"""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/event-tsunami-wave-polish-v3"
PARENT = ENGINE + "/recovery/event-area-propagation-v3"
FINAL = ENGINE + "/recovery/event-flow-v2-final/FINAL_MANIFEST.json"
FLOW_COMMIT = "fbc3be89d94040271c7f54a051162913ad134bac"
FLOW_PARENT = ENGINE + "/recovery/event-feature-bundle-v2-polish"
PARENT_COMMIT = "17557113f628a724aafca839a158899e7927210b"
FINAL_SHA = "43f83ff77895ef8f4749b328a49a3acd0bb6b13667198347bb606e187efbe1e3"
SCOPE_COMMIT = "05bdd90"
SCOPE = "EVENT_FEATURE_BUNDLE_V3_TSUNAMI_WAVE_VISUAL_POLISH"
BRANCH = "development/event-tsunami-wave-polish-v3-20261013"
NAMES = ("SOURCE", "FIXTURE", "DATA", "EVIDENCE", "RUNTIME_ASSET", "BUILD_INPUT", "DEPENDENCY", "IMPORT", "REPRODUCTION")
MP4 = "TOHOKU_2011_TSUNAMI_WAVE_VISUAL_POLISH.mp4"
CHECKPOINTS = ("01_EVENT_ARRIVAL.png", "02_ORIGIN.png", "03_FIRST_WAVE.png", "04_WAVE_TRAIN.png",
               "05_COAST_APPROACH.png", "06_SEQUENTIAL_IMPACT.png", "07_ENERGY_FADE.png", "08_FINAL_HOLD.png")
POSTSAVE = {BASE + "/evidence/" + name for name in
            ("SECRET_SCAN.json", "SECRET_SCAN_IMPLEMENTATION.json", "SECRET_SCAN_FIXTURE.json",
             "PERSISTENCE_VERIFICATION.json", "POST_COMMIT_VERIFICATION.json", "POST_SCAN_SOURCE_CHECK.json",
             "FINAL_PERSISTENCE.json", "SOURCE_AFTER_SECRET_SCAN.json", "HTTP_DOWNLOAD_VERIFY.json")}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.DEVNULL)


def discover(directory, pattern):
    return sorted(path.relative_to(REPO).as_posix() for path in (REPO / directory).glob(pattern) if path.is_file())


NEW_MODULES = discover(ENGINE + "/web/map_infographic_v1", "wave_*.mjs")
NEW_TESTS = discover(ENGINE + "/tests", "wave_*.test.mjs")


def frozen_helpers():
    relative = ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py"
    if (REPO / relative).read_bytes() != git("show", PARENT_COMMIT + ":" + relative):
        raise ValueError("FROZEN_AST_AND_RECORD_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("frozen_wave_inventory_helpers", REPO / relative)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.BASE, helper.V2, helper.NEW_MODULES, helper.NEW_TESTS = BASE, PARENT, NEW_MODULES, NEW_TESTS
    return helper


H = frozen_helpers()
record, encode = H.record, H.encode


def require(condition, reason):
    if not condition:
        raise ValueError("WAVE_POLISH_CANDIDATE_INVALID: " + reason)


def protection():
    original = set(git("ls-tree", "-r", "--name-only", PARENT_COMMIT).decode().splitlines())
    changed = sorted(original & set(git("diff", "--name-only", PARENT_COMMIT).decode().splitlines()))
    require(not changed, "PARENT_FINAL_SOURCE_CHANGED: " + ", ".join(changed))
    parent = H.protected_record(PARENT_COMMIT, FINAL)
    require(parent["sha256"] == FINAL_SHA, "PARENT_FINAL_MANIFEST_SHA_CHANGED")
    return {"baseline": "EVENT_FEATURE_BUNDLE_V3_AREA_CANDIDATE", "commit": PARENT_COMMIT,
            "frozen_final_baseline": "EVENT_FEATURE_BUNDLE_V2_FLOW_FINAL_BASELINE",
            "manifest": parent, "original_tracked_paths": len(original), "changed_original_paths": [],
            "event_v1_flow_v2_area_core_front_line_state_transition_time_step_camera_projection_layout_marker_visual_sources": "UNCHANGED",
            "approved_parent_timings_styles_geometry": "UNCHANGED"}


def source_guard():
    require(NEW_MODULES, "NEW_WAVE_VISUAL_SOURCE_MISSING")
    require(NEW_TESTS, "NEW_WAVE_FOCUSED_TEST_SOURCE_MISSING")
    H.common_source_guard()
    for relative in NEW_MODULES:
        text = H.HELPER.safe_file(relative).read_text()
        require(not re.search(r"\b(?:japan|tohoku|fukushima|sendai|indonesia|sumatra)\b", text, re.I),
                "FIXTURE_PLACE_NAME_IN_ENGINE_SOURCE: " + relative)
        require(not re.search(r"(?:file://|/tmp/|/workspace/)[^\s'\"`]*", text),
                "ABSOLUTE_OR_TEMPORARY_ENGINE_INPUT: " + relative)


def inactive_descriptors(fixtures):
    # Reuse the accepted classifier for explicitly inactive historical /tmp
    # descriptors. Active runtime inputs remain canonical repository paths.
    relative = FLOW_PARENT + "/build_candidate_manifest.py"
    require((REPO / relative).read_bytes() == git("show", FLOW_COMMIT + ":" + relative),
            "FROZEN_TEMP_DESCRIPTOR_CLASSIFIER_CHANGED")
    spec = importlib.util.spec_from_file_location("readonly_flow_candidate_classifier", REPO / relative)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.BASE, helper.H = BASE, H
    return helper.inactive_descriptors(fixtures)


def evidence(filename, key="status"):
    path = BASE + "/evidence/" + filename
    value = json.loads(H.HELPER.safe_file(path).read_text())
    require(value.get(key) == "PASS", "EVIDENCE_NOT_PASS: " + filename)
    return {"input": record(path), "result_key": key, "result": value[key]}, value


def focused_receipt():
    binding, value = evidence("WAVE_REGRESSION.json")
    require(value.get("areaCoreModified", False) is False, "AREA_CORE_CHANGED")
    require(value.get("permanentGateExecuted", False) is False, "APPROVAL_ONLY_GATE_EXECUTED")
    return binding


def proof_report(candidate):
    focused = focused_receipt()
    visual, _ = evidence("VISUAL_AUDIT.json")
    public = {Path(path).name: record(path) for path in candidate if path.startswith(BASE + "/public-review/")}
    require(set(public) == {MP4, *CHECKPOINTS, "SHA256SUMS"}, "PUBLIC_MEDIA_ALLOWLIST")
    path = BASE + "/evidence/proof/REPORT.json"
    report = json.loads(H.HELPER.safe_file(path).read_text())
    require(report.get("status") == "PASS" and report.get("state") == "EVENT_FEATURE_BUNDLE_V3_TSUNAMI_WAVE_POLISH_CANDIDATE", "PROOF_STATE")
    require(all(report.get(key) is False for key in ("userVideoApproved", "eventFinal", "permanentGateExecuted")), "PRE_APPROVAL_FINAL_GATE")
    require((report.get("width"), report.get("height"), report.get("fps"), report.get("audio")) == (1080, 1920, 30, False), "PROOF_FORMAT")
    count, duration = report.get("totalFrames"), report.get("durationSeconds")
    require(isinstance(count, int) and isinstance(duration, (int, float)) and 8 <= duration <= 10 and count == duration * 30, "PROOF_DURATION")
    source = report.get("sourceCommit")
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source), "ORIGINAL_RENDER_SOURCE_COMMIT")
    require(git("rev-parse", source + "^{commit}").decode().strip() == source, "RENDER_SOURCE_UNSAVED")
    require(git("merge-base", PARENT_COMMIT, source).decode().strip() == PARENT_COMMIT, "RENDER_SOURCE_PARENT")
    for directory in ("public-review", "evidence/proof"):
        require(not git("ls-tree", "-r", "--name-only", source, "--", BASE + "/" + directory).strip(),
                "ORIGINAL_RENDER_OUTPUTS_EXIST_AT_SOURCE_COMMIT")
    render_inputs = NEW_MODULES + [BASE + "/wave_runtime.mjs", BASE + "/render_proof.mjs"]
    render_inputs += [path for path in candidate if "/fixtures/" in path or "/data/" in path]
    render_inputs += [row["input"]["path"] for row in (focused,)]
    bindings = [H.protected_record(source, path) for path in sorted(set(render_inputs))]
    frames = report.get("frames", [])
    require(len(frames) == count, "COMPLETE_FRAME_INVENTORY")
    keys = ("protectedChangedPixels", "markerChangedPixels", "outsideRoiChangedPixels")
    for frame, row in enumerate(frames):
        require(row.get("frame") == frame and row.get("glError") == 0, "FRAME_ORDER_OR_GL_ERROR")
        pixel = row.get("protection", row.get("wave", {}).get("protection", row.get("area", {}).get("protection", {})))
        require(all(pixel.get(key) == 0 for key in keys), "FRAME_GRAPHIC_PROTECTION")
    require(all(report.get("protection", {}).get(key) == 0 for key in keys), "AGGREGATE_GRAPHIC_PROTECTION")
    require(report.get("decodeValidation") == "PASS", "PROOF_DECODE")
    streams = report.get("ffprobe", {}).get("streams", [])
    require(len(streams) == 1, "SILENT_SINGLE_VIDEO_STREAM")
    stream = streams[0]
    require((stream.get("codec_type"), stream.get("codec_name"), stream.get("width"), stream.get("height"), stream.get("avg_frame_rate"))
            == ("video", "h264", 1080, 1920, "30/1") and int(stream.get("nb_read_frames", -1)) == count
            and float(stream.get("duration", -1)) == duration, "PROBED_VIDEO_FORMAT")
    require(all(report.get("video", {}).get(key) == public[MP4][key] for key in ("sha256", "bytes")), "MP4_BODY")
    checkpoints = report.get("checkpoints", [])
    require(len(checkpoints) == 8 and {row.get("file") for row in checkpoints} == set(CHECKPOINTS), "CHECKPOINT_SET")
    for row in checkpoints:
        require(all(row.get(key) == public[row["file"]][key] for key in ("sha256", "bytes")), "CHECKPOINT_BODY")
        require(row.get("sourceMatchesEncodedNativeFrame") is True and frames[row["frame"]]["png_sha256"] == row["sha256"], "CHECKPOINT_ENCODE_INPUT")
    sums = "".join(public[name]["sha256"] + "  " + name + "\n" for name in sorted({MP4, *CHECKPOINTS}))
    require(H.HELPER.safe_file(BASE + "/public-review/SHA256SUMS").read_text() == sums, "PUBLIC_SHA256SUMS")
    return {"report": record(path), "mp4": public[MP4], "checkpoints": [public[name] for name in CHECKPOINTS],
            "public_checksums": public["SHA256SUMS"], "total_frames": count, "duration_seconds": duration,
            "prerequisites": [focused], "post_render_visual_audit": visual,
            "original_render_source_commit": source, "original_render_source_and_input_bindings": bindings,
            "original_render_outputs_absent_at_source_revision": True, "permanent_gate_executed": False}


def documents(stage, exclusions):
    protected = protection()
    source_guard()
    parent_rows, parents = [], {}
    for name in (*NAMES, "HASH"):
        relative = PARENT + "/manifests/" + name + "_MANIFEST.json"
        parent_rows.append(H.protected_record(PARENT_COMMIT, relative))
        parents[name] = json.loads(H.HELPER.safe_file(relative).read_text())
    inherited = [H.verify_record(row) for row in parents["HASH"]["required_files"]]
    inherited += [parent_rows[-1], H.protected_record(PARENT_COMMIT, PARENT + "/manifests/SHA256SUMS")]
    candidate = H.candidate_paths(exclusions)
    graph = H.import_graph(candidate)
    installed = H.HELPER.toolchain(parents["DEPENDENCY"])
    source = sorted(set(NEW_MODULES + NEW_TESTS + [path for path in candidate if Path(path).suffix in {".mjs", ".py", ".md", ".sh"}]))
    fixtures = [path for path in candidate if "/fixtures/" in path or Path(path).suffix == ".json" and "/evidence/" not in path]
    evidence_paths = sorted(set(candidate) - set(source) - set(fixtures))
    inactive = inactive_descriptors(fixtures)
    proof = proof_report(candidate) if stage == "candidate" else None
    common = {"schema": 1, "scope": SCOPE, "development_branch": BRANCH, "inventory_stage": stage,
              "candidate_state": "EVENT_FEATURE_BUNDLE_V3_TSUNAMI_WAVE_POLISH_CANDIDATE" if stage == "candidate" else "IMPLEMENTATION_CHECKPOINT",
              "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
              "parent_baseline": protected, "quality_grade": "FACT_BASED_VISUAL_GRADE", "scope_commit": SCOPE_COMMIT,
              "change_scope": "Wave visual extension, authored wave/coast fixture data and proof delivery only",
              "unchanged_area_war_generalization_receipt": H.protected_record(PARENT_COMMIT, PARENT + "/evidence/SYNTHETIC.json"),
              "event_final": False, "user_video_approved": False, "permanent_gate_executed": False,
              "required_temp_only_files": [], "postsave_report_exclusions": sorted(exclusions),
              "candidate_media_commit_binding": "GIT_COMMIT_CONTAINING_ORIGINAL_PUBLIC_MEDIA_AND_THIS_MANIFEST"}
    def make(**fields):
        return {**common, **fields}
    parent_by_name = {Path(row["path"]).name.removesuffix("_MANIFEST.json"): row for row in parent_rows}
    routes = {row["url"]: dict(row) for row in parents["RUNTIME_ASSET"]["runtime_routes"]}
    for path in graph["browser_runtime_modules"]:
        if "/web/map_infographic_v1/" in path:
            routes["/modules/" + Path(path).name] = {"url": "/modules/" + Path(path).name, "file": path}
    for url, filename in (("/inputs/regional.json", "REGIONAL-plan.json"), ("/inputs/continent.json", "CONTINENT-plan.json"), ("/inputs/scene.json", "scene.json")):
        relative = BASE + "/fixtures/" + filename
        if (REPO / relative).is_file():
            routes[url] = {"url": url, "file": relative}
    explicit_routes = REPO / BASE / "fixtures/RUNTIME_ROUTES.json"
    if explicit_routes.is_file():
        value = json.loads(explicit_routes.read_text())
        declared = value.get("runtime_routes") if isinstance(value, dict) else value
        require(isinstance(declared, list), "EXPLICIT_RUNTIME_ROUTES_NOT_LIST")
        for route in declared:
            require(isinstance(route, dict) and isinstance(route.get("url"), str)
                    and route["url"].startswith("/") and not route["url"].startswith("//"), "INVALID_RUNTIME_ROUTE_URL")
            H.HELPER.safe_file(route["file"])
            routes[route["url"]] = {"url": route["url"], "file": route["file"]}
    dependencies = parents["DEPENDENCY"]
    numpy_dependency = next(row for row in dependencies["dependencies"] if row["name"] == "numpy")
    audit_dependencies = [{**numpy_dependency, "use": "FOCUSED_POST_ENCODE_VISUAL_AUDIT_ONLY",
                           "consumer": BASE + "/verify_visual_proof.py",
                           "execution_python": "/usr/bin/python3", "python_version": installed["interpreters"]["python"],
                           "observed_version": importlib.metadata.version("numpy"),
                           "verification_source": H.protected_record(PARENT_COMMIT, numpy_dependency["lock_path"])}]
    require(audit_dependencies[0]["observed_version"] == numpy_dependency["version"], "AUDIT_NUMPY_PARENT_PIN_CHANGED")
    data = sorted(path for path in candidate if "/data/" in path)
    docs = {
        "SOURCE_MANIFEST.json": make(parent=parent_by_name["SOURCE"], entries=[record(path) for path in graph["reachable_modules"]],
                                      candidate_source_and_procedures=[record(path) for path in source],
                                      new_engine_modules=[record(path) for path in NEW_MODULES], focused_tests=[record(path) for path in NEW_TESTS]),
        "FIXTURE_MANIFEST.json": make(parent=parent_by_name["FIXTURE"], entries=[record(path) for path in fixtures],
                                       mandatory_runtime_paths_are_repository_relative=True, inactive_historical_descriptors=inactive),
        "DATA_MANIFEST.json": make(parent=parent_by_name["DATA"], new_visual_fixture_and_derivatives=[record(path) for path in data],
                                    original_parent_data_unchanged=True, production_grade="FACT_BASED_VISUAL_GRADE",
                                    semantic_policy="Visual-only wave fronts and coast contact timing; immutable parent historical origin/coast relation retained, no precise physics or numeric claims."),
        "RUNTIME_ASSET_MANIFEST.json": make(parent=parent_by_name["RUNTIME_ASSET"], runtime_routes=sorted(routes.values(), key=lambda row: row["url"]),
                                             new_runtime_modules=[record(path) for path in NEW_MODULES],
                                             new_data_asset_bodies=[record(path) for path in data],
                                             existing_parent_asset_bodies_verified=True, existing_renderer_projection_visual_source_modified=False),
        "BUILD_INPUT_MANIFEST.json": make(parent=parent_by_name["BUILD_INPUT"], inherited_inputs_and_recipe=parents["BUILD_INPUT"]["inherited_inputs_and_recipe"],
                                           dependency_locks=dependencies["dependency_locks"], new_fixture_and_asset_build_procedures=[record(path) for path in source
                                           if path.startswith(BASE + "/") and Path(path).name.startswith(("build_", "prepare_"))]),
        "EVIDENCE_MANIFEST.json": make(entries=[record(path) for path in evidence_paths], proof=proof,
                                        public_review_allowed_bodies=["MP4", "PNG", "SHA256SUMS"],
                                        delivery_receipt_policy={"path": BASE + "/evidence/HTTP_DOWNLOAD_VERIFY.json", "runtime_required": False,
                                        "binding": "Later receipt names immutable original media commit and actual HTTP 200 body hashes; its exact body is bound by containing Git commit."}),
        "DEPENDENCY_MANIFEST.json": make(parent=parent_by_name["DEPENDENCY"], dependencies=dependencies["dependencies"],
                                           interpreters=dependencies["interpreters"], setup=dependencies["setup"],
                                           dependency_locks=dependencies["dependency_locks"], parser_provider=dependencies["parser_provider"],
                                           observed_toolchain=installed, additional_runtime_dependencies=[], focused_audit_dependencies=audit_dependencies),
        "IMPORT_MANIFEST.json": make(**graph),
        "REPRODUCTION_MANIFEST.json": make(setup_recipe=dependencies["setup"], interpreters=dependencies["interpreters"],
                                             entrypoints=[record(path) for path in source if Path(path).suffix in {".mjs", ".py"}],
                                             inherited_required_file_count=len(inherited), inherited_manifests=parent_rows,
                                             focused_test_argv=["node", "--test", *NEW_TESTS],
                                             proof_argv=["node", BASE + "/render_proof.mjs"],
                                             candidate_manifest_argv=["/usr/bin/python3", "-B", BASE + "/build_candidate_manifest.py", "--stage", stage],
                                             original_render_source_commit=None if proof is None else proof["original_render_source_commit"],
                                             primary_remote_checkout={"url": "https://github.com/dimon3898-sys/yeonhwarok-free.git", "branch": BRANCH,
                                                 "revision": "PENDING_ORIGINAL_RENDER_SOURCE_COMMIT" if proof is None else proof["original_render_source_commit"],
                                                 "policy": "Pin original pre-render source revision; public-review and evidence/proof absent there. Use retained remote Git/LFS originals and fresh pinned dependencies."},
                                             clean_environment_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL", proof=proof),
    }
    return docs, inherited, [protected["manifest"], *parent_rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("implementation", "fixture", "candidate"), default="implementation")
    parser.add_argument("--write-manifests", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--require-persisted", action="store_true")
    parser.add_argument("--exclude-postsave", action="append", default=[])
    args = parser.parse_args()
    if args.inspect_only and (args.write_manifests or args.require_persisted):
        parser.error("--inspect-only excludes writes and persistence checks")
    exclusions = set(POSTSAVE)
    for path in args.exclude_postsave:
        if not path.startswith(BASE + "/evidence/") or Path(path).suffix != ".json" or ".." in Path(path).parts:
            parser.error("Only Candidate/evidence JSON post-save receipts may be excluded")
        exclusions.add(path)
    docs, inherited, parents = documents(args.stage, exclusions)
    rows = H.inventory_of(docs, inherited, parents)
    encoded = {name: encode(doc) for name, doc in docs.items()}
    for name, body in encoded.items():
        path = BASE + "/manifests/" + name
        rows[path] = {"path": path, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    inventory = sorted(rows.values(), key=lambda row: row["path"])
    encoded["HASH_MANIFEST.json"] = encode({"schema": 1, "scope": SCOPE, "inventory_stage": args.stage,
                                            "required_files": inventory, "required_temp_only_files": [],
                                            "event_final": False, "user_video_approved": False, "permanent_gate_executed": False,
                                            "postsave_report_exclusions": sorted(exclusions),
                                            "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are excluded from recursive hashes; HEAD/index bind exact bytes."})
    encoded["SHA256SUMS"] = "".join(row["sha256"] + "  " + row["path"] + "\n" for row in inventory).encode()
    target = REPO / BASE / "manifests"
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, body in encoded.items():
            (target / name).write_bytes(body)
    if not args.inspect_only:
        for name, body in encoded.items():
            require((target / name).read_bytes() == body, "MANIFEST_STALE_OR_CHANGED: " + name)
    paths = sorted(set(rows) | {BASE + "/manifests/" + name for name in encoded})
    if args.require_persisted:
        for path in paths:
            H.verify_persisted(path)
    print(json.dumps({"scope": SCOPE, "inventory_status": "PASS", "inventory_stage": args.stage,
                      "required_files": len(paths), "inherited_required_files": len(inherited),
                      "new_engine_modules": len(NEW_MODULES), "focused_tests": len(NEW_TESTS),
                      "reachable_import_modules": len(docs["IMPORT_MANIFEST.json"]["reachable_modules"]),
                      "import_edges": len(docs["IMPORT_MANIFEST.json"]["edges"]), "required_temp_only_files": 0,
                      "head_and_index_compared": args.require_persisted, "permanent_gate_executed": False,
                      "user_video_approved": False, "event_final": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
