"""Focused tests for the immutable-image camera proof; no Docker or GPU work."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('camera_ci_under_test', HERE / 'camera_ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class CameraCiTests(unittest.TestCase):
    def pngs(self, root):
        data = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 1080, 1920) + b'\0' * 16
        for name in sorted(ci.PNG_NAMES):
            (root / name).write_bytes(data)
        return ci.collect_pngs(root)

    def report(self, records):
        value = {'schema': 'REFERENCE_CAMERA_HOLD_FOLLOWUP_SW_V1', 'status': 'PASS',
                 'immutableImage': ci.IMAGE, 'followupScriptSha256': ci.SCRIPT_SHA,
                 'selectedComparisonFrame': 100, 'actualCameraDeltaPixels': 3.5,
                 'sourceVerification': {'status': 'PASS', 'manifestSha256': ci.MANIFEST_SHA},
                 'files': [dict(row, scope='CPU_SW_NOT_NVIDIA') for row in records]}
        for key in ('testOnly', 'actualShaderCompile', 'actualWebGL2DrawExecuted', 'actualReadPixelsExecuted',
                    'softwareWebGLDrawExecuted', 'materialAndSourceAndEventAndWorldUnitsEqual',
                    'holdLocked', 'eventAdvances', 'pixelsDiffer'):
            value[key] = True
        for key in ('physicalNvidiaExecuted', 'gpuRenderingVerified', 'actualNvidiaVideoGenerated',
                    'imageBuilt', 'productionSourcesModified', 'videoQualityApproved', 'productionRenderAllowed'):
            value[key] = False
        return value

    def test_archived_manifest_and_original_auditor_frozen_without_retargeting_new_commit(self):
        with patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40}):
            manifest = ci.frozen_manifest()
            module = ci.frozen_ci()
            self.assertEqual(module.generate_manifest(), manifest)
            self.assertEqual(module.generate_manifest()['sourceCommit'], ci.SOURCE)
            self.assertEqual(len(module.extensions()), 57)
            self.assertEqual(module.extensions()['repo/' + ci.NAMESPACE + '/REFERENCE_FILES.json'], ci.MANIFEST_SHA)
        self.assertEqual(ci.sha(ci.LANE / 'ci.py'), ci.AUDITOR_SHA)

    def test_local_runtime_and_parent_source_hashes_match_published_image(self):
        report = ci.verify_checkout_sources()
        self.assertEqual(report['frozenHashes'], 56)
        self.assertEqual(report['status'], 'PASS')

    def test_exact_two_pngs_are_required_and_unknown_files_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            records = self.pngs(root)
            self.assertEqual([row['file'] for row in records], ['A_100.png', 'E_100.png'])
            (root / 'diagnostic.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'EXACT_TWO_CAMERA_PNGS_REQUIRED'):
                ci.collect_pngs(root)

    def test_symlink_hardlink_dimensions_and_size_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.pngs(root)
            first = root / 'A_100.png'
            second = root / 'E_100.png'
            second.unlink()
            second.symlink_to(first)
            with self.assertRaisesRegex(RuntimeError, 'UNSAFE_CAMERA_PNG'):
                ci.collect_pngs(root)
            second.unlink()
            os.link(first, second)
            with self.assertRaisesRegex(RuntimeError, 'UNSAFE_CAMERA_PNG'):
                ci.collect_pngs(root)
            second.unlink()
            second.write_bytes(b'x' * 40)
            with self.assertRaisesRegex(RuntimeError, 'CAMERA_PNG_DIMENSIONS_REQUIRED'):
                ci.collect_pngs(root)
            second.write_bytes(b'x')
            with self.assertRaisesRegex(RuntimeError, 'UNSAFE_CAMERA_PNG'):
                ci.collect_pngs(root)

    def test_actual_software_report_rejects_hardware_claims_wrong_source_and_subpixel_delta(self):
        with tempfile.TemporaryDirectory() as folder:
            records = self.pngs(Path(folder))
            valid = self.report(records)
            ci.validate_probe_report(valid, records)
            for key in ('physicalNvidiaExecuted', 'gpuRenderingVerified', 'imageBuilt', 'productionRenderAllowed'):
                wrong = copy.deepcopy(valid)
                wrong[key] = True
                with self.assertRaisesRegex(RuntimeError, 'ACTUAL_TEST_ONLY_CAMERA_PROOF_REQUIRED'):
                    ci.validate_probe_report(wrong, records)
            for delta in (0, 1, True, float('inf'), float('nan')):
                wrong = copy.deepcopy(valid)
                wrong['actualCameraDeltaPixels'] = delta
                with self.assertRaisesRegex(RuntimeError, 'ACTUAL_CAMERA_DELTA_GREATER_THAN_ONE_PIXEL_REQUIRED'):
                    ci.validate_probe_report(wrong, records)
            wrong = copy.deepcopy(valid)
            wrong['sourceVerification']['manifestSha256'] = 'b' * 64
            with self.assertRaisesRegex(RuntimeError, 'IMMUTABLE_PROBE_SOURCE_VERIFICATION_REQUIRED'):
                ci.validate_probe_report(wrong, records)

    def test_png_report_must_bind_exact_download_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            records = self.pngs(Path(folder))
            report = self.report(records)
            report['files'][0]['sha256'] = 'b' * 64
            with self.assertRaisesRegex(RuntimeError, 'ACTUAL_CAMERA_PNG_HASH_BINDING_REQUIRED'):
                ci.validate_probe_report(report, records)

    def test_container_mounts_only_external_test_tool_and_has_no_gpu_or_package_overlay(self):
        command = ci.probe_command(Path('/tmp/camera-output'))
        self.assertIn('--user=1000:1000', command)
        self.assertIn('--network=none', command)
        self.assertIn('--restart=no', command)
        self.assertEqual(command[-2:], [ci.IMAGE, '/__ci/camera_hold_followup.mjs'])
        self.assertFalse(any('--gpus' in item or 'target=/opt/' in item for item in command))
        self.assertTrue(any('target=/__ci/camera_hold_followup.mjs,readonly' in item for item in command))

    def test_public_evidence_contains_only_two_pngs_and_sha_while_diagnostics_stay_outside(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}):
            root = Path(folder)
            records = self.pngs(root)
            value = {'status': 'REFERENCE_CAMERA_HOLD_CPU_SOFTWARE_VERIFIED_HARDWARE_PENDING',
                     'actualCameraSoftwareProbe': {'pngRoot': str(root), 'pngs': records, 'report': self.report(records)}}
            paths = ci.evidence_paths(value)
            public = {path.rsplit('/', 1)[-1] for path in paths if '/public-review/' in path}
            self.assertEqual(public, {'A_100.png', 'E_100.png', 'SHA256SUMS'})
            self.assertEqual(len(paths), 4)
            self.assertEqual(sum(path.endswith('/result.json') for path in paths), 1)
            value['status'] = 'REFERENCE_CAMERA_FOLLOWUP_BLOCKED'
            self.assertEqual(len(ci.evidence_paths(value)), 1)

    def test_image_provenance_uses_original_image_commit_not_followup_commit(self):
        facts = {'Id': ci.CONFIG_DIGEST, 'Os': 'linux', 'Architecture': 'amd64', 'RepoDigests': [ci.IMAGE],
                 'Config': {'Entrypoint': ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '/opt/world-engine-storage-fix/launch.py'],
                 'Labels': {'world-engine.reference-v2.source-revision': ci.SOURCE,
                 'world-engine.reference-v2.parent-digest': 'sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae'}}}
        with patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40}):
            self.assertEqual(ci.validate_image_facts(facts)['imageSourceCommit'], ci.SOURCE)
        facts['Config']['Labels']['world-engine.reference-v2.source-revision'] = 'a' * 40
        with self.assertRaisesRegex(RuntimeError, 'IMMUTABLE_CAMERA_IMAGE_PROVENANCE_REQUIRED'):
            ci.validate_image_facts(facts)


if __name__ == '__main__':
    unittest.main()
