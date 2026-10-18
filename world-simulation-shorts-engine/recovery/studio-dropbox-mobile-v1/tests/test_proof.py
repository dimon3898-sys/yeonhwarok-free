"""Focused mobile proof orchestration tests; all provider/Docker work is mocked."""
from contextlib import redirect_stdout
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_mobile_proof_tests', HERE / 'proof_ci.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_SHA': 'b' * 40, 'GITHUB_RUN_ID': '12345',
            'GITHUB_RUN_ATTEMPT': '2'}, clear=False)
        self.env.start()
        self.scratch = tempfile.TemporaryDirectory(prefix='mobile-proof-test-')
        self.root = Path(self.scratch.name)
        self.value = {'requestSourceCommit': 'b' * 40}
        self.helper = SimpleNamespace(ci=SimpleNamespace(state=lambda: self.value, save=Mock(),
            run=Mock(return_value=SimpleNamespace(stdout='', stderr='', returncode=0)),
            require_free_runner=Mock(return_value={'status': 'PASS'})),
            pull=Mock(), external=Mock())
        self.outcomes = {name: 'success' for name in ('preflight', 'scan', 'pull', 'external')}

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def complete(self):
        self.value.update(proofPrerequisitesVerified=True, pullVerified=True,
            protectedParentUnchanged=True, inheritedDependenciesChanged=False,
            imageReference=proof.SOURCE_IMAGE, imageDigest=proof.SOURCE_DIGEST,
            secretScan={'status': 'PASS'}, imageHashes={'sourceCommit': proof.SOURCE_COMMIT},
            builder={'status': 'PASS'}, externalDurability={'status': 'PASS',
                'offlineTokenRefreshVerified': True, 'metadataReadVerified': True,
                'externalStorageRecoveryVerified': True, 'gpuExecuted': False,
                'productionRenderingStarted': False, 'productionApprovalGranted': False,
                'secretFilesRemoved': True, 'syntheticMedia': True,
                'proofId': 'a' * 64, 'checkpointId': 'c' * 64,
                'expiresUnix': int(time.time()) + 86400})

    def test_exact_old_helper_is_read_only_and_rebound_in_memory(self):
        before = proof.OFFLINE.read_bytes()
        helper = proof.frozen_helper()
        self.assertEqual(hashlib.sha256(before).hexdigest(), proof.OFFLINE_CI_SHA)
        self.assertEqual(helper.ci.BRANCH, proof.BRANCH)
        self.assertEqual(helper.ci.NAMESPACE, proof.NAMESPACE)
        self.assertEqual(helper.HERE, proof.OFFLINE.parent)
        self.assertEqual(before, proof.OFFLINE.read_bytes())

    def test_changed_old_helper_rejected_before_import(self):
        path = self.root / 'fixture.py'
        path.write_text('# synthetic changed helper\n')
        with patch.object(proof, 'OFFLINE', path):
            with self.assertRaisesRegex(RuntimeError, 'MOBILE_FROZEN_OFFLINE_HELPER_SHA_MISMATCH'):
                proof.frozen_helper()

    def test_image_binding_is_scoped_and_restored_on_failure(self):
        with patch.dict(os.environ, {'RESULT_PUBLISHED_TAG': 'existing'}, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                with proof.original_image_source_binding():
                    self.assertEqual(os.environ['GITHUB_SHA'], proof.SOURCE_COMMIT)
                    self.assertEqual(os.environ['RESULT_PUBLISHED_DIGEST'], proof.SOURCE_DIGEST)
                    raise RuntimeError('fixture')
            self.assertEqual(os.environ['GITHUB_SHA'], 'b' * 40)
            self.assertEqual(os.environ['RESULT_PUBLISHED_TAG'], 'existing')

    def test_preflight_reuses_free_runner_guard_and_keeps_request_source(self):
        proof.preflight(self.helper)
        self.helper.ci.require_free_runner.assert_called_once_with()
        self.assertEqual(self.value['requestSourceCommit'], 'b' * 40)
        self.assertEqual(self.value['imageSourceCommit'], proof.SOURCE_COMMIT)
        self.assertIs(self.value['imageBuildRequested'], False)
        self.assertIs(self.value['imagePushRequested'], False)

    def test_additive_validator_uses_same_pinned_scanner_and_rejects_unsafe_report(self):
        self.helper.ci.secret_scan = Mock(return_value={'status': 'PASS'})
        report = {'status': 'PASS', 'files': 12, 'protectedChanges': 0, 'gpuExecuted': False,
                  'secretScan': {'status': 'PASS', 'findings': 0, 'rawFindings': 5,
                                 'classifiedVendorFunctionNames': 5}}
        self.helper.ci.run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(report))
        with patch.object(proof, 'location', return_value=self.root):
            proof.scan(self.helper)
        self.helper.ci.secret_scan.assert_called_once_with()
        command = self.helper.ci.run.call_args.args[0]
        self.assertEqual(command[-2:], ['--scanner', str(self.root / 'scanner/gitleaks')])
        self.assertEqual(self.value['secretScan']['findings'], 0)
        for field, changed in (('protectedChanges', 1), ('gpuExecuted', True), ('status', 'FAIL')):
            bad = dict(report, **{field: changed})
            self.helper.ci.run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(bad))
            with patch.object(proof, 'location', return_value=self.root):
                with self.assertRaisesRegex(RuntimeError, 'MOBILE_ADDITIVE_SOURCE_VALIDATION_REQUIRED'):
                    proof.scan(self.helper)
        bad = dict(report, secretScan=dict(report['secretScan'], findings=1))
        self.helper.ci.run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(bad))
        with patch.object(proof, 'location', return_value=self.root):
            with self.assertRaisesRegex(RuntimeError, 'MOBILE_ADDITIVE_SOURCE_VALIDATION_REQUIRED'):
                proof.scan(self.helper)

    def test_missing_secrets_are_blocked_never_passed(self):
        self.value['externalDurability'] = {'status': 'BLOCKED',
            'reasonCode': 'OFFLINE_EXTERNAL_SECRETS_NOT_BOUND'}
        report = proof.safe_proof(self.value, self.outcomes)
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['reasonCode'], 'MOBILE_DROPBOX_SECRETS_NOT_BOUND')
        self.assertFalse(report['offlineTokenRefreshVerified'])
        self.assertFalse(report['externalStorageRecoveryVerified'])
        self.assertNotIn('proofId', report)

    def test_only_complete_real_provider_report_can_pass(self):
        self.complete()
        report = proof.safe_proof(self.value, self.outcomes)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['reasonCode'], 'MOBILE_DROPBOX_CPU_RECOVERY_VERIFIED')
        self.assertEqual(report['schema'], 'WORLD_ENGINE_MOBILE_DROPBOX_PROOF_V1')
        self.assertEqual((report['runId'], report['attempt']), (12345, 2))
        self.assertIs(report['gpuExecuted'], False)
        self.assertIs(report['productionRenderingStarted'], False)

    def test_incomplete_or_failed_prerequisites_never_pass(self):
        self.complete()
        for field, value in (('pullVerified', False), ('protectedParentUnchanged', False),
                             ('proofPrerequisitesVerified', False),
                             ('inheritedDependenciesChanged', True), ('imageReference', 'wrong'),
                             ('imageDigest', 'wrong'), ('imageHashes', {'sourceCommit': 'wrong'})):
            original = self.value[field]
            self.value[field] = value
            with self.subTest(field=field):
                self.assertNotEqual(proof.safe_proof(self.value, self.outcomes)['status'], 'PASS')
            self.value[field] = original
        for phase in self.outcomes:
            changed = dict(self.outcomes, **{phase: 'failure'})
            self.assertNotEqual(proof.safe_proof(self.value, changed)['status'], 'PASS')

    def test_no_expired_malformed_or_missing_proof_claim(self):
        self.complete()
        original = dict(self.value['externalDurability'])
        for field, value in (('expiresUnix', int(time.time()) - 1), ('expiresUnix', True),
                             ('proofId', 'not-a-hash'), ('checkpointId', None),
                             ('secretFilesRemoved', False), ('metadataReadVerified', False),
                             ('offlineTokenRefreshVerified', False), ('syntheticMedia', False),
                             ('productionApprovalGranted', True), ('gpuExecuted', True)):
            self.value['externalDurability'] = dict(original, **{field: value})
            with self.subTest(field=field):
                report = proof.safe_proof(self.value, self.outcomes)
                self.assertNotEqual(report['status'], 'PASS')
                self.assertFalse(report['externalStorageRecoveryVerified'])
                self.assertNotIn('checkpointId', report)

    def test_secret_or_raw_output_fields_never_persist(self):
        self.complete()
        self.value['untrustedOutput'] = 'DO_NOT_PUBLISH_FIXTURE'
        self.value['externalDurability']['rawTokenBody'] = 'DO_NOT_PUBLISH_FIXTURE'
        report = proof.safe_proof(self.value, self.outcomes)
        self.assertNotIn('DO_NOT_PUBLISH_FIXTURE', json.dumps(report))
        self.assertNotIn('rawTokenBody', report)
        self.assertNotIn('untrustedOutput', report)

    def test_provider_failure_is_nonpass_with_sanitized_code(self):
        self.value['externalDurability'] = {'status': 'BLOCKED', 'reasonCode': 'arbitrary HTTP body'}
        report = proof.safe_proof(self.value, self.outcomes)
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['reasonCode'], 'MOBILE_CPU_PROOF_FAILED')
        self.assertFalse(report['metadataReadVerified'])

    def test_external_cannot_bypass_source_protection(self):
        with self.assertRaisesRegex(RuntimeError, 'MOBILE_IMMUTABLE_SOURCE_PROTECTION_REQUIRED'):
            proof.external(self.helper)
        self.helper.external.assert_not_called()
        self.value['proofPrerequisitesVerified'] = True
        proof.external(self.helper)
        self.helper.external.assert_called_once_with()

    def test_pull_uses_existing_helper_and_checks_all_protections(self):
        self.complete()
        proof.pull(self.helper)
        self.helper.pull.assert_called_once_with()
        self.assertTrue(self.value['proofPrerequisitesVerified'])
        self.value['protectedParentUnchanged'] = False
        with self.assertRaisesRegex(RuntimeError, 'MOBILE_FROZEN_IMAGE_VERIFICATION_FAILED'):
            proof.pull(self.helper)

    def test_unsafe_run_identifier_rejected(self):
        for run in ('../12', '0', '123/45'):
            with patch.dict(os.environ, {'GITHUB_RUN_ID': run}):
                with self.assertRaisesRegex(RuntimeError, 'MOBILE_PROOF_RUN_ID_REQUIRED'):
                    proof.identifiers()

    def test_persist_is_newnamespace_only_and_existing_evidence_is_preserved(self):
        self.complete()
        def run(command, **kwargs):
            if command == ['git', 'diff', '--cached', '--name-only']:
                return SimpleNamespace(stdout='\n'.join(sorted([
                    proof.NAMESPACE + '/runs/12345-2/proof.json',
                    proof.NAMESPACE + '/runs/12345-2/SHA256SUMS'])) + '\n')
            return SimpleNamespace(stdout='', stderr='', returncode=0)
        self.helper.ci.run = Mock(side_effect=run)
        with patch.object(proof, 'REPO', self.root), \
             patch.dict(os.environ, {'RESULT_STEP_OUTCOMES': json.dumps(self.outcomes)}), \
             redirect_stdout(io.StringIO()):
            proof.persist(self.helper)
            path = self.root / proof.NAMESPACE / 'runs/12345-2/proof.json'
            before = path.read_bytes()
            self.assertEqual(json.loads(before)['status'], 'PASS')
            self.assertEqual({p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file()},
                             {proof.NAMESPACE + '/runs/12345-2/proof.json',
                              proof.NAMESPACE + '/runs/12345-2/SHA256SUMS'})
            with self.assertRaisesRegex(RuntimeError, 'MOBILE_EXISTING_PROOF_OVERWRITE_FORBIDDEN'):
                proof.persist(self.helper)
            self.assertEqual(before, path.read_bytes())
        commands = self.helper.ci.run.call_args_list
        self.assertTrue(any('[skip ci]' in str(item) for item in commands))
        self.assertFalse(any('docker' in str(item) for item in commands))

    def test_workflow_cannot_build_push_deploy_or_use_nonstandard_runner(self):
        root = HERE.parents[2]
        text = (root / proof.WORKFLOW).read_text()
        self.assertIn('cancel-in-progress: false', text)
        self.assertEqual(text.count('runs-on: ubuntu-24.04'), 2)
        self.assertNotIn('packages: write', text)
        for command in ('docker build', 'docker push', 'gcube workload', '--gpus'):
            self.assertNotIn(command, text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn('needs: cpu-mobile', text)
        self.assertIn('contents: write', text)
        self.assertEqual(text.count('WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN:'), 1)


if __name__ == '__main__':
    unittest.main()
