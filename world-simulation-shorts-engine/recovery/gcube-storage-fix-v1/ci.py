#!/usr/bin/env python3
"""Free CPU verification and a minimal immutable-parent storage adapter layer."""
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
NAMESPACE = "world-simulation-shorts-engine/recovery/gcube-storage-fix-v1"
WORKFLOW = ".github/workflows/gcube-storage-fix.yml"
BRANCH = "development/gcube-storage-fix-20261015"
BASELINE = "44085eccd9c11b0fa3d7ed904eb15f56dd34dd90"
PARENT_DIGEST = "sha256:3e8611e32860f4ae4f01febda8c4567f069552b111d7628cf0836101bdda9297"
DIAGNOSTIC_SOURCE = "2799b949cab8c8954f2ac7f2a72f7f9b1a2f7a7d"
DIAGNOSTIC_MANIFEST_SHA = "de56af52ab0655045efed69fbc7a1f3cdf2b99ade96e700e89cf8a0e6dcba59a"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
BASE = IMAGE + "@" + PARENT_DIGEST
DEST = "/opt/world-engine-storage-fix"
DIAGNOSTIC = "/opt/world-engine-startup-diagnostics"
PACKAGE = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1"
ENGINE = "/opt/rtx-package/repo/world-simulation-shorts-engine"
MODULES = ("storage.py", "launch.py")
SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"
REUSE_RUN = "38680285245-1"
REUSE_SOURCE = "97872d4949ad9a0d0c96b96fc418a68f24e67f67"
REUSE_EVIDENCE_SHA = "db585124797f17f86949adc04f2ba602da02534f5db883c1a5b1eb3a51371461"
sys.path.insert(0, str(HERE.parent / "rtx-image-build-v1"))


def helpers():
    import pipeline
    return pipeline


def run(args, *, timeout=120, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=timeout, **kwargs).stdout


