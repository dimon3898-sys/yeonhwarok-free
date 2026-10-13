#!/usr/bin/env python3
"""Inventory Planner Scene JSON V1 without executing its approval-only Final Gate.

Read frozen Git/LFS records and the existing pinned Babel import parser. Only
--write-manifests writes new Candidate inventory documents. Rendering, research,
Final promotion and historical test suite execution are not performed here.
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
BASE = ENGINE + "/recovery/planner-scene-json-v1"
PARENT = ENGINE + "/recovery/event-tsunami-wave-polish-v3"
FINAL_ROOT = ENGINE + "/recovery/event-area-v3-final"
PARENT_COMMIT = "7da699c07cddf618f5e8a93ca735db51d31bbb39"
FINAL_SHA = "672aa536a65c5f36d5e3f2b96a70c548897872093b9d602772fe75d96d14bc45"
BRANCH = "development/event-area-v3-final-planner-v1-20261013"
SCOPE = "PLANNER_SCENE_JSON_V1"
MP4 = "KOREAN_WAR_PLANNER_SCENE_JSON_V1_CANDIDATE.mp4"
SCENE_JSON = "SCENE_PLAN.json"
CHECKPOINTS = ("01_GEOGRAPHIC_CONTEXT.png", "02_INITIAL_FRONT.png", "03_PUSAN_PERIMETER.png",
               "04_NORTH_ADVANCE.png", "05_SEOUL_WITHDRAWAL.png", "06_ARMISTICE.png",
               "07_FRONT_COMPLETE.png", "08_FINAL_HOLD.png")
NAMES = ("SOURCE", "FIXTURE", "DATA", "EVIDENCE", "RUNTIME_ASSET", "BUILD_INPUT", "DEPENDENCY", "IMPORT", "REPRODUCTION")
POSTSAVE = {BASE + "/evidence/" + name for name in
            ("SECRET_SCAN.json", "SECRET_SCAN_IMPLEMENTATION.json", "SECRET_SCAN_FIXTURE.json",
             "PERSISTENCE_VERIFICATION.json", "POST_COMMIT_VERIFICATION.json", "POST_SCAN_SOURCE_CHECK.json",
             "FINAL_PERSISTENCE.json", "SOURCE_AFTER_SECRET_SCAN.json", "HTTP_DOWNLOAD_VERIFY.json")}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.DEVNULL)


def discover(directory, pattern):
    return sorted(path.relative_to(REPO).as_posix() for path in (REPO / directory).glob(pattern) if path.is_file())


NEW_MODULES = discover(ENGINE + "/web/map_infographic_v1", "planner_*.mjs")
NEW_TESTS = discover(ENGINE + "/tests", "planner_*.test.mjs")
NEW_SCHEMAS = discover(ENGINE + "/web/map_infographic_v1", "planner_*.schema.json")


def frozen_helpers():
    relative = ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py"
    if (REPO / relative).read_bytes() != git("show", PARENT_COMMIT + ":" + relative):
        raise ValueError("FROZEN_CANONICAL_AST_AND_RECORD_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("readonly_planner_inventory_helpers", REPO / relative)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # Only configure the imported helper in memory. No frozen source is edited.
    helper.BASE, helper.V2, helper.NEW_MODULES, helper.NEW_TESTS = BASE, PARENT, NEW_MODULES, NEW_TESTS
    return helper


H = frozen_helpers()
record, encode = H.record, H.encode


def require(condition, reason):
    if not condition:
        raise ValueError("PLANNER_CANDIDATE_INVALID: " + reason)


def protection():
    original = set(git("ls-tree", "-r", "--name-only", PARENT_COMMIT).decode().splitlines())
    changed = sorted(original & set(git("diff", "--name-only", PARENT_COMMIT).decode().splitlines()))
    require(not changed, "EXISTING_FINAL_TRACKED_PATH_CHANGED: " + ", ".join(changed))
    final = H.protected_record(PARENT_COMMIT, FINAL_ROOT + "/FINAL_MANIFEST.json")
    require(final["sha256"] == FINAL_SHA, "PARENT_FINAL_MANIFEST_SHA_CHANGED")
    value = json.loads(H.HELPER.safe_file(final["path"]).read_text())
    require(value.get("baseline_name") == "EVENT_FEATURE_BUNDLE_V3_AREA_FINAL_BASELINE"
            and value.get("user_video_review") == "PASS" and value.get("gate_result", {}).get("passed") == 7
            and value.get("gate_result", {}).get("total") == 7
            and value.get("clean_reproduction", {}).get("result") == "BIT_EXACT", "PART_A_FINAL_NOT_PASS")
    return {"baseline": value["baseline_name"], "commit": PARENT_COMMIT, "manifest": final,
            "original_tracked_paths": len(original), "changed_original_paths": [],
            "area_flow_event_v1_camera_v5_projection_geometry_layout_marker_visual_source": "UNCHANGED",
            "approved_final_style_timing_geometry": "UNCHANGED", "part_a_permanent_gate": "7/7_PASS",
            "part_a_clean_reproduction": "BIT_EXACT"}


def source_guard():
    require(NEW_MODULES and NEW_TESTS and NEW_SCHEMAS, "PLANNER_SOURCE_TEST_OR_SCHEMA_MISSING")
    for relative in NEW_MODULES:
        body = H.HELPER.safe_file(relative).read_text()
        require(not re.search(r"\b(?:suez|egypt|korea|korean|japan|tohoku|fukushima|sendai|busan|incheon|seoul)\b|193\s*\.\s*30", body, re.I),
                "FIXTURE_TOPIC_OR_PLACE_HARDCODE_IN_COMMON_ENGINE: " + relative)
        require(not re.search(r"(?:file://|/tmp/|/workspace/)[^\s'\"`]*", body), "ABSOLUTE_OR_TEMPORARY_ENGINE_INPUT: " + relative)
        require(not re.search(r"\b(?:WebGLRenderingContext|WebGL2RenderingContext|glCreateShader|minimumContextCamera)\b", body),
                "CAMERA_OR_RENDERER_IMPLEMENTATION_DUPLICATION: " + relative)


def evidence(filename):
    path = BASE + "/evidence/" + filename
    value = json.loads(H.HELPER.safe_file(path).read_text())
    require(value.get("status") == "PASS", "EVIDENCE_NOT_PASS: " + filename)
    require(value.get("permanentGateExecuted", False) is False, "PLANNER_FINAL_GATE_EXECUTED_BEFORE_USER_APPROVAL")
    return {"input": record(path), "result": "PASS"}, value


def scene_document(path):
    source = H.HELPER.safe_file(path)
    value = json.loads(source.read_text())
    require(value.get("metadata", {}).get("schema") == "PLANNER_SCENE_JSON_V1", "SCENE_JSON_SCHEMA_ID")
    require(importlib.metadata.version("jsonschema") == "4.19.2", "PINNED_SCHEMA_AUDIT_DEPENDENCY_CHANGED")
    from jsonschema import Draft202012Validator
    schema_path = ENGINE + "/web/map_infographic_v1/planner_scene_v1.schema.json"
    schema = json.loads(H.HELPER.safe_file(schema_path).read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    module = "./" + ENGINE + "/web/map_infographic_v1/planner_scene_v1.mjs"
    program = "import {validateScenePlan} from " + json.dumps(module) + ";import fs from 'node:fs'; const scene=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const result=validateScenePlan(scene);if(result===false||result?.valid===false||result?.status==='FAIL')throw new Error('SCENE_SCHEMA_INVALID');"
    subprocess.check_call(["node", "--input-type=module", "-e", program, str(source)], cwd=REPO)
    forbidden_keys = {"password", "passwd", "secret", "token", "api_key", "apikey", "credential", "private_key",
                      "runtime_routes", "runtimefiles", "nativefiles", "diagnostics", "internal_plan", "source_code", "repository_path"}
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                require(str(key).lower() not in forbidden_keys, "PUBLIC_SCENE_INTERNAL_OR_CREDENTIAL_KEY: " + str(key))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            require(not re.search(r"(?:file://|/workspace/|/tmp/|world-simulation-shorts-engine/|recovery/|node_modules/|web/map_infographic_v1/)", item),
                    "PUBLIC_SCENE_RUNTIME_OR_INTERNAL_FILE_PATH")
    visit(value)
    return {"input": record(path), "schema": "PLANNER_SCENE_JSON_V1", "published_json_schema": record(schema_path),
            "schema_validation": "PASS", "schema_validator": {"name": "jsonschema", "version": "4.19.2", "draft": "2020-12"},
            "canonical_public_export_safety": "PASS", "runtime_or_internal_file_paths": 0}, value


def candidate_paths(exclusions):
    paths = []
    for path in (REPO / BASE).rglob("*"):
        parts = path.relative_to(REPO / BASE).parts
        if "manifests" in parts or "__pycache__" in parts or not path.is_file():
            continue
        relative = path.relative_to(REPO).as_posix()
        H.HELPER.safe_file(relative)
        if relative in exclusions:
            continue
        if "public-review" in parts:
            require(path.name in {MP4, *CHECKPOINTS, SCENE_JSON, "SHA256SUMS"}, "PUBLIC_REVIEW_ALLOWLIST: " + relative)
        paths.append(relative)
    return sorted(paths)


def runtime_routes(parent, graph):
    routes = {row["url"]: dict(row) for row in parent["runtime_routes"]}
    for path in graph["browser_runtime_modules"]:
        if "/web/map_infographic_v1/" in path:
            routes["/modules/" + Path(path).name] = {"url": "/modules/" + Path(path).name, "file": path}
    explicit = REPO / BASE / "fixtures/RUNTIME_ROUTES.json"
    if explicit.is_file():
        value = json.loads(explicit.read_text())
        declared = value.get("runtime_routes") if isinstance(value, dict) else value
        require(isinstance(declared, list), "EXPLICIT_RUNTIME_ROUTES_NOT_LIST")
        for row in declared:
            require(isinstance(row, dict) and isinstance(row.get("url"), str)
                    and row["url"].startswith("/") and not row["url"].startswith("//"), "INVALID_RUNTIME_ROUTE_URL")
            H.HELPER.safe_file(row["file"])
            routes[row["url"]] = {"url": row["url"], "file": row["file"]}
    # Bind the exact input override URLs consumed by the existing V5 server.
    runtime = REPO / BASE / "fixtures/RUNTIME_FIXTURE.json"
    if runtime.is_file():
        value = json.loads(runtime.read_text())
        inputs = value.get("nativeFiles")
        require(isinstance(inputs, dict), "NATIVE_RUNTIME_INPUTS_MISSING")
        mapping = {"regionalPlan": "/inputs/regional.json", "continentPlan": "/inputs/continent.json",
                   "scene": "/inputs/scene.json", "cameraPlan": "/inputs/camera-plan.json",
                   "inputManifest": "/inputs/input-manifest.json"}
        require(set(inputs) == set(mapping), "NATIVE_RUNTIME_INPUT_CONTRACT")
        for key, url in mapping.items():
            relative = inputs[key]
            require(isinstance(relative, str) and not Path(relative).is_absolute()
                    and not re.search(r"(?:file:|https?:|\\|\btmp/)", relative)
                    and ".." not in Path(relative).parts, "REQUIRED_TEMP_OR_EXTERNAL_NATIVE_INPUT")
            relative = ENGINE + "/" + relative
            H.HELPER.safe_file(relative)
            routes[url] = {"url": url, "file": relative}
        scene_path = value.get("scenePlanPath")
        require(scene_path == "recovery/planner-scene-json-v1/fixtures/" + SCENE_JSON,
                "SCENE_RUNTIME_INPUT_NOT_CANONICAL_REPOSITORY_PATH")
        H.HELPER.safe_file(ENGINE + "/" + scene_path)
    return sorted(routes.values(), key=lambda row: row["url"])


def proof_report(candidate, synthetic, integration, scene):
    visual, _ = evidence("VISUAL_AUDIT.json")
    public = {Path(path).name: record(path) for path in candidate if path.startswith(BASE + "/public-review/")}
    require(set(public) == {MP4, *CHECKPOINTS, SCENE_JSON, "SHA256SUMS"}, "PUBLIC_REVIEW_EXACT_BODY_SET")
    public_scene, _ = scene_document(BASE + "/public-review/" + SCENE_JSON)
    require(public_scene["input"]["sha256"] == scene["input"]["sha256"], "PUBLIC_SCENE_DIFFERS_FROM_EXECUTED_SCENE")
    path = BASE + "/evidence/proof/REPORT.json"
    report = json.loads(H.HELPER.safe_file(path).read_text())
    require(report.get("status") == "PASS" and report.get("state") == "PLANNER_SCENE_JSON_V1_CANDIDATE", "PROOF_STATE")
    require(all(report.get(key) is False for key in ("userVideoApproved", "eventFinal", "permanentGateExecuted")), "PRE_APPROVAL_FINAL_GATE")
    require((report.get("width"), report.get("height"), report.get("fps"), report.get("audio")) == (1080, 1920, 30, False), "PROOF_FORMAT")
    count, duration = report.get("totalFrames"), report.get("durationSeconds")
    require(isinstance(count, int) and isinstance(duration, (int, float)) and 10 <= duration <= 15 and count == duration * 30, "PROOF_DURATION")
    source = report.get("sourceCommit")
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source), "ORIGINAL_RENDER_SOURCE_COMMIT")
    require(git("rev-parse", source + "^{commit}").decode().strip() == source
            and git("merge-base", PARENT_COMMIT, source).decode().strip() == PARENT_COMMIT, "RENDER_SOURCE_UNSAVED_OR_WRONG_PARENT")
    for directory in ("public-review", "evidence/proof"):
        require(not git("ls-tree", "-r", "--name-only", source, "--", BASE + "/" + directory).strip(), "RENDER_OUTPUTS_EXIST_AT_SOURCE_COMMIT")
    inputs = NEW_MODULES + NEW_SCHEMAS + [path for path in candidate if "/fixtures/" in path or "/data/" in path]
    inputs += [path for path in candidate if Path(path).name in {"planner_runtime.mjs", "render_proof.mjs"}]
    inputs += [row["input"]["path"] for row in (synthetic, integration)]
    bindings = [H.protected_record(source, path) for path in sorted(set(inputs))]
    frames = report.get("frames", [])
    require(len(frames) == count, "COMPLETE_FRAME_INVENTORY")
    keys = ("protectedChangedPixels", "markerChangedPixels", "outsideRoiChangedPixels")
    for frame, row in enumerate(frames):
        require(row.get("frame") == frame and row.get("glError") == 0, "FRAME_ORDER_OR_GL_ERROR")
        pixel = row.get("protection", row.get("planner", {}).get("protection", row.get("area", {}).get("protection", {})))
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
    points = report.get("checkpoints", [])
    require(len(points) == len(CHECKPOINTS) and {row.get("file") for row in points} == set(CHECKPOINTS), "CHECKPOINT_SET")
    for row in points:
        require(all(row.get(key) == public[row["file"]][key] for key in ("sha256", "bytes")), "CHECKPOINT_BODY")
        require(row.get("sourceMatchesEncodedNativeFrame") is True and frames[row["frame"]]["png_sha256"] == row["sha256"], "CHECKPOINT_ENCODE_INPUT")
    sums = "".join(public[name]["sha256"] + "  " + name + "\n" for name in sorted({MP4, *CHECKPOINTS, SCENE_JSON}))
    require(H.HELPER.safe_file(BASE + "/public-review/SHA256SUMS").read_text() == sums, "PUBLIC_SHA256SUMS")
    return {"report": record(path), "mp4": public[MP4], "scene_json": public_scene,
            "checkpoints": [public[name] for name in CHECKPOINTS], "public_checksums": public["SHA256SUMS"],
            "total_frames": count, "duration_seconds": duration, "prerequisites": [synthetic, integration],
            "post_render_visual_audit": visual, "original_render_source_commit": source,
            "original_render_source_and_input_bindings": bindings, "original_outputs_absent_at_source_revision": True,
            "permanent_gate_executed": False}


def documents(stage, exclusions):
    protected = protection()
    source_guard()
    parents, parent_rows = {}, []
    for name in (*NAMES, "HASH"):
        relative = PARENT + "/manifests/" + name + "_MANIFEST.json"
        parent_rows.append(H.protected_record(PARENT_COMMIT, relative))
        parents[name] = json.loads(H.HELPER.safe_file(relative).read_text())
    inherited = [H.verify_record(row) for row in parents["HASH"]["required_files"]]
    inherited += [parent_rows[-1], H.protected_record(PARENT_COMMIT, PARENT + "/manifests/SHA256SUMS")]
    final_paths = git("ls-tree", "-r", "--name-only", PARENT_COMMIT, "--", FINAL_ROOT).decode().splitlines()
    final_rows = [H.protected_record(PARENT_COMMIT, path) for path in final_paths]
    candidate = candidate_paths(exclusions)
    graph = H.import_graph(candidate)
    installed = H.HELPER.toolchain(parents["DEPENDENCY"])
    synthetic, _ = evidence("SYNTHETIC.json")
    integration = scene = None
    if stage != "implementation":
        integration, _ = evidence("INTEGRATION.json")
        scene, _ = scene_document(BASE + "/fixtures/" + SCENE_JSON)
    source = sorted(set(NEW_MODULES + NEW_TESTS + NEW_SCHEMAS + [path for path in candidate if Path(path).suffix in {".mjs", ".py", ".md", ".sh"}]))
    fixtures = [path for path in candidate if "/fixtures/" in path or Path(path).suffix == ".json" and "/evidence/" not in path]
    evidence_paths = sorted(set(candidate) - set(source) - set(fixtures))
    proof = proof_report(candidate, synthetic, integration, scene) if stage == "candidate" else None
    common = {"schema": 1, "scope": SCOPE, "development_branch": BRANCH, "inventory_stage": stage,
              "candidate_state": "PLANNER_SCENE_JSON_V1_CANDIDATE" if stage == "candidate" else "IMPLEMENTATION_CHECKPOINT",
              "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
              "parent_baseline": protected, "quality_grade": "FACT_BASED_VISUAL_GRADE",
              "change_scope": "Topic/Beat/Feature/Timing planning and declarative existing engine intent adapter only",
              "event_final": False, "planner_final": False, "user_video_approved": False, "permanent_gate_executed": False,
              "required_temp_only_files": [], "postsave_report_exclusions": sorted(exclusions),
              "candidate_media_commit_binding": "GIT_COMMIT_CONTAINING_ORIGINAL_PUBLIC_MEDIA_AND_THIS_MANIFEST"}
    def make(**fields):
        return {**common, **fields}
    parent_by_name = {Path(row["path"]).name.removesuffix("_MANIFEST.json"): row for row in parent_rows}
    dependencies = parents["DEPENDENCY"]
    validation_lock = BASE + "/planner-validation-requirements.lock"
    validation_dependencies = []
    for name, version in (("jsonschema", "4.19.2"), ("attrs", "25.3.0"),
                          ("jsonschema-specifications", "2023.12.1"), ("referencing", "0.36.2"), ("rpds-py", "0.21.0")):
        observed = importlib.metadata.version(name)
        require(observed == version, "SCHEMA_AUDIT_TEST_DEPENDENCY_PIN_CHANGED: " + name)
        validation_dependencies.append({"name": name, "version": version, "ecosystem": "python",
            "execution_python": "/usr/bin/python3", "use": "PLANNER_SCHEMA_AUDIT_AND_TEST_ONLY",
            "observed_version": observed, "lock": record(validation_lock), "new_runtime_dependency": False})
    data = sorted(path for path in candidate if "/data/" in path)
    routes = runtime_routes(parents["RUNTIME_ASSET"], graph)
    docs = {
        "SOURCE_MANIFEST.json": make(parent=parent_by_name["SOURCE"], entries=[record(path) for path in graph["reachable_modules"]],
                                      candidate_source_and_procedures=[record(path) for path in source],
                                      new_engine_modules=[record(path) for path in NEW_MODULES], scene_schemas=[record(path) for path in NEW_SCHEMAS],
                                      focused_tests=[record(path) for path in NEW_TESTS]),
        "FIXTURE_MANIFEST.json": make(parent=parent_by_name["FIXTURE"], entries=[record(path) for path in fixtures], scene_json=scene,
                                       mandatory_runtime_paths_are_repository_relative=True),
        "DATA_MANIFEST.json": make(parent=parent_by_name["DATA"], new_fixture_fact_geometry_and_sources=[record(path) for path in data],
                                    original_final_data_unchanged=True, semantic_policy="Historical fixture facts remain traceable; approximate fronts and areas are illustrative, not tactical simulation."),
        "RUNTIME_ASSET_MANIFEST.json": make(parent=parent_by_name["RUNTIME_ASSET"], runtime_routes=routes,
                                             new_runtime_modules=[record(path) for path in NEW_MODULES], new_data_asset_bodies=[record(path) for path in data],
                                             existing_final_asset_bodies_verified=True, camera_renderer_visual_source_modified=False),
        "BUILD_INPUT_MANIFEST.json": make(parent=parent_by_name["BUILD_INPUT"], inherited_inputs_and_recipe=parents["BUILD_INPUT"]["inherited_inputs_and_recipe"],
                                           dependency_locks=dependencies["dependency_locks"], new_fixture_and_asset_build_procedures=[record(path) for path in source
                                           if path.startswith(BASE + "/") and Path(path).name.startswith(("build_", "prepare_"))]),
        "EVIDENCE_MANIFEST.json": make(entries=[record(path) for path in evidence_paths], proof=proof, synthetic=synthetic, integration=integration,
                                        inherited_final_documents=final_rows, public_review_allowed_bodies=["MP4", "PNG", "Scene JSON", "SHA256SUMS"],
                                        delivery_receipt_policy={"path": BASE + "/evidence/HTTP_DOWNLOAD_VERIFY.json", "runtime_required": False,
                                            "binding": "Later receipt names immutable original media commit and actual HTTP 200 downloaded body hashes."}),
        "DEPENDENCY_MANIFEST.json": make(parent=parent_by_name["DEPENDENCY"], dependencies=dependencies["dependencies"],
                                           interpreters=dependencies["interpreters"], setup=dependencies["setup"], dependency_locks=dependencies["dependency_locks"],
                                           parser_provider=dependencies["parser_provider"], observed_toolchain=installed, additional_runtime_dependencies=[],
                                           additional_audit_test_dependencies=validation_dependencies),
        "IMPORT_MANIFEST.json": make(**graph),
        "REPRODUCTION_MANIFEST.json": make(setup_recipe=dependencies["setup"], interpreters=dependencies["interpreters"],
                                             entrypoints=[record(path) for path in source if Path(path).suffix in {".mjs", ".py"}],
                                             inherited_required_file_count=len(inherited), inherited_manifests=parent_rows, inherited_final_documents=final_rows,
                                             focused_test_argv=["node", "--test", *NEW_TESTS], proof_argv=["node", BASE + "/render_proof.mjs"],
                                             candidate_manifest_argv=["/usr/bin/python3", "-B", BASE + "/build_candidate_manifest.py", "--stage", stage],
                                             original_render_source_commit=None if proof is None else proof["original_render_source_commit"],
                                             primary_remote_checkout={"url": "https://github.com/dimon3898-sys/yeonhwarok-free.git", "branch": BRANCH,
                                                 "revision": "PENDING_ORIGINAL_RENDER_SOURCE_COMMIT" if proof is None else proof["original_render_source_commit"],
                                                 "policy": "Pin saved pre-render source revision; original public media and proof reports are absent there."},
                                             clean_environment_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL", proof=proof),
    }
    return docs, inherited, [protected["manifest"], *parent_rows, *final_rows]


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
                                            "event_final": False, "planner_final": False, "user_video_approved": False, "permanent_gate_executed": False,
                                            "postsave_report_exclusions": sorted(exclusions),
                                            "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are excluded from recursive hashes; exact bytes are bound by HEAD/index."})
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
                      "required_files": len(paths), "inherited_required_files": len(inherited), "new_engine_modules": len(NEW_MODULES),
                      "scene_schemas": len(NEW_SCHEMAS), "focused_tests": len(NEW_TESTS),
                      "reachable_import_modules": len(docs["IMPORT_MANIFEST.json"]["reachable_modules"]),
                      "import_edges": len(docs["IMPORT_MANIFEST.json"]["edges"]), "required_temp_only_files": 0,
                      "head_and_index_compared": args.require_persisted, "permanent_gate_executed": False,
                      "user_video_approved": False, "event_final": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
