"""Surface ingest checks using the delivered archive and small explicit grids."""
from io import BytesIO
from pathlib import Path
import struct
import unittest
from zipfile import ZipFile
import zlib

import numpy as np
from osgeo import osr
from PIL import Image, PngImagePlugin

from astra_cpu.model import DataError, sha256
from astra_cpu.surface import parse_surface


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent / "astra-map-quality-v1" / "inputs" / "ESSENTIAL_MAP_SAMPLES.zip"
PNG_NAME = "samples/BlueMarble_NextGeneration_Korea.png"
WORLD_NAME = "samples/BlueMarble_NextGeneration_Korea.pgw"
PROJECTION_NAME = "samples/BlueMarble_NextGeneration_Korea.prj"
FIXTURE_HASHES = {
    "PNG": "991c7bdfb8515a787c220b58b066241ac38411721124fbd8e6fae22131c793be",
    "worldfile": "aa58b9441629200b0c916fc339fedf5fa244fbc27db3f3d6b4c3abd31ea85807",
    "projection": "d0b1115b75468680d8d22aa102e02d4ce76b79de9c06e4c7f8663f4c3d29fcd2",
}


def projection_wkt(code=4326):
    with osr.ExceptionMgr():
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(code)
        return reference.ExportToWkt()


WGS84 = projection_wkt()
WORLD = "0.5\n0\n0\n-0.5\n-123.75\n-10.25\n"
RGB = np.array([[[1, 2, 3], [64, 128, 200], [255, 0, 10]],
                [[20, 30, 40], [50, 60, 70], [80, 90, 100]]], dtype=np.uint8)


def png_bytes(values=RGB, **save_options):
    buffer = BytesIO()
    Image.fromarray(values).save(buffer, format="PNG", **save_options)
    return buffer.getvalue()


class ArchiveSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only the three inputs consumed by this parser are checked here.
        with ZipFile(ARCHIVE) as archive:
            cls.png = archive.read(PNG_NAME)
            cls.world = archive.read(WORLD_NAME)
            cls.projection = archive.read(PROJECTION_NAME)
        cls.raster = parse_surface(
            cls.png, cls.world, cls.projection,
            expected_sha256=FIXTURE_HASHES["PNG"],
            expected_sidecar_sha256={name: FIXTURE_HASHES[name]
                                    for name in ("worldfile", "projection")})

    def test_delivered_png_channels_are_bit_exact(self):
        with Image.open(BytesIO(self.png)) as image:
            original = np.array(image)
        self.assertEqual(self.raster.values.shape, (2000, 1600, 4))
        self.assertEqual(self.raster.values.dtype, np.uint8)
        np.testing.assert_array_equal(self.raster.values, original)
        self.assertTrue(self.raster.valid.all())
        self.assertFalse(self.raster.values.flags.writeable)

    def test_first_center_and_corner_transform_follow_worldfile(self):
        np.testing.assert_allclose(self.raster.metadata["transform"],
                                   [124, .005, 0, 43, 0, -.005], rtol=0, atol=1e-12)
        np.testing.assert_allclose([self.raster.x[0], self.raster.y[0]],
                                   [124.0025, 42.9975], rtol=0, atol=1e-12)
        np.testing.assert_allclose([self.raster.x[-1], self.raster.y[-1]],
                                   [131.9975, 33.0025], rtol=0, atol=1e-12)
        np.testing.assert_allclose(self.raster.bbox, [124, 33, 132, 43], rtol=0, atol=1e-12)

    def test_archive_crop_preserves_channels_and_actual_coordinates(self):
        crop = self.raster.crop((126, 36, 129, 39))
        np.testing.assert_array_equal(crop.values, self.raster.values[800:1400, 400:1000])
        np.testing.assert_array_equal(crop.valid, self.raster.valid[800:1400, 400:1000])
        np.testing.assert_array_equal(crop.x, self.raster.x[400:1000])
        np.testing.assert_array_equal(crop.y, self.raster.y[800:1400])
        np.testing.assert_allclose(crop.bbox, [126, 36, 129, 39], rtol=0, atol=1e-12)

    def test_metadata_retains_raw_sidecar_hashes_without_source_resolution_inference(self):
        metadata = self.raster.metadata
        self.assertEqual(metadata["inputSha256"], FIXTURE_HASHES["PNG"])
        self.assertEqual(metadata["sidecarSha256"],
                         {name: FIXTURE_HASHES[name] for name in ("worldfile", "projection")})
        self.assertEqual(metadata["crs"], "EPSG:4326")
        self.assertEqual(metadata["projectionWkt"], self.projection.decode())
        self.assertEqual(metadata["pixelRegistration"], "Area")
        self.assertEqual(metadata["horizontalUnits"], "degree")
        self.assertEqual(metadata["verticalDatum"], "NOT_APPLICABLE")
        self.assertEqual(metadata["pngInfo"], {})
        self.assertEqual(metadata["colorSpace"], "UNSPECIFIED_ENCODED_PNG_BYTES_PRESERVED")
        self.assertEqual(metadata["physicalAlbedo"], "NOT_INFERRED")
        self.assertNotIn("nativeResolution", metadata)


