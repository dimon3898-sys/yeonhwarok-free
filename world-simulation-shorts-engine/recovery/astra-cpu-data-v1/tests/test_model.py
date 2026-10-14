import unittest
import numpy as np
from astra_cpu.model import RasterData, DataError, split_dateline, validate_bbox


class NeutralRasterTests(unittest.TestCase):
    def raster(self, x0=-61., y0=-30., dy=-.1):
        values = np.arange(24, dtype=np.int16).reshape(4, 6)
        return RasterData(values, x0 + (np.arange(6)+.5)*.1,
                          y0 + (np.arange(4)+.5)*dy,
                          np.ones((4, 6), dtype=bool),
                          {"transform": [x0, .1, 0., y0, 0., dy], "crs": "EPSG:4326"})

    def test_southern_western_crop_preserves_exact_values_and_origin(self):
        raster = self.raster()
        out = raster.crop([-60.9, -30.3, -60.7, -30.1])
        np.testing.assert_array_equal(out.values, raster.values[1:3, 1:3])
        np.testing.assert_array_equal(out.x, raster.x[1:3])
        np.testing.assert_array_equal(out.y, raster.y[1:3])
        np.testing.assert_allclose(out.bbox, [-60.9, -30.3, -60.7, -30.1], atol=1e-12)
        self.assertFalse(out.values.flags.writeable)
        np.testing.assert_array_equal(raster.values, np.arange(24).reshape(4, 6))

    def test_north_up_is_lossless_row_reorder(self):
        raster = self.raster(dy=.1)
        north = raster.north_up()
        np.testing.assert_array_equal(north.values, raster.values[::-1])
        np.testing.assert_array_equal(north.y, raster.y[::-1])
        np.testing.assert_allclose(north.bbox, raster.bbox, atol=1e-12)
        self.assertIs(north.north_up(), north)

    def test_missing_nonfinite_cells_remain_nonfinite(self):
        a = np.array([[np.nan, -2.]], dtype=np.float32)
        raster = RasterData(a, [.5, 1.5], [.5], [[False, True]],
                            {"transform": [0., 1., 0., 0., 0., 1.], "crs": "EPSG:4326"})
        self.assertTrue(np.isnan(raster.values[0, 0]))
        with self.assertRaises(DataError):
            RasterData(a, [.5, 1.5], [.5], [[True, True]], raster.metadata)

    def test_no_center_support_is_explicit(self):
        with self.assertRaisesRegex(DataError, "no supplied sample"):
            self.raster().crop([20, 10, 21, 11])

    def test_dateline_parts_and_world_without_country_branch(self):
        self.assertEqual(split_dateline([175, -12, -176, 7]),
                         [(175., -12., 180., 7.), (-180., -12., -176., 7.)])
        self.assertEqual(split_dateline([-180, -90, 180, 90]),
                         [(-180., -90., 180., 90.)])
        self.assertEqual(split_dateline([180, -1, -170, 1]), [(-180., -1., -170., 1.)])

    def test_invalid_bbox_and_unsupported_grid_are_not_coerced(self):
        for bbox in ([0, 0, 0, 1], [0, 2, 1, 1], [0, 0, 181, 1], [False, 0, 1, 1], [0, 0, 1, float('nan')]):
            with self.assertRaises(DataError):
                validate_bbox(bbox)
        with self.assertRaises(DataError):
            RasterData([[1]], [.5], [.5], [[True]], {"transform": [0, 1, .1, 0, 0, 1]})


if __name__ == "__main__":
    unittest.main()
