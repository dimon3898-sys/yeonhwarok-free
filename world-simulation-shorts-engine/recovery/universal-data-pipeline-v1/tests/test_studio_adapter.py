"""Focused orchestration contracts with mocked compiler/child, never video claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

m = load('udp_studio_under_test', HERE / 'studio_adapter.py')
w = load('udp_worker_under_test', HERE / 'software_worker.py')
REQUEST = {'schema': m.REQUEST_SCHEMA, 'prompt': {'schema': 'WORLD_ENGINE_DATA_PROMPT_V1', 'topic': 'unit transport', 'simulationType': 'GENERAL'}, 'sceneId': 'unit-route'}


def compiler(prompt, registry):
    scene = {'metadata': {'schema': 'PLANNER_SCENE_JSON_V1', 'output': {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}}, 'subject': {'label': 'Unit test supplied route'},
        'timing': {'fps': 30, 'total_frames': 60}, 'inputData': deepcopy(prompt)}
    return {'schema': 'WORLD_ENGINE_DATA_PIPELINE_RESULT_V1', 'status': 'PASS', 'inputSHA256': m.sha(m.canonical(prompt)),
        'issues': [], 'sceneResults': [{'sceneId': 'unit-route', 'status': 'PASS'}],
        'renderableSceneIds': ['unit-route'], 'blockedSceneIds': [],
        'renderRequests': [{'sceneId': 'unit-route', 'scene': scene, 'enginePlan': {}, 'renderSettings': {'sourceRegionId': 'europe_germany'}, 'sourceManifest': []}]}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='udp-studio-unit-', dir='/workspace')
        self.root = Path(self.temp.name)
        self.patch = patch.object(m, 'compile_prompt', side_effect=compiler)
        self.patch.start()
        self.controller = m.StudioController(control_root=self.root / 'control', export_root=self.root / 'exports', allow_free_data_review=True)

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def start_mock(self, request=None, key='udp-unit-start-00000001'):
        submission = self.controller.submit(REQUEST if request is None else request)['submissionId']
        class Child:
            pid = os.getpid()
        with patch.object(m.manager.subprocess, 'Popen', return_value=Child()) as child:
            state = self.controller.start(submission, key, consent=True)
        return submission, state, child

    def test_normalization_preserves_standard_scene_and_trace(self):
        value = self.controller._normal(REQUEST)
        pipeline = value['sourcePipeline']
        self.assertEqual(value['videoPlan'], pipeline['runtimePayload']['scene'])
        self.assertEqual(pipeline['originalRequest'], REQUEST)
        self.assertEqual(pipeline['sceneSHA256'], m.sha(m.canonical(value['videoPlan'])))
        self.assertEqual(self.controller._normal(REQUEST), value)

    def test_unknown_or_production_request_has_no_fallback(self):
        self.assertFalse(self.controller.preflight({'schema': 'WORLD_ENGINE_STUDIO_PROMPT_V2'})['valid'])
        with self.assertRaisesRegex(m.StudioError, 'EXPLICIT_DATA_SCENE_SELECTION'):
            self.controller._normal({**REQUEST, 'approved': True})

    def test_partial_selection_is_explicit_and_blocked_scene_cannot_start(self):
        with patch.object(m, 'compile_prompt', return_value={**compiler({}, []), 'status': 'NEEDS_INPUT', 'blockedSceneIds': ['missing-history']}):
            result = self.controller.preflight(REQUEST)
            self.assertTrue(result['ready'])
            self.assertEqual(result['blockedSceneIds'], ['missing-history'])
            self.assertTrue(result['partialSelectionExplicit'])
            self.assertFalse(self.controller.preflight({**REQUEST, 'sceneId': 'missing-history'})['ready'])

    def test_historical_g3_remains_blocked_even_mock_compiler_says_pass(self):
        request = deepcopy(REQUEST)
        request['prompt']['simulationType'] = 'HISTORICAL'
        result = self.controller.preflight(request)
        self.assertFalse(result['ready'])
        self.assertFalse(result['historicalRenderAllowed'])
        self.assertIn('UDP_HISTORICAL_G3_REMAINS_BLOCKED', [r.get('code') for r in result['checks']])

    def test_server_opt_in_required(self):
        self.controller.allow_free_data_review = False
        self.assertFalse(self.controller.preflight(REQUEST)['ready'])

    def test_consent_required_before_child_launch(self):
        submission = self.controller.submit(REQUEST)['submissionId']
        with patch.object(m.manager.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(m.StudioError, 'OWNER_CONSENT_REQUIRED'):
                self.controller.start(submission, 'udp-no-consent-00001')
            child.assert_not_called()

    def test_duplicate_start_and_reconnect_reuse_same_claim(self):
        submission, state, child = self.start_mock()
        self.assertTrue(child.call_args.kwargs['start_new_session'])
        with patch.object(m.manager.subprocess, 'Popen') as second:
            self.assertEqual(self.controller.start(submission, 'udp-unit-start-00000001', consent=True)['jobId'], state['jobId'])
            self.assertEqual(self.controller.start(submission, 'udp-new-browser-start-0002', consent=True)['jobId'], state['jobId'])
            second.assert_not_called()
        self.assertFalse(list(self.controller.control_root.glob('approvals/*')))

    def test_other_active_job_is_blocked(self):
        self.start_mock()
        other = deepcopy(REQUEST)
        other['prompt']['topic'] = 'other test route'
        submission = self.controller.submit(other)['submissionId']
        with self.assertRaises(m.StudioError) as caught:
            self.controller.start(submission, 'udp-other-active-start', consent=True)
        self.assertEqual(caught.exception.code, 'STUDIO_JOB_ALREADY_ACTIVE')

    def test_submit_to_start_source_change_is_rejected(self):
        submission = self.controller.submit(REQUEST)['submissionId']
        with patch.object(m, 'source_bindings', return_value=[{'path': 'changed', 'sha256': '1' * 64}]), patch.object(m.manager.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(m.StudioError, 'BINDING_CHANGED'):
                self.controller.start(submission, 'udp-changed-source-start', consent=True)
            child.assert_not_called()

    def test_restart_constructor_never_starts_and_resume_forbidden(self):
        _, state, _ = self.start_mock()
        with patch.object(m.manager.subprocess, 'Popen') as child:
            m.StudioController(control_root=self.root / 'control', export_root=self.root / 'exports', allow_free_data_review=True)
            child.assert_not_called()
        with self.assertRaisesRegex(m.StudioError, 'AUTORETRY_FORBIDDEN'):
            self.controller.resume(state['jobId'], 'udp-no-autoretry-0001', consent=True)

    def test_state_cannot_be_shared_export_or_repo(self):
        with self.assertRaisesRegex(m.StudioError, 'SEPARATE_PRIVATE_STATE'):
            m.StudioController(control_root=self.root / 'exports', export_root=self.root / 'exports')
        with self.assertRaisesRegex(m.StudioError, 'SEPARATE_PRIVATE_STATE'):
            m.StudioController(control_root=HERE / 'private-wrong', export_root=self.root / 'exports')

    def test_server_registry_hash_not_client_truth_flag(self):
        registry = self.root / 'registry.json'
        registry.write_text('[]')
        controller = m.StudioController(control_root=self.root / 'other', export_root=self.root / 'exports', evidence_registry=registry,
            expected_registry_sha256='1' * 64, allow_free_data_review=True)
        self.assertEqual(controller.preflight(REQUEST)['error']['code'], 'UDP_SERVER_EVIDENCE_REGISTRY_CHANGED')

    def test_worker_bound_package_and_historical_rejection(self):
        _, state, _ = self.start_mock()
        file = self.controller.control_root / 'source-jobs' / state['jobId'] / 'compiledpackage.json'
        raw = file.read_bytes()
        package = w.validate_package(raw, w.sha(raw))
        self.assertEqual(package['sourcePipeline']['scope'], m.PROFILE)
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_HASH_MISMATCH'):
            w.validate_package(raw, '0' * 64)
        for key, value in [('simulationType', 'HISTORICAL'), ('totalFrames', 241), ('sceneSHA256', '0' * 64)]:
            altered = deepcopy(package)
            altered['sourcePipeline'][key] = value
            encoded = w.canonical(altered)
            with self.assertRaises(RuntimeError):
                w.validate_package(encoded, w.sha(encoded))

    def test_expired_receipt_is_rejected(self):
        _, state, _ = self.start_mock()
        file = self.controller.control_root / 'source-jobs' / state['jobId'] / 'compiledpackage.json'
        package = json.loads(file.read_bytes())
        package['executionReceipt']['expiresAt'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        raw = w.canonical(package)
        with self.assertRaisesRegex(RuntimeError, 'RECEIPT_EXPIRED'):
            w.validate_package(raw, w.sha(raw))


class HttpSecurityTests(unittest.TestCase):
    def test_real_server_auth_csrf_origin_and_owner_form_preserved(self):
        with tempfile.TemporaryDirectory(prefix='udp-http-unit-', dir='/workspace') as directory, patch.object(m, 'compile_prompt', side_effect=compiler):
            root = Path(directory)
            owner = root / 'owner-code'
            owner.write_text('unit-owner-code-not-a-real-secret-123456')
            owner.chmod(0o600)
            import socket
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            app = m.local_application(state_root=root / 'state', owner_file=owner, export_root=root / 'exports', port=port, allow_free_data_review=True)
            http_server = m.server.ThreadingHTTPServer(('127.0.0.1', port), m.server.make_handler(app))
            threading.Thread(target=http_server.serve_forever, daemon=True).start()
            origin = f'http://127.0.0.1:{port}'
            def call(path, body=None, cookie=None, csrf=None, supplied_origin=origin):
                client = http.client.HTTPConnection('127.0.0.1', port)
                headers = {'Origin': supplied_origin, 'Content-Type': 'application/json'}
                if cookie: headers['Cookie'] = cookie
                if csrf: headers['X-Studio-CSRF'] = csrf
                client.request('POST' if body is not None else 'GET', path, None if body is None else json.dumps(body), headers)
                response = client.getresponse(); data = response.read(); status = response.status
                cookie = response.getheader('Set-Cookie'); client.close()
                return status, json.loads(data) if data.startswith(b'{') else data, cookie
            try:
                self.assertEqual(call('/api/preflight', REQUEST)[0], 401)
                self.assertEqual(call('/api/preflight', REQUEST, supplied_origin='https://invalid.example')[0], 403)
                status, login, cookie = call('/api/login', {'password': owner.read_text()})
                self.assertEqual(status, 200)
                cookie = cookie.split(';', 1)[0]
                self.assertEqual(call('/api/preflight', REQUEST, cookie)[0], 403)
                status, result, _ = call('/api/preflight', REQUEST, cookie, login['csrf'])
                self.assertEqual(status, 200)
                self.assertTrue(result['ready'])
            finally:
                http_server.shutdown(); http_server.server_close()


class ActualCompilerStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='udp-actual-compiler-studio-', dir='/workspace')
        root = Path(self.temp.name)
        registry = HERE / 'evidence/TRUSTED_EVIDENCE.json'
        self.controller = m.StudioController(control_root=root / 'control', export_root=root / 'exports',
            evidence_registry=registry, expected_registry_sha256=m.sha(registry.read_bytes()), allow_free_data_review=True)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, filename):
        prompt = json.loads((HERE / 'examples' / filename).read_bytes())
        return {'schema': m.REQUEST_SCHEMA, 'prompt': prompt, 'sceneId': prompt['scenes'][0]['sceneId']}

    def test_real_invalid_coordinate_is_blocked_before_job(self):
        result = self.controller.preflight(self.request('negative/INVALID_COORDINATE.json'))
        self.assertFalse(result['ready'])
        self.assertEqual(result['error']['code'], 'UDP_SELECTED_SCENE_NOT_RENDERABLE')
        self.assertIn('COORDINATE', json.dumps(result['error']['fields']))

    def test_all_three_real_nonhistorical_inputs_select_actual_scene(self):
        for filename in ('AVIATION_GERMANY.json', 'FICTIONAL_NAMIBIA.json', 'TRADE_CHILE.json'):
            request = self.request(filename)
            result = self.controller.preflight(request)
            self.assertTrue(result['ready'], (filename, result))
            self.assertEqual(result['selectedSceneId'], request['sceneId'])
            self.assertFalse(result['gpuRenderingVerified'])

    def test_missing_future_scene_does_not_silently_replace_it(self):
        request = self.request('AVIATION_GERMANY.json')
        prompt = request['prompt']
        first = prompt['scenes'][0]
        frame_count = first['endFrame']
        child = deepcopy(first)
        child.update(sceneId='missing-future-child', startFrame=frame_count, endFrame=2 * frame_count, dependsOn=[])
        child['facts']['geometries'] = []
        prompt['scenes'].append(child)
        prompt['durationSeconds'] *= 2
        result = self.controller.preflight(request)
        self.assertTrue(result['ready'], result)
        self.assertIn('missing-future-child', result['blockedSceneIds'])
        request['sceneId'] = 'missing-future-child'
        self.assertFalse(self.controller.preflight(request)['ready'])

    def test_real_sixty_fps_cannot_claim_render_ready(self):
        request = self.request('AVIATION_GERMANY.json')
        request['prompt']['fps'] = 60
        request['prompt']['durationSeconds'] /= 2
        self.assertFalse(self.controller.preflight(request)['ready'])

    def test_real_historical_control_data_remains_blocked(self):
        request = self.request('KOREAN_WAR_MISSING_CONTROL.json')
        result = self.controller.preflight(request)
        self.assertFalse(result['ready'])
        self.assertFalse(result['historicalRenderAllowed'])



if __name__ == '__main__':
    unittest.main()
