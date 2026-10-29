"""New publication contracts only. No Docker/skopeo/network/build/push calls."""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('new_publish_contract', HERE / 'publish_contract.py')
contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
HEAD = 'a' * 40
CID = 'sha256:' + 'b' * 64


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def evidence():
    stage = {'status': 'PREPARED_NOT_BUILT', 'sourceCommit': contract.SOURCE_COMMIT,
        'parentImageDigest': contract.SUCCESS_DIGEST,
        'sourceFiles': 353, 'unchangedSourceRows': 352, 'changedRuntimeRows': [contract.PROFILE],
        'overlayFiles': {name: {'bytes': 3, 'sha256': 'c' * 64} for name in contract.OVERLAY_FILES},
        'parentPreserved': True, 'imageBuilt': False, 'imagePublished': False,
        'parentRuntimeManifestSHA256': contract.OLD_RUNTIME_SHA,
        'parentStartupManifestSHA256': contract.OLD_STARTUP_SHA,
        'runtimeManifestSHA256': 'd' * 64, 'startupManifestSHA256': 'e' * 64,
        'browserLaunched': False, 'gpuExecuted': False, 'priorPassSuitesRerun': False}
    return {
        'PREFLIGHT': {'status': 'PASS', 'parentDigest': contract.SUCCESS_DIGEST,
            'profileSHA256': contract.PROFILE_SHA, 'reviewedHead': HEAD},
        'BUILD': {'status': 'PASS', 'candidateImageID': CID, 'parentDigest': contract.SUCCESS_DIGEST,
            'buildAttempts': 1, 'pushed': False, 'gpuExecuted': False},
        'CONNECTION_VERIFY': {'status': 'PASS', 'scope': 'NEW_OVERLAY_AND_PIN_CONNECTIONS_ONLY',
            'sourceFiles': 353, 'unchangedSourceRows': 352, 'overlayFilesVerified': 4,
            'entrypointPinsVerified': True, 'parentConfigPreservedExceptEntrypoint': True,
            'runtimeManifestSHA256': 'd' * 64, 'startupManifestSHA256': 'e' * 64,
            'browserLaunched': False, 'gpuExecuted': False, 'priorPassSuitesRerun': False},
        'IMAGE_SCOPE': {'status': 'PASS', 'parentPreserved': True, 'candidateImageID': CID,
            'parentLayerCount': 75, 'candidateLayerCount': 79, 'additionalCopyLayers': 4,
            'gpuExecuted': False, 'priorPassTestsRerun': False},
        'STAGE_RECEIPT': stage}


def layout(root):
    layers = [b'new publication synthetic layer 1', b'new publication synthetic layer 2']
    diff_ids = [contract.sha(raw) for raw in layers]
    config = wire({'rootfs': {'type': 'layers', 'diff_ids': diff_ids},
                   'architecture': 'amd64', 'os': 'linux'})
    cid = contract.sha(config)
    (root / cid[7:]).write_bytes(config)
    descriptors = []
    for raw in layers:
        blob = gzip.compress(raw, mtime=0)
        digest = contract.sha(blob); (root / digest[7:]).write_bytes(blob)
        descriptors.append({'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip',
                            'digest': digest, 'size': len(blob)})
    manifest = wire({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
        'config': {'mediaType': 'application/vnd.oci.image.config.v1+json',
                   'digest': cid, 'size': len(config)}, 'layers': descriptors})
    (root / 'manifest.json').write_bytes(manifest)
    (root / 'version').write_text('Directory Transport Version: 1.1\n')
    return cid, diff_ids, manifest


