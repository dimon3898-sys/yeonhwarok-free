"""Verify the four declared historical JSON authorities without asset re-audit."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_JSON = 16 * 1024 * 1024
SOURCE_FILE_SPECS = {
    "VIDEO_PLAN_80S.json": {
        "path": "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json",
        "role": "HISTORICAL_EXECUTION_PLAN", "schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2"},
    "FRONT_PROFILE.json": {
        "path": "verified-front-data-v4-recovery/FRONT_PROFILE.json",
        "role": "APPROXIMATE_PARTIAL_FRONT_PROFILE", "schema": "WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4"},
    "FRONT_FILES.json": {
        "path": "verified-front-data-v4-recovery/FRONT_FILES.json",
        "role": "HISTORICAL_SOURCE_MANIFEST", "schema": "WORLD_ENGINE_VERIFIED_FRONT_FILES_V4"},
    "PARENT_PLAN_80S.json": {
        "path": "verified-front-data-v4-recovery/PARENT_PLAN_80S.json",
        "role": "PRESERVED_QUALIFIED_PARENT_PLAN", "schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2"},
}


class HistorySourceBindingError(ValueError):
    pass


def _fail(code):
    raise HistorySourceBindingError(code)


def _open_directory(root):
    value = Path(root)
    if not value.is_absolute() or ".." in value.parts:
        _fail("HISTORY_SOURCE_ROOT_ABSOLUTE_REQUIRED")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in value.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError:
        os.close(descriptor)
        _fail("HISTORY_SOURCE_PATH_UNSAFE_OR_UNAVAILABLE")


def _read_regular(root_descriptor, relative):
    directory = os.dup(root_descriptor)
    descriptor = None
    try:
        parts = relative.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= _MAX_JSON:
            _fail("HISTORY_SOURCE_BOUNDED_REGULAR_JSON_REQUIRED")
        content = bytearray()
        while len(content) < before.st_size:
            chunk = os.read(descriptor, min(1024 * 1024, before.st_size - len(content)))
            if not chunk:
                _fail("HISTORY_SOURCE_CHANGED_DURING_READ")
            content.extend(chunk)
        after = os.fstat(descriptor)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if signature(before) != signature(after):
            _fail("HISTORY_SOURCE_CHANGED_DURING_READ")
        return bytes(content)
    except OSError:
        _fail("HISTORY_SOURCE_PATH_UNSAFE_OR_UNAVAILABLE")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _verify_source_documents(catalog, recovery_root):
    if not isinstance(catalog, dict) or catalog.get("schema") != "WORLD_ENGINE_COMPLETION_SOURCE_CATALOG_V1":
        _fail("HISTORY_SOURCE_CATALOG_SCHEMA_REQUIRED")
    bindings = catalog.get("sourceFileBindings")
    if not isinstance(bindings, dict) or set(bindings) != set(SOURCE_FILE_SPECS):
        _fail("HISTORY_SOURCE_EXACT_FOUR_BINDINGS_REQUIRED")
    for name, expected in SOURCE_FILE_SPECS.items():
        row = bindings[name]
        if (not isinstance(row, dict) or set(row) != {"path", "sha256", "role", "schema"}
                or any(row.get(key) != value for key, value in expected.items())
                or not _SHA.fullmatch(str(row.get("sha256", "")))):
            _fail("HISTORY_SOURCE_WHITELIST_ROLE_OR_SCHEMA_INVALID")
    root_descriptor = _open_directory(recovery_root)
    actual, documents = {}, {}
    try:
        for name, row in bindings.items():
            raw = _read_regular(root_descriptor, row["path"])
            digest = hashlib.sha256(raw).hexdigest()
            if digest != row["sha256"]:
                _fail("HISTORY_SOURCE_ACTUAL_SHA_MISMATCH")
            try:
                document = json.loads(raw, parse_constant=lambda value: _fail("HISTORY_SOURCE_JSON_CONSTANT_INVALID"))
            except (ValueError, UnicodeDecodeError):
                _fail("HISTORY_SOURCE_JSON_INVALID")
            if not isinstance(document, dict) or document.get("schema") != row["schema"]:
                _fail("HISTORY_SOURCE_DOCUMENT_SCHEMA_INVALID")
            actual[name], documents[name] = digest, document
    finally:
        os.close(root_descriptor)
    profile = documents["FRONT_PROFILE.json"]
    manifest = documents["FRONT_FILES.json"]
    plan = documents["VIDEO_PLAN_80S.json"]
    archive = plan.get("sourceManifest", {}).get("archivalFrontV4", {})
    if (archive.get("profileSha256") != actual["FRONT_PROFILE.json"]
            or archive.get("sourceManifestSha256") != actual["FRONT_FILES.json"]
            or profile.get("unchangedBasePlanSha256") != actual["PARENT_PLAN_80S.json"]
            or manifest.get("files", {}).get("FRONT_PROFILE.json") != actual["FRONT_PROFILE.json"]
            or manifest.get("files", {}).get("PARENT_PLAN_80S.json") != actual["PARENT_PLAN_80S.json"]
            or profile.get("runtimeProfile") != "VERIFIED_ARCHIVAL_FRONT_V4"
            or manifest.get("profileId") != "VERIFIED_ARCHIVAL_FRONT_V4"):
        _fail("HISTORY_SOURCE_AUTHORITY_CROSS_BINDING_MISMATCH")
    return actual, documents


def verify_declared_source_files(catalog, recovery_root):
    """Return filename-to-actual-SHA bindings for ``assess_history``.

    The catalog itself must first be admitted by the completion source manifest.
    This checks actual four-file JSON authority and its cross-links. For a
    supplied in-memory plan/profile, use ``verify_bound_history_objects`` so
    declarations cannot stand in for the verified objects themselves.
    """
    actual, _ = _verify_source_documents(catalog, recovery_root)
    return actual


def _exact_json(left, right):
    """Typed equality: booleans/numbers, extra fields and changed arrays differ."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (all(type(key) is str for key in left) and left.keys() == right.keys()
                and all(_exact_json(value, right[key]) for key, value in left.items()))
    if isinstance(left, list):
        return len(left) == len(right) and all(_exact_json(a, b) for a, b in zip(left, right))
    return type(left) in (str, int, float, bool, type(None)) and left == right


