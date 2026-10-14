from dataclasses import replace
from pathlib import Path
import tempfile
import json
import subprocess
from types import SimpleNamespace
from copy import deepcopy
import unittest
from unittest.mock import patch

import numpy as np
from astra_cpu.cache import FileCache
from astra_cpu.model import sha256, RasterData
from astra_cpu.pipeline import CpuDataPipeline, source_metadata_sha256
from astra_cpu.providers import ArchiveCatalog, DataRequest, SourceSpec, TerrainSource
from astra_cpu.scene import prepare_scene

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent/'astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip'
ROI = (128.35,37.35,128.36,37.36)  # Only a real-data test fixture, never engine policy.


class PipelineRealDataTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ArchiveCatalog(ARCHIVE, license_verified=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = FileCache(self.temp.name)
        self.pipeline = CpuDataPipeline(self.catalog, self.cache)
        self.request = DataRequest(ROI, target_ground_resolution=100)

    def test_all_three_cached_results_reuse_without_original_reads_or_parsing(self):
        for source_id in self.catalog.sources:
            with self.subTest(source=source_id):
                first = self.pipeline.provide(source_id, self.request)
                self.assertEqual(first.status, 'available', first.error)
                with patch.object(self.catalog, 'read_bytes', side_effect=AssertionError('cache must avoid original read')):
                    second = CpuDataPipeline(self.catalog, self.cache).provide(source_id, self.request)
                self.assertEqual(first.to_dict(), second.to_dict())
                for before, after in zip(first.rasters, second.rasters):
                    self.assertEqual(before.values.dtype, after.values.dtype)
                    np.testing.assert_array_equal(before.values, after.values)
                    self.assertEqual(before.metadata, after.metadata)
        self.assertEqual(len(list((Path(self.temp.name)/'blobs/raw').glob('*.bin'))),5)

    def test_corrupt_derived_cache_is_invalid_and_not_silently_replaced(self):
        source_id = next(iter(self.catalog.sources))
        self.pipeline.provide(source_id,self.request)
        blob=next((Path(self.temp.name)/'blobs/derived').glob('*.bin'))
        blob.write_bytes(b'corrupt')
        result=self.pipeline.provide(source_id,self.request)
        self.assertEqual(result.status,'invalid_data')
        self.assertEqual(blob.read_bytes(),b'corrupt')

    def test_license_and_version_do_not_become_available_from_cached_rasters(self):
        source_id=next(iter(self.catalog.sources))
        self.pipeline.provide(source_id,self.request)
        self.assertEqual(self.pipeline.provide(source_id,self.request,source_version='other').status,'version_changed')
        self.catalog.sources[source_id]=replace(self.catalog.sources[source_id],license_verified=False)
        self.assertEqual(self.pipeline.provide(source_id,self.request).status,'license_unverified')

    def test_source_metadata_sidecars_datum_and_version_change_cache_identity(self):
        spec=next(iter(self.catalog.sources.values()))
        for changed in (replace(spec,vertical_datum='different datum'),
                        replace(spec,source_version='other version'),
                        replace(spec,metadata={**spec.metadata,'accuracy':'changed'}),
                        replace(spec,sidecars=({'relative_path':'auxiliary.prj','sha256':'0'*64},))):
            self.assertNotEqual(source_metadata_sha256(spec),source_metadata_sha256(changed))

    def test_read_only_miss_and_bypass_do_not_publish_cache_entries(self):
        source_id=next(iter(self.catalog.sources))
        for mode in ('read_only','bypass'):
            result=CpuDataPipeline(self.catalog,self.cache,mode=mode).provide(source_id,self.request)
            self.assertEqual(result.status,'available')
            self.assertEqual(list((Path(self.temp.name)/'lookups/raw').glob('*.json')),[])
            self.assertEqual(list((Path(self.temp.name)/'lookups/derived').glob('*.json')),[])

    def test_unsupported_region_does_not_publish_successful_derived_cache(self):
        source_id=next(iter(self.catalog.sources))
        result=self.pipeline.provide(source_id,DataRequest((-65,-40,-64,-39)))
        self.assertEqual(result.status,'unavailable')
        self.assertEqual(list((Path(self.temp.name)/'lookups/derived').glob('*.json')),[])

    def test_scene_preparation_executes_only_explicit_roles_and_respects_read_only(self):
        scene=json.loads((ROOT/'fixtures/LOCAL_DATA_SCENE.json').read_bytes())
        before=deepcopy(scene)
        scene['mapData']['cache']['mode']='read_only'
        prepared=prepare_scene(scene,self.catalog)
        result=self.pipeline.prepare(prepared)
        self.assertEqual(set(result.results),{'terrain','bathymetry','surfaceTexture'})
        self.assertTrue(all(r.status=='available' for r in result.results.values()))
        self.assertFalse(result.gpu_activation)
        self.assertFalse(result.to_dict()['networkRequestsExecuted'])
        self.assertEqual(list((Path(self.temp.name)/'lookups/raw').glob('*.json')),[])
        self.assertEqual(scene['purpose'],before['purpose'])

    def test_disabled_scene_performs_no_catalog_cache_or_source_lookup(self):
        preparation=prepare_scene({'schema':'opaque legacy','camera':[1,2,3]})
        pipeline=CpuDataPipeline(None)
        result=pipeline.prepare(preparation)
        self.assertFalse(result.enabled)
        self.assertFalse(result.gpu_activation)
        self.assertEqual(result.results,{})

    def test_oversized_cache_policy_and_changed_binding_are_rejected(self):
        scene=json.loads((ROOT/'fixtures/LOCAL_DATA_SCENE.json').read_bytes())
        scene['mapData']['cache']['maxBytes']=1
        with self.assertRaises(ValueError):self.pipeline.prepare(prepare_scene(scene,self.catalog))
        scene['mapData']['cache'].pop('maxBytes')
        prepared=prepare_scene(scene,self.catalog)
        key=next(iter(self.catalog.sources))
        self.catalog.sources[key]=replace(self.catalog.sources[key],source_version='changed')
        with self.assertRaises(ValueError):self.pipeline.prepare(prepared)

    def test_cli_artifacts_are_deterministic_in_a_fresh_process_and_all_hashes_match(self):
        output=Path(self.temp.name)/'export'
        command=['/usr/bin/python3','-B',str(ROOT/'prepare_data.py'),'--scene',str(ROOT/'fixtures/LOCAL_DATA_SCENE.json'),
                 '--archive',str(ARCHIVE),'--cache-dir',str(Path(self.temp.name)/'cli-cache'),
                 '--output',str(output),'--accept-recorded-license-evidence']
        first=subprocess.run(command,check=True,capture_output=True,timeout=20)
        manifest_before=(output/'CPU_PREPARATION_MANIFEST.json').read_bytes()
        second=subprocess.run(command,check=True,capture_output=True,timeout=20)
        self.assertEqual(first.stdout,second.stdout)
        self.assertEqual(manifest_before,(output/'CPU_PREPARATION_MANIFEST.json').read_bytes())
        manifest=json.loads(manifest_before)
        self.assertEqual(len(manifest['artifacts']),3)
        for item in manifest['artifacts']:
            self.assertEqual(sha256((output/item['file']).read_bytes()),item['sha256'])
        self.assertFalse(manifest['gpuActivation'])

    def test_disabled_cli_does_not_open_missing_archive_or_create_cache(self):
        scene=Path(self.temp.name)/'disabled.json'
        scene.write_text(json.dumps({'schema':'unchanged legacy','mapData':{'enabled':False}}))
        cache=Path(self.temp.name)/'not-created'
        output=Path(self.temp.name)/'disabled-export'
        completed=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'prepare_data.py'),'--scene',str(scene),
                                  '--archive',str(Path(self.temp.name)/'missing.zip'),'--cache-dir',str(cache),
                                  '--output',str(output)],check=True,capture_output=True,timeout=10)
        self.assertFalse(cache.exists())
        self.assertFalse(json.loads(completed.stdout)['enabled'])

    def test_cli_unverified_license_is_explicit_and_emits_no_rasters(self):
        output=Path(self.temp.name)/'unverified'
        command=['/usr/bin/python3','-B',str(ROOT/'prepare_data.py'),'--scene',str(ROOT/'fixtures/LOCAL_DATA_SCENE.json'),
                 '--archive',str(ARCHIVE),'--output',str(output)]
        result=subprocess.run(command,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2)
        self.assertEqual(set(json.loads(result.stdout)['statusByRole'].values()),{'license_unverified'})
        self.assertEqual(list(output.glob('*.npz')),[])


