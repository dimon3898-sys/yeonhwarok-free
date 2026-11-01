"""CPU-only checks of newly added safe failure metadata; never launch a child."""
import errno
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import capture_environment_runner_v2 as runner


class RunnerErrorMetadataTests(unittest.TestCase):
    def test_permission_failure_retains_only_stage_type_and_errno(self):
        result = runner.safe_exception(PermissionError(errno.EACCES, 'OWNER=secret-token', '/private/credential'), 'WORKER_ENV_READ')
        self.assertEqual(result['code'], 'DIAG_ENVIRONMENT_LAUNCH_FAILED')
        self.assertEqual(result['diagnosticStage'], 'WORKER_ENV_READ')
        self.assertEqual(result['exceptionType'], 'PermissionError')
        self.assertEqual((result['errno'], result['errnoName']), (13, 'EACCES'))
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('/private', json.dumps(result))

    def test_main_marks_source_read_before_generic_exception(self):
        args = SimpleNamespace(approved_single_diagnostic=True)
        with patch.object(Path, 'read_bytes', side_effect=FileNotFoundError(errno.ENOENT, 'sensitive-path')):
            with self.assertRaises(FileNotFoundError) as failure:
                runner.main(args)
        result = runner.safe_exception(failure.exception, runner.diagnostic_stage)
        self.assertEqual(result['diagnosticStage'], 'SOURCE_PIN')
        self.assertEqual(result['exceptionType'], 'FileNotFoundError')
        self.assertEqual(result['errnoName'], 'ENOENT')
        self.assertNotIn('sensitive', json.dumps(result))

    def test_child_metadata_survives_filter_without_open_strings(self):
        result = runner.safe_exception(OSError(errno.EIO, 'raw-sensitive-message'), 'CHILD_WAIT')
        filtered = runner.safe_stdout(json.dumps(result).encode())
        self.assertEqual(filtered, result)
        bad = {'status': 'BLOCKED', 'diagnosticStage': '/private', 'exceptionType': 'OwnerSecret',
               'errno': 9999999, 'errnoName': 'SECRET', 'raw': 'token'}
        self.assertEqual(runner.safe_stdout(json.dumps(bad).encode()), {'status': 'BLOCKED'})


if __name__ == '__main__':
    unittest.main()
