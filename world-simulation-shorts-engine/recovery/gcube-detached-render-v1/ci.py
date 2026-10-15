#!/usr/bin/env python3
"""CPU-only detached CLI image; approved parent runtime is byte-preserved."""
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
NAMESPACE = "world-simulation-shorts-engine/recovery/gcube-detached-render-v1"
WORKFLOW = ".github/workflows/gcube-detached-render.yml"
BRANCH = "development/gcube-detached-render-20261015"
BASELINE = "b7e50d34b01b52f7ae1683df587010cb2fbb02d3"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
PARENT_DIGEST = "sha256:1a0a953d36ed0269a0c99267dd2d2d9e92ac6c50ffb7808e78bfbde24e7e2842"
BASE = IMAGE + "@" + PARENT_DIGEST
PARENT_SOURCE = "da01dfa1d19695adbcee7ecb0be6c8ac426a1bba"
DIAGNOSTIC_SOURCE = "eb937ec312cd60af147b7333677c5e5f10bd687e"
DEST = "/opt/world-engine-detached-render"
PARENT_NAMESPACE = HERE.parent / "gcube-65422-render-v1"
MODULES = ("job_manager.py", "job_store.py", "inspect_existing.py")
VERIFIER_SHA = "137bee60cbb242aa83d807a32909752cebb8afdc336aa8310235c68c72e11109"
CPU_FIXTURE_SHA = "8ff45a5972d3e59270c33e186738c225ade3d1161bca852fe9d46848a2a26e61"
INHERITED_MANIFESTS = {
    "/opt/world-engine-storage-fix/STORAGE_FILES.json": "c6d0d1566d2f6dce221c4c8049aa21dbb638e28ac72d9172a960ec86ccc3a3e3",
    "/opt/world-engine-diagnostic-result/RESULT_FILES.json": "98c37d4ec021571be39a8148d2cd0aa1a644659b69f903ea3a9f0a82457ef213",
    "/opt/world-engine-65422-render/RENDER_FILES.json": "25cc691e39760392f85512173ac25a0cc6f25ac92da3767294e84f45c243f722",
    "/opt/world-engine-startup-diagnostics/DIAGNOSTIC_FILES.json": "1299b2a789ffcff29a69269cdc31801b7261085cc571b35324a59336bfdb658c"}
spec = importlib.util.spec_from_file_location("detached_parent_ci", PARENT_NAMESPACE / "ci.py")
parent_ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(parent_ci)
controls = parent_ci.orchestration
# Configure an isolated read-only imported CI module, not production modules.
for name, value in {"HERE": HERE, "REPO": REPO, "NAMESPACE": NAMESPACE, "WORKFLOW": WORKFLOW, "BRANCH": BRANCH,
        "BASELINE": BASELINE, "BASE": BASE, "PARENT_DIGEST": PARENT_DIGEST, "PATCHES": {}}.items(): setattr(controls, name, value)
run = controls.run
save = controls.save
state_path = controls.state_path
sha = controls.sha
safe_log = controls.safe_log
helpers = controls.helpers
preflight = controls.preflight
guard = controls.guard
publish = controls.publish


def state():
    if state_path().exists(): return json.loads(state_path().read_text())
    return {"schema": "GCUBE_DETACHED_RENDER_IMAGE_V1", "status": "IN_PROGRESS", "ciCommit": os.environ.get("GITHUB_SHA"),
        "parentImage": BASE, "gpuExecuted": False, "gCubeDeployed": False, "paidWorkExecuted": False,
        "rendererModified": False, "finalModified": False, "oldImagesDeleted": False,
        "imageBuilt": False, "imagePushed": False, "pullVerified": False}


controls.state = state


