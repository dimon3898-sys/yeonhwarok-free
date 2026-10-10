"""The additive release gate admits only sealed selector deltas and new assets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from deployment.gcube import bold_preflight as bold


class BoldReleaseHarnessV023(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(bold.MANIFEST.read_bytes())

    def test_all_original_runtime_and_1125_test_identities_stay_frozen(self):
        _, receipt = bold.verify_sources()
        self.assertEqual(receipt['protected_runtime_files'], 67)
        self.assertEqual(receipt['original_unique_tests'], 1125)
        self.assertEqual(len(self.value['inherited_core_ids']), 888)
        self.assertEqual(len(self.value['proxy_ids']), 206)
        self.assertEqual(len(self.value['diagnostic_ids']), 31)
        self.assertEqual(receipt['physical_gpu'], 'NOT_RUN')

    def test_parent_manifest_projection_changes_only_authorized_selector_rows(self):
        before = bold.parent_value()
        projected = bold.translated_parent_manifest(self.value)
        self.assertEqual({k: v for k, v in before.items() if k != 'runtime_records'},
                         {k: v for k, v in projected.items() if k != 'runtime_records'})
        changed = {a['path'] for a, b in zip(before['runtime_records'], projected['runtime_records']) if a != b}
        self.assertEqual(changed, {row['path'] for row in self.value['parent_deltas']})
        self.assertLessEqual(changed, bold.AUTHORIZED_PARENT_DELTAS)
        self.assertEqual(hashlib.sha256(bold.PARENT_MANIFEST.read_bytes()).hexdigest(),
                         self.value['parent_manifest_sha256'])

    def test_unsealed_authorized_ui_bytes_fail_before_parent_view(self):
        actual = Path.read_bytes
        target = bold.APP / 'web/app.js'
        def changed(path):
            raw = actual(path)
            return raw + b'\nUNAUTHORIZED_SOURCE' if path == target else raw
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'BOLD_SOURCE_CHANGED:web/app.js'):
                bold.verify_sources()

    def test_geometry_tamper_is_not_an_authorized_selector_delta(self):
        actual = Path.read_bytes
        target = bold.APP / 'web/infographic/v022/registry.json'
        def changed(path):
            raw = actual(path)
            return raw + b'\nGEOMETRY_TAMPER' if path == target else raw
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'BOLD_SOURCE_CHANGED:web/infographic/v022/registry.json'):
                bold.verify_sources()

    def test_context_restores_original_file_reads_and_subprocess_on_exception(self):
        original_read, original_run = Path.read_text, bold.subprocess.run
        actual_manifest = bold.PARENT_MANIFEST.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'BOLD_CONTEXT_TEST_EXIT'):
            with bold.parent_admission_view():
                projected = json.loads(bold.PARENT_MANIFEST.read_text())
                self.assertEqual(projected, bold.translated_parent_manifest(self.value))
                self.assertEqual(bold.PARENT_MANIFEST.read_bytes(), actual_manifest)
                raise RuntimeError('BOLD_CONTEXT_TEST_EXIT')
        self.assertIs(Path.read_text, original_read)
        self.assertIs(bold.subprocess.run, original_run)

    def test_parent_receipt_cannot_authorize_an_additional_runtime_path(self):
        forged = deepcopy(self.value)
        forged['parent_deltas'].append(dict(path='engine/infographic_backend.py', size=1, sha256='0' * 64))
        actual = Path.read_bytes
        def changed(path):
            return json.dumps(forged).encode() if path == bold.MANIFEST else actual(path)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'BOLD_PARENT_SCOPE_CHANGED'):
                bold.verify_sources()

    def test_child_cli_admission_rejects_another_script_without_execution(self):
        with self.assertRaisesRegex(AssertionError, 'BOLD_CHILD_SCRIPT_CHANGED'):
            bold.child_entrypoint("raise RuntimeError('MUST_NOT_EXECUTE')")

    def test_immutable_workflow_separates_gpu_and_preview_evidence(self):
        text = (bold.ROOT / '.github/workflows/gcube-bold-v023.yml').read_text()
        self.assertIn('push: false', text)
        self.assertIn('--pixels-only', text)
        self.assertIn('--regressions-only', text)
        self.assertIn('--env WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=V022_LEGACY', text)
        self.assertIn('Anonymous public pull', text)
        self.assertNotIn('--gpus', text)
        self.assertIn('GPU_HARDWARE_UNAVAILABLE', text)
        dockerfile = (bold.APP / 'deployment/gcube/Dockerfile.bold-v023').read_text()
        self.assertIn('@' + bold.PARENT_DIGEST, dockerfile)
        self.assertIn('WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE=BOLD_INFOGRAPHIC_V023', dockerfile)
        self.assertNotIn('NVIDIA_DRIVER_CAPABILITIES=', dockerfile)


if __name__ == '__main__':
    unittest.main()
