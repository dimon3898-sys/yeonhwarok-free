"""Data-bound v021 micro beats over the certified v020 camera/material path.

Native tests measure planning and canvas commands; they do not claim NVIDIA
draws or rendered AFTER pixels. The approved sample is compiled source data,
not a reconstruction of a missing GPU diagnostic archive.
"""
from copy import deepcopy
from fractions import Fraction
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

from engine import story_progression as story
from engine.event_quality import ROOT
from engine.frame_grid import FrameGrid


V020_FROZEN = {
    'engine/reference_effects.py': '0df0d207772493269f748575dfd618d52d9dd0b8a886bd05d1712fe1d7214a87',
    'engine/reference_effects_backend.py': '9d260626b0fc96d85fd6eac5d651391b370afd5be5c6a9a761a44dd39a202eae',
    'web/reference_effects_adapter.js': 'cd52f405cac6e8707a1c7dc6aca46735ff32d0d2bfbb44215ccebbb0785d43e1',
    'web/render_reference_effects_earth.html': '31863216d72fb76c139cf49f01c99b23047e1cb9af2a2e7359b47b2f29c30e0a',
    'data/reference_effects_v020.json': '2df0563abca82d8f0c71311d4eeb66feb9769e810504fc9d9b2bbe26d06e168f',
    'web/reference_effects_v020.json': '2df0563abca82d8f0c71311d4eeb66feb9769e810504fc9d9b2bbe26d06e168f',
}


def _render_must_not_start(*args, **kwargs):
    raise AssertionError('Rejected admission must never start the original renderer')


