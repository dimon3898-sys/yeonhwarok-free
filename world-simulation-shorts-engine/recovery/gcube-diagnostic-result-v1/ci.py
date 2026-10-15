#!/usr/bin/env python3
"""CPU-only diagnostic-result patch build; immutable renderer and GPU admission."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = "world-simulation-shorts-engine/recovery/gcube-diagnostic-result-v1"
WORKFLOW = ".github/workflows/gcube-diagnostic-result.yml"
BRANCH = "development/gcube-diagnostic-result-20261015"
BASELINE = "d1f6041d4fdb97c5ac1c8245d3b8ce66821b3343"
PARENT_DIGEST = "sha256:119873aa8515622c3508e934247bd4a18e85d080e3f33696e66acc1bae874825"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
BASE = IMAGE + "@" + PARENT_DIGEST
DIAG_SOURCE = "world-simulation-shorts-engine/recovery/gcube-diagnostic-image-v1"
STORAGE_SOURCE = "world-simulation-shorts-engine/recovery/gcube-storage-fix-v1"
DIAG = "/opt/world-engine-startup-diagnostics"
STORAGE = "/opt/world-engine-storage-fix"
DEST = "/opt/world-engine-diagnostic-result"
PACKAGE = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1"
ENGINE = "/opt/rtx-package/repo/world-simulation-shorts-engine"
OLD_DIAG_SHA = "de56af52ab0655045efed69fbc7a1f3cdf2b99ade96e700e89cf8a0e6dcba59a"
OLD_STORAGE_SHA = "ecee5f20c68bb55ae9d63964befa30fd6209b21d7615bde52847de033ee62b30"
SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
UNCHANGED = {DIAG + "/records.py": "d5fb2ba1736a1febf6ff766aa1c3607a4ef6df25be2aacf85f7e2e62e14a4080",
    DIAG + "/service.py": "f7f0f6c57b8c7e5c856b5f013c615eac8d2cd71d9699dadbdebebe5adb477fd5",
    DIAG + "/healthcheck.py": "0f49a39d6158ff4012fa2bf172cf23b20cb6a922a20e15fb567942f500c557c5",
    STORAGE + "/storage.py": "ff8679bdbdf1f42f75b498ee9f68afa701346e4f535043bfdda9663005c130c1"}
PATCHES = {DIAG_SOURCE + "/startup.py": "startup.py", STORAGE_SOURCE + "/launch.py": "launch.py"}
sys.path.insert(0, str(HERE.parent / "rtx-image-build-v1"))


def helpers():
    import pipeline
    return pipeline


def run(args, *, timeout=120, **kwargs):
    return subprocess.run(args, text=True, check=True, capture_output=True, timeout=timeout, **kwargs).stdout


def state_path():
    return Path(os.environ.get("RESULT_CI_STATE") or str(Path(os.environ["RUNNER_TEMP"]) /
        ("result-state-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "-" + os.environ["RESULT_PHASE"] + ".json")))


def state():
    return json.loads(state_path().read_text()) if state_path().exists() else {
        "schema": "GCUBE_DIAGNOSTIC_RESULT_IMAGE_V1", "status": "IN_PROGRESS", "ciCommit": os.environ.get("GITHUB_SHA"),
        "parentImage": BASE, "gpuExecuted": False, "gCubeDeployed": False, "paidWorkExecuted": False,
        "finalModified": False, "rendererModified": False, "oldImagesDeleted": False,
        "imageBuilt": False, "imagePushed": False, "pullVerified": False}


def save(value):
    path = state_path(); path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".writing"); pending.write_text(json.dumps(value, indent=2) + "\n"); pending.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_log(text):
    text = str(text or "")[:65536]
    text = re.sub(r"(?i)(authorization|token|password|secret|credential)(\s*[:=]\s*)[^\s,}\"']+", r"\1\2[REDACTED]", text)
    text = re.sub(r"https?://[^\s]+", "[URL_REDACTED]", text)
    return re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+)", "[REDACTED]", text)


def preflight():
    if (os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("GITHUB_REPOSITORY") != "dimon3898-sys/yeonhwarok-free"
            or os.environ.get("RESULT_REPOSITORY_PRIVATE") != "false"
            or os.environ.get("RESULT_RUNNER_LABEL") != "ubuntu-24.04"
            or os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH):
        raise RuntimeError("FREE_PUBLIC_STANDARD_RUNNER_REQUIRED")
    identifier, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not all(re.fullmatch(r"[1-9][0-9]*", part) for part in (identifier, attempt)):
        raise RuntimeError("TRUSTED_RUN_ID_REQUIRED")
    if run(["git", "rev-parse", "HEAD"], cwd=REPO).strip() != os.environ["GITHUB_SHA"]:
        raise RuntimeError("CHECKOUT_COMMIT_MISMATCH")
    changed = run(["git", "diff", "--name-only", BASELINE, "HEAD"], cwd=REPO).splitlines()
    if any(p != WORKFLOW and p not in PATCHES and not p.startswith(NAMESPACE + "/") for p in changed):
        raise RuntimeError("PROTECTED_EXISTING_SOURCE_CHANGED")
    if run(["git", "status", "--porcelain"], cwd=REPO).strip(): raise RuntimeError("CLEAN_CHECKOUT_REQUIRED")
    value = state(); value.update(builder=helpers().require_space(), tag="rtx4080s-2f9158b-" + identifier + "-" + attempt,
        protection={"status": "PASS", "base": BASELINE, "changedFiles": changed, "allowedExistingPatches": sorted(PATCHES)},
        freeRunner={"publicRepository": True, "label": "ubuntu-24.04", "largerRunner": False})
    value["image"] = IMAGE + ":" + value["tag"]; save(value)


def guard():
    from registry_guard import RegistryGuard
    value = state(); value["tagCheck"] = RegistryGuard().check_tag(value["tag"]); save(value)


def manifests():
    old_diag = REPO / DIAG_SOURCE / "DIAGNOSTIC_FILES.json"
    old_storage = REPO / STORAGE_SOURCE / "STORAGE_FILES.json"
    if sha(old_diag) != OLD_DIAG_SHA or sha(old_storage) != OLD_STORAGE_SHA:
        raise RuntimeError("PINNED_PARENT_MANIFESTS_REQUIRED")
    for absolute, expected in UNCHANGED.items():
        relative = (DIAG_SOURCE if absolute.startswith(DIAG + "/") else STORAGE_SOURCE) + "/" + Path(absolute).name
        if sha(REPO / relative) != expected: raise RuntimeError("UNCHANGED_HELPER_HASH_MISMATCH")
    meta = {"parentDigest": PARENT_DIGEST, "sourceCommit": os.environ["GITHUB_SHA"]}
    diagnostic = {"schema": "WORLD_ENGINE_STARTUP_DIAGNOSTICS_FILES_V1", **meta, "previousManifestSha256": OLD_DIAG_SHA,
        "files": {name: sha(REPO / DIAG_SOURCE / name) for name in ("startup.py", "records.py", "service.py", "healthcheck.py")}}
    storage = {"schema": "WORLD_ENGINE_STORAGE_FILES_V1", **meta, "previousManifestSha256": OLD_STORAGE_SHA,
        "files": {name: sha(REPO / STORAGE_SOURCE / name) for name in ("storage.py", "launch.py")}}
    result = {"schema": "WORLD_ENGINE_DIAGNOSTIC_RESULT_FILES_V1", **meta, "helperSha256": sha(HERE / "recover_existing.py"),
        "patchedSources": {DIAG + "/startup.py": diagnostic["files"]["startup.py"], STORAGE + "/launch.py": storage["files"]["launch.py"]},
        "unchangedSources": UNCHANGED}
    return {"DIAGNOSTIC_FILES.json": diagnostic, "STORAGE_FILES.json": storage, "RESULT_FILES.json": result}


def test():
    helpers().require_space()
    host = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-p", "test_ci.py", "-v"],
        text=True, capture_output=True, timeout=60, check=False)
    value = state(); value["ciSafetyTests"] = {"exitCode": host.returncode, "stdout": safe_log(host.stdout), "stderr": safe_log(host.stderr), "scope": "NEW_CI_MOCKS_ONLY"}; save(value)
    if host.returncode: raise RuntimeError("NEW_CI_SAFETY_TESTS_FAILED")
    run(["docker", "pull", BASE], timeout=900)
    before = Path(os.environ["RUNNER_TEMP"]) / ("before-startup-" + value["tag"] + ".py")
    before.write_text(run(["git", "show", BASELINE + ":" + DIAG_SOURCE + "/startup.py"], cwd=REPO))
    command = ["docker", "run", "--rm", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256", "--restart=no", "--user=0:0",
        "--tmpfs", "/workspace:rw,mode=1777",
        "--entrypoint=/usr/bin/python3", "--mount", "type=bind,source=" + str(HERE) + ",target=" + DEST + ",readonly",
        "--mount", "type=bind,source=" + str(REPO / DIAG_SOURCE / "startup.py") + ",target=" + DIAG + "/startup.py,readonly",
        "--mount", "type=bind,source=" + str(REPO / STORAGE_SOURCE / "launch.py") + ",target=" + STORAGE + "/launch.py,readonly",
        "--mount", "type=bind,source=" + str(before) + ",target=/__ci/baseline_startup.py,readonly",
        "--env", "WORLD_ENGINE_TEST_BASELINE_STARTUP=/__ci/baseline_startup.py",
        "--env", "PYTHONPATH=" + DEST + ":" + STORAGE + ":" + DIAG + ":" + PACKAGE + ":" + ENGINE, BASE, "-B", "-c"]
    results = []
    for pattern in ("test_success_result.py", "test_failure_retention.py", "test_recovery.py"):
        code = ("import os,unittest; os.setgroups([]); os.setgid(1000); os.setuid(1000); "
            "s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + pattern + "'); "
            "r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>0 and not r.skipped else 1)")
        outcome = subprocess.run(command + [code], text=True, capture_output=True, timeout=180, check=False)
        results.append({"pattern": pattern, "exitCode": outcome.returncode, "stdout": safe_log(outcome.stdout), "stderr": safe_log(outcome.stderr)})
        value["focusedTests"] = {"exitCode": max(item["exitCode"] for item in results), "results": results,
            "scope": "ONLY_NEW_DIAGNOSTIC_RESULT_FAILURE_RECOVERY_TESTS_WITH_EXPLICIT_MOCKS_NO_GPU"}; save(value)
        if outcome.returncode: raise RuntimeError("FOCUSED_DIAGNOSTIC_RESULT_TESTS_FAILED")


def stage():
    value = state()
    if value.get("focusedTests", {}).get("exitCode") != 0: raise RuntimeError("FOCUSED_TESTS_REQUIRED")
    context = Path(os.environ["RUNNER_TEMP"]) / ("result-context-" + value["tag"]); context.mkdir(mode=0o700)
    for relative, target in PATCHES.items():
        source = REPO / relative
        if source.is_symlink() or not source.is_file(): raise RuntimeError("EXPLICIT_PATCH_FILE_REQUIRED")
        shutil.copyfile(source, context / target)
    for name in ("recover_existing.py", "Dockerfile"):
        source = HERE / name
        if source.is_symlink() or not source.is_file(): raise RuntimeError("EXPLICIT_HELPER_FILE_REQUIRED")
        shutil.copyfile(source, context / name)
    generated = manifests()
    for name, body in generated.items(): (context / name).write_text(json.dumps(body, indent=2) + "\n")
    value.update(context=str(context), manifests=generated, manifestSha256={name: sha(context / name) for name in generated},
        dockerfileSha256=sha(context / "Dockerfile"), explicitContextFiles=sorted(p.name for p in context.iterdir())); save(value)


def inspect_image(image):
    facts = json.loads(run(["docker", "image", "inspect", image]))[0]; config = facts.get("Config", {}); labels = config.get("Labels", {})
    if (facts.get("Os") != "linux" or facts.get("Architecture") != "amd64"
            or labels.get("org.opencontainers.image.revision") != "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
            or any(labels.get("world-engine." + part + ".source-revision") != os.environ["GITHUB_SHA"] for part in ("diagnostics", "storage", "result"))
            or labels.get("world-engine.result.parent-digest") != PARENT_DIGEST): raise RuntimeError("IMAGE_PROVENANCE_MISMATCH")
    if config.get("Entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", STORAGE + "/launch.py"]:
        raise RuntimeError("ORIGINAL_ENTRYPOINT_REQUIRED")
    if {v.partition("=")[0] for v in config.get("Env", [])} & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}:
        raise RuntimeError("CREDENTIAL_ENV_IN_IMAGE")
    return facts


def build():
    value = state(); value["builderBeforeBuild"] = helpers().require_space(); save(value)
    context = Path(value["context"])
    if set(p.name for p in context.iterdir()) != {"startup.py", "launch.py", "recover_existing.py", "Dockerfile", "DIAGNOSTIC_FILES.json", "STORAGE_FILES.json", "RESULT_FILES.json"}:
        raise RuntimeError("BUILD_CONTEXT_WHITELIST_VIOLATION")
    command = ["docker", "build", "--platform=linux/amd64", "--file", str(context / "Dockerfile")]
    for part in ("diagnostics", "storage", "result"):
        command += ["--label", "world-engine." + part + ".source-revision=" + os.environ["GITHUB_SHA"]]
    subprocess.run(command + ["--tag", value["image"], str(context)], check=True, timeout=600)
    facts = inspect_image(value["image"]); value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"], rootfsDiffIds=facts["RootFS"]["Layers"]); save(value)


def image_hashes(image):
    expected = manifests()
    code = """import hashlib,json,pathlib
