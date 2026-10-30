"""New read-only label variant packaging tests; historical generator never runs."""
from pathlib import Path
from contextlib import redirect_stdout
from unittest import mock
import builtins
import copy
import importlib.util
import io
import json
import runpy
import sys
import unittest

HERE = Path(__file__).resolve().parent
HANDOFF = HERE.parent / 'codex-to-gcube-handoff-v1'
BUILDER = HANDOFF / 'backend/build_variants.py'
VARIANTS = HANDOFF / 'backend/GENERATED_SOURCE_MANIFEST.json'
RUNTIME = HANDOFF / 'RUNTIME_SOURCE_MANIFEST.json'
spec = importlib.util.spec_from_file_location('new_label_variant_builder', BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
original_read_text = Path.read_text


def metadata_override(file, value):
    """Override one metadata read in memory without changing pinned files."""
    def read_text(path, *args, **kwargs):
        if path == file:
            return json.dumps(value)
        return original_read_text(path, *args, **kwargs)
    return mock.patch.object(Path, 'read_text', read_text)


class NewVariantLinkage(unittest.TestCase):
    def test_01_actual_read_only_cli_checks_committed_derivation(self):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', [str(BUILDER), '--verify-existing']), redirect_stdout(output):
            runpy.run_path(str(BUILDER), run_name='__main__')
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['variantRows'], 3)
        self.assertTrue(result['runtimeDerivationMatches'])
        self.assertEqual(set(result['labelModuleSHA256']), {'presentation_labels.mjs', 'presentation_label_layer.mjs'})
        self.assertEqual(result['filesWritten'], 0)
        self.assertFalse(result['gpuExecuted'])
        self.assertEqual(result['historicalPatchRegeneration'], 'NOT_RUN')

    def test_02_verifier_succeeds_with_file_mutation_apis_blocked(self):
        original_open = builtins.open
        original_io_open = io.open
        def read_only_open(file, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wax+'):
                raise AssertionError('NEW_VERIFIER_WRITE_FORBIDDEN')
            return original_open(file, mode, *args, **kwargs)
        def read_only_io_open(file, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wax+'):
                raise AssertionError('NEW_VERIFIER_WRITE_FORBIDDEN')
            return original_io_open(file, mode, *args, **kwargs)
        patches = [mock.patch.object(Path, name, side_effect=AssertionError('NEW_VERIFIER_MUTATION_FORBIDDEN'))
                   for name in ['write_text', 'write_bytes', 'mkdir', 'touch', 'unlink', 'rename', 'replace', 'symlink_to']]
        with mock.patch('builtins.open', read_only_open), mock.patch('io.open', read_only_io_open):
            for patch in patches:
                patch.start()
            try:
                result = builder.verify_existing()
            finally:
                for patch in reversed(patches):
                    patch.stop()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['filesWritten'], 0)

    def test_03_stale_variant_sha_is_rejected(self):
        metadata = json.loads(VARIANTS.read_text())
        metadata['variants'][0]['variantSHA256'] = '0' * 64
        with metadata_override(VARIANTS, metadata):
            with self.assertRaisesRegex(RuntimeError, 'GCUBE_EXISTING_SOURCE_SHA_MISMATCH:capture_vulkan.generated.mjs'):
                builder.verify_existing()

    def test_04_duplicate_variant_is_rejected(self):
        metadata = json.loads(VARIANTS.read_text())
        metadata['variants'][1] = copy.deepcopy(metadata['variants'][0])
        with metadata_override(VARIANTS, metadata):
            with self.assertRaisesRegex(RuntimeError, 'GCUBE_EXISTING_VARIANT_SET_MISMATCH'):
                builder.verify_existing()

    def test_05_label_module_row_pin_is_rejected_when_tampered(self):
        metadata = json.loads(RUNTIME.read_text())
        row = next(row for row in metadata['files'] if row['path'].endswith('/presentation_label_layer.mjs'))
        row['sha256'] = '0' * 64
        with metadata_override(RUNTIME, metadata):
            with self.assertRaisesRegex(RuntimeError, 'GCUBE_LABEL_SOURCE_PIN_MISMATCH:presentation_label_layer.mjs'):
                builder.verify_existing()

    def test_06_missing_diagnostic_anchor_fails_closed(self):
        source = (builder.UP2 / 'presentation_runtime.mjs').read_text()
        anchor = 'inputTrace=null}={}){'
        self.assertEqual(source.count(anchor), 1)
        source = source.replace(anchor, 'inputTrace=null,unreviewedDiagnosticChange=true}={}){')
        with self.assertRaisesRegex(RuntimeError, 'GCUBE_VARIANT_UNIQUE_ANCHOR_REQUIRED:1:0'):
            builder.derive_runtime(source)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NewVariantLinkage)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'schema': 'WORLD_ENGINE_NEW_LABEL_VARIANT_LINKAGE_TESTS_V1',
                      'status': 'PASS' if result.wasSuccessful() else 'BLOCKED',
                      'newCases': result.testsRun,
                      'passed': result.testsRun - len(result.failures) - len(result.errors),
                      'failures': len(result.failures), 'errors': len(result.errors),
                      'historicalGeneratorExecuted': False, 'existingPASSReexecuted': False,
                      'imageBuilt': False, 'gpuExecuted': False}, sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
