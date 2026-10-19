"""Real HTTP/auth and controller CPU contracts; every backend is an explicit fake.

No container, browser GPU, detached worker, external API or video is started.
Receipt fixtures below test the validator only, never authorize real work.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
from http.cookies import SimpleCookie
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_test_unified_entry', HERE / 'studio_entry.py')
entry = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = entry
spec.loader.exec_module(entry)
controller = entry.controller_module
DIGEST = 'sha256:' + 'b' * 64
ORIGIN = 'https://studio-test.invalid'


class FakeParentBackend:
    def __init__(self):
        self.calls = []

    def default_plan(self, profile):
        return json.loads((HERE.parent / 'verified-front-data-v4-recovery/PARENT_PLAN_80S.json').read_bytes())

    def bind_render_image(self, plan, profile, digest):
        result = deepcopy(plan)
        result['renderProfile']['imageDigest'] = digest
        return result

    def validate_render_plan(self, *args):
        return args[0]

    def preflight(self, *args, **kwargs):
        self.calls.append('old-preflight')
        raise AssertionError('An integrated submission must never fall back to the V1 runtime')

    def start_studio_job(self, *args, **kwargs):
        self.calls.append('old-start')
        raise AssertionError('No old start may receive V2 metadata')


class FakeBridge:
    def __init__(self):
        self.calls = []

    def gate_context(self, submission, **kwargs):
        return {'sourceCommit': 'a' * 40, 'sourceManifestSHA256': 'b' * 64,
            'sourceClosureManifestSHA256': 'c' * 64,
            'sceneSHA256': controller.parent.canonical_sha256(submission['videoPlan']),
            'imageDigest': kwargs['image_digest'], 'durationSeconds': 80, 'fps': 30,
            'sourceClosureVerified': True, 'imagePackageIncluded': True,
            'requiredModules': {'AREA.REVEAL': 'READY'}, 'dataBlockers': [],
            'referenceSHA256': 'd' * 64, 'candidateSHA256': 'e' * 64}

    def preflight(self, submission, **kwargs):
        self.calls.append(('preflight', deepcopy(submission)))
        return {'renderAllowed': False, 'gpuRenderingVerified': False,
                'checks': [{'name': 'TEST_HARDWARE', 'status': 'BLOCKED', 'code': 'TEST_NO_GPU'}]}

    def start_studio_job(self, *args, **kwargs):
        self.calls.append(('start', None))
        raise AssertionError('No GPU or fake detached launch is needed by these tests')


def value(schema='WORLD_ENGINE_STUDIO_PROMPT_V2', **visual):
    prompt = {'schema': schema, 'preset': 'VERIFIED_FRONT_V4_80S',
              'title': 'CPU integration fixture', 'durationSeconds': 80,
              'profile': 'V4_ARCHIVAL_80S'}
    if schema.endswith('_V2'):
        prompt['visualProfile'] = visual
    return {'prompt': json.dumps(prompt), 'durationSeconds': 80,
            'profile': 'V4_ARCHIVAL_80S', 'sfx': {'enabled': False}}


def policy(instance):
    result = {'schema': 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1',
        'validUntil': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'maxWallSeconds': 600, 'maxRetries': 0, 'maxCostAmount': '1',
        'currency': 'USD', 'gpuHourlyRate': '1'}
    with instance._cache.PrivateTree(instance.control_root) as root:
        root.write_json('operator_policy.json', result, replace=True)
    return result


def approval_fixture(instance, bridge, submission):
    context = bridge.gate_context(submission, image_digest=DIGEST)
    bindings = {key: context[key] for key in ('sourceCommit', 'sourceManifestSHA256',
        'sourceClosureManifestSHA256', 'sceneSHA256', 'imageDigest', 'referenceSHA256', 'candidateSHA256')}
    receipt = {'schema': 'WORLD_ENGINE_5S_USER_QUALITY_APPROVAL_V1',
        'userReview': 'PASS', **bindings,
        'targetDurationSeconds': 80, 'targetFps': 30,
        'reviewedAt': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        'validUntil': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        'candidate': {'durationSeconds': 5, 'fps': 30, 'width': 1080, 'height': 1920,
            'frames': 150, 'gpuVendor': 'NVIDIA', 'gpuRenderingVerified': True,
            'mp4FullyDecoded': True, 'gpuEvidenceSHA256': 'f' * 64},
        'referenceComparison': {'status': 'COMPLETED',
            'referenceSHA256': context['referenceSHA256'],
            'candidateSHA256': context['candidateSHA256'], 'evidenceSHA256': '1' * 64}}
    # Test-only synthetic evidence in an auto-cleaned private directory.
    with instance._cache.PrivateTree(instance.control_root) as root:
        with root.child('quality_receipts', create=True) as target:
            target.write_json('approval.json', receipt)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='unified-controller-')
        self.root = Path(self.tmp.name)
        self.backend, self.bridge = FakeParentBackend(), FakeBridge()
        self.instance = controller.StudioController(control_root=self.root / 'production',
            export_root=self.root / 'exports', image_digest=DIGEST,
            backend=self.backend, bridge=self.bridge)

    def tearDown(self):
        self.tmp.cleanup()

    def test_v1_normalizer_is_identical_but_new_entry_blocks_long_execution(self):
        raw = value('WORLD_ENGINE_STUDIO_PROMPT_V1')
        expected = controller.parent.studio_contracts.normalize_submission(raw,
            image_digest=DIGEST, backend=self.backend)
        self.assertEqual(expected, self.instance._normal(raw))
        report = self.instance.preflight(raw)
        self.assertFalse(report['ready'])
        self.assertIn('INTEGRATION_PROFILE_REQUIRED_BEFORE_80S', str(report))
        self.assertEqual(self.backend.calls, [])

    def test_v2_sibling_and_immutable_claim_identity_are_preserved(self):
        first = self.instance.submit(value())
        second = self.instance.submit(value(territoryOpacity=.7))
        self.assertNotEqual(first['submissionId'], second['submissionId'])
        with self.instance._cache.PrivateTree(self.instance.control_root) as root:
            a = self.instance._read_submission(root, first['submissionId'])['submission']
            b = self.instance._read_submission(root, second['submissionId'])['submission']
        self.assertEqual(a['videoPlan'], b['videoPlan'])
        self.assertEqual(a['integration']['visualProfile']['territoryOpacity'], .62)
        self.assertEqual(b['integration']['visualProfile']['territoryOpacity'], .7)
        self.assertEqual(self.backend.calls, [])

    def test_real_quality_gate_blocks_missing_receipt_before_any_native_gpu_check(self):
        policy(self.instance)
        result = self.instance.preflight(value())
        self.assertFalse(result['ready'])
        self.assertIn('INTEGRATION_QUALITY_RECEIPT_PATH_UNSAFE', str(result))
        self.assertEqual(self.bridge.calls, [])
        self.assertEqual(self.backend.calls, [])

    def test_real_quality_gate_accepts_private_fixture_then_routes_explicit_bridge(self):
        policy(self.instance)
        submission = self.instance._normal(value())
        approval_fixture(self.instance, self.bridge, submission)
        result = self.instance.preflight(value())
        self.assertFalse(result['ready'])
        self.assertIn('TEST_NO_GPU', str(result))
        self.assertEqual(self.bridge.calls[0][0], 'preflight')
        self.assertEqual(self.bridge.calls[0][1]['integration'], submission['integration'])
        self.assertEqual(self.backend.calls, [])

    def test_start_blocked_without_creating_claims_or_starting_backend(self):
        policy(self.instance)
        identifier = self.instance.submit(value())['submissionId']
        with self.assertRaises(controller.StudioError) as error:
            self.instance.start(identifier, 'cpu-request-123456', consent=True)
        self.assertEqual(error.exception.code, 'STUDIO_PREFLIGHT_BLOCKED')
        self.assertEqual(list((self.instance.control_root / 'requests').iterdir()), [])
        self.assertEqual(self.bridge.calls, [])

    def test_new_namespace_preserves_existing_state_and_reads_existing_policy(self):
        parent_root = self.root / 'production'
        with self.instance._cache.PrivateTree(parent_root) as root:
            root.write_json('existing-job.json', {'state': 'KEEP'})
            root.write_json('operator_policy.json', policy(self.instance))
        (self.instance.control_root / 'operator_policy.json').unlink()
        before = (parent_root / 'existing-job.json').read_bytes()
        self.instance.preflight(value())
        self.assertEqual((parent_root / 'existing-job.json').read_bytes(), before)
        self.assertEqual(self.instance.control_root.name, 'universal-integration-v1')

    def test_missing_bridge_method_never_falls_back(self):
        instance = controller.StudioController(control_root=self.root / 'other',
            export_root=self.root / 'exports', image_digest=DIGEST,
            backend=self.backend, bridge=object())
        result = instance.preflight(value())
        self.assertIn('STUDIO_UNIFIED_RUNTIME_NOT_CONNECTED', str(result))
        self.assertEqual(self.backend.calls, [])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='unified-http-')
        root = Path(self.tmp.name) / 'private'
        root.mkdir(mode=0o700)
        self.owner = root / 'owner-code'
        self.password = secrets.token_urlsafe(32)
        self.owner.write_text(self.password)
        self.owner.chmod(0o600)
        self.backend, self.bridge = FakeParentBackend(), FakeBridge()
        test = self
        def factory(**kwargs):
            test.controller = controller.StudioController(**kwargs,
                backend=test.backend, bridge=test.bridge)
            policy(test.controller)
            return test.controller
        self.app = entry.Application(root, self.owner, Path(self.tmp.name) / 'exports',
            DIGEST, controller_factory=factory, gpu_check=lambda: False, initial_origin=ORIGIN)
        self.server = entry.proxy.original.StudioHTTPServer(('127.0.0.1', 0), self.app.handler())
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, method='GET', body=None, cookie='', csrf='', host='studio-test.invalid', origin=ORIGIN):
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        headers = {'Host': host, 'Origin': origin, 'Sec-Fetch-Site': 'same-origin'}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-Studio-CSRF'] = csrf
        if body is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(body)
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        raw = response.read()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw
        cookie_value = ''
        for key, text in response.getheaders():
            if key.lower() == 'set-cookie':
                parsed = SimpleCookie(text)
                cookie_value += '; '.join(name + '=' + morsel.value for name, morsel in parsed.items())
        connection.close()
        return response.status, payload, cookie_value

    def login(self):
        status, record, cookie = self.request('/api/login', 'POST', {'password': self.password})
        self.assertEqual(status, 200)
        return cookie, record['csrf']

    def test_actual_http_normalizes_v2_without_gpu_and_keeps_auth_csrf(self):
        self.assertEqual(self.request('/api/integration/profile')[0], 401)
        cookie, csrf = self.login()
        self.assertEqual(self.request('/api/preflight', 'POST', value(), cookie)[0], 403)
        status, report, _ = self.request('/api/preflight', 'POST', value(), cookie, csrf)
        self.assertEqual(status, 200)
        self.assertTrue(report['valid'])
        self.assertFalse(report['ready'])
        status, stored, _ = self.request('/api/submissions', 'POST', value(), cookie, csrf)
        self.assertEqual(status, 201)
        self.assertRegex(stored['submissionId'], '^[a-f0-9]{64}$')
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.bridge.calls, [])

    def test_host_origin_protection_and_ui_job_namespace_remain(self):
        cookie, _ = self.login()
        self.assertGreaterEqual(self.request('/api/integration/profile', cookie=cookie, host='bad.invalid')[0], 400)
        self.assertEqual(self.request('/api/integration/profile', cookie=cookie, origin='https://bad.invalid')[0], 403)
        self.assertEqual(self.request('/api/integration/profile', cookie=cookie)[1]['profile'], 'VISUAL_UNIFIED_V1')
        status, script, _ = self.request('/app.js', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'world-studio-unified-v1-job', script)
        self.assertNotIn(b"'world-studio-job'", script)


if __name__ == '__main__':
    unittest.main()
