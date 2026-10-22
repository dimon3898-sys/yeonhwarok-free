"""CPU contract tests. Every generated polygon/source below is SYNTHETIC_TEST.

No generated geometry is an historical position, owner mask or approval for
the Incheon scene. The sole historical test expects the real source gate BLOCKED.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("integration_control_provider", HERE / "control_provider.py")
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


def rectangle(west, south, east, north):
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north],
                                                 [west, north], [west, south]]]}


def ordinary_state():
    return {"schema": provider.SCHEMA, "mode": "SYNTHETIC_TEST", "stateId": "SYNTHETIC_START",
            "frame": 0, "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY",
            "bbox": [0, 0, 4, 4], "crs": "EPSG:4326", "classification": "observed",
            "factions": ["TEST_A", "TEST_B"],
            "domain": {"geometry": rectangle(0, 0, 4, 4), "sourceRef": "DOMAIN"},
            "ownerMasks": [{"factionId": "TEST_A", "geometry": rectangle(0, 0, 2, 4), "sourceRef": "A"},
                           {"factionId": "TEST_B", "geometry": rectangle(2, 0, 4, 4), "sourceRef": "B"}],
            "unknownMasks": [], "contestedMasks": []}


class SyntheticServerFixture:
    """Test-only server store, with the manifest pin passed outside Scene JSON."""
    def __init__(self, state, *, mode="SYNTHETIC_TEST", qualification_override=None):
        self.temp = tempfile.TemporaryDirectory(prefix="control-provider-fixture-")
        self.root = Path(self.temp.name)
        source = b"SYNTHETIC UNIT TEST ONLY; NOT HISTORICAL DATA OR PRODUCTION ADMISSION\n"
        (self.root / "source.txt").write_bytes(source)
        self.manifest = {"schema": provider.RECEIPT_SCHEMA, "mode": mode, "receipts": []}
        records = [(state["domain"], "DOMAIN_COVERAGE"),
                   *[(row, "FULL_CONTROL_OBSERVATION") for row in state["ownerMasks"]],
                   *[(row, "UNKNOWN_EXTENT") for row in state["unknownMasks"]],
                   *[(row, "CONTESTED_EXTENT") for row in state["contestedMasks"]]]
        for row, qualification in records:
            name = row["sourceRef"] + ".json"
            raw = provider.canonical(row["geometry"])
            (self.root / name).write_bytes(raw)
            qualification = qualification_override or ("SYNTHETIC_TEST" if mode == "SYNTHETIC_TEST" else qualification)
            self.manifest["receipts"].append({"id": row["sourceRef"], "sourcePath": "source.txt",
                "sourceSHA256": provider.sha(source), "sourceURL": "fixture://synthetic-only/no-historical-claims",
                "geometryPath": name, "geometryFileSHA256": provider.sha(raw), "geometrySHA256": provider.sha(raw),
                "qualification": qualification, "asOfDate": state["asOfDate"],
                "timeQualifier": state["timeQualifier"], "factions": [row["factionId"]] if "factionId" in row else [],
                "crs": "EPSG:4326", "license": "Test author generated synthetic fixture only",
                "licenseStatus": "REVIEWED_FOR_THIS_GEOMETRY"})
        self.path = self.root / "manifest.json"
        self.persist()

    def persist(self):
        raw = provider.canonical(self.manifest)
        self.path.write_bytes(raw)
        self.pin = provider.sha(raw)

    def registry(self):
        return provider.SourceRegistry.from_manifest(self.path, expected_sha256=self.pin,
                                                     mode=self.manifest["mode"])

    def close(self):
        self.temp.cleanup()


class ControlProviderTests(unittest.TestCase):
    def compile(self, state=None, **kwargs):
        state = ordinary_state() if state is None else state
        store = SyntheticServerFixture(state, **kwargs)
        self.addCleanup(store.close)
        return provider.compile_control_state(state, store.registry())

    def preflight(self, first, second, **changes):
        args = {"expected_factions": ["TEST_A", "TEST_B"],
                "expected_dates": ["2000-01-01", "2000-01-02"],
                "expected_time_qualifiers": ["DATE_ONLY", "DATE_ONLY"],
                "camera_admission": {"ready": True, "purpose": "SOURCE_QUALIFIED_EVENT_CAMERA"},
                "event_roi": [0, 0, 4, 4], "require_observed": False}
        args.update(changes)
        return provider.preflight_control_transition(first, second, **args)

    def endpoint_pair(self):
        first = self.compile()
        second = ordinary_state()
        second.update(stateId="SYNTHETIC_END", frame=29, asOfDate="2000-01-02")
        second["ownerMasks"][0]["geometry"] = rectangle(0, 0, 3, 4)
        second["ownerMasks"][1]["geometry"] = rectangle(3, 0, 4, 4)
        return first, self.compile(second)

    def test_one_state_owns_masks_unknown_contested_and_front(self):
        result = self.compile()
        self.assertTrue(result["completeExplicitDomainPartition"])
        self.assertFalse(result["unknownOwnerComplementUsed"])
        self.assertEqual(result["sharedFront"]["geometry"]["coordinates"], [[[2., 0.], [2., 4.]]])
        for part in [*result["ownerMasks"], result["unknownMask"], result["contestedMask"], result["sharedFront"]]:
            self.assertEqual((part["fieldId"], part["frame"]), (result["fieldId"], result["frame"]))

    def test_source_geometry_order_and_precision_not_changed(self):
        state = ordinary_state()
        state["ownerMasks"][0]["geometry"] = rectangle(0, 0, 1.12345678912345, 4)
        state["ownerMasks"][1]["geometry"] = rectangle(1.12345678912345, 0, 4, 4)
        result = self.compile(state)
        self.assertEqual(state["ownerMasks"][0]["geometry"], result["ownerMasks"][0]["geometry"])

    def test_nonmonotone_polygon_front_is_not_scalar_latitude(self):
        state = ordinary_state()
        boundary = [[2, 0], [1, 1], [3, 2], [1, 3], [2, 4]]
        state["ownerMasks"][0]["geometry"] = {"type": "Polygon", "coordinates": [[[0, 0], *boundary, [0, 4], [0, 0]]]}
        state["ownerMasks"][1]["geometry"] = {"type": "Polygon", "coordinates": [[*boundary, [4, 4], [4, 0], boundary[0]]]}
        result = self.compile(state)
        self.assertEqual(len(result["sharedFront"]["geometry"]["coordinates"]), 4)
        self.assertTrue(result["completeExplicitDomainPartition"])

    def test_multipolygon_islands_and_source_hole_supported(self):
        state = ordinary_state()
        state["bbox"] = [0, 0, 6, 6]
        state["domain"]["geometry"] = rectangle(0, 0, 6, 6)
        exterior = rectangle(0, 0, 6, 6)["coordinates"][0]
        hole1 = rectangle(1, 1, 2, 2)["coordinates"][0]
        hole2 = rectangle(4, 4, 5, 5)["coordinates"][0]
        state["ownerMasks"][0]["geometry"] = {"type": "Polygon", "coordinates": [exterior, hole1, hole2]}
        state["ownerMasks"][1]["geometry"] = {"type": "MultiPolygon", "coordinates": [[hole1], [hole2]]}
        result = self.compile(state)
        self.assertEqual(result["ownerMasks"][1]["geometry"]["type"], "MultiPolygon")
        self.assertTrue(result["completeExplicitDomainPartition"])
        self.assertEqual(sum(len(part) - 1 for part in result["sharedFront"]["geometry"]["coordinates"]), 8)

    def test_unassigned_is_unknown_not_opponent_complement(self):
        state = ordinary_state()
        state["ownerMasks"] = state["ownerMasks"][:1]
        result = self.compile(state)
        self.assertFalse(result["completeExplicitDomainPartition"])
        self.assertEqual(result["unassignedAreaDegreesSquared"], 8)
        self.assertEqual(len(result["ownerMasks"]), 1)
        self.assertEqual(result["sharedFront"]["geometry"]["coordinates"], [])

    def test_unknown_and_contested_masks_are_explicit_and_do_not_glow(self):
        state = ordinary_state()
        state["ownerMasks"][0]["geometry"] = rectangle(0, 0, 1, 4)
        state["ownerMasks"][1]["geometry"] = rectangle(3, 0, 4, 4)
        state["unknownMasks"] = [{"sourceRef": "UNKNOWN", "geometry": rectangle(1, 0, 2, 4)}]
        state["contestedMasks"] = [{"sourceRef": "CONTESTED", "geometry": rectangle(2, 0, 3, 4)}]
        result = self.compile(state)
        self.assertTrue(result["completeExplicitDomainPartition"])
        self.assertIsNotNone(result["contestedMask"]["geometry"])
        self.assertEqual(result["sharedFront"]["geometry"]["coordinates"], [])

    def test_positive_area_overlap_rejected_even_below_screen_pixel(self):
        state = ordinary_state()
        state["ownerMasks"][1]["geometry"] = rectangle(1.999999999, 0, 4, 4)
        with self.assertRaisesRegex(ValueError, "OVERLAPPING_MASK_INTERIORS"):
            self.compile(state)

    def test_empty_owner_geometry_rejected(self):
        state = ordinary_state()
        state["ownerMasks"][0]["geometry"] = {"type": "Polygon", "coordinates": []}
        with self.assertRaisesRegex(ValueError, "AREA_VALIDATION_FAILED"):
            self.compile(state)

    def test_self_intersection_reuses_area_v3_rejection(self):
        state = ordinary_state()
        state["ownerMasks"][0]["geometry"] = {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]]}
        with self.assertRaisesRegex(ValueError, "AREA_RING_SELF_INTERSECTION"):
            self.compile(state)

    def test_mask_outside_source_domain_rejected(self):
        state = ordinary_state()
        state["ownerMasks"][1]["geometry"] = rectangle(2, 0, 5, 4)
        with self.assertRaisesRegex(ValueError, "MASK_OUTSIDE_SOURCE_DOMAIN"):
            self.compile(state)

    def test_unwrapped_projection_limit_is_explicit(self):
        for bounds in ([170, -5, -170, 5], [0, 86, 4, 89]):
            with self.subTest(bounds=bounds):
                state = ordinary_state()
                state["bbox"] = bounds
                with self.assertRaisesRegex(ValueError, "UNWRAPPED_GEOGRAPHIC_DOMAIN"):
                    self.compile(state)

    def test_western_and_southern_hemispheres_are_generic(self):
        state = ordinary_state()
        state["bbox"] = [-80, -40, -76, -36]
        state["domain"]["geometry"] = rectangle(-80, -40, -76, -36)
        state["ownerMasks"][0]["geometry"] = rectangle(-80, -40, -78, -36)
        state["ownerMasks"][1]["geometry"] = rectangle(-78, -40, -76, -36)
        self.assertTrue(self.compile(state)["completeExplicitDomainPartition"])

    def test_scene_cannot_replace_registered_geometry(self):
        state = ordinary_state()
        store = SyntheticServerFixture(state)
        self.addCleanup(store.close)
        registry = store.registry()
        state["ownerMasks"][0]["geometry"] = rectangle(0, 0, 3, 4)
        with self.assertRaisesRegex(ValueError, "SCENE_GEOMETRY_NOT_SOURCE_BOUND"):
            provider.compile_control_state(state, registry)

    def test_scene_approval_flags_are_rejected_not_authorization(self):
        state = ordinary_state()
        state.update(approved=True, ready=True)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_MISSING_FIELDS"):
            self.compile(state)

    def test_manifest_and_source_bytes_are_both_hash_pinned(self):
        store = SyntheticServerFixture(ordinary_state())
        self.addCleanup(store.close)
        with self.assertRaisesRegex(ValueError, "MANIFEST_HASH_MISMATCH"):
            provider.SourceRegistry.from_manifest(store.path, expected_sha256="0" * 64, mode="SYNTHETIC_TEST")
        (store.root / "source.txt").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
            store.registry()

    def test_source_symlink_and_path_escape_rejected(self):
        store = SyntheticServerFixture(ordinary_state())
        self.addCleanup(store.close)
        store.manifest["receipts"][0]["sourcePath"] = "../outside.txt"
        store.persist()
        with self.assertRaisesRegex(ValueError, "SOURCE_PATH_ESCAPE"):
            store.registry()
        store.manifest["receipts"][0]["sourcePath"] = "alias.txt"
        (store.root / "alias.txt").symlink_to(store.root / "source.txt")
        store.persist()
        with self.assertRaisesRegex(ValueError, "SOURCE_SYMLINK_REJECTED"):
            store.registry()

    def test_production_receipt_date_and_faction_are_checked(self):
        # Synthetic fixture exercising production validation only, never history.
        state = ordinary_state()
        state["mode"] = "PRODUCTION"
        store = SyntheticServerFixture(state, mode="PRODUCTION")
        self.addCleanup(store.close)
        registry = store.registry()
        changed = deepcopy(state)
        changed["asOfDate"] = "2000-01-02"
        with self.assertRaisesRegex(ValueError, "SOURCE_DATE_MISMATCH"):
            provider.compile_control_state(changed, registry)
        changed = deepcopy(state)
        changed["ownerMasks"][0]["factionId"] = "TEST_B"
        with self.assertRaisesRegex(ValueError, "SOURCE_FACTION_MISMATCH"):
            provider.compile_control_state(changed, registry)

    def test_synthetic_receipt_never_promoted_to_production(self):
        state = ordinary_state()
        store = SyntheticServerFixture(state)
        self.addCleanup(store.close)
        store.manifest["mode"] = "PRODUCTION"
        store.persist()
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_NOT_PRODUCTION"):
            store.registry()

    def test_illustrative_transition_needs_separate_source_adapter(self):
        state = ordinary_state()
        state["classification"] = "illustrative_transition"
        with self.assertRaisesRegex(ValueError, "SOURCE_SUPPORTED_TRANSITION_ADAPTER_REQUIRED"):
            self.compile(state)

    def test_standalone_front_input_cannot_desynchronize_from_masks(self):
        state = ordinary_state()
        state["sharedFront"] = {"type": "LineString", "coordinates": [[0, 0], [4, 4]]}
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_MISSING_FIELDS"):
            self.compile(state)

    def test_explicit_cpu_endpoint_contract_can_pass_without_gpu_claim(self):
        first, second = self.endpoint_pair()
        report = self.preflight(first, second)
        self.assertTrue(report["ready"])
        self.assertFalse(report["renderAllowed"])
        self.assertFalse(report["continuousMorphAllowed"])
        self.assertFalse(report["gpuVerified"])

    def test_same_state_with_new_frame_is_not_proof_of_movement(self):
        first = self.compile()
        second = ordinary_state()
        second.update(frame=29, asOfDate="2000-01-02", stateId="NEW_LABEL_SAME_GEOMETRY")
        report = self.preflight(first, self.compile(second))
        self.assertIn("CONTROL_SAME_MASKS_NOT_MOVEMENT", report["blockers"])

    def test_reordered_masks_and_reversed_rings_are_not_movement(self):
        first = self.compile()
        second = ordinary_state()
        second.update(frame=29, asOfDate="2000-01-02", stateId="DIFFERENT_SERIALIZATION_ONLY")
        second["ownerMasks"].reverse()
        for row in second["ownerMasks"]:
            row["geometry"]["coordinates"][0].reverse()
        self.assertIn("CONTROL_SAME_MASKS_NOT_MOVEMENT", self.preflight(first, self.compile(second))["blockers"])

    def test_disconnected_owners_without_shared_front_cannot_pass_front_gate(self):
        first_state = ordinary_state()
        first_state["ownerMasks"][0]["geometry"] = rectangle(0, 0, 1, 4)
        first_state["ownerMasks"][1]["geometry"] = rectangle(3, 0, 4, 4)
        first_state["unknownMasks"] = [{"sourceRef": "UNKNOWN", "geometry": rectangle(1, 0, 3, 4)}]
        second_state = deepcopy(first_state)
        second_state.update(frame=29, asOfDate="2000-01-02", stateId="DISCONNECTED_END")
        second_state["ownerMasks"][0]["geometry"] = rectangle(0, 0, 1.5, 4)
        second_state["unknownMasks"][0]["geometry"] = rectangle(1.5, 0, 3, 4)
        report = self.preflight(self.compile(first_state), self.compile(second_state))
        self.assertIn("CONTROL_SHARED_BILATERAL_FRONT_REQUIRED", report["blockers"])
        self.assertFalse(report["ready"])

    def test_endpoint_time_qualifiers_are_not_inferred_from_date(self):
        first, second = self.endpoint_pair()
        self.assertIn("CONTROL_ENDPOINT_TIME_QUALIFIER_MISMATCH",
                      self.preflight(first, second, expected_time_qualifiers=["NIGHT", "NIGHT"])["blockers"])
        self.assertIn("CONTROL_EXPECTED_ENDPOINT_TIME_QUALIFIERS_REQUIRED",
                      self.preflight(first, second, expected_time_qualifiers=None)["blockers"])

    def test_missing_endpoints_camera_and_roi_are_blocked_before_render(self):
        result = provider.preflight_control_transition(None, None, expected_factions=["A", "B"],
            expected_dates=["2000-01-01", "2000-01-02"], camera_admission={"ready": False}, event_roi=None)
        self.assertFalse(result["ready"])
        self.assertEqual(set(result["blockers"]), {"CONTROL_START_AND_END_REQUIRED", "CONTROL_EVENT_ROI_UNSUPPORTED",
                                                   "CONTROL_CAMERA_UNSUPPORTED_ZOOM"})

    def test_wrong_dates_faction_roi_and_fallback_id_blocked(self):
        first, second = self.endpoint_pair()
        result = self.preflight(first, second, expected_factions=["WRONG_COALITION", "TEST_B"],
            expected_dates=["1999-01-01", "2000-01-02"], event_roi=[10, 10, 20, 20],
            expected_state_ids=["NOT_SOURCE_START", "BUSAN_FALLBACK_LABEL"])
        for code in ("CONTROL_ENDPOINT_DATE_MISMATCH_OR_REVERSED", "CONTROL_ENDPOINT_FACTIONS_MISSING_OR_WRONG",
                     "CONTROL_EVENT_ROI_MISMATCH_NO_GEOGRAPHIC_FALLBACK", "CONTROL_SOURCE_ENDPOINT_ID_MISMATCH_NO_FALLBACK"):
            self.assertIn(code, result["blockers"])

    def test_reversed_date_and_frame_blocked(self):
        first, second = self.endpoint_pair()
        result = self.preflight(second, first)
        self.assertIn("CONTROL_ENDPOINT_DATE_MISMATCH_OR_REVERSED", result["blockers"])
        self.assertIn("CONTROL_ENDPOINT_FRAME_ORDER", result["blockers"])

    def test_json_compiled_lookalike_and_modified_frame_are_not_trusted(self):
        first, second = self.endpoint_pair()
        lookalike = json.loads(json.dumps(first))
        self.assertIn("CONTROL_UNTRUSTED_OR_MODIFIED_COMPILED_STATE", self.preflight(lookalike, second)["blockers"])
        first["sharedFront"]["frame"] = 100
        result = self.preflight(first, second)
        self.assertIn("CONTROL_UNTRUSTED_OR_MODIFIED_COMPILED_STATE", result["blockers"])
        self.assertIn("CONTROL_MASK_FRONT_SAME_FRAME_ID_REQUIRED", result["blockers"])

    def test_synthetic_positive_test_cannot_approve_historical_render(self):
        first, second = self.endpoint_pair()
        self.assertIn("CONTROL_SYNTHETIC_NOT_PRODUCTION", self.preflight(first, second, require_observed=True)["blockers"])

    def test_strict_json_rejects_duplicate_keys_and_nonfinite(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                provider.parse(raw)

    def test_actual_incheon_gate_is_server_pinned_blocked_no_new_coordinates(self):
        result = provider.validate_g2_history()
        self.assertEqual(result["status"], "G2_BLOCKED")
        self.assertFalse(result["ready"])
        self.assertFalse(result["renderAllowed"])
        self.assertEqual(result["historicalCoordinatesInvented"], 0)
        self.assertIn("G2_DATED_BILATERAL_CONTROL_START_AND_END_MISSING", result["blockers"])
        document = provider.parse((HERE / "fixtures/INCHEON_SOURCE_GATE.json").read_bytes())
        document["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "CLIENT_SOURCE_RECEIPT_NOT_TRUSTED"):
            provider.validate_g2_history(document)


if __name__ == "__main__":
    unittest.main()
