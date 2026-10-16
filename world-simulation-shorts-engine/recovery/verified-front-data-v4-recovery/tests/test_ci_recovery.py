"""New immutable packaging and truthful software-evidence boundaries only."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zlib

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('front_ci_under_test', HERE / 'ci_recovery.py')
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG = 'front-v4-4c4f39a-12345-1'


class FrontPackagingBoundaries(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='front-ci-tests-'); self.addCleanup(area.cleanup)
        self.root = Path(area.name)
        environment = {'RESULT_CI_STATE': str(self.root / 'state.json'), 'RUNNER_TEMP': str(self.root),
            'RUNNER_ENVIRONMENT': 'github-hosted', 'RESULT_REPOSITORY_PRIVATE': 'false',
            'RESULT_RUNNER_LABEL': 'ubuntu-24.04', 'RESULT_PHASE': 'build',
            'GITHUB_REPOSITORY': 'dimon3898-sys/yeonhwarok-free', 'GITHUB_REF': 'refs/heads/' + ci.BRANCH,
            'GITHUB_SHA': 'c' * 40, 'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1'}
        self.addCleanup(patch.stopall); patch.dict(os.environ, environment, clear=True).start()
        self.command = patch.object(ci.controls, 'run', Mock(side_effect=AssertionError('UNEXPECTED_EXTERNAL_COMMAND'))).start()
        self.helper = SimpleNamespace(require_space=Mock(return_value={'freeBytes': 22 * 1024**3}))
        patch.object(ci.controls, 'helpers', return_value=self.helper).start()

    def report(self):
        rows = [{'frame': frame, 'rawRgbaSha256': str(i + 1) * 64, 'pngSha256': 'a' * 64,
            'sourceActiveFrame': frame > 0, 'sourceGeoJsonSha256': 'b' * 64,
            'sourceMapDate': '1953-07-27', 'sourceCoordinateCount': 12,
            'geometryBounds': {'active': frame > 0, 'wholeEventGeometryInViewport': True, 'wholeEventGeometryInSafeArea': True}}
            for i, frame in enumerate((0, 1600, 2399))]
        report = {'schema': 'WORLD_ENGINE_ARCHIVAL_FRONT_V4_SOFTWARE_PROBE_V1', 'status': 'PASS',
            'testOnly': True, 'nvidiaHardwareVerified': False, 'full80SecondVideoRendered': False,
            'physicalNvidiaExecuted': False, 'gpuRenderingVerified': False, 'gpuVideoQualityApproved': False,
            'rows': rows, 'abComparison': {'status': 'PASS', 'sameCamera': True, 'sameFrame': True,
                'changedPixelCount': 100, 'protectedGraphicChangedPixelCount': 0, 'outsideSafeAreaChangedPixelCount': 0},
            'preservedFallback': {'status': 'PASS', 'frame': 0, 'bitExact': True, 'originalV3CompositorUsed': True,
                'rawRgbaSha256': rows[0]['rawRgbaSha256']},
            'nativeBoundaryProtection': {'status': 'PASS', 'actualReadPixelsCompared': True}}
        for key in ('actualDrawReadPixels', 'actualShaderCompile', 'softwareWebGLDrawExecuted',
            'sourceActiveFrame', 'actualHistoricalSourceSelected', 'originalSourcesUnchanged',
            'actualAstraUpload', 'sourceOrderVerified', 'fullPlan2400Frames', 'twelveChapterPlanSelected'):
            report[key] = True
        return report

    def test_only_public_standard_free_runner_and_exact_branch_are_allowed(self):
        for name, value in [('RUNNER_ENVIRONMENT', 'self-hosted'), ('RESULT_REPOSITORY_PRIVATE', 'true'),
                ('RESULT_RUNNER_LABEL', 'larger-runner'), ('GITHUB_REF', 'refs/heads/main')]:
            with self.subTest(name=name), patch.dict(os.environ, {name: value}), self.assertRaisesRegex(RuntimeError, 'FREE_PUBLIC_STANDARD'):
                ci.preflight()
        self.command.assert_not_called(); self.helper.require_space.assert_not_called()

    def test_no_old_namespace_can_be_changed_by_new_build(self):
        changed = ''
        def git(arguments, **_):
            return os.environ['GITHUB_SHA'] if arguments[1] == 'rev-parse' else changed if arguments[1] == 'diff' else ''
        self.command.side_effect = git
        for changed in [ci.files.PARENT_NAMESPACE + '/production_adapter.mjs',
                '.github/workflows/universal-production-v3.yml', 'world-simulation-shorts-engine/recovery/verified-front-data-v4/georeference.py']:
            with self.subTest(path=changed), self.assertRaisesRegex(RuntimeError, 'PROTECTED_EXISTING_SOURCE_CHANGED'):
                ci.preflight()
        changed = ci.NAMESPACE + '/front_adapter.mjs'; ci.preflight()
        self.assertEqual(ci.state()['tag'], TAG)
        self.assertEqual(ci.controls.PATCHES, {})

    def test_unique_tag_never_overwrites_parent_or_latest(self):
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG))
        for value in ['latest', 'production-v3-e09be5d-12345-1', 'front-v4-4c4f39a-0-1']:
            self.assertIsNone(ci.TAG_PATTERN.fullmatch(value))

    def test_parent_is_exact_272_file_inventory_with_110_bound_additions(self):
        parent, inherited = ci.files.parent_closure(ci.REPO)
        self.assertEqual(parent['sourceCommit'], ci.files.PARENT_SOURCE_COMMIT)
        self.assertEqual(len(inherited), 110)
        self.assertEqual(ci.files.PARENT_INVENTORY_FILES, 162 + len(inherited))
        self.assertEqual(inherited[ci.files.PARENT_NAMESPACE + '/PRODUCTION_FILES.json'], ci.files.PARENT_MANIFEST_SHA)

    def test_forged_parent_manifest_and_changed_parent_source_are_rejected(self):
        folder = self.root / ci.files.PARENT_NAMESPACE; folder.mkdir(parents=True)
        (folder / 'PRODUCTION_FILES.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'FROZEN_PARENT_MANIFEST_CHANGED'):
            ci.files.parent_closure(self.root)
        original = ci.files.read_source
        def altered(root, name):
            return b'changed' if name.endswith('/production_adapter.mjs') else original(root, name)
        with patch.object(ci.files, 'read_source', side_effect=altered):
            with self.assertRaisesRegex(RuntimeError, 'FROZEN_PARENT_SOURCE_CHANGED'):
                ci.files.parent_closure(ci.REPO)

    def test_no_symlink_traversal_or_path_normalization(self):
        (self.root / 'plain').write_bytes(b'original\x00\xff\r\n')
        (self.root / 'linked').symlink_to(self.root / 'plain')
        self.assertEqual(ci.files.read_source(self.root, 'plain'), b'original\x00\xff\r\n')
        for path in ('../plain', '/plain', './plain', 'a//plain', 'a\\plain', 'linked'):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                ci.files.read_source(self.root, path)

    def write_inventory(self, **changes):
        for name in ('source_manifest_recovery.py', 'software_probe_front.mjs'):
            (self.root / name).write_text('fixture only')
        raw = b'{"type":"LineString","coordinates":[[12,34],[13,35]]}\n'
        (self.root / 'source.geojson').write_bytes(raw)
        profile = {'schema': 'WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4', 'runtimeProfile': ci.files.PROFILE_ID,
            'fronts': [{'sourceFile': 'source.geojson', 'geoJsonSha256': hashlib.sha256(raw).hexdigest()}]}
        (self.root / 'FRONT_PROFILE.json').write_text(json.dumps(profile))
        inventory = {'schema': 'WORLD_ENGINE_FRONT_RUNTIME_INVENTORY_V4',
            'files': ['FRONT_PROFILE.json', 'RUNTIME_INVENTORY.json', 'source.geojson', 'source_manifest_recovery.py'],
            'testFiles': ['software_probe_front.mjs']}
        inventory.update(changes)
        (self.root / 'RUNTIME_INVENTORY.json').write_text(json.dumps(inventory))
        return inventory

    def test_explicit_inventory_excludes_self_manifest_and_duplicate_groups(self):
        original = self.write_inventory()
        self.assertEqual(ci.files.inventory(self.root), original)
        for patch_fields in ({'files': original['files'] + ['FRONT_FILES.json']},
                {'files': list(reversed(original['files']))}, {'testFiles': ['source_manifest_recovery.py']},
                {'testFiles': []}):
            self.write_inventory(**patch_fields)
            with self.subTest(fields=patch_fields), self.assertRaises(RuntimeError):
                ci.files.inventory(self.root)

    def test_profile_source_present_on_disk_but_omitted_from_package_is_rejected(self):
        inventory = self.write_inventory()
        inventory['files'].remove('source.geojson')
        (self.root / 'RUNTIME_INVENTORY.json').write_text(json.dumps(inventory))
        self.assertTrue((self.root / 'source.geojson').is_file())
        with self.assertRaisesRegex(RuntimeError, 'FRONT_PROFILE_SOURCE_NOT_IN_RUNTIME_INVENTORY'):
            ci.files.inventory(self.root)

    def test_profile_source_hash_must_match_the_actual_packaged_geojson(self):
        self.write_inventory()
        (self.root / 'source.geojson').write_text('{"type":"LineString","coordinates":[[0,0],[1,1]]}')
        with self.assertRaisesRegex(RuntimeError, 'FRONT_PROFILE_SOURCE_SHA_MISMATCH'):
            ci.files.inventory(self.root)

    def test_all_actual_profile_sources_are_in_generated_image_manifest(self):
        profile = json.loads((HERE / 'FRONT_PROFILE.json').read_text())
        manifest = ci.generate_manifest()
        self.assertGreaterEqual(len(profile['fronts']), 1)
        for source in profile['fronts']:
            with self.subTest(source=source['sourceFile']):
                self.assertIn(source['sourceFile'], manifest['files'])
                self.assertEqual(manifest['files'][source['sourceFile']], source['geoJsonSha256'])

    def test_staging_requires_focused_tests_and_actual_connected_software_proof(self):
        ci.save({**ci.state(), 'tag': TAG, 'focusedTests': {'status': 'PASS'}, 'softwareProbeBeforeBuild': {'exitCode': 0},
            'sourceReproduction': {'report': {'status': 'PASS'}}})
        with self.assertRaisesRegex(RuntimeError, 'CONNECTED_SOURCE_PIXELS_REQUIRED'):
            ci.stage()
        self.assertFalse((self.root / ('front-v4-image-' + TAG)).exists())

    def test_software_report_requires_actual_source_geometry_and_pixels(self):
        report = self.report()
        self.assertEqual(ci.validate_software_report(report)['actualSourceActiveFrames'], 2)
        for changes in ({'actualDrawReadPixels': False}, {'sourceActiveFrame': False}, {'nvidiaHardwareVerified': True},
                {'full80SecondVideoRendered': True}, {'physicalNvidiaExecuted': True}, {'rows': []}):
            changed = deepcopy(report); changed.update(changes)
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                ci.validate_software_report(changed)

    def test_unused_geojson_cannot_unlock_build(self):
        report = self.report()
        for row in report['rows']:
            row['sourceActiveFrame'] = False
        with self.assertRaisesRegex(RuntimeError, 'DATA_MUST_BE_SELECTED_BY_RENDERER'):
            ci.validate_software_report(report)

    def test_source_dates_hashes_and_unique_frames_are_required(self):
        for field, value in [('sourceGeoJsonSha256', ''), ('sourceMapDate', 'event date only'),
                ('sourceCoordinateCount', 1), ('rawRgbaSha256', 'not a hash')]:
            report = self.report(); report['rows'][1][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                ci.validate_software_report(report)
        report = self.report(); report['rows'][1]['frame'] = 0
        with self.assertRaisesRegex(RuntimeError, 'UNIQUE_GLOBAL_FRAMES'):
            ci.validate_software_report(report)

    def test_actual_ab_must_differ_without_changing_protected_graphics(self):
        for field, value in [('changedPixelCount', 0), ('sameCamera', False), ('sameFrame', False),
                ('protectedGraphicChangedPixelCount', 1), ('outsideSafeAreaChangedPixelCount', 1)]:
            report = self.report(); report['abComparison'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'ACTUAL_AB_AND_PROTECTED'):
                ci.validate_software_report(report)

    def test_actual_source_crop_and_changed_legacy_fallback_are_rejected(self):
        report = self.report(); report['rows'][1]['geometryBounds']['wholeEventGeometryInSafeArea'] = False
        with self.assertRaisesRegex(RuntimeError, 'MUST_FIT_VIEWPORT_AND_SAFE_AREA'):
            ci.validate_software_report(report)
        report = self.report(); report['preservedFallback']['rawRgbaSha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'PARENT_FALLBACK_PIXEL_EQUALITY'):
            ci.validate_software_report(report)

    def test_segmented_cut_claim_must_match_actual_rendered_pixel_hashes(self):
        report = self.report(); report['actualBoundaryPair'] = 1600
        row = deepcopy(report['rows'][1]); row.update(frame=1599, rawRgbaSha256='4' * 64); report['rows'].append(row)
        report['continuity'] = [{'frame': frame, 'bitExact': True,
            'segmentedRawRgbaSha256': digest, 'fullTimelineRawRgbaSha256': digest}
            for frame, digest in ((1599, '4' * 64), (1600, '2' * 64))]
        ci.validate_software_report(report)
        report['continuity'][1]['fullTimelineRawRgbaSha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'SEGMENTED_PIXEL_EQUALITY'):
            ci.validate_software_report(report)

    def bound_source_fixture(self):
        geometry = {'type': 'LineString', 'coordinates': [[12, 34], [13, 35]]}
        source = {'type': 'Feature', 'properties': {'mapDate': '1953-07-27'}, 'geometry': geometry}
        raw = (json.dumps(source) + '\n').encode(); (self.root / 'actual.geojson').write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        profile = {'schema': 'WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4', 'runtimeProfile': ci.files.PROFILE_ID,
            'fronts': [{'frontId': 'ACTUAL_MAP', 'sourceFile': 'actual.geojson', 'geoJsonSha256': digest,
                'mapDate': '1953-07-27', 'geometry': geometry}],
            'schedule': [{'startFrame': 1600, 'endFrame': 2400, 'frontId': 'ACTUAL_MAP'}]}
        profile_raw = json.dumps(profile).encode(); (self.root / 'FRONT_PROFILE.json').write_bytes(profile_raw)
        report = self.report(); report['frontProfileSha256'] = hashlib.sha256(profile_raw).hexdigest()
        for row in report['rows'][1:]:
            row.update(frontId='ACTUAL_MAP', sourceFile='actual.geojson', sourceGeoJsonSha256=digest)
        return report, profile

    def test_source_witness_recomputes_original_geojson_bytes_and_profile(self):
        report, _ = self.bound_source_fixture()
        self.assertEqual(len(ci.validate_source_bindings(report, self.root)['rows']), 2)
        (self.root / 'actual.geojson').write_text('{"type":"LineString","coordinates":[[0,0],[1,1]]}')
        with self.assertRaisesRegex(RuntimeError, 'ORIGINAL_GEOJSON_FILE_SHA'):
            ci.validate_source_bindings(report, self.root)

    def test_profile_cannot_replace_source_coordinates_or_frame_schedule(self):
        for change in ('geometry', 'schedule'):
            report, profile = self.bound_source_fixture()
            if change == 'geometry':
                profile['fronts'][0]['geometry']['coordinates'][0] = [0, 0]
            else:
                profile['schedule'][0]['startFrame'] = 1601
            raw = json.dumps(profile).encode(); (self.root / 'FRONT_PROFILE.json').write_bytes(raw)
            report['frontProfileSha256'] = hashlib.sha256(raw).hexdigest()
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                ci.validate_source_bindings(report, self.root)

    def png_fixture(self, name):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1080, 1920, 8, 6, 0, 0, 0))
        raw += chunk(b'IDAT', zlib.compress((b'\0' + b'\0' * (1080 * 4)) * 1920)) + chunk(b'IEND', b'')
        (self.root / name).write_bytes(raw)
        return {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_png_evidence_hashes_and_exact_set_are_checked(self):
        records = [self.png_fixture(name) for name in ('FRAME_000000.png', 'FRAME_001600.png', 'FRAME_002399.png')]
        sums = ''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in records)
        (self.root / 'SHA256SUMS').write_text(sums)
        self.assertEqual(ci.collect_png_evidence(self.root, {'files': records}), records)
        (self.root / records[0]['file']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(RuntimeError, 'PNG_SHA_OR_DIMENSION'):
            ci.collect_png_evidence(self.root, {'files': records})

    def test_temporal_png_claim_is_bound_to_actual_saved_file(self):
        records = [self.png_fixture(name) for name in ('FRAME_000000.png', 'FRAME_001600.png', 'FRAME_002399.png')]
        (self.root / 'SHA256SUMS').write_text(''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in records))
        report = {'files': records, 'rows': [{'frame': 1600, 'pngSha256': records[1]['sha256']}]}
        ci.collect_png_evidence(self.root, report)
        report['rows'][0]['pngSha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'TEMPORAL_PNG_BYTES_NOT_BOUND'):
            ci.collect_png_evidence(self.root, report)

    def test_dockerfile_only_adds_namespace_and_keeps_original_entrypoint(self):
        text = (HERE / 'Dockerfile').read_text()
        self.assertIn('FROM ' + ci.BASE, text)
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith('#')]
        self.assertEqual(sum(line.startswith('COPY ') for line in lines), 1)
        self.assertFalse(any(line.startswith(('ENTRYPOINT ', 'CMD ', 'HEALTHCHECK ')) for line in lines))
        self.assertNotIn('apt-get', text)
        self.assertNotIn('pip install', text)

    def test_workflow_does_not_trigger_itself_for_result_commits(self):
        text = (ci.REPO / ci.WORKFLOW).read_text()
        trigger = text.split('  workflow_dispatch:', 1)[0]
        self.assertNotIn('/runs/', trigger)
        self.assertIn('runs-on: ubuntu-24.04', text)
        self.assertNotIn('self-hosted', text)
        self.assertIn("github.event.repository.private == false", text)
        self.assertIn('verify-pull:', text)
        self.assertNotIn('gcube deploy', text.lower())


if __name__ == '__main__':
    unittest.main()
