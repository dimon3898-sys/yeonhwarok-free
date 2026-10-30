"""New 355-source packaging connection checks; never run legacy PASS suites."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('label_source_package', HERE / 'package_labels.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
CONTEXT_OUTPUT = None


class NewLabelPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='world-label-package-')
        cls.root = Path(cls.temp.name)
        cls.context = CONTEXT_OUTPUT or cls.root / 'context'
        cls.report = package.prepare(REPO, cls.context)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_01_actual_fixed_context_and_declared_entrypoint_readback(self):
        result = package.verify(REPO, self.context)
        self.assertEqual(result['runtimeSourceRows'], 355)
        self.assertEqual(result['contextFilesVerified'], 26)
        self.assertEqual(result['overlayFiles'], 25)
        self.assertEqual(result['contextReadback'], 'PASS')
        self.assertFalse(result['actualCandidateImageBuilt'])
        old = json.loads((REPO / (package.EVIDENCE + 'image-config.json')).read_text())['Entrypoint']
        entry = result['entrypoint']
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, entry)) if a != b], [10, 14])
        self.assertEqual(entry[10], package.PINS[package.STARTUP])
        self.assertEqual(entry[14], package.PINS[package.RUNTIME])
        text = (self.context / 'Dockerfile').read_text()
        self.assertTrue(text.startswith('FROM ' + package.PARENT + '\n'))
        self.assertEqual(len([line for line in text.splitlines() if line.startswith('COPY ')]), 25)
        self.assertFalse(any(line.startswith(('RUN ', 'USER ', 'ENV ', 'CMD ', 'WORKDIR '))
                             for line in text.splitlines()))
        evidence = HERE / 'evidence'
        evidence.mkdir(exist_ok=True)
        (evidence / 'CONTEXT_PLAN.json').write_text(json.dumps(result, indent=2) + '\n')
        (evidence / 'Dockerfile.preview').write_text(text)

    def test_02_inherited_333_sources_never_read(self):
        original = package.read_file
        current = package.rows(json.loads((REPO / package.RUNTIME).read_text()), 355)
        previous = package.rows(json.loads((REPO / (package.EVIDENCE + 'RUNTIME_SOURCE_MANIFEST.json')).read_text()), 353)
        inherited = {name for name, row in current.items() if row == previous.get(name)}
        seen = []

        def guarded(file):
            name = Path(file).relative_to(REPO).as_posix()
            self.assertNotIn(name, inherited)
            seen.append(name)
            return original(file)

        with patch.object(package, 'read_file', guarded):
            result = package.plan(REPO)
        self.assertEqual(len(inherited), 333)
        self.assertEqual(result['inheritedSourceFilesRead'], 0)
        self.assertEqual(result['changedExistingRows'], 20)
        self.assertEqual(result['newLabelRows'], 2)
        self.assertEqual(len(seen), 28)  # five metadata files, bootstrap, 22 delta sources
        native = package.HANDOFF + 'backend/native_guard.mjs'
        self.assertIn(native, inherited)

    def test_03_fixed_manifest_pin_rejects_substitution_before_row_parsing(self):
        original = package.read_file

        def changed(file):
            raw = original(file)
            return raw + b'\n' if Path(file) == REPO / package.RUNTIME else raw

        with patch.object(package, 'read_file', changed):
            with self.assertRaisesRegex(RuntimeError, 'LABEL_PACKAGE_PIN_MISMATCH'):
                package.plan(REPO)

    def test_04_row_parser_rejects_duplicate_traversal_and_hash_cycles(self):
        original = json.loads((REPO / package.RUNTIME).read_text())
        for mutation, message in (
            (lambda v: v['files'].__setitem__(1, copy.deepcopy(v['files'][0])), 'DUPLICATE_SOURCE_PATH'),
            (lambda v: v['files'][0].update(path='world-simulation-shorts-engine/../escape'), 'ROW_INVALID'),
            (lambda v: v['files'][0].update(path=package.RUNTIME), 'HASH_CYCLE_FORBIDDEN'),
        ):
            value = copy.deepcopy(original)
            mutation(value)
            with self.assertRaisesRegex(RuntimeError, message):
                package.rows(value, 355)

    def test_05_new_overlay_source_tamper_rejected(self):
        original = package.read_file
        target = REPO / (package.REC + 'universal-presentation-v2/presentation_labels.mjs')

        def changed(file):
            raw = original(file)
            return raw + b'\n' if Path(file) == target else raw

        with patch.object(package, 'read_file', changed):
            with self.assertRaisesRegex(RuntimeError, 'OVERLAY_SOURCE_MISMATCH'):
                package.plan(REPO)

    def test_06_context_tamper_and_extra_file_rejected(self):
        target = self.context / 'Dockerfile'
        original = target.read_bytes()
        try:
            target.write_bytes(original + b'RUN forbidden\n')
            with self.assertRaisesRegex(RuntimeError, 'CONTEXT_FILE_MISMATCH'):
                package.verify(REPO, self.context)
        finally:
            target.write_bytes(original)
        extra = self.context / 'unexpected.txt'
        try:
            extra.write_text('non-sensitive synthetic extra')
            extra.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'UNEXPECTED_CONTEXT_FILE'):
                package.verify(REPO, self.context)
        finally:
            extra.unlink()

    def test_07_context_symlink_and_modes_rejected(self):
        link = self.context / 'synthetic-link'
        try:
            link.symlink_to(self.context / 'Dockerfile')
            with self.assertRaisesRegex(RuntimeError, 'SYMLINK_FORBIDDEN'):
                package.verify(REPO, self.context)
        finally:
            link.unlink()
        target = self.context / 'Dockerfile'
        try:
            target.chmod(0o666)
            with self.assertRaisesRegex(RuntimeError, 'FILE_MODE_INVALID'):
                package.verify(REPO, self.context)
        finally:
            target.chmod(0o644)

    def test_08_reused_or_overlapping_context_forbidden(self):
        with self.assertRaisesRegex(RuntimeError, 'FRESH_CONTEXT_REQUIRED'):
            package.prepare(REPO, self.context)
        with self.assertRaisesRegex(RuntimeError, 'SEPARATE_CONTEXT_REQUIRED'):
            package.prepare(REPO, REPO / 'never-created-label-context')
        self.assertFalse((REPO / 'never-created-label-context').exists())

    def test_09_source_symlink_ancestor_and_unbounded_file_forbidden(self):
        link = self.root / 'source-link'
        link.symlink_to(REPO, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'SYMLINK_FORBIDDEN'):
            package.plan(link)
        oversized = self.root / 'oversized'
        oversized.write_bytes(b'x' * (package.MAX_FILE + 1))
        with self.assertRaisesRegex(RuntimeError, 'BOUNDED_REGULAR_FILE_REQUIRED'):
            package.read_file(oversized)

    def test_10_new_packager_cannot_launch_process_or_network(self):
        # Inspect the complete AST, rather than trusting a success receipt flag.
        import ast
        tree = ast.parse((HERE / 'package_labels.py').read_text())
        imports = {alias.name.split('.')[0] for node in ast.walk(tree)
                   if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in (node.names if isinstance(node, ast.Import) else [])}
        imports.update(node.module.split('.')[0] for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom) and node.module)
        self.assertFalse(imports.intersection({'subprocess', 'socket', 'urllib', 'requests', 'http', 'os'}))
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in {'exec', 'eval', '__import__', 'compile'}
                             for node in ast.walk(tree)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context-output', type=Path)
    args = parser.parse_args()
    CONTEXT_OUTPUT = args.context_output

    class RecordedResult(unittest.TextTestResult):
        cases = []

        def addSuccess(self, test):
            super().addSuccess(test)
            self.cases.append({'name': test.id().split('.')[-1], 'status': 'PASS'})

        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.cases.append({'name': test.id().split('.')[-1], 'status': 'BLOCKED'})

        def addError(self, test, err):
            super().addError(test, err)
            self.cases.append({'name': test.id().split('.')[-1], 'status': 'BLOCKED'})

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NewLabelPackagingTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    report = {'schema': 'WORLD_ENGINE_NEW_LABEL_PACKAGE_TEST_RESULT_V1',
              'status': 'PASS' if result.wasSuccessful() else 'BLOCKED',
              'cases': result.cases, 'testsRun': result.testsRun,
              'existingPASSSuitesRun': 0, 'imageBuilds': 0, 'gpuRuns': 0,
              'actualCandidateOCIConfigVerified': False}
    (HERE / 'evidence' / 'NEW_CONTEXT_TEST_RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
