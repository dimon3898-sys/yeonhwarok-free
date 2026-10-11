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
from unittest.mock import patch
from http.server import ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gate1_release_server', HERE / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
BUNDLE = Path(os.environ.get('STATIC_PROOF_TEST_BUNDLE', '/tmp/terrain-shading-static-release-context/bundle'))
BASELINE = Path(os.environ.get('STATIC_PROOF_TEST_BASELINE', '/workspace/terrain-shading-results'))
LEGACY_BASELINE = Path(os.environ.get('STATIC_PROOF_TEST_LEGACY_BASELINE', '/tmp/world-map-gate1/iteration-05'))
PNG_NAME = 'SUEZ_TERRAIN_SHADING_RTX4080S.png'
RENDERER_SHA = 'e0108a8bf3cb3828529b9077925b9429455dbccd2c695f797f2578ac904b067d'
SOFTWARE_PNG_SHA = '29323353b1e76af7dfbc54407a9cdbdbb559fbfefe9ffac08d70f65f54e98a8d'
DEM_SHA = '08a1b86fbe9c47a9495336e0e83d0bfdea014a4e5c7b36beaaa544aa283fd5a8'


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='gate1-api-test-')
        cls.png = (BASELINE / 'D-final.png').read_bytes()
        cls.calls = []
        def controlled_worker(mode, output, emit):
            cls.calls.append(mode)
            emit({'stage': 'FOCUSED_TEST_WORKER', 'result': 'TEST_ONLY'})
            if mode == 'proof':
                (output / PNG_NAME).write_bytes(cls.png)
            plan = json.loads((BUNDLE / 'compiled-plan.json').read_text())
            height = json.loads((BUNDLE / 'height-source.json').read_text())
            # Simulated admission transport only. No browser/GPU execution takes
            # place; downloaded bytes are the preserved Software D fixture.
            return True, {'test_fixture': True, 'gpu_visual_quality': 'NOT_RUN',
                          'gpu_renderer': 'NVIDIA GeForce RTX 4080 SUPER (TEST_FIXTURE_NOT_HARDWARE)',
                          'capability': {'webgl2': True, 'actualPixelDraw': True, 'gl_error': 0},
                          'gl_error': 0, 'selected_gpu_backend': 'egl',
                          'renderer_source_hash': plan['provenance']['shaderHash'],
                          'scene_hash': plan['provenance']['sceneHash'],
                          'shader_version': cls.service.manifest['shader_version'],
                          'theme_version': cls.service.manifest['theme_version'],
                          'dem_hash': height['sha256'],
                          'dem_source_hashes': [{'file': Path(r['file']).name, 'sha256': r['sha256']} for r in height['originals']],
                          'software_d_final_hash': SOFTWARE_PNG_SHA,
                          'render_parameters': json.loads((BUNDLE / 'render-parameters.json').read_text()),
                          'output_resolution': [1080, 1920], 'render_duration_ms': 'UNKNOWN',
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

    def wait_job(self, identifier, headers, expected='PASS'):
        limit = time.monotonic() + 3
        while time.monotonic() < limit:
            code, _, body = self.request('GET', '/api/jobs/' + identifier, headers=headers)
            self.assertEqual(code, 200)
            value = json.loads(body)
            if value['status'] != 'RUNNING' and 'finished' in value:
                self.assertEqual(value['status'], expected)
                return value
            time.sleep(.01)
        self.fail('Focused fixture worker deadline exceeded')

    def job(self, endpoint='/api/generate', headers=None):
        headers = headers or self.login()
        if endpoint == '/api/generate':
            self.job('/api/check-gpu', headers)
        code, _, body = self.request('POST', endpoint, {}, headers)
        self.assertEqual(code, 202)
        identifier = json.loads(body)['job']
        self.wait_job(identifier, headers)
        return identifier, headers

    def test_source_renderer_exact(self):
        self.assertEqual((BUNDLE / 'renderer.mjs').read_bytes(), (BASELINE / 'renderer-source.mjs').read_bytes())
        self.assertEqual(hashlib.sha256((BUNDLE / 'renderer.mjs').read_bytes()).hexdigest(), RENDERER_SHA)

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

    def test_dem_height_source_exact_and_routed(self):
        height = json.loads((BUNDLE / 'height-source.json').read_text())
        software = json.loads((BASELINE / 'height-source.json').read_text())
        for key in ['dimensions', 'footprint', 'firstSample', 'pixelSpacing', 'scale', 'offset', 'NoData', 'sha256', 'byteLength', 'format']:
            self.assertEqual(height[key], software[key], key)
        self.assertEqual(height['byteLength'], 207360000)
        self.assertEqual(height['sha256'], DEM_SHA)
        manifest = json.loads((BUNDLE / 'manifest.json').read_text())
        route = next(row for row in manifest['routes'] if row['url'] == height['url'])
        file = BUNDLE / route['file']
        self.assertEqual(file.stat().st_size, height['byteLength'])
        # Stream the admitted 197.75 MiB Float32 asset to avoid a duplicate RAM copy.
        digest = hashlib.sha256()
        with file.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        self.assertEqual(digest.hexdigest(), DEM_SHA)
        self.assertEqual([r['sha256'] for r in height['originals']], [r['sha256'] for r in software['originals']])

    def test_render_parameters_are_final_d(self):
        parameters = json.loads((BUNDLE / 'render-parameters.json').read_text())
        self.assertEqual(parameters, {'dem': True, 'correctedLight': True, 'verticalExaggeration': 2,
                                      'bakedSuppression': 0.1, 'shadingCorrection': 'OUTPUT'})

    def test_source_manifest_preserves_software_final_identity(self):
        self.assertEqual(hashlib.sha256(self.png).hexdigest(), SOFTWARE_PNG_SHA)
        manifest = json.loads((BUNDLE / 'manifest.json').read_text())
        self.assertEqual(manifest['png_filename'], PNG_NAME)
        self.assertEqual(manifest['source_identity']['shaderHash'], RENDERER_SHA)
        self.assertEqual(manifest['source_identity']['softwareProofHash'], SOFTWARE_PNG_SHA)
        self.assertEqual(manifest['source_identity']['softwareDFinalHash'], SOFTWARE_PNG_SHA)
        self.assertEqual(manifest['source_identity']['heightSourceHash'], DEM_SHA)
        height = json.loads((BUNDLE / 'height-source.json').read_text())
        self.assertEqual(manifest['source_identity']['demSourceHashes'], [r['sha256'] for r in height['originals']])
        self.assertEqual(manifest['source_identity']['originalHeightDescriptorHash'], hashlib.sha256((BASELINE / 'height-source.json').read_bytes()).hexdigest())

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

    def test_generate_requires_successful_check_in_same_session(self):
        before = len(self.calls)
        code, _, body = self.request('POST', '/api/generate', {}, self.login())
        self.assertEqual(code, 403)
        self.assertEqual(json.loads(body)['error'], 'GPU_PROBE_REQUIRED')
        self.assertEqual(before, len(self.calls))

    def test_probe_readiness_reported_from_server_session(self):
        headers = self.login()
        self.assertFalse(json.loads(self.request('GET', '/api/session', headers=headers)[2])['gpu_probe_ready'])
        self.job('/api/check-gpu', headers)
        self.assertTrue(json.loads(self.request('GET', '/api/session', headers=headers)[2])['gpu_probe_ready'])

    def test_failed_probe_does_not_authorize_generation(self):
        headers = self.login()
        def failed_worker(mode, output, emit):
            return False, {'error_code': 'WEBGL2_REQUIRED', 'failed_stage': 'WEBGL2_CREATE',
                           'capability_result': {'result': 'FAIL'}, 'gpu_visual_quality': 'NOT_RUN'}
        with patch.object(self.service, 'worker', failed_worker):
            code, _, body = self.request('POST', '/api/check-gpu', {}, headers)
            self.assertEqual(code, 202)
            identifier = json.loads(body)['job']
            self.wait_job(identifier, headers, 'FAIL')
        self.assertEqual(self.request('POST', '/api/generate', {}, headers)[0], 403)
        diagnostic = json.loads(self.request('GET', '/download/' + identifier + '/diagnostic', headers=headers)[2])
        self.assertEqual(diagnostic['error_code'], 'WEBGL2_REQUIRED')
        self.assertEqual(diagnostic['failed_stage'], 'WEBGL2_CREATE')

    def test_software_probe_cannot_authorize_generation_even_with_pass_flag(self):
        headers = self.login()
        def software_worker(mode, output, emit):
            return True, {'gpu_renderer': 'ANGLE SwiftShader', 'capability_result': {'result': 'PASS'},
                          'capability': {'webgl2': True, 'actualPixelDraw': True, 'gl_error': 0}}
        with patch.object(self.service, 'worker', software_worker):
            code, _, body = self.request('POST', '/api/check-gpu', {}, headers)
            self.assertEqual(code, 202)
            self.wait_job(json.loads(body)['job'], headers)
        self.assertEqual(self.request('POST', '/api/generate', {}, headers)[0], 403)

    def test_pixel_error_probe_cannot_authorize_generation(self):
        headers = self.login()
        def bad_pixel_worker(mode, output, emit):
            return True, {'gpu_renderer': 'NVIDIA GeForce RTX 4080 SUPER', 'capability_result': {'result': 'PASS'},
                          'capability': {'webgl2': True, 'actualPixelDraw': True, 'gl_error': 1282}}
        with patch.object(self.service, 'worker', bad_pixel_worker):
            code, _, body = self.request('POST', '/api/check-gpu', {}, headers)
            self.assertEqual(code, 202)
            self.wait_job(json.loads(body)['job'], headers)
        self.assertEqual(self.request('POST', '/api/generate', {}, headers)[0], 403)

    def test_expired_probe_requires_another_check(self):
        job, headers = self.job('/api/check-gpu')
        self.service.jobs[job]['finished'] = time.time() - 901
        self.assertEqual(self.request('POST', '/api/generate', {}, headers)[0], 403)

    def test_gpu_probe_is_not_shared_with_new_login(self):
        self.job('/api/check-gpu')
        self.assertEqual(self.request('POST', '/api/generate', {}, self.login())[0], 403)

    def test_job_and_download_are_bound_to_session(self):
        identifier, _ = self.job()
        foreign = self.login()
        for path in ['/api/jobs/' + identifier, '/download/' + identifier + '/png', '/download/' + identifier + '/diagnostic']:
            self.assertEqual(self.request('GET', path, headers=foreign)[0], 404, path)

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
        self.assertEqual(response_headers['Content-Disposition'], 'attachment; filename="' + PNG_NAME + '"')
        self.assertEqual(body, self.png)
        self.assertEqual(hashlib.sha256(body).hexdigest(), SOFTWARE_PNG_SHA)

    def test_png_lossless_resolution(self):
        job, headers = self.job()
        body = self.request('GET', '/download/' + job + '/png', headers=headers)[2]
        self.assertEqual(body[:8], bytes([137,80,78,71,13,10,26,10]))
        self.assertEqual([int.from_bytes(body[16:20], 'big'), int.from_bytes(body[20:24], 'big')], [1080, 1920])

    def test_diagnostic_download(self):
        job, headers = self.job()
        code, response_headers, body = self.request('GET', '/download/' + job + '/diagnostic', headers=headers)
        self.assertEqual(code, 200)
        self.assertEqual(response_headers['Content-Disposition'], 'attachment; filename="SUEZ_TERRAIN_SHADING_RTX4080S.diagnostic.json"')
        diagnostic = json.loads(body)
        self.assertEqual(diagnostic['gpu_visual_quality'], 'NOT_RUN')
        self.assertTrue(diagnostic['test_fixture'])
        self.assertEqual(diagnostic['renderer_source_hash'], RENDERER_SHA)
        self.assertEqual(diagnostic['dem_hash'], DEM_SHA)
        self.assertEqual(diagnostic['software_d_final_hash'], SOFTWARE_PNG_SHA)
        self.assertEqual(diagnostic['output_resolution'], [1080, 1920])
        self.assertEqual(diagnostic['gl_error'], 0)
        self.assertEqual(diagnostic['selected_gpu_backend'], 'egl')
        self.assertEqual(len(diagnostic['dem_source_hashes']), 4)

    def test_probe_cannot_download_png(self):
        job, headers = self.job('/api/check-gpu')
        self.assertEqual(self.request('GET', '/download/' + job + '/png', headers=headers)[0], 409)

    def test_failed_admission_blocks_png(self):
        identifier, headers = self.job('/api/check-gpu')
        self.service.jobs[identifier].update(status='FAIL', mode='proof')
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
        self.assertEqual(hashlib.sha256((LEGACY_BASELINE / 'proof.png').read_bytes()).hexdigest(), '3e4830cb7db4b6c585b6caec1d77330c257c54918432af5fad9678d6535f0d17')
        root = Path(os.environ.get('STATIC_PROOF_TEST_EVIDENCE_ROOT', str(LEGACY_BASELINE.parent)))
        self.assertEqual(hashlib.sha256((root / 'visual-iterations.png').read_bytes()).hexdigest(), 'e474d0c3d6e69a14b886e03037079932d9bf2321cd2f3e35268ac454c3bed845')
        self.assertEqual(hashlib.sha256((root / 'REPORT.md').read_bytes()).hexdigest(), '22d1763fa5ca9bf0eaedefacc6320443dbebcebc84811ede1ddb39131272a633')


class LiveResult(unittest.TextTestResult):
    total = 0

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.outcome = 'PASS'
        print(json.dumps({'test': test.id(), 'stage': 'START', 'completed': self.testsRun - 1,
                          'total': self.total}), flush=True)

    def stopTest(self, test):
        super().stopTest(test)
        print(json.dumps({'test': test.id(), 'stage': 'END', 'result': self.outcome, 'elapsed_seconds': round(time.monotonic() - self.started, 3),
                          'completed': self.testsRun,
                          'total': self.total}), flush=True)

    def addFailure(self, test, error):
        self.outcome = 'FAIL'
        super().addFailure(test, error)

    def addError(self, test, error):
        self.outcome = 'ERROR'
        super().addError(test, error)


class LiveRunner(unittest.TextTestRunner):
    def run(self, test):
        LiveResult.total = test.countTestCases()
        return super().run(test)


if __name__ == '__main__':
    unittest.main(testRunner=LiveRunner(verbosity=2, resultclass=LiveResult))
