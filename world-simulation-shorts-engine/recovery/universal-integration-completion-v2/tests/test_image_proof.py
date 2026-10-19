from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_completion_image_test', HERE / 'image_proof.py')
image = importlib.util.module_from_spec(spec); spec.loader.exec_module(image)


def synthetic():
    return {'schema': 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1', 'imageDigest': 'sha256:' + 'a'*64,
        'sourceManifestSHA256': 'b'*64, 'sourceCommit': 'c'*40,
        'independentPullVerified': True, 'sourceHashesVerified': True,
        'baseDigest': image.BASE_IMAGE, 'result': 'PASS'}


class ImageProofTests(unittest.TestCase):
    def test_strict_synthetic_receipt_not_a_real_build_claim(self):
        value = synthetic()
        self.assertEqual(image.validate(value, source_manifest_sha256='b'*64,
                                      image_digest='sha256:'+'a'*64), value)

    def test_unverified_or_wrong_bound_source_image_rejected(self):
        for key, value in [('independentPullVerified', False), ('sourceHashesVerified', False),
                           ('result', 'SKIP'), ('baseDigest', 'sha256:'+'d'*64),
                           ('imageDigest', image.BASE_IMAGE), ('approved', True)]:
            with self.subTest(key=key):
                document = synthetic(); document[key] = value
                with self.assertRaises(RuntimeError): image.validate(document)
        with self.assertRaises(RuntimeError): image.validate(synthetic(), source_manifest_sha256='d'*64)
        with self.assertRaises(RuntimeError): image.validate(synthetic(), image_digest='sha256:'+'d'*64)

    def test_missing_proof_never_claims_image_included(self):
        with tempfile.TemporaryDirectory(dir=HERE.parents[2]) as directory:
            production = Path(directory); production.chmod(0o700)
            control = production/'universal-integration-completion-v2/universal-integration-v1'
            control.mkdir(mode=0o700, parents=True)
            self.assertIsNone(image.read(control, source_manifest_sha256='b'*64, image_digest='sha256:'+'a'*64))

    def test_private_proof_exact_identity_and_public_mode_rejection(self):
        with tempfile.TemporaryDirectory(dir=HERE.parents[2]) as directory:
            production = Path(directory); production.chmod(0o700)
            control = production/'universal-integration-completion-v2/universal-integration-v1'
            control.mkdir(mode=0o700, parents=True)
            file = production/'completion_image_proof.json'
            file.write_text(json.dumps(synthetic())); file.chmod(0o600)
            self.assertEqual(image.read(control, source_manifest_sha256='b'*64,
                image_digest='sha256:'+'a'*64), synthetic())
            file.chmod(0o644)
            with self.assertRaises(RuntimeError): image.read(control, source_manifest_sha256='b'*64,image_digest='sha256:'+'a'*64)

    def test_bootstrap_installs_without_rewriting_existing_operator_data(self):
        calls=[]
        class Owner:
            def _private_file(*args): calls.append(args)
        with tempfile.TemporaryDirectory(dir=HERE.parents[2]) as directory:
            self.assertFalse(image.install(None, {'root':Path(directory)}, 'b'*64, Owner))
            self.assertTrue(image.install(json.dumps(synthetic()), {'root':Path(directory)}, 'b'*64, Owner))
        self.assertEqual(len(calls),1); self.assertEqual(calls[0][0].name,'completion_image_proof.json')


if __name__=='__main__': unittest.main()
