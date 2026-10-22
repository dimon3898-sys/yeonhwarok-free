"""CPU source/clock regressions; actual native projection pixels are a later probe."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_g2_geometry_probe_builder", HERE/"tools/build_generic_probes.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class GenericGeometryAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("G2_GENERIC_PROBE_ROOT")
        cls.temporary = None
        if configured:
            cls.root = Path(configured)
        else:
            cls.temporary = tempfile.TemporaryDirectory(prefix="g2-generic-source-test-", dir="/workspace")
            cls.root = Path(cls.temporary.name)/"probes"
            builder.build(cls.root)
        cls.manifest = json.loads((cls.root/"PROBES.json").read_bytes())
        cls.cases = {row["id"]: row for row in cls.manifest["cases"]}
        cls.payloads = {}
        for case, row in cls.cases.items():
            file = cls.root/case/row["runtime"]["path"]
            cls.assert_hash(file, row["runtime"]["sha256"])
            cls.payloads[case] = json.loads(file.read_bytes())

    @classmethod
    def tearDownClass(cls):
        if cls.temporary is not None:
            cls.temporary.cleanup()

    @staticmethod
    def assert_hash(path, digest):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AssertionError("Actual generated source payload differs from its persisted SHA")

    def test_two_distinct_source_regions_and_terrain_conditions_use_one_builder(self):
        self.assertEqual(set(self.cases), {"namibia_desert_coast", "nepal_himalaya"})
        self.assertEqual({r["terrainCondition"] for r in self.cases.values()}, {"DESERT_AND_ATLANTIC_COAST", "MOUNTAIN_AND_PLAINS"})
        targets = {p["nativePlan"]["primary"] for p in self.payloads.values()}
        self.assertEqual(len(targets), 2)
        for value in ("COUNTRY_NAM", "COUNTRY_NPL", "COUNTRY_KOR"):
            self.assertNotIn(value, (HERE/"tools/build_generic_probes.py").read_text())

    def test_unchanged_main_geometry_archive_and_quarter_grid_are_not_smoothed(self):
        source = builder.OLD/"fixtures/SOURCE_BUNDLE.zip"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), "bd6e7f54691bfed361d98f0bd8b3c4575a17a0dc2fc033f7501b2be730d03cb3")
        with ZipFile(source) as archive:
            raw = archive.read("demo/DOMAIN.geojson")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), "85cadf15126dab7354b73b4a3f4e5bf0d3cb4f2f5dc166682081a870cb5c9af8")
            geometry = json.loads(raw)
            self.assertEqual(len(geometry["coordinates"][0]), 105)
            self.assertTrue(all(value*4 == round(value*4) for point in geometry["coordinates"][0] for value in point))
            self.assertTrue(all(archive.read(f"demo/frames/{frame:03d}_DOMAIN.geojson") == raw for frame in range(180)))

    def test_every_owner_and_front_frame_is_compiled_from_actual_pinned_receipts(self):
        for case, payload in self.payloads.items():
            root = self.root/case
            for index, current in enumerate(payload["frames"]):
                folder = root/f"samples/{index:03d}"
                registry = builder.control.SourceRegistry.from_manifest(folder/"RECEIPTS.json",
                    expected_sha256=builder.sha((folder/"RECEIPTS.json").read_bytes()), mode="SYNTHETIC_TEST")
                source = json.loads((folder/"STATE.json").read_bytes())
                result = builder.control.compile_control_state(source, registry)
                self.assertTrue(result.source_binding_valid())
                self.assertEqual(dict(result), current)
                self.assertEqual(current["frame"], index)
                self.assertTrue(current["completeExplicitDomainPartition"])
                self.assertTrue(current["sharedFront"]["geometry"]["coordinates"])
                for item in [*current["ownerMasks"], current["sharedFront"], current["unknownMask"], current["contestedMask"]]:
                    self.assertEqual((item["fieldId"], item["frame"]), (current["fieldId"], index))

    def test_southern_latitudes_land_containment_and_exact_partition_are_preserved(self):
        self.assertLess(self.payloads["namibia_desert_coast"]["eventLocation"][1], 0)
        self.assertGreater(self.payloads["nepal_himalaya"]["eventLocation"][1], 0)
        for case, payload in self.payloads.items():
            primary = next(g for g in payload["nativePlan"]["geometries"] if g["id"] == payload["nativePlan"]["primary"])
            original = {"type": primary["geometry_type"], "coordinates": primary["coordinates"]}
            domain = json.loads((self.root/case/"DOMAIN.geojson").read_bytes())
            with builder.control._Geos() as geos:
                land, observation = geos.geometry(original), geos.geometry(domain)
                self.assertEqual(geos.area(geos.operation("difference", observation, land)), 0)
                for field in payload["frames"]:
                    first, second = [geos.geometry(item["geometry"]) for item in field["ownerMasks"]]
                    self.assertEqual(geos.area(geos.operation("difference", first, observation)), 0)
                    self.assertEqual(geos.area(geos.operation("difference", second, observation)), 0)
                    self.assertEqual(geos.area(geos.operation("intersection", first, second)), 0)
                    self.assertEqual(geos.area(geos.operation("difference", observation, geos.operation("union", first, second))), 0)

    def test_three_camera_samples_are_actual_immutable_v5_evaluations(self):
        bridge = """