class SyntheticSurfaceTests(unittest.TestCase):
    def test_rgb_grid_uses_its_own_bounds_and_keeps_southern_hemisphere_signs(self):
        raster = parse_surface(png_bytes(), WORLD, WGS84)
        np.testing.assert_array_equal(raster.values, RGB)
        np.testing.assert_array_equal(raster.x, [-123.75, -123.25, -122.75])
        np.testing.assert_array_equal(raster.y, [-10.25, -10.75])
        self.assertEqual(raster.bbox, (-124, -11, -122.5, -10))
        self.assertTrue(raster.valid.all())
        self.assertIsNone(raster.metadata["nodata"])
        self.assertEqual(raster.metadata["rowOrder"], "NORTH_TO_SOUTH")
        self.assertIs(raster.north_up(), raster)

    def test_south_up_reordering_and_crop_are_lossless(self):
        world = WORLD.replace("-0.5\n", "0.5\n")
        raster = parse_surface(png_bytes(), world, WGS84)
        np.testing.assert_array_equal(raster.y, [-10.25, -9.75])
        self.assertEqual(raster.metadata["rowOrder"], "SOUTH_TO_NORTH")
        north_up = raster.north_up()
        np.testing.assert_array_equal(north_up.values, RGB[::-1])
        np.testing.assert_array_equal(north_up.y, [-9.75, -10.25])
        self.assertEqual(north_up.bbox, raster.bbox)
        crop = north_up.crop((-123.5, -10.5, -122.5, -10))
        np.testing.assert_array_equal(crop.values, RGB[0:1, 1:3])
        np.testing.assert_array_equal(crop.x, [-123.25, -122.75])
        np.testing.assert_array_equal(crop.y, [-10.25])

    def test_alpha_zero_masks_support_without_zero_filling_or_dropping_alpha(self):
        rgba = np.array([[[200, 100, 50, 0], [1, 2, 3, 1], [4, 5, 6, 255]]], dtype=np.uint8)
        raster = parse_surface(png_bytes(rgba), WORLD, WGS84)
        np.testing.assert_array_equal(raster.values, rgba)
        np.testing.assert_array_equal(raster.valid, [[False, True, True]])
        self.assertEqual(raster.metadata["nodata"], {"alpha": 0})

    def test_rgb_transparency_masks_matching_samples_without_color_conversion(self):
        raster = parse_surface(png_bytes(transparency=(64, 128, 200)), WORLD, WGS84)
        np.testing.assert_array_equal(raster.values, RGB)
        np.testing.assert_array_equal(raster.valid, [[True, False, True], [True, True, True]])
        self.assertEqual(raster.metadata["nodata"], {"transparency": (64, 128, 200)})

    def test_black_rgb_is_valid_without_explicit_transparency(self):
        black = np.zeros((1, 1, 3), dtype=np.uint8)
        raster = parse_surface(png_bytes(black), WORLD, WGS84)
        self.assertTrue(raster.valid[0, 0])
        np.testing.assert_array_equal(raster.values, black)

    def test_png_gamma_srgb_and_text_are_preserved_and_never_applied(self):
        png_info = PngImagePlugin.PngInfo()
        png_info.add(b"gAMA", struct.pack(">I", 45455))
        png_info.add(b"sRGB", b"\x00")
        chromaticity = (31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)
        png_info.add(b"cHRM", struct.pack(">8I", *chromaticity))
        png_info.add_text("description", "Encoded color, not measured albedo")
        data = png_bytes(pnginfo=png_info)
        raster = parse_surface(data, WORLD, WGS84)
        with Image.open(BytesIO(data)) as image:
            expected_info = dict(image.info)
        np.testing.assert_array_equal(raster.values, RGB)
        self.assertEqual(raster.metadata["pngInfo"], expected_info)
        self.assertEqual(raster.metadata["pngColorMetadata"],
                         {key: expected_info[key] for key in ("gamma", "srgb", "chromaticity")})
        self.assertEqual(raster.metadata["colorSpace"], "sRGB_ENCODED_BYTES_PRESERVED")
        self.assertEqual(raster.metadata["colorConversion"], "NONE")

    def test_embedded_icc_bytes_are_preserved_without_interpreting_profile(self):
        profile = b"opaque fixture ICC bytes\x00\x01"
        raster = parse_surface(png_bytes(icc_profile=profile), WORLD, WGS84)
        np.testing.assert_array_equal(raster.values, RGB)
        self.assertEqual(raster.metadata["pngInfo"]["icc_profile"], profile)
        self.assertEqual(raster.metadata["colorSpace"], "ICC_ENCODED_BYTES_PRESERVED")

    def test_non_wgs84_geographic_crs_is_preserved_without_defaulting_to_wgs84(self):
        raster = parse_surface(png_bytes(), WORLD, projection_wkt(4269))
        self.assertEqual(raster.metadata["crs"], "EPSG:4269")
        np.testing.assert_array_equal(raster.values, RGB)

    def test_exact_sidecar_line_endings_bom_and_utf8_text_hashes(self):
        data = png_bytes()
        world = b"\xef\xbb\xbf" + WORLD.replace("\n", "\r\n").encode()
        projection = WGS84 + "\n"
        hashes = {"worldfile": sha256(world), "projection": sha256(projection.encode())}
        raster = parse_surface(data, world, projection, expected_sha256=sha256(data).upper(),
                               expected_sidecar_sha256=hashes)
        self.assertEqual(raster.metadata["sidecarSha256"], hashes)
        self.assertNotEqual(hashes["worldfile"], sha256(WORLD.encode()))


class InvalidSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.png = png_bytes()

    def test_hash_mismatch_checks_each_raw_input(self):
        for name in ("PNG", "worldfile", "projection"):
            with self.subTest(name=name), self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
                options = ({"expected_sha256": "0" * 64} if name == "PNG"
                           else {"expected_sidecar_sha256": {name: "0" * 64}})
                parse_surface(self.png, WORLD, WGS84, **options)

    def test_bad_hash_format_and_unknown_sidecar_keys_fail(self):
        options_list = [{"expected_sha256": "bad"}, {"expected_sha256": 123},
                        {"expected_sidecar_sha256": {"worldfile": "bad"}},
                        {"expected_sidecar_sha256": {"pgw": "0" * 64}},
                        {"expected_sidecar_sha256": []}]
        for options in options_list:
            with self.subTest(options=options), self.assertRaises(DataError):
                parse_surface(self.png, WORLD, WGS84, **options)

    def test_rotated_or_sheared_worldfiles_fail_explicitly(self):
        for world in (".5\n.01\n0\n-.5\n1\n2", ".5\n0\n-.01\n-.5\n1\n2"):
            with self.subTest(world=world), self.assertRaisesRegex(DataError, "rotated or sheared"):
                parse_surface(self.png, world, WGS84)

    def test_nonfinite_malformed_degenerate_and_westward_worldfiles_fail(self):
        worlds = ["", "0.5 0 0 -0.5 1", "0.5 0 0 -0.5 1 2 3", "word 0 0 -1 1 2",
                  "nan 0 0 -1 1 2", "1 0 0 inf 1 2", "1 0 0 -1 -inf 2",
                  "0 0 0 -1 1 2", "1 0 0 0 1 2", "-1 0 0 -1 1 2",
                  "1.7e308 0 0 -1 -1.7e308 2", "1e308 0 0 -1 1e308 2",
                  b"\xff", "0.5\x00 0 0 -0.5 1 2", None]
        for world in worlds:
            with self.subTest(world=world), self.assertRaises(DataError):
                parse_surface(self.png, world, WGS84)

    def test_finite_centers_cannot_hide_infinite_outer_pixel_edges(self):
        single = png_bytes(np.array([[[1, 2, 3]]], dtype=np.uint8))
        with self.assertRaisesRegex(DataError, "nonfinite outer pixel edges"):
            parse_surface(single, "1.7e308 0 0 -1 1e308 38", WGS84)

    def test_unrepresentable_spacing_cannot_collapse_centers_or_edges(self):
        for world in ("1e-20 0 0 -1 125 38", "1 0 0 -1e-20 125 38"):
            with self.subTest(world=world), self.assertRaisesRegex(DataError, "collapses"):
                parse_surface(self.png, world, WGS84)
        single = png_bytes(np.array([[[1, 2, 3]]], dtype=np.uint8))
        with self.assertRaisesRegex(DataError, "collapses"):
            parse_surface(single, "1e-20 0 0 -1e-20 125 38", WGS84)

    def test_empty_invalid_non_wkt_and_projected_projection_fail(self):
        for projection in ("", "not a projection", "EPSG:4326", b"\xff", None):
            with self.subTest(projection=projection), self.assertRaises(DataError):
                parse_surface(self.png, WORLD, projection)
        with self.assertRaisesRegex(DataError, "projected.*unsupported"):
            parse_surface(self.png, WORLD, projection_wkt(3857))

    def test_radian_and_nonfinite_geodetic_crs_fail(self):
        radians = ('GEOGCS["Custom radians",DATUM["D",SPHEROID["Sphere",6371000,0]],'
                   'PRIMEM["Greenwich",0],UNIT["radian",1],'
                   'AXIS["Longitude",EAST],AXIS["Latitude",NORTH]]')
        with self.assertRaisesRegex(DataError, "degrees"):
            parse_surface(self.png, WORLD, radians)
        nonfinite = WGS84.replace("6378137", "nan")
        with self.assertRaises(DataError):
            parse_surface(self.png, WORLD, nonfinite)

    def test_non_png_wms_exception_and_truncated_payloads_fail(self):
        jpeg = BytesIO()
        Image.fromarray(RGB).save(jpeg, format="JPEG")
        payloads = [b"", b"not an image", b'<ServiceExceptionReport><ServiceException>Bad layer</ServiceException></ServiceExceptionReport>',
                    b"<html>server error</html>", jpeg.getvalue(), b"\x89PNG\r\n\x1a\n",
                    self.png[:40], self.png[:-14], bytearray(self.png)]
        for payload in payloads:
            with self.subTest(payload_type=type(payload), length=len(payload)), self.assertRaises(DataError):
                parse_surface(payload, WORLD, WGS84)

    def test_grayscale_palette_and_16bit_truecolor_are_rejected_without_conversion(self):
        for image in (Image.new("L", (1, 1)), Image.new("P", (1, 1))):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            with self.subTest(mode=image.mode), self.assertRaisesRegex(DataError, "original 8-bit RGB or RGBA"):
                parse_surface(buffer.getvalue(), WORLD, WGS84)

        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))

        # A valid 16-bit RGB PNG which Pillow would otherwise expose as RGB uint8.
        png16 = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 16, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(b"\x00\x12\x34\x56\x78\x9a\xbc"))
                 + chunk(b"IEND", b""))
        with self.assertRaisesRegex(DataError, "original 8-bit RGB or RGBA"):
            parse_surface(png16, WORLD, WGS84)

    def test_animated_png_is_rejected_instead_of_silently_using_first_frame(self):
        buffer = BytesIO()
        first = Image.fromarray(RGB)
        second = Image.fromarray(RGB[::-1])
        first.save(buffer, format="PNG", save_all=True, append_images=[second], duration=100)
        with self.assertRaisesRegex(DataError, "animated"):
            parse_surface(buffer.getvalue(), WORLD, WGS84)


if __name__ == "__main__":
    unittest.main()
