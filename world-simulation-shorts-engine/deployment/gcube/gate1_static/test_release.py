"""Focused release contracts; real browser download is checked separately."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gate1_release_server', HERE / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
BUNDLE = Path(os.environ.get('STATIC_PROOF_TEST_BUNDLE', '/tmp/gate1-static-release-context/bundle'))
BASELINE = Path(os.environ.get('STATIC_PROOF_TEST_BASELINE', '/tmp/world-map-gate1/iteration-05'))


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='gate1-api-test-')
        cls.png = (BASELINE / 'proof.png').read_bytes()
        cls.calls = []
        def controlled_worker(mode, output, emit):
            cls.calls.append(mode)
            emit({'stage': 'FOCUSED_TEST_WORKER', 'result': 'TEST_ONLY'})
            if mode == 'proof':
                (output / 'SUEZ_STATIC_PROOF_RTX4080S.png').write_bytes(cls.png)
            return True, {'test_fixture': True, 'gpu_visual_quality': 'NOT_RUN', 'gpu_renderer': 'TEST_FIXTURE_NOT_HARDWARE',
                          'frame_count': 1 if mode == 'proof' else 0, 'capability_result': {'result': 'PASS'}}
        cls.service = server.ProofService(BUNDLE, cls.temp.name, 'release-test-owner-code', controlled_worker)
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(cls.service))
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_headers = {}

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        values = dict(headers or {})
        if body is not None:
            body = json.dumps(body)
            values['Content-Type'] = 'application/json'
        conn.request(method, path, body, values)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def login(self):
        code, headers, body = self.request('POST', '/auth/login', {'password': 'release-test-owner-code'})
        self.assertEqual(code, 200)
        return {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-Proof-CSRF': json.loads(body)['csrf']}

    def job(self, endpoint='/api/generate'):
        headers = self.login()
        code, _, body = self.request('POST', endpoint, {}, headers)
        self.assertEqual(code, 202)
        identifier = json.loads(body)['job']
        limit = time.monotonic() + 3
        while time.monotonic() < limit:
            code, _, body = self.request('GET', '/api/jobs/' + identifier, headers=headers)
            value = json.loads(body)
            if value['status'] != 'RUNNING':
                self.assertEqual(value['status'], 'PASS')
                return identifier, headers
            time.sleep(.01)
        self.fail('Focused fixture worker deadline exceeded')

    def test_source_renderer_exact(self):
        self.assertEqual((BUNDLE / 'renderer.mjs').read_bytes(), (BASELINE / 'renderer-source.mjs').read_bytes())

    def test_compiled_plan_exact(self):
        self.assertEqual((BUNDLE / 'compiled-plan.json').read_bytes(), (BASELINE / 'compiled-plan.json').read_bytes())

    def test_frozen_asset_integrity(self):
        server.verify_bundle(BUNDLE)

    def test_shader_factory_unmodified(self):
        source = (BUNDLE / 'renderer.mjs').read_text()
        self.assertIn('export const createProofPreview=createMapInfographicRenderer;', source)
        self.assertIn('export const createProofFinal=createMapInfographicRenderer;', source)
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), json.loads((BUNDLE / 'compiled-plan.json').read_text())['provenance']['shaderHash'])

    def test_asset_plan_references(self):
        manifest = json.loads((BUNDLE / 'manifest.json').read_text())
        routes = {row['url'] for row in manifest['routes']}
        plan = json.loads((BUNDLE / 'compiled-plan.json').read_text())
        self.assertTrue(all(value['url'] in routes for value in plan['assets'].values()))

    def test_health_no_automatic_render(self):
        before = len(self.calls)
        code, _, body = self.request('GET', '/healthz')
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)['auto_render'])
        self.assertEqual(before, len(self.calls))

    def test_public_static_ui(self):
        code, _, body = self.request('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn(b'GENERATE STATIC PROOF', body)
        self.assertIn(b'DOWNLOAD PNG', body)

    def test_login_wrong_code(self):
        self.assertEqual(self.request('POST', '/auth/login', {'password': 'wrong'})[0], 403)

    def test_authentication_required(self):
        for url in ['/api/session', '/api/jobs/notfound', '/download/notfound/png', '/download/notfound/diagnostic']:
            self.assertEqual(self.request('GET', url)[0], 401)

    def test_csrf_required(self):
        headers = self.login()
        headers.pop('X-Proof-CSRF')
        self.assertEqual(self.request('POST', '/api/generate', {}, headers)[0], 403)

    def test_request_cannot_change_scene(self):
        headers = self.login()
        for body in [{'scene': 'Singapore'}, {'mode': 'validate-software'}, {'width': 540}, {'frames': 720}, {'theme': 'new'}]:
            self.assertEqual(self.request('POST', '/api/generate', body, headers)[0], 400)

    def test_png_exact_download_name_and_bytes(self):
        job, headers = self.job()
        code, response_headers, body = self.request('GET', '/download/' + job + '/png', headers=headers)
        self.assertEqual(code, 200)
        self.assertEqual(response_headers['Content-Type'], 'image/png')
        self.assertEqual(response_headers['Content-Disposition'], 'attachment; filename="SUEZ_STATIC_PROOF_RTX4080S.png"')
        self.assertEqual(body, self.png)

    def test_png_lossless_resolution(self):
        job, headers = self.job()
        body = self.request('GET', '/download/' + job + '/png', headers=headers)[2]
        self.assertEqual(body[:8], bytes([137,80,78,71,13,10,26,10]))
        self.assertEqual([int.from_bytes(body[16:20], 'big'), int.from_bytes(body[20:24], 'big')], [1080, 1920])

    def test_diagnostic_download(self):
        job, headers = self.job()
        code, response_headers, body = self.request('GET', '/download/' + job + '/diagnostic', headers=headers)
        self.assertEqual(code, 200)
        self.assertEqual(response_headers['Content-Disposition'], 'attachment; filename="SUEZ_STATIC_PROOF_RTX4080S.diagnostic.json"')
        self.assertEqual(json.loads(body)['gpu_visual_quality'], 'NOT_RUN')

    def test_probe_cannot_download_png(self):
        job, headers = self.job('/api/check-gpu')
        self.assertEqual(self.request('GET', '/download/' + job + '/png', headers=headers)[0], 409)

    def test_failed_admission_blocks_png(self):
        headers = self.login()
        identifier = 'failed-admission'
        self.service.jobs[identifier] = {'id': identifier, 'status': 'FAIL', 'mode': 'proof'}
        self.assertEqual(self.request('GET', '/download/' + identifier + '/png', headers=headers)[0], 409)

    def test_no_video_or_audio_imports(self):
        for file in ['server.py', 'worker.mjs']:
            source = (HERE / file).read_text()
            for forbidden in ['ffmpeg', 'render.mjs', 'audio_pipeline', 'tts_pipeline', 'mobile_server', 'production_plan']:
                self.assertNotIn(forbidden, source)

    def test_no_software_mode_public(self):
        source = (HERE / 'server.py').read_text()
        self.assertNotIn('validate-software', source)
        self.assertIn("env['WORLD_ENGINE_RENDER_MODE'] = 'gpu-required'", source)

    def test_original_software_proof_preserved(self):
        self.assertEqual(hashlib.sha256((BASELINE / 'proof.png').read_bytes()).hexdigest(), '3e4830cb7db4b6c585b6caec1d77330c257c54918432af5fad9678d6535f0d17')
        root = Path(os.environ.get('STATIC_PROOF_TEST_EVIDENCE_ROOT', str(BASELINE.parent)))
        self.assertEqual(hashlib.sha256((root / 'visual-iterations.png').read_bytes()).hexdigest(), 'e474d0c3d6e69a14b886e03037079932d9bf2321cd2f3e35268ac454c3bed845')
        self.assertEqual(hashlib.sha256((root / 'REPORT.md').read_bytes()).hexdigest(), '22d1763fa5ca9bf0eaedefacc6320443dbebcebc84811ede1ddb39131272a633')


class LiveResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.outcome = 'PASS'
        print(json.dumps({'test': test.id(), 'stage': 'START', 'completed': self.testsRun - 1, 'total': 19}), flush=True)

    def stopTest(self, test):
        super().stopTest(test)
        print(json.dumps({'test': test.id(), 'stage': 'END', 'result': self.outcome, 'elapsed_seconds': round(time.monotonic() - self.started, 3),
                          'completed': self.testsRun, 'total': 19}), flush=True)

    def addFailure(self, test, error):
        self.outcome = 'FAIL'
        super().addFailure(test, error)

    def addError(self, test, error):
        self.outcome = 'ERROR'
        super().addError(test, error)


if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(verbosity=2, resultclass=LiveResult))
