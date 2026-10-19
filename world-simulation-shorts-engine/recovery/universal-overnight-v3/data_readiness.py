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
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "universal-integration-completion-v2"
SOURCE_ROLES = frozenset({"GEOMETRY", "OBJECT_GRAPHIC", "FLOW_PLAN", "NATIONAL_UNIT_SCENE",
                          "SCALAR_CONTROL_PLAN"})


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
    actual = hashlib.sha256(_canonical(row.get("payload"))).hexdigest()
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