def state_path():
    return Path(os.environ.get("STORAGE_CI_STATE") or str(Path(os.environ["RUNNER_TEMP"]) /
        ("storage-state-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "-" + os.environ["STORAGE_PHASE"] + ".json")))


def state():
    path = state_path()
    return json.loads(path.read_text()) if path.exists() else {
        "schema": "GCUBE_STORAGE_FIX_IMAGE_V1", "status": "IN_PROGRESS", "ciCommit": os.environ.get("GITHUB_SHA"),
        "parentImage": BASE, "gpuExecuted": False, "gCubeDeployed": False, "paidWorkExecuted": False,
        "finalModified": False, "originalSourcesModified": False, "oldImagesDeleted": False,
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
            or os.environ.get("STORAGE_REPOSITORY_PRIVATE") != "false"
            or os.environ.get("STORAGE_RUNNER_LABEL") != "ubuntu-24.04"
            or os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH):
        raise RuntimeError("FREE_PUBLIC_STANDARD_RUNNER_REQUIRED")
    identifier, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not all(re.fullmatch(r"[1-9][0-9]*", part) for part in (identifier, attempt)):
        raise RuntimeError("TRUSTED_RUN_ID_REQUIRED")
    if run(["git", "rev-parse", "HEAD"], cwd=REPO).strip() != os.environ["GITHUB_SHA"]:
        raise RuntimeError("CHECKOUT_COMMIT_MISMATCH")
    changed = run(["git", "diff", "--name-only", BASELINE, "HEAD"], cwd=REPO).splitlines()
    if any(path != WORKFLOW and not path.startswith(NAMESPACE + "/") for path in changed):
        raise RuntimeError("PROTECTED_EXISTING_SOURCE_CHANGED")
    if run(["git", "status", "--porcelain"], cwd=REPO).strip():
        raise RuntimeError("CLEAN_CHECKOUT_REQUIRED")
    value = state(); value.update(builder=helpers().require_space(),
        tag="rtx4080s-2f9158b-" + identifier + "-" + attempt,
        protection={"status": "PASS", "base": BASELINE, "allowedChangedFiles": changed},
        freeRunner={"publicRepository": True, "label": "ubuntu-24.04", "largerRunner": False})
    value["image"] = IMAGE + ":" + value["tag"]; save(value)


def guard():
    from registry_guard import RegistryGuard
    value = state(); value["tagCheck"] = RegistryGuard().check_tag(value["tag"]); save(value)


def manifest():
    return {"schema": "WORLD_ENGINE_STORAGE_FILES_V1", "parentDigest": PARENT_DIGEST,
        "sourceCommit": os.environ["GITHUB_SHA"], "files": {name: sha(HERE / name) for name in MODULES}}


def verified_reuse():
    """Reuse observations only when pinned evidence and production bytes agree."""
    path = HERE / "runs" / REUSE_RUN / "build.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2 or sha(path) != REUSE_EVIDENCE_SHA:
        raise RuntimeError("PINNED_REUSE_EVIDENCE_REQUIRED")
    evidence = json.loads(path.read_text())
    expected_files = {name: sha(HERE / name) for name in MODULES}
    results = evidence.get("focusedTests", {}).get("results", [])
    if (evidence.get("ciCommit") != REUSE_SOURCE or evidence.get("parentImage") != BASE
            or evidence.get("storageManifest", {}).get("files") != expected_files
            or evidence.get("dockerfileSha256") != sha(HERE / "Dockerfile")
            or evidence.get("focusedTests", {}).get("exitCode") != 0
            or {item.get("pattern") for item in results} != {"test_storage.py", "test_launch.py"}
            or any(item.get("exitCode") != 0 for item in results)
            or evidence.get("gpuExecuted") is not False or evidence.get("gCubeDeployed") is not False
            or evidence.get("originalSources", {}).get("status") != "PASS"
            or evidence.get("imageHashes", {}).get("originalDiagnosticManifestSha256") != DIAGNOSTIC_MANIFEST_SHA):
        raise RuntimeError("REUSE_PRODUCTION_BYTES_OR_TEST_EVIDENCE_MISMATCH")
    expected_counts = {"test_storage.py": 24, "test_launch.py": 16}
    for name, count in expected_counts.items():
        current_test = HERE / "tests" / name
        original = run(["git", "show", REUSE_SOURCE + ":" + NAMESPACE + "/tests/" + name], cwd=REPO)
        if current_test.is_symlink() or hashlib.sha256(original.encode()).hexdigest() != sha(current_test):
            raise RuntimeError("REUSE_TEST_SOURCE_CHANGED")
        observation = next(item for item in results if item["pattern"] == name)
        observed_count = re.search(r"\bRan ([0-9]+) tests? in ", observation.get("stderr", ""))
        if observed_count is None or int(observed_count[1]) != count:
            raise RuntimeError("REUSE_TEST_EXECUTION_COUNT_MISMATCH")
    expected_cases = {"before-original-shared-permission": ("STORAGE_VALIDATION_FAILED", 1),
        "after-normal-shared-storage": ("GPU_HARDWARE_UNAVAILABLE", 2),
        "after-normal-default-root": ("GPU_HARDWARE_UNAVAILABLE", 2),
        "after-normal-readonly-export": ("STORAGE_UNAVAILABLE", 1)}
    cases = evidence.get("integrationCases", [])
    if len(cases) != 4 or {item.get("case") for item in cases} != set(expected_cases):
        raise RuntimeError("REUSE_INTEGRATION_EVIDENCE_INCOMPLETE")
    for item in cases:
        expected_code, expected_exit = expected_cases[item["case"]]
        if (item.get("status") != "PASS" or item.get("errorCode") != expected_code
                or item.get("exitCode") != expected_exit or item.get("actualGPU") is not False or item.get("mock") is not False):
            raise RuntimeError("REUSE_INTEGRATION_EVIDENCE_INVALID")
    origin = {"run": REUSE_RUN, "sourceCommit": REUSE_SOURCE, "evidenceSha256": REUSE_EVIDENCE_SHA,
              "productionModuleHashesMatch": True, "dockerfileHashMatches": True, "testSourceHashesMatch": True,
              "reusedCPUUnitTests": 40, "observation": "REUSED_NOT_REEXECUTED"}
    return evidence, origin


def test():
    helpers().require_space()
    host = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE / "tests"),
        "-p", "test_ci.py", "-v"], text=True, capture_output=True, timeout=60, check=False)
    value = state(); value["ciSafetyTests"] = {"exitCode": host.returncode,
        "stdout": safe_log(host.stdout), "stderr": safe_log(host.stderr), "externalOperations": "MOCK_ONLY"}; save(value)
    if host.returncode: raise RuntimeError("NEW_CI_SAFETY_TESTS_FAILED")
    run(["docker", "pull", BASE], timeout=900)
    evidence, origin = verified_reuse()
    value = state(); value["focusedTests"] = {**evidence["focusedTests"], "reuse": origin}
    value["reusedIntegrationCases"] = {"reuse": origin, "cases": evidence["integrationCases"]}; save(value)


