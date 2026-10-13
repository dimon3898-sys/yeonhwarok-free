#!/usr/bin/env python3
"""HTTP GET the original immutable Planner review bytes; never encode media."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request
from build_candidate_manifest import MP4, SCENE_JSON, CHECKPOINTS, scene_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    assert len(args.commit) == 40 and all(char in "0123456789abcdef" for char in args.commit)
    root = Path(__file__).resolve().parent
    repo = root.parents[2]
    public = root / "public-review"
    expected = {MP4, SCENE_JSON, *CHECKPOINTS, "SHA256SUMS"}
    files = sorted(public.iterdir())
    assert {path.name for path in files} == expected and len(files) == 11
    assert all(path.is_file() and not path.is_symlink() for path in files)
    assert len([path for path in files if path.suffix == ".png"]) == 8
    assert len([path for path in files if path.suffix == ".mp4"]) == 1
    assert len([path for path in files if path.suffix == ".json"]) == 1
    scene_binding, _ = scene_document(public.relative_to(repo).as_posix() + "/" + SCENE_JSON)
    assert (public / SCENE_JSON).read_bytes() == (root / "fixtures" / SCENE_JSON).read_bytes()
    base = "https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/" + args.commit + "/" + public.relative_to(repo).as_posix() + "/"
    with tempfile.TemporaryDirectory(prefix="planner-v1-public-review-get-") as temporary:
        temporary = Path(temporary)
        def check(source):
            original = source.read_bytes()
            relative = source.relative_to(repo).as_posix()
            assert original == subprocess.check_output(["git", "show", args.commit + ":" + relative], cwd=repo)
            url = base + source.name
            request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
            with urllib.request.urlopen(request, timeout=60) as response:
                status = response.status
                downloaded = response.read()
            assert status == 200, url
            original_sha = hashlib.sha256(original).hexdigest()
            download_sha = hashlib.sha256(downloaded).hexdigest()
            assert download_sha == original_sha and downloaded == original, url
            (temporary / source.name).write_bytes(downloaded)
            return {"file": source.name, "url": url, "http_status": status, "sha256": original_sha,
                    "download_sha256": download_sha, "bytes": len(downloaded), "matches_original_and_commit": True}
        with ThreadPoolExecutor(max_workers=3) as workers:
            rows = list(workers.map(check, files))
        by_name = {row["file"]: row for row in rows}
        sums = (temporary / "SHA256SUMS").read_text().splitlines()
        assert len(sums) == 10
        assert {line.split("  ", 1)[1] for line in sums} == expected - {"SHA256SUMS"}
        for line in sums:
            checksum, filename = line.split("  ", 1)
            assert by_name[filename]["sha256"] == checksum
    report = {"schema": 1, "status": "PASS", "mediaCommit": args.commit, "files": rows, "verifiedFiles": 11,
              "publicReviewAllowedOnly": ["MP4", "PNG", "Scene JSON", "SHA256SUMS"], "publicReviewOtherFiles": 0,
              "canonicalPublicScene": scene_binding, "sceneMatchesExecutedProductionFixture": True,
              "originalMp4Reencoded": False, "downloadCopiesTemporaryOnlyNotRuntimeInputs": True,
              "permanentGateExecuted": False, "eventFinal": False, "plannerFinal": False, "userVideoApproved": False}
    (root / "evidence").mkdir(exist_ok=True)
    (root / "evidence/HTTP_DOWNLOAD_VERIFY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "http200": len(rows), "matchingOriginalSha256": len(rows), "mediaCommit": args.commit}))


if __name__ == "__main__":
    main()
