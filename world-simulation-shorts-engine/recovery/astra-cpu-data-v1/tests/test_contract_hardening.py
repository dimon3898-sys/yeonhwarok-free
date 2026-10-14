from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
import zipfile
import numpy as np
from PIL import Image
from astra_cpu.model import RasterData, DataError, validate_bbox
from astra_cpu.providers import ArchiveCatalog, DataRequest, SourceSpec
from astra_cpu.download_contract import DownloadRequest
from astra_cpu.surface import parse_surface
from astra_cpu.terrain import parse_terrain

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT.parent/'astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip'


class ContractHardeningTests(unittest.TestCase):
    def test_support_mask_strings_numbers_and_nan_are_not_boolean_coerced(self):
        for support in ([['false']], [[np.nan]], [[1]]):
            with self.assertRaisesRegex(DataError,'booleans'):
                RasterData([[3]], [.5], [.5], support, {'transform':[0,1,0,0,0,1]})

    def test_source_license_and_credential_url_validation(self):
        args=dict(source_id='synthetic',source_version='v1',source_url='https://example.invalid/data',
                  data_class='land_elevation',relative_path='data',sha256='0'*64,
                  native_resolution=None,vertical_datum=None,attribution='synthetic')
        with self.assertRaises(DataError): SourceSpec(**args,license_verified='false')
        with self.assertRaisesRegex(DataError,'credentials'):
            SourceSpec(**{**args,'source_url':'https://placeholder:placeholder@example.invalid/data'})

    def test_manifest_duplicates_and_missing_source_member(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            manifest=archive.read('DATA_MANIFEST.json');attribution=archive.read('licenses/ATTRIBUTION.txt')
        with tempfile.TemporaryDirectory() as folder:
            missing=Path(folder)/'missing.zip'
            with zipfile.ZipFile(missing,'w') as archive:
                archive.writestr('DATA_MANIFEST.json',manifest)
                archive.writestr('licenses/ATTRIBUTION.txt',attribution)
            catalog=ArchiveCatalog(missing,license_verified=True)
            spec=next(x for x in catalog.sources.values() if x.data_class=='land_elevation')
            result=catalog.provider(spec.source_id).provide(DataRequest(tuple(spec.metadata['sample_extent'])))
            self.assertEqual(result.status,'unavailable')
            with zipfile.ZipFile(missing,'a') as archive, warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                archive.writestr('DATA_MANIFEST.json',manifest)
            with self.assertRaisesRegex(DataError,'duplicate'):
                ArchiveCatalog(missing)

    def test_real_grid_roundoff_not_reported_as_missing_and_parsed_datum_retained(self):
        catalog=ArchiveCatalog(ARCHIVE,license_verified=True)
        spec=next(x for x in catalog.sources.values() if x.data_class=='ocean_bathymetry')
        provider=catalog.provider(spec.source_id)
        provider.spec=replace(spec,vertical_datum=None)
        result=provider.provide(DataRequest(tuple(spec.metadata['sample_extent'])))
        self.assertEqual(result.status,'available')
        self.assertTrue(result.coverage['complete'])
        self.assertEqual(result.vertical_datum,'EPSG:5831')

    def test_overflow_and_malformed_download_numeric_metadata_are_explicit(self):
        with self.assertRaises(DataError): validate_bbox([10**400,0,1,1])
        with self.assertRaises(DataError): DataRequest((0,0,1,1),target_ground_resolution=10**400).validate()
        base=dict(url='https://example.invalid/data',source_id='synthetic',source_version='v1',max_bytes=1024)
        for extra in ({'byte_range':(0,2),'total_object_bytes':'3'}, {'resolution':float('nan')},
                      {'resolution':10**400},{'source_version':123},{'expected_etag':'invalid\nheader'}):
            with self.assertRaises(DataError): DownloadRequest(**{**base,**extra}).validate()

    def test_decoder_caps_before_large_raster_or_png_allocation(self):
        fake=SimpleNamespace(RasterCount=1,RasterXSize=5000,RasterYSize=5000)
        with patch('astra_cpu.terrain.gdal.OpenEx',return_value=fake):
            with self.assertRaisesRegex(DataError,'bounded CPU raster'):
                parse_terrain(b'nonempty TIFF input')
        image=Image.new('RGB',(1,1));stream=BytesIO();image.save(stream,format='PNG')
        header=bytearray(stream.getvalue());header[16:20]=(5000).to_bytes(4,'big');header[20:24]=(5000).to_bytes(4,'big')
        with patch('astra_cpu.surface.Image.open',side_effect=AssertionError('allocation forbidden')):
            # Projection is parsed before pixels; use real supplied sidecar.
            with zipfile.ZipFile(ARCHIVE) as archive:
                projection=archive.read('samples/BlueMarble_NextGeneration_Korea.prj')
            with self.assertRaisesRegex(DataError,'bounded CPU raster'):
                parse_surface(bytes(header),'1\n0\n0\n-1\n0.5\n0.5',projection)


if __name__=='__main__': unittest.main()