def stage():
    value = state()
    if value.get("focusedTests", {}).get("exitCode") != 0:
        raise RuntimeError("NEW_TESTS_REQUIRED_BEFORE_BUILD")
    context = Path(os.environ["RUNNER_TEMP"]) / ("storage-context-" + value["tag"]); context.mkdir(mode=0o700)
    for name in (*MODULES, "Dockerfile"):
        source = HERE / name
        if source.is_symlink() or not source.is_file(): raise RuntimeError("EXPLICIT_SOURCE_FILE_REQUIRED")
        shutil.copyfile(source, context / name)
    module_manifest = manifest()
    (context / "STORAGE_FILES.json").write_text(json.dumps(module_manifest, indent=2) + "\n")
    value.update(context=str(context), storageManifest=module_manifest, storageManifestSha256=sha(context / "STORAGE_FILES.json"),
        explicitContextFiles=sorted(path.name for path in context.iterdir()), dockerfileSha256=sha(context / "Dockerfile")); save(value)


def inspect_image(image):
    facts = json.loads(run(["docker", "image", "inspect", image]))[0]
    config = facts.get("Config", {}); labels = config.get("Labels", {})
    if (facts.get("Os") != "linux" or facts.get("Architecture") != "amd64"
            or labels.get("org.opencontainers.image.revision") != "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
            or labels.get("world-engine.diagnostics.source-revision") != DIAGNOSTIC_SOURCE
            or labels.get("world-engine.storage.source-revision") != os.environ["GITHUB_SHA"]
            or labels.get("world-engine.storage.parent-digest") != PARENT_DIGEST):
        raise RuntimeError("IMAGE_PLATFORM_OR_PROVENANCE_MISMATCH")
    names = [item.partition("=")[0] for item in config.get("Env", [])]
    if set(names) & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}:
        raise RuntimeError("CREDENTIAL_ENV_IN_IMAGE")
    if config.get("Entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", DEST + "/launch.py"]:
        raise RuntimeError("STORAGE_ENTRYPOINT_REQUIRED")
    return facts


def build():
    value = state(); value["builderBeforeBuild"] = helpers().require_space(); save(value)
    context = Path(value["context"])
    if set(path.name for path in context.iterdir()) != set((*MODULES, "Dockerfile", "STORAGE_FILES.json")):
        raise RuntimeError("BUILD_CONTEXT_WHITELIST_VIOLATION")
    subprocess.run(["docker", "build", "--platform=linux/amd64", "--file", str(context / "Dockerfile"),
        "--label", "world-engine.storage.source-revision=" + os.environ["GITHUB_SHA"], "--tag", value["image"], str(context)],
        timeout=600, check=True)
    facts = inspect_image(value["image"])
    value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"], rootfsDiffIds=facts["RootFS"]["Layers"]); save(value)


