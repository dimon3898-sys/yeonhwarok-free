"""Reject unauthorized legacy-asset changes while admitting the pinned UI fix."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from deployment.gcube import asset_audit, visual_quality_preflight
from deployment.gcube import selection_preflight as selection


class SelectionReleaseAssetsV022(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = selection._actual_asset_audit()
        cls.container = len(cls.actual['assets']) == 83
        if len(cls.actual['assets']) not in (74, 83):
            raise AssertionError('Unexpected native/container asset inventory')
        cls.application = selection.record(selection.APP / 'web/app.js', selection.APP)

    def projection(self, audit=None, application=None, container=None):
        return selection.authorized_ui_asset_projection(
            deepcopy(self.actual if audit is None else audit),
            deepcopy(self.application if application is None else application),
            require_container_assets=self.container if container is None else container)

    def test_exact_delta_preserves_actual_bytes_and_complete_parent_identity(self):
        original = deepcopy(self.actual)
        baseline, proof = self.projection()
        self.assertEqual(self.actual, original)
        changed = [(before['path'], before['size'], after['size'])
                   for before, after in zip(original['assets'], baseline['assets']) if before != after]
        self.assertEqual(changed, [(selection.UI_ASSET_PATH, self.application['size'], 43729)])
        self.assertEqual(proof['actual_current_audit'], original)
        self.assertEqual(proof['authorized_asset_delta'][0]['actual_sha256'], self.application['sha256'])
        self.assertTrue(proof['only_authorized_ui_delta'])

    def test_other_parent_asset_hash_change_is_rejected(self):
        audit = deepcopy(self.actual)
        row = next(row for row in audit['assets'] if row['path'] == 'cinematic-world-map/assets/v3/earth/earth-day-8k.jpg')
        row['sha256'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'SELECTION_UNAUTHORIZED_PARENT_ASSET_DELTA'):
            self.projection(audit)

    def test_wrong_current_ui_hash_or_size_is_rejected(self):
        for field, value in (('sha256', '0' * 64), ('size', self.application['size'] + 1)):
            with self.subTest(field=field):
                audit = deepcopy(self.actual)
                next(row for row in audit['assets'] if row['path'] == selection.UI_ASSET_PATH)[field] = value
                with self.assertRaisesRegex(AssertionError, 'SELECTION_UI_ASSET_SOURCE_CHANGED'):
                    self.projection(audit)

    def test_application_record_cannot_authorize_another_file(self):
        application = dict(self.application, path='web/earth_adapter.js')
        with self.assertRaisesRegex(AssertionError, 'SELECTION_UI_ASSET_SCOPE_CHANGED'):
            self.projection(application=application)

    def test_missing_added_or_duplicate_asset_is_rejected(self):
        for operation in ('missing', 'added', 'duplicate'):
            with self.subTest(operation=operation):
                audit = deepcopy(self.actual)
                if operation == 'missing':
                    audit['assets'].pop()
                elif operation == 'added':
                    audit['assets'].append(dict(audit['assets'][0], path='unapproved.js'))
                else:
                    audit['assets'][0] = deepcopy(audit['assets'][1])
                with self.assertRaises(AssertionError):
                    self.projection(audit)

    def test_failed_or_unreadable_actual_audit_is_rejected(self):
        for operation in ('failed', 'unreadable'):
            with self.subTest(operation=operation):
                audit = deepcopy(self.actual)
                if operation == 'failed':
                    audit['passed'] = False
                else:
                    audit['assets'][0]['readable'] = False
                with self.assertRaises(AssertionError):
                    self.projection(audit)

    def test_native_container_inventory_cannot_be_mislabeled(self):
        with self.assertRaisesRegex(AssertionError, 'SELECTION_CURRENT_ASSET_INVENTORY_CHANGED'):
            self.projection(container=not self.container)

    def test_context_uses_new_ui_expectation_and_restores_actual_auditors(self):
        asset_function = asset_audit.audit_assets
        source_function = visual_quality_preflight.audit_frozen_sources
        constants = deepcopy(visual_quality_preflight.FROZEN_SOURCES)
        with selection.authorized_ui_asset_view(require_container_assets=self.container) as proof:
            report = visual_quality_preflight.audit_frozen_sources()
            self.assertTrue(report['passed'])
            row = next(row for row in report['sources'] if row['file'] == selection.UI_ASSET_PATH)
            self.assertEqual(row['actual_sha256'], self.application['sha256'])
            self.assertEqual(row['expected_sha256'], self.application['sha256'])
            self.assertEqual(row['legacy_expected_sha256'], selection.BASE_UI_ASSET['sha256'])
            self.assertFalse(row['actual_unchanged'])
            self.assertTrue(row['authorized_delta'])
            self.assertFalse(proof['actual_legacy_frozen_source_audit']['passed'])
            self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)
        self.assertIs(asset_audit.audit_assets, asset_function)
        self.assertIs(visual_quality_preflight.audit_frozen_sources, source_function)
        self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)

    def test_context_keeps_other_original_source_hash_checks(self):
        original_read = Path.read_bytes
        target = selection.ROOT / 'cinematic-world-map/src/renderer_v3.js'
        constants = deepcopy(visual_quality_preflight.FROZEN_SOURCES)
        with selection.authorized_ui_asset_view(require_container_assets=self.container):
            def changed_read(path):
                data = original_read(path)
                return data + b'\nSOURCE_TAMPER' if path == target else data
            with patch.object(Path, 'read_bytes', changed_read):
                report = visual_quality_preflight.audit_frozen_sources()
            self.assertFalse(report['passed'])
            self.assertEqual([row['file'] for row in report['sources'] if not row['unchanged']],
                             ['cinematic-world-map/src/renderer_v3.js'])
            self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)

    def test_context_keeps_original_texture_dimension_checks(self):
        original_open = visual_quality_preflight.Image.open
        target = selection.ROOT / 'cinematic-world-map/assets/v3/earth/earth-day-8k.jpg'
        constants = deepcopy(visual_quality_preflight.FROZEN_SOURCES)
        with selection.authorized_ui_asset_view(require_container_assets=self.container):
            def changed_open(path, *args, **kwargs):
                source = original_open(path, *args, **kwargs)
                if Path(path) != target:
                    return source
                class WrongDimensions:
                    size = (8191, 4096)
                    def __enter__(self):
                        return self
                    def __exit__(self, *unused):
                        source.close()
                return WrongDimensions()
            with patch.object(visual_quality_preflight.Image, 'open', changed_open):
                report = visual_quality_preflight.audit_frozen_sources()
            self.assertFalse(report['passed'])
            self.assertEqual([row['file'] for row in report['dimensions'] if not row['unchanged']],
                             ['cinematic-world-map/assets/v3/earth/earth-day-8k.jpg'])
            self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)

    def test_context_rejects_ui_bytes_outside_frozen_selection_hash(self):
        original_read = Path.read_bytes
        target = selection.APP / 'web/app.js'
        constants = deepcopy(visual_quality_preflight.FROZEN_SOURCES)
        with selection.authorized_ui_asset_view(require_container_assets=self.container):
            def changed_read(path):
                data = original_read(path)
                return data + b'\nUI_TAMPER' if path == target else data
            with patch.object(Path, 'read_bytes', changed_read):
                with self.assertRaisesRegex(AssertionError, 'SELECTION_UI_ASSET_SOURCE_CHANGED'):
                    visual_quality_preflight.audit_frozen_sources()
            self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)

    def test_context_restores_auditors_after_exception(self):
        asset_function = asset_audit.audit_assets
        source_function = visual_quality_preflight.audit_frozen_sources
        constants = deepcopy(visual_quality_preflight.FROZEN_SOURCES)
        with self.assertRaisesRegex(RuntimeError, 'TEST_CONTEXT_FAILURE'):
            with selection.authorized_ui_asset_view(require_container_assets=self.container):
                raise RuntimeError('TEST_CONTEXT_FAILURE')
        self.assertIs(asset_audit.audit_assets, asset_function)
        self.assertIs(visual_quality_preflight.audit_frozen_sources, source_function)
        self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)
        original_read = Path.read_bytes
        target = selection.ROOT / 'cinematic-world-map/src/renderer_v3.js'
        with selection.authorized_ui_asset_view(require_container_assets=self.container):
            def failed_read(path):
                if path == target:
                    raise RuntimeError('TEST_AUDIT_READ_FAILURE')
                return original_read(path)
            with patch.object(Path, 'read_bytes', failed_read):
                with self.assertRaisesRegex(RuntimeError, 'TEST_AUDIT_READ_FAILURE'):
                    visual_quality_preflight.audit_frozen_sources()
            self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)
        self.assertIs(asset_audit.audit_assets, asset_function)
        self.assertIs(visual_quality_preflight.audit_frozen_sources, source_function)
        self.assertEqual(visual_quality_preflight.FROZEN_SOURCES, constants)


if __name__ == '__main__':
    unittest.main()