def verify_bound_history_objects(catalog, recovery_root, *, plan, front_profile, image_digest):
    """Bind actual assessed objects to verified source, allowing image rebinding.

    Only the existing root and scene ``renderProfile.imageDigest`` slots may
    change. Every slot must name the same caller-selected immutable image. The
    separate image/source-closure admission remains authoritative for whether
    that image can run; this helper grants no image, GPU or user approval.
    """
    if not isinstance(image_digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None:
        _fail("HISTORY_SELECTED_IMMUTABLE_IMAGE_REQUIRED")
    actual, documents = _verify_source_documents(catalog, recovery_root)
    expected = deepcopy(documents["VIDEO_PLAN_80S.json"])
    scenes = expected.get("scenes")
    if (not isinstance(scenes, list) or not scenes
            or not isinstance(expected.get("renderProfile"), dict)
            or "imageDigest" not in expected["renderProfile"]):
        _fail("HISTORY_SOURCE_EXISTING_IMAGE_SLOTS_REQUIRED")
    expected["renderProfile"]["imageDigest"] = image_digest
    for scene in scenes:
        if (not isinstance(scene, dict) or not isinstance(scene.get("renderProfile"), dict)
                or "imageDigest" not in scene["renderProfile"]):
            _fail("HISTORY_SOURCE_EXISTING_IMAGE_SLOTS_REQUIRED")
        scene["renderProfile"]["imageDigest"] = image_digest
    if not _exact_json(plan, expected):
        _fail("HISTORY_ASSESSED_PLAN_DIFFERS_FROM_VERIFIED_SOURCE")
    if not _exact_json(front_profile, documents["FRONT_PROFILE.json"]):
        _fail("HISTORY_ASSESSED_FRONT_PROFILE_DIFFERS_FROM_VERIFIED_SOURCE")
    return actual
