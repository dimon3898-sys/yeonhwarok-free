"""Source/input regressions for the five actual regional draw cases.

These CPU checks do not claim any browser, NVIDIA or visual-quality success.
The parent's separately gated draw phase must exercise every prepared region.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

from PIL import Image

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
OLD = HERE.parent / 'g2-renderer-recovery-v1'
spec = importlib.util.spec_from_file_location('_final_generic_test_builder', HERE / 'tools/build_generic_regions.py')
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


class GenericRegions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((HERE / 'fixtures/GENERIC_REGIONS.json').read_bytes())
        cls.report = json.loads((HERE / 'reports/GENERIC_REGIONS_PREPARATION.json').read_bytes())
        cls.archive = HERE / 'fixtures/GENERIC_REGION_INPUTS.zip'
        with zipfile.ZipFile(cls.archive) as z:
            cls.runtime_raw = {c['id']: z.read(c['id'] + '/RECOVERY_RUNTIME.json') for c in cls.report['cases']}
            cls.domains = {c['id']: json.loads(z.read(c['id'] + '/DOMAIN.geojson')) for c in cls.report['cases']}
        cls.runtimes = {k: json.loads(v) for k, v in cls.runtime_raw.items()}

    def test_five_distinct_source_regions_not_historical(self):
        self.assertEqual(len(self.config['cases']), 5)
        self.assertEqual(set(self.runtimes), {'namibia_desert_coast', 'nepal_himalaya', 'korean_peninsula', 'europe_germany', 'south_america_chile'})
        self.assertEqual(len({r['nativePlan']['primary'] for r in self.runtimes.values()}), 5)
        self.assertFalse(self.report['rendererExecuted'])
        self.assertFalse(self.report['historicalClaims'])
        for runtime in self.runtimes.values():
            self.assertTrue(all(f['mode'] == 'SYNTHETIC_TEST' for f in runtime['frames']))

    def test_archive_integrity_and_safe_relative_names(self):
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(), self.report['persistence']['sha256'])
        with zipfile.ZipFile(self.archive) as z:
            self.assertIsNone(z.testzip())
            for row in self.report['persistence']['files']:
                self.assertFalse(Path(row['path']).is_absolute())
                self.assertNotIn('..', Path(row['path']).parts)
                self.assertEqual(hashlib.sha256(z.read(row['path'])).hexdigest(), row['sha256'])
                self.assertEqual(len(z.read(row['path'])), row['bytes'])

    def test_failed_and_passed_prior_inputs_are_byte_exact(self):
        with zipfile.ZipFile(OLD / 'fixtures/GENERIC_PROBE_INPUTS.zip') as z:
            for case in ['namibia_desert_coast', 'nepal_himalaya']:
                self.assertEqual(self.runtime_raw[case], z.read(case + '/RECOVERY_RUNTIME.json'))
                row = next(c for c in self.report['cases'] if c['id'] == case)
                self.assertTrue(row['originalRuntime']['copiedRuntimeBytesExact'])

    def test_all_source_partition_geometry_is_exact(self):
        for case, runtime in self.runtimes.items():
            actual = builder.verify_partition(runtime, self.domains[case])
            self.assertEqual(len(actual), 3)
            for row in actual:
                self.assertEqual(row['outsideAreaDegreesSquared'], 0)
                self.assertEqual(row['unassignedAreaDegreesSquared'], 0)
                self.assertEqual(row['overlapAreaDegreesSquared'], 0)

    def test_actual_native_pngs_sha_crs_and_viewport_support(self):
        for runtime in self.runtimes.values():
            receipt = runtime['sourceStyle']
            asset = receipt['terrainAsset']
            module = builder.style
            module.ASSET_PREFIX = asset['path'].rsplit('/', 1)[0] + '/'
            checked = module.validate_style(receipt, runtime['cameraSchedule'])
            self.assertTrue(checked['coverageFull'])
            self.assertLessEqual(max(checked['maxProjectedPixelsPerNativeTexel']), 1)
            self.assertEqual(asset['classification'], 'BAKED HILLSHADE')
            self.assertEqual(receipt['sourceOriginal']['license'], 'Public Domain')
            self.assertIsNone(asset['NoData'])
            self.assertEqual(asset['CRS'], 'EPSG:4326')
            with Image.open(REPO / asset['path']) as image:
                self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(), receipt['decodedNativeCropRGBSHA256'])

    def test_anchors_glyphs_and_location_role_not_removed(self):
        for case, runtime in self.runtimes.items():
            self.assertEqual(runtime['eventLocation'], runtime['nativePlan']['anchor']['coordinates'])
            self.assertEqual(runtime['nativePlan']['text']['locationLabel'], 'ZONE')
            self.assertTrue(runtime['nativePlan']['scale']['information']['location'])
            self.assertEqual(runtime['nativePlan']['layout']['measured']['location']['fontSize'], 36)
            self.assertEqual(runtime['nativePlan']['layout']['measured']['location']['gap'], 18)
            # Adapter selection is a separate explicit phase; source fixtures are unchanged.
            self.assertNotIn('locationPlacement', runtime['nativePlan']['layout'])

    def test_all_camera_schedules_are_actual_unchanged_v5(self):
        bridge = r'''
import {evaluateMinimumContextCameraFrame} from './world-simulation-shorts-engine/web/map_infographic_v1/camera_director_v5.mjs';
import {cameraBoundsNumericallyAgree} from './world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/camera_numeric_contract.mjs';
import {readFileSync} from 'node:fs';
const inputs=JSON.parse(readFileSync(0,'utf8')),results=[];
for(const [id,runtime]of Object.entries(inputs)){
 for(const row of runtime.cameraSchedule){
  const actual=evaluateMinimumContextCameraFrame(runtime.cameraPlan,row.sourceFrame);
  if(actual.admission.localUsed||!cameraBoundsNumericallyAgree(actual.camera.flatBounds,row.flatBounds).matches)throw Error('SOURCE_CAMERA_NOT_ACTUAL_V5');
 }
 results.push({id,frames:runtime.cameraSchedule.map(r=>r.sourceFrame)});
}
process.stdout.write(JSON.stringify(results));
'''
        result = subprocess.run(['node', '--input-type=module', '-e', bridge], cwd=REPO,
            input=builder.canonical(self.runtimes), capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        rows = json.loads(result.stdout)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r['frames'] == [0, 54, 0] for r in rows))

    def test_marker_projection_is_safe_and_camera_actually_changes(self):
        for runtime in self.runtimes.values():
            positions = []
            safe = runtime['nativePlan']['layout']['safe']
            marker = runtime['nativePlan']['layout']['measured']['markerSize']
            lon, lat = runtime['eventLocation']
            for row in runtime['cameraSchedule']:
                west, south, east, north = row['flatBounds']
                x, y = (lon - west) / (east - west) * 1080, (north - lat) / (north - south) * 1920
                positions.append([x, y])
                self.assertGreaterEqual(x - marker/2, safe[0])
                self.assertGreaterEqual(y - marker/2, safe[1])
                self.assertLessEqual(x + marker/2, safe[2])
                self.assertLessEqual(y + marker/2, safe[3])
            self.assertEqual(positions[0], positions[2])
            self.assertNotEqual(runtime['cameraSchedule'][0]['flatBounds'], runtime['cameraSchedule'][1]['flatBounds'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
