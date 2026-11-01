import ast
import io
import json
from pathlib import Path
import unittest
import capture_environment_runner as diagnostic


class DiagnosticPreparationTests(unittest.TestCase):
    def test_selects_keys_before_secret_values(self):
        stream = io.BytesIO(b'OWNER_CODE=never-retain\0PATH=/bin\0TOKEN=secret\0GPU_BACKEND=vulkan\0')
        result = diagnostic.selected_environment(stream, {'PATH', 'GPU_BACKEND'})
        self.assertEqual(result, {'PATH': '/bin', 'GPU_BACKEND': 'vulkan'})
        self.assertNotIn('secret', json.dumps(result))

    def test_extracts_original_controller_allowlist_without_execution(self):
        names = diagnostic.allowed_environment_names("def _runtime_environment(environ=None):\n names={'PATH','GPU_BACKEND'}\n raise AssertionError('must never execute')\n")
        self.assertEqual(names, {'PATH', 'GPU_BACKEND'})

    def test_closes_child_summary_string_fields(self):
        raw = json.dumps({'status': 'BLOCKED', 'code': 'secret /private', 'resultFile': '/private', 'contextAttempts': 100, 'owner': 'secret'}).encode()
        self.assertEqual(diagnostic.safe_stdout(raw), {'status': 'BLOCKED'})
        safe = diagnostic.safe_stdout(b'{"status":"BLOCKED","code":"DIAG_TEST_ERROR","contextAttempts":1,"renderedFrames":0,"providerStopRequired":true}')
        self.assertEqual(safe['code'], 'DIAG_TEST_ERROR')
        self.assertTrue(safe['providerStopRequired'])

    def test_runner_syntax_without_execution(self):
        ast.parse(Path(diagnostic.__file__).read_text())


if __name__ == '__main__':
    unittest.main()
