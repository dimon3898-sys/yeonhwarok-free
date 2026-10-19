"""Source-bound data admission reused by the overnight extension.

This module neither acquires data nor grants render/image/cost approval.  The
existing four-file authority, source catalog and history admission remain the
owners.  A city point or a national flag cannot become a historical unit plan.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "universal-integration-completion-v2"
SOURCE_ROLES = frozenset({"GEOMETRY", "METRIC", "OBJECT_GRAPHIC", "FLOW_PLAN", "AREA_INTENT",
                          "NATIONAL_UNIT_SCENE", "SCALAR_CONTROL_PLAN"})
EXTENSION_SCHEMA = "WORLD_ENGINE_OVERNIGHT_SOURCE_EXTENSION_V1"
CATALOG_LIMIT = 4 * 1024 * 1024


class DataReadinessError(ValueError):
    pass


def _fail(code):
    raise DataReadinessError(code)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bytes(path, limit=16 * 1024 * 1024):
    """Read only an existing confined regular metadata file, never a symlink."""
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
        _fail("OVERNIGHT_DATA_METADATA_UNAVAILABLE_OR_UNSAFE")
    if not 0 < path.stat().st_size <= limit:
        _fail("OVERNIGHT_DATA_METADATA_BOUNDED_FILE_REQUIRED")
    return path.read_bytes()


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError):
        _fail("OVERNIGHT_DATA_CANONICAL_JSON_REQUIRED")


def canonical_catalog_bytes(value):
    """Use the original JS canonical owner, including its number semantics.

    Python serializes 80.0 differently from JS JSON.stringify(80).  Reusing the
    existing canonicalSourceJSON prevents a new catalog or payload SHA from
    disagreeing with the actual browser/Event/Flow/visual consumer.
    """
    raw = _canonical(value)
    if len(raw) > CATALOG_LIMIT:
        _fail("OVERNIGHT_DATA_CATALOG_TOO_LARGE")
    script = ("import {canonicalSourceJSON} from "
              + json.dumps((PARENT / "event_flow_binding.mjs").as_uri())
              + "; let raw=''; for await(const chunk of process.stdin){raw+=chunk;}"
                " process.stdout.write(canonicalSourceJSON(JSON.parse(raw)));")
    try:
        result = subprocess.run(["node", "--no-warnings", "--input-type=module", "-e", script],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        _fail("OVERNIGHT_DATA_ORIGINAL_CANONICAL_OWNER_UNAVAILABLE")
    if result.returncode or len(result.stdout) > CATALOG_LIMIT:
        _fail("OVERNIGHT_DATA_ORIGINAL_CANONICAL_OWNER_FAILED")
    return result.stdout


def _strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                _fail("OVERNIGHT_DATA_JSON_DUPLICATE_FIELD")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda value: _fail("OVERNIGHT_DATA_NONFINITE_JSON_FORBIDDEN"))
    except (ValueError, UnicodeError):
        _fail("OVERNIGHT_DATA_JSON_INVALID")


def _validate_json_numbers(value):
    if isinstance(value, dict):
        for item in value.values():
            _validate_json_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_numbers(item)
    elif type(value) is int and abs(value) > 9007199254740991:
        _fail("OVERNIGHT_DATA_SAFE_JSON_NUMBER_REQUIRED")
    elif type(value) is float and not math.isfinite(value):
        _fail("OVERNIGHT_DATA_NONFINITE_JSON_FORBIDDEN")


def merge_source_catalog(parent_catalog, extension, *, parent_sha256, extension_sha256,
                         allow_synthetic=False):
    """Pure merge of already package-owned authorities; never infer new roles.

    This helper is also usable by isolated CPU tests. Production callers use
    load_effective_catalog(), which verifies both on-disk manifest authorities.
    A caller-supplied prompt catalog is never an authority.
    """
    if (not isinstance(parent_catalog, dict)
            or parent_catalog.get("schema") != "WORLD_ENGINE_COMPLETION_SOURCE_CATALOG_V1"
            or not isinstance(parent_catalog.get("trustedSources"), list)
            or not isinstance(extension, dict)
            or set(extension) != {"schema", "parentCatalogSHA256", "trustedSources"}
            or extension["schema"] != EXTENSION_SCHEMA
            or extension["parentCatalogSHA256"] != parent_sha256
            or not re.fullmatch(r"[a-f0-9]{64}", str(parent_sha256))
            or not re.fullmatch(r"[a-f0-9]{64}", str(extension_sha256))
            or not isinstance(extension["trustedSources"], list)
            or len(extension["trustedSources"]) > 128 or type(allow_synthetic) is not bool):
        _fail("OVERNIGHT_DATA_EXTENSION_AUTHORITY_INVALID")
    found = {row.get("sourceId") for row in parent_catalog["trustedSources"] if isinstance(row, dict)}
    if len(found) != len(parent_catalog["trustedSources"]):
        _fail("OVERNIGHT_DATA_PARENT_CATALOG_IDENTITIES_INVALID")
    extra = []
    for row in extension["trustedSources"]:
        if (not isinstance(row, dict)
                or set(row) != {"sourceId", "sha256", "role", "verificationStatus", "payload"}
                or not isinstance(row["sourceId"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", row["sourceId"])
                or row["sourceId"] in found or row["role"] not in SOURCE_ROLES
                or not re.fullmatch(r"[a-f0-9]{64}", str(row["sha256"]))
                or row["verificationStatus"] not in {"VERIFIED", "SYNTHETIC_TEST"}
                or not isinstance(row["payload"], dict)):
            _fail("OVERNIGHT_DATA_EXTENSION_ROLE_OR_ID_INVALID")
        if row["verificationStatus"] == "SYNTHETIC_TEST" and not allow_synthetic:
            _fail("OVERNIGHT_DATA_SYNTHETIC_NOT_PRODUCTION")
        _validate_json_numbers(row["payload"])
        if hashlib.sha256(canonical_catalog_bytes(row["payload"])).hexdigest() != row["sha256"]:
            _fail("OVERNIGHT_DATA_EXTENSION_PAYLOAD_SHA_MISMATCH")
        found.add(row["sourceId"])
        extra.append(deepcopy(row))
    result = deepcopy(parent_catalog)
    result["trustedSources"].extend(extra)
    result["overnightExtension"] = {"schema": EXTENSION_SCHEMA,
        "parentCatalogSHA256": parent_sha256, "extensionSHA256": extension_sha256,
        "sourceCount": len(extra)}
    canonical = canonical_catalog_bytes(result)
    return result, canonical, hashlib.sha256(canonical).hexdigest()


def load_effective_catalog(*, parent_root=PARENT, extension_root=HERE, allow_synthetic=False):
    """Load the additive package authority and return (catalog, bytes, SHA).

    No parent file is written. Extra records can be added by a separately
    reviewed new package instead of changing the preserved completion catalog.
    The public Studio path always leaves allow_synthetic=False.
    """
    parent_root, root = Path(parent_root), Path(extension_root)
    parent = load_existing_catalog(parent_root)
    parent_sha = hashlib.sha256(_bytes(parent_root / "SOURCE_DATA_CATALOG.json")).hexdigest()
    manifest = _strict_json(_bytes(root / "OVERNIGHT_FILES.json"))
    if manifest.get("schema") != "WORLD_ENGINE_OVERNIGHT_FILES_V1":
        _fail("OVERNIGHT_DATA_EXTENSION_MANIFEST_REQUIRED")
    raw = _bytes(root / "EXTENSION_SOURCES.json", CATALOG_LIMIT)
    digest = hashlib.sha256(raw).hexdigest()
    if manifest.get("files", {}).get("EXTENSION_SOURCES.json") != digest:
        _fail("OVERNIGHT_DATA_EXTENSION_MANIFEST_SHA_MISMATCH")
    return merge_source_catalog(parent, _strict_json(raw), parent_sha256=parent_sha,
                               extension_sha256=digest, allow_synthetic=allow_synthetic)


def admit_capture_sources(submission, catalog):
    """Bind old history and new supplied subevents without changing old data.

    Only the COPY used for the old history authority has its optional subevent
    array emptied. The ORIGINAL request is then validated by its original
    Event/Flow/Area compiler against the actual package-merged catalog. No
    ignored field, unverified source, or historical coordinate is synthesized.
    """
    expected, expected_bytes, expected_sha = load_effective_catalog()
    if canonical_catalog_bytes(catalog) != expected_bytes:
        _fail("OVERNIGHT_DATA_CAPTURE_CATALOG_NOT_PACKAGE_AUTHORITY")
    if not isinstance(submission, dict):
        _fail("OVERNIGHT_DATA_CAPTURE_SUBMISSION_INVALID")
    before = _canonical(submission)
    copied = deepcopy(submission)
    try:
        original_request = deepcopy(submission["completionV2"]["eventFlow"])
        copied["completionV2"]["eventFlow"] = {
            "schema": "WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1", "events": [], "flows": [], "areas": []}
        original = (Path("/opt/world-engine-production-studio") if HERE.is_relative_to("/opt")
                    else PARENT.parent / "production-studio-mvp-v1")
        previous_path = list(sys.path)
        try:
            sys.path.insert(0, str(original))
            old = _load(PARENT / "runtime_bridge.py", "_overnight_preserved_history_bridge")
            result = old.data_admission(copied)
        finally:
            sys.path[:] = previous_path
        plan = submission["videoPlan"]
        event = _load(PARENT / "event_flow_contract.py", "_overnight_preserved_event_flow_authority")
        event_receipt = event.validate_event_flow(original_request, fps=plan["fps"],
            total_frames=plan["totalFrames"], trusted_sources=expected["trustedSources"])
    except (KeyError, TypeError):
        _fail("OVERNIGHT_DATA_CAPTURE_SUBMISSION_INVALID")
    if _canonical(submission) != before:
        _fail("OVERNIGHT_DATA_CAPTURE_SUBMISSION_MUTATED")
    result["eventFlowAdmission"] = event_receipt
    result["effectiveSourceCatalogSHA256"] = expected_sha
    result["parentHistorySourceUnchanged"] = True
    result["renderAllowed"] = False
    return result


def load_existing_catalog(parent_root=PARENT):
    """Return the preserved catalog only after its existing manifest SHA check."""
    root = Path(parent_root)
    manifest = json.loads(_bytes(root / "COMPLETION_FILES.json"))
    expected = manifest.get("files", {}).get("SOURCE_DATA_CATALOG.json")
    raw = _bytes(root / "SOURCE_DATA_CATALOG.json")
    if not isinstance(expected, str) or hashlib.sha256(raw).hexdigest() != expected:
        _fail("OVERNIGHT_DATA_CATALOG_MANIFEST_MISMATCH")
    catalog = json.loads(raw)
    if (catalog.get("schema") != "WORLD_ENGINE_COMPLETION_SOURCE_CATALOG_V1"
            or not isinstance(catalog.get("trustedSources"), list)):
        _fail("OVERNIGHT_DATA_SOURCE_CATALOG_INVALID")
    return catalog


def resolve_source_reference(catalog, reference, *, expected_role):
    """Resolve a reference against backend-owned source authority, not user data.

    Callers must obtain ``catalog`` from ``load_existing_catalog`` or their own
    verified server-side manifest owner.  This does not trust a prompt-supplied
    catalog and does not turn an optional role into supplied historical data.
    """
    if expected_role not in SOURCE_ROLES:
        _fail("OVERNIGHT_DATA_SOURCE_ROLE_UNSUPPORTED")
    if (not isinstance(reference, dict) or set(reference) != {"sourceId", "sha256"}
            or not isinstance(reference["sourceId"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", str(reference["sha256"]))):
        _fail("OVERNIGHT_DATA_SOURCE_REFERENCE_INVALID")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("trustedSources"), list):
        _fail("OVERNIGHT_DATA_SOURCE_CATALOG_INVALID")
    matches = [row for row in catalog["trustedSources"]
               if isinstance(row, dict) and row.get("sourceId") == reference["sourceId"]]
    if len(matches) != 1:
        _fail("OVERNIGHT_DATA_SOURCE_NOT_UNIQUE_OR_UNAVAILABLE")
    row = matches[0]
    if row.get("role") != expected_role or row.get("verificationStatus") != "VERIFIED":
        _fail("OVERNIGHT_DATA_SOURCE_ROLE_OR_REVIEW_MISMATCH")
    actual = hashlib.sha256(canonical_catalog_bytes(row.get("payload"))).hexdigest()
    if row.get("sha256") != actual or reference["sha256"] != actual:
        _fail("OVERNIGHT_DATA_SOURCE_PAYLOAD_SHA_MISMATCH")
    return deepcopy(row["payload"])


def assess_existing_data(*, requested=None, plan=None, front_profile=None,
                         image_digest=None, parent_root=PARENT):
    """Reuse exact historical authority and per-capability data blockers.

    Optional production roles remain blocked until their actual source plans
    exist.  Regional raster support never certifies full-scene high detail.
    ``renderAllowed`` always remains false; source admission is not execution.
    """
    parent = Path(parent_root)
    recovery = parent.parent
    catalog = load_existing_catalog(parent)
    source = recovery / "verified-front-data-v4-recovery"
    if plan is None:
        plan = json.loads(_bytes(source / "VIDEO_PLAN_80S.json"))
    if front_profile is None:
        front_profile = json.loads(_bytes(source / "FRONT_PROFILE.json"))
    selected_image = image_digest or plan.get("renderProfile", {}).get("imageDigest")
    binding = _load(parent / "history_source_binding.py", "_overnight_existing_history_source")
    hashes = binding.verify_bound_history_objects(catalog, recovery.resolve(), plan=plan,
                    front_profile=front_profile, image_digest=selected_image)
    history = _load(parent / "history_admission.py", "_overnight_existing_history_admission")
    coverage = json.loads(_bytes(recovery / "universal-integration-v1/reports/TIMELINE_80S_COVERAGE.json"))
    result = history.assess_history(plan, front_profile, coverage=coverage,
                                    requested=requested, source_bindings=hashes)
    result["sourceChecks"]["actualSourceBytesVerifiedByThisAssessment"] = True
    return {"schema": "WORLD_ENGINE_OVERNIGHT_DATA_ADMISSION_V1",
            "status": result["status"], "qualifiedBasePlanAdmitted": result["qualifiedBasePlanAdmitted"],
            "requestedCapabilitiesAdmitted": result["dataAdmitted"],
            "dataAdmission": result,
            "optionalRoleSourceCounts": {role: sum(row.get("role") == role for row in catalog["trustedSources"])
                                          for role in sorted(SOURCE_ROLES)},
            "sourceCatalogSHA256": hashlib.sha256(_bytes(parent / "SOURCE_DATA_CATALOG.json")).hexdigest(),
            "sourceBytesVerified": True, "sourceValuesOrCoordinatesChanged": False,
            "gpuOutputVerified": False, "renderAllowed": False,
            "approvalOwner": "SEPARATE_EXISTING_SOURCE_IMAGE_GPU_COST_AND_USER_QUALITY_GATES"}


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="store_true", required=True,
                        help="Print only the verified public package catalog's canonical JSON.")
    parser.parse_args()
    try:
        sys.stdout.buffer.write(load_effective_catalog()[1])
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", code):
            code = "OVERNIGHT_DATA_EXTENSION_LOAD_FAILED"
        print(json.dumps({"status": "BLOCKED", "errorCode": code}), file=sys.stderr)
        raise SystemExit(2)
