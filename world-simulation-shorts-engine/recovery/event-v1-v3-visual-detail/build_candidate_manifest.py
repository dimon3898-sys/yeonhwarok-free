#!/usr/bin/env python3
"""Inventory the visual-detail Candidate without running the approval-only final gate.

This command parses imports and reads retained inputs. It never builds terrain,
renders frames, invokes the seven-condition Permanent Gate, or grants approval.
Only --write-manifests writes files, exclusively under this Candidate/manifests.
Use --stage inputs before the proof; use --stage candidate once proof files exist.
"""
import argparse
import hashlib
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENGINE = "world-simulation-shorts-engine"
BASE = ENGINE + "/recovery/event-v1-v3-visual-detail"
V2 = ENGINE + "/recovery/event-v1-candidate-v2"
DATA_ADMISSION = ENGINE + "/recovery/suez-detail-data-admission-v1"
DATA = ENGINE + "/recovery/event-data/suez-full-canal-20261012"
BASELINES = {
    "camera_v5": "29b8ee294360812b55ef577b62411de58159003b",
    "event_v2": "8cbbbd64573ea87aa56decbc0fb5218071e45bbe",
    "suez_data": "69e6ed83acac00bfa7ab1853722f873792a813e1",
    "v3_block": "9cf4661a56db0334bc1d9e936a6671f643562112",
    "survey_detail_evidence": "8e68b02016707db5274535f18e808b5630bb57d2",
}
NEW_MODULES = [ENGINE + "/web/map_infographic_v1/" + name + ".mjs" for name in (
    "visual_detail_admission_v1", "camera_detail_approach_adapter_v1", "visual_event_gpu_adapter_v1")]
NEW_TESTS = [ENGINE + "/tests/" + name + ".test.mjs" for name in (
    "visual_detail_admission_v1", "camera_detail_approach_adapter_v1")]
INPUT_REFS = [DATA_ADMISSION + "/DETAIL_DATA_PROFILE.json",
              DATA_ADMISSION + "/evidence/DETAIL_QUALITY_AUDIT.json",
              DATA_ADMISSION + "/DATA_RESEARCH_MANIFEST.json"]
PARENT_NAMES = ("SOURCE_MANIFEST.json", "FIXTURE_MANIFEST.json", "EVIDENCE_MANIFEST.json",
                "RUNTIME_ASSET_MANIFEST.json", "BUILD_INPUT_MANIFEST.json",
                "DEPENDENCY_MANIFEST.json", "IMPORT_MANIFEST.json", "HASH_MANIFEST.json")
DOC_NAMES = ("SOURCE_MANIFEST.json", "FIXTURE_MANIFEST.json", "DATA_MANIFEST.json",
             "EVIDENCE_MANIFEST.json", "RUNTIME_ASSET_MANIFEST.json", "BUILD_INPUT_MANIFEST.json",
             "DEPENDENCY_MANIFEST.json", "IMPORT_MANIFEST.json", "REPRODUCTION_MANIFEST.json")
MP4_NAME = "SUEZ_EVENT_SYSTEM_V1_V3_VISUAL_DETAIL.mp4"
CHECKPOINT_NAMES = ("01_EVENT_ARRIVAL.png", "02_DETAIL_APPROACH.png", "03_DETAIL_LOCK.png",
                    "04_LINE_REVEAL.png", "05_LINE_COMPLETE.png", "06_METRIC_REVEAL.png",
                    "07_INFORMATION_HOLD.png")
DEFAULT_POSTSAVE = {
    BASE + "/evidence/SECRET_SCAN_A.json",
    BASE + "/evidence/SECRET_SCAN_B.json",
    BASE + "/evidence/SECRET_SCAN.json",
    BASE + "/evidence/PERSISTENCE_VERIFICATION.json",
    BASE + "/evidence/POST_COMMIT_VERIFICATION.json",
    BASE + "/evidence/FINAL_PERSISTENCE.json",
    BASE + "/evidence/POST_SCAN_SOURCE_CHECK.json",
    BASE + "/evidence/SOURCE_AFTER_SECRET_SCAN.json",
}
LFS = re.compile(rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.DEVNULL)


def encode(document):
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()


