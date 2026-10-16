"""Focused integrity boundary; no GPU, old full suite or data acquisition."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('universal_file_verifier_tested', HERE / 'universal_files.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UniversalFiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='universal-files-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_regular_binary_bytes_preserved(self):
        value = b'\0\xff\x01original'
        (self.root / 'data.bin').write_bytes(value)
        self.assertEqual(module._bytes(self.root, 'data.bin'), value)

    def test_noncanonical_traversal_and_symlink_rejected(self):
        (self.root / 'target').write_bytes(b'original')
        (self.root / 'link').symlink_to(self.root / 'target')
        for name in ['../target', '/absolute', 'a//b', './target', 'a\\b', 'link']:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                module._bytes(self.root, name)

    def test_empty_missing_and_directory_cannot_be_hashed_as_runtime(self):
        (self.root / 'empty').touch()
        (self.root / 'directory').mkdir()
        for name in ['missing', 'empty', 'directory']:
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'REGULAR_SOURCE_REQUIRED'):
                module._bytes(self.root, name)

    def test_supplemental_copy_cannot_overwrite_an_existing_parent(self):
        manifest = {'schema': module.SCHEMA, 'additionalRepoFiles': {'old/source.py': 'a' * 64}}
        (self.root / 'UNIVERSAL_FILES.json').write_text(json.dumps(manifest))
        repo = self.root / 'repo'; (repo / 'old').mkdir(parents=True)
        with patch.object(module, 'HERE', self.root), patch.object(module, 'REPO', repo):
            self.assertEqual(module.check_supplemental_absent()['supplementalFilesAbsent'], 1)
            (repo / 'old/source.py').write_text('preserved')
            with self.assertRaisesRegex(RuntimeError, 'OVERWRITE_PARENT_FILE'):
                module.check_supplemental_absent()
        self.assertEqual((repo / 'old/source.py').read_text(), 'preserved')

    def test_frozen_reference_manifest_hash_is_required_before_parent_execution(self):
        root = self.root / module.PARENT_NAMESPACE
        root.mkdir(parents=True)
        (root / 'REFERENCE_FILES.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'FROZEN_REFERENCE_MANIFEST_CHANGED'):
            module.frozen_parent_files(self.root)

    def test_python_alias_is_same_strict_verifier(self):
        self.assertIs(module.verify_extension, module.verify_files)


if __name__ == '__main__':
    unittest.main()
