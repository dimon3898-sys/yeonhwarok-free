#!/usr/bin/env python3
"""Bounded free-runner build of a diagnostic-only layer; no GPU execution."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NAMESPACE = "world-simulation-shorts-engine/recovery/gcube-diagnostic-image-v1"
WORKFLOW = ".github/workflows/gcube-diagnostic-image.yml"
BRANCH = "development/gcube-diagnostic-image-20261015"
BASELINE = "a28487dc8c901eb0ca38e0c162fe70dd39294430"
PARENT_DIGEST = "sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
BASE = IMAGE + "@" + PARENT_DIGEST
MODULES = ("startup.py", "records.py", "service.py", "healthcheck.py")
PACKAGE = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1"
ENGINE = "/opt/rtx-package/repo/world-simulation-shorts-engine"
DEST = "/opt/world-engine-startup-diagnostics"
SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
HELPERS = HERE.parent / "rtx-image-build-v1"
sys.path.insert(0, str(HELPERS))


def previous():
    import pipeline
    return pipeline


def run(arguments, *, timeout=120, **kwargs):
    return subprocess.run(arguments, text=True, capture_output=True, check=True,
                          timeout=timeout, **kwargs).stdout


def state_path():
    if os.environ.get("DIAG_CI_STATE"):
        return Path(os.environ["DIAG_CI_STATE"])
    return Path(os.environ["RUNNER_TEMP"]) / ("diag-state-" + os.environ["GITHUB_RUN_ID"]
        + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "-" + os.environ["DIAG_PHASE"] + ".json")


def read_state():
    path = state_path()
    return json.loads(path.read_text()) if path.exists() else {
        "schema": "GCUBE_DIAGNOSTIC_IMAGE_V1", "status": "IN_PROGRESS",
        "ciCommit": os.environ.get("GITHUB_SHA"), "parentImage": BASE,
        "originalSourceCommit": "2f9158ba2df2a9f58362fb0b17118b8dc19f705a",
        "gpuExecuted": False, "gCubeDeployed": False, "paidWorkExecuted": False,
        "finalModified": False, "originalSourceModified": False, "oldImagesDeleted": False,
        "imageBuilt": False, "imagePushed": False, "pullVerified": False}


def save(value):
    path = state_path(); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, indent=2) + "\n"); temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_log(text):
    """Only local synthetic executions are retained. Scrub accidental credentials."""
    value = str(text or "")[:65536]
    value = re.sub(r"(?i)(authorization|token|password|secret|credential)(\s*[:=]\s*)[^\s,}\"']+",
                   r"\1\2[REDACTED]", value)
    value = re.sub(r"https?://[^\s]+", "[URL_REDACTED]", value)
    value = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+)", "[REDACTED]", value)
    return value


def preflight():
    if (os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("GITHUB_REPOSITORY") != "dimon3898-sys/yeonhwarok-free"
            or os.environ.get("DIAG_REPOSITORY_PRIVATE") != "false"
            or os.environ.get("DIAG_RUNNER_LABEL") != "ubuntu-24.04"
            or os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH):
        raise RuntimeError("FREE_PUBLIC_STANDARD_RUNNER_REQUIRED")
    identifier, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not all(re.fullmatch(r"[1-9][0-9]*", x) for x in (identifier, attempt)):
        raise RuntimeError("TRUSTED_RUN_ID_REQUIRED")
    if run(["git", "rev-parse", "HEAD"], cwd=REPO).strip() != os.environ["GITHUB_SHA"]:
        raise RuntimeError("CHECKOUT_COMMIT_MISMATCH")
    changes = run(["git", "diff", "--name-only", BASELINE, "HEAD"], cwd=REPO).splitlines()
    if any(p != WORKFLOW and not p.startswith(NAMESPACE + "/") for p in changes):
        raise RuntimeError("PROTECTED_EXISTING_SOURCE_CHANGED")
    if run(["git", "status", "--porcelain"], cwd=REPO).strip():
        raise RuntimeError("CLEAN_CHECKOUT_REQUIRED")
    value = read_state(); value["builder"] = previous().require_space()
    value.update(tag="rtx4080s-2f9158b-" + identifier + "-" + attempt,
                 protection={"status": "PASS", "base": BASELINE, "allowedChangedFiles": changes},
                 freeRunner={"publicRepository": True, "label": "ubuntu-24.04", "largerRunner": False})
    value["image"] = IMAGE + ":" + value["tag"]; save(value)


def guard():
    from registry_guard import RegistryGuard
    value = read_state(); value["tagCheck"] = RegistryGuard().check_tag(value["tag"]); save(value)


def module_manifest():
    return {"schema": "WORLD_ENGINE_STARTUP_DIAGNOSTICS_FILES_V1", "parentDigest": PARENT_DIGEST,
            "sourceCommit": os.environ["GITHUB_SHA"], "files": {name: sha(HERE / name) for name in MODULES}}


def test():
    previous().require_space()
    host = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE / "tests"),
        "-p", "test_ci_safety.py", "-v"], text=True, capture_output=True, check=False, timeout=60)
    value = read_state(); value["ciSafetyTests"] = {"exitCode": host.returncode,
        "stdout": safe_log(host.stdout), "stderr": safe_log(host.stderr), "externalOperations": "MOCK_ONLY"}; save(value)
    if host.returncode: raise RuntimeError("CI_SAFETY_TESTS_FAILED")
    run(["docker", "pull", BASE], timeout=900)
    command = ["docker", "run", "--rm", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256",
        "--restart=no", "--user=0:0", "--entrypoint=/usr/bin/python3",
        "--mount", "type=bind,source=" + str(HERE) + ",target=" + DEST + ",readonly",
        "--env", "PYTHONPATH=" + DEST + ":" + PACKAGE + ":" + ENGINE,
        BASE, "-B", "-m", "unittest", "discover", "-s", DEST + "/tests"]
    value = read_state(); results = []
    for pattern in ("test_startup.py", "test_records_service.py"):
        result = subprocess.run(command + ["-p", pattern, "-v"], text=True, capture_output=True, check=False, timeout=180)
        results.append({"pattern": pattern, "exitCode": result.returncode,
            "stdout": safe_log(result.stdout), "stderr": safe_log(result.stderr)})
        value["focusedTests"] = {"exitCode": max(item["exitCode"] for item in results), "results": results,
            "scope": "NEW_TESTS_ONLY_REAL_CPU_AND_EXPLICIT_MOCKS_NO_GPU", "baseImage": BASE}; save(value)
        if result.returncode: raise RuntimeError("FOCUSED_DIAGNOSTIC_TESTS_FAILED")


def stage():
    value = read_state()
    if value.get("focusedTests", {}).get("exitCode") != 0:
        raise RuntimeError("FOCUSED_TESTS_REQUIRED_BEFORE_BUILD")
    context = Path(os.environ["RUNNER_TEMP"]) / ("diag-context-" + value["tag"])
    context.mkdir(mode=0o700)
    for name in (*MODULES, "Dockerfile"):
        origin = HERE / name
        if origin.is_symlink() or not origin.is_file(): raise RuntimeError("EXPLICIT_SOURCE_FILE_REQUIRED")
        shutil.copyfile(origin, context / name)
    manifest = module_manifest()
    (context / "DIAGNOSTIC_FILES.json").write_text(json.dumps(manifest, indent=2) + "\n")
    value.update(context=str(context), diagnosticManifest=manifest,
        diagnosticManifestSha256=sha(context / "DIAGNOSTIC_FILES.json"),
        explicitContextFiles=sorted(p.name for p in context.iterdir()),
        dockerfileSha256=sha(context / "Dockerfile")); save(value)


def inspect_image(image):
    facts = json.loads(run(["docker", "image", "inspect", image]))[0]
    labels = facts.get("Config", {}).get("Labels", {})
    if (facts.get("Os") != "linux" or facts.get("Architecture") != "amd64"
            or labels.get("org.opencontainers.image.revision") != "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
            or labels.get("world-engine.diagnostics.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.diagnostics.parent-digest") != PARENT_DIGEST):
        raise RuntimeError("IMAGE_PLATFORM_OR_PROVENANCE_MISMATCH")
    names = [item.partition("=")[0] for item in facts["Config"].get("Env", [])]
    if set(names) & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}:
        raise RuntimeError("CREDENTIAL_ENV_IN_IMAGE")
    if facts["Config"].get("Entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", DEST + "/startup.py"]:
        raise RuntimeError("DIAGNOSTIC_ENTRYPOINT_REQUIRED")
    return facts


def build():
    value = read_state(); value["builderBeforeBuild"] = previous().require_space(); save(value)
    context = Path(value["context"])
    allowed = set((*MODULES, "Dockerfile", "DIAGNOSTIC_FILES.json"))
    if set(p.name for p in context.iterdir()) != allowed:
        raise RuntimeError("BUILD_CONTEXT_WHITELIST_VIOLATION")
    subprocess.run(["docker", "build", "--platform=linux/amd64", "--file", str(context / "Dockerfile"),
        "--label", "world-engine.diagnostics.source-revision=" + os.environ["GITHUB_SHA"],
        "--tag", value["image"], str(context)], check=True, timeout=600)
    facts = inspect_image(value["image"])
    value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"],
        rootfsDiffIds=facts["RootFS"]["Layers"]); save(value)


def image_manifest(image):
    code = ("import hashlib,json,pathlib; p=pathlib.Path('" + DEST + "'); "
        "m=json.loads((p/'DIAGNOSTIC_FILES.json').read_text()); "
        "assert set(m['files'])=={'startup.py','records.py','service.py','healthcheck.py'}; "
        "assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['files'].items()); "
        "print(json.dumps(m))")
    observed = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000",
        "--entrypoint=/usr/bin/python3", image, "-B", "-c", code]))
    if observed != module_manifest(): raise RuntimeError("NEW_MODULE_HASH_MISMATCH")
    return observed


def check_persistence(primary, fallback_roots, expected, *, readonly, expected_uid=1000):
    """Inspect a bounded set of private records; return no paths or raw bodies."""
    counts = {"primary": 0, "local_fallback": 0}
    roots = [("primary", Path(primary)), *(("local_fallback", Path(p)) for p in fallback_roots)]
    inspected = 0
    for tier, root in roots:
        if not root.exists():
            continue
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("PRIVATE_DIAGNOSTIC_DIRECTORY_REQUIRED")
        for path in root.glob("*.json"):
            inspected += 1
            if inspected > 256:
                raise RuntimeError("DIAGNOSTIC_RECORD_COUNT_LIMIT")
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != expected_uid
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 131072):
                raise RuntimeError("PRIVATE_DIAGNOSTIC_RECORD_REQUIRED")
            body = json.loads(path.read_text())
            if body.get("errorCode") == expected["errorCode"] and body.get("exitCode") == expected["exitCode"]:
                counts[tier] += 1
    if readonly and (counts["primary"] != 0 or counts["local_fallback"] < 1):
        raise RuntimeError("READONLY_FALLBACK_RECORD_REQUIRED")
    if not readonly and counts["primary"] < 1:
        raise RuntimeError("PRIMARY_DIAGNOSTIC_RECORD_REQUIRED")
    return {"status": "PASS", "tier": "local_fallback" if readonly else "primary",
        "matchingRecords": sum(counts.values()), "counts": counts,
        "fileMode": "0600", "directoryMode": "0700", "uid": expected_uid,
        "durable": False, "durabilityScope": "CPU_EPHEMERAL_CONTAINER_ONLY"}


def execute_case(image, name, *, diagnostic=False, readonly=False):
    """Created containers only are stopped/removed; host mounts are new fixtures."""
    fixture = Path(tempfile.mkdtemp(prefix="diag-storage-", dir=os.environ["RUNNER_TEMP"]))
    fixture.chmod(0o755)
    args = ["docker", "create", "--network=none", "--shm-size=2g", "--memory=4g", "--cpus=2",
            "--pids-limit=256", "--restart=no"]
    if readonly:
        args += ["--mount", "type=bind,source=" + str(fixture) + ",target=/world-storage,readonly"]
    if diagnostic:
        args += ["--env", "WORLD_ENGINE_STARTUP_MODE=diagnostic", "--env", "WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=30"]
    args += [image]
    if not diagnostic: args.append("--check")
    container = run(args).strip()
    if not re.fullmatch(r"[0-9a-f]{64}", container): raise RuntimeError("CREATED_CONTAINER_ID_INVALID")
    evidence = {"case": name, "actualGPU": False, "mock": False}
    try:
        run(["docker", "start", container])
        if diagnostic:
            probe = ("import json,urllib.request,urllib.error; "
                "o=urllib.request.build_opener(urllib.request.ProxyHandler({})); "
                "r=o.open('http://127.0.0.1:8000/healthz',timeout=2); d=json.load(r); "
                "assert r.status==200 and d['diagnosticServiceAlive'] is True and d['status']=='BLOCKED' "
                "and d['renderAllowed'] is False and d['gpuRenderingVerified'] is False; print(json.dumps(d))")
            health = None
            for _ in range(120):
                response = subprocess.run(["docker", "exec", container, "/usr/bin/python3", "-B", "-c", probe],
                    text=True, capture_output=True, timeout=5, check=False)
                if response.returncode == 0:
                    health = json.loads(response.stdout); break
                time.sleep(0.5)
            if health is None: raise RuntimeError("DIAGNOSTIC_SERVICE_NOT_AVAILABLE")
            evidence["healthz"] = health
            persistence_code = ("import json,stat\nfrom pathlib import Path\n" + inspect.getsource(check_persistence)
                + "\nprint(json.dumps(check_persistence('/world-storage/rtx-gpu-package-v1/startup-diagnostics', "
                + "list(Path('/tmp').glob('world-engine-startup-diagnostics-*')), "
                + repr({"errorCode": health["errorCode"], "exitCode": health["exitCode"]})
                + ", readonly=" + repr(readonly) + ")))\n")
            evidence["persistence"] = json.loads(run(["docker", "exec", "--user=1000:1000", container,
                "/usr/bin/python3", "-B", "-c", persistence_code]))
            endpoint_code = """import json,urllib.request,urllib.error
