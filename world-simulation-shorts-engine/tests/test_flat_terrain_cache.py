"""Tiny synthetic geospatial fixtures test asset caching, not video quality."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.prepare_flat_terrain import prepare_flat_terrain, TerrainPreparationError, sha256_file


class FlatTerrainCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wss-flat-terrain-test-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "synthetic-test-only.tif"
        image = Image.new("RGB", (8, 4))
        image.putdata([(x * 27, y * 50, (x + y) * 17) for y in range(4) for x in range(8)])
        image.save(self.source, "TIFF")
        self.world = self.root / "synthetic-test-only.tfw"
        self.world.write_text("45\n0\n0\n-45\n-157.5\n67.5\n")
        self.projection = self.root / "synthetic-test-only.prj"
        self.projection.write_text('GEOGCS["GCS_WGS_1984",UNIT["Degree",0.017453292519943295]]')
        self.notice = self.root / "NOTICE.txt"
        self.notice.write_text("Synthetic fixture created by test; not production geography.")
        self.record = {"source_original_sha256": sha256_file(self.source),
                       "source_original_dimensions": [8, 4],
                       "world_file_sha256": sha256_file(self.world),
                       "projection_file_sha256": sha256_file(self.projection),
                       "source_pinned_commit": "a" * 40,
                       "url": "https://example.invalid/test-only-geography.tif",
                       "author": "Test fixture", "license": "CC0-1.0",
                       "attribution_required": False, "download_date": "not downloaded"}
        self.cache = self.root / "cache"

    def prepare(self, **changes):
        values = dict(source=self.source, source_record=self.record, world_file=self.world,
                      projection_file=self.projection, license_notice=self.notice,
                      bounds=(-135, -45, 45, 45), cache_dir=self.cache,
                      max_width=4096, max_height=4096)
        values.update(changes)
        return prepare_flat_terrain(**values)

    def test_real_pixel_crop_and_identical_bytes_reused_without_rewrite(self):
        original = self.source.read_bytes()
        first = self.prepare()
        png = Path(first["file"])
        metadata = png.with_suffix(".json")
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (png, metadata)]
        second = self.prepare()
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["cache_key"], second["cache_key"])
        self.assertEqual(first["source_pixel_box"], [1, 1, 5, 3])
        self.assertEqual(first["dimensions"], [4, 2])
        self.assertEqual(first["geographic_bounds"], dict(west=-135.0, south=-45.0, east=45.0, north=45.0))
        with Image.open(png) as crop, Image.open(self.source) as source:
            self.assertEqual(crop.getpixel((0, 0)), source.getpixel((1, 1)))
            self.assertEqual(crop.getpixel((3, 1)), source.getpixel((4, 2)))
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in (png, metadata)])
        self.assertEqual(self.source.read_bytes(), original)

    def test_size_cap_downsamples_without_upscale_and_changes_cache_key(self):
        native = self.prepare()
        smaller = self.prepare(max_width=2, max_height=2)
        self.assertEqual(native["dimensions"], [4, 2])
        self.assertEqual(smaller["dimensions"], [2, 1])
        self.assertNotEqual(native["cache_key"], smaller["cache_key"])
        self.assertFalse(native["upscaled"])
        self.assertFalse(smaller["upscaled"])

    def test_fractional_request_reports_outward_native_pixel_bounds(self):
        result = self.prepare(bounds=(-130, -40, 40, 40))
        self.assertEqual(result["source_pixel_box"], [1, 1, 5, 3])
        self.assertEqual(result["geographic_bounds"], dict(west=-135.0, south=-45.0, east=45.0, north=45.0))
        self.assertEqual(result["recipe"]["requested_bounds"]["west"], -130)

    def test_tampered_cached_png_is_preserved_and_refused(self):
        result = self.prepare()
        png = Path(result["file"])
        png.write_bytes(png.read_bytes() + b"changed")
        tampered = png.read_bytes()
        with self.assertRaisesRegex(TerrainPreparationError, "CACHE_METADATA_OR_SHA_MISMATCH"):
            self.prepare()
        self.assertEqual(png.read_bytes(), tampered)

    def test_missing_metadata_does_not_overwrite_complete_png(self):
        result = self.prepare()
        png = Path(result["file"])
        before = png.read_bytes()
        png.with_suffix(".json").unlink()
        with self.assertRaisesRegex(TerrainPreparationError, "INCOMPLETE_IMMUTABLE"):
            self.prepare()
        self.assertEqual(png.read_bytes(), before)

    def test_source_and_georeference_hash_mismatch_are_blocked(self):
        bad = deepcopy(self.record)
        bad["source_original_sha256"] = "0" * 64
        with self.assertRaisesRegex(TerrainPreparationError, "SOURCE_SHA256_MISMATCH"):
            self.prepare(source_record=bad)
        self.world.write_text("45\n0\n0\n-45\n-156.5\n67.5\n")
        with self.assertRaisesRegex(TerrainPreparationError, "GEOREFERENCE_HASH_MISMATCH"):
            self.prepare()
        self.assertFalse(self.cache.exists())

    def test_dateline_polar_nonfinite_and_invalid_bounds_fail_without_cache(self):
        for bounds in [(170, -10, -170, 10), (-20, -90, 20, 40),
                       (-20, 10, 20, 90), (float("nan"), -10, 20, 10),
                       (-181, -10, 20, 10), (-20, 30, 20, 10)]:
            with self.subTest(bounds=bounds), self.assertRaises(TerrainPreparationError):
                self.prepare(bounds=bounds)
        self.assertFalse(self.cache.exists())

    def test_projected_or_rotated_sources_are_not_silently_stretched(self):
        self.projection.write_text('PROJCS["WGS_1984_Web_Mercator",UNIT["Meter",1]]')
        with self.assertRaisesRegex(TerrainPreparationError, "UNSUPPORTED_PROJECTION"):
            self.prepare()
        self.projection.write_text('GEOGCS["GCS_WGS_1984",UNIT["Degree",0.017453292519943295]]')
        self.world.write_text("45\n0.2\n0\n-45\n-157.5\n67.5\n")
        with self.assertRaisesRegex(TerrainPreparationError, "UNSUPPORTED_ROTATED"):
            self.prepare()
        self.assertFalse(self.cache.exists())

    def test_changed_bounds_have_independent_cache_entries(self):
        first = self.prepare()
        second = self.prepare(bounds=(-90, -45, 90, 45))
        self.assertNotEqual(first["cache_key"], second["cache_key"])
        self.assertEqual(len(list(self.cache.glob("*.png"))), 2)

    def test_missing_pinned_provenance_and_unknown_license_are_refused(self):
        for field, value in [("source_original_sha256", ""),
                             ("source_pinned_commit", "main"),
                             ("author", ""), ("license", "UNKNOWN")]:
            bad = deepcopy(self.record)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(TerrainPreparationError):
                self.prepare(source_record=bad)
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
