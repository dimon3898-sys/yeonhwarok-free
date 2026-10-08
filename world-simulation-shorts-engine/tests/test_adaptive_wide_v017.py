"""Actual spherical framing tests; no Chromium or GPU render is performed."""
import json
import math
import subprocess
import unittest
from pathlib import Path

from engine.adaptive_wide import adaptive_wide, project_location, AdaptiveFramingError
from engine.gis import resolve_location, great_circle_distance

ROOT = Path(__file__).resolve().parents[1]


class AdaptiveWideV017(unittest.TestCase):
    def pair(self, a, b, **kwargs):
        return adaptive_wide(resolve_location(a), resolve_location(b), **kwargs)

    def check_fit(self, result):
        self.assertTrue(result['current_screen']['visible'])
        self.assertTrue(result['next_screen']['visible'])
        self.assertTrue(result['current_screen']['in_safe_area'])
        self.assertTrue(result['next_screen']['in_safe_area'])
        self.assertTrue(result['framing']['all_samples_in_safe_area'])
        self.assertEqual(result['camera_distance'], 1+result['camera']['height'])

    def test_suez_singapore_is_nearest_continental_framing(self):
        result = self.pair('Suez Canal', 'Singapore')
        self.check_fit(result)
        self.assertEqual(result['wide_type'], 'CONTINENT_WIDE')
        self.assertLess(result['camera']['height'], 2.5)
        self.assertGreater(result['framing']['earth_horizontal_occupancy'], 1)
        self.assertAlmostEqual(result['distance_km'], great_circle_distance(resolve_location('Suez Canal'), resolve_location('Singapore')), places=7)
        closer = {**result['camera'], 'height': result['camera']['height']-1e-5}
        self.assertFalse(project_location(closer, resolve_location('Suez Canal'))['in_safe_area'])

    def test_seoul_tokyo_does_not_zoom_to_world(self):
        result = self.pair('Seoul', 'Tokyo')
        self.check_fit(result)
        self.assertEqual(result['wide_type'], 'REGIONAL_WIDE')
        self.assertLess(result['camera']['height'], .5)
        self.assertGreater(result['framing']['earth_horizontal_occupancy'], 3)

    def test_france_germany_stays_regional(self):
        result = self.pair('France', 'Germany')
        self.check_fit(result)
        self.assertEqual(result['wide_type'], 'REGIONAL_WIDE')
        self.assertLessEqual(result['camera']['height'], .3)

    def test_intercontinental_pair_can_use_world(self):
        result = self.pair('London', 'Sydney')
        self.check_fit(result)
        self.assertEqual(result['wide_type'], 'WORLD_WIDE')
        self.assertLess(result['framing']['earth_horizontal_occupancy'], .74)

    def test_identical_location_has_no_division_by_zero(self):
        result = self.pair('Singapore', 'Singapore')
        self.check_fit(result)
        self.assertEqual(result['framing']['sample_count'], 1)
        self.assertEqual(result['distance_km'], 0)
        self.assertEqual(result['camera']['height'], .2)
        self.assertAlmostEqual(result['current_screen']['x'], .5)
        self.assertAlmostEqual(result['current_screen']['y'], .5)

    def test_dateline_midpoint_does_not_cross_greenwich(self):
        result = adaptive_wide({'lon': 170, 'lat': 30}, {'lon': -170, 'lat': 30})
        self.check_fit(result)
        self.assertAlmostEqual(abs(result['camera']['lon']), 180)
        self.assertGreater(result['camera']['lat'], 30)

    def test_polar_pair_uses_valid_north_up_frame(self):
        result = adaptive_wide({'lon': 0, 'lat': 85}, {'lon': 180, 'lat': 85})
        self.check_fit(result)
        self.assertAlmostEqual(result['camera']['lat'], 90)

    def test_antipodal_locations_are_not_falsely_made_visible(self):
        with self.assertRaises(AdaptiveFramingError):
            adaptive_wide({'lon': 0, 'lat': 0}, {'lon': 180, 'lat': 0})

    def test_portrait_angular_orientation_changes_required_distance(self):
        # Equal great-circle distance, different north-up screen footprint:
        # the portrait viewport is narrower horizontally than vertically.
        a = {'lon': 0, 'lat': 0}
        horizontal = adaptive_wide(a, {'lon': 40, 'lat': 0})
        vertical = adaptive_wide(a, {'lon': 0, 'lat': 40})
        self.assertAlmostEqual(horizontal['distance_km'], vertical['distance_km'])
        self.assertGreater(horizontal['camera_distance'], vertical['camera_distance'])

    def test_stricter_safe_area_increases_distance(self):
        usual = self.pair('Suez Canal', 'Singapore')
        strict = self.pair('Suez Canal', 'Singapore', safe_area={'x_min': .2, 'x_max': .8, 'y_min': .2, 'y_max': .8})
        self.check_fit(strict)
        self.assertGreater(strict['camera_distance'], usual['camera_distance'])

    def test_nonportrait_viewport_is_not_hardcoded(self):
        portrait = self.pair('Suez Canal', 'Singapore')
        landscape = self.pair('Suez Canal', 'Singapore', aspect=16/9)
        self.check_fit(landscape)
        self.assertLess(landscape['camera_distance'], portrait['camera_distance'])

    def test_behind_earth_location_is_not_readable(self):
        camera = {'lon': 0, 'lat': 0, 'height': 2.5, 'fov': 64}
        result = project_location(camera, {'lon': 180, 'lat': 0})
        self.assertFalse(result['visible'])
        self.assertFalse(result['in_safe_area'])

    def test_invalid_inputs_are_rejected(self):
        valid = {'lon': 0, 'lat': 0}
        for point in (None, [], {}, {'lon': math.nan, 'lat': 0}, {'lon': 181, 'lat': 0}, {'lon': 0, 'lat': math.inf}):
            with self.subTest(point=point), self.assertRaises(AdaptiveFramingError):
                adaptive_wide(valid, point)
        for parameters in ({'fov': 0}, {'fov': math.nan}, {'aspect': 0}, {'minimum_height': math.inf}, {'safe_area': {'x_min': .8}}):
            with self.subTest(parameters=parameters), self.assertRaises(AdaptiveFramingError):
                adaptive_wide(valid, valid, **parameters)

    def test_projection_matches_real_three_camera_and_not_a_flat_map(self):
        pairs = [('Suez Canal', 'Singapore'), ('Seoul', 'Tokyo'), ('France', 'Germany'), ('London', 'Sydney')]
        rows = []
        for a, b in pairs:
            framing = self.pair(a, b)
            rows.append({'framing': framing, 'locations': [resolve_location(a)['coordinates'], resolve_location(b)['coordinates']]})
        code = r'''
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const THREE = await import(pathToFileURL(path.resolve('../cinematic-world-map/node_modules/three/build/three.module.js')));
const results = [];
for (const row of JSON.parse(fs.readFileSync(0,'utf8'))) {
  const pose=row.framing.camera, lon=pose.lon*Math.PI/180, lat=pose.lat*Math.PI/180;
  const normal=new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));
  const north=new THREE.Vector3(-Math.sin(lat)*Math.cos(lon),Math.cos(lat),Math.sin(lat)*Math.sin(lon));
  const camera=new THREE.PerspectiveCamera(pose.fov,9/16,.02,30);
  camera.position.copy(normal).multiplyScalar(1+pose.height);camera.up.copy(north);
  camera.lookAt(normal.clone().multiplyScalar(.99));camera.updateProjectionMatrix();camera.updateMatrixWorld();
  results.push(row.locations.map(p=>{
    const lon=p.lon*Math.PI/180,lat=p.lat*Math.PI/180;
    const point=new THREE.Vector3(Math.cos(lat)*Math.cos(lon),Math.sin(lat),-Math.cos(lat)*Math.sin(lon));
    const visible=point.dot(camera.position)>1;
    point.project(camera);
    return {x:(point.x+1)/2,y:(1-point.y)/2,visible};
  }));
}
console.log(JSON.stringify(results));
'''
        result = subprocess.run(['node', '--input-type=module', '-e', code], cwd=ROOT, input=json.dumps(rows), capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout)
        for row, output in zip(rows, outputs):
            for name, projected in zip(('current_screen', 'next_screen'), output):
                expected = row['framing'][name]
                self.assertAlmostEqual(projected['x'], expected['x'], places=12)
                self.assertAlmostEqual(projected['y'], expected['y'], places=12)
                self.assertEqual(projected['visible'], expected['visible'])


if __name__ == '__main__':
    unittest.main()
