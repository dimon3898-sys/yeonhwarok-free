"""Focused V2 preparation/manifest checks. No GPU, downloads or old full suite."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reference_v2_preparation_test', HERE / 'prepare_ref2.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def manifest_for(root, files):
    tools = {}
    for name in q.TEST_FILES:
        tool = root / name
        tool.write_text('CPU_TEST_TOOL_HASH_FIXTURE_ONLY\n')
        tools[name] = hashlib.sha256(tool.read_bytes()).hexdigest()
    return {'schema': q.SCHEMA, 'profileId': q.PROFILE_ID, 'baselineCommit': q.BASELINE,
            'parentImage': q.PARENT_IMAGE, 'parentQualityManifestSha256': q.PARENT_MANIFEST_SHA,
            'sourceCommit': 'a' * 40, 'files': files, 'repoDependencies': {}, 'testFiles': tools}


class ReferencePreparationTests(unittest.TestCase):
    def test_actual_parent_quality_f_data_scene_and_bytes_preserved_in_separate_v2_activation(self):
        with tempfile.TemporaryDirectory(prefix='ref2-real-cpu-prepare-', dir='/workspace') as folder:
            Path(folder).chmod(0o700)
            result = q.prepare_activation(Path(folder))
            selected = Path(result['activationFile'])
            old = selected.parent / 'quality_activation_F.json'
            before = json.loads(old.read_text())
            after = json.loads(selected.read_text())
            old_bytes = old.read_bytes()
            self.assertNotEqual(selected, old)
            self.assertEqual(after.pop('referenceV2'), {'variant': 'F', 'parameters': {}})
            self.assertEqual(after.pop('profileId'), 'REFERENCE_VISUAL_MASTER_V2_F')
            self.assertEqual(before.pop('profileId'), 'VISUAL_QUALITY_UPGRADE_V1_F')
            self.assertEqual(after, before)
            self.assertEqual(after['quality'], {'profile': 'F'})
            self.assertEqual(result['bundleManifestSha256'], '02495857b20e92b75c5e4f9d60090e2e959b82c677053ef068024a7d5c63261f')
            self.assertEqual(result['artifactBytes'], 32115808)
            self.assertEqual(result['parameterValidation'], 'CANONICAL_JS_RUNTIME_REQUIRED')
            self.assertFalse(result['gpuExecuted'])
            self.assertEqual(stat.S_IMODE(selected.stat().st_mode), 0o600)
            self.assertEqual(hashlib.sha256(selected.read_bytes()).hexdigest(), result['activationSha256'])
            self.assertEqual(old.read_bytes(), old_bytes)

    def test_unknown_variant_or_unserializable_parameters_rejected_before_parent_data_processing(self):
        with patch.object(q.base, 'prepare_activation') as old:
            for variant in ('', 'G', 'FF', None, ['F']):
                with self.assertRaises(q.ActivationError):
                    q.prepare_activation(Path('/not-used'), variant=variant)
            for parameters in ([], 'not-an-object', {1: 1}, {'value': float('nan')}, {'oversize': 'x' * 20000}):
                with self.assertRaises(q.ActivationError):
                    q.prepare_activation(Path('/not-used'), parameters=parameters)
            old.assert_not_called()

    def test_inspection_variant_uses_old_f_base_and_preserves_overrides_without_python_normalizer(self):
        with tempfile.TemporaryDirectory(prefix='ref2-prep-variant-', dir='/workspace') as folder:
            root = Path(folder)
            old = root / 'quality_activation_F.json'
            payload = {'profileId': 'VISUAL_QUALITY_UPGRADE_V1_F', 'quality': {'profile': 'F'}, 'data': 'UNCHANGED'}
            old.write_text(json.dumps(payload))
            prepared = {'activationFile': str(old), 'activationSha256': hashlib.sha256(old.read_bytes()).hexdigest()}
            parameters = {'gainBrightness': 1.15, 'cameraReadHoldFrames': 11}
            with patch.object(q.base, 'prepare_activation', return_value=prepared) as parent:
                result = q.prepare_activation(root, variant='B', parameters=parameters)
            parent.assert_called_once_with(root, profile='F')
            actual = json.loads(Path(result['activationFile']).read_text())
            self.assertEqual(actual['referenceV2'], {'variant': 'B', 'parameters': parameters})
            self.assertEqual(actual['quality'], {'profile': 'F'})
            self.assertEqual(actual['profileId'], 'REFERENCE_VISUAL_MASTER_V2_B')
            self.assertEqual(json.loads(old.read_text()), payload)
            self.assertEqual(parameters, {'gainBrightness': 1.15, 'cameraReadHoldFrames': 11})

    def test_changed_parent_preparation_bytes_or_wrong_quality_base_rejected(self):
        with tempfile.TemporaryDirectory(prefix='ref2-parent-corruption-', dir='/workspace') as folder:
            root = Path(folder)
            old = root / 'quality_activation_F.json'
            old.write_text(json.dumps({'profileId': 'OTHER', 'quality': {'profile': 'A'}}))
            for digest, message in (('0' * 64, 'REFERENCE_PREPARED_SOURCE_CHANGED'),
                                   (hashlib.sha256(old.read_bytes()).hexdigest(), 'REFERENCE_QUALITY_F_BASE_REQUIRED')):
                with patch.object(q.base, 'prepare_activation', return_value={'activationFile': str(old), 'activationSha256': digest}):
                    with self.assertRaisesRegex(q.ActivationError, message):
                        q.prepare_activation(root)
            self.assertFalse((root / 'reference_v2_activation_F.json').exists())

    def test_new_manifest_cannot_hide_new_or_parent_hash_corruption(self):
        with tempfile.TemporaryDirectory(prefix='ref2-manifest-', dir='/workspace') as folder:
            root = Path(folder)
            source = root / 'runtime.mjs'
            source.write_text('export const reference=true;\n')
            manifest = manifest_for(root, {'runtime.mjs': hashlib.sha256(source.read_bytes()).hexdigest()})
            filename = root / 'REFERENCE_FILES.json'
            filename.write_text(json.dumps(manifest))
            with patch.object(q, 'HERE', root), patch.object(q, 'MANIFEST_FILE', filename), patch.object(q.base, 'verify_extension', return_value={'status': 'PASS', 'manifestSha256': q.PARENT_MANIFEST_SHA}) as parent:
                result = q.verify_extension(require_staged=False)
                self.assertTrue(result['testOnly'])
                self.assertFalse(result['gpuExecuted'])
                parent.assert_called_once()
                source.write_text('changed')
                with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_SOURCE_HASH_MISMATCH'):
                    q.verify_extension(require_staged=False)
                parent.return_value = {'status': 'PASS', 'manifestSha256': '0' * 64}
                with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_PARENT_MANIFEST_MISMATCH'):
                    q.verify_extension(require_staged=False)

    def test_manifest_parent_identity_dependency_hash_and_no_follow_paths_are_enforced(self):
        with tempfile.TemporaryDirectory(prefix='ref2-manifest-paths-', dir='/workspace') as folder:
            root = Path(folder)
            source = root / 'real'
            source.write_text('unchanged')
            (root / 'alias').symlink_to(source)
            filename = root / 'REFERENCE_FILES.json'
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with patch.object(q, 'HERE', root), patch.object(q, 'REPO', root), patch.object(q, 'MANIFEST_FILE', filename), patch.object(q.base, 'verify_extension', return_value={'status': 'PASS', 'manifestSha256': q.PARENT_MANIFEST_SHA}):
                for name in ('alias', '../real'):
                    filename.write_text(json.dumps(manifest_for(root, {name: digest})))
                    with self.assertRaises(q.ActivationError):
                        q.verify_extension(require_staged=False)
                manifest = manifest_for(root, {'real': digest})
                manifest['parentQualityManifestSha256'] = '0' * 64
                filename.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_MANIFEST_REQUIRED'):
                    q.verify_extension(require_staged=False)
                manifest['parentQualityManifestSha256'] = q.PARENT_MANIFEST_SHA
                manifest['repoDependencies'] = {'real': '0' * 64}
                filename.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_DEPENDENCY_HASH_MISMATCH'):
                    q.verify_extension(require_staged=False)

    def test_required_test_tools_cannot_be_omitted_changed_or_replaced_by_symlinks(self):
        with tempfile.TemporaryDirectory(prefix='ref2-test-tool-tamper-', dir='/workspace') as folder:
            root = Path(folder)
            source = root / 'runtime.mjs'
            source.write_text('RUNTIME_HASH_FIXTURE_ONLY\n')
            manifest = manifest_for(root, {'runtime.mjs': hashlib.sha256(source.read_bytes()).hexdigest()})
            filename = root / 'REFERENCE_FILES.json'
            with patch.object(q, 'HERE', root), patch.object(q, 'MANIFEST_FILE', filename), patch.object(q.base, 'verify_extension', return_value={'status': 'PASS', 'manifestSha256': q.PARENT_MANIFEST_SHA}):
                for invalid in (None, {}, {'unexpected.py': 'a' * 64}):
                    changed = {**manifest, 'testFiles': invalid}
                    filename.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_TEST_TOOL_MANIFEST_REQUIRED'):
                        q.verify_extension(require_staged=False)
                filename.write_text(json.dumps(manifest))
                self.assertEqual(q.verify_extension(require_staged=False)['files'], 6)
                tool = root / 'gain_ab_probe.mjs'
                tool.write_text('CORRUPTED_REQUIRED_TOOL\n')
                with self.assertRaisesRegex(q.ActivationError, 'REFERENCE_TEST_TOOL_HASH_MISMATCH'):
                    q.verify_extension(require_staged=False)
                tool.unlink()
                tool.symlink_to(source)
                with self.assertRaises(q.ActivationError):
                    q.verify_extension(require_staged=False)


if __name__ == '__main__':
    unittest.main()
