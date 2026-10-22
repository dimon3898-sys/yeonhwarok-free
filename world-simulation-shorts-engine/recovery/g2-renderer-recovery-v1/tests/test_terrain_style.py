import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_test_recovery_terrain_style',HERE/'terrain_style.py')
style=importlib.util.module_from_spec(spec);sys.modules[spec.name]=style;spec.loader.exec_module(style)

class NativeWindowTests(unittest.TestCase):
    def setUp(self):
        self.schedule=[{'frame':0,'flatBounds':[93,-3,123,43]},{'frame':1,'flatBounds':[97,3,117,35]}]

    def test_native_window_contains_full_camera_without_changing_values(self):
        before=json.dumps(self.schedule);window=style.native_window(self.schedule)
        self.assertEqual(json.dumps(self.schedule),before)
        self.assertEqual(window.pixel_box,(16372,2812,18188,5588))
        self.assertEqual(window.dimensions,(1816,2776))
        self.assertEqual(window.max_density,(.9,1))
        self.assertLess(window.geographic_bounds[0],93)
        self.assertGreater(window.geographic_bounds[3],43)

    def test_world_file_uses_pixel_centers_and_preserves_half_pixel_alignment(self):
        tfw='0.01666666666667\n0\n0\n-0.01666666666667\n-179.99166666666667\n89.99166666666667'
        result=style.world_file_contract(tfw,'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"]]')
        self.assertEqual(result['pixelEdgeBounds'],[-180,-90,180,90])
        self.assertEqual(result['firstSample'],[-180+1/120,90-1/120])
        with self.assertRaisesRegex(ValueError,'TRANSFORM'):
            style.world_file_contract(tfw.replace('-179.99166666666667','-180'),'GCS_WGS_1984 WGS_1984')

    def test_wrapped_dateline_and_outside_polar_source_fail_explicitly(self):
        for box,code in [([170,-20,-170,20],'DATELINE'),([0,70,30,91],'POLAR'),([-181,0,-150,40],'SOURCE')]:
            with self.assertRaisesRegex(ValueError,code):style.native_window([{'frame':0,'flatBounds':box}])

    def test_source_edge_has_no_invented_clamped_gutter(self):
        with self.assertRaisesRegex(ValueError,'GUTTER_UNAVAILABLE'):
            style.native_window([{'frame':0,'flatBounds':[-180,-10,-150,40]}])
        with self.assertRaisesRegex(ValueError,'GUTTER_UNAVAILABLE'):
            style.native_window([{'frame':0,'flatBounds':[0,58,30,90]}])

    def test_magnified_data_and_oversized_texture_fail_without_lowering_limits(self):
        with self.assertRaisesRegex(ValueError,'PIXEL_BUDGET'):
            style.native_window([{'frame':0,'flatBounds':[97,3,107,19]}])
        with self.assertRaisesRegex(ValueError,'TEXTURE_DIMENSION'):
            style.native_window([{'frame':0,'flatBounds':[-100,-60,100,60]}])

    def test_south_west_and_high_latitude_supported_native_windows(self):
        for box in [[-1,-45,31,1],[-100,-45,-68,1],[0,48,32,80]]:
            window=style.native_window([{'frame':0,'flatBounds':box}]);self.assertTrue(all(v>0 for v in window.dimensions))
            self.assertLessEqual(max(window.max_density),1)

    def test_frame_gaps_nonfinite_and_rotated_world_file_fail(self):
        with self.assertRaisesRegex(ValueError,'FRAME_GAP'):
            style.envelope([{'frame':2,'flatBounds':[0,0,20,32]}])
        with self.assertRaisesRegex(ValueError,'FINITE'):
            style.bounds([0,float('nan'),20,32])
        with self.assertRaisesRegex(ValueError,'ROTATED'):
            style.world_file_contract('0.01666666666667 0.1 0 -0.01666666666667 -179.99166666666667 89.99166666666667','WGS_1984 GCS_WGS_1984')

class ReceiptTests(unittest.TestCase):
    def test_actual_receipt_validates_and_corrupt_asset_or_claims_fail(self):
        receipt_path=HERE/'fixtures/RECOVERY_STYLE_RECEIPT.json'
        if not receipt_path.is_file():self.skipTest('Real source crop not yet prepared; not counted as real-data PASS')
        receipt=json.loads(receipt_path.read_bytes())
        with __import__('zipfile').ZipFile(HERE.parent/'universal-source-pipeline-v2/fixtures/SOURCE_BUNDLE.zip') as archive:
            schedule=json.loads(archive.read('demo/NATIVE.json'))['cameraSchedule']
        result=style.validate_style(receipt,schedule);self.assertTrue(result['ready']);self.assertTrue(result['coverageFull'])
        for field,value in [('CRS','EPSG:3857'),('pixelSpacing',[.001,.001]),('NoData',0)]:
            bad=json.loads(json.dumps(receipt));bad['terrainAsset'][field]=value
            with self.assertRaisesRegex(ValueError,'REGISTRATION_OR_SOURCE'):style.validate_style(bad,schedule)
        bad=json.loads(json.dumps(receipt));bad['terrainAsset']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'BYTES_OR_SHA'):style.validate_style(bad,schedule)

if __name__=='__main__':unittest.main()
