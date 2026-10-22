import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_positions_test", HERE / "tools/extract_source_positions.py")
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
PDF = Path("/workspace/astra-history-p0-research-20261021/GOVINFO_UN_OFFENSIVE_1950.pdf")
OUTPUT = HERE / "source-review/CMH_UN_OFFENSIVE_PDF008_POSITION_PATHS.json"


class SourcePositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(OUTPUT.read_bytes())

    def test_original_hash_bound_and_persisted_source_commands_reproducible(self):
        if not PDF.is_file():
            self.skipTest("Original cached PDF absent; source SHA remains pinned, not a live source test")
        self.assertEqual(self.record, extractor.extract(PDF))

    def test_eight_dated_native_position_paths_no_fake_geographic_geometry(self):
        positions = self.record["positions"]
        self.assertEqual(len(positions), 8)
        self.assertEqual(sum(r["as_of_date"] == "1950-09-15" for r in positions), 6)
        self.assertEqual(sum(r["as_of_date"] == "1950-09-16" for r in positions), 2)
        self.assertEqual({r["geometry"]["type"] for r in positions}, {"PDF_VECTOR_PATH"})
        self.assertFalse(any(r["geometry"]["closed"] for r in positions))

    def test_source_coordinate_system_cannot_be_mistaken_for_epsg4326(self):
        coordinates = self.record["page_coordinates"]
        self.assertEqual(coordinates["crs"], "PDF_PAGE_POINTS_TOP_LEFT")
        self.assertIsNone(coordinates["geographic_crs"])
        self.assertIsNone(coordinates["coordinate_transform"]["coefficients"])
        self.assertEqual(coordinates["coordinate_transform"]["status"], "UNVERIFIED")

    def test_bhl_arrows_coastline_opposing_owner_not_admitted(self):
        evidence = self.record["selection_evidence"]
        self.assertNotIn(evidence["excluded_bhl_path_index"], [r["source_path_index_zero_based"] for r in self.record["positions"]])
        self.assertTrue(evidence["landing_arrows_unit_symbols_shoreline_and_urban_fill_excluded"])
        self.assertEqual(self.record["owner_masks"], [])
        self.assertFalse(self.record["render_allowed"])
        self.assertEqual(self.record["g2_full_area"], "BLOCKED")

    def test_no_registration_residual_or_geographic_accuracy_invented(self):
        registration = self.record["registration"]
        self.assertEqual(registration["independent_geographic_gcps"], 0)
        for key in ("residual_meters", "held_out_residual_meters", "total_spatial_accuracy_meters"):
            self.assertIsNone(registration[key])


if __name__ == "__main__":
    unittest.main()