def manifest():
    for deployed, expected in INHERITED_MANIFESTS.items():
        origin = (HERE.parent / "gcube-diagnostic-result-v1" / "image-manifests" if deployed.startswith("/opt/world-engine-startup-diagnostics") else PARENT_NAMESPACE / "image-manifests") / Path(deployed).name
        if sha(origin) != expected: raise RuntimeError("PINNED_PARENT_MANIFEST_REQUIRED")
    render = json.loads((PARENT_NAMESPACE / "image-manifests/RENDER_FILES.json").read_text())
    storage = json.loads((PARENT_NAMESPACE / "image-manifests/STORAGE_FILES.json").read_text())
    inherited = {**render["unchangedSources"], "/opt/world-engine-storage-fix/storage.py": storage["files"]["storage.py"]}
    for deployed, expected in inherited.items():
        if deployed.startswith("/opt/world-engine-startup-diagnostics/"): namespace = "gcube-diagnostic-image-v1"
        elif deployed.startswith("/opt/world-engine-storage-fix/"): namespace = "gcube-storage-fix-v1"
        else: namespace = "gcube-diagnostic-result-v1"
        if sha(HERE.parent / namespace / Path(deployed).name) != expected: raise RuntimeError("INHERITED_RUNTIME_CHANGED")
    if sha(PARENT_NAMESPACE / "verify_artifacts.py") != VERIFIER_SHA: raise RuntimeError("PINNED_VERIFIER_REQUIRED")
    return {"schema": "WORLD_ENGINE_DETACHED_JOB_FILES_V1", "sourceCommit": os.environ["GITHUB_SHA"], "parentDigest": PARENT_DIGEST,
        "files": {**{name: sha(HERE / name) for name in MODULES}, "verify_artifacts.py": VERIFIER_SHA},
        "reusedVerifier": {"sourceCommit": BASELINE, "sourcePath": "world-simulation-shorts-engine/recovery/gcube-65422-render-v1/verify_artifacts.py", "sha256": VERIFIER_SHA},
        "inheritedSources": inherited, "inheritedManifests": INHERITED_MANIFESTS}


def prepare_unit_context():
    fixture = PARENT_NAMESPACE / "tests/test_artifacts.py"
    verifier = PARENT_NAMESPACE / "verify_artifacts.py"
    if sha(fixture) != CPU_FIXTURE_SHA or sha(verifier) != VERIFIER_SHA:
        raise RuntimeError("PINNED_CPU_FIXTURE_REQUIRED")
    destination = Path(tempfile.mkdtemp(prefix="detached-unit-context-", dir=os.environ["RUNNER_TEMP"]))
    shutil.copytree(HERE, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("runs", "__pycache__"))
    shutil.copyfile(verifier, destination / "verify_artifacts.py")
    dependency = destination / "cpu-artifact-fixture"; (dependency / "tests").mkdir(parents=True)
    shutil.copyfile(fixture, dependency / "tests/test_artifacts.py")
    shutil.copyfile(verifier, dependency / "verify_artifacts.py")
    value = state(); value["unitFixture"] = {"sourceCommit": BASELINE, "fixtureSha256": CPU_FIXTURE_SHA,
        "verifierSha256": VERIFIER_SHA, "scope": "REUSED_PNG_BUILDER_ONLY_OLD_SUITE_NOT_EXECUTED"}; save(value)
    return destination


def test():
    helpers().require_space()
    host = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-p", "test_ci.py", "-v"], text=True, capture_output=True, check=False, timeout=60)
    value = state(); value["ciSafetyTests"] = {"exitCode": host.returncode, "stdout": safe_log(host.stdout), "stderr": safe_log(host.stderr), "scope": "NEW_CI_MOCKS_ONLY"}; save(value)
    if host.returncode: raise RuntimeError("NEW_CI_TESTS_FAILED")
    run(["docker", "pull", BASE], timeout=900)
    # A separate unit context avoids a nested mount creating an untracked file
    # inside the read-only checkout when the reused verifier is staged.
    test_root = prepare_unit_context()
    value = state()
    command = ["docker", "run", "--rm", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256", "--restart=no", "--user=0:0",
        "--tmpfs", "/workspace:rw,mode=1777", "--entrypoint=/usr/bin/python3",
        "--mount", "type=bind,source=" + str(test_root) + ",target=" + DEST + ",readonly",
        "--env", "PYTHONPATH=" + DEST + ":/opt/world-engine-storage-fix:/opt/world-engine-startup-diagnostics:/opt/world-engine-diagnostic-result", BASE, "-B", "-c"]
    results = []
    for pattern in ("test_job_store.py", "test_inspect.py", "test_manager.py", "test_native_monitor.py"):
        code = ("import os,pathlib,unittest; p=pathlib.Path('/var/lib/world-engine-private/engine/job-control-v1'); "
            "p.mkdir(mode=0o700); os.chown(p,1000,1000); os.setgroups([]); os.setgid(1000); os.setuid(1000); "
            "s=unittest.defaultTestLoader.discover('" + DEST + "/tests',pattern='" + pattern + "'); "
            "r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>0 and not r.skipped else 1)")
        result = subprocess.run(command + [code], text=True, capture_output=True, timeout=180, check=False)
        results.append({"pattern": pattern, "exitCode": result.returncode, "stdout": safe_log(result.stdout), "stderr": safe_log(result.stderr)})
        value["focusedTests"] = {"exitCode": max(x["exitCode"] for x in results), "results": results,
            "scope": "NEW_STORE_INSPECTION_MANAGER_TESTS_ONLY_REAL_CPU_AND_EXPLICIT_TEST_SEAMS_NO_GPU"}; save(value)
        if result.returncode: raise RuntimeError("NEW_DETACHED_TESTS_FAILED")


