"""NEW build-to-publication integration tests; no prior PASS suite is imported.

The actual five-receipt validator and registry-byte validators execute here.
Only process/registry effects are simulated. Recorded public parent bytes are
reused read-only; they are not fetched or revalidated as an old-image PASS.
"""
from __future__ import annotations

import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PUBLISH = HERE.parent / 'vulkan-surface-publish-v1'
spec = importlib.util.spec_from_file_location('new_build_publish_connection', PUBLISH / 'publish_candidate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
contract = module.contract
HEAD = 'a' * 40
RUN_ID = '43123456789'
TAG = 'world-engine-surface-candidate:d259e61c96e8-' + RUN_ID + '-a1'
SECRET = 'SYNTHETIC_CONNECTION_TEST_CREDENTIAL'
PARENT_FIXTURE = HERE.parent / 'ghcr-bootstrap-workflow-v1/tests/fixtures/parent-registry-manifest.json'


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def image_bytes(marker='verified'):
    # Seventy-five parent rows plus four copy rows, represented by tiny synthetic
    # layers. No Docker image, renderer or old runtime test is constructed/run.
    raw_layers = [('NEW CONNECTION FIXTURE %s %d' % (marker, i)).encode() for i in range(79)]
    diff_ids = [sha(raw) for raw in raw_layers]
    config = wire({'architecture': 'amd64', 'os': 'linux',
                   'rootfs': {'type': 'layers', 'diff_ids': diff_ids}})
    blobs = {sha(config)[7:]: config}
    layers = []
    for raw in raw_layers:
        blob = gzip.compress(raw, mtime=0)
        hashed = sha(blob)
        blobs[hashed[7:]] = blob
        layers.append({'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip',
                       'digest': hashed, 'size': len(blob)})
    manifest = wire({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                     'config': {'mediaType': 'application/vnd.oci.image.config.v1+json',
                                'digest': sha(config), 'size': len(config)}, 'layers': layers})
    return sha(config), diff_ids, manifest, blobs


def producer_receipts(candidate_id):
    # Producer field shapes come from actions_candidate.py/package_candidate.py;
    # no old test module or accepted suite is imported or executed.
    stage = {'status': 'PREPARED_NOT_BUILT', 'sourceCommit': contract.SOURCE_COMMIT,
        'parentImageDigest': contract.SUCCESS_DIGEST, 'sourceFiles': 353,
        'unchangedSourceRows': 352, 'changedRuntimeRows': [contract.PROFILE],
        'overlayFiles': {name: {'bytes': 3, 'sha256': 'c' * 64} for name in contract.OVERLAY_FILES},
        'parentPreserved': True, 'imageBuilt': False, 'imagePublished': False,
        'parentRuntimeManifestSHA256': contract.OLD_RUNTIME_SHA,
        'parentStartupManifestSHA256': contract.OLD_STARTUP_SHA,
        'runtimeManifestSHA256': 'd' * 64, 'startupManifestSHA256': 'e' * 64,
        'browserLaunched': False, 'gpuExecuted': False, 'priorPassSuitesRerun': False}
    return {
        'PREFLIGHT': {'status': 'PASS', 'parentDigest': contract.SUCCESS_DIGEST,
            'profileSHA256': contract.PROFILE_SHA, 'reviewedHead': HEAD},
        'BUILD': {'status': 'PASS', 'candidateImageID': candidate_id, 'candidateTag': TAG,
            'parentDigest': contract.SUCCESS_DIGEST, 'buildAttempts': 1,
            'pushed': False, 'gpuExecuted': False},
        'CONNECTION_VERIFY': {'status': 'PASS', 'scope': 'NEW_OVERLAY_AND_PIN_CONNECTIONS_ONLY',
            'sourceFiles': 353, 'unchangedSourceRows': 352, 'overlayFilesVerified': 4,
            'entrypointPinsVerified': True, 'parentConfigPreservedExceptEntrypoint': True,
            'runtimeManifestSHA256': 'd' * 64, 'startupManifestSHA256': 'e' * 64,
            'browserLaunched': False, 'gpuExecuted': False, 'priorPassSuitesRerun': False},
        'IMAGE_SCOPE': {'status': 'PASS', 'parentPreserved': True,
            'candidateImageID': candidate_id, 'parentLayerCount': 75,
            'candidateLayerCount': 79, 'additionalCopyLayers': 4,
            'gpuExecuted': False, 'priorPassTestsRerun': False},
        'STAGE_RECEIPT': stage}


def approved_policy():
    return {'schema': 'WORLD_ENGINE_SURFACE_PUBLISH_POLICY_V1',
        'status': 'APPROVED_FOR_SEPARATE_MANUAL_RUN', 'publicationApprovalRecorded': True,
        'candidateRepository': module.CANDIDATE_REPO, 'successfulRepository': module.SUCCESS_REPO,
        'parentDigest': module.PARENT_DIGEST, 'publisherIdentity': 'candidate-only-writer',
        'publisherCanWriteSuccessfulPackage': False, 'publisherCanDeleteSuccessfulPackage': False,
        'candidatePackageExclusiveWriterVerified': True, 'credentialHasDeleteScope': False,
        'aclEvidenceSHA256': 'b' * 64, 'approvedSkopeoVersion': 'skopeo version TEST_FIXTURE'}


def environment():
    return {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
        'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free',
        'GITHUB_REF': 'refs/heads/recovery/g1-capture-diagnostic-contract-20261028',
        'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64',
        'PUBLICATION_APPROVAL': 'PUBLISH_VERIFIED_SURFACE_CANDIDATE_ONCE',
        'SIGNAL_APPROVAL': 'BUILD_SURFACE_CANDIDATE_LOCAL_ONLY', 'ZERO_COST_CONFIRMED': 'true',
        'APPROVED_HEAD_SHA': HEAD, 'GITHUB_SHA': HEAD, 'GITHUB_RUN_ID': RUN_ID,
        'SURFACE_CANDIDATE_GHCR_USER': 'candidate-only-writer',
        'SURFACE_CANDIDATE_GHCR_TOKEN': SECRET}


class BuildPublicationConnectionTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('subprocess.run', side_effect=AssertionError('REAL_PROCESS_FORBIDDEN')))
        self.stack.enter_context(patch('urllib.request.urlopen', side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')))
        self.stack.enter_context(patch('urllib.request.build_opener', side_effect=AssertionError('REAL_NETWORK_FORBIDDEN')))
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix='new-build-publish-connection-'))
        self.root = Path(temporary)
        self.work, self.build, self.tool = (self.root / name for name in ('publish', 'build', 'tool'))
        for directory in (self.work / 'evidence', self.work / 'private', self.work / 'attempts',
                          self.build / 'evidence', self.tool):
            directory.mkdir(parents=True)
        self.cid, self.diff_ids, self.manifest, self.blobs = image_bytes()
        self.export_bytes = (self.cid, self.diff_ids, self.manifest, self.blobs)
        self.receipts = producer_receipts(self.cid)
        self.write_receipts()
        self.policy = approved_policy()
        self.write_policy()
        module.write(self.work / 'private/anonymous-auth.json', {'auths': {}})
        self.parent_raw = PARENT_FIXTURE.read_bytes()
        self.calls = []
        self.reads = []
        self.tag_id = self.cid
        self.id_inspection_id = self.cid
        self.output = io.StringIO()
        self.stack.enter_context(patch.object(module, 'HERE', self.tool))
        self.stack.enter_context(patch.object(module, 'skopeo', return_value='synthetic-skopeo'))
        self.stack.enter_context(patch.object(module, 'command', side_effect=self.command))
        self.stack.enter_context(patch.object(module, 'inspect_raw', side_effect=self.inspect_raw))
        self.stack.enter_context(patch.object(module.shutil, 'disk_usage', return_value=SimpleNamespace(free=10**12)))
        self.stack.enter_context(patch.dict(os.environ, environment(), clear=True))
        self.stack.enter_context(contextlib.redirect_stdout(self.output))

    def write_receipts(self):
        for name, value in self.receipts.items():
            module.write(self.build / 'evidence' / (name + '.json'), value)

    def write_policy(self):
        module.write(self.tool / 'PUBLISH_POLICY.json', self.policy)
        module.write(self.work / 'evidence/PUBLICATION_PREFLIGHT.json',
            {'status': 'PASS', 'policySHA256': module.digest((self.tool / 'PUBLISH_POLICY.json').read_bytes())})

    def command(self, args, **kwargs):
        self.calls.append(list(args))
        self.assertNotIn(SECRET, ' '.join(map(str, args)))
        if args[:4] == ['docker', '--host=unix:///var/run/docker.sock', 'image', 'inspect']:
            value = self.id_inspection_id if args[4] == self.cid else self.tag_id
            image = {'Id': value, 'Size': 8192, 'RootFS': {'Layers': self.diff_ids}}
            return subprocess.CompletedProcess(args, 0, wire([image]), b'')
        self.assertEqual(args[0], 'synthetic-skopeo')
        self.assertIn('--retry-times=0', args)
        if args[-1].startswith('dir:'):
            destination = Path(args[-1][4:])
            destination.mkdir()
            _, _, raw, blobs = self.export_bytes
            (destination / 'manifest.json').write_bytes(raw)
            for name, content in blobs.items():
                (destination / name).write_bytes(content)
            return subprocess.CompletedProcess(args, 0, b'', b'')
        self.assertIn('--preserve-digests', args)
        self.assertEqual(args[-1], 'docker://' + contract.candidate_destination(RUN_ID, 1, HEAD))
        Path(args[args.index('--digestfile') + 1]).write_text(sha(self.manifest))
        return subprocess.CompletedProcess(args, 0, b'', b'')

    def inspect_raw(self, tool, reference, authfile, **kwargs):
        self.reads.append(reference)
        if reference in (module.SUCCESS_TAG, module.SUCCESS_REPO + '@' + module.PARENT_DIGEST):
            return self.parent_raw
        if kwargs.get('absent_allowed'):
            return None
        self.assertTrue(reference.startswith(module.CANDIDATE_REPO))
        return self.manifest

    def exports(self):
        return [args for args in self.calls if args[0] == 'synthetic-skopeo' and args[-1].startswith('dir:')]

    def pushes(self):
        return [args for args in self.calls if args[0] == 'synthetic-skopeo' and args[-1].startswith('docker://')]

    def test_01_real_receipt_to_prepare_to_publish_bindings_with_mocked_effects(self):
        module.prepare(self.work, self.build)
        ready = module.load(self.work / 'evidence/REGISTRY_READY.json')
        self.assertEqual(ready['candidateImageID'], self.cid)
        self.assertEqual(ready['expectedRegistryDigest'], sha(self.manifest))
        self.assertEqual(ready['layerCount'], 79)
        self.assertEqual([args[-1] for args in self.calls if args[0] == 'docker'], [self.cid, TAG])
        module.publish(self.work, self.build)
        self.assertEqual(len(self.exports()), 1)
        self.assertEqual(len(self.pushes()), 1)
        receipt = module.load(self.work / 'evidence/PUBLISH_RECEIPT.json')
        self.assertEqual(receipt['candidateImageID'], self.cid)
        self.assertEqual(receipt['registryDigest'], sha(self.manifest))
        self.assertEqual(receipt['oldPackageWriteRequests'], 0)
        self.assertEqual(receipt['retryCount'], 0)
        self.assertFalse(receipt['gpuExecuted'])
        self.assertNotIn(SECRET, self.output.getvalue())

    def test_02_tag_or_tested_id_inspection_mismatch_blocks_before_export(self):
        self.tag_id = 'sha256:' + 'f' * 64
        with self.assertRaisesRegex(RuntimeError, 'BUILD_PUBLISH_TAG_NOT_TESTED_IMAGE'):
            module.prepare(self.work, self.build)
        self.assertEqual(self.exports(), [])
        self.assertEqual(self.reads, [])

    def test_03_tag_changed_during_export_still_fails_actual_config_binding(self):
        self.export_bytes = image_bytes('changed-after-tag-inspection')
        with self.assertRaisesRegex(RuntimeError, 'PUBLISH_MANIFEST_CONFIG_NOT_TESTED_IMAGE'):
            module.prepare(self.work, self.build)
        self.assertEqual(len(self.exports()), 1)
        self.assertFalse((self.work / 'evidence/REGISTRY_READY.json').exists())
        self.assertEqual(self.pushes(), [])

    def test_04_registry_ready_cannot_substitute_another_build_image(self):
        module.prepare(self.work, self.build)
        ready = module.load(self.work / 'evidence/REGISTRY_READY.json')
        ready['candidateImageID'] = 'sha256:' + 'f' * 64
        module.write(self.work / 'evidence/REGISTRY_READY.json', ready)
        self.calls.clear()
        self.reads.clear()
        with self.assertRaisesRegex(RuntimeError, 'PUBLISH_READY_BUILD_CONNECTION_CHANGED'):
            module.publish(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])
        self.assertFalse((self.work / 'evidence/PUBLISH_INTENT.json').exists())
        self.assertFalse((self.work / 'evidence/PUBLISH_RECEIPT.json').exists())

    def test_05_build_failure_stops_prepare_before_any_export_effect(self):
        module.write(self.build / 'evidence/FAILURE.json', {'status': 'BLOCKED'})
        with self.assertRaisesRegex(RuntimeError, 'BUILD_OR_VERIFICATION_FAILED'):
            module.prepare(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])

    def test_06_build_failure_after_prepare_stops_publication_connection(self):
        module.prepare(self.work, self.build)
        module.write(self.build / 'evidence/FAILURE.json', {'status': 'BLOCKED'})
        self.calls.clear()
        self.reads.clear()
        with self.assertRaisesRegex(RuntimeError, 'BUILD_OR_VERIFICATION_FAILED'):
            module.publish(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])
        self.assertFalse((self.work / 'evidence/PUBLISH_INTENT.json').exists())

    def test_07_unbound_producer_receipt_blocks_before_local_image_export(self):
        self.receipts['CONNECTION_VERIFY']['runtimeManifestSHA256'] = 'f' * 64
        self.write_receipts()
        with self.assertRaisesRegex(RuntimeError, 'PUBLISH_NEW_PIN_BINDING_INVALID'):
            module.prepare(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])

    def test_08_namespace_owner_cannot_enter_candidate_only_publish_connection(self):
        self.policy['publisherIdentity'] = 'DiMoN3898-SYS'
        self.write_policy()
        with self.assertRaisesRegex(RuntimeError, 'CANDIDATE_ONLY_NON_OWNER_PUBLISHER_REQUIRED'):
            module.publish(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])
        self.assertFalse((self.work / 'evidence/PUBLISH_INTENT.json').exists())

    def test_09_invalid_publisher_identity_cannot_enter_publish_connection(self):
        self.policy['publisherIdentity'] = 'candidate/../writer'
        self.write_policy()
        with self.assertRaisesRegex(RuntimeError, 'CANDIDATE_ONLY_NON_OWNER_PUBLISHER_REQUIRED'):
            module.publish(self.work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])

    def test_10_draft_preflight_blocks_tools_before_reused_build_can_begin(self):
        self.policy['status'] = 'DRAFT_NOT_AUTHORIZED'
        self.policy['publicationApprovalRecorded'] = False
        self.write_policy()
        fresh_work = self.root / 'fresh-draft-preflight'
        os.environ.pop('SURFACE_CANDIDATE_GHCR_USER')
        os.environ.pop('SURFACE_CANDIDATE_GHCR_TOKEN')
        with patch.object(module, 'verify_tool', side_effect=AssertionError('TOOL_BEFORE_APPROVAL')):
            with self.assertRaisesRegex(RuntimeError, 'PUBLICATION_POLICY_NOT_AUTHORIZED'):
                module.preflight(fresh_work, self.build)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
