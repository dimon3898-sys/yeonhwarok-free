"""v019 material-only admission and frozen v018 identity; no GPU draw is faked."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from engine.event_quality import ROOT, apply_quality, validate_quality


V018_FROZEN = {
    'engine/visual_quality.py': '171abfc112f510acf3b4b92e3ee2aeca4898e3a5b2142dec0ea275c5ca1caf0b',
    'engine/visual_quality_backend.py': 'e2f269a3fb32cf007f8688f8966ec87231110aaaaecf90fb7f90accf21e19fd5',
    'web/visual_quality_adapter.js': 'c86494cc4f300e83c8633b7788b501400589abade2ec7f8a000e67f9d640da10',
    'web/render_visual_quality_earth.html': '6e67c5a1a1f0b4ac6796da6e3cef890b540a4629d6ed07ad67a1d331ebf7f69e',
    'data/visual_quality_v018.json': '5e504ecb58db272387d8606455dd5b6d9e09d7f2270143c487817eeab709f822',
    'web/visual_quality_v018.json': '5e504ecb58db272387d8606455dd5b6d9e09d7f2270143c487817eeab709f822',
    'web/earth-detail/v018/manifest.json': '4ad2b6ec9a1a5c3d0803bbec33648eb1fe474757fdcc1b279459201113f630c6',
}
NIGHT_SOURCE = ROOT.parent / 'cinematic-world-map/assets/v3/earth/earth-night-8k.jpg'
NIGHT_SHA = '9894e83a585a22c1c425e7ca4f987a9ba625bf08ecee45d3c9dcacae3c2ad5f7'


class EventQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        cls.saved = (schema.validate_plan, gpu_preflight.validate_plan,
                     schema.SCHEMA_PATH, visibility.TOOL)
        cls.environment = patch.dict(os.environ, {
            'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
            'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'legacy',
            'WORLD_ENGINE_DIRECTION_VERSION': 'v013',
            'WORLD_ENGINE_SECOND_EVENT_TEST': '0',
            'WORLD_ENGINE_RETURN_WIDE_TEST': '0',
            'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST': '0',
        })
        cls.environment.start()
        cls.addClassCleanup(cls.environment.stop)
        from engine.qa_planner import generate_deployment_plan
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       direction_profile='SECOND_EVENT_ADAPTIVE_WIDE_TEST', qa_mode=True,
                       quality='HIGH', tts=False, subtitles=False, bgm=True, sfx=True)
        cls.before = generate_deployment_plan(cls.raw)
        cls.after = apply_quality(cls.before)

    @classmethod
    def tearDownClass(cls):
        from engine import schema, gpu_preflight, visibility
        schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = cls.saved

    def test_opt_in_plan_retains_v018_and_passes_original_gates(self):
        from engine.schema import validate_plan
        self.assertTrue(validate_quality(self.after)['passed'])
        self.assertTrue(validate_plan(self.after)['passed'])
        self.assertTrue(self.after['gate']['passed'])
        self.assertEqual(self.after['metadata']['visual_quality'],
                         self.before['metadata']['visual_quality'])
        self.assertEqual(self.after['metadata']['event_quality']['version'], 'v019')

    def test_only_additive_event_quality_changes_entire_plan(self):
        after = deepcopy(self.after)
        after['metadata'].pop('event_quality')
        after.pop('gate', None)
        for scene in after['scenes']:
            scene.pop('event_quality')
        before = deepcopy(self.before)
        before.pop('gate', None)
        self.assertEqual(after, before)

    def test_actual_adapter_preserves_720_camera_frames_and_wide_response(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text(json.dumps(self.after))
            result = subprocess.run(['node', 'tools/test_event_quality_v019.mjs', str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['passed'])
            self.assertEqual(report['frames'], 720)
            self.assertEqual(report['camera_trajectory'], 'UNCHANGED')
            self.assertEqual(report['wide_response'], 'UNCHANGED')

    def test_frame_grid_is_same_720_frame_plan(self):
        from engine.second_event_camera import validate_camera
        self.assertTrue(validate_camera(self.after)['passed'])
        self.assertEqual(self.after['scenes'], [dict(self.before['scenes'][0],
                                                   event_quality=self.after['scenes'][0]['event_quality'])])
        self.assertEqual(self.after['request']['duration'], 24)

    def test_missing_v018_lod_is_not_silently_replaced(self):
        malformed = deepcopy(self.before)
        malformed['metadata'].pop('visual_quality')
        for scene in malformed['scenes']:
            scene.pop('visual_quality')
        with self.assertRaises(ValueError):
            apply_quality(malformed)

    def test_old_v018_renderer_identity_and_cache_unchanged(self):
        from engine.event_quality import renderer_version
        from engine.visual_quality import renderer_version as v018_version
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        old, new = self.before['scenes'][0], self.after['scenes'][0]
        self.assertEqual(renderer_version(old), v018_version(old))
        self.assertNotEqual(renderer_version(new), renderer_version(old))
        assets = {'assets': []}
        settings = quality_settings('HIGH')
        self.assertNotEqual(scene_cache_key(old, assets, settings, renderer_version(old)),
                            scene_cache_key(new, assets, settings, renderer_version(new)))

    def test_project_digest_changes_only_for_opt_in(self):
        from engine.event_quality import project_renderer_version
        from engine.visual_quality import project_renderer_version as v018_version
        self.assertEqual(project_renderer_version(self.before), v018_version(self.before))
        self.assertNotEqual(project_renderer_version(self.after), v018_version(self.before))

    def test_source_hash_tamper_rejected(self):
        plan = deepcopy(self.after)
        hashes = plan['scenes'][0]['event_quality']['source_hashes']
        hashes[next(iter(hashes))] = '0' * 64
        self.assertFalse(validate_quality(plan)['passed'])

    def test_profile_hash_tamper_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0]['event_quality']['profile_sha256'] = '0' * 64
        self.assertFalse(validate_quality(plan)['passed'])

    def test_external_profile_url_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0]['event_quality']['profile_url'] = 'https://untrusted.example/profile.json'
        self.assertFalse(validate_quality(plan)['passed'])

    def test_unknown_event_quality_field_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0]['event_quality']['force_gpu_pass'] = True
        self.assertFalse(validate_quality(plan)['passed'])

    def test_unknown_event_quality_metadata_rejected(self):
        plan = deepcopy(self.after)
        plan['metadata']['event_quality']['override'] = True
        self.assertFalse(validate_quality(plan)['passed'])

    def test_malformed_version_rejected(self):
        for key, value in (('version', 'v999'), ('source_hashes', None)):
            plan = deepcopy(self.after)
            plan['metadata']['event_quality'][key] = value
            with self.subTest(key=key):
                self.assertFalse(validate_quality(plan)['passed'])

    def test_absent_scene_receipt_rejected(self):
        plan = deepcopy(self.after)
        plan['scenes'][0].pop('event_quality')
        self.assertFalse(validate_quality(plan)['passed'])

    def test_camera_fov_and_unrecognized_fields_still_fail(self):
        from engine.schema import validate_plan
        for changes in ({'camera_start': dict(self.after['scenes'][0]['camera_start'], fov=5)},
                        {'unvalidated_override': True}, {'direction': {'force_motion': True}}):
            plan = deepcopy(self.after)
            plan['scenes'][0].update(changes)
            with self.subTest(changes=changes):
                self.assertFalse(validate_plan(plan)['passed'])

    def test_backend_changes_only_page_without_chromium_arguments(self):
        from engine.event_quality_backend import event_quality_command, EventQualityBackend
        from engine.backends import CPULocalBackend
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(self.after['scenes'][0]))
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1:8000/static/render_production_earth.html',
                       '--width', '2160', '--height', '3840']
            mapped = event_quality_command(command)
            expected = list(command)
            expected[expected.index('--url') + 1] = 'http://127.0.0.1:8000/static/render_event_quality_earth.html'
            self.assertEqual(mapped, expected)
            with patch.object(CPULocalBackend, 'run', return_value='unchanged transport') as transport:
                self.assertEqual(EventQualityBackend().run(command, ROOT, None), 'unchanged transport')
                self.assertEqual(transport.call_args.args[0], mapped)

    def test_environment_cannot_switch_saved_v018_scene(self):
        from engine.event_quality_backend import event_quality_command
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(self.before['scenes'][0]))
            with patch.dict(os.environ, {'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019'}):
                with self.assertRaises(RuntimeError):
                    event_quality_command(['node', 'renderer', '--scene-json', str(path), '--url',
                                           'http://127.0.0.1/static/render_production_earth.html'])
        self.assertNotIn('event_quality', self.before['metadata'])

    def test_new_24_second_default_selects_both_lod_and_event_profile(self):
        from engine.qa_planner import generate_deployment_plan
        with patch.dict(os.environ, {'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
                                    'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019'}):
            plan = generate_deployment_plan(self.raw)
        self.assertEqual(plan['metadata']['visual_quality']['version'], 'v018')
        self.assertEqual(plan['metadata']['event_quality']['version'], 'v019')
        self.assertTrue(plan['gate']['passed'])

    def test_served_profile_bytes_are_exact(self):
        self.assertEqual((ROOT / 'data/event_quality_v019.json').read_bytes(),
                         (ROOT / 'web/event_quality_v019.json').read_bytes())

    def test_deployed_profile_rejects_nonfinite_boolean_and_invalid_radiance(self):
        from engine import event_quality
        original = json.loads((ROOT / 'data/event_quality_v019.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            for key, value in (('day_input_scale', float('nan')), ('day_input_scale', True),
                               ('ocean_specular_scale', -1), ('city_contribution_scale', 2),
                               ('daylight_full', 0), ('daylight_full', .0005),
                               ('additional_textures', 1), ('additional_textures', False),
                               ('city_mask', 'invented_city_map')):
                modified = {**original, key: value}
                for prefix in ('data', 'web'):
                    (root / prefix / 'event_quality_v019.json').write_text(json.dumps(modified))
                with self.subTest(key=key, value=value), patch.object(event_quality, 'ROOT', root):
                    report = validate_quality(self.after)
                    self.assertFalse(report['passed'])
                    self.assertTrue(any(row['code'].startswith('EVENT_QUALITY_') for row in report['errors']))

    def test_deployed_profile_mismatch_rejected_before_renderer(self):
        from engine import event_quality
        original = (ROOT / 'data/event_quality_v019.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            (root / 'data/event_quality_v019.json').write_bytes(original)
            (root / 'web/event_quality_v019.json').write_bytes(b'{"version":"v999"}')
            with patch.object(event_quality, 'ROOT', root):
                report = validate_quality(self.after)
            self.assertFalse(report['passed'])
            self.assertIn('EVENT_QUALITY_SERVED_PROFILE_MISMATCH', [row['code'] for row in report['errors']])

    def test_v018_lod_source_bytes_and_configuration_are_unchanged(self):
        for name, expected in V018_FROZEN.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        from engine.visual_quality import asset_records
        self.assertEqual(len(asset_records()), 4)

    def test_night_source_integrity_native_jpeg_resolution(self):
        from PIL import Image
        self.assertEqual(hashlib.sha256(NIGHT_SOURCE.read_bytes()).hexdigest(), NIGHT_SHA)
        with Image.open(NIGHT_SOURCE) as source:
            source.load()
            self.assertEqual(source.format, 'JPEG')
            self.assertEqual(source.size, (8192, 4096))
            self.assertEqual(source.mode, 'RGB')

    def test_event_quality_does_not_admit_a_software_gpu(self):
        from deployment.gcube.gpu import classify_probe, GPUError
        hardware = [{'name': 'NVIDIA GeForce RTX 4080 SUPER', 'memory_total_mib': 16384.0,
                     'driver_version': '570.124.04'}]
        for renderer in ('ANGLE (Google, SwiftShader Device)', 'llvmpipe (LLVM 17)'):
            rejected = {'webgl': {'context_available': True, 'context_version': 2,
                                 'draw_passed': True, 'webgl_error': 0,
                                 'renderer': renderer, 'vendor': 'Google Inc. (NVIDIA)',
                                 'pixel': [255, 0, 0, 255], 'debug_renderer_available': True,
                                 'max_texture_size': 16384, 'max_renderbuffer_size': 16384}}
            with self.subTest(renderer=renderer), self.assertRaises(GPUError):
                classify_probe(rejected, hardware)

    def test_saved_v019_validates_fresh_gateway_with_no_camera_default_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'approved.json'
            path.write_text(json.dumps(self.after))
            env = dict(os.environ, WORLD_ENGINE_EVENT_QUALITY_VERSION='v019',
                       WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                       WORLD_ENGINE_DIRECTION_VERSION='v013',
                       WORLD_ENGINE_SECOND_EVENT_TEST='0', WORLD_ENGINE_RETURN_WIDE_TEST='0',
                       WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST='0')
            code = ('import json,sys;from engine.qa_planner import configure_qa_schema;'
                    'configure_qa_schema();from engine.schema import validate_plan;'
                    'result=validate_plan(json.load(open(sys.argv[1])));assert result["passed"],result')
            result = subprocess.run([sys.executable, '-c', code, str(path)], cwd=ROOT, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_v019_plan_with_no_default_camera_flags(self):
        env = dict(os.environ, WORLD_ENGINE_EVENT_QUALITY_VERSION='v019',
                   WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018', WORLD_ENGINE_DIRECTION_VERSION='v013',
                   WORLD_ENGINE_SECOND_EVENT_TEST='0', WORLD_ENGINE_RETURN_WIDE_TEST='0',
                   WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST='0')
        code = ('import json,sys;from engine.qa_planner import generate_deployment_plan;'
                'plan=generate_deployment_plan(json.loads(sys.argv[1]));assert plan["gate"]["passed"],plan["gate"];'
                'assert plan["metadata"]["event_quality"]["version"]=="v019";'
                'assert plan["metadata"]["visual_quality"]["version"]=="v018"')
        result = subprocess.run([sys.executable, '-c', code, json.dumps(self.raw)], cwd=ROOT, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_persisted_source_report_retains_both_versions_and_renderer_identity(self):
        from engine.event_quality import record_source_report, project_renderer_version
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            record = record_source_report(folder, self.after, {'passed': True, 'assets': [], 'errors': []})
            persisted = json.loads((folder / 'source_report.json').read_text())
            self.assertEqual(record, persisted)
            self.assertEqual(record['renderer_version'], project_renderer_version(self.after))
            self.assertEqual(record['visual_quality']['version'], 'v018')
            self.assertEqual(record['event_quality']['version'], 'v019')
            previous = (folder / 'source_report.json').read_bytes()
            with self.assertRaises(FileExistsError):
                record_source_report(folder, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual(previous, (folder / 'source_report.json').read_bytes())
            self.assertEqual(json.loads(previous)['renderer_version'], project_renderer_version(self.after))

    def test_existing_source_report_is_never_overwritten(self):
        from engine.event_quality import record_source_report
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            original = b'{"preserved_previous_project":true}\n'
            (folder / 'source_report.json').write_bytes(original)
            with self.assertRaises(FileExistsError):
                record_source_report(folder, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual((folder / 'source_report.json').read_bytes(), original)

    def test_diagnostic_bundle_retains_material_receipt_and_redacts_secret(self):
        from engine.gpu_bundle import DiagnosticBundle
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'scene_json').mkdir()
            (folder / 'scene_plan.json').write_text(json.dumps(self.after))
            hidden = 'test-diagnostic-private-value-019'
            with patch.dict(os.environ, {'WORLD_ENGINE_OWNER_CODE': hidden}):
                bundle = DiagnosticBundle(folder, 'job_019abcdef012', self.after)
                scene_dir = bundle.root / 'S001'
                scene_dir.mkdir()
                safe = dict(version='v019', parent_version='v018', material_weight=1.0,
                            profile_sha256=self.after['scenes'][0]['event_quality']['profile_sha256'],
                            day_input_scale=.60, ocean_specular_scale=.50,
                            city_contribution_scale=.12, city_mask='existing_native_regional_land_mask',
                            additional_textures=0, additional_texture_uploads=0,
                            preserved=dict(camera=True, timing=True, wide=True, regional_lod=True))
                receipt = dict(scene_id='S001', frame_index=630, errors=[],
                               cameraState='EVENT2_HOLD', eventQuality={**safe, 'owner_code': hidden})
                (scene_dir / 'frame-audit.jsonl').write_text(json.dumps(receipt) + '\n')
                bundle.log('stderr', 'original failure ' + hidden)
                bundle.finish(status='failed', error={'code': 'TEST_INJECTED_FAILURE'})
                with zipfile.ZipFile(bundle.package()) as archive:
                    row = json.loads(archive.read('frame-audit.json'))[0]
                    self.assertEqual(row['eventQuality'], safe)
                    serialized = b'\n'.join(archive.read(name) for name in archive.namelist())
                    self.assertNotIn(hidden.encode(), serialized)

    def test_certified_gpu_camera_audio_and_transport_sources_are_unchanged(self):
        from deployment.gcube.visual_quality_preflight import audit_frozen_sources
        report = audit_frozen_sources()
        self.assertTrue(report['passed'], [row for row in report['sources'] if not row['unchanged']])