def stage():
    value = state()
    if value.get("focusedTests", {}).get("exitCode") != 0: raise RuntimeError("FOCUSED_TESTS_REQUIRED")
    context = Path(os.environ["RUNNER_TEMP"]) / ("detached-context-" + value["tag"]); context.mkdir(mode=0o700)
    for name in (*MODULES, "Dockerfile"):
        source = HERE / name
        if source.is_symlink() or not source.is_file(): raise RuntimeError("EXPLICIT_SOURCE_REQUIRED")
        shutil.copyfile(source, context / name)
    shutil.copyfile(PARENT_NAMESPACE / "verify_artifacts.py", context / "verify_artifacts.py")
    contract = manifest(); (context / "JOB_FILES.json").write_text(json.dumps(contract, indent=2) + "\n")
    value.update(context=str(context), jobManifest=contract, jobManifestSha256=sha(context / "JOB_FILES.json"),
        dockerfileSha256=sha(context / "Dockerfile"), explicitContextFiles=sorted(p.name for p in context.iterdir())); save(value)


def inspect_image(image):
    facts = json.loads(run(["docker", "image", "inspect", image]))[0]; config = facts.get("Config", {}); labels = config.get("Labels", {})
    if (facts.get("Os") != "linux" or facts.get("Architecture") != "amd64"
            or labels.get("org.opencontainers.image.revision") != "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
            or labels.get("world-engine.detached-render.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.detached-render.parent-digest") != PARENT_DIGEST
            or labels.get("world-engine.diagnostics.source-revision") != DIAGNOSTIC_SOURCE
            or any(labels.get("world-engine." + part + ".source-revision") != PARENT_SOURCE for part in ("storage", "result", "render-export"))):
        raise RuntimeError("IMAGE_PROVENANCE_MISMATCH")
    if config.get("Entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", "/opt/world-engine-storage-fix/launch.py"]: raise RuntimeError("PARENT_ENTRYPOINT_CHANGED")
    if {v.partition("=")[0] for v in config.get("Env", [])} & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}: raise RuntimeError("CREDENTIAL_ENV_IN_IMAGE")
    return facts


def build():
    value = state(); value["builderBeforeBuild"] = helpers().require_space(); save(value); context = Path(value["context"])
    if set(p.name for p in context.iterdir()) != {*MODULES, "verify_artifacts.py", "Dockerfile", "JOB_FILES.json"}: raise RuntimeError("BUILD_CONTEXT_WHITELIST_VIOLATION")
    subprocess.run(["docker", "build", "--platform=linux/amd64", "--file", str(context / "Dockerfile"),
        "--label", "world-engine.detached-render.source-revision=" + os.environ["GITHUB_SHA"], "--tag", value["image"], str(context)], check=True, timeout=600)
    facts = inspect_image(value["image"]); value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"]); save(value)


def image_hashes(image):
    code = """import hashlib,json,pathlib
p=pathlib.Path('/opt/world-engine-detached-render'); m=json.loads((p/'JOB_FILES.json').read_text())
assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())
assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==h for n,h in {**m['inheritedSources'],**m['inheritedManifests']}.items())
print(json.dumps(m))
"""
    actual = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3", image, "-B", "-c", code]))
    if actual != manifest(): raise RuntimeError("JOB_OR_PARENT_SOURCE_HASH_MISMATCH")
    return actual


def verify():
    value = state(); os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(value["image"], hashes_only=True), imageHashes=image_hashes(value["image"])); save(value)
    outcomes = []
    for action in ("inspect", "status"):
        shared = Path(tempfile.mkdtemp(prefix="detached-empty-export-", dir=os.environ["RUNNER_TEMP"])); shared.chmod(0o777)
        command = ["docker", "run", "--rm", "--network=none", "--memory=2g", "--cpus=2", "--pids-limit=128", "--restart=no", "--user=1000:1000",
            "--mount", "type=bind,source=" + str(shared) + ",target=/world-storage",
            "--entrypoint=/usr/bin/python3", value["image"], "-B", DEST + "/job_manager.py", action]
        result = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
        try: body = json.loads(result.stdout)
        except ValueError: raise RuntimeError("READ_ONLY_CLI_JSON_REQUIRED") from None
        if not isinstance(body, dict): raise RuntimeError("READ_ONLY_CLI_OBJECT_REQUIRED")
        outcomes.append({"action": action, "exitCode": result.returncode, "report": body, "stderr": safe_log(result.stderr),
            "scope": "REAL_CPU_READ_ONLY_NO_START_COMMAND_NO_GPU"})
        validate_read_only_result(action, result.returncode, body)
    value["actualImageReadOnlyCLI"] = outcomes; save(value)
    secret_scan(value["image"]); value = state(); value["verification"] = "PASS"; save(value)


