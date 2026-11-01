"""New diagnostic overlay boundary checks; no Docker, browser, GPU or old suite."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


MODULE = Path(__file__).with_name('build_once.py')
SPEC = importlib.util.spec_from_file_location('capture_evidence_builder', MODULE)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
SOURCE_REPO = Path(sys.argv.pop(1)).resolve()


class DiagnosticOverlayBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='capture-evidence-overlay-')
        self.root = Path(self.temp.name)
        self.repo, self.context = self.root / 'repo', self.root / 'context'
        for name in (*BUILDER.SOURCES, *BUILDER.BASE_PINS, BUILDER.CAPTURE,
                     BUILDER.PRESENTATION, BUILDER.GENERATED, BUILDER.PROFILE):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE_REPO / name, path)

    def tearDown(self):
        self.temp.cleanup()

    def focus_record(self, plan):
        path = self.repo / (BUILDER.REC + 'capture-evidence-retention-v1/FOCUSED_RESULT.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        value = {'schema': 'WORLD_ENGINE_CAPTURE_EVIDENCE_FOCUSED_V1', 'status': 'PASS',
                 'sourceBaseCommit': BUILDER.BASE, 'allRequiredChecksPassed': True,
                 'focusedTestsPassed': 1, 'gpuExecutions': 0, 'oldPASSReruns': 0,
                 'overlay': plan['overlay']}
        path.write_bytes(BUILDER.encoded(value))
        return path, value

    def test_six_reviewed_files_and_focused_evidence_bind_to_same_bytes(self):
        plan = BUILDER.prepare(self.repo, self.context)
        self.assertEqual({r['path'] for r in plan['overlay']},
                         set(BUILDER.SOURCES) | set(BUILDER.BASE_PINS))
        self.assertEqual(plan['unchangedSourceRowsReused'], 352)
        recipe = (self.context / 'Dockerfile').read_text().splitlines()
        self.assertEqual(recipe[0], 'FROM ' + BUILDER.PARENT)
        self.assertEqual(sum(s.startswith('COPY ') for s in recipe), 6)
        self.assertFalse(any(s.startswith(('RUN ', 'ENV ', 'CMD ', 'USER ')) for s in recipe))
        self.assertEqual(json.loads(recipe[-1].removeprefix('ENTRYPOINT ')), plan['entrypoint'])
        self.assertEqual(plan['entrypoint'][:6], ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B'])
        self.focus_record(plan)
        proof = BUILDER.focused_validation(self.repo, plan)
        self.assertEqual(proof['focusedTestsPassed'], 1)

    def test_changed_source_after_review_is_rejected_before_context_creation(self):
        path = self.repo / BUILDER.SOURCES[2]
        path.write_bytes(path.read_bytes() + b'\n# unreviewed drift\n')
        with self.assertRaisesRegex(RuntimeError, '^APPROVED_DIAGNOSTIC_SOURCE_MISMATCH$'):
            BUILDER.prepare(self.repo, self.context)
        self.assertFalse(self.context.exists())

    def test_runtime_manifest_cannot_include_a_fourth_source_change(self):
        path = self.repo / BUILDER.RUNTIME
        value = json.loads(path.read_bytes())
        row = next(r for r in value['files'] if r['path'] not in BUILDER.SOURCES)
        row['sha256'] = '0' * 64
        path.write_bytes(BUILDER.encoded(value))
        with self.assertRaisesRegex(RuntimeError, '^EXACT_THREE_RUNTIME_ROWS_REQUIRED$'):
            BUILDER.prepare(self.repo, self.context)
        self.assertFalse(self.context.exists())

    def test_focus_result_for_other_bytes_cannot_authorize_build(self):
        plan = BUILDER.prepare(self.repo, self.context)
        path, value = self.focus_record(plan)
        value['overlay'][0]['sha256'] = '0' * 64
        path.write_bytes(BUILDER.encoded(value))
        with self.assertRaisesRegex(RuntimeError, '^FOCUSED_VALIDATION_BYTES_CHANGED$'):
            BUILDER.focused_validation(self.repo, BUILDER.prepare(self.repo, self.root / 'second-context'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