roots={'DIAGNOSTIC_FILES.json':'/opt/world-engine-startup-diagnostics','STORAGE_FILES.json':'/opt/world-engine-storage-fix','RESULT_FILES.json':'/opt/world-engine-diagnostic-result'}
reports={}
for name,root in roots.items():
 p=pathlib.Path(root); m=json.loads((p/name).read_text()); reports[name]=m
 if name!='RESULT_FILES.json': assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())
 else:
  assert hashlib.sha256((p/'recover_existing.py').read_bytes()).hexdigest()==m['helperSha256']
  assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==h for n,h in {**m['patchedSources'],**m['unchangedSources']}.items())
print(json.dumps(reports))
"""
    actual = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3", image, "-B", "-c", code]))
    if actual != expected: raise RuntimeError("PATCHED_OR_UNCHANGED_SOURCE_HASH_MISMATCH")
    return actual


def fixture_root():
    root = Path(tempfile.mkdtemp(prefix="result-shared-", dir=os.environ["RUNNER_TEMP"])); root.chmod(0o777)
    code = "import os,pathlib; p=pathlib.Path('/fixture/rtx-gpu-package-v1'); p.mkdir(mode=0o755); os.chmod(p,0o755); s=p/'preserved-sentinel'; s.write_bytes(b'EXISTING_SHARED_DATA_UNCHANGED'); s.chmod(0o644)"
    run(["docker", "run", "--rm", "--network=none", "--user=0:0", "--entrypoint=/usr/bin/python3", "--mount", "type=bind,source=" + str(root) + ",target=/fixture", BASE, "-B", "-c", code])
    return root


def snapshot(root):
    leaf = root / "rtx-gpu-package-v1"; sentinel = leaf / "preserved-sentinel"
    return {"worldUid": root.stat().st_uid, "worldMode": root.stat().st_mode & 0o7777,
        "oldLeafUid": leaf.stat().st_uid, "oldLeafMode": leaf.stat().st_mode & 0o7777,
        "sentinelUid": sentinel.stat().st_uid, "sentinelMode": sentinel.stat().st_mode & 0o7777, "sentinelSha256": sha(sentinel)}


def json_lines(text):
    values = []
    for line in text.splitlines():
        try: value = json.loads(line)
        except ValueError: continue
        if isinstance(value, dict): values.append(value)
    return values


def diagnostic_case(image, root, *, as_root):
    args = ["docker", "create", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256", "--restart=no", "--shm-size=2g",
        "--mount", "type=bind,source=" + str(root) + ",target=/world-storage", "--env", "WORLD_ENGINE_STARTUP_MODE=diagnostic",
        "--env", "WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=45"]
    if not as_root: args += ["--user=1000:1000"]
    container = run(args + [image]).strip()
    if not re.fullmatch(r"[a-f0-9]{64}", container): raise RuntimeError("NEW_CONTAINER_ID_REQUIRED")
    report = {"case": "root-diagnostic-gpu-absence" if as_root else "unprivileged-first-error-preserved", "actualGPU": False, "mock": False}
    try:
        run(["docker", "start", container])
        if as_root:
            probe = """import json,urllib.request,urllib.error
