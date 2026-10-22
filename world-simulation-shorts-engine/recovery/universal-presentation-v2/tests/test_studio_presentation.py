"""Focused orchestration tests. Mocked draws never count as rendered video."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('_up2_controller_test', HERE / 'studio_adapter.py')
w = load('_up2_worker_test', HERE / 'software_worker.py')
runner = load('_up2_runner_test', HERE / 'run_studio_demos.py')
REQUEST = {'schema': m.REQUEST_SCHEMA, 'prompt': {'schema': 'WORLD_ENGINE_PRESENTATION_PROMPT_V2',
    'prompt': 'Use the supplied illustrative route and camera intent.', 'simulationType': 'GENERAL'}, 'sceneId': '__timeline__'}


def compiler(prompt, registry):
    rows = []
    for index in range(2):
        scene = {'metadata': {'schema': 'PLANNER_SCENE_JSON_V1', 'output': {
            'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}},
            'timing': {'fps': 30, 'total_frames': 30},
            'geometries': [{'type': 'Polygon', 'id': 'test', 'coordinates': [[1, 2], [3, 4], [1, 2]]}]}
        rows.append({'sceneId': 'scene-' + str(index), 'startFrame': 30 * index, 'endFrame': 30 * (index + 1),
            'scene': scene, 'region': {'center': [10, 50], 'bbox': [9, 49, 11, 51]},
            'presentation': {'camera': {'mode': 'KEYFRAMES', 'keyframes': [
                {'frame': 0, 'center': [10, 50], 'zoom': .8}, {'frame': 29, 'center': [10, 50], 'zoom': 1}]}},
            'inputTrace': [{'path': '$.data.scenes[' + str(index) + ']'}]})
    return {'schema': 'WORLD_ENGINE_PRESENTATION_PIPELINE_RESULT_V2',
        'simulationType': prompt.get('simulationType', 'GENERAL'), 'status': 'PASS',
        'inputSHA256': m.sha(m.canonical(prompt)), 'issues': [], 'clarifications': [],
        'renderRequests': rows, 'renderableSceneIds': [row['sceneId'] for row in rows],
        'blockedSceneIds': [], 'transitionPlan': [{'type': 'CUT', 'frame': 30}], 'inputTrace': []}


def mock_prepare(request, cache_root):
    # This is an integrity fixture, explicitly not geographic/source evidence.
    cache_root.mkdir(mode=0o700)
    material = cache_root / 'integrity-fixture.bin'
    material.write_bytes(b'unit-test-only-not-a-map-or-real-render')
    material.chmod(0o600)
    qualification = {'schema': 'WORLD_ENGINE_PRESENTATION_SOURCES_V2',
        'segments': [{'segmentIndex': index, 'sourceId': 'UNIT_TEST_ONLY'}
                     for index in range(len(request['segments']))], 'totalFrames': request['totalFrames']}
    wire = m.canonical(qualification).decode()
    return {'totalFrames': request['totalFrames'], 'segments': [{} for _ in request['segments']],
        'sourceQualification': qualification, 'sourceQualificationWireJSON': wire,
        'sourceQualificationSHA256': m.sha(wire.encode()),
        'sourceBindings': [{'path': str(material), 'sha256': m.sha(material.read_bytes())}]}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='up2-studio-unit-', dir='/workspace')
        self.root = Path(self.temp.name)
        self.compiler = patch.object(m, 'compile_prompt', side_effect=compiler)
        self.preparer = patch.object(m, 'prepare_runtime', side_effect=mock_prepare)
        self.verifier = patch.object(m, 'verify_prepared_sources', return_value={'status': 'PASS'})
        self.compiler.start(); self.prepare_mock = self.preparer.start(); self.verifier.start()
        self.controller = m.StudioController(control_root=self.root / 'control', export_root=self.root / 'exports',
            allow_free_data_review=True)

    def tearDown(self):
        self.compiler.stop(); self.preparer.stop(); self.verifier.stop(); self.temp.cleanup()

    def start_mock(self, request=None, key='up2-unit-start-00000001'):
        submitted = self.controller.submit(REQUEST if request is None else request)['submissionId']
        class Child:
            pid = os.getpid()
        with patch.object(m.manager.subprocess, 'Popen', return_value=Child()) as child:
            state = self.controller.start(submitted, key, consent=True)
        return submitted, state, child

    def package(self):
        _, state, _ = self.start_mock()
        file = self.controller.control_root / 'source-jobs' / state['jobId'] / 'compiledpackage.json'
        return json.loads(file.read_bytes())

    def test_timeline_and_raw_planner_member_order_are_bound(self):
        value = self.controller._normal(REQUEST)
        pipeline = value['sourcePipeline']
        self.assertEqual(pipeline['segmentCount'], 2)
        self.assertEqual(pipeline['runtimePayload']['transitions'], [{'type': 'CUT', 'frame': 30}])
        self.assertEqual(json.loads(pipeline['runtimeRequestWireJSON']), value['videoPlan'])
        self.assertEqual(pipeline['runtimeWireSHA256'], m.sha(pipeline['runtimeRequestWireJSON'].encode()))
        self.assertNotEqual(m.canonical(value['videoPlan']), pipeline['runtimeRequestWireJSON'].encode())
        self.assertEqual(self.controller._normal(REQUEST), value)

    def test_old_schema_or_extra_fields_cannot_fall_back_to_production(self):
        for request in ({'schema': 'WORLD_ENGINE_STUDIO_PROMPT_V2'}, {**REQUEST, 'approved': True}):
            self.assertFalse(self.controller.preflight(request)['ready'])

    def test_blocked_scene_prevents_complete_timeline(self):
        result = compiler({}, [])
        result.update(status='NEEDS_INPUT', blockedSceneIds=['missing-fact'])
        with patch.object(m, 'compile_prompt', return_value=result):
            self.assertEqual(self.controller.preflight(REQUEST)['error']['code'], 'UP2_COMPLETE_TIMELINE_DATA_REQUIRED')

    def test_single_scene_selection_preserves_original_global_range(self):
        result = compiler({}, [])
        result.update(status='NEEDS_INPUT', blockedSceneIds=['unrelated-missing-scene'])
        with patch.object(m, 'compile_prompt', return_value=result):
            value = self.controller._normal({**REQUEST, 'sceneId': 'scene-1'})
        segment = value['videoPlan']['segments'][0]
        self.assertEqual([segment['startFrame'], segment['endFrame']], [0, 30])
        self.assertEqual(segment['sourceFrameRange'], [30, 60])
        self.assertEqual(value['sourcePipeline']['blockedSceneIds'], ['unrelated-missing-scene'])

    def test_no_unknown_scene_selection(self):
        self.assertFalse(self.controller.preflight({**REQUEST, 'sceneId': 'not-present'})['ready'])

    def test_gap_overlap_and_missing_or_fade_cut_are_blocked(self):
        for mutation in ('gap', 'overlap', 'missing', 'fade'):
            result = compiler({}, [])
            if mutation == 'gap': result['renderRequests'][1]['startFrame'] = 31
            if mutation == 'overlap': result['renderRequests'][1]['startFrame'] = 29
            if mutation == 'missing': result['transitionPlan'] = []
            if mutation == 'fade': result['transitionPlan'][0]['type'] = 'FADE'
            with self.subTest(mutation=mutation), patch.object(m, 'compile_prompt', return_value=result):
                self.assertFalse(self.controller.preflight(REQUEST)['ready'])

    def test_historical_authority_remains_blocked_and_never_prepares(self):
        request = deepcopy(REQUEST)
        request['prompt']['simulationType'] = 'HISTORICAL'
        result = self.controller.preflight(request)
        self.assertFalse(result['ready']); self.assertFalse(result['historicalRenderAllowed'])
        self.prepare_mock.assert_not_called()

    def test_server_opt_in_is_still_required(self):
        self.controller.allow_free_data_review = False
        self.assertFalse(self.controller.preflight(REQUEST)['ready'])

    def test_actual_material_files_mandatory(self):
        with patch.object(m, 'prepare_runtime', return_value={**mock_prepare(
                {'segments': [{}, {}], 'totalFrames': 60}, self.root / 'unbound'), 'sourceBindings': []}):
            self.assertEqual(self.controller.preflight(REQUEST)['error']['code'], 'UP2_ACTUAL_MATERIAL_FILES_REQUIRED')

    def test_preparation_reused_without_new_crop(self):
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        self.assertEqual(self.prepare_mock.call_count, 1)

    def test_corrupt_crop_cache_is_rejected_without_regeneration(self):
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        material = next((self.controller.control_root / 'presentation-sources').glob('*-crop/integrity-fixture.bin'))
        material.write_bytes(b'corrupted')
        self.assertEqual(self.controller.preflight(REQUEST)['error']['code'], 'UP2_MATERIAL_FILE_CHANGED_OR_UNSAFE')
        self.assertEqual(self.prepare_mock.call_count, 1)

    def test_missing_crop_cache_is_rejected_without_regeneration(self):
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        material = next((self.controller.control_root / 'presentation-sources').glob('*-crop/integrity-fixture.bin'))
        material.unlink()
        self.assertFalse(self.controller.preflight(REQUEST)['ready'])
        self.assertEqual(self.prepare_mock.call_count, 1)

    def test_cached_qualification_seal_tampering_is_rejected(self):
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        file = next((self.controller.control_root / 'presentation-sources').glob('*.json'))
        value = json.loads(file.read_bytes())
        value['admission']['sourceQualification']['totalFrames'] = 61
        file.write_bytes(m.canonical(value))
        self.assertEqual(self.controller.preflight(REQUEST)['error']['code'], 'UP2_QUALIFICATION_SEAL_MISMATCH')

    def test_provider_stored_receipt_recheck_is_mandatory(self):
        self.assertTrue(self.controller.preflight(REQUEST)['ready'])
        with patch.object(m, 'verify_prepared_sources', side_effect=m.StudioError('UP2_STORED_SOURCE_QUALIFICATION_INVALID')):
            self.assertFalse(self.controller.preflight(REQUEST)['ready'])
        self.assertEqual(self.prepare_mock.call_count, 1)

    def test_private_state_cannot_be_shared_or_in_repo(self):
        for root in (self.root / 'exports', HERE / 'unsafe-state'):
            with self.assertRaisesRegex(m.StudioError, 'SEPARATE_PRIVATE_STATE'):
                m.StudioController(control_root=root, export_root=self.root / 'exports')

    def test_explicit_owner_consent_required(self):
        submission = self.controller.submit(REQUEST)['submissionId']
        with patch.object(m.manager.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(m.StudioError, 'OWNER_CONSENT_REQUIRED'):
                self.controller.start(submission, 'up2-no-consent-000001')
            child.assert_not_called()

    def test_duplicate_touch_and_reconnected_browser_reuse_one_claim(self):
        submission, state, child = self.start_mock()
        self.assertTrue(child.call_args.kwargs['start_new_session'])
        self.assertEqual(self.controller.status(state['jobId'])['totalScenes'], 2)
        with patch.object(m.manager.subprocess, 'Popen') as duplicate:
            for key in ('up2-unit-start-00000001', 'up2-reconnected-000001'):
                self.assertEqual(self.controller.start(submission, key, consent=True)['jobId'], state['jobId'])
            duplicate.assert_not_called()

    def test_competing_job_is_blocked(self):
        self.start_mock()
        other = deepcopy(REQUEST); other['prompt']['prompt'] += ' A different request.'
        submission = self.controller.submit(other)['submissionId']
        with self.assertRaises(m.StudioError) as caught:
            self.controller.start(submission, 'up2-other-active-000001', consent=True)
        self.assertEqual(caught.exception.code, 'STUDIO_JOB_ALREADY_ACTIVE')

    def test_code_change_between_submit_and_start_is_blocked(self):
        submission = self.controller.submit(REQUEST)['submissionId']
        with patch.object(m, 'source_bindings', return_value=[{'path': 'changed', 'sha256': '1' * 64}]), \
                patch.object(m.manager.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(m.StudioError, 'BINDING_CHANGED'):
                self.controller.start(submission, 'up2-source-change-00001', consent=True)
            child.assert_not_called()

    def test_restart_never_auto_starts_and_resume_is_forbidden(self):
        _, state, _ = self.start_mock()
        with patch.object(m.manager.subprocess, 'Popen') as child:
            m.StudioController(control_root=self.root / 'control', export_root=self.root / 'exports', allow_free_data_review=True)
            child.assert_not_called()
        with self.assertRaisesRegex(m.StudioError, 'AUTORETRY_FORBIDDEN'):
            self.controller.resume(state['jobId'], 'up2-no-autoretry-00001', consent=True)

    def test_server_registry_pin_is_not_a_user_truth_flag(self):
        registry = self.root / 'registry.json'; registry.write_text('[]')
        other = m.StudioController(control_root=self.root / 'other', export_root=self.root / 'exports',
            evidence_registry=registry, expected_registry_sha256='0' * 64, allow_free_data_review=True)
        self.assertEqual(other.preflight(REQUEST)['error']['code'], 'UDP_SERVER_EVIDENCE_REGISTRY_CHANGED')

    def test_worker_accepts_the_bound_detached_package(self):
        package = self.package(); raw = w.canonical(package)
        self.assertEqual(w.validate_package(raw, w.sha(raw))['profile'], m.PROFILE)
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_HASH_MISMATCH'):
            w.validate_package(raw, '0' * 64)

    def test_worker_rejects_historical_oversize_and_scope_change(self):
        package = self.package()
        for key, value in (('simulationType', 'HISTORICAL'), ('totalFrames', 241), ('scope', 'PAID_RENDER')):
            invalid = deepcopy(package); invalid['sourcePipeline'][key] = value; raw = w.canonical(invalid)
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'EXECUTION_SCOPE_INVALID'):
                w.validate_package(raw, w.sha(raw))

    def test_worker_rejects_equivalent_but_changed_wire_bytes(self):
        package = self.package(); package['sourcePipeline']['runtimeRequestWireJSON'] += ' '
        raw = w.canonical(package)
        with self.assertRaisesRegex(RuntimeError, 'EXECUTION_SCOPE_INVALID'):
            w.validate_package(raw, w.sha(raw))

    def test_worker_rejects_changed_qualification_seal(self):
        package = self.package()
        package['sourcePipeline']['sourceAdmission']['sourceQualification']['totalFrames'] = 80
        raw = w.canonical(package)
        with self.assertRaisesRegex(RuntimeError, 'QUALIFICATION_SEAL_MISMATCH'):
            w.validate_package(raw, w.sha(raw))

    def test_worker_rejects_expired_claim(self):
        package = self.package()
        package['executionReceipt']['expiresAt'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        raw = w.canonical(package)
        with self.assertRaisesRegex(RuntimeError, 'RECEIPT_EXPIRED'):
            w.validate_package(raw, w.sha(raw))

    def test_non_finite_input_is_not_sent_to_node(self):
        with self.assertRaisesRegex(m.StudioError, 'FINITE_JSON_INPUT_REQUIRED'):
            m.node_json('throw Error("unreachable")', {'invalid': float('nan')})

    def test_malformed_private_prepared_wire_is_structurally_rejected(self):
        with self.assertRaisesRegex(m.StudioError, 'STORED_SOURCE_WIRE_CHANGED'):
            # Exercise the actual parser rather than the fixture verifier mock.
            self.verifier.stop()
            try:
                m.verify_prepared_sources({}, prepared_wire='{invalid')
            finally:
                self.verifier.start()


class HttpSecurityTests(unittest.TestCase):
    def test_real_auth_origin_csrf_and_missing_consent_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix='up2-http-unit-', dir='/workspace') as directory, \
                patch.object(m, 'compile_prompt', side_effect=compiler), \
                patch.object(m, 'prepare_runtime', side_effect=mock_prepare), \
                patch.object(m, 'verify_prepared_sources', return_value={'status': 'PASS'}):
            root = Path(directory); owner = root / 'owner-code'
            owner.write_text('unit-fixture-only-not-a-live-owner-credential'); owner.chmod(0o600)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            app = m.local_application(state_root=root / 'state', owner_file=owner,
                export_root=root / 'exports', port=port, allow_free_data_review=True)
            http_server = m.server.ThreadingHTTPServer(('127.0.0.1', port), m.server.make_handler(app))
            threading.Thread(target=http_server.serve_forever, daemon=True).start()
            origin = 'http://127.0.0.1:' + str(port)
            def call(path, body=None, cookie=None, csrf=None, supplied_origin=origin):
                client = http.client.HTTPConnection('127.0.0.1', port)
                headers = {'Origin': supplied_origin, 'Content-Type': 'application/json'}
                if cookie: headers['Cookie'] = cookie
                if csrf: headers['X-Studio-CSRF'] = csrf
                client.request('POST' if body is not None else 'GET', path,
                    None if body is None else json.dumps(body), headers)
                response = client.getresponse(); raw = response.read(); status = response.status
                saved_cookie = response.getheader('Set-Cookie'); client.close()
                return status, json.loads(raw) if raw.startswith(b'{') else raw, saved_cookie
            try:
                self.assertEqual(call('/api/preflight', REQUEST)[0], 401)
                self.assertEqual(call('/api/preflight', REQUEST, supplied_origin='https://attacker.invalid')[0], 403)
                status, login, cookie = call('/api/login', {'password': owner.read_text()})
                self.assertEqual(status, 200); cookie = cookie.split(';', 1)[0]
                self.assertEqual(call('/api/preflight', REQUEST, cookie)[0], 403)
                status, result, _ = call('/api/preflight', REQUEST, cookie, login['csrf'])
                self.assertEqual(status, 200); self.assertTrue(result['ready'])
                self.assertEqual(result['totalScenes'], 2)
                self.assertFalse(result['gpuRenderingVerified']); self.assertFalse(result['paidRenderAllowed'])
            finally:
                http_server.shutdown(); http_server.server_close()


class RunnerGateTests(unittest.TestCase):
    def test_production_demo_is_blocked_until_all_a_e_gates_pass(self):
        gate = json.loads((HERE / 'reports/GATES.json').read_bytes())
        gate['phaseE'] = {'status': 'PENDING'}
        with tempfile.TemporaryDirectory(prefix='up2-gate-test-', dir='/workspace') as directory:
            file = Path(directory) / 'gate.json'; file.write_bytes(m.canonical(gate))
            with self.assertRaisesRegex(RuntimeError, 'REQUIRED_GATES_NOT_PASSED'):
                runner.require_gates(file, m.sha(file.read_bytes()))
            for name in 'ABCDE': gate['phase' + name] = {'status': 'PASS'}
            file.write_bytes(m.canonical(gate))
            self.assertEqual(runner.require_gates(file, m.sha(file.read_bytes()))['schema'], 'WORLD_ENGINE_UP2_GATES_V1')
            with self.assertRaisesRegex(RuntimeError, 'GATE_HASH_MISMATCH'):
                runner.require_gates(file, '0' * 64)


class ActualCompilerSourceTests(unittest.TestCase):
    """Real compiler, actual licensed source bytes/crops; no browser or draw."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='up2-actual-studio-contract-', dir='/workspace')
        root = Path(self.temp.name)
        self.controller = m.StudioController(control_root=root / 'control', export_root=root / 'exports',
            allow_free_data_review=True)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, file):
        return {'schema': m.REQUEST_SCHEMA, 'prompt': json.loads((HERE / 'examples' / file).read_bytes()),
            'sceneId': m.TIMELINE_ID}

    def test_five_actual_regions_prepare_complete_camera_sources(self):
        for name in ('AVIATION_EUROPE_NL.json', 'TRADE_SOUTH_AMERICA_NL.json', 'FICTIONAL_AFRICA_NL.json',
                     'NEW_REGION_JAPAN_NL.json', 'NEW_REGION_AUSTRALIA_NL.json'):
            with self.subTest(name=name):
                request = self.request(name)
                frames = request['prompt']['data']['durationSeconds'] * request['prompt']['data']['fps']
                result = self.controller.preflight(request)
                self.assertTrue(result['ready'], result)
                self.assertFalse(result['gpuRenderingVerified'])
                self.assertFalse(result['sourceAdmission']['actualDrawPerformed'])
                self.assertTrue(result['sourceAdmission']['preparedBeforeClaim'])
                for credit in result['sourceAdmission']['sourceCredits']:
                    self.assertTrue(credit['attribution']); self.assertTrue(credit['license'])
                    self.assertTrue(credit['sourceURL'])
                self.assertEqual(result['totalFrames'], frames)
                self.assertEqual(result['sourceAdmission']['sourceQualification']['totalFrames'], frames)

    def test_actual_private_persistence_preserves_exact_planner_wire(self):
        request = self.request('AVIATION_EUROPE_NL.json')
        submission = self.controller.submit(request)
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            saved = self.controller._read_submission(root, submission['submissionId'])['submission']
        pipeline = saved['sourcePipeline']
        self.assertEqual(json.loads(pipeline['runtimeRequestWireJSON']), saved['videoPlan'])
        self.assertNotEqual(m.canonical(saved['videoPlan']), pipeline['runtimeRequestWireJSON'].encode())
        proof = m.node_json("import{readFileSync}from'node:fs';const p=JSON.parse(readFileSync(0,'utf8'));"
            "const{validateRuntimeRequest}=await import(p.module);"
            "let sortedRejected=false;try{validateRuntimeRequest(p.sorted);}catch(e){sortedRejected=true;}"
            "validateRuntimeRequest(JSON.parse(p.wire));"
            "process.stdout.write(JSON.stringify({wireValidated:true,sortedRejected,rendered:false}));",
            {'module': (HERE / 'capture_presentation.mjs').as_uri(), 'sorted': saved['videoPlan'],
             'wire': pipeline['runtimeRequestWireJSON']})
        self.assertTrue(proof['wireValidated']); self.assertTrue(proof['sortedRejected'])
        self.assertFalse(proof['rendered'])

    def test_real_invalid_coordinate_cannot_prepare_or_claim(self):
        result = self.controller.preflight(self.request('negative/INVALID_COORDINATE.json'))
        self.assertFalse(result['ready']); self.assertIn('COORDINATE', json.dumps(result))
        self.assertFalse(list((self.controller.control_root / 'source-jobs').iterdir()))

    def test_actual_cached_crop_corruption_is_rejected_without_regeneration(self):
        request = self.request('AVIATION_EUROPE_NL.json')
        self.assertTrue(self.controller.preflight(request)['ready'])
        memo = next((self.controller.control_root / 'presentation-sources').glob('*.json'))
        cached = json.loads(memo.read_bytes())
        crop = Path(cached['prepared']['segments'][0]['terrainPath'])
        crop.write_bytes(b'intentionally-corrupted-new-private-test-cache')
        self.assertFalse(self.controller.preflight(request)['ready'])
        self.assertEqual(crop.read_bytes(), b'intentionally-corrupted-new-private-test-cache')

    def test_self_consistent_but_false_aggregate_source_claim_is_rejected(self):
        request = self.request('AVIATION_EUROPE_NL.json')
        self.assertTrue(self.controller.preflight(request)['ready'])
        file = next((self.controller.control_root / 'presentation-sources').glob('*.json'))
        cached = json.loads(file.read_bytes())
        qualification = cached['admission']['sourceQualification']
        qualification['segments'][0]['sourceId'] = 'IMPOSTOR_SOURCE'
        wire = m.canonical(qualification).decode()
        cached['admission'].update(sourceQualificationWireJSON=wire,
            sourceQualificationSHA256=m.sha(wire.encode()))
        file.write_bytes(m.canonical(cached))
        self.assertFalse(self.controller.preflight(request)['ready'])

    def test_both_cached_aggregate_copies_cannot_override_verified_actual_sources(self):
        request = self.request('AVIATION_EUROPE_NL.json')
        self.assertTrue(self.controller.preflight(request)['ready'])
        file = next((self.controller.control_root / 'presentation-sources').glob('*.json'))
        cached = json.loads(file.read_bytes())
        qualification = cached['admission']['sourceQualification']
        qualification['segments'][0]['sourceId'] = 'IMPOSTOR_SOURCE'
        wire = m.canonical(qualification).decode()
        for destination in (cached['admission'], cached['prepared']):
            destination.update(sourceQualification=qualification, sourceQualificationWireJSON=wire,
                sourceQualificationSHA256=m.sha(wire.encode()))
        ordered = json.loads(cached['preparedWireJSON'])
        ordered.update(sourceQualification=qualification, sourceQualificationWireJSON=wire,
            sourceQualificationSHA256=m.sha(wire.encode()))
        cached['preparedWireJSON'] = json.dumps(ordered, separators=(',', ':'), ensure_ascii=False)
        file.write_bytes(m.canonical(cached))
        result = self.controller.preflight(request)
        self.assertFalse(result['ready'])
        self.assertEqual(result['error']['code'], 'UP2_STORED_SOURCE_QUALIFICATION_INVALID')


if __name__ == '__main__':
    unittest.main()
