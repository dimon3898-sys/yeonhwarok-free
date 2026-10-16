"""New free-build safety tests; registry/containers are explicitly mocked."""
from __future__ import annotations
import importlib.util
import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('universal_ci_tested', HERE / 'ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
TAG = 'universal-v2-c1e9c09-12345-1'
DIGEST = 'sha256:' + 'a' * 64
CONFIG = 'sha256:' + 'b' * 64


class UniversalCISafety(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='universal-ci-')
        self.addCleanup(area.cleanup)
        self.root = Path(area.name)
        self.env = {'RESULT_CI_STATE': str(self.root / 'state.json'), 'RUNNER_TEMP': str(self.root),
            'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free',
            'RESULT_REPOSITORY_PRIVATE': 'false', 'RESULT_RUNNER_LABEL': 'ubuntu-24.04',
            'RESULT_PHASE': 'build', 'GITHUB_REF': 'refs/heads/' + ci.BRANCH,
            'GITHUB_SHA': 'c' * 40, 'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1',
            'RESULT_PUBLISHED_TAG': TAG, 'RESULT_PUBLISHED_DIGEST': DIGEST,
            'GITHUB_OUTPUT': str(self.root / 'outputs')}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        self.command = Mock(side_effect=AssertionError('unexpected command'))
        patch.object(ci, 'run', self.command).start()
        patch.object(ci.controls, 'run', self.command).start()
        self.process = patch.object(ci.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')).start()
        self.helper = SimpleNamespace(require_space=Mock(return_value={'freeBytes': 22 * 1024**3}),
            check_image=Mock(return_value={'status': 'PASS'}), login=Mock())
        patch.object(ci, 'helpers', return_value=self.helper).start()
        patch.object(ci.controls, 'helpers', return_value=self.helper).start()
        self.registry = Mock()
        self.registry.check_tag.return_value = {'status': 'TAG_UNUSED'}
        self.registry.inspect_digest.return_value = {'digest': DIGEST, 'configDigest': CONFIG}
        module = ModuleType('registry_guard')
        module.RegistryGuard = lambda: self.registry
        module.validate_tag = lambda value: value
        module.validate_digest = lambda value: value
        patch.dict(sys.modules, {'registry_guard': module}).start()

    def seed(self, **changes):
        value = ci.state()
        value.update(tag=TAG, image=ci.IMAGE + ':' + TAG, configDigest=CONFIG,
            focusedTests={'status': 'PASS'}, softwareProbeBeforeBuild={'exitCode': 0},
            verification='PASS', secretScan={'status': 'PASS', 'findings': 0})
        value.update(changes)
        ci.save(value)
        return value

    def facts(self):
        return {'Id': CONFIG, 'Size': 1, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {
            'Entrypoint': ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py'],
            'Env': ['PATH=/usr/bin'], 'Labels': {
                'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
                'world-engine.reference-v2.source-revision': 'e9feafc785fbd138cbac3ca4db090380968dc37e',
                'world-engine.universal-v2.source-revision': self.env['GITHUB_SHA'],
                'world-engine.universal-v2.parent-digest': ci.PARENT_DIGEST}}}

    def software_report(self, before=None, after=None):
        """Explicit mock pixels with real immutable fixture range metadata."""
        raw = (HERE / 'fixtures/PLAN_80S.json').read_bytes()
        document = json.loads(raw)
        if before is None:
            timing = document['legacyScenePlan']['timing']
            after_reveal = timing['event_start_frame'] + timing['initial_reveal_frames']
            after = next(scene['startFrame'] for scene in document['scenes'][1:]
                if scene['startFrame'] > after_reveal and any(scene['startFrame'] > step['start_frame']
                    and scene['startFrame'] < step['start_frame'] + step['transition_frames'] - 1
                    for step in document['legacyScenePlan']['time_steps'][1:]))
            before = after - 1
        select = lambda frame: next(scene for scene in document['scenes'] if scene['startFrame'] <= frame < scene['endFrame'])
        frames = [0, before, after, document['totalFrames'] // 2, document['totalFrames'] - 1]
        rows = []
        for frame in frames:
            scene = select(frame)
            rows.append({'frame': frame, 'globalFrame': frame, 'sceneId': scene['sceneId'],
                'sceneRange': [scene['startFrame'], scene['endFrame']],
                'sceneRangeSha256': hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest(),
                'rawRgbaSha256': hashlib.sha256(('TEST_ONLY_FRAME_' + str(frame)).encode()).hexdigest()})
        left, right = select(before), select(after)
        continuity = [{'globalFrame': row['frame'], 'sceneId': row['sceneId'],
            'productionSceneRange': row['sceneRange'], 'productionSceneRangeSha256': row['sceneRangeSha256'],
            'segmentedRawRgbaSha256': row['rawRgbaSha256'], 'fullTimelineRawRgbaSha256': row['rawRgbaSha256'], 'bitExact': True}
            for row in rows if row['frame'] in (before, after)]
        return {'schema': 'WORLD_ENGINE_UNIVERSAL_ACTUAL_SOFTWARE_PROBE_V2', 'status': 'PASS',
            'testOnly': True, 'nvidiaHardwareVerified': False, 'full80SecondVideoRendered': False,
            'actualDrawReadPixels': True, 'all5TemporalFrames': True,
            'actualHistoricalSceneSelected': True, 'boundaryContinuityBitExact': True,
            'nativeBoundaryProtection': {'status': 'PASS', 'actualReadPixelsCompared': True},
            'productionCpuPreparationSelected': True, 'inputCacheReuseVerified': True,
            'originalSourcesUnchanged': True, 'planSha256': hashlib.sha256(raw).hexdigest(),
            'frames': frames, 'rows': rows, 'continuity': continuity,
            'actualBoundaryPair': {'cutFrame': after, 'beforeFrame': before, 'afterFrame': after,
                'leftSceneId': left['sceneId'], 'rightSceneId': right['sceneId'],
                'leftRange': [left['startFrame'], left['endFrame']], 'rightRange': [right['startFrame'], right['endFrame']]}}

    def test_free_public_standard_runner_and_exact_branch(self):
        for key, value in [('RUNNER_ENVIRONMENT', 'self-hosted'), ('RESULT_REPOSITORY_PRIVATE', 'true'),
                ('RESULT_RUNNER_LABEL', 'larger-runner'), ('GITHUB_REF', 'refs/heads/main')]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(RuntimeError):
                ci.preflight()
        self.command.assert_not_called()
        self.helper.require_space.assert_not_called()

    def test_preflight_protects_all_prior_sources_and_uses_unique_tag(self):
        def git(args, **kwargs):
            if args[1] == 'rev-parse':
                return self.env['GITHUB_SHA']
            return changed if args[1] == 'diff' else ''
        self.command.side_effect = git
        for changed in ['world-simulation-shorts-engine/web/map_infographic_v1/renderer.mjs', '.github/workflows/reference-visual-master-v2.yml']:
            with self.assertRaisesRegex(RuntimeError, 'PROTECTED_EXISTING_SOURCE_CHANGED'):
                ci.preflight()
        changed = ci.NAMESPACE + '/planner.py'
        ci.preflight()
        self.assertEqual(ci.state()['tag'], TAG)
        self.assertEqual(ci.controls.PATCHES, {})
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG))
        self.assertIsNone(ci.TAG_PATTERN.fullmatch('latest'))

    def test_reference_parent_manifest_and_57_files_are_frozen(self):
        parent, files = ci.files.frozen_parent_files(ci.REPO)
        self.assertEqual(parent['sourceCommit'], 'e9feafc785fbd138cbac3ca4db090380968dc37e')
        self.assertEqual(len(files), 57)
        self.assertEqual(files[ci.files.PARENT_NAMESPACE + '/REFERENCE_FILES.json'], ci.files.PARENT_MANIFEST_SHA)

    def test_parent_source_tamper_is_rejected(self):
        original = ci.files._bytes
        def changed(root, name):
            return b'changed' if name.endswith('/ref2_runtime.mjs') else original(root, name)
        with patch.object(ci.files, '_bytes', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'FROZEN_REFERENCE_SOURCE_CHANGED'):
                ci.files.frozen_parent_files(ci.REPO)

    def test_manifest_contains_declared_runtime_and_only_missing_old_supplements(self):
        manifest = ci.generate_manifest()
        self.assertEqual(set(manifest['files']), set(ci.runtime_files()))
        self.assertEqual(set(manifest['testFiles']), set(ci.TEST_FILES))
        self.assertEqual(len(manifest['repoDependencies']), 57)
        self.assertEqual(manifest['sourceCommit'], self.env['GITHUB_SHA'])
        self.assertEqual(manifest['parentReferenceManifestSha256'], ci.files.PARENT_MANIFEST_SHA)
        self.assertFalse(set(manifest['additionalRepoFiles']) & set(manifest['repoDependencies']))
        self.assertTrue(all(not name.lower().endswith(('.mp4', '.png', '.zip'))
            for name in (*manifest['files'], *manifest['testFiles'])))

    def test_build_context_rejects_undeclared_media_without_running_docker(self):
        self.seed()
        ci.stage()
        context = Path(ci.state()['context'])
        self.assertFalse(context.is_relative_to(ci.REPO))
        self.assertEqual(set(path.name for path in context.iterdir()), {'universal', 'supplemental', 'Dockerfile'})
        (context / 'universal/unknown-reference.mp4').write_bytes(b'synthetic forbidden media')
        with self.assertRaisesRegex(RuntimeError, 'EXPLICIT_UNIVERSAL_BUILD_CONTEXT_REQUIRED'):
            ci.build()
        self.process.assert_not_called()

    def test_actual_software_proof_is_mandatory_before_stage(self):
        for changes in [{'focusedTests': {'status': 'FAIL'}}, {'softwareProbeBeforeBuild': {'exitCode': 1}}]:
            self.seed(**changes)
            with self.assertRaisesRegex(RuntimeError, 'FOCUSED_AND_CONNECTED_SOFTWARE_PROOF_REQUIRED'):
                ci.stage()
        self.process.assert_not_called()

    def test_software_probe_requires_real_draw_selected_history_and_range_continuity(self):
        self.seed()
        good = self.software_report()
        for changes in [{'nvidiaHardwareVerified': True}, {'testOnly': False},
                {'actualHistoricalSceneSelected': False}, {'boundaryContinuityBitExact': False},
                {'actualDrawReadPixels': False}, {'nativeBoundaryProtection': {'status': 'FAIL'}},
                {'productionCpuPreparationSelected': False}, {'inputCacheReuseVerified': False}]:
            self.process.return_value = SimpleNamespace(returncode=0, stdout=json.dumps({**good, **changes}), stderr='')
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'ACTUAL_UNIVERSAL_SOFTWARE_RANGE_PROOF_REQUIRED'):
                ci.software_probe('synthetic-image', phase='synthetic')
        self.process.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(good), stderr='')
        ci.software_probe('synthetic-image', phase='synthetic')
        command = self.process.call_args.args[0]
        self.assertIn('--network=none', command)
        self.assertNotIn('--gpus', command)

    def test_adjacent_frames_in_one_scene_cannot_claim_an_actual_cut(self):
        self.seed()
        bad = self.software_report(before=299, after=300)
        self.assertTrue(bad['boundaryContinuityBitExact'])
        self.assertEqual(bad['actualBoundaryPair']['leftSceneId'], bad['actualBoundaryPair']['rightSceneId'])
        self.process.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(bad), stderr='')
        with self.assertRaisesRegex(RuntimeError, 'REAL_SOURCE_SCENE_CUT_REQUIRED'):
            ci.software_probe('synthetic-image', phase='synthetic')
        self.assertEqual(ci.state()['synthetic']['actualBoundaryAudit']['status'], 'FAIL')

    def test_actual_cut_is_independently_bound_to_real_fixture_ids_ranges_and_pixels(self):
        good = self.software_report()
        audit = ci.validate_actual_boundary_report(good)
        self.assertTrue(audit['differentActualProductionScenes'])
        self.assertFalse(audit['reportBooleanAloneAccepted'])
        self.assertNotEqual(audit['leftSceneId'], audit['rightSceneId'])
        mutations = [lambda row: row.__setitem__('planSha256', '0' * 64),
            lambda row: row['actualBoundaryPair'].__setitem__('rightSceneId', row['actualBoundaryPair']['leftSceneId']),
            lambda row: row['actualBoundaryPair'].__setitem__('rightRange', [0, 2400]),
            lambda row: row['rows'][1].__setitem__('globalFrame', 0),
            lambda row: row['continuity'][0].__setitem__('sceneId', row['actualBoundaryPair']['rightSceneId']),
            lambda row: row['continuity'][0].__setitem__('productionSceneRange', [0, 2400]),
            lambda row: row['continuity'][1].__setitem__('fullTimelineRawRgbaSha256', '0' * 64)]
        for change in mutations:
            bad = deepcopy(good)
            change(bad)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                ci.validate_actual_boundary_report(bad)

    def test_inherited_entrypoint_platform_and_parent_labels_cannot_change(self):
        self.command.side_effect = None
        self.command.return_value = json.dumps([self.facts()])
        ci.inspect_image('synthetic-image')
        for key in self.facts()['Config']['Labels']:
            bad = self.facts()
            bad['Config']['Labels'][key] = 'changed'
            self.command.return_value = json.dumps([bad])
            with self.assertRaisesRegex(RuntimeError, 'PROVENANCE'):
                ci.inspect_image('synthetic-image')
        bad = self.facts()
        bad['Config']['Entrypoint'] = ['/bin/true']
        self.command.return_value = json.dumps([bad])
        with self.assertRaisesRegex(RuntimeError, 'PARENT_ENTRYPOINT_CHANGED'):
            ci.inspect_image('synthetic-image')

    def test_credentials_in_image_are_rejected(self):
        self.command.side_effect = None
        bad = self.facts()
        bad['Config']['Env'].append('GCUBE_ACCESS_TOKEN=not-a-real-credential')
        self.command.return_value = json.dumps([bad])
        with self.assertRaisesRegex(RuntimeError, 'CREDENTIAL_ENV_IN_IMAGE'):
            ci.inspect_image('synthetic-image')

    def test_publish_requires_zero_secrets_and_successful_image_verification(self):
        for changes in [{'verification': 'FAIL'}, {'secretScan': {'status': 'PASS', 'findings': 1}}]:
            self.seed(**changes)
            with self.assertRaises(RuntimeError):
                ci.publish()
        self.helper.login.assert_not_called()
        self.registry.check_tag.assert_not_called()

    def test_publish_rechecks_unique_tag_without_mutating_old_auth(self):
        self.seed()
        own = self.root / 'new-auth'; own.mkdir(); (own / 'config.json').write_text('synthetic')
        old = self.root / 'old-auth'; old.mkdir(); (old / 'config.json').write_text('preserved')
        self.helper.login.return_value = (own, {})
        self.registry.check_tag.side_effect = [{'status': 'TAG_UNUSED'}, RuntimeError('TAG_ALREADY_EXISTS')]
        with self.assertRaisesRegex(RuntimeError, 'TAG_ALREADY_EXISTS'):
            ci.publish()
        self.assertFalse(own.exists())
        self.assertEqual((old / 'config.json').read_text(), 'preserved')

    def test_independent_pull_fails_when_any_bound_hash_changes(self):
        self.seed()
        auth = self.root / 'auth'; auth.mkdir(); (auth / 'config.json').write_text('synthetic')
        self.helper.login.return_value = (auth, {})
        self.command.side_effect = None
        with patch.object(ci.controls, 'inspect_image', return_value=self.facts()), patch.object(ci.controls, 'image_hashes', side_effect=RuntimeError('HASH_MISMATCH')):
            with self.assertRaisesRegex(RuntimeError, 'HASH_MISMATCH'):
                ci.pull()
        self.assertFalse(ci.state()['pullVerified'])

    def test_dockerfile_is_additive_and_keeps_production_service(self):
        source = (HERE / 'Dockerfile').read_text()
        code = '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith('#'))
        self.assertIn('FROM ' + ci.BASE, code)
        self.assertIn('--check-supplemental-absent', code)
        self.assertNotRegex(code, r'(?m)^(ENTRYPOINT|CMD|HEALTHCHECK|EXPOSE|ENV)\b')
        self.assertNotIn('apt-get', code)
        self.assertNotIn('--gpus', code)

    def test_workflow_is_bounded_public_free_and_has_independent_pull(self):
        source = (ci.REPO / ci.WORKFLOW).read_text()
        self.assertEqual(source.count('runs-on: ubuntu-24.04'), 2)
        self.assertIn('github.event.repository.private == false', source)
        self.assertIn('needs: build', source)
        self.assertIn('timeout-minutes: 60', source)
        self.assertIn('timeout-minutes: 20', source)
        self.assertNotIn('self-hosted', source)
        self.assertNotIn('gcube workload start', source)


if __name__ == '__main__':
    unittest.main()
