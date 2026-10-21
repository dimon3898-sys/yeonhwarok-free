"""Opt-in, source-bound Event Director input; never a GPU/quality approval.

Original Studio parsers, source-safe file reads and V1/V2 callbacks are reused.
Request refs are claims until matched against a server-owned explicit allowlist.
Unknown history remains unknown, including in QUALIFIED_SOURCE_REVIEW.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "production-studio-mvp-v1"
if str(ORIGINAL) not in sys.path:
    sys.path.insert(0, str(ORIGINAL))
from studio_contracts import StudioContractError, _bounded_json, _parse_json

SCHEMA = "WORLD_ENGINE_EVENT_DIRECTOR_REQUEST_V1"
REFS = ("eventDirectorProfileRef", "controlTimelineRef", "cameraAdmissionRef",
        "sourceCatalogRef", "markerEvidenceRef", "audioCueManifestRef")
FIELDS = {"schema", "sourcePlanSha256", "subjectId", "fps", "totalFrames",
          "requiredCapabilities", "purpose", *REFS}
PURPOSES = {"PRODUCTION", "QUALIFIED_SOURCE_REVIEW"}
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Its descriptor walking and bounded regular-file reads are preserved unchanged.
_safe_source = _load("_astra_director_preserved_source_reader",
    HERE.parent / "universal-integration-completion-v2/history_source_binding.py")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_sha(value):
    return _sha(json.dumps(value, ensure_ascii=False, allow_nan=False,
                           sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _actual(value):
    # Type summaries avoid reflecting tokens, paths or full arbitrary JSON.
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object" if isinstance(value, dict) else "non-JSON"


def _error(code, path, expected, value=None):
    error = StudioContractError(code, "사건 감독 입력의 필드·자료·해시를 확인하세요.", [path])
    error.issues = [{"path": path, "expected": expected, "actual": _actual(value)}]
    raise error


def _blocked(code, path, detail):
    return {"code": code, "path": path, "detail": detail, "status": "BLOCKED"}


def _regular_absolute(path):
    target = Path(path)
    if not target.is_absolute() or ".." in target.parts:
        _error("DIRECTOR_SOURCE_ROOT_INVALID", "sourcePlanSha256", "server-owned absolute regular file")
    fd = None
    try:
        fd = _safe_source._open_directory(target.parent)
        return _safe_source._read_regular(fd, target.name)
    except (OSError, ValueError):
        _error("DIRECTOR_SOURCE_FILE_UNAVAILABLE", "sourcePlanSha256", "readable non-symlink regular file")
    finally:
        if fd is not None:
            import os
            os.close(fd)


def _path(value, field):
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or ":" in value or "?" in value or "#" in value
            or PurePosixPath(value).is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        _error("DIRECTOR_REFERENCE_PATH_INVALID", field + ".path", "canonical relative local path", value)
    return value


def _parse_document(raw, field):
    try:
        value = _parse_json(raw.decode("utf-8"))
    except (StudioContractError, UnicodeDecodeError):
        _error("DIRECTOR_REFERENCE_JSON_INVALID", field, "bounded unique-key finite UTF-8 JSON object")
    if not isinstance(value, dict):
        _error("DIRECTOR_REFERENCE_JSON_INVALID", field, "JSON object", value)
    return value


def _request(value):
    _bounded_json(value)
    if not isinstance(value, dict):
        _error("DIRECTOR_REQUEST_OBJECT_REQUIRED", "prompt", "JSON object", value)
    extra = sorted(set(value) - FIELDS)
    if extra:
        _error("DIRECTOR_FIELD_UNSUPPORTED", extra[0], "supported Event Director field", value[extra[0]])
    for field in sorted(FIELDS - {"purpose"}):
        if field not in value:
            _error("DIRECTOR_FIELD_REQUIRED", field, "explicit required field, not an inferred default")
    if value["schema"] != SCHEMA:
        _error("DIRECTOR_SCHEMA_UNSUPPORTED", "schema", SCHEMA, value["schema"])
    if not isinstance(value["sourcePlanSha256"], str) or not _HEX.fullmatch(value["sourcePlanSha256"]):
        _error("DIRECTOR_SOURCE_SHA_INVALID", "sourcePlanSha256", "64 lowercase hexadecimal characters", value["sourcePlanSha256"])
    if not isinstance(value["subjectId"], str) or not _NAME.fullmatch(value["subjectId"]):
        _error("DIRECTOR_SUBJECT_INVALID", "subjectId", "nonempty portable source subject ID", value["subjectId"])
    for field, low, high in (("fps", 1, 120), ("totalFrames", 2, 2_000_000)):
        if type(value[field]) is not int or not low <= value[field] <= high:
            _error("DIRECTOR_TIME_VALUE_INVALID", field, f"integer {low}..{high}", value[field])
    caps = value["requiredCapabilities"]
    if (not isinstance(caps, list) or not caps or len(caps) > 256
            or any(not isinstance(x, str) or not _NAME.fullmatch(x) for x in caps)
            or len(set(caps)) != len(caps)):
        _error("DIRECTOR_CAPABILITIES_INVALID", "requiredCapabilities", "1..256 unique capability IDs", caps)
    result = deepcopy(value)
    result.setdefault("purpose", "PRODUCTION")
    if not isinstance(result["purpose"], str) or result["purpose"] not in PURPOSES:
        _error("DIRECTOR_PURPOSE_UNSUPPORTED", "purpose", "PRODUCTION or QUALIFIED_SOURCE_REVIEW", result["purpose"])
    for field in REFS:
        ref = result[field]
        # Explicit null is a diagnosable incomplete request, never a ready ref.
        if ref is None:
            continue
        if not isinstance(ref, dict) or set(ref) != {"path", "version", "sha256"}:
            _error("DIRECTOR_REFERENCE_FIELDS_INVALID", field, "path/version/sha256 object or explicit blocked null", ref)
        _path(ref["path"], field)
        if (not isinstance(ref["version"], str) or not ref["version"].strip()
                or len(ref["version"]) > 128 or any(ord(c) < 32 for c in ref["version"])):
            _error("DIRECTOR_REFERENCE_VERSION_INVALID", field + ".version", "nonempty version string", ref["version"])
        if not isinstance(ref["sha256"], str) or not _HEX.fullmatch(ref["sha256"]):
            _error("DIRECTOR_REFERENCE_SHA_INVALID", field + ".sha256", "64 lowercase hexadecimal characters", ref["sha256"])
    return result


def _read_ref(ref, field, root, trusted_refs):
    name = _path(ref["path"], field)
    binding = trusted_refs.get(name)
    if (not isinstance(binding, dict) or binding.get("role") != field
            or binding.get("sha256") != ref["sha256"] or str(binding.get("version")) != ref["version"]):
        _error("DIRECTOR_REFERENCE_NOT_AUTHORIZED", field, "exact server-owned path/role/version/SHA binding", ref)
    fd = None
    try:
        fd = _safe_source._open_directory(root)
        raw = _safe_source._read_regular(fd, name)
    except (OSError, ValueError):
        _error("DIRECTOR_REFERENCE_UNAVAILABLE", field, "safe existing bounded regular source file", ref)
    finally:
        if fd is not None:
            import os
            os.close(fd)
    if _sha(raw) != ref["sha256"]:
        _error("DIRECTOR_REFERENCE_SHA_MISMATCH", field + ".sha256", "SHA-256 of actual original bytes", ref["sha256"])
    document = _parse_document(raw, field)
    if str(document.get("version")) != ref["version"]:
        _error("DIRECTOR_REFERENCE_VERSION_MISMATCH", field + ".version", "actual document version", ref["version"])
    return document


def _range_rows(rows, total, path):
    if not isinstance(rows, list) or not rows:
        _error("DIRECTOR_TIMELINE_REQUIRED", path, "nonempty contiguous half-open timeline", rows)
    end = 0
    for i, row in enumerate(rows):
        if (not isinstance(row, dict) or type(row.get("startFrame")) is not int
                or type(row.get("endFrame")) is not int or row["startFrame"] != end
                or not end < row["endFrame"] <= total):
            _error("DIRECTOR_TIMELINE_GAP_OR_OVERLAP", f"{path}[{i}]", "exact contiguous [startFrame,endFrame) range", row)
        end = row["endFrame"]
    if end != total:
        _error("DIRECTOR_TIMELINE_TOTAL_MISMATCH", path, "coverage exactly equal to totalFrames", rows)


def _profile_semantics(profile, catalog, request):
    for field in ("subjectId", "fps", "totalFrames"):
        if type(profile.get(field)) is not type(request[field]) or profile[field] != request[field]:
            _error("DIRECTOR_PROFILE_IDENTITY_MISMATCH", "eventDirectorProfileRef." + field, "request/source profile equality", profile.get(field))
    chapters, schedule = profile.get("chapters"), profile.get("sourceSchedule")
    _range_rows(chapters, request["totalFrames"], "eventDirectorProfileRef.chapters")
    _range_rows(schedule, request["totalFrames"], "eventDirectorProfileRef.sourceSchedule")
    if (any(not isinstance(row.get("chapterId"), str) or not _NAME.fullmatch(row["chapterId"]) for row in chapters)
            or len({row.get("chapterId") for row in chapters}) != len(chapters)):
        _error("DIRECTOR_CHAPTER_ID_DUPLICATE", "eventDirectorProfileRef.chapters", "unique chapter IDs")
    prior_date = None
    sources = catalog.get("sources")
    if not isinstance(sources, dict):
        _error("DIRECTOR_SOURCE_CATALOG_INVALID", "sourceCatalogRef.sources", "server-bound source catalog object", sources)
    for i, row in enumerate(chapters):
        if i and chapters[i-1].get("controlEndState") != row.get("controlStartState"):
            _error("DIRECTOR_CHAPTER_STATE_DISCONTINUITY", f"eventDirectorProfileRef.chapters[{i}]", "same adjacent endpoint control state")
    for i, row in enumerate(schedule):
        p = f"eventDirectorProfileRef.sourceSchedule[{i}]"
        if not any(c["startFrame"] <= row["startFrame"] < row["endFrame"] <= c["endFrame"]
                   and c.get("chapterId") == row.get("chapterId") for c in chapters):
            _error("DIRECTOR_SOURCE_CHAPTER_MISMATCH", p, "one containing declared chapter", row)
        truth = row.get("truthKind")
        if truth not in {"observed", "schematic", "illustrative_transition", "unknown"}:
            _error("DIRECTOR_TRUTH_KIND_INVALID", p + ".truthKind", "explicit supported source truth kind", truth)
        if truth == "unknown" and (row.get("stateId") is not None or row.get("sourceIds")):
            _error("DIRECTOR_UNKNOWN_STATE_NOT_NULL", p, "null unknown state without previous-state fallback", row)
        if truth == "unknown" and row.get("sourceDate") is not None:
            _error("DIRECTOR_UNKNOWN_SOURCE_DATE_CLAIM", p + ".sourceDate", "unknown source date is null; event dates belong to the chapter", row.get("sourceDate"))
        ids = row.get("sourceIds")
        if not isinstance(ids, list) or any(not isinstance(x, str) or x not in sources for x in ids):
            _error("DIRECTOR_SOURCE_ID_UNAVAILABLE", p + ".sourceIds", "IDs present in exact source catalog", ids)
        if truth != "unknown" and (not ids or row.get("stateId") is None):
            _error("DIRECTOR_KNOWN_STATE_SOURCE_REQUIRED", p, "stateId and sourceIds for qualified known state", row)
        raw_date = row.get("sourceDate")
        if raw_date is not None:
            try:
                current = date.fromisoformat(raw_date)
            except (TypeError, ValueError):
                _error("DIRECTOR_SOURCE_DATE_INVALID", p + ".sourceDate", "ISO date or explicit unknown null", raw_date)
            if prior_date is not None and current < prior_date:
                _error("DIRECTOR_SOURCE_DATE_REGRESSION", p + ".sourceDate", "nondecreasing actual source dates", raw_date)
            prior_date = current
    return chapters, schedule


def _derivation(bindings, request, documents, plan):
    """Bind an actual compiler's files, not a schema-shaped invented Scene."""
    if bindings is None:
        return None
    fields = {"receiptPath", "receiptSHA256", "scenePath", "frontProfilePath", "compilerPath"}
    if not isinstance(bindings, dict) or set(bindings) != fields:
        _error("DIRECTOR_DERIVATION_BINDING_INVALID", "prompt", "server-owned actual compiler/receipt/Scene paths and receipt SHA")
    raw = _regular_absolute(bindings["receiptPath"])
    if not isinstance(bindings["receiptSHA256"], str) or _sha(raw) != bindings["receiptSHA256"]:
        _error("DIRECTOR_DERIVATION_RECEIPT_SHA_MISMATCH", "prompt", "actual compiler receipt byte SHA")
    receipt = _parse_document(raw, "runtimeBindingManifest")
    if receipt.get("schema") != "WORLD_ENGINE_ASTRA_DERIVATION_RECEIPT_V2":
        _error("DIRECTOR_DERIVATION_RECEIPT_INVALID", "runtimeBindingManifest", "actual versioned canonical compiler receipt")
    comparisons = {"sourcePlanSHA256": request["sourcePlanSha256"],
                   "eventProfileSHA256": request["eventDirectorProfileRef"]["sha256"] if request["eventDirectorProfileRef"] else None,
                   "sourceCatalogSHA256": request["sourceCatalogRef"]["sha256"] if request["sourceCatalogRef"] else None}
    if any(receipt.get(key) != expected for key, expected in comparisons.items()):
        _error("DIRECTOR_DERIVATION_INPUT_MISMATCH", "prompt", "actual compiler receipt matching original Plan/profile/catalog SHAs")
    records = {}
    values = {}
    for name, path_field, hash_field in (("scene", "scenePath", "derivedSceneSHA256"),
            ("frontProfile", "frontProfilePath", "derivedFrontProfileSHA256"),
            ("compiler", "compilerPath", "compilerSHA256")):
        content = _regular_absolute(bindings[path_field])
        digest = _sha(content)
        if digest != receipt.get(hash_field):
            _error("DIRECTOR_DERIVATION_OUTPUT_SHA_MISMATCH", "runtimeBindingManifest", "actual compiler/output bytes matching receipt", name)
        records[name] = {"sha256": digest, "bytes": len(content)}
        if name != "compiler":
            values[name] = _parse_document(content, "runtimeBindingManifest")
    scene = values["scene"]
    if (scene.get("legacyScenePlan") != plan.get("legacyScenePlan")
            or [x.get("renderProfile", {}).get("nativePayload") for x in scene.get("scenes", [])]
            != [x.get("renderProfile", {}).get("nativePayload") for x in plan.get("scenes", [])]
            or scene.get("fps") != request["fps"] or scene.get("totalFrames") != request["totalFrames"]):
        _error("DIRECTOR_DERIVATION_PRESERVED_SOURCE_CHANGED", "runtimeBindingManifest", "unchanged legacy geometry/native payload and source clock")
    if documents["eventDirectorProfileRef"] is not None:
        expected = documents["eventDirectorProfileRef"]["chapters"]
        actual = scene.get("productionV3", {}).get("eventChapters", [])
        if ([{k: row.get(k) for k in ("chapterId", "eventId", "startFrame", "endFrame", "title", "displayLabel")} for row in actual]
                != [{k: row.get(k) for k in ("chapterId", "eventId", "startFrame", "endFrame", "title", "displayLabel")} for row in expected]):
            _error("DIRECTOR_DERIVATION_EVENT_MAPPING_MISMATCH", "runtimeBindingManifest", "exact compiled chapter identity/chronology/display mapping")
    return {"records": records, "receiptSHA256": _sha(raw), "actualDerivedSceneSHA256": records["scene"]["sha256"],
            "sourcePlanSHA256": request["sourcePlanSha256"], "compilerExecutedByThisNormalizer": False,
            "compilerOutputsReadAndVerified": True, "actualDrawVerified": False}