class PublicationContracts(unittest.TestCase):
    def test_01_candidate_namespace_and_unique_run_tag(self):
        destination = contract.candidate_destination('12345', '1', HEAD)
        self.assertEqual(destination, contract.CANDIDATE_PACKAGE + ':surface-v1-d259e61c96e8-12345-a1')
        self.assertEqual(contract.validate_destination(destination, '12345', 1, HEAD), destination)
        self.assertNotEqual(destination, contract.candidate_destination('12346', 1, HEAD))
        self.assertNotIn(contract.SUCCESS_PACKAGE + ':', destination)
    def test_02_old_namespace_and_unreviewed_or_retry_inputs_rejected(self):
        for target in [contract.SUCCESS_PACKAGE + ':candidate', 'ghcr.io/other/project:tag']:
            with self.assertRaisesRegex(RuntimeError, 'DESTINATION'): contract.validate_destination(target, '12345', 1, HEAD)
        for run, attempt, head in [('123', 2, HEAD), ('0', 1, HEAD), ('../123', 1, HEAD), ('123', 1, 'invalid')]:
            with self.assertRaises(RuntimeError): contract.candidate_destination(run, attempt, head)
    def test_03_all_existing_new_image_receipts_bind_without_reexecution(self):
        source = evidence(); before = copy.deepcopy(source)
        receipt = contract.validate_evidence(source, reviewed_head=HEAD)
        self.assertEqual(receipt['status'], 'PASS'); self.assertEqual(receipt['candidateImageID'], CID)
        self.assertEqual(len(receipt['evidenceBindingSHA256']), 64)
        self.assertEqual(source, before)
    def test_04_missing_failure_or_nonpass_evidence_blocks_publication(self):
        for transform in [lambda x: x.pop('BUILD'), lambda x: x.update(FAILURE={}),
                          lambda x: x['CONNECTION_VERIFY'].update(status='BLOCKED')]:
            source = evidence(); transform(source)
            with self.assertRaises(RuntimeError): contract.validate_evidence(source)
    def test_05_image_parent_pin_and_scope_crossbinding_are_required(self):
        cases = [('IMAGE_SCOPE', 'candidateImageID', 'sha256:' + 'f' * 64),
            ('BUILD', 'parentDigest', 'sha256:' + 'f' * 64),
            ('CONNECTION_VERIFY', 'runtimeManifestSHA256', 'f' * 64),
            ('STAGE_RECEIPT', 'unchangedSourceRows', 351),
            ('IMAGE_SCOPE', 'parentPreserved', False),
            ('PREFLIGHT', 'reviewedHead', 'f' * 40),
            ('BUILD', 'buildAttempts', 2)]
        for name, key, value in cases:
            source = evidence(); source[name][key] = value
            with self.subTest(name=name, key=key), self.assertRaises(RuntimeError):
                contract.validate_evidence(source, reviewed_head=HEAD)
    def test_06_gpu_browser_or_prior_suite_execution_is_not_silently_accepted(self):
        for name, key in [('BUILD', 'gpuExecuted'), ('CONNECTION_VERIFY', 'browserLaunched'),
                          ('CONNECTION_VERIFY', 'priorPassSuitesRerun'), ('IMAGE_SCOPE', 'priorPassTestsRerun')]:
            source = evidence(); source[name][key] = True
            with self.assertRaises(RuntimeError): contract.validate_evidence(source)
    def test_07_registry_ready_manifest_config_and_diffids_verified_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cid, diff_ids, raw = layout(root)
            result = contract.validate_registry_ready(root, cid, expected_diff_ids=diff_ids)
            self.assertEqual(result['expectedRegistryDigest'], contract.sha(raw))
            self.assertEqual(result['configDigest'], cid)
            self.assertNotEqual(result['expectedRegistryDigest'], cid)
            self.assertFalse(result['published'])
    def test_08_wrong_config_or_tested_diffids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cid, diff_ids, raw = layout(root)
            with self.assertRaisesRegex(RuntimeError, 'CONFIG_NOT_TESTED'):
                contract.validate_registry_ready(root, CID)
            with self.assertRaisesRegex(RuntimeError, 'DIFF_IDS_MISMATCH'):
                contract.validate_registry_ready(root, cid, expected_diff_ids=['sha256:' + 'f' * 64] * 2)
    def test_09_mutated_layer_or_config_bytes_are_rejected(self):
        for what in ['config', 'layer']:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); cid, _, raw = layout(root); m = json.loads(raw)
                target = root / (cid[7:] if what == 'config' else m['layers'][0]['digest'][7:])
                target.write_bytes(target.read_bytes() + b'x')
                with self.assertRaises(RuntimeError): contract.validate_registry_ready(root, cid)
    def test_10_foreign_urls_extra_file_symlink_and_index_rejected(self):
        for what in ['urls', 'file', 'symlink', 'index']:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); cid, _, raw = layout(root); m = json.loads(raw)
                if what == 'urls':
                    m['layers'][0]['urls'] = ['https://unapproved.invalid/blob']
                    (root / 'manifest.json').write_bytes(wire(m))
                elif what == 'file': (root / 'raw-stderr.txt').write_text('TEST_ONLY_SECRET_SENTINEL')
                elif what == 'symlink':
                    p = root / m['layers'][0]['digest'][7:]; saved = root.parent / ('synthetic-link-' + root.name)
                    saved.write_bytes(p.read_bytes()); p.unlink(); p.symlink_to(saved)
                    self.addCleanup(saved.unlink)
                else:
                    (root / 'manifest.json').write_bytes(wire({'schemaVersion': 2, 'manifests': []}))
                with self.subTest(what=what), self.assertRaises(RuntimeError): contract.validate_registry_ready(root, cid)
    def test_11_tag_absence_is_required_and_not_claimed_atomic(self):
        raw = b'new synthetic parent body'
        destination = contract.candidate_destination('123', 1, HEAD)
        with patch.object(contract, 'SUCCESS_DIGEST', contract.sha(raw)):
            result = contract.validate_publish_preconditions(destination, '123', 1, HEAD,
                tag_exists=False, parent_manifest_raw=raw)
            self.assertFalse(result['atomicRegistryTagCreationClaimed'])
            for exists in [True, None]:
                with self.assertRaisesRegex(RuntimeError, 'TAG_ALREADY_EXISTS_OR_UNKNOWN'):
                    contract.validate_publish_preconditions(destination, '123', 1, HEAD,
                        tag_exists=exists, parent_manifest_raw=raw)
    def test_12_postpublish_tag_and_digest_exact_bytes_match_expected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cid, _, raw = layout(Path(tmp)); parent = b'new synthetic successful parent body'
            with patch.object(contract, 'SUCCESS_DIGEST', contract.sha(parent)):
                result = contract.validate_registry_readback(contract.sha(raw), cid, raw, raw, parent, parent)
                self.assertTrue(result['expectedRegistryDigestMatched'])
                self.assertTrue(result['tagAndDigestBodiesIdentical'])
    def test_13_postpublish_conversion_or_success_tag_change_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            cid, _, raw = layout(Path(tmp)); parent = b'new synthetic parent body'
            with patch.object(contract, 'SUCCESS_DIGEST', contract.sha(parent)):
                for tag_raw, digest_raw, after in [(raw+b' ', raw+b' ', parent),
                    (raw, raw+b' ', parent), (raw, raw, parent+b'changed')]:
                    with self.assertRaises(RuntimeError):
                        contract.validate_registry_readback(contract.sha(raw), cid, tag_raw, digest_raw, parent, after)


if __name__ == '__main__': unittest.main(verbosity=2)
