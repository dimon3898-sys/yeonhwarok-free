"""Source-qualified polygon control fields, independent of every protected renderer.

This is a CPU contract, not a new renderer, a historical digitizer or a morph
engine. Area V3 owns polygon validation; system GEOS owns topology operations.
One immutable source state supplies masks and shared boundaries together. No
scalar latitude field, previous-state fallback or opposing-owner complement is
created. A server-pinned receipt manifest is necessary; Scene JSON approval
flags cannot register sources. The historical Incheon gate remains blocked.
"""
from __future__ import annotations

from copy import deepcopy
import ctypes as C
import ctypes.util
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from types import MappingProxyType

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]
AREA = ENGINE / "web/map_infographic_v1/area_core_v3.mjs"
AREA_SHA256 = "10c55061c2a38ab527411fcd58cb6c4248d4a4fc21c0c59ae31271e755500d3f"
INCHEON_FIXTURE_SHA256 = "9d077cf26a67228a7a842f82f913ee99d6bfd6271fa3a6a412715e67214dca85"
SCHEMA = "WORLD_ENGINE_SOURCE_CONTROL_STATE_V1"
RECEIPT_SCHEMA = "WORLD_ENGINE_SERVER_CONTROL_RECEIPTS_V1"
QUALIFICATIONS = {"FULL_CONTROL_OBSERVATION", "SCHEMATIC_CONTROL", "UNKNOWN_EXTENT",
                  "CONTESTED_EXTENT", "DOMAIN_COVERAGE", "SYNTHETIC_TEST"}
_COMPILE_TOKEN = object()