def load_helper():
    path = REPO / V2 / "validate_manifests.py"
    spec = importlib.util.spec_from_file_location("readonly_v2_manifest_helpers", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.unchanged(BASELINES["event_v2"], V2 + "/validate_manifests.py")
    return helper


HELPER = load_helper()
RECORDS = {}


def record(path, **extra):
    if path not in RECORDS:
        RECORDS[path] = HELPER.record(path)
    return {**RECORDS[path], **extra}


def verify_record(expected):
    actual = record(expected["path"])
    if any(expected[key] != actual[key] for key in ("sha256", "bytes")):
        raise ValueError("INHERITED_INPUT_BODY_CHANGED: " + expected["path"])
    return actual


def protected_record(ref, path):
    actual = record(path)
    expected = HELPER.expected_body(ref, path)
    if any(actual[key] != expected[key] for key in ("sha256", "bytes")):
        raise ValueError("PROTECTED_BASELINE_BODY_CHANGED: " + path)
    return actual


def baseline_protection():
    # The newest retained evidence baseline includes all earlier locked files.
    # Added V3 files are allowed; no original tracked body may be modified.
    original = set(git("ls-tree", "-r", "--name-only", BASELINES["survey_detail_evidence"]).decode().splitlines())
    changed = set(git("diff", "--name-only", BASELINES["survey_detail_evidence"]).decode().splitlines())
    protected_changed = sorted(original & changed)
    if protected_changed:
        raise ValueError("PROTECTED_PREEXISTING_PATH_CHANGED: " + ", ".join(protected_changed))
    return {"comparison_base": BASELINES["survey_detail_evidence"],
            "original_tracked_paths": len(original), "changed_original_paths": [],
            "camera_v5_core": "UNCHANGED", "event_v2_sources_and_style": "UNCHANGED",
            "production_geometry_metric_and_provenance": "UNCHANGED",
            "survey_detail_result": "RETAINED_UNALTERED",
            "visual_detail_is_separate_policy": True}


def candidate_paths(postsave):
    paths = []
    root = REPO / BASE
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if "manifests" in parts or "__pycache__" in parts:
            continue
        if path.is_file():
            relative = path.relative_to(REPO).as_posix()
            HELPER.safe_file(relative)
            if relative in postsave:
                continue
            public = any(part in {"public-review", "public_review"} for part in parts)
            if public and path.name != "SHA256SUMS" and path.suffix.lower() not in {".png", ".mp4"}:
                raise ValueError("PUBLIC_REVIEW_MEDIA_OR_SHA256SUMS_ONLY: " + relative)
            paths.append(relative)
    return sorted(paths)


def import_graph(paths):
    helper_path = "tools/v4_recovery_gate.py"
    protected_record(BASELINES["camera_v5"], helper_path)
    spec = importlib.util.spec_from_file_location("readonly_pinned_ast_program", REPO / helper_path)
    parser_helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_helper)
    parser = REPO / parser_helper.AST_PARSER
    if hashlib.sha256(parser.read_bytes()).hexdigest() != parser_helper.AST_PARSER_SHA:
        raise ValueError("PINNED_AST_PARSER_CHANGED")
    roots = sorted(set(NEW_MODULES + NEW_TESTS + [p for p in paths if p.endswith(".mjs")]))
    parsed, edges, externals, pending = {}, [], [], list(roots)
    lock_path = "cinematic-world-map/package-lock.json"
    lock = json.loads(HELPER.safe_file(lock_path).read_text())
    while pending:
        path = pending.pop()
        if path in parsed:
            continue
        request = {"parser": str(parser), "files": [{"path": path, "absolute": str(HELPER.safe_file(path))}]}
        row = json.loads(subprocess.check_output(["node", "-e", parser_helper.AST_PROGRAM],
                                                input=json.dumps(request).encode(), cwd=REPO))[0]
        known_requires = {"playwright", "playwright/package.json"}
        text = HELPER.safe_file(path).read_text()
        reviewed_commonjs = (path.startswith((BASE + "/", V2 + "/")) and
                             all(r["specifier"] in known_requires for r in row["requires"]) and
                             "createRequire(path.join(repo,'cinematic-world-map/package.json'))" in text)
        issues = [issue for issue in row["issues"] if not (
            issue["code"] == "COMMONJS_RUNTIME_CLOSURE_REQUIRES_REVIEW" and reviewed_commonjs)]
        if issues:
            raise ValueError("AST_IMPORT_ISSUE: " + path + ": " + json.dumps(issues))
        parsed[path] = row
        for required in row["requires"]:
            package = lock["packages"]["node_modules/playwright"]
            externals.append({"from": path, **required, "kind": "LOCKED_NPM_COMMONJS_PACKAGE",
                              "version": package["version"], "integrity": package["integrity"],
                              "lock_path": lock_path, "resolution_root": "cinematic-world-map/package.json"})
        for imported in row["imports"]:
            source = imported["specifier"]
            if not isinstance(source, str) or source.startswith(("file:", "/tmp/", "http:", "https:")):
                raise ValueError("UNSAFE_OR_UNRESOLVED_RUNTIME_IMPORT: " + path)
            if source.startswith("node:"):
                externals.append({"from": path, **imported, "kind": "NODE_BUILTIN", "node_version": HELPER.PINNED["node"]})
                continue
            if source in {"three", "playwright", "playwright-core"}:
                package = lock["packages"]["node_modules/" + source]
                externals.append({"from": path, **imported, "kind": "LOCKED_NPM_PACKAGE",
                                  "version": package["version"], "integrity": package["integrity"], "lock_path": lock_path})
                continue
            if source == "/three.js":
                target = ENGINE + "/web/vendor/three/0.170.0/three.module.js"
            elif source.startswith("/modules/"):
                target = ENGINE + "/web/map_infographic_v1/" + source.removeprefix("/modules/")
            elif source.startswith(("./", "../")):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), source))
            else:
                raise ValueError("UNRESOLVED_RUNTIME_IMPORT: " + source)
            HELPER.safe_file(target)
            pending.append(target)
            edges.append({"from": path, "to": target, **imported})
    # Resolve export forwarding; checking names against parser-local exports
    # alone would miss an export-all binding without examining its target.
    exports = {path: set(row["exports"]) for path, row in parsed.items()}
    defaults = {path: row["default"] for path, row in parsed.items()}
    for _ in range(len(parsed) + 1):
        changed = False
        for path, row in parsed.items():
            for forwarding in row["reexports"]:
                edge = next((e for e in edges if e["from"] == path and e["specifier"] == forwarding["specifier"]), None)
                if edge is None:
                    raise ValueError("EXTERNAL_REEXPORT_NOT_REVIEWED: " + path)
                target = edge["to"]
                names = forwarding["names"]
                if names is None:
                    before = len(exports[path])
                    exports[path].update(exports[target])
                    changed |= before != len(exports[path])
                else:
                    for name in names:
                        imported = name["imported"]
                        if imported == "*" or imported in exports[target] or imported == "default" and defaults[target]:
                            if name["exported"] == "default":
                                changed |= not defaults[path]
                                defaults[path] = True
                            elif name["exported"] not in exports[path]:
                                exports[path].add(name["exported"])
                                changed = True
        if not changed:
            break
    for edge in edges:
        missing = set(edge["names"]) - exports[edge["to"]]
        if missing or edge["default"] and not defaults[edge["to"]]:
            raise ValueError("IMPORTED_EXPORT_BINDING_MISSING: " + edge["to"])
    return {"parser": "PINNED_BABEL_AST", "parser_sha256": parser_helper.AST_PARSER_SHA,
            "parser_provider_lock": lock_path, "parser_provider_version": "1.62.1", "helper": record(helper_path),
            "roots": roots, "reachable_modules": sorted(parsed),
            "browser_runtime_modules": sorted(p for p in parsed if "/web/map_infographic_v1/" in p or "/web/vendor/" in p),
            "edges": sorted(edges, key=lambda r: (r["from"], r["line"], r["to"])),
            "locked_or_builtin_imports": sorted(externals, key=lambda r: (r["from"], r["specifier"])),
            "issues": [], "required_temp_only_files": []}