o=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=o.open('http://127.0.0.1:8000/diagnostics',timeout=2); b=json.load(r)
assert r.status==200 and b['status']=='BLOCKED' and b['errorCode']=='GPU_HARDWARE_UNAVAILABLE'
assert b['gpuRenderingVerified'] is False and b['renderAllowed'] is False
print(json.dumps(b))
"""
            body = None
            for _ in range(120):
                result = subprocess.run(["docker", "exec", container, "/usr/bin/python3", "-B", "-c", probe], text=True, capture_output=True, timeout=5, check=False)
                if result.returncode == 0: body = json.loads(result.stdout); break
                time.sleep(0.5)
            if body is None: raise RuntimeError("DIAGNOSTIC_SERVICE_UNAVAILABLE")
            report["diagnostics"] = body
            endpoint = """import json,urllib.request,urllib.error
o=urllib.request.build_opener(urllib.request.ProxyHandler({})); v={}
for path,method,expected in [('/healthz','GET',200),('/readyz','GET',503),('/render','GET',404),('/render','POST',405)]:
 try: r=o.open(urllib.request.Request('http://127.0.0.1:8000'+path,method=method),timeout=2); s=r.status
 except urllib.error.HTTPError as e: s=e.code
 assert s==expected; v[method+' '+path]=s
