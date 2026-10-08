"""Actual-output quality adapter contracts; no NVIDIA rasterizer is simulated."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from engine.visual_quality import ROOT, apply_quality, validate_quality, asset_records


class VisualQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        cls.saved = (schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL)
        from engine.qa_planner import generate_deployment_plan
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       direction_profile='SECOND_EVENT_ADAPTIVE_WIDE_TEST', qa_mode=True,
                       quality='HIGH', tts=False, subtitles=False, bgm=True, sfx=True)
        with patch.dict(os.environ, {'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'legacy'}):
            cls.before = generate_deployment_plan(cls.raw)
        cls.after = apply_quality(cls.before)

    @classmethod
    def tearDownClass(cls):
        from engine import schema, gpu_preflight, visibility
        schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = cls.saved

    def test_valid_explicit_quality_plan(self):
        self.assertTrue(validate_quality(self.after)['passed'])
        self.assertTrue(self.after['gate']['passed'])

    def test_content_camera_and_timing_identical(self):
        value = deepcopy(self.after)
        value['metadata'].pop('visual_quality')
        value.pop('gate', None)
        for scene in value['scenes']:
            scene.pop('visual_quality')
        before = deepcopy(self.before)
        before.pop('gate', None)
        self.assertEqual(value, before)

    def test_all_720_poses_identical_and_valid(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'plan.json'
            path.write_text(json.dumps(self.after))
            result = subprocess.run(['node', 'tools/test_visual_quality_v018.mjs', str(path)],
                                    cwd=ROOT, capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)
            self.assertTrue(report['passed'])
            self.assertEqual(report['frames'], 720)
            self.assertEqual(report['camera_trajectory'], 'UNCHANGED')

    def test_legacy_render_version_and_new_cache_separate(self):
        from engine.assets import renderer_version as legacy
        from engine.visual_quality import renderer_version
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        old = self.before['scenes'][0]
        new = self.after['scenes'][0]
        self.assertEqual(renderer_version(old), legacy(old))
        self.assertNotEqual(renderer_version(new), renderer_version(old))
        assets = {'assets': []}
        self.assertNotEqual(scene_cache_key(old, assets, quality_settings('HIGH'), renderer_version(old)),
                            scene_cache_key(new, assets, quality_settings('HIGH'), renderer_version(new)))

    def test_source_tamper_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0]['visual_quality']['source_hashes']['web/visual_quality_adapter.js'] = '0'*64
        self.assertFalse(validate_quality(plan)['passed'])

    def test_asset_tamper_rejected(self):
        plan = deepcopy(self.after)
        key = next(iter(plan['scenes'][0]['visual_quality']['asset_hashes']))
        plan['scenes'][0]['visual_quality']['asset_hashes'][key] = '0'*64
        self.assertFalse(validate_quality(plan)['passed'])

    def test_unknown_quality_version_rejected(self):
        plan = deepcopy(self.after)
        plan['metadata']['visual_quality']['version'] = 'v999'
        self.assertFalse(validate_quality(plan)['passed'])

    def test_invalid_camera_still_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0]['camera_start']['fov'] = 5
        self.assertFalse(validate_quality(plan)['passed'])

    def test_unknown_scene_field_still_rejected(self):
        from engine.schema import validate_plan
        plan = deepcopy(self.after)
        plan['scenes'][0]['unvalidated_override'] = True
        self.assertFalse(validate_plan(plan)['passed'])

    def test_unsupported_motion_still_rejected(self):
        from engine.schema import validate_plan
        plan = deepcopy(self.after)
        plan['scenes'][0]['direction'] = {'force_motion': True}
        self.assertFalse(validate_plan(plan)['passed'])

    def test_asset_pair_native_source_grid(self):
        records = asset_records()
        self.assertEqual(len(records), 4)
        for value in records:
            self.assertTrue(value['exists'] and value['readable'] and value['non_zero'])
            self.assertFalse(value['resized'])
            self.assertFalse(value['sharpened'])
            if value['role'] == 'regional_day_relief':
                self.assertEqual(value['source_resolution'], [21600, 10800])
                self.assertAlmostEqual(value['width'] / (value['bounds'][2]-value['bounds'][0]), 60)

    def test_backend_changes_only_page_and_delegates_transport(self):
        from engine.visual_quality_backend import quality_command, VisualQualityBackend
        from engine.backends import CPULocalBackend
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 's.json'
            path.write_text(json.dumps(self.after['scenes'][0]))
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1/static/render_production_earth.html', '--width', '2160']
            mapped = quality_command(command)
            self.assertEqual(mapped[:mapped.index('--url')+1], command[:command.index('--url')+1])
            self.assertEqual(mapped[-2:], command[-2:])
            self.assertIn('http://127.0.0.1/static/render_visual_quality_earth.html', mapped)
            with patch.object(CPULocalBackend, 'run', return_value='existing-transport') as existing:
                self.assertEqual(VisualQualityBackend().run(command, ROOT, None), 'existing-transport')
                self.assertEqual(existing.call_args.args[0], mapped)

    def test_unversioned_legacy_scene_not_switched_by_environment(self):
        from engine.visual_quality_backend import quality_command
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 's.json'
            path.write_text(json.dumps(self.before['scenes'][0]))
            with patch.dict(os.environ, {'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018'}):
                with self.assertRaisesRegex(RuntimeError, 'VISUAL_QUALITY_SOURCE_MISMATCH'):
                    quality_command(['node', 'renderer', '--scene-json', str(path), '--url',
                                     'http://127.0.0.1/static/render_production_earth.html'])

    def test_deployment_opt_in_only_new_24_second_plan(self):
        from engine.qa_planner import generate_deployment_plan
        with patch.dict(os.environ, {'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018'}):
            selected = generate_deployment_plan(self.raw)
        self.assertEqual(selected['metadata']['visual_quality']['version'], 'v018')
        self.assertNotIn('visual_quality', self.before['metadata'])

    def test_profile_served_bytes_exact(self):
        self.assertEqual((ROOT/'data/visual_quality_v018.json').read_bytes(),
                         (ROOT/'web/visual_quality_v018.json').read_bytes())

    def test_diagnostic_bundle_keeps_quality_receipt(self):
        from engine.gpu_bundle import DiagnosticBundle
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder/'scene_json').mkdir()
            (folder/'scene_plan.json').write_text(json.dumps(self.after))
            bundle = DiagnosticBundle(folder, 'job_0123456789ab', self.after)
            receipt = dict(scene_id='S001', frame_index=630, errors=[], cameraState='EVENT2_HOLD',
                           visualQuality=dict(version='v018', closeWeight=1, night_detail='original source'))
            scene = bundle.root/'S001'
            scene.mkdir()
            (scene/'frame-audit.jsonl').write_text(json.dumps(receipt)+'\n')
            bundle.finish(status='failed', error={'code': 'TEST_INJECTED_FAILURE'})
            with zipfile.ZipFile(bundle.package()) as archive:
                row = json.loads(archive.read('frame-audit.json'))[0]
                self.assertEqual(row['visualQuality'], receipt['visualQuality'])

    def test_camera_sources_match_frozen_v017(self):
        from deployment.gcube.visual_quality_preflight import audit_frozen_sources
        self.assertTrue(audit_frozen_sources()['passed'])

    def test_saved_quality_plan_validates_on_fresh_gateway_boot(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'saved.json'
            path.write_text(json.dumps(self.after))
            env = dict(os.environ, WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                       WORLD_ENGINE_DIRECTION_VERSION='v013', WORLD_ENGINE_SECOND_EVENT_TEST='1')
            command = 'import json,sys;from engine.qa_planner import configure_qa_schema;configure_qa_schema();from engine.schema import validate_plan;p=json.load(open(sys.argv[1]));r=validate_plan(p);assert r["passed"],r'
            subprocess.run(['python', '-c', command, str(path)], cwd=ROOT, env=env,
                           capture_output=True, text=True, check=True)

    def test_new_source_report_survives_retry_with_quality_identity(self):
        from engine.visual_quality import record_source_report, project_renderer_version
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            record = record_source_report(folder, self.after, {'passed': True, 'assets': [], 'errors': []})
            persisted = json.loads((folder/'source_report.json').read_text())
            self.assertEqual(record, persisted)
            self.assertEqual(persisted['renderer_version'], project_renderer_version(self.after))
            self.assertEqual(persisted['visual_quality']['version'], 'v018')
            self.assertIn('Natural Earth', (folder/'source_report.md').read_text())
            previous = (folder/'source_report.json').read_bytes()
            with self.assertRaises(FileExistsError):
                record_source_report(folder, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual(previous, (folder/'source_report.json').read_bytes())

    def test_explicit_quality_request_without_camera_default_flags(self):
        env = dict(os.environ, WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018', WORLD_ENGINE_DIRECTION_VERSION='v013',
                   WORLD_ENGINE_SECOND_EVENT_TEST='0', WORLD_ENGINE_RETURN_WIDE_TEST='0', WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST='0')
        command = 'import json,sys;from engine.qa_planner import generate_deployment_plan;p=generate_deployment_plan(json.loads(sys.argv[1]));assert p["gate"]["passed"];assert p["metadata"]["visual_quality"]["version"]=="v018"'
        subprocess.run(['python', '-c', command, json.dumps(self.raw)], cwd=ROOT, env=env,
                       capture_output=True, text=True, check=True)
