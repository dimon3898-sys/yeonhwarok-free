#!/usr/bin/env python3
"""Pin a small source closure and stage it without changing preserved sources.

This tool performs local, read-only Git object checks. It never fetches, merges,
installs dependencies, starts a renderer, or deploys a workload.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

SCHEMA = "RTX_GPU_SOURCE_CONTRACT_V1"
CPU_COMMIT = "a002d89492734bfa9d17b98145ee6cb9a3b366a2"
GLOW_COMMIT = "45af879d7417abba58e9ebd59d8e6630a785ac28"
PHASE_A_COMMIT = "21036824888dffbe232934d0332420c5910b98a4"
ENGINE = "world-simulation-shorts-engine"
CPU = ENGINE + "/recovery/astra-cpu-data-v1"
GLOW = ENGINE + "/recovery/moving-frontier-glow-fix-v1"
PACKAGE = ENGINE + "/recovery/rtx-gpu-package-v1"
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class ContractError(ValueError):
    """Missing, changed, conflicting or unsafe package source."""


def canonical_path(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ContractError("CANONICAL_REPO_PATH_REQUIRED")
    return value


def regular_bytes(root, relative, *, expected_size=None):
    relative = canonical_path(relative)
    try:
        root = Path(root).resolve(strict=True)
    except OSError as error:
        raise ContractError("SOURCE_ROOT_UNAVAILABLE") from error
    candidate = root
    for part in PurePosixPath(relative).parts:
        candidate /= part
        if candidate.is_symlink():
            raise ContractError("SOURCE_SYMLINK_FORBIDDEN: " + relative)
    try:
        fd = os.open(candidate, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ContractError("REGULAR_SOURCE_REQUIRED: " + relative)
            if info.st_size > MAX_FILE_BYTES or (expected_size is not None and info.st_size != expected_size):
                raise ContractError("SOURCE_SIZE_MISMATCH: " + relative)
            body = source.read(MAX_FILE_BYTES + 1)
            if len(body) != info.st_size:
                raise ContractError("SOURCE_CHANGED_WHILE_READING: " + relative)
            return body
    except OSError as error:
        raise ContractError("SOURCE_UNAVAILABLE: " + relative) from error


def digest(body):
    return hashlib.sha256(body).hexdigest()


def git_read(repo, arguments, *, timeout=60):
    """Use existing local objects only; missing objects fail without fetching."""
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "-C", str(repo), *arguments],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContractError("LOCAL_GIT_OBJECT_CHECK_UNAVAILABLE") from error
    if result.returncode:
        raise ContractError("LOCAL_GIT_OBJECT_OR_ANCESTRY_UNAVAILABLE")
    return result.stdout


def validate_contract(contract):
    if not isinstance(contract, dict) or contract.get("schema") != SCHEMA:
        raise ContractError("SOURCE_CONTRACT_SCHEMA_REQUIRED")
    records = contract.get("files")
    if not isinstance(records, list) or not records or len(records) > 2048:
        raise ContractError("NONEMPTY_EXPLICIT_FILE_LIST_REQUIRED")
    seen, total = set(), 0
    for record in records:
        if not isinstance(record, dict):
            raise ContractError("FILE_RECORD_REQUIRED")
        path = canonical_path(record.get("repoPath"))
        if path in seen or path.startswith(PACKAGE + "/") or "/.git/" in "/" + path + "/":
            raise ContractError("DUPLICATE_OR_OVERLAY_SOURCE_PATH")
        seen.add(path)
        size = record.get("bytes")
        hash_value = record.get("sha256")
        if (type(size) is not int or not 0 <= size <= MAX_FILE_BYTES
                or not isinstance(hash_value, str) or not SHA.fullmatch(hash_value)):
            raise ContractError("VALID_SOURCE_DIGEST_AND_SIZE_REQUIRED")
        commits = record.get("sourceCommits")
        if (not isinstance(commits, list) or not commits or not all(
                isinstance(c, str) and COMMIT.fullmatch(c) for c in commits)
                or len(set(commits)) != len(commits)):
            raise ContractError("PINNED_SOURCE_COMMIT_REQUIRED")
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ContractError("SOURCE_BYTE_LIMIT_EXCEEDED")
    routes = contract.get("runtimeRoutes", [])
    if not isinstance(routes, list):
        raise ContractError("RUNTIME_ROUTE_LIST_REQUIRED")
    route_seen = set()
    for route in routes:
        if not isinstance(route, dict) or not isinstance(route.get("url"), str) or not route["url"].startswith("/"):
            raise ContractError("RUNTIME_ROUTE_RECORD_REQUIRED")
        url = route["url"]
        if any(c in url for c in ("\\", "\x00", "?", "#")) or any(p in {".", ".."} for p in url.split("/")):
            raise ContractError("CANONICAL_RUNTIME_ROUTE_REQUIRED")
        if route["url"] in route_seen or canonical_path(route.get("repoPath")) not in seen:
            raise ContractError("UNBOUND_OR_DUPLICATE_RUNTIME_ROUTE")
        route_seen.add(route["url"])
    by_path = {r["repoPath"]: r for r in records}
    authorities = contract.get("manifestSha256", {})
    if not isinstance(authorities, dict) or any(path not in by_path or value != by_path[path]["sha256"]
            for path, value in authorities.items()):
        raise ContractError("MANIFEST_AUTHORITY_HASH_CONTRADICTION")
    edges = contract.get("literalImportEdges", [])
    if not isinstance(edges, list) or not all(isinstance(edge, dict) and edge.get("from") in seen
            and edge.get("to") in seen for edge in edges):
        raise ContractError("UNBOUND_LITERAL_IMPORT_DEPENDENCY")
    policy = contract.get("runtimePolicy", {})
    if not isinstance(policy, dict) or not isinstance(policy.get("activeEntrypoints", []), list):
        raise ContractError("ACTIVE_ENTRYPOINT_POLICY_REQUIRED")
    for path in policy.get("activeEntrypoints", []):
        if not canonical_path(path).startswith(PACKAGE + "/"):
            raise ContractError("NEW_PACKAGE_ACTIVE_ENTRYPOINT_REQUIRED")
    ancestry = contract.get("ancestry", [])
    if not isinstance(ancestry, list) or not all(isinstance(a, dict)
            and isinstance(a.get("ancestor"), str) and COMMIT.fullmatch(a["ancestor"])
            and isinstance(a.get("descendant"), str) and COMMIT.fullmatch(a["descendant"]) for a in ancestry):
        raise ContractError("PINNED_ANCESTRY_REQUIRED")
    return records


def verify_contract(repo, contract, *, check_git=True):
    records = validate_contract(contract)
    if check_git:
        for relation in contract.get("ancestry", []):
            git_read(repo, ["merge-base", "--is-ancestor", relation["ancestor"], relation["descendant"]])
    for record in records:
        body = regular_bytes(repo, record["repoPath"], expected_size=record["bytes"])
        if digest(body) != record["sha256"]:
            raise ContractError("SOURCE_HASH_MISMATCH: " + record["repoPath"])
        if check_git:
            for commit in record["sourceCommits"]:
                size = git_read(repo, ["cat-file", "-s", commit + ":" + record["repoPath"]]).strip()
                if size != str(record["bytes"]).encode("ascii"):
                    raise ContractError("PINNED_GIT_BLOB_SIZE_MISMATCH: " + record["repoPath"])
                blob = git_read(repo, ["cat-file", "blob", commit + ":" + record["repoPath"]])
                if len(blob) != record["bytes"] or digest(blob) != record["sha256"]:
                    raise ContractError("PINNED_GIT_BLOB_MISMATCH: " + record["repoPath"])
    return {"status": "PASS", "files": len(records), "bytes": sum(r["bytes"] for r in records),
            "gitBlobVerification": check_git, "networkRequests": 0, "merges": 0}


def _json(repo, path):
    try:
        return json.loads(regular_bytes(repo, path))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("SOURCE_MANIFEST_INVALID: " + path) from error


def _js_imports(body):
    text = body.decode("utf-8")
    patterns = [r"\b(?:import|export)\s+[\w*{},\s]+?\s+from\s*['\"]([^'\"]+)['\"]",
                r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
                r"\bimport\s*['\"]([^'\"]+)['\"]"]
    return sorted({m for pattern in patterns for m in re.findall(pattern, text)})


def _js_path(parent, specifier):
    if specifier.startswith("."):
        # Resolve dot segments inside the repository, never outside it.
        parts = list(PurePosixPath(parent).parent.parts)
        for part in specifier.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise ContractError("IMPORT_OUTSIDE_REPOSITORY")
                parts.pop()
            else:
                parts.append(part)
        return canonical_path("/".join(parts))
    if specifier.startswith("/modules/"):
        return canonical_path(ENGINE + "/web/map_infographic_v1/" + specifier.removeprefix("/modules/"))
    if specifier == "/three.js":
        return ENGINE + "/web/vendor/three/0.170.0/three.module.js"
    if specifier.startswith("/"):
        raise ContractError("UNDECLARED_ABSOLUTE_MODULE_ROUTE: " + specifier)
    return None  # Node builtins and installed packages are dependency-lock inputs.


def _python_imports(path, body):
    result = set()
    try:
        tree = ast.parse(body, filename=path)
    except (SyntaxError, UnicodeError) as error:
        raise ContractError("SOURCE_PYTHON_PARSE_FAILED: " + path) from error
    for node in ast.walk(tree):
        modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for module in modules:
            if isinstance(node, ast.ImportFrom) and node.level:
                parts = list(PurePosixPath(path).parent.parts)
                for _ in range(node.level - 1):
                    if not parts:
                        raise ContractError("IMPORT_OUTSIDE_REPOSITORY")
                    parts.pop()
                target = "/".join(parts + module.split(".")) if module else "/".join(parts) + "/__init__"
                result.add(target + ".py")
            elif module.startswith("deployment."):
                result.add(ENGINE + "/" + module.replace(".", "/") + ".py")
                result.add(ENGINE + "/deployment/__init__.py")
                result.add(ENGINE + "/deployment/gcube/__init__.py")
            elif module.startswith("astra_cpu."):
                result.add(CPU + "/" + module.replace(".", "/") + ".py")
    return sorted(result)


def generate_contract(repo, *, check_git=True):
    """Build an explicit closure from pinned manifests and literal imports."""
    repo = Path(repo).resolve(strict=True)
    selected = {}
    authorities = {}

    def add(path, commit, role, *, expected=None, authority=None):
        path = canonical_path(path)
        body = regular_bytes(repo, path)
        actual = {"sha256": digest(body), "bytes": len(body)}
        if expected and (expected["sha256"] != actual["sha256"] or expected["bytes"] != actual["bytes"]):
            raise ContractError("MANIFEST_SOURCE_CONFLICT: " + path)
        if path in selected:
            record = selected[path]
            if record["sha256"] != actual["sha256"] or record["bytes"] != actual["bytes"]:
                raise ContractError("SOURCE_CONFLICT_NO_MERGE: " + path)
            if commit not in record["sourceCommits"]:
                record["sourceCommits"].append(commit)
            if role not in record["roles"]:
                record["roles"].append(role)
            if authority and authority not in record["authorities"]:
                record["authorities"].append(authority)
            return
        selected[path] = {"repoPath": path, **actual, "sourceCommits": [commit],
                          "roles": [role], "authorities": [authority] if authority else [],
                          "imagePath": "/opt/rtx-package/repo/" + path}

    def manifest(path, commit):
        value = _json(repo, path)
        authorities[path] = digest(regular_bytes(repo, path))
        add(path, commit, "provenance_manifest")
        return value

    cpu_manifest = manifest(CPU + "/SOURCE_ASSET_MANIFEST.json", CPU_COMMIT)
    for record in cpu_manifest["files"]:
        path = record["path"]
        if ((path.startswith("astra_cpu/") and path.endswith(".py")) or path == "prepare_data.py"
                or (path.endswith(".json") and (path.startswith("fixtures/") or path == "DEPENDENCIES.json"))):
            add(CPU + "/" + path, CPU_COMMIT, "cpu_preparation", expected=record,
                authority=CPU + "/SOURCE_ASSET_MANIFEST.json")
    input_manifest_path = ENGINE + "/recovery/astra-map-quality-v1/inputs/INPUT_MANIFEST.json"
    for record in manifest(input_manifest_path, CPU_COMMIT)["files"]:
        add(record["path"], CPU_COMMIT, "original_astra_input", expected=record, authority=input_manifest_path)

    runtime_path, source_path = GLOW + "/manifests/RUNTIME_ASSET_MANIFEST.json", GLOW + "/manifests/SOURCE_MANIFEST.json"
    runtime, source = manifest(runtime_path, GLOW_COMMIT), manifest(source_path, GLOW_COMMIT)
    for field in ("declared_runtime_module_bodies", "asset_bodies", "native_input_bodies",
                  "inherited_visual_admission_bodies", "additional_runtime_asset_bodies"):
        for record in runtime[field]:
            add(record["path"], GLOW_COMMIT, field, expected=record, authority=runtime_path)
    server = runtime["loopback_server"]
    add(server["path"], GLOW_COMMIT, "loopback_server", expected=server, authority=runtime_path)
    for record in source["entries"]:
        if record["path"].startswith(GLOW + "/") and Path(record["path"]).name in {
                "reference_runtime.mjs", "render_proof.mjs", "probe_native.mjs", "build_fixture.mjs"}:
            add(record["path"], GLOW_COMMIT, "preserved_cpu_reproduction_source", expected=record, authority=source_path)
    hash_path = GLOW + "/manifests/HASH_MANIFEST.json"
    for record in manifest(hash_path, GLOW_COMMIT)["required_files"]:
        if record["path"].startswith(GLOW + "/fixtures/") or record["path"] in {
                GLOW + "/evidence/VISUAL_ADMISSION.json",
                ENGINE + "/recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json"}:
            add(record["path"], GLOW_COMMIT, "glow_fixture_or_admission", expected=record, authority=hash_path)

    explicit = ["cinematic-world-map/package.json", "cinematic-world-map/package-lock.json",
                ENGINE + "/recovery/v5/index.html", ENGINE + "/recovery/v5/harness.mjs",
                ENGINE + "/web/vendor/three/0.170.0/LICENSE", ENGINE + "/web/fonts/LICENSE_Noto_CJK.txt",
                "cinematic-world-map/assets/gis/natural-earth-license.html",
                ENGINE + "/web/fonts/SOURCE.json", "cinematic-world-map/assets/three-globe-MIT.txt",
                "cinematic-world-map/assets/v3/CREDITS_V3.txt", "cinematic-world-map/assets/v3/earth/SOURCES_V3.json",
                ENGINE + "/assets/flat/NATURAL_EARTH_PUBLIC_DOMAIN.txt", ENGINE + "/assets/flat/SOURCES.json",
                "cinematic-world-map/assets/SOURCES.json"]
    explicit += [GLOW + "/evidence/native_probe/" + n + ".png" for n in ("000", "074", "149")]
    for path in explicit:
        add(path, GLOW_COMMIT, "explicit_runtime_support_or_license")
    for name in ("__init__.py", "gpu.py", "gpu_access.py", "gpu_runtime_facts.py", "gpu_probe.mjs",
                 "chromium_wrapper.py", "graphics_runtime.py", "graphics_start.py"):
        add(ENGINE + "/deployment/gcube/" + name, CPU_COMMIT, "reused_gpu_admission")
    for name in ("PROTECTION_RESULTS.json", "PERSISTENCE_RECEIPT.json",
                 "FRESH_WORKTREE_REPRODUCTION.json", "G_ALL_TEST_RESULTS.json"):
        add(CPU + "/evidence/" + name, CPU_COMMIT, "prior_cpu_protection_or_validation_receipt")
    for name in ("BASELINE_BINDINGS.json", "INPUT_INTEGRITY.json"):
        add(ENGINE + "/recovery/astra-map-quality-v1/evidence/" + name, CPU_COMMIT,
            "prior_original_input_or_baseline_receipt")
    for relative in ("evidence/proof/CAPTURE_STATUS.json", "CHECKPOINT_STATUS.json",
                     "manifests/FIXTURE_MANIFEST.json", "manifests/DEPENDENCY_MANIFEST.json"):
        add(GLOW + "/" + relative, GLOW_COMMIT, "prior_glow_fixture_or_capture_receipt")

    # Recursively capture literal source imports; dynamic browser routes are bound
    # separately by the persisted runtime manifest and explicit server inputs.
    scanned = set()
    import_edges = []
    while set(selected) - scanned:
        path = sorted(set(selected) - scanned)[0]
        scanned.add(path)
        if path.endswith((".mjs", ".js")):
            imports = [_js_path(path, s) for s in _js_imports(regular_bytes(repo, path))]
        elif path.endswith(".py"):
            imports = _python_imports(path, regular_bytes(repo, path))
        else:
            continue
        for target in sorted({p for p in imports if p is not None}):
            for commit in list(selected[path]["sourceCommits"]):
                add(target, commit, "literal_import_dependency")
            import_edges.append({"from": path, "to": target})
    routes = [{"url": r["url"], "repoPath": r["file"]} for r in runtime["runtime_routes"]]
    routes.extend([{"url": "/", "repoPath": ENGINE + "/recovery/v5/index.html"},
                   {"url": "/index.html", "repoPath": ENGINE + "/recovery/v5/index.html"},
                   {"url": "/harness.mjs", "repoPath": ENGINE + "/recovery/v5/harness.mjs"}])
    archive = ENGINE + "/recovery/astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip"
    with zipfile.ZipFile(repo / archive) as z:
        license_members = [{"member": n, "sha256": digest(z.read(n)), "bytes": z.getinfo(n).file_size}
                           for n in ("README.txt", "licenses/ATTRIBUTION.txt", "licenses/LICENSE_EVIDENCE.md",
                                     "licenses/License-COPDEM-30.pdf")]
    contract = {"schema": SCHEMA, "sourceCommits": {"cpu": CPU_COMMIT, "glow": GLOW_COMMIT},
                "ancestry": [{"ancestor": GLOW_COMMIT, "descendant": CPU_COMMIT},
                             {"ancestor": PHASE_A_COMMIT, "descendant": CPU_COMMIT}],
                "manifestSha256": authorities, "runtimeRoutes": routes, "literalImportEdges": import_edges,
                "originalArchiveLicenses": {"repoPath": archive, "members": license_members,
                                            "preservation": "Inside the original unchanged ZIP; no extraction or re-encoding."},
                "runtimePolicy": {"activeEntrypoints": [PACKAGE + "/bootstrap.py", PACKAGE + "/gpu_launcher.py",
                                                        PACKAGE + "/hardware_runtime.mjs", PACKAGE + "/hardware_render.mjs"],
                                  "preservedReproductionSourcesInactive": True, "wholeRepositoryCopied": False,
                                  "nodeModulesCopied": False, "heightSourcePresent": runtime["height_source_present"],
                                  "unselectedServerRoute": "/height.f32",
                                  "preservedLegacyGitDependentRenderProof": True},
                "files": [selected[p] for p in sorted(selected)]}
    verify_contract(repo, contract, check_git=check_git)
    return contract


def _publish_new_directory(source, destination):
    """Linux atomic no-replace publication, including concurrent stage calls."""
    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError as error:
        raise ContractError("ATOMIC_NO_REPLACE_RENAME_UNAVAILABLE") from error
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise ContractError("CONTEXT_DESTINATION_APPEARED")
        raise ContractError("ATOMIC_CONTEXT_PUBLICATION_FAILED") from OSError(error, os.strerror(error))


def stage_context(repo, contract, destination, *, package_files=(), check_git=True):
    """Stage only verified source records and explicitly named new package files."""
    repo, requested_destination = Path(repo).resolve(strict=True), Path(destination).absolute()
    if any(p.is_symlink() for p in [requested_destination, *requested_destination.parents]):
        raise ContractError("CONTEXT_SYMLINK_FORBIDDEN")
    destination = requested_destination.resolve(strict=False)
    if destination == repo or repo in destination.parents or destination in repo.parents:
        raise ContractError("CONTEXT_MUST_BE_OUTSIDE_CHECKOUT")
    if destination.exists() or destination.is_symlink():
        raise ContractError("NEW_EMPTY_CONTEXT_DESTINATION_REQUIRED")
    verification = verify_contract(repo, contract, check_git=check_git)
    overlay = []
    for value in package_files:
        relative = canonical_path(value)
        if not relative.startswith(PACKAGE + "/") or relative in {r["repoPath"] for r in overlay}:
            raise ContractError("EXPLICIT_UNIQUE_NEW_PACKAGE_FILE_REQUIRED")
        body = regular_bytes(repo, relative)
        overlay.append({"repoPath": relative, "sha256": digest(body), "bytes": len(body),
                        "mode": stat.S_IMODE((repo / relative).stat().st_mode) & 0o777})
        if (len(contract["files"]) + len(overlay) > 2048
                or sum(r["bytes"] for r in contract["files"]) + sum(r["bytes"] for r in overlay) > MAX_TOTAL_BYTES):
            raise ContractError("STAGED_CONTEXT_COUNT_OR_BYTE_LIMIT_EXCEEDED")
    required = contract.get("runtimePolicy", {}).get("activeEntrypoints", [])
    if not isinstance(required, list) or not all(canonical_path(p) in {r["repoPath"] for r in overlay} for p in required):
        raise ContractError("EXPLICIT_ACTIVE_ENTRYPOINT_OVERLAY_REQUIRED")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="." + destination.name + "-", dir=destination.parent))
    try:
        copied = []
        for record in [*contract["files"], *overlay]:
            body = regular_bytes(repo, record["repoPath"], expected_size=record["bytes"])
            if digest(body) != record["sha256"]:
                raise ContractError("SOURCE_CHANGED_DURING_STAGING: " + record["repoPath"])
            target = temporary / "repo" / record["repoPath"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            os.chmod(target, record.get("mode", stat.S_IMODE((repo / record["repoPath"]).stat().st_mode)) & 0o777)
            copied.append({"repoPath": record["repoPath"], "sha256": record["sha256"], "bytes": record["bytes"]})
        contract_body = (json.dumps(contract, indent=2) + "\n").encode()
        receipt = {"schema": "RTX_GPU_STAGED_CONTEXT_V1", "status": "PASS", "sourceVerification": verification,
                   "contractSha256": digest(contract_body),
                   "files": copied, "packageOverlay": overlay, "networkRequests": 0,
                   "gpuExecuted": False, "deployed": False}
        (temporary / "source_contract.json").write_bytes(contract_body)
        (temporary / "STAGING_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if destination.exists() or destination.is_symlink():
            raise ContractError("CONTEXT_DESTINATION_APPEARED")
        _publish_new_directory(temporary, destination)
        return receipt
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_staged_context(package_root="/opt/rtx-package", *, require_git_receipt=True):
    """Verify shipped sources without Git, network, rendering or GPU probes.

    Original commits are verified while staging. This check binds all immutable
    original and new package bytes to that receipt; it does not authenticate an
    untrusted receipt or prove GPU availability. Pin the built image digest too.
    """
    root = Path(package_root)
    if root.is_symlink():
        raise ContractError("PACKAGE_ROOT_SYMLINK_FORBIDDEN")
    try:
        contract_body = regular_bytes(root, "source_contract.json")
        contract = json.loads(contract_body)
        receipt = json.loads(regular_bytes(root, "STAGING_RECEIPT.json"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("STAGED_CONTRACT_OR_RECEIPT_INVALID") from error
    originals = validate_contract(contract)
    contract_hash = digest(contract_body)
    if (not isinstance(receipt, dict) or receipt.get("schema") != "RTX_GPU_STAGED_CONTEXT_V1"
            or receipt.get("status") != "PASS" or receipt.get("contractSha256") != contract_hash
            or receipt.get("gpuExecuted") is not False or receipt.get("deployed") is not False
            or receipt.get("networkRequests") != 0):
        raise ContractError("STAGING_RECEIPT_CONTRADICTION")
    verification = receipt.get("sourceVerification", {})
    if (not isinstance(verification, dict) or verification.get("status") != "PASS"
            or verification.get("files") != len(originals)
            or verification.get("bytes") != sum(r["bytes"] for r in originals)
            or verification.get("networkRequests") != 0 or verification.get("merges") != 0
            or (require_git_receipt and verification.get("gitBlobVerification") is not True)):
        raise ContractError("PINNED_SOURCE_VERIFICATION_RECEIPT_REQUIRED")
    overlay = receipt.get("packageOverlay")
    if not isinstance(overlay, list):
        raise ContractError("PACKAGE_OVERLAY_RECEIPT_REQUIRED")
    expected = {r["repoPath"]: {k: r[k] for k in ("repoPath", "sha256", "bytes")} for r in originals}
    for record in overlay:
        if not isinstance(record, dict):
            raise ContractError("PACKAGE_OVERLAY_RECORD_REQUIRED")
        path = canonical_path(record.get("repoPath"))
        size = record.get("bytes")
        if (not path.startswith(PACKAGE + "/") or path in expected
                or not isinstance(record.get("sha256"), str) or not SHA.fullmatch(record["sha256"]) or type(size) is not int
                or not 0 <= size <= MAX_FILE_BYTES):
            raise ContractError("PACKAGE_OVERLAY_IDENTITY_INVALID")
        expected[path] = {k: record[k] for k in ("repoPath", "sha256", "bytes")}
        if len(expected) > 2048 or sum(r["bytes"] for r in expected.values()) > MAX_TOTAL_BYTES:
            raise ContractError("STAGED_CONTEXT_COUNT_OR_BYTE_LIMIT_EXCEEDED")
    required = contract.get("runtimePolicy", {}).get("activeEntrypoints", [])
    if not isinstance(required, list) or not all(canonical_path(p) in expected for p in required):
        raise ContractError("STAGED_ACTIVE_ENTRYPOINT_REQUIRED")
    copied = receipt.get("files")
    if not isinstance(copied, list) or len(copied) != len(expected):
        raise ContractError("STAGED_FILE_INVENTORY_MISMATCH")
    observed = set()
    for record in copied:
        if (not isinstance(record, dict) or record.get("repoPath") in observed
                or expected.get(record.get("repoPath")) != record):
            raise ContractError("STAGED_FILE_INVENTORY_MISMATCH")
        observed.add(record["repoPath"])
    repo = root / "repo"
    verify_contract(repo, contract, check_git=False)
    for record in overlay:
        body = regular_bytes(repo, record["repoPath"], expected_size=record["bytes"])
        if digest(body) != record["sha256"]:
            raise ContractError("PACKAGE_OVERLAY_HASH_MISMATCH: " + record["repoPath"])
    return {"status": "PASS", "files": len(expected), "sourceContractSha256": contract_hash,
            "sourceCommits": contract.get("sourceCommits", {}), "gpuExecuted": False,
            "gitQueries": 0, "networkRequests": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--contract", type=Path, required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--contract", type=Path, required=True)
    stage.add_argument("--destination", type=Path, required=True)
    stage.add_argument("--package-file", action="append", default=[])
    context = commands.add_parser("verify-context")
    context.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            contract = generate_contract(args.repo)
            args.output.write_text(json.dumps(contract, indent=2) + "\n")
            result = {"status": "PASS", "files": len(contract["files"]), "output": str(args.output)}
        elif args.command == "verify-context":
            result = verify_staged_context(args.package_root)
        else:
            contract = json.loads(args.contract.read_text())
            result = verify_contract(args.repo, contract) if args.command == "verify" else stage_context(
                args.repo, contract, args.destination, package_files=args.package_file)
            result = {k: v for k, v in result.items() if k != "packageOverlay" and not (k == "files" and isinstance(v, list))}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