class CompiledControlState(dict):
    """JSON-serializable result whose admission seal is never accepted from JSON."""
    def __init__(self, value, token):
        if token is not _COMPILE_TOKEN:
            raise TypeError("CONTROL_SERVER_COMPILE_REQUIRED")
        super().__init__(value)
        self._seal = sha(canonical(value))

    def source_binding_valid(self):
        return self._seal == sha(canonical(dict(self)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("CONTROL_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("CONTROL_DOCUMENT_CAPACITY")
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("CONTROL_NONFINITE_JSON")))


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or set(value) - set(required) - set(optional):
        raise ValueError("CONTROL_UNKNOWN_OR_MISSING_FIELDS")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and not re.search(r"[\x00-\x1f\x7f]", value)


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("CONTROL_SOURCE_DATE_REQUIRED")
    return date.fromisoformat(value)


def _bounds(value):
    return (isinstance(value, list) and len(value) == 4
            and all(type(n) in (float, int) and math.isfinite(n) for n in value)
            and -180 <= value[0] < value[2] <= 180 and -85 <= value[1] < value[3] <= 85)


def validate_area_geometries(geometries):
    """Invoke, without copying/editing, the protected Area V3 validator."""
    if sha(AREA.read_bytes()) != AREA_SHA256:
        raise ValueError("CONTROL_PROTECTED_AREA_SOURCE_CHANGED")
    bridge = ("import {readFileSync} from 'node:fs';"
              "const {validateAreaGeometry}=await import(process.argv[1]);"
              "try{const input=JSON.parse(readFileSync(0,'utf8'));"
              "process.stdout.write(JSON.stringify(input.map(validateAreaGeometry)));}"
              "catch(e){process.stderr.write(String(e.message));process.exit(2);}")
    result = subprocess.run(["node", "--input-type=module", "-e", bridge, AREA.as_uri()],
                            input=canonical(geometries), capture_output=True, timeout=20)
    if result.returncode:
        code = result.stderr.decode(errors="replace").strip()
        raise ValueError("CONTROL_AREA_VALIDATION_FAILED:" + (code if re.fullmatch(r"[A-Z0-9_]+", code) else "INVALID_GEOMETRY"))
    if parse(result.stdout) != geometries:
        raise ValueError("CONTROL_SOURCE_GEOMETRY_MUTATION")


class SourceRegistry:
    """Server-only manifest loader; do not expose its arguments as request fields.

    expected_sha256 must come from the deployment/source owner, not the Scene.
    Hashing verifies source identity, not historical truth. The pinned reviewed
    manifest must separately state date, faction, license and qualification.
    SYNTHETIC_TEST registries can never authorize a PRODUCTION state.
    """
    def __init__(self, *args, **kwargs):
        raise TypeError("CONTROL_SERVER_PINNED_MANIFEST_REQUIRED")

    @classmethod
    def from_manifest(cls, manifest_path, *, expected_sha256, mode="PRODUCTION"):
        if mode not in ("PRODUCTION", "SYNTHETIC_TEST"):
            raise ValueError("CONTROL_DATA_MODE_REQUIRED")
        path = Path(manifest_path)
        if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha256)):
            raise ValueError("CONTROL_TRUSTED_MANIFEST_PIN_REQUIRED")
        raw = path.read_bytes()
        if sha(raw) != expected_sha256:
            raise ValueError("CONTROL_MANIFEST_HASH_MISMATCH")
        document = parse(raw)
        _keys(document, ("schema", "mode", "receipts"))
        if document["schema"] != RECEIPT_SCHEMA or document["mode"] != mode:
            raise ValueError("CONTROL_RECEIPT_MODE_MISMATCH")
        rows = document["receipts"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
            raise ValueError("CONTROL_RECEIPT_CAPACITY")
        root, records = path.parent.resolve(), {}
        for receipt in rows:
            _keys(receipt, ("id", "sourcePath", "sourceSHA256", "sourceURL", "geometryPath",
                            "geometryFileSHA256", "geometrySHA256", "qualification", "asOfDate",
                            "timeQualifier", "factions", "crs", "license", "licenseStatus"))
            if (not _text(receipt["id"]) or receipt["id"] in records
                    or receipt["qualification"] not in QUALIFICATIONS
                    or receipt["crs"] != "EPSG:4326"
                    or receipt["licenseStatus"] != "REVIEWED_FOR_THIS_GEOMETRY"
                    or not _text(receipt["license"]) or not _text(receipt["sourceURL"])
                    or not isinstance(receipt["factions"], list)
                    or any(not _text(f) for f in receipt["factions"])
                    or len(set(receipt["factions"])) != len(receipt["factions"])):
                raise ValueError("CONTROL_INVALID_SOURCE_RECEIPT")
            if mode == "SYNTHETIC_TEST" and receipt["qualification"] != "SYNTHETIC_TEST":
                raise ValueError("CONTROL_SYNTHETIC_RECEIPT_REQUIRED")
            if mode == "PRODUCTION" and receipt["qualification"] == "SYNTHETIC_TEST":
                raise ValueError("CONTROL_SYNTHETIC_NOT_PRODUCTION")
            if receipt["qualification"] not in ("DOMAIN_COVERAGE", "SYNTHETIC_TEST"):
                _date(receipt["asOfDate"])
            if receipt["timeQualifier"] not in ("DATE_ONLY", "MORNING", "EVENING", "NIGHT", "NOT_TEMPORAL"):
                raise ValueError("CONTROL_TIME_QUALIFIER_REQUIRED")
            blobs = {}
            for role, field, digest in (("source", "sourcePath", "sourceSHA256"),
                                        ("geometry", "geometryPath", "geometryFileSHA256")):
                relative = receipt[field]
                if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                    raise ValueError("CONTROL_SOURCE_PATH_ESCAPE")
                candidate = root / relative
                if any(item.is_symlink() for item in (candidate, *candidate.parents) if item != root.parent):
                    raise ValueError("CONTROL_SOURCE_SYMLINK_REJECTED")
                if not candidate.resolve().is_relative_to(root) or candidate.stat().st_size > 64 * 1024 * 1024:
                    raise ValueError("CONTROL_SOURCE_PATH_OR_CAPACITY")
                blobs[role] = candidate.read_bytes()
                if sha(blobs[role]) != receipt[digest]:
                    raise ValueError("CONTROL_SOURCE_HASH_MISMATCH")
            geometry = parse(blobs["geometry"])
            if sha(canonical(geometry)) != receipt["geometrySHA256"]:
                raise ValueError("CONTROL_GEOMETRY_HASH_MISMATCH")
            records[receipt["id"]] = {"receipt": deepcopy(receipt), "geometry": geometry,
                                        "receiptSHA256": sha(canonical(receipt))}
        validate_area_geometries([row["geometry"] for row in records.values()])
        obj = object.__new__(cls)
        obj._records = MappingProxyType(records)
        obj.mode, obj.manifest_sha256 = mode, expected_sha256
        return obj

    def resolve(self, reference, geometry, *, role, faction, as_of, qualifier):
        if reference not in self._records:
            raise ValueError("CONTROL_SERVER_RECEIPT_NOT_FOUND")
        record = self._records[reference]
        receipt = record["receipt"]
        if sha(canonical(geometry)) != receipt["geometrySHA256"] or geometry != record["geometry"]:
            raise ValueError("CONTROL_SCENE_GEOMETRY_NOT_SOURCE_BOUND")
        expected = {"owner": {"FULL_CONTROL_OBSERVATION", "SCHEMATIC_CONTROL"},
                    "unknown": {"UNKNOWN_EXTENT"}, "contested": {"CONTESTED_EXTENT"},
                    "domain": {"DOMAIN_COVERAGE"}}[role]
        if self.mode != "SYNTHETIC_TEST":
            if receipt["qualification"] not in expected:
                raise ValueError("CONTROL_SOURCE_ROLE_NOT_QUALIFIED")
            if role != "domain" and (receipt["asOfDate"] != as_of or receipt["timeQualifier"] != qualifier):
                raise ValueError("CONTROL_SOURCE_DATE_MISMATCH")
        if role == "owner" and faction not in receipt["factions"]:
            raise ValueError("CONTROL_SOURCE_FACTION_MISMATCH")
        return {"sourceRef": reference, "receiptSHA256": record["receiptSHA256"],
                "sourceSHA256": receipt["sourceSHA256"], "geometrySHA256": receipt["geometrySHA256"],
                "qualification": receipt["qualification"]}


class _Geos:
    """Small resource-owning binding to installed GEOS, not geometry algorithms."""
    def __enter__(self):
        library = ctypes.util.find_library("geos_c")
        if not library:
            raise RuntimeError("CONTROL_GEOS_CPU_DEPENDENCY_UNAVAILABLE")
        self.lib = C.CDLL(library)
        def bind(name, result, *args):
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = result, list(args)
            return fn
        ptr = C.c_void_p
        self.init = bind("GEOS_init_r", ptr)
        self.finish = bind("GEOS_finish_r", None, ptr)
        self.destroy = bind("GEOSGeom_destroy_r", None, ptr, ptr)
        self.reader_create = bind("GEOSGeoJSONReader_create_r", ptr, ptr)
        self.reader_destroy = bind("GEOSGeoJSONReader_destroy_r", None, ptr, ptr)
        self.read = bind("GEOSGeoJSONReader_readGeometry_r", ptr, ptr, ptr, C.c_char_p)
        self.writer_create = bind("GEOSGeoJSONWriter_create_r", ptr, ptr)
        self.writer_destroy = bind("GEOSGeoJSONWriter_destroy_r", None, ptr, ptr)
        self.write = bind("GEOSGeoJSONWriter_writeGeometry_r", ptr, ptr, ptr, ptr, C.c_int)
        self.free = bind("GEOSFree_r", None, ptr, ptr)
        self.area_fn = bind("GEOSArea_r", C.c_int, ptr, ptr, C.POINTER(C.c_double))
        self.intersection_fn = bind("GEOSIntersection_r", ptr, ptr, ptr, ptr)
        self.union_fn = bind("GEOSUnion_r", ptr, ptr, ptr, ptr)
        self.difference_fn = bind("GEOSDifference_r", ptr, ptr, ptr, ptr)
        self.boundary_fn = bind("GEOSBoundary_r", ptr, ptr, ptr)
        self.version = bind("GEOSversion", C.c_char_p)().decode()
        self.ctx, self.items = self.init(), []
        self.reader = self.reader_create(self.ctx)
        self.writer = self.writer_create(self.ctx)
        if not self.ctx or not self.reader or not self.writer:
            raise RuntimeError("CONTROL_GEOS_INITIALIZATION_FAILED")
        return self

    def own(self, pointer):
        if not pointer:
            raise ValueError("CONTROL_GEOS_OPERATION_FAILED")
        self.items.append(pointer)
        return pointer

    def geometry(self, value):
        return self.own(self.read(self.ctx, self.reader, canonical(value)))

    def operation(self, name, *pointers):
        return self.own(getattr(self, name + "_fn")(self.ctx, *pointers))

    def area(self, pointer):
        result = C.c_double()
        if not self.area_fn(self.ctx, pointer, C.byref(result)):
            raise ValueError("CONTROL_GEOS_AREA_FAILED")
        return result.value

    def json(self, pointer):
        raw = self.write(self.ctx, self.writer, pointer, -1)
        if not raw:
            raise ValueError("CONTROL_GEOS_SERIALIZATION_FAILED")
        try:
            return parse(C.string_at(raw))
        finally:
            self.free(self.ctx, raw)

    def __exit__(self, *ignored):
        for pointer in reversed(self.items):
            self.destroy(self.ctx, pointer)
        self.reader_destroy(self.ctx, self.reader)
        self.writer_destroy(self.ctx, self.writer)
        self.finish(self.ctx)


def _line_parts(geometry):
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]] if len(geometry["coordinates"]) >= 2 else []
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    if geometry["type"] == "GeometryCollection":
        return [part for geometry in geometry["geometries"] for part in _line_parts(geometry)]
    return []  # Point-only touching is not a shared frontier.


