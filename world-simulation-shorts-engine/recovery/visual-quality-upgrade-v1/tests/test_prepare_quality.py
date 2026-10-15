import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quality_preparation_test', HERE/'prepare_quality.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class QualityPreparationTests(unittest.TestCase):
    def test_real_parent_preparation_preserves_data_scene_and_separate_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder).chmod(0o700)
            result = q.prepare_activation(Path(folder))
            selected = Path(result['activationFile'])
            original = selected.parent/'activation.json'
            before = json.loads(original.read_text())
            after = json.loads(selected.read_text())
            self.assertNotEqual(selected, original)
            self.assertEqual(after.pop('quality'), {'profile':'F'})
            self.assertEqual(after.pop('profileId'), 'VISUAL_QUALITY_UPGRADE_V1_F')
            before.pop('profileId')
            self.assertEqual(after, before)
            self.assertEqual(result['bundleManifestSha256'], '02495857b20e92b75c5e4f9d60090e2e959b82c677053ef068024a7d5c63261f')
            self.assertEqual(result['artifactBytes'], 32115808)
            self.assertFalse(result['gpuExecuted'])
            self.assertEqual(stat.S_IMODE(selected.stat().st_mode), 0o600)
            self.assertEqual(hashlib.sha256(selected.read_bytes()).hexdigest(), result['activationSha256'])

    def test_unknown_profile_rejected_before_source_processing(self):
        with patch.object(q.base,'prepare_activation') as old:
            for profile in ('', 'G', 'FF', None, ['F']):
                with self.assertRaises(q.base.ActivationError):q.prepare_activation(Path('/not-used'), profile=profile)
            old.assert_not_called()

    def test_new_manifest_corruption_cannot_bypass_original_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'runtime.mjs';source.write_text('export const quality=true;\n')
            manifest={'schema':q.SCHEMA,'profileId':q.PROFILE_ID,'baselineCommit':q.BASELINE,
                      'parentImage':q.PARENT_IMAGE,'sourceCommit':'a'*40,
                      'files':{'runtime.mjs':hashlib.sha256(source.read_bytes()).hexdigest()},'repoDependencies':{}}
            f=root/'QUALITY_FILES.json';f.write_text(json.dumps(manifest))
            with patch.object(q,'HERE',root),patch.object(q,'MANIFEST_FILE',f),patch.object(q.base,'verify_extension',return_value={'status':'PASS','manifestSha256':q.PARENT_MANIFEST_SHA}) as parent:
                result=q.verify_extension(require_staged=False)
                self.assertTrue(result['testOnly']);parent.assert_called_once()
                source.write_text('changed')
                with self.assertRaisesRegex(q.base.ActivationError,'QUALITY_SOURCE_HASH_MISMATCH'):q.verify_extension(require_staged=False)
                parent.return_value={'status':'PASS','manifestSha256':'0'*64}
                with self.assertRaisesRegex(q.base.ActivationError,'QUALITY_PARENT_MANIFEST_MISMATCH'):q.verify_extension(require_staged=False)

    def test_new_manifest_cannot_bind_symlink_or_parent_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'real';source.write_text('unchanged')
            alias=root/'alias';alias.symlink_to(source)
            f=root/'QUALITY_FILES.json'
            manifest={'schema':q.SCHEMA,'profileId':q.PROFILE_ID,'baselineCommit':q.BASELINE,
                      'parentImage':q.PARENT_IMAGE,'sourceCommit':'a'*40,'repoDependencies':{}}
            with patch.object(q,'HERE',root),patch.object(q,'MANIFEST_FILE',f),patch.object(q.base,'verify_extension',return_value={'status':'PASS','manifestSha256':q.PARENT_MANIFEST_SHA}):
                for name in ('alias','../real'):
                    manifest['files']={name:hashlib.sha256(source.read_bytes()).hexdigest()};f.write_text(json.dumps(manifest))
                    with self.assertRaises(q.base.ActivationError):q.verify_extension(require_staged=False)


if __name__=='__main__':unittest.main()
