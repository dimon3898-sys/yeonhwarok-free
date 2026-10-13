#!/usr/bin/env python3
"""GET every immutable public body and bind HTTP 200 bytes to original Git media."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from build_manifest import BASE, REPO, MP4, SCENE_JSON, public_files, git, require, encode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--download-directory", type=Path,
                        help="Optional durable copies; no downloaded copy is a runtime input.")
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.commit), "IMMUTABLE_MEDIA_COMMIT_REQUIRED")
    require(git("rev-parse", args.commit + "^{commit}").decode().strip() == args.commit, "UNKNOWN_MEDIA_COMMIT")
    root = REPO / BASE
    report = json.loads((root / "evidence/proof/REPORT.json").read_text())
    files = public_files(report)
    copies = args.download_directory or Path("/workspace/.onboarding/planner-night-http") / args.commit
    require(copies.is_absolute() and "/tmp" not in str(copies.resolve()), "DOWNLOAD_COPIES_REQUIRE_DURABLE_PATH")
    copies.mkdir(parents=True, exist_ok=True)
    base = "https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/" + args.commit + "/" + BASE + "/public-review/"
    def check(source):
        original = source.read_bytes()
        relative = source.relative_to(REPO).as_posix()
        require(original == git("show", args.commit + ":" + relative), "MEDIA_BYTES_DIFFER_FROM_COMMIT: " + relative)
        url = base + source.name
        request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            downloaded = response.read()
            final_url = response.url
        require(status == 200, "PUBLIC_HTTP_NOT_200: " + url)
        original_sha = hashlib.sha256(original).hexdigest()
        download_sha = hashlib.sha256(downloaded).hexdigest()
        require(downloaded == original and download_sha == original_sha, "PUBLIC_BODY_OR_SHA_MISMATCH: " + url)
        destination = copies / source.name
        if destination.exists():
            require(destination.read_bytes() == downloaded, "EXISTING_DOWNLOAD_COPY_DIFFERS: " + source.name)
        else:
            destination.write_bytes(downloaded)
        return {"file": source.name, "url": url, "final_url": final_url, "http_status": status,
                "sha256": original_sha, "download_sha256": download_sha, "bytes": len(downloaded),
                "matches_original_and_commit": True}
    with ThreadPoolExecutor(max_workers=3) as workers:
        rows = list(workers.map(check, files))
    by_name = {row["file"]: row for row in rows}
    sums = (copies / "SHA256SUMS").read_text().splitlines()
    require(len(sums) == len(rows) - 1, "DOWNLOADED_SHA_ENTRY_COUNT")
    require({line.split("  ", 1)[1] for line in sums} == set(by_name) - {"SHA256SUMS"}, "DOWNLOADED_SHA_FILE_SET")
    for line in sums:
        checksum, filename = line.split("  ", 1)
        require(by_name[filename]["sha256"] == checksum, "DOWNLOADED_SHA_BODY_BINDING")
    require((copies / SCENE_JSON).read_bytes() == (root / "fixtures" / SCENE_JSON).read_bytes(), "DOWNLOADED_SCENE_NOT_EXECUTED_INPUT")
    result = {"schema": 1, "status": "PASS", "mediaCommit": args.commit, "sourceCommit": report["sourceCommit"],
              "files": rows, "verifiedFiles": len(rows), "publicReviewAllowedOnly": ["MP4", "PNG", "Scene JSON", "SHA256SUMS"],
              "publicReviewOtherFiles": 0, "sceneMatchesExecutedProductionFixture": True,
              "originalMp4Reencoded": False, "downloadCopies": str(copies), "downloadCopiesRuntimeRequired": False,
              "requiredTempOnlyFiles": 0, "permanentGateExecuted": False, "eventFinal": False,
              "plannerFinal": False, "userVideoApproved": False, "next": "USER_VIDEO_REVIEW_REQUIRED"}
    (root / "evidence/HTTP_DOWNLOAD_VERIFY.json").write_bytes(encode(result))
    print(json.dumps({"status": "PASS", "http200": len(rows), "matchingOriginalAndGitSha256": len(rows),
                      "mediaCommit": args.commit, "videoSha256": by_name[MP4]["sha256"]}))


if __name__ == "__main__":
    main()
