"""Public bridge input/selection boundaries; no GPU or rendered-image claims."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.mobile_server import MobileApplication
from engine.public_infographic_selection import (
    QA_PROFILE, PRODUCTION_PROFILE, expected_creation_profile,
    require_infographic_selection, require_project_infographic_selection,
    validate_public_production_request,
)
from engine.storage import EngineError, atomic_json


ROOT = Path(__file__).resolve().parents[1]


def preserve_gateway_validation(case):
    from engine import schema, gpu_preflight, visibility
    original = schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL
    def restore():
        schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = original
    case.addCleanup(restore)


class AuthoredInputBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())

    def request(self):
        return dict(direction_profile=PRODUCTION_PROFILE, script_record=deepcopy(self.script))

    def assert_rejected(self, value, code='INFOGRAPHIC_SCRIPT_INVALID'):
        with self.assertRaises(EngineError) as caught:
            validate_public_production_request(value)
        self.assertEqual(caught.exception.code, code)

    def test_registered_fixture_is_valid_without_mutation_or_speech(self):
        value = self.request()
        original = deepcopy(value)
        with patch('engine.infographic_planner.generate_production_infographic') as speech:
            selected = validate_public_production_request(value)
        self.assertEqual(selected['script_record'], original['script_record'])
        self.assertEqual(value, original)
        self.assertIsNot(selected['script_record'], value['script_record'])
        speech.assert_not_called()

    def test_server_owned_controls_cannot_cross_public_boundary(self):
        for field, value in [('duration', 75), ('provider', 'external'), ('directory', '/tmp/user'),
                             ('fps', 60), ('quality', 'CINEMA'), ('tts', False)]:
            with self.subTest(field=field):
                request = self.request()
                request[field] = value
                self.assert_rejected(request, 'UNSUPPORTED_INPUT')

    def test_paths_and_private_timing_are_not_authored_script_fields(self):
        for field, value in [('directory', '../escape'), ('provider', 'external'), ('fps', 60),
                             ('camera_arrival', 0), ('after_state_hold', 0), ('framing_profile', 'invented')]:
            with self.subTest(field=field):
                request = self.request()
                request['script_record'][field] = value
                self.assert_rejected(request)

    def test_registered_source_descriptor_must_be_exact(self):
        for field in ('url', 'local_path', 'sha256'):
            with self.subTest(field=field):
                request = self.request()
                request['script_record']['sources'][0][field] = 'unregistered-input'
                self.assert_rejected(request)

    def test_unknown_geometry_and_wrong_point_fail_before_synthesis(self):
        for refs, point in [(['FAKE_GEOMETRY'], 'LOCATION_SUEZ_CANAL'),
                            (['CANAL_SUEZ_RIVER_NE10M'], 'COUNTRY_EGY')]:
            with self.subTest(point=point):
                request = self.request()
                request['script_record']['events'][0]['target_geometry_refs'] = refs
                request['script_record']['events'][0]['location_point_ref'] = point
                self.assert_rejected(request)

    def test_source_claim_and_semantic_bindings_are_required(self):
        cases = [('claim_id', 'ABSENT'), ('semantic_segment_ref', 'ABSENT'),
                 ('sentence_index', 999), ('visual_kind', 'arbitrary_particles')]
        for field, value in cases:
            with self.subTest(field=field):
                request = self.request()
                request['script_record']['events'][0][field] = value
                self.assert_rejected(request)

    def test_fake_factual_closed_state_is_rejected(self):
        request = self.request()
        request['script_record']['events'][0]['state_after'] = 'CLOSED'
        request['script_record']['events'][0]['visual_kind'] = 'route_blocked'
        self.assert_rejected(request)

    def test_audio_clock_cannot_be_disabled_or_nan(self):
        for options in [dict(tts=False), dict(tts='true'), dict(quality=[]), dict(pace=[]), dict(sfx='true')]:
            with self.subTest(options=options):
                request = self.request()
                request['script_record']['options'] = options
                self.assert_rejected(request)
        request = self.request()
        request['script_record']['speed'] = float('nan')
        self.assert_rejected(request)

    def test_empty_or_duplicate_events_fail(self):
        for duplicate in (False, True):
            request = self.request()
            events = request['script_record']['events']
            request['script_record']['events'] = events + [deepcopy(events[0])] if duplicate else []
            self.assert_rejected(request)


class ActualSelectionBoundary(unittest.TestCase):
    @staticmethod
    def plan(family='story-progression-v021'):
        return dict(metadata=dict(infographic=dict(version='v022', parent_renderer_family=family)),
                    request={}, scenes=[dict(scene_id='S001', infographic=dict(version='v022', parent_renderer_family=family))])

    def test_numeric_string_automatic_qa_matches_original_planner(self):
        env = {'WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION': 'v022'}
        self.assertEqual(expected_creation_profile(dict(duration='24', direction_profile='REFERENCE_MASTER'), env), QA_PROFILE)
        for request in [dict(duration=12, direction_profile='REFERENCE_MASTER'),
                        dict(duration=24, direction_profile='SECOND_EVENT_ADAPTIVE_WIDE_TEST'),
                        dict(duration=24, production_preset='LEGACY'), dict(duration='bad'),
                        dict(duration=24, direction_profile=[])]:
            self.assertIsNone(expected_creation_profile(request, env))
        preserve_gateway_validation(self)
        with tempfile.TemporaryDirectory() as directory:
            access = Path(directory) / 'owner.txt'
            access.write_text('isolated-named-qa-input-test-owner-code')
            access.chmod(0o600)
            app = MobileApplication(Path(directory) / 'state', 'http://127.0.0.1:8123', access, disk_floor=0)
            raw = dict(topic='authored QA location', direction_profile=QA_PROFILE)
            self.assertEqual(app.validate_request({**raw, 'duration': '24'})['direction_profile'], QA_PROFILE)
            for duration in (12, 15, 24.1, None):
                with self.subTest(duration=duration), self.assertRaises(EngineError) as caught:
                    app.validate_request({**raw, 'duration': duration})
                self.assertEqual(caught.exception.code, 'INVALID_DURATION')
            with self.assertRaises(EngineError) as caught:
                app.validate_request(raw)
            self.assertEqual(caught.exception.code, 'INVALID_DURATION')

    def test_legacy_saved_plan_does_not_validate_or_migrate(self):
        legacy = dict(metadata={}, scenes=[dict(scene_id='S001')], request=dict(direction_profile='REFERENCE_MASTER', duration=24))
        before = deepcopy(legacy)
        with patch('engine.infographic_contract.validate_infographic') as checker:
            self.assertIsNone(require_infographic_selection(legacy))
        checker.assert_not_called()
        self.assertEqual(before, legacy)

    def test_declared_new_profile_cannot_be_served_by_legacy_plan(self):
        for profile in (QA_PROFILE, PRODUCTION_PROFILE):
            with self.subTest(profile=profile), self.assertRaises(EngineError) as caught:
                require_infographic_selection(dict(metadata={}, scenes=[{}], request=dict(direction_profile=profile)))
            self.assertEqual(caught.exception.code, 'INFOGRAPHIC_SELECTION_MISMATCH')

    def test_partial_version_family_and_shape_fail_closed(self):
        malformed = [dict(metadata=[], scenes=[]), dict(metadata={}, scenes=[None]),
                     dict(metadata={}, scenes={}), dict(metadata={}, scenes=[], request=[])]
        base = self.plan()
        for field in ('metadata', 'scenes'):
            value = deepcopy(base)
            if field == 'metadata':
                value['metadata'].pop('infographic')
            else:
                value['scenes'][0].pop('infographic')
            malformed.append(value)
        for field, value in [('version', 'v021'), ('parent_renderer_family', 'production-earth-v1')]:
            candidate = deepcopy(base)
            candidate['scenes'][0]['infographic'][field] = value
            malformed.append(candidate)
        for value in malformed:
            with self.subTest(value=value), self.assertRaises(EngineError) as caught:
                require_infographic_selection(value, QA_PROFILE)
            self.assertEqual(caught.exception.code, 'INFOGRAPHIC_SELECTION_MISMATCH')

    def test_selected_source_contract_must_pass(self):
        with patch('engine.infographic_contract.validate_infographic', return_value=dict(passed=False)):
            with self.assertRaises(EngineError) as caught:
                require_infographic_selection(self.plan(), QA_PROFILE)
        self.assertEqual(caught.exception.code, 'INFOGRAPHIC_PLAN_INVALID')

    def test_production_reloads_actual_measured_voice_gate(self):
        with patch('engine.infographic_contract.validate_infographic', return_value=dict(passed=True)), \
             patch('engine.semantic_timeline.validate_production_plan', return_value=dict(passed=False)) as voice:
            with self.assertRaises(EngineError) as caught:
                require_infographic_selection(self.plan('production-earth-v1'), PRODUCTION_PROFILE)
        voice.assert_called_once()
        self.assertEqual(caught.exception.code, 'INFOGRAPHIC_PLAN_INVALID')

    def test_original_creation_receipt_survives_new_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'versions/v001').mkdir(parents=True)
            (root / 'versions/v002').mkdir()
            (root / 'prompt').mkdir()
            atomic_json(root / 'prompt/request_v001.json', dict(direction_profile='REFERENCE_MASTER'))
            atomic_json(root / 'versions/v001/public-selection.json', dict(version='v022', effective_profile=QA_PROFILE))
            class Store:
                def path(self, pid): return root
                def version_path(self, pid, version): return root / 'versions' / version
            with self.assertRaises(EngineError) as caught:
                require_project_infographic_selection(Store(), 'project_fixture', 'v002', dict(metadata={}, scenes=[{}], request={}))
            self.assertEqual(caught.exception.code, 'INFOGRAPHIC_SELECTION_MISMATCH')


class ServerArtifactBoundary(unittest.TestCase):
    def app(self, directory):
        preserve_gateway_validation(self)
        access = Path(directory) / 'owner.txt'
        access.write_text('isolated-server-artifact-test-owner-code')
        access.chmod(0o600)
        return MobileApplication(Path(directory) / 'state', 'http://127.0.0.1:8123', access, disk_floor=0)

    def test_failed_new_speech_creation_retains_prior_artifacts(self):
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            app = self.app(directory)
            old = app.store.root / '.infographic-production' / 'previous'
            old.mkdir(parents=True)
            kept = old / 'kept.wav'
            kept.write_bytes(b'existing-private-speech')
            def unavailable(record, path, provider, fps):
                self.assertEqual(record, script)
                self.assertIsNone(provider)
                self.assertEqual(fps, 30)
                self.assertEqual(path.parent, app.store.root / '.infographic-production')
                self.assertNotEqual(path, old)
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
                (path / 'partial.wav').write_bytes(b'new-partial')
                return dict(scenes=[], gate=dict(passed=False))
            with patch('engine.infographic_planner.generate_production_infographic', side_effect=unavailable):
                with self.assertRaises(EngineError) as caught:
                    app.create_project(dict(direction_profile=PRODUCTION_PROFILE, script_record=script))
            self.assertEqual(caught.exception.code, 'INFOGRAPHIC_PRODUCTION_NOT_READY')
            self.assertEqual(kept.read_bytes(), b'existing-private-speech')
            self.assertEqual([p.name for p in old.parent.iterdir()], ['previous'])
            self.assertEqual(app.store.list(), [])

    def test_artifact_root_symlink_cannot_redirect_speech(self):
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            app = self.app(directory)
            target = Path(directory) / 'outside'
            target.mkdir()
            (app.store.root / '.infographic-production').symlink_to(target, target_is_directory=True)
            with patch('engine.infographic_planner.generate_production_infographic') as voice:
                with self.assertRaises(EngineError) as caught:
                    app.create_project(dict(direction_profile=PRODUCTION_PROFILE, script_record=script))
            self.assertEqual(caught.exception.code, 'UNSAFE_ARTIFACT_DIRECTORY')
            voice.assert_not_called()
            self.assertEqual(list(target.iterdir()), [])

    def test_partial_plan_write_failure_keeps_referenced_pcm(self):
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            app = self.app(directory)
            def measured(record, path, provider, fps):
                (path / 'narration.wav').write_bytes(b'private-measured-pcm-fixture')
                return dict(duration=8, scenes=[{}], gate=dict(passed=True),
                            metadata=dict(semantic_timeline_directory=str(path)))
            def partial_write(request, plan):
                saved = app.store.root / 'project_partial_fixture/versions/v001/scene_plan.json'
                atomic_json(saved, plan, True)
                raise OSError('injected failure after plan persisted')
            with patch('engine.infographic_planner.generate_production_infographic', side_effect=measured), \
                 patch('engine.public_infographic_selection.require_infographic_selection', return_value=PRODUCTION_PROFILE), \
                 patch.object(app.store, 'create', side_effect=partial_write):
                with self.assertRaises(OSError):
                    app.create_project(dict(direction_profile=PRODUCTION_PROFILE, script_record=script))
            saved = json.loads((app.store.root / 'project_partial_fixture/versions/v001/scene_plan.json').read_text())
            path = Path(saved['metadata']['semantic_timeline_directory'])
            self.assertEqual(path.parent, app.store.root / '.infographic-production')
            self.assertEqual((path / 'narration.wav').read_bytes(), b'private-measured-pcm-fixture')

    def test_failed_new_directory_allocation_never_removes_existing_artifacts(self):
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            app = self.app(directory)
            existing = app.store.root / '.infographic-production' / ('a' * 32)
            existing.mkdir(parents=True)
            kept = existing / 'kept.wav'
            kept.write_bytes(b'prior-private-pcm')
            with patch('deployment.mobile_server.uuid.uuid4') as identifier, \
                 patch('engine.infographic_planner.generate_production_infographic') as voice:
                identifier.return_value.hex = 'a' * 32
                with self.assertRaises(FileExistsError):
                    app.create_project(dict(direction_profile=PRODUCTION_PROFILE, script_record=script))
            voice.assert_not_called()
            self.assertEqual(kept.read_bytes(), b'prior-private-pcm')


if __name__ == '__main__':
    unittest.main()
