"""Read-only checks of partial bindings against preserved original source bytes."""

import hashlib
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class SourceBindingIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((HERE / "REFERENCE_DIRECTOR_INPUT.json").read_text())

    def test_every_referenced_source_is_actual_original_bytes(self):
        for binding in self.inputs["sourceBindings"]:
            with self.subTest(path=binding["path"]):
                content = (ROOT / binding["path"]).read_bytes()
                self.assertEqual(len(content), binding["bytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), binding["sha256"])

    def test_geometries_are_verbatim_source_features_not_fitted_replacements(self):
        for binding in self.inputs["dataRecords"]["geometries"]:
            with self.subTest(id=binding["id"]):
                source = binding["source"]
                features = json.loads((ROOT / source["path"]).read_text())["features"]
                original = features[source["featureIndex"]]
                self.assertEqual(original["properties"]["ADM0_A3"], source["featureId"])
                self.assertEqual(binding["geometry"], original["geometry"])
                self.assertEqual(canonical_hash(original), source["canonicalFeatureSHA256"])
                self.assertEqual(canonical_hash(original["geometry"]), source["canonicalGeometrySHA256"])
        primary = next(x for x in self.inputs["dataRecords"]["geometries"] if x["id"] == "COUNTRY_ESP")
        self.assertEqual(primary["geometry"]["type"], "MultiPolygon")
        self.assertEqual(len(primary["geometry"]["coordinates"]), 12)

    def test_locality_anchors_preserve_source_points_and_identity(self):
        for binding in self.inputs["dataRecords"]["locations"]:
            with self.subTest(id=binding["id"]):
                source = binding["source"]
                original = json.loads((ROOT / source["path"]).read_text())["features"][source["featureIndex"]]
                self.assertEqual(original["properties"]["ne_id"], source["featureId"])
                self.assertEqual(binding["geometry"], original["geometry"])
                self.assertEqual(canonical_hash(original), source["canonicalFeatureSHA256"])
                self.assertEqual(canonical_hash(original["geometry"]), source["canonicalGeometrySHA256"])

    def test_all_registered_raster_parents_and_licenses_match_catalog(self):
        from PIL import Image

        catalog_path = ROOT / "world-simulation-shorts-engine/recovery/universal-presentation-v2/REGION_SOURCE_CATALOG.json"
        catalog = json.loads(catalog_path.read_text())
        for source in catalog["sources"]:
            with self.subTest(id=source["id"]):
                image_path = ROOT / source["file"]
                self.assertEqual(hashlib.sha256(image_path.read_bytes()).hexdigest(), source["sha256"])
                self.assertEqual(image_path.stat().st_size, source["bytes"])
                with Image.open(image_path) as image:
                    self.assertEqual(list(image.size), source["dimensions"])
                license_bytes = (ROOT / source["licenseFile"]).read_bytes()
                self.assertEqual(hashlib.sha256(license_bytes).hexdigest(), source["licenseSHA256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
