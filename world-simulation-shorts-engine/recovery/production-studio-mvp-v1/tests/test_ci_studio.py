import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_test_ci_studio', HERE / 'ci_studio.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class CISafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.dict(os.environ, {'RUNNER_TEMP': self.temp.name, 'GITHUB_RUN_ID': '12345',
            'GITHUB_RUN_ATTEMPT': '1', 'RESULT_PHASE': 'build', 'GITHUB_SHA': 'a' * 40,
            'RESULT_CI_STATE': str(Path(self.temp.name) / 'state.json')})
        self.patch.start()
    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()
    def test_parent_image_and_manifest_are_frozen(self):
        self.assertEqual(m.parent.generate_manifest(), m.frozen)
        self.assertEqual(m.parent.generate_manifest()['sourceCommit'], m.files.PARENT_SOURCE_COMMIT)
        self.assertNotEqual(m.parent.generate_manifest()['sourceCommit'], os.environ['GITHUB_SHA'])
        self.assertEqual(m.sha(m.frozen_path), m.files.PARENT_MANIFEST_SHA)
    def test_parent_inventory_remains373_not_masked_studio_files(self):
        with mock.patch.object(m.parent, 'composed_image_check', return_value={'source': {'composedInventoryFiles': 374}}):
            with self.assertRaisesRegex(RuntimeError, 'EXACT_PARENT373'):
                m.parent_image_check('test')
    def test_fixed_unique_tag_family(self):
        self.assertTrue(m.TAG_PATTERN.fullmatch('studio-v1-344dc2d-12345-1'))
        for tag in ['latest', 'front-v4-4c4f39a-12345-1', 'studio-v1-344dc2d-0-1', 'studio-v1-344dc2d-12345-1\n']:
            self.assertIsNone(m.TAG_PATTERN.fullmatch(tag))
    def test_new_image_payload_is_outside_frozen_repository(self):
        self.assertFalse(Path(m.DEST).is_relative_to('/opt/rtx-package/repo'))
        dockerfile = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + m.BASE, dockerfile)
        self.assertNotIn('COPY . ', dockerfile)
        self.assertIn('COPY studio/ /opt/world-engine-production-studio/', dockerfile)
        self.assertNotIn('apt-get', dockerfile)
        self.assertNotIn('pip install', dockerfile)
    def test_original_healthcheck_is_inherited(self):
        dockerfile = (HERE / 'Dockerfile').read_text()
        self.assertFalse(any(line.startswith('HEALTHCHECK ') for line in dockerfile.splitlines()))
        self.assertIn('EXPOSE 8080', dockerfile)
    def test_no_privileged_gpu_docker_flags(self):
        command = m.container()
        for flag in ['--privileged', '--gpus', '--device', '--network=host']:
            self.assertNotIn(flag, command)
        self.assertIn('--network=none', command)
        self.assertIn('--restart=no', command)
    def test_container_uid_drops_groups(self):
        code = m.uid_code('pass')
        self.assertIn('os.setgroups([])', code)
        self.assertIn('os.setgid(1000)', code)
        self.assertIn('os.setuid(1000)', code)
    def test_stage_cannot_bypass_tests(self):
        with self.assertRaisesRegex(RuntimeError, 'FOCUSED_AND_MOBILE'):
            m.stage()
    def test_build_cannot_bypass_tests(self):
        with mock.patch.object(m.native, 'require_space', return_value={'freeBytes': 30 * 1024**3}):
            with self.assertRaisesRegex(RuntimeError, 'TESTS_REQUIRED'):
                m.build()
    def test_publication_requires_verification_and_zero_secrets(self):
        with self.assertRaisesRegex(RuntimeError, 'VERIFICATION_AND_ZERO_SECRETS'):
            m.publish()
    def test_free_runner_gate_reused(self):
        with mock.patch.dict(os.environ, {'RUNNER_ENVIRONMENT': 'self-hosted'}):
            with self.assertRaisesRegex(RuntimeError, 'FREE_PUBLIC_STANDARD_RUNNER'):
                m.preflight()
    def test_failure_state_never_reports_hardware_pass(self):
        state = m.state()
        self.assertFalse(state['gpuExecuted'])
        self.assertFalse(state['nvidiaHardwareVerified'])
        self.assertFalse(state['paidWorkExecuted'])
        self.assertFalse(state['actual80SecondNvidiaVideoGenerated'])
        self.assertFalse(state['externalDropboxDeliveryVerified'])
    def test_workflow_is_public_standard_runner_only(self):
        workflow = (m.REPO / m.WORKFLOW).read_text()
        self.assertIn("github.event.repository.private == false", workflow)
        self.assertEqual(workflow.count('runs-on: ubuntu-24.04'), 2)
        self.assertNotIn('self-hosted', workflow)
        self.assertNotIn('cancel-in-progress: true', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
    def test_guard_checks_before_both_build_and_publish(self):
        with mock.patch.object(m.controls, 'guard') as guard:
            m.guard(); guard.assert_called_once()
        with mock.patch.object(m.controls, 'publish') as publish:
            m.publish(); publish.assert_called_once()
    def test_independent_pull_requests_only_read_token_scope(self):
        registry = m.configure_registry(); observed = []
        def transport(url, headers, bound):
            observed.append(url)
            return registry.Response(200, {}, b'{"token":"cpu-test-issued-value"}')
        guard = m.read_only_registry()(transport=transport, environ={'GITHUB_ACTOR': 'test-user', 'GH_TOKEN': 'cpu-test-auth'})
        token, access = guard._authenticate()
        self.assertEqual(token, 'cpu-test-issued-value')
        from urllib.parse import urlsplit, parse_qs
        self.assertEqual(parse_qs(urlsplit(observed[0]).query)['scope'], ['repository:' + registry.REPOSITORY + ':pull'])
        self.assertFalse(access['push']); self.assertFalse(access['pushVerified'])
        with self.assertRaisesRegex(registry.GuardError, 'READ_ONLY_REGISTRY'):
            guard.check_tag('studio-v1-344dc2d-12345-1')
    def test_pull_workflow_uses_read_only_packages(self):
        workflow = (m.REPO / m.WORKFLOW).read_text(); build, pull = workflow.split('  verify-pull:', 1)
        self.assertIn('packages: write', build); self.assertIn('packages: read', pull)
        self.assertNotIn('packages: write', pull)
    def test_software_probe_uses_real_parent_path_not_alias(self):
        import inspect
        self.assertEqual(m.PARENT_PROBE, '/opt/rtx-package/repo/' + m.files.PARENT_NAMESPACE + '/software_probe_front.mjs')
        implementation = inspect.getsource(m.software_probe)
        self.assertIn('repr(PARENT_PROBE)', implementation)
        self.assertNotIn('/opt/world-engine-front-v4/software_probe_front.mjs', implementation)
        parent_source = (m.HERE.parent / 'verified-front-data-v4-recovery/software_probe_front.mjs').read_text()
        self.assertIn('path.resolve(process.argv[1])===fileURLToPath(import.meta.url)', parent_source)
    def reuse_state(self):
        return {'image': 'test-image', 'originalSources': {'status': 'PASS', 'source': {
            'composedInventoryFiles': 373, 'unexpectedFiles': 0}}, 'imageHashes': {'status': 'PASS',
            'sourceCommit': os.environ['GITHUB_SHA'], 'parent': {'manifestSha256': m.files.PARENT_MANIFEST_SHA}}}
    def test_pinned_software_reuse_rechecks_real_pngs_without_claiming_new_draw(self):
        m.save(self.reuse_state())
        self.assertTrue(m.reuse_inherited_software_evidence('test-image'))
        value = m.state(); reused = value['inheritedSoftwareEvidenceReuse']
        self.assertFalse(reused['executedInThisRun']); self.assertFalse(reused['gpuExecuted'])
        self.assertEqual(len(reused['actualPngHashesRechecked']), 14)
        self.assertEqual(reused['audit']['actualTemporalFrames'], 12)
        self.assertNotIn('inheritedActualSoftwareDraw', value)
        self.assertNotIn('evidenceFolder', reused)
    def test_reuse_requires_fresh_current_image373_verification(self):
        with self.assertRaisesRegex(RuntimeError, 'FRESH_IMAGE_AND_FROZEN_PARENT'):
            m.reuse_inherited_software_evidence('test-image')
    def test_reuse_rejects_changed_pinned_report_bytes(self):
        m.save(self.reuse_state()); original = m.files.read_source
        def read(root, name):
            raw = original(root, name)
            return raw + b' ' if name == 'build.json' else raw
        with mock.patch.object(m.files, 'read_source', side_effect=read):
            with self.assertRaisesRegex(RuntimeError, 'PINNED_SOFTWARE_REPORT_SHA_MISMATCH'):
                m.reuse_inherited_software_evidence('test-image')
    def test_image_wrong_entrypoint_or_credential_rejected(self):
        config = {'Os': 'linux', 'Architecture': 'amd64', 'Config': {'Labels': {
            'world-engine.studio.parent-digest': m.PARENT_DIGEST,
            'world-engine.studio.source-revision': os.environ['GITHUB_SHA'],
            'world-engine.front-v4.source-revision': m.files.PARENT_SOURCE_COMMIT},
            'Entrypoint': ['/bin/sh'], 'Env': []}}
        with mock.patch.object(m, 'run', return_value=json.dumps([config])):
            with self.assertRaisesRegex(RuntimeError, 'FIXED_BOOTSTRAP'):
                m.inspect_image('test')
        config['Config']['Entrypoint'] = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-B', m.DEST + '/bootstrap.py']
        config['Config']['Env'] = ['WORLD_ENGINE_STUDIO_OWNER_CODE=' + 'test-placeholder']
        with mock.patch.object(m, 'run', return_value=json.dumps([config])):
            with self.assertRaisesRegex(RuntimeError, 'CREDENTIAL_ENV_IN_IMAGE'):
                m.inspect_image('test')


if __name__ == '__main__':
    unittest.main()
