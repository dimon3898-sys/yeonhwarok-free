"""Focused additive packaging/provenance tests; no Docker/GPU/network calls."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('_overnight_test_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load('ci_package')
manifest = load('package_manifest')


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='overnight-package-')
        self.root = Path(self.tmp.name) / 'runtime'
        self.root.mkdir()
        self.names = {'bootstrap.py', 'studio_entry.py', 'studio_controller.py', 'runtime_bridge.py', 'package_manifest.py',
                      'prepare_source_preview.py', 'capture_runtime.mjs'}
        for name in self.names:
            (self.root / name).write_text('CPU source fixture ' + name + '\n')
        self.value = {'schema': 'WORLD_ENGINE_OVERNIGHT_FILES_V1', 'baseOperatingImageDigest': package.ci.BASE_DIGEST,
                      'previousManifestSHA256': package.PARENT_MANIFEST_SHA,
                      'files': {name: package.ci.sha(self.root / name) for name in self.names}}
        self.write_manifest()
        (self.root / 'Dockerfile').write_text('FROM immutable-fixture\n')

    def tearDown(self):
        self.tmp.cleanup()

    def write_manifest(self):
        (self.root / package.MANIFEST_NAME).write_text(json.dumps(self.value))

    def context(self):
        with patch.object(package, 'location', return_value=Path(self.tmp.name)):
            return package.payload_context(root=self.root)

    def test_only_manifested_new_source_is_copied(self):
        (self.root / 'PRIVATE_UNLISTED.json').write_text('{"not":"copied"}')
        context = self.context()
        self.assertEqual({p.name for p in context.iterdir()}, {'overnight', 'Dockerfile'})
        self.assertEqual({p.name for p in (context / 'overnight').iterdir()}, self.names | {package.MANIFEST_NAME})

    def test_changed_source_is_rejected(self):
        (self.root / 'bootstrap.py').write_text('wrong source')
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_SHA_MISMATCH'):
            self.context()

    def test_source_symlink_is_rejected(self):
        path = self.root / 'bootstrap.py'
        path.unlink()
        path.symlink_to(self.root / 'studio_entry.py')
        with self.assertRaisesRegex(RuntimeError, 'REGULAR_SOURCE_REQUIRED'):
            self.context()

    def test_path_traversal_is_rejected(self):
        self.value['files']['../escape.py'] = 'a' * 64
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'PACKAGE_PATH_INVALID'):
            self.context()

    def test_parent_manifest_is_exactly_bound(self):
        self.value['previousManifestSHA256'] = '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'EXPLICIT_PARENT_BOUND_FILES_REQUIRED'):
            self.context()

    def test_parent_image_cannot_be_replaced(self):
        self.value['baseOperatingImageDigest'] = 'sha256:' + '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'EXPLICIT_PARENT_BOUND_FILES_REQUIRED'):
            self.context()

    def test_disconnected_runtime_is_rejected(self):
        del self.value['files']['studio_entry.py']
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'CONNECTED_STUDIO_RUNTIME_REQUIRED'):
            self.context()

    def test_free_public_runner_is_required(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}):
            with self.assertRaisesRegex(RuntimeError, 'FREE_PUBLIC_STANDARD_RUNNER_REQUIRED'):
                package.ci.require_free_runner()

    def test_unique_tags_exclude_old_or_mutable_tags(self):
        self.assertIsNotNone(package.ci.TAG.fullmatch('overnight-v3-0123456789-123456-1'))
        for tag in ['latest', 'completion-v2-0123456789-123456-1', 'overnight-v3-0123456789-0-1']:
            self.assertIsNone(package.ci.TAG.fullmatch(tag))

    def test_container_cannot_use_gpu_or_network(self):
        command = package.container('immutable-fixture')
        self.assertIn('--network=none', command)
        self.assertIn('--restart=no', command)
        self.assertNotIn('--gpus', command)
        self.assertNotIn('--privileged', command)
        self.assertNotIn('--device', command)

    def test_actual_configuration_is_additive_and_free(self):
        dockerfile = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + package.ci.BASE, dockerfile)
        self.assertIn('test ! -e ' + package.ci.DEST, dockerfile)
        self.assertIn('COPY overnight/ ' + package.ci.DEST, dockerfile)
        self.assertEqual(dockerfile.count('COPY '), 1)
        self.assertNotIn('apt-get', dockerfile)
        self.assertNotIn('pip install', dockerfile)
        workflow = (package.ci.REPO / package.ci.WORKFLOW).read_text()
        self.assertIn('branches: [development/universal-overnight-safe-20261019]', workflow)
        self.assertIn('runs-on: ubuntu-24.04', workflow)
        self.assertNotIn('branches: [main]', workflow)
        self.assertNotIn('self-hosted', workflow)
        self.assertNotIn('gcube workload', workflow)
        self.assertNotIn('universal-overnight-v3/runs/**', workflow)

    def test_failed_source_container_keeps_first_bounded_error(self):
        saved = []
        failed = SimpleNamespace(returncode=7, stdout='source probe failed', stderr='actual first error')
        with patch.object(package.ci, 'run', return_value=failed), patch.object(package.ci, 'state', return_value={}), \
                patch.object(package.ci, 'save', side_effect=saved.append):
            with self.assertRaisesRegex(RuntimeError, 'CONTAINER_SOURCE_VERIFICATION_FAILED'):
                package.image_hashes('immutable-fixture')
        self.assertEqual(saved[-1]['sourceContainerFailure']['exitCode'], 7)
        self.assertIn('actual first error', saved[-1]['sourceContainerFailure']['stderr'])
        self.assertFalse(saved[-1]['sourceContainerFailure']['gpuExecuted'])

    def test_only_actual_independent_pull_issues_image_proof(self):
        value = {'pullVerified': True, 'imageDigest': 'sha256:' + 'b' * 64,
                 'imageHashes': {'status': 'PASS'}, 'imageConfiguration': {'status': 'PASS'}}
        saved = []
        with patch.object(package.ci, 'pull'), patch.object(package.ci, 'state', return_value=value), \
                patch.object(package.ci, 'save', side_effect=saved.append), patch.object(package.ci, 'sha', return_value='c' * 64), \
                patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40}):
            package.pull()
        proof = saved[-1]['imageProof']
        self.assertEqual(proof['schema'], 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_V1')
        self.assertEqual(proof['baseDigest'], package.ci.BASE_DIGEST)
        self.assertTrue(proof['independentPullVerified'])
        manifest.validate_image_proof(proof, source_manifest_sha256='c' * 64, image_digest='sha256:' + 'b' * 64)

    def test_failed_pull_cannot_issue_proof(self):
        with patch.object(package.ci, 'pull'), patch.object(package.ci, 'state', return_value={'pullVerified': False}):
            with self.assertRaisesRegex(RuntimeError, 'INDEPENDENT_PULL_PROOF_REQUIRED'):
                package.pull()

    def test_actual_source_plan_probe_loads_original_plan_without_gl_opener(self):
        report = {'status': 'PASS', 'scope': 'ACTUAL_SOURCE_PLAN_LOAD_NO_GL', 'originalTotalFrames': 2400,
                  'range': {'startFrame': 1400, 'endFrame': 1550}, 'gpuExecuted': False,
                  'browserOpened': False, 'renderStarted': False}
        result = SimpleNamespace(stdout=json.dumps(report) + '\n')
        with patch.object(package.ci, 'record', return_value=result) as recorder:
            self.assertEqual(package.source_plan_probe('immutable-fixture'), report)
        command = recorder.call_args.args[1]
        code = command[-1]
        compile(code, '<actual_source_plan_probe>', 'exec')
        self.assertIn('loadLongRuntimePlan(options)', code)
        self.assertNotIn('openLongRuntime', code)
        self.assertNotIn('chromium.launch', code)
        self.assertIn('prepare_source_preview.py', code)
        self.assertIn('--network=none', command)

    def test_source_probe_cannot_accept_render_or_gpu_claim(self):
        report = {'status': 'PASS', 'scope': 'ACTUAL_SOURCE_PLAN_LOAD_NO_GL', 'originalTotalFrames': 2400,
                  'range': {'startFrame': 1400, 'endFrame': 1550}, 'gpuExecuted': True,
                  'browserOpened': False, 'renderStarted': False}
        with patch.object(package.ci, 'record', return_value=SimpleNamespace(stdout=json.dumps(report))):
            with self.assertRaisesRegex(RuntimeError, 'ACTUAL_SOURCE_PLAN_LOAD_REQUIRED'):
                package.source_plan_probe('immutable-fixture')


class ManifestProofTests(unittest.TestCase):
    def proof(self):
        return {'schema': 'WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_V1', 'imageDigest': 'sha256:' + 'b' * 64,
                'sourceManifestSHA256': 'c' * 64, 'sourceCommit': 'a' * 40,
                'independentPullVerified': True, 'sourceHashesVerified': True,
                'baseDigest': manifest.BASE_IMAGE, 'result': 'PASS'}

    def test_legacy_proof_or_gpu_claim_cannot_be_used(self):
        for key, value in [('schema', 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1'), ('independentPullVerified', False),
                           ('baseDigest', 'sha256:' + '0' * 64), ('result', 'GPU_PASS')]:
            proof = self.proof()
            proof[key] = value
            with self.assertRaisesRegex(RuntimeError, 'INDEPENDENT_IMAGE_PROOF_INVALID'):
                manifest.validate_image_proof(proof)

    def test_source_and_digest_binding_are_independent(self):
        with self.assertRaisesRegex(RuntimeError, 'IMAGE_SOURCE_BINDING_MISMATCH'):
            manifest.validate_image_proof(self.proof(), source_manifest_sha256='d' * 64)
        with self.assertRaisesRegex(RuntimeError, 'IMAGE_DIGEST_BINDING_MISMATCH'):
            manifest.validate_image_proof(self.proof(), image_digest='sha256:' + 'd' * 64)

    def test_parent_image_cannot_claim_to_include_new_source(self):
        proof = self.proof()
        proof['imageDigest'] = manifest.BASE_IMAGE
        with self.assertRaisesRegex(RuntimeError, 'INDEPENDENT_IMAGE_PROOF_INVALID'):
            manifest.validate_image_proof(proof)

    def test_private_receipt_retains_original_permissions_and_no_symlinks(self):
        with tempfile.TemporaryDirectory(prefix='overnight-proof-') as tmp:
            authority = Path(tmp) / 'production'
            authority.mkdir(mode=0o700)
            control_root = authority / 'universal-overnight-v3/universal-integration-v1'
            file = authority / 'overnight_image_proof.json'
            file.write_text(json.dumps(self.proof()))
            file.chmod(0o600)
            result = manifest.read_image_proof(control_root, source_manifest_sha256='c' * 64, image_digest='sha256:' + 'b' * 64)
            self.assertEqual(result, self.proof())
            file.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'FILE_NOT_PRIVATE'):
                manifest.read_image_proof(control_root, source_manifest_sha256='c' * 64, image_digest='sha256:' + 'b' * 64)

    def test_receipt_in_parent_control_scope_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'OPERATOR_SCOPE_REQUIRED'):
            manifest.read_image_proof(Path('/tmp/universal-integration-completion-v2/universal-integration-v1'),
                                      source_manifest_sha256='c' * 64, image_digest='sha256:' + 'b' * 64)

    def test_install_delegates_immutable_private_writer_without_replacing_secret_settings(self):
        calls = []
        owner = SimpleNamespace(_private_file=lambda *args: calls.append(args))
        self.assertFalse(manifest.install_image_proof(None, {}, 'c' * 64, owner))
        self.assertTrue(manifest.install_image_proof(json.dumps(self.proof()), {'root': '/private/state'}, 'c' * 64, owner))
        self.assertEqual(calls[0][0], Path('/private/state/production/overnight_image_proof.json'))
        self.assertEqual(calls[0][2:], (1000, 1000))
        self.assertEqual(json.loads(calls[0][1]), self.proof())


if __name__ == '__main__':
    unittest.main()
