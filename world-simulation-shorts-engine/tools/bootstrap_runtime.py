#!/usr/bin/env python3
"""Install the pinned eSpeak Korean runtime inside this app, without sudo.

Uses only tools/runtime/SOURCES.json's recorded Ubuntu archive URLs and SHA-256
pins. Existing packages and installed files are validated or preserved, never
overwritten. Proxy settings are inherited normally through urllib.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid

APP_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = APP_ROOT / "tools" / "runtime"
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
REQUIRED_PACKAGES = {
    "espeak-ng_1.51+dfsg-12build1_amd64.deb",
    "espeak-ng-data_1.51+dfsg-12build1_amd64.deb",
    "libespeak-ng1_1.51+dfsg-12build1_amd64.deb",
    "libpcaudio0_1.2-2build3_amd64.deb",
    "libsonic0_0.2.0-11build1_amd64.deb",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sources() -> list[dict]:
    records = json.loads((RUNTIME_ROOT / "SOURCES.json").read_text(encoding="utf-8"))
    if not isinstance(records, list) or {r.get("file") for r in records} != REQUIRED_PACKAGES:
        raise RuntimeError("RUNTIME_MANIFEST_INVALID: pinned package set changed")
    if len(records) != len(REQUIRED_PACKAGES):
        raise RuntimeError("RUNTIME_MANIFEST_INVALID: duplicate package")
    for record in records:
        name = record["file"]
        parsed = urllib.parse.urlsplit(record["url"])
        if (parsed.scheme != "http" or parsed.netloc != "archive.ubuntu.com"
                or not parsed.path.startswith("/ubuntu/pool/")
                or urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]) != name
                or parsed.query or parsed.fragment
                or not re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", ""))):
            raise RuntimeError("RUNTIME_MANIFEST_INVALID: URL or SHA pin invalid")
        if Path(name).name != name:
            raise RuntimeError("RUNTIME_MANIFEST_INVALID: package path must be a filename")
        license_path = Path(record["license_file"])
        if license_path.is_absolute() or ".." in license_path.parts:
            raise RuntimeError("RUNTIME_MANIFEST_INVALID: license path escapes runtime")
    return records


def package_file(record: dict, offline: bool) -> Path:
    destination = RUNTIME_ROOT / record["file"]
    if destination.exists():
        if not destination.is_file() or sha256(destination) != record["sha256"]:
            raise RuntimeError(f"PRESERVED_PACKAGE_HASH_MISMATCH: {destination}; preserve it and investigate")
        return destination
    if offline:
        raise RuntimeError(f"OFFLINE_PACKAGE_MISSING: {destination.name}")
    partial = RUNTIME_ROOT / (destination.name + ".download_" + uuid.uuid4().hex + ".partial")
    digest = hashlib.sha256()
    count = 0
    # No shell, proxy bypass, alternate mirror, TLS trust change or global install.
    with urllib.request.urlopen(record["url"], timeout=30) as response, partial.open("xb") as target:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > MAX_PACKAGE_BYTES:
                raise RuntimeError(f"PACKAGE_DOWNLOAD_TOO_LARGE: {partial}")
            digest.update(block)
            target.write(block)
        target.flush()
        os.fsync(target.fileno())
    if digest.hexdigest() != record["sha256"]:
        raise RuntimeError(f"PACKAGE_DOWNLOAD_HASH_MISMATCH: {partial}; untrusted partial preserved")
    # link() is exclusive: a concurrent installation cannot overwrite a package.
    try:
        os.link(partial, destination)
    except FileExistsError:
        if sha256(destination) != record["sha256"]:
            raise RuntimeError(f"CONCURRENT_PACKAGE_CONFLICT: {destination}; partial preserved at {partial}")
    partial.unlink()
    return destination


def _same_file(original: Path, existing: Path) -> bool:
    if original.is_symlink():
        return existing.is_symlink() and os.readlink(original) == os.readlink(existing)
    return existing.is_file() and not existing.is_symlink() and sha256(original) == sha256(existing)


def install_files(staging: Path) -> dict:
    files = [p for p in sorted(staging.rglob("*")) if p.is_file() or p.is_symlink()]
    # Validate every existing destination before adding a single runtime file.
    for source in files:
        destination = RUNTIME_ROOT / source.relative_to(staging)
        if os.path.lexists(destination) and not _same_file(source, destination):
            raise RuntimeError(f"PRESERVED_RUNTIME_CONFLICT: {destination}; no existing file was overwritten")
        parent = destination.parent
        while parent != RUNTIME_ROOT:
            if os.path.lexists(parent) and (parent.is_symlink() or not parent.is_dir()):
                raise RuntimeError(f"PRESERVED_RUNTIME_PARENT_CONFLICT: {parent}")
            parent = parent.parent
    added, reused = 0, 0
    for source in files:
        destination = RUNTIME_ROOT / source.relative_to(staging)
        if os.path.lexists(destination):
            reused += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            os.symlink(os.readlink(source), destination)
        else:
            with source.open("rb") as original, destination.open("xb") as target:
                shutil.copyfileobj(original, target, 1024 * 1024)
            shutil.copymode(source, destination)
        added += 1
    return {"added_files": added, "reused_files": reused, "overwritten_files": 0}


def runtime_environment() -> dict:
    environment = dict(os.environ)
    libraries = [RUNTIME_ROOT / "usr/lib/x86_64-linux-gnu", RUNTIME_ROOT / "lib/x86_64-linux-gnu"]
    environment["LD_LIBRARY_PATH"] = ":".join(map(str, libraries))
    data = RUNTIME_ROOT / "usr/lib/x86_64-linux-gnu/espeak-ng-data"
    if not data.is_dir():
        data = RUNTIME_ROOT / "usr/lib/espeak-ng-data"
    environment["ESPEAK_DATA_PATH"] = str(data)
    return environment


def verify_runtime() -> dict:
    executable = RUNTIME_ROOT / "usr/bin/espeak-ng"
    environment = runtime_environment()
    data = environment["ESPEAK_DATA_PATH"]
    command = [str(executable), "--path=" + data, "--voices=ko"]
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=20)
    if result.returncode or not re.search(r"\bko\b", result.stdout):
        raise RuntimeError("KOREAN_RUNTIME_VALIDATION_FAILED: " + result.stderr[-1500:])
    # Synthesizing to stdout validates all shared libraries and the Korean data;
    # it neither creates a final asset nor claims that the voice was listened to.
    result = subprocess.run([str(executable), "--path=" + data, "-v", "ko", "--stdout", "--stdin"],
                            input="서울과 세계를 연결합니다.\n".encode(), env=environment,
                            capture_output=True, timeout=30)
    if result.returncode or not result.stdout.startswith(b"RIFF") or len(result.stdout) < 200:
        raise RuntimeError("KOREAN_SYNTHESIS_VALIDATION_FAILED: " + result.stderr.decode(errors="replace")[-1500:])
    return {"executable": str(executable), "korean_voice_available": True,
            "actual_test_wav_bytes": len(result.stdout), "direct_listening": False}


def bootstrap(offline: bool = False) -> dict:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("UNSUPPORTED_RUNTIME_PLATFORM: these pinned packages require Linux x86_64; use system eSpeak, an external voice, or TTS OFF")
    if not shutil.which("dpkg-deb"):
        raise RuntimeError("DPKG_DEB_REQUIRED: install dpkg extraction tools or use a system TTS provider")
    records = sources()
    packages = [package_file(record, offline) for record in records]
    with tempfile.TemporaryDirectory(prefix="world_engine_espeak_stage_") as directory:
        staging = Path(directory)
        for package in packages:
            result = subprocess.run(["dpkg-deb", "-x", str(package), str(staging)],
                                    capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise RuntimeError("RUNTIME_EXTRACTION_FAILED: " + result.stderr[-1500:])
        for record in records:
            if not (staging / record["license_file"]).is_file():
                raise RuntimeError("RUNTIME_LICENSE_FILE_MISSING: " + record["license_file"])
        merged = install_files(staging)
    return {"passed": True, "scope": "isolated pinned Linux x86_64 eSpeak runtime",
            "runtime_root": str(RUNTIME_ROOT), "offline": offline,
            "verified_packages": [{"file": r["file"], "sha256": r["sha256"]} for r in records],
            **merged, **verify_runtime(), "system_packages_modified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Require preserved .deb packages; do not download")
    arguments = parser.parse_args()
    try:
        print(json.dumps(bootstrap(arguments.offline), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
