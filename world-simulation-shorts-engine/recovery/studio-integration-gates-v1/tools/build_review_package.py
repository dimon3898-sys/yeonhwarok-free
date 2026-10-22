"""Bounded mobile ZIP of allowlisted public review files, never private state."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parents[1]


def build():
    files = [p for p in (HERE / "public-review").iterdir() if p.is_file()]
    files += [HERE / "README.md"]
    files += list((HERE / "newdocuments").glob("*.md"))
    files += [HERE / "reports" / name for name in (
        "GATE_RESULTS.json", "G1_CAPTURE_EVIDENCE.json", "STUDIO_HTTP_EXECUTION.json",
        "G1_PATH_AUDIT.json", "G1_IMPLEMENTATION_REVIEW.json", "G2_HISTORY_GATE.json",
        "MASTER_ACCESS.json", "LAYOUT_REPAIR.json", "PROTECTION.json", "FOCUSED_TESTS.json",
        "REUSE_AND_REMAINING.json")]
    files += [HERE / "fixtures/INCHEON_SOURCE_GATE.json", HERE / "fixtures/STUDIO_G1_REQUEST.json"]
    files += [p for p in (HERE / "comparisons").glob("*/*") if p.suffix in (".json", ".csv")]
    if any(not p.is_file() or p.is_symlink() for p in files):
        raise RuntimeError("REVIEW_PACKAGE_REQUIRED_FILE_MISSING")
    destination = HERE / "mobile-downloads"
    destination.mkdir(exist_ok=True)
    archive = destination / "WORLD_ENGINE_INTEGRATION_GATES_REVIEW.zip"
    if archive.exists():
        raise RuntimeError("REFUSE_REPLACE_EXISTING_PACKAGE")
    manifest = [{"file": p.relative_to(HERE).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                 "bytes": p.stat().st_size} for p in sorted(set(files))]
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for row in manifest:
            output.write(HERE / row["file"], row["file"])
        output.writestr("PACKAGE_MANIFEST.json", json.dumps({"schema": "PUBLIC_REVIEW_ALLOWLIST_V1", "files": manifest,
            "privateSceneAuthTokensAndCachesIncluded": False, "userApproved": False}, indent=2) + "\n")
    if archive.stat().st_size >= 32 * 1024**2:
        raise RuntimeError("MOBILE_PACKAGE_EXCEEDS_32_MIB")
    checks = [*sorted((HERE / "public-review").glob("*")), archive]
    (HERE / "SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(HERE).as_posix() + "\n"
                                         for p in checks if p.is_file()))
    print(json.dumps({"archive": str(archive.relative_to(HERE)), "bytes": archive.stat().st_size,
                      "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "files": len(manifest)}))


if __name__ == "__main__":
    build()