def image_hashes(image):
    code = """import hashlib,json,pathlib
d=pathlib.Path('/opt/world-engine-startup-diagnostics')
b=(d/'DIAGNOSTIC_FILES.json').read_bytes()
assert hashlib.sha256(b).hexdigest()=='""" + DIAGNOSTIC_MANIFEST_SHA + """'
old=json.loads(b)
assert old['sourceCommit']=='""" + DIAGNOSTIC_SOURCE + """'
assert set(old['files'])=={'startup.py','records.py','service.py','healthcheck.py'}
assert all(hashlib.sha256((d/n).read_bytes()).hexdigest()==h for n,h in old['files'].items())
p=pathlib.Path('/opt/world-engine-storage-fix'); new=json.loads((p/'STORAGE_FILES.json').read_text())
assert set(new['files'])=={'storage.py','launch.py'}
assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in new['files'].items())
print(json.dumps({'originalDiagnosticManifestSha256':hashlib.sha256(b).hexdigest(),'new':new}))
"""
    report = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3",
        image, "-B", "-c", code]))
    if report.get("new") != manifest(): raise RuntimeError("STORAGE_MODULE_HASH_MISMATCH")
    return report


def fixture_root():
    """New fixture only: unsafe existing leaf is created root-owned by Docker."""
    root = Path(tempfile.mkdtemp(prefix="storage-shared-fixture-", dir=os.environ["RUNNER_TEMP"])); root.chmod(0o777)
    code = """import os,pathlib
p=pathlib.Path('/fixture/rtx-gpu-package-v1'); p.mkdir(mode=0o755); os.chmod(p,0o755)
s=p/'preserved-sentinel'; s.write_bytes(b'UNCHANGED_SHARED_STORAGE_SENTINEL'); s.chmod(0o644)
"""
    run(["docker", "run", "--rm", "--network=none", "--user=0:0", "--entrypoint=/usr/bin/python3", "--mount",
        "type=bind,source=" + str(root) + ",target=/fixture", BASE, "-B", "-c", code])
    return root


def fixture_snapshot(root):
    leaf = root / "rtx-gpu-package-v1"; sentinel = leaf / "preserved-sentinel"
    return {"worldMode": oct(root.stat().st_mode & 0o7777), "worldUid": root.stat().st_uid,
        "oldLeafMode": oct(leaf.stat().st_mode & 0o7777), "oldLeafUid": leaf.stat().st_uid,
        "sentinelMode": oct(sentinel.stat().st_mode & 0o7777), "sentinelUid": sentinel.stat().st_uid, "sentinelSha256": sha(sentinel)}


def get_records(text):
    result = []
    for line in text.splitlines():
        try: item = json.loads(line)
        except ValueError: continue
        if isinstance(item, dict) and item.get("schema") == "WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1": result.append(item)
    return result