class StoryProgression(unittest.TestCase):
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
            'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020',
            'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'legacy',
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
        cls.after = story.apply_progression(cls.before)

    def assert_rejected(self, plan, expected_code=None):
        from engine.schema import validate_plan
        result = story.validate_progression(plan)
        self.assertFalse(result['passed'], result)
        self.assertTrue(result['errors'], result)
        if expected_code:
            self.assertIn(expected_code, [error['code'] for error in result['errors']])
        self.assertFalse(validate_plan(plan)['passed'])

    def generic_scene(self, name='Seoul', *, fps=30, start=120, end=300,
                      label=True, total=720, text='DEPARTURE CONFIRMED'):
        """Author an independent semantic fixture using a real catalog point."""
        from engine.gis import resolve_location, verified_coordinate
        location = resolve_location(name)
        coordinate = deepcopy(location['coordinates'])
        coordinate['location_id'] = location['id']
        self.assertTrue(verified_coordinate(coordinate))
        clock = FrameGrid(fps)
        pose = dict(height=.2, tilt=0, yaw=0, bank=0, fov=48,
                    lon=coordinate['lon'], lat=coordinate['lat'],
                    target_lon=coordinate['lon'], target_lat=coordinate['lat'])
        event = dict(id='AUTHORED_STATE_A', kind='milestone_reveal', time=clock.seconds(start),
                     duration=clock.seconds(end-start), target_id=location['id'],
                     coordinates=coordinate, text=text, description=text,
                     role='variable', caused_by=None, meaningful=True, claim_id='FIXTURE_CLAIM')
        return dict(scene_id='GENERIC', duration=clock.seconds(total), frame_count=total,
                    camera_start=deepcopy(pose), camera_end=deepcopy(pose),
                    visual_events=[event],
                    text_events=[dict(id='T_AUTHORED_STATE_A', event_id=event['id'],
                                      text=text, coordinates=deepcopy(coordinate),
                                      start_time=clock.seconds(start), end_time=clock.seconds(end),
                                      role='status', priority=9)],
                    labels=[dict(text=name.upper(), role='city', coordinates=deepcopy(coordinate),
                                 start_time=0, end_time=clock.seconds(total))] if label else [],
                    direction=dict(locked_windows=[dict(start_frame=0, end_frame=total,
                                                       camera_key='camera_start')]),
                    routes=[], entities=[], sound_events=[])

    def test_off_is_exact_isolated_parent_plan_and_rejects_selected_input(self):
        original = deepcopy(self.before)
        off = story.apply_progression(self.before, enabled=False)
        self.assertEqual(off, original)
        self.assertEqual(self.before, original)
        self.assertIsNot(off, self.before)
        off['scenes'][0]['labels'][0]['text'] = 'isolated test mutation'
        self.assertEqual(self.before, original)
        with self.assertRaisesRegex(ValueError, 'OFF_REQUIRES_PARENT_PLAN'):
            story.apply_progression(self.after, enabled=False)

    def test_off_cache_renderer_and_parent_backend_command_are_identical(self):
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        from engine.reference_effects_backend import reference_effects_command
        assets, settings = {'assets': []}, quality_settings('HIGH')
        off = story.apply_progression(self.before, enabled=False)
        for old, new in zip(self.before['scenes'], off['scenes']):
            self.assertEqual(story.renderer_version(new), story.parent.renderer_version(old))
            self.assertEqual(scene_cache_key(new, assets, settings, story.renderer_version(new)),
                             scene_cache_key(old, assets, settings, story.parent.renderer_version(old)))
        self.assertEqual(story.project_renderer_version(off), story.parent.project_renderer_version(self.before))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(off['scenes'][0]))
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1:8000/static/render_production_earth.html']
            mapped = reference_effects_command(command)
            self.assertEqual(mapped[-1], 'http://127.0.0.1:8000/static/render_reference_effects_earth.html')

    def test_on_changes_only_own_selection_and_gate_over_full_v020_plan(self):
        from engine.schema import validate_plan
        plain = deepcopy(self.after)
        plain['metadata'].pop('story_progression')
        for scene in plain['scenes']:
            scene.pop('story_progression')
        plain.pop('gate')
        baseline = deepcopy(self.before)
        baseline.pop('gate')
        self.assertEqual(plain, baseline)
        self.assertTrue(story.validate_progression(self.after)['passed'])
        checked = validate_plan(self.after)
        self.assertTrue(checked['passed'], checked)
        self.assertEqual(checked['story_progression'], {'passed': True, 'version': 'v021'})
        self.assertEqual(checked['reference_effects'], {'passed': True, 'version': 'v020'})

    def test_on_cache_identity_is_separate_and_all_v020_runtime_hashes_are_frozen(self):
        from engine.rendering import scene_cache_key
        from engine.backends import quality_settings
        old, new = self.before['scenes'][0], self.after['scenes'][0]
        assets, settings = {'assets': []}, quality_settings('HIGH')
        self.assertNotEqual(story.renderer_version(old), story.renderer_version(new))
        self.assertNotEqual(scene_cache_key(old, assets, settings, story.renderer_version(old)),
                            scene_cache_key(new, assets, settings, story.renderer_version(new)))
        self.assertNotEqual(story.project_renderer_version(self.before), story.project_renderer_version(self.after))
        self.assertEqual(set(story.parent.SOURCES), set(V020_FROZEN))
        for name, expected in V020_FROZEN.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(new['story_progression']['parent_source_hashes'], V020_FROZEN)

    def test_native_all_720_frames_freeze_camera_material_and_off_canvas(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text(json.dumps(self.after))
            result = subprocess.run(['node', 'tools/test_story_progression_v021.mjs', str(path)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['frames'], 720)
        for key in ('camera_trajectory', 'material', 'wide', 'overlay_off', 'audio'):
            self.assertEqual(report[key], 'UNCHANGED', key)
        self.assertEqual(report['additional_texture_uploads'], 0)
        self.assertEqual(report['GPU'], 'NOT_RUN')
        self.assertEqual(report['pixel_quality'], 'NOT_RUN')
        self.assertGreater(report['changed_overlay_frames'], 0)
        self.assertLess(report['changed_overlay_frames'], 720)

    def test_backend_maps_only_page_preserves_transport_and_environment(self):
        from engine.story_progression_backend import story_progression_command, StoryProgressionBackend
        from engine.backends import CPULocalBackend
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(self.after['scenes'][0]))
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1:8000/static/render_production_earth.html?scene=S001#canvas',
                       '--width', '2160', '--height', '3840', '--fps', '30']
            previous, environment = list(command), dict(os.environ)
            expected = list(command)
            expected[expected.index('--url')+1] = 'http://127.0.0.1:8000/static/render_story_progression_earth.html?scene=S001#canvas'
            self.assertEqual(story_progression_command(command), expected)
            self.assertEqual(command, previous)
            progress = lambda event: None
            with patch.object(CPULocalBackend, 'run', return_value='retained transport') as transport:
                self.assertEqual(StoryProgressionBackend().run(command, ROOT, progress), 'retained transport')
                transport.assert_called_once_with(expected, ROOT, progress)
            self.assertEqual(dict(os.environ), environment)
            self.assertEqual(story_progression_command(['ffmpeg', '-version']), ['ffmpeg', '-version'])

    def test_backend_does_not_force_saved_parent_or_accept_tampered_receipt(self):
        from engine.story_progression_backend import story_progression_command
        bad = deepcopy(self.after['scenes'][0])
        bad['story_progression']['microbeats'][0]['primary_information'] = 'INVENTED DAMAGE'
        for selected in (self.before['scenes'][0], bad):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'scene.json'
                path.write_text(json.dumps(selected))
                with patch.dict(os.environ, {'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'v021'}):
                    with self.assertRaisesRegex(RuntimeError, 'STORY_PROGRESSION_SOURCE_MISMATCH'):
                        story_progression_command(['node', 'renderer', '--scene-json', str(path), '--url',
                                                   'http://127.0.0.1:8000/static/render_production_earth.html'])

    def test_exact_authored_suez_state_sequence_protects_camera_windows(self):
        beats = self.after['scenes'][0]['story_progression']['microbeats']
        self.assertEqual([(b['phase'], b['start_frame'], b['end_frame']) for b in beats], [
            ('EVENT_REVEAL', 180, 197), ('PERCEPTION', 197, 221),
            ('LOCATION_EMPHASIS', 221, 238), ('EVENT_STATE', 238, 330),
            ('STATE_CHANGE', 330, 347), ('PERCEPTION', 347, 360)])
        self.assertEqual([b['primary_information'] for b in beats], ['CANAL CLOSED']*4+['CANAL OPEN']*2)
        self.assertEqual([b['primary'] for b in beats], [False, False, True, False, False, False])
        self.assertEqual([b['pattern'] for b in beats], ['TEXT_REVEAL_HALO', 'NONE',
                         'LOCATION_TEXT_HALO', 'NONE', 'TEXT_REVEAL_HALO', 'NONE'])
        self.assertTrue(all(b['end_frame'] <= 360 for b in beats))

    def test_every_microbeat_retains_exact_authored_event_text_claim_and_coordinates(self):
        scene = self.after['scenes'][0]
        for beat in scene['story_progression']['microbeats']:
            source = next(e for e in scene['visual_events'] if e['id'] == beat['story_event_id'])
            text = next(t for t in scene['text_events'] if t['id'] == beat['text_event_id'])
            self.assertEqual(beat['primary_information'], source['text'])
            self.assertEqual(beat['primary_information'], text['text'])
            self.assertEqual(beat['coordinates'], source['coordinates'])
            self.assertEqual(beat['target_id'], source['target_id'])
            self.assertEqual(beat['claim_id'], source['claim_id'])
            self.assertEqual(beat['caused_by'], source['caused_by'])
            self.assertEqual(beat['source_ref']['event_sha256'], story._json_sha(source))
            self.assertEqual(beat['source_ref']['text_sha256'], story._json_sha(text))
            self.assertIn(source['id'], {'E002', 'E003'})

    def test_missing_bound_gis_never_becomes_a_canalline_or_invented_semantic_segment(self):
        scene = self.after['scenes'][0]
        self.assertEqual(scene['story_progression']['boundary']['status'], 'NOT_AVAILABLE')
        self.assertIsNone(scene['story_progression']['boundary']['geometry_ref'])
        for beat in scene['story_progression']['microbeats']:
            self.assertIsNone(beat['geometry_ref'])
            self.assertIsNone(beat['semantic_segment_ref'])
        for key, value, code in [('geometry_ref', {'coordinates': [[0, 0], [1, 1]]}, 'FAKE_GEOMETRY'),
                                 ('semantic_segment_ref', 'invented TTS sentence', 'UNSUPPORTED_STORY_EVENT')]:
            plan = deepcopy(self.after)
            plan['scenes'][0]['story_progression']['microbeats'][0][key] = value
            self.assert_rejected(plan, code)

    def test_singapore_has_no_authored_status_so_gets_no_status_microbeats(self):
        scene = self.after['scenes'][0]
        self.assertEqual([e['text'] for e in scene['visual_events'] if e['target_id'] == 'singapore'], ['', ''])
        self.assertFalse(any(b['target_id'] == 'singapore' for b in scene['story_progression']['microbeats']))
        self.assertEqual(scene['reference_effects'], self.before['scenes'][0]['reference_effects'])
        self.assertEqual(scene['labels'], self.before['scenes'][0]['labels'])

    def test_four_authored_domains_compile_without_suez_name_or_time_conditions(self):
        fixtures = [('SUEZ_CANAL', 'CANAL CLOSED'), ('Seoul', 'DEPARTURE CONFIRMED'),
                    ('France', 'REGION STATUS'), ('Tokyo', 'NETWORK STATUS')]
        for location, text in fixtures:
            with self.subTest(location=location):
                scene = self.generic_scene(location, start=120, end=300, text=text)
                original = deepcopy(scene)
                beats = story.compile_microbeats(scene)
                self.assertEqual(scene, original)
                self.assertEqual([(b['start_frame'], b['end_frame']) for b in beats],
                                 [(120, 137), (137, 161), (161, 178), (178, 300)])
                self.assertTrue(all(b['primary_information'] == text for b in beats))
                self.assertTrue(all(b['target_id'] == scene['visual_events'][0]['target_id'] for b in beats))
                self.assertEqual(scene['routes'], [])
                self.assertEqual(scene['entities'], [])
                self.assertEqual(scene['sound_events'], [])
        # A network fixture really contains two independent authored locations,
        # rather than changing only the name of a single sample. Its later
        # state must remain bound to its own Tokyo source and camera lock.
        network = self.generic_scene('Seoul', start=120, end=300, text='NETWORK A READY')
        destination = self.generic_scene('Tokyo', start=360, end=540, text='NETWORK B READY')
        event = destination['visual_events'][0]
        event['id'] = 'AUTHORED_STATE_B'
        event['caused_by'] = 'AUTHORED_STATE_A'
        text = destination['text_events'][0]
        text['id'], text['event_id'] = 'T_AUTHORED_STATE_B', event['id']
        network['visual_events'].append(event)
        network['text_events'].append(text)
        network['labels'].extend(destination['labels'])
        original = deepcopy(network)
        beats = story.compile_microbeats(network)
        self.assertEqual(network, original)
        self.assertEqual([b['story_event_id'] for b in beats], ['AUTHORED_STATE_A']*4+['AUTHORED_STATE_B']*4)
        self.assertEqual(beats[4]['start_frame'], 360)
        self.assertEqual(beats[-1]['end_frame'], 540)
        self.assertTrue(all(b['coordinates'] == event['coordinates'] for b in beats[4:]))
        self.assertTrue(all(b['caused_by'] == 'AUTHORED_STATE_A' for b in beats[4:]))
        self.assertEqual(network['routes'], [])

    def test_shifted_authored_times_shift_beats_without_moving_camera_or_scene(self):
        first = self.generic_scene(start=120, end=300)
        second = self.generic_scene(start=210, end=390)
        a, b = story.compile_microbeats(first), story.compile_microbeats(second)
        self.assertEqual([(v['start_frame']+90, v['end_frame']+90) for v in a],
                         [(v['start_frame'], v['end_frame']) for v in b])
        self.assertEqual(first['direction'], second['direction'])
        self.assertEqual(first['duration'], second['duration'])

    def test_short_lock_or_missing_location_omits_secondary_emphasis_not_read_time(self):
        for scene in (self.generic_scene(end=168), self.generic_scene(label=False)):
            original = deepcopy(scene)
            beats = story.compile_microbeats(scene)
            self.assertEqual(scene, original)
            self.assertEqual([b['phase'] for b in beats], ['EVENT_REVEAL', 'PERCEPTION'])
            self.assertEqual(beats[0]['end_frame']-beats[0]['start_frame'], 17)
            self.assertEqual(beats[-1]['end_frame'], round(scene['text_events'][0]['end_time']*30))
        scene = self.generic_scene()
        scene['direction']['locked_windows'][0]['end_frame'] = 168
        self.assertEqual(story.compile_microbeats(scene)[-1]['end_frame'], 168)
        self.assertEqual(scene['text_events'][0]['end_time'], 10.0)

    def test_fps_24_25_fractional_30_60_preserve_integer_authored_boundaries(self):
        for fps in (24, 25, Fraction(30000, 1001), 30, 60):
            with self.subTest(fps=str(fps)):
                scene = self.generic_scene(fps=fps)
                beats = story.compile_microbeats(scene, fps)
                expected_reveal = FrameGrid(fps).frames(Fraction(17, 30))
                expected_gap = FrameGrid(fps).frames(Fraction(24, 30))
                self.assertEqual(beats[0]['start_frame'], 120)
                self.assertEqual(beats[0]['end_frame'], 120+expected_reveal)
                self.assertEqual(beats[1]['end_frame'], 120+expected_reveal+expected_gap)
                self.assertEqual(beats[-1]['end_frame'], 300)
                self.assertTrue(all(type(b[k]) is int for b in beats for k in ('start_frame', 'end_frame')))
                for previous, following in zip(beats, beats[1:]):
                    self.assertEqual(previous['end_frame'], following['start_frame'])

    def test_invalid_fps_frames_and_unaligned_source_times_are_rejected(self):
        for key, value in [('duration', float('nan')), ('duration', 0), ('frame_count', True),
                           ('frame_count', 720.0), ('frame_count', -1)]:
            scene = self.generic_scene()
            scene[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                story.compile_microbeats(scene)
        for fps in (True, 0, -1, 'invalid', float('inf')):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                story.compile_microbeats(self.generic_scene(), fps)
        scene = self.generic_scene()
        scene['text_events'][0]['start_time'] += .01
        with self.assertRaisesRegex(ValueError, 'TIME_NOT_ON_FRAME_GRID'):
            story.compile_microbeats(scene)

    def test_unmatched_wording_target_coordinates_and_duplicate_source_bindings_fail(self):
        for field, value in [('event_id', 'nonexistent'), ('text', 'invented alternate message'),
                             ('coordinates', dict(lon=0, lat=0, source_id='invented', location_id='seoul'))]:
            scene = self.generic_scene()
            scene['text_events'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'UNSUPPORTED_STORY_EVENT'):
                story.compile_microbeats(scene)
        scene = self.generic_scene()
        scene['visual_events'][0]['target_id'] = 'invented_other_target'
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_STORY_EVENT'):
            story.compile_microbeats(scene)
        scene = self.generic_scene()
        scene['text_events'].append(deepcopy(scene['text_events'][0]))
        with self.assertRaisesRegex(ValueError, 'TEXT_PRIORITY_CONFLICT'):
            story.compile_microbeats(scene)

    def test_empty_nonstatus_text_is_not_promoted_into_an_event(self):
        for role, text in [('support', 'SUPPORT ONLY'), ('status', '')]:
            scene = self.generic_scene(text=text)
            scene['text_events'][0]['role'] = role
            self.assertEqual(story.compile_microbeats(scene), [])

    def test_reveal_outside_declared_lock_or_corrupt_camera_lock_fails(self):
        contiguous = self.generic_scene()
        contiguous['direction']['locked_windows'] = [
            dict(start_frame=0, end_frame=210, camera_key='camera_start'),
            dict(start_frame=210, end_frame=720, camera_key='camera_start')]
        original = deepcopy(contiguous)
        beats = story.compile_microbeats(contiguous)
        self.assertEqual(contiguous, original)
        self.assertEqual([(b['start_frame'], b['end_frame']) for b in beats],
                         [(120, 137), (137, 161), (161, 178), (178, 300)])
        # A status crosses the authoring-window boundary without a camera
        # change. Both source references must survive the merged lock, and
        # its event state must not be truncated at frame 210.
        expected_lock = dict(start_frame=0, end_frame=720, camera_key='camera_start',
                             source_paths=['direction.locked_windows[0]', 'direction.locked_windows[1]'])
        self.assertTrue(all(b['camera_lock_ref'] == expected_lock for b in beats))
        contiguous['story_progression'] = story._selection(contiguous, 30)
        result = story.progression_qc(contiguous)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['errors'], [])
        cases = [dict(start_frame=130, end_frame=720, camera_key='FIXED'),
                 dict(start_frame=True, end_frame=720, camera_key='FIXED'),
                 dict(start_frame=0, end_frame=720, camera_key=''),
                 dict(start_frame=0, end_frame=720, camera_key='FIXED', allow_motion=True)]
        for lock in cases:
            scene = self.generic_scene()
            scene['direction']['locked_windows'] = [lock]
            with self.subTest(lock=lock), self.assertRaisesRegex(ValueError, 'CAMERA_CHANGED_DURING_EVENT_VIEW'):
                story.compile_microbeats(scene)

    def test_scene_camera_quality_and_source_mutations_invalidate_saved_selection(self):
        changes = [('camera', lambda s: s['camera_start'].update(fov=63), 'CAMERA_CHANGED_DURING_EVENT_VIEW'),
                   ('quality', lambda s: s['event_quality'].update(version='v999'), 'STORY_PROGRESSION_VISUAL_QUALITY_CHANGED'),
                   ('source', lambda s: s['visual_events'][1].update(claim_id='invented'), 'UNSUPPORTED_STORY_EVENT')]
        for name, change, code in changes:
            plan = deepcopy(self.after)
            change(plan['scenes'][0])
            with self.subTest(change=name):
                self.assert_rejected(plan, code)

    def test_selection_source_profile_parent_hash_url_and_unknown_fields_reject(self):
        cases = [('source_hashes', {}), ('parent_source_hashes', {}), ('profile_sha256', '0'*64),
                 ('profile_url', 'https://untrusted.example/profile.json'), ('profile_url', '/static/../profile.json'),
                 ('version', 'v999'), ('source_sha256', '0'*64), ('force_gpu_pass', True)]
        for field, value in cases:
            plan = deepcopy(self.after)
            plan['scenes'][0]['story_progression'][field] = value
            with self.subTest(field=field):
                self.assert_rejected(plan)
        plan = deepcopy(self.after)
        plan['metadata']['story_progression']['unknown_override'] = True
        self.assert_rejected(plan)

    def test_microbeat_tampering_never_creates_content_pattern_geometry_or_timing(self):
        cases = [('story_event_id', 'invented'), ('text_event_id', 'invented'),
                 ('primary_information', 'invented damage: 99 ships'), ('target_id', 'Tokyo'),
                 ('coordinates', {'lon': 0, 'lat': 0}), ('claim_id', 'fake_claim'),
                 ('caused_by', 'fake_event'), ('start_frame', 181),
                 ('source_ref', {}), ('pattern', 'PARTICLES'), ('repeated_pulse', True)]
        for field, value in cases:
            plan = deepcopy(self.after)
            plan['scenes'][0]['story_progression']['microbeats'][0][field] = value
            with self.subTest(field=field):
                self.assert_rejected(plan)

    def test_density_continuous_effect_conflicting_status_and_frame_types_fail(self):
        cases = []
        plan = deepcopy(self.after)
        beat = plan['scenes'][0]['story_progression']['microbeats'][0]
        beat.update(primary=True, pattern='LOCATION_TEXT_HALO')
        cases.append(('TOO_MANY_PRIMARY_EFFECTS', plan))
        plan = deepcopy(self.after)
        plan['scenes'][0]['story_progression']['microbeats'][0]['end_frame'] = 210
        cases.append(('CONTINUOUS_EFFECT', plan))
        plan = deepcopy(self.after)
        duplicate = deepcopy(plan['scenes'][0]['story_progression']['microbeats'][0])
        duplicate['id'] += '_DUPLICATE'
        plan['scenes'][0]['story_progression']['microbeats'].append(duplicate)
        cases.append(('TEXT_PRIORITY_CONFLICT', plan))
        for code, plan in cases:
            with self.subTest(code=code):
                self.assert_rejected(plan, code)
        for field, value in [('start_frame', True), ('start_frame', 180.0), ('end_frame', 180),
                             ('end_frame', 721), ('end_frame', float('nan'))]:
            plan = deepcopy(self.after)
            plan['scenes'][0]['story_progression']['microbeats'][0][field] = value
            with self.subTest(field=field, value=value):
                self.assert_rejected(plan)

    def test_profile_rejects_unknown_nonfinite_and_equal_value_wrong_numeric_types(self):
        original = story._profile()
        cases = []
        for field, value in [('version', 'v020'), ('reference_sha256', '0'*64), ('unknown_override', True)]:
            item = deepcopy(original)
            item[field] = value
            cases.append((field, item))
        for section, field, value in [('timing', 'text_reveal_frames', 17.0),
                                      ('limits', 'max_primary', True),
                                      ('typography', 'event_size_px', 64.0),
                                      ('typography', 'event_opacity', float('nan'))]:
            item = deepcopy(original)
            item[section][field] = value
            cases.append((field, item))
        for field, value in [('max_frames', 17.0), ('primary', 0)]:
            item = deepcopy(original)
            item['patterns']['TEXT_REVEAL_HALO'][field] = value
            cases.append(('pattern_'+field, item))
        item = deepcopy(original)
        item['evidence'][0]['start_frame'] = 289.0
        cases.append(('evidence_frame', item))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            for name, item in cases:
                payload = json.dumps(item)
                (root / 'data/story_progression_v021.json').write_text(payload)
                (root / 'web/story_progression_v021.json').write_text(payload)
                with self.subTest(name=name), patch.object(story, 'ROOT', root):
                    with self.assertRaises(ValueError):
                        story._profile()

    def test_served_profile_bytes_must_match_and_hierarchy_does_not_add_new_font(self):
        original = (ROOT / 'data/story_progression_v021.json').read_bytes()
        self.assertEqual(original, (ROOT / 'web/story_progression_v021.json').read_bytes())
        profile = story._profile()
        self.assertEqual(profile['typography'], dict(event_size_px=64, event_weight=400,
                        event_opacity=.98, location_opacity=.60))
        self.assertFalse(profile['design']['shader_changes'])
        self.assertEqual(profile['design']['texture_uploads'], 0)
        self.assertEqual(profile['limits']['max_added_sfx'], 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'web').mkdir()
            (root / 'data/story_progression_v021.json').write_bytes(original)
            (root / 'web/story_progression_v021.json').write_bytes(b'{"version":"v999"}')
            with patch.object(story, 'ROOT', root), self.assertRaisesRegex(ValueError, 'SERVED_PROFILE_MISMATCH'):
                story._profile()

    def test_original_schema_camera_and_unknown_fields_still_fail(self):
        from engine.schema import validate_plan
        for change in [{'camera_start': dict(self.after['scenes'][0]['camera_start'], fov=5)},
                       {'unvalidated_override': True}]:
            plan = deepcopy(self.after)
            plan['scenes'][0].update(change)
            self.assertFalse(validate_plan(plan)['passed'])

    def test_explicit_boolean_selection_requires_approved_v020_parent(self):
        for value in (1, 'true', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'SELECTION_INVALID'):
                story.apply_progression(self.before, enabled=value)
        plan = deepcopy(self.before)
        plan['metadata'].pop('reference_effects')
        for scene in plan['scenes']:
            scene.pop('reference_effects')
        with self.assertRaisesRegex(ValueError, 'V020_BASELINE_REQUIRED'):
            story.apply_progression(plan)

    def test_audio_narration_route_entity_text_and_all_semantics_are_unchanged(self):
        self.assertEqual(self.after['options'], self.before['options'])
        for old, new in zip(self.before['scenes'], self.after['scenes']):
            for field in ('visual_events', 'text_events', 'labels', 'narration', 'narration_event_ids',
                          'claim_ids', 'routes', 'entities', 'sound_events', 'geographic_targets'):
                self.assertEqual(new.get(field), old.get(field), field)
        report = story.validate_progression(self.after)
        self.assertEqual(report['added_sfx'], 0)
        self.assertEqual(report['added_textures'], 0)
        self.assertEqual(report['physical_gpu'], 'NOT_RUN')

    def test_diagnostic_24_second_timeline_covers_each_frame_including_clean_none(self):
        scene = self.after['scenes'][0]
        rows = story.progression_timeline(scene)
        self.assertEqual(rows[0]['start_frame'], 0)
        self.assertEqual(rows[-1]['end_frame'], 720)
        self.assertEqual(sum(r['frame_count'] for r in rows), 720)
        for left, right in zip(rows, rows[1:]):
            self.assertEqual(left['end_frame'], right['start_frame'])
        for frame in range(720):
            self.assertEqual(sum(r['start_frame'] <= frame < r['end_frame'] for r in rows), 1)
        for row in rows:
            self.assertEqual(row['frame_count'], row['end_frame']-row['start_frame'])
            self.assertAlmostEqual(row['start_seconds'], row['start_frame']/30)
            self.assertEqual(row['added_sfx'], 'NONE')
            if 'ZOOM' in row['camera_state']:
                self.assertEqual(row['story_state'], 'NONE')
                self.assertEqual(row['visual_effect'], 'NONE')
        self.assertTrue(any(r['story_state'] == 'NONE' for r in rows))
        self.assertTrue(any(r['story_state'] == 'EVENT_STATE' and r['visual_effect'] == 'NONE' for r in rows))
        report = story.diagnostic_record(self.after)
        self.assertEqual(report['scenes'][0]['timeline'], rows)
        self.assertEqual(report['scenes'][0]['microbeats'], scene['story_progression']['microbeats'])
        self.assertTrue(report['qc']['passed'])
        self.assertEqual(report['physical_gpu'], 'NOT_RUN')
        self.assertIn('NO_ADDED_SFX_OR_TTS', report['audio'])

    def test_bundle_success_preserves_scene_and_durable_nested_story_receipt(self):
        from engine.gpu_bundle import DiagnosticBundle, Redactor
        report = story.diagnostic_record(self.after)
        with tempfile.TemporaryDirectory() as directory:
            bundle = DiagnosticBundle(Path(directory), 'job_021abcdef001', self.after)
            scene_dir = bundle.root / 'S001'
            scene_dir.mkdir()
            (scene_dir / 'renderer-diagnostics.json').write_text(json.dumps({'story_progression': report}))
            receipt = dict(scene_id='S001', frame_index=221, source='UNIT_PROTOCOL_FIXTURE', errors=[],
                           effectLayer=dict(version='v020', storyProgression=dict(version='v021',
                             microbeat_id='SP_E002_LOCATION_EMPHASIS', physical_gpu='NOT_RUN')))
            (scene_dir / 'frame-audit.jsonl').write_text(json.dumps(receipt)+'\n')
            archive_path = bundle.finish(status='SUCCESS', result={'qc': {'passed': True, 'gpu': 'NOT_RUN'}, 'outputs': {}})
            with zipfile.ZipFile(archive_path) as archive:
                selected = json.loads(archive.read('S001.json'))['story_progression']
                self.assertEqual(selected, Redactor().clean(self.after['scenes'][0]['story_progression']))
                self.assertEqual(json.loads(archive.read('frame-audit.json'))[0], receipt)
                records = json.loads(archive.read('renderer-diagnostics.json'))
                saved = next(r['record']['story_progression'] for r in records if 'story_progression' in r['record'])
                self.assertEqual(saved, Redactor().clean(report))
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')

    def test_real_pipeline_story_admission_failure_exports_qc_before_collector_or_render(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle
        plan = deepcopy(self.after)
        plan['scenes'][0]['story_progression']['microbeats'][0]['geometry_ref'] = 'fake canal'
        sentinel = FunctionType(_render_must_not_start.__code__, dict(rendering.render_project.__globals__))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DiagnosticBundle(root, 'job_021abcdef002', plan)
            with patch.object(rendering, 'render_project', sentinel), patch('engine.gpu_preflight.collect_all') as collect:
                with self.assertRaisesRegex(RuntimeError, '^STORY_PROGRESSION_PREFLIGHT_FAILED$'):
                    pipeline_stability.render_project(root, plan, 'http://127.0.0.1:8000', diagnostic=bundle)
                collect.assert_not_called()
            saved = json.loads((bundle.root / 'preflight.json').read_text())
            self.assertFalse(saved['passed'])
            self.assertFalse(saved['story_progression']['qc']['passed'])
            self.assertIn('FAKE_GEOMETRY', [e['code'] for e in saved['story_progression']['qc']['errors']])
            archive_path = bundle.finish(status='FAILED', error={'code': 'STORY_PROGRESSION_PREFLIGHT_FAILED', 'scene_id': 'S001'})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('preflight.json')), saved)
                self.assertEqual(json.loads(archive.read('frame-audit.json')), [])
                self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'], 'STORY_PROGRESSION_PREFLIGHT_FAILED')
                self.assertEqual(json.loads(archive.read('gpu-diagnostics.json'))['measurement_status'], 'NOT_AVAILABLE')
        # Even the evidence writer failing must not replace the rejected
        # story invariant with a storage exception or start the renderer.
        for index, storage_error in enumerate((OSError('INJECTED_DIAGNOSTIC_STORAGE_FAILURE'),
                                                ValueError('INJECTED_DIAGNOSTIC_SERIALIZATION_FAILURE'))):
            with self.subTest(error_type=type(storage_error).__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                bundle = DiagnosticBundle(root, f'job_021abcdef02{index}', plan)
                original_write = bundle.write
                def write_with_preflight_failure(name, value):
                    if name == 'preflight.json':
                        raise storage_error
                    return original_write(name, value)
                with patch.object(rendering, 'render_project', sentinel), \
                        patch('engine.gpu_preflight.collect_all') as collect, \
                        patch.object(bundle, 'write', side_effect=write_with_preflight_failure) as writer:
                    with self.assertRaisesRegex(RuntimeError, '^STORY_PROGRESSION_PREFLIGHT_FAILED$'):
                        pipeline_stability.render_project(root, plan, 'http://127.0.0.1:8000', diagnostic=bundle)
                    collect.assert_not_called()
                    preflight_calls = [call for call in writer.call_args_list if call.args[0] == 'preflight.json']
                    self.assertEqual(len(preflight_calls), 1)
                # Restore the storage method before using the real, stable
                # ZIP finalizer. Its original PRIMARY_ERROR remains intact.
                archive_path = bundle.finish(status='FAILED', error={
                    'code': 'STORY_PROGRESSION_PREFLIGHT_FAILED', 'scene_id': 'S001'})
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'],
                                     'STORY_PROGRESSION_PREFLIGHT_FAILED')
                    self.assertEqual(json.loads(archive.read('frame-audit.json')), [])

    def test_real_collector_failure_preserves_original_error_and_story_evidence(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle, Redactor
        inherited = {'passed': False, 'gpu_draw': 'NOT_RUN', 'checks': [],
                     'scenes': [{'scene_id': 'S001', 'passed': False, 'error': 'INJECTED_NATIVE_PREFLIGHT_FAILURE'}]}
        def reject(directory, plan, diagnostic):
            diagnostic.write('preflight.json', inherited)
            raise RuntimeError('COLLECT_ALL_PREFLIGHT_FAILED')
        sentinel = FunctionType(_render_must_not_start.__code__, dict(rendering.render_project.__globals__))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DiagnosticBundle(root, 'job_021abcdef003', self.after)
            with patch.object(rendering, 'render_project', sentinel), patch('engine.gpu_preflight.collect_all', side_effect=reject) as collect:
                with self.assertRaisesRegex(RuntimeError, '^COLLECT_ALL_PREFLIGHT_FAILED$'):
                    pipeline_stability.render_project(root, self.after, 'http://127.0.0.1:8000', diagnostic=bundle)
                collect.assert_called_once_with(root, self.after, bundle)
            saved = json.loads((bundle.root / 'preflight.json').read_text())
            for key, value in inherited.items():
                self.assertEqual(saved[key], value)
            self.assertEqual(saved['story_progression'], Redactor().clean(story.diagnostic_record(self.after)))
            archive_path = bundle.finish(status='FAILED', error={'code': 'COLLECT_ALL_PREFLIGHT_FAILED', 'scene_id': 'S001'})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('preflight.json')), saved)
                self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'], 'COLLECT_ALL_PREFLIGHT_FAILED')

    def test_source_report_keeps_parent_versions_hashes_and_exclusive_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = story.record_source_report(root, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual(report, json.loads((root / 'source_report.json').read_text()))
            for key, version in [('visual_quality', 'v018'), ('event_quality', 'v019'),
                                 ('reference_effects', 'v020'), ('story_progression', 'v021')]:
                self.assertEqual(report[key]['version'], version)
            self.assertEqual(report['renderer_version'], story.project_renderer_version(self.after))
            self.assertEqual(json.loads((root / 'story_progression_plan.json').read_text()), story.diagnostic_record(self.after))
            original = (root / 'story_progression_plan.json').read_bytes()
            with self.assertRaises(FileExistsError):
                story.record_source_report(root, self.after, {'passed': True, 'assets': [], 'errors': []})
            self.assertEqual((root / 'story_progression_plan.json').read_bytes(), original)

    def test_planner_selection_is_versioned_and_explicit_off_preserves_v020(self):
        from engine.qa_planner import generate_deployment_plan
        with patch.dict(os.environ, {'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'legacy'}):
            quality_baseline = generate_deployment_plan(dict(self.raw, reference_effects=False))
        with patch.dict(os.environ, {'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'v021'}):
            selected = generate_deployment_plan(self.raw)
            off = generate_deployment_plan(dict(self.raw, story_progression=False))
            parent_off = [generate_deployment_plan(dict(self.raw, reference_effects=False, **selection))
                          for selection in ({}, {'story_progression': False}, {'story_progression': True})]
        self.assertEqual(off, self.before)
        self.assertEqual(selected, self.after)
        self.assertEqual(off['metadata']['reference_effects']['version'], 'v020')
        self.assertNotIn('story_progression', off['metadata'])
        # Selecting the dependent default must not force a parent layer that
        # the request explicitly disabled, nor alter its v019 gate or content.
        self.assertEqual(quality_baseline['metadata']['event_quality']['version'], 'v019')
        self.assertTrue(quality_baseline['gate']['passed'])
        for plan in parent_off:
            self.assertEqual(plan, quality_baseline)
            self.assertNotIn('reference_effects', plan['metadata'])
            self.assertNotIn('story_progression', plan['metadata'])
            self.assertTrue(all('reference_effects' not in scene and 'story_progression' not in scene
                                for scene in plan['scenes']))

    def test_saved_v021_plan_validates_in_fresh_gateway_with_camera_defaults_off(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'approved.json'
            path.write_text(json.dumps(self.after))
            environment = dict(os.environ, WORLD_ENGINE_STORY_PROGRESSION_VERSION='v021',
                               WORLD_ENGINE_REFERENCE_EFFECTS_VERSION='v020',
                               WORLD_ENGINE_EVENT_QUALITY_VERSION='v019', WORLD_ENGINE_VISUAL_QUALITY_VERSION='v018',
                               WORLD_ENGINE_DIRECTION_VERSION='v013', WORLD_ENGINE_SECOND_EVENT_TEST='0',
                               WORLD_ENGINE_RETURN_WIDE_TEST='0', WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST='0')
            code = ('import json,sys;from engine.qa_planner import configure_qa_schema;'
                    'configure_qa_schema();from engine.schema import validate_plan;'
                    'r=validate_plan(json.load(open(sys.argv[1])));assert r["passed"],r;'
                    'assert r["story_progression"]["version"]=="v021";'
                    'assert r["reference_effects"]["version"]=="v020"')
            result = subprocess.run([sys.executable, '-c', code, str(path)], cwd=ROOT, env=environment,
                                    capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