class PipelineSyntheticDatelineTests(unittest.TestCase):
    def test_aggregate_request_context_does_not_alias_identical_dateline_parts(self):
        spec=SourceSpec('synthetic-global','v1','https://example.invalid/global',
                        'land_elevation','global',sha256(b'global fixture'),None,None,
                        'Synthetic only',True)
        class GlobalTerrain(TerrainSource):
            def parse(self,raw):
                return RasterData(np.arange(720,dtype=np.float32).reshape(2,360),
                                  np.arange(-179.5,180,1),[-.5,.5],np.ones((2,360),dtype=bool),
                                  {'transform':[-180,1,0,-1,0,1],'crs':'EPSG:4326',
                                   'inputSha256':sha256(raw),'verticalDatum':None,'nodata':None})
        catalog=SimpleNamespace(sources={spec.source_id:spec},read_bytes=lambda _:b'global fixture')
        crossing=DataRequest((175,0,-175,1))
        east=DataRequest((175,0,180,1));west=DataRequest((-180,0,-175,1))
        with tempfile.TemporaryDirectory() as folder, patch.dict('astra_cpu.pipeline._CLASSES',land_elevation=GlobalTerrain):
            pipeline=CpuDataPipeline(catalog,FileCache(folder))
            for request in (crossing,east,west,crossing):
                result=pipeline.provide(spec.source_id,request)
                self.assertEqual(result.status,'available',result.error)
                self.assertEqual(result.coverage['requestedBBox'],list(request.bbox))
                self.assertEqual(result.coverage['validSampleCount'],sum(int(r.valid.sum()) for r in result.rasters))
                self.assertEqual(len(result.coverage['actualBBoxes']),len(result.rasters))
        with tempfile.TemporaryDirectory() as folder, patch.dict('astra_cpu.pipeline._CLASSES',land_elevation=GlobalTerrain):
            pipeline=CpuDataPipeline(catalog,FileCache(folder))
            for request in (east,west,crossing,crossing):
                result=pipeline.provide(spec.source_id,request)
                self.assertEqual(result.status,'available',result.error)
                self.assertEqual(result.coverage['requestedBBox'],list(request.bbox))


if __name__=='__main__': unittest.main()