def execute_case(image, name, root, *, diagnostic=False, readonly=False, expected_code=None, expected_exit=2, as_root=False, service_expected=None):
    service_expected = diagnostic if service_expected is None else service_expected
    args = ["docker", "create", "--network=none", "--memory=4g", "--cpus=2", "--pids-limit=256",
        "--restart=no", "--shm-size=2g", "--mount", "type=bind,source=" + str(root) + ",target=/world-storage" + (",readonly" if readonly else "")]
    if not as_root: args += ["--user=1000:1000"]
    if diagnostic: args += ["--env", "WORLD_ENGINE_STARTUP_MODE=diagnostic", "--env", "WORLD_ENGINE_DIAGNOSTIC_TTL_SECONDS=45"]
    args += [image]
    if not diagnostic: args.append("--check")
    container = run(args).strip()
    if not re.fullmatch(r"[a-f0-9]{64}", container): raise RuntimeError("NEW_CONTAINER_ID_REQUIRED")
    report = {"case": name, "actualGPU": False, "mock": False, "entryAccount": "image-default-root" if as_root else "uid1000"}
    try:
        run(["docker", "start", container])
        if service_expected:
            probe = """import json,urllib.request,urllib.error
o=urllib.request.build_opener(urllib.request.ProxyHandler({}))
r=o.open('http://127.0.0.1:8000/healthz',timeout=2); b=json.load(r)
assert r.status==200 and b['status']=='BLOCKED' and b['diagnosticServiceAlive'] is True
assert b['gpuRenderingVerified'] is False and b['renderAllowed'] is False
print(json.dumps(b))
"""
            health = None
            for _ in range(120):
                observed = subprocess.run(["docker", "exec", "--user=1000:1000", container, "/usr/bin/python3", "-B", "-c", probe],
                    text=True, capture_output=True, timeout=5, check=False)
                if observed.returncode == 0: health = json.loads(observed.stdout); break
                time.sleep(0.5)
            if health is None: raise RuntimeError("DIAGNOSTIC_SERVICE_UNAVAILABLE")
            if health.get("errorCode") != expected_code: raise RuntimeError("DIAGNOSTIC_FAILURE_STAGE_CHANGED")
            report["healthz"] = health
            endpoint = """import json,urllib.request,urllib.error
o=urllib.request.build_opener(urllib.request.ProxyHandler({})); v={}
for path,method,expected in [('/readyz','GET',503),('/render','GET',404),('/render','POST',405)]:
 try: r=o.open(urllib.request.Request('http://127.0.0.1:8000'+path,method=method),timeout=2); s=r.status
 except urllib.error.HTTPError as e: s=e.code
 assert s==expected; v[method+' '+path]=s
print(json.dumps(v))
"""
            report["endpoints"] = json.loads(run(["docker", "exec", container, "/usr/bin/python3", "-B", "-c", endpoint]))
            live = None
            for _ in range(20):
                live = json.loads(run(["docker", "inspect", "--format",
                    '{"restartCount":{{.RestartCount}},"running":{{.State.Running}},"health":"{{.State.Health.Status}}"}', container]))
                if live == {"restartCount": 0, "running": True, "health": "healthy"}: break
                time.sleep(0.5)
            if live != {"restartCount": 0, "running": True, "health": "healthy"}:
                raise RuntimeError("DIAGNOSTIC_LIVENESS_INVALID")
            report["runningState"] = live
            report["exportReadback"] = verify_safe_export(container, expected_code, expected_exit)
            run(["docker", "stop", "--time", "5", container], timeout=10)
        report["exitCode"] = int(run(["docker", "wait", container], timeout=90).strip())
        if report["exitCode"] != expected_exit: raise RuntimeError("STARTUP_EXIT_SEMANTICS_CHANGED")
        logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, check=True, timeout=10)
        report.update(stdout=safe_log(logs.stdout), stderr=safe_log(logs.stderr))
        records = get_records(logs.stdout + "\n" + logs.stderr)
        if not any(item.get("errorCode") == expected_code and item.get("exitCode") == expected_exit for item in records):
            raise RuntimeError("EXPECTED_STRUCTURED_FAILURE_REQUIRED")
        if image != BASE and expected_code == "GPU_HARDWARE_UNAVAILABLE":
            phases = set(); storage_pass = False
            for line in (logs.stdout + "\n" + logs.stderr).splitlines():
                try: event = json.loads(line)
                except ValueError: continue
                if not isinstance(event, dict): continue
                if (event.get("schema") == "WORLD_ENGINE_STARTUP_PHASE_V1" and event.get("status") == "PASS"
                        and event.get("testOnly") is False and event.get("gpuRenderingVerified") is False
                        and event.get("renderAllowed") is False):
                    phases.add(event.get("stage"))
                if (event.get("schema") == "WORLD_ENGINE_STORAGE_FACTS_V1" and event.get("status") == "PASS"
                        and event.get("testOnly") is False): storage_pass = True
            if not {"SOURCE_INTEGRITY", "DEPENDENCY"}.issubset(phases) or not storage_pass:
                raise RuntimeError("NATIVE_STORAGE_SOURCE_DEPENDENCY_PHASES_REQUIRED")
            report["nativeCPUPhases"] = {"storage": "PASS", "sourceIntegrity": "PASS", "dependencies": "PASS",
                "testOnly": False, "gpuRenderingVerified": False}
        report.update(status="PASS", errorCode=expected_code)
        return report
    except Exception as error:
        code = str(error); report.update(status="FAIL", reasonCode=code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "CASE_OPERATION_FAILED")
        raise
    finally:
        try:
            logs = subprocess.run(["docker", "logs", container], text=True, capture_output=True, check=False, timeout=10)
            report.update(stdout=safe_log(logs.stdout), stderr=safe_log(logs.stderr))
            details = json.loads(run(["docker", "inspect", "--format", "{{json .State}}", container]))
            report["containerState"] = {key: details.get(key) for key in ("Status", "ExitCode", "OOMKilled")}
        except Exception: report["evidenceCapture"] = "PARTIAL"
        value = state(); value.setdefault("integrationAttempts", []).append(report); save(value)
        subprocess.run(["docker", "stop", "--time", "2", container], capture_output=True, timeout=5, check=False)
        subprocess.run(["docker", "rm", container], capture_output=True, timeout=10, check=False)