import {readFileSync} from 'node:fs';
import {evaluateMinimumContextCameraFrame} from './world-simulation-shorts-engine/web/map_infographic_v1/camera_director_v5.mjs';
const p=JSON.parse(readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(p.cameraSchedule.map(c=>evaluateMinimumContextCameraFrame(p.cameraPlan,c.sourceFrame))));
"""
        for payload in self.payloads.values():
            self.assertEqual([v["frame"] for v in payload["cameraSchedule"]], [0, 1, 2])
            self.assertEqual([v["sourceFrame"] for v in payload["cameraSchedule"]], [0, 54, 0])
            response = subprocess.run(["node", "--input-type=module", "-e", bridge], cwd=builder.REPO,
                input=builder.canonical(payload), capture_output=True, timeout=30, check=True)
            for clock, actual in zip(payload["cameraSchedule"], json.loads(response.stdout)):
                self.assertEqual(clock["flatBounds"], actual["camera"]["flatBounds"])
                self.assertFalse(actual["admission"]["localUsed"])
            self.assertEqual(payload["cameraSchedule"][0]["flatBounds"], payload["cameraSchedule"][2]["flatBounds"])

    def test_original_modern_source_polygon_vertices_are_not_replaced_by_grid(self):
        seed = json.loads(Path("/workspace/exact-65422-capsule-20261020/world-simulation-shorts-engine/recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json").read_bytes())
        for payload in self.payloads.values():
            current = next(g for g in payload["nativePlan"]["geometries"] if g["id"] == payload["nativePlan"]["primary"])
            original = next(g for g in seed["geometries"] if g["id"] == current["id"])
            self.assertEqual(current["coordinates"], original["coordinates"])
            self.assertEqual(current["source_file_sha256"], original["source_file_sha256"])

    def test_any_unapproved_coordinate_change_fails_the_existing_source_registry(self):
        case = next(iter(self.payloads))
        folder = self.root/case/"samples/000"
        registry = builder.control.SourceRegistry.from_manifest(folder/"RECEIPTS.json",
            expected_sha256=builder.sha((folder/"RECEIPTS.json").read_bytes()), mode="SYNTHETIC_TEST")
        state = json.loads((folder/"STATE.json").read_bytes())
        changed = deepcopy(state)
        coordinate = builder.points(changed["ownerMasks"][0]["geometry"]["coordinates"])[0]
        coordinate[0] += 1e-9
        with self.assertRaisesRegex(ValueError, "CONTROL_SCENE_GEOMETRY_NOT_SOURCE_BOUND"):
            builder.control.compile_control_state(changed, registry)

    def test_sources_cannot_claim_history_pixels_or_automatically_replace_a_run(self):
        for case, manifest in self.cases.items():
            self.assertEqual(manifest["classification"], "SYNTHETIC_TECHNICAL_PROBE_NOT_HISTORY")
            self.assertFalse(manifest["rendererExecuted"])
            self.assertFalse(manifest["historicalG3Allowed"])
            self.assertFalse(manifest["materialStyleAdmitted"])
            self.assertTrue(all(v["mode"] == "SYNTHETIC_TEST" for v in self.payloads[case]["frames"]))
        before = (self.root/"PROBES.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "GENERIC_PROBE_OUTPUT_MUST_BE_NEW"):
            builder.build(self.root)
        self.assertEqual((self.root/"PROBES.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
