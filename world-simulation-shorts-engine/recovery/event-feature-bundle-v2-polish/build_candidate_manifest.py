#!/usr/bin/env python3
"""Inventory the Flow visual-polish Candidate. This is not the approval-only Permanent Gate.

Reuse the frozen V1 AST parser and canonical Git/LFS body helpers. The only
writes are new Candidate/manifests files; no render, data build, or approval.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/event-feature-bundle-v2-polish"
ACCEPTED = ENGINE + "/recovery/event-feature-bundle-v2"
ACCEPTED_COMMIT = "12715730f0d93cecf450bd51099be9e99fbdb71c"
ADAPTER = ENGINE + "/web/map_infographic_v1/flow_gpu_adapter_v2.mjs"
ACCEPTED_FIXTURE_NAMES = ("ROUTE_FLOW_REAL.json", "FLOW_PLAN.json", "DETAIL_ADAPTER_PLAN.json",
                          "DETAIL_REQUEST.json", "NATIVE_EVENT_PLAN.json", "MOTION_CONTINUITY.json",
                          "synthetic-a.json", "synthetic-b.json", "synthetic-c.json", "scene.json",
                          "REGIONAL-plan.json", "CONTINENT-plan.json")
ACCEPTED_INPUTS = [ACCEPTED + "/fixtures/" + name for name in ACCEPTED_FIXTURE_NAMES]
ACCEPTED_INPUTS += [ACCEPTED + "/evidence/proof/REPORT.json"]
PARENT = ENGINE + "/recovery/event-v1-v3-visual-detail"
FINAL = ENGINE + "/recovery/event-v1-final/FINAL_MANIFEST.json"
PARENT_COMMIT = "f79f3d55d945ef0e53b03ac2ed666f48f28b5881"
FINAL_SHA = "52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1"
SCOPE = "EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH"
BRANCH = "development/event-flow-polish-v2-20261013"
NEW_MODULES = [ENGINE + "/web/map_infographic_v1/" + n + ".mjs" for n in
               ("flow_core_v2", "flow_graphic_pass_v2", "flow_gpu_adapter_v2", "flow_visual_profile_v2")]
NEW_TESTS = [ENGINE + "/tests/flow_visual_profile_v2.test.mjs"]
NAMES = ("SOURCE", "FIXTURE", "DATA", "EVIDENCE", "RUNTIME_ASSET", "BUILD_INPUT",
         "DEPENDENCY", "IMPORT", "REPRODUCTION")
MP4 = "SUEZ_EVENT_FEATURE_BUNDLE_V2_FLOW_MOVEMENT_POLISH.mp4"
CHECKPOINTS = ("01_ROUTE_START.png", "02_OBJECT_DEPARTURE.png", "03_OBJECT_TRAVEL.png",
               "04_TRAVEL_APPROACH.png", "05_ENDPOINT_PULSE.png", "06_FINAL_HOLD.png")
POSTSAVE = {BASE + "/evidence/" + n for n in
            ("SECRET_SCAN.json", "SECRET_SCAN_IMPLEMENTATION.json", "PERSISTENCE_VERIFICATION.json",
             "POST_COMMIT_VERIFICATION.json", "POST_SCAN_SOURCE_CHECK.json", "FINAL_PERSISTENCE.json",
             "SOURCE_AFTER_SECRET_SCAN.json",
             "HTTP_DOWNLOAD_VERIFY.json")}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.DEVNULL)


def load_frozen_helpers():
    path = PARENT + "/build_candidate_manifest.py"
    raw = git("show", PARENT_COMMIT + ":" + path)
    if (REPO / path).read_bytes() != raw:
        raise ValueError("FROZEN_MANIFEST_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("frozen_v1_candidate_helpers", REPO / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Parameterize the existing reviewed AST closure walker for the new roots.
    module.BASE, module.NEW_MODULES, module.NEW_TESTS = BASE, NEW_MODULES, NEW_TESTS
    return module


H = load_frozen_helpers()
record, encode = H.record, H.encode


def protection():
    existing = set(git("ls-tree", "-r", "--name-only", PARENT_COMMIT).decode().splitlines())
    changed = sorted(existing & set(git("diff", "--name-only", PARENT_COMMIT).decode().splitlines()))
    if changed:
        raise ValueError("V1_FINAL_PROTECTED_PATH_CHANGED: " + ", ".join(changed))
    final = H.protected_record(PARENT_COMMIT, FINAL)
    if final["sha256"] != FINAL_SHA:
        raise ValueError("PARENT_FINAL_MANIFEST_SHA_MISMATCH")
    accepted = set(git("ls-tree", "-r", "--name-only", ACCEPTED_COMMIT).decode().splitlines())
    changed_flow = sorted(accepted & set(git("diff", "--name-only", ACCEPTED_COMMIT).decode().splitlines()))
    if any(path != ADAPTER for path in changed_flow):
        raise ValueError("ACCEPTED_FLOW_PROTECTED_PATH_CHANGED: " + ", ".join(changed_flow))
    prior_adapter = git("show", ACCEPTED_COMMIT + ":" + ADAPTER).decode()
    # Exactly this optional caller-controlled presentation hook is allowed. The
    # native projection, arc-length controls, camera, pixel checks and disabled
    # extension branch remain byte-for-byte the accepted implementation.
    replacements = (
        ("import {createFlowGraphicPass} from './flow_graphic_pass_v2.mjs';\n",
         "import {createFlowGraphicPass} from './flow_graphic_pass_v2.mjs';\nimport {applyFlowVisualProfile} from './flow_visual_profile_v2.mjs';\n"),
        ("flowPlan,detailPlan,approvedEventStyle,approvedMetricStyle,extensionEnabled=true",
         "flowPlan,detailPlan,approvedEventStyle,approvedMetricStyle,visualProfile=null,extensionEnabled=true"),
        ("let controls=null,result=null,primitive=null;", "let controls=null,result=null,primitive=null,presentation=null;"),
        ("    if(!pass){style=chooseStyle", "    if(visualProfile)presentation=applyFlowVisualProfile({flowPlan:flow,controls,primitive,profile:visualProfile});\n    if(!pass){style=chooseStyle"),
        ("    result=pass.draw({primitive,controls,safeArea,protectedGraphics:native.event.protectedGraphics,flowIntent:flow.intent});",
         "    result=pass.draw({primitive,controls:presentation?.controls??controls,safeArea,protectedGraphics:native.event.protectedGraphics,\n     flowIntent:presentation?{...flow.intent,object_graphic:presentation.objectGraphic}:flow.intent});"),
        ("    primitive,graphics:result,style:copy(style),protection},width,height,glError:0};return last;",
         "    primitive,graphics:result,style:copy(style),protection,\n    ...(presentation?{visualControls:presentation.controls,visualProfile:presentation.metadata}:{})},width,height,glError:0};return last;")
    )
    expected_adapter = prior_adapter
    for before, after in replacements:
        if expected_adapter.count(before) != 1:
            raise ValueError("REVIEWED_ADAPTER_HOOK_INPUT_NOT_UNIQUE")
        expected_adapter = expected_adapter.replace(before, after)
    if H.HELPER.safe_file(ADAPTER).read_text() != expected_adapter:
        raise ValueError("ADAPTER_CHANGED_BEYOND_REVIEWED_PRESENTATION_HOOK")
    frozen_flow = [H.protected_record(ACCEPTED_COMMIT, path) for path in
                   (NEW_MODULES[0], NEW_MODULES[1], ENGINE + "/tests/flow_core_v2.test.mjs",
                    ACCEPTED + "/build_candidate_manifest.py")]
    return {"baseline": "EVENT_SYSTEM_V1_FINAL_BASELINE", "commit": PARENT_COMMIT,
            "manifest": final, "original_tracked_paths": len(existing),
            "changed_original_paths": [], "camera_core": "UNCHANGED", "v1_source": "UNCHANGED",
            "existing_visual_and_layout": "UNCHANGED", "approved_geometry_and_metric": "UNCHANGED",
            "accepted_flow_commit": ACCEPTED_COMMIT, "accepted_flow_tracked_paths": len(accepted),
            "accepted_flow_changed_paths": changed_flow, "frozen_flow_sources": frozen_flow,
            "allowed_adapter_change": {"classification": "OPTIONAL_CALLER_PRESENTATION_HOOK_ONLY",
                                       "exact_reviewed_patch_verified": True, "current": record(ADAPTER),
                                       "prior_sha256": hashlib.sha256(prior_adapter.encode()).hexdigest()},
            "new_presentation_profile": record(NEW_MODULES[-1])}


def inactive_descriptors(fixtures):
    rows = []
    for path in fixtures:
        if not path.endswith("-plan.json"):
            continue
        value = json.loads(H.HELPER.safe_file(path).read_text())
        descriptors = value.get("_recovery", {}).get("inactive_historical_asset_descriptors", {})
        inactive = {}
        for name, item in descriptors.items():
            if (item.get("runtime_required") is False and item.get("runtime_loaded") is False
                    and isinstance(item.get("historical_file_reference_NOT_REQUIRED"), str)):
                inactive[item["historical_file_reference_NOT_REQUIRED"]] = (name, item)
        def visit(item, pointer=""):
            if isinstance(item, dict):
                for key, child in item.items():
                    visit(child, pointer + "/" + key)
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    visit(child, pointer + "/" + str(index))
            elif isinstance(item, str) and item.startswith("/tmp/"):
                if item not in inactive:
                    raise ValueError("UNCLASSIFIED_TEMP_FIXTURE_REFERENCE: " + path + pointer)
                name, description = inactive[item]
                rows.append({"fixture": path, "json_pointer": pointer, "historical_reference": item,
                             "classification": "INACTIVE_PROVENANCE_DESCRIPTOR",
                             "runtime_required": False, "runtime_loaded": False,
                             "descriptor": "_recovery/inactive_historical_asset_descriptors/" + name,
                             "reason": description["reason"]})
        visit(value)
    return rows


def require(condition, reason):
    if not condition:
        raise ValueError("FLOW_POLISH_CANDIDATE_EVIDENCE_INVALID: " + reason)


def proof_report(candidate):
    prerequisite_specs = (("FOCUSED_VALIDATION.json", "status"), ("OBJECT_SIZE_COMPARISON.json", "status"))
    prerequisites = []
    for filename, result_key in prerequisite_specs:
        prerequisite_path = BASE + "/evidence/" + filename
        prerequisite = json.loads(H.HELPER.safe_file(prerequisite_path).read_text())
        require(prerequisite.get(result_key) == "PASS", "PREREQUISITE_" + filename)
        prerequisites.append({"input": record(prerequisite_path), "result_key": result_key,
                              "result": prerequisite[result_key]})
    visual_path = BASE + "/evidence/VISUAL_AUDIT.json"
    visual = json.loads(H.HELPER.safe_file(visual_path).read_text())
    require(visual.get("status") == "PASS", "POST_RENDER_VISUAL_AUDIT")
    public = {Path(p).name: record(p) for p in candidate if p.startswith(BASE + "/public-review/")}
    require(set(public) == {MP4, *CHECKPOINTS, "SHA256SUMS"}, "PUBLIC_MEDIA_ALLOWLIST")
    path = BASE + "/evidence/proof/REPORT.json"
    report = json.loads(H.HELPER.safe_file(path).read_text())
    require(report.get("status") == "PASS" and report.get("state") == "EVENT_FEATURE_BUNDLE_V2_POLISH_CANDIDATE", "STATUS")
    require(all(report.get(k) is False for k in ("userVideoApproved", "eventFinal", "permanentGateExecuted")), "APPROVAL_GATE")
    require((report.get("width"), report.get("height"), report.get("fps"), report.get("audio")) == (1080, 1920, 30, False), "FORMAT")
    count, duration = report.get("totalFrames"), report.get("durationSeconds")
    require(isinstance(count, int) and isinstance(duration, (int, float)) and 7 <= duration <= 9 and count == duration * 30, "DURATION")
    source_commit = report.get("sourceCommit")
    require(isinstance(source_commit, str) and len(source_commit) == 40
            and all(char in "0123456789abcdef" for char in source_commit), "RENDER_SOURCE_COMMIT")
    require(git("rev-parse", source_commit + "^{commit}").decode().strip() == source_commit, "RENDER_SOURCE_REVISION")
    require(git("merge-base", PARENT_COMMIT, source_commit).decode().strip() == PARENT_COMMIT, "RENDER_SOURCE_PARENT")
    # The original pre-media source revision is the primary fresh-checkout
    # reproduction target: it includes prerequisites but no existing outputs.
    for directory in ("public-review", "evidence/proof"):
        require(not git("ls-tree", "-r", "--name-only", source_commit, "--", BASE + "/" + directory).strip(),
                "ORIGINAL_RENDER_OUTPUTS_ALREADY_EXIST_" + directory)
    original_inputs = NEW_MODULES + ACCEPTED_INPUTS + [BASE + "/polish_runtime.mjs", BASE + "/render_proof.mjs"]
    original_inputs += [p for p in candidate if p.startswith(BASE + "/fixtures/")]
    original_inputs += [BASE + "/evidence/" + filename for filename, _ in prerequisite_specs]
    source_bindings = [H.protected_record(source_commit, p) for p in sorted(set(original_inputs))]
    detail = json.loads(H.HELPER.safe_file(BASE + "/fixtures/DETAIL_ADAPTER_PLAN.json").read_text())
    flow = json.loads(H.HELPER.safe_file(BASE + "/fixtures/FLOW_PLAN.json").read_text())
    visual_profile = json.loads(H.HELPER.safe_file(BASE + "/fixtures/VISUAL_PROFILE.json").read_text())
    lock, frames = detail["detailLockFrame"], report.get("frames", [])
    require(len(frames) == count, "FRAME_INVENTORY")
    for index, row in enumerate(frames):
        require(row.get("frame") == index and row.get("glError") == 0, "FRAME_ORDER_OR_GL_ERROR")
        effect = row.get("flow", {})
        require(all(effect.get("protection", {}).get(k) == 0 for k in
                    ("protectedChangedPixels", "markerChangedPixels", "outsideRoiChangedPixels")), "FRAME_PROTECTION")
        if index < lock:
            require(effect.get("enabled") is False and effect.get("controls") is None, "FLOW_BEFORE_DETAIL_LOCK")
        else:
            require(row.get("cameraLocked") is True and effect.get("enabled") is True, "DETAIL_LOCK")
            require(effect.get("graphics", {}).get("nativeStateRestored") is True, "NATIVE_STATE")
            require(effect.get("primitive", {}).get("intent", {}).get("line", {}).get("geometry") == flow["intent"]["route_geometry"], "GEOMETRY")
            require(effect.get("style", {}).get("width") == 7, "V1_ROUTE_STYLE_REUSE")
            original, presented = effect.get("controls", {}), effect.get("visualControls", {})
            require(all(original.get(key) == presented.get(key) for key in
                        ("localFrame", "objectFraction", "objectPosition", "objectHeading", "state")),
                    "PRESENTATION_MODIFIED_CORE_OBJECT_MOTION")
            require(effect.get("visualProfile", {}).get("objectScale") == visual_profile.get("objectScale"),
                    "PRESENTATION_PROFILE_BINDING")
            require(0 <= presented.get("routeFraction", -1) <= 1, "ROUTE_VISUAL_PROGRESS_RANGE")
    require(report.get("decodeValidation") == "PASS", "DECODE")
    streams = report.get("ffprobe", {}).get("streams", [])
    require(len(streams) == 1, "SILENT_SINGLE_VIDEO_STREAM")
    s = streams[0]
    require((s.get("codec_type"), s.get("codec_name"), s.get("width"), s.get("height"), s.get("avg_frame_rate")) ==
            ("video", "h264", 1080, 1920, "30/1"), "VIDEO_PROBE")
    require(int(s.get("nb_read_frames", -1)) == count and float(s.get("duration", -1)) == duration, "PROBED_DURATION")
    require(all(report.get("video", {}).get(k) == public[MP4][k] for k in ("sha256", "bytes")), "MP4_BODY")
    checkpoints = report.get("checkpoints", [])
    require(len(checkpoints) == len(CHECKPOINTS) and {c.get("file") for c in checkpoints} == set(CHECKPOINTS), "CHECKPOINT_SET")
    for c in checkpoints:
        require(all(c.get(k) == public[c["file"]][k] for k in ("sha256", "bytes")), "CHECKPOINT_BODY")
        require(c.get("sourceMatchesEncodedNativeFrame") is True and frames[c["frame"]]["png_sha256"] == c["sha256"], "CHECKPOINT_ENCODE_INPUT")
    sums = "".join(public[n]["sha256"] + "  " + n + "\n" for n in sorted({MP4, *CHECKPOINTS}))
    require(H.HELPER.safe_file(BASE + "/public-review/SHA256SUMS").read_text() == sums, "PUBLIC_SHA256SUMS")
    return {"report": record(path), "mp4": public[MP4], "checkpoints": [public[n] for n in CHECKPOINTS],
            "public_checksums": public["SHA256SUMS"], "total_frames": count, "duration_seconds": duration,
            "prerequisites": prerequisites, "original_render_source_commit": source_commit,
            "post_render_visual_audit": {"input": record(visual_path), "status": visual["status"]},
            "original_render_source_and_input_bindings": source_bindings,
            "original_render_outputs_absent_at_source_revision": True,
            "detail_lock_frame": lock, "actual_original_delivery_hashes": "PASS",
            "ffprobe_and_decode_reexecuted_by_inventory": False, "permanent_gate_executed": False}


def documents(stage, exclusions):
    protected = protection()
    H.common_source_guard()
    profile = H.HELPER.safe_file(NEW_MODULES[-1]).read_text()
    if re.search(r"\b(?:ship|aircraft)\b", profile, re.I):
        raise ValueError("OBJECT_TYPE_BRANCH_IN_PRESENTATION_PROFILE")
    parent_rows, parent_docs = [], {}
    for name in (*NAMES, "HASH"):
        file = name + "_MANIFEST.json"
        path = PARENT + "/manifests/" + file
        parent_rows.append(H.protected_record(PARENT_COMMIT, path))
        parent_docs[name] = json.loads(H.HELPER.safe_file(path).read_text())
    inherited = [H.verify_record(r) for r in parent_docs["HASH"]["required_files"]]
    accepted_inputs = [H.protected_record(ACCEPTED_COMMIT, path) for path in ACCEPTED_INPUTS]
    observed = H.HELPER.toolchain(parent_docs["DEPENDENCY"])
    candidate = H.candidate_paths(exclusions)
    graph = H.import_graph(candidate)
    source = sorted(set(NEW_MODULES + NEW_TESTS + [p for p in candidate if Path(p).suffix in {".mjs", ".py", ".md", ".sh"}]))
    fixtures = [p for p in candidate if "/fixtures/" in p or Path(p).suffix == ".json" and "/evidence/" not in p]
    evidence = sorted(set(candidate) - set(source) - set(fixtures))
    inactive = inactive_descriptors(fixtures)
    proof = proof_report(candidate) if stage == "candidate" else None
    common = {"schema": 1, "scope": SCOPE, "development_branch": BRANCH, "inventory_stage": stage,
              "candidate_state": "EVENT_FEATURE_BUNDLE_V2_POLISH_CANDIDATE" if stage == "candidate" else "IMPLEMENTATION_CHECKPOINT",
              "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
              "parent_baseline": protected, "quality_grade": "FACT_BASED_VISUAL_GRADE",
              "visual_polish_scope": ["OBJECT_PRESENCE", "ROUTE_PROGRESS", "TEST_TEXT_REMOVAL", "ARRIVAL_EMPHASIS"],
              "candidate_media_commit_binding": "GIT_COMMIT_CONTAINING_ORIGINAL_PUBLIC_MEDIA_AND_THIS_MANIFEST",
              "event_final": False, "user_video_approved": False, "permanent_gate_executed": False,
              "required_temp_only_files": [], "postsave_report_exclusions": sorted(exclusions)}
    def make(**fields):
        return {**common, **fields}
    parent = {Path(r["path"]).name.removesuffix("_MANIFEST.json"): r for r in parent_rows}
    routes = {r["url"]: dict(r) for r in parent_docs["RUNTIME_ASSET"]["runtime_routes"]}
    for path in graph["browser_runtime_modules"]:
        if "/web/map_infographic_v1/" in path:
            routes["/modules/" + Path(path).name] = {"url": "/modules/" + Path(path).name, "file": path}
    for url, file in (("/inputs/regional.json", "REGIONAL-plan.json"), ("/inputs/continent.json", "CONTINENT-plan.json"),
                      ("/inputs/scene.json", "scene.json")):
        routes[url] = {"url": url, "file": BASE + "/fixtures/" + file}
    dependency = parent_docs["DEPENDENCY"]
    source_doc = make(parent=parent["SOURCE"], entries=[record(p) for p in graph["reachable_modules"]],
                      candidate_source_and_procedures=[record(p) for p in source],
                      flow_module_closure=[record(p) for p in NEW_MODULES],
                      new_engine_modules=[record(NEW_MODULES[-1])],
                      optional_presentation_hook=record(ADAPTER), focused_tests=[record(p) for p in NEW_TESTS],
                      reviewed_inventory_helper=H.protected_record(PARENT_COMMIT, PARENT + "/build_candidate_manifest.py"))
    fixture_doc = make(parent=parent["FIXTURE"], entries=[record(p) for p in fixtures],
                       route_geometry_source="RETAINED_VERIFIED_V1_PRODUCTION_GEOMETRY", original_geometry_modified=False,
                       inactive_historical_descriptors=inactive, mandatory_runtime_paths_are_repository_relative=True)
    runtime_doc = make(parent=parent["RUNTIME_ASSET"], runtime_routes=sorted(routes.values(), key=lambda r: r["url"]),
                       flow_extension_module_closure=[record(p) for p in NEW_MODULES],
                       new_runtime_modules=[record(NEW_MODULES[-1])], inherited_asset_bodies_verified=True,
                       existing_renderer_and_visual_sources_modified=False,
                       optional_flow_gpu_presentation_hook_modified=True,
                       arc_length_projection_camera_layout_occlusion_core_modified=False)
    docs = {
        "SOURCE_MANIFEST.json": source_doc, "FIXTURE_MANIFEST.json": fixture_doc,
        "DATA_MANIFEST.json": make(parent=parent["DATA"], new_source_data_downloaded=False,
                                    inherited_geometry_and_metric_provenance_unchanged=True),
        "RUNTIME_ASSET_MANIFEST.json": runtime_doc,
        "BUILD_INPUT_MANIFEST.json": make(parent=parent["BUILD_INPUT"], inherited_inputs_and_recipe=parent_docs["BUILD_INPUT"]["inherited_inputs_and_recipe"],
                                           dependency_locks=dependency["dependency_locks"], new_fixture_builder=record(BASE + "/build_polish_fixture.mjs"),
                                           immutable_accepted_flow_fixture_and_comparison_inputs=accepted_inputs),
        "EVIDENCE_MANIFEST.json": make(entries=[record(p) for p in evidence], proof=proof,
                                        original_render_source_commit=None if proof is None else proof["original_render_source_commit"],
                                        delivery_receipt_policy={"path": BASE + "/evidence/HTTP_DOWNLOAD_VERIFY.json",
                                                                 "classification": "POST_MEDIA_COMMIT_DOWNLOAD_VALIDATION_RECEIPT",
                                                                 "runtime_required": False,
                                                                 "binding": "The later receipt must name the immutable original media commit and actual downloaded body hashes. Its exact body is bound by its containing Git commit rather than a recursive Candidate hash."},
                                        public_review_allowed_bodies=["MP4", "PNG", "SHA256SUMS"],
                                        acceptance="Technical Candidate inventory does not grant video approval."),
        "DEPENDENCY_MANIFEST.json": make(parent=parent["DEPENDENCY"], dependencies=dependency["dependencies"],
                                          interpreters=dependency["interpreters"], setup=dependency["setup"],
                                          dependency_locks=dependency["dependency_locks"], parser_provider=dependency["parser_provider"],
                                          observed_toolchain=observed, additional_runtime_dependencies=[]),
        "IMPORT_MANIFEST.json": make(**graph),
        "REPRODUCTION_MANIFEST.json": make(setup_recipe=dependency["setup"], interpreters=dependency["interpreters"],
                                            entrypoints=[record(p) for p in candidate if Path(p).suffix in {".py", ".mjs"}],
                                            inherited_required_file_count=len(inherited), inherited_manifests=parent_rows,
                                            immutable_accepted_flow_fixture_and_comparison_inputs=accepted_inputs,
                                            focused_test_argv=["node", "--test", *NEW_TESTS],
                                            fixture_argv=["node", BASE + "/build_polish_fixture.mjs"],
                                            proof_argv=["node", BASE + "/render_proof.mjs"],
                                            candidate_manifest_argv=["/usr/bin/python3", "-B", BASE + "/build_candidate_manifest.py", "--stage", stage],
                                            original_render_source_commit=None if proof is None else proof["original_render_source_commit"],
                                            primary_remote_checkout={"url": "https://github.com/dimon3898-sys/yeonhwarok-free.git",
                                                                     "branch": BRANCH,
                                                                     "revision": "PENDING_ORIGINAL_RENDER_SOURCE_COMMIT" if proof is None else proof["original_render_source_commit"],
                                                                     "output_directories_absent": None if proof is None else proof["original_render_outputs_absent_at_source_revision"],
                                                                     "prerequisite_evidence": [] if proof is None else proof["prerequisites"],
                                                                     "policy": "Fetch the named original source revision from the remote and use a fresh checkout. Its public-review and evidence/proof folders are absent, so render_proof.mjs can create original reproduction outputs without deleting or changing approved media."},
                                            alternate_candidate_checkout={"url": "https://github.com/dimon3898-sys/yeonhwarok-free.git",
                                                                          "branch": BRANCH,
                                                                          "revision": "PIN_TO_GIT_COMMIT_CONTAINING_CANDIDATE_MANIFESTS",
                                                                          "policy": "Optional: in a disposable remote Candidate checkout, verify hashes and archive the original public-review and evidence/proof folders before rendering separate copies. Preserve production Candidate/Public Review."},
                                            runtime_assets="Fetch the retained required Git/LFS bodies; use the unchanged parent pinned setup and toolchain.",
                                            clean_environment_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL", proof=proof)}
    return docs, inherited, [protected["manifest"], *parent_rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("implementation", "candidate"), default="implementation")
    parser.add_argument("--write-manifests", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--require-persisted", action="store_true")
    parser.add_argument("--exclude-postsave", action="append", default=[])
    args = parser.parse_args()
    if args.inspect_only and (args.write_manifests or args.require_persisted):
        parser.error("--inspect-only excludes writes and persistence verification")
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
    inventory = sorted(rows.values(), key=lambda r: r["path"])
    encoded["HASH_MANIFEST.json"] = encode({"schema": 1, "scope": SCOPE, "inventory_stage": args.stage,
                                           "required_files": inventory, "required_temp_only_files": [],
                                           "event_final": False, "user_video_approved": False, "permanent_gate_executed": False,
                                           "postsave_report_exclusions": sorted(exclusions),
                                           "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are excluded from recursive hashes; HEAD/index may bind their exact bytes."})
    encoded["SHA256SUMS"] = "".join(r["sha256"] + "  " + r["path"] + "\n" for r in inventory).encode()
    target = REPO / BASE / "manifests"
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, body in encoded.items():
            (target / name).write_bytes(body)
    if not args.inspect_only:
        for name, body in encoded.items():
            if (target / name).read_bytes() != body:
                raise ValueError("FLOW_POLISH_CANDIDATE_MANIFEST_STALE_OR_CHANGED: " + name)
    paths = sorted(set(rows) | {BASE + "/manifests/" + name for name in encoded})
    if args.require_persisted:
        for path in paths:
            H.verify_persisted(path)
    print(json.dumps({"scope": SCOPE, "inventory_status": "PASS", "inventory_stage": args.stage,
                      "required_files": len(paths), "inherited_required_files": len(inherited),
                      "flow_module_closure": len(NEW_MODULES), "new_engine_modules": 1,
                      "optional_presentation_hooks": 1, "focused_tests": len(NEW_TESTS),
                      "reachable_import_modules": len(docs["IMPORT_MANIFEST.json"]["reachable_modules"]),
                      "import_edges": len(docs["IMPORT_MANIFEST.json"]["edges"]),
                      "required_temp_only_files": 0, "head_and_index_compared": args.require_persisted,
                      "permanent_gate_executed": False, "user_video_approved": False, "event_final": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