o=urllib.request.build_opener(urllib.request.ProxyHandler({}))
observed={}
for path,method,expected in [('/readyz','GET',503),('/render','GET',404),('/render','POST',405)]:
 try:
  r=o.open(urllib.request.Request('http://127.0.0.1:8000'+path,method=method),timeout=2); status=r.status
 except urllib.error.HTTPError as e: status=e.code
 assert status==expected,(path,method,status)
 observed[method+' '+path]=status
print(json.dumps(observed))
"""
            evidence["endpoints"] = json.loads(run(["docker", "exec", container, "/usr/bin/python3", "-B", "-c", endpoint_code]))
            health_state = None
            for _ in range(15):
                health_state = json.loads(run(["docker", "inspect", "--format", "{{json .State.Health}}", container]))
                if health_state.get("Status") == "healthy": break
                time.sleep(0.5)
            if health_state.get("Status") != "healthy": raise RuntimeError("DIAGNOSTIC_DOCKER_HEALTHCHECK_FAILED")
            evidence["dockerHealth"] = health_state["Status"]
            running = json.loads(run(["docker", "inspect", "--format",
                '{"restartCount":{{.RestartCount}},"running":{{.State.Running}},"health":"{{.State.Health.Status}}"}', container]))
            if running != {"restartCount": 0, "running": True, "health": "healthy"}:
                raise RuntimeError("DIAGNOSTIC_LIVENESS_RESTART_STATE_INVALID")
            evidence["runningState"] = running
            # SIGTERM must preserve the captured failure, never turn failure into exit 0.
            run(["docker", "stop", "--time", "5", container], timeout=10)
        result = run(["docker", "wait", container], timeout=75).strip()
        evidence["exitCode"] = int(result)
        log = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=10, check=True)
        evidence.update(stdout=safe_log(log.stdout), stderr=safe_log(log.stderr))
        expected = 1 if readonly else 2
        if evidence["exitCode"] != expected: raise RuntimeError("STARTUP_EXIT_SEMANTICS_CHANGED")
        combined = log.stdout + log.stderr
        if '"errorCode"' not in combined and '"code"' not in combined:
            raise RuntimeError("STRUCTURED_STARTUP_FAILURE_REQUIRED")
        evidence["status"] = "PASS"
        return evidence
    except Exception as error:
        code = str(error)
        evidence.update(status="FAIL", reasonCode=code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "INTEGRATION_OPERATION_FAILED")
        raise
    finally:
        # Preserve failed-case evidence as well; do not expose Docker Config/Env.
        try:
            log = subprocess.run(["docker", "logs", container], text=True, capture_output=True, timeout=10, check=False)
            evidence.update(stdout=safe_log(log.stdout), stderr=safe_log(log.stderr))
            observed = json.loads(run(["docker", "inspect", "--format", "{{json .State}}", container]))
            evidence["containerState"] = {name: observed.get(name) for name in ("Status", "ExitCode", "OOMKilled")}
            value = read_state(); value.setdefault("integrationAttempts", []).append(evidence); save(value)
        except Exception:
            value = read_state(); evidence["evidenceCapture"] = "PARTIAL"; value.setdefault("integrationAttempts", []).append(evidence); save(value)
        # No prune, global cleanup, pre-existing image/volume/cache mutation.
        subprocess.run(["docker", "stop", "--time", "2", container], check=False, capture_output=True, timeout=5)
        subprocess.run(["docker", "rm", container], check=False, capture_output=True, timeout=10)
        # Fixture intentionally left for CI ephemeral runner cleanup.


def secret_scan(image):
    value = read_state(); root = Path(os.environ["RUNNER_TEMP"]) / ("diag-scan-" + value["tag"])
    root.mkdir(mode=0o700)
    actual = root / "image-layer"
    container = run(["docker", "create", "--entrypoint=/bin/true", image]).strip()
    try: run(["docker", "cp", container + ":" + DEST, str(actual)], timeout=120)
    finally: run(["docker", "rm", container])
    shutil.copytree(HERE, root / "new-namespace", ignore=shutil.ignore_patterns("runs", "__pycache__"))
    shutil.copyfile(REPO / WORKFLOW, root / "workflow.yml")
    scanner_dir = Path(tempfile.mkdtemp(prefix="diag-scanner-", dir=os.environ["RUNNER_TEMP"]))
    archive = scanner_dir / "archive.tar.gz"
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response:
        body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
    archive.write_bytes(body)
    run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if sha(scanner) != SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    ignore = scanner_dir / "empty-ignore"; ignore.write_text("")
    config = scanner_dir / "defaults-only.toml"; config.write_text("[extend]\nuseDefault = true\n")
    report = scanner_dir / "findings.json"
    result = subprocess.run([str(scanner), "dir", str(root), "--config", str(config), "--gitleaks-ignore-path", str(ignore),
        "--ignore-gitleaks-allow", "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"],
        text=True, capture_output=True, timeout=180, check=False)
    findings = json.loads(report.read_text()) if report.exists() and report.stat().st_size < 16 * 1024**2 else None
    scan = {"status": "PASS" if result.returncode == 0 and findings == [] else "FAIL",
        "findings": len(findings) if isinstance(findings, list) else None,
        "scannerExitCode": result.returncode, "scannerSha256": SCANNER_SHA,
        "scope": "actual new image layer, new namespace, workflow; approved parent scan reused"}
    value["secretScan"] = scan; save(value)
    if scan["status"] != "PASS": raise RuntimeError("DIAGNOSTIC_SECRET_SCAN_FAILED")
    return scan


def verify():
    value = read_state(); image = value["image"]
    # Reuse hashes-only verification of all 160 original files. No old 104/8 suites.
    os.environ["RTX_CI_STATE"] = str(state_path())
    value["originalSources"] = previous().check_image(image, hashes_only=True)
    value["diagnosticFiles"] = image_manifest(image); save(value)
    cases = []
    for name, diagnostic, readonly in [("normal-no-gpu", False, False), ("normal-readonly-storage", False, True),
            ("diagnostic-no-gpu", True, False), ("diagnostic-readonly-storage", True, True)]:
        cases.append(execute_case(image, name, diagnostic=diagnostic, readonly=readonly))
        value["integrationCases"] = cases; save(value)
    value["verification"] = "PASS"; save(value)
    secret_scan(image)


def clean_auth(auth):
    (auth / "config.json").unlink(missing_ok=True); auth.rmdir()


def publish():
    from registry_guard import RegistryGuard
    value = read_state()
    if (value.get("verification") != "PASS" or value.get("secretScan", {}).get("status") != "PASS"
            or value.get("secretScan", {}).get("findings") != 0):
        raise RuntimeError("VERIFICATION_AND_ZERO_SECRETS_REQUIRED")
    registry = RegistryGuard(); registry.check_tag(value["tag"])
    auth, env = previous().login(value)
    try:
        registry.check_tag(value["tag"])
        output = run(["docker", "push", value["image"]], env=env, timeout=900)
        matches = re.findall(r"^" + re.escape(value["tag"]) + r": digest: (sha256:[0-9a-f]{64}) size: [0-9]+$", output, re.MULTILINE)
        if len(matches) != 1: raise RuntimeError("UNIQUE_PUSH_DIGEST_REQUIRED")
        value.update(imagePushed=True, imageDigest=matches[0]); save(value)
        remote = registry.inspect_digest(matches[0])
        if remote["configDigest"] != value["configDigest"]:
            raise RuntimeError("PUSHED_CONFIG_HASH_MISMATCH")
        value.update(registryVerification=remote, imageReference=IMAGE + "@" + remote["digest"],
                     status="PUBLISHED_INDEPENDENT_PULL_PENDING"); save(value)
        with open(os.environ["GITHUB_OUTPUT"], "a") as outputs:
            outputs.write("tag=" + value["tag"] + "\ndigest=" + remote["digest"] + "\n")
    finally: clean_auth(auth)


def pull():
    from registry_guard import RegistryGuard, validate_digest, validate_tag
    value = read_state(); value["tag"] = validate_tag(os.environ["DIAG_PUBLISHED_TAG"])
    value["imageDigest"] = validate_digest(os.environ["DIAG_PUBLISHED_DIGEST"])
    remote = RegistryGuard().inspect_digest(value["imageDigest"])
    value["imageReference"] = IMAGE + "@" + remote["digest"]; save(value)
    auth, env = previous().login(value)
    try: run(["docker", "pull", value["imageReference"]], env=env, timeout=900)
    finally: clean_auth(auth)
    facts = inspect_image(value["imageReference"])
    if facts["Id"] != remote["configDigest"]: raise RuntimeError("PULLED_CONFIG_HASH_MISMATCH")
    os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=previous().check_image(value["imageReference"], hashes_only=True),
        diagnosticFiles=image_manifest(value["imageReference"]), pullVerified=True,
        configDigest=facts["Id"], registryVerification=remote, imagePushed=True,
        status="GPU_DIAGNOSTIC_IMAGE_READY"); save(value)


def persist():
    value = read_state(); outcomes = json.loads(os.environ.get("DIAG_STEP_OUTCOMES", "{}"))
    value["stepOutcomes"] = outcomes
    if value.get("status") == "IN_PROGRESS" or any(x == "failure" for x in outcomes.values()):
        value["status"] = "GPU_DIAGNOSTIC_BLOCKED"
    relative = NAMESPACE + "/runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "/" + os.environ["DIAG_PHASE"] + ".json"
    # Fetch before report creation; no force-push, merge, rebase or source mutation.
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180)
    run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    output = REPO / relative
    if output.exists(): raise RuntimeError("EVIDENCE_OVERWRITE_FORBIDDEN")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(value, indent=2) + "\n")
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO)
    run(["git", "add", "--", relative], cwd=REPO)
    if run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines() != [relative]:
        raise RuntimeError("REPORT_ONLY_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: persist diagnostic image " + os.environ["DIAG_PHASE"] + " evidence [skip ci]"], cwd=REPO)
    run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["preflight", "guard", "test", "stage", "build", "verify", "publish", "pull", "persist"])
    args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = "DIAGNOSTIC_CI_OPERATION_FAILED"
        value = read_state(); value.update(status="GPU_DIAGNOSTIC_BLOCKED", failedPhase=args.phase,
            reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError): value["failedCommandExitCode"] = error.returncode
        save(value); print(json.dumps({"status": "GPU_DIAGNOSTIC_BLOCKED", "phase": args.phase, "reasonCode": code}))
        raise SystemExit(1)