def verify_safe_export(container, code, exit_code):
    # Concrete adapter receipt layout is deliberately checked in its unit tests;
    # actual image verification reads the exported safe record from the mount.
    script = """import hashlib,json,pathlib,re,stat
root=pathlib.Path('/world-storage'); matches=[]; verified_receipts=0
for receipt in list(pathlib.Path('/var/lib/world-engine-private/engine').glob('session-*/EXPORT_RECEIPT.json'))[:256]:
 assert not receipt.is_symlink() and not receipt.parent.is_symlink() and stat.S_IMODE(receipt.stat().st_mode)==0o600 and receipt.stat().st_uid==1000
 assert stat.S_IMODE(receipt.parent.stat().st_mode)==0o700 and receipt.parent.stat().st_uid==1000
 d=json.loads(receipt.read_text()); assert d['schema']=='WORLD_ENGINE_EXPORT_SESSION_V1' and d['preflightVerified'] is True
 assert d['mountedViewReadbackVerified'] is True and d['remotePersistenceVerified'] is False
 assert d['externalDownloadVerified'] is False and d['privateDataAllowed'] is False
 name=d['exportName']; assert re.fullmatch('world-engine-export-[a-f0-9]{24}',name)
 directory=root/name; assert not directory.is_symlink() and directory.is_dir()
 actual=directory.stat(); rootstat=root.stat()
 assert d['directoryIdentity']=={'device':actual.st_dev,'inode':actual.st_ino}
 assert d['rootIdentity']=={'device':rootstat.st_dev,'inode':rootstat.st_ino}
 verified_receipts+=1
 for p in list(directory.glob('startup-safe-*.json'))[:256]:
  if p.is_symlink() or not stat.S_ISREG(p.lstat().st_mode): continue
  b=p.read_bytes(); assert len(b)<=131072; d=json.loads(b)
  if d.get('schema')=='WORLD_ENGINE_STARTUP_DIAGNOSTIC_V1' and d.get('errorCode')==CODE and d.get('exitCode')==EXIT:
   assert d.get('renderAllowed') is False and d.get('gpuRenderingVerified') is False
   matches.append({'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
assert matches and verified_receipts
print(json.dumps({'status':'PASS','safeRecords':matches,'privateSessionReceipts':verified_receipts,'mountedViewReadbackVerified':True,
 'remotePersistenceVerified':False,'externalDownloadVerified':False,'privateDataAllowed':False}))
""".replace("CODE", repr(code)).replace("EXIT", str(exit_code))
    return json.loads(run(["docker", "exec", "--user=1000:1000", container, "/usr/bin/python3", "-B", "-c", script]))


