"""Focused new-overlay checks; no Docker, browser, network or old PASS suite."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


MODULE = Path(__file__).with_name('build_once.py')
SPEC = importlib.util.spec_from_file_location('surface_restore_builder', MODULE)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
SOURCE_REPO = Path(sys.argv.pop(1)).resolve()


class NewOverlayPackaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='surface-overlay-focus-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.context = self.root / 'context'
        for name in (*BUILDER.SOURCES, *BUILDER.BASE_PINS,
                     BUILDER.CAPTURE, BUILDER.PRESENTATION, BUILDER.GENERATED):
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE_REPO / name, target)

    def tearDown(self):
        self.temp.cleanup()

    def test_final_four_files_only_with_pinned_parent_and_startup(self):
        result = BUILDER.prepare(self.repo, self.context)
        self.assertEqual(set(r['path'] for r in result['overlay']),
                         {BUILDER.PROFILE, BUILDER.RUNTIME, BUILDER.BOOTSTRAP, BUILDER.STARTUP})
        self.assertEqual(result['changedSources'], [BUILDER.PROFILE])
        self.assertEqual(result['unchangedSourceRowsReused'], 354)
        text = (self.context / 'Dockerfile').read_text()
        self.assertEqual(text.splitlines()[0], 'FROM ' + BUILDER.PARENT)
        self.assertEqual(sum(line.startswith('COPY ') for line in text.splitlines()), 4)
        self.assertFalse(any(line.startswith(('RUN ', 'ENV ', 'CMD ', 'USER ')) for line in text.splitlines()))
        entry = json.loads(text.splitlines()[-1].removeprefix('ENTRYPOINT '))
        self.assertEqual(entry, result['entrypoint'])
        self.assertEqual(entry[:6], ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B'])

    def test_unrelated_runtime_row_mutation_is_rejected_before_context_creation(self):
        path = self.repo / BUILDER.RUNTIME
        value = json.loads(path.read_bytes())
        row = next(r for r in value['files'] if r['path'] != BUILDER.PROFILE)
        row['sha256'] = '0' * 64
        path.write_bytes(BUILDER.encoded(value))
        with self.assertRaisesRegex(RuntimeError, '^EXACT_ONE_RUNTIME_ROW_CHANGE_REQUIRED$'):
            BUILDER.prepare(self.repo, self.context)
        self.assertFalse(self.context.exists())

    def test_bootstrap_behavior_mutation_is_rejected(self):
        path = self.repo / BUILDER.BOOTSTRAP
        path.write_bytes(path.read_bytes() + b'\n# unrelated change\n')
        with self.assertRaisesRegex(RuntimeError, '^BOOTSTRAP_SINGLE_PIN_REQUIRED$'):
            BUILDER.prepare(self.repo, self.context)
        self.assertFalse(self.context.exists())

    def test_worker_pin_mutation_is_rejected(self):
        path = self.repo / BUILDER.STARTUP
        value = json.loads(path.read_bytes())
        value['files']['worker.py']['sha256'] = '0' * 64
        path.write_bytes(BUILDER.encoded(value))
        with self.assertRaisesRegex(RuntimeError, '^STARTUP_ONLY_REQUIRED_HASHES_CHANGED$'):
            BUILDER.prepare(self.repo, self.context)
        self.assertFalse(self.context.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
