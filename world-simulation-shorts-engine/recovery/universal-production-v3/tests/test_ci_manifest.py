"""Focused immutable-parent and source-file boundaries, using CPU bytes only."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('production_manifest_under_test', HERE / 'source_manifest.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class ProductionSourceManifest(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='production-manifest-tests-'); self.addCleanup(area.cleanup)
        self.root = Path(area.name)

    def test_regular_binary_source_bytes_are_not_normalized(self):
        raw = b'\0\xff\r\noriginal'; (self.root / 'sample.bin').write_bytes(raw)
        self.assertEqual(module.read_source(self.root, 'sample.bin'), raw)

    def test_noncanonical_traversal_and_symlinks_fail_before_source_use(self):
        (self.root / 'target').write_bytes(b'original'); (self.root / 'link').symlink_to(self.root / 'target')
        for name in ['../target', '/target', './target', 'a//target', 'a\\target', 'link', '']:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                module.read_source(self.root, name)

    def test_empty_directory_and_missing_are_never_accepted_as_sources(self):
        (self.root / 'empty').touch(); (self.root / 'directory').mkdir()
        for name in ['empty', 'directory', 'missing']:
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'BOUNDED_REGULAR_SOURCE'):
                module.read_source(self.root, name)

    def test_counterfeit_parent_manifest_fails_before_import_or_hash_updates(self):
        parent = self.root / module.PARENT_NAMESPACE; parent.mkdir(parents=True)
        (parent / 'UNIVERSAL_FILES.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'FROZEN_PARENT_MANIFEST_CHANGED'):
            module.parent_closure(self.root)

    def test_frozen_parent_source_tampering_is_rejected(self):
        original = module.read_source
        def changed(root, name):
            return b'TAMPERED_PARENT_BYTES' if name.endswith('/long_runtime.mjs') else original(root, name)
        with patch.object(module, 'read_source', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'FROZEN_PARENT_SOURCE_CHANGED'):
                module.parent_closure(module.REPO)

    def test_persisted_parent_closure_matches_exact_original_248_inventory(self):
        _, inherited = module.parent_closure(module.REPO)
        document = json.loads((HERE / 'PARENT_CLOSURE.json').read_text())
        self.assertEqual(document['additiveFiles'], inherited)
        self.assertEqual(document['originalReceiptFiles'] + document['inventoryMetadataFiles'] + len(inherited), 248)
        self.assertEqual(document['parentManifestSha256'], module.PARENT_MANIFEST_SHA)
        self.assertEqual(document['parentSourceCommit'], module.PARENT_SOURCE_COMMIT)

    def test_cli_and_runtime_call_the_same_strict_verifier(self):
        self.assertIs(module.verify_sources, module.verify_extension)


if __name__ == '__main__':
    unittest.main()
