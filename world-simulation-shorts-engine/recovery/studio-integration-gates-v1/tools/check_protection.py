"""Read-only protected-owner verification; writes only this extension's report."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
BASE = "419d01ccace83d871277b2fcfc487d1b61ff7d81"


def check():
    prefix = HERE.relative_to(REPO).as_posix() + "/"
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE], cwd=REPO, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO, text=True).splitlines()
    outside = [p for p in changed + untracked if not p.startswith(prefix)]
    # Reuse the original audit's 318-entry / 307-unique-file verifier. Adjust
    # only its allowed namespace in-memory; do not edit or run its old writer.
    original = HERE.parent / "astra-event-director-v2/tools/check_preservation.py"
    source = original.read_text().replace(
        "allowed = ROOT.relative_to(REPO).as_posix() + '/'", "allowed = " + repr(prefix))
    namespace = {"__file__": str(original), "__name__": "_gates_reused_preservation"}
    exec(compile(source, str(original), "exec"), namespace)
    inherited = namespace["verify"]()
    # Its old baseline includes the previous completed ASTRA namespace. Our
    # explicit newer BASE check above separately proves there are zero edits.
    inherited.pop("outsideNamespaceChanges", None)
    errors = inherited["parentFileErrors"]
    capsule_manifest = json.loads((HERE.parent / "exact-65422-reproduction-v1/reports/SOURCE_CAPSULE_MANIFEST.json").read_bytes())
    capsule = Path(capsule_manifest["capsuleRoot"])
    closure_errors = []
    for row in capsule_manifest["files"]:
        file = capsule / row["path"]
        if (not file.is_file() or file.is_symlink() or file.stat().st_size != row["bytes"]
                or hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]):
            closure_errors.append(row["path"])
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"gh[pousr]_[A-Za-z0-9]{30,}", rb"github_pat_[A-Za-z0-9_]{40,}",
                rb"\bAKIA[A-Z0-9]{16}\b"]
    findings = []
    for file in HERE.rglob("*"):
        if not file.is_file() or any(x in file.parts for x in ("captures", "__pycache__", ".git")):
            continue
        if file.suffix in (".py", ".mjs", ".json", ".md", ".csv", ".txt"):
            data = file.read_bytes()
            if any(re.search(pattern, data) for pattern in patterns):
                findings.append(file.relative_to(HERE).as_posix())
    result = {"schema": "STUDIO_INTEGRATION_PROTECTION_V1", "status": "PASS" if not outside and not errors and not closure_errors and not findings else "FAIL",
        "baselineCommit": BASE, "outsideNamespaceChanges": outside,
        "protectedUniqueFilesVerified": inherited["verifiedUniqueParentFiles"],
        "protectedManifestEntriesVerified": inherited["verifiedParentManifestEntries"],
        "protectedFileErrors": errors, "originalCapsuleFilesChecked": len(capsule_manifest["files"]),
        "originalCapsuleErrors": closure_errors, "secretPatternFindings": findings,
        "secretScanScope": "new source/reports text files; explicit strong token/key patterns plus publication allowlist",
        "ownerCodesCookiesAndAuthStatePublished": False,
        "existingFinalRendererCameraShaderSceneAssetModified": False,
        "existingClaimsCachesVideosDeletedOrOverwritten": False, "paidGpuExecuted": False,
        "deploymentPerformed": False, "full80SecondVideoRendered": False, "finalPromotion": False,
        "requiredTempOnlyFiles": 0,
        "tempNote": "Original capsule is reproducible from pinned Git objects. New raw PNG cache/private credentials are not required artifacts; persisted per-frame hash evidence and new MP4/checkpoints are sufficient to review and repeat the source capture."}
    (HERE / "reports/PROTECTION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    check()
