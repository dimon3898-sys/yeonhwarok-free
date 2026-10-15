#!/usr/bin/env python3
"""One-file bounded REPORT reader patch; reuse the proven free CI controls."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = "world-simulation-shorts-engine/recovery/gcube-65422-render-v1"
WORKFLOW = ".github/workflows/gcube-65422-render.yml"
BRANCH = "development/gcube-65422-render-prep-20261015"
BASELINE = "51fba453ce2b9a0fc8ed9e9062bd993fe0489ccc"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
PARENT_DIGEST = "sha256:e7245bdd73c99eff806effdfd1f5ba6765fcffdc2d64fbdb52c360e79148dff3"
BASE = IMAGE + "@" + PARENT_DIGEST
OLD_STORAGE_SHA = "1b0481cd1f2ccb6fc10fa06b3eed3ca4e5177dc755feacb5e7e839adfb85ddc3"
OLD_DIAG_SHA = "1299b2a789ffcff29a69269cdc31801b7261085cc571b35324a59336bfdb658c"
OLD_RESULT_SHA = "3f4b8d692a81d45cecdd390076141fcc47de488caf160389c1c043c08d978a1e"
PARENT_SOURCE = "eb937ec312cd60af147b7333677c5e5f10bd687e"
STORAGE_SOURCE = "world-simulation-shorts-engine/recovery/gcube-storage-fix-v1/storage.py"
STORAGE = "/opt/world-engine-storage-fix"
DIAG = "/opt/world-engine-startup-diagnostics"
RESULT = "/opt/world-engine-diagnostic-result"
DEST = "/opt/world-engine-65422-render"
PARENT_NAMESPACE = HERE.parent / "gcube-diagnostic-result-v1"
spec = importlib.util.spec_from_file_location("render_parent_cpu_orchestration", PARENT_NAMESPACE / "ci.py")
orchestration = importlib.util.module_from_spec(spec); spec.loader.exec_module(orchestration)
# This isolated imported CI module has configuration globals. No production
# module, existing source file, Docker image or protected API is changed here.
for key, value in {"HERE": HERE, "REPO": REPO, "NAMESPACE": NAMESPACE, "WORKFLOW": WORKFLOW,
        "BRANCH": BRANCH, "BASELINE": BASELINE, "PARENT_DIGEST": PARENT_DIGEST, "BASE": BASE,
        "PATCHES": {STORAGE_SOURCE: "storage.py"}}.items(): setattr(orchestration, key, value)
run = orchestration.run
save = orchestration.save
state_path = orchestration.state_path
sha = orchestration.sha
safe_log = orchestration.safe_log
helpers = orchestration.helpers
preflight = orchestration.preflight
guard = orchestration.guard
publish = orchestration.publish


def state():
    if state_path().exists(): return json.loads(state_path().read_text())
    return {"schema": "GCUBE_65422_RENDER_PREP_IMAGE_V1", "status": "IN_PROGRESS", "ciCommit": os.environ.get("GITHUB_SHA"),
        "parentImage": BASE, "gpuExecuted": False, "gCubeDeployed": False, "paidWorkExecuted": False,
        "rendererModified": False, "finalModified": False, "oldImagesDeleted": False,
        "imageBuilt": False, "imagePushed": False, "pullVerified": False}


orchestration.state = state


def manifests():
    directory = PARENT_NAMESPACE / "image-manifests"
    for name, expected in [("STORAGE_FILES.json", OLD_STORAGE_SHA), ("DIAGNOSTIC_FILES.json", OLD_DIAG_SHA), ("RESULT_FILES.json", OLD_RESULT_SHA)]:
        if sha(directory / name) != expected: raise RuntimeError("PINNED_PARENT_MANIFEST_REQUIRED")
    old_diag = json.loads((directory / "DIAGNOSTIC_FILES.json").read_text())
    old_storage = json.loads((directory / "STORAGE_FILES.json").read_text())
    old_result = json.loads((directory / "RESULT_FILES.json").read_text())
    unchanged = {DIAG + "/" + name: digest for name, digest in old_diag["files"].items()}
    unchanged[STORAGE + "/launch.py"] = old_storage["files"]["launch.py"]
    unchanged[RESULT + "/recover_existing.py"] = old_result["helperSha256"]
    for deployed, expected in unchanged.items():
        namespace = "gcube-diagnostic-image-v1" if deployed.startswith(DIAG) else ("gcube-storage-fix-v1" if deployed.startswith(STORAGE) else "gcube-diagnostic-result-v1")
        if sha(HERE.parent / namespace / Path(deployed).name) != expected: raise RuntimeError("UNCHANGED_HELPER_HASH_MISMATCH")
    storage = {"schema": "WORLD_ENGINE_STORAGE_FILES_V1", "parentDigest": PARENT_DIGEST, "sourceCommit": os.environ["GITHUB_SHA"],
        "previousManifestSha256": OLD_STORAGE_SHA, "files": {"storage.py": sha(REPO / STORAGE_SOURCE), "launch.py": unchanged[STORAGE + "/launch.py"]}}
    result = {**old_result, "parentDigest": PARENT_DIGEST, "sourceCommit": os.environ["GITHUB_SHA"],
        "previousManifestSha256": OLD_RESULT_SHA, "helperSourceCommit": PARENT_SOURCE,
        "patchedSources": {**old_result["patchedSources"], STORAGE + "/storage.py": storage["files"]["storage.py"]},
        "unchangedSources": {name: digest for name, digest in old_result["unchangedSources"].items() if name != STORAGE + "/storage.py"}}
    render = {"schema": "WORLD_ENGINE_RENDER_EXPORT_FILES_V1", "parentDigest": PARENT_DIGEST, "sourceCommit": os.environ["GITHUB_SHA"],
        "storageSha256": storage["files"]["storage.py"], "unchangedSources": unchanged,
        "inheritedDiagnosticManifestSha256": OLD_DIAG_SHA, "previousResultManifestSha256": OLD_RESULT_SHA,
        "resultManifestSha256": hashlib.sha256((json.dumps(result, indent=2) + "\n").encode()).hexdigest()}
    return {"STORAGE_FILES.json": storage, "RESULT_FILES.json": result, "RENDER_FILES.json": render}


def test():
    helpers().require_space()
    host = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-p", "test_ci.py", "-v"], text=True, capture_output=True, check=False, timeout=60)
    value = state(); value["ciSafetyTests"] = {"exitCode": host.returncode, "stdout": safe_log(host.stdout), "stderr": safe_log(host.stderr)}; save(value)
    if host.returncode: raise RuntimeError("NEW_CI_TESTS_FAILED")
    run(["docker", "pull", BASE], timeout=900)
    baseline = Path(os.environ["RUNNER_TEMP"]) / ("baseline-storage-" + value["tag"] + ".py")
    baseline.write_text(run(["git", "show", BASELINE + ":" + STORAGE_SOURCE], cwd=REPO))
    command = ["docker", "run", "--rm", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256", "--restart=no", "--user=0:0",
        "--tmpfs", "/workspace:rw,mode=1777", "--entrypoint=/usr/bin/python3",
        "--mount", "type=bind,source=" + str(HERE) + ",target=" + DEST + ",readonly",
        "--mount", "type=bind,source=" + str(REPO / STORAGE_SOURCE) + ",target=" + STORAGE + "/storage.py,readonly",
        "--mount", "type=bind,source=" + str(baseline) + ",target=/__ci/baseline_storage.py,readonly",
        "--env", "WORLD_ENGINE_TEST_BASELINE_STORAGE=/__ci/baseline_storage.py",
        "--env", "PYTHONPATH=" + STORAGE + ":" + DIAG + ":" + DEST, BASE, "-B", "-c"]
    results = []
    for pattern in ("test_report_export.py", "test_artifacts.py"):
        code = ("import os,unittest; os.setgroups([]); os.setgid(1000); os.setuid(1000); "
            "s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + pattern + "'); "
            "r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>0 and not r.skipped else 1)")
        result = subprocess.run(command + [code], text=True, capture_output=True, timeout=180, check=False)
        results.append({"pattern": pattern, "exitCode": result.returncode, "stdout": safe_log(result.stdout), "stderr": safe_log(result.stderr)})
        value["focusedTests"] = {"exitCode": max(x["exitCode"] for x in results), "results": results,
            "scope": "NEW_REPORT_EXPORT_BEFORE_AFTER_AND_SYNTHETIC_CPU_ARTIFACT_TESTS_NO_GPU"}; save(value)
        if result.returncode: raise RuntimeError("FOCUSED_REPORT_EXPORT_TESTS_FAILED")


def stage():
    value = state()
    if value.get("focusedTests", {}).get("exitCode") != 0: raise RuntimeError("FOCUSED_TESTS_REQUIRED")
    context = Path(os.environ["RUNNER_TEMP"]) / ("render-context-" + value["tag"]); context.mkdir(mode=0o700)
    for source, name in [(REPO / STORAGE_SOURCE, "storage.py"), (HERE / "Dockerfile", "Dockerfile")]:
        if source.is_symlink() or not source.is_file(): raise RuntimeError("EXPLICIT_SOURCE_REQUIRED")
        shutil.copyfile(source, context / name)
    generated = manifests()
    for name, body in generated.items(): (context / name).write_text(json.dumps(body, indent=2) + "\n")
    value.update(context=str(context), manifests=generated, manifestSha256={n: sha(context / n) for n in generated},
        dockerfileSha256=sha(context / "Dockerfile"), explicitContextFiles=sorted(p.name for p in context.iterdir())); save(value)


def inspect_image(image):
    facts = json.loads(run(["docker", "image", "inspect", image]))[0]; config = facts.get("Config", {}); labels = config.get("Labels", {})
    if (facts.get("Os") != "linux" or facts.get("Architecture") != "amd64"
            or labels.get("org.opencontainers.image.revision") != "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
            or labels.get("world-engine.storage.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.render-export.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.result.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.render-export.parent-digest") != PARENT_DIGEST
            or labels.get("world-engine.result.helper-source-revision") != PARENT_SOURCE
            or labels.get("world-engine.diagnostics.source-revision") != PARENT_SOURCE):
        raise RuntimeError("IMAGE_PROVENANCE_MISMATCH")
    if config.get("Entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", STORAGE + "/launch.py"]: raise RuntimeError("INHERITED_ENTRYPOINT_REQUIRED")
    if {v.partition("=")[0] for v in config.get("Env", [])} & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}: raise RuntimeError("CREDENTIAL_ENV_IN_IMAGE")
    return facts


def build():
    value = state(); value["builderBeforeBuild"] = helpers().require_space(); save(value); context = Path(value["context"])
    if set(p.name for p in context.iterdir()) != {"storage.py", "Dockerfile", "STORAGE_FILES.json", "RESULT_FILES.json", "RENDER_FILES.json"}: raise RuntimeError("BUILD_CONTEXT_WHITELIST_VIOLATION")
    subprocess.run(["docker", "build", "--platform=linux/amd64", "--file", str(context / "Dockerfile"),
        "--label", "world-engine.storage.source-revision=" + os.environ["GITHUB_SHA"],
        "--label", "world-engine.result.source-revision=" + os.environ["GITHUB_SHA"],
        "--label", "world-engine.result.helper-source-revision=" + PARENT_SOURCE,
        "--label", "world-engine.render-export.source-revision=" + os.environ["GITHUB_SHA"], "--tag", value["image"], str(context)], check=True, timeout=600)
    facts = inspect_image(value["image"]); value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"]); save(value)


def image_hashes(image):
    code = """import hashlib,json,pathlib
