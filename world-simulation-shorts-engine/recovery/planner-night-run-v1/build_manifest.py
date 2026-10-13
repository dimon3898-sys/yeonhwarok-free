#!/usr/bin/env python3
"""Inventory retained Night inputs; never render or run a Permanent/FINAL gate."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/planner-night-run-v1"
OLD = ENGINE + "/recovery/planner-scene-json-v1"
SOURCE_PARENT = "8bf6fa536a4dafba1ae803a421781ee953397be2"
AREA_FINAL = "7da699c07cddf618f5e8a93ca735db51d31bbb39"
BRANCH = "development/planner-night-causal-visual-20261013"
MP4 = "KOREAN_WAR_PLANNER_SCENE_JSON_V1_CAUSAL_VISUAL_14S.mp4"
SCENE_JSON = "SCENE_PLAN.json"
ORIGINAL_MP4_SHA = "d8a2fbcca285b8e87f5782cbc6e94c7c0d84a110f16aa5a06eb2b879157b45d0"
OPTIONAL_OVERRIDES = {ENGINE + "/web/map_infographic_v1/" + name for name in
                      ("planner_scene_v1.mjs", "planner_scene_v1.schema.json")}
NAMES = ("SOURCE", "FIXTURE", "DATA", "EVIDENCE", "RUNTIME_ASSET", "BUILD_INPUT", "DEPENDENCY", "IMPORT", "REPRODUCTION")
POSTSAVE = {BASE + "/CHECKPOINT_STATUS.json"} | {BASE + "/evidence/" + name for name in
    ("HTTP_DOWNLOAD_VERIFY.json", "SECRET_SCAN.json", "SECRET_SCAN_IMPLEMENTATION.json",
     "SECRET_SCAN_FIXTURE.json", "SECRET_SCAN_CANDIDATE.json", "PERSISTENCE_VERIFICATION.json",
     "POST_COMMIT_VERIFICATION.json", "POST_SCAN_SOURCE_CHECK.json", "SOURCE_AFTER_SECRET_SCAN.json",
     "FINAL_PERSISTENCE.json", "REMOTE_VERIFICATION.json")}


def require(condition, reason):
    if not condition:
        raise ValueError("NIGHT_PROOF: " + reason)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.PIPE)


def frozen_helpers():
    relative = ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py"
    require((REPO / relative).read_bytes() == git("show", AREA_FINAL + ":" + relative),
            "PINNED_HASH_AST_IMPORT_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("readonly_night_inventory_helpers", REPO / relative)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.BASE = BASE
    # The retained original planner runtime also has reviewed locked Playwright
    # createRequire calls. Rebind only the parser's secondary reviewed root.
    helper.V2 = OLD
    helper.NEW_MODULES = discover(ENGINE + "/web/map_infographic_v1", "planner_causal*.mjs") + sorted(OPTIONAL_OVERRIDES - {ENGINE + "/web/map_infographic_v1/planner_scene_v1.schema.json"})
    helper.NEW_TESTS = discover(ENGINE + "/tests", "planner_causal*.test.mjs")
    return helper


def discover(directory, pattern):
    return sorted(p.relative_to(REPO).as_posix() for p in (REPO / directory).glob(pattern) if p.is_file())


H = frozen_helpers()
record, encode = H.record, H.encode


def load(relative):
    return json.loads(H.HELPER.safe_file(relative).read_text())


def protection():
    area_paths = set(git("ls-tree", "-r", "--name-only", AREA_FINAL).decode().splitlines())
    require(len(area_paths) == 2684, "AREA_FINAL_PATH_SET")
    changed = set(git("diff", "--no-ext-diff", "--name-only", AREA_FINAL).decode().splitlines())
    require(not area_paths & changed, "PROTECTED_AREA_FINAL_PATH_CHANGED: " + ", ".join(sorted(area_paths & changed)))
    old_paths = git("ls-tree", "-r", "--name-only", SOURCE_PARENT, "--", OLD).decode().splitlines()
    old_rows = [H.protected_record(SOURCE_PARENT, path) for path in old_paths]
    actual_old = {p.relative_to(REPO).as_posix() for p in (REPO / OLD).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts}
    require(actual_old == set(old_paths), "ORIGINAL_PLANNER_RECOVERY_FILE_SET_CHANGED")
    require(record(OLD + "/public-review/KOREAN_WAR_PLANNER_SCENE_JSON_V1_CANDIDATE.mp4")["sha256"] == ORIGINAL_MP4_SHA,
            "ORIGINAL_APPROVED_CANDIDATE_CHANGED")
    preexisting = set(git("ls-tree", "-r", "--name-only", SOURCE_PARENT).decode().splitlines())
    touched = preexisting & set(git("diff", "--no-ext-diff", "--name-only", SOURCE_PARENT).decode().splitlines())
    require(touched <= OPTIONAL_OVERRIDES, "UNAUTHORIZED_EXISTING_SOURCE_CHANGE: " + ", ".join(sorted(touched - OPTIONAL_OVERRIDES)))
    return {"area_final_commit": AREA_FINAL, "area_final_original_paths": len(area_paths),
            "changed_area_final_paths": [], "original_planner_commit": SOURCE_PARENT,
            "original_planner_files": old_rows, "original_mp4_sha256": ORIGINAL_MP4_SHA,
            "optional_nonfinal_adapter_changes": sorted(touched), "final_source_geometry_style": "UNCHANGED"}


def scene_document(relative):
    value = load(relative)
    schema_relative = ENGINE + "/web/map_infographic_v1/planner_scene_v1.schema.json"
    require(importlib.metadata.version("jsonschema") == "4.19.2", "PINNED_SCHEMA_VALIDATOR_CHANGED")
    from jsonschema import Draft202012Validator
    schema = load(schema_relative)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    module = "./" + ENGINE + "/web/map_infographic_v1/planner_scene_v1.mjs"
    program = "import fs from 'node:fs';import {validateScenePlan} from " + json.dumps(module) + ";const s=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));console.log(JSON.stringify(validateScenePlan(s)));"
    result = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", program, str(REPO / relative)], cwd=REPO))
    require(result.get("valid") is True, "SCENE_RUNTIME_VALIDATION_FAILED")
    forbidden = {"password", "passwd", "secret", "token", "api_key", "apikey", "credential", "private_key",
                 "runtime_routes", "runtimefiles", "nativefiles", "diagnostics", "internal_plan", "source_code", "repository_path"}
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                require(str(key).lower() not in forbidden, "PUBLIC_SCENE_INTERNAL_KEY: " + str(key))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            require(not re.search(r"(?:file://|/workspace/|/tmp/|world-simulation-shorts-engine/|recovery/|node_modules/|web/map_infographic_v1/)", item), "PUBLIC_SCENE_INTERNAL_PATH")
    visit(value)
    return {"input": record(relative), "published_json_schema": record(schema_relative),
            "schema_validation": "PASS", "canonical_public_export_safety": "PASS"}, value


def public_files(report=None):
    """PNG enumeration is bound to fixture/report declarations, never arbitrary glob permission."""
    fixture = load(BASE + "/fixtures/RUNTIME_FIXTURE.json")
    points = fixture["presentation"]["checkpoints"]
    names = {row.get("file") or row.get("name") for row in points}
    require(names and all(isinstance(n, str) and re.fullmatch(r"[A-Za-z0-9_-]+\.png", n) for n in names), "PUBLIC_PNG_NAMES")
    names.add("PREVIEW.png")
    if report is not None:
        require({row["file"] for row in report["checkpoints"]} == names, "REPORT_FIXTURE_CHECKPOINT_BINDING")
    expected = {MP4, SCENE_JSON, "SHA256SUMS", *names}
    public = REPO / BASE / "public-review"
    paths = sorted(public.iterdir())
    require({path.name for path in paths} == expected, "PUBLIC_REVIEW_EXACT_MP4_PNG_SCENE_SHA_ONLY")
    require(all(path.is_file() and not path.is_symlink() for path in paths), "PUBLIC_NONREGULAR_FILE")
    require((public / SCENE_JSON).read_bytes() == (REPO / BASE / "fixtures" / SCENE_JSON).read_bytes(), "PUBLIC_SCENE_NOT_EXECUTED_FIXTURE")
    sums = "".join(record(path.relative_to(REPO).as_posix())["sha256"] + "  " + path.name + "\n"
                   for path in paths if path.name != "SHA256SUMS")
    require((public / "SHA256SUMS").read_text() == sums, "PUBLIC_SHA256SUMS_BODY")
    scene_document(BASE + "/public-review/" + SCENE_JSON)
    return paths


def candidate_paths(exclusions):
    rows = []
    for path in (REPO / BASE).rglob("*"):
        parts = path.relative_to(REPO / BASE).parts
        if any(part in {"manifests", "__pycache__", ".pytest_cache"} for part in parts) or not path.is_file():
            continue
        relative = path.relative_to(REPO).as_posix()
        H.HELPER.safe_file(relative)
        if relative not in exclusions:
            rows.append(relative)
    return sorted(rows)


def focused_evidence():
    result = {}
    for name in ("FOCUSED_TESTS.json", "INTEGRATION.json"):
        relative = BASE + "/evidence/" + name
        value = load(relative)
        require(value.get("status") == "PASS" and value.get("permanentGateExecuted") is False,
                "FOCUSED_EVIDENCE_NOT_PASS: " + name)
        require(value.get("requiredTempOnlyFiles") == 0 and value.get("fullVisualReviewClaimed") is False,
                "FOCUSED_EVIDENCE_SCOPE: " + name)
        if name == "FOCUSED_TESTS.json":
            require(value["totalPassed"] > 0 and sum(row["passed"] for row in value["tests"]) == value["totalPassed"]
                    and all(row["failed"] == 0 for row in value["tests"]), "FOCUSED_TEST_COUNTS")
            for row in value["sourceBindings"]:
                require(record(ENGINE + "/" + row["file"])["sha256"] == row["sha256"], "FOCUSED_TEST_SOURCE_BINDING")
        else:
            require(value["geometryUnchanged"] is True and len(value["samples"]) == len(value["focusedFrames"]) > 0,
                    "INTEGRATION_GEOMETRY_OR_SAMPLE_COUNT")
            for expected_frame, sample in zip(value["focusedFrames"], value["samples"]):
                diagnostic = sample["diagnostic"]
                require(diagnostic["frame"] == expected_frame and diagnostic["glError"] == 0 and
                        diagnostic["nativeDrawCount"] == 1, "INTEGRATION_NATIVE_FRAME_BINDING")
                pixel = diagnostic["protection"]
                require(pixel.get("checked") is True and all(pixel.get(key) == 0 for key in
                        ("protectedChangedPixels", "markerChangedPixels", "textChangedPixels", "outsideRoiChangedPixels",
                         "safeAreaChangedPixels", "protectedBoundaryChangedPixels")), "INTEGRATION_PIXEL_PROTECTION")
        result[name] = {"input": record(relative), "status": "PASS"}
    return result


def documents(stage, exclusions):
    protected = protection()
    for relative in discover(ENGINE + "/web/map_infographic_v1", "planner_causal*.mjs"):
        body = H.HELPER.safe_file(relative).read_text()
        require(not re.search(r"\b(?:suez|egypt|korea|korean|japan|tohoku|fukushima|busan|incheon|seoul)\b", body, re.I),
                "FIXTURE_PLACE_HARDCODE_IN_GENERIC_ADAPTER: " + relative)
        require(not re.search(r"(?:file://|/tmp/|/workspace/)[^\s'\"`]*", body), "TEMP_OR_ABSOLUTE_GENERIC_INPUT: " + relative)
    parents = {name: load(OLD + "/manifests/" + name + "_MANIFEST.json") for name in (*NAMES, "HASH")}
    parent_rows = [H.protected_record(SOURCE_PARENT, OLD + "/manifests/" + name + "_MANIFEST.json") for name in (*NAMES, "HASH")]
    inherited = [record(row["path"]) if row["path"] in OPTIONAL_OVERRIDES else H.verify_record(row)
                 for row in parents["HASH"]["required_files"]]
    inherited += [H.protected_record(SOURCE_PARENT, OLD + "/manifests/SHA256SUMS")]
    candidate = candidate_paths(exclusions)
    graph = H.import_graph(candidate)
    dependencies = parents["DEPENDENCY"]
    installed = H.HELPER.toolchain(dependencies)
    for pin in dependencies["additional_audit_test_dependencies"]:
        require(importlib.metadata.version(pin["name"]) == pin["version"], "AUDIT_DEPENDENCY_PIN: " + pin["name"])
        H.verify_record(pin["lock"])
    source = sorted(set(H.NEW_MODULES + H.NEW_TESTS + list(OPTIONAL_OVERRIDES) +
                        [p for p in candidate if Path(p).suffix in {".mjs", ".py", ".md", ".sh", ".txt", ".lock"}]))
    fixtures = [p for p in candidate if "/fixtures/" in p or "/data/" in p]
    evidences = sorted(set(candidate) - set(source) - set(fixtures))
    focused = focused_evidence() if stage != "implementation" else None
    scene = scene_document(BASE + "/fixtures/" + SCENE_JSON)[0] if stage != "implementation" else None
    routes = {row["url"]: dict(row) for row in parents["RUNTIME_ASSET"]["runtime_routes"]}
    for path in graph["browser_runtime_modules"]:
        if "/web/map_infographic_v1/" in path:
            routes["/modules/" + Path(path).name] = {"url": "/modules/" + Path(path).name, "file": path}
    explicit = REPO / BASE / "fixtures/RUNTIME_ROUTES.json"
    if explicit.is_file():
        declared = json.loads(explicit.read_text())
        for row in declared.get("runtime_routes", []) if isinstance(declared, dict) else declared:
            require(isinstance(row["url"], str) and row["url"].startswith("/") and not row["url"].startswith("//"), "INVALID_RUNTIME_ROUTE")
            H.HELPER.safe_file(row["file"])
            routes[row["url"]] = {"url": row["url"], "file": row["file"]}
    runtime = REPO / BASE / "fixtures/RUNTIME_FIXTURE.json"
    if runtime.is_file():
        value = json.loads(runtime.read_text())
        mapping = {"regionalPlan": "/inputs/regional.json", "continentPlan": "/inputs/continent.json", "scene": "/inputs/scene.json", "cameraPlan": "/inputs/camera-plan.json", "inputManifest": "/inputs/input-manifest.json"}
        require(set(value["nativeFiles"]) == set(mapping), "NATIVE_INPUT_CONTRACT")
        for key, url in mapping.items():
            path = value["nativeFiles"][key]
            require(isinstance(path, str) and not Path(path).is_absolute() and ".." not in Path(path).parts and not re.search(r"(?:file:|https?:|\\|\btmp/)", path), "TEMP_OR_EXTERNAL_INPUT")
            H.HELPER.safe_file(ENGINE + "/" + path)
            routes[url] = {"url": url, "file": ENGINE + "/" + path}
        require(value["scenePlanPath"] == BASE.removeprefix(ENGINE + "/") + "/fixtures/" + SCENE_JSON, "SCENE_INPUT_NOT_NEW_FIXTURE")
    proof = None
    if stage == "candidate":
        report = load(BASE + "/evidence/proof/REPORT.json")
        require(report["status"] == "PASS", "RENDER_NOT_PASS")
        audit = load(BASE + "/evidence/CANDIDATE_AUDIT.json")
        require(audit["status"] == "PASS" and audit["technicalInspection"]["allFramesDecoded"] == 420, "TECHNICAL_AUDIT_NOT_PASS")
        files = public_files(report)
        require(audit["video"]["sha256"] == report["video"]["sha256"] == record(BASE + "/public-review/" + MP4)["sha256"], "AUDIT_CURRENT_VIDEO_BINDING")
        proof = {"report": record(BASE + "/evidence/proof/REPORT.json"), "focused_technical_audit": record(BASE + "/evidence/CANDIDATE_AUDIT.json"),
                 "original_render_source_commit": report["sourceCommit"], "public_review": [record(p.relative_to(REPO).as_posix()) for p in files],
                 "full_visual_review_claimed": False, "user_video_review_required": True}
    common = {"schema": 1, "scope": "PLANNER_NIGHT_CAUSAL_VISUAL_V1", "development_branch": BRANCH,
              "inventory_stage": stage, "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
              "protection": protected, "required_temp_only_files": [], "postsave_report_exclusions": sorted(exclusions),
              "event_final": False, "planner_final": False, "user_video_approved": False, "permanent_gate_executed": False}
    def make(**fields):
        return {**common, **fields}
    docs = {
        "SOURCE_MANIFEST.json": make(entries=[record(p) for p in graph["reachable_modules"]], procedures=[record(p) for p in source], focused_tests=[record(p) for p in H.NEW_TESTS]),
        "FIXTURE_MANIFEST.json": make(entries=[record(p) for p in fixtures], canonical_scene=scene, mandatory_paths_repository_relative=True),
        "DATA_MANIFEST.json": make(original_fact_geometry_source_documents=[record(p) for p in discover(OLD + "/data", "*.json")], historical_data_unchanged=True, schematic_movement_not_historical_unit_routes=True),
        "EVIDENCE_MANIFEST.json": make(entries=[record(p) for p in evidences], focused_checks=focused, proof=proof, public_allowed_bodies=["MP4", "PNG", "Scene JSON", "SHA256SUMS"]),
        "RUNTIME_ASSET_MANIFEST.json": make(runtime_routes=sorted(routes.values(), key=lambda r: r["url"]), inherited_asset_bodies_verified=True, new_modules=[record(p) for p in H.NEW_MODULES]),
        "BUILD_INPUT_MANIFEST.json": make(inherited_inputs_and_recipe=parents["BUILD_INPUT"]["inherited_inputs_and_recipe"], dependency_locks=dependencies["dependency_locks"]),
        "DEPENDENCY_MANIFEST.json": make(dependencies=dependencies["dependencies"], interpreters=dependencies["interpreters"], setup=dependencies["setup"], dependency_locks=dependencies["dependency_locks"], parser_provider=dependencies["parser_provider"], observed_toolchain=installed, additional_audit_test_dependencies=dependencies["additional_audit_test_dependencies"], additional_runtime_dependencies=[]),
        "IMPORT_MANIFEST.json": make(**graph),
        "REPRODUCTION_MANIFEST.json": make(inherited_manifests=parent_rows, inherited_required_files=len(inherited), setup_recipe=dependencies["setup"], focused_test_argv=["node", "--test", *H.NEW_TESTS], proof_argv=["node", BASE + "/render_proof.mjs"], candidate_audit_argv=["/usr/bin/python3", "-B", BASE + "/verify_candidate.py"], proof=proof, clean_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL", cache_and_onboarding_tool_paths_required=False),
    }
    return docs, inherited, parent_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("implementation", "fixture", "candidate"), default="implementation")
    parser.add_argument("--write-manifests", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--require-persisted", action="store_true")
    args = parser.parse_args()
    require(not args.inspect_only or not (args.write_manifests or args.require_persisted), "INSPECT_ONLY_CONFLICT")
    docs, inherited, parents = documents(args.stage, POSTSAVE)
    rows = H.inventory_of(docs, inherited, parents)
    encoded = {name: encode(doc) for name, doc in docs.items()}
    for name, body in encoded.items():
        path = BASE + "/manifests/" + name
        rows[path] = {"path": path, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    inventory = sorted(rows.values(), key=lambda row: row["path"])
    encoded["HASH_MANIFEST.json"] = encode({"schema": 1, "scope": "PLANNER_NIGHT_CAUSAL_VISUAL_V1", "inventory_stage": args.stage,
        "required_files": inventory, "required_temp_only_files": [], "postsave_report_exclusions": sorted(POSTSAVE),
        "planner_final": False, "user_video_approved": False, "permanent_gate_executed": False,
        "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are bound by committed HEAD/index, excluded from recursive hashes"})
    encoded["SHA256SUMS"] = "".join(r["sha256"] + "  " + r["path"] + "\n" for r in inventory).encode()
    target = REPO / BASE / "manifests"
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, body in encoded.items():
            (target / name).write_bytes(body)
    if not args.inspect_only:
        for name, body in encoded.items():
            require((target / name).read_bytes() == body, "MANIFEST_STALE: " + name)
    paths = sorted(set(rows) | {BASE + "/manifests/" + name for name in encoded})
    if args.require_persisted:
        for path in paths:
            H.verify_persisted(path)
    print(json.dumps({"status": "PASS", "stage": args.stage, "requiredFiles": len(paths), "inheritedRequiredFiles": len(inherited),
                      "requiredTempOnlyFiles": 0, "headAndIndexCompared": args.require_persisted, "permanentGateExecuted": False}))


if __name__ == "__main__":
    main()