def common_source_guard():
    for path in NEW_MODULES:
        text = HELPER.safe_file(path).read_text()
        if re.search(r"\b(?:suez|egypt)\b|193\s*\.\s*30", text, re.I) or any(
                name != "COUNTRY_LABEL" for name in re.findall(r"\bCOUNTRY_[A-Z_]+\b", text)):
            raise ValueError("FIXTURE_HARDCODE_IN_COMMON_ENGINE: " + path)
        if re.search(r"(?:file://|/tmp/|/workspace/)[^\s'\"`]*", text):
            raise ValueError("TEMPORARY_OR_ABSOLUTE_ENGINE_REFERENCE: " + path)


def documents(stage, postsave):
    protection = baseline_protection()
    common_source_guard()
    parents, inherited_docs = [], {}
    for name in PARENT_NAMES:
        path = V2 + "/manifests/" + name
        parents.append(protected_record(BASELINES["event_v2"], path))
        inherited_docs[name] = json.loads(HELPER.safe_file(path).read_text())
    inherited_rows = [verify_record(row) for row in inherited_docs["HASH_MANIFEST.json"]["required_files"]]
    installed = HELPER.toolchain(inherited_docs["DEPENDENCY_MANIFEST.json"])
    previous_data = [protected_record(BASELINES["survey_detail_evidence"], path) for path in INPUT_REFS]
    candidate = candidate_paths(postsave)
    graph = import_graph(candidate)
    source = sorted(set(NEW_MODULES + NEW_TESTS + [p for p in candidate if Path(p).suffix in {".mjs", ".py", ".md", ".sh"}]))
    fixtures = [p for p in candidate if "/fixtures/" in p or Path(p).suffix == ".json" and "/evidence/" not in p]
    evidence = [p for p in candidate if "/evidence/" in p or Path(p).suffix in {".mp4", ".png"} or Path(p).name == "SHA256SUMS"]
    other = sorted(set(candidate) - set(source) - set(fixtures) - set(evidence))
    proof = None
    if stage == "candidate":
        media_by_name = {}
        for path in candidate:
            if Path(path).suffix in {".mp4", ".png"}:
                media_by_name.setdefault(Path(path).name, []).append(path)
        selected = {}
        for name in (MP4_NAME, *CHECKPOINT_NAMES):
            choices = media_by_name.get(name, [])
            if not choices:
                raise ValueError("CANDIDATE_PROOF_FILE_MISSING: " + name)
            hashes = {record(path)["sha256"] for path in choices}
            if len(hashes) != 1:
                raise ValueError("CANDIDATE_PROOF_DUPLICATE_BODY_DIFFERS: " + name)
            selected[name] = record(sorted(choices)[0])
        proof = {"mp4": selected[MP4_NAME], "checkpoints": [selected[n] for n in CHECKPOINT_NAMES],
                 "output": {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16", "audio": "NONE"},
                 "original_candidate_delivery": True, "proof_metadata_requires_evidence_report": True}
    base = {"schema": 1, "scope": "EVENT_SYSTEM_V1_V3_VISUAL_DETAIL", "inventory_stage": stage,
            "candidate_state": "EVENT_SYSTEM_V1_V3_VISUAL_CANDIDATE" if stage == "candidate" else "CHECKPOINT_B_INPUT_INVENTORY",
            "status": "USER_VIDEO_REVIEW_REQUIRED" if stage == "candidate" else "PROOF_RENDER_PENDING",
            "baselines": BASELINES, "protected_baselines": protection,
            "event_final": False, "user_video_approved": False,
            "permanent_gate_executed": False, "required_temp_only_files": [],
            "inventory_root": "REPOSITORY_ROOT", "postsave_report_exclusions": sorted(postsave)}
    def make(**fields):
        return {**base, **fields}
    graph_rows = [record(path, origin="NEW_VISUAL_DETAIL_SOURCE" if path in NEW_MODULES or path.startswith(BASE + "/") or path in NEW_TESTS
                         else "RETAINED_PROTECTED_SOURCE") for path in graph["reachable_modules"]]
    routes = {row["url"]: row for row in inherited_docs["RUNTIME_ASSET_MANIFEST.json"]["runtime_routes"]}
    for path in graph["browser_runtime_modules"]:
        if "/web/map_infographic_v1/" in path:
            routes["/modules/" + Path(path).name] = {"url": "/modules/" + Path(path).name, "file": path}
    parent_by_name = {Path(row["path"]).name: row for row in parents}
    source_doc = make(entries=graph_rows, candidate_source_and_procedures=[record(p) for p in source],
                      inherited_source_manifest=parent_by_name["SOURCE_MANIFEST.json"],
                      new_engine_modules=[record(p) for p in NEW_MODULES], focused_tests=[record(p) for p in NEW_TESTS])
    fixture_doc = make(entries=[record(p) for p in fixtures],
                       production_fixture=protected_record(BASELINES["suez_data"], DATA + "/fixture.json"),
                       inherited_fixture_manifest=parent_by_name["FIXTURE_MANIFEST.json"],
                       production_data_regenerated=False, event_geometry_modified=False,
                       metric_meaning_or_provenance_modified=False)
    data_doc = make(retained_data_profile_and_candidate_evidence=previous_data,
                    inherited_build_input_manifest=parent_by_name["BUILD_INPUT_MANIFEST.json"],
                    inherited_runtime_asset_manifest=parent_by_name["RUNTIME_ASSET_MANIFEST.json"],
                    retained_survey_result="NOT_ADMITTED_UNCHANGED",
                    separate_production_quality_grade="FACT_BASED_VISUAL_GRADE",
                    new_source_data_downloaded=False, terrain_upscaled_or_sharpened=False)
    evidence_doc = make(entries=[record(p) for p in evidence], other_retained_candidate_files=[record(p) for p in other],
                        proof=proof, acceptance="Technical evidence does not grant user video approval.",
                        public_review_allowed_bodies=["MP4", "PNG", "SHA256SUMS"])
    runtime_doc = make(parent=parent_by_name["RUNTIME_ASSET_MANIFEST.json"],
                       runtime_routes=sorted(routes.values(), key=lambda row: row["url"]),
                       new_runtime_modules=[record(p) for p in NEW_MODULES],
                       existing_assets_reused=True, renderer_visual_source_modified=False)
    build_doc = make(parent=parent_by_name["BUILD_INPUT_MANIFEST.json"],
                     inherited_inputs_and_recipe=[verify_record(row) for row in inherited_docs["BUILD_INPUT_MANIFEST.json"]["entries"]],
                     dependency_locks=[verify_record(row) for row in inherited_docs["BUILD_INPUT_MANIFEST.json"]["dependency_locks"]],
                     input_inventory_references=previous_data,
                     retention="Original committed Git/LFS objects are retained; no live /tmp or /workspace input is required.")
    dependencies = inherited_docs["DEPENDENCY_MANIFEST.json"]
    dependency_doc = make(parent=parent_by_name["DEPENDENCY_MANIFEST.json"],
                          dependencies=dependencies["dependencies"], interpreters=dependencies["interpreters"],
                          observed_toolchain=installed, setup=dependencies["setup"],
                          dependency_locks=dependencies["dependency_locks"],
                          parser_provider=dependencies["parser_provider"], additional_runtime_dependencies=[],
                          python_procedures="Python standard library plus unchanged pinned baseline tools.")
    reproduction_doc = make(candidate_entrypoints=[record(p) for p in candidate if Path(p).suffix in {".py", ".mjs"}],
                            setup_recipe=dependencies["setup"],
                            python_requirements=record(ENGINE + "/recovery/v4/runtime/python-requirements.lock"),
                            interpreters=dependencies["interpreters"],
                            focused_test_argv=["node", "--test", *NEW_TESTS],
                            candidate_manifest_argv=["/usr/bin/python3", "-B", BASE + "/build_candidate_manifest.py", "--stage", stage],
                            fresh_render_reproduction="NOT_EXECUTED_BY_INVENTORY_TOOL",
                            clean_environment_final_gate="DEFERRED_UNTIL_USER_VIDEO_APPROVAL",
                            retained_input_manifest_references=parents,
                            proof=proof)
    return {"SOURCE_MANIFEST.json": source_doc, "FIXTURE_MANIFEST.json": fixture_doc,
            "DATA_MANIFEST.json": data_doc, "EVIDENCE_MANIFEST.json": evidence_doc,
            "RUNTIME_ASSET_MANIFEST.json": runtime_doc, "BUILD_INPUT_MANIFEST.json": build_doc,
            "DEPENDENCY_MANIFEST.json": dependency_doc, "IMPORT_MANIFEST.json": make(**graph),
            "REPRODUCTION_MANIFEST.json": reproduction_doc}, inherited_rows, parents


def inventory_of(documents, inherited_rows, parents):
    rows = {}
    def add(row):
        current = {key: row[key] for key in ("path", "sha256", "bytes")}
        if current["path"] in rows and rows[current["path"]] != current:
            raise ValueError("CONFLICTING_REQUIRED_FILE_HASH: " + current["path"])
        rows[current["path"]] = current
    def visit(value):
        if isinstance(value, dict):
            if all(key in value for key in ("path", "sha256", "bytes")):
                add(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for row in [*inherited_rows, *parents]:
        add(row)
    for document in documents.values():
        visit(document)
    for route in documents["RUNTIME_ASSET_MANIFEST.json"]["runtime_routes"]:
        add(record(route["file"]))
    return rows


def verify_persisted(path):
    actual = record(path)
    expected = HELPER.expected_body("HEAD", path)
    if any(actual[key] != expected[key] for key in ("sha256", "bytes")):
        raise ValueError("REQUIRED_FILE_NOT_SAVED_IN_HEAD: " + path)
    raw = git("show", ":" + path)
    pointer = LFS.fullmatch(raw)
    index = {"sha256": pointer[1].decode(), "bytes": int(pointer[2])} if pointer else {
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    if index != expected:
        raise ValueError("REQUIRED_FILE_INDEX_DIFFERS_FROM_HEAD: " + path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("inputs", "candidate"), default="inputs")
    parser.add_argument("--write-manifests", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--require-persisted", action="store_true",
                        help="Read-only HEAD/index body comparison; never executes the approval-only Permanent Gate")
    parser.add_argument("--exclude-postsave", action="append", default=[], metavar="REPOSITORY_RELATIVE_PATH")
    args = parser.parse_args()
    if args.inspect_only and (args.write_manifests or args.require_persisted):
        parser.error("--inspect-only cannot be combined with writes or persistence verification")
    postsave = set(DEFAULT_POSTSAVE)
    for path in args.exclude_postsave:
        if not path.startswith(BASE + "/evidence/") or Path(path).suffix != ".json" or ".." in Path(path).parts:
            parser.error("Post-save exclusions must be JSON records inside Candidate/evidence")
        postsave.add(path)
    docs, inherited_rows, parents = documents(args.stage, postsave)
    rows = inventory_of(docs, inherited_rows, parents)
    encoded = {name: encode(document) for name, document in docs.items()}
    for name, body in encoded.items():
        path = BASE + "/manifests/" + name
        rows[path] = {"path": path, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    inventory = sorted(rows.values(), key=lambda row: row["path"])
    encoded["HASH_MANIFEST.json"] = encode({"schema": 1, "scope": "EVENT_SYSTEM_V1_V3_VISUAL_DETAIL",
                                           "inventory_stage": args.stage, "required_files": inventory,
                                           "required_temp_only_files": [], "event_final": False,
                                           "user_video_approved": False, "permanent_gate_executed": False,
                                           "postsave_report_exclusions": sorted(postsave),
                                           "self_hash_policy": "HASH_MANIFEST.json and manifests/SHA256SUMS are excluded to prevent recursive hashes; their HEAD/index bodies can still be checked."})
    encoded["SHA256SUMS"] = "".join(row["sha256"] + "  " + row["path"] + "\n" for row in inventory).encode()
    target = REPO / BASE / "manifests"
    if args.write_manifests:
        target.mkdir(parents=True, exist_ok=True)
        for name, body in encoded.items():
            (target / name).write_bytes(body)
    if not args.inspect_only:
        for name, body in encoded.items():
            if (target / name).read_bytes() != body:
                raise ValueError("CANDIDATE_MANIFEST_STALE_OR_CHANGED: " + name)
    persistence_paths = sorted(set(rows) | {BASE + "/manifests/" + name for name in encoded})
    if args.require_persisted:
        for path in persistence_paths:
            verify_persisted(path)
    print(json.dumps({"scope": "EVENT_SYSTEM_V1_V3_VISUAL_DETAIL", "inventory_status": "PASS",
                      "inventory_stage": args.stage, "required_files": len(persistence_paths),
                      "new_engine_modules": len(NEW_MODULES), "focused_tests": len(NEW_TESTS),
                      "reachable_import_modules": len(docs["IMPORT_MANIFEST.json"]["reachable_modules"]),
                      "import_edges": len(docs["IMPORT_MANIFEST.json"]["edges"]),
                      "required_temp_only_files": 0, "head_and_index_compared": bool(args.require_persisted),
                      "permanent_gate_executed": False, "user_video_approved": False,
                      "event_final": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