def validate_read_only_result(action, exit_code, body):
    if not isinstance(body, dict) or body.get("renderAllowed") is not False or exit_code != 0:
        raise RuntimeError("READ_ONLY_CLI_MUST_BE_CLEAR_OR_NOT_STARTED")
    if action == "inspect":
        if (body.get("schema") != "WORLD_ENGINE_EXISTING_CAPTURE_INSPECTION_V1"
                or body.get("status") != "CLEAR" or body.get("gpuExecuted") is not False):
            raise RuntimeError("READ_ONLY_INSPECTION_MUST_BE_CLEAR")
    elif action == "status":
        if (body.get("schema") != "WORLD_ENGINE_DETACHED_STATUS_V1" or body.get("state") != "NOT_STARTED"
                or body.get("gpuRenderingVerified") is not False):
            raise RuntimeError("NEW_IMAGE_JOB_MUST_NOT_START")
    else:
        raise RuntimeError("READ_ONLY_ACTION_REQUIRED")


def secret_scan(image):
    value = state(); root = Path(os.environ["RUNNER_TEMP"]) / ("detached-scan-" + value["tag"]); root.mkdir(mode=0o700)
    container = run(["docker", "create", "--entrypoint=/bin/true", image]).strip()
    try: run(["docker", "cp", container + ":" + DEST, str(root / "actual-image-cli")])
    finally: run(["docker", "rm", container])
    shutil.copytree(HERE, root / "new-namespace", ignore=shutil.ignore_patterns("runs", "__pycache__")); shutil.copyfile(REPO / WORKFLOW, root / "workflow.yml")
    scanner_dir = Path(tempfile.mkdtemp(prefix="detached-scanner-", dir=os.environ["RUNNER_TEMP"]))
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response: body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
    archive = scanner_dir / "scanner.tar.gz"; archive.write_bytes(body); run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if sha(scanner) != controls.SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    config = scanner_dir / "defaults.toml"; config.write_text("[extend]\nuseDefault = true\n"); ignore = scanner_dir / "empty"; ignore.write_text("")
    report = scanner_dir / "findings.json"
    result = subprocess.run([str(scanner), "dir", str(root), "--config", str(config), "--gitleaks-ignore-path", str(ignore), "--ignore-gitleaks-allow", "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"], text=True, capture_output=True, check=False, timeout=180)
    findings = json.loads(report.read_text()) if report.exists() and report.stat().st_size < 16 * 1024**2 else None
    value["secretScan"] = {"status": "PASS" if result.returncode == 0 and findings == [] else "FAIL", "findings": len(findings) if isinstance(findings,list) else None,
        "scannerExitCode": result.returncode, "scope": "actual new CLI modules and reused verifier, new namespace/workflow; immutable parent audit reused"}; save(value)
    if value["secretScan"]["status"] != "PASS": raise RuntimeError("DETACHED_SECRET_SCAN_FAILED")


controls.inspect_image = inspect_image
controls.image_hashes = image_hashes


def pull():
    controls.pull()
    value = state(); value["status"] = "DETACHED_RENDER_IMAGE_CPU_VERIFIED"; save(value)


def persist():
    outcomes = json.loads(os.environ.get("RESULT_STEP_OUTCOMES", "{}")); value = state(); value["stepOutcomes"] = outcomes
    if value["status"] == "IN_PROGRESS" or any(x == "failure" for x in outcomes.values()): value["status"] = "DETACHED_RENDER_BLOCKED"
    relative = NAMESPACE + "/runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "/" + os.environ["RESULT_PHASE"] + ".json"
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180); run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    target = REPO / relative
    if target.exists(): raise RuntimeError("EVIDENCE_OVERWRITE_FORBIDDEN")
    target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(value, indent=2) + "\n")
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO); run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO); run(["git", "add", "--", relative], cwd=REPO)
    if run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines() != [relative]: raise RuntimeError("REPORT_ONLY_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: persist detached CLI image " + os.environ["RESULT_PHASE"] + " evidence [skip ci]"], cwd=REPO); run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("phase", choices=["preflight", "guard", "test", "stage", "build", "verify", "publish", "pull", "persist"]); args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        reason = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason): reason = "DETACHED_CI_FAILED"
        value = state(); value.update(status="DETACHED_RENDER_BLOCKED", failedPhase=args.phase, reasonCode=reason, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError): value["failedCommandExitCode"] = error.returncode
        save(value); print(json.dumps({"status": "DETACHED_RENDER_BLOCKED", "phase": args.phase, "reasonCode": reason})); raise SystemExit(1)
