"""Only new profile/preparation integration; original CPU/provider suites are not repeated."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tested_activation_preparation',HERE/'prepare_activation.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)


class PreparationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='astra-active-prep-tests-',dir='/workspace')
        cls.root=Path(cls.temp.name)
        cls.before=(prep.ENGINE/'recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json').read_bytes()
        cls.result=prep.prepare_activation(cls.root)
        cls.activation=json.loads(Path(cls.result['activationFile']).read_text())
        cls.bundle=json.loads(Path(cls.activation['bundleManifestFile']).read_text())

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_real_existing_three_sources_prepare_without_replacing_scene(self):
        self.assertEqual(self.result['profileId'],'ASTRA_SOURCE_MATERIAL_V1')
        self.assertEqual(set(self.bundle['sources']),{'terrain','bathymetry','surfaceTexture'})
        self.assertTrue(all(x['status']=='available' and x['parts'] for x in self.bundle['sources'].values()))
        self.assertEqual(self.before,(prep.ENGINE/'recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json').read_bytes())
        self.assertEqual(hashlib.sha256(self.before).hexdigest(),self.activation['scenePlanByteSha256'])
        self.assertIs(self.result['gpuExecuted'],False)
        self.assertEqual(self.bundle['rendererPayloadSHA256'],self.activation['rendererPayloadSha256'])

    def test_full_profile_support_remains_partial_and_original_signed_values(self):
        self.assertTrue(all(x['coverage']['complete'] is False for x in self.bundle['sources'].values()))
        part=self.bundle['sources']['bathymetry']['parts'][0]
        self.assertEqual(part['quantity'],'SIGNED_ELEVATION');self.assertEqual(part['numericDtype'],'<i2')
        self.assertEqual(part['metadata']['positive'],'up')
        for source in self.bundle['sources'].values():
            for part in source['parts']:
                self.assertEqual(part['fallback'],'UNCHANGED_BASELINE_OUTSIDE_SOURCE_OR_INVALID')
        self.assertLess(self.bundle['artifactBytes'],64*1024*1024)

    def test_bundle_paths_hashes_and_private_files_are_exact(self):
        file=Path(self.result['activationFile'])
        self.assertEqual(file.stat().st_mode&0o777,0o600)
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),self.result['activationSha256'])
        manifest=Path(self.activation['bundleManifestFile'])
        self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(),self.result['bundleManifestSha256'])
        for artifact in self.bundle['artifacts']:
            value=manifest.parent/artifact['file']
            self.assertEqual(value.stat().st_size,artifact['bytes'])
            self.assertEqual(hashlib.sha256(value.read_bytes()).hexdigest(),artifact['sha256'])

    def test_unsupported_region_fails_without_success_activation_or_zero_padding(self):
        profile=json.loads(prep.PROFILE_FILE.read_text());profile['mapData']['bbox']=[-70,-40,-69,-39]
        with tempfile.TemporaryDirectory(prefix='astra-unavailable-',dir='/workspace') as d:
            base=Path(d);file=base/'profile.json';file.write_text(json.dumps(profile))
            with self.assertRaisesRegex(prep.ActivationError,'ACTIVATION_SOURCE_UNAVAILABLE'):
                prep.prepare_activation(base,file)
            self.assertEqual(list(base.rglob('activation.json')),[])

    def test_shared_or_symlink_work_root_is_refused_without_modifying_data(self):
        with tempfile.TemporaryDirectory(prefix='astra-root-refusal-',dir='/workspace') as d:
            base=Path(d);shared=base/'shared';shared.mkdir(mode=0o777);shared.chmod(0o777)
            with self.assertRaisesRegex(prep.ActivationError,'ACTIVATION_PRIVATE_ROOT_REQUIRED'):
                prep.prepare_activation(shared)
            self.assertEqual(list(shared.iterdir()),[])
            link=base/'link';link.symlink_to(self.root,target_is_directory=True)
            with self.assertRaisesRegex(prep.ActivationError,'ACTIVATION_PRIVATE_ROOT_REQUIRED'):
                prep.prepare_activation(link)

    def test_extension_manifest_rejects_modified_runtime_and_dependency(self):
        with tempfile.TemporaryDirectory(prefix='astra-manifest-test-',dir='/workspace') as d:
            root=Path(d);source=root/'code.py';source.write_text('immutable = True')
            manifest={'schema':prep.SCHEMA,'profileId':prep.PROFILE_ID,'files':{'code.py':hashlib.sha256(source.read_bytes()).hexdigest()},'repoDependencies':{},'inheritedFiles':[]}
            file=root/'ACTIVATION_FILES.json';file.write_text(json.dumps(manifest))
            with mock.patch.object(prep,'HERE',root),mock.patch.object(prep,'MANIFEST_FILE',file):
                report=prep.verify_extension(require_staged=False)
                self.assertIs(report['testOnly'],True)
                source.write_text('immutable = False')
                with self.assertRaisesRegex(prep.ActivationError,'ACTIVATION_EXTENSION_HASH_MISMATCH'):
                    prep.verify_extension(require_staged=False)


if __name__=='__main__': unittest.main()