def _capabilities(names, bindings, documents):
    result, blockers = {}, []
    for name in names:
        item = bindings.get(name)
        if not isinstance(item, dict):
            _error("DIRECTOR_CAPABILITY_UNSUPPORTED", "requiredCapabilities", "IDs from server-owned capability registry", name)
        if item.get("available") is not True:
            result[name] = {"available": False, "status": "BLOCKED", "reason": str(item.get("reason", "SOURCE_OR_CONSUMER_UNAVAILABLE"))[:160]}
            blockers.append(_blocked("DIRECTOR_REQUIRED_CAPABILITY_BLOCKED", "requiredCapabilities", name))
            continue
        required = ("sourcePath", "sha256", "symbol", "consumer", "selector")
        if any(not isinstance(item.get(k), str) or not item[k] for k in required) or not _HEX.fullmatch(item["sha256"]):
            _error("DIRECTOR_CAPABILITY_BINDING_INVALID", "requiredCapabilities", "actual source/SHA/symbol/consumer/selector binding", name)
        raw = _regular_absolute(item["sourcePath"])
        if _sha(raw) != item["sha256"] or item["symbol"].encode() not in raw:
            _error("DIRECTOR_CAPABILITY_SOURCE_MISMATCH", "requiredCapabilities", "actual unchanged consumer source bytes and symbol", name)
        result[name] = {k: item[k] for k in required if k != "sourcePath"}
        result[name].update(available=True, status="BOUND_SOURCE_NOT_RENDER_PROOF")
        requirements = deepcopy(item.get("inputRequirements", []))
        # Canonical existing capability families cannot treat an approved empty
        # manifest as an executed unit/audio effect. This is capability meaning,
        # never a country/event-dependent core branch.
        if name.startswith(("UNITS.", "MARKERS.")) or name == "NATIONAL_FLAGS":
            requirements.append({"ref": "markerEvidenceRef", "field": "markers", "minItems": 1})
        audio_requested = name == "SFX" or name.startswith(("SFX.", "AUDIO.", "STUDIO.SFX"))
        if audio_requested:
            requirements.append({"ref": "audioCueManifestRef", "field": "cues", "minItems": 1})
        if not isinstance(requirements, list):
            _error("DIRECTOR_CAPABILITY_BINDING_INVALID", "requiredCapabilities", "server-owned input requirements array", name)
        for requirement in requirements:
            if (not isinstance(requirement, dict) or set(requirement) != {"ref", "field", "minItems"}
                    or requirement["ref"] not in REFS or not isinstance(requirement["field"], str)
                    or type(requirement["minItems"]) is not int or requirement["minItems"] < 1):
                _error("DIRECTOR_CAPABILITY_BINDING_INVALID", "requiredCapabilities", "explicit ref/collection/minItems source requirement", name)
            doc = documents.get(requirement["ref"])
            collection = doc.get(requirement["field"]) if isinstance(doc, dict) else None
            if not isinstance(collection, list) or len(collection) < requirement["minItems"]:
                blockers.append(_blocked("DIRECTOR_REQUIRED_CAPABILITY_INPUT_MISSING", requirement["ref"], name))
                result[name].update(inputReady=False, status="SOURCE_BOUND_BUT_INPUT_BLOCKED")
        if audio_requested:
            audio = documents.get("audioCueManifestRef")
            if not isinstance(audio, dict) or audio.get("enabled") is not True or not audio.get("gain", 0) > 0:
                blockers.append(_blocked("DIRECTOR_REQUIRED_CAPABILITY_INPUT_MISSING", "audioCueManifestRef", name + ": disabled or zero gain"))
                result[name].update(inputReady=False, status="SOURCE_BOUND_BUT_INPUT_BLOCKED")
    return result, blockers


