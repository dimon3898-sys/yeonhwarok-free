"""CPU contract/native-fixture checks; injected preparation tests are mocks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_video as preparation
from contracts import canonical_sha256, validate_plan
from cache import PrivateTree
from planner import plan_topic


class NativePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bound = json.loads((ROOT / 'fixtures/PLAN_80S.json').read_bytes())
        cls.payload = json.loads((ROOT / 'fixtures/NATIVE_PAYLOAD.json').read_bytes())

    def test_persisted_native_files_actual_hash_and_binding(self):
        report = preparation.validate_native_binding(self.bound, self.payload)
        self.assertEqual(report['status'], 'VERIFIED')
        self.assertEqual(report['nativeFiles'], 5)
        self.assertFalse(report['gpuExecuted'])
        self.assertEqual(report['cameraStartFrame'] + report['eventStartFrame'], report['nativeLockFrame'])
        validate_plan(self.bound, require_renderable=True)

    def test_generic_catalog_fixture_wiring(self):
        plan = plan_topic('한국전쟁', duration_seconds=80)
        payload = preparation.build_native_payload(plan)
        self.assertEqual(payload, self.payload)
        self.assertEqual(payload['nativeRuntimeFixture'], self.bound['sourceManifest']['nativeRuntimeFixture'])

    def test_80_to_600_ready_contract_same_native_data(self):
        for seconds in (80, 120, 180, 300, 600):
            with self.subTest(seconds=seconds), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'plan.json'
                plan = preparation.prepare_topic('한국전쟁', output, duration_seconds=seconds)
                self.assertEqual(plan['totalFrames'], seconds * 30)
                self.assertEqual(plan['renderProfile']['status'], 'READY')
                self.assertFalse(plan['performanceTarget']['costApproved'])
                self.assertEqual(json.loads((Path(temporary) / 'NATIVE_PAYLOAD.json').read_bytes()), self.payload)

    def test_optional_image_digest_bound_before_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'plan.json'
            digest = 'sha256:' + '3' * 64
            plan = preparation.prepare_topic('한국전쟁 80초', path, image_digest=digest)
            self.assertEqual(plan['renderProfile']['imageDigest'], digest)
            self.assertEqual(plan['renderProfile']['imageBindingStatus'], 'OPERATOR_CONFIGURED_IMMUTABLE_DIGEST')
            self.assertTrue(all(s['renderProfile']['imageDigest'] == digest for s in plan['scenes']))
        self.assertEqual(self.bound['renderProfile']['imageBindingStatus'], 'IMAGE_BINDING_REQUIRED')
        self.assertNotIn('imageDigest', self.bound['renderProfile'])

    def test_malformed_image_digest_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'plan.json'
            with self.assertRaisesRegex(preparation.PreparationError, 'INVALID_IMAGE_DIGEST'):
                preparation.prepare_topic('한국전쟁 80초', path, image_digest='mutable-tag')
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_plan_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'plan.json'
            output.write_bytes(b'preserve previous')
            with self.assertRaisesRegex(preparation.PreparationError, 'PLAN_OUTPUT_ALREADY_EXISTS'):
                preparation.prepare_topic('한국전쟁 80초', output)
            self.assertEqual(output.read_bytes(), b'preserve previous')

    def test_existing_payload_conflict_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            native = Path(temporary) / 'NATIVE_PAYLOAD.json'
            native.write_bytes(b'preserved conflict')
            with self.assertRaisesRegex(preparation.PreparationError, 'EXISTING_NATIVE_PAYLOAD_CONFLICT'):
                preparation.prepare_topic('한국전쟁 80초', Path(temporary) / 'plan.json')
            self.assertEqual(native.read_bytes(), b'preserved conflict')

    def test_payload_hash_tampering_rejected(self):
        payload = deepcopy(self.payload)
        payload['nativeFiles']['scene']['sha256'] = '0' * 64
        with self.assertRaisesRegex(preparation.PreparationError, 'NATIVE_INPUT_HASH_MISMATCH'):
            preparation.validate_native_binding(self.bound, payload)

    def test_wrong_country_anchor_and_resolution_rejected(self):
        for modify, code in ((lambda p: p['legacyScenePlan']['camera_intent'].__setitem__('anchor', [1, 2]), 'NATIVE_EVENT_ANCHOR_MISMATCH'),
                             (lambda p: p['legacyScenePlan']['camera_intent']['native_context'].__setitem__('primary_country_id', 'OTHER'), 'NATIVE_COUNTRY_BINDING_MISMATCH'),
                             (lambda p: p.__setitem__('resolution', {'width': 1920, 'height': 1080}), 'NATIVE_OUTPUT_RESOLUTION_MISMATCH')):
            plan = deepcopy(self.bound)
            modify(plan)
            with self.subTest(code=code), self.assertRaisesRegex(preparation.PreparationError, code):
                preparation.validate_native_binding(plan, self.payload)

    def test_camera_fps_and_lock_fail_without_core_changes(self):
        plan = deepcopy(self.bound)
        plan['fps'] = 24
        with self.assertRaisesRegex(preparation.PreparationError, 'NATIVE_CAMERA_FPS_MISMATCH'):
            preparation.validate_native_binding(plan, self.payload)
        payload = deepcopy(self.payload)
        payload['cameraStartFrame'] = 0
        with self.assertRaisesRegex(preparation.PreparationError, 'EVENT_BEFORE_NATIVE_CAMERA_LOCK'):
            preparation.validate_native_binding(self.bound, payload)

    def test_path_traversal_and_symlinks_rejected(self):
        payload = deepcopy(self.payload)
        payload['nativeFiles']['scene']['path'] = '../outside.json'
        with self.assertRaisesRegex(preparation.PreparationError, 'NATIVE_ENGINE_RELATIVE_PATH_REQUIRED'):
            preparation.validate_native_binding(self.bound, payload)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'target.json'
            target.write_bytes(b'{}')
            link = Path(temporary) / 'link.json'
            link.symlink_to(target)
            with self.assertRaisesRegex(preparation.PreparationError, 'SOURCE_SYMLINK_FORBIDDEN'):
                preparation._safe_regular(link)


class MockPreparedInputRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / 'fixtures/PLAN_80S.json').read_bytes())
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.calls = []
        self.overlay = mock.patch.object(preparation, '_verify_overlay', return_value={'status': 'PASS', 'testOnly': False, 'manifestSha256': '2' * 64})
        self.verifier = mock.patch.object(preparation, '_verify_activation', side_effect=self.verify_mock_activation)
        self.factory = mock.patch.object(preparation, '_reference_preparation', return_value=SimpleNamespace(prepare_activation=self.fake_prepare))
        self.overlay.start(); self.verifier.start(); self.factory.start()
        self.addCleanup(self.overlay.stop); self.addCleanup(self.verifier.stop); self.addCleanup(self.factory.stop)
        self.addCleanup(self.temporary.cleanup)

    def fake_prepare(self, root, variant):
        self.calls.append(str(root))
        self.assertEqual(variant, 'F')
        target = Path(root) / 'activation.json'
        raw = b'{"testOnly":"MOCK_CPU_PREPARATION"}'
        target.write_bytes(raw); target.chmod(0o600)
        bundle = Path(root) / 'bundle.bin'
        bundle.write_bytes(b'original signed float values'); bundle.chmod(0o600)
        return {'activationFile': str(target), 'activationSha256': hashlib.sha256(raw).hexdigest()}

    def verify_mock_activation(self, path, expected):
        self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected)
        return {'status': 'PASS', 'testOnly': True, 'gpuExecuted': False}

    def test_mock_original_preparation_called_once_reused_receipt(self):
        first = preparation.prepare_job_inputs(self.plan, self.root)
        second = preparation.prepare_job_inputs(self.plan, self.root)
        self.assertFalse(first['cacheHit'])
        self.assertTrue(second['cacheHit'])
        self.assertFalse(second['gpuExecuted'])
        self.assertEqual(first['activationSha256'], second['activationSha256'])
        self.assertEqual(len(self.calls), 1)

    def test_corrupt_prepared_part_not_reused_or_overwritten(self):
        first = preparation.prepare_job_inputs(self.plan, self.root)
        bundle = Path(first['activationFile']).parent / 'bundle.bin'
        bundle.write_bytes(b'corruption retained')
        with self.assertRaisesRegex(preparation.PreparationError, 'PREPARED_INPUT_HASH_MISMATCH'):
            preparation.prepare_job_inputs(self.plan, self.root)
        self.assertEqual(bundle.read_bytes(), b'corruption retained')
        self.assertEqual(len(self.calls), 1)

    def test_different_plan_cannot_rebind_existing_preparation(self):
        preparation.prepare_job_inputs(self.plan, self.root)
        changed = deepcopy(self.plan)
        changed['titleCandidates'].append('different authorized plan')
        with self.assertRaisesRegex(preparation.PreparationError, 'PREPARED_JOB_BINDING_MISMATCH'):
            preparation.prepare_job_inputs(changed, self.root)
        self.assertEqual(len(self.calls), 1)

    def test_failed_prepare_not_success_cached_and_partial_preserved(self):
        def fail(root, variant):
            partial = Path(root) / 'partial.bin'
            partial.write_bytes(b'partial preserved')
            raise preparation.PreparationError('MOCK_SOURCE_FAILURE')
        with mock.patch.object(preparation, '_reference_preparation', return_value=SimpleNamespace(prepare_activation=fail)):
            with self.assertRaisesRegex(preparation.PreparationError, 'MOCK_SOURCE_FAILURE'):
                preparation.prepare_job_inputs(self.plan, self.root)
        partial = self.root / 'runtime-inputs/attempt-0001/partial.bin'
        self.assertEqual(partial.read_bytes(), b'partial preserved')
        self.assertFalse((self.root / 'runtime-inputs/INPUTS.json').exists())
        successful = preparation.prepare_job_inputs(self.plan, self.root)
        self.assertIn('attempt-0002', successful['activationFile'])
        self.assertEqual(partial.read_bytes(), b'partial preserved')

    def test_failed_prepare_retry_limit_is_bounded(self):
        def fail(root, variant):
            (Path(root) / 'partial.bin').write_bytes(b'keep')
            raise preparation.PreparationError('MOCK_SOURCE_FAILURE')
        with mock.patch.object(preparation, '_reference_preparation', return_value=SimpleNamespace(prepare_activation=fail)):
            for _ in range(2):
                with self.assertRaisesRegex(preparation.PreparationError, 'MOCK_SOURCE_FAILURE'):
                    preparation.prepare_job_inputs(self.plan, self.root)
            with self.assertRaisesRegex(preparation.PreparationError, 'PREPARATION_RETRY_LIMIT_REACHED'):
                preparation.prepare_job_inputs(self.plan, self.root)
        self.assertEqual(len(list((self.root / 'runtime-inputs').glob('attempt-*'))), 2)

    def test_corrupt_receipt_attempt_path_cannot_escape(self):
        preparation.prepare_job_inputs(self.plan, self.root)
        with PrivateTree(self.root / 'runtime-inputs') as runtime, runtime.lock():
            receipt = runtime.json('INPUTS.json')
            receipt['attemptDirectory'] = '../../outside'
            runtime.write_json('INPUTS.json', receipt, replace=True)
        with self.assertRaisesRegex(preparation.PreparationError, 'PREPARED_ATTEMPT_PATH_INVALID'):
            preparation.prepare_job_inputs(self.plan, self.root)

    def test_previous_old_result_files_untouched(self):
        old = self.root / 'old-approved.mp4'
        old.write_bytes(b'not a real movie: protection test marker'); old.chmod(0o600)
        before = old.read_bytes()
        preparation.prepare_job_inputs(self.plan, self.root)
        self.assertEqual(old.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