print(json.dumps(v))
"""
            report["endpoints"] = json.loads(run(["docker", "exec", container, "/usr/bin/python3", "-B", "-c", endpoint]))
            live = None
            for _ in range(20):
                live = json.loads(run(["docker", "inspect", "--format", '{"restartCount":{{.RestartCount}},"running":{{.State.Running}},"health":"{{.State.Health.Status}}"}', container]))
                if live == {"restartCount": 0, "running": True, "health": "healthy"}: break
                time.sleep(0.5)
            if live != {"restartCount": 0, "running": True, "health": "healthy"}: raise RuntimeError("DIAGNOSTIC_LIVENESS_INVALID")
            report["runningState"] = live
            run(["docker", "stop", "--time", "5", container], timeout=10)
        report["exitCode"] = int(run(["docker", "wait", container], timeout=90).strip())
        expected_exit = 2 if as_root else 1
        if report["exitCode"] != expected_exit: raise RuntimeError("DIAGNOSTIC_EXIT_SEMANTICS_CHANGED")
        logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=10, check=True)
        report.update(stdout=safe_log(logs.stdout), stderr=safe_log(logs.stderr))
        failures = [v for v in json_lines(logs.stdout) if v.get("schema") == "WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1"]
        if not failures or failures[0].get("errorCode") != "GPU_HARDWARE_UNAVAILABLE": raise RuntimeError("FIRST_GPU_FAILURE_MUST_BE_PRESERVED")
        if as_root:
            if report["diagnostics"] != failures[0]: raise RuntimeError("HTTP_AND_CONSOLE_DIAGNOSTICS_DIFFER")
        elif not any(v.get("errorCode") == "UID_GID_FAILED" for v in failures[1:]): raise RuntimeError("SECONDARY_UID_FAILURE_REQUIRED")
        report["recordReadback"] = verify_records(container, failures[0], root_mode=as_root)
        report["status"] = "PASS"; return report
    except Exception as error:
        reason = str(error); report.update(status="FAIL", reasonCode=reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason) else "CASE_OPERATION_FAILED"); raise
    finally:
        try:
            logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=10, check=False)
            report.update(stdout=safe_log(logs.stdout), stderr=safe_log(logs.stderr))
            details = json.loads(run(["docker", "inspect", "--format", "{{json .State}}", container]))
            report["containerState"] = {key: details.get(key) for key in ("Status", "ExitCode", "OOMKilled")}
        except Exception: report["evidenceCapture"] = "PARTIAL"
        value = state(); value.setdefault("integrationAttempts", []).append(report); save(value)
        subprocess.run(["docker", "stop", "--time", "2", container], capture_output=True, timeout=5, check=False)
        subprocess.run(["docker", "rm", container], capture_output=True, timeout=10, check=False)


def verify_records(container, first, *, root_mode):
    # docker cp works after the process stops and never mutates original files.
    target = Path(tempfile.mkdtemp(prefix="result-readback-", dir=os.environ["RUNNER_TEMP"]))
    run(["docker", "cp", container + ":/var/lib/world-engine-private/engine", str(target / "private")])
    run(["docker", "cp", container + ":/world-storage", str(target / "shared")])
    matching = 0; secondary = 0
    for path in (target / "private").glob("session-*/startup-diagnostics/*.json"):
        if path.is_symlink() or path.stat().st_size > 131072 or path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError("PRIVATE_RECORD_UNSAFE")
        body = json.loads(path.read_text())
        if body == first: matching += 1
        if body.get("errorCode") == "UID_GID_FAILED": secondary += 1
    if not matching or (not root_mode and not secondary): raise RuntimeError("PRIVATE_FIRST_FAILURE_RECORD_REQUIRED")
    shared_first = []; shared_secondary = 0
    for path in (target / "shared").glob("world-engine-export-*/startup-safe-*.json"):
        if path.is_symlink() or path.stat().st_size > 131072: raise RuntimeError("SHARED_SAFE_RECORD_UNSAFE")
        body = json.loads(path.read_text())
        if body == first: shared_first.append({"sha256": sha(path), "bytes": path.stat().st_size})
        if body.get("errorCode") == "UID_GID_FAILED": shared_secondary += 1
    if not shared_first or (not root_mode and not shared_secondary): raise RuntimeError("SHARED_FIRST_FAILURE_RECORD_REQUIRED")
    return {"status": "PASS", "firstFailurePrivateCopies": matching, "secondaryUIDCopies": secondary,
        "firstFailureSharedCopies": shared_first, "secondaryUIDSharedCopies": shared_secondary,
        "mountedViewReadbackVerified": True, "remotePersistenceVerified": False, "externalDownloadVerified": False}


def secret_scan(image):
    value = state(); root = Path(os.environ["RUNNER_TEMP"]) / ("result-secret-scan-" + value["tag"]); root.mkdir(mode=0o700)
    container = run(["docker", "create", "--entrypoint=/bin/true", image]).strip()
    try:
        for source, name in [(DIAG + "/startup.py", "startup.py"), (STORAGE + "/launch.py", "launch.py"), (DEST + "/recover_existing.py", "recover_existing.py")]:
            run(["docker", "cp", container + ":" + source, str(root / name)])
    finally: run(["docker", "rm", container])
    shutil.copytree(HERE, root / "new-namespace", ignore=shutil.ignore_patterns("runs", "__pycache__")); shutil.copyfile(REPO / WORKFLOW, root / "workflow.yml")
    scanner_dir = Path(tempfile.mkdtemp(prefix="result-scanner-", dir=os.environ["RUNNER_TEMP"]))
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response: body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
    archive = scanner_dir / "archive.tar.gz"; archive.write_bytes(body); run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if sha(scanner) != SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    config = scanner_dir / "defaults.toml"; config.write_text("[extend]\nuseDefault = true\n")
    ignore = scanner_dir / "empty-ignore"; ignore.write_text(""); report = scanner_dir / "findings.json"
    outcome = subprocess.run([str(scanner), "dir", str(root), "--config", str(config), "--gitleaks-ignore-path", str(ignore), "--ignore-gitleaks-allow",
        "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"], text=True, capture_output=True, check=False, timeout=180)
    findings = json.loads(report.read_text()) if report.exists() and report.stat().st_size < 16 * 1024**2 else None
    value["secretScan"] = {"status": "PASS" if outcome.returncode == 0 and findings == [] else "FAIL", "findings": len(findings) if isinstance(findings,list) else None,
        "scannerExitCode": outcome.returncode, "scannerSha256": SCANNER_SHA, "scope": "actual patched two modules, new recovery helper, new namespace and workflow; parent audit reused"}; save(value)
    if value["secretScan"]["status"] != "PASS": raise RuntimeError("RESULT_SECRET_SCAN_FAILED")


def verify():
    value = state(); image = value["image"]; os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(image, hashes_only=True), imageHashes=image_hashes(image)); save(value)
    shared = fixture_root(); before = snapshot(shared); value["sharedStorageBefore"] = before; save(value)
    cases = [diagnostic_case(image, shared, as_root=True)]
    identity = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3", image, "-B", "-c",
        "import os,json; print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups()}))"]))
    if identity.get("uid") != 1000 or identity.get("gid") != 1000 or not isinstance(identity.get("groups"), list): raise RuntimeError("UID_IDENTITY_PROBE_INVALID")
    value["identityProbe"] = identity
    if identity["groups"]: cases.append(diagnostic_case(image, shared, as_root=False))
    else: value["unprivilegedGuard"] = {"status": "SKIP", "reasonCode": "NO_SUPPLEMENTARY_GROUPS_PRESENT"}
    after = snapshot(shared)
    if before != after: raise RuntimeError("EXISTING_SHARED_STORAGE_CHANGED")
    value.update(integrationCases=cases, sharedStorageProtection={"status": "PASS", "before": before, "after": after}, verification="PASS"); save(value); secret_scan(image)


def clean_auth(auth):
    (auth / "config.json").unlink(missing_ok=True); auth.rmdir()


def publish():
    from registry_guard import RegistryGuard
    value = state()
    if value.get("verification") != "PASS" or value.get("secretScan", {}).get("status") != "PASS" or value.get("secretScan", {}).get("findings") != 0:
        raise RuntimeError("VERIFICATION_AND_ZERO_SECRETS_REQUIRED")
    registry = RegistryGuard(); registry.check_tag(value["tag"]); auth, env = helpers().login(value)
    try:
        registry.check_tag(value["tag"]); output = run(["docker", "push", value["image"]], env=env, timeout=900)
        matches = re.findall(r"^" + re.escape(value["tag"]) + r": digest: (sha256:[a-f0-9]{64}) size: [0-9]+$", output, re.MULTILINE)
        if len(matches) != 1: raise RuntimeError("UNIQUE_PUSH_DIGEST_REQUIRED")
        value.update(imagePushed=True, imageDigest=matches[0]); save(value); remote = registry.inspect_digest(matches[0])
        if remote["configDigest"] != value["configDigest"]: raise RuntimeError("PUSHED_CONFIG_HASH_MISMATCH")
        value.update(registryVerification=remote, imageReference=IMAGE + "@" + remote["digest"], status="PUBLISHED_INDEPENDENT_PULL_PENDING"); save(value)
        with open(os.environ["GITHUB_OUTPUT"], "a") as outputs: outputs.write("tag=" + value["tag"] + "\ndigest=" + remote["digest"] + "\n")
    finally: clean_auth(auth)


def pull():
    from registry_guard import RegistryGuard, validate_digest, validate_tag
    value = state(); value["tag"] = validate_tag(os.environ["RESULT_PUBLISHED_TAG"]); value["imageDigest"] = validate_digest(os.environ["RESULT_PUBLISHED_DIGEST"])
    remote = RegistryGuard().inspect_digest(value["imageDigest"]); value["imageReference"] = IMAGE + "@" + remote["digest"]; save(value); auth, env = helpers().login(value)
    try: run(["docker", "pull", value["imageReference"]], env=env, timeout=900)
    finally: clean_auth(auth)
    facts = inspect_image(value["imageReference"])
    if facts["Id"] != remote["configDigest"]: raise RuntimeError("PULLED_CONFIG_HASH_MISMATCH")
    os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(value["imageReference"], hashes_only=True), imageHashes=image_hashes(value["imageReference"]),
        configDigest=facts["Id"], registryVerification=remote, pullVerified=True, imagePushed=True, status="DIAGNOSTIC_RESULT_IMAGE_CPU_VERIFIED"); save(value)


def persist():
    value = state(); value["stepOutcomes"] = json.loads(os.environ.get("RESULT_STEP_OUTCOMES", "{}"))
    if value.get("status") == "IN_PROGRESS" or any(x == "failure" for x in value["stepOutcomes"].values()): value["status"] = "DIAGNOSTIC_RESULT_BLOCKED"
    relative = NAMESPACE + "/runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "/" + os.environ["RESULT_PHASE"] + ".json"
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180); run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    output = REPO / relative
    if output.exists(): raise RuntimeError("EVIDENCE_OVERWRITE_FORBIDDEN")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(value, indent=2) + "\n")
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO); run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO)
    run(["git", "add", "--", relative], cwd=REPO)
    if run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines() != [relative]: raise RuntimeError("REPORT_ONLY_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: persist diagnostic result " + os.environ["RESULT_PHASE"] + " evidence [skip ci]"], cwd=REPO)
    run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("phase", choices=["preflight", "guard", "test", "stage", "build", "verify", "publish", "pull", "persist"]); args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = "RESULT_CI_OPERATION_FAILED"
        value = state(); value.update(status="DIAGNOSTIC_RESULT_BLOCKED", failedPhase=args.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError): value["failedCommandExitCode"] = error.returncode
        save(value); print(json.dumps({"status": "DIAGNOSTIC_RESULT_BLOCKED", "phase": args.phase, "reasonCode": code})); raise SystemExit(1)
