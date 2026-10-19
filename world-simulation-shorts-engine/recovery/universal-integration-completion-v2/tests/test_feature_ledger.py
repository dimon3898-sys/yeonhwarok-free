"""CPU-only ledger identity, receipt integrity and non-render claim tests."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('completion_feature_ledger', HERE / 'feature_ledger.py')
assert SPEC and SPEC.loader
ledger_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger_module)


class FeatureLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit, cls.prior = ledger_module.load_inputs()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.relative = 'world-simulation-shorts-engine/recovery/universal-integration-completion-v2/cpu_owner.py'
        self.source = self.repo / self.relative
        self.source.parent.mkdir(parents=True)
        self.source.write_text('# Explicit CPU fixture owner, not production or GPU evidence.\n')
        self.source_record = {'path': self.relative, 'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}

    def empty(self):
        return {'schema': 'WORLD_ENGINE_COMPLETION_CONNECTION_RECEIPTS_V1', 'receipts': []}

    def receipt(self, feature_ids=None):
        return {'id': 'cpu-fixture-owner',
                'featureIds': feature_ids or ['AREA.PRODUCTION_WHITE_GOLD'],
                'implementationExists': 'YES', 'studioV2Exposed': 'CONDITIONAL',
                'sceneJSONAddressable': 'YES', 'runtimeSelected': 'CONDITIONAL',
                'actualRendererConsumer': 'CPU_INSTRUMENTED',
                'sourceFiles': [self.source_record],
                'inputFields': ['completion.visualProfile'], 'factories': ['explicitCpuFactory'],
                'consumers': ['explicitCpuConsumer'],
                'cpuTests': [{'name': 'explicit CPU forwarding fixture', 'result': 'PASS'}],
                'evidenceKind': 'CPU_INSTRUMENTATION', 'actualOutputProduced': False}

    def build(self, connections):
        return ledger_module.build_ledger(self.audit, self.prior, connections, repo=self.repo)

    def synthetic_image_fixture(self):
        """Isolated fabricated bytes exercise proof admission, not a real build."""
        manifest = self.repo / ledger_module.COMPLETION_MANIFEST_PATH
        manifest.write_text('{"fixture":"SYNTHETIC_IMAGE_ADMISSION_TEST_ONLY"}\n')
        proof_path = manifest.parent / 'runs/synthetic-test/IMAGE_PROOF.json'
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof = {'schema': 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1', 'result': 'PASS',
                 'independentPullVerified': True, 'sourceHashesVerified': True,
                 'imageDigest': 'sha256:' + '7' * 64,
                 'sourceManifestSHA256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                 'baseDigest': ledger_module.BASE_IMAGE_DIGEST, 'sourceCommit': '8' * 40}
        image = {'state': 'INDEPENDENT_PULL_VERIFIED', 'digest': proof['imageDigest'],
                 'proof': {'path': proof_path.relative_to(self.repo).as_posix(), 'sha256': ''}}
        self.write_synthetic_image_proof(image, proof_path, proof)
        return image, proof_path, proof, manifest

    @staticmethod
    def write_synthetic_image_proof(image, path, proof):
        path.write_text(json.dumps(proof, sort_keys=True) + '\n')
        image['proof']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_preserves_all_151_original_feature_objects_and_exact_ids(self):
        result = self.build(self.empty())
        self.assertEqual(result['featureCount'], 151)
        self.assertEqual({r['id'] for r in result['features']}, {r['id'] for r in self.audit['features']})
        for original, row in zip(self.audit['features'], result['features']):
            with self.subTest(feature=original['id']):
                self.assertEqual({k: row[k] for k in original}, original)

    def test_preserves_exact_53_original_unwired_and_aliases(self):
        result = self.build(self.empty())
        unwired = ledger_module.unwired_ledger(result)
        expected = {r['id'] for r in self.audit['features'] if r['classification'] == 'NOT_WIRED'}
        self.assertEqual(len(expected), 53)
        self.assertEqual({r['id'] for r in unwired['features']}, expected)
        self.assertEqual(result['canonicalRecordGroups'], 146)
        prior_by_id = {r['id']: r for r in self.prior['features']}
        for row in result['features']:
            self.assertEqual(row['canonicalId'], prior_by_id[row['id']]['integrationReview']['canonicalId'])

    def test_no_receipts_preserves_previous_blockers_and_claims_no_cpu_gpu_output(self):
        result = self.build(self.empty())
        self.assertEqual(result['connectionReceiptCount'], 0)
        self.assertEqual(result['featuresWithConnectionReceipts'], 0)
        previous = {r['id']: r['integrationReview'] for r in self.prior['features']}
        for row in result['features']:
            with self.subTest(feature=row['id']):
                self.assertEqual(row['status'], previous[row['id']]['status'])
                self.assertEqual(row['cpuProof'], 'NOT_VERIFIED_FOR_COMPLETION')
                self.assertEqual(row['gpuProof'], 'NOT_VERIFIED')
                self.assertEqual(row['completionEvidence']['outputTrace'], {'state': 'NOT_PRODUCED'})
        self.assertEqual(result['actualOutputAppliedCount'], 0)
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertFalse(result['full80sRenderAllowed'])
        self.assertFalse(result['all151RequiredOnScreen'])

    def test_named_cpu_consumer_receipt_changes_only_addressed_rows_and_dynamic_counts(self):
        connections = self.empty()
        connections['receipts'] = [self.receipt()]
        result = self.build(connections)
        row = next(r for r in result['features'] if r['id'] == 'AREA.PRODUCTION_WHITE_GOLD')
        self.assertEqual(row['cpuProof'], 'PASS')
        self.assertEqual(row['actualRendererConsumer'], 'CPU_INSTRUMENTED')
        self.assertEqual(row['runtimeSelected'], 'CONDITIONAL')
        self.assertEqual(row['status'], 'SUPPORTING')
        self.assertEqual(row['gpuProof'], 'NOT_VERIFIED')
        self.assertEqual(result['featuresWithConnectionReceipts'], 1)
        self.assertEqual(sum(result['statusCounts'].values()), 151)
        unaffected = next(r for r in result['features'] if r['id'] == 'FLOW.MOVING_OBJECT')
        self.assertEqual(unaffected['status'], 'BLOCKED')
        self.assertEqual(unaffected['cpuProof'], 'NOT_VERIFIED_FOR_COMPLETION')

    def test_connecting_generic_flow_does_not_erase_missing_historical_actor_data(self):
        connections = self.empty()
        connections['receipts'] = [self.receipt(['FLOW.MOVING_OBJECT', 'FLOW.DIRECTIONAL_FLOW'])]
        result = self.build(connections)
        selected = [r for r in result['features'] if r['id'] in connections['receipts'][0]['featureIds']]
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(r['cpuProof'] == 'PASS' and r['status'] == 'BLOCKED' for r in selected))
        self.assertTrue(all(r['implementationExists'] == 'YES' for r in selected))

    def test_explicit_qualified_source_reclassification_requires_concrete_reason(self):
        receipt = self.receipt(['TERRITORY.SUPPLIED_AREA_COLOR'])
        receipt.update({'status': 'SUPPORTING', 'reason': 'Qualified supplied held-core support only; no complete bilateral ownership or invented complement is claimed.'})
        connections = self.empty()
        connections['receipts'] = [receipt]
        result = self.build(connections)
        row = next(r for r in result['features'] if r['id'] == 'TERRITORY.SUPPLIED_AREA_COLOR')
        self.assertEqual(row['status'], 'SUPPORTING')
        self.assertEqual(row['previousIntegrationReview']['status'], 'BLOCKED')
        receipt['reason'] = 'Ready'
        with self.assertRaisesRegex(ValueError, 'RECLASSIFICATION_REASON_REQUIRED'):
            self.build(connections)

    def test_blocking_reasons_cannot_be_hidden_by_supporting_status(self):
        receipt = self.receipt()
        receipt.update({'status': 'SUPPORTING', 'reason': 'A sufficiently detailed reason that nevertheless tries to hide the missing source.',
                        'blockingReasons': [{'code': 'MISSING_SOURCE', 'reason': 'Verified source ownership data are absent.'}]})
        connections = self.empty()
        connections['receipts'] = [receipt]
        with self.assertRaisesRegex(ValueError, 'BLOCKERS_CANNOT_BE_HIDDEN'):
            self.build(connections)
        receipt['status'] = 'BLOCKED'
        result = self.build(connections)
        self.assertEqual(next(r for r in result['features'] if r['id'] == 'AREA.PRODUCTION_WHITE_GOLD')['status'], 'BLOCKED')

    def test_changed_missing_symlink_and_traversal_source_rejected(self):
        connections = self.empty()
        connections['receipts'] = [self.receipt()]
        self.source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'SOURCE_SHA_MISMATCH'):
            self.build(connections)
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, 'SOURCE_FILE_UNAVAILABLE'):
            self.build(connections)
        self.source.symlink_to(HERE / 'feature_ledger.py')
        with self.assertRaisesRegex(ValueError, 'SOURCE_FILE_UNAVAILABLE'):
            self.build(connections)
        connections['receipts'][0]['sourceFiles'][0]['path'] = '../secret'
        with self.assertRaisesRegex(ValueError, 'SOURCE_PATH_OR_SHA_INVALID'):
            self.build(connections)

    def test_unknown_fields_unknown_ids_and_duplicate_receipts_rejected(self):
        connections = self.empty()
        connections['receipts'] = [self.receipt()]
        connections['receipts'][0]['silentUnknown'] = True
        with self.assertRaisesRegex(ValueError, 'CONNECTION_UNKNOWN_FIELD'):
            self.build(connections)
        connections['receipts'] = [self.receipt(['UNKNOWN.NEW_FEATURE'])]
        with self.assertRaisesRegex(ValueError, 'FEATURE_ID_INVALID'):
            self.build(connections)
        connections['receipts'] = [self.receipt(), self.receipt()]
        with self.assertRaisesRegex(ValueError, 'CONNECTION_ID_INVALID'):
            self.build(connections)
        connections['receipts'][1]['id'] = 'other-id'
        with self.assertRaisesRegex(ValueError, 'FEATURE_REPEATED'):
            self.build(connections)

    def test_cpu_instrumentation_without_tests_factory_or_consumer_is_rejected(self):
        for field in ('cpuTests', 'factories', 'consumers'):
            with self.subTest(field=field):
                receipt = self.receipt()
                receipt[field] = []
                connections = self.empty()
                connections['receipts'] = [receipt]
                with self.assertRaisesRegex(ValueError, 'INSTRUMENTATION_PROOF_REQUIRED'):
                    self.build(connections)
        receipt = self.receipt()
        receipt['cpuTests'][0]['result'] = 'FAIL'
        connections['receipts'] = [receipt]
        with self.assertRaisesRegex(ValueError, 'INSTRUMENTATION_PROOF_REQUIRED'):
            self.build(connections)

    def test_gpu_applied_and_unverified_image_claims_are_rejected(self):
        connections = self.empty()
        receipt = self.receipt()
        receipt['actualOutputProduced'] = True
        connections['receipts'] = [receipt]
        with self.assertRaisesRegex(ValueError, 'NO_OUTPUT_CLAIM_ALLOWED'):
            self.build(connections)
        receipt['actualOutputProduced'] = False
        receipt['status'] = 'APPLIED'
        with self.assertRaisesRegex(ValueError, 'NO_APPLIED_OR_UNKNOWN_STATUS'):
            self.build(connections)
        connections = self.empty()
        connections['candidateImage'] = {'state': 'BUILD_PULL_VERIFIED', 'digest': 'sha256:' + '1' * 64}
        with self.assertRaisesRegex(ValueError, 'UNVERIFIED_CANDIDATE_IMAGE'):
            self.build(connections)

    def test_explicit_synthetic_verified_image_proof_admission_keeps_gpu_unverified(self):
        image, _, _, _ = self.synthetic_image_fixture()
        connections = self.empty()
        connections['candidateImage'] = image
        result = self.build(connections)
        self.assertEqual(result['candidateImage'], image)
        self.assertFalse(result['gpuRenderingVerified'])
        self.assertEqual(result['actualOutputAppliedCount'], 0)
        self.assertTrue(all(row['gpuProof'] == 'NOT_VERIFIED' for row in result['features']))

    def test_synthetic_image_proof_fields_fail_closed(self):
        image, path, original, _ = self.synthetic_image_fixture()
        cases = {'schema': 'UNSUPPORTED_IMAGE_PROOF', 'result': 'FAIL',
                 'independentPullVerified': False, 'sourceHashesVerified': False,
                 'imageDigest': 'sha256:' + '0' * 64, 'baseDigest': 'sha256:' + '0' * 64,
                 'sourceCommit': 'not-a-commit', 'unknownIgnoredField': True}
        for field, value in cases.items():
            with self.subTest(field=field):
                proof = dict(original)
                proof[field] = value
                self.write_synthetic_image_proof(image, path, proof)
                connections = self.empty()
                connections['candidateImage'] = image
                with self.assertRaisesRegex(ValueError, 'IMAGE_PROOF_INVALID'):
                    self.build(connections)
        missing_proof = {'state': 'INDEPENDENT_PULL_VERIFIED', 'digest': original['imageDigest']}
        connections['candidateImage'] = missing_proof
        with self.assertRaisesRegex(ValueError, 'UNVERIFIED_CANDIDATE_IMAGE'):
            self.build(connections)

    def test_synthetic_image_proof_file_and_source_manifest_are_hash_bound(self):
        image, path, proof, manifest = self.synthetic_image_fixture()
        connections = self.empty()
        connections['candidateImage'] = image
        path.write_text(json.dumps({**proof, 'result': 'FAIL'}))
        with self.assertRaisesRegex(ValueError, 'SOURCE_SHA_MISMATCH'):
            self.build(connections)
        self.write_synthetic_image_proof(image, path, proof)
        manifest.write_text('{"changed":"manifest after proof"}\n')
        with self.assertRaisesRegex(ValueError, 'SOURCE_MANIFEST_MISMATCH'):
            self.build(connections)
        manifest.unlink()
        with self.assertRaisesRegex(ValueError, 'SOURCE_MANIFEST_UNAVAILABLE'):
            self.build(connections)

    def test_csv_preserves_all_independent_axes_and_json_evidence(self):
        result = self.build(self.empty())
        rows = list(csv.DictReader(io.StringIO(ledger_module.ledger_csv(result['features']))))
        self.assertEqual(len(rows), 151)
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in self.audit['features']})
        for row, feature in zip(rows, result['features']):
            self.assertEqual(json.loads(row['originalAxes']), feature['axes'])
            self.assertEqual(json.loads(row['outputTrace']), {'state': 'NOT_PRODUCED'})
            self.assertEqual(row['gpuProof'], 'NOT_VERIFIED')

    def test_preserved_input_tampering_and_determinism(self):
        result = self.build(self.empty())
        self.assertEqual(result, self.build(self.empty()))
        audit = copy.deepcopy(self.audit)
        audit['features'][0]['name'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'PRIOR_AUDIT_IDENTITY_MISMATCH'):
            ledger_module.build_ledger(audit, self.prior, self.empty(), repo=self.repo)


if __name__ == '__main__':
    unittest.main()
