"""New packaging boundary only; no Docker/provider/GPU is invoked by these mocks."""
from copy import deepcopy
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import struct
from types import ModuleType, SimpleNamespace
import unittest
import zlib
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('production_ci_under_test', HERE / 'ci.py')
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = 'production-v3-e09be5d-12345-1'
CONFIG = 'sha256:' + 'b' * 64
DIGEST = 'sha256:' + 'a' * 64


class ProductionCISafety(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='production-ci-tests-'); self.addCleanup(area.cleanup)
        self.root = Path(area.name)
        environment = {'RESULT_CI_STATE': str(self.root / 'state.json'), 'RUNNER_TEMP': str(self.root),
            'RUNNER_ENVIRONMENT': 'github-hosted', 'RESULT_REPOSITORY_PRIVATE': 'false',
            'RESULT_RUNNER_LABEL': 'ubuntu-24.04', 'RESULT_PHASE': 'build',
            'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free', 'GITHUB_REF': 'refs/heads/' + ci.BRANCH,
            'GITHUB_SHA': 'c' * 40, 'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1',
            'GITHUB_OUTPUT': str(self.root / 'outputs'), 'RESULT_PUBLISHED_TAG': TAG, 'RESULT_PUBLISHED_DIGEST': DIGEST}
        self.addCleanup(patch.stopall); patch.dict(os.environ, environment, clear=True).start()
        self.command = Mock(side_effect=AssertionError('UNEXPECTED_EXTERNAL_COMMAND'))
        patch.object(ci, 'run', self.command).start(); patch.object(ci.controls, 'run', self.command).start()
        self.process = patch.object(ci.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')).start()
        self.helper = SimpleNamespace(require_space=Mock(return_value={'freeBytes': 22 * 1024**3}), login=Mock())
        patch.object(ci, 'helpers', return_value=self.helper).start(); patch.object(ci.controls, 'helpers', return_value=self.helper).start()
        self.registry = Mock(); module = ModuleType('registry_guard')
        module.RegistryGuard = lambda: self.registry; module.validate_digest = lambda value: value; module.validate_tag = lambda value: value
        patch.dict(sys.modules, {'registry_guard': module}).start()

    def seed(self, **changes):
        value = ci.state(); value.update(tag=TAG, image=ci.IMAGE + ':' + TAG, configDigest=CONFIG,
            focusedTests={'status': 'PASS'}, softwareProbeBeforeBuild={'exitCode': 0}, verification='PASS',
            secretScan={'status': 'PASS', 'findings': 0}); value.update(changes); ci.save(value); return value

    def facts(self):
        return {'Id': CONFIG, 'Size': 1, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {
            'Entrypoint': ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py'],
            'Env': ['PATH=/usr/bin'], 'Labels': {
                'org.opencontainers.image.revision': '2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
                'world-engine.universal-v2.source-revision': ci.files.PARENT_SOURCE_COMMIT,
                'world-engine.production-v3.source-revision': os.environ['GITHUB_SHA'],
                'world-engine.production-v3.parent-digest': ci.PARENT_DIGEST}}}

    def software_report(self):
        return {'schema': 'WORLD_ENGINE_PRODUCTION_V3_ACTUAL_SOFTWARE_PROBE_V1', 'status': 'PASS',
            'testOnly': True, 'nvidiaHardwareVerified': False, 'full80SecondVideoRendered': False,
            'physicalNvidiaExecuted': False, 'gpuRenderingVerified': False, 'sampleMp4Generated': False,
            'gpuVideoQualityApproved': False, 'actualShaderCompile': True, 'softwareWebGLDrawExecuted': True,
            'actualDrawReadPixels': True, 'all5TemporalFrames': True, 'boundaryContinuityBitExact': True,
            'actualHistoricalSceneSelected': True, 'originalSourcesUnchanged': True,
            'productionCpuPreparationSelected': True, 'rangeBoundaryContinuityVerified': True,
            'inputCacheReuseVerified': True, 'projectedEventGeometryMeasured': True,
            'wholeEventGeometryInViewport': True, 'wholeEventGeometryInSafeArea': True,
            'actualAstraUpload': True, 'sourceGradeSelected': True, 'sourceOrderVerified': True,
            'ABComparisonVerified': True, 'twelveChapterPlanSelected': True,
            'nativeBoundaryProtection': {'status': 'PASS', 'actualReadPixelsCompared': True}}

    def test_free_public_standard_runner_and_exact_branch_required(self):
        for name, value in [('RUNNER_ENVIRONMENT', 'self-hosted'), ('RESULT_REPOSITORY_PRIVATE', 'true'),
                ('RESULT_RUNNER_LABEL', 'larger-runner'), ('GITHUB_REF', 'refs/heads/main')]:
            with self.subTest(name=name), patch.dict(os.environ, {name: value}), self.assertRaises(RuntimeError):
                ci.preflight()
        self.command.assert_not_called(); self.helper.require_space.assert_not_called()

    def test_all_existing_files_and_parent_workflows_are_protected(self):
        def git(arguments, **_):
            return os.environ['GITHUB_SHA'] if arguments[1] == 'rev-parse' else changed if arguments[1] == 'diff' else ''
        self.command.side_effect = git
        for changed in [ci.files.PARENT_NAMESPACE + '/long_runtime.mjs', '.github/workflows/universal-auto-video-v2.yml',
                'world-simulation-shorts-engine/web/map_infographic_v1/area_core_v3.mjs']:
            with self.assertRaisesRegex(RuntimeError, 'PROTECTED_EXISTING_SOURCE_CHANGED'):
                ci.preflight()
        changed = ci.NAMESPACE + '/production_adapter.mjs'; ci.preflight()
        self.assertEqual(ci.state()['tag'], TAG); self.assertEqual(ci.controls.PATCHES, {})

    def test_unique_tag_cannot_be_latest_or_any_previous_namespace(self):
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG))
        for value in ['latest', 'production-v3-e09be5d-0-1', 'universal-v2-c1e9c09-12345-1']:
            self.assertIsNone(ci.TAG_PATTERN.fullmatch(value))

    def test_immutable_parent_manifest_and_all_86_additions_are_preserved(self):
        parent, closure = ci.files.parent_closure(ci.REPO)
        self.assertEqual(len(closure), 86); self.assertEqual(parent['sourceCommit'], ci.files.PARENT_SOURCE_COMMIT)
        self.assertEqual(ci.files.PARENT_INVENTORY_FILES, 248)
        self.assertEqual(closure[ci.files.PARENT_NAMESPACE + '/UNIVERSAL_FILES.json'], ci.files.PARENT_MANIFEST_SHA)

    def test_stage_requires_new_tests_and_real_connected_software_success(self):
        for changes in [{'focusedTests': {'status': 'FAIL'}}, {'softwareProbeBeforeBuild': {'exitCode': 1}}]:
            self.seed(**changes)
            with self.assertRaisesRegex(RuntimeError, 'FOCUSED_AND_CONNECTED'):
                ci.stage()
        self.process.assert_not_called()

    def test_build_context_cannot_contain_old_files_or_undeclared_media(self):
        self.seed()
        with patch.object(ci, 'runtime_files', return_value=('source_manifest.py', 'PARENT_CLOSURE.json')), patch.object(ci, 'TEST_FILES', ()):
            ci.stage(); folder = Path(ci.state()['context'])
            self.assertEqual({p.name for p in folder.iterdir()}, {'production', 'Dockerfile'})
            (folder / 'production/old-renderer.mjs').write_text('FORBIDDEN_ADDITION')
            with self.assertRaisesRegex(RuntimeError, 'EXPLICIT_NEW_NAMESPACE_CONTEXT'):
                ci.build()
        self.process.assert_not_called()

    def test_software_proof_never_accepts_cpu_as_nvidia_or_full_video(self):
        good = self.software_report()
        with patch.object(ci, 'validate_actual_production_boundary', return_value={'status': 'PASS'}) as boundary, \
                patch.object(ci, 'validate_ab_witness', return_value={'status': 'PASS'}):
            ci.validate_software_report(good); boundary.assert_called_once()
            for changes in [{'testOnly': False}, {'nvidiaHardwareVerified': True}, {'full80SecondVideoRendered': True},
                    {'actualDrawReadPixels': False}, {'productionCpuPreparationSelected': False},
                    {'actualHistoricalSceneSelected': False}, {'boundaryContinuityBitExact': False},
                    {'nativeBoundaryProtection': {'status': 'FAIL'}}]:
                with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'CONNECTED_SOFTWARE_PROOF'):
                    ci.validate_software_report({**good, **changes})

    def test_boundary_validator_still_rejects_same_scene_even_if_boolean_says_pass(self):
        good = self.software_report()
        with patch.object(ci, 'validate_actual_production_boundary', side_effect=RuntimeError('REAL_SOURCE_SCENE_CUT_REQUIRED')):
            with self.assertRaisesRegex(RuntimeError, 'REAL_SOURCE_SCENE_CUT_REQUIRED'):
                ci.validate_software_report(good)

    def test_software_run_cannot_request_host_network_or_hardware_gpu(self):
        self.seed(); self.process.return_value.stdout = json.dumps(self.software_report())
        with patch.object(ci, 'validate_software_report', return_value={'status': 'PASS'}), \
                patch.object(ci, 'collect_png_evidence', return_value=[]), patch.object(ci, 'validate_ab_witness', return_value={'status': 'PASS'}):
            ci.software_probe('TEST_ONLY_IMAGE', phase='mockSoftware')
        arguments = self.process.call_args.args[0]
        self.assertIn('--network=none', arguments); self.assertIn('--restart=no', arguments)
        self.assertNotIn('--gpus', arguments); self.assertEqual(ci.state()['mockSoftware']['gpuExecuted'], False)

    def test_parent_entrypoint_platform_and_both_revision_labels_stay_fixed(self):
        self.command.side_effect = None; self.command.return_value = json.dumps([self.facts()]); ci.inspect_image('TEST_ONLY_IMAGE')
        for name in self.facts()['Config']['Labels']:
            bad = self.facts(); bad['Config']['Labels'][name] = 'changed'; self.command.return_value = json.dumps([bad])
            with self.assertRaisesRegex(RuntimeError, 'PROVENANCE'):
                ci.inspect_image('TEST_ONLY_IMAGE')
        bad = self.facts(); bad['Config']['Entrypoint'] = ['/bin/true']; self.command.return_value = json.dumps([bad])
        with self.assertRaisesRegex(RuntimeError, 'ENTRYPOINT_CHANGED'):
            ci.inspect_image('TEST_ONLY_IMAGE')

    def test_credentials_cannot_be_saved_as_image_environment(self):
        self.command.side_effect = None
        for name in ['GH_TOKEN', 'GITHUB_TOKEN', 'GCUBE_ACCESS_TOKEN', 'GCUBE_API_TOKEN', 'DOCKER_AUTH_CONFIG']:
            bad = self.facts(); bad['Config']['Env'].append(name + '=TEST_PLACEHOLDER'); self.command.return_value = json.dumps([bad])
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'CREDENTIAL_ENV'):
                ci.inspect_image('TEST_ONLY_IMAGE')

    def test_publish_requires_new_verification_and_zero_secrets(self):
        for changes in [{'verification': 'FAIL'}, {'secretScan': {'status': 'FAIL', 'findings': 1}}]:
            self.seed(**changes)
            with self.assertRaisesRegex(RuntimeError, 'VERIFICATION_AND_ZERO_SECRETS_REQUIRED'):
                ci.publish()
        self.helper.login.assert_not_called(); self.command.assert_not_called()

    def test_state_never_claims_actual_nvidia_video_delivery_or_quality(self):
        value = ci.state()
        for name in ['gpuExecuted', 'gCubeDeployed', 'paidWorkExecuted', 'videoQualityApproved',
                'actual80SecondNvidiaVideoGenerated', 'externalDropboxDeliveryVerified', 'rendererModified', 'finalModified']:
            self.assertIs(value[name], False)
        self.assertEqual(value['existingV2TestsReused'], 168)

    def test_dockerfile_is_additive_and_preserves_runtime_entrypoint(self):
        body = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + ci.BASE, body)
        self.assertEqual([line for line in body.splitlines() if line.startswith('COPY ')],
            ['COPY production/ ' + ci.DEST + '/'])
        self.assertNotIn('\nENTRYPOINT ', body); self.assertNotIn('\nCMD ', body)
        self.assertIn('test ! -e ' + ci.DEST, body)
        self.assertNotIn('apt-get', body); self.assertNotIn('pip install', body)

    def temporal_report(self):
        """Explicit synthetic source/pixels; the production V3 clock is independent."""
        document = {'totalFrames': 1200, 'scenes': [
            {'sceneId': 'scene-0', 'startFrame': 0, 'endFrame': 200},
            {'sceneId': 'scene-1', 'startFrame': 200, 'endFrame': 300},
            {'sceneId': 'scene-2', 'startFrame': 300, 'endFrame': 1200}],
            'productionV3': {'chapterCount': 12, 'eventChapters': [
                {'chapterId': 'chapter-' + str(index), 'startFrame': index * 100, 'endFrame': (index + 1) * 100} for index in range(12)],
                'geometrySchedule': [
                    {'scheduleId': 'clock-0', 'mode': 'HOLD_SUPPLIED_SNAPSHOT', 'startFrame': 0, 'endFrame': 250, 'sourceStartFrame': 100, 'sourceEndFrame': 100},
                    {'scheduleId': 'clock-1', 'mode': 'TRANSITION_SUPPLIED_SNAPSHOTS', 'startFrame': 250, 'endFrame': 350, 'sourceStartFrame': 100, 'sourceEndFrame': 800},
                    {'scheduleId': 'clock-2', 'mode': 'HOLD_SUPPLIED_SNAPSHOT', 'startFrame': 350, 'endFrame': 1200, 'sourceStartFrame': 800, 'sourceEndFrame': 800}]}}
        fixture = self.root / 'test-only-plan.json'; fixture.write_text(json.dumps(document))
        report = self.software_report(); frames = [0, 299, 300, 700, 1199]
        report.update(planSha256=hashlib.sha256(fixture.read_bytes()).hexdigest(), frames=frames, rows=[])
        for frame in frames:
            scene = ci._one_at(document['scenes'], frame, 'TEST_BAD_SCENE')
            chapter = ci._one_at(document['productionV3']['eventChapters'], frame, 'TEST_BAD_CHAPTER')
            clock = ci._one_at(document['productionV3']['geometrySchedule'], frame, 'TEST_BAD_CLOCK')
            report['rows'].append({'frame': frame, 'globalFrame': frame, 'sceneId': scene['sceneId'],
                'sceneRange': [scene['startFrame'], scene['endFrame']], 'sceneRangeSha256': hashlib.sha256(json.dumps(scene).encode()).hexdigest(),
                'chapterId': chapter['chapterId'], 'geometryScheduleId': clock['scheduleId'], 'sourceGeometryFrame': ci._geometry_frame(clock, frame),
                'rawRgbaSha256': hashlib.sha256(('TEST_ONLY_RAW_' + str(frame)).encode()).hexdigest()})
        report['actualBoundaryPair'] = {'cutFrame': 300, 'beforeFrame': 299, 'afterFrame': 300,
            'leftSceneId': 'scene-1', 'rightSceneId': 'scene-2', 'leftRange': [200, 300], 'rightRange': [300, 1200]}
        report['continuity'] = [{'globalFrame': row['frame'], 'sceneId': row['sceneId'], 'productionSceneRange': row['sceneRange'],
            'productionSceneRangeSha256': row['sceneRangeSha256'], 'bitExact': True, 'segmentedRawRgbaSha256': row['rawRgbaSha256'],
            'fullTimelineRawRgbaSha256': row['rawRgbaSha256']} for row in report['rows'][1:3]]
        row = report['rows'][3]
        report['abComparison'] = {'status': 'PASS', 'frame': 700, 'sceneId': row['sceneId'], 'sceneRangeSha256': row['sceneRangeSha256'],
            'comparisonScope': 'SAME_FRAME_CAMERA_GEOMETRY_DATE', 'sameFrame': True, 'sameGeometryClock': True, 'sameCamera': True, 'sameChapterDate': True,
            'changedPixelCount': 1, 'protectedGraphicChangedPixelCount': 0, 'outsideSafeAreaChangedPixelCount': 0,
            'before': {'cameraSha256': '1' * 64, 'geometrySha256': '2' * 64, 'dateSha256': '3' * 64,
                'rawRgbaSha256': '4' * 64, 'pngSha256': '5' * 64},
            'after': {'cameraSha256': '1' * 64, 'geometrySha256': '2' * 64, 'dateSha256': '3' * 64,
                'rawRgbaSha256': row['rawRgbaSha256'], 'pngSha256': '6' * 64}}
        return fixture, report

    def test_actual_v3_clock_cut_is_bound_without_using_unrelated_legacy_timing(self):
        fixture, report = self.temporal_report(); audit = ci.validate_actual_production_boundary(report, fixture)
        self.assertTrue(audit['actualCutPixelsBitExact']); self.assertNotEqual(*audit['sourceGeometryFrames'])
        self.assertFalse(audit['reportBooleanAloneAccepted'])

    def test_geometry_clock_or_actual_range_witness_tamper_is_rejected(self):
        fixture, good = self.temporal_report()
        changes = [lambda r: r['rows'][1].__setitem__('sourceGeometryFrame', 0),
            lambda r: r['rows'][2].__setitem__('geometryScheduleId', 'wrong-clock'),
            lambda r: r['rows'][3].__setitem__('chapterId', 'wrong-date'),
            lambda r: r['actualBoundaryPair'].__setitem__('rightSceneId', 'scene-1'),
            lambda r: r['continuity'][1].__setitem__('fullTimelineRawRgbaSha256', '0' * 64)]
        for change in changes:
            bad = deepcopy(good); change(bad)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                ci.validate_actual_production_boundary(bad, fixture)

    def test_unrelated_legacy_active_transition_does_not_certify_a_v3_hold_cut(self):
        fixture, report = self.temporal_report(); document = json.loads(fixture.read_text())
        document['productionV3']['geometrySchedule'][1]['mode'] = 'HOLD_SUPPLIED_SNAPSHOT'
        document['legacyScenePlan'] = {'time_steps': [{'start_frame': 0}, {'start_frame': 100, 'transition_frames': 1000}]}
        fixture.write_text(json.dumps(document)); report['planSha256'] = hashlib.sha256(fixture.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, 'ACTUAL_ACTIVE_GEOMETRY_CLOCK_CUT'):
            ci.validate_actual_production_boundary(report, fixture)

    def test_ab_actual_camera_geometry_date_hashes_must_match(self):
        _, good = self.temporal_report(); ci.validate_ab_witness(good)
        for name in ('cameraSha256', 'geometrySha256', 'dateSha256'):
            bad = deepcopy(good); bad['abComparison']['after'][name] = '0' * 64
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'CAMERA_GEOMETRY_DATE_CHANGED'):
                ci.validate_ab_witness(bad)

    def test_ab_no_actual_pixel_change_or_protected_graphic_change_is_rejected(self):
        _, good = self.temporal_report()
        for changes in [{'changedPixelCount': 0}, {'protectedGraphicChangedPixelCount': 1}, {'outsideSafeAreaChangedPixelCount': 1}]:
            bad = deepcopy(good); bad['abComparison'].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'ACTUAL_AB_COMPARISON_REQUIRED'):
                ci.validate_ab_witness(bad)

    def software_png_fixture(self):
        """Lossless synthetic uniform PNG bytes; not actual rendered evidence."""
        _, report = self.temporal_report(); output = self.root / 'software-test-fixture'; output.mkdir()
        def chunk(kind, value):
            return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)
        raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1080, 1920, 8, 6, 0, 0, 0))
        raw += chunk(b'IDAT', zlib.compress((b'\0' + b'\0\0\0\xff' * 1080) * 1920)) + chunk(b'IEND', b'')
        names = ['FRAME_' + str(frame).zfill(6) + '.png' for frame in report['frames']] + ['AB_AFTER.png', 'AB_BEFORE.png']
        records = []
        for name in names:
            (output / name).write_bytes(raw)
            records.append({'file': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                'width': 1080, 'height': 1920, 'scope': 'CPU_SW_NOT_NVIDIA'})
        report['files'] = records
        (output / 'SHA256SUMS').write_text(''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in records))
        for row in report['rows']:
            row['pngSha256'] = hashlib.sha256(raw).hexdigest()
        report['abComparison']['before']['pngSha256'] = report['abComparison']['after']['pngSha256'] = hashlib.sha256(raw).hexdigest()
        return output, report

    def test_actual_png_and_sha_bytes_are_bound_independently_of_insertion_order(self):
        output, report = self.software_png_fixture(); records = ci.collect_png_evidence(output, report)
        self.assertEqual(len(records), 7); self.assertEqual(records, sorted(records, key=lambda row: row['file']))
        report['files'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'ACTUAL_PNG_REPORT_SHA_MISMATCH'):
            ci.collect_png_evidence(output, report)

    def test_software_evidence_rejects_extra_files_or_duplicate_sum_entries(self):
        output, report = self.software_png_fixture(); extra = output / 'INTERNAL_SOURCE.py'; extra.write_text('NEVER_PUBLIC')
        with self.assertRaisesRegex(RuntimeError, 'EXACT_SOFTWARE_PNG_SET'):
            ci.collect_png_evidence(output, report)
        extra.unlink(); sums = output / 'SHA256SUMS'; sums.write_text(sums.read_text() + sums.read_text().splitlines()[0] + '\n')
        with self.assertRaisesRegex(RuntimeError, 'SHA256SUMS_MISMATCH'):
            ci.collect_png_evidence(output, report)


if __name__ == '__main__':
    unittest.main()
