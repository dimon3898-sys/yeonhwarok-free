"""Actual frozen inputs and the new sidecar authority; no process can render."""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prepare = load('authority_actual_prepare', ROOT / 'prepare_source_preview.py')
authority = load('authority_actual_guard', ROOT / 'runtime_authority.py')


class ActualSidecarAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='overnight-authority-', dir='/workspace')
        cls.base = Path(cls.temp.name)
        cls.prepared = prepare.prepare(cls.base / 'template')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(prefix='case-', dir=self.base)
        self.addCleanup(self.temp_case.cleanup)
        self.directory = Path(self.temp_case.name) / 'inputs'
        shutil.copytree(self.base / 'template', self.directory)

    def verify(self):
        return authority.verify_runtime_sidecars(self.directory / 'OVERNIGHT_REQUEST.json', self.directory / 'PLAN.json')

    def modify(self, filename, change):
        path = self.directory / filename
        value = json.loads(path.read_bytes())
        change(value)
        path.write_text(json.dumps(value, ensure_ascii=False))

    def test_actual_prepared_normalized_source_range_and_image_parent_are_bound(self):
        value = self.verify()
        self.assertEqual(value['preview']['range']['frameCount'], 150)
        self.assertEqual(value['preview']['range']['startFrame'], 1400)
        self.assertEqual(value['preview']['range']['endFrame'], 1550)
        self.assertTrue(value['globalGPUAdmissionRequired'])
        self.assertFalse(value['rendererOutputVerified'])

    def test_capture_signature_tamper_is_rejected(self):
        self.modify('OVERNIGHT_REQUEST.json', lambda x: x.update(captureSignature='0' * 64))
        with self.assertRaisesRegex(RuntimeError, 'CAPTURE_SIGNATURE_CHANGED'):
            self.verify()

    def test_exact_old_capture_sidecar_is_required(self):
        self.modify('INTEGRATION_REQUEST.json', lambda x: x.update(imageDigest='sha256:' + 'f' * 64))
        with self.assertRaisesRegex(RuntimeError, 'PRESERVED_CAPTURE_REQUEST_CHANGED'):
            self.verify()

    def test_preview_sidecar_range_tamper_is_rejected(self):
        self.modify('PREVIEW_REQUEST.json', lambda x: x['range'].update(startFrame=0, endFrame=150))
        with self.assertRaisesRegex(RuntimeError, 'PREVIEW_FILE_CHANGED'):
            self.verify()

    def test_changed_history_object_cannot_keep_old_source_claims(self):
        self.modify('PLAN.json', lambda x: x['productionV3']['eventChapters'][0].update(title='UNSOURCED CHANGE'))
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_unexpected_authority_knob_and_symlink_are_rejected(self):
        self.modify('OVERNIGHT_REQUEST.json', lambda x: x.update(softwareRenderingAllowed=True))
        with self.assertRaisesRegex(RuntimeError, 'EXACT_CAPTURE_REQUEST'):
            self.verify()
        request = self.directory / 'OVERNIGHT_REQUEST.json'
        request.unlink()
        request.symlink_to(self.base / 'template/OVERNIGHT_REQUEST.json')
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
