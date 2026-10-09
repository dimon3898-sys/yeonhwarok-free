"""Independent v022 admission and deployment contracts; no NVIDIA draw claims."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import FunctionType
import unittest
from unittest.mock import patch
import zipfile

from engine import infographic_contract as infographic
from engine.infographic_planner import generate_infographic_qa, parent_qa_plan


def _never_render(*args, **kwargs):
    raise AssertionError('Rejected preflight must not start the original renderer')


class InfographicIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        saved = (schema.validate_plan, gpu_preflight.validate_plan,
                 schema.SCHEMA_PATH, visibility.TOOL)
        def restore():
            schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = saved
        cls.addClassCleanup(restore)
        environment = patch.dict(os.environ, {
            'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
            'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019',
            'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020',
            'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'v021',
            'WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION': 'v022',
            'WORLD_ENGINE_DIRECTION_VERSION': 'v013',
            'WORLD_ENGINE_SECOND_EVENT_TEST': '1',
            'WORLD_ENGINE_RETURN_WIDE_TEST': '0',
            'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST': '0',
        })
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       quality='HIGH', pace='FAST_PLUS', qa_mode=True,
                       tts=False, subtitles=False, bgm=True, sfx=True)
        cls.parent = parent_qa_plan(cls.raw)
        cls.selected = generate_infographic_qa(cls.raw)

    def test_new_deployment_default_does_not_migrate_explicit_old_profile(self):
        from engine.qa_planner import generate_deployment_plan
        new = generate_deployment_plan(self.raw)
        self.assertTrue(infographic.validate_infographic(new)['passed'])
        self.assertTrue(any(s['infographic']['events'] for s in new['scenes']))
        old = generate_deployment_plan({**self.raw, 'direction_profile':
                                       'SECOND_EVENT_ADAPTIVE_WIDE_TEST'})
        self.assertNotIn('infographic', old['metadata'])
        for before, after in zip(old['scenes'], new['scenes']):
            self.assertNotIn('infographic', before)
            self.assertEqual(infographic.parent._camera_snapshot(after),
                             infographic.parent._camera_snapshot(before))
            self.assertEqual(infographic.parent._quality_snapshot(after),
                             infographic.parent._quality_snapshot(before))
            self.assertEqual(infographic.parent._source_snapshot(after),
                             infographic.parent._source_snapshot(before))

    def test_context_persists_without_turning_country_into_canal_closure(self):
        selection = self.selected['scenes'][0]['infographic']
        events = {e['story_source_ref']['visual_event_id']: e for e in selection['events']}
        country = [l for l in selection['geometry_layers'] if l['geometry_ref'] == 'COUNTRY_EGY']
        self.assertEqual(len(country), 1)
        self.assertEqual(country[0]['start_frame'], events['E001']['start_frame'])
        self.assertEqual(country[0]['end_frame'], events['E003']['end_frame'])
        self.assertEqual(country[0]['primary_until_frame'], events['E001']['end_frame'])
        self.assertEqual(country[0]['state_after'], 'LOCATION')
        self.assertNotEqual(country[0]['state_after'], events['E002']['state_after'])
        canal = [l for l in selection['geometry_layers']
                 if l['geometry_ref'] in {'CANAL_SUEZ_RIVER_NE10M', 'CANAL_SUEZ_LAKE_NE10M'}]
        self.assertEqual({l['state_after'] for l in canal}, {'CLOSED', 'OPEN'})
        for l in canal:
            source = events['E002'] if l['state_after'] == 'CLOSED' else events['E003']
            self.assertEqual((l['start_frame'], l['end_frame']),
                             (source['start_frame'], source['end_frame']))
        marker = next(m for m in selection['markers'] if m['geometry_ref'] == 'LOCATION_SUEZ_CANAL')
        initial_label = next(l for l in selection['labels'] if l['event_id'] == events['E001']['id'])
        self.assertEqual(marker['end_frame'], events['E003']['end_frame'])
        self.assertGreater(marker['end_frame'], initial_label['end_frame'])
        self.assertGreater(initial_label['start_frame'], marker['start_frame'])
        self.assertLessEqual(marker['intro_end_frame'], initial_label['start_frame'])

    def test_off_returns_exact_isolated_parent_and_same_renderer_cache(self):
        from engine.backends import quality_settings
        from engine.rendering import scene_cache_key
        before = deepcopy(self.parent)
        # A single actual parent instance avoids comparing unrelated planner
        # timestamps and proves the complete OFF value, not selected fields.
        with patch('engine.infographic_planner.parent_qa_plan', return_value=self.parent):
            off = generate_infographic_qa({**self.raw, 'map_infographic': False})
        self.assertEqual(off, before)
        self.assertEqual(self.parent, before)
        self.assertIsNot(off, self.parent)
        settings, assets = quality_settings('HIGH'), {'assets': []}
        for old, scene in zip(self.parent['scenes'], off['scenes']):
            old_version = infographic.parent.renderer_version(old)
            self.assertEqual(infographic.renderer_version(scene), old_version)
            self.assertEqual(scene_cache_key(scene, assets, settings, infographic.renderer_version(scene)),
                             scene_cache_key(old, assets, settings, old_version))
        off['scenes'][0]['labels'][0]['text'] = 'isolated mutation'
        self.assertEqual(self.parent, before)

    def test_on_preserves_all_parent_data_and_input_without_retiming(self):
        before = deepcopy(self.parent)
        with patch('engine.infographic_planner.parent_qa_plan', return_value=self.parent):
            selected = generate_infographic_qa(self.raw)
        restored = deepcopy(selected)
        restored['metadata'].pop('infographic')
        for scene in restored['scenes']:
            scene.pop('infographic')
        restored['gate'] = deepcopy(before['gate'])
        self.assertEqual(restored, before)
        self.assertEqual(self.parent, before)
        self.assertEqual(selected['metadata']['frame_grid'], before['metadata']['frame_grid'])
        self.assertFalse(selected['options']['tts'])
        self.assertFalse(selected['options']['subtitles'])

    def test_backend_maps_only_checked_page_and_keeps_transport_arguments(self):
        from engine.infographic_backend import infographic_command, InfographicBackend
        from engine.backends import CPULocalBackend
        self.assertIs(InfographicBackend.__mro__[1], CPULocalBackend)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text(json.dumps(self.selected['scenes'][0]))
            command = ['node', 'unchanged-renderer', '--scene-json', str(path),
                       '--url', 'http://127.0.0.1:8000/static/render_production_earth.html?unchanged=1',
                       '--browser', '/approved/chromium-wrapper', '--gpu-profile', 'nvidia-vulkan',
                       '--output', str(Path(directory) / 'output.mp4')]
            mapped = infographic_command(command)
            url_index = command.index('--url') + 1
            self.assertEqual(mapped[url_index],
                             'http://127.0.0.1:8000/static/render_infographic_earth.html?unchanged=1')
            self.assertEqual(mapped[:url_index], command[:url_index])
            self.assertEqual(mapped[url_index + 1:], command[url_index + 1:])
            self.assertNotEqual(mapped, command)
            for page in ['/static/unknown-renderer.html', '/not-static/render_production_earth.html']:
                with self.subTest(page=page):
                    bad = list(command)
                    bad[url_index] = 'http://127.0.0.1:8000' + page
                    with self.assertRaises(RuntimeError):
                        infographic_command(bad)

    def test_backend_rejects_forged_source_and_camera_even_with_edited_receipts(self):
        from engine.infographic_backend import infographic_command
        mutations = {
            'geometry': lambda s: s['infographic']['geometries'][0]['coordinates'].append([0, 0]),
            'camera': lambda s: s['camera_start'].__setitem__('fov', s['camera_start']['fov'] + 1),
            'event text': lambda s: s['infographic']['events'][0]['text'].__setitem__('location_label', 'INVENTED LOCATION'),
            'unknown effect': lambda s: s['infographic'].__setitem__('unverified_effect', 'explosion'),
            'real but wrong target': lambda s: s['infographic']['events'][0].__setitem__('location_point_ref', 'LOCATION_SEOUL'),
            'country closure substitution': lambda s: s['infographic']['events'][1].__setitem__('target_geometry_refs', ['COUNTRY_EGY']),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            command = ['node', 'renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1:8000/static/render_production_earth.html']
            for description, mutate in mutations.items():
                with self.subTest(description=description):
                    scene = deepcopy(self.selected['scenes'][0])
                    mutate(scene)
                    # Updating a self-proclaimed hash cannot authorize camera
                    # drift or manufacture geometry/event source data.
                    if description == 'camera':
                        scene['infographic']['parent_camera_sha256'] = infographic.parent._json_sha(
                            infographic.parent._camera_snapshot(scene))
                    path.write_text(json.dumps(scene))
                    with self.assertRaisesRegex(RuntimeError, 'SOURCE_MISMATCH'):
                        infographic_command(command)

    def test_rejected_admission_survives_preflight_writer_failure(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle
        plan = deepcopy(self.selected)
        plan['scenes'][0]['infographic']['events'][0]['text']['location_label'] = 'INVENTED LOCATION'
        sentinel = FunctionType(_never_render.__code__, dict(rendering.render_project.__globals__))
        for storage_error in (None, OSError('injected storage failure'), ValueError('injected serialization failure')):
            with self.subTest(error=storage_error), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                bundle = DiagnosticBundle(root, 'job_022abcdef001', plan)
                real_write = bundle.write
                def writer(name, value):
                    if storage_error is not None and name == 'preflight.json':
                        raise storage_error
                    return real_write(name, value)
                with patch.object(rendering, 'render_project', sentinel), \
                        patch('engine.gpu_preflight.collect_all') as collector, \
                        patch.object(bundle, 'write', side_effect=writer):
                    with self.assertRaisesRegex(RuntimeError, '^INFOGRAPHIC_PREFLIGHT_FAILED$'):
                        pipeline_stability.render_project(root, plan, 'http://127.0.0.1:8000', diagnostic=bundle)
                    collector.assert_not_called()
                if storage_error is None:
                    saved = json.loads((bundle.root / 'preflight.json').read_text())
                    self.assertFalse(saved['passed'])
                    self.assertFalse(saved['map_infographic']['qc']['passed'])
                archive_path = bundle.finish(status='FAILED', error={
                    'code': 'INFOGRAPHIC_PREFLIGHT_FAILED', 'scene_id': 'S001'})
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'],
                                     'INFOGRAPHIC_PREFLIGHT_FAILED')
                    self.assertEqual(json.loads(archive.read('frame-audit.json')), [])

    def test_collector_failure_retains_original_cause_and_selected_evidence(self):
        from engine import rendering, pipeline_stability
        from engine.gpu_bundle import DiagnosticBundle, Redactor
        inherited = dict(passed=False, gpu_draw='NOT_RUN', scenes=[dict(
            scene_id='S001', passed=False, error='INJECTED_STATIC_PREFLIGHT_FAILURE')])
        def reject(directory, plan, diagnostic):
            diagnostic.write('preflight.json', inherited)
            raise RuntimeError('COLLECT_ALL_PREFLIGHT_FAILED')
        sentinel = FunctionType(_never_render.__code__, dict(rendering.render_project.__globals__))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DiagnosticBundle(root, 'job_022abcdef002', self.selected)
            with patch.object(rendering, 'render_project', sentinel), \
                    patch('engine.gpu_preflight.collect_all', side_effect=reject):
                with self.assertRaisesRegex(RuntimeError, '^COLLECT_ALL_PREFLIGHT_FAILED$'):
                    pipeline_stability.render_project(root, self.selected, 'http://127.0.0.1:8000', diagnostic=bundle)
            saved = json.loads((bundle.root / 'preflight.json').read_text())
            for key, value in inherited.items():
                self.assertEqual(saved[key], value)
            self.assertEqual(saved['map_infographic'], Redactor().clean(infographic.diagnostic_record(self.selected)))
            archive_path = bundle.finish(status='FAILED', error={
                'code': 'COLLECT_ALL_PREFLIGHT_FAILED', 'scene_id': 'S001'})
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read('preflight.json')), saved)
                self.assertEqual(json.loads(archive.read('failed-invariant.json'))['PRIMARY_ERROR'],
                                 'COLLECT_ALL_PREFLIGHT_FAILED')
                self.assertEqual(json.loads(archive.read('frame-audit.json')), [])

    def test_new_qc_preserves_technical_failures_and_delegates_legacy_exactly(self):
        from engine import infographic_qc
        original = dict(passed=False, failures=['FROZEN_INTERVAL', 'WEBGL_ERROR', 'FRAME_SIZE_INVALID'],
                        decoded_video='checked', audio='checked')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('engine.qc.run_qc', return_value=original) as technical, \
                    patch('engine.infographic_qc.audit_map_state', return_value=dict(passed=True, errors=[])), \
                    patch('engine.second_event_qc.camera_qc', return_value=dict(passed=True, failures=[])):
                selected = infographic_qc.run_qc(root / 'video.mp4', self.selected, [], root / 'selected',
                                               ffmpeg_verified=True)
                self.assertFalse(selected['passed'])
                self.assertEqual(selected['failures'], ['FRAME_SIZE_INVALID', 'WEBGL_ERROR'])
                self.assertEqual(selected['legacy_pacing_not_applicable'], ['FROZEN_INTERVAL'])
                self.assertEqual(original['failures'], ['FROZEN_INTERVAL', 'WEBGL_ERROR', 'FRAME_SIZE_INVALID'])
                technical.assert_called_once_with(root / 'video.mp4', self.selected, [],
                                                  root / 'selected' / 'technical', ffmpeg_verified=True)
            with patch('engine.qc.run_qc', return_value=original) as technical:
                legacy = infographic_qc.run_qc(root / 'video.mp4', self.parent, [], root / 'legacy',
                                             ffmpeg_verified=True)
                self.assertIs(legacy, original)
                technical.assert_called_once_with(root / 'video.mp4', self.parent, [], root / 'legacy',
                                                  ffmpeg_verified=True)

    def test_empty_actual_map_receipts_cannot_pass_geometry_or_hypothesis_qc(self):
        from engine.infographic_qc import audit_map_state
        empty = audit_map_state(self.selected, [])
        self.assertFalse(empty['passed'])
        self.assertIn('INFOGRAPHIC_AUDIT_FRAME_COUNT_INVALID', {e['code'] for e in empty['errors']})
        # Evidence count alone cannot authorize a draw: actual rows without
        # geometry/text/watermark receipts must still fail each relevant gate.
        rows = [dict(scene_id=scene['scene_id'], frame_index=i, t=i / 30)
                for scene in self.selected['scenes'] for i in range(scene['frame_count'])]
        result = audit_map_state(self.selected, rows)
        self.assertFalse(result['passed'])
        errors = {e['code'] for e in result['errors']}
        self.assertIn('INFOGRAPHIC_AUDIT_SOURCE_INVALID', errors)
        self.assertIn('INFOGRAPHIC_GEOMETRY_STATE_NOT_VISIBLE', errors)
        self.assertIn('INFOGRAPHIC_PRIMARY_TEXT_NOT_READABLE', errors)
        self.assertIn('INFOGRAPHIC_HYPOTHESIS_NOT_VISIBLE', errors)

    def test_production_service_measures_pcm_and_reuses_it_without_qa_migration(self):
        import numpy as np
        from scipy.io import wavfile
        from engine import audio
        from engine.infographic_planner import generate_production_infographic
        from engine.semantic_timeline import prepare_production_audio, validate_production_plan
        script = 'Seoul is shown. Tokyo is shown.'
        phrases = ['Seoul is shown.', 'Tokyo is shown.']
        sources = [next(s for s in json.loads((infographic.ROOT / 'data/locations.json').read_text())['sources']
                        if s['id'] == 'natural_earth_places')]
        claims, segments, events = [], [], []
        for number, (phrase, location, point) in enumerate(zip(phrases, ['seoul', 'tokyo'],
                                                               ['LOCATION_SEOUL', 'LOCATION_TOKYO']), 1):
            cid, sid, eid = f'FACT_{number}', f'UTTERANCE_{number}', f'LOCATION_EVENT_{number}'
            claims.append(dict(id=cid, text=phrase, status='FACT', source_ids=['natural_earth_places']))
            start = script.index(phrase)
            segments.append(dict(id=sid, start_char=start, end_char=start + len(phrase),
                                 claim_ids=[cid], source_ids=['natural_earth_places'],
                                 target_ids=[location], event_ids=[eid]))
            events.append(dict(id=eid, semantic_segment_ref=sid, claim_id=cid,
                target_geometry_refs=[], location_point_ref=point, state_before='CONTEXT',
                state_after='LOCATION', primary_role='LOCATION_LABEL', evidence_type='sourced_fact',
                watermark=None, text=dict(event_title=None, location_label=location.upper(), support_data=None)))
        authored = dict(text=script, segments=segments, claims=claims, sources=sources, events=events,
                        options=dict(bgm=False, sfx=False, subtitles=True))
        class ActualPCMFixture:
            name = 'LOCAL_PCM_TEST_FIXTURE'
            def __init__(self):
                self.calls = []
            def synthesize(self, text, destination, **kwargs):
                self.calls.append(text)
                count = round(audio.SR * ([9.4, 11.7][len(self.calls) - 1]))
                samples = np.arange(count)
                pcm = np.rint(np.sin(2 * np.pi * 230 * samples / audio.SR) * 5000).astype(np.int16)
                wavfile.write(destination, audio.SR, pcm)
                return dict(duration=999, estimated=True)  # Must not allocate from provider metadata.
        provider = ActualPCMFixture()
        original = deepcopy(authored)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = generate_production_infographic(authored, root / 'speech', provider=provider)
            self.assertTrue(plan['gate']['passed'], plan['gate'])
            self.assertTrue(validate_production_plan(plan)['passed'])
            self.assertTrue(infographic.validate_infographic(plan)['passed'])
            self.assertEqual(provider.calls, phrases)
            self.assertEqual(authored, original)
            self.assertNotIn('camera_test_preset', plan['metadata'])
            self.assertEqual(plan['metadata']['infographic_preset'], 'MAP_INFOGRAPHIC_PRODUCTION_V022')
            self.assertNotEqual(plan['duration'], 24)
            self.assertEqual([s['narration'] for s in plan['scenes']], phrases)
            self.assertEqual(plan['scenes'][1]['scene_start_frame'], plan['scenes'][0]['scene_end_frame'])
            self.assertNotEqual(plan['scenes'][0]['frame_count'], plan['scenes'][1]['frame_count'])
            self.assertTrue(all(s['infographic']['parent_renderer_family'] == 'production-earth-v1'
                                for s in plan['scenes']))
            timeline = plan['metadata']['semantic_timeline']
            self.assertFalse(timeline['word_alignment'])
            self.assertEqual([s['sample_count'] for s in timeline['segments']],
                             [round(audio.SR * 9.4), round(audio.SR * 11.7)])
            with patch('engine.audio.ESpeakProvider', side_effect=AssertionError('measured speech must not resynthesize')):
                mixed = prepare_production_audio(plan, timeline, root / 'speech', root / 'mixed')
            self.assertEqual(provider.calls, phrases)
            self.assertFalse(mixed['audio']['semantic_timeline']['resynthesized'])
            self.assertEqual(mixed['audio']['semantic_timeline']['voice_sha256'], timeline['voice']['sha256'])
            self.assertEqual(mixed['audio']['semantic_timeline']['script_sha256'], timeline['script_sha256'])
            self.assertTrue((root / 'mixed' / 'semantic-audio-reuse.json').is_file())

    def test_qa_does_not_enable_speech_and_rejects_nonboolean_selection(self):
        qa_parent = parent_qa_plan({**self.raw, 'tts': True, 'subtitles': True})
        with patch('engine.infographic_planner.parent_qa_plan', return_value=qa_parent):
            qa = generate_infographic_qa({**self.raw, 'tts': True, 'subtitles': True})
        # Explicit caller speech flags still cannot synthesize inside fixed QA.
        self.assertFalse(qa['options']['tts'])
        self.assertFalse(qa['options']['subtitles'])
        for value in ['true', 1, None, [], {}]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'REQUIRES_BOOLEAN'):
                generate_infographic_qa({**self.raw, 'map_infographic': value})
        with self.assertRaisesRegex(ValueError, 'REQUIRES_24_SECONDS'):
            parent_qa_plan({**self.raw, 'duration': 12})

    def test_real_production_render_handoff_reuses_verified_audio_and_subtitle_checkpoints(self):
        import hashlib
        import numpy as np
        from scipy.io import wavfile
        from engine import audio, pipeline_stability, rendering
        from engine.infographic_planner import generate_production_infographic
        from engine.storage import atomic_json, plan_hash
        from engine.gpu_bundle import DiagnosticBundle
        phrase = 'Seoul is shown.'
        source = next(s for s in json.loads((infographic.ROOT / 'data/locations.json').read_text())['sources']
                      if s['id'] == 'natural_earth_places')
        authored = dict(project_id='map_integration_v022', text=phrase,
            segments=[dict(id='UTTERANCE_HANDOFF', start_char=0, end_char=len(phrase),
                claim_ids=['FACT_HANDOFF'], source_ids=['natural_earth_places'], target_ids=['seoul'],
                event_ids=['EVENT_HANDOFF'])],
            claims=[dict(id='FACT_HANDOFF', text=phrase, status='FACT', source_ids=['natural_earth_places'])],
            sources=[source], events=[dict(id='EVENT_HANDOFF', semantic_segment_ref='UTTERANCE_HANDOFF',
                claim_id='FACT_HANDOFF', target_geometry_refs=[], location_point_ref='LOCATION_SEOUL',
                state_before='CONTEXT', state_after='LOCATION', primary_role='LOCATION_LABEL',
                evidence_type='sourced_fact', watermark=None,
                text=dict(event_title=None, location_label='SEOUL', support_data=None))],
            options=dict(bgm=False, sfx=False, subtitles=True))
        class MeasuredPCMFixture:
            name = 'LOCAL_PCM_HANDOFF_FIXTURE'
            calls = 0
            def synthesize(self, text, destination, **kwargs):
                self.calls += 1
                pcm = np.rint(np.sin(2*np.pi*230*np.arange(round(audio.SR*4.7))/audio.SR)*5000).astype(np.int16)
                wavfile.write(destination, audio.SR, pcm)
                return dict(duration=999, estimated=True)
        class BackendBoundaryReached(RuntimeError):
            pass
        provider, commands = MeasuredPCMFixture(), []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = generate_production_infographic(authored, root / 'speech', provider=provider)
            self.assertTrue(plan['gate']['passed'], plan['gate'])
            plan['plan_hash'] = plan_hash(plan)
            version = root / 'project' / 'versions' / 'v001'
            atomic_json(version / 'scene_plan.json', plan, exclusive=True)
            atomic_json(version / 'approval.json', dict(user_approval=True, plan_hash=plan['plan_hash']), exclusive=True)
            for scene in plan['scenes']:
                atomic_json(version / 'scene_json' / (scene['scene_id']+'.json'), scene, exclusive=True)
            bundle = DiagnosticBundle(version, 'job_022abcdef003', plan)
            def fake_transport(backend, command, cwd, progress):
                # The actual InfographicBackend has already checked source data
                # and mapped its parent page before this no-GPU boundary.
                self.assertIn('/static/render_infographic_earth.html?', command[command.index('--url')+1])
                persisted = json.loads(Path(command[command.index('--scene-json')+1]).read_text())
                self.assertEqual(persisted, plan['scenes'][0])
                commands.append(list(command))
                raise BackendBoundaryReached('TEST_ONLY_NO_GPU_TRANSPORT_BOUNDARY')
            with patch('engine.backends.CPULocalBackend.run', new=fake_transport), \
                    patch.object(rendering, '_cached_scene', return_value=None), \
                    patch('engine.audio.ESpeakProvider', side_effect=AssertionError('Measured speech must not resynthesize')), \
                    patch.object(rendering, 'create_subtitles', side_effect=AssertionError('Persisted subtitle checkpoint must be reused')):
                with self.assertRaises(BackendBoundaryReached):
                    try:
                        pipeline_stability.render_project(version, plan, 'http://127.0.0.1:8000/static', diagnostic=bundle)
                    except RuntimeError as error:
                        if isinstance(error, BackendBoundaryReached):
                            raise
                        report_path = bundle.root / 'preflight.json'
                        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
                        failed = [dict(name=row.get('name'), error=row.get('error'),
                            error_type=row.get('error_type'), errors=row.get('result', {}).get('errors'))
                            for row in report.get('checks', []) if not row.get('passed')]
                        scene_failed = [dict(scene_id=scene['scene_id'], name=row.get('name'),
                            error=row.get('error'), error_type=row.get('error_type'),
                            errors=row.get('report', {}).get('errors'))
                            for scene in report.get('scenes', []) for row in scene.get('checks', [])
                            if not row.get('passed')]
                        self.fail(json.dumps(dict(error=str(error), failed=failed, scene_failed=scene_failed)))
                self.assertEqual(len(commands), 1)
                self.assertEqual(provider.calls, 1)
                checkpoints = [version / 'audio' / name for name in
                    ['audio_report.json', 'subtitle_report.json', 'semantic-audio-reuse.json', 'mix.wav', 'subtitles.ass']]
                self.assertTrue(all(path.is_file() for path in checkpoints))
                saved_audio = json.loads(checkpoints[0].read_text())
                self.assertEqual(saved_audio['semantic_timeline']['voice_sha256'],
                                 plan['metadata']['semantic_timeline']['voice']['sha256'])
                self.assertFalse(saved_audio['semantic_timeline']['resynthesized'])
                saved_subtitles = json.loads(checkpoints[1].read_text())
                self.assertEqual(saved_subtitles['path'], str(checkpoints[-1]))
                self.assertTrue(saved_subtitles['captions'])
                before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in checkpoints}
                with patch('engine.audio.create_audio', side_effect=AssertionError('Verified checkpoint must not remix')), \
                        patch('engine.audio.create_subtitles', side_effect=AssertionError('Verified checkpoint must not rewrite ASS')):
                    with self.assertRaises(BackendBoundaryReached):
                        pipeline_stability.render_project(version, plan, 'http://127.0.0.1:8000/static', diagnostic=bundle)
                    self.assertEqual(len(commands), 2)
                    self.assertEqual(provider.calls, 1)
                    self.assertEqual({str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in checkpoints}, before)
                    # A valid WAV modified after the checkpoint, an altered ASS,
                    # or changed measured source cannot enter the GPU transport.
                    voice = root / 'speech' / plan['metadata']['semantic_timeline']['voice']['file']
                    for corrupt in (checkpoints[3], checkpoints[4], voice):
                        with self.subTest(corrupt=corrupt.name):
                            original = corrupt.read_bytes()
                            if corrupt.suffix == '.wav':
                                rate, pcm = wavfile.read(corrupt)
                                pcm = pcm.copy()
                                samples = pcm.reshape(-1)
                                samples[len(samples)//2] += 1 if np.issubdtype(samples.dtype, np.integer) else .00001
                                wavfile.write(corrupt, rate, pcm)
                            else:
                                corrupt.write_bytes(original+b'\n; altered after approval\n')
                            self.assertNotEqual(hashlib.sha256(corrupt.read_bytes()).hexdigest(),
                                                hashlib.sha256(original).hexdigest())
                            try:
                                with self.assertRaisesRegex((ValueError, RuntimeError), 'SEMANTIC_|INFOGRAPHIC_PREFLIGHT_FAILED'):
                                    pipeline_stability.render_project(version, plan, 'http://127.0.0.1:8000/static', diagnostic=bundle)
                                self.assertEqual(len(commands), 2)
                            finally:
                                corrupt.write_bytes(original)
                self.assertEqual(plan_hash(json.loads((version / 'scene_plan.json').read_text())), plan['plan_hash'])


if __name__ == '__main__':
    unittest.main()
