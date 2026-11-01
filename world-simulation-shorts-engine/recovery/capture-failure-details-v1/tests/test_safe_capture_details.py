import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / 'codex-to-gcube-handoff-v1/controller/safe_capture_export.py'
spec = importlib.util.spec_from_file_location('safe_export', MODULE)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class SafeCaptureDetails(unittest.TestCase):
    def export(self, failure, *, cleanup=True, receipt=True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        job = root / 'job'
        capture = job / 'capture'
        capture.mkdir(parents=True, mode=0o700)
        os.chmod(job, 0o700)
        def write(path, body):
            path.write_text(json.dumps(body))
            path.chmod(0o600)
        write(job / 'LEASE_SUPERVISOR_RESULT.json', {'cleanupVerified': cleanup, 'reason': 'GCUBE_CAPTURE_RUNTIME_FAILED'})
        write(job / 'FIRST_CAPTURE_FAILURE.json', {'code': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'stage': 'RENDER_RUNTIME'})
        if receipt:
            write(capture / 'CAPTURE_RECEIPT.json', {'durationSeconds': 10, 'totalFrames': 300, 'renderedFrames': 0,
                  'nvidiaVerified': False, 'failure': failure})
        destination = root / 'export'
        result = exporter.export_failure(job, destination)
        wire = (destination / 'CAPTURE_DIAGNOSTIC.json').read_bytes()
        self.assertEqual(result['sha256'], hashlib.sha256(wire).hexdigest())
        self.assertEqual(json.loads(wire), result['diagnostic'])
        return result['diagnostic'], wire.decode()

    def test_wrapped_reviewed_domain_code_and_stage_survive(self):
        raw = 'page.evaluate: Error: UP2_WEBGL2_REQUIRED\n    at https://private.example/secret.js:3:4'
        payload, wire = self.export({'code': raw, 'diagnosticStage': 'PAGE_EVALUATE_FIRST_NATIVE_DRAW'})
        detail = payload['capture']['failure']
        self.assertEqual(detail['code'], 'UP2_WEBGL2_REQUIRED')
        self.assertEqual(detail['exceptionType'], 'Error')
        self.assertEqual(detail['reason'], 'DOMAIN_ERROR')
        self.assertEqual(detail['diagnosticStage'], 'PAGE_EVALUATE_FIRST_NATIVE_DRAW')
        self.assertNotIn('private.example', wire)
        self.assertEqual(detail['messageSHA256'], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(payload['schema'], 'WORLD_ENGINE_CAPTURE_DIAGNOSTIC_SAFE_V3')
        self.assertEqual(payload['capture']['code'], 'UNCLASSIFIED_EXCEPTION')
        self.assertEqual(payload['capture']['messageCategory'], 'PAGE_EVALUATION')

    def test_type_error_reason_survives_without_property_or_stack(self):
        raw = "page.evaluate: TypeError: Cannot read properties of undefined (reading 'OWNER_TOKEN_SECRET')\n at /var/private/path"
        payload, wire = self.export({'code': raw, 'diagnosticStage': 'PAGE_EVALUATE_FRAME_CAPTURE', 'frameIndex': 299})
        detail = payload['capture']['failure']
        self.assertEqual(detail['exceptionType'], 'TypeError')
        self.assertEqual(detail['reason'], 'UNDEFINED_PROPERTY_READ')
        self.assertEqual(detail['frameIndex'], 299)
        self.assertEqual(detail['message'], 'page.evaluate: TypeError: [REDACTED]')
        self.assertNotIn('OWNER_TOKEN_SECRET', wire)
        self.assertNotIn('/var/private', wire)

    def test_unknown_secrets_and_uppercase_identifiers_never_leave(self):
        raw = 'page.evaluate: Error: OWNER_CODE_SECRET_992645\nBearer xyzSECRET123\nhttps://user:password@host/private?token=abc\nC:\\private\\token'
        payload, wire = self.export({'code': raw, 'diagnosticStage': 'SECRET_STAGE', 'frameIndex': True})
        detail = payload['capture']['failure']
        self.assertEqual(detail['code'], 'UNCLASSIFIED_EXCEPTION')
        self.assertEqual(detail['reason'], 'UNCLASSIFIED')
        self.assertIsNone(detail['diagnosticStage'])
        self.assertIsNone(detail['frameIndex'])
        for secret in ('992645', 'xyzSECRET123', 'password', 'SECRET_STAGE', 'token=abc', 'C:\\private'):
            self.assertNotIn(secret, wire)

    def test_import_reason_has_no_module_url(self):
        raw = 'page.evaluate: TypeError: Failed to fetch dynamically imported module: https://private.example/file?token=secret'
        payload, wire = self.export({'code': raw, 'diagnosticStage': 'PAGE_EVALUATE_RUNTIME_IMPORT'})
        self.assertEqual(payload['capture']['failure']['reason'], 'MODULE_IMPORT_FAILED')
        self.assertNotIn('private.example', wire)
        self.assertNotIn('token=secret', wire)

    def test_original_plain_domain_and_legacy_fields_are_preserved(self):
        payload, _ = self.export({'code': 'UP2_BLACK_FRAME', 'diagnosticStage': None})
        self.assertEqual(payload['capture']['code'], 'UP2_BLACK_FRAME')
        self.assertEqual(payload['capture']['failure']['code'], 'UP2_BLACK_FRAME')
        self.assertEqual(payload['firstFailure'], {'code': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'stage': 'RENDER_RUNTIME', 'unrecognizedCode': False})
        self.assertEqual(payload['supervisor'], {'reason': 'GCUBE_CAPTURE_RUNTIME_FAILED', 'cleanupVerified': True})

    def test_missing_receipt_stays_missing(self):
        payload, _ = self.export(None, receipt=False)
        self.assertIsNone(payload['capture']['failure'])
        self.assertTrue(payload['missingEvidence']['capture'])

    def test_cleanup_gate_is_unchanged(self):
        with self.assertRaisesRegex(ValueError, '^DIAGNOSTIC_VERIFIED_CLEANUP_REQUIRED$'):
            self.export({'code': 'UP2_BLACK_FRAME'}, cleanup=False)

    def test_message_bound_and_nonstring_input(self):
        raw = 'page.evaluate: RangeError: ' + 'SENSITIVE' * 1000
        detail = exporter.safe_capture_failure({'code': raw, 'frameIndex': 300}, total_frames=300)
        self.assertEqual(detail['messageSHA256'], hashlib.sha256(raw[:4000].encode()).hexdigest())
        self.assertLess(len(detail['message']), 160)
        self.assertIsNone(detail['frameIndex'])
        self.assertIsNone(exporter.safe_capture_failure({'code': {'secret': 'do-not-export'}}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
