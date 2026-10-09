"""Sparse v020 admission over frozen v019; native tests do not claim GPU pixels."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import FunctionType
import unittest
from unittest.mock import patch
import zipfile

from engine import reference_effects as effects
from engine.event_quality import ROOT


V019_FROZEN = {
    'engine/event_quality.py': 'ed3a64e59656327eeb8ad661ba3b94429d0a847d16b3b759c4f316a58e6bfb05',
    'engine/event_quality_backend.py': 'ed6698ce19bb09a5aebe254014c6acfa26953cf014965f9a2d72fae6325d058a',
    'web/event_quality_adapter.js': 'bab46f0ed430b275193fde8e9df9e216b16a23659005bb02903c318ddce029b2',
    'web/render_event_quality_earth.html': 'ea7b9834dd5a2ef348d6d6a58ed17605ebf407cab41cb658b0c611e9005fb56d',
    'data/event_quality_v019.json': '3def1eb34d8de4be8bd04cc86cdeb3198d3181dfdc786d073f1259e1a4d001fd',
    'web/event_quality_v019.json': '3def1eb34d8de4be8bd04cc86cdeb3198d3181dfdc786d073f1259e1a4d001fd',
}
REFERENCE_SHA = '853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc'
REFERENCE_UPLOAD = Path('/workspace/attachments/db50adcf-6934-40ae-b53a-e9950f78b63a/lv_0_20261008074313.mp4')


def _render_must_not_start(*args, **kwargs):
    raise AssertionError('Admission failure must prevent the original render function from starting')


class ReferenceEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        saved = (schema.validate_plan, gpu_preflight.validate_plan,
                 schema.SCHEMA_PATH, visibility.TOOL)
        def restore():
            schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = saved
        cls.addClassCleanup(restore)
        cls.environment = patch.dict(os.environ, {
            'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
            'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019',
            'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'legacy',
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
        cls.after = effects.apply_effects(cls.before)

    def assert_rejected(self, plan):
        from engine.schema import validate_plan
        result = effects.validate_effects(plan)
        self.assertFalse(result['passed'], result)
        self.assertTrue(result['errors'], result)
        self.assertFalse(validate_plan(plan)['passed'])

    def test_off_is_independent_exact_whole_parent_plan_including_gate(self):
        original = deepcopy(self.before)
        off = effects.apply_effects(self.before, enabled=False)
        self.assertEqual(off, original)
        self.assertEqual(self.before, original)
        self.assertIsNot(off, self.before)
        off['scenes'][0]['labels'][0]['text'] = 'mutated isolated copy'
        self.assertEqual(self.before, original)
        with self.assertRaisesRegex(ValueError, 'OFF_REQUIRES_PARENT_PLAN'):
            effects.apply_effects(self.after, enabled=False)

    def test_off_scene_cache_and_both_renderer_identities_are_exact_parent(self):
        from engine.event_quality import renderer_version, project_renderer_version
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        off = effects.apply_effects(self.before, enabled=False)
        assets, settings = {'assets': []}, quality_settings('HIGH')
        for old, new in zip(self.before['scenes'], off['scenes']):
            self.assertEqual(new, old)
            self.assertEqual(effects.renderer_version(new), renderer_version(old))
            self.assertEqual(scene_cache_key(new, assets, settings, effects.renderer_version(new)),
                             scene_cache_key(old, assets, settings, renderer_version(old)))
        self.assertEqual(effects.project_renderer_version(off), project_renderer_version(self.before))

    def test_on_is_only_additive_selection_and_gate_over_entire_v019_plan(self):
        from engine.schema import validate_plan
        plain = deepcopy(self.after)
        plain['metadata'].pop('reference_effects')
        for scene in plain['scenes']:
            scene.pop('reference_effects')
        plain.pop('gate')
        parent = deepcopy(self.before)
        parent.pop('gate')
        self.assertEqual(plain, parent)
        self.assertTrue(effects.validate_effects(self.after)['passed'])
        self.assertTrue(validate_plan(self.after)['passed'])
        self.assertTrue(self.after['gate']['passed'])
        self.assertEqual(self.after['gate']['reference_effects'], {'passed': True, 'version': 'v020'})

    def test_on_has_separate_scene_cache_and_project_renderer_identity(self):
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        assets, settings = {'assets': []}, quality_settings('HIGH')
        old, new = self.before['scenes'][0], self.after['scenes'][0]
        self.assertNotEqual(effects.renderer_version(old), effects.renderer_version(new))
        self.assertNotEqual(scene_cache_key(old, assets, settings, effects.renderer_version(old)),
                            scene_cache_key(new, assets, settings, effects.renderer_version(new)))
        self.assertNotEqual(effects.project_renderer_version(self.before),
                            effects.project_renderer_version(self.after))

    def test_all_six_actual_v019_source_files_keep_frozen_sha256(self):
        self.assertEqual(set(effects.parent.SOURCES), set(V019_FROZEN))
        for name, expected in V019_FROZEN.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        for scene in self.after['scenes']:
            self.assertEqual(scene['reference_effects']['parent_source_hashes'], V019_FROZEN)

    def test_actual_node_overlay_preserves_all_720_camera_material_and_off_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text(json.dumps(self.after))
            result = subprocess.run(['node', 'tools/test_reference_effects_v020.mjs', str(path)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['frames'], 720)
        for key in ('camera_trajectory', 'material', 'wide', 'overlay_off', 'sfx'):
            self.assertEqual(report[key], 'UNCHANGED', key)
        self.assertEqual(report['additional_texture_uploads'], 0)
        self.assertGreater(report['changed_overlay_frames'], 0)
        self.assertLess(report['changed_overlay_frames'], 720)
        self.assertEqual(report['GPU'], 'NOT_RUN')
        self.assertEqual(report['shader_compile'], 'NVIDIA_NOT_RUN')
        self.assertEqual(report['pixel_quality'], 'NOT_RUN')
        self.assertEqual(set(report['receipt_coverage']), {'FX_E001', 'FX_E002', 'FX_E003', 'FX_E004'})
        self.assertTrue(all(0 < count <= 45 for count in report['receipt_coverage'].values()))
        self.assertEqual(set(report['marker_scales']), {'FX_E001', 'FX_E004'})
        for values in report['marker_scales'].values():
            self.assertGreater(len(values), 1)
            self.assertLessEqual(max(row['scale'] for row in values), 1.10 + 1e-9)

    def test_backend_changes_only_renderer_page_and_preserves_transport_and_env(self):
        from engine.reference_effects_backend import reference_effects_command, ReferenceEffectsBackend
        from engine.backends import CPULocalBackend
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(self.after['scenes'][0]))
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1:8000/static/render_production_earth.html?scene=S001#canvas',
                       '--width', '2160', '--height', '3840', '--fps', '30']
            previous = list(command)
            environment = dict(os.environ)
            expected = list(command)
            expected[expected.index('--url') + 1] = 'http://127.0.0.1:8000/static/render_reference_effects_earth.html?scene=S001#canvas'
            mapped = reference_effects_command(command)
            self.assertEqual(mapped, expected)
            self.assertEqual(command, previous)
            self.assertEqual(dict(os.environ), environment)
            progress = lambda event: None
            with patch.object(CPULocalBackend, 'run', return_value='retained transport') as transport:
                self.assertEqual(ReferenceEffectsBackend().run(command, ROOT, progress), 'retained transport')
                transport.assert_called_once_with(expected, ROOT, progress)
            self.assertEqual(dict(os.environ), environment)
            self.assertEqual(reference_effects_command(['ffmpeg', '-version']), ['ffmpeg', '-version'])

    def test_backend_environment_cannot_switch_saved_parent_or_accept_tampered_receipt(self):
        from engine.reference_effects_backend import reference_effects_command
        for selected in (self.before['scenes'][0],
                         dict(self.after['scenes'][0], reference_effects={})):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'scene.json'
                path.write_text(json.dumps(selected))
                with patch.dict(os.environ, {'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020'}):
                    with self.assertRaisesRegex(RuntimeError, 'REFERENCE_EFFECTS_SOURCE_MISMATCH'):
                        reference_effects_command(['node', 'renderer', '--scene-json', str(path), '--url',
                                                   'http://127.0.0.1/static/render_production_earth.html'])

    def test_events_bind_only_existing_semantics_and_unmodified_text_coordinates(self):
        scene = self.after['scenes'][0]
        events = scene['reference_effects']['events']
        self.assertEqual([e['story_event_id'] for e in events], [e['id'] for e in scene['visual_events']])
        self.assertEqual([e['type'] for e in events], ['LOCATION_REVEAL', 'EVENT_START', 'EVENT_RESOLVED',
                                                     'NEXT_LOCATION_REVEAL', 'EVENT_STATE_CHANGE'])
        self.assertEqual([e['start_frame'] for e in events], [60, 180, 330, 450, 615])
        self.assertEqual([e['text'] for e in events], ['SUEZ CANAL', 'CANAL CLOSED', 'CANAL OPEN', 'SINGAPORE', ''])
        for event, source in zip(events, scene['visual_events']):
            self.assertEqual(event['coordinates'], source['coordinates'])
            self.assertEqual(event['start_frame'], round(source['time'] * 30))
        self.assertEqual(events[-1]['pattern'], 'NONE')
        self.assertFalse(events[-1]['primary'])

    def test_segment_timeline_covers_zero_to_720_once_with_explicit_none_rows(self):
        scene = self.after['scenes'][0]
        rows = effects.effect_timeline(scene)
        self.assertLess(len(rows), 720)
        self.assertEqual(rows[0]['start_frame'], 0)
        self.assertEqual(rows[-1]['end_frame'], 720)
        self.assertEqual(sum(row['frame_count'] for row in rows), 720)
        for previous, following in zip(rows, rows[1:]):
            self.assertEqual(previous['end_frame'], following['start_frame'])
        for frame in range(720):
            self.assertEqual(sum(row['start_frame'] <= frame < row['end_frame'] for row in rows), 1)
        for row in rows:
            self.assertGreater(row['end_frame'], row['start_frame'])
            self.assertEqual(row['frame_count'], row['end_frame'] - row['start_frame'])
            self.assertAlmostEqual(row['duration_seconds'], row['frame_count'] / 30)
            expected_sound = {60: 'EXISTING_soft_pulse', 180: 'EXISTING_low_impact'}.get(row['start_frame'], 'NONE')
            self.assertEqual(row['sfx'], expected_sound)
            if expected_sound != 'NONE':
                self.assertEqual(row['frame_count'], 1)
            if 'ZOOM' in row['camera_state']:
                self.assertEqual(row['visual_effect'], 'NONE')
                self.assertEqual(row['text_effect'], 'NONE')
        self.assertTrue(any(row['story_events'] == ['NONE'] and row['visual_effect'] == 'NONE'
                            and row['text_effect'] == 'NONE' for row in rows))
        self.assertEqual([(row['start_frame'], row['end_frame'], row['sfx'])
                          for row in rows if row['sfx'] != 'NONE'],
                         [(60, 61, 'EXISTING_soft_pulse'), (180, 181, 'EXISTING_low_impact')])

    def test_effect_qc_detects_all_six_density_and_readability_failures(self):
        def changes(code, scene):
            events = scene['reference_effects']['events']
            if code == 'EXCESSIVE_PULSE':
                events[0]['repeat_count'] = 2
            elif code == 'CONTINUOUS_GLOW':
                events[0]['pattern'] = 'GLOW'
            elif code == 'SFX_OVERDENSITY':
                events[0]['sfx'] = 'IMPACT_LIGHT_01'
            elif code == 'TEXT_MOTION_OVERLOAD':
                events[1]['end_frame'] = events[1]['start_frame'] + 19
            elif code == 'TOO_MANY_SIMULTANEOUS_EFFECTS':
                events.append(dict(events[0], id='FX_DUPLICATE'))
            else:
                events[0].update(start_frame=90, peak_frame=94, end_frame=99)
        for code in ('EXCESSIVE_PULSE', 'CONTINUOUS_GLOW', 'SFX_OVERDENSITY', 'TEXT_MOTION_OVERLOAD',
                     'TOO_MANY_SIMULTANEOUS_EFFECTS', 'EFFECT_DURING_UNREADABLE_CAMERA_MOTION'):
            scene = deepcopy(self.after['scenes'][0])
            changes(code, scene)
            with self.subTest(code=code):
                result = effects.effect_qc(scene)
                self.assertFalse(result['passed'])
                self.assertIn(code, [item['code'] for item in result['errors']])
        self.assertTrue(effects.effect_qc(self.after['scenes'][0])['passed'])

    def test_effect_qc_rejects_noninteger_nonfinite_reverse_and_empty_frame_ranges(self):
        for key, value in (('start_frame', True), ('start_frame', 60.0), ('start_frame', float('nan')),
                           ('peak_frame', '64'), ('peak_frame', 59), ('end_frame', 60), ('end_frame', 721)):
            scene = deepcopy(self.after['scenes'][0])
            scene['reference_effects']['events'][0][key] = value
            with self.subTest(key=key, value=value):
                result = effects.effect_qc(scene)
                self.assertFalse(result['passed'])
                self.assertIn('REFERENCE_EFFECTS_FRAME_GRID_INVALID', [e['code'] for e in result['errors']])

    def test_source_hash_profile_hash_parent_hash_and_external_url_tampering_fail(self):
        for key, value in (('source_hashes', {}), ('source_hashes', None), ('parent_source_hashes', {}),
                           ('profile_sha256', '0' * 64), ('version', 'v999'),
                           ('profile_url', 'https://untrusted.example/effect.json'),
                           ('profile_url', '/static/../effect.json')):
            plan = deepcopy(self.after)
            plan['scenes'][0]['reference_effects'][key] = value
            with self.subTest(key=key, value=value):
                self.assert_rejected(plan)

    def test_unknown_metadata_and_scene_selection_fields_are_rejected(self):
        for location in ('metadata', 'scene'):
            plan = deepcopy(self.after)
            selected = plan['metadata']['reference_effects'] if location == 'metadata' else plan['scenes'][0]['reference_effects']
            selected['force_gpu_pass'] = True
            with self.subTest(location=location):
                self.assert_rejected(plan)
        for value in ({'version': 'v020'}, None, 'v020'):
            plan = deepcopy(self.after)
            plan['metadata']['reference_effects'] = value
            with self.subTest(metadata=value):
                self.assert_rejected(plan)

    def test_changed_event_type_story_binding_wording_coordinates_and_unknown_fields_fail(self):
        cases = (('type', 'EXPLOSION'), ('story_event_id', 'nonexistent'), ('pattern', 'FLASH'),
                 ('text', 'copied reference text'), ('coordinates', {'lon': 0, 'lat': 0}),
                 ('start_frame', 61), ('reference_evidence_ids', ['invented']), ('source_url', 'https://foreign.example'))
        for key, value in cases:
            plan = deepcopy(self.after)
            plan['scenes'][0]['reference_effects']['events'][0][key] = value
            with self.subTest(key=key):
                self.assert_rejected(plan)
        for value in ([], None, {}, 'events'):
            plan = deepcopy(self.after)
            plan['scenes'][0]['reference_effects']['events'] = value
            with self.subTest(events=value):
                self.assert_rejected(plan)

    def test_profile_rejects_unobserved_nonfinite_typed_and_unknown_source_configuration(self):
        original = json.loads((ROOT / 'data/reference_effects_v020.json').read_text())
        cases = []
        for key, value in (('version', 'v019'), ('reference_sha256', '0' * 64),
                           ('reference_fps', 30.0), ('reference_content_end_frame', True),
                           ('unknown_override', True)):
            changed = deepcopy(original)
            changed[key] = value
            cases.append((key, changed))
        for field, value in (('pop_frames', 9.0), ('peak_offset_frames', float('inf')),
                             ('start_scale', float('nan')), ('radius_px', -1)):
            changed = deepcopy(original)
            changed['patterns']['MARKER_POP'][field] = value
            cases.append((field, changed))
        changed = deepcopy(original)
        changed['limits']['max_added_sfx'] = 1
        cases.append(('added_sfx', changed))
        changed = deepcopy(original)
        changed['evidence'][0]['start_frame'] = -1
        cases.append(('evidence_frame', changed))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            for name, changed in cases:
                payload = json.dumps(changed)
                (root / 'data/reference_effects_v020.json').write_text(payload)
                (root / 'web/reference_effects_v020.json').write_text(payload)
                with self.subTest(name=name), patch.object(effects, 'ROOT', root):
                    with self.assertRaises(ValueError):
                        effects._profile()

    def test_source_and_served_profiles_are_exact_and_mismatch_is_rejected(self):
        original = (ROOT / 'data/reference_effects_v020.json').read_bytes()
        self.assertEqual(original, (ROOT / 'web/reference_effects_v020.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            (root / 'data/reference_effects_v020.json').write_bytes(original)
            (root / 'web/reference_effects_v020.json').write_bytes(b'{"version":"v999"}')
            with patch.object(effects, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'SERVED_PROFILE_MISMATCH'):
                    effects._profile()

    def test_original_invalid_camera_and_unknown_scene_fields_still_fail(self):
        from engine.schema import validate_plan
        for change in ({'camera_start': dict(self.after['scenes'][0]['camera_start'], fov=5)},
                       {'unvalidated_override': True}, {'direction': {'force_motion': True}}):
            plan = deepcopy(self.after)
            plan['scenes'][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(validate_plan(plan)['passed'])

    def test_effects_require_original_v019_parent_and_boolean_explicit_selection(self):
        for value in (True, 1, 'true', None):
            if value is True:
                continue
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'SELECTION_INVALID'):
                effects.apply_effects(self.before, enabled=value)
        plan = deepcopy(self.before)
        plan['metadata'].pop('event_quality')
        for scene in plan['scenes']:
            scene.pop('event_quality')
        with self.assertRaisesRegex(ValueError, 'V019_BASELINE_REQUIRED'):
            effects.apply_effects(plan)

    def test_existing_audio_events_times_gain_and_legacy_mix_policy_are_exact(self):
        from engine.sfx_library import production_audio_enabled
        from engine.rhythm_sound import rhythm_audio_enabled
        from engine.audio_stability import enabled
        self.assertEqual(self.after['options'], self.before['options'])
        for old, new in zip(self.before['scenes'], self.after['scenes']):
            self.assertEqual(new['sound_events'], old['sound_events'])
        events = self.after['scenes'][0]['sound_events']
        self.assertEqual([e['time'] for e in events], [2.0, 6.0])
        self.assertEqual([e['kind'] for e in events], ['soft_pulse', 'low_impact'])
        self.assertEqual([e['visual_event_id'] for e in events], ['E001', 'E002'])
        self.assertEqual([e['gain_db'] for e in events], [-12, -12])
        for plan in (self.before, self.after):
            self.assertNotIn('production_defaults', plan)
            self.assertNotIn('rhythm_policy', plan)
            self.assertFalse(production_audio_enabled(plan))
            self.assertFalse(rhythm_audio_enabled(plan))
            self.assertFalse(enabled(plan))

    def test_real_existing_legacy_audio_mix_and_mastered_pcm_are_unchanged(self):
        from engine.audio import create_audio, _stereo
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = create_audio(self.before, root / 'before')
            after = create_audio(self.after, root / 'after')
            self.assertEqual(before['sound_events'], after['sound_events'])
            self.assertEqual(before['normalization'], after['normalization'])
            self.assertEqual((root / 'before/mix_raw.wav').read_bytes(), (root / 'after/mix_raw.wav').read_bytes())
            first, second = _stereo(Path(before['file'])), _stereo(Path(after['file']))
            self.assertEqual(first.shape, (24 * 48000, 2))
            self.assertGreater(float(np.max(np.abs(first))), 0)
            self.assertTrue(np.array_equal(first, second))

    def test_real_reference_identity_and_native_evidence_support_only_observed_patterns(self):
        profile = effects._profile()
        self.assertEqual(effects.REFERENCE_SHA256, REFERENCE_SHA)
        self.assertEqual(profile['reference_sha256'], REFERENCE_SHA)
        # The uploaded original is present in the native review workspace;
        # container release tests retain its measured identity in the profile.
        if REFERENCE_UPLOAD.is_file():
            self.assertEqual(hashlib.sha256(REFERENCE_UPLOAD.read_bytes()).hexdigest(), REFERENCE_SHA)
        self.assertEqual(profile['reference_content_end_frame'], 575)
        self.assertEqual(set(profile['patterns']), {'MARKER_POP', 'TEXT_CHARACTER_REVEAL'})
        evidence = {item['id']: item for item in profile['evidence']}
        self.assertEqual((evidence['REF_INITIAL_PIN_ENTRANCE']['start_frame'],
                          evidence['REF_INITIAL_PIN_ENTRANCE']['peak_frame'],
                          evidence['REF_INITIAL_PIN_ENTRANCE']['settled_frame']), (177, 181, 186))
        self.assertEqual((evidence['REF_LABEL_CHARACTER_ENTRANCE']['start_frame'],
                          evidence['REF_LABEL_CHARACTER_ENTRANCE']['end_frame'],
                          evidence['REF_LABEL_CHARACTER_ENTRANCE']['second_start_frame']), (289, 306, 311))
        self.assertIn('Full-screen flash', profile['excluded'])
        self.assertIn('Transition accent', profile['excluded'])
        for scene in self.after['scenes']:
            for event in scene['reference_effects']['events']:
                self.assertTrue(set(event['reference_evidence_ids']) <= set(evidence))

    def test_unconfirmed_mixed_reference_adds_no_sfx_texture_or_shader_policy(self):
        profile = effects._profile()
        self.assertEqual(profile['audio']['status'], 'UNCONFIRMED')
        self.assertEqual(profile['limits']['max_added_sfx'], 0)
        self.assertEqual(profile['design']['texture_uploads'], 0)
        self.assertFalse(profile['design']['shader_changes'])
        report = effects.validate_effects(self.after)
        self.assertEqual(report['added_sfx'], 0)
        self.assertEqual(report['added_textures'], 0)
        self.assertEqual(report['physical_gpu'], 'NOT_RUN')
        for scene in self.after['scenes']:
            self.assertTrue(all(e['sfx'] == 'NONE' for e in scene['reference_effects']['events']))

    def test_diagnostic_record_preserves_events_segment_coverage_and_truthful_gpu_status(self):
        report = effects.diagnostic_record(self.after)
        self.assertEqual(report['version'], 'v020')
        self.assertTrue(report['qc']['passed'])
        self.assertEqual(report['reference_sha256'], REFERENCE_SHA)
        self.assertEqual(report['physical_gpu'], 'NOT_RUN')
        self.assertIn('UNCONFIRMED', report['sfx'])
        for record, scene in zip(report['scenes'], self.after['scenes']):
            self.assertEqual(record['events'], scene['reference_effects']['events'])
            self.assertEqual(record['timeline'], effects.effect_timeline(scene))
            self.assertEqual(sum(row['frame_count'] for row in record['timeline']), 720)

    def test_success_bundle_integrates_effect_selection_and_diagnostic_record_without_gpu_claim(self):
        from engine.gpu_bundle import DiagnosticBundle, Redactor
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = effects.diagnostic_record(self.after)
            bundle = DiagnosticBundle(root, 'job_020abcdef012', self.after)
            scene_dir = bundle.root / 'S001'
            scene_dir.mkdir()
            (scene_dir / 'renderer-diagnostics.json').write_text(json.dumps({'reference_effects': report}))
            # This tests the durable audit protocol, not a rendered GPU frame.
            receipt = {'scene_id': 'S001', 'frame_index': 64, 'source': 'UNIT_PROTOCOL_FIXTURE',
                       'errors': [], 'referenceEffects': {'version': 'v020', 'effect_id': 'FX_E001',
                       'scale': 1.10, 'texture_uploads': 0, 'physical_gpu': 'NOT_RUN'}}
            (scene_dir / 'frame-audit.jsonl').write_text(json.dumps(receipt) + '\n')
            archive_path = bundle.finish(status='SUCCESS', result={'qc': {'passed': True, 'gpu': 'NOT_RUN'}, 'outputs': {}})
            with zipfile.ZipFile(archive_path) as archive:
                scene = json.loads(archive.read('S001.json'))
                self.assertEqual(scene['reference_effects'], Redactor().clean(self.after['scenes'][0]['reference_effects']))
                self.assertEqual(json.loads(archive.read('frame-audit.json'))[0], receipt)
                diagnostics = json.loads(archive.read('renderer-diagnostics.json'))
                selected = next(item['record']['reference_effects'] for item in diagnostics
                                if 'reference_effects' in item['record'])
                self.assertEqual(selected, Redactor().clean(report))
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')
                self.assertTrue(json.loads(archive.read('qc.json'))['passed'])

    def test_before_frame_failure_bundle_keeps_rejected_scene_and_original_error(self):
        from engine.gpu_bundle import DiagnosticBundle
        plan = deepcopy(self.after)
        plan['scenes'][0]['reference_effects']['events'][0]['sfx'] = 'IMPACT_LIGHT_01'
        failure = effects.validate_effects(plan)
        self.assertFalse(failure['passed'])
        self.assertIn('SFX_OVERDENSITY', [e['code'] for e in failure['errors']])
        with tempfile.TemporaryDirectory() as directory:
            bundle = DiagnosticBundle(Path(directory), 'job_020abcdef013', plan)
            archive_path = bundle.finish(status='FAILED', error={'code': 'REFERENCE_EFFECTS_PLAN_INVALID',
                                                                 'scene_id': 'S001', 'effect_qc': failure})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('frame-audit.json')), [])
                scene = json.loads(archive.read('S001.json'))
                self.assertEqual(scene['reference_effects']['events'][0]['sfx'], 'IMPACT_LIGHT_01')
                failed = json.loads(archive.read('failed-invariant.json'))
                self.assertEqual(failed['PRIMARY_ERROR'], 'REFERENCE_EFFECTS_PLAN_INVALID')
                self.assertFalse(failed['evidence']['effect_qc']['passed'])
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')

    def test_real_pipeline_effect_admission_failure_exports_qc_before_render_or_collector(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle
        plan = deepcopy(self.after)
        plan['scenes'][0]['reference_effects']['events'][0]['sfx'] = 'IMPACT_LIGHT_01'
        # A real FunctionType exercises the wrapper's production branch. Its
        # preserved rendering globals supply the normal source-report hooks,
        # while its body fails if admission ever allows rendering to begin.
        sentinel = FunctionType(_render_must_not_start.__code__, dict(rendering.render_project.__globals__))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DiagnosticBundle(root, 'job_020abcdef014', plan)
            with patch.object(rendering, 'render_project', sentinel), \
                    patch('engine.gpu_preflight.collect_all') as collect:
                with self.assertRaisesRegex(RuntimeError, '^REFERENCE_EFFECTS_PREFLIGHT_FAILED$'):
                    pipeline_stability.render_project(root, plan, 'http://127.0.0.1:8000', diagnostic=bundle)
                collect.assert_not_called()
            saved = json.loads((bundle.root / 'preflight.json').read_text())
            self.assertFalse(saved['passed'])
            self.assertFalse(saved['reference_effects']['qc']['passed'])
            self.assertIn('SFX_OVERDENSITY', [e['code'] for e in saved['reference_effects']['qc']['errors']])
            self.assertEqual(saved['reference_effects']['physical_gpu'], 'NOT_RUN')
            archive_path = bundle.finish(status='FAILED', error={'code': 'REFERENCE_EFFECTS_PREFLIGHT_FAILED',
                                                                 'scene_id': 'S001'})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('preflight.json')), saved)
                self.assertEqual(json.loads(archive.read('frame-audit.json')), [])
                self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'],
                                 'REFERENCE_EFFECTS_PREFLIGHT_FAILED')
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')

    def test_real_pipeline_collector_failure_preserves_its_errors_and_exports_effect_record(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle, Redactor
        inherited_failure = {'passed': False, 'gpu_draw': 'NOT_RUN', 'seconds': .25,
                             'checks': [{'name': 'Scene_JSON', 'passed': True},
                                        {'name': 'FFmpeg_command_capabilities', 'passed': False,
                                         'error_type': 'INJECTED_ENCODER_CAPABILITY_FAILURE'}],
                             'scenes': [{'scene_id': 'S001', 'passed': False,
                                         'checks': [{'name': 'native_geometry_camera_route_entity_all_frames',
                                                     'passed': False, 'error': 'INJECTED_NATIVE_PREFLIGHT_FAILURE'}]}]}
        def reject(project_dir, plan, diagnostic):
            diagnostic.write('preflight.json', inherited_failure)
            raise RuntimeError('COLLECT_ALL_PREFLIGHT_FAILED')
        sentinel = FunctionType(_render_must_not_start.__code__, dict(rendering.render_project.__globals__))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DiagnosticBundle(root, 'job_020abcdef015', self.after)
            with patch.object(rendering, 'render_project', sentinel), \
                    patch('engine.gpu_preflight.collect_all', side_effect=reject) as collect:
                with self.assertRaisesRegex(RuntimeError, '^COLLECT_ALL_PREFLIGHT_FAILED$'):
                    pipeline_stability.render_project(root, self.after, 'http://127.0.0.1:8000', diagnostic=bundle)
                collect.assert_called_once_with(root, self.after, bundle)
            saved = json.loads((bundle.root / 'preflight.json').read_text())
            for key, expected in inherited_failure.items():
                self.assertEqual(saved[key], expected)
            self.assertEqual(saved['reference_effects'], Redactor().clean(effects.diagnostic_record(self.after)))
            self.assertTrue(saved['reference_effects']['qc']['passed'])
            self.assertFalse(saved['passed'])
            archive_path = bundle.finish(status='FAILED', error={'code': 'COLLECT_ALL_PREFLIGHT_FAILED',
                                                                 'scene_id': 'S001'})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('preflight.json')), saved)
                self.assertEqual(json.loads(archive.read('frame-audit.json')), [])
                self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'],
                                 'COLLECT_ALL_PREFLIGHT_FAILED')
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')

    def test_source_report_retains_parent_records_and_diagnostic_plan_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = effects.record_source_report(root, self.after, {'passed': True, 'assets': [], 'errors': []})
            persisted = json.loads((root / 'source_report.json').read_text())
            self.assertEqual(result, persisted)
            self.assertEqual(persisted['visual_quality']['version'], 'v018')
            self.assertEqual(persisted['event_quality']['version'], 'v019')
            self.assertEqual(persisted['reference_effects']['version'], 'v020')
            self.assertEqual(persisted['renderer_version'], effects.project_renderer_version(self.after))
            self.assertEqual(json.loads((root / 'reference_effects_plan.json').read_text()), effects.diagnostic_record(self.after))
            previous = (root / 'source_report.json').read_bytes()
            previous_diagnostic = (root / 'reference_effects_plan.json').read_bytes()
            with self.assertRaises(FileExistsError):
                effects.record_source_report(root, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual((root / 'source_report.json').read_bytes(), previous)
            self.assertEqual((root / 'reference_effects_plan.json').read_bytes(), previous_diagnostic)

    def test_saved_plan_validates_in_fresh_gateway_with_all_camera_default_flags_off(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'approved.json'
            path.write_text(json.dumps(self.after))
            env = dict(os.environ, WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='v020',
                       WORLD_ENGINE_EVENT_QUALITY_VERSION='v019', WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                       WORLD_ENGINE_DIRECTION_VERSION='v013', WORLD_ENGINE_SECOND_EVENT_TEST='0',
                       WORLD_ENGINE_RETURN_WIDE_TEST='0', WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST='0')
            code = ('import json,sys;from engine.qa_planner import configure_qa_schema;'
                    'configure_qa_schema();from engine.schema import validate_plan;'
                    'result=validate_plan(json.load(open(sys.argv[1])));assert result["passed"],result;'
                    'assert result["reference_effects"]["version"]=="v020"')
            result = subprocess.run([sys.executable, '-c', code, str(path)], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_v020_deployment_selection_supports_explicit_off_exact_v019_plan(self):
        from engine.qa_planner import generate_deployment_plan
        with patch.dict(os.environ, {'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020'}):
            off = generate_deployment_plan(dict(self.raw, reference_effects=False))
            on = generate_deployment_plan(dict(self.raw, reference_effects=True))
        # Per-request IDs and request dictionaries are planner-generated;
        # the v020 OFF adapter itself is tested above for exact whole-plan identity.
        self.assertNotIn('reference_effects', off['metadata'])
        self.assertTrue(all('reference_effects' not in scene for scene in off['scenes']))
        self.assertEqual(off['scenes'], self.before['scenes'])
        self.assertEqual(off['gate'], self.before['gate'])
        self.assertEqual(on['metadata']['reference_effects']['version'], 'v020')
        self.assertTrue(effects.validate_effects(on)['passed'])


if __name__ == '__main__':
    unittest.main()