def compile_control_state(document, registry):
    """Return a neutral exact-polygon mask bundle and SAME-state shared front.

    No geographic resampling is done. GEOS differences identify unassigned
    source-domain space as *unobserved*, never as the other faction. This is
    not evidence that an official source measured an unknown-area boundary.
    Continuous interpolation is intentionally unsupported without independent
    topology/time evidence. Production permission belongs to a later gate.
    """
    state = parse(document) if isinstance(document, bytes) else deepcopy(document)
    _keys(state, ("schema", "mode", "stateId", "frame", "asOfDate", "timeQualifier", "bbox", "crs",
                  "classification", "factions", "domain", "ownerMasks", "unknownMasks", "contestedMasks"))
    if state["schema"] != SCHEMA or not _text(state["stateId"]) or state["mode"] != registry.mode:
        raise ValueError("CONTROL_STATE_ID_OR_MODE_REQUIRED")
    _date(state["asOfDate"])
    if (type(state["frame"]) is not int or state["frame"] < 0 or not _bounds(state["bbox"])
            or state["crs"] != "EPSG:4326"):
        raise ValueError("CONTROL_FRAME_OR_UNWRAPPED_GEOGRAPHIC_DOMAIN_REQUIRED")
    if state["timeQualifier"] not in ("DATE_ONLY", "MORNING", "EVENING", "NIGHT"):
        raise ValueError("CONTROL_TIME_QUALIFIER_REQUIRED")
    if state["classification"] not in ("observed", "schematic", "illustrative_transition", "unknown"):
        raise ValueError("CONTROL_CLASSIFICATION_REQUIRED")
    if state["classification"] == "illustrative_transition":
        raise ValueError("CONTROL_SOURCE_SUPPORTED_TRANSITION_ADAPTER_REQUIRED")
    factions = state["factions"]
    if (not isinstance(factions, list) or not 2 <= len(factions) <= 32
            or any(not _text(f) for f in factions) or len(set(factions)) != len(factions)):
        raise ValueError("CONTROL_UNIQUE_FACTIONS_REQUIRED")
    _keys(state["domain"], ("geometry", "sourceRef"))
    rows, receipts = [], []
    for field, role in (("ownerMasks", "owner"), ("unknownMasks", "unknown"), ("contestedMasks", "contested")):
        if not isinstance(state[field], list):
            raise ValueError("CONTROL_MASK_ARRAY_REQUIRED")
        for row in state[field]:
            _keys(row, ("geometry", "sourceRef", "factionId") if role == "owner" else ("geometry", "sourceRef"))
            faction = row.get("factionId")
            if role == "owner" and faction not in factions:
                raise ValueError("CONTROL_UNDECLARED_FACTION")
            receipts.append(registry.resolve(row["sourceRef"], row["geometry"], role=role, faction=faction,
                                            as_of=state["asOfDate"], qualifier=state["timeQualifier"]))
            rows.append((role, row))
    if not 1 <= len(rows) <= 64:
        raise ValueError("CONTROL_EMPTY_OR_EXCESSIVE_STATE")
    if state["classification"] == "unknown" and state["ownerMasks"]:
        raise ValueError("CONTROL_UNKNOWN_CLASSIFICATION_HAS_OWNERS")
    if state["classification"] == "observed" and any(r["qualification"] == "SCHEMATIC_CONTROL" for r in receipts):
        raise ValueError("CONTROL_SCHEMATIC_NOT_OBSERVED")
    receipts.append(registry.resolve(state["domain"]["sourceRef"], state["domain"]["geometry"], role="domain",
                                    faction=None, as_of=state["asOfDate"], qualifier=state["timeQualifier"]))
    validate_area_geometries([state["domain"]["geometry"], *[row["geometry"] for _, row in rows]])
    identity = sha(canonical({"state": state, "manifest": registry.manifest_sha256, "receipts": receipts}))
    with _Geos() as geos:
        domain = geos.geometry(state["domain"]["geometry"])
        west, south, east, north = state["bbox"]
        roi = geos.geometry({"type": "Polygon", "coordinates": [[[west, south], [east, south],
                            [east, north], [west, north], [west, south]]]})
        if geos.area(geos.operation("difference", domain, roi)) > 0:
            raise ValueError("CONTROL_DOMAIN_OUTSIDE_DECLARED_BBOX")
        geometries, union, classified = [], None, None
        for role, row in rows:
            current = geos.geometry(row["geometry"])
            if geos.area(current) <= 0:
                raise ValueError("CONTROL_EMPTY_MASK_GEOMETRY")
            if geos.area(geos.operation("difference", current, domain)) > 0:
                raise ValueError("CONTROL_MASK_OUTSIDE_SOURCE_DOMAIN")
            for previous, _, _ in geometries:
                if geos.area(geos.operation("intersection", previous, current)) > 0:
                    raise ValueError("CONTROL_OVERLAPPING_MASK_INTERIORS")
            union = current if union is None else geos.operation("union", union, current)
            if role != "unknown":
                classified = current if classified is None else geos.operation("union", classified, current)
            geometries.append((current, role, row))
        unassigned = geos.operation("difference", domain, union)
        unknown = domain if classified is None else geos.operation("difference", domain, classified)
        shared_parts, pairs = [], []
        for index, (first, role, row) in enumerate(geometries):
            if role != "owner":
                continue
            for second, other_role, other in geometries[index + 1:]:
                if other_role != "owner" or row["factionId"] == other["factionId"]:
                    continue
                overlap = geos.operation("intersection", geos.operation("boundary", first), geos.operation("boundary", second))
                clipped = geos.operation("intersection", overlap, domain)
                parts = _line_parts(geos.json(clipped))
                shared_parts.extend(parts)
                if parts:
                    pairs.append({"factions": [row["factionId"], other["factionId"]], "parts": len(parts)})
        contested = None
        for geometry, role, _ in geometries:
            if role == "contested":
                contested = geometry if contested is None else geos.operation("union", contested, geometry)
        result = {"schema": "WORLD_ENGINE_SOURCE_CONTROL_FRAME_V1", "fieldId": identity,
            "stateId": state["stateId"], "frame": state["frame"], "asOfDate": state["asOfDate"],
            "timeQualifier": state["timeQualifier"], "classification": state["classification"],
            "crs": state["crs"], "bbox": state["bbox"], "mode": state["mode"],
            "ownerMasks": [{**deepcopy(row), "fieldId": identity, "frame": state["frame"]} for row in state["ownerMasks"]],
            "unknownMask": {"geometry": geos.json(unknown), "fieldId": identity, "frame": state["frame"],
                            "meaning": "EXPLICIT_UNKNOWN_PLUS_UNOBSERVED_SOURCE_DOMAIN_NOT_OPPONENT"},
            "contestedMask": {"geometry": geos.json(contested) if contested else None,
                              "fieldId": identity, "frame": state["frame"]},
            "sharedFront": {"geometry": {"type": "MultiLineString", "coordinates": shared_parts},
                            "fieldId": identity, "frame": state["frame"], "pairs": pairs,
                            "derivedFrom": "INTERSECTION_OF_THIS_STATE_OWNER_BOUNDARIES_CLIPPED_TO_THIS_DOMAIN"},
            "sourceReceipts": receipts, "serverManifestSHA256": registry.manifest_sha256,
            "unassignedAreaDegreesSquared": geos.area(unassigned),
            "completeExplicitDomainPartition": geos.area(unassigned) == 0,
            "sourceGeometryUnchanged": True, "continuousMorphSupported": False,
            "standaloneFrontInputAllowed": False, "unknownOwnerComplementUsed": False,
            "previousStateFallbackUsed": False, "geosVersion": geos.version,
            "areaValidatorSHA256": AREA_SHA256, "gpuVerified": False, "renderAllowed": False}
    # Caller receives independent data; mutations do not modify source registry.
    return CompiledControlState(result, _COMPILE_TOKEN)