def _audio_settings(document):
    if document is None:
        return {}
    if not {"enabled", "gain", "cues"} <= document.keys():
        _error("DIRECTOR_AUDIO_MANIFEST_INVALID", "audioCueManifestRef", "explicit enabled/gain/cues settings")
    settings = {key: deepcopy(document[key]) for key in ("enabled", "gain", "exportWav", "cues") if key in document}
    if (type(settings["enabled"]) is not bool or type(settings["gain"]) not in (int, float)
            or not 0 <= settings["gain"] <= 1 or not isinstance(settings["cues"], list)
            or len(settings["cues"]) > 10000 or ("exportWav" in settings and type(settings["exportWav"]) is not bool)):
        _error("DIRECTOR_AUDIO_MANIFEST_INVALID", "audioCueManifestRef", "boolean enabled, numeric gain 0..1, explicit cues array", document)
    return settings


def normalize_request(value, *, source_plan_path, source_root, trusted_refs,
                      capability_bindings, component_validators=None, derivation_bindings=None):
    """Resolve trusted bytes and semantic lineage without authorizing a render.

    ``trusted_refs``, capability bindings and optional component validators are
    server-owned arguments, never values accepted from a production prompt.
    Component validators receive (document, request, resolved_documents) and
    return explicit ``{ready: bool, blockers: [...]}``; they cannot erase earlier
    blockers. Detailed camera/control validation remains with its actual owner.
    """
    request = _request(value)
    if not isinstance(trusted_refs, dict) or not isinstance(capability_bindings, dict):
        _error("DIRECTOR_SOURCE_CONTEXT_REQUIRED", "prompt", "server-owned source and capability registry")
    raw = _regular_absolute(source_plan_path)
    if _sha(raw) != request["sourcePlanSha256"]:
        _error("DIRECTOR_SOURCE_PLAN_SHA_MISMATCH", "sourcePlanSha256", "actual unmodified source Plan byte SHA", request["sourcePlanSha256"])
    plan = _parse_document(raw, "sourcePlanSha256")
    if (type(plan.get("fps")) is not int or plan["fps"] != request["fps"]
            or type(plan.get("totalFrames")) is not int or plan["totalFrames"] != request["totalFrames"]):
        _error("DIRECTOR_SOURCE_PLAN_TIME_MISMATCH", "totalFrames", "unchanged source Plan global clock", plan.get("totalFrames"))
    documents, blockers = {}, []
    for field in REFS:
        ref = request[field]
        if ref is None:
            blockers.append(_blocked("DIRECTOR_REFERENCE_UNRESOLVED", field, "Explicit null, no generated default or previous-state replacement"))
            documents[field] = None
            continue
        document = _read_ref(ref, field, source_root, trusted_refs)
        if ("sourcePlanSHA256" in document and document["sourcePlanSHA256"] != request["sourcePlanSha256"]):
            _error("DIRECTOR_COMPONENT_SOURCE_PLAN_MISMATCH", field, "same source Plan byte SHA", document.get("sourcePlanSHA256"))
        documents[field] = document
    profile, catalog = documents[REFS[0]], documents["sourceCatalogRef"]
    _audio_settings(documents["audioCueManifestRef"])
    if profile is not None and catalog is not None:
        chapters, schedule = _profile_semantics(profile, catalog, request)
        unknown = sum(x["endFrame"] - x["startFrame"] for x in schedule if x["truthKind"] == "unknown")
        if unknown:
            blockers.append(_blocked("DIRECTOR_EVENT_DATA_UNKNOWN", "eventDirectorProfileRef.sourceSchedule", f"{unknown} global frames explicitly lack event-specific control/front evidence"))
    else:
        chapters, schedule, unknown = [], [], None
    capabilities, cap_blockers = _capabilities(request["requiredCapabilities"], capability_bindings, documents)
    blockers.extend(cap_blockers)
    component_receipts = {}
    for field, validator in (component_validators or {}).items():
        if field not in REFS or not callable(validator):
            _error("DIRECTOR_COMPONENT_VALIDATOR_INVALID", "prompt", "server-owned callable for a declared Ref role")
        if documents[field] is None:
            continue
        receipt = validator(deepcopy(documents[field]), deepcopy(request), deepcopy(documents))
        if not isinstance(receipt, dict) or type(receipt.get("ready")) is not bool or not isinstance(receipt.get("blockers", []), list):
            _error("DIRECTOR_COMPONENT_RECEIPT_INVALID", field, "explicit ready boolean and blockers array", receipt)
        _bounded_json(receipt)
        component_receipts[field] = deepcopy(receipt)
        if receipt["ready"] is False:
            rows = deepcopy(receipt.get("blockers", [])) or [_blocked("DIRECTOR_COMPONENT_BLOCKED", field, "Actual component validation is not ready")]
            if any(not isinstance(row, dict) or not isinstance(row.get("code"), str) for row in rows):
                _error("DIRECTOR_COMPONENT_RECEIPT_INVALID", field, "bounded coded blocker objects", receipt)
            for row in rows:
                row["blocksReview"] = receipt.get("reviewReady") is not True
            blockers.extend(rows)
    # Active marker/audio inputs also require their actual date/role/license
    # owner; an approved empty manifest is permitted without inventing effects.
    required_owner_validation = {"cameraAdmissionRef", "controlTimelineRef"}
    markers = documents["markerEvidenceRef"]
    audio = documents["audioCueManifestRef"]
    if isinstance(markers, dict) and markers.get("markers"):
        required_owner_validation.add("markerEvidenceRef")
    if isinstance(audio, dict) and audio.get("enabled") is True and audio.get("cues"):
        required_owner_validation.add("audioCueManifestRef")
    # Files cannot declare their own admission simply by existing.
    for field in sorted(required_owner_validation):
        if documents[field] is not None and field not in component_receipts:
            blockers.append(_blocked("DIRECTOR_COMPONENT_CONSUMER_NOT_VALIDATED", field, "Actual camera/control owner validator is required"))
    compiler_inputs = {"schema": "WORLD_ENGINE_EVENT_DIRECTOR_COMPILER_INPUT_V1", "sourcePlanSHA256": request["sourcePlanSha256"],
        "subjectId": request["subjectId"], "fps": request["fps"], "totalFrames": request["totalFrames"],
        "frameConvention": "GLOBAL_HALF_OPEN", "chapters": deepcopy(chapters), "sourceSchedule": deepcopy(schedule),
        "sourceReferences": {key: deepcopy(request[key]) for key in REFS},
        "unknownSourceFrames": unknown, "noUnknownComplement": True, "noPreviousStateFallback": True}
    actual_derivation = _derivation(derivation_bindings, request, documents, plan)
    if actual_derivation is None:
        blockers.append(_blocked("DIRECTOR_ACTUAL_RUNTIME_DERIVATION_UNBOUND", "runtimeBindingManifest", "Actual canonical compiler Scene/receipt/source bytes must be bound before selecting a renderer"))
    identity = {"schema": "WORLD_ENGINE_EVENT_DIRECTOR_RUNTIME_BINDING_V1", "requestSHA256": canonical_sha(request),
        "sourcePlanSHA256": request["sourcePlanSha256"], "compilerInputSHA256": canonical_sha(compiler_inputs),
        "actualDerivation": actual_derivation,
        "refs": {key: deepcopy(request[key]) for key in REFS}, "capabilities": capabilities,
        "componentReceipts": component_receipts, "selector": "EVENT_DIRECTOR_V1_EXPLICIT_CALLBACK",
        "actualDrawVerified": False, "deployedStudioSupported": False, "imagePackageVerified": False}
    review_blockers = [x for x in blockers if x.get("blocksReview") is not False and x.get("code") not in {
        "DIRECTOR_EVENT_DATA_UNKNOWN", "DIRECTOR_REQUIRED_CAPABILITY_BLOCKED", "DIRECTOR_REQUIRED_CAPABILITY_INPUT_MISSING"}]
    return {"schema": "WORLD_ENGINE_EVENT_DIRECTOR_NORMALIZED_V1", "normalizedRequest": request,
        "sourcePlan": plan, "resolvedDocuments": documents, "compilerInputs": compiler_inputs,
        "runtimeBindingManifest": identity, "blockers": blockers,
        "productionReady": not blockers, "ready": not blockers,
        "reviewReady": request["purpose"] == "QUALIFIED_SOURCE_REVIEW" and not review_blockers,
        "requiredCapabilitiesRemoved": False, "renderAllowed": False,
        "nvidiaHardwareVerified": False, "visualQualityApproved": False}