def secret_scan(image):
    value = state(); root = Path(os.environ["RUNNER_TEMP"]) / ("storage-secret-scan-" + value["tag"]); root.mkdir(mode=0o700)
    container = run(["docker", "create", "--entrypoint=/bin/true", image]).strip()
    try: run(["docker", "cp", container + ":" + DEST, str(root / "image-layer")], timeout=120)
    finally: run(["docker", "rm", container])
    shutil.copytree(HERE, root / "new-namespace", ignore=shutil.ignore_patterns("runs", "__pycache__"))
    shutil.copyfile(REPO / WORKFLOW, root / "workflow.yml")
    scanner_dir = Path(tempfile.mkdtemp(prefix="storage-scanner-", dir=os.environ["RUNNER_TEMP"]))
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response:
        body = response.read(32 * 1024**2 + 1)
    if len(body) > 32 * 1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
    archive = scanner_dir / "archive.tar.gz"; archive.write_bytes(body)
    run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if sha(scanner) != SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    config = scanner_dir / "defaults.toml"; config.write_text("[extend]\nuseDefault = true\n")
    ignore = scanner_dir / "empty-ignore"; ignore.write_text("")
    findings_path = scanner_dir / "findings.json"
    outcome = subprocess.run([str(scanner), "dir", str(root), "--config", str(config), "--gitleaks-ignore-path", str(ignore),
        "--ignore-gitleaks-allow", "--redact=100", "--report-format=json", "--report-path", str(findings_path), "--no-banner"],
        text=True, capture_output=True, check=False, timeout=180)
    findings = json.loads(findings_path.read_text()) if findings_path.exists() and findings_path.stat().st_size < 16 * 1024**2 else None
    scan = {"status": "PASS" if outcome.returncode == 0 and findings == [] else "FAIL", "findings": len(findings) if isinstance(findings,list) else None,
        "scannerExitCode": outcome.returncode, "scannerSha256": SCANNER_SHA, "scope": "new image layer, new namespace, new workflow; immutable parent audit reused"}
    value["secretScan"] = scan; save(value)
    if scan["status"] != "PASS": raise RuntimeError("STORAGE_SECRET_SCAN_FAILED")


def verify():
    value = state(); image = value["image"]
    os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(image, hashes_only=True), imageHashes=image_hashes(image)); save(value)
    shared = fixture_root(); before = fixture_snapshot(shared); cases = []
    value["sharedStorageBefore"] = before; save(value)
    _, reuse_origin = verified_reuse()
    value["reusedIntegrationEvidenceOrigin"] = reuse_origin; save(value)
    identity_code = "import json,os; print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups()}))"
    identity = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3",
        image, "-B", "-c", identity_code]))
    if identity.get("uid") != 1000 or identity.get("gid") != 1000 or not isinstance(identity.get("groups"), list):
        raise RuntimeError("UNPRIVILEGED_DIAGNOSTIC_IDENTITY_REQUIRED")
    value["unprivilegedIdentityProbe"] = identity; save(value)
    actual_cases = [(image, "after-diagnostic-shared-default-root", True, False, "GPU_HARDWARE_UNAVAILABLE", 2, True, True)]
    if identity["groups"]:
        actual_cases.append((image, "unprivileged-diagnostic-group-guard", True, False, "UID_GID_FAILED", 1, False, False))
    else:
        value["unprivilegedDiagnosticGroupGuard"] = {"status": "SKIP", "reasonCode": "NO_SUPPLEMENTARY_GROUPS_PRESENT"}; save(value)
    for args in actual_cases:
        reference, name, diagnostic, readonly, code, exit_code, as_root, service_expected = args
        cases.append(execute_case(reference, name, shared, diagnostic=diagnostic, readonly=readonly, expected_code=code,
            expected_exit=exit_code, as_root=as_root, service_expected=service_expected))
        if fixture_snapshot(shared) != before: raise RuntimeError("EXISTING_SHARED_STORAGE_CHANGED")
        value["integrationCases"] = cases; save(value)
    after = fixture_snapshot(shared)
    if before != after: raise RuntimeError("EXISTING_SHARED_STORAGE_CHANGED")
    value.update(sharedStorageProtection={"status": "PASS", "before": before, "after": after}, verification="PASS"); save(value)
    secret_scan(image)


def clean_auth(auth):
    (auth / "config.json").unlink(missing_ok=True); auth.rmdir()


