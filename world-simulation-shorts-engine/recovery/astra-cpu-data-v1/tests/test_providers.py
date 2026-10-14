from dataclasses import replace
from io import BytesIO
from unittest.mock import patch
import zipfile
import unittest
from pathlib import Path
import numpy as np
from astra_cpu.providers import ArchiveCatalog, DataRequest, TerrainSource, SourceSpec, RasterProvider
from astra_cpu.model import RasterData
from astra_cpu.neutral import encode_neutral, decode_neutral

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent/'astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip'


class ProviderRealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = ArchiveCatalog(ARCHIVE, license_verified=True)

    def test_all_three_real_providers_have_required_contract_and_lossless_export(self):
        required = {'status','sourceId','sourceVersion','sourceURL','bbox','CRS',
                    'nativeResolution','outputResolution','verticalDatum','nodata','attribution','SHA-256','error'}
        for spec in self.catalog.sources.values():
            with self.subTest(source=spec.source_id):
                bbox = tuple(spec.metadata['sample_extent'])
                result = self.catalog.provider(spec.source_id).provide(DataRequest(bbox), source_version=spec.source_version)
                self.assertEqual(result.status, 'available', result.error)
                self.assertTrue(required <= result.to_dict().keys())
                self.assertFalse(result.to_dict()['gpuUploadExecuted'])
                for raster in result.rasters:
                    decoded = decode_neutral(encode_neutral(raster))
                    self.assertEqual(decoded.values.dtype, raster.values.dtype)
                    np.testing.assert_array_equal(decoded.values, raster.values)
                    np.testing.assert_array_equal(decoded.x, raster.x)
                    np.testing.assert_array_equal(decoded.y, raster.y)
                    np.testing.assert_array_equal(decoded.valid, raster.valid)
                    self.assertEqual(decoded.metadata['inputSha256'], spec.sha256)
                if spec.data_class == 'ocean_bathymetry':
                    self.assertTrue(any('OCEAN_MASK_REQUIRED' in w for w in result.warnings))

    def test_partial_coverage_keeps_actual_edges_and_explicit_warning(self):
        spec = next(x for x in self.catalog.sources.values() if x.data_class == 'land_elevation')
        bbox = list(spec.metadata['sample_extent']); bbox[0] -= .1
        result = self.catalog.provider(spec.source_id).provide(DataRequest(tuple(bbox), target_ground_resolution=1))
        self.assertEqual(result.status, 'available')
        self.assertFalse(result.coverage['complete'])
        self.assertFalse(result.coverage['paddingApplied'])
        self.assertLess(result.rasters[0].values.shape[1], 1801)
        self.assertIn('PARTIAL_SOURCE_COVERAGE_NO_PADDING_OR_EXTRAPOLATION', result.warnings)
        self.assertNotEqual(result.bbox, bbox)

    def test_license_version_missing_source_and_auth_states_before_or_during_parse(self):
        spec = next(x for x in self.catalog.sources.values() if x.data_class == 'land_elevation')
        request = DataRequest(tuple(spec.metadata['sample_extent']))
        self.assertEqual(TerrainSource(replace(spec, license_verified=False), self.catalog.read_bytes).provide(request).status, 'license_unverified')
        self.assertEqual(self.catalog.provider(spec.source_id).provide(request, source_version='different-release').status, 'version_changed')
        def missing(_): raise FileNotFoundError()
        def auth(_): raise PermissionError()
        self.assertEqual(TerrainSource(spec, missing).provide(request).status, 'unavailable')
        self.assertEqual(TerrainSource(spec, auth).provide(request).status, 'auth_required')
        self.assertEqual(TerrainSource(spec, lambda _: b'invalid input').provide(request).status, 'invalid_data')

    def test_unsupported_bbox_crs_resolution_region_and_catalog_path(self):
        spec = next(x for x in self.catalog.sources.values() if x.data_class == 'land_elevation')
        provider = self.catalog.provider(spec.source_id)
        for request in (DataRequest((0,0,1,1), 'EPSG:3857'), DataRequest((0,0,1,1), target_ground_resolution=0),
                        DataRequest((0,0,1,1), target_ground_resolution=True), DataRequest((0,0,1,100))):
            self.assertEqual(provider.provide(request).status, 'invalid_data')
        self.assertEqual(provider.provide(DataRequest((-65,-40,-64,-39))).status, 'unavailable')
        self.assertEqual(provider.provide(DataRequest((175,-1,-176,1))).status, 'unavailable')
        with self.assertRaises(ValueError): self.catalog.read_bytes('../escape')


