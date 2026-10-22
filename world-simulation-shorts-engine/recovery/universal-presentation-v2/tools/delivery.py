"""Selective public packaging and credential-free HTTPS readback for UP2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
BASE = "b0d013832ee38571f9d3dfe685ce63f7083ba90f"


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(data)
    return result.hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def scan(report):
    patterns = {
        "githubToken": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b",
        "privateKey": rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
        "awsAccessKey": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        "dropboxLongToken": rb"\bsl\.[A-Za-z0-9_-]{60,}\b",
        "bearerCredential": rb"(?i)authorization[\"\x27]?\s*[:=]\s*[\"\x27]?bearer\s+[A-Za-z0-9_.-]{30,}",
    }
    files, findings = [], []
    for file in sorted(HERE.rglob("*")):
        if file.is_symlink():
            raise ValueError("DELIVERY_SYMLINK_FORBIDDEN")
        if not file.is_file() or "__pycache__" in file.parts or file == report:
            continue
        raw = file.read_bytes()
        files.append({"path": file.relative_to(HERE).as_posix(), "bytes": len(raw), "sha256": sha(file)})
        if file.suffix.lower() in {".png", ".mp4", ".jpg", ".zip"}:
            continue
        for kind, pattern in patterns.items():
            count = len(re.findall(pattern, raw))
            if count:
                findings.append({"path": file.relative_to(HERE).as_posix(), "kind": kind, "count": count})
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE], cwd=REPO, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO, text=True).splitlines()
    prefix = HERE.relative_to(REPO).as_posix() + "/"
    outside = sorted({file for file in changed + untracked if not file.startswith(prefix)})
    value = {"schema": "WORLD_ENGINE_UP2_SECRET_SCAN_V1", "status": "PASS" if not findings and not outside else "FAIL",
        "credentialFindings": findings, "changedOutsideNewNamespace": outside, "scannedFiles": len(files),
        "method": "Credential-pattern scan, complete tracked and untracked namespace check",
        "limitations": "Pattern checks do not formally exclude every possible credential encoding.", "files": files}
    write(report, value)
    print(json.dumps({k: v for k, v in value.items() if k != "files"}))
    if value["status"] != "PASS":
        raise ValueError("SECRET_OR_PROTECTION_BOUNDARY_FAILURE")


def package():
    gate = json.loads((HERE / "reports/GATES.json").read_text())
    if (gate["phaseF"]["status"] != "PASS" or gate["phaseG"]["status"] != "PASS"
            or gate["paidGpuExecuted"] is not False or gate["historicalProduction"] != "BLOCKED"):
        raise ValueError("COMPLETED_FREE_GATES_REQUIRED")
    archive = HERE / "review-package/WORLD_ENGINE_PRESENTATION_V2_REVIEW.zip"
    archive.parent.mkdir(exist_ok=True)
    files = []
    for file in sorted(HERE.rglob("*")):
        relative = file.relative_to(HERE)
        if file.is_symlink():
            raise ValueError("REVIEW_SYMLINK_FORBIDDEN")
        if (not file.is_file() or "__pycache__" in file.parts or relative.parts[0] == "review-package"
                or file.name in {"SHA256SUMS", "DOWNLOAD_VERIFICATION.json"}):
            continue
        # Full decoded frames remain individually downloadable. Keep the ZIP
        # small using the real movies and actual-frame contact sheets.
        if file.suffix.lower() == ".png" and not any(x in file.name for x in ("CONTACT", "COMPARISON")):
            continue
        files.append(file)
    manifest = [{"path": f.relative_to(HERE).as_posix(), "bytes": f.stat().st_size, "sha256": sha(f)} for f in files]
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for file in files:
            info = zipfile.ZipInfo(file.relative_to(HERE).as_posix(), (2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            target.writestr(info, file.read_bytes())
        target.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(archive) as target:
        if target.testzip() is not None:
            raise ValueError("ZIP_CRC_FAILED")
        for item in manifest:
            if hashlib.sha256(target.read(item["path"])).hexdigest() != item["sha256"]:
                raise ValueError("ZIP_SHA_FAILED")
    primary = [archive, *sorted((HERE / "public-review").glob("*.mp4")),
               *sorted((HERE / "public-review").glob("*CONTACT_SHEET.png"))]
    with (HERE / "SHA256SUMS").open("x") as stream:
        stream.write("".join(sha(f) + "  " + f.relative_to(HERE).as_posix() + "\n" for f in primary))
    with (HERE / "public-review/SHA256SUMS").open("x") as stream:
        stream.write("".join(sha(f) + "  " + f.name + "\n" for f in primary if f.parent.name == "public-review"))
    print(json.dumps({"files": len(files), "zipBytes": archive.stat().st_size, "zipSHA256": sha(archive),
                      "zipCRC": "PASS", "bundledSHA256": "PASS", "privateJobStateIncluded": False}))


def verify(args):
    if not re.fullmatch(r"[a-f0-9]{40}", args.commit):
        raise ValueError("IMMUTABLE_COMMIT_REQUIRED")
    args.download_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    rows = []
    for index, relative in enumerate(args.file):
        file = HERE / relative
        if (not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(HERE.resolve())
                or not relative.startswith(("public-review/", "review-package/"))):
            raise ValueError("PUBLIC_ARTIFACT_REQUIRED")
        url = ("https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/" + args.commit + "/" +
               urllib.parse.quote(file.relative_to(REPO).as_posix(), safe="/"))
        request = urllib.request.Request(url, headers={"User-Agent": "WORLD-ENGINE-UP2-integrity/1"})
        result, count = hashlib.sha256(), 0
        with urllib.request.urlopen(request, timeout=60) as response, (
                args.download_root / (str(index) + "-" + file.name)).open("xb") as target:
            if response.status != 200 or not response.url.startswith("https://"):
                raise ValueError("HTTPS_200_REQUIRED")
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                count += len(chunk)
                if count > file.stat().st_size:
                    raise ValueError("DOWNLOAD_OVERSIZE")
                result.update(chunk)
                target.write(chunk)
        row = {"file": relative, "url": url, "httpStatus": 200, "bytes": count,
               "expectedSHA256": sha(file), "downloadSHA256": result.hexdigest(),
               "status": "PASS" if result.hexdigest() == sha(file) and count == file.stat().st_size else "FAIL"}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if row["status"] != "PASS":
            raise ValueError("DOWNLOAD_SHA_FAILED")
    write(args.report, {"schema": "WORLD_ENGINE_UP2_DOWNLOADS_V1", "status": "PASS", "commit": args.commit,
        "tlsVerificationDisabled": False, "credentialsUsed": False, "files": rows})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["scan", "package", "verify"])
    parser.add_argument("--report", type=Path, default=HERE / "reports/SECRET_SCAN.json")
    parser.add_argument("--commit")
    parser.add_argument("--download-root", type=Path)
    parser.add_argument("--file", action="append")
    args = parser.parse_args()
    if args.mode == "scan":
        scan(args.report)
    elif args.mode == "package":
        package()
    else:
        verify(args)
