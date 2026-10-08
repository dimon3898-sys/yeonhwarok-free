"""Native regional assets and geometry masks must not invent source detail."""
from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path

from PIL import Image


APP_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = APP_ROOT / "tools/build_visual_quality_assets.py"
SPEC = importlib.util.spec_from_file_location("visual_quality_asset_builder", BUILDER_PATH)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class NativeRegionalAssetsTests(unittest.TestCase):
    def test_actual_manifest_regions_are_native_pixels_and_original_source(self):
        root = APP_ROOT / "web/earth-detail/v018"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["source"]["resolution"], [21600, 10800])
        self.assertEqual(manifest["source"]["sha256"], builder.RASTER_SHA256)
        self.assertEqual(manifest["coast_source"]["sha256"], builder.COUNTRIES_SHA256)
        self.assertEqual(manifest["generation"]["resampling"], "NONE")
        self.assertEqual(manifest["generation"]["global_master_textures"], "UNCHANGED")
        self.assertEqual(len(manifest["textures"]), 4)
        for texture in manifest["textures"]:
            file = APP_ROOT / texture["file"]
            self.assertTrue(file.is_file())
            self.assertGreater(file.stat().st_size, 0)
            self.assertEqual(builder.sha256(file), texture["sha256"])
            with Image.open(file) as image:
                self.assertEqual(list(image.size), [texture["width"], texture["height"]])
                self.assertEqual(image.mode, "RGB" if texture["role"] == "regional_day_relief" else "L")
            self.assertFalse(texture["resized"])
            self.assertFalse(texture["sharpened"])
            left, top, right, bottom = texture["source_pixel_window"]
            self.assertEqual(right - left, texture["width"])
            self.assertEqual(bottom - top, texture["height"])
            west, south, east, north = texture["bounds"]
            self.assertAlmostEqual(west, left / 21600 * 360 - 180)
            self.assertAlmostEqual(east, right / 21600 * 360 - 180)
            self.assertAlmostEqual(north, 90 - top / 10800 * 180)
            self.assertAlmostEqual(south, 90 - bottom / 10800 * 180)

    def test_native_window_matches_span_without_source_resampling(self):
        window, bounds = builder.native_crop_window(15.137, 22.419, (21600, 10800))
        left, top, right, bottom = window
        self.assertEqual((right - left, bottom - top), (1440, 1680))
        west, south, east, north = bounds
        self.assertEqual(round((east - west) * 60), 1440)
        self.assertEqual(round((north - south) * 60), 1680)
        self.assertLessEqual(abs((west + east) / 2 - 15.137), 1 / 120)
        self.assertLessEqual(abs((south + north) / 2 - 22.419), 1 / 120)

    def test_antimeridian_request_rejected_instead_of_silent_wrong_crop(self):
        with self.assertRaisesRegex(ValueError, "ANTIMERIDIAN_REQUIRES_SPLIT"):
            builder.native_crop_window(175, 20, (21600, 10800))

    def test_invalid_center_is_explicit(self):
        for lon, lat in [(math.nan, 20), (15, math.inf), (181, 0), (0, 91)]:
            with self.subTest(lon=lon, lat=lat):
                with self.assertRaisesRegex(ValueError, "COORDINATE_INVALID"):
                    builder.native_crop_window(lon, lat, (21600, 10800))

    def test_generic_event_centers_do_not_depend_on_place_names(self):
        plan = {"scenes": [{"second_event_camera": {
            "event1_camera": {"lon": 10.5, "lat": -20.5},
            "event2_camera": {"lon": -70.5, "lat": 40.5},
            "adaptive_camera": {"lon": 0, "lat": 0}}}]}
        self.assertEqual(builder.event_centers(plan), [
            {"lon": 10.5, "lat": -20.5}, {"lon": -70.5, "lat": 40.5}])

    def test_land_mask_preserves_polygon_water_hole(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]
        feature = {"geometry": {"type": "Polygon", "coordinates": [outer, hole]}}
        mask, count = builder.rasterize_land_mask([feature], [0, 0, 10, 10], (100, 100))
        self.assertEqual(count, 1)
        self.assertEqual(mask.getpixel((10, 10)), 255)
        self.assertEqual(mask.getpixel((50, 50)), 0)

    def test_enclave_union_independent_of_feature_order(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]
        enclave = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
        first = {"geometry": {"type": "Polygon", "coordinates": [outer, hole]}}
        second = {"geometry": {"type": "Polygon", "coordinates": [enclave]}}
        a, _ = builder.rasterize_land_mask([first, second], [0, 0, 10, 10], (100, 100))
        b, _ = builder.rasterize_land_mask([second, first], [0, 0, 10, 10], (100, 100))
        self.assertEqual(a.tobytes(), b.tobytes())
        self.assertEqual(a.getpixel((50, 50)), 255)
        self.assertEqual(a.getpixel((35, 35)), 0)

    def test_distant_antimeridian_polygon_cannot_fill_local_tile(self):
        ring = [[179, 1], [-179, 1], [-179, -1], [179, -1], [179, 1]]
        feature = {"geometry": {"type": "Polygon", "coordinates": [ring]}}
        mask, count = builder.rasterize_land_mask([feature], [-12, -14, 12, 14], (120, 140))
        self.assertEqual(count, 0)
        self.assertIsNone(mask.getbbox())


if __name__ == "__main__":
    unittest.main()