def preflight_control_transition(start, end, *, expected_factions, expected_dates,
                                 camera_admission, event_roi, require_movement=True,
                                 require_observed=True, expected_state_ids=None,
                                 expected_time_qualifiers=None, require_shared_front=True):
    """No boolean from this report grants GPU permission or replaces G1."""
    errors = []
    if not start or not end:
        errors.append("CONTROL_START_AND_END_REQUIRED")
    if not _bounds(event_roi):
        errors.append("CONTROL_EVENT_ROI_UNSUPPORTED")
    if (not isinstance(camera_admission, dict) or camera_admission.get("ready") is not True
            or camera_admission.get("purpose") != "SOURCE_QUALIFIED_EVENT_CAMERA"):
        errors.append("CONTROL_CAMERA_UNSUPPORTED_ZOOM")
    if start and end:
        trusted = all(isinstance(s, CompiledControlState) and s.source_binding_valid() for s in (start, end))
        if not trusted:
            errors.append("CONTROL_UNTRUSTED_OR_MODIFIED_COMPILED_STATE")
        if not isinstance(expected_factions, list) or len(expected_factions) < 2 or len(set(expected_factions)) != len(expected_factions):
            errors.append("CONTROL_EXPECTED_FACTIONS_REQUIRED")
        if not isinstance(expected_dates, list) or len(expected_dates) != 2:
            errors.append("CONTROL_EXPECTED_ENDPOINT_DATES_REQUIRED")
        else:
            try:
                if (_date(start["asOfDate"]) > _date(end["asOfDate"])
                        or [start["asOfDate"], end["asOfDate"]] != expected_dates):
                    errors.append("CONTROL_ENDPOINT_DATE_MISMATCH_OR_REVERSED")
            except (ValueError, KeyError):
                errors.append("CONTROL_ENDPOINT_DATE_MISMATCH_OR_REVERSED")
        if (not isinstance(expected_time_qualifiers, list) or len(expected_time_qualifiers) != 2
                or any(q not in ("DATE_ONLY", "MORNING", "EVENING", "NIGHT") for q in expected_time_qualifiers)):
            errors.append("CONTROL_EXPECTED_ENDPOINT_TIME_QUALIFIERS_REQUIRED")
        elif [start.get("timeQualifier"), end.get("timeQualifier")] != expected_time_qualifiers:
            errors.append("CONTROL_ENDPOINT_TIME_QUALIFIER_MISMATCH")
        if type(start.get("frame")) is not int or type(end.get("frame")) is not int or start["frame"] >= end["frame"]:
            errors.append("CONTROL_ENDPOINT_FRAME_ORDER")
        for state in (start, end):
            if state.get("schema") != "WORLD_ENGINE_SOURCE_CONTROL_FRAME_V1":
                errors.append("CONTROL_COMPILED_SERVER_STATE_REQUIRED")
            if state.get("mode") != "PRODUCTION" and require_observed:
                errors.append("CONTROL_SYNTHETIC_NOT_PRODUCTION")
            if require_observed and state.get("classification") != "observed":
                errors.append("CONTROL_OBSERVED_ENDPOINT_REQUIRED")
            owners = {row.get("factionId") for row in state.get("ownerMasks", [])}
            if owners != set(expected_factions or []):
                errors.append("CONTROL_ENDPOINT_FACTIONS_MISSING_OR_WRONG")
            if state.get("completeExplicitDomainPartition") is not True:
                errors.append("CONTROL_ENDPOINT_UNASSIGNED_DOMAIN")
            if _bounds(event_roi) and (state.get("bbox") != event_roi):
                errors.append("CONTROL_EVENT_ROI_MISMATCH_NO_GEOGRAPHIC_FALLBACK")
            field_id = state.get("fieldId")
            masks = [*state.get("ownerMasks", []), state.get("unknownMask", {}),
                     state.get("contestedMask", {}), state.get("sharedFront", {})]
            if not field_id or any(m.get("fieldId") != field_id or m.get("frame") != state.get("frame") for m in masks):
                errors.append("CONTROL_MASK_FRONT_SAME_FRAME_ID_REQUIRED")
            if require_shared_front and not state.get("sharedFront", {}).get("geometry", {}).get("coordinates"):
                errors.append("CONTROL_SHARED_BILATERAL_FRONT_REQUIRED")
        if expected_state_ids is not None and [start.get("stateId"), end.get("stateId")] != expected_state_ids:
            errors.append("CONTROL_SOURCE_ENDPOINT_ID_MISMATCH_NO_FALLBACK")
        # Frame/state labels, row order and ring orientation do not prove motion.
        # GEOS compares each faction's actual occupied area topologically.
        if require_movement and trusted:
            changed = False
            with _Geos() as geos:
                def owners(state):
                    output = {}
                    for row in state["ownerMasks"]:
                        geometry = geos.geometry(row["geometry"])
                        key = row["factionId"]
                        output[key] = geometry if key not in output else geos.operation("union", output[key], geometry)
                    return output
                first, second = owners(start), owners(end)
                if first.keys() != second.keys():
                    changed = True
                else:
                    for faction in first:
                        if (geos.area(geos.operation("difference", first[faction], second[faction])) > 0
                                or geos.area(geos.operation("difference", second[faction], first[faction])) > 0):
                            changed = True
                            break
            if not changed:
                errors.append("CONTROL_SAME_MASKS_NOT_MOVEMENT")
    errors = list(dict.fromkeys(errors))
    return {"ready": not errors, "status": "G2_CPU_CONTRACT_READY" if not errors else "G2_BLOCKED",
            "blockers": errors, "gpuVerified": False, "visualQualityApproved": False,
            "renderAllowed": False, "continuousMorphAllowed": False,
            "transitionMeaning": "SOURCE_ENDPOINTS_ONLY_NOT_VALIDATED_CONTINUOUS_MORPH"}


