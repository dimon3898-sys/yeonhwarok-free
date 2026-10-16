"""Reuse the existing untrusted Dropbox export primitives for long videos.

Mounted readback is not remote synchronization or external delivery. External
verification accepts actual private URL input, uses the existing Dropbox URL
and redirect guards and never emits the URLs into a public receipt.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import time
import urllib.request

HERE = Path(__file__).resolve().parent
PUBLIC = frozenset({"WORLD_ENGINE_AUTO_VIDEO.mp4", "QUALITY_SUMMARY.json", "SHA256SUMS"})
HASH = re.compile(r"[0-9a-f]{64}\Z")
STORAGE_SHA256 = "4c858e7afe5e912bce63bf03f08c6c98d9430cc91134262710db5bdbd6ca4491"
VERIFIER_SHA256 = "137bee60cbb242aa83d807a32909752cebb8afdc336aa8310235c68c72e11109"
FLAGS = {"mountedViewReadbackVerified": True, "remotePersistenceVerified": False, "externalDownloadVerified": False}


class DeliveryError(RuntimeError):
    pass


def _load(name, paths, expected=None):
    for path in paths:
        if path.is_file():
            if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise DeliveryError("EXISTING_ADAPTER_SOURCE_CHANGED")
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise DeliveryError("EXISTING_ADAPTER_UNAVAILABLE")


def _storage():
    return _load("_universal_existing_storage", [Path("/opt/world-engine-storage-fix/storage.py"), HERE.parent / "gcube-storage-fix-v1/storage.py"], STORAGE_SHA256)


def _verifier():
    return _load("_universal_existing_dropbox_verifier", [Path("/opt/world-engine-detached-render/verify_artifacts.py"),
                  HERE.parent / "gcube-65422-render-v1/verify_artifacts.py"], VERIFIER_SHA256)


def _compose():
    return _load("_universal_compose_delivery", [HERE / "compose.py"])


def _public_manifest(root, anchor):
    module = _compose()
    if not isinstance(anchor, str) or not HASH.fullmatch(anchor):
        raise DeliveryError("SOURCE_MANIFEST_ANCHOR_REQUIRED")
    if root.is_symlink() or set(os.listdir(root)) != PUBLIC:
        raise DeliveryError("EXACT_PUBLIC_ALLOWLIST_REQUIRED")
    if module.digest_file(root / "SHA256SUMS") != anchor:
        raise DeliveryError("SOURCE_MANIFEST_ANCHOR_MISMATCH")
    body = (root / "SHA256SUMS").read_bytes()
    if len(body) > 4096:
        raise DeliveryError("PUBLIC_MANIFEST_TOO_LARGE")
    expected = {}
    for line in body.decode("ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in expected or match[2] not in PUBLIC - {"SHA256SUMS"}:
            raise DeliveryError("PUBLIC_MANIFEST_INVALID")
        expected[match[2]] = match[1]
    if set(expected) != PUBLIC - {"SHA256SUMS"}:
        raise DeliveryError("PUBLIC_MANIFEST_INVALID")
    expected["SHA256SUMS"] = anchor
    for name, digest in expected.items():
        if module.digest_file(root / name) != digest:
            raise DeliveryError("PUBLIC_SOURCE_HASH_MISMATCH")
    summary_path = root / "QUALITY_SUMMARY.json"
    if summary_path.stat().st_size > 16384:
        raise DeliveryError("SAFE_QA_SUMMARY_TOO_LARGE")
    _safe_summary(json.loads(summary_path.read_text()))
    return expected


def _safe_summary(summary):
    module = _compose()
    allowed = {"schema", "technicalVerification", "fps", "durationSeconds", "frames", "width", "height", "videoCodec", "audioStreams",
               "sceneCount", "fullDecode", "decodedFrameSequenceMatchesSegments", "compositionMode", "boundaryStateContract", "visualContinuity",
               "visualQuality", "hardwareVerification", "finalPromotion"}
    if (not isinstance(summary, dict) or set(summary) != allowed or summary.get("schema") != "WORLD_ENGINE_UNIVERSAL_SAFE_QA_V2"
            or summary.get("technicalVerification") != "PASS" or summary.get("visualContinuity") != "UNREVIEWED"
            or summary.get("visualQuality") != "USER_VIDEO_REVIEW_REQUIRED" or summary.get("finalPromotion") is not False
            or summary.get("videoCodec") != "h264" or summary.get("audioStreams") != 0 or summary.get("fullDecode") != "PASS"
            or summary.get("decodedFrameSequenceMatchesSegments") is not True
            or summary.get("compositionMode") not in {"VERIFIED_STREAM_COPY", "LOSSLESS_NORMALIZE_THEN_COPY"}
            or summary.get("boundaryStateContract") not in {"PASS", "NOT_PROVIDED"}
            or summary.get("hardwareVerification") != "NOT_ASSERTED_BY_COMPOSER"
            or type(summary.get("sceneCount")) is not int or not 1 <= summary["sceneCount"] <= 10000):
        raise DeliveryError("PUBLIC_SAFE_QA_SUMMARY_INVALID")
    try:
        # The summary deliberately contains numeric width/height only.
        contract = module.video_contract({**summary, "resolution": [summary.get("width"), summary.get("height")]})
    except module.ComposeError:
        raise DeliveryError("PUBLIC_SAFE_QA_SUMMARY_INVALID") from None
    if type(summary["frames"]) is not int or summary["frames"] != contract["frames"]:
        raise DeliveryError("PUBLIC_SAFE_QA_SUMMARY_INVALID")
    return summary


def export_video(plan, composed, export_root, *, private_base=None):
    """Fresh export; old Dropbox files, claims and export sessions are untouched.

    Reuses StorageSession.create/preflight, private path isolation, exclusive
    files, source identity, streamed copying, fsync and readback. Existing
    adapter has a 4GiB/file limit; exceeding it is explicitly blocked.
    """
    storage, module = _storage(), _compose()
    source = Path(composed["publicDir"]).absolute()
    receipt_path = Path(composed["receiptPath"]).absolute()
    if receipt_path.parent != source.parent or receipt_path.name != "COMPOSE_COMPLETE.json":
        raise DeliveryError("COMPOSITION_RECEIPT_REQUIRED")
    complete = json.loads(receipt_path.read_text())
    contract = module.video_contract(plan)
    if (complete.get("status") != "COMPLETE" or complete.get("sha256") != composed.get("sha256")
            or complete.get("frames") != contract["frames"]):
        raise DeliveryError("COMPOSITION_RECEIPT_MISMATCH")
    expected = _public_manifest(source, complete.get("sha256SumsSHA256"))
    if expected["WORLD_ENGINE_AUTO_VIDEO.mp4"] != complete["sha256"]:
        raise DeliveryError("COMPOSITION_MP4_HASH_MISMATCH")
    account = pwd.getpwuid(1000)
    try:
        session = storage.StorageSession.create(account, base=Path(private_base or source.parent), export_root=Path(export_root))
        session.preflight()
    except storage.StorageError as error:
        raise DeliveryError(error.code) from None
    private = export = public_fd = target = None
    started = time.monotonic()
    try:
        private = session._private_fd()
        export = session._export_fd(private)
        public_fd = storage._open_directory(source, safe_parents=True, account_uid=1000)
        for name, digest in expected.items():
            session._source_digest(public_fd, name, digest)
        name, target = storage._new_directory(export, "video-")
        # This unit contains public files only. Logs, receipt and source stay out.
        output = []
        for filename in sorted(PUBLIC):
            output.append(session._copy_public_file(public_fd, target, filename, expected[filename]))
        storage._shared_fsync(target)
        report = {"schema": "WORLD_ENGINE_UNIVERSAL_EXPORT_V2", "status": "MOUNTED_EXPORT_VERIFIED", "files": output,
                  "exportDirectory": session.export_name + "/" + name, "exportSeconds": time.monotonic() - started,
                  "sha256SumsSHA256": expected["SHA256SUMS"], **FLAGS}
        # Receipt remains private, not in the public-review folder.
        module._json(session.private_root / "UNIVERSAL_EXPORT_COMPLETE.json", report)
        return {**report, "privateReceipt": str(session.private_root / "UNIVERSAL_EXPORT_COMPLETE.json")}
    except storage.StorageError as error:
        raise DeliveryError(error.code) from None
    finally:
        for descriptor in (target, public_fd, export, private):
            if descriptor is not None:
                os.close(descriptor)


# The coordinator can use either descriptive entrypoint without a second engine.
export_completed = export_video


def _expected_rows(value, names):
    rows = value.get("files")
    if not isinstance(rows, list) or len(rows) != len(names):
        raise DeliveryError("EXPORTED_FILE_RECEIPT_INVALID")
    result = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"file", "sha256", "bytes"} or row.get("file") not in names
                or row["file"] in result or not isinstance(row.get("sha256"), str) or not HASH.fullmatch(row["sha256"])
                or type(row.get("bytes")) is not int or not 1 <= row["bytes"] <= 4 * 1024**3):
            raise DeliveryError("EXPORTED_FILE_RECEIPT_INVALID")
        result[row["file"]] = row
    return result


def _open_export(storage, root, location, kind):
    if (not isinstance(location, str) or not re.fullmatch(r"world-engine-export-[0-9a-f]{24}/" + kind + r"-[0-9a-f]{24}", location)):
        raise DeliveryError("EXPORTED_DIRECTORY_INVALID")
    root_fd = storage._open_directory(Path(root).absolute())
    parent = child = None
    try:
        first, second = location.split("/")
        parent = os.open(first, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        child = os.open(second, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        return child
    except BaseException:
        if child is not None:
            os.close(child)
        raise
    finally:
        if parent is not None:
            os.close(parent)
        os.close(root_fd)


def _rehash_shared(storage, directory, expected, *, collect=False):
    descriptor = os.open(expected["file"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = storage._file_info(descriptor)  # Shared mounts need not preserve UID.
        if before.st_size != expected["bytes"] or (collect and before.st_size > 16384):
            raise DeliveryError("EXPORTED_FILE_SIZE_CHANGED")
        digest, size, body = hashlib.sha256(), 0, bytearray()
        for chunk in iter(lambda: os.read(descriptor, 1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
            if size > expected["bytes"]:
                raise DeliveryError("EXPORTED_FILE_SIZE_CHANGED")
            if collect:
                body.extend(chunk)
        after = os.fstat(descriptor)
        current = os.stat(expected["file"], dir_fd=directory, follow_symlinks=False)
        if (digest.hexdigest() != expected["sha256"] or size != expected["bytes"]
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)):
            raise DeliveryError("EXPORTED_FILE_SHA256_OR_IDENTITY_CHANGED")
        return bytes(body) if collect else None
    finally:
        os.close(descriptor)


def verify_mounted_export(result, export_root):
    """Read-only rehash from trusted job receipt; no render or successful replay."""
    storage = _storage()
    directory = None
    try:
        if (not isinstance(result, dict) or result.get("schema") != "WORLD_ENGINE_UNIVERSAL_EXPORT_V2"
                or result.get("status") != "MOUNTED_EXPORT_VERIFIED"):
            raise DeliveryError("COMPLETED_EXPORT_RECEIPT_INVALID")
        expected = _expected_rows(result, PUBLIC)
        if expected["SHA256SUMS"]["sha256"] != result.get("sha256SumsSHA256"):
            raise DeliveryError("EXPORTED_MANIFEST_ANCHOR_MISMATCH")
        directory = _open_export(storage, export_root, result.get("exportDirectory"), "video")
        if set(os.listdir(directory)) != PUBLIC:
            raise DeliveryError("EXACT_PUBLIC_ALLOWLIST_REQUIRED")
        bodies = {}
        for name, row in expected.items():
            bodies[name] = _rehash_shared(storage, directory, row, collect=name != "WORLD_ENGINE_AUTO_VIDEO.mp4")
        sums = "".join(f"{expected[name]['sha256']}  {name}\n" for name in ("WORLD_ENGINE_AUTO_VIDEO.mp4", "QUALITY_SUMMARY.json"))
        if bodies["SHA256SUMS"] != sums.encode("ascii"):
            raise DeliveryError("EXPORTED_MANIFEST_CONTENT_INVALID")
        _safe_summary(json.loads(bodies["QUALITY_SUMMARY.json"]))
        return {**result, **FLAGS, "reverification": "MOUNTED_BYTES_REHASHED"}
    except DeliveryError:
        raise
    except Exception:
        raise DeliveryError("COMPLETED_EXPORT_REVALIDATION_FAILED") from None
    finally:
        if directory is not None:
            os.close(directory)


def _canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def export_scene_checkpoint(plan, scene, segment, shared_root, private_root=None, *, private_base=None):
    """Mounted-only, NONPUBLIC MP4+SHA recovery copy with private trust anchor.

    A retained private POSIX anchor is mandatory for later trust. Shared files
    cannot authenticate NVIDIA provenance after the private ledger is lost.
    """
    storage, module = _storage(), _compose()
    source = Path(segment["path"]).absolute()
    if (source.name != "segment.mp4" or segment.get("technical") != "PASS" or segment.get("frameCountVerified") is not True
            or segment.get("fullDecodeVerified") is not True or type(segment.get("testOnly")) is not bool
            or (not segment["testOnly"] and segment.get("hardwareVerified") is not True)
            or any(segment.get(key) != scene.get(key) for key in ("sceneId", "startFrame", "endFrame"))
            or not isinstance(segment.get("sha256"), str) or not HASH.fullmatch(segment["sha256"])):
        raise DeliveryError("VERIFIED_SCENE_CHECKPOINT_REQUIRED")
    if module.digest_file(source) != segment["sha256"]:
        raise DeliveryError("SCENE_CHECKPOINT_SOURCE_HASH_MISMATCH")
    base = Path(private_base or private_root or source.parent)
    session = storage.StorageSession.create(pwd.getpwuid(1000), base=base, export_root=Path(shared_root))
    session.preflight()
    private = export = src = target = None
    try:
        private = session._private_fd()
        export = session._export_fd(private)
        src = storage._open_directory(source.parent, safe_parents=True, account_uid=1000)
        storage._private_check(src, pwd.getpwuid(1000))
        session._source_digest(src, source.name, segment["sha256"])
        sums = f"{segment['sha256']}  segment.mp4\n".encode("ascii")
        storage._new_file(private, "SHA256SUMS", sums, private=True)
        name, target = storage._new_directory(export, "scene-recovery-")
        files = [session._copy_public_file(src, target, "segment.mp4", segment["sha256"]),
                 session._copy_public_file(private, target, "SHA256SUMS", hashlib.sha256(sums).hexdigest())]
        storage._shared_fsync(target)
        anchor = {"schema": "WORLD_ENGINE_PRIVATE_SCENE_CHECKPOINT_ANCHOR_V2", "sceneId": scene["sceneId"],
                  "startFrame": scene["startFrame"], "endFrame": scene["endFrame"], "planSHA256": _canonical_sha(plan),
                  "sceneSHA256": _canonical_sha(scene), "files": files, "exportDirectory": session.export_name + "/" + name,
                  "sha256SumsSHA256": hashlib.sha256(sums).hexdigest(), "testOnly": segment["testOnly"],
                  "hardwareVerified": segment.get("hardwareVerified") is True, "publicReview": False,
                  "trust": "RETAINED_PRIVATE_ANCHOR_REQUIRED", **FLAGS}
        written = storage._new_file(private, "SCENE_CHECKPOINT_ANCHOR.json",
                                    (json.dumps(anchor, sort_keys=True, allow_nan=False) + "\n").encode(), private=True)
        os.fsync(private)
        return {**anchor, "status": "SCENE_CHECKPOINT_MOUNTED_VERIFIED",
                "privateAnchor": str(session.private_root / "SCENE_CHECKPOINT_ANCHOR.json"), "privateAnchorSHA256": written["sha256"]}
    except storage.StorageError as error:
        raise DeliveryError(error.code) from None
    finally:
        for descriptor in (target, src, export, private):
            if descriptor is not None:
                os.close(descriptor)


def verify_scene_checkpoint(checkpoint, export_root):
    """Revalidate retained private anchor first, then untrusted recovery bytes."""
    storage = _storage()
    private = anchor_fd = shared = None
    try:
        if (not isinstance(checkpoint, dict) or checkpoint.get("schema") != "WORLD_ENGINE_PRIVATE_SCENE_CHECKPOINT_ANCHOR_V2"
                or checkpoint.get("status") != "SCENE_CHECKPOINT_MOUNTED_VERIFIED"):
            raise DeliveryError("PRIVATE_SCENE_ANCHOR_REQUIRED")
        anchor_sha = checkpoint.get("privateAnchorSHA256")
        if not isinstance(anchor_sha, str) or not HASH.fullmatch(anchor_sha):
            raise DeliveryError("PRIVATE_SCENE_ANCHOR_REQUIRED")
        anchor_path = Path(checkpoint["privateAnchor"])
        if anchor_path.name != "SCENE_CHECKPOINT_ANCHOR.json":
            raise DeliveryError("PRIVATE_SCENE_ANCHOR_REQUIRED")
        private = storage._open_directory(anchor_path.parent, safe_parents=True, account_uid=1000)
        storage._private_check(private, pwd.getpwuid(1000))
        anchor_fd = os.open(anchor_path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=private)
        before = storage._file_info(anchor_fd, uid=1000, private=True)
        body = storage._read_fd(anchor_fd, limit=16384)
        after = os.fstat(anchor_fd)
        if (hashlib.sha256(body).hexdigest() != anchor_sha
                or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)):
            raise DeliveryError("PRIVATE_SCENE_ANCHOR_CORRUPT")
        anchor = json.loads(body)
        if (anchor.get("schema") != "WORLD_ENGINE_PRIVATE_SCENE_CHECKPOINT_ANCHOR_V2"
                or anchor.get("publicReview") is not False or anchor.get("trust") != "RETAINED_PRIVATE_ANCHOR_REQUIRED"
                or any(anchor.get(key) != checkpoint.get(key) for key in ("sceneId", "startFrame", "endFrame", "planSHA256", "sceneSHA256",
                                                                        "exportDirectory", "files", "testOnly", "hardwareVerified"))):
            raise DeliveryError("PRIVATE_SCENE_ANCHOR_MISMATCH")
        expected = _expected_rows(anchor, {"segment.mp4", "SHA256SUMS"})
        if expected["SHA256SUMS"]["sha256"] != anchor.get("sha256SumsSHA256"):
            raise DeliveryError("SCENE_CHECKPOINT_MANIFEST_INVALID")
        shared = _open_export(storage, export_root, anchor["exportDirectory"], "scene-recovery")
        if set(os.listdir(shared)) != {"segment.mp4", "SHA256SUMS"}:
            raise DeliveryError("SCENE_CHECKPOINT_ALLOWLIST_REQUIRED")
        _rehash_shared(storage, shared, expected["segment.mp4"])
        body = _rehash_shared(storage, shared, expected["SHA256SUMS"], collect=True)
        if body != f"{expected['segment.mp4']['sha256']}  segment.mp4\n".encode():
            raise DeliveryError("SCENE_CHECKPOINT_MANIFEST_INVALID")
        return {**checkpoint, **FLAGS, "reverification": "PRIVATE_ANCHOR_AND_MOUNTED_BYTES_REHASHED"}
    except DeliveryError:
        raise
    except Exception:
        raise DeliveryError("PRIVATE_SCENE_CHECKPOINT_REVALIDATION_FAILED") from None
    finally:
        for descriptor in (shared, anchor_fd, private):
            if descriptor is not None:
                os.close(descriptor)


def verify_external(public_dir, urls, destination, anchor, *, opener=None):
    """Actual HTTP 200 plus independently anchored streamed download hashes.

    A supplied opener is explicitly SYNTHETIC and cannot yield delivery PASS.
    Missing URLs do not trigger discovery, publishing, credentials or retries.
    """
    source = Path(public_dir)
    expected = _public_manifest(source, anchor)
    verifier, module = _verifier(), _compose()
    if not isinstance(urls, dict) or set(urls) != PUBLIC:
        raise DeliveryError("EXACT_PRIVATE_DROPBOX_URL_MAP_REQUIRED")
    for url in urls.values():
        verifier.validate_dropbox_url(url)
    root = Path(destination)
    try:
        root.mkdir(mode=0o700)
    except OSError:
        raise DeliveryError("FRESH_DOWNLOAD_DIRECTORY_REQUIRED") from None
    client = opener or urllib.request.build_opener(verifier.DropboxRedirect())
    files, started = [], time.monotonic()
    for name in sorted(PUBLIC):
        limit = 4 * 1024**3 if name.endswith(".mp4") else 16384
        digest, count = hashlib.sha256(), 0
        try:
            request = urllib.request.Request(urls[name], headers={"User-Agent": "WorldEngineUniversalDelivery/2"})
            with client.open(request, timeout=30) as response:
                verifier.validate_dropbox_url(response.geturl())
                if response.status != 200:
                    raise DeliveryError("DOWNLOAD_HTTP_200_REQUIRED")
                if not callable(getattr(response, "read1", None)):
                    raise DeliveryError("BOUNDED_DOWNLOAD_STREAM_REQUIRED")
                value = response.headers.get("Content-Length")
                if value is not None and (not value.isdecimal() or not 0 < int(value) <= limit):
                    raise DeliveryError("DOWNLOAD_SIZE_LIMIT")
                fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as output:
                    while True:
                        if time.monotonic() - started > 1800:
                            raise DeliveryError("DOWNLOAD_TOTAL_TIMEOUT")
                        chunk = response.read1(module.CHUNK)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > limit:
                            raise DeliveryError("DOWNLOAD_SIZE_LIMIT")
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if not count or (value is not None and int(value) != count) or digest.hexdigest() != expected[name]:
                    raise DeliveryError("DOWNLOADED_SHA256_OR_SIZE_MISMATCH")
                files.append({"file": name, "httpStatus": 200, "bytes": count, "sha256": digest.hexdigest()})
        except DeliveryError:
            raise
        except Exception:
            raise DeliveryError("EXTERNAL_DOWNLOAD_FAILED") from None
    _public_manifest(root, anchor)
    return {"schema": "WORLD_ENGINE_UNIVERSAL_EXTERNAL_DELIVERY_V2", "status": "SYNTHETIC_ONLY" if opener else "EXTERNAL_DELIVERY_VERIFIED",
            "files": files, "externalDownloadVerified": opener is None, "remotePersistenceVerified": opener is None,
            "synthetic": opener is not None, "downloadVerificationSeconds": time.monotonic() - started,
            "visualQuality": "USER_VIDEO_REVIEW_REQUIRED", "finalPromotion": False}
