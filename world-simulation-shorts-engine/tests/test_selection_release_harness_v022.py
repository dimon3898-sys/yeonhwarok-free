"""Admission harness stays isolated from real application and protected tests."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

from deployment.gcube import selection_preflight as selection
from deployment.mobile_server import MobileApplication
import test_codespaces_origin


class SelectionReleaseHarnessV022(unittest.TestCase):
    def test_legacy_fixture_adapter_preserves_real_create_and_original_dispatch_guards(self):
        fixture = test_codespaces_origin.CodespacesHTTPTests
        previous = fixture.setUp
        real_create = MobileApplication.create_project
        with selection.legacy_codespaces_fixture_view() as adapted:
            self.assertIs(adapted, fixture)
            case = fixture('test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin')
            case.setUp()
            try:
                self.assertIs(case.app.create_project.__func__, real_create)
                self.assertIs(case.app.create_project.__self__, case.app)
                self.assertIsInstance(case.app.check_profile_selection, Mock)
                self.assertIsInstance(case.app.check_revision_profile_selection, Mock)
                case.test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin()
                case.app.check_profile_selection.assert_called_once()
                case.app.check_revision_profile_selection.assert_called_once()
            finally:
                case.tearDown()
        self.assertIs(fixture.setUp, previous)
        self.assertIs(MobileApplication.create_project, real_create)

    def test_legacy_fixture_adapter_preserves_wrong_origin_before_dispatch(self):
        fixture = test_codespaces_origin.CodespacesHTTPTests
        with selection.legacy_codespaces_fixture_view():
            case = fixture('test_all_ten_post_endpoints_reject_wrong_origin_before_body_or_auth')
            case.setUp()
            try:
                case.test_all_ten_post_endpoints_reject_wrong_origin_before_body_or_auth()
                case.app.check_profile_selection.assert_not_called()
                case.app.check_revision_profile_selection.assert_not_called()
            finally:
                case.tearDown()

    def test_legacy_fixture_adapter_restores_setup_after_nested_context_and_exception(self):
        fixture = test_codespaces_origin.CodespacesHTTPTests
        previous = fixture.setUp
        with self.assertRaisesRegex(RuntimeError, 'TEST_ADAPTER_CONTEXT_EXCEPTION'):
            with selection.legacy_codespaces_fixture_view():
                outer = fixture.setUp
                with selection.legacy_codespaces_fixture_view():
                    self.assertIs(fixture.setUp, outer)
                    case = fixture('test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin')
                    case.setUp()
                    try:
                        self.assertIs(case.app.create_project.__func__, MobileApplication.create_project)
                        case.test_all_ten_post_endpoints_dispatch_with_exact_codespaces_origin()
                    finally:
                        case.tearDown()
                self.assertIs(fixture.setUp, outer)
                raise RuntimeError('TEST_ADAPTER_CONTEXT_EXCEPTION')
        self.assertIs(fixture.setUp, previous)

    def test_cli_and_canonical_import_share_real_auditors_in_nested_asset_tests(self):
        # Reproduce `python -m` before canonical import; this caught a CI-only
        # duplicate cache that had captured an already projected parent receipt.
        script = """
import importlib, json, runpy, sys, unittest
sys.argv = ['deployment.gcube.selection_preflight', '--manifest-only']
runpy.run_module('deployment.gcube.selection_preflight', run_name='__main__', alter_sys=True)
selection = importlib.import_module('deployment.gcube.selection_preflight')
package = importlib.import_module('deployment.gcube')
assert package.selection_preflight is selection
assert selection.sha.__module__ == '__main__'
actual = selection._actual_asset_audit()
ui = next(row for row in actual['assets'] if row['path'] == selection.UI_ASSET_PATH)
assert ui['sha256'] == selection.sha(selection.APP / 'web/app.js')
suite = unittest.TestLoader().discover('tests', pattern='test_selection_release_assets_v022.py')
with selection.authorized_ui_asset_view(require_container_assets=len(actual['assets']) == 83):
    result = unittest.TextTestRunner().run(suite)
assert result.testsRun == 12 and result.wasSuccessful() and not result.skipped
print(json.dumps({'cli_shared_module': True, 'nested_asset_tests': result.testsRun, 'passed': True}))
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=selection.APP,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        record = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(record, dict(cli_shared_module=True, nested_asset_tests=12, passed=True))

    def test_safe_failure_annotations_preserve_engine_location_and_hide_paths_messages(self):
        namespace = {}
        exec(compile("def fail():\n    raise FileExistsError(17, 'TOKEN=PRIVATE_VALUE', '/private/secret.wav')\n",
                     '/private/engine/audio.py', 'exec'), namespace)
        class ExpectedFailure(unittest.TestCase):
            def test_expected_failure(self):
                namespace['fail']()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExpectedFailure)
        expected = selection.identities(suite)
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(AssertionError, 'SELECTION_REGRESSION_FAILED'):
            selection.execute_suite(suite, expected, 'test-only-diagnostic')
        text = output.getvalue()
        self.assertNotIn('PRIVATE_VALUE', text)
        self.assertNotIn('/private', text)
        self.assertNotIn('secret.wav', text)
        rows = [json.loads(line.split('::', 2)[-1]) for line in text.splitlines()]
        self.assertEqual(rows[0]['safe_failure_records'], 1)
        self.assertEqual(rows[1]['exception_type'], 'FileExistsError')
        self.assertEqual(rows[1]['errno'], 17)
        self.assertIn(dict(file='audio.py', function='fail', line=2), rows[1]['python_runtime_locations'])


if __name__ == '__main__':
    unittest.main()
