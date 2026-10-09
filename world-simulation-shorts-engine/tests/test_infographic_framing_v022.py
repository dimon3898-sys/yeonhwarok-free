"""Actual native geometry fit and existing texture selection, without GPU claims."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from engine import infographic_framing as framing
from engine import adaptive_wide as rig
from engine import visual_quality
from engine.infographic_contract import load_registry,canonical_sha


class InfographicFramingV022(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=load_registry();cls.records={r['id']:r for r in cls.registry['geometries']}
        cls.frozen_manifest=visual_quality.MANIFEST.read_bytes()
        cls.frozen_assets={r['file']:r['sha256']for r in visual_quality.asset_records()}

    def test_off_is_exact_independent_baseline_camera_and_does_not_read_assets(self):
        baseline=dict(lon=32.383,lat=30.317,height=.3,fov=40,tilt=.6,yaw=-.15,bank=.015)
        with patch('engine.visual_quality.asset_records',side_effect=AssertionError('OFF must not load LOD')):
            result=framing.fit_native_geometry([],enabled=False,baseline_camera=baseline)
        self.assertEqual(result['camera'],baseline);self.assertIsNot(result['camera'],baseline)
        self.assertTrue(result['unchanged']);self.assertFalse(result['enabled'])

    def test_local_close_rejects_actual_point_instead_of_inventing_circle(self):
        point=self.records['LOCATION_SUEZ_CANAL']
        with self.assertRaisesRegex(ValueError,'REQUIRES_NATIVE_EXTENT'):
            framing.fit_native_geometry([point],registry=self.registry)
        self.assertEqual(point['geometry_type'],'Point')

    def test_canal_full_native_line_extent_fits_in_safe_area(self):
        records=[self.records['CANAL_SUEZ_RIVER_NE10M'],self.records['CANAL_SUEZ_LAKE_NE10M']]
        result=framing.fit_native_geometry(records,registry=self.registry)
        self.assertTrue(result['all_samples_in_safe_area']);self.assertGreater(result['projected_sample_count'],5)
        self.assertFalse(result['point_promoted_to_polygon']);self.assertEqual(result['physical_gpu'],'NOT_RUN')
        area=result['safe_area'];box=result['screen_bounds']
        for key in ('x_min','y_min'):self.assertGreaterEqual(box[key],area[key]-1e-8)
        for key in ('x_max','y_max'):self.assertLessEqual(box[key],area[key]+1e-8)
        self.assertEqual(result['native_geometry_sha256s'],{r['id']:r['sha256']for r in records})

    def test_country_multipart_and_holes_are_preserved_not_bounding_box_polygon(self):
        original=deepcopy(self.records['COUNTRY_KOR'])
        result=framing.fit_native_geometry([original],registry=self.registry)
        self.assertTrue(result['native_parts_preserved']);self.assertTrue(result['holes_preserved'])
        self.assertEqual(original,self.records['COUNTRY_KOR'])
        self.assertGreater(result['projected_sample_count'],len(original['coordinates']))
        self.assertEqual(result['source_precision'][0]['source_scale']['denominator'],50000000)

    def test_dateline_native_country_does_not_use_arithmetic_longitude_bbox(self):
        result=framing.fit_native_geometry([self.records['COUNTRY_FJI']],registry=self.registry)
        self.assertGreater(abs(result['camera']['lon']),150)
        self.assertTrue(result['all_samples_in_safe_area'])
        self.assertNotEqual(result['camera']['lon'],0)

    def test_title_and_subtitle_reservations_tighten_actual_projected_extent(self):
        record=self.records['COUNTRY_KOR']
        broad=framing.fit_native_geometry([record],registry=self.registry,title_bottom=.12,subtitle_top=.82)
        reserved=framing.fit_native_geometry([record],registry=self.registry,title_bottom=.3,subtitle_top=.7)
        self.assertGreaterEqual(reserved['camera']['height'],broad['camera']['height'])
        self.assertGreaterEqual(reserved['screen_bounds']['y_min'],.3-1e-8)
        self.assertLessEqual(reserved['screen_bounds']['y_max'],.7+1e-8)

    def test_solver_reuses_existing_adaptive_camera_and_exact_projector(self):
        with patch.object(rig,'adaptive_wide',wraps=rig.adaptive_wide)as solver,patch.object(rig,'project_location',wraps=rig.project_location)as projector:
            result=framing.fit_native_geometry([self.records['COUNTRY_SGP']],registry=self.registry)
        solver.assert_called_once();self.assertGreater(projector.call_count,5)
        self.assertEqual(result['method'],'INHERITED_SPHERICAL_SOLVER_COMPLETE_NATIVE_EXTENT')
        self.assertEqual(result['camera']['target_lon'],result['camera']['lon'])

    def test_unknown_profile_and_nonfinite_or_boolean_camera_policy_are_rejected(self):
        record=[self.records['COUNTRY_SGP']]
        cases=[dict(profile='legacy'),dict(fov=True),dict(fov=float('nan')),dict(aspect=float('inf')),
               dict(minimum_height=False),dict(title_bottom=.9),dict(subtitle_top=.1),dict(enabled='true')]
        for options in cases:
            with self.subTest(options=options),self.assertRaises(ValueError):framing.fit_native_geometry(record,registry=self.registry,**options)

    def test_self_consistent_fake_geometry_hash_still_cannot_replace_native_source(self):
        forged=deepcopy(self.records['COUNTRY_SGP']);forged['coordinates'][0][0][0]+=.01
        forged['coordinates'][0][-1]=deepcopy(forged['coordinates'][0][0])
        from engine.infographic_contract import _vertices
        points=_vertices(forged['coordinates'])
        forged['bbox']=[min(p[0]for p in points),min(p[1]for p in points),max(p[0]for p in points),max(p[1]for p in points)]
        forged['sha256']=canonical_sha(dict(type=forged['geometry_type'],coordinates=forged['coordinates']))
        with self.assertRaisesRegex(ValueError,'SOURCE_BINDING_INVALID'):framing.fit_native_geometry([forged],registry=self.registry)
        with self.assertRaisesRegex(ValueError,'SOURCE_BINDING_INVALID'):framing.select_regional_lod([forged])

    def test_suez_and_singapore_select_only_existing_matching_region_pairs(self):
        for point,region in [('LOCATION_SUEZ_CANAL','detail_0'),('LOCATION_SINGAPORE_PORT','detail_1')]:
            with self.subTest(point=point):
                result=framing.select_regional_lod([self.records[point]])
                self.assertTrue(result['coverage_complete']);self.assertEqual(result['warnings'],[])
                self.assertEqual([r['region_id']for r in result['selected_regions']],[region])
                self.assertEqual(result['selected_texture_count'],2);self.assertEqual(result['new_textures'],0)
                self.assertGreater(result['selected_disk_bytes'],0)
                self.assertEqual(result['selected_regions'][0]['native_source_resolution'],[21600,10800])
                for asset in result['selected_regions'][0]['textures']:
                    self.assertEqual(asset['sha256'],self.frozen_assets[asset['file']])

    def test_uncovered_region_explicitly_retains_global_source_without_fetch(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('No external texture fetch')):
            result=framing.select_regional_lod([self.records['COUNTRY_KOR']])
        self.assertFalse(result['coverage_complete']);self.assertEqual(result['selected_regions'],[])
        self.assertEqual(result['warnings'][0]['code'],'REGIONAL_LOD_UNAVAILABLE')
        self.assertEqual(result['physical_gpu'],'NOT_RUN')

    def test_far_apart_geometry_does_not_claim_one_local_region_covers_all(self):
        records=[self.records['LOCATION_SUEZ_CANAL'],self.records['LOCATION_SINGAPORE_PORT']]
        full=framing.select_regional_lod(records)
        self.assertFalse(full['coverage_complete']);self.assertEqual(full['selected_texture_count'],0)
        partial=framing.select_regional_lod(records,allow_partial=True)
        self.assertTrue(partial['coverage_complete']);self.assertEqual(partial['selected_texture_count'],4)
        self.assertTrue(all(r['coverage']=='TARGET_GEOMETRY'for r in partial['selected_regions']))

    def test_existing_manifest_material_sources_and_texture_bytes_remain_unchanged(self):
        framing.fit_native_geometry([self.records['COUNTRY_SGP']],registry=self.registry)
        self.assertEqual(visual_quality.MANIFEST.read_bytes(),self.frozen_manifest)
        for file,digest in self.frozen_assets.items():self.assertEqual(hashlib.sha256((visual_quality.ROOT/file).read_bytes()).hexdigest(),digest)

    def test_density_uses_native_source_and_projection_not_fake_sharpening(self):
        camera=dict(lon=103.85,lat=1.3,height=.001,fov=20)
        result=framing.select_regional_lod([self.records['LOCATION_SINGAPORE_PORT']],camera=camera)
        self.assertGreater(result['screen_pixels_per_native_texel'],2.5)
        self.assertIn('SOURCE_TEXEL_MAGNIFICATION_LIMIT',{w['code']for w in result['warnings']})
        self.assertEqual(result['selected_regions'][0]['texels_per_degree'],60)
        self.assertEqual(result['rendered_quality'],'NOT_RUN')

    def test_invalid_texture_hash_from_existing_audit_blocks_selection(self):
        with patch('engine.visual_quality.asset_records',side_effect=ValueError('VISUAL_QUALITY_ASSET_HASH_MISMATCH')):
            with self.assertRaisesRegex(ValueError,'ASSET_HASH_MISMATCH'):framing.select_regional_lod([self.records['LOCATION_SUEZ_CANAL']])


if __name__=='__main__':unittest.main()
