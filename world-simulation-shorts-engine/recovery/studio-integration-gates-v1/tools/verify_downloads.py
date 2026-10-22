"""Verify fixed-commit public GET 200 and full streamed download hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

HERE = Path(__file__).resolve().parents[1]
PREFIX = "world-simulation-shorts-engine/recovery/studio-integration-gates-v1/"


def verify(commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("IMMUTABLE_COMMIT_REQUIRED")
    base = f"https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/{commit}/{PREFIX}"
    files = ["SHA256SUMS"]
    files += [line.split("  ", 1)[1] for line in (HERE / "SHA256SUMS").read_text().splitlines()]
    rows = []
    for relative in files:
        path = HERE / relative
        if not path.resolve().is_relative_to(HERE) or not path.is_file() or path.is_symlink():
            raise ValueError("DOWNLOAD_ALLOWLIST_PATH_INVALID")
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        url = base + relative
        digest, count = hashlib.sha256(), 0
        request = urllib.request.Request(url, headers={"User-Agent": "WorldEngine-PublicReview-Integrity/1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200 or not response.url.startswith(base):
                raise ValueError("PUBLIC_DOWNLOAD_HTTP_OR_REDIRECT_INVALID")
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > path.stat().st_size:
                    raise ValueError("PUBLIC_DOWNLOAD_SIZE_EXCEEDED")
                digest.update(chunk)
        if digest.hexdigest() != expected or count != path.stat().st_size:
            raise ValueError("PUBLIC_DOWNLOAD_SHA_MISMATCH")
        row = {"file": relative, "url": url, "httpStatus": 200,
               "bytes": count, "sha256": expected, "downloadMatchesOriginal": True}
        rows.append(row)
        print(json.dumps({"file": relative, "httpStatus": 200, "shaMatches": True}), flush=True)
    result = {"schema": "STUDIO_GATE_PUBLIC_DOWNLOAD_VERIFICATION_V1", "status": "PASS",
        "artifactCommit": commit, "filesVerified": len(rows), "files": rows,
        "externalDropboxSynchronizationClaimed": False, "userApproved": False}
    (HERE / "reports/DOWNLOAD_VERIFICATION.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    verify(parser.parse_args().commit)