def _director_prompt(value):
    if not isinstance(value, dict) or not isinstance(value.get("prompt"), str):
        return None
    parsed = _parse_json(value["prompt"])
    return parsed if isinstance(parsed, dict) and parsed.get("schema") == SCHEMA else None


def normalize_submission(value, *, parent_normalize, image_digest=None, backend=None, **context):
    """Select the new request explicitly, otherwise delegate V1/V2 untouched."""
    try:
        request = _director_prompt(value)
    except StudioContractError:
        # Existing parsers retain ownership of every non-director failure.
        return parent_normalize(value, image_digest=image_digest, backend=backend)
    if request is None:
        return parent_normalize(value, image_digest=image_digest, backend=backend)
    if set(value) - {"prompt", "sceneJson", "durationSeconds", "profile", "sfx"}:
        _error("DIRECTOR_ENVELOPE_FIELD_UNSUPPORTED", "prompt", "preserved Studio submission envelope")
    if value.get("sceneJson") is not None:
        _error("DIRECTOR_SCENE_CONFLICT", "sceneJson", "director refs or direct Scene, not both", value["sceneJson"])
    if not {"source_plan_path", "source_root", "trusted_refs", "capability_bindings"} <= context.keys():
        _error("DIRECTOR_SOURCE_CONTEXT_REQUIRED", "prompt", "complete server-owned source context")
    resolved = normalize_request(request, **context)
    audio = resolved["resolvedDocuments"]["audioCueManifestRef"]
    settings = _audio_settings(audio)
    ui = value.get("sfx")
    if "sfx" in value:
        if not isinstance(ui, dict) or any(key not in {"enabled", "gain", "exportWav", "cues"} for key in ui):
            _error("DIRECTOR_SFX_UI_CONFLICT", "sfx", "exact source-bound audio settings", ui)
        for key, item in ui.items():
            same_type = key in settings and (type(item) is type(settings[key]) or
                (key == "gain" and type(item) in (int, float) and type(settings[key]) in (int, float)))
            if not same_type or item != settings[key]:
                _error("DIRECTOR_SFX_UI_CONFLICT", "sfx." + key, "same explicit source-bound value including false/0/[]", item)
    outer = deepcopy(value)
    outer["sceneJson"] = deepcopy(resolved["sourcePlan"])
    if audio is not None:
        outer["sfx"] = settings
    base = parent_normalize(outer, image_digest=image_digest, backend=backend)
    if not isinstance(base, dict) or "eventDirector" in base:
        _error("DIRECTOR_PARENT_RESULT_INVALID", "prompt", "unchanged normalized Studio base result")
    result = deepcopy(base)
    result["promptText"] = value["prompt"]
    result["eventDirector"] = {key: deepcopy(item) for key, item in resolved.items() if key != "sourcePlan"}
    return result


def select_runtime(submission, *, director_selector, parent_selector):
    """Real explicit callback edge; no renderer import from a client Ref."""
    admission = submission.get("eventDirector") if isinstance(submission, dict) else None
    if admission is None:
        return parent_selector(submission)
    if not callable(director_selector):
        raise RuntimeError("DIRECTOR_RUNTIME_NOT_CONNECTED")
    if canonical_sha(admission["compilerInputs"]) != admission["runtimeBindingManifest"]["compilerInputSHA256"]:
        raise RuntimeError("DIRECTOR_COMPILER_INPUT_CHANGED")
    if (admission["normalizedRequest"]["purpose"] != "QUALIFIED_SOURCE_REVIEW"
            or admission.get("reviewReady") is not True):
        raise RuntimeError("DIRECTOR_FREE_REVIEW_PREFLIGHT_BLOCKED")
    return director_selector(deepcopy(submission["videoPlan"]), deepcopy(admission["compilerInputs"]),
                             deepcopy(admission["runtimeBindingManifest"]), deepcopy(admission["resolvedDocuments"]))