def publish():
    from registry_guard import RegistryGuard
    value = state()
    if (value.get("verification") != "PASS" or value.get("secretScan", {}).get("status") != "PASS"
            or value.get("secretScan", {}).get("findings") != 0): raise RuntimeError("VERIFICATION_AND_ZERO_SECRETS_REQUIRED")
    registry = RegistryGuard(); registry.check_tag(value["tag"])
    auth, env = helpers().login(value)
    try:
        registry.check_tag(value["tag"])
        output = run(["docker", "push", value["image"]], env=env, timeout=900)
        matches = re.findall(r"^" + re.escape(value["tag"]) + r": digest: (sha256:[0-9a-f]{64}) size: [0-9]+$", output, re.MULTILINE)
        if len(matches) != 1: raise RuntimeError("UNIQUE_PUSH_DIGEST_REQUIRED")
        value.update(imagePushed=True, imageDigest=matches[0]); save(value)
        remote = registry.inspect_digest(matches[0])
        if remote["configDigest"] != value["configDigest"]: raise RuntimeError("PUSHED_CONFIG_HASH_MISMATCH")
        value.update(registryVerification=remote, imageReference=IMAGE + "@" + remote["digest"], status="PUBLISHED_INDEPENDENT_PULL_PENDING"); save(value)
        with open(os.environ["GITHUB_OUTPUT"], "a") as outputs:
            outputs.write("tag=" + value["tag"] + "\ndigest=" + remote["digest"] + "\n")
    finally: clean_auth(auth)


def pull():
    from registry_guard import RegistryGuard, validate_digest, validate_tag
    value = state(); value["tag"] = validate_tag(os.environ["STORAGE_PUBLISHED_TAG"])
    value["imageDigest"] = validate_digest(os.environ["STORAGE_PUBLISHED_DIGEST"])
    remote = RegistryGuard().inspect_digest(value["imageDigest"]); value["imageReference"] = IMAGE + "@" + remote["digest"]; save(value)
    auth, env = helpers().login(value)
    try: run(["docker", "pull", value["imageReference"]], env=env, timeout=900)
    finally: clean_auth(auth)
    facts = inspect_image(value["imageReference"])
    if facts["Id"] != remote["configDigest"]: raise RuntimeError("PULLED_CONFIG_HASH_MISMATCH")
    os.environ["RTX_CI_STATE"] = str(state_path())
    value.update(originalSources=helpers().check_image(value["imageReference"], hashes_only=True),
        imageHashes=image_hashes(value["imageReference"]), configDigest=facts["Id"], registryVerification=remote,
        pullVerified=True, imagePushed=True, status="STORAGE_FIX_IMAGE_CPU_VERIFIED"); save(value)


def persist():
    value = state(); value["stepOutcomes"] = json.loads(os.environ.get("STORAGE_STEP_OUTCOMES", "{}"))
    if value.get("status") == "IN_PROGRESS" or any(x == "failure" for x in value["stepOutcomes"].values()):
        value["status"] = "STORAGE_FIX_BLOCKED"
    relative = NAMESPACE + "/runs/" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "/" + os.environ["STORAGE_PHASE"] + ".json"
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180)
    run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    output = REPO / relative
    if output.exists(): raise RuntimeError("EVIDENCE_OVERWRITE_FORBIDDEN")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(value, indent=2) + "\n")
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO)
    run(["git", "add", "--", relative], cwd=REPO)
    if run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines() != [relative]: raise RuntimeError("REPORT_ONLY_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: persist storage adapter " + os.environ["STORAGE_PHASE"] + " evidence [skip ci]"], cwd=REPO)
    run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["preflight", "guard", "test", "stage", "build", "verify", "publish", "pull", "persist"])
    args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = "STORAGE_CI_OPERATION_FAILED"
        value = state(); value.update(status="STORAGE_FIX_BLOCKED", failedPhase=args.phase, reasonCode=code, errorType=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError): value["failedCommandExitCode"] = error.returncode
        save(value); print(json.dumps({"status": "STORAGE_FIX_BLOCKED", "phase": args.phase, "reasonCode": code})); raise SystemExit(1)
