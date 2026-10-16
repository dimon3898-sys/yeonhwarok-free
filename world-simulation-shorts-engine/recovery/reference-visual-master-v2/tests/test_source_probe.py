"""Focused synthetic fixture recipe tests; none is a WebGL/NVIDIA test."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

FILE = Path(__file__).resolve().parents[1] / "build_source_probe.py"
SPEC = importlib.util.spec_from_file_location("reference_source_probe_recipe", FILE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceProbeRecipeTests(unittest.TestCase):
    def test_three_role_recipe_and_every_download_binding_are_hash_anchored(self):
        with tempfile.TemporaryDirectory(prefix="source-probe-test-") as temp:
            target = Path(temp) / "bundle"
            result = MODULE.build(target)
            self.assertTrue(result["testOnly"])
            self.assertFalse(result["externalDownloadExecuted"])
            self.assertEqual(len(result["bindings"]), 14)
            for item in result["bindings"]:
                raw = (target / item["name"]).read_bytes()
                self.assertEqual(item["bytes"], len(raw))
                self.assertEqual(item["sha256"], MODULE.sha(raw))
            manifest = json.loads((target / "UPLOAD_BUNDLE.json").read_text())
            self.assertEqual(set(manifest["sources"]), {"terrain", "bathymetry", "surfaceTexture"})
            self.assertEqual(manifest["sources"]["terrain"]["parts"][0]["rowOrder"], "NORTH_TO_SOUTH")
            self.assertEqual(manifest["sources"]["bathymetry"]["parts"][0]["rowOrder"], "SOUTH_TO_NORTH")
            self.assertFalse(manifest["gpuRenderingVerified"])

    def test_negative_land_positive_bathymetry_and_all_role_nodata_points_are_real_fixture_values(self):
        sources, fixture = MODULE.fixture_sources()
        for role, result in sources.items():
            raster = result.rasters[0]
            t = raster.metadata["transform"]
            def sample(name):
                x, y = fixture["points"][name]
                i, j = int(np.floor((x - t[0]) / t[1])), int(np.floor((y - t[3]) / t[5]))
                return raster.values[j, i], raster.valid[j, i]
            value, valid = sample("noData")
            self.assertFalse(valid)
            if role == "terrain":
                self.assertTrue(np.isnan(value))
                self.assertEqual(float(sample("negativeDemLand")[0]), -30.)
                self.assertTrue(sample("negativeDemLand")[1])
            elif role == "bathymetry":
                self.assertEqual(int(value), -32767)
                self.assertEqual(int(sample("positiveGebcoOcean")[0]), 12)
                self.assertEqual(int(sample("negativeDemLand")[0]), -300)
            else:
                self.assertEqual(int(value[3]), 0)

    def test_recipe_is_deterministic_and_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory(prefix="source-probe-test-") as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            first, second = MODULE.build(a), MODULE.build(b)
            self.assertEqual(first["bindings"], second["bindings"])
            before = {file.name: file.read_bytes() for file in a.iterdir()}
            with self.assertRaises(FileExistsError):
                MODULE.build(a)
            self.assertEqual(before, {file.name: file.read_bytes() for file in a.iterdir()})


if __name__ == "__main__":
    unittest.main()