def validate_g2_history(document=None, request=None, resolved_documents=None):
    """Server-owned fail-closed Incheon admission callback for the Studio adapter.

    The receipt fixture is a record of actual missing inputs, not a JSON switch
    that users can flip to approve historical rendering. No client ready flag
    or replacements for the frozen source catalog are accepted.
    """
    raw = (HERE / "fixtures/INCHEON_SOURCE_GATE.json").read_bytes()
    if sha(raw) != INCHEON_FIXTURE_SHA256:
        raise ValueError("G2_SERVER_SOURCE_RECEIPT_CHANGED")
    expected = parse(raw)
    if document is not None and document != expected:
        raise ValueError("G2_CLIENT_SOURCE_RECEIPT_NOT_TRUSTED")
    if (request is not None and request.get("sourcePlanSha256") is not None
            and request["sourcePlanSha256"] != expected["sourcePlanSHA256"]):
        raise ValueError("G2_HISTORY_SOURCE_PLAN_MISMATCH")
    dependency_hashes = {}
    for filename, field in (("HISTORY_EVENT_PROFILE_V2.json", "historyProfileSHA256"),
                            ("HISTORY_SOURCE_CATALOG.json", "historyCatalogSHA256")):
        preserved = HERE.parent / "astra-event-director-v2/fixtures" / filename
        digest = sha(preserved.read_bytes())
        if digest != expected[field]:
            raise ValueError("G2_PRESERVED_HISTORY_SOURCE_CHANGED")
        dependency_hashes[filename] = digest
    result = preflight_control_transition(None, None,
        expected_factions=expected["expectedFactions"], expected_dates=expected["expectedEndpointDates"],
        camera_admission={"ready": False}, event_roi=expected["eventROI"], expected_state_ids=None,
        expected_time_qualifiers=expected["expectedEndpointTimeQualifiers"])
    result["blockers"] = list(dict.fromkeys([*result["blockers"], *expected["blockers"]]))
    result.update({"sourceFixtureSHA256": sha(raw), "sourceRecords": expected["sourceCatalog"],
                   "fullControlStatesCreated": 0, "historicalCoordinatesInvented": 0,
                   "sourceHashIsNotOwnershipEvidence": True,
                   "preservedHistoryDependencies": dependency_hashes,
                   "reviewReady": False, "firstBlockedStage": "G2_HISTORY_CONTROL_ENDPOINTS"})
    return result


if __name__ == "__main__":
    print(json.dumps(validate_g2_history(), indent=2, ensure_ascii=False))
