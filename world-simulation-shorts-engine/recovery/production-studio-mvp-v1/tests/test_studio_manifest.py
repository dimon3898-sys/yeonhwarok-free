import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_test_studio_manifest', HERE / 'studio_manifest.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.files = ['bootstrap.py', 'server.py', 'studio_manifest.py', 'studio_runtime.py',
            'audio/ASSET_MANIFEST.json', 'audio/test.wav', 'RUNTIME_INVENTORY.json']
        self.tests = ['tests/probe.mjs']
        for name in [*self.files, *self.tests]:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'source-bytes')
        self.audio = {'assets': [{'file': 'test.wav', 'license': 'CC0-1.0', 'sha256': hashlib.sha256(b'source-bytes').hexdigest()}]}
        (self.root / 'audio/ASSET_MANIFEST.json').write_text(json.dumps(self.audio))
        self.freeze()
    def tearDown(self):
        self.temp.cleanup()
    def freeze(self):
        document = {'schema': 'WORLD_ENGINE_STUDIO_RUNTIME_INVENTORY_V1', 'files': sorted(self.files), 'testFiles': sorted(self.tests)}
        (self.root / m.INVENTORY_NAME).write_text(json.dumps(document))
        value = {'schema': m.SCHEMA, 'profileId': m.PROFILE_ID, 'sourceCommit': 'a' * 40,
            'baselineCommit': m.BASELINE, 'parentImage': m.PARENT_IMAGE, 'parentManifestSha256': m.PARENT_MANIFEST_SHA,
            'parentSourceCommit': m.PARENT_SOURCE_COMMIT, 'parentInventoryFiles': m.PARENT_INVENTORY_FILES,
            'files': {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in sorted(self.files)},
            'testFiles': {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in sorted(self.tests)}}
        (self.root / m.MANIFEST_NAME).write_text(json.dumps(value))
    def test_complete_exact_payload_passes_without_claiming_gpu(self):
        result = m.verify_payload(self.root)
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(result['gpuExecuted'])
        self.assertTrue(result['testOnly'])
    def test_changed_source_rejected(self):
        (self.root / 'server.py').write_bytes(b'different')
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_SHA_MISMATCH'):
            m.verify_payload(self.root)
    def test_extra_source_cannot_hide_outside_manifest(self):
        (self.root / 'unlisted.py').write_bytes(b'extra')
        with self.assertRaisesRegex(RuntimeError, 'UNEXPECTED_PAYLOAD_FILE'):
            m.verify_payload(self.root)
    def test_symlink_rejected_without_following_outside(self):
        (self.root / 'server.py').unlink(); (self.root / 'server.py').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(RuntimeError, 'SYMLINK_FORBIDDEN'):
            m.verify_payload(self.root)
    def test_parent_image_cannot_change(self):
        path = self.root / m.MANIFEST_NAME; value = json.loads(path.read_text()); value['parentImage'] = 'different'; path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, 'FROZEN_PARENT_PROVENANCE'):
            m.verify_payload(self.root)
    def test_traversal_and_absolute_paths_rejected(self):
        for name in ['../source', '/etc/passwd', 'audio/../test.wav', 'a\\b', './server.py']:
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, 'CANONICAL_SOURCE'):
                    m.read_source(self.root, name)
    def test_audio_file_omission_caught_before_build(self):
        self.files.remove('audio/test.wav'); self.freeze()
        with self.assertRaisesRegex(RuntimeError, 'AUDIO_ASSET_NOT_MANIFESTED'):
            m.inventory(self.root)
    def test_unverified_license_blocked(self):
        self.audio['assets'][0]['license'] = 'UNKNOWN'
        (self.root / 'audio/ASSET_MANIFEST.json').write_text(json.dumps(self.audio)); self.freeze()
        with self.assertRaisesRegex(RuntimeError, 'AUDIO_LICENSE_UNVERIFIED'):
            m.inventory(self.root)
    def test_corrupted_audio_cannot_be_frozen_as_valid_license_source(self):
        (self.root / 'audio/test.wav').write_bytes(b'damaged'); self.freeze()
        with self.assertRaisesRegex(RuntimeError, 'AUDIO_ASSET_SHA_MISMATCH'):
            m.inventory(self.root)
    def test_required_connected_service_not_optional(self):
        self.files.remove('server.py'); self.freeze()
        with self.assertRaisesRegex(RuntimeError, 'CONNECTED_RUNTIME_MUST_BE_BOUND'):
            m.inventory(self.root)
    def test_duplicate_or_unsorted_inventory_rejected(self):
        path = self.root / m.INVENTORY_NAME; value = json.loads(path.read_text()); value['files'] += ['server.py']; path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, 'SORTED_DISJOINT'):
            m.inventory(self.root)


if __name__ == '__main__':
    unittest.main()
