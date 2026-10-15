#!/usr/bin/env python3
"""Free hosted-runner orchestration over the unchanged, pinned GPU package."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

SOURCE = "2f9158ba2df2a9f58362fb0b17118b8dc19f705a"
BRANCH = "development/rtx-gpu-package-20261015"
IMAGE = "ghcr.io/dimon3898-sys/world-simulation-shorts-engine"
PACKAGE = "world-simulation-shorts-engine/recovery/rtx-gpu-package-v1"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCANNER_SHA = "e18325d568268b6efb6cd0cc721f8bea5667f4cd1c8d03618ab61987f41269ad"


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, capture_output=True,
                          timeout=kwargs.pop("timeout", 60), **kwargs).stdout


def state_file():
    if "RTX_CI_STATE" in os.environ: return Path(os.environ["RTX_CI_STATE"])
    return Path(os.environ["RUNNER_TEMP"]) / ("rtx-state-" + os.environ["GITHUB_RUN_ID"]
        + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "-" + os.environ["RTX_PHASE"] + ".json")


def read_state():
    return json.loads(state_file().read_text()) if state_file().exists() else {
        "schema": "RTX_IMAGE_BUILD_V1", "sourceCommit": SOURCE,
        "ciCommit": os.environ.get("GITHUB_SHA"), "gpuExecuted": False,
        "gCubeDeployed": False, "videoRendered": False, "finalModified": False,
        "oldImageModified": False, "oldCacheDeleted": False,
        "imageBuilt": False, "imagePushed": False, "pullVerified": False,
        "imageDigest": None, "status": "IN_PROGRESS"}


def save(value):
    target = state_file(); target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".writing")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(target)


def require_space():
    info = json.loads(run(["docker", "info", "--format", "{{json .DockerRootDir}}"])); root = Path(info)
    free = shutil.disk_usage(root).free
    if free < 20 * 1024**3:
        raise RuntimeError("DISK_BACKED_BUILDER_20_GIB_FREE_REQUIRED")
    fs = run(["stat", "-f", "-c", "%T", str(root)]).strip()
    if fs == "tmpfs": raise RuntimeError("TMPFS_IS_NOT_DURABLE_BUILD_STORAGE")
    return {"root": str(root), "freeBytes": free, "filesystem": fs,
            "driver": run(["docker", "info", "--format", "{{.Driver}}"] ).strip()}


def preflight():
    if (os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("GITHUB_REPOSITORY") != "dimon3898-sys/yeonhwarok-free"
            or os.environ.get("RTX_REPOSITORY_PRIVATE") != "false"
            or os.environ.get("RTX_RUNNER_LABEL") != "ubuntu-24.04"):
        raise RuntimeError("FREE_PUBLIC_STANDARD_RUNNER_REQUIRED")
    identifier, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    if not re.fullmatch(r"[1-9][0-9]*", identifier) or not re.fullmatch(r"[1-9][0-9]*", attempt):
        raise RuntimeError("TRUSTED_RUN_ID_REQUIRED")
    value = read_state(); value["builder"] = require_space()
    value["freeRunner"] = {"repositoryPublic": True, "label": "ubuntu-24.04", "largerRunner": False,
        "officialBillingSource": "https://github.com/github/docs/blob/main/content/billing/concepts/product-billing/github-actions.md"}
    value["tag"] = "rtx4080s-2f9158b-" + identifier + "-" + attempt
    value["image"] = IMAGE + ":" + value["tag"]; save(value)
    print(json.dumps({"builder": value["builder"], "image": value["image"], "gpuExecuted": False}))


def stage():
    package = REPO / PACKAGE
    contract = json.loads((package / "source_contract.json").read_text())
    overlay = json.loads((package / "package_overlay.json").read_text())["files"]
    paths = [item["repoPath"] for item in contract["files"]] + overlay
    patterns = sorted({"/" + item for item in paths} | {"/world-simulation-shorts-engine/recovery/rtx-image-build-v1/**", "/.github/workflows/rtx-gpu-image.yml"})
    run(["git", "sparse-checkout", "set", "--no-cone", "--stdin"], cwd=REPO, input="\n".join(patterns)+"\n", timeout=300)
    actual = run(["git", "rev-parse", "HEAD"], cwd=REPO).strip()
    if actual != os.environ["GITHUB_SHA"]: raise RuntimeError("CHECKOUT_COMMIT_MISMATCH")
    changed = run(["git", "diff", "--name-only", SOURCE, "HEAD"], cwd=REPO).splitlines()
    if any(path != ".github/workflows/rtx-gpu-image.yml" and not path.startswith(
            "world-simulation-shorts-engine/recovery/rtx-image-build-v1/") for path in changed):
        raise RuntimeError("EXISTING_SOURCE_OR_FINAL_CHANGED")
    if run(["git", "diff", "--name-only", SOURCE, "HEAD", "--", *paths], cwd=REPO).strip():
        raise RuntimeError("PINNED_PACKAGE_OR_PROTECTED_SOURCE_CHANGED")
    if run(["git", "status", "--porcelain"], cwd=REPO).strip(): raise RuntimeError("CLEAN_CHECKOUT_REQUIRED")
    value = read_state(); value["builderBeforeStage"] = require_space()
    context = Path(os.environ["RUNNER_TEMP"]) / ("rtx-context-" + value["tag"])
    run(["python3", "-B", str(package / "prepare_context.py"), "--destination", str(context)],
        cwd=REPO, env={**os.environ, "GIT_NO_LAZY_FETCH": "1"}, timeout=600)
    receipt = json.loads((context / "STAGING_RECEIPT.json").read_text())
    value.update(context=str(context), sourceVerification=receipt["sourceVerification"],
                 protectedSourceChanges=0, protectedPackageChanges=0,
                 contractSha256=receipt["contractSha256"], stagedFileCount=len(receipt["files"]),
                 stagingReceiptSha256=hashlib.sha256((context / "STAGING_RECEIPT.json").read_bytes()).hexdigest())
    save(value)


def build():
    value = read_state(); value["builderBeforeBuild"] = require_space(); save(value)
    context = Path(value["context"]); dockerfile = context / "repo" / PACKAGE / "Dockerfile"
    # No remote cache exporter, GPU, credentials in build args, or existing tag.
    command = ["docker", "build", "--platform=linux/amd64", "--file", str(dockerfile),
        "--label", "org.opencontainers.image.source=https://github.com/dimon3898-sys/yeonhwarok-free",
        "--label", "org.opencontainers.image.revision=" + SOURCE,
        "--label", "world-engine.ci-revision=" + os.environ["GITHUB_SHA"], "--tag", value["image"], str(context)]
    subprocess.run(command, check=True, timeout=2400)
    facts = json.loads(run(["docker", "image", "inspect", value["image"]]))[0]
    if facts["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != SOURCE:
        raise RuntimeError("BUILT_SOURCE_COMMIT_MISMATCH")
    if facts.get("Architecture") != "amd64" or facts.get("Os") != "linux":
        raise RuntimeError("BUILT_PLATFORM_MISMATCH")
    names = [entry.partition("=")[0] for entry in facts["Config"].get("Env", [])]
    if set(names) & {"GH_TOKEN", "GITHUB_TOKEN", "DOCKER_AUTH_CONFIG", "GITHUB_AUTHORIZATION"}:
        raise RuntimeError("CREDENTIAL_ENVIRONMENT_IN_IMAGE")
    value.update(imageBuilt=True, configDigest=facts["Id"], imageSizeBytes=facts["Size"],
                 architecture=facts["Architecture"], imageEnvNames=names, rootfsDiffIds=facts["RootFS"]["Layers"])
    save(value)


def check_image(image, *, hashes_only=False):
    command = ["docker", "run", "--rm", "--network=none", "--user=1000:1000", "--entrypoint=/usr/bin/python3",
        "--mount", "type=bind,source=" + str(HERE / "image_checks.py") + ",target=/__ci/image_checks.py,readonly",
        image, "-B", "/__ci/image_checks.py"]
    if hashes_only: command.append("--hashes-only")
    result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=180)
    try: report = json.loads(result.stdout)
    except (ValueError, TypeError): raise RuntimeError("IMAGE_CHECK_JSON_REQUIRED") from None
    source = report.get("source", {}) if isinstance(report, dict) else {}
    valid = (isinstance(report, dict) and report.get("schema") == "RTX_BUILT_IMAGE_CPU_CHECK_V1"
        and report.get("status") == "PASS" and type(report.get("uid")) is int and report["uid"] == 1000
        and report.get("gpuExecuted") is False and report.get("browserPageOpened") is False
        and report.get("networkIsolation") == "LOOPBACK_ONLY"
        and report.get("mode") == ("hashes-only" if hashes_only else "full-cpu")
        and isinstance(source, dict) and source.get("files") == 160 and source.get("originalFiles") == 140
        and source.get("sourceContractSha256") == "5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180"
        and source.get("sourceCommits") == {"cpu": "a002d89492734bfa9d17b98145ee6cb9a3b366a2",
                                          "glow": "45af879d7417abba58e9ebd59d8e6630a785ac28"})
    if result.returncode or not valid:
        value = read_state(); value["imageChecks"] = report; save(value)
        raise RuntimeError("IMAGE_CPU_VERIFICATION_FAILED")
    return report


def verify():
    value = read_state(); value["imageChecks"] = check_image(value["image"])
    roots = ["/root/.docker/config.json", "/root/.git-credentials", "/home/engine/.docker/config.json", "/opt/rtx-package/repo/.env"]
    code = "import os,json; paths=" + repr(roots) + "; assert not any(os.path.lexists(p) for p in paths); print(json.dumps({'knownCredentialPathsAbsent':True}))"
    value["credentialPathCheck"] = json.loads(run(["docker", "run", "--rm", "--network=none", "--user=0:0", "--entrypoint=/usr/bin/python3", value["image"], "-c", code]))
    # Scan actual application bytes copied out of the built image. No auth/config
    # directories are copied into its build context or this scan directory.
    temp = Path(os.environ["RUNNER_TEMP"]); scanroot = temp / ("rtx-image-source-" + value["tag"])
    container = run(["docker", "create", "--entrypoint=/bin/true", value["image"]]).strip()
    try: run(["docker", "cp", container + ":/opt/rtx-package", str(scanroot)], timeout=120)
    finally: run(["docker", "rm", container])  # Only this new, never-started inspection container.
    scanner_dir = temp / ("rtx-scanner-" + value["tag"]); scanner_dir.mkdir()
    archive = scanner_dir / "gitleaks.tar.gz"
    with urllib.request.urlopen("https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz", timeout=30) as response:
        body = response.read(32*1024**2+1)
        if len(body) > 32*1024**2: raise RuntimeError("SCANNER_ARCHIVE_SIZE_LIMIT")
        archive.write_bytes(body)
    run(["tar", "-xzf", str(archive), "-C", str(scanner_dir), "gitleaks"])
    scanner = scanner_dir / "gitleaks"
    if hashlib.sha256(scanner.read_bytes()).hexdigest() != SCANNER_SHA: raise RuntimeError("SCANNER_BINARY_SHA_MISMATCH")
    config = scanner_dir / "trusted.toml"; config.write_text("[extend]\nuseDefault = true\n")
    ignore = scanner_dir / "empty-ignore"; ignore.write_text("")
    report = scanner_dir / "findings.json"
    run([str(scanner), "dir", str(scanroot), "--config", str(config), "--gitleaks-ignore-path", str(ignore),
         "--ignore-gitleaks-allow", "--redact=100", "--report-format=json", "--report-path", str(report), "--no-banner"], timeout=180)
    if json.loads(report.read_text()): raise RuntimeError("SECRET_SCAN_FINDINGS")
    value["secretScan"] = {"status": "PASS", "findings": 0, "scope": "actual built application tree and known image credential paths/env", "scannerBinarySha256": SCANNER_SHA}
    save(value)


def login(value):
    token, actor = os.environ["GH_TOKEN"], os.environ["GITHUB_ACTOR"]
    auth = Path(os.environ["RUNNER_TEMP"]) / ("rtx-auth-" + value["tag"])
    auth.mkdir(mode=0o700)
    env = {**os.environ, "DOCKER_CONFIG": str(auth)}
    try:
        subprocess.run(["docker", "login", "ghcr.io", "--username", actor, "--password-stdin"],
                       input=token+"\n", env=env, text=True, check=True, capture_output=True, timeout=30)
    except Exception:
        (auth / "config.json").unlink(missing_ok=True); auth.rmdir()
        raise RuntimeError("ISOLATED_DOCKER_LOGIN_FAILED") from None
    return auth, env


def tag_guard():
    from registry_guard import RegistryGuard
    value = read_state(); value["tagCheck"] = RegistryGuard().check_tag(value["tag"]); save(value)


def publish():
    from registry_guard import RegistryGuard, validate_tag
    value = read_state()
    if (value.get("imageChecks", {}).get("status") != "PASS"
            or value.get("secretScan", {}).get("status") != "PASS"
            or value.get("secretScan", {}).get("findings") != 0):
        raise RuntimeError("IMAGE_CHECKS_BEFORE_PUSH_REQUIRED")
    registry = RegistryGuard(); validation = registry.check_tag(validate_tag(value["tag"])); value["tagCheck"] = validation; save(value)
    auth, env = login(value)
    try:
        # Repeat the no-overwrite check immediately before the first and only push.
        registry.check_tag(value["tag"])
        try:
            output = run(["docker", "push", value["image"]], env=env, timeout=900)
        except subprocess.CalledProcessError as error:
            message = (error.stderr or "").lower()
            denied = any(word in message for word in ("denied", "unauthorized", "authentication required", "permission"))
            code = "GHCR_PUSH_AUTH_OR_PACKAGE_ACCESS_DENIED" if denied else "DOCKER_PUSH_FAILED"
            value["pushFailure"] = {"exitCode": error.returncode, "reasonCode": code}; save(value)
            raise RuntimeError(code) from None
        value["imagePushed"] = True; save(value)
        digests = re.findall(r"^"+re.escape(value["tag"])+r": digest: (sha256:[0-9a-f]{64}) size: [0-9]+$", output, re.MULTILINE)
        if len(digests) != 1: raise RuntimeError("UNIQUE_PUSH_DIGEST_REQUIRED")
        value.update(imagePushed=True, imageDigest=digests[0]); save(value)
        published = registry.inspect_digest(digests[0])
        if published["configDigest"] != value["configDigest"]: raise RuntimeError("PUBLISHED_CONFIG_DIFFERS_FROM_VALIDATED_IMAGE")
        value.update(imagePushed=True, imageDigest=published["digest"], registryVerification=published,
                     imageReference=IMAGE+"@"+published["digest"], status="BUILD_AND_PUSH_PASS_PULL_PENDING")
        save(value)
        with open(os.environ["GITHUB_OUTPUT"], "a") as outputs:
            outputs.write("tag="+value["tag"]+"\ndigest="+published["digest"]+"\n")
    finally:
        # This isolated authentication directory was created by this invocation.
        (auth / "config.json").unlink(missing_ok=True); auth.rmdir()


def pull():
    from registry_guard import RegistryGuard, validate_tag, validate_digest
    value = read_state(); value.update(pullVerified=False, status="IN_PROGRESS"); value.pop("imageChecks", None)
    value["builder"] = require_space()
    value["tag"] = validate_tag(os.environ["RTX_PUBLISHED_TAG"]); value["imageDigest"] = os.environ["RTX_PUBLISHED_DIGEST"]
    validate_digest(value["imageDigest"]); save(value)
    remote = RegistryGuard().inspect_digest(validate_digest(value["imageDigest"])); value["imageReference"] = IMAGE+"@"+remote["digest"]
    auth, env = login(value)
    try: subprocess.run(["docker", "pull", value["imageReference"]], env=env, check=True, timeout=900)
    finally: (auth/"config.json").unlink(missing_ok=True); auth.rmdir()
    facts = json.loads(run(["docker", "image", "inspect", value["imageReference"]]))[0]
    if facts["Id"] != remote["configDigest"]: raise RuntimeError("PULLED_CONFIG_HASH_MISMATCH")
    if facts["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != SOURCE:
        raise RuntimeError("PULLED_SOURCE_COMMIT_MISMATCH")
    value.update(pullVerified=True, configDigest=facts["Id"], imagePushed=True, registryVerification=remote,
                 imageChecks=check_image(value["imageReference"], hashes_only=True), status="GPU_IMAGE_READY_FOR_DEPLOYMENT")
    save(value)


def persist():
    value = read_state(); outcomes = json.loads(os.environ.get("RTX_STEP_OUTCOMES", "{}")); value["stepOutcomes"] = outcomes
    if any(status == "failure" for status in outcomes.values()): value["status"] = "GPU_IMAGE_PARTIAL_BLOCKED"
    if value.get("status") == "IN_PROGRESS": value["status"] = "GPU_IMAGE_PARTIAL_BLOCKED"
    result = HERE / "runs" / (os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]) / (os.environ["RTX_PHASE"] + ".json")
    result.parent.mkdir(parents=True, exist_ok=True); result.write_text(json.dumps(value,indent=2)+"\n")
    relative = result.relative_to(REPO).as_posix()
    run(["git", "fetch", "--filter=blob:none", "origin", BRANCH], cwd=REPO, timeout=180)
    run(["git", "switch", "--detach", "FETCH_HEAD"], cwd=REPO)
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=REPO)
    run(["git", "add", "--", relative], cwd=REPO)
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=REPO).splitlines()
    if staged != [relative]: raise RuntimeError("REPORT_ONLY_GIT_COMMIT_REQUIRED")
    run(["git", "commit", "-m", "docs: save RTX image "+os.environ["RTX_PHASE"]+" result [skip ci]"], cwd=REPO)
    run(["git", "push", "origin", "HEAD:refs/heads/"+BRANCH], cwd=REPO, timeout=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("phase", choices=["preflight","tag_guard","stage","build","verify","publish","pull","persist"])
    args = parser.parse_args()
    try: globals()[args.phase]()
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code, re.ASCII): code = "OPERATION_FAILED"
        value = read_state(); value.update(status="GPU_IMAGE_PARTIAL_BLOCKED", failedPhase=args.phase,
            errorType=type(error).__name__, reasonCode=code)
        save(value); print(json.dumps({"status":value["status"],"failedPhase":args.phase,"errorType":type(error).__name__})); raise SystemExit(1)
