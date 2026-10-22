"""Actual localhost HTTP security and fail-closed readiness; no render mocks PASS."""
import http.client
import importlib.util
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_rd_studio_preflight_tests', HERE / 'studio_preflight.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def request(window='A_CONTEXT'):
    return {'schema': m.REQUEST_SCHEMA, 'windowId': window, 'targetSHA256': m.TARGET_SHA256}


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rd-preflight-test-', dir='/workspace')
        self.root = Path(self.temp.name)
        self.controller = m.StudioController(control_root=self.root / 'control',
            export_root=self.root / 'exports', allow_free_data_review=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_windows_honestly_map_one_global_timeline(self):
        for window, source_range in m.WINDOWS.items():
            with self.subTest(window=window):
                result = self.controller.preflight(request(window))
                self.assertTrue(result['valid'])
                self.assertFalse(result['ready'])
                self.assertFalse(result['renderAllowed'])
                self.assertEqual(result['blockers'], ['CAPABILITY_EXTENSION_REQUIRED', 'DATA_DETAIL_BLOCKED'])
                self.assertEqual(result['window']['sourceFrameRange'], list(source_range))
                count = source_range[1] - source_range[0]
                self.assertEqual(result['window']['localFrameRange'], [0, count])
                self.assertEqual(result['totalFrames'], count)
                self.assertLessEqual(count, 240)
                self.assertEqual(result['window']['globalFrameCount'], 546)
                self.assertEqual(result['window']['globalCoreFrameRange'], [source_range[0] - 29, source_range[1] - 29])
                self.assertFalse(result['window']['resetTimeline'])
                self.assertFalse(result['nvidiaVerified'])

    def test_client_admission_overrides_are_rejected(self):
        for key, value in [('ready', True), ('renderAllowed', True), ('capabilities', {'rotation': True}),
                ('dataBindings', {}), ('paidRenderAllowed', True), ('globalFrameCount', 180)]:
            with self.subTest(key=key):
                result = self.controller.preflight({**request(), key: value})
                self.assertFalse(result['valid'])
                self.assertEqual(result['error']['code'], 'RD_EXPLICIT_SEALED_WINDOW_REQUEST_REQUIRED')

    def test_missing_or_unknown_window_and_wrong_types_are_rejected(self):
        for value in ('ALL', None, [], {}, 29):
            with self.subTest(value=value):
                self.assertFalse(self.controller.preflight({**request(), 'windowId': value})['valid'])
        no_window = request()
        del no_window['windowId']
        self.assertFalse(self.controller.preflight(no_window)['valid'])

    def test_client_target_sha_cannot_select_different_target(self):
        result = self.controller.preflight({**request(), 'targetSHA256': '0' * 64})
        self.assertFalse(result['valid'])
        self.assertEqual(result['error']['code'], 'RD_EXPLICIT_SEALED_WINDOW_REQUEST_REQUIRED')

    def test_changed_server_target_or_partial_input_is_not_readiness_evidence(self):
        target = self.root / 'changed-target.json'
        target.write_text('{}')
        for field, error in [('TARGET_FILE', 'RD_SERVER_TARGET_CHANGED'),
                ('PARTIAL_INPUT_FILE', 'RD_SERVER_PARTIAL_INPUT_CHANGED')]:
            with self.subTest(field=field), patch.object(m, field, target):
                result = self.controller.preflight(request())
                self.assertFalse(result['valid'])
                self.assertEqual(result['error']['code'], error)

    def test_changed_protected_renderer_is_rejected(self):
        renderer = self.root / 'changed-renderer.mjs'
        renderer.write_text('export const fake=true;')
        with patch.object(m, 'RENDERER_FILE', renderer):
            result = self.controller.preflight(request())
        self.assertFalse(result['valid'])
        self.assertEqual(result['error']['code'], 'RD_PROTECTED_RENDERER_CHANGED')

    def test_reference_submit_never_saves_or_claims_or_launches(self):
        before = snapshot(self.root)
        with patch.object(self.controller, '_save_submission') as save, \
                patch.object(m.preserved.manager.subprocess, 'Popen') as process:
            for window in m.WINDOWS:
                with self.assertRaises(m.StudioError) as raised:
                    self.controller.submit(request(window))
                self.assertEqual(raised.exception.code, 'RD_REFERENCE_RENDER_GATES_BLOCKED')
            save.assert_not_called()
            process.assert_not_called()
        self.assertEqual(snapshot(self.root), before)

    def test_readiness_is_read_only_and_missing_inputs_are_explicit(self):
        before = snapshot(self.root)
        result = self.controller.preflight(request())
        self.assertTrue(result['rendererStillProtected'])
        fields = [item['field'] for item in result['missingDataBindings']]
        self.assertEqual(len(fields), 6)
        self.assertIn('detailGeometryId', fields)
        self.assertIn('detailBoundaryGeometryId', fields)
        self.assertIn('basemapSourceIds.detailCoverage', fields)
        self.assertNotIn('primaryCountryGeometryId', fields)
        self.assertNotIn('metricValueId', fields)
        self.assertEqual(result['availableBindings']['primaryCountryGeometryId'], 'COUNTRY_ESP')
        self.assertEqual(len(result['availableBindings']['contextLocationIds']), 2)
        self.assertEqual(result['availableBindings']['metricValueId'], 'REF64306_OBSERVED_TEXT_85_M')
        self.assertEqual(result['partialInputSHA256'], m.PARTIAL_INPUT_SHA256)
        self.assertFalse(result['unverifiedClaims'][0]['blocksObservedTextDisplay'])
        self.assertFalse(result['createsSubmission'])
        self.assertFalse(result['createsClaim'])
        self.assertFalse(result['actualRendererDrawPerformed'])
        self.assertEqual(snapshot(self.root), before)

    def test_non_reference_preflight_delegates_preserved_behavior(self):
        old = m.preserved.StudioController(control_root=self.root / 'legacy-control',
            export_root=self.root / 'legacy-exports', allow_free_data_review=True)
        malformed_old = {'schema': m.preserved.REQUEST_SCHEMA, 'prompt': {}}
        self.assertEqual(self.controller.preflight(malformed_old), old.preflight(malformed_old))

    def test_non_reference_submission_delegates_preserved_behavior(self):
        value = {'schema': m.preserved.REQUEST_SCHEMA, 'prompt': {}}
        with patch.object(m.preserved.StudioController, 'submit', return_value={'existingPath': True}) as old:
            self.assertEqual(self.controller.submit(value), {'existingPath': True})
            old.assert_called_once_with(value)

    def test_missing_owner_file_remains_a_startup_failure(self):
        with self.assertRaises(Exception) as raised:
            m.local_application(state_root=self.root / 'missing-owner-state', owner_file=self.root / 'missing-owner',
                export_root=self.root / 'missing-owner-exports', port=18191)
        self.assertEqual(getattr(raised.exception, 'code', None), 'STUDIO_OWNER_FILE_REQUIRED')

    def test_actual_http_preserves_auth_origin_csrf_and_blocks_submission(self):
        owner = self.root / 'owner'
        # Fresh private fixture, never an existing credential or a chat token.
        owner.write_text(secrets.token_urlsafe(48))
        owner.chmod(0o600)
        with socket.socket() as socket_probe:
            socket_probe.bind(('127.0.0.1', 0))
            port = socket_probe.getsockname()[1]
        app = m.local_application(state_root=self.root / 'http-state', owner_file=owner,
            export_root=self.root / 'http-exports', port=port)
        http_server = m.server.ThreadingHTTPServer(('127.0.0.1', port), m.server.make_handler(app))
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(port)

        def call(path, body=None, cookie=None, csrf=None, supplied_origin=origin):
            client = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            headers = {'Origin': supplied_origin, 'Content-Type': 'application/json'}
            if cookie:
                headers['Cookie'] = cookie
            if csrf:
                headers['X-Studio-CSRF'] = csrf
            client.request('GET' if body is None else 'POST', path,
                None if body is None else json.dumps(body), headers)
            response = client.getresponse()
            raw, status, saved_cookie = response.read(), response.status, response.getheader('Set-Cookie')
            client.close()
            return status, json.loads(raw), saved_cookie

        try:
            status, health, _ = call('/healthz')
            self.assertEqual(status, 200)
            self.assertTrue(health['authenticationRequired'])
            self.assertFalse(health['renderingVerified'])
            self.assertEqual(call('/api/preflight', request())[0], 401)
            self.assertEqual(call('/api/preflight', request(), supplied_origin='https://attacker.invalid')[0], 403)
            self.assertEqual(call('/api/login', {'password': 'invalid-fixture-password'})[0], 401)
            status, login, cookie = call('/api/login', {'password': owner.read_text()})
            self.assertEqual(status, 200)
            cookie = cookie.split(';', 1)[0]
            self.assertEqual(call('/api/preflight', request(), cookie)[0], 403)
            before = snapshot(app.controller.control_root)
            with patch.object(m.preserved.manager.subprocess, 'Popen') as process:
                for window in m.WINDOWS:
                    status, result, _ = call('/api/preflight', request(window), cookie, login['csrf'])
                    self.assertEqual(status, 200)
                    self.assertTrue(result['valid'])
                    self.assertFalse(result['ready'])
                    self.assertFalse(result['renderAllowed'])
                    self.assertEqual(result['window']['id'], window)
                    status, denied, _ = call('/api/submissions', request(window), cookie, login['csrf'])
                    self.assertEqual(status, 409)
                    self.assertEqual(denied['error']['code'], 'RD_REFERENCE_RENDER_GATES_BLOCKED')
                    self.assertFalse(denied['renderAllowed'])
                process.assert_not_called()
            self.assertEqual(snapshot(app.controller.control_root), before)
            self.assertEqual(call('/api/preflight', request(), cookie, login['csrf'], 'https://attacker.invalid')[0], 403)
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