class NeutralSyntheticTests(unittest.TestCase):
    def raster(self):
        return RasterData(np.array([[np.nan, -1]], dtype=np.float32), [.5,1.5], [.5], [[False,True]],
                          {'transform':[0.,1.,0.,0.,0.,1.], 'crs':'EPSG:4326',
                           'nodata':float('nan'), 'colorProfile': b'original binary profile'})

    def test_nonfinite_nodata_and_binary_metadata_roundtrip_without_pickle(self):
        before=self.raster();after=decode_neutral(encode_neutral(before))
        np.testing.assert_array_equal(before.values.view(np.uint32), after.values.view(np.uint32))
        self.assertTrue(np.isnan(after.metadata['nodata']))
        self.assertEqual(after.metadata['colorProfile'], b'original binary profile')

    def test_corruption_hash_and_size_limit_are_rejected(self):
        payload=encode_neutral(self.raster())
        for body,kwargs in ((b'broken',{}),(payload,{'expected_sha256':'0'*64}),
                            (payload,{'max_expanded_bytes':1})):
            with self.assertRaises(ValueError): decode_neutral(body,**kwargs)

    def test_forged_npy_shape_rejected_before_numpy_load(self):
        payload=encode_neutral(self.raster())
        bad=BytesIO()
        header=BytesIO()
        np.lib.format.write_array_header_1_0(header, {'descr':'<f8', 'fortran_order':False, 'shape':(100000000,)})
        with zipfile.ZipFile(BytesIO(payload)) as original, zipfile.ZipFile(bad,'w') as target:
            for name in original.namelist():
                target.writestr(name, header.getvalue() if name=='values.npy' else original.read(name))
        with patch('astra_cpu.neutral.np.load', side_effect=AssertionError('must reject before allocating')) as load:
            with self.assertRaisesRegex(ValueError, 'declared shape'):
                decode_neutral(bad.getvalue(), max_expanded_bytes=4096)
            load.assert_not_called()

    def test_literal_metadata_marker_dictionaries_are_not_reinterpreted(self):
        original=self.raster()
        metadata=dict(original.metadata)
        metadata['literalMarker']={'__numeric_metadata__':'NaN'}
        metadata['nestedMarker']={'__literal_dictionary__':{'__binary_metadata__':'not binary'}}
        raster=RasterData(original.values,original.x,original.y,original.valid,metadata)
        decoded=decode_neutral(encode_neutral(raster))
        self.assertEqual(decoded.metadata['literalMarker'],metadata['literalMarker'])
        self.assertEqual(decoded.metadata['nestedMarker'],metadata['nestedMarker'])

    def test_all_invalid_support_not_published_as_available(self):
        spec=SourceSpec('synthetic','v1','https://example.invalid/file','land_elevation','file','0'*64,
                        None,None,'synthetic fixture',True)
        class Stub(RasterProvider):
            data_class='land_elevation'
            def parse(self,_):
                return RasterData([[np.nan]], [.5], [.5], [[False]], {'transform':[0,1,0,0,0,1],'crs':'EPSG:4326'})
        result=Stub(spec,lambda _:b'fixture').provide(DataRequest((0,0,1,1)))
        self.assertEqual(result.status,'unavailable')
        self.assertEqual(result.error['code'],'NO_VALID_SAMPLE_SUPPORT')

    def test_no_silent_crs_reprojection(self):
        spec=SourceSpec('synthetic','v1','https://example.invalid/file','land_elevation','file','0'*64,
                        None,None,'synthetic fixture',True)
        class Stub(RasterProvider):
            data_class='land_elevation'
            def parse(self,_):
                return RasterData([[1.]], [.5], [.5], [[True]], {'transform':[0,1,0,0,0,1],'crs':'EPSG:4269'})
        self.assertEqual(Stub(spec,lambda _:b'fixture').provide(DataRequest((0,0,1,1))).status,'invalid_data')


if __name__ == '__main__': unittest.main()