p=pathlib.Path('/opt/world-engine-storage-fix'); s=json.loads((p/'STORAGE_FILES.json').read_text()); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in s['files'].items())
r=json.loads(pathlib.Path('/opt/world-engine-65422-render/RENDER_FILES.json').read_text()); assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==h for n,h in r['unchangedSources'].items())
assert hashlib.sha256(pathlib.Path('/opt/world-engine-startup-diagnostics/DIAGNOSTIC_FILES.json').read_bytes()).hexdigest()==r['inheritedDiagnosticManifestSha256']
p=pathlib.Path('/opt/world-engine-diagnostic-result'); b=(p/'RESULT_FILES.json').read_bytes(); q=json.loads(b)
assert hashlib.sha256(b).hexdigest()==r['resultManifestSha256']
assert hashlib.sha256((p/'recover_existing.py').read_bytes()).hexdigest()==q['helperSha256']
assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==h for n,h in {**q['patchedSources'],**q['unchangedSources']}.items())
print(json.dumps({'STORAGE_FILES.json':s,'RESULT_FILES.json':q,'RENDER_FILES.json':r}))
"""
    actual = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3", image, "-B", "-c", code]))
    if actual != manifests(): raise RuntimeError("PATCH_OR_INHERITED_HASH_MISMATCH")
    return actual


def verify():
    value = state(); os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(value["image"], hashes_only=True), imageHashes=image_hashes(value["image"])); save(value)
    # Exercise the same new real-file tests using the built patch, not a bind
    # mount of production code. Existing test suites and GPU admission are unused.
    baseline = Path(os.environ["RUNNER_TEMP"]) / ("baseline-storage-" + value["tag"] + ".py")
    command = ["docker", "run", "--rm", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256", "--restart=no", "--user=1000:1000",
        "--tmpfs", "/workspace:rw,mode=1777", "--entrypoint=/usr/bin/python3",
        "--mount", "type=bind,source=" + str(HERE) + ",target=/__ci/tests,readonly",
        "--mount", "type=bind,source=" + str(baseline) + ",target=/__ci/baseline_storage.py,readonly",
        "--env", "WORLD_ENGINE_TEST_BASELINE_STORAGE=/__ci/baseline_storage.py", "--env", "PYTHONPATH=" + STORAGE + ":" + DIAG,
        value["image"], "-B", "-c", "import unittest; s=unittest.defaultTestLoader.discover('/__ci/tests/tests',pattern='test_report_export.py'); r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>0 and not r.skipped else 1)"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=180, check=False)
    value["actualImageExportTests"] = {"exitCode": result.returncode, "stdout": safe_log(result.stdout), "stderr": safe_log(result.stderr), "gpuExecuted": False}; save(value)
    if result.returncode: raise RuntimeError("ACTUAL_IMAGE_EXPORT_TEST_FAILED")
    secret_scan(value["image"]); value = state(); value["verification"] = "PASS"; save(value)


def secret_scan(image):
    value = state(); root = Path(os.environ["RUNNER_TEMP"]) / ("render-scan-" + value["tag"]); root.mkdir(mode=0o700)
    container = run(["docker", "create", "--entrypoint=/bin/true", image]).strip()
    try: run(["docker", "cp", container + ":" + STORAGE + "/storage.py", str(root / "storage.py")])
    finally: run(["docker", "rm", container])
    shutil.copytree(HERE, root / "new-namespace", ignore=shutil.ignore_patterns("runs", "__pycache__")); shutil.copyfile(REPO / WORKFLOW, root / "workflow.yml")
    scanner_dir = Path(tempfile.mkdtemp(prefix="render-scanner-", dir=os.environ["RUNNER_TEMP"]))
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response: body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
    archive = scanner_dir / "scanner.tar.gz"; archive.write_bytes(body); run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if sha(scanner) != orchestration.SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    config = scanner_dir / "defaults.toml"; config.write_text("[extend]\nuseDefault = true\n"); ignore = scanner_dir / "empty"; ignore.write_text("")
    report = scanner_dir / "findings.json"
    result = subprocess.run([str(scanner), "dir", str(root), "--config", str(config), "--gitleaks-ignore-path", str(ignore), "--ignore-gitleaks-allow", "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"], text=True, capture_output=True, check=False, timeout=180)
    findings = json.loads(report.read_text()) if report.exists() and report.stat().st_size < 16 * 1024**2 else None
    value["secretScan"] = {"status": "PASS" if result.returncode == 0 and findings == [] else "FAIL", "findings": len(findings) if isinstance(findings,list) else None, "scannerExitCode": result.returncode, "scope": "actual patched storage.py plus new namespace/workflow; immutable parent audit reused"}; save(value)
    if value["secretScan"]["status"] != "PASS": raise RuntimeError("RENDER_EXPORT_SECRET_SCAN_FAILED")


orchestration.inspect_image = inspect_image
orchestration.image_hashes = image_hashes


def pull():
    orchestration.pull()
    value = state(); value["status"] = "RENDER_EXPORT_IMAGE_CPU_VERIFIED"; save(value)


def persist():
    outcomes = json.loads(os.environ.get("RESULT_STEP_OUTCOMES", "{}")); value = state(); value["stepOutcomes"] = outcomes
    if value["status"] == "IN_PROGRESS" or any(x == "failure" for x in outcomes.values()): value["status"] = "RENDER_EXPORT_BLOCKED"
    relative = NAMESPACE + "/runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "/" + os.environ["RESULT_PHASE"] + ".json"
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180); run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    target = REPO / relative
    if target.exists(): raise RuntimeError("EVIDENCE_OVERWRITE_FORBIDDEN")
    target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(value, indent=2) + "\n")
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO); run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO); run(["git", "add", "--", relative], cwd=REPO)
    if run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines() != [relative]: raise RuntimeError("REPORT_ONLY_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: persist bounded export image " + os.environ["RESULT_PHASE"] + " evidence [skip ci]"], cwd=REPO); run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("phase", choices=["preflight", "guard", "test", "stage", "build", "verify", "publish", "pull", "persist"]); args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        reason = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason): reason = "RENDER_EXPORT_CI_FAILED"
        value = state(); value.update(status="RENDER_EXPORT_BLOCKED", failedPhase=args.phase, reasonCode=reason, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError): value["failedCommandExitCode"] = error.returncode
        save(value); print(json.dumps({"status": "RENDER_EXPORT_BLOCKED", "phase": args.phase, "reasonCode": reason})); raise SystemExit(1)
