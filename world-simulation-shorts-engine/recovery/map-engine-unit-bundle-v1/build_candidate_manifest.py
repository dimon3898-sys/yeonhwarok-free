#!/usr/bin/env python3
"""Inventory this additive map-engine/unit Candidate without rendering or FINAL gates.

Only --write-manifests writes, exclusively inside this Candidate/manifests.
The retained hash/LFS and AST readers are imported read-only and rebound in memory.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import subprocess

REPO = Path(__file__).resolve().parents[3]
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/map-engine-unit-bundle-v1"
PRIOR = ENGINE + "/recovery/reference-reproduction-v1"
MAP_PRIOR = ENGINE + "/recovery/map-visual-upgrade-v1"
OLD = ENGINE + "/recovery/planner-scene-json-v1"
NIGHT = ENGINE + "/recovery/planner-night-run-v1"
PARENT = "882bd8e939010962b40a81c268937e7f7e88bb62"
BRANCH = "development/map-engine-unit-bundle-20261014"
SCOPE = "MAP_ENGINE_UNIT_BUNDLE_V1"
BASELINES = {
    "camera_v5": "29b8ee294360812b55ef577b62411de58159003b",
    "event_v1": "f79f3d55d945ef0e53b03ac2ed666f48f28b5881",
    "flow_v2": "fbc3be89d94040271c7f54a051162913ad134bac",
    "area_v3": "7da699c07cddf618f5e8a93ca735db51d31bbb39",
}
MP4 = "WORLD_ENGINE_MAP_ENGINE_UNIT_BUNDLE_5S.mp4"
REFERENCE_SHA = "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6"
CURRENT_CANDIDATE_SHA = "0630ab5c5e5e362d1a74ef65fd6041482d30f0ae1b12daa7f3f99490983c0772"
MODULE_NAMES = ("map_engine_unit_gpu_adapter_v4.mjs", "reference_terrain_material_v4.mjs",
                "reference_ocean_material_v4.mjs", "national_unit_badge_v1.mjs",
                "unit_participation_policy_v1.mjs")
ROOT_TEST_NAMES = ("test_unit_participation.mjs", "test_national_units.mjs")
TEST_PATHS = [BASE + "/" + name for name in ROOT_TEST_NAMES] + [ENGINE + "/tests/map_engine_unit_fixture_v4.test.mjs", ENGINE + "/tests/reference_ocean_material_v4.test.mjs", ENGINE + "/tests/reference_terrain_material_v4.test.mjs"]
PUBLIC_NAMES = {MP4, "SCENE_PLAN.json", "SHA256SUMS", "COMPARE_01_START.png", "COMPARE_02_ADVANCE.png",
                "COMPARE_03_TRACKING.png", "COMPARE_04_CONTINUOUS_CONTROL.png", "COMPARE_05_END.png"}
POSTSAVE_NAMES = {
    "HTTP_DOWNLOAD_VERIFY.json", "PERSISTENCE_VERIFICATION.json", "POST_COMMIT_VERIFICATION.json",
    "FINAL_PERSISTENCE.json", "REMOTE_VERIFICATION.json", "SOURCE_AFTER_SECRET_SCAN.json",
    "POST_SCAN_SOURCE_CHECK.json", "POST_SAVE_VERIFICATION.json",
    "SECRET_SCAN.json", "SECRET_SCAN_SOURCE.json", "SECRET_SCAN_CANDIDATE.json", "SECRET_SCAN_PUBLIC.json",
    "SECRET_SCAN_IMPLEMENTATION.json", "SECRET_SCAN_PRE_RENDER.json", "SECRET_SCAN_FINAL_REPORT.json",
}


def require(condition, reason):
    if not condition:
        raise ValueError("MAP_ENGINE_UNIT_STORAGE: " + reason)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.PIPE)


def load(relative):
    return json.loads(H.HELPER.safe_file(relative).read_text())


def frozen_helpers():
    relative = ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py"
    require((REPO / relative).read_bytes() == git("show", BASELINES["area_v3"] + ":" + relative),
            "FROZEN_HASH_AST_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("readonly_map_engine_unit_inventory_helpers", REPO / relative)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.BASE, helper.V2 = BASE, OLD
    helper.NEW_MODULES = [ENGINE + "/web/map_infographic_v1/" + name for name in MODULE_NAMES]
    helper.NEW_TESTS = TEST_PATHS
    return helper


H = frozen_helpers()
record, encode = H.record, H.encode


def protection():
    original = set(git("ls-tree", "-r", "--name-only", PARENT).decode().splitlines())
    changed = set(git("diff", "--no-ext-diff", "--name-only", PARENT).decode().splitlines())
    require(not original & changed, "PREEXISTING_TRACKED_PATH_CHANGED: " + ", ".join(sorted(original & changed)))
    head_changed = set(git("diff", "--no-ext-diff", "--name-only", PARENT, "HEAD").decode().splitlines())
    require(not original & head_changed, "PREEXISTING_COMMITTED_PATH_CHANGED")
    require(git("merge-base", PARENT, "HEAD").decode().strip() == PARENT, "WRONG_DEVELOPMENT_ANCESTOR")
    return {"comparison_parent_commit": PARENT, "original_tracked_paths": len(original),
            "changed_original_paths": [], "committed_original_changes": [],
            "worktree_and_head_compared": True, "final_baselines": BASELINES,
            "camera_renderer_geometry_style_originals": "UNCHANGED"}


def candidate_paths(exclusions):
    paths = []
    for file in (REPO / BASE).rglob("*"):
        parts = file.relative_to(REPO / BASE).parts
        if any(part in {"manifests", "__pycache__", ".pytest_cache"} for part in parts) or not file.is_file():
            continue
        relative = file.relative_to(REPO).as_posix()
        H.HELPER.safe_file(relative)
        if relative not in exclusions:
            paths.append(relative)
    return sorted(paths)


def default_exclusions():
    # Declare receipt names before they exist: later HTTP/persistence writes do
    # not change this hash inventory's exclusions or stale its manifest body.
    return {BASE + "/CHECKPOINT_STATUS.json", *(BASE + "/evidence/" + name for name in POSTSAVE_NAMES)}


def public_scene(relative):
    value = load(relative)
    require(value.get("schema") == value.get("version") == "MAP_ENGINE_UNIT_SCENE_V4", "PUBLIC_SCENE_SCHEMA")
    require(value.get("metadata", {}).get("output") == {"width": 1080, "height": 1920, "fps": 30, "audio": False},
            "PUBLIC_SCENE_OUTPUT")
    require(value["metadata"].get("referenceSHA256") == REFERENCE_SHA, "PUBLIC_SCENE_REFERENCE_BINDING")
    require(value["metadata"].get("semanticMode") ==
            "COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY",
            "PUBLIC_COUNTERFACTUAL_SEMANTICS_MUST_REMAIN_SEPARATE_FROM_PRIVATE_HISTORY")
    prior_scene = load(MAP_PRIOR + "/fixtures/SCENE_PLAN.json")
    require(all(value.get(key) == prior_scene.get(key) for key in
                ("controlIntent", "cameraKeyframes", "presentationProfile")),
            "PRESERVED_CONTROL_GEOMETRY_OR_CAMERA_TRACK_CHANGED")
    profiles = value.get("combatProfile", {}).get("profiles", {})
    require(isinstance(profiles, dict) and profiles and
            all(isinstance(profile, dict) and profile.get("private_only") is not True
                for profile in profiles.values()), "PRIVATE_HISTORICAL_PROFILES_EXPORTED_TO_PUBLIC_SCENE")
    forbidden = {"password", "passwd", "secret", "token", "api_key", "apikey", "credential", "private_key",
                 "nativefiles", "runtimefiles", "runtime_routes", "diagnostics", "internal_plan", "source_code"}
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                require(str(key).lower() not in forbidden, "PUBLIC_SCENE_INTERNAL_KEY: " + str(key))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            require(not re.search(r"(?:file://|/workspace/|/tmp/|world-simulation-shorts-engine/|recovery/|node_modules/|web/map_infographic_v1/)", item),
                    "PUBLIC_SCENE_INTERNAL_PATH")
    visit(value)
    return {"input": record(relative), "canonical_export_safety": "PASS",
            "executed_scene_version": value["schema"], "historical_fixture_substitution": False}


def public_files():
    declaration_path = BASE + "/evidence/PUBLIC_REVIEW_FILES.json"
    declaration = load(declaration_path)
    rows = declaration.get("files") if isinstance(declaration, dict) else declaration
    require(isinstance(rows, list) and rows, "PUBLIC_EXACT_ALLOWLIST_REQUIRED")
    names = []
    for row in rows:
        name = row if isinstance(row, str) else row.get("file", row.get("name"))
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]+\.(?:png|mp4|json)|SHA256SUMS", name),
                "PUBLIC_UNSAFE_FILE_NAME")
        require(name == MP4 or name in {"SCENE_PLAN.json", "SHA256SUMS"} or name.endswith(".png"),
                "PUBLIC_MP4_PNG_CANONICAL_SCENE_SHA_ONLY")
        names.append(name)
    require(len(names) == len(set(names)) and set(names) == PUBLIC_NAMES,
            "PUBLIC_EXACT_EIGHT_BODY_ALLOWLIST_REQUIRED")
    paths = sorted((REPO / BASE / "public-review").iterdir())
    require({path.name for path in paths} == set(names), "PUBLIC_DIRECTORY_ALLOWLIST_MISMATCH")
    records = []
    for path in paths:
        actual = record(path.relative_to(REPO).as_posix())
        declared = next((row for row in rows if isinstance(row, dict) and row.get("file", row.get("name")) == path.name), None)
        if declared and "sha256" in declared:
            require(declared["sha256"] == actual["sha256"], "PUBLIC_DECLARED_HASH_CHANGED")
        records.append(actual)
    require((REPO / BASE / "public-review/SCENE_PLAN.json").read_bytes() ==
            (REPO / BASE / "fixtures/SCENE_PLAN.json").read_bytes(), "PUBLIC_SCENE_NOT_EXECUTED_FIXTURE")
    sums = "".join(row["sha256"] + "  " + Path(row["path"]).name + "\n"
                   for row in records if Path(row["path"]).name != "SHA256SUMS")
    require((REPO / BASE / "public-review/SHA256SUMS").read_text() == sums, "PUBLIC_SHA256SUMS_BODY")
    public_scene(BASE + "/public-review/SCENE_PLAN.json")
    return records


def runtime_assets(graph):
    fixture = load(BASE + "/fixtures/RUNTIME_FIXTURE.json")
    mapping = {"regionalPlan": "/inputs/regional.json", "continentPlan": "/inputs/continent.json",
               "scene": "/inputs/scene.json", "cameraPlan": "/inputs/camera-plan.json",
               "inputManifest": "/inputs/input-manifest.json"}
    require(set(fixture["nativeFiles"]) == set(mapping), "RUNTIME_NATIVE_INPUT_CONTRACT")
    routes, assets = {}, {}
    for key, url in mapping.items():
        relative = fixture["nativeFiles"][key]
        require(isinstance(relative, str) and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "TEMP_OR_EXTERNAL_NATIVE_INPUT")
        routes[url] = {"url": url, "file": ENGINE + "/" + relative}
        record(routes[url]["file"])

    def visit(value):
        if isinstance(value, dict):
            if "file" in value and "url" in value:
                file, url = value["file"], value["url"]
                require(isinstance(file, str) and not Path(file).is_absolute() and isinstance(url, str)
                        and url.startswith("/") and not url.startswith("//") and ".." not in Path(url).parts,
                        "RUNTIME_ASSET_PATH_OR_URL")
                canonical = file if file.startswith((ENGINE + "/", "cinematic-world-map/")) else posixpath.normpath(ENGINE + "/" + file)
                actual = record(canonical)
                if "sha256" in value:
                    require(value["sha256"] == actual["sha256"], "RUNTIME_ASSET_SOURCE_HASH_CHANGED: " + canonical)
                if "bytes" in value:
                    require(value["bytes"] == actual["bytes"], "RUNTIME_ASSET_SOURCE_SIZE_CHANGED")
                require(url not in routes or routes[url]["file"] == canonical, "RUNTIME_ROUTE_FILE_CONFLICT")
                routes[url], assets[canonical] = {"url": url, "file": canonical}, actual
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    license_documents, non_runtime_references = {}, []
    for key in ("regionalPlan", "continentPlan"):
        plan = load(ENGINE + "/" + fixture["nativeFiles"][key])
        visit(plan.get("assets", {}))
        for geometry in plan.get("geometries", []):
            license_data = geometry.get("license", {})
            if isinstance(license_data, dict) and isinstance(license_data.get("file"), str):
                candidates = [license_data["file"], posixpath.normpath(ENGINE + "/" + license_data["file"])]
                relative = next((p for p in candidates if (REPO / p).is_file()), None)
                if relative:
                    license_documents[relative] = record(relative)
                elif license_data not in non_runtime_references:
                    non_runtime_references.append({**license_data,
                        "status": "ORIGINAL_PROVENANCE_REFERENCE_NOT_A_RUNTIME_FETCH", "local_body_present": False})
    inputs = load(ENGINE + "/" + fixture["nativeFiles"]["inputManifest"])
    for key in ("heightSource", "contextTerrain", "runtimeAsset"):
        visit(inputs.get(key))
    for path in graph["browser_runtime_modules"]:
        url = "/three.js" if "/web/vendor/" in path else "/modules/" + Path(path).name
        routes[url] = {"url": url, "file": path}
    inherited = fixture.get("inheritedAdmissionFiles", {})
    require(set(inherited) == {"scenePlan", "visualAdmission"}, "PERSISTED_INHERITED_VISUAL_PROFILE_REQUIRED")
    inherited_bodies = []
    for relative in inherited.values():
        require(isinstance(relative, str) and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "INHERITED_PROFILE_MUST_BE_PERSISTED_ENGINE_INPUT")
        inherited_bodies.append(H.protected_record(PARENT, ENGINE + "/" + relative))
    # The fixture explicitly owns any additional permanent source raster/input
    # bodies. These are file inventories, not permission for a new live fetch.
    additional_runtime_bodies = []
    for relative in fixture.get("runtimeAssetFiles", []):
        require(isinstance(relative, str) and not Path(relative).is_absolute()
                and ".." not in Path(relative).parts, "ADDITIONAL_RUNTIME_ASSET_MUST_BE_PERSISTED")
        actual = record(ENGINE + "/" + relative)
        additional_runtime_bodies.append(actual)
        assets[actual["path"]] = actual
    declared_modules = fixture.get("runtimeModuleFiles")
    require(isinstance(declared_modules, list) and declared_modules, "PERSISTED_RUNTIME_MODULE_CLOSURE_REQUIRED")
    module_bodies = [record(ENGINE + "/" + relative) for relative in declared_modules]
    require(set(graph["browser_runtime_modules"]) <= {row["path"] for row in module_bodies},
            "FIXTURE_RUNTIME_BROWSER_CLOSURE_MISSING")
    originals = set(git("ls-tree", "-r", "--name-only", PARENT).decode().splitlines())
    inherited_module_bodies = [H.protected_record(PARENT, relative)
                              for relative in graph["browser_runtime_modules"] if relative in originals]
    return {"runtime_routes": sorted(routes.values(), key=lambda row: row["url"]),
            "asset_bodies": sorted(assets.values(), key=lambda row: row["path"]),
            "source_license_documents": sorted(license_documents.values(), key=lambda row: row["path"]),
            "non_runtime_original_provenance_references": non_runtime_references,
            "native_input_bodies": [record(ENGINE + "/" + fixture["nativeFiles"][key]) for key in mapping],
            "inherited_visual_admission_bodies": inherited_bodies,
            "additional_runtime_asset_bodies": additional_runtime_bodies,
            "declared_runtime_module_bodies": module_bodies,
            "inherited_browser_module_bodies": inherited_module_bodies,
            "loopback_server": record(ENGINE + "/recovery/v5/serve.py"),
            "generated_routes": ["/runtime-config.json"],
            "live_external_runtime_requests": False, "height_source_present": load(routes["/inputs/input-manifest.json"]["file"]).get("heightSource") is not None}


def proof_metadata():
    path = BASE + "/evidence/proof/REPORT.json"
    report = load(path)
    require(report.get("status") == "PASS", "PROOF_RENDER_NOT_PASS")
    source = report.get("sourceCommit")
    require(re.fullmatch(r"[0-9a-f]{40}", source or ""), "RENDER_SOURCE_COMMIT_REQUIRED")
    require(git("rev-parse", source + "^{commit}").decode().strip() == source and
            git("merge-base", PARENT, source).decode().strip() == PARENT, "RENDER_SOURCE_UNKNOWN_OR_WRONG_PARENT")
    bindings = report.get("sourceBindings")
    require(isinstance(bindings, list) and bindings, "RENDER_SOURCE_BODY_BINDINGS_REQUIRED")
    bound_paths = set()
    for binding in bindings:
        relative = binding.get("path")
        actual_binding = record(relative)
        committed_binding = H.HELPER.expected_body(source, relative)
        require(relative not in bound_paths and all(actual_binding[key] == binding.get(key) == committed_binding[key]
                for key in ("sha256", "bytes")), "RENDER_SOURCE_BINDING_CHANGED: " + str(relative))
        bound_paths.add(relative)
    fixture = load(BASE + "/fixtures/RUNTIME_FIXTURE.json")
    required_modules = {ENGINE + "/" + relative for relative in fixture["runtimeModuleFiles"]}
    require(set(H.NEW_MODULES) | required_modules <= bound_paths and BASE + "/fixtures/SCENE_PLAN.json" in bound_paths
            and BASE + "/fixtures/RUNTIME_FIXTURE.json" in bound_paths, "RENDER_REQUIRED_INPUT_NOT_BOUND")
    video = report.get("video", {})
    actual = record(BASE + "/public-review/" + MP4)
    require(video.get("file") == MP4 and all(video.get(key) == actual[key] for key in ("sha256", "bytes")),
            "PROOF_CURRENT_MP4_BINDING")
    audit_path = BASE + "/evidence/CANDIDATE_AUDIT.json"
    audit = load(audit_path)
    require(audit.get("status") == "PASS", "ENCODED_CANDIDATE_AUDIT_NOT_PASS")
    inspection = audit.get("technicalInspection", {})
    decoded = inspection.get("allFramesDecoded", audit.get("allFramesDecoded", audit.get("decodedFrames")))
    require(decoded == 150, "ALL_150_ENCODED_FRAMES_NOT_VERIFIED")
    if isinstance(audit.get("video"), dict):
        require(audit["video"].get("sha256") == actual["sha256"], "AUDIT_CURRENT_MP4_BINDING")
    if "frames" in report:
        require(len(report["frames"]) == 150 and all(row.get("frame") == index and row.get("glError") == 0
                and row.get("sourceCommit") == source for index, row in enumerate(report["frames"])),
                "RENDER_FRAME_INVENTORY_INCOMPLETE_OR_UNBOUND")
    require((report.get("totalFrames"), report.get("durationSeconds"), report.get("fps"),
             report.get("width"), report.get("height")) == (150, 5, 30, 1080, 1920), "RENDER_OUTPUT_FORMAT")
    return {"render_report": record(path), "encoded_audit": record(audit_path),
            "render_source_commit": source, "render_source_bodies": bindings, "video": actual, "public_review": public_files(),
            "all_150_encoded_frames_verified": True, "technical_pass_is_user_approval": False}


def documents(stage, exclusions):
    protected = protection()
    paths = candidate_paths(exclusions)
    graph = H.import_graph(paths)
    assets = runtime_assets(graph)
    dependency_path = NIGHT + "/manifests/DEPENDENCY_MANIFEST.json"
    dependencies = load(dependency_path)
    H.protected_record(PARENT, dependency_path)
    installed = H.HELPER.toolchain(dependencies)
    python_helpers = [ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py",
                      ENGINE + "/recovery/event-v1-candidate-v2/validate_manifests.py", "tools/v4_recovery_gate.py"]
    source = sorted(set(H.NEW_MODULES + H.NEW_TESTS + graph["reachable_modules"] + python_helpers +
                        [p for p in paths if Path(p).suffix in {".mjs", ".py", ".md", ".txt", ".sh", ".lock"}]))
    fixtures = [p for p in paths if "/fixtures/" in p]
    data = [p for p in paths if "/data/" in p]
    evidence = sorted(set(paths) - set(source) - set(fixtures) - set(data))
    reference = record(PRIOR + "/data/REFERENCE_65379_COMPRESSED.mp4")
    require(reference["sha256"] == REFERENCE_SHA, "ORIGINAL_COMPRESSED_REFERENCE_CHANGED")
    current_candidate = H.protected_record(PARENT, MAP_PRIOR + "/public-review/WORLD_ENGINE_MAP_VISUAL_UPGRADE_5S.mp4")
    require(current_candidate["sha256"] == CURRENT_CANDIDATE_SHA, "PRIOR_65409_CANDIDATE_CHANGED")
    canonical = public_scene(BASE + "/fixtures/SCENE_PLAN.json")
    audit = load(BASE + "/evidence/input_audit/REPORT.json")
    fresh_reference, fresh_candidate = audit.get("reference", {}), audit.get("currentCandidate", {})
    reused_review = audit.get("wholeReferenceAuditReused", {})
    require(audit.get("schema") == "MAP_ENGINE_UNIT_INPUT_BINDING_V1" and audit.get("status") == "PASS"
            and fresh_reference.get("inputSha256") == REFERENCE_SHA
            and fresh_reference.get("sourceTotalFrames") == 958
            and fresh_reference.get("freshDecodedRelevantFrames") == 151
            and fresh_reference.get("everyRelevantFrameMatchesPreservedRgbAudit") is True
            and fresh_reference.get("fullDurationChronologicalContactCoverage") is True
            and fresh_candidate.get("inputSha256") == CURRENT_CANDIDATE_SHA
            and fresh_candidate.get("sourceTotalFrames") == 150
            and fresh_candidate.get("freshDecodedRelevantFrames") == 150
            and fresh_candidate.get("everyRelevantFrameMatchesPreservedRgbAudit") is True
            and reused_review.get("referenceShaIdentical") is True
            and reused_review.get("preservedFrameCount") == 958
            and reused_review.get("preservedWholeVisualReview", {}).get("all958FramesCovered") is True
            and reused_review.get("freshRelevant151FrameRgbMatch") is True
            and reused_review.get("whole958ReDecodeClaimedThisRun") is False
            and audit.get("userClarification") ==
                "PUBLIC_COUNTERFACTUAL_PRESERVED_HISTORICAL_FLAGS_AND_PARTICIPATION_GATES_PRIVATE_ONLY"
            and audit.get("historicalFiveFactionInsertionIntoPublic") is False
            and audit.get("inputsModified") is False,
            "ACTUAL_RELEVANT_REFERENCE_AND_PRESERVED_FULL_AUDIT_MISSING")
    preserved_whole_audit = H.protected_record(PARENT, PRIOR + "/evidence/REFERENCE_AUDIT_SUMMARY.json")
    proof = proof_metadata() if stage == "candidate" else None
    common = {"schema": 1, "scope": SCOPE, "development_branch": BRANCH,
              "inventory_stage": stage, "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
              "protected_baselines": protected, "required_temp_only_files": [], "event_final": False,
              "user_video_approved": False, "permanent_gate_executed": False,
              "postsave_report_exclusions": sorted(exclusions)}
    def make(**fields):
        return {**common, **fields}
    docs = {
        "SOURCE_MANIFEST.json": make(entries=[record(p) for p in source], new_engine_modules=[record(p) for p in H.NEW_MODULES], focused_tests=[record(p) for p in H.NEW_TESTS]),
        "FIXTURE_MANIFEST.json": make(entries=[record(p) for p in fixtures], canonical_public_scene=canonical, native_input_bodies=assets["native_input_bodies"]),
        "DATA_MANIFEST.json": make(entries=[record(p) for p in data], original_reference=reference, protected_previous_candidate=current_candidate,
                                   real_country_geometry=record(OLD + "/data/NATIVE_PENINSULA.json"), historical_fact_source=record(OLD + "/data/FACT_DATA.json"),
                                   reference_semantics="MODERN_COUNTERFACTUAL_VISUAL_STUDY_NOT_HISTORICAL_KOREAN_WAR", original_historical_data_unchanged=True,
                                   private_historical_role_policy=record(BASE + "/fixtures/HISTORICAL_UNIT_POLICY.json"),
                                   private_national_flag_profile_fixture=record(BASE + "/fixtures/NATIONAL_FLAG_PROFILES.json"),
                                   historical_policy_application_to_public="OUT_OF_SCOPE_COUNTERFACTUAL_NOT_HISTORY",
                                   five_historical_factions_inserted_into_public=False),
        "EVIDENCE_MANIFEST.json": make(entries=[record(p) for p in evidence], proof=proof, actual_relevant_reference_audit=record(BASE + "/evidence/input_audit/REPORT.json"), preserved_whole_reference_audit=preserved_whole_audit, whole958_redecode_claimed_this_run=False, public_allowed_bodies=["MP4", "five three-way Reference/prior/new comparison PNGs", "Canonical Scene JSON", "SHA256SUMS"]),
        "RUNTIME_ASSET_MANIFEST.json": make(**assets),
        "DEPENDENCY_MANIFEST.json": make(parent=record(dependency_path), dependencies=dependencies["dependencies"], interpreters=dependencies["interpreters"], setup=dependencies["setup"], dependency_locks=[H.verify_record(row) for row in dependencies["dependency_locks"]], parser_provider=dependencies["parser_provider"], observed_toolchain=installed, additional_runtime_dependencies=[], optional_measurement_build_tools={"numpy": "2.2.4", "already_installed": True, "required_for_saved_fixture_proof": False, "usage": "Actual decoded pixel diagnostics; measured anchors and camera/control tracks remain persisted unchanged"}),
        "IMPORT_MANIFEST.json": make(**graph),
        "BUILD_INPUT_MANIFEST.json": make(reused_hash_ast_helper=H.protected_record(BASELINES["area_v3"], ENGINE + "/recovery/event-v1-v3-visual-detail/build_candidate_manifest.py"), inherited_build_recipe=H.protected_record(PARENT, OLD + "/manifests/BUILD_INPUT_MANIFEST.json"), dependency_locks=[H.verify_record(row) for row in dependencies["dependency_locks"]], terrain_regenerated=False, final_source_modified=False),
        "REPRODUCTION_MANIFEST.json": make(setup_recipe=dependencies["setup"], focused_test_argv=["node", "--test", "--test-isolation=none", *H.NEW_TESTS], proof_argv=["node", BASE + "/render_proof.mjs"], candidate_audit_argv=["/usr/bin/python3", "-B", BASE + "/audit_candidate.py"], instructions=record(BASE + "/REPRODUCTION.md"), proof=proof, clean_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL", renderer_backend="ANGLE_SWIFTSHADER", cache_and_onboarding_tool_paths_required=False),
    }
    return docs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("inputs", "candidate"), default="inputs")
    parser.add_argument("--write-manifests", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--require-persisted", action="store_true")
    parser.add_argument("--exclude-postsave", action="append", default=[])
    args = parser.parse_args()
    require(not args.inspect_only or not (args.write_manifests or args.require_persisted), "INSPECT_ONLY_CONFLICT")
    exclusions = default_exclusions()
    for relative in args.exclude_postsave:
        require(relative.startswith(BASE + "/evidence/") and Path(relative).suffix == ".json" and ".." not in Path(relative).parts,
                "POSTSAVE_EXCLUSION_MUST_BE_PRIVATE_JSON")
        exclusions.add(relative)
    docs = documents(args.stage, exclusions)
    rows = H.inventory_of(docs, [], [])
    for path, expected in list(rows.items()):
        actual = H.HELPER.record(path)
        require(all(actual[key] == expected[key] for key in ("sha256", "bytes")), "INPUT_CHANGED_DURING_INVENTORY: " + path)
    encoded = {name: encode(doc) for name, doc in docs.items()}
    for name, body in encoded.items():
        relative = BASE + "/manifests/" + name
        rows[relative] = {"path": relative, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    inventory = sorted(rows.values(), key=lambda row: row["path"])
    encoded["HASH_MANIFEST.json"] = encode({"schema": 1, "scope": SCOPE, "inventory_stage": args.stage,
        "required_files": inventory, "required_temp_only_files": [], "event_final": False, "user_video_approved": False,
        "permanent_gate_executed": False, "postsave_report_exclusions": sorted(exclusions),
        "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are excluded from recursive hashes; HEAD/index verification still checks their bodies."})
    encoded["SHA256SUMS"] = "".join(row["sha256"] + "  " + row["path"] + "\n" for row in inventory).encode()
    target = REPO / BASE / "manifests"
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, body in encoded.items():
            (target / name).write_bytes(body)
    if not args.inspect_only:
        for name, body in encoded.items():
            require((target / name).read_bytes() == body, "MANIFEST_STALE_OR_CHANGED: " + name)
    persistence_paths = sorted(set(rows) | {BASE + "/manifests/" + name for name in encoded})
    if args.require_persisted:
        for relative in persistence_paths:
            H.verify_persisted(relative)
    print(json.dumps({"scope": SCOPE, "inventory_status": "PASS", "inventory_stage": args.stage,
        "required_files": len(persistence_paths), "reachable_import_modules": len(docs["IMPORT_MANIFEST.json"]["reachable_modules"]),
        "import_edges": len(docs["IMPORT_MANIFEST.json"]["edges"]), "runtime_routes": len(docs["RUNTIME_ASSET_MANIFEST.json"]["runtime_routes"]),
        "original_tracked_paths": docs["SOURCE_MANIFEST.json"]["protected_baselines"]["original_tracked_paths"],
        "changed_original_paths": [], "required_temp_only_files": 0, "head_and_index_compared": bool(args.require_persisted),
        "permanent_gate_executed": False, "user_video_approved": False, "event_final": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
